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
from typing import Any, Callable, Mapping, Sequence

from business_ops_ledger import (
    append_event,
    append_packet_receipt,
    append_retrieval_receipt,
    append_side_effect,
    init_business_ops_ledger,
)
from agent_voice_profiles import voice_profile_ref_for_speaker
import hitl_action_service
from cassandra_recommendation_loop import Recommendation, emit_recommendation, get_recommendation


CORRESPONDENCE_WATCHER_VERSION = "correspondence_watcher_v0"
REYNOLDS_REPLY_WATCH_VERSION = "reynolds_reply_watch_v0"
NILES_PERSONA_SOURCE_REF = ".claude/commands/niles.md"
WINSHIP_REPLY_VOICE_PROFILE_REF = voice_profile_ref_for_speaker("niles")
WINSHIP_REPLY_VIBE_PROFILE_REF = "agent_vibe_profile:niles"
WINSHIP_REPLY_AUTHOR = "winship_via_niles_voice"
REYNOLDS_REPLY_SENDER = "reservations@reynoldstavern.com"
REYNOLDS_REPLY_SUBJECT_FRAGMENT = "June 27 music at Reynolds Tavern"
GMAIL_SCOPE_DECISION_FOR_WINSHIP = {
    "decision_owner": "Winship",
    "decision_status": "pending",
    "watcher_recommended_scope": "https://www.googleapis.com/auth/gmail.readonly",
    "watcher_reason": "The correspondence watcher needs readonly access only to inspect selected thread bodies before drafting grounded replies.",
    "watcher_scopes_not_requested": (
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/gmail.send",
    ),
    "future_send_scope_decision": "A live email_send transport needs a separate Winship decision after SEND_HOLD lifts; this module does not request or activate send scope.",
    "send_authority_granted": False,
}
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
    gmail_scope_decision_required: bool = False
    gmail_scope_decision: dict[str, Any] = field(default_factory=dict)
    voice_profile_ref: str = WINSHIP_REPLY_VOICE_PROFILE_REF
    vibe_profile_ref: str = WINSHIP_REPLY_VIBE_PROFILE_REF
    voice_persona_source_ref: str = NILES_PERSONA_SOURCE_REF
    draft_author: str = WINSHIP_REPLY_AUTHOR
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
            "gmail_scope_decision_required": self.gmail_scope_decision_required,
            "gmail_scope_decision": dict(self.gmail_scope_decision),
            "voice_profile_ref": self.voice_profile_ref,
            "vibe_profile_ref": self.vibe_profile_ref,
            "voice_persona_source_ref": self.voice_persona_source_ref,
            "draft_author": self.draft_author,
            "receipts": dict(self.receipts),
        }


@dataclass(frozen=True)
class ReynoldsReplyWatchResult:
    status: str
    matched: bool
    thread_id: str
    sender_email: str
    subject: str
    notification_text: str
    notification_result: dict[str, Any]
    recommendation_id: str | None
    recommendation_status: str | None
    plan: CorrespondencePlan | None
    gmail_api_called: bool = False
    gmail_body_read_performed: bool = False
    email_send_performed: bool = False
    external_send_performed: bool = False
    raw_body_stored: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": REYNOLDS_REPLY_WATCH_VERSION,
            "status": self.status,
            "matched": self.matched,
            "thread_id": self.thread_id,
            "sender_email": self.sender_email,
            "subject": self.subject,
            "notification_text": self.notification_text,
            "notification_result": dict(self.notification_result),
            "recommendation_id": self.recommendation_id,
            "recommendation_status": self.recommendation_status,
            "plan": self.plan.to_dict() if self.plan else None,
            "gmail_api_called": self.gmail_api_called,
            "gmail_body_read_performed": self.gmail_body_read_performed,
            "email_send_performed": self.email_send_performed,
            "external_send_performed": self.external_send_performed,
            "raw_body_stored": self.raw_body_stored,
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


def _extract_email(value: str) -> str:
    match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", value or "")
    return match.group(0).lower() if match else _clean_text(value).lower()


