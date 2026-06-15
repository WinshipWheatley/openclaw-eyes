import sqlite3
from pathlib import Path

from chief_compose import EXECUTORS, compose, execute_packet, register_executor
from compose_contract import GateState
from email_send_executor import (
    EMAIL_SEND_SURFACE,
    build_email_send_executor,
    email_send_executor_registered,
    execute_email_send_packet,
)
from intent_router import route_operator_intent


def _approve_packet(db_path: Path, packet_id: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE agent_work_packets SET execution_allowed = 1, status = 'proposed' WHERE packet_id = ?",
            (packet_id,),
        )
        conn.commit()
    finally:
        conn.close()


def _payload() -> dict[str, object]:
    return {
        "to": "Sally <reservations@reynoldstavern.com>",
        "subject": "June 27 music at Reynolds Tavern",
        "body": "Hi Sally,\n\nApproved send body.",
        "attachment_path": None,
    }


def test_email_send_executor_is_registered_in_live_compose():
    assert email_send_executor_registered() is True
    assert EXECUTORS[EMAIL_SEND_SURFACE] is execute_email_send_packet


def test_send_phrases_route_to_email_and_invoice_action_types(tmp_path):
    email_route = route_operator_intent(
        text="send Sally the Reynolds intro note",
        source_kind="mission_control",
        source_channel="wire_email_send_test",
        requested_by="winship",
        db_path=tmp_path / "email.sqlite",
    )
    invoice_route = route_operator_intent(
        text="send the Reynolds Tavern invoice",
        source_kind="mission_control",
        source_channel="wire_email_send_test",
        requested_by="winship",
        db_path=tmp_path / "invoice.sqlite",
    )

    assert email_route.intent_category == "email_send"
    assert email_route.candidate_action_type == "email_send"
    assert invoice_route.intent_category == "invoice_send"
    assert invoice_route.candidate_action_type == "invoice_send"


def test_registered_email_send_blocks_under_send_hold_before_sender(tmp_path):
    db_path = tmp_path / "compose.sqlite"
    result = compose(
        "send Sally the Reynolds intro note",
        source_kind="mission_control",
        source_channel="wire_email_send_test",
        requested_by="winship",
        db_path=str(db_path),
    )
    assert result.gate_state is GateState.PENDING_APPROVAL
    _approve_packet(db_path, result.packet_id or "")
    hold_path = tmp_path / "SEND_HOLD.md"
    hold_path.write_text("hold\n", encoding="utf-8")
    sender_calls = []
    original = EXECUTORS[EMAIL_SEND_SURFACE]
    try:
        register_executor(
            EMAIL_SEND_SURFACE,
            build_email_send_executor(
                send_hold_path=hold_path,
                email_sender=lambda **kwargs: sender_calls.append(kwargs),
                outbound_payload=_payload(),
            ),
        )
        receipt = execute_packet(result.packet_id or "", surface=EMAIL_SEND_SURFACE, db_path=str(db_path))
    finally:
        register_executor(EMAIL_SEND_SURFACE, original)

    assert receipt.ok is False
    assert "SEND_HOLD is active" in receipt.detail
    assert sender_calls == []
    assert receipt.meta["gmail_api_called"] is False


def test_registered_email_send_approved_no_hold_invokes_executor_sender(tmp_path):
    db_path = tmp_path / "compose.sqlite"
    result = compose(
        "send Sally the Reynolds intro note",
        source_kind="mission_control",
        source_channel="wire_email_send_test",
        requested_by="winship",
        db_path=str(db_path),
    )
    assert result.gate_state is GateState.PENDING_APPROVAL
    _approve_packet(db_path, result.packet_id or "")
    sender_calls = []

    def sender(**kwargs):
        sender_calls.append(kwargs)
        return {"ok": True, "data": {"message_id": "gmail-mock-a3"}, "error": ""}

    original = EXECUTORS[EMAIL_SEND_SURFACE]
    try:
        register_executor(
            EMAIL_SEND_SURFACE,
            build_email_send_executor(
                send_hold_path=tmp_path / "missing_SEND_HOLD.md",
                email_sender=sender,
                outbound_payload=_payload(),
            ),
        )
        receipt = execute_packet(result.packet_id or "", surface=EMAIL_SEND_SURFACE, db_path=str(db_path))
    finally:
        register_executor(EMAIL_SEND_SURFACE, original)

    assert receipt.ok is True
    assert receipt.meta["email_send_performed"] is True
    assert receipt.meta["gmail_api_called"] is True
    assert receipt.meta["outbound_payload"] == _payload()
    assert len(sender_calls) == 1
    assert sender_calls[0]["packet_id"] == result.packet_id
