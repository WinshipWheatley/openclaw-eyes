import json
from pathlib import Path

import capital_hilton_invoice_delivery_steel_thread as steel
from scripts.export_capital_hilton_invoice_delivery_steel_thread import main as export_main


FIXED_NOW = "2026-05-24T16:00:00+00:00"


def _build() -> dict:
    return steel.build_capital_hilton_invoice_delivery_steel_thread(generated_at=FIXED_NOW)


def test_steel_thread_and_required_models_exist():
    payload = _build()

    assert payload["schema_version"] == steel.SCHEMA_VERSION
    assert payload["read_model_id"] == steel.READ_MODEL_ID
    assert payload["contract_status"] == steel.CONTRACT_STATUS
    assert payload["machine_proof"]["steel_thread_model_present"] is True
    assert payload["machine_proof"]["captured_block_state_model_present"] is True
    assert payload["model_schemas"]["steel_thread"]["required_fields"] == list(
        steel.REQUIRED_STEEL_THREAD_FIELDS
    )
    assert payload["model_schemas"]["captured_block_state"]["required_fields"] == list(
        steel.REQUIRED_CAPTURED_BLOCK_FIELDS
    )
    assert payload["model_schemas"]["invoice_packet"]["required_fields"] == list(
        steel.REQUIRED_INVOICE_PACKET_FIELDS
    )
    assert payload["model_schemas"]["artifact_readiness"]["required_fields"] == list(
        steel.REQUIRED_ARTIFACT_READINESS_FIELDS
    )
    assert payload["model_schemas"]["email_draft_packet"]["required_fields"] == list(
        steel.REQUIRED_EMAIL_DRAFT_PACKET_FIELDS
    )
    assert payload["model_schemas"]["coupa_submission_readiness"]["required_fields"] == list(
        steel.REQUIRED_COUPA_READINESS_FIELDS
    )
    assert payload["model_schemas"]["approval_readiness_packet"]["required_fields"] == list(
        steel.REQUIRED_APPROVAL_PACKET_FIELDS
    )
    assert payload["model_schemas"]["delivery_blocker_report"]["required_fields"] == list(
        steel.REQUIRED_BLOCKER_REPORT_FIELDS
    )


def test_performance_dates_are_captured_and_read_back_as_four_dates():
    payload = _build()
    block = payload["captured_blocks_by_id"]["performance_dates"]
    readback = payload["capture_readback"]["performance_dates"]

    assert block["previous_value"]["performance_dates"] == steel.PREVIOUS_DATES
    assert block["captured_value"]["performance_dates"] == steel.CAPTURED_DATES
    assert block["captured_value"]["show_count"] == 4
    assert block["receipt_type"] == "OPERATOR_PERFORMANCE_DATES_ADDITION"
    assert block["state_readback"]["readback_matches_capture"] is True
    assert readback["captured_value"]["performance_dates"] == steel.CAPTURED_DATES
    assert payload["machine_proof"]["performance_dates_captured_readback_four_dates"] is True
    for item in [
        "invoice_packet_preview",
        "invoice_packet_artifact",
        "email_draft_attachment",
        "approval_packet_preview",
        "prior_subtotal_preview",
        "proof_po_coverage_status",
    ]:
        assert item in block["downstream_invalidations"]


def test_rate_is_captured_and_subtotal_is_1600():
    payload = _build()
    rate = payload["captured_blocks_by_id"]["rate_confirmation"]
    invoice = payload["invoice_packet"]

    assert rate["receipt_type"] == "OPERATOR_RATE_CONFIRMATION"
    assert rate["captured_value"]["rate"]["amount"] == 400
    assert rate["state_readback"]["captured_value"]["rate"]["display"] == "$400/show"
    assert invoice["dates"] == steel.CAPTURED_DATES
    assert invoice["rate"]["amount"] == 400
    assert invoice["subtotal"]["amount"] == 1600
    assert invoice["subtotal"]["calculation"] == "4 shows x $400/show"
    assert payload["machine_proof"]["rate_captured_readback_400"] is True
    assert payload["machine_proof"]["subtotal_is_1600"] is True


def test_po_proof_posture_is_captured_as_needs_discovery_with_blocker():
    payload = _build()
    posture = payload["captured_blocks_by_id"]["po_coupa_proof_posture"]
    blockers = payload["delivery_blocker_report"]["exact_blockers"]

    assert posture["captured_value"]["po_reference_status"] == "NEEDS_DISCOVERY"
    assert posture["captured_value"]["known_po_reference"] is None
    assert posture["captured_value"]["coupa_required_status"] == "UNKNOWN_OR_NEEDS_DISCOVERY"
    assert posture["proof_status"] == "proof_or_po_reference_still_required_before_final_send_or_submit"
    assert payload["machine_proof"]["po_proof_posture_captured_needs_discovery"] is True
    assert any(blocker["blocker_id"] == "missing_po_coupa_reference" for blocker in blockers)


def test_invoice_packet_artifact_email_coupa_and_approval_rails_exist():
    payload = _build()

    assert payload["machine_proof"]["invoice_packet_exists_from_captured_state"] is True
    assert payload["machine_proof"]["artifact_readiness_exists"] is True
    assert payload["machine_proof"]["email_draft_packet_exists"] is True
    assert payload["machine_proof"]["coupa_submission_readiness_exists"] is True
    assert payload["machine_proof"]["approval_readiness_packet_exists"] is True
    assert payload["artifact_readiness"]["generation_status"] == "BLOCKED_MISSING_SAFE_LOCAL_GENERATOR"
    assert payload["email_draft_packet"]["send_readiness"].startswith("BLOCKED")
    assert payload["coupa_submission_readiness"]["submit_readiness"].startswith("BLOCKED")
    assert payload["approval_readiness_packet"]["approval_status"] == (
        "NOT_READY_MISSING_ARTIFACT_DELIVERY_ROUTE_AND_PO_POSTURE"
    )
    assert payload["machine_proof"]["missing_internal_rails_are_readiness_packets"] is True


