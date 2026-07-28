"""Deterministic response policy for an unresolved semantic-vote failure.

The typed contract deliberately keeps an outside-session vote failure as an
unhandled ``PASS_THROUGH`` decision.  This module recognizes only that exact
receipt and lets each installed adapter replace its legacy/model fallthrough
with one warm line.  It does not mutate the receipt or grant new authority.

Maestro may instead use an existing deterministic plate/digest renderer when
the operator explicitly requested that shape.  Merely mentioning an overview,
an update, or a digest is not enough to activate that exception.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Mapping


MODEL_TIMEOUT_CLARIFICATION = (
    "The language model timed out before it could classify that request. "
    "The GPU may be busy. I left your request untouched; please try again in a moment."
)
MODEL_FAILURE_CLARIFICATION = (
    "The language model didn't return a usable routing decision. I left your "
    "request untouched; please try again in a moment."
)
UNKNOWN_STATUS_CLARIFICATION = (
    "The language model vote returned an unrecognized result. I left your "
    "request untouched; please try again in a moment."
)
# Compatibility name retained for installed Task 167 callers.
WARM_TIMEOUT_CLARIFICATION = MODEL_TIMEOUT_CLARIFICATION


class ExplicitDigestIntent(str, Enum):
    NONE = "none"
    PLATE = "plate"
    DIGEST = "digest"


class VoteFailureKind(str, Enum):
    NONE = "none"
    TIMEOUT = "timeout"
    MODEL_FAILURE = "model_failure"
    UNKNOWN_STATUS = "unknown_status"


class VoteTimeoutDisposition(str, Enum):
    NONE = "none"
    CLARIFY = "clarify"
    DETERMINISTIC_DIGEST = "deterministic_digest"


_TIMEOUT_FAILURE_STATUSES = frozenset({"deadline_exceeded"})
_NON_FAILURE_STATUSES = frozenset({"accepted_unresolved"})
_MODEL_FAILURE_STATUSES = frozenset(
    {
        "empty",
        "invalid",
        "below_threshold",
        "session_label_without_session",
        # Compatibility for receipts written before Task 167 split empty from
        # malformed output. Its ambiguity prevents a truthful timeout claim.
        "timeout_or_invalid",
    }
)


def _normalize_request(text: Any) -> str:
    normalized = str(text or "").lower()
    normalized = normalized.replace("’", "'").replace("‘", "'")
    normalized = normalized.replace("—", " ").replace("–", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.rstrip(" ?!.").strip()


_TIME_SCOPE = (
    r"(?:today|tonight|right\s+now|this\s+morning|this\s+afternoon|this\s+evening)"
)
_TIME_SCOPE_SUFFIX = rf"(?:\s+(?:for\s+)?{_TIME_SCOPE})?"
_POLITE_REQUEST_PREFIX = (
    r"(?:(?:(?:can|could|would|will)\s+you\s+)(?:please\s+)?|please\s+)?"
)
_PLATE_PATTERNS = (
    re.compile(
        r"(?:what(?:'s|s|\s+is)|what\s+all\s+is)\s+on\s+my\s+plate"
        + _TIME_SCOPE_SUFFIX
        + r"(?:\s*,?\s*(?:and\s+)?what\s+(?:actually\s+)?needs\s+me"
        + _TIME_SCOPE_SUFFIX
        + r")?"
    ),
    re.compile(
        _POLITE_REQUEST_PREFIX
        + r"(?:show|tell|give)\s+me\s+what(?:'s|s|\s+is)"
        + r"\s+on\s+my\s+plate"
        + _TIME_SCOPE_SUFFIX
    ),
    re.compile(
        _POLITE_REQUEST_PREFIX
        + r"(?:(?:tell|show)\s+me\s+)?what\s+(?:actually\s+)?needs\s+me"
        + _TIME_SCOPE_SUFFIX
    ),
    re.compile(
        _POLITE_REQUEST_PREFIX
        + r"(?:(?:tell|show)\s+me\s+)?what\s+needs\s+my\s+attention"
        + _TIME_SCOPE_SUFFIX
    ),
)

_DIGEST_SCOPE = (
    r"(?:everything|where\s+things\s+stand|the\s+(?:current\s+)?(?:system|fleet|picture)|"
    r"current\s+operations|operations|my\s+(?:current\s+)?priorities|what\s+needs\s+me|"
    r"what(?:'s|s|\s+is)\s+going\s+on|what\s+needs\s+my\s+attention)"
)
_DIGEST_PATTERNS = (
    re.compile(
        _POLITE_REQUEST_PREFIX
        + r"(?:catch\s+me\s+up|fill\s+me\s+in)"
        + rf"(?:\s+on\s+{_DIGEST_SCOPE}|\s+(?:for\s+)?{_TIME_SCOPE})?"
    ),
    re.compile(
        _POLITE_REQUEST_PREFIX
        + rf"brief\s+me(?:\s+on\s+{_DIGEST_SCOPE}|"
        rf"\s+(?:for\s+)?{_TIME_SCOPE})?"
    ),
    re.compile(
        _POLITE_REQUEST_PREFIX
        + rf"(?:give|show|tell)\s+me\s+"
        r"(?:(?:a|an|the|my)\s+)?"
        r"(?:(?:current|quick|full|latest|daily|morning|afternoon|evening)\s+)?"
        r"(?:overview|summary|rundown|recap|digest|brief)"
        rf"(?:\s+of\s+{_DIGEST_SCOPE}|\s+(?:for\s+)?{_TIME_SCOPE})?"
    ),
    re.compile(
        r"(?:(?:can|could|may|would)\s+i\s+)(?:please\s+)?(?:get|have)\s+"
        r"(?:(?:a|an|the|my)\s+)?"
        r"(?:(?:current|quick|full|latest|daily|morning|afternoon|evening)\s+)?"
        r"(?:overview|summary|rundown|recap|digest|brief)"
        rf"(?:\s+of\s+{_DIGEST_SCOPE}|\s+(?:for\s+)?{_TIME_SCOPE})?"
    ),
    re.compile(
        r"(?:i(?:'d|\s+would)\s+like|i\s+want)\s+"
        r"(?:(?:a|an|the|my)\s+)?"
        r"(?:(?:current|quick|full|latest|daily|morning|afternoon|evening)\s+)?"
        r"(?:overview|summary|rundown|recap|digest|brief)"
        rf"(?:\s+of\s+{_DIGEST_SCOPE}|\s+(?:for\s+)?{_TIME_SCOPE})?"
    ),
    re.compile(
        _POLITE_REQUEST_PREFIX
        + rf"(?:summarize|recap)\s+{_DIGEST_SCOPE}"
    ),
    re.compile(
        r"(?:please\s+)?(?:what(?:'s|s|\s+is)\s+(?:up|new|the\s+latest)|"
        r"how\s+are\s+things|where\s+do\s+things\s+stand)"
        rf"(?:\s+{_TIME_SCOPE})?"
    ),
    re.compile(
        _POLITE_REQUEST_PREFIX
        + r"(?:give|show)\s+me\s+the\s+lay\s+of\s+the\s+land"
        rf"(?:\s+{_TIME_SCOPE})?"
    ),
    re.compile(
        r"(?:please\s+)?(?:overview|rundown|recap|digest|brief|the\s+latest)"
        r"(?:\s+please)?"
    ),
)


def classify_explicit_digest_intent(text: Any) -> ExplicitDigestIntent:
    """Classify an explicit global plate/digest request with closed grammar.

    The full-string matches are intentional.  They prevent a business-domain
    mutation (``update the invoice``), a narrow summary request, or a mere
    mention of digest wording from reopening the packet-wide overview path.
    """

    normalized = _normalize_request(text)
    if not normalized:
        return ExplicitDigestIntent.NONE
    if any(pattern.fullmatch(normalized) for pattern in _PLATE_PATTERNS):
        return ExplicitDigestIntent.PLATE
    if any(pattern.fullmatch(normalized) for pattern in _DIGEST_PATTERNS):
        return ExplicitDigestIntent.DIGEST
    return ExplicitDigestIntent.NONE


def _receipt_mapping(receipt_or_decision: Any) -> Mapping[str, Any]:
    candidate = receipt_or_decision
    decision_receipt = getattr(candidate, "receipt", None)
    if decision_receipt is not None:
        candidate = decision_receipt
    if not isinstance(candidate, Mapping):
        to_dict = getattr(candidate, "to_dict", None)
        if callable(to_dict):
            try:
                candidate = to_dict()
            except Exception:
                return {}
    if not isinstance(candidate, Mapping):
        return {}
    nested = candidate.get("receipt")
    if "source" not in candidate and isinstance(nested, Mapping):
        candidate = nested
    return candidate if isinstance(candidate, Mapping) else {}


def _semantic_vote_status(receipt: Mapping[str, Any]) -> str:
    status = receipt.get("semantic_vote_status")
    return status.strip() if isinstance(status, str) else ""


def classify_vote_failure_kind(receipt_or_decision: Any) -> VoteFailureKind:
    """Classify only Task 167's exact outside-session fail-open receipt."""

    receipt = _receipt_mapping(receipt_or_decision)
    if not receipt:
        return VoteFailureKind.NONE
    if str(receipt.get("source") or "") != "semantic_vote":
        return VoteFailureKind.NONE
    if str(receipt.get("label") or "") != "unresolved":
        return VoteFailureKind.NONE
    if str(receipt.get("action") or "") != "pass_through":
        return VoteFailureKind.NONE
    if str(receipt.get("reason") or "") != "uncertain_outside_session_fail_open":
        return VoteFailureKind.NONE
    status = _semantic_vote_status(receipt)
    if status in _NON_FAILURE_STATUSES:
        return VoteFailureKind.NONE
    if status in _TIMEOUT_FAILURE_STATUSES:
        return VoteFailureKind.TIMEOUT
    if status in _MODEL_FAILURE_STATUSES:
        return VoteFailureKind.MODEL_FAILURE
    normalized = status.lower()
    if normalized.startswith("error:"):
        return (
            VoteFailureKind.TIMEOUT
            if "timeout" in normalized
            else VoteFailureKind.MODEL_FAILURE
        )
    if not status:
        return VoteFailureKind.MODEL_FAILURE
    # This is an exact semantic-vote failure receipt. Unknown or future status
    # values must not make the failure disappear and reopen downstream work.
    return VoteFailureKind.UNKNOWN_STATUS


