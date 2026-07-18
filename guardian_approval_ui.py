"""Shared human-facing contract for Guardian approval surfaces."""

from __future__ import annotations

import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo


APPROVE_BUTTON_TEXT = "✅ Approve"
DENY_BUTTON_TEXT = "❌ Deny"
EASTERN = ZoneInfo("America/New_York")


def human_reply_code(reference: str) -> str:
    """Return a stable four-digit code that reveals no signed callback material."""

    digest = hashlib.sha256(str(reference or "").encode("utf-8")).digest()
    return f"{int.from_bytes(digest[:4], 'big') % 10_000:04d}"


def fallback_lines(reference: str, *, allow_approve_all: bool = False) -> tuple[str, ...]:
    code = human_reply_code(reference)
    lines = (
        f"or reply: APPROVE {code}",
        f"or reply: DENY {code}",
    )
    if allow_approve_all:
        return (lines[0], f"or reply: APPROVE ALL {code}", lines[1])
    return lines


def parse_human_reply(
    text: str,
    reference: str,
    *,
    allow_approve_all: bool = False,
) -> tuple[str | None, str | None]:
    """Parse APPROVE/DENY CODE while retaining the legacy CODE 1/2 fallback."""

    expected = human_reply_code(reference)
    parts = str(text or "").strip().upper().split()
    if len(parts) == 2 and parts[0] in {"APPROVE", "DENY"}:
        command, supplied = parts
        if supplied != expected:
            return None, "wrong_reply_code"
        return ("Y" if command == "APPROVE" else "N"), None
    if allow_approve_all and len(parts) == 3 and parts[:2] == ["APPROVE", "ALL"]:
        if parts[2] != expected:
            return None, "wrong_reply_code"
        return "A", None

    # Existing clients may still send the prior CODE DECISION shape. It stays
    # ID-bound and is never rendered in new messages.
    if len(parts) == 2 and parts[0] == str(reference or "")[:4].upper():
        if allow_approve_all and parts[1] in {"2", "YES_FOR_ALL"}:
            return "A", None
        if parts[1] in {"1", "Y", "YES"}:
            return "Y", None
        deny_values = {"3", "N", "NO"} if allow_approve_all else {"2", "N", "NO"}
        if parts[1] in deny_values:
            return "N", None
        return None, "invalid_reply_decision"
    return None, "reply_code_required"


def terminal_outcome(
    outcome: str,
    *,
    when: datetime | None = None,
    approved_suffix: str = "executing",
) -> str:
    """Render token-free final text for same-message Telegram replacement."""

    normalized = str(outcome or "").strip().lower()
    local = (when or datetime.now(tz=EASTERN)).astimezone(EASTERN)
    clock = local.strftime("%I:%M %p").lstrip("0")
    if normalized == "approved":
        return f"✅ Approved by you at {clock} — {approved_suffix}"
    if normalized == "denied":
        return f"❌ Denied by you at {clock}"
    if normalized == "expired":
        return "⏰ Expired"
    if normalized == "delayed":
        return f"⏳ Deferred by you at {clock} — a fresh approval will follow"
    return "⚠️ Approval unavailable — no action taken"


__all__ = [
    "APPROVE_BUTTON_TEXT",
    "DENY_BUTTON_TEXT",
    "fallback_lines",
    "human_reply_code",
    "parse_human_reply",
    "terminal_outcome",
]