def test_no_fake_sent_submitted_artifact_draft_or_coupa_ready_status():
    payload = _build()

    assert payload["steel_thread"]["final_delivery_status"] not in {"SENT", "SUBMITTED_TO_COUPA"}
    assert payload["machine_proof"]["no_fake_sent_status"] is True
    assert payload["artifact_readiness"]["artifact_path_if_exists"] is None
    assert payload["artifact_readiness"]["artifact_hash_if_exists"] is None
    assert payload["machine_proof"]["no_fake_artifact_path_or_hash"] is True
    assert payload["email_draft_packet"]["recipients"] == ()
    assert payload["machine_proof"]["no_fake_email_draft_or_send"] is True
    assert payload["machine_proof"]["no_fake_coupa_packet_ready"] is True


def test_final_delivery_status_and_exact_blockers_are_named():
    payload = _build()
    report = payload["delivery_blocker_report"]
    blocker_ids = {blocker["blocker_id"] for blocker in report["exact_blockers"]}

    assert payload["steel_thread"]["final_delivery_status"] == "BLOCKED_MISSING_OPERATOR_FACT"
    assert payload["machine_proof"]["final_delivery_status_exists"] is True
    assert payload["machine_proof"]["exact_external_or_operator_blocker_named"] is True
    assert {
        "missing_safe_invoice_artifact_generator",
        "missing_confirmed_delivery_route",
        "missing_po_coupa_reference",
        "approval_not_ready",
    } <= blocker_ids
    assert report["manual_fallback_available"] is True


def test_delivery_requirements_are_explicit_and_do_not_overclaim():
    payload = _build()
    requirements = payload["delivery_requirements"]

    assert requirements["email_required"] == "UNKNOWN"
    assert requirements["coupa_required"] == "UNKNOWN_OR_LIKELY_PENDING_OPERATOR_COUPA_CONFIRMATION"
    assert requirements["both_required"] == "UNKNOWN"
    assert requirements["ap_route_or_recipient_known"] == "CANDIDATE_EXISTS_NOT_CONFIRMED"
    assert "confirmed PO/reference or explicit no-PO posture" in requirements["missing_fields"]
    assert "approved artifact path/hash" in requirements["missing_fields"]
    assert "confirmed email/AP recipient" in requirements["missing_fields"]


def test_idempotency_no_duplicate_write_behavior_for_captured_blocks():
    payload = _build()
    proof = payload["idempotency_proof"]
    keys = [block["idempotency_key"] for block in payload["captured_blocks"]]

    assert proof["captured_block_count"] == 5
    assert proof["unique_idempotency_keys"] == 5
    assert proof["no_duplicate_capture_keys"] is True
    assert proof["same_rate_block_same_key"] is True
    assert proof["same_performance_dates_block_same_key"] is True
    assert len(keys) == len(set(keys))
    assert payload["machine_proof"]["idempotency_no_duplicate_write_behavior"] is True


def test_authority_flags_allow_only_local_generated_read_model_capture():
    payload = _build()
    boundary = payload["authority_boundary"]

    assert boundary["local_receipt_write_allowed_for_this_lane"] is True
    assert boundary["local_state_update_allowed_for_this_lane"] is True
    assert boundary["local_write_mode"] == "deterministic_generated_read_model_capture_harness_only"
    for key in [
        "production_ledger_receipt_write_allowed",
        "production_workflow_state_write_allowed",
        "unsupported_generic_workflow_write_allowed",
        "invoice_generation_allowed",
        "email_draft_allowed",
        "email_send_allowed",
        "coupa_submit_allowed",
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


def test_no_credentials_secrets_or_raw_private_bodies():
    payload = _build()
    serialized = json.dumps(payload, sort_keys=True).lower()
    forbidden = [
        "password",
        "api_key",
        "apikey",
        "secret",
        "cookie",
        "raw email body",
        "raw_private_body",
        "full_markdown_body",
    ]

    assert payload["machine_proof"]["credential_material_included"] is False
    assert payload["machine_proof"]["raw_private_content_included"] is False
    for token in forbidden:
        assert token not in serialized


def test_source_does_not_import_network_runtime_send_or_browser_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "capital_hilton_invoice_delivery_steel_thread.py",
            "scripts/export_capital_hilton_invoice_delivery_steel_thread.py",
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
        "reply_text",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source


def test_export_writes_json_operator_and_cli_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    result = steel.export_capital_hilton_invoice_delivery_steel_thread(
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / steel.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / steel.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert result.captured_block_count == 5
    assert result.subtotal_amount == 1600
    assert result.final_delivery_status == "BLOCKED_MISSING_OPERATOR_FACT"
    assert payload["invoice_packet"]["subtotal"]["amount"] == 1600
    assert "Capital Hilton Invoice Delivery Steel Thread v0" in operator
    assert "four shows at $400/show, total $1,600" in operator
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["captured_block_count"] == 5
    assert summary["subtotal_amount"] == 1600
