import json
import sqlite3
from pathlib import Path

import st_annes_work_log_intake as intake
import st_annes_work_log_review as review


FIXED_NOW = "2026-06-02T03:10:00+00:00"
FIXED_INTAKE_NOW = "2026-06-01T23:30:00+00:00"
FIXED_DATE = "2026-06-01"


def _stage_event(sqlite_path: Path, export_root: Path, text: str = "Mark that I'm at church running sound.") -> str:
    result = intake.intake_and_record(
        text,
        current_date=FIXED_DATE,
        generated_at=FIXED_INTAKE_NOW,
        sqlite_path=sqlite_path,
        export_root=export_root,
    )
    assert result.event is not None
    return result.event["event_id"]


def _row(sqlite_path: Path, event_id: str):
    conn = sqlite3.connect(sqlite_path)
    try:
        return conn.execute(
            """
            SELECT operator_confirmed, staging_status, invoice_inclusion_status, invoice_ref,
                   service_date, service_label, description
            FROM st_annes_work_log_events
            WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()
    finally:
        conn.close()


def test_confirm_staged_event_marks_ready_for_rollup_without_external_actions(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    export_root = tmp_path / "read_models"
    event_id = _stage_event(sqlite_path, export_root)

    result = review.review_event(
        event_id,
        review.CONFIRM_ACTION,
        sqlite_path=sqlite_path,
        generated_at=FIXED_NOW,
    )
    paths = review.publish_read_models(
        sqlite_path=sqlite_path,
        export_root=export_root,
        bridge_export_root=None,
        generated_at=FIXED_NOW,
    )

    assert result.status == "RECORDED"
    assert result.event["operator_confirmed"] is True
    assert result.event["invoice_inclusion_status"] == "READY_FOR_MONTHLY_ROLLUP"
    assert result.receipt["machine_proof"]["excel_mutation_performed"] is False
    assert result.receipt["machine_proof"]["email_send_performed"] is False
    assert result.receipt["machine_proof"]["ledger_mutation_performed"] is False
    assert _row(sqlite_path, event_id)[:4] == (
        1,
        "OPERATOR_CONFIRMED",
        "READY_FOR_MONTHLY_ROLLUP",
        "",
    )

    events_payload = json.loads(Path(paths["events_read_model_path"]).read_text())
    surface = json.loads(Path(paths["review_surface_path"]).read_text())
    assert events_payload["staged_events"][0]["operator_confirmed"] is True
    assert surface["event_counts"]["ready_for_monthly_rollup"] == 1
    assert surface["machine_proof"]["invoice_created"] is False


def test_discard_staged_event_preserves_original_evidence_and_blocks_invoice_inclusion(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    export_root = tmp_path / "read_models"
    event_id = _stage_event(sqlite_path, export_root)

    result = review.review_event(
        event_id,
        review.DISCARD_ACTION,
        sqlite_path=sqlite_path,
        generated_at=FIXED_NOW,
    )

    assert result.status == "RECORDED"
    assert result.event["staging_status"] == "DISCARDED_BY_OPERATOR"
    assert result.event["invoice_inclusion_status"] == "DISCARDED_NOT_FOR_INVOICE"
    assert result.receipt["machine_proof"]["original_evidence_deleted"] is False
    assert _row(sqlite_path, event_id)[:4] == (
        0,
        "DISCARDED_BY_OPERATOR",
        "DISCARDED_NOT_FOR_INVOICE",
        "",
    )

    conn = sqlite3.connect(sqlite_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM st_annes_work_log_intake_results").fetchone()[0] == 1
        receipt = conn.execute(
            "SELECT previous_event_json FROM st_annes_work_log_review_actions WHERE event_id = ?",
            (event_id,),
        ).fetchone()[0]
    finally:
        conn.close()
    previous = json.loads(receipt)
    assert previous["invoice_inclusion_status"] == "NOT_INCLUDED_OPERATOR_CONFIRMATION_REQUIRED"


def test_unknown_event_blocks_without_creating_work_log_event(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"

    result = review.review_event(
        "st_annes_work_log:missing",
        review.CONFIRM_ACTION,
        sqlite_path=sqlite_path,
        generated_at=FIXED_NOW,
    )

    assert result.status == "BLOCKED"
    assert result.blocked_reason == "unknown_event"
    conn = sqlite3.connect(sqlite_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM st_annes_work_log_events").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM st_annes_work_log_review_actions").fetchone()[0] == 1
    finally:
        conn.close()


def test_confirmed_event_still_does_not_touch_excel_send_or_ledger(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    export_root = tmp_path / "read_models"
    event_id = _stage_event(sqlite_path, export_root)
    result = review.review_event(event_id, review.CONFIRM_ACTION, sqlite_path=sqlite_path, generated_at=FIXED_NOW)

    proof = result.receipt["machine_proof"]
    assert proof["excel_mutation_performed"] is False
    assert proof["workbook_mutation_performed"] is False
    assert proof["invoice_created"] is False
    assert proof["pdf_export_performed"] is False
    assert proof["email_send_performed"] is False
    assert proof["ledger_mutation_performed"] is False
    assert proof["paid_marking_performed"] is False

    surface = review.build_review_surface(sqlite_path=sqlite_path, generated_at=FIXED_NOW)
    assert surface["authority_boundary"]["workbook_mutation_allowed"] is False
    assert surface["authority_boundary"]["email_send_allowed"] is False
    assert surface["authority_boundary"]["ledger_posting_allowed"] is False
    assert surface["machine_proof"]["authority_flags_all_false"] is True


def test_simple_safe_edit_resets_confirmation_and_preserves_staging(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    export_root = tmp_path / "read_models"
    event_id = _stage_event(sqlite_path, export_root)
    review.review_event(event_id, review.CONFIRM_ACTION, sqlite_path=sqlite_path, generated_at=FIXED_NOW)

    result = review.review_event(
        event_id,
        review.EDIT_ACTION,
        edits={"service_date": "2026-06-03", "service_label": "Church Service", "description": "Church service sound support"},
        sqlite_path=sqlite_path,
        generated_at="2026-06-02T03:12:00+00:00",
    )

    assert result.status == "RECORDED"
    assert result.event["operator_confirmed"] is False
    assert result.event["invoice_inclusion_status"] == "NOT_INCLUDED_OPERATOR_CONFIRMATION_REQUIRED"
    assert _row(sqlite_path, event_id) == (
        0,
        "OPERATOR_REVIEW_REQUIRED",
        "NOT_INCLUDED_OPERATOR_CONFIRMATION_REQUIRED",
        "",
        "2026-06-03",
        "Church Service",
        "Church service sound support",
    )


def test_no_unsafe_true_grants_in_review_surface(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    event_id = _stage_event(sqlite_path, tmp_path / "read_models")
    review.review_event(event_id, review.CONFIRM_ACTION, sqlite_path=sqlite_path, generated_at=FIXED_NOW)
    surface = review.build_review_surface(sqlite_path=sqlite_path, generated_at=FIXED_NOW)

    unsafe_keys = [
        "email_send_allowed",
        "ledger_posting_allowed",
        "workbook_mutation_allowed",
        "pdf_export_allowed",
        "paid",
        "sent",
    ]
    assert all(surface["authority_boundary"][key] is False for key in unsafe_keys)
    assert surface["machine_proof"]["unsafe_true_grants_absent"] is True