def is_outside_session_vote_failure(receipt_or_decision: Any) -> bool:
    """Return true only for Task 167's exact fail-open receipt shape."""

    return classify_vote_failure_kind(receipt_or_decision) is not VoteFailureKind.NONE


def is_recoverable_outside_session_vote_timeout(receipt_or_decision: Any) -> bool:
    """Return true when a timed-out advisory vote may continue to a text answer.

    The receipt classifier already requires an outside-session ``PASS_THROUGH``
    decision. Recovery therefore grants no workflow, tool, or external authority;
    it only prevents the advisory classifier from terminating the text turn.
    """

    return classify_vote_failure_kind(receipt_or_decision) is VoteFailureKind.TIMEOUT


def is_recoverable_outside_session_conversational_failure(
    receipt_or_decision: Any,
) -> bool:
    """Allow safe text continuation for timeout or an honest low-confidence vote.

    The exact outside-session PASS_THROUGH receipt remains mandatory. Empty,
    malformed, unavailable, or error responses still use the failure-specific
    clarification instead of opening a second model path.
    """

    kind = classify_vote_failure_kind(receipt_or_decision)
    if kind is VoteFailureKind.TIMEOUT:
        return True
    receipt = _receipt_mapping(receipt_or_decision)
    return (
        kind is VoteFailureKind.MODEL_FAILURE
        and _semantic_vote_status(receipt) == "below_threshold"
    )