def _message_sender_email(message: Mapping[str, Any]) -> str:
    for key in ("sender_email", "from_email", "from", "sender"):
        value = str(message.get(key) or "")
        if value:
            return _extract_email(value)
    return ""


def _message_thread_id(message: Mapping[str, Any]) -> str:
    return _clean_text(str(message.get("thread_id") or message.get("gmail_thread_id") or message.get("conversation_id") or ""))


def _message_subject(message: Mapping[str, Any]) -> str:
    return _clean_text(str(message.get("subject") or ""))


def _safe_message_summary(message: Mapping[str, Any]) -> str:
    return _clean_text(str(message.get("body_summary") or message.get("snippet") or ""))


def _matches_reynolds_reply(message: Mapping[str, Any]) -> bool:
    sender = _message_sender_email(message)
    subject = _message_subject(message).lower()
    thread_id = _message_thread_id(message).lower()
    sender_matches = sender == REYNOLDS_REPLY_SENDER
    subject_matches = (
        "june 27" in subject
        and "reynolds" in subject
        and ("music" in subject or "tavern" in subject)
    )
    thread_matches = "reynolds" in thread_id and ("june27" in thread_id or "june_27" in thread_id or "music" in thread_id)
    return sender_matches and (subject_matches or thread_matches)


def _reply_subject(subject: str) -> str:
    cleaned = _clean_text(subject)
    if not cleaned:
        return f"Re: {REYNOLDS_REPLY_SUBJECT_FRAGMENT}"
    return cleaned if cleaned.lower().startswith("re:") else f"Re: {cleaned}"


def _payload_hash(*, recipient: str, subject: str, body: str) -> str:
    joined = "\0".join([recipient, subject, body])
    return "sha256:" + hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _record_only_operator_notification(text: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": "recorded_operator_notification",
        "channel": "operator_channel_record_only",
        "sent": False,
        "text_hash": _payload_hash(recipient="operator", subject="reynolds_reply_notification", body=text),
        "metadata": dict(metadata),
    }


def _notify_operator(
    text: str,
    *,
    metadata: Mapping[str, Any],
    operator_notifier: Callable[[str, Mapping[str, Any]], Mapping[str, Any] | None] | None,
) -> dict[str, Any]:
    notifier = operator_notifier or _record_only_operator_notification
    try:
        result = notifier(text, metadata)
    except Exception as exc:
        return {
            "status": "operator_notification_failed",
            "sent": False,
            "error_type": type(exc).__name__,
            "error": str(exc)[:200],
        }
    return dict(result or {"status": "operator_notification_recorded", "sent": False})


def _record_reynolds_notification(
    *,
    event_id: str,
    thread_id: str,
    subject: str,
    notification_text: str,
    notification_result: Mapping[str, Any],
    recommendation_id: str | None,
    db_path: str | Path | None,
) -> None:
    path = str(db_path) if db_path is not None else None
    append_event(
        event_id=event_id,
        event_type="reynolds_reply_detected",
        actor="cassandra",
        operator_visible_summary="Reynolds replied; Cassandra prepared an operator notification and recommendation.",
        raw_sensitive_data_stored=False,
        replay_safe=True,
        db_path=path,
    )
    append_packet_receipt(
        {
            "packet_id": _stable_id("reynolds_reply_notification", event_id),
            "intent_name": "reynolds_reply_operator_notification",
            "request_category": "operator_notification",
            "actor_name": "cassandra",
            "execution_authority": False,
            "approval_required": False,
            "approval_tier": None,
            "action_status": str(notification_result.get("status") or "recorded"),
            "thread_id": thread_id,
            "subject": subject,
            "notification_text": notification_text,
            "notification_sent": bool(notification_result.get("sent")),
            "recommendation_id": recommendation_id,
            "gmail_api_called": False,
            "email_send_performed": False,
            "external_send_performed": False,
            "raw_body_stored": False,
        },
        event_id=event_id,
        db_path=path,
    )


