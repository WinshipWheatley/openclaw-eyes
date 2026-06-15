import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import hitl_action_service
import hitl_pending_store
from cassandra_recommendation_loop import accept_recommendation, get_recommendation
from correspondence_watcher import (
    REYNOLDS_REPLY_SENDER,
    REYNOLDS_REPLY_SUBJECT_FRAGMENT,
    WINSHIP_REPLY_AUTHOR,
    WINSHIP_REPLY_VOICE_PROFILE_REF,
    plan_reynolds_correspondence_reply,
    watch_reynolds_reply,
)
from email_send_executor import (
    EMAIL_SEND_SURFACE,
    build_email_send_executor,
    email_send_executor_descriptor,
    email_send_executor_registered,
    execute_email_send_packet,
)
from hitl_pending_store import WAITING_FOR_APPROVAL


def _db(tmp_path: Path) -> str:
    return str(tmp_path / "correspondence.sqlite")


def _isolate_hitl(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hitl_pending_store, "HITL_STATE_PATH", tmp_path / "hitl_state.json")
    monkeypatch.setattr(hitl_pending_store, "HITL_AUDIT_LOG", tmp_path / "hitl_audit.jsonl")
    monkeypatch.setattr(hitl_pending_store, "HITL_FLAG_PATH", tmp_path / "hitl_enabled.flag")
    monkeypatch.setattr(hitl_action_service._store, "HITL_STATE_PATH", tmp_path / "hitl_state.json")
    monkeypatch.setattr(hitl_action_service._store, "HITL_AUDIT_LOG", tmp_path / "hitl_audit.jsonl")
    monkeypatch.setattr(hitl_action_service._store, "HITL_FLAG_PATH", tmp_path / "hitl_enabled.flag")


def test_correspondence_watcher_blocks_when_gmail_body_scope_missing(tmp_path):
    db_path = _db(tmp_path)

    plan = plan_reynolds_correspondence_reply(
        thread_id="thread_reynolds_001",
        sender_name="Sally",
        db_path=db_path,
    )

    assert plan.status == "needs_gmail_readonly_scope"
    assert plan.scope_upgrade_required is True
    assert plan.draft_text is None
    assert plan.email_send_performed is False
    assert plan.gmail_api_called is False
    assert plan.gmail_body_read_performed is False
    assert plan.calendar_api_called is False
    assert plan.gmail_scope_decision_required is True
    assert plan.gmail_scope_decision["decision_owner"] == "Winship"
    assert plan.gmail_scope_decision["watcher_recommended_scope"] == "https://www.googleapis.com/auth/gmail.readonly"
    assert "https://www.googleapis.com/auth/gmail.send" in plan.gmail_scope_decision["watcher_scopes_not_requested"]

    conn = sqlite3.connect(db_path)
    try:
        scope_packet = conn.execute(
            "SELECT packet_id, action_status, packet_json_safe FROM packets WHERE intent_name = 'gmail_scope_decision'"
        ).fetchone()
        assert scope_packet[1] == "blocked_pending_winship_scope_decision"
        assert "winship_scope_decision_required" in scope_packet[2]
        assert "gmail.readonly" in scope_packet[2]
        assert "gmail.send" in scope_packet[2]

        row = conn.execute(
            "SELECT packet_id, blocked, raw_sensitive_data_stored FROM retrieval_receipts WHERE source = 'gmail.readonly'"
        ).fetchone()
        assert row == (scope_packet[0], 1, 0)
    finally:
        conn.close()


