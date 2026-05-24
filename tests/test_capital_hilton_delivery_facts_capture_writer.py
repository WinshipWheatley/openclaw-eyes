import json
from dataclasses import asdict, replace
from pathlib import Path

import capital_hilton_delivery_facts_capture_writer as writer
from scripts.import_capital_hilton_delivery_facts_capture import main as import_main


FIXED_NOW = "2026-05-24T21:00:00+00:00"


def _build(tmp_path: Path) -> dict:
    return writer.build_capital_hilton_delivery_facts_capture_writer(
        generated_at=FIXED_NOW,
        db_path=tmp_path / "delivery.sqlite",
    )


def test_required_models_exist(tmp_path):
    payload = _build(tmp_path)

    assert payload["schema_version"] == writer.SCHEMA_VERSION
    assert payload["read_model_id"] == writer.READ_MODEL_ID
    assert payload["machine_proof"]["capture_request_model_exists"] is True
    assert payload["machine_proof"]["validation_model_exists"] is True
    assert payload["machine_proof"]["receipt_payload_exists"] is True
    assert payload["machine_proof"]["state_update_target_exists"] is True
    assert payload["machine_proof"]["readback_exists"] is True
    assert payload["machine_proof"]["closeout_exists"] is True
    assert payload["model_schemas"]["capture_request"]["required_fields"] == list(
        writer.REQUIRED_CAPTURE_REQUEST_FIELDS
    )
    assert payload["model_schemas"]["intake_validation"]["required_fields"] == list(
        writer.REQUIRED_VALIDATION_FIELDS
    )
    assert payload["model_schemas"]["receipt_payload"]["required_fields"] == list(
        writer.REQUIRED_RECEIPT_PAYLOAD_FIELDS
    )
    assert payload["model_schemas"]["state_update_target"]["required_fields"] == list(
        writer.REQUIRED_STATE_UPDATE_TARGET_FIELDS
    )
    assert payload["model_schemas"]["capture_readback"]["required_fields"] == list(
        writer.REQUIRED_READBACK_FIELDS
    )
    assert payload["model_schemas"]["closeout"]["required_fields"] == list(writer.REQUIRED_CLOSEOUT_FIELDS)


def test_fixture_requests_validate_for_local_capture():
    po, ap, protected = writer.default_fixture_capture_requests()
    validations = [writer.validate_capture_request(request) for request in (po, ap, protected)]

    assert po.block_id == "proof_po_reference"
    assert po.operation == "set_needs_discovery"
    assert po.proposed_posture == "NEEDS_DISCOVERY"
    assert po.receipt_type_requested == "OPERATOR_PROOF_PO_DISCOVERY_POSTURE"
    assert ap.block_id == "ap_email_route"
    assert ap.operation == "set_ap_route_candidate_needs_confirmation"
    assert ap.proposed_posture == "AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION"
    assert ap.receipt_type_requested == "OPERATOR_AP_EMAIL_ROUTE_CANDIDATE"
    assert protected.block_id == "protected_evidence_reference"
    assert protected.protected_reference_metadata["normal_read_model_body_allowed"] is False
    assert protected.protected_reference_metadata["guardian_review_required"] is True
    assert [item.validation_status for item in validations] == [
        "VALID_FOR_LOCAL_CAPTURE",
        "VALID_FOR_LOCAL_CAPTURE",
        "VALID_FOR_LOCAL_CAPTURE",
    ]
    assert all(item.write_allowed is True for item in validations)
    assert all(item.external_execution_allowed is False for item in validations)


def test_local_sqlite_write_and_readback_for_default_fixtures(tmp_path):
    db_path = tmp_path / "delivery.sqlite"
    validations, readbacks = writer.apply_fixture_capture_requests(db_path=db_path, created_at=FIXED_NOW)
    rows = writer.read_delivery_fact_state(db_path=db_path)

    assert db_path.is_file()
    assert [item.validation_status for item in validations] == [
        "VALID_FOR_LOCAL_CAPTURE",
        "VALID_FOR_LOCAL_CAPTURE",
        "VALID_FOR_LOCAL_CAPTURE",
    ]
    assert [item.write_status for item in readbacks] == [
        "WRITTEN_TO_LOCAL_LEDGER",
        "WRITTEN_TO_LOCAL_LEDGER",
        "WRITTEN_TO_LOCAL_LEDGER",
    ]
    assert rows["proof_po_reference"]["posture"] == "NEEDS_DISCOVERY"
    assert rows["proof_po_reference"]["value"]["po_coupa_posture"] == "NEEDS_DISCOVERY"
    assert rows["ap_email_route"]["posture"] == "AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION"
    assert rows["ap_email_route"]["value"]["confirmed_recipient"] is None
    assert rows["protected_evidence_reference"]["value"]["normal_read_model_body_allowed"] is False
    assert all(item.external_action_performed is False for item in readbacks)


