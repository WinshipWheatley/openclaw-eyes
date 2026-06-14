"""Safe correspondence watcher scaffold for approval-gated email replies.

This module is local-only. It accepts already-available metadata or explicit
test fixture text, drafts a deterministic reply summary, and creates an
approval-gated `email_send` packet. It does not call Gmail, Calendar, models,
or any external send surface.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from business_ops_ledger import (
    append_event,
    append_packet_receipt,
    append_retrieval_receipt,
    append_side_effect,
    init_business_ops_ledger,
)


CORRESPONDENCE_WATCHER_VERSION = "correspondence_watcher_v0"
REYNOLDS_GIG_CONTEXT = {
    "venue_name": "Reynolds Tavern",
    "date": "2026-06-27",
    "display_date": "June 27, 2026",
    "start_time": "19:00",
    "end_time": "22:00",
    "display_time": "7:00-10:00 PM",
    "covering_for": "Mike Heuer",
}


@dataclass(frozen=True)
class CorrespondencePlan:
    status: str
    thread_id: str
    classification: str
    draft_text: str | None
    packet_id: str | None
    side_effect_id: str | None
    approval_required: bool = True
    email_send_performed: bool = False
    gmail_api_called: bool = False
    gmail_body_read_performed: bool = False
    calendar_api_called: bool = False
    calendar_event_created: bool = False
    raw_body_stored: bool = False
    scope_upgrade_required: bool = False
    receipts: dict[str, str | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CORRESPONDENCE_WATCHER_VERSION,
            "status": self.status,
            "thread_id": self.thread_id,
            "classification": self.classification,
            "draft_text": self.draft_text,
            "packet_id": self.packet_id,
            "side_effect_id": self.side_effect_id,
            "approval_required": self.approval_required,
            "email_send_performed": self.email_send_performed,
            "gmail_api_called": self.gmail_api_called,
            "gmail_body_read_performed": self.gmail_body_read_performed,
            "calendar_api_called": self.calendar_api_called,
            "calendar_event_created": self.calendar_event_created,
            "raw_body_stored": self.raw_body_stored,
            "scope_upgrade_required": self.scope_upgrade_required,
            "receipts": dict(self.receipts),
        }


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _classify_reply(text_or_summary: str) -> str:
    text = text_or_summary.lower()
    if any(word in text for word in ("confirmed", "confirm", "sounds good", "great", "yes", "perfect")):
        return "confirmation"
    if "reschedule" in text or "different time" in text or "change" in text:
        return "reschedule_or_change"
    if "?" in text or any(word in text for word in ("question", "what", "when", "where", "how")):
        return "question"
    return "needs_operator_review"


def _draft_reynolds_reply(classification: str, gig_context: dict[str, Any]) -> str:
    venue = gig_context.get("venue_name") or "the venue"
    display_date = gig_context.get("display_date") or gig_context.get("date") or "the date"
    display_time = gig_context.get("display_time") or "the booked time"
    covering_for = gig_context.get("covering_for") or "the performer"
    if classification == "confirmation":
        return (
            "Hi Sally,\n\n"
            f"Great, thank you. I have {display_date}, {display_time} at {venue} "
            f"for covering {covering_for}. Looking forward to it.\n\n"
            "Best,\nWinship"
        )
    if classification == "question":
        return (
            "Hi Sally,\n\n"
            f"Thanks for checking in. I have {display_date}, {display_time} at {venue} "
            "as the working booking details. Let me know what you need clarified and I will tighten it up.\n\n"
            "Best,\nWinship"
        )
    return (
        "Hi Sally,\n\n"
        f"Thanks for the update. I have {display_date}, {display_time} at {venue} "
        "as the current booking context. I will review the details before anything goes out.\n\n"
        "Best,\nWinship"
    )


def plan_reynolds_correspondence_reply(
    *,
    thread_id: str,
    sender_name: str = "Sally",
    sender_email: str | None = None,
    body_text: str | None = None,
    body_summary: str | None = None,
    db_path: str | Path | None = None,
    gig_context: dict[str, Any] | None = None,
    source_channel: str = "correspondence_watcher_fixture",
) -> CorrespondencePlan:
    """Plan a Reynolds reply from supplied safe context without external calls."""

    path = str(db_path) if db_path is not None else None
    init_business_ops_ledger(path)
    thread_id = _clean_text(thread_id)
    if not thread_id:
        raise ValueError("thread_id is required")
    sender_name = _clean_text(sender_name) or "the sender"
    safe_summary = _clean_text(body_summary or body_text or "")
    event_id = _stable_id("correspondence_watch", thread_id, safe_summary or "scope_needed")

    if not safe_summary:
        append_event(
            event_id=event_id,
            event_type="correspondence_watch_scope_needed",
            actor="cassandra",
            operator_visible_summary="Gmail reply metadata is visible, but body reading needs explicit scope approval.",
            raw_sensitive_data_stored=False,
            replay_safe=True,
            db_path=path,
        )
        append_retrieval_receipt(
            packet_id=event_id,
            source="gmail.readonly",
            attempted=True,
            blocked=True,
            reason="gmail body scope not approved; metadata-only watcher cannot draft a grounded reply",
            raw_sensitive_data_stored=False,
            db_path=path,
        )
        return CorrespondencePlan(
            status="needs_gmail_readonly_scope",
            thread_id=thread_id,
            classification="body_unavailable",
            draft_text=None,
            packet_id=None,
            side_effect_id=None,
            scope_upgrade_required=True,
            receipts={"event_id": event_id, "retrieval_receipt": event_id},
        )

    classification = _classify_reply(safe_summary)
    context = dict(REYNOLDS_GIG_CONTEXT)
    context.update(gig_context or {})
    draft_text = _draft_reynolds_reply(classification, context)

    append_event(
        event_id=event_id,
        event_type="correspondence_reply_candidate",
        actor="cassandra",
        operator_visible_summary=f"Prepared draft-only Reynolds reply candidate for {sender_name}; no send.",
        raw_sensitive_data_stored=False,
        replay_safe=True,
        db_path=path,
    )

    from chief_compose import compose

    compose_result = compose(
        (
            f"Draft an email reply to {sender_name} about the Reynolds Tavern gig on "
            f"{context['display_date']} from {context['display_time']}."
        ),
        source_channel=source_channel,
        requested_by="winship",
        source_message_id=thread_id,
        db_path=path,
    )
    packet_id = compose_result.packet_id
    side_effect_id = append_side_effect(
        packet_id=packet_id or event_id,
        effect_type="email_draft_candidate",
        status="pending_approval",
        approval_required=True,
        approval_tier="operator_final_send",
        replay_safe=False,
        external_ref=None,
        db_path=path,
    )
    append_packet_receipt(
        {
            "packet_id": _stable_id("correspondence_packet", thread_id, packet_id or "no_packet"),
            "intent_name": "monitored_email_conversation",
            "request_category": "email_reply_candidate",
            "actor_name": "cassandra",
            "execution_authority": False,
            "approval_required": True,
            "approval_tier": "operator_final_send",
            "action_status": "draft_only_pending_approval",
            "thread_id": thread_id,
            "sender_name": sender_name,
            "sender_email_present": bool(sender_email),
            "classification": classification,
            "draft_summary": "Winship-voice Reynolds reply candidate prepared from fixture or approved summary.",
            "raw_body_stored": False,
            "email_send_performed": False,
            "gmail_api_called": False,
            "calendar_api_called": False,
        },
        event_id=event_id,
        db_path=path,
    )
    return CorrespondencePlan(
        status="draft_ready_pending_approval",
        thread_id=thread_id,
        classification=classification,
        draft_text=draft_text,
        packet_id=packet_id,
        side_effect_id=side_effect_id,
        receipts={"event_id": event_id, "agent_work_packet_id": packet_id, "side_effect_id": side_effect_id},
    )


__all__ = [
    "CORRESPONDENCE_WATCHER_VERSION",
    "CorrespondencePlan",
    "REYNOLDS_GIG_CONTEXT",
    "plan_reynolds_correspondence_reply",
]
