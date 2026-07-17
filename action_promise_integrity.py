"""Hard boundary for action-promising operator text.

An acknowledgement or final response may promise work only when it carries a
reference to the performed action or to a queued job receipt. Unbound promises
are replaced with the addressed agent's canonical honest fallback.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

import agent_voice_profiles


SCHEMA_VERSION = "action_promise_integrity_v0"

_ACTION_PROMISE_PATTERNS = (
    re.compile(r"\b(?:i'm|im)\s+on\s+it\b", re.IGNORECASE),
    re.compile(r"\bon\s+it\b", re.IGNORECASE),
    re.compile(r"\bpull(?:ing)?\s+(?:that|this|it|the\s+[^.!?]{0,48})?\s*up\b", re.IGNORECASE),
    re.compile(r"\blet\s+me\s+(?:get|grab|pull|open|find|fetch|bring)\b", re.IGNORECASE),
    re.compile(r"\bi(?:'ll|\s+will)\s+(?:get|grab|pull|open|find|fetch|bring)\b", re.IGNORECASE),
    re.compile(
        r"\bi(?:'ll|\s+will)\s+(?:handle|do|check|investigate|review|fix|"
        r"work\s+on|look\s+into|take\s+care\s+of)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:i'm|im)\s+(?:working\s+on|looking\s+into|checking|handling|"
        r"getting|grabbing|fetching|opening|finding|fixing)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:getting|grabbing|fetching|opening|finding|checking)\s+"
        r"(?:that|this|it)(?:\s+for\s+you)?(?:\s+now)?\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:one\s+sec|gimme\s+a\s+beat|hang\s+tight|lemme\s+think)\b", re.IGNORECASE),
)


def _normalized_text(text: str) -> str:
    return (
        str(text or "")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u2026", "...")
        .replace("\u2014", "-")
    )


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def contains_action_promise(text: str) -> bool:
    value = _normalized_text(text)
    return any(pattern.search(value) for pattern in _ACTION_PROMISE_PATTERNS)


def _receipt_refs(values: Iterable[object]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        values = (values,)
    return tuple(
        dict.fromkeys(
            str(value).strip()
            for value in values
            if str(value or "").strip()
        )
    )


@dataclass(frozen=True)
class ActionPromiseIntegrityReceipt:
    schema_version: str
    speaker_ref: str
    promise_detected: bool
    action_binding_present: bool
    substituted: bool
    action_receipt_refs: tuple[str, ...]
    original_text_sha256: str
    visible_text_sha256: str
    enforcement: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["action_receipt_refs"] = list(self.action_receipt_refs)
        return payload


@dataclass(frozen=True)
class ActionPromiseIntegrityResult:
    visible_text: str
    receipt: ActionPromiseIntegrityReceipt


def enforce_action_promise_integrity(
    text: str,
    *,
    speaker_ref: str,
    action_receipt_refs: Iterable[object] = (),
) -> ActionPromiseIntegrityResult:
    original = str(text or "")
    refs = _receipt_refs(action_receipt_refs)
    promise_detected = contains_action_promise(original)
    binding_present = bool(refs)
    substituted = promise_detected and not binding_present
    visible = (
        agent_voice_profiles.action_promise_fallback_for_speaker(speaker_ref)
        if substituted
        else original
    )
    canonical_speaker = str(speaker_ref or "").strip().lower()
    if canonical_speaker not in agent_voice_profiles.SPEAKER_REFS:
        canonical_speaker = "openclaw"
    reason = (
        "unbound_action_promise_replaced"
        if substituted
        else (
            "action_promise_bound_to_receipt"
            if promise_detected
            else "no_action_promise_detected"
        )
    )
    return ActionPromiseIntegrityResult(
        visible_text=visible,
        receipt=ActionPromiseIntegrityReceipt(
            schema_version=SCHEMA_VERSION,
            speaker_ref=canonical_speaker,
            promise_detected=promise_detected,
            action_binding_present=binding_present,
            substituted=substituted,
            action_receipt_refs=refs,
            original_text_sha256=_sha256_text(original),
            visible_text_sha256=_sha256_text(visible),
            enforcement="fail_closed",
            reason=reason,
        ),
    )


__all__ = [
    "ActionPromiseIntegrityReceipt",
    "ActionPromiseIntegrityResult",
    "SCHEMA_VERSION",
    "contains_action_promise",
    "enforce_action_promise_integrity",
]
