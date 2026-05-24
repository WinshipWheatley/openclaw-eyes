import json
from dataclasses import asdict, replace
from pathlib import Path

import mission_control_capture_request_intake as intake
from scripts.import_mission_control_capture_request import main as import_main


FIXED_NOW = "2026-05-24T18:00:00+00:00"


def _build(tmp_path: Path) -> dict:
    return intake.build_mission_control_capture_request_intake(
        generated_at=FIXED_NOW,
        db_path=tmp_path / "capture.sqlite",
    )


def test_models_exist_and_lane_is_narrow(tmp_path):
    payload = _build(tmp_path)

    assert payload["schema_version"] == intake.SCHEMA_VERSION
    assert payload["read_model_id"] == intake.READ_MODEL_ID
    assert payload["machine_proof"]["capture_request_model_exists"] is True
    assert payload["machine_proof"]["intake_validation_model_exists"] is True
    assert payload["machine_proof"]["readback_model_exists"] is True
    assert payload["machine_proof"]["capture_session_result_model_exists"] is True
    assert payload["machine_proof"]["completion_closeout_exists"] is True
    assert payload["machine_proof"]["outbox_contract_exists"] is True
    assert payload["machine_proof"]["only_performance_dates_and_rate_enabled"] is True
    assert payload["machine_proof"]["batch_capture_not_implemented"] is True
    assert payload["machine_proof"]["po_coupa_capture_not_implemented"] is True
    assert payload["machine_proof"]["invoice_packet_readiness_not_directly_committed"] is True
    assert payload["machine_proof"]["approval_send_prerequisite_not_directly_committed"] is True
    assert payload["model_schemas"]["capture_request"]["required_fields"] == list(
        intake.REQUIRED_CAPTURE_REQUEST_FIELDS
    )
    assert payload["model_schemas"]["completion_closeout"]["required_fields"] == list(
        intake.REQUIRED_CLOSEOUT_FIELDS
    )


def test_fixture_requests_are_visual_agnostic_and_match_screen_draft():
    dates, rate = intake.default_fixture_capture_requests()

    assert dates.source_surface == "mission_control"
    assert dates.source_channel == "local_desktop_capture"
    assert "screen_x" not in intake.REQUIRED_CAPTURE_REQUEST_FIELDS
    assert "button_id" not in intake.REQUIRED_CAPTURE_REQUEST_FIELDS
    assert dates.workflow_session_ref == "capital_hilton_invoice_workflow_session"
    assert dates.block_id == "performance_dates"
    assert dates.operation == "add_dates"
    assert dates.current_value["performance_dates"] == intake.CURRENT_DATES
    assert dates.proposed_value["performance_dates"] == intake.CAPTURED_DATES
    assert dates.receipt_type_requested == "OPERATOR_PERFORMANCE_DATES_ADDITION"
    assert rate.block_id == "rate_confirmation"
    assert rate.operation == "confirm_rate"
    assert rate.proposed_value["rate"] == intake.RATE_CAPTURE
    assert rate.receipt_type_requested == "OPERATOR_RATE_CONFIRMATION"


def test_performance_dates_and_rate_validate_for_local_sqlite_capture():
    dates, rate = intake.default_fixture_capture_requests()
    date_validation = intake.validate_capture_request(dates)
    rate_validation = intake.validate_capture_request(rate)

    assert date_validation.validation_status == "VALID_FOR_LOCAL_SQLITE_CAPTURE"
    assert date_validation.write_allowed is True
    assert date_validation.execution_allowed is False
    assert date_validation.normalized_request["performance_dates"] == intake.CAPTURED_DATES
    assert date_validation.normalized_request["added_dates"] == intake.ADDED_DATES
    assert rate_validation.validation_status == "VALID_FOR_LOCAL_SQLITE_CAPTURE"
    assert rate_validation.write_allowed is True
    assert rate_validation.execution_allowed is False
    assert rate_validation.normalized_request["rate"] == intake.RATE_CAPTURE


