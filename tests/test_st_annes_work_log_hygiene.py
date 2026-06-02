import json
import sqlite3
from pathlib import Path

import st_annes_work_log_hygiene as hygiene
import st_annes_work_log_intake as intake
import st_annes_work_log_review as review


FIXED_INTAKE_NOW = "2026-06-01T23:30:00+00:00"
FIXED_HYGIENE_NOW = "2026-06-02T05:30:00+00:00"
FIXED_DATE = "2026-06-01"


def _stage_smoke_event(sqlite_path: Path, export_root: Path) -> str:
    result = intake.intake_and_record(
        "Mark that I'm at church running sound.",
        current_date=FIXED_DATE,
        generated_at=FIXED_INTAKE_NOW,
        sqlite_path=sqlite_path,
        export_root=export_root,
    )
    assert result.event is not None
    return result.event["event_id"]


def _write_smoke_evidence(request_dir: Path, response_dir: Path, event_id: str) -> None:
    request_dir.mkdir(parents=True)
    response_dir.mkdir(parents=True)
    request_payload = {
        "request_id": "st_annes_work_log_review_action_confirm_smoke",
        "request_type": review.REQUEST_TYPE,
        "source_surface": "mission_control",
        "event_id": event_id,
        "review_action": review.CONFIRM_ACTION,
        "operator_business_confirmed": False,
    }
    response_payload = {
        "source_request_id": "st_annes_work_log_review_action_confirm_smoke",
        "response_kind": "ST_ANNES_WORK_LOG_REVIEW_ACTION_RESPONSE",
        "event_id": event_id,
        "invoice_inclusion_status": review.READY_FOR_ROLLUP,
        "operator_confirmed": True,
    }
    (request_dir / "mission_control_st_annes_work_log_review_action_confirm_smoke.json").write_text(
        json.dumps(request_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (response_dir / "openclaw_response_for_mac_st_annes_work_log_review_action_confirm_smoke.json").write_text(
        json.dumps(response_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _event_row(sqlite_path: Path, event_id: str):
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        return dict(
            conn.execute(
                """
                SELECT operator_confirmed, operator_business_confirmed, staging_status,
                       invoice_inclusion_status, billing_truth_status, hygiene_evidence_refs_json
                FROM st_annes_work_log_events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()
        )
    finally:
        conn.close()


def test_smoke_confirmed_event_is_excluded_from_invoice_rollup_and_evidence_is_preserved(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    export_root = tmp_path / "read_models"
    request_dir = tmp_path / "requests"
    response_dir = tmp_path / "responses"
    event_id = _stage_smoke_event(sqlite_path, export_root)
    review.review_event(event_id, review.CONFIRM_ACTION, sqlite_path=sqlite_path, generated_at="2026-06-02T04:28:06+00:00")
    _write_smoke_evidence(request_dir, response_dir, event_id)

    result = hygiene.run_hygiene(
        sqlite_path=sqlite_path,
        request_dir=request_dir,
        response_dir=response_dir,
        export_root=export_root,
        bridge_export_root=None,
        generated_at=FIXED_HYGIENE_NOW,
    )

    assert result.status == hygiene.READY_STATUS
    assert result.smoke_event_ids == (event_id,)
    assert result.excluded_event_ids == (event_id,)
    row = _event_row(sqlite_path, event_id)
    assert row["operator_confirmed"] == 0
    assert row["operator_business_confirmed"] == 0
    assert row["staging_status"] == hygiene.SMOKE_OR_TEST_STATUS
    assert row["invoice_inclusion_status"] == hygiene.NOT_INCLUDED_SMOKE
    assert row["billing_truth_status"] == hygiene.SMOKE_OR_TEST_STATUS
    assert json.loads(row["hygiene_evidence_refs_json"])

    read_model = json.loads((export_root / hygiene.JSON_EXPORT_NAME).read_text())
    events_model = json.loads((export_root / intake.JSON_EXPORT_NAME).read_text())
    review_surface = json.loads((export_root / review.JSON_EXPORT_NAME).read_text())
    assert read_model["smoke_test_events_found"] == 1
    assert read_model["events_excluded_from_invoice_rollup"] == [event_id]
    assert read_model["machine_proof"]["smoke_events_excluded_from_rollup"] is True
    assert events_model["staged_events"][0]["billing_truth_status"] == hygiene.SMOKE_OR_TEST_STATUS
    assert review_surface["event_counts"]["ready_for_monthly_rollup"] == 0
    assert review_surface["event_counts"]["smoke_or_test_not_included"] == 1

    conn = sqlite3.connect(sqlite_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM st_annes_work_log_review_actions WHERE event_id = ?", (event_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM st_annes_work_log_hygiene_actions WHERE event_id = ?", (event_id,)).fetchone()[0] == 1
    finally:
        conn.close()


def test_explicit_business_confirmed_event_can_remain_ready_for_rollup(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    export_root = tmp_path / "read_models"
    event_id = _stage_smoke_event(sqlite_path, export_root)
    review.review_event(event_id, review.CONFIRM_ACTION, sqlite_path=sqlite_path, generated_at="2026-06-02T04:28:06+00:00")
    conn = sqlite3.connect(sqlite_path)
    try:
        intake.init_sqlite(sqlite_path)
        conn.execute(
            """
            UPDATE st_annes_work_log_events
            SET operator_business_confirmed = 1
            WHERE event_id = ?
            """,
            (event_id,),
        )
        conn.commit()
    finally:
        conn.close()

    hygiene.run_hygiene(
        sqlite_path=sqlite_path,
        request_dir=tmp_path / "requests",
        response_dir=tmp_path / "responses",
        export_root=export_root,
        bridge_export_root=None,
        generated_at=FIXED_HYGIENE_NOW,
    )

    row = _event_row(sqlite_path, event_id)
    assert row["operator_confirmed"] == 1
    assert row["operator_business_confirmed"] == 1
    assert row["invoice_inclusion_status"] == review.READY_FOR_ROLLUP
    assert row["billing_truth_status"] == hygiene.BUSINESS_CONFIRMED_STATUS

    read_model = json.loads((export_root / hygiene.JSON_EXPORT_NAME).read_text())
    assert read_model["smoke_test_events_found"] == 0
    assert read_model["business_confirmed_ready_event_ids"] == [event_id]
    assert read_model["machine_proof"]["ready_for_rollup_not_smoke"] is True


def test_hygiene_read_model_has_no_external_authority(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    event_id = _stage_smoke_event(sqlite_path, tmp_path / "read_models")
    review.review_event(event_id, review.CONFIRM_ACTION, sqlite_path=sqlite_path, generated_at="2026-06-02T04:28:06+00:00")
    hygiene.run_hygiene(
        sqlite_path=sqlite_path,
        request_dir=tmp_path / "requests",
        response_dir=tmp_path / "responses",
        export_root=tmp_path / "read_models",
        bridge_export_root=None,
        generated_at=FIXED_HYGIENE_NOW,
    )
    payload = json.loads((tmp_path / "read_models" / hygiene.JSON_EXPORT_NAME).read_text())
    unsafe_keys = [
        "email_send_allowed",
        "ledger_posting_allowed",
        "workbook_write_allowed",
        "pdf_export_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "sent",
        "paid",
    ]
    assert all(payload["authority_boundary"][key] is False for key in unsafe_keys)
    assert payload["machine_proof"]["email_send_performed"] is False
    assert payload["machine_proof"]["ledger_mutation_performed"] is False
    assert payload["machine_proof"]["workbook_mutation_performed"] is False