def _draft_reynolds_reply(classification: str, gig_context: dict[str, Any]) -> str:
    venue = gig_context.get("venue_name") or "the venue"
    display_date = gig_context.get("display_date") or gig_context.get("date") or "the date"
    display_time = gig_context.get("display_time") or "the booked time"
    covering_for = gig_context.get("covering_for") or "the performer"
    if classification == "confirmation":
        return (
            "Hi Sally,\n\n"
            f"Great, thank you. I have {display_date}, {display_time} at {venue} "
            f"for covering {covering_for}. I will keep the set tidy and easy for the room. "
            "Looking forward to it.\n\n"
            "Warmly,\nWinship"
        )
    if classification == "question":
        return (
            "Hi Sally,\n\n"
            f"Thanks for checking in. I have {display_date}, {display_time} at {venue} "
            "as the working booking details. Tell me what needs clarifying and I will tighten it up.\n\n"
            "Warmly,\nWinship"
        )
    return (
        "Hi Sally,\n\n"
        f"Thanks for the update. I have {display_date}, {display_time} at {venue} "
        "as the current booking context. I will review the details before anything goes out.\n\n"
        "Warmly,\nWinship"
    )


def _build_reynolds_reply_recommendation(
    *,
    thread_id: str,
    sender_email: str,
    subject: str,
    safe_summary: str,
    draft_text: str,
) -> Recommendation:
    reply_subject = _reply_subject(subject)
    payload_hash = _payload_hash(recipient=sender_email, subject=reply_subject, body=draft_text)
    recommendation_id = _stable_id("reynolds_reply_recommendation", thread_id, sender_email, payload_hash)
    request_id = _stable_id("reynolds_reply_exact_send", thread_id, payload_hash)
    return Recommendation(
        id=recommendation_id,
        surface="correspondence.reynolds",
        summary="Draft a reply to Sally at Reynolds Tavern.",
        proposed_action={
            "action_type": hitl_action_service.ACTION_TYPE_EXACT_GMAIL_SEND,
            "summary": "Send reviewed Reynolds Tavern reply to Sally.",
            "payload": {
                "recipient": sender_email,
                "subject": reply_subject,
                "body": draft_text,
                "body_preview": draft_text[:500],
                "payload_hash": payload_hash,
                "request_id": request_id,
                "objective_id": "reynolds_reply_watch",
                "thread_id": thread_id,
                "body_stored_in_recommendation": True,
                "body_stored_in_hitl_queue": True,
            },
            "request_id": request_id,
            "owner_agent": "cassandra",
            "owner_objective_id": "reynolds_reply_watch",
            "risk_warning": "External email remains approval-gated and SEND_HOLD-blocked until the normal gate allows it.",
            "route_back": {
                "type": "cassandra_exact_send_executor",
                "objective_id": "reynolds_reply_watch",
                "thread_id": thread_id,
                "executor_must_use_reviewed_gate": True,
                "guardian_calls_gmail_or_broker_directly": False,
            },
        },
        rationale=f"Sally replied about Reynolds Tavern: {safe_summary}",
        confidence=0.82,
        created_by="cassandra",
    )