def clarification_for_vote_failure(receipt_or_decision: Any) -> str | None:
    kind = classify_vote_failure_kind(receipt_or_decision)
    if kind is VoteFailureKind.TIMEOUT:
        return MODEL_TIMEOUT_CLARIFICATION
    if kind is VoteFailureKind.MODEL_FAILURE:
        return MODEL_FAILURE_CLARIFICATION
    if kind is VoteFailureKind.UNKNOWN_STATUS:
        return UNKNOWN_STATUS_CLARIFICATION
    return None


def named_clarification_for_vote_failure(
    receipt_or_decision: Any, *, agent: str = "agent", stage: str = "semantic_vote"
) -> str | None:
    """The same refusal, but it says which agent, which stage, and what happened.

    Cassandra and Chief both answered the 2026-07-28 battery with *"The language
    model didn't return a usable routing decision. I left your request untouched;
    please try again in a moment."* That sentence is true and safe and nearly
    useless: it names no agent, no stage, and no cause, and it promises that
    retrying might help when nothing about the failure has changed.

    Safety posture is identical — nothing ran, nothing was authorised. The only
    difference is that the operator now learns which lever to pull.
    """

    kind = classify_vote_failure_kind(receipt_or_decision)
    if kind is VoteFailureKind.NONE:
        return None

    from grounded_answer_contract import named_routing_failure

    detail = {
        VoteFailureKind.TIMEOUT: "the model did not classify the request before the deadline",
        VoteFailureKind.MODEL_FAILURE: "the vote returned no usable routing decision",
        VoteFailureKind.UNKNOWN_STATUS: "the vote returned a status this build does not recognise",
    }[kind]
    next_step = {
        VoteFailureKind.TIMEOUT: "The GPU may be busy; a retry can help only if it frees up.",
        VoteFailureKind.MODEL_FAILURE: "Retrying repeats this unless the model or the prompt changes.",
        VoteFailureKind.UNKNOWN_STATUS: "This is a defect worth reporting, not a transient.",
    }[kind]
    return named_routing_failure(
        agent=agent, stage=stage, failure_kind=kind.value.upper(),
        detail=detail, operator_next_step=next_step,
    )


