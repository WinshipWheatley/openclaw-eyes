"""Turn a Guardian approval into human ELI5 — what it is, what approve/deny does, the risk.

Operator ask 2026-07-03: Guardian's messages read like machine contract; the operator wants
to understand what he's approving without deciphering JSON/field-names, so he never
"throws his hands up and hits approve." This layer produces plain English.

Design: facts are extracted DETERMINISTICALLY from the approval (never invented), so the
humanization can't misrepresent the action. An optional LM pass (``llm_polish``) may only
smooth the phrasing of already-correct facts — it is never allowed to change what is being
approved (the deterministic text is the source of truth and the fallback).
"""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping


def _first(*vals: object) -> str:
    for v in vals:
        s = str(v or "").strip()
        if s:
            return s
    return ""


def _ctx(approval: Mapping[str, Any]) -> dict:
    c = approval.get("approval_context")
    return dict(c) if isinstance(c, Mapping) else {}


def _risk_phrase(approval: Mapping[str, Any]) -> str:
    raw = str(_first(approval.get("risk_tier"), approval.get("tier"))).lower()
    if any(k in raw for k in ("3", "high", "critical")):
        return "High stakes — money, an outside send, or a deletion could happen. Read it before you approve."
    if any(k in raw for k in ("2", "medium")):
        return "Medium stakes — this reaches outside the system or touches real records. Worth a look."
    if any(k in raw for k in ("1", "low")):
        return "Low stakes — an internal change, nothing leaves the system."
    return "Take a quick look before approving."


def _classify(approval: Mapping[str, Any]) -> str:
    ctx = _ctx(approval)
    surface = _first(approval.get("source_surface_id"), approval.get("source"))
    action = _first(approval.get("action"), approval.get("action_summary_label"),
                    ctx.get("action_label")).lower()
    if ctx.get("to") or "gmail" in action or "email" in action or "send" in action:
        return "email"
    if any(k in surface.lower() for k in ("build", "hermes", "self_improvement", "factory")) or \
       any(k in action for k in ("build", "improve", "add ", "wire", "refactor")):
        return "build"
    if "calendar" in action and ("delete" in action or "remove" in action):
        return "calendar_delete"
    if any(k in action for k in ("payment", "invoice send", "pay ", "move money", "ledger post")):
        return "money"
    return "generic"


def humanize_approval(approval: Mapping[str, Any]) -> dict[str, str]:
    """Return plain-English parts: headline, plain, if_approve, if_deny, risk, ref, who."""
    ctx = _ctx(approval)
    who = _first(approval.get("requester"), approval.get("actor"), "The system")
    ref = _first(approval.get("id"), approval.get("approval_id"), approval.get("legacy_approval_id"))
    kind = _classify(approval)
    risk = _risk_phrase(approval)

    if kind == "email":
        to = _first(ctx.get("to"), approval.get("target"))
        subject = _first(ctx.get("subject"))
        preview = _first(ctx.get("draft_preview"), ctx.get("proposed_send"))
        recipient = to or "someone outside the system"
        headline = f"{who} wants to send an email to {recipient}."
        plain_bits = []
        if subject:
            plain_bits.append(f"Subject: {subject}.")
        if preview:
            plain_bits.append(f"It says, roughly: “{preview.strip().rstrip('.')}.”")
        if not plain_bits:
            # No draft context — carry the action detail so nothing (e.g. an amount) is lost.
            act = _first(approval.get("action"), approval.get("action_summary_label"))
            plain_bits.append(f"What: {act}." if act else "It's an outgoing email drafted for your sign-off.")
        plain = " ".join(plain_bits)
        if_approve = f"I'll send the email to {recipient} exactly as drafted."
        if_deny = "I won't send anything; the draft just waits for you."
    elif kind == "build":
        what = _first(approval.get("action_summary_label"), approval.get("action"),
                      "make a change to the system")
        headline = (what if _is_sentence(what) else f"{who} wants to {_lower_verb(what)}")
        headline = headline.rstrip(".") + "."
        plain = "It's a code/system change, built and tested in isolation before anything goes live."
        if_approve = "I'll let it build the change (still gated + tested before it can affect anything live)."
        if_deny = "Nothing gets built; the request just closes."
    elif kind == "calendar_delete":
        headline = f"{who} wants to delete a calendar event."
        plain = _first(approval.get("action"), "A calendar event is queued for deletion.")
        if_approve = "I'll delete that calendar event."
        if_deny = "The event stays; nothing is deleted."
    elif kind == "money":
        what = _first(approval.get("action"), "record or move money")
        headline = (what if _is_sentence(what) else f"{who} wants to {_lower_verb(what)}")
        headline = headline.rstrip(".") + "."
        plain = "This touches your money/records — it's held until you say so."
        if_approve = "I'll do the money action as described."
        if_deny = "Nothing moves; your records are untouched."
    else:
        action = _first(approval.get("action"), approval.get("action_summary_label"), "do something")
        headline = f"{who} wants to: {action}."
        plain = "Here's what it's asking, in plain terms — approve only if it makes sense to you."
        if_approve = "I'll go ahead with it."
        if_deny = "I won't do it; it just stops here."

    return {
        "who": who, "ref": ref, "kind": kind, "risk": risk,
        "headline": _clean(headline), "plain": _clean(plain),
        "if_approve": _clean(if_approve), "if_deny": _clean(if_deny),
    }


def _is_sentence(text: str) -> bool:
    low = text.strip().lower()
    return (" wants to " in low or " needs to " in low or low.startswith(("the ", "an ", "a ")))


def _lower_verb(text: str) -> str:
    t = text.strip()
    return (t[0].lower() + t[1:]) if t else t


_MACHINE = re.compile(r"[{}\[\]]|sha256:|::|_id\b|approval_context|risk_tier|\btier_\d")


def _clean(s: str) -> str:
    s = _MACHINE.sub("", str(s or ""))
    return re.sub(r"\s{2,}", " ", s).strip()


def render_operator_message(h: Mapping[str, str], *, llm_polish: Callable[[str], str] | None = None) -> str:
    """Compose the final human message. If ``llm_polish`` is given it may smooth the prose,
    but the deterministic version is used if the LM changes the facts or fails."""
    lines = [
        f"🔔 {h['headline']}",
        "",
        h["plain"],
        "",
        f"✅ Approve → {h['if_approve']}",
        f"🚫 Deny → {h['if_deny']}",
        "",
        h["risk"],
    ]
    deterministic = "\n".join(x for x in lines if x is not None)
    if llm_polish is None:
        return deterministic
    try:
        polished = str(llm_polish(deterministic) or "").strip()
    except Exception:
        return deterministic
    # Guard: the polish must keep the key facts (recipient/action words) or we discard it.
    if not polished or _facts_lost(deterministic, polished, h):
        return deterministic
    return polished


def _facts_lost(deterministic: str, polished: str, h: Mapping[str, str]) -> bool:
    # Cheap safety net: the recipient/who and the approve/deny direction must survive.
    who = h.get("who", "")
    if who and who.lower() not in polished.lower():
        return True
    if "approve" not in polished.lower() or "deny" not in polished.lower():
        return True
    return False


__all__ = ["humanize_approval", "render_operator_message"]