def watch_reynolds_reply(
    *,
    inbox_messages: Sequence[Mapping[str, Any]] | None = None,
    inbox_reader: Callable[[], Sequence[Mapping[str, Any]]] | None = None,
    gmail_readonly_scope_approved: bool = False,
    operator_notifier: Callable[[str, Mapping[str, Any]], Mapping[str, Any] | None] | None = None,
    db_path: str | Path | None = None,
) -> ReynoldsReplyWatchResult:
    """Detect a Reynolds reply from supplied/read-only inbox metadata.

    The default path is record-only and does not call Gmail or Telegram. A live
    caller must explicitly pass an already-approved read-only inbox reader and
    an operator notifier.
    """
    if inbox_messages is None:
        if inbox_reader is None:
            return ReynoldsReplyWatchResult(
                status="no_inbox_source",
                matched=False,
                thread_id="",
                sender_email="",
                subject="",
                notification_text="",
                notification_result={"status": "not_attempted", "sent": False},
                recommendation_id=None,
                recommendation_status=None,
                plan=None,
            )
        if not gmail_readonly_scope_approved:
            return ReynoldsReplyWatchResult(
                status="gmail_readonly_scope_required",
                matched=False,
                thread_id="",
                sender_email="",
                subject="",
                notification_text="",
                notification_result={"status": "not_attempted_scope_required", "sent": False},
                recommendation_id=None,
                recommendation_status=None,
                plan=None,
            )
        messages = list(inbox_reader())
        gmail_api_called = True
        gmail_body_read_performed = True
    else:
        messages = list(inbox_messages)
        gmail_api_called = False
        gmail_body_read_performed = False

    match = next((message for message in messages if _matches_reynolds_reply(message)), None)
    if match is None:
        return ReynoldsReplyWatchResult(
            status="no_reynolds_reply",
            matched=False,
            thread_id="",
            sender_email="",
            subject="",
            notification_text="",
            notification_result={"status": "not_attempted_no_match", "sent": False},
            recommendation_id=None,
            recommendation_status=None,
            plan=None,
            gmail_api_called=gmail_api_called,
            gmail_body_read_performed=gmail_body_read_performed,
        )

    thread_id = _message_thread_id(match) or _stable_id("reynolds_thread", _message_subject(match), _message_sender_email(match))
    sender_email = _message_sender_email(match)
    subject = _message_subject(match)
    safe_summary = _safe_message_summary(match)
    if not safe_summary:
        plan = plan_reynolds_correspondence_reply(
            thread_id=thread_id,
            sender_name="Sally",
            sender_email=sender_email,
            db_path=db_path,
            source_channel="reynolds_reply_watch",
        )
        return ReynoldsReplyWatchResult(
            status="needs_gmail_readonly_scope",
            matched=True,
            thread_id=thread_id,
            sender_email=sender_email,
            subject=subject,
            notification_text="",
            notification_result={"status": "not_attempted_missing_safe_summary", "sent": False},
            recommendation_id=None,
            recommendation_status=None,
            plan=plan,
            gmail_api_called=gmail_api_called,
            gmail_body_read_performed=gmail_body_read_performed,
        )

    plan = plan_reynolds_correspondence_reply(
        thread_id=thread_id,
        sender_name="Sally",
        sender_email=sender_email,
        body_summary=safe_summary,
        db_path=db_path,
        source_channel="reynolds_reply_watch",
    )
    notification_text = f"Reynolds replied - here's what Sally said: {safe_summary}"
    recommendation = _build_reynolds_reply_recommendation(
        thread_id=thread_id,
        sender_email=sender_email,
        subject=subject,
        safe_summary=safe_summary,
        draft_text=plan.draft_text or "",
    )
    try:
        recommendation_outcome = emit_recommendation(recommendation, db_path=db_path)
        recommendation_status = recommendation_outcome.status
    except ValueError:
        existing = get_recommendation(recommendation.id, db_path=db_path)
        recommendation_status = str((existing or {}).get("status") or "already_exists")

    notification_result = _notify_operator(
        notification_text,
        metadata={
            "thread_id": thread_id,
            "sender_email": sender_email,
            "subject": subject,
            "recommendation_id": recommendation.id,
            "email_send_performed": False,
        },
        operator_notifier=operator_notifier,
    )
    event_id = _stable_id("reynolds_reply_watch", thread_id, safe_summary)
    _record_reynolds_notification(
        event_id=event_id,
        thread_id=thread_id,
        subject=subject,
        notification_text=notification_text,
        notification_result=notification_result,
        recommendation_id=recommendation.id,
        db_path=db_path,
    )

    return ReynoldsReplyWatchResult(
        status="reynolds_reply_detected",
        matched=True,
        thread_id=thread_id,
        sender_email=sender_email,
        subject=subject,
        notification_text=notification_text,
        notification_result=notification_result,
        recommendation_id=recommendation.id,
        recommendation_status=recommendation_status,
        plan=plan,
        gmail_api_called=gmail_api_called,
        gmail_body_read_performed=gmail_body_read_performed,
    )


