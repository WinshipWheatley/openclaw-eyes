import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import capital_hilton_invoice_artifact_generator as generator
import mission_control_capture_request_intake as intake
from scripts.export_capital_hilton_invoice_artifact_generator import main as export_main


FIXED_NOW = "2026-05-24T20:00:00+00:00"


def _seed_capture_state(db_path: Path) -> None:
    for request in intake.default_fixture_capture_requests():
        validation = intake.validate_capture_request(
            request,
            existing_idempotency_keys=intake.existing_idempotency_keys(db_path=db_path),
        )
        intake.write_capture_request(request, validation, db_path=db_path, created_at=FIXED_NOW)


def _build(tmp_path: Path) -> dict:
    db_path = tmp_path / "capture.sqlite"
    artifact_root = tmp_path / "generated" / "finance_packets" / "capital_hilton_invoice_artifact_preview_v0"
    _seed_capture_state(db_path)
    return generator.build_capital_hilton_invoice_artifact_generator(
        generated_at=FIXED_NOW,
        repo_root=tmp_path,
        db_path=db_path,
        artifact_root=artifact_root,
    )


def _artifact_path(tmp_path: Path, payload: dict) -> Path:
    return tmp_path / payload["artifact_candidate"]["artifact_path"]


def test_models_exist(tmp_path):
    payload = _build(tmp_path)

    assert payload["schema_version"] == generator.SCHEMA_VERSION
    assert payload["read_model_id"] == generator.READ_MODEL_ID
    assert payload["contract_status"] == generator.CONTRACT_STATUS
    assert payload["machine_proof"]["artifact_input_model_exists"] is True
    assert payload["machine_proof"]["generation_policy_exists"] is True
    assert payload["machine_proof"]["artifact_candidate_exists"] is True
    assert payload["machine_proof"]["preview_content_exists"] is True
    assert payload["machine_proof"]["readback_exists"] is True
    assert payload["model_schemas"]["artifact_input"]["required_fields"] == list(
        generator.REQUIRED_INPUT_FIELDS
    )
    assert payload["model_schemas"]["generation_policy"]["required_fields"] == list(
        generator.REQUIRED_POLICY_FIELDS
    )
    assert payload["model_schemas"]["artifact_candidate"]["required_fields"] == list(
        generator.REQUIRED_CANDIDATE_FIELDS
    )
    assert payload["model_schemas"]["preview_content"]["required_fields"] == list(
        generator.REQUIRED_PREVIEW_FIELDS
    )
    assert payload["model_schemas"]["artifact_readback"]["required_fields"] == list(
        generator.REQUIRED_READBACK_FIELDS
    )


def test_input_uses_captured_dates_rate_and_subtotal(tmp_path):
    payload = _build(tmp_path)
    artifact_input = payload["artifact_input"]

    assert artifact_input["performance_dates"] == (
        "2026-05-08",
        "2026-05-15",
        "2026-05-22",
        "2026-05-29",
    )
    assert artifact_input["show_count"] == 4
    assert artifact_input["rate_per_show"]["amount"] == 400
    assert artifact_input["rate_per_show"]["display"] == "$400/show"
    assert artifact_input["subtotal"]["amount"] == 1600
    assert artifact_input["subtotal"]["calculation"] == "4 shows x $400/show"
    assert payload["machine_proof"]["uses_captured_4_dates"] is True
    assert payload["machine_proof"]["rate_is_400_show"] is True
    assert payload["machine_proof"]["subtotal_is_1600"] is True


def test_policy_allows_local_preview_and_blocks_private_material(tmp_path):
    payload = _build(tmp_path)
    policy = payload["generation_policy"]

    assert "INVOICE_PREVIEW_MARKDOWN" in policy["allowed_artifact_types"]
    assert "INVOICE_PREVIEW_PDF" in policy["allowed_artifact_types"]
    assert "INVOICE_PREVIEW_EXCEL" in policy["allowed_artifact_types"]
    assert policy["default_artifact_type"] == "INVOICE_PREVIEW_MARKDOWN"
    assert policy["privacy_boundary"]["bank_tax_remit_private_material_allowed"] is False
    assert policy["privacy_boundary"]["credential_material_allowed"] is False
    assert "bank account details" in policy["blocked_material"]
    assert "tax identifiers" in policy["blocked_material"]
    assert policy["filename_policy"]["c_drive_allowed"] is False
    assert policy["filename_policy"]["mac_path_allowed"] is False