def test_duplicate_retry_does_not_duplicate_receipt_or_state(tmp_path):
    db_path = tmp_path / "delivery.sqlite"
    request = writer.fixture_po_coupa_needs_discovery_request()
    first_validation = writer.validate_capture_request(request)
    first = writer.write_capture_request(request, first_validation, db_path=db_path, created_at=FIXED_NOW)
    duplicate_validation = writer.validate_capture_request(
        request,
        existing_idempotency_keys=(request.idempotency_key,),
    )
    duplicate = writer.write_capture_request(request, duplicate_validation, db_path=db_path, created_at=FIXED_NOW)

    rows = writer.read_delivery_fact_state(db_path=db_path)
    assert first.write_status == "WRITTEN_TO_LOCAL_LEDGER"
    assert duplicate_validation.validation_status == "DUPLICATE_NOOP"
    assert duplicate.write_status == "DUPLICATE_NOOP"
    assert duplicate.duplicate_retry_result == "DUPLICATE_NOOP_NO_SECOND_RECEIPT_OR_STATE_ROW"
    assert rows["proof_po_reference"]["receipt_ref"] == writer._receipt_id(request)


def test_hashes_are_stable_and_change_when_payload_changes():
    request = writer.fixture_po_coupa_needs_discovery_request()
    changed = replace(
        request,
        proposed_posture="NO_PO_KNOWN_PENDING_PROOF",
        proposed_value={"po_reference": None, "coupa_reference": None},
    )

    assert writer.derive_idempotency_key(request) == request.idempotency_key
    assert writer.derive_payload_hash(request) == request.payload_hash
    assert writer.derive_payload_hash(request) != writer.derive_payload_hash(changed)


