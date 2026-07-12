"""Public, dependency-light control-language and technical-intent policy.

The classifier is deliberately pure: it performs no I/O, imports no agent
runtime, and returns bounded reason codes plus a one-way text hash.  Truth
intake, final output rendering, and state hygiene all consume this one owner so
their control-language definitions cannot drift independently.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


CONTROL_LANGUAGE_SCHEMA_VERSION = "control_language_policy_v1"


class ControlLanguageReason(str, Enum):
    CONTROL_PHRASE = "control_phrase"
    PROBE_LABEL = "probe_label"
    INSTRUCTION_PREFIX = "instruction_prefix"
    RUNTIME_DIAGNOSTIC = "runtime_diagnostic"


_CONTROL_PHRASES = (
    "alive check",
    "answer one sentence",
    "compact recovery check",
    "deep probe",
    "degraded recovery",
    "health probe",
    "probe prompt",
    "recovery check",
    "stress probe",
)

_RUNTIME_DIAGNOSTIC_PHRASES = (
    "local model stream limit",
    "model stream limit",
    "no usable chunks",
    "stale partial output",
    "upstream local model",
)

_RUNTIME_DIAGNOSTIC_SHAPE_RE = re.compile(
    r"(?:\b(?:check|checking|retry(?:ing)?\s+after\s+checking)\b.{0,80}"
    r"\bgateway\s+health\b|"
    r"\bgateway\s+health\b.{0,80}\bollama\s+contention\b)",
    re.IGNORECASE,
)

_PROBE_LABEL_RE = re.compile(
    r"\b(?:"
    r"cass[-_ ]?deep[-_: ]?\d+"
    r"|probe-(?:[a-z0-9_]+-?)+"
    r"|stress-(?!test\b)(?:[a-z0-9_]+-?)+"
    r"|recovery-check(?:-(?:[a-z0-9_]+-?)+)?"
    r")\b",
    re.IGNORECASE,
)
_INSTRUCTION_PREFIX_RE = re.compile(
    r"^\s*(?:answer|reply|respond|summarize)\b"
    r"(?!\s+(?:received|sent|ready|recorded|pending|queued|delivered|failed|succeeded)\b)",
    re.IGNORECASE,
)

_STATUS_REQUEST_RE = re.compile(
    r"\b(?:status|how(?:'s|\s+is)\s+(?:the\s+)?system|system\s+looking|from\s+your\s+seat)\b",
    re.IGNORECASE,
)
_BUSINESS_REQUEST_RE = re.compile(
    r"\b(?:invoice|payment|paid|check|money|owes?|receivable|client|ledger|gmail|email)\b",
    re.IGNORECASE,
)
_TECHNICAL_MECHANISM_RE = re.compile(
    r"\b(?:"
    r"architecture|code|debug(?:ger|ging)?|diagnos(?:e|is|tic|tics)|gateway|"
    r"implementation|log|model|ollama|stack\s*trace|stream(?:ing)?|technical|"
    r"timeout|trace|troubleshoot(?:ing)?|webhook|contention"
    r")\b",
    re.IGNORECASE,
)
_TECHNICAL_ACTION_RE = re.compile(
    r"\b(?:explain|debug|diagnose|troubleshoot|why|how\s+(?:does|do|is|are)|"
    r"where\s+(?:does|is|are)|implementation)\b",
    re.IGNORECASE,
)
_CONTROL_RECITATION_RE = re.compile(
    r"(?:"
    r"^\s*(?:please\s+)?(?:repeat|quote|recite)\b"
    r"|\b(?:please\s+|can\s+you\s+(?:please\s+)?|"
    r"could\s+you\s+(?:please\s+)?|would\s+you\s+(?:please\s+)?|"
    r"will\s+you\s+(?:please\s+)?)(?:repeat|quote|recite)\b"
    r"|\b(?:repeat|quote|recite)\s+(?:it|that|this|what|exactly|verbatim|"
    r"the\s+(?:answer|message|model|output|reply|response|text))\b"
    r"|\bsay\s+(?:that|it)\s+again\b"
    r"|\b(?:give|provide|show)\s+(?:me\s+)?(?:the\s+)?(?:exact|verbatim)\b"
    r")",
    re.IGNORECASE,
)
_IMPLICIT_RECITATION_RE = re.compile(
    r"(?:"
    r"\b(?:tell|show|give)\s+(?:me\s+)?(?:what|the\s+(?:exact|raw|verbatim))\b"
    r".{0,48}\b(?:assistant|gateway|model|system)\b"
    r".{0,24}\b(?:output|replied|reply|response|returned|said|say)\b"
    r"|\bwhat\s+(?:did|is|was)\s+(?:the\s+)?(?:exact\s+|raw\s+|verbatim\s+)?"
    r"(?:assistant|gateway|model|system)\s+"
    r"(?:output|reply|response|return|returned|say|said)\b"
    r")",
    re.IGNORECASE,
)
_QUOTED_TEXT_RE = re.compile(r"[\"“][^\"”]+[\"”]")


def _hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _compact(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", " ").split()).strip()


@dataclass(frozen=True, slots=True)
class ControlLanguageClassification:
    is_control_language: bool
    reason_codes: tuple[str, ...]
    text_sha256: str
    schema_version: str = CONTROL_LANGUAGE_SCHEMA_VERSION

    @property
    def always_suppress(self) -> bool:
        return any(
            reason
            in {
                ControlLanguageReason.CONTROL_PHRASE.value,
                ControlLanguageReason.PROBE_LABEL.value,
                ControlLanguageReason.INSTRUCTION_PREFIX.value,
            }
            for reason in self.reason_codes
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TechnicalIntentDecision:
    is_technical: bool
    reason_code: str
    request_sha256: str
    schema_version: str = CONTROL_LANGUAGE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_control_language(text: Any) -> ControlLanguageClassification:
    """Classify internal control/runtime phrasing with closed reason codes."""

    clean = _compact(text)
    lowered = clean.casefold()
    reasons: list[str] = []
    if _PROBE_LABEL_RE.search(clean):
        reasons.append(ControlLanguageReason.PROBE_LABEL.value)
    if any(phrase in lowered for phrase in _CONTROL_PHRASES):
        reasons.append(ControlLanguageReason.CONTROL_PHRASE.value)
    if _INSTRUCTION_PREFIX_RE.search(clean):
        reasons.append(ControlLanguageReason.INSTRUCTION_PREFIX.value)
    if any(phrase in lowered for phrase in _RUNTIME_DIAGNOSTIC_PHRASES) or (
        _RUNTIME_DIAGNOSTIC_SHAPE_RE.search(clean)
    ):
        reasons.append(ControlLanguageReason.RUNTIME_DIAGNOSTIC.value)
    deduped = tuple(dict.fromkeys(reasons))
    return ControlLanguageClassification(
        is_control_language=bool(deduped),
        reason_codes=deduped,
        text_sha256=_hash(text),
    )


def classify_technical_intent(source_request: Any) -> TechnicalIntentDecision:
    """Decide technical intent before output filtering.

    Status and business questions retain their user-facing meaning even when
    they contain a generic word such as "system" or "check".  Explicit asks to
    explain/debug technical mechanisms are the only positive class.
    """

    clean = _compact(source_request)
    control = classify_control_language(clean)
    if _CONTROL_RECITATION_RE.search(clean) or _IMPLICIT_RECITATION_RE.search(clean):
        return TechnicalIntentDecision(
            False,
            "control_recitation_request",
            _hash(source_request),
        )
    if (
        ControlLanguageReason.RUNTIME_DIAGNOSTIC.value in control.reason_codes
        and _QUOTED_TEXT_RE.search(clean)
    ):
        return TechnicalIntentDecision(
            False,
            "control_recitation_request",
            _hash(source_request),
        )
    status_request = bool(_STATUS_REQUEST_RE.search(clean))
    business_request = bool(_BUSINESS_REQUEST_RE.search(clean))
    technical_mechanism = bool(_TECHNICAL_MECHANISM_RE.search(clean))
    explicit_technical = technical_mechanism and bool(
        _TECHNICAL_ACTION_RE.search(clean)
        or (not status_request and not business_request)
    )
    if explicit_technical:
        return TechnicalIntentDecision(True, "explicit_technical_question", _hash(source_request))
    if status_request:
        return TechnicalIntentDecision(False, "status_request", _hash(source_request))
    if business_request:
        return TechnicalIntentDecision(False, "business_request", _hash(source_request))
    return TechnicalIntentDecision(False, "ordinary_request", _hash(source_request))


__all__ = [
    "CONTROL_LANGUAGE_SCHEMA_VERSION",
    "ControlLanguageClassification",
    "ControlLanguageReason",
    "TechnicalIntentDecision",
    "classify_control_language",
    "classify_technical_intent",
]