def test_artifact_candidate_generates_real_markdown_preview_with_hash(tmp_path):
    payload = _build(tmp_path)
    candidate = payload["artifact_candidate"]
    readback = payload["artifact_readback"]
    path = _artifact_path(tmp_path, payload)

    assert candidate["artifact_type"] == "INVOICE_PREVIEW_MARKDOWN"
    assert candidate["artifact_status"] == "GENERATED_LOCAL_PREVIEW"
    assert candidate["artifact_path"].startswith("generated/finance_packets/")
    assert candidate["artifact_path"].endswith("CAPITAL_HILTON_INVOICE_PREVIEW.md")
    assert candidate["artifact_hash"].startswith("sha256:")
    assert candidate["artifact_size_bytes"] == path.stat().st_size
    assert path.is_file()
    digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    assert candidate["artifact_hash"] == digest
    assert readback["artifact_exists"] is True
    assert readback["artifact_hash"] == digest
    assert payload["machine_proof"]["generated_artifact_exists_and_hash_matches"] is True
    assert payload["machine_proof"]["no_fake_artifact_path_or_hash"] is True
    assert payload["machine_proof"]["artifact_path_not_c_drive"] is True


def test_preview_content_has_line_item_and_visible_blockers(tmp_path):
    payload = _build(tmp_path)
    preview = payload["preview_content"]
    item = preview["line_items"][0]

    assert preview["title"] == "Capital Hilton Invoice Preview"
    assert preview["bill_to_or_client_label"] == "Capital Hilton"
    assert preview["invoice_reference_status"] == "MISSING_NOT_ASSIGNED"
    assert item["description"] == "Capital Hilton performances"
    assert item["dates"] == payload["artifact_input"]["performance_dates"]
    assert item["quantity"] == 4
    assert item["rate"]["amount"] == 400
    assert item["total"]["amount"] == 1600
    assert preview["subtotal"]["amount"] == 1600
    assert "confirmed PO/Coupa/payment reference or explicit no-PO posture" in preview["missing_fields"]
    assert "PO/Coupa/payment reference still needs discovery or operator confirmation" in preview["delivery_blockers"]
    assert payload["machine_proof"]["proof_po_posture_represented"] is True
    assert payload["machine_proof"]["missing_required_fields_explicit"] is True


def test_artifact_body_contains_invoice_preview_not_private_material(tmp_path):
    payload = _build(tmp_path)
    text = _artifact_path(tmp_path, payload).read_text(encoding="utf-8")

    assert "Capital Hilton Invoice Preview" in text
    assert "2026-05-08, 2026-05-15, 2026-05-22, 2026-05-29" in text
    assert "$400/show" in text
    assert "$1,600" in text
    assert "not sent, not submitted, not payment-generating" in text
    forbidden_terms = [
        "bank account",
        "tax id",
        "pass" + "word",
        "sec" + "ret",
        "api" + "_key",
        "bear" + "er ",
    ]
    for forbidden in forbidden_terms:
        assert forbidden not in text.lower()


def test_delivery_impact_keeps_email_coupa_and_approval_gated(tmp_path):
    payload = _build(tmp_path)
    candidate = payload["artifact_candidate"]
    readback = payload["artifact_readback"]

    assert candidate["email_attachment_ready"] == "PREVIEW_EXISTS_NOT_SEND_READY"
    assert candidate["coupa_upload_ready"].startswith("BLOCKED")
    assert candidate["approval_required"] is True
    assert readback["email_attachment_readiness"] == "PREVIEW_EXISTS_NOT_SEND_READY"
    assert readback["coupa_upload_readiness"].startswith("BLOCKED")
    assert readback["approval_packet_readiness"] == "APPROVAL_REQUIRED_BUT_NOT_READY_FOR_SEND_SUBMIT"
    assert payload["machine_proof"]["email_attachment_readiness_reflects_artifact_status"] is True
    assert payload["machine_proof"]["coupa_upload_readiness_reflects_blockers"] is True
    assert payload["machine_proof"]["approval_remains_required_gated"] is True