def test_correspondence_watcher_creates_draft_only_email_packet_from_safe_summary(tmp_path):
    db_path = _db(tmp_path)

    plan = plan_reynolds_correspondence_reply(
        thread_id="thread_reynolds_002",
        sender_name="Sally",
        body_summary="Sally confirmed the June 27 Reynolds gig sounds good.",
        db_path=db_path,
    )

    assert plan.status == "draft_ready_pending_approval"
    assert plan.classification == "confirmation"
    assert plan.packet_id
    assert plan.side_effect_id
    assert "Hi Sally" in (plan.draft_text or "")
    assert "June 27, 2026" in (plan.draft_text or "")
    assert "set tidy and easy for the room" in (plan.draft_text or "")
    assert plan.voice_profile_ref == WINSHIP_REPLY_VOICE_PROFILE_REF
    assert plan.draft_author == WINSHIP_REPLY_AUTHOR
    assert plan.approval_required is True
    assert plan.email_send_performed is False
    assert plan.gmail_api_called is False
    assert plan.calendar_api_called is False
    assert plan.raw_body_stored is False

    conn = sqlite3.connect(db_path)
    try:
        packet = conn.execute(
            "SELECT intent_category, approval_required, execution_allowed, action_created FROM agent_work_packets WHERE packet_id = ?",
            (plan.packet_id,),
        ).fetchone()
        assert packet == ("email_send", 1, 0, 0)

        side_effect = conn.execute(
            "SELECT effect_type, status, approval_required, replay_safe FROM side_effects WHERE id = 1"
        ).fetchone()
        assert side_effect == ("email_draft_candidate", "pending_approval", 1, 0)

        receipt = conn.execute(
            "SELECT action_status, packet_json_safe FROM packets WHERE intent_name = 'monitored_email_conversation'"
        ).fetchone()
        assert receipt[0] == "draft_only_pending_approval"
        assert "raw_body_stored" in receipt[1]
        assert WINSHIP_REPLY_VOICE_PROFILE_REF in receipt[1]
        assert WINSHIP_REPLY_AUTHOR in receipt[1]
    finally:
        conn.close()


def test_correspondence_watcher_safe_summary_invokes_compose(monkeypatch, tmp_path):
    db_path = _db(tmp_path)
    calls = []

    def fake_compose(text, **kwargs):
        calls.append({"text": text, "kwargs": kwargs})
        return SimpleNamespace(packet_id="compose_packet_0030")

    monkeypatch.setattr("chief_compose.compose", fake_compose)

    plan = plan_reynolds_correspondence_reply(
        thread_id="thread_reynolds_compose_trigger",
        sender_name="Sally",
        body_summary="Sally confirmed the June 27 Reynolds gig sounds good.",
        db_path=db_path,
    )

    assert plan.status == "draft_ready_pending_approval"
    assert plan.packet_id == "compose_packet_0030"
    assert plan.side_effect_id
    assert len(calls) == 1
    assert "Draft an email reply to Sally" in calls[0]["text"]
    assert calls[0]["kwargs"] == {
        "source_channel": "correspondence_watcher_fixture",
        "requested_by": "winship",
        "source_message_id": "thread_reynolds_compose_trigger",
        "db_path": db_path,
    }

    conn = sqlite3.connect(db_path)
    try:
        side_effect = conn.execute(
            "SELECT effect_type, status, approval_required FROM side_effects WHERE effect_type = 'email_draft_candidate'"
        ).fetchone()
        assert side_effect == ("email_draft_candidate", "pending_approval", 1)
    finally:
        conn.close()


def test_reynolds_sally_fixture_creates_gated_niles_voice_reply(tmp_path):
    db_path = _db(tmp_path)
    fixture_path = Path("fixtures/correspondence/reynolds_sally_confirmation.json")
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    plan = plan_reynolds_correspondence_reply(
        thread_id=fixture["thread_id"],
        sender_name=fixture["sender_name"],
        body_summary=fixture["body_summary"],
        db_path=db_path,
    )

    assert plan.status == fixture["expected_status"]
    assert plan.classification == "confirmation"
    assert plan.voice_persona_source_ref == ".claude/commands/niles.md"
    assert plan.email_send_performed is False
    assert plan.gmail_api_called is False


