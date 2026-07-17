"""Context-aware final-surface control-language boundary.

The source request is classified before reply filtering and carried only in a
bounded in-memory context.  Machine receipts contain hashes and closed reason
codes, never the request or matched control text.  Unsafe fragments are
substituted independently so grounded neighboring facts survive.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Callable

from agent_voice_profiles import (
    canonical_speaker_ref,
    validate_voice_conformance,
    voice_boundary_fallback_for_speaker,
    voice_profile_ref_for_speaker,
)
from control_language_policy import (
    ControlLanguageClassification,
    classify_control_language,
    classify_technical_intent,
)


OUTPUT_BOUNDARY_SCHEMA_VERSION = "final_output_boundary_v1"
FLEET_VOICE_BOUNDARY_ENV_VAR = "OPENCLAW_FLEET_VOICE_BOUNDARY"
MAX_BOUNDED_SOURCE_REQUEST_CHARS = 512
CONTROL_SUBSTITUTION = (
    "I couldn't use an internal control instruction as the answer. "
    "Nothing was sent or changed."
)
RUNTIME_SUBSTITUTION = "I couldn't produce a fresh grounded answer just now."
CLASSIFIER_ERROR_SUBSTITUTION = (
    "I couldn't safely render that part of the answer just now. "
    "Nothing was sent or changed."
)

_LINE_SPLIT_RE = re.compile(r"(\n+)")
_CLAUSE_SPLIT_RE = re.compile(
    r"((?<=[.!?;,:])[ \t]+|[ \t]+(?:—|–|\|)[ \t]+)"
)


def _hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class OutputBoundaryContext:
    bounded_source_request: str
    source_request_sha256: str
    source_request_truncated: bool
    technical_intent: bool
    technical_intent_reason: str
    schema_version: str = OUTPUT_BOUNDARY_SCHEMA_VERSION

    @classmethod
    def from_source_request(
        cls,
        source_request: Any,
        *,
        technical_intent: bool | None = None,
    ) -> "OutputBoundaryContext":
        raw = str(source_request or "")
        decision = classify_technical_intent(raw)
        if isinstance(technical_intent, bool):
            is_technical = technical_intent
            reason = "explicit_adapter_override"
        else:
            is_technical = decision.is_technical
            reason = decision.reason_code
        return cls(
            bounded_source_request=raw[:MAX_BOUNDED_SOURCE_REQUEST_CHARS],
            source_request_sha256=_hash(raw),
            source_request_truncated=len(raw) > MAX_BOUNDED_SOURCE_REQUEST_CHARS,
            technical_intent=is_technical,
            technical_intent_reason=reason,
        )

    def to_machine_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_request_sha256": self.source_request_sha256,
            "source_request_truncated": self.source_request_truncated,
            "technical_intent": self.technical_intent,
            "technical_intent_reason": self.technical_intent_reason,
            "bounded_source_request_included": False,
        }


@dataclass(frozen=True, slots=True)
class OutputBoundaryReceipt:
    outcome: str
    source_request_sha256: str
    source_request_truncated: bool
    technical_intent: bool
    technical_intent_reason: str
    original_text_sha256: str
    visible_text_sha256: str
    fragment_count: int
    preserved_fragment_count: int
    replaced_fragment_count: int
    classifier_error_count: int
    reason_codes: tuple[str, ...]
    speaker_ref: str = "openclaw"
    voice_profile_ref: str = "agent_voice_profile:openclaw"
    voice_conformance_outcome: str = "not_checked"
    voice_checked_fragment_count: int = 0
    voice_replaced_fragment_count: int = 0
    raw_control_text_included: bool = False
    schema_version: str = OUTPUT_BOUNDARY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # Receipts cross JSON bridges and are compared before and after
        # serialization.  Keep the public machine shape JSON-native so an
        # unchanged receipt does not drift from tuple to list in transit.
        payload["reason_codes"] = list(self.reason_codes)
        return payload


@dataclass(frozen=True, slots=True)
class FinalOutputBoundaryResult:
    visible_text: str
    receipt: OutputBoundaryReceipt
    context: OutputBoundaryContext


Classifier = Callable[[str], ControlLanguageClassification]


def fleet_voice_boundary_enabled() -> bool:
    return os.environ.get(FLEET_VOICE_BOUNDARY_ENV_VAR, "1").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }


def split_output_fragments(text: Any) -> tuple[str, ...]:
    """Return clause-sized content and separator fragments without rewriting bytes."""

    pieces: list[str] = []
    for line_piece in _LINE_SPLIT_RE.split(str(text or "")):
        if not line_piece or _LINE_SPLIT_RE.fullmatch(line_piece):
            pieces.append(line_piece)
            continue
        stripped = line_piece.strip()
        json_shaped = (
            stripped.startswith("{") and stripped.endswith("}")
        ) or (
            stripped.startswith("[") and stripped.endswith("]")
        )
        if json_shaped:
            pieces.append(line_piece)
        else:
            pieces.extend(_CLAUSE_SPLIT_RE.split(line_piece))
    return tuple(pieces)


def _unsafe_for_context(
    classification: ControlLanguageClassification,
    context: OutputBoundaryContext,
) -> bool:
    if classification.always_suppress:
        return True
    return classification.is_control_language and not context.technical_intent


def _substitution_for(classification: ControlLanguageClassification) -> str:
    if classification.always_suppress:
        return CONTROL_SUBSTITUTION
    return RUNTIME_SUBSTITUTION


def render_final_output(
    text: Any,
    *,
    context: OutputBoundaryContext | None = None,
    classifier: Classifier = classify_control_language,
    speaker_ref: str = "openclaw",
) -> FinalOutputBoundaryResult:
    """Render one final answer while preserving every classified-safe fragment."""

    original = str(text or "")
    resolved_context = context or OutputBoundaryContext.from_source_request("")
    pieces = split_output_fragments(original)
    rendered: list[str] = []
    reasons: list[str] = []
    fragment_count = 0
    preserved_count = 0
    replaced_count = 0
    classifier_errors = 0
    voice_checked = 0
    voice_replaced = 0
    emitted_substitutions: set[str] = set()
    inline_unsafe_continuation = False
    speaker = canonical_speaker_ref(speaker_ref)
    voice_enabled = fleet_voice_boundary_enabled()

    for piece in pieces:
        if not piece or not piece.strip() or piece.strip() in {"—", "–", "|"}:
            rendered.append(piece)
            if "\n" in piece or piece.strip() in {"—", "–", "|"}:
                inline_unsafe_continuation = False
            continue
        try:
            classification = classifier(piece)
            if not isinstance(classification, ControlLanguageClassification):
                raise TypeError("classifier returned an invalid result")
        except Exception:
            fragment_count += 1
            classifier_errors += 1
            replaced_count += 1
            reasons.append("boundary_classifier_error")
            if CLASSIFIER_ERROR_SUBSTITUTION not in emitted_substitutions:
                rendered.append(CLASSIFIER_ERROR_SUBSTITUTION)
                emitted_substitutions.add(CLASSIFIER_ERROR_SUBSTITUTION)
            inline_unsafe_continuation = False
            continue
        if _unsafe_for_context(classification, resolved_context):
            if not inline_unsafe_continuation:
                fragment_count += 1
                replaced_count += 1
                reasons.extend(classification.reason_codes)
            substitution = _substitution_for(classification)
            if substitution not in emitted_substitutions:
                rendered.append(substitution)
                emitted_substitutions.add(substitution)
            inline_unsafe_continuation = piece.rstrip().endswith((",", ":"))
        else:
            fragment_count += 1
            voice_result = (
                validate_voice_conformance(speaker, piece)
                if voice_enabled
                else {"passed": True, "violations": []}
            )
            if voice_enabled:
                voice_checked += 1
            if voice_enabled and not voice_result["passed"]:
                replaced_count += 1
                voice_replaced += 1
                reasons.extend(
                    f"voice_conformance:{item['code']}"
                    for item in voice_result["violations"]
                )
                fallback = voice_boundary_fallback_for_speaker(speaker)
                if fallback not in emitted_substitutions:
                    rendered.append(fallback)
                    emitted_substitutions.add(fallback)
            else:
                preserved_count += 1
                rendered.append(piece)
            inline_unsafe_continuation = False

    visible = "".join(rendered).strip()
    if not visible and original:
        visible = CLASSIFIER_ERROR_SUBSTITUTION
        classifier_errors += 1
        replaced_count += 1
        reasons.append("boundary_empty_after_filter")
    reason_codes = tuple(dict.fromkeys(reasons))
    outcome = (
        "classifier_error"
        if classifier_errors
        else "voice_substituted"
        if voice_replaced
        else "substituted"
        if replaced_count
        else "unchanged"
    )
    receipt = OutputBoundaryReceipt(
        outcome=outcome,
        source_request_sha256=resolved_context.source_request_sha256,
        source_request_truncated=resolved_context.source_request_truncated,
        technical_intent=resolved_context.technical_intent,
        technical_intent_reason=resolved_context.technical_intent_reason,
        original_text_sha256=_hash(original),
        visible_text_sha256=_hash(visible),
        fragment_count=fragment_count,
        preserved_fragment_count=preserved_count,
        replaced_fragment_count=replaced_count,
        classifier_error_count=classifier_errors,
        reason_codes=reason_codes,
        speaker_ref=speaker,
        voice_profile_ref=voice_profile_ref_for_speaker(speaker),
        voice_conformance_outcome=(
            "disabled"
            if not voice_enabled
            else "substituted"
            if voice_replaced
            else "passed"
        ),
        voice_checked_fragment_count=voice_checked,
        voice_replaced_fragment_count=voice_replaced,
    )
    return FinalOutputBoundaryResult(visible, receipt, resolved_context)


__all__ = [
    "CLASSIFIER_ERROR_SUBSTITUTION",
    "CONTROL_SUBSTITUTION",
    "FLEET_VOICE_BOUNDARY_ENV_VAR",
    "MAX_BOUNDED_SOURCE_REQUEST_CHARS",
    "OUTPUT_BOUNDARY_SCHEMA_VERSION",
    "RUNTIME_SUBSTITUTION",
    "FinalOutputBoundaryResult",
    "OutputBoundaryContext",
    "OutputBoundaryReceipt",
    "classify_control_language",
    "fleet_voice_boundary_enabled",
    "render_final_output",
    "split_output_fragments",
]