def _gmail_scope_decision_packet(*, event_id: str, thread_id: str, sender_name: str) -> dict[str, Any]:
    decision = dict(GMAIL_SCOPE_DECISION_FOR_WINSHIP)
    return {
        "packet_id": _stable_id("gmail_scope_decision", thread_id, sender_name),
        "intent_name": "gmail_scope_decision",
        "request_category": "winship_scope_decision_required",
        "actor_name": "guardian",
        "execution_authority": False,
        "approval_required": True,
        "approval_tier": "winship_gmail_scope_decision",
        "action_status": "blocked_pending_winship_scope_decision",
        "thread_id": thread_id,
        "sender_name": sender_name,
        "decision_for_winship": decision,
        "event_ref": event_id,
        "raw_body_stored": False,
        "gmail_api_called": False,
        "email_send_performed": False,
    }


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
        scope_packet = _gmail_scope_decision_packet(
            event_id=event_id,
            thread_id=thread_id,
            sender_name=sender_name,
        )
        append_event(
            event_id=event_id,
            event_type="correspondence_watch_scope_needed",
            actor="guardian",
            operator_visible_summary="Gmail reply metadata is visible, but body reading needs explicit scope approval.",
            raw_sensitive_data_stored=False,
            replay_safe=True,
            db_path=path,
        )
        append_packet_receipt(scope_packet, event_id=event_id, db_path=path)
        append_retrieval_receipt(
            packet_id=scope_packet["packet_id"],
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
            gmail_scope_decision_required=True,
            gmail_scope_decision=dict(GMAIL_SCOPE_DECISION_FOR_WINSHIP),
            receipts={
                "event_id": event_id,
                "scope_decision_packet_id": scope_packet["packet_id"],
                "retrieval_receipt_packet_id": scope_packet["packet_id"],
            },
        )

    classification = _classify_reply(safe_summary)
    context = dict(REYNOLDS_GIG_CONTEXT)
    context.update(gig_context or {})
    draft_text = _draft_reynolds_reply(classification, context)

    append_event(
        event_id=event_id,
        event_type="correspondence_reply_candidate",
        actor="niles",
        operator_visible_summary=f"Prepared draft-only Winship/Niles-voice Reynolds reply candidate for {sender_name}; no send.",
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
            "actor_name": "niles",
            "draft_author": WINSHIP_REPLY_AUTHOR,
            "voice_profile_ref": WINSHIP_REPLY_VOICE_PROFILE_REF,
            "vibe_profile_ref": WINSHIP_REPLY_VIBE_PROFILE_REF,
            "voice_persona_source_ref": NILES_PERSONA_SOURCE_REF,
            "execution_authority": False,
            "approval_required": True,
            "approval_tier": "operator_final_send",
            "action_status": "draft_only_pending_approval",
            "thread_id": thread_id,
            "sender_name": sender_name,
            "sender_email_present": bool(sender_email),
            "classification": classification,
            "draft_summary": "Winship/Niles-voice Reynolds reply candidate prepared from fixture or approved summary.",
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
    "GMAIL_SCOPE_DECISION_FOR_WINSHIP",
    "NILES_PERSONA_SOURCE_REF",
    "REYNOLDS_REPLY_SENDER",
    "REYNOLDS_REPLY_SUBJECT_FRAGMENT",
    "REYNOLDS_REPLY_WATCH_VERSION",
    "REYNOLDS_GIG_CONTEXT",
    "ReynoldsReplyWatchResult",
    "WINSHIP_REPLY_AUTHOR",
    "WINSHIP_REPLY_VOICE_PROFILE_REF",
    "plan_reynolds_correspondence_reply",
    "watch_reynolds_reply",
]
