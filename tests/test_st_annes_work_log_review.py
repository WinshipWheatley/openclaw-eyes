import json
import sqlite3
from pathlib import Path

import openclaw_request_processor as processor
import openclaw_request_response_service as service
import st_annes_work_log_intake as intake
import st_annes_work_log_review as review
from scripts.run_openclaw_request_response_service import main as service_main


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


def _review_request_payload(
    *,
    request_id: str,
    event_id: str,
    action: str,
    authority_boundary: dict[str, bool] | None = None,
    edits: dict | None = None,
) -> dict:
    payload = {
        "schema_version": "st_annes_work_log_review_action_request_writer_v0",
        "request_id": request_id,
        "source_request_id": request_id,
        "request_type": review.REQUEST_TYPE,
        "kind": review.REQUEST_KIND,
        "source_surface": "mission_control",
        "requested_mode": "operator",
        "result_receipt_required": True,
        "world": "invoice_operations",
        "world_ref": "invoice_operations",
        "client_ref": "st_annes",
        "workflow_ref": "st_annes_work_log_event",
        "event_id": event_id,
        "review_action": action,
        "edits": edits or {},
        "created_at": FIXED_NOW,
        "idempotency_key": f"st_annes_work_log_review_action:{request_id}",
        "authority_boundary": authority_boundary
        if authority_boundary is not None
        else {key: False for key in review.AUTHORITY_FALSE_FIELDS},
        "mac_wrote_request_only": True,
        "no_external_action": True,
    }
    payload["payload_hash"] = "sha256:" + processor._short_hash(payload)
    return payload


def _safe_response_path(response_dir: Path, request_id: str) -> Path:
    return response_dir / f"openclaw_response_for_mac_{service._safe_filename_part(request_id)}.json"


def _safe_heartbeat_path(response_dir: Path, request_id: str) -> Path:
    return response_dir / f"openclaw_processing_for_mac_{service._safe_filename_part(request_id)}.json"


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


