from __future__ import annotations

import json
from pathlib import Path

from contacts_registry import ContactsRegistry
from st_annes_forward_tracking_workflow import (
    advance_st_annes_receivable_state,
    export_st_annes_receivable_state,
)


SENT_RECEIPT = {
    "ok": True,
    "sent_at_utc_iso": "2026-07-06T12:00:00+00:00",
    "invoice_ref": "ST-ANNES-REAL-2026-06",
    "proof_ref": "gmail_send_receipt:st_annes:2026-07",
    "invoice_status": "SENT",
    "recipient": "draper.carter@gmail.com",
    "cc": ["winshiplive@gmail.com"],
    "subject": "St. Anne's Invoice - June 2026 Services",
    "provenance": "external_agent_send",
    "operator_authorized": True,
    "gmail_message_id": "message-1",
}


def test_synthetic_forward_and_glenn_ack_drive_true_state_read_model(tmp_path: Path) -> None:
    contacts_db = tmp_path / "contacts.sqlite3"
    ContactsRegistry(str(contacts_db), seed=True)
    messages = [
        {
            "message_id": "gmail:m-forward",
            "thread_id": "thread:st-annes-invoice",
            "from": "Draper Carter <draper.carter@gmail.com>",
            "to": ["Glenn Mortoro <treasurer@stannes-annapolis.org>"],
            "cc": ["Winship Live <winshiplive@gmail.com>"],
            "received_at_utc_iso": "2026-07-06T14:00:00+00:00",
            "subject": "Fwd: St. Anne's invoice",
            "body": "Glenn - forwarding Winship's invoice for St. Anne's.",
        },
        {
            "message_id": "gmail:m-ack",
            "thread_id": "thread:st-annes-invoice",
            "from": "Glenn Mortoro <glennmortoro@gmail.com>",
            "to": ["Draper Carter <draper.carter@gmail.com>", "winshiplive@gmail.com"],
            "received_at_utc_iso": "2026-07-06T15:00:00+00:00",
            "subject": "Re: St. Anne's invoice",
            "body": "Thanks, I received it and will get it in the payment run.",
        },
    ]

    state = advance_st_annes_receivable_state(
        sent_receipt=SENT_RECEIPT,
        messages=messages,
        contacts_db_path=str(contacts_db),
        generated_at_utc_iso="2026-07-06T15:05:00+00:00",
    )

    assert state["read_model_id"] == "st_annes_receivable_state"
    assert state["sent"] is True
    assert state["forwarded_to_glenn"] is True
    assert state["glenn_acknowledged"] is True
    assert state["workflow_stage"] == "awaiting_payment"
    assert state["forwarded_at_utc_iso"] == "2026-07-06T14:00:00+00:00"
    assert state["acknowledged_at_utc_iso"] == "2026-07-06T15:00:00+00:00"
    assert state["glenn_note"] == "Thanks, I received it and will get it in the payment run."
    assert state["forward_proof"]["signal"] == "primary_cc_forward_to_glenn"
    assert state["forward_proof"]["message_id"] == "gmail:m-forward"
    assert state["ack_proof"]["message_id"] == "gmail:m-ack"
    assert state["authority_boundary"]["email_send_performed"] is False
    assert state["authority_boundary"]["ledger_mutation_performed"] is False
    assert state["authority_boundary"]["paid_marking_performed"] is False

    result = export_st_annes_receivable_state(
        state,
        export_root=tmp_path / "read_models",
    )
    payload = json.loads(Path(result.read_model_path).read_text(encoding="utf-8"))
    assert payload == state


def test_draper_reply_saying_forwarded_is_secondary_forward_signal(tmp_path: Path) -> None:
    contacts_db = tmp_path / "contacts.sqlite3"
    ContactsRegistry(str(contacts_db), seed=True)

    state = advance_st_annes_receivable_state(
        sent_receipt=SENT_RECEIPT,
        messages=[
            {
                "message_id": "gmail:m-secondary",
                "thread_id": "thread:st-annes-invoice",
                "from": "Draper <draper.carter@gmail.com>",
                "to": ["winshiplive@gmail.com"],
                "received_at_utc_iso": "2026-07-06T16:00:00+00:00",
                "body": "I forwarded it to Glenn a few minutes ago.",
            }
        ],
        contacts_db_path=str(contacts_db),
        generated_at_utc_iso="2026-07-06T16:05:00+00:00",
    )

    assert state["forwarded_to_glenn"] is True
    assert state["glenn_acknowledged"] is False
    assert state["workflow_stage"] == "awaiting_glenn_ack"
    assert state["forward_proof"]["signal"] == "secondary_draper_forwarded_reply"


def test_day_four_followup_due_is_gated_and_never_sends(tmp_path: Path) -> None:
    contacts_db = tmp_path / "contacts.sqlite3"
    ContactsRegistry(str(contacts_db), seed=True)

    state = advance_st_annes_receivable_state(
        sent_receipt=SENT_RECEIPT,
        messages=[],
        contacts_db_path=str(contacts_db),
        generated_at_utc_iso="2026-07-10T12:00:00+00:00",
    )

    assert state["workflow_stage"] == "awaiting_forward_to_glenn"
    assert state["follow_up"]["status"] == "FOLLOW_UP_DUE"
    assert state["follow_up"]["step"] == "forward_to_glenn"
    assert state["follow_up"]["cadence_days"] == 3
    assert state["follow_up"]["proposal"]["gated"] is True
    assert state["follow_up"]["proposal"]["send_performed"] is False
    assert state["follow_up"]["proposal"]["voice_profile_ref"] == "agent_voice_profile:clara"
    assert state["follow_up"]["proposal"]["voice_conformance"]["passed"] is True
    assert "Please forward the St. Anne's invoice to Glenn after your review" in state["follow_up"]["proposal"]["draft"]["body"]
    assert state["follow_up"]["proposal"]["authority_boundary"]["send_hold_required"] is True
    assert state["follow_up"]["proposal"]["authority_boundary"]["guardian_required"] is True


def test_sent_state_preserves_nothing_downstream_frontier_and_monitoring(tmp_path: Path) -> None:
    contacts_db = tmp_path / "contacts.sqlite3"
    ContactsRegistry(str(contacts_db), seed=True)

    state = advance_st_annes_receivable_state(
        sent_receipt=SENT_RECEIPT,
        messages=[],
        contacts_db_path=str(contacts_db),
        generated_at_utc_iso="2026-07-06T12:05:00+00:00",
    )

    assert state["invoice_status"] == "SENT"
    assert state["recipient"] == "draper.carter@gmail.com"
    assert state["send_proof"]["provenance"] == "external_agent_send"
    assert state["workflow_stage"] == "awaiting_forward_to_glenn"
    assert state["operator_surface_flag"] == "AWAITING_DRAPER_FORWARD_TO_GLENN"
    assert state["monitoring"]["status"] == "ARMED"
    assert state["monitoring"]["auto_send"] is False
    assert state["milestones"]["sent_to_draper"]["status"] == "PROVEN"
    for milestone in (
        "draper_forwarded_to_glenn",
        "glenn_acknowledged",
        "check_received",
        "invoice_paid",
    ):
        assert state["milestones"][milestone] == {
            "status": "UNKNOWN", "state": "pending"
        }
    assert state["payment_status"] == "NOT_MARKED_PAID"
    assert state["paid"] is False
    assert state["payment_check_cadence"]["status"] == "NOT_ARMED_AWAITING_GLENN_ACK"
