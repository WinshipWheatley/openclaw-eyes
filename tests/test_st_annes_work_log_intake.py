import json
import sqlite3
from pathlib import Path

import pytest

import st_annes_work_log_intake as intake


FIXED_NOW = "2026-06-01T23:30:00+00:00"
FIXED_DATE = "2026-06-01"


def test_church_running_sound_creates_today_event_needing_confirmation(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    result = intake.intake_and_record(
        "Mark that I'm at church running sound.",
        current_date=FIXED_DATE,
        generated_at=FIXED_NOW,
        sqlite_path=sqlite_path,
        export_root=tmp_path / "read_models",
    )

    assert result.status == "STAGED"
    event = result.event
    assert event is not None
    assert result.package["workflow_ref"] == "st_annes_work_log_event"
    assert event["client_ref"] == "st_annes"
    assert event["service_date"] == "2026-06-01"
    assert event["date_inference_basis"] == "implied_today"
    assert event["service_label"] == "Church sound"
    assert event["default_rate"] == 125
    assert event["amount"] == 125
    assert event["source"] == "mission_control"
    assert event["operator_confirmed"] is False
    assert event["authority_boundary"]["workbook_write_allowed"] is False
    assert event["authority_boundary"]["email_send_allowed"] is False
    assert event["authority_boundary"]["ledger_posting_allowed"] is False

    read_model = json.loads((tmp_path / "read_models" / "st_annes_work_log_events.json").read_text())
    assert read_model["event_count"] == 1
    assert read_model["staged_events"][0]["event_id"] == event["event_id"]


def test_may_25_funeral_input_creates_explicit_date_event(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    result = intake.intake_and_record(
        "Add a funeral AV tech event for St. Anne's on May 25.",
        current_date=FIXED_DATE,
        generated_at=FIXED_NOW,
        sqlite_path=sqlite_path,
        export_root=tmp_path / "read_models",
    )

    event = result.event
    assert event is not None
    assert event["service_date"] == "2026-05-25"
    assert event["date_inference_basis"] == "explicit_month_day"
    assert event["service_label"] == "Funeral"
    assert event["description"] == "Funeral AV tech event"
    assert event["included_in_invoice_period"] == "2026-05"
    assert event["operator_confirmed"] is False


def test_adult_forum_today_input_routes_to_work_log_event(tmp_path):
    result = intake.intake_and_record(
        "I worked St. Anne's adult forum today.",
        current_date=FIXED_DATE,
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "st_annes_monthly_work_log.sqlite",
        export_root=tmp_path / "read_models",
    )

    assert result.status == "STAGED"
    assert result.package["workflow_ref"] == "st_annes_work_log_event"
    assert result.event["service_label"] == "Adult Forum"
    assert result.event["service_date"] == "2026-06-01"


def test_unknown_client_blocks_even_with_sound_language(tmp_path):
    result = intake.intake_and_record(
        "Mark that I'm at Capital Hilton running sound.",
        current_date=FIXED_DATE,
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "st_annes_monthly_work_log.sqlite",
        export_root=tmp_path / "read_models",
    )

    assert result.status == "BLOCKED"
    assert result.event is None
    assert result.blocked_reason == "unsupported_client:capital_hilton"

    conn = sqlite3.connect(tmp_path / "st_annes_monthly_work_log.sqlite")
    try:
        assert conn.execute("SELECT COUNT(*) FROM st_annes_work_log_events").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM st_annes_work_log_intake_results").fetchone()[0] == 1
    finally:
        conn.close()


def test_send_invoice_language_does_not_mutate_excel_or_create_event(tmp_path):
    result = intake.intake_and_record(
        "Send St. Anne's invoice.",
        current_date=FIXED_DATE,
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "st_annes_monthly_work_log.sqlite",
        export_root=tmp_path / "read_models",
    )

    assert result.status == "BLOCKED"
    assert result.event is None
    assert result.package["workflow_ref"] == "st_annes_monthly_invoice_rollup"
    assert result.blocked_reason == "workflow_ref_not_work_log_event:st_annes_monthly_invoice_rollup"
    assert result.package["worker_result"]["workbook_mutation_performed"] is False
    assert result.package["worker_result"]["email_send_performed"] is False
    assert result.package["worker_result"]["ledger_mutation_performed"] is False


def test_date_missing_without_today_implication_blocks(tmp_path):
    result = intake.intake_and_record(
        "Add St. Anne's adult forum.",
        current_date=FIXED_DATE,
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "st_annes_monthly_work_log.sqlite",
        export_root=tmp_path / "read_models",
    )

    assert result.status == "BLOCKED"
    assert result.event is None
    assert result.blocked_reason == "service_date_required"


def test_sqlite_row_and_read_model_have_no_unsafe_true_grants(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    intake.intake_and_record(
        "Mark that I'm at church running sound.",
        current_date=FIXED_DATE,
        generated_at=FIXED_NOW,
        sqlite_path=sqlite_path,
        export_root=tmp_path / "read_models",
    )

    conn = sqlite3.connect(sqlite_path)
    try:
        row = conn.execute(
            "SELECT client_ref, service_date, service_label, default_rate, amount, operator_confirmed "
            "FROM st_annes_work_log_events"
        ).fetchone()
        assert row == ("st_annes", "2026-06-01", "Church sound", 125, 125, 0)
    finally:
        conn.close()

    read_model = json.loads((tmp_path / "read_models" / "st_annes_work_log_events.json").read_text())
    blocked_keys = [
        "email_send_allowed",
        "ledger_posting_allowed",
        "workbook_write_allowed",
        "pdf_export_allowed",
        "paid",
        "sent",
    ]
    assert all(read_model["authority_boundary"][key] is False for key in blocked_keys)
    assert all(row["authority_boundary"][key] is False for row in read_model["staged_events"] for key in blocked_keys)


def test_build_read_model_from_existing_sqlite(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    result = intake.intake_work_log_event(
        "Add a funeral AV tech event for St. Anne's on May 25.",
        current_date=FIXED_DATE,
        generated_at=FIXED_NOW,
    )
    intake.record_intake_result(result, sqlite_path=sqlite_path)

    payload = intake.build_read_model(sqlite_path=sqlite_path, generated_at=FIXED_NOW)

    assert payload["status"] == "ST_ANNES_WORK_LOG_INTAKE_V0_READY"
    assert payload["event_count"] == 1
    assert payload["staged_events"][0]["service_date"] == "2026-05-25"
    assert payload["machine_proof"]["operator_confirmed_defaults_false"] is True


def test_precondition_validator_blocks_missing_contract(tmp_path):
    missing = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError):
        intake.validate_preconditions(contract_path=missing)