def unknown_vote_status_receipt(receipt_or_decision: Any) -> dict[str, Any] | None:
    """Return a countable defect receipt for an unrecognized vote status."""

    if classify_vote_failure_kind(receipt_or_decision) is not VoteFailureKind.UNKNOWN_STATUS:
        return None
    status = _semantic_vote_status(_receipt_mapping(receipt_or_decision))
    return {
        "vote_failure_kind": "UNKNOWN_STATUS",
        "status": status,
        "defect_signal": "semantic_vote_unknown_status",
        "occurrence_count": 1,
    }


def classify_vote_timeout_disposition(
    text: Any,
    receipt_or_decision: Any,
    *,
    deterministic_digest_available: bool = False,
) -> VoteTimeoutDisposition:
    if not is_outside_session_vote_failure(receipt_or_decision):
        return VoteTimeoutDisposition.NONE
    if (
        deterministic_digest_available
        and classify_explicit_digest_intent(text) is not ExplicitDigestIntent.NONE
    ):
        return VoteTimeoutDisposition.DETERMINISTIC_DIGEST
    return VoteTimeoutDisposition.CLARIFY


def warm_clarification_for_vote_timeout(
    text: Any,
    receipt_or_decision: Any,
    *,
    deterministic_digest_available: bool = False,
) -> str | None:
    disposition = classify_vote_timeout_disposition(
        text,
        receipt_or_decision,
        deterministic_digest_available=deterministic_digest_available,
    )
    return (
        clarification_for_vote_failure(receipt_or_decision)
        if disposition is VoteTimeoutDisposition.CLARIFY
        else None
    )


def enforce_vote_timeout_output(
    text: Any,
    candidate: Any,
    receipt_or_decision: Any,
    *,
    deterministic_digest_available: bool = False,
) -> str:
    """Apply the visible-response invariant after all answer post-processing."""

    clarification = warm_clarification_for_vote_timeout(
        text,
        receipt_or_decision,
        deterministic_digest_available=deterministic_digest_available,
    )
    return clarification if clarification is not None else str(candidate or "")


__all__ = [
    "ExplicitDigestIntent",
    "MODEL_FAILURE_CLARIFICATION",
    "MODEL_TIMEOUT_CLARIFICATION",
    "UNKNOWN_STATUS_CLARIFICATION",
    "VoteFailureKind",
    "VoteTimeoutDisposition",
    "WARM_TIMEOUT_CLARIFICATION",
    "classify_explicit_digest_intent",
    "classify_vote_failure_kind",
    "classify_vote_timeout_disposition",
    "clarification_for_vote_failure",
    "enforce_vote_timeout_output",
    "is_outside_session_vote_failure",
    "is_recoverable_outside_session_conversational_failure",
    "is_recoverable_outside_session_vote_timeout",
    "unknown_vote_status_receipt",
    "warm_clarification_for_vote_timeout",
]
