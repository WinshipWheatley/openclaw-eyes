"""One egress every agent reply passes through, whichever listener produced it.

Maestro got the grounded-answer contracts first. Cassandra, Chief, Niles and
Guardian each have their own listener with its own final reply funnel, and wiring
the same four checks into four places by hand is how they drift apart: one gets a
fix, three keep the bug, and the battery that catches it runs a month later.

So the checks live here once, and each listener's funnel calls this with its own
agent name. The order is deliberate:

    1. question dominance   — is this an answer, or the persona changing the subject
    2. retrieval status     — if the packet failed to load, say which failure
    3. nonce interlock      — never emit an approval nonce over unproven identity
    4. identity banner      — say who is speaking (opt-in; see below)

Placing all four at the funnel rather than at callers means a new code path cannot
opt out by forgetting. That is the same reason the interlock matches the nonce in
the outgoing *text* instead of trusting a flag passed down from whoever built it.

The banner is opt-in because it changes what the operator reads on every message.
The interlock is not, and must never become so: a guard you can disable by
forgetting an environment variable is decoration.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

SCHEMA_VERSION = "agent_reply_egress_v1"

#: What turns a message into an approval. Matched at egress, not trusted upstream.
NONCE_IN_TEXT = re.compile(r"send-hold-graduation:[A-Za-z0-9:_-]{8,}")

WITHHELD_PREFIX = "Withheld:"


def _withheld(agent: str, reason: str) -> str:
    return (
        f"{WITHHELD_PREFIX} this {agent} reply carried an approval nonce and Telegram "
        f"agent identity is not proven. {reason} Nothing was sent, approved, or authorised."
    )


def apply_question_dominance(agent: str, question: str, text: str) -> str:
    """Refuse to relay a persona deflection as though it answered the question.

    Niles replied "What's the main goal: groove, melody, or arrangement?" to a
    technical exact-send question. Every agent has a persona that can do this; the
    check belongs to all of them, not to the one that was caught.
    """

    if not text or not question:
        return text
    try:
        import grounded_answer_contract as gac
    except Exception:  # noqa: BLE001 - a contract import must never eat a reply
        return text
    ok, reason = gac.check_question_dominance(question, text)
    if ok:
        return text
    return (
        f"UNKNOWN — {agent} did not answer your question. ({reason}) The reply "
        "produced changed the subject rather than addressing it, so it is not being "
        "relayed. Nothing ran and nothing was sent."
    )


def retrieval_status_suffix(payload: Mapping[str, Any] | None) -> str:
    """Name the retrieval failure, so a bare UNKNOWN becomes actionable."""

    if not isinstance(payload, Mapping):
        return ""
    try:
        import packet_retrieval_status as prs
    except Exception:  # noqa: BLE001
        return ""
    raw = payload.get("retrieval_status")
    if not isinstance(raw, Mapping):
        return ""
    status = str(raw.get("status") or "")
    if status not in prs.FAILURE_STATUSES:
        return ""
    result = prs.RetrievalResult(
        facts=[], status=status, detail=str(raw.get("detail") or ""),
        source_path=str(raw.get("source_path") or ""),
    )
    packet = {"source_refs": list(payload.get("source_refs") or ()), "facts": []}
    return prs.answer_suffix(packet, retrieval=result)


def join(text: str, suffix: str) -> str:
    suffix = str(suffix or "").strip()
    if not suffix or suffix in str(text or ""):
        return text
    return f"{text}\n\n{suffix}".strip()


def finalize_agent_reply(
    agent: str,
    text: str,
    *,
    payload: Mapping[str, Any] | None = None,
    question: str = "",
) -> str:
    """The single egress. Every listener's final funnel calls exactly this."""

    body = str(text or "")
    name = str(agent or "agent").strip().lower() or "agent"

    if not question and isinstance(payload, Mapping):
        question = str(payload.get("source_text") or payload.get("operator_message") or "")

    body = apply_question_dominance(name, question, body)
    body = join(body, retrieval_status_suffix(payload))

    try:
        import agent_telegram_identity as ident
    except Exception:  # noqa: BLE001
        return body

    if NONCE_IN_TEXT.search(body):
        allowed, reason = ident.nonce_preview_allowed()
        if not allowed:
            return _withheld(name, reason)

    if not ident.banner_enabled():
        return body
    try:
        banner = ident.identity_banner(name)
    except Exception:  # noqa: BLE001 - an unregistered agent gets no banner, not a crash
        return body
    return body if body.startswith(banner) else f"{banner}\n{body}"


__all__ = [
    "NONCE_IN_TEXT",
    "SCHEMA_VERSION",
    "WITHHELD_PREFIX",
    "apply_question_dominance",
    "finalize_agent_reply",
    "join",
    "retrieval_status_suffix",
]
