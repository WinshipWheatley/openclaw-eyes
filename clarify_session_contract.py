"""ONE shared contract for every clarify/intake session (task 142).

Live evidence (LIVE-ROUND-BATTERY-v2.md PASS-2): a chief billing-intake clarify
session stayed alive 12+ hours and ate a delete bait; the invoice-cockpit
session intercepted every message on every channel. The class fix, applied to
every ``_clarify`` state machine (chief billing intake, the invoice cockpit,
Cassandra's guided-review/rates wizard):

1. REFUSAL ABOVE SESSIONS — operator_refusal_guard (task 141) evaluates before
   any session resume. A session NEVER captures refusal-class verbs.
2. TTL — sessions expire minutes-scale (default 30min, env
   ``OPENCLAW_CLARIFY_SESSION_TTL_S``). A session with no stamp at all (every
   pre-142 stuck session, including the parked live files) is already expired.
3. SURFACE SCOPE — a session is scoped to the channel that started it and
   never captures another channel's traffic (the session survives for its own
   channel; only its own channel's unrelated input expires it).
4. UNRELATED-INPUT PASS-THROUGH — input that does not answer the pending
   question AND classifies as a question or an instruction routes through the
   agent's normal pipeline untouched, and the session expires.

Deterministic and text-only: no model calls, no I/O beyond the refusal guard's
own fail-open receipt. Callers hold the session dicts; this module only reads
and stamps them.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

CONTRACT_KEY = "clarify_contract"
CONTRACT_VERSION = 1

DEFAULT_TTL_SECONDS = 30 * 60
TTL_ENV = "OPENCLAW_CLARIFY_SESSION_TTL_S"


def clarify_session_ttl_seconds() -> float:
    """TTL in seconds; env-tunable, falls back to the 30-minute default."""
    raw = os.environ.get(TTL_ENV, "").strip()
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return float(DEFAULT_TTL_SECONDS)


# ═════════════════════════════ stamps (TTL + scope) ═══════════════════════════


def stamp_clarify_session(session: dict, *, surface: str = "", now: float | None = None) -> dict:
    """Stamp a session dict with its lease + owning surface. Mutates and returns it."""
    session[CONTRACT_KEY] = {
        "version": CONTRACT_VERSION,
        "touched_at_epoch": float(now if now is not None else time.time()),
        "surface": str(surface or ""),
    }
    return session


def touch_clarify_session(session: dict, now: float | None = None) -> dict:
    """Renew the lease on a captured turn; stamps an unstamped session."""
    stamp = session.get(CONTRACT_KEY)
    if not isinstance(stamp, dict):
        return stamp_clarify_session(session, now=now)
    stamp["touched_at_epoch"] = float(now if now is not None else time.time())
    return session


def _stamp_of(session: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(session, Mapping):
        return None
    stamp = session.get(CONTRACT_KEY)
    return stamp if isinstance(stamp, Mapping) else None


def clarify_session_expired(
    session: Mapping[str, Any] | None,
    *,
    now: float | None = None,
    ttl_seconds: float | None = None,
) -> bool:
    """True when the session's lease is stale. Missing/invalid stamp = expired:
    every pre-contract stuck session (the parked live files) must never capture."""
    stamp = _stamp_of(session)
    if stamp is None:
        return True
    try:
        touched = float(stamp.get("touched_at_epoch"))
    except (TypeError, ValueError):
        return True
    ttl = float(ttl_seconds) if ttl_seconds is not None else clarify_session_ttl_seconds()
    current = float(now if now is not None else time.time())
    return (current - touched) > ttl


def clarify_session_scope_ok(session: Mapping[str, Any] | None, *, surface: str) -> bool:
    """True when the message's surface matches the session's owning surface.
    Blank on either side fails open (single-surface callers, legacy stamps)."""
    stamp = _stamp_of(session)
    session_surface = str((stamp or {}).get("surface") or "")
    incoming = str(surface or "")
    if not session_surface or not incoming:
        return True
    return session_surface == incoming


def iso_timestamp_expired(
    iso_text: str,
    *,
    now_iso: str | None = None,
    ttl_seconds: float | None = None,
) -> bool:
    """TTL check for machines that already track ISO-8601 ``updated_at_utc``
    stamps (Cassandra's guided review). Unparseable/blank = expired."""
    parsed = _parse_iso(iso_text)
    if parsed is None:
        return True
    current = _parse_iso(now_iso) if now_iso else datetime.now(timezone.utc)
    if current is None:
        current = datetime.now(timezone.utc)
    ttl = float(ttl_seconds) if ttl_seconds is not None else clarify_session_ttl_seconds()
    return (current - parsed).total_seconds() > ttl


def _parse_iso(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# ═════════════════════════ input-shape classification ═════════════════════════

_WORD_RE = re.compile(r"[a-z']+")

# Interrogative openers: a leading one of these (or a trailing "?") means the
# text is asking, not answering — it belongs to the normal pipeline.
_QUESTION_OPENERS = frozenset(
    {
        "who", "whos", "who's", "what", "whats", "what's", "when", "whens", "when's",
        "where", "wheres", "where's", "why", "which", "how", "hows", "how's",
        "does", "did", "do", "is", "are", "was", "were", "am",
        "will", "would", "can", "could", "should", "shall", "has", "have",
        "anyone", "anybody",
    }
)

# Imperative openers that hand work to the system — dispatch verbs, kept narrow
# so ordinary wizard answers ("none", "$450", "Draper Carter") never match.
_INSTRUCTION_OPENERS = frozenset(
    {
        "send", "email", "text", "sms", "call", "phone", "route", "forward",
        "dispatch", "schedule", "book", "remind", "post", "publish", "get",
        "go", "stage", "ship", "deploy", "restart", "prepare", "draft",
    }
)

# Dispatch idioms anywhere in the text (the live Maestro instruction: "the PA
# rental invoice for Live Arts needs to go out — get it to the right agent").
_INSTRUCTION_IDIOMS = (
    "needs to go out",
    "need to go out",
    "needs to be sent",
    "need to be sent",
    "get it to",
    "get this to",
    "get it over to",
    "send it out",
    "send it to",
    "send this to",
    "hand it off",
    "hand this off",
    "hand it to",
    "route it",
    "route this",
    "make sure it goes out",
    "take it to the",
)


def _first_word(text: str) -> str:
    match = _WORD_RE.search(str(text or "").lower())
    return match.group(0) if match else ""


def is_question_shaped(text: str) -> bool:
    """Asking, not answering: trailing '?' or an interrogative opener."""
    stripped = str(text or "").strip()
    if not stripped:
        return False
    if stripped.rstrip(" .!…").endswith("?"):
        return True
    return _first_word(stripped) in _QUESTION_OPENERS


def is_instruction_shaped(text: str) -> bool:
    """Handing work to the system: a leading dispatch verb or a dispatch idiom."""
    stripped = str(text or "").strip()
    if not stripped:
        return False
    lowered = " ".join(stripped.lower().split())
    if any(idiom in lowered for idiom in _INSTRUCTION_IDIOMS):
        return True
    return _first_word(stripped) in _INSTRUCTION_OPENERS


def refusal_reply(text: str, *, agent: str, surface: str = "") -> str | None:
    """Task 141 tap, fail-open: guard errors never block a session machine."""
    try:
        from operator_refusal_guard import refusal_reply_for_text

        return refusal_reply_for_text(text, agent=agent, surface=surface)
    except Exception:
        return None


# ═════════════════════════════ the one disposition ════════════════════════════

ACTION_REFUSE = "refuse"
ACTION_PASS_THROUGH = "pass_through"
ACTION_CAPTURE = "capture"

REASON_REFUSAL = "operator_refusal_guard"
REASON_TTL = "ttl_expired"
REASON_SCOPE = "surface_mismatch"
REASON_UNRELATED = "unrelated_input"
REASON_ANSWER = "in_session_answer"


@dataclass(frozen=True)
class ClarifyDisposition:
    action: str
    reason: str
    reply: str | None = None
    expire_session: bool = False


def clarify_session_disposition(
    session: Mapping[str, Any] | None,
    text: str,
    *,
    agent: str,
    surface: str = "",
    answers_pending: Callable[[str], bool] | None = None,
    now: float | None = None,
    ttl_seconds: float | None = None,
) -> ClarifyDisposition:
    """Decide what an ACTIVE clarify session may do with an operator message.

    Order is the contract: refusal (141) → TTL → surface scope → the machine's
    own pending-answer hook → question/instruction pass-through → capture.
    """
    refusal = refusal_reply(text, agent=agent, surface=surface)
    if refusal is not None:
        return ClarifyDisposition(action=ACTION_REFUSE, reason=REASON_REFUSAL, reply=refusal)

    if clarify_session_expired(session, now=now, ttl_seconds=ttl_seconds):
        return ClarifyDisposition(action=ACTION_PASS_THROUGH, reason=REASON_TTL, expire_session=True)

    if not clarify_session_scope_ok(session, surface=surface):
        return ClarifyDisposition(action=ACTION_PASS_THROUGH, reason=REASON_SCOPE, expire_session=False)

    if answers_pending is not None:
        try:
            if answers_pending(text):
                return ClarifyDisposition(action=ACTION_CAPTURE, reason=REASON_ANSWER)
        except Exception:
            pass

    if is_question_shaped(text) or is_instruction_shaped(text):
        return ClarifyDisposition(
            action=ACTION_PASS_THROUGH, reason=REASON_UNRELATED, expire_session=True
        )

    return ClarifyDisposition(action=ACTION_CAPTURE, reason=REASON_ANSWER)


__all__ = [
    "ACTION_CAPTURE",
    "ACTION_PASS_THROUGH",
    "ACTION_REFUSE",
    "CONTRACT_KEY",
    "ClarifyDisposition",
    "DEFAULT_TTL_SECONDS",
    "REASON_ANSWER",
    "REASON_REFUSAL",
    "REASON_SCOPE",
    "REASON_TTL",
    "REASON_UNRELATED",
    "TTL_ENV",
    "clarify_session_disposition",
    "clarify_session_expired",
    "clarify_session_scope_ok",
    "clarify_session_ttl_seconds",
    "is_instruction_shaped",
    "is_question_shaped",
    "iso_timestamp_expired",
    "refusal_reply",
    "stamp_clarify_session",
    "touch_clarify_session",
]