def test_watch_reynolds_reply_detects_notifies_and_emits_recommendation(tmp_path):
    db_path = _db(tmp_path)
    notifications = []

    def fake_notify(text, metadata):
        notifications.append((text, dict(metadata)))
        return {"status": "sent_to_operator_fixture", "sent": True, "channel": "fixture"}

    result = watch_reynolds_reply(
        inbox_messages=[
            {
                "sender_email": "someone@example.com",
                "subject": "Unrelated",
                "thread_id": "other_thread",
                "body_summary": "Ignore this.",
            },
            {
                "from": f"Sally <{REYNOLDS_REPLY_SENDER}>",
                "subject": f"Re: {REYNOLDS_REPLY_SUBJECT_FRAGMENT}",
                "thread_id": "reynolds_june27_music",
                "body_summary": "Sally says June 27 still works and asks to confirm details.",
            },
        ],
        operator_notifier=fake_notify,
        db_path=db_path,
    )

    assert result.status == "reynolds_reply_detected"
    assert result.matched is True
    assert result.sender_email == REYNOLDS_REPLY_SENDER
    assert result.recommendation_id
    assert result.recommendation_status == "proposed"
    assert result.notification_result["sent"] is True
    assert result.email_send_performed is False
    assert result.external_send_performed is False
    assert result.gmail_api_called is False
    assert result.gmail_body_read_performed is False
    assert result.raw_body_stored is False
    assert result.plan is not None
    assert result.plan.email_send_performed is False
    assert result.plan.gmail_api_called is False

    assert len(notifications) == 1
    notification_text, metadata = notifications[0]
    assert "Reynolds replied" in notification_text
    assert metadata["recommendation_id"] == result.recommendation_id
    assert metadata["email_send_performed"] is False

    recommendation = get_recommendation(result.recommendation_id or "", db_path=db_path)
    assert recommendation is not None
    assert recommendation["status"] == "proposed"
    action = recommendation["proposed_action"]
    assert action["action_type"] == hitl_action_service.ACTION_TYPE_EXACT_GMAIL_SEND
    assert action["route_back"]["type"] == "cassandra_exact_send_executor"
    assert action["route_back"]["executor_must_use_reviewed_gate"] is True
    assert action["route_back"]["guardian_calls_gmail_or_broker_directly"] is False
    assert action["payload"]["recipient"] == REYNOLDS_REPLY_SENDER
    assert action["payload"]["subject"] == f"Re: {REYNOLDS_REPLY_SUBJECT_FRAGMENT}"
    assert action["payload"]["thread_id"] == "reynolds_june27_music"
    assert "Hi Sally" in action["payload"]["body"]
    assert action["payload"]["body_stored_in_recommendation"] is True
    assert action["payload"]["body_stored_in_hitl_queue"] is True

    conn = sqlite3.connect(db_path)
    try:
        notification_packet = conn.execute(
            "SELECT action_status, packet_json_safe FROM packets WHERE intent_name = 'reynolds_reply_operator_notification'"
        ).fetchone()
    finally:
        conn.close()
    assert notification_packet is not None
    assert notification_packet[0] == "sent_to_operator_fixture"
    assert '"external_send_performed": false' in notification_packet[1]
    assert '"raw_body_stored": false' in notification_packet[1]


def test_watch_reynolds_reply_accepts_recommendation_through_hitl_without_send(tmp_path, monkeypatch):
    _isolate_hitl(monkeypatch, tmp_path)
    db_path = _db(tmp_path)
    send_hold = tmp_path / "SEND_HOLD.md"
    send_hold.write_text("SEND_HOLD active for Reynolds reply test.\n", encoding="utf-8")

    result = watch_reynolds_reply(
        inbox_messages=[
            {
                "sender_email": REYNOLDS_REPLY_SENDER,
                "subject": REYNOLDS_REPLY_SUBJECT_FRAGMENT,
                "thread_id": "reynolds_june27_music",
                "body_summary": "Sally confirmed June 27 and says the 7 to 10 slot is set.",
            }
        ],
        db_path=db_path,
    )

    outcome = accept_recommendation(
        result.recommendation_id or "",
        db_path=db_path,
        send_hold_path=send_hold,
    )

    assert outcome.gate_status == "queued_pending_hitl_send_hold_active"
    assert outcome.send_hold_active is True
    assert outcome.send_hold_blocked is True
    assert outcome.receipt["external_send_performed"] is False
    assert outcome.receipt["approval_bypassed"] is False
    assert outcome.receipt["external_send_allowed"] is False

    action = hitl_action_service.get_pending_action(outcome.hitl_action_id or "")
    assert action is not None
    assert action["status"] == WAITING_FOR_APPROVAL
    assert action["action_type"] == hitl_action_service.ACTION_TYPE_EXACT_GMAIL_SEND
    assert action["execution_result"]["status"] == "pending_approval"
    assert action["payload"]["schema_version"] == hitl_action_service.OPERATOR_ACTION_APPROVAL_REQUEST_SCHEMA
    assert action["payload"]["payload"]["recipient"] == REYNOLDS_REPLY_SENDER
    assert action["payload"]["payload"]["thread_id"] == "reynolds_june27_music"
    assert action["payload"]["route_back"]["type"] == "cassandra_exact_send_executor"
    assert action["payload"]["execution_result"]["status"] == "pending_approval"

    recommendation = get_recommendation(result.recommendation_id or "", db_path=db_path)
    assert recommendation is not None
    assert recommendation["status"] == "accepted"


