from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import autonomous_invoice_prep_scheduler as scheduler
from receivable_temporal_scoping import ClientPaidThroughStore


def test_due_st_annes_invoice_prepares_dry_run_review_and_attention_once(tmp_path: Path) -> None:
    paid_store_path = tmp_path / "client_paid_through.sqlite"
    ClientPaidThroughStore(paid_store_path).set_paid_through(
        "st_annes",
        date(2026, 6, 15),
        source_ref="test_paid_up_june",
    )
    queue_sqlite = tmp_path / "workflow_package_queue.sqlite"
    state_path = tmp_path / "autonomous_invoice_prep_state.json"
    attention_path = tmp_path / "autonomous_invoice_prep_attention.json"

    result = scheduler.run_once(
        today=date(2026, 7, 1),
        paid_through_store_path=paid_store_path,
        queue_sqlite_path=queue_sqlite,
        state_path=state_path,
        attention_outbox_path=attention_path,
        generated_at="2026-07-01T08:00:00+00:00",
    )

    assert result["status"] == "PREPARED"
    assert result["machine_proof"]["email_send_performed"] is False
    assert result["machine_proof"]["ledger_mutation_performed"] is False
    assert result["machine_proof"]["telegram_send_performed"] is False
    assert result["machine_proof"]["active_clients_evaluated"] >= 1
    assert result["machine_proof"]["recurrence_registry_used"] is True

    prepared = result["prepared"][0]
    assert prepared["client_ref"] == "st_annes"
    assert prepared["next_expected_invoice"] == "2026-07-01"
    assert prepared["workflow_ref"] == "st_annes_monthly_invoice_rollup"
    assert prepared["receipt"]["capability_gate_status"] == "ALLOW_DRY_RUN"
    assert [ref["artifact_kind"] for ref in prepared["receipt"]["proof_refs"]] == [
        "pdf_proof",
        "clara_draft",
        "guardian_gate",
    ]
    assert prepared["receipt"]["dry_run_proof_bundle"]["machine_proof"]["pdf_proof_first"] is True
    assert prepared["receipt"]["machine_proof"]["email_send_performed"] is False
    assert prepared["receipt"]["machine_proof"]["pdf_export_performed"] is False

    attention = json.loads(attention_path.read_text(encoding="utf-8"))
    assert attention["schema_version"] == scheduler.ATTENTION_SCHEMA_VERSION
    assert len(attention["events"]) == 1
    event = attention["events"][0]
    assert event["event_id"] == "autonomous_invoice_prep:st_annes:2026-07-01"
    assert event["target_surface"] == "operator_attention_lane"
    assert "St. Anne's invoice is due" in event["headline"]
    assert "approve to send" in event["operator_message"].lower()
    assert event["telegram_nudge"]["telegram_send_performed"] is False
    assert event["authority_boundary"]["email_send_allowed"] is False
    assert event["authority_boundary"]["ledger_posting_allowed"] is False
    assert event["proof_refs"] == prepared["receipt"]["proof_refs"]

    with sqlite3.connect(queue_sqlite) as conn:
        rows = conn.execute("SELECT workflow_ref, client_ref, status FROM packages").fetchall()
    assert rows == [("st_annes_monthly_invoice_rollup", "st_annes", "OPERATOR_REVIEW_REQUIRED")]

    second = scheduler.run_once(
        today=date(2026, 7, 1),
        paid_through_store_path=paid_store_path,
        queue_sqlite_path=queue_sqlite,
        state_path=state_path,
        attention_outbox_path=attention_path,
        generated_at="2026-07-01T09:00:00+00:00",
    )

    assert second["status"] == "IDLE"
    assert second["prepared"] == []
    assert second["skipped"][0]["reason"] == "already_prepared_for_cycle"
    attention_after = json.loads(attention_path.read_text(encoding="utf-8"))
    assert len(attention_after["events"]) == 1
    with sqlite3.connect(queue_sqlite) as conn:
        assert conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0] == 1
