from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import autonomous_followup_watch_scheduler as scheduler
from client_followup_watch import ClientFollowupWatchStore
from contacts_registry import ContactsRegistry


def test_st_annes_reply_tracking_and_due_followups_are_surfaced_once(tmp_path: Path) -> None:
    contacts_db = tmp_path / "contacts.sqlite3"
    ContactsRegistry(str(contacts_db), seed=True)

    sent_receipt_path = tmp_path / "st_annes_sent_receipt.json"
    sent_receipt_path.write_text(
        json.dumps(
            {
                "ok": True,
                "sent_at_utc_iso": "2026-07-01T12:00:00+00:00",
                "invoice_ref": "ST-ANNES-REAL-2026-06",
                "proof_ref": "test_manual_send_receipt",
            }
        ),
        encoding="utf-8",
    )
    messages_path = tmp_path / "st_annes_observed_messages.json"
    messages_path.write_text(
        json.dumps(
            {
                "messages": [
                    {
                        "message_id": "gmail:draper-forward",
                        "thread_id": "thread:st-annes-invoice",
                        "from": "Draper Carter <draper.carter@gmail.com>",
                        "to": ["winshiplive@gmail.com"],
                        "received_at_utc_iso": "2026-07-02T13:00:00+00:00",
                        "subject": "Re: St. Anne's invoice",
                        "body": "I forwarded it to Glenn this afternoon.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    followup_db = tmp_path / "client_followups.sqlite3"
    watch = ClientFollowupWatchStore(str(followup_db)).add_watch(
        client_ref="st_annes",
        client_name="St. Anne's",
        recipient="draper.carter@gmail.com",
        subject="Invoice ST-ANNES-REAL-2026-06",
        sent_at_utc_iso="2026-07-01T12:00:00+00:00",
        invoice_ref="ST-ANNES-REAL-2026-06",
        days_without_reply=3,
    )
    export_root = tmp_path / "read_models"
    attention_path = tmp_path / "followup_attention.json"
    state_path = tmp_path / "followup_scheduler_state.json"

    result = scheduler.run_once(
        now_utc_iso="2026-07-06T14:00:00+00:00",
        st_annes_sent_receipt_path=sent_receipt_path,
        st_annes_messages_path=messages_path,
        contacts_db_path=contacts_db,
        followup_db_path=followup_db,
        export_root=export_root,
        attention_outbox_path=attention_path,
        state_path=state_path,
    )

    assert result["status"] == "PREPARED"
    assert result["machine_proof"]["st_annes_forward_tracking_workflow_used"] is True
    assert result["machine_proof"]["client_followup_watch_used"] is True
    assert result["machine_proof"]["email_send_performed"] is False
    assert result["machine_proof"]["gmail_send_performed"] is False
    assert result["machine_proof"]["telegram_send_performed"] is False
    assert result["machine_proof"]["ledger_mutation_performed"] is False

    tracking_state = result["st_annes_tracking"]["state"]
    assert tracking_state["workflow_stage"] == "awaiting_glenn_ack"
    assert tracking_state["forwarded_to_glenn"] is True
    assert tracking_state["glenn_acknowledged"] is False
    assert tracking_state["follow_up"]["status"] == "FOLLOW_UP_DUE"
    assert tracking_state["follow_up"]["proposal"]["send_performed"] is False
    assert tracking_state["follow_up"]["proposal"]["authority_boundary"]["guardian_required"] is True

    exported_state = json.loads((export_root / "st_annes_receivable_state.json").read_text(encoding="utf-8"))
    assert exported_state == tracking_state

    armed_watch = result["client_followup_watch"]["armed_watch"]
    assert armed_watch["watch_id"] == watch["watch_id"]
    assert armed_watch["status"] == "closed_reply_seen"
    assert armed_watch["reply_ref"] == "gmail:draper-forward"
    assert result["client_followup_watch"]["due_proposal_count"] == 0

    attention = json.loads(attention_path.read_text(encoding="utf-8"))
    assert attention["schema_version"] == scheduler.ATTENTION_SCHEMA_VERSION
    assert [event["event_kind"] for event in attention["events"]] == [
        "st_annes_forward_tracking_followup",
    ]
    assert all(event["authority_boundary"]["send_hold_required"] is True for event in attention["events"])
    assert all(event["machine_proof"]["email_send_performed"] is False for event in attention["events"])

    second = scheduler.run_once(
        now_utc_iso="2026-07-06T14:30:00+00:00",
        st_annes_sent_receipt_path=sent_receipt_path,
        st_annes_messages_path=messages_path,
        contacts_db_path=contacts_db,
        followup_db_path=followup_db,
        export_root=export_root,
        attention_outbox_path=attention_path,
        state_path=state_path,
    )

    assert second["status"] == "IDLE"
    assert second["prepared"] == []
    assert {row["reason"] for row in second["skipped"]} == {"already_surfaced"}
    attention_after = json.loads(attention_path.read_text(encoding="utf-8"))
    assert len(attention_after["events"]) == 1


def test_scheduler_arms_st_annes_watch_and_operator_monitoring_without_send(
    tmp_path: Path,
) -> None:
    contacts_db = tmp_path / "contacts.sqlite3"
    ContactsRegistry(str(contacts_db), seed=True)
    sent_receipt_path = tmp_path / "st_annes_sent_receipt.json"
    sent_receipt_path.write_text(
        json.dumps(
            {
                "ok": True,
                "sent_at_utc_iso": "2026-07-17T04:23:30+00:00",
                "invoice_ref": "ST-ANNES-2026-06-INVOICE-3",
                "invoice_status": "SENT",
                "recipient": "draper.carter@gmail.com",
                "subject": "St. Anne's Invoice - June 2026 Services",
                "provenance": "external_agent_send",
                "operator_authorized": True,
                "proof_ref": "external-agent-send:gmail:message-1",
            }
        ),
        encoding="utf-8",
    )
    messages_path = tmp_path / "messages.json"
    messages_path.write_text(json.dumps({"messages": []}), encoding="utf-8")
    followup_db = tmp_path / "client_followups.sqlite3"
    attention_path = tmp_path / "attention.json"

    result = scheduler.run_once(
        now_utc_iso="2026-07-17T13:00:00+00:00",
        st_annes_sent_receipt_path=sent_receipt_path,
        st_annes_messages_path=messages_path,
        contacts_db_path=contacts_db,
        followup_db_path=followup_db,
        export_root=tmp_path / "read_models",
        attention_outbox_path=attention_path,
        state_path=tmp_path / "scheduler_state.json",
    )

    assert result["status"] == "PREPARED"
    armed = result["client_followup_watch"]["armed_watch"]
    assert armed["status"] == "active"
    assert armed["recipient"] == "draper.carter@gmail.com"
    assert armed["due_at_utc_iso"] == "2026-07-21T04:23:30+00:00"
    assert result["client_followup_watch"]["due_proposal_count"] == 0
    assert [event["event_kind"] for event in result["prepared"]] == [
        "st_annes_receivable_monitor_armed"
    ]
    event = result["prepared"][0]
    assert event["operator_surface_flag"] == "AWAITING_DRAPER_FORWARD_TO_GLENN"
    assert event["machine_proof"]["monitoring_only"] is True
    assert event["machine_proof"]["email_send_performed"] is False