def test_watch_reynolds_reply_requires_scope_before_calling_inbox_reader(tmp_path):
    db_path = _db(tmp_path)
    calls = []

    def reader():
        calls.append("called")
        raise AssertionError("reader must not run before gmail readonly scope approval")

    result = watch_reynolds_reply(
        inbox_reader=reader,
        gmail_readonly_scope_approved=False,
        db_path=db_path,
    )

    assert result.status == "gmail_readonly_scope_required"
    assert result.matched is False
    assert result.notification_result["sent"] is False
    assert result.recommendation_id is None
    assert result.gmail_api_called is False
    assert result.gmail_body_read_performed is False
    assert calls == []


def test_email_send_executor_scaffold_is_not_registered_and_send_hold_blocks(tmp_path):
    db_path = _db(tmp_path)
    plan = plan_reynolds_correspondence_reply(
        thread_id="thread_reynolds_003",
        sender_name="Sally",
        body_summary="Sally confirmed the June 27 Reynolds gig sounds good.",
        db_path=db_path,
    )

    assert email_send_executor_registered() is False
    descriptor = email_send_executor_descriptor()
    assert descriptor["surface"] == EMAIL_SEND_SURFACE
    assert descriptor["registry_owner"] == "codex-pc-1"
    assert descriptor["registered_by_this_module"] is False
    assert descriptor["gmail_scope_decision_for_winship"]["decision_owner"] == "Winship"

    receipt = execute_email_send_packet(packet_id=plan.packet_id or "", db_path=db_path)

    assert receipt.ok is False
    assert receipt.surface == "email_send"
    assert "SEND_HOLD is active" in receipt.detail
    assert receipt.side_effect_id
    assert receipt.meta["email_send_performed"] is False
    assert receipt.meta["gmail_api_called"] is False
    assert receipt.meta["external_send_performed"] is False
    assert receipt.meta["gmail_scope_decision_for_winship"]["send_scope_not_activated_here"] is True

    conn = sqlite3.connect(db_path)
    try:
        blocked = conn.execute(
            "SELECT effect_type, status, approval_required FROM side_effects WHERE effect_type = 'email_send'"
        ).fetchone()
        assert blocked == ("email_send", "blocked_no_send", 1)
    finally:
        conn.close()


def test_email_send_executor_scaffold_refuses_unapproved_packet_even_without_send_hold(tmp_path):
    db_path = _db(tmp_path)
    missing_hold = tmp_path / "SEND_HOLD_missing.md"
    plan = plan_reynolds_correspondence_reply(
        thread_id="thread_reynolds_004",
        sender_name="Sally",
        body_summary="Sally confirmed the June 27 Reynolds gig sounds good.",
        db_path=db_path,
    )

    receipt = execute_email_send_packet(
        packet_id=plan.packet_id or "",
        db_path=db_path,
        send_hold_path=missing_hold,
        email_sender=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not call sender")),
    )

    assert receipt.ok is False
    assert "not execution-approved" in receipt.detail
    assert receipt.meta["send_hold_active"] is False
    assert receipt.meta["email_send_performed"] is False


def test_build_email_send_executor_returns_registry_compatible_wrapper(tmp_path):
    db_path = _db(tmp_path)
    plan = plan_reynolds_correspondence_reply(
        thread_id="thread_reynolds_005",
        sender_name="Sally",
        body_summary="Sally confirmed the June 27 Reynolds gig sounds good.",
        db_path=db_path,
    )
    wrapper = build_email_send_executor(
        send_hold_path=tmp_path / "SEND_HOLD_missing.md",
        email_sender=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not call sender")),
    )

    receipt = wrapper(packet_id=plan.packet_id or "", db_path=db_path)

    assert receipt.ok is False
    assert receipt.surface == "email_send"
    assert "not execution-approved" in receipt.detail
