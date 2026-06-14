import sqlite3
from pathlib import Path

from correspondence_watcher import plan_reynolds_correspondence_reply
from email_send_executor import email_send_executor_registered, execute_email_send_packet


def _db(tmp_path: Path) -> str:
    return str(tmp_path / "correspondence.sqlite")


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

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT blocked, raw_sensitive_data_stored FROM retrieval_receipts WHERE source = 'gmail.readonly'"
        ).fetchone()
        assert row == (1, 0)
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
    finally:
        conn.close()


def test_email_send_executor_scaffold_is_not_registered_and_send_hold_blocks(tmp_path):
    db_path = _db(tmp_path)
    plan = plan_reynolds_correspondence_reply(
        thread_id="thread_reynolds_003",
        sender_name="Sally",
        body_summary="Sally confirmed the June 27 Reynolds gig sounds good.",
        db_path=db_path,
    )

    assert email_send_executor_registered() is False

    receipt = execute_email_send_packet(packet_id=plan.packet_id or "", db_path=db_path)

    assert receipt.ok is False
    assert receipt.surface == "email_send"
    assert "SEND_HOLD is active" in receipt.detail
    assert receipt.side_effect_id
    assert receipt.meta["email_send_performed"] is False
    assert receipt.meta["gmail_api_called"] is False
    assert receipt.meta["external_send_performed"] is False

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