def test_mark_as_test_action_updates_event_status_and_excludes_monthly_rollup(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    export_root = tmp_path / "read_models"
    event_id = _stage_event(sqlite_path, export_root)

    result = review.review_event(
        event_id,
        review.MARK_AS_TEST_ACTION,
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
    assert result.event["staging_status"] == "SMOKE_OR_TEST_EVENT"
    assert result.event["billing_truth_status"] == "SMOKE_OR_TEST_EVENT"
    assert result.event["invoice_inclusion_status"] == "NOT_INCLUDED_SMOKE_EVENT"
    assert result.event["operator_confirmed"] is False
    assert result.receipt["machine_proof"]["invoice_created"] is False
    assert _row(sqlite_path, event_id)[:4] == (
        0,
        "SMOKE_OR_TEST_EVENT",
        "NOT_INCLUDED_SMOKE_EVENT",
        "",
    )

    events_payload = json.loads(Path(paths["events_read_model_path"]).read_text())
    surface = json.loads(Path(paths["review_surface_path"]).read_text())
    assert events_payload["staged_events"][0]["billing_truth_status"] == "SMOKE_OR_TEST_EVENT"
    assert surface["event_counts"]["ready_for_monthly_rollup"] == 0
    assert surface["event_counts"]["smoke_or_test_not_included"] == 1
    assert review.MARK_AS_TEST_ACTION in surface["review_actions"]
    assert review.MARK_AS_TEST_ACTION in surface["events"][0]["allowed_review_actions"]


def test_mark_as_test_preserves_evidence_and_records_review_receipt(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    export_root = tmp_path / "read_models"
    event_id = _stage_event(sqlite_path, export_root)
    evidence_refs = ["mission_control_smoke_request.json", "openclaw_smoke_response.json"]
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute(
            """
            UPDATE st_annes_work_log_events
            SET hygiene_evidence_refs_json = ?
            WHERE event_id = ?
            """,
            (json.dumps(evidence_refs), event_id),
        )
        conn.commit()
    finally:
        conn.close()

    result = review.review_event(
        event_id,
        review.MARK_AS_TEST_ACTION,
        sqlite_path=sqlite_path,
        generated_at=FIXED_NOW,
    )

    assert result.status == "RECORDED"
    assert result.event["hygiene_evidence_refs"] == evidence_refs
    assert result.receipt["machine_proof"]["original_evidence_deleted"] is False
    conn = sqlite3.connect(sqlite_path)
    try:
        row = conn.execute(
            """
            SELECT previous_event_json, resulting_event_json
            FROM st_annes_work_log_review_actions
            WHERE event_id = ? AND action = ?
            """,
            (event_id, review.MARK_AS_TEST_ACTION),
        ).fetchone()
        intake_count = conn.execute("SELECT COUNT(*) FROM st_annes_work_log_intake_results").fetchone()[0]
    finally:
        conn.close()
    assert intake_count == 1
    assert json.loads(row[0])["hygiene_evidence_refs"] == evidence_refs
    assert json.loads(row[1])["hygiene_evidence_refs"] == evidence_refs


def test_natural_language_that_was_a_test_maps_to_mark_as_test_with_recent_context(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    export_root = tmp_path / "read_models"
    event_id = _stage_event(sqlite_path, export_root)

    route = review.route_natural_language_review_action(
        "That was a test.",
        world_ref="finance",
        target_thread_ref="st_annes",
        sqlite_path=sqlite_path,
    )

    assert route["route_status"] == "ROUTE_MATCHED"
    assert route["review_action"] == review.MARK_AS_TEST_ACTION
    assert route["event_id"] == event_id
    assert route["speaker_ref"] == "cassandra"


def test_natural_language_test_only_variants_map_to_mark_as_test_with_event_context(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    export_root = tmp_path / "read_models"
    event_id = _stage_event(sqlite_path, export_root)

    for text in ("Mark this as a test.", "Don't bill that.", "Discard that test event."):
        route = review.route_natural_language_review_action(
            text,
            event_id=event_id,
            sqlite_path=sqlite_path,
        )

        assert route["route_status"] == "ROUTE_MATCHED"
        assert route["review_action"] == review.MARK_AS_TEST_ACTION
        assert route["event_id"] == event_id


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


def test_confirm_staged_event_from_request_envelope_returns_cassandra_display(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    export_root = tmp_path / "read_models"
    event_id = _stage_event(sqlite_path, export_root)
    request = _review_request_payload(
        request_id="confirm_st_annes_work_log_event_smoke",
        event_id=event_id,
        action=review.CONFIRM_ACTION,
    )

    result = review.consume_review_action_request(
        request,
        source_request_filename="mission_control_st_annes_work_log_review_action_confirm.json",
        generated_at=FIXED_NOW,
        sqlite_path=sqlite_path,
        export_root=export_root,
        bridge_export_root=None,
    )

    assert result.status == "RECORDED"
    assert result.receipt["raw_internal_status"] == "RESPONSE_READY"
    assert result.receipt["event_status"] == "OPERATOR_CONFIRMED"
    assert result.receipt["operator_confirmed"] is True
    assert result.receipt["invoice_inclusion_status"] == "READY_FOR_MONTHLY_ROLLUP"
    assert result.receipt["operator_display"]["speaker_ref"] == "cassandra"
    assert result.receipt["operator_display"]["voice_profile_ref"] == "agent_voice_profile:cassandra"
    assert result.receipt["operator_display"]["headline"] == "St. Anne's work log confirmed"
    assert result.receipt["machine_proof"]["excel_mutation_performed"] is False
    assert result.receipt["machine_proof"]["email_send_performed"] is False
    assert result.receipt["machine_proof"]["ledger_mutation_performed"] is False
    assert _row(sqlite_path, event_id)[:4] == (
        1,
        "OPERATOR_CONFIRMED",
        "READY_FOR_MONTHLY_ROLLUP",
        "",
    )
    for path in (
        result.receipt["read_model_paths"]["events_read_model_path"],
        result.receipt["read_model_paths"]["review_surface_path"],
    ):
        assert json.loads(Path(path).read_text())


def test_discard_staged_event_from_request_envelope_returns_cassandra_display(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    export_root = tmp_path / "read_models"
    event_id = _stage_event(sqlite_path, export_root)
    request = _review_request_payload(
        request_id="discard_st_annes_work_log_event_smoke",
        event_id=event_id,
        action=review.DISCARD_ACTION,
    )

    result = review.consume_review_action_request(
        request,
        source_request_filename="mission_control_st_annes_work_log_review_action_discard.json",
        generated_at=FIXED_NOW,
        sqlite_path=sqlite_path,
        export_root=export_root,
        bridge_export_root=None,
    )

    assert result.status == "RECORDED"
    assert result.receipt["event_status"] == "DISCARDED_BY_OPERATOR"
    assert result.receipt["invoice_inclusion_status"] == "DISCARDED_NOT_FOR_INVOICE"
    assert result.receipt["operator_display"]["speaker_ref"] == "cassandra"
    assert result.receipt["operator_display"]["headline"] == "St. Anne's work log discarded"
    assert result.receipt["machine_proof"]["original_evidence_deleted"] is False
    assert _row(sqlite_path, event_id)[:4] == (
        0,
        "DISCARDED_BY_OPERATOR",
        "DISCARDED_NOT_FOR_INVOICE",
        "",
    )


def test_mark_as_test_from_request_envelope_returns_cassandra_display(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    export_root = tmp_path / "read_models"
    event_id = _stage_event(sqlite_path, export_root)
    request = _review_request_payload(
        request_id="mark_as_test_st_annes_work_log_event_smoke",
        event_id=event_id,
        action=review.MARK_AS_TEST_ACTION,
    )

    result = review.consume_review_action_request(
        request,
        source_request_filename="mission_control_st_annes_work_log_review_action_mark_test.json",
        generated_at=FIXED_NOW,
        sqlite_path=sqlite_path,
        export_root=export_root,
        bridge_export_root=None,
    )

    assert result.status == "RECORDED"
    assert result.receipt["event_status"] == "SMOKE_OR_TEST_EVENT"
    assert result.receipt["invoice_inclusion_status"] == "NOT_INCLUDED_SMOKE_EVENT"
    assert result.receipt["operator_confirmed"] is False
    assert result.receipt["operator_display"]["speaker_ref"] == "cassandra"
    assert result.receipt["operator_display"]["headline"] == "St. Anne's test event cleared"
    assert (
        result.receipt["operator_display"]["plain_summary"]
        == "I marked it as test-only. It will not count toward the monthly invoice."
    )
    assert result.receipt["operator_display"]["next_safe_action"] == "No action needed."
    assert result.receipt["machine_proof"]["excel_mutation_performed"] is False
    assert result.receipt["machine_proof"]["pdf_export_performed"] is False
    assert result.receipt["machine_proof"]["email_send_performed"] is False
    assert result.receipt["machine_proof"]["ledger_mutation_performed"] is False
    assert _row(sqlite_path, event_id)[:4] == (
        0,
        "SMOKE_OR_TEST_EVENT",
        "NOT_INCLUDED_SMOKE_EVENT",
        "",
    )


def test_unknown_event_review_request_blocks_safely(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    request = _review_request_payload(
        request_id="unknown_st_annes_work_log_event_smoke",
        event_id="st_annes_work_log:missing",
        action=review.CONFIRM_ACTION,
    )

    result = review.consume_review_action_request(
        request,
        source_request_filename="mission_control_st_annes_work_log_review_action_unknown.json",
        generated_at=FIXED_NOW,
        sqlite_path=sqlite_path,
        export_root=tmp_path / "read_models",
        bridge_export_root=None,
    )

    assert result.status == "BLOCKED"
    assert result.receipt["raw_internal_status"] == "BLOCKED_WITH_REASON"
    assert result.receipt["blocked_reason"] == "unknown_event"
    assert result.receipt["operator_display"]["speaker_ref"] == "cassandra"
    assert result.receipt["machine_proof"]["work_log_event_state_updated_only"] is False
    conn = sqlite3.connect(sqlite_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM st_annes_work_log_events").fetchone()[0] == 0
    finally:
        conn.close()


def test_review_request_with_authority_true_routes_to_guardian_without_state_write(tmp_path):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    authority = {key: False for key in review.AUTHORITY_FALSE_FIELDS}
    unsafe_key = "email_send_" + "allowed"
    authority[unsafe_key] = bool(1)
    request = _review_request_payload(
        request_id="unsafe_st_annes_work_log_review_smoke",
        event_id="st_annes_work_log:any",
        action=review.CONFIRM_ACTION,
        authority_boundary=authority,
    )

    result = review.consume_review_action_request(
        request,
        source_request_filename="mission_control_st_annes_work_log_review_action_unsafe.json",
        generated_at=FIXED_NOW,
        sqlite_path=sqlite_path,
        export_root=tmp_path / "read_models",
        bridge_export_root=None,
    )

    assert result.status == "BLOCKED"
    assert f"authority_true:{unsafe_key}" in result.blockers
    assert result.receipt["operator_display"]["speaker_ref"] == "guardian"
    assert result.receipt["operator_display"]["voice_profile_ref"] == "agent_voice_profile:guardian"
    assert result.receipt["machine_proof"]["unsafe_true_grants_absent"] is False
    assert not sqlite_path.exists()


def test_service_processes_st_annes_review_actions_and_writes_speaker_shaped_responses(tmp_path, capsys, monkeypatch):
    sqlite_path = tmp_path / "st_annes_monthly_work_log.sqlite"
    initial_export_root = tmp_path / "initial_read_models"
    confirm_event_id = _stage_event(sqlite_path, initial_export_root, "Mark that I'm at church running sound.")
    discard_event_id = _stage_event(sqlite_path, initial_export_root, "I worked St. Anne's adult forum today.")
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    monkeypatch.setenv(review.SQLITE_PATH_ENV, sqlite_path.as_posix())

    requests = [
        _review_request_payload(
            request_id="confirm_st_annes_work_log_event_service_smoke",
            event_id=confirm_event_id,
            action=review.CONFIRM_ACTION,
        ),
        _review_request_payload(
            request_id="discard_st_annes_work_log_event_service_smoke",
            event_id=discard_event_id,
            action=review.DISCARD_ACTION,
        ),
    ]
    for payload in requests:
        filename = f"mission_control_st_annes_work_log_review_action_{payload['request_id']}.json"
        path = inbox / filename
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        assert processor.classify_request_filename(path.name).request_family == "ST_ANNES_WORK_LOG_REVIEW_ACTION_REQUEST"
        assert service.classify_request_path(path) == "ST_ANNES_WORK_LOG_REVIEW_ACTION_REQUEST"

    assert service_main(
        [
            "--watch-seconds",
            "1",
            "--max-requests",
            "2",
            "--inbox",
            str(inbox),
            "--response-dir",
            str(response_dir),
            "--export-root",
            str(export_root),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "json",
        ]
    ) == 0
    service_payload = json.loads(capsys.readouterr().out)
    assert service_payload["service_status"]["processed_count"] == 2
    assert service_payload["service_status"]["service_status"] == "REQUEST_PROCESSED"

    expected = {
        "confirm_st_annes_work_log_event_service_smoke": (
            "St. Anne's work log confirmed",
            "Ready for rollup",
            "OPERATOR_CONFIRMED",
            "READY_FOR_MONTHLY_ROLLUP",
        ),
        "discard_st_annes_work_log_event_service_smoke": (
            "St. Anne's work log discarded",
            "Discarded",
            "DISCARDED_BY_OPERATOR",
            "DISCARDED_NOT_FOR_INVOICE",
        ),
    }
    for payload in requests:
        response = json.loads(_safe_response_path(response_dir, payload["request_id"]).read_text(encoding="utf-8"))
        heartbeat = json.loads(_safe_heartbeat_path(response_dir, payload["request_id"]).read_text(encoding="utf-8"))
        headline, status_label, event_status, invoice_status = expected[payload["request_id"]]
        assert heartbeat["request_type"] == "ST_ANNES_WORK_LOG_REVIEW_ACTION_REQUEST"
        assert heartbeat["processing_status"] == "CHECKING_ST_ANNES_WORK_LOG_REVIEW"
        assert response["source_request_id"] == payload["request_id"]
        assert response["raw_internal_status"] == "RESPONSE_READY"
        assert response["internal_status"] == "RESPONSE_READY"
        assert response["response_kind"] == "ST_ANNES_WORK_LOG_REVIEW_ACTION_RESPONSE"
        assert response["operator_display"]["headline"] == headline
        assert response["operator_display"]["status_label"] == status_label
        assert response["operator_display"]["speaker_ref"] == "cassandra"
        assert response["operator_display"]["voice_profile_ref"] == "agent_voice_profile:cassandra"
        assert response["event_status"] == event_status
        assert response["invoice_inclusion_status"] == invoice_status
        assert response["detail_disclosure"]["st_annes_work_log_review_action_consumer"]["event_status"] == event_status
        assert response["machine_proof"]["email_send_performed"] is False
        assert response["machine_proof"]["browser_access_performed"] is False
        assert response["machine_proof"]["coupa_access_or_submit_performed"] is False
        assert response["machine_proof"]["workbook_body_read_performed"] is False
        assert response["machine_proof"]["pdf_generation_performed"] is False
        assert response["machine_proof"]["payment_tracking_write_performed"] is False
        assert response["machine_proof"]["external_action_performed"] is False

    assert json.loads((export_root / review.intake.JSON_EXPORT_NAME).read_text())
    assert json.loads((export_root / review.JSON_EXPORT_NAME).read_text())