def test_durable_sqlite_receipt_state_write_and_readback(tmp_path):
    db_path = tmp_path / "capture.sqlite"
    readbacks = []

    for request in intake.default_fixture_capture_requests():
        validation = intake.validate_capture_request(
            request,
            existing_idempotency_keys=intake.existing_idempotency_keys(db_path=db_path),
        )
        readbacks.append(
            intake.write_capture_request(
                request,
                validation,
                db_path=db_path,
                created_at=FIXED_NOW,
            )
        )

    rows = intake.read_workflow_block_state(db_path=db_path)

    assert db_path.is_file()
    assert [item.write_status for item in readbacks] == [
        "WRITTEN_TO_LOCAL_SQLITE",
        "WRITTEN_TO_LOCAL_SQLITE",
    ]
    assert rows["performance_dates"]["value"]["performance_dates"] == list(intake.CAPTURED_DATES)
    assert rows["performance_dates"]["value"]["show_count"] == 4
    assert rows["rate_confirmation"]["value"]["rate"] == intake.RATE_CAPTURE
    assert all(item.external_action_performed is False for item in readbacks)

    reopened_rows = intake.read_workflow_block_state(db_path=db_path)
    assert reopened_rows == rows


def test_capture_session_readback_derives_subtotal_and_closeout(tmp_path):
    payload = _build(tmp_path)
    state = payload["sqlite_readback"]["current_openclaw_state_summary"]
    closeout = payload["completion_closeout"]

    assert state["performance_dates"] == intake.CAPTURED_DATES
    assert state["show_count"] == 4
    assert state["rate"] == intake.RATE_CAPTURE
    assert state["derived_subtotal"] == intake.DERIVED_SUBTOTAL
    assert payload["machine_proof"]["durable_sqlite_state_readback_has_4_dates"] is True
    assert payload["machine_proof"]["durable_sqlite_state_readback_has_400_rate"] is True
    assert payload["machine_proof"]["derived_subtotal_is_1600"] is True
    assert "OpenClaw now has" in closeout["operator_summary"]
    assert "$400/show" in closeout["captain_message"]
    assert "$1,600" in closeout["captain_message"]
    assert "PO/Coupa route" in closeout["captain_message"]
    assert closeout["downstream_readiness"]["approval_send"] == "LOCKED"


def test_duplicate_retry_does_not_duplicate_receipt_or_state(tmp_path):
    db_path = tmp_path / "capture.sqlite"
    request = intake.fixture_performance_dates_request()
    first_validation = intake.validate_capture_request(request)
    first = intake.write_capture_request(
        request,
        first_validation,
        db_path=db_path,
        created_at=FIXED_NOW,
    )
    duplicate_validation = intake.validate_capture_request(
        request,
        existing_idempotency_keys=(request.idempotency_key,),
    )
    duplicate = intake.write_capture_request(
        request,
        duplicate_validation,
        db_path=db_path,
        created_at=FIXED_NOW,
    )

    assert first.write_status == "WRITTEN_TO_LOCAL_SQLITE"
    assert duplicate_validation.validation_status == "DUPLICATE_NOOP"
    assert duplicate.write_status == "DUPLICATE_NOOP"
    assert duplicate.receipt_ref == first.receipt_ref
    assert duplicate.state_ref == first.state_ref


def test_hashes_are_stable_and_change_when_payload_changes():
    request = intake.fixture_performance_dates_request()
    changed = replace(
        request,
        proposed_value={"performance_dates": ("2026-05-08", "2026-05-15", "2026-05-22")},
    )

    assert intake.derive_idempotency_key(request) == request.idempotency_key
    assert intake.derive_payload_hash(request) == request.payload_hash
    assert intake.derive_preview_state_hash(request) == request.preview_state_hash
    assert intake.derive_payload_hash(request) != intake.derive_payload_hash(changed)


def test_unsupported_block_operation_invalid_payload_and_authority_fail_closed():
    dates = intake.fixture_performance_dates_request()
    rate = intake.fixture_rate_confirmation_request()

    unsupported_block = intake.validate_capture_request(replace(dates, block_id="proof_po_reference"))
    unsupported_operation = intake.validate_capture_request(replace(dates, operation="set_needs_discovery"))
    invalid_payload = intake.validate_capture_request(replace(dates, payload_hash="sha256:bad"))
    blocked_authority = intake.validate_capture_request(
        replace(
            rate,
            authority_scope_requested={**rate.authority_scope_requested, "email_send": True},
        )
    )

    assert unsupported_block.validation_status == "UNSUPPORTED_BLOCK"
    assert unsupported_block.write_allowed is False
    assert unsupported_operation.validation_status == "UNSUPPORTED_OPERATION"
    assert unsupported_operation.write_allowed is False
    assert invalid_payload.validation_status == "INVALID_PAYLOAD"
    assert invalid_payload.write_allowed is False
    assert blocked_authority.validation_status == "BLOCKED_BY_AUTHORITY"
    assert blocked_authority.write_allowed is False


