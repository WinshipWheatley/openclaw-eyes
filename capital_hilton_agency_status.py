"""Capital Hilton agency/payment status readback.

This deterministic responder reads only the tracked operator-facing status
markdown. It never verifies bank/payment processor state, moves money, sends
messages, or mutates finance ledgers.
"""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
STATUS_OPERATOR_MD = ROOT / "generated/read_models/capital_hilton_agency_status_OPERATOR.md"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def _status_lines() -> list[str]:
    if not STATUS_OPERATOR_MD.exists():
        return []
    return [line.rstrip() for line in STATUS_OPERATOR_MD.read_text(encoding="utf-8").splitlines()]


def _extract_line(prefix: str, *, default: str = "") -> str:
    for line in _status_lines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return default


def _mentions_capital_hilton(text: str) -> bool:
    normalized = _normalize(text)
    return "capital hilton" in normalized or "dcash00983536" in normalized


def _mentions_agency_or_payment_status(text: str) -> bool:
    normalized = _normalize(text)
    return any(
        phrase in normalized
        for phrase in (
            "agency status",
            "openclaw status",
            "openclaw autonomous",
            "agency readback",
        )
    )


def _base_answer(*, include_openclaw_attribution: bool) -> str:
    status = _extract_line("Status:", default="Capital Hilton status is recorded in the local operator readback.")
    openclaw_state = _extract_line("OpenClaw State:", default="payment_watch_waiting_for_expected_check")
    next_safe_action = _extract_line(
        "Next Safe Action:",
        default="Wait for authorized finance proof before marking paid.",
    )
    evidence = _extract_line(
        "- operator supplied current status;",
        default="operator supplied current status; not bank or payment-processor proof",
    )
    answer = (
        f"Capital Hilton status: {status} "
        f"OpenClaw state: {openclaw_state}. "
        f"Evidence tier: {evidence}. "
        f"Next safe action: {next_safe_action} "
        "No send, Coupa submit, ledger mutation, paid marking, bank verification, or money movement ran."
    )
    if include_openclaw_attribution:
        answer += (
            " OpenClaw autonomous system status: no autonomous completion of the Capital Hilton payment workflow is claimed."
        )
    return answer


def format_capital_hilton_agency_answer(text: str) -> str | None:
    if not _mentions_capital_hilton(text):
        return None
    if not _mentions_agency_or_payment_status(text):
        return None
    normalized = _normalize(text)
    if "openclaw status" in normalized or "openclaw autonomous" in normalized:
        return None
    return _base_answer(include_openclaw_attribution=False)


def format_capital_hilton_openclaw_status_answer(text: str) -> str | None:
    if not _mentions_capital_hilton(text):
        return None
    normalized = _normalize(text)
    if "openclaw status" not in normalized and "openclaw autonomous" not in normalized:
        return None
    return _base_answer(include_openclaw_attribution=True)


__all__ = [
    "format_capital_hilton_agency_answer",
    "format_capital_hilton_openclaw_status_answer",
]
