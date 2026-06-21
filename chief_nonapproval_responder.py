"""Deterministic Chief/Guardian replies for non-approval Telegram prompts.

This module intentionally does not send messages, write ledgers, or call a model.
It only classifies the small set of operator-facing prompts that must not collapse
into the approval-status responder.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class NonApprovalResponse:
    intent: str
    reply: str
    send_performed: bool = False
    ledger_touched: bool = False

    def as_route_result(self) -> dict:
        return {
            "intent": self.intent,
            "reply": self.reply,
            "send_performed": self.send_performed,
            "ledger_touched": self.ledger_touched,
        }


def _norm(text: str) -> str:
    return " ".join(str(text or "").lower().strip().split())


def _has_any(t: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in t for phrase in phrases)


def _approval_hold_reason(t: str) -> str | None:
    send_like = _has_any(
        t,
        (
            "send",
            "email",
            "text",
            "sms",
            "submit",
            "post",
            "publish",
            "deliver",
            "pay",
        ),
    )
    approval_like = _has_any(t, ("approval", "approved", "approve", "sign off", "sign-off", "ok from", "greenlight"))
    if not send_like or not approval_like:
        return None

    missing_final_approval = _has_any(
        t,
        (
            "before approval",
            "before final approval",
            "before getting approval",
            "before approval lands",
            "before winship",
            "without approval",
            "without final approval",
            "approval missing",
            "approval pending",
            "pending approval",
            "pending final approval",
            "missing approval",
            "needs approval",
            "need approval",
            "not approved",
            "not yet approved",
            "no approval",
            "until approval",
            "until final approval",
            "until approval lands",
            "after approval",
            "after approval lands",
            "after final approval",
            "waiting on approval",
            "waiting for approval",
            "final wording approval",
        ),
    )
    if missing_final_approval:
        return "final approval is missing"

    contradictory_approval = approval_like and _has_any(
        t,
        (
            "approved but",
            "approve but",
            "approval but",
            "approved, but",
            "approve, but",
            "approval, but",
            "approved except",
            "approved however",
            "approved; but",
            "approve then",
            "approve, then",
            "approve; then",
            "approved then",
            "approved, then",
            "approved; then",
            "approval says wait",
            "approval says hold",
            "approved if",
            "approved unless",
        ),
    )
    if contradictory_approval and _has_any(
        t,
        ("send", "pay", "wait", "hold", "not yet", "before", "unless", "until", "pending", "final"),
    ):
        return "the approval is conditional or contradictory"

    return None


def looks_like_approval_status_query(text: str) -> bool:
    t = _norm(text)
    if not t:
        return False
    if _has_any(
        t,
        (
            "open approval",
            "open approvals",
            "pending approval",
            "pending approvals",
            "approval request",
            "approval requests",
            "approval status",
            "anything waiting on me",
            "what is waiting on me",
            "what's waiting on me",
            "whats waiting on me",
        ),
    ):
        return True
    return bool(re.search(r"\b(approvals?|approve|approval)\b", t) and re.search(r"\b(open|pending|waiting|status)\b", t))


def classify_nonapproval_prompt(text: str) -> str | None:
    t = _norm(text)
    if not t:
        return None
    if looks_like_approval_status_query(t):
        return "approval_status"
    if _has_any(t, ("wire ", "zelle", "venmo", "ach", "bank transfer", "pay $", "send $")):
        return "money_block"
    if re.search(r"\$\s*\d", t) and _has_any(t, ("send", "wire", "pay", "transfer", "money")):
        return "money_block"
    if _approval_hold_reason(t) is not None:
        return "guardian_judgment_block"
    if _has_any(t, ("is it safe to send", "safe to send", "should i send")):
        return "safety_judgment"
    if _has_any(
        t,
        (
            "send an email",
            "send email",
            "draft and send",
            "send a text",
            "send sms",
            "email my",
            "email to",
            "send this",
        ),
    ):
        return "send_hold_stage_deny"
    if _has_any(
        t,
        (
            "what can you help",
            "what can you do",
            "what do you do",
            "what's your job",
            "whats your job",
            "your job",
            "what do you protect",
            "protect against",
            "capabilities",
        ),
    ):
        return "capability"
    if _has_any(t, ("next best move", "what should i do next", "what's next", "whats next")):
        return "next_move"
    if re.search(r"\bflorble\b|\?\?\?|^\W*$", t):
        return "clarification"
    return None


def _approval_status_reply(surface: str) -> str:
    if surface == "guardian":
        return "No pending approval requests."
    return "No pending approval requests."


def _chief_reply(intent: str) -> str:
    if intent == "approval_status":
        return _approval_status_reply("chief")
    if intent == "capability":
        return (
            "Chief handles HITL approvals, safe staging/denial, and operational routing for OpenClaw. "
            "I can check approvals, stage drafts, route bounded work, and say no when a request would "
            "send, spend, or mutate under SEND_HOLD."
        )
    if intent == "send_hold_stage_deny":
        return (
            "Understood. Nothing was sent. SEND_HOLD is active, so I can only stage a draft or approval "
            "packet and ask for explicit confirmation before any external send."
        )
    if intent == "money_block":
        return (
            "No money moved. SEND_HOLD blocks payments and transfers; Chief can only stage a bounded "
            "review packet for explicit approval."
        )
    if intent == "next_move":
        return (
            "Chief handles approvals and safe operational routing. For a next-best-move call, ask "
            "Cassandra for prioritization or give Chief a concrete workflow to stage. I will not dispatch "
            "or send from this prompt."
        )
    if intent == "safety_judgment":
        return (
            "I can stage the question, but I need the actual message, recipient, and intended action. "
            "Nothing was sent under SEND_HOLD."
        )
    if intent == "guardian_judgment_block":
        return (
            "STAGE/BLOCK: hold it. Nothing was sent because final or unambiguous approval is missing; "
            "I can only stage this for review under SEND_HOLD."
        )
    return (
        "I do not have enough signal to route that. Say whether you want approval status, a safe staged "
        "draft, or an operational handoff."
    )


def _guardian_reply(intent: str) -> str:
    if intent == "approval_status":
        return _approval_status_reply("guardian")
    if intent == "capability":
        return (
            "Guardian protects the boundary before high-risk actions. I check sends, money moves, "
            "deletions, and protected access. If proof or approval is missing, I block the action in "
            "plain English."
        )
    if intent == "send_hold_stage_deny":
        return (
            "Nothing was sent. SEND_HOLD is active, so this is blocked until there is an exact draft, "
            "proof, and explicit approval. I can review the proposed send, but I will not claim it happened."
        )
    if intent == "money_block":
        return (
            "No money moved. I block money actions under SEND_HOLD. They need exact scope, proof, and "
            "explicit approval before anything can run."
        )
    if intent == "safety_judgment":
        return (
            "I can make a safety call, but I need the actual message, recipient, and intended action. "
            "Nothing was sent."
        )
    if intent == "guardian_judgment_block":
        return (
            "STAGE/BLOCK: hold it. Nothing was sent because final or unambiguous approval is missing; "
            "I can only review or stage it under SEND_HOLD."
        )
    if intent == "next_move":
        return (
            "Guardian can tell you whether a proposed action is safe to run. Send the action and the "
            "proof you have; I will block it if the boundary is not met."
        )
    return (
        "I cannot tell what you want me to protect or review. Send the action, recipient, and risk you "
        "want checked."
    )


def nonapproval_response_for_text(text: str, *, surface: str = "chief") -> NonApprovalResponse | None:
    intent = classify_nonapproval_prompt(text)
    if intent is None:
        return None
    reply = _guardian_reply(intent) if surface == "guardian" else _chief_reply(intent)
    return NonApprovalResponse(intent=intent, reply=reply)


def guardian_no_pending_reply(text: str) -> str:
    response = nonapproval_response_for_text(text, surface="guardian")
    if response is not None:
        return response.reply
    return _guardian_reply("clarification")
