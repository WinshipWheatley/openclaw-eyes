from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import cassandra_custom_tools
import operator_conversation_router


def test_cassandra_real_objective_route_prepares_immutable_no_send_envelope(tmp_path: Path) -> None:
    artifact = tmp_path / "safe-canary.pdf"
    artifact.write_bytes(b"%PDF-1.4\nCassandra W0 canary\n")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    packet = {
        "client_ref": "live_arts_md",
        "client_display_name": "Live Arts MD",
        "invoice_number": "LAMD-2026-0717",
        "service_period": "July 2026",
        "currency": "USD",
        "amount_minor_units": 10000,
        "source_workbook": {
            "path": "/mnt/c/OpenClawFinance/Invoice Live Arts MD.xlsx",
            "version": "operator_truth_20260717",
            "sha256": "b" * 64,
        },
        "workflow_ref": "live_arts_md_invoice_send",
        "allowed_facts": ["Live Arts MD", "LAMD-2026-0717", "July 2026", "$100.00"],
    }
    contract = {
        "sender": "winshiplive@gmail.com",
        "to": ["Accountant@liveartsmd.org"],
        "cc": [],
        "bcc": [],
        "voice_speaker": "clara",
        "workflow_ref": "live_arts_md_invoice_send",
        "next_verification_milestone": "accountant_acknowledged",
        "human_closing_ask": "Could you send me a quick note once the invoice is in your accounting queue?",
        "ask_why": "That helps me know it landed and keeps our records straight.",
        "forbidden_claims": ["already paid", "already sent"],
    }
    artifact_receipt = {
        "path": str(artifact),
        "mime_type": "application/pdf",
        "size_bytes": artifact.stat().st_size,
        "sha256": digest,
        "artifact_verification_receipt_id": "w0-cassandra-artifact-verified",
        "formula_freshness_receipt_id": "w0-cassandra-formula-not-applicable",
    }

    result = cassandra_custom_tools.handle_operator_objective(
        "Prepare the July Live Arts invoice envelope. Do not send anything.",
        source_channel="operator_frontdoor_canary",
        source_message_ref="w0-live-canary-001",
        lane_context={
            "target_world_ref": "finance",
            "target_thread_ref": "live_arts_md",
            "deterministic_invoice_packet": packet,
            "immutable_copy_contract": contract,
            "artifact_receipt": artifact_receipt,
        },
        sqlite_path=tmp_path / "cassandra-objectives.sqlite",
        generated_at="2026-07-17T16:05:00+00:00",
    )

    assert result is not None
    assert result["response_status"] == "CASSANDRA_INVOICE_ENVELOPE_PREPARED"
    assert result["invoice_prepare"]["transaction"]["lifecycle_state"] == "PREPARED"
    assert result["machine_proof"]["email_send_performed"] is False
    assert result["machine_proof"]["gmail_draft_created"] is False
    assert result["machine_proof"]["immutable_envelope_persisted"] is True
    assert result["voice_boundary_receipt"]["speaker_ref"] == "cassandra"
    assert result["voice_boundary_receipt"]["voice_conformance_outcome"] == "passed"

    with sqlite3.connect(tmp_path / "cassandra-objectives.sqlite") as conn:
        assert conn.execute("SELECT count(*) FROM invoice_send_transactions").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM cassandra_operator_objectives").fetchone()[0] == 1

    frontdoor_sqlite_path = tmp_path / "frontdoor-objectives.sqlite"
    cassandra_frontdoor_sqlite_path = tmp_path / "frontdoor-cassandra-objectives.sqlite"
    frontdoor = operator_conversation_router.route_conversation_text(
        {
            "request_id": "w0-frontdoor-canary-001",
            "request_type": operator_conversation_router.REQUEST_TYPE,
            "controller_event_type": "chat_goal",
            "operator_text": "Prepare the July Live Arts invoice envelope. Do not send anything.",
            "current_world_ref": "finance",
            "current_thread_ref": "live_arts_md",
            "selected_card_id": "dynamic_card.live_arts_md",
            "selected_action_id": "",
            "authority_boundary": dict(operator_conversation_router.AUTHORITY_BOUNDARY),
            "authority_requested": [],
            "deterministic_invoice_packet": packet,
            "immutable_copy_contract": contract,
            "artifact_receipt": artifact_receipt,
            "cassandra_objective_sqlite_path": str(cassandra_frontdoor_sqlite_path),
        },
        sqlite_path=frontdoor_sqlite_path,
        generated_at="2026-07-17T16:06:00+00:00",
    )
    assert frontdoor["route_status"] == "CASSANDRA_INVOICE_ENVELOPE_PREPARED"
    assert frontdoor["cassandra_operator_objective"]["response_status"] == "CASSANDRA_INVOICE_ENVELOPE_PREPARED"
    assert frontdoor["machine_proof"]["email_send_performed"] is False
    with sqlite3.connect(cassandra_frontdoor_sqlite_path) as conn:
        assert conn.execute("SELECT count(*) FROM invoice_send_transactions").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM cassandra_operator_objectives").fetchone()[0] == 1
    with sqlite3.connect(frontdoor_sqlite_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        assert "invoice_send_transactions" not in tables
        assert "cassandra_operator_objectives" not in tables