def test_file_import_accepts_single_capture_request_only(tmp_path, capsys):
    request_path = tmp_path / "capture_request.json"
    db_path = tmp_path / "capture.sqlite"
    request_path.write_text(
        intake.stable_json(asdict(intake.fixture_performance_dates_request())),
        encoding="utf-8",
    )

    assert import_main(["--file", str(request_path), "--db", str(db_path), "--format", "json"]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["validation"]["validation_status"] == "VALID_FOR_LOCAL_SQLITE_CAPTURE"
    assert output["readback"]["write_status"] == "WRITTEN_TO_LOCAL_SQLITE"
    assert output["readback"]["external_action_performed"] is False
    assert output["completion_closeout"]["what_openclaw_knows_now"]["performance_dates"] == list(
        intake.CAPTURED_DATES
    )


def test_file_import_rejects_batch_packet(tmp_path):
    request_path = tmp_path / "batch_request.json"
    request_path.write_text(
        intake.stable_json({"block_capture_requests": [asdict(intake.fixture_performance_dates_request())]}),
        encoding="utf-8",
    )

    try:
        intake.load_capture_request_file(request_path)
    except ValueError as exc:
        assert "batch capture packets are not supported" in str(exc)
    else:
        raise AssertionError("batch packet should fail closed")


def test_export_writes_json_operator_and_summary(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    db_path = tmp_path / "capture.sqlite"

    assert import_main(["--export-root", str(export_root), "--db", str(db_path), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((export_root / intake.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert summary["final_show_count"] == 4
    assert summary["rate_display"] == "$400/show"
    assert summary["derived_subtotal"] == 1600
    assert summary["external_action_performed"] is False
    assert payload["completion_closeout"]["what_openclaw_knows_now"]["rate"] == intake.RATE_CAPTURE
    assert (export_root / intake.OPERATOR_EXPORT_NAME).is_file()


def test_authority_flags_allow_only_narrow_local_sqlite_capture(tmp_path):
    payload = _build(tmp_path)
    boundary = payload["authority_boundary"]

    assert boundary["local_sqlite_capture_write_allowed_for_enabled_adapters"] is True
    assert tuple(boundary["enabled_adapter_blocks"]) == ("performance_dates", "rate_confirmation")
    for key in [
        "generic_capture_write_allowed",
        "unsupported_block_write_allowed",
        "batch_capture_allowed",
        "po_coupa_capture_allowed",
        "invoice_packet_readiness_commit_allowed",
        "approval_send_prerequisite_commit_allowed",
        "invoice_generation_allowed",
        "email_draft_allowed",
        "smtp_send_allowed",
        "email_send_allowed",
        "approval_submission_allowed",
        "browser_automation_allowed",
        "coupa_access_allowed",
        "gmail_access_allowed",
        "telegram_send_allowed",
        "credential_handling_allowed",
        "model_call_allowed",
        "agent_activation_allowed",
        "tool_execution_allowed",
        "queue_execution_allowed",
        "runtime_dispatch_allowed",
        "raw_body_ingestion_allowed",
        "file_cleanup_archive_allowed",
        "network_operation_allowed",
        "mac_sync_import_allowed",
        "mission_control_swift_change_allowed",
        "git_push_pull_fetch_allowed",
    ]:
        assert boundary[key] is False
    assert payload["machine_proof"]["smtp_coupa_model_tool_send_authority_false"] is True


def test_no_credentials_secrets_or_raw_private_bodies_in_export_payload(tmp_path):
    payload = _build(tmp_path)
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert payload["machine_proof"]["credential_material_included"] is False
    assert payload["machine_proof"]["raw_private_content_included"] is False
    assert "raw_private_body" in serialized
    assert "session_cookie" in serialized
    assert "api_key" not in serialized
    assert "bearer " not in serialized
    assert "smtp://" not in serialized
    assert "oauth" not in serialized


def test_source_does_not_import_network_runtime_send_or_browser_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "mission_control_capture_request_intake.py",
            "scripts/import_mission_control_capture_request.py",
        ]
    )
    forbidden = [
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "subprocess.",
        "os.system",
        "smtplib",
        "selenium",
        "playwright",
        "coupa.login",
        "send_message",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source