def test_unsupported_block_operation_invalid_payload_and_authority_fail_closed():
    request = writer.fixture_po_coupa_needs_discovery_request()
    ap = writer.fixture_ap_route_candidate_request()

    unsupported_block = writer.validate_capture_request(replace(request, block_id="invoice_packet"))
    unsupported_operation = writer.validate_capture_request(replace(request, operation="confirm_rate"))
    invalid_payload = writer.validate_capture_request(replace(request, payload_hash="sha256:bad"))
    blocked_authority = writer.validate_capture_request(
        replace(
            ap,
            authority_scope_requested={**ap.authority_scope_requested, "email_send": True},
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


def test_protected_reference_rejects_raw_body_material():
    request = writer.fixture_protected_reference_required_request()
    bad = replace(
        request,
        protected_reference_metadata={
            **request.protected_reference_metadata,
            "email_body": "do not store",
        },
    )

    validation = writer.validate_capture_request(bad)
    assert validation.validation_status == "INVALID_PAYLOAD"
    assert validation.write_allowed is False


def test_closeout_says_what_is_known_and_blocked(tmp_path):
    payload = _build(tmp_path)
    closeout = payload["delivery_facts_closeout"]

    assert closeout["what_openclaw_knows_now"]["po_coupa_posture"] == "NEEDS_DISCOVERY"
    assert closeout["what_openclaw_knows_now"]["ap_email_route_posture"] == "AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION"
    assert closeout["what_openclaw_knows_now"]["ap_route_confirmed"] is False
    assert closeout["what_openclaw_knows_now"]["po_or_coupa_reference_obtained"] is False
    assert "confirmed PO/Coupa/payment reference" in closeout["what_remains_unknown"]
    assert "email draft/send remains blocked" in closeout["what_remains_blocked"]
    assert "Do you have a PO/Coupa/payment reference" in closeout["suggested_next_operator_question"]
    assert payload["machine_proof"]["po_coupa_posture_readback_needs_discovery"] is True
    assert payload["machine_proof"]["ap_route_remains_candidate_not_confirmed"] is True
    assert payload["machine_proof"]["delivery_readiness_remains_blocked"] is True


def test_read_model_keeps_raw_bodies_and_secrets_out(tmp_path):
    payload = _build(tmp_path)
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert payload["machine_proof"]["normal_read_models_exclude_raw_protected_bodies"] is True
    assert payload["machine_proof"]["credentials_cookies_tokens_forbidden"] is True
    assert payload["machine_proof"]["credential_material_included"] is False
    assert payload["machine_proof"]["raw_private_content_included"] is False
    forbidden_terms = [
        "api" + "_key",
        "bear" + "er ",
        "pass" + "word:",
        "sec" + "ret:",
        "session" + "_cookie",
        "raw" + "_private_body",
        (Path("/mnt") / "c").as_posix() + "/",
        "c" + ":\\",
    ]
    for forbidden in forbidden_terms:
        assert forbidden not in serialized


def test_authority_flags_allow_only_enabled_local_delivery_fact_write(tmp_path):
    payload = _build(tmp_path)
    boundary = payload["authority_boundary"]

    assert boundary["local_delivery_fact_write_allowed_for_enabled_adapters"] is True
    assert boundary["test_delivery_fact_write_allowed"] is True
    assert tuple(boundary["enabled_adapter_blocks"]) == (
        "proof_po_reference",
        "ap_email_route",
        "protected_evidence_reference",
    )
    for key in [
        "generic_delivery_write_allowed",
        "unsupported_block_write_allowed",
        "email_send_allowed",
        "email_draft_allowed",
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
    ]:
        assert boundary[key] is False
    assert boundary["all_external_authority_false"] is True
    assert payload["machine_proof"]["all_external_authority_false"] is True


def test_file_import_accepts_single_capture_request(tmp_path, capsys):
    request_path = tmp_path / "delivery_capture.json"
    db_path = tmp_path / "delivery.sqlite"
    request_path.write_text(
        writer.stable_json(asdict(writer.fixture_ap_route_candidate_request())),
        encoding="utf-8",
    )

    assert import_main(["--file", str(request_path), "--db", str(db_path), "--format", "json"]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["validation"][0]["validation_status"] == "VALID_FOR_LOCAL_CAPTURE"
    assert output["readback"][0]["write_status"] == "WRITTEN_TO_LOCAL_LEDGER"
    assert output["readback"][0]["captured_posture"] == "AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION"
    assert output["readback"][0]["external_action_performed"] is False


def test_file_import_accepts_visual_agnostic_basis_request(tmp_path, capsys):
    request_path = tmp_path / "delivery_capture_basis.json"
    db_path = tmp_path / "delivery.sqlite"
    payload = asdict(writer.fixture_po_coupa_needs_discovery_request())
    payload.pop("idempotency_key")
    payload.pop("payload_hash")
    payload.update(
        {
            "client_ref": "capital_hilton",
            "tenant_ref": "openclaw_local",
            "world_ref": "finance",
            "lane_ref": "capital_hilton_invoice",
            "source_channel": "mission_control_capture_outbox",
            "request_created_at_policy": "backend computes canonical receipt timing",
            "current_person_profile_ref": "winship_operator_profile",
            "idempotency_key_basis": {
                "workflow_session_ref": payload["workflow_session_ref"],
                "block_id": payload["block_id"],
                "operation": payload["operation"],
                "receipt_type_requested": payload["receipt_type_requested"],
                "proposed_posture": payload["proposed_posture"],
                "proposed_value": payload["proposed_value"],
                "protected_reference_metadata": payload["protected_reference_metadata"],
            },
            "payload_hash_basis": {
                "workflow_session_ref": payload["workflow_session_ref"],
                "world_ref": "finance",
                "lane_ref": "capital_hilton_invoice",
                "block_id": payload["block_id"],
                "operation": payload["operation"],
                "proposed_posture": payload["proposed_posture"],
                "receipt_type_requested": payload["receipt_type_requested"],
                "tenant_ref": "openclaw_local",
                "client_ref": "capital_hilton",
            },
        }
    )
    request_path.write_text(writer.stable_json(payload), encoding="utf-8")

    assert import_main(["--file", str(request_path), "--db", str(db_path), "--format", "json"]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["validation"][0]["validation_status"] == "VALID_FOR_LOCAL_CAPTURE"
    assert output["readback"][0]["write_status"] == "WRITTEN_TO_LOCAL_LEDGER"
    assert output["readback"][0]["captured_posture"] == "NEEDS_DISCOVERY"
    assert output["readback"][0]["idempotency_key"].startswith("capital_hilton_delivery_fact:")
    assert output["readback"][0]["payload_hash"].startswith("sha256:")
    assert output["readback"][0]["external_action_performed"] is False


def test_file_import_rejects_visual_specific_payload_keys(tmp_path):
    request_path = tmp_path / "delivery_capture_bad_ui_key.json"
    payload = asdict(writer.fixture_po_coupa_needs_discovery_request())
    payload["button_id"] = "capture-po-button"
    request_path.write_text(writer.stable_json(payload), encoding="utf-8")

    try:
        writer.load_capture_request_file(request_path)
    except ValueError as exc:
        assert "unsupported top-level field" in str(exc) or "forbidden field" in str(exc)
    else:
        raise AssertionError("visual-specific payload key should fail closed")


def test_import_fixture_exports_json_operator_and_summary(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    db_path = tmp_path / "delivery.sqlite"

    assert import_main(
        [
            "--fixture",
            "default",
            "--export-root",
            str(export_root),
            "--db",
            str(db_path),
            "--format",
            "summary",
        ]
    ) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((export_root / writer.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / writer.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["po_coupa_posture"] == "NEEDS_DISCOVERY"
    assert summary["ap_email_route_posture"] == "AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION"
    assert summary["external_action_performed"] is False
    assert payload["sqlite_state_readback"]["proof_po_reference"]["posture"] == "NEEDS_DISCOVERY"
    assert "Capital Hilton Delivery Facts Capture Writer v0" in operator
    assert "did not log into Coupa or Gmail" in operator


def test_source_does_not_import_network_runtime_send_or_browser_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "capital_hilton_delivery_facts_capture_writer.py",
            "scripts/import_capital_hilton_delivery_facts_capture.py",
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