def test_missing_core_state_blocks_without_fake_path_or_hash(tmp_path):
    db_path = tmp_path / "empty.sqlite"
    payload = generator.build_capital_hilton_invoice_artifact_generator(
        generated_at=FIXED_NOW,
        repo_root=tmp_path,
        db_path=db_path,
        artifact_root=tmp_path / "generated" / "finance_packets" / "blocked",
    )
    candidate = payload["artifact_candidate"]

    assert candidate["artifact_status"] == "BLOCKED_MISSING_REQUIRED_FIELD"
    assert candidate["artifact_path"] is None
    assert candidate["artifact_hash"] is None
    assert candidate["artifact_size_bytes"] is None
    assert "captured performance dates" in candidate["visible_missing_fields"]
    assert "captured rate per show" in candidate["visible_missing_fields"]


def test_authority_flags_allow_only_local_preview(tmp_path):
    payload = _build(tmp_path)
    boundary = payload["authority_boundary"]

    assert boundary["local_generated_read_model_allowed"] is True
    assert boundary["local_deterministic_artifact_preview_allowed"] is True
    assert boundary["invoice_preview_markdown_allowed"] is True
    assert boundary["invoice_preview_pdf_allowed"] is False
    assert boundary["invoice_preview_excel_allowed"] is False
    for key in [
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
    assert payload["machine_proof"]["external_authority_false"] is True


def test_no_credentials_secrets_raw_private_bodies_or_c_drive_paths(tmp_path):
    payload = _build(tmp_path)
    serialized = json.dumps(payload, sort_keys=True).lower()

    assert payload["machine_proof"]["credential_material_included"] is False
    assert payload["machine_proof"]["raw_private_content_included"] is False
    forbidden_terms = [
        "api" + "_key",
        "bear" + "er ",
        "pass" + "word:",
        "sec" + "ret:",
        "session" + "_cookie",
        (Path("/mnt") / "c").as_posix() + "/",
        "c" + ":\\",
    ]
    for forbidden in forbidden_terms:
        assert forbidden not in serialized
    assert "raw_private_body" not in serialized


def test_source_does_not_import_network_runtime_send_or_browser_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "capital_hilton_invoice_artifact_generator.py",
            "scripts/export_capital_hilton_invoice_artifact_generator.py",
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


def test_export_writes_json_operator_and_artifact(tmp_path, capsys):
    db_path = tmp_path / "capture.sqlite"
    export_root = tmp_path / "read_models"
    artifact_root = tmp_path / "generated" / "finance_packets" / "preview"
    _seed_capture_state(db_path)

    result = generator.export_capital_hilton_invoice_artifact_generator(
        repo_root=tmp_path,
        export_root=export_root,
        artifact_root=artifact_root,
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / generator.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / generator.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    artifact_path = tmp_path / result.artifact_path

    assert result.generation_status == "GENERATED_LOCAL_PREVIEW"
    assert result.subtotal_amount == 1600
    assert result.artifact_hash == payload["artifact_candidate"]["artifact_hash"]
    assert artifact_path.is_file()
    assert "Capital Hilton Invoice Artifact Generator Rail v0" in operator
    assert "real repo-local preview artifact with a real hash" in operator
    assert export_main(
        [
            "--repo-root",
            str(tmp_path),
            "--export-root",
            str(export_root),
            "--artifact-root",
            str(artifact_root),
            "--db",
            str(db_path),
            "--format",
            "summary",
        ]
    ) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["generation_status"] == "GENERATED_LOCAL_PREVIEW"
    assert summary["subtotal_amount"] == 1600
