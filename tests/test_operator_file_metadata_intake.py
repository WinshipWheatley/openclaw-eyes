import json
import re
from pathlib import Path

import operator_file_metadata_intake as intake
from scripts.export_operator_file_metadata_readback import main as export_main
from scripts.import_operator_file_metadata import main as import_main


FIXED_NOW = "2026-05-25T15:00:00+00:00"


def _import_fixture(tmp_path: Path, capsys, fixture: str = "spreadsheet") -> tuple[dict, dict]:
    export_root = tmp_path / "read_models"
    assert import_main(
        [
            "--fixture",
            fixture,
            "--export-root",
            str(export_root),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "summary",
        ]
    ) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    return summary, payload


def test_fixture_request_hash_helper_is_deterministic():
    first = intake.make_fixture_request("spreadsheet", created_at=FIXED_NOW)
    second = intake.make_fixture_request("spreadsheet", created_at=FIXED_NOW)

    assert intake.stable_json(first) == intake.stable_json(second)
    assert first["payload_hash"] == intake.compute_request_payload_hash(first)
    assert first["idempotency_key"]


def test_required_models_exist_in_readback(tmp_path, capsys):
    _, payload = _import_fixture(tmp_path, capsys)
    proof = payload["machine_proof"]
    schemas = payload["model_schemas"]

    assert proof["intake_request_model_present"] is True
    assert proof["source_ref_record_model_present"] is True
    assert proof["metadata_readback_model_present"] is True
    assert proof["intake_receipt_model_present"] is True
    assert proof["intake_blocker_model_present"] is True
    assert schemas["operator_file_metadata_intake_request"]["required_fields"] == list(intake.REQUIRED_INTAKE_REQUEST_FIELDS)
    assert schemas["operator_file_source_ref_record"]["required_fields"] == list(intake.REQUIRED_SOURCE_RECORD_FIELDS)
    assert schemas["operator_file_metadata_readback"]["required_fields"] == list(intake.REQUIRED_METADATA_READBACK_FIELDS)
    assert schemas["operator_file_intake_receipt"]["required_fields"] == list(intake.REQUIRED_INTAKE_RECEIPT_FIELDS)
    assert schemas["operator_file_intake_blocker"]["required_fields"] == list(intake.REQUIRED_INTAKE_BLOCKER_FIELDS)


def test_valid_spreadsheet_metadata_request_creates_source_ref(tmp_path, capsys):
    summary, payload = _import_fixture(tmp_path, capsys, "spreadsheet")
    source_ref = payload["source_ref_record"]
    readback = payload["metadata_readback"]
    receipt = payload["intake_receipt"]

    assert summary["readback_status"] == "SOURCE_REF_CREATED"
    assert source_ref["safe_display_label"] == "Capital Hilton invoice.xlsx"
    assert source_ref["file_type"] == "invoice_artifact"
    assert source_ref["file_extension"] == ".xlsx"
    assert source_ref["file_size_bytes"] == 24576
    assert source_ref["extraction_status"] == "NOT_EXTRACTED_BODY_NOT_READ"
    assert source_ref["hash_or_fingerprint_policy"] == "metadata_fingerprint_only_body_not_read"
    assert "raw body to LLM" in source_ref["prohibited_use"]
    assert readback["headline"] == "File reference captured"
    assert "The file body was not read." in readback["summary"]
    assert receipt["persistent_registry_write"] is False
    assert receipt["duplicate_result"] == "NOT_PERSISTED_NO_DUPLICATE_CHECK"


def test_screenshot_proof_request_sets_protected_posture(tmp_path, capsys):
    _, payload = _import_fixture(tmp_path, capsys, "screenshot")
    source_ref = payload["source_ref_record"]

    assert source_ref["file_type"] == "screenshot"
    assert source_ref["protected_ref_required"] is True
    assert source_ref["requested_intake_mode"] == "PROTECTED_EVIDENCE_REFERENCE"
    assert source_ref["sensitivity_class"] in {"SENSITIVE_SOURCE_METADATA", "PROTECTED_SOURCE_METADATA"}
    assert payload["machine_proof"]["screenshot_protected_posture_if_present"] is True
    assert "Protected evidence posture is required" in "\n".join(payload["metadata_readback"]["human_bullets"])


def test_album_visual_workspace_source_example_exists(tmp_path, capsys):
    _, payload = _import_fixture(tmp_path, capsys, "album")
    source_ref = payload["source_ref_record"]

    assert source_ref["safe_display_label"] == "album spreadsheet.xlsx"
    assert source_ref["file_type"] == "spreadsheet"
    assert source_ref["requested_intake_mode"] == "VISUAL_WORKSPACE_SOURCE"
    assert "bind into visual workspace" in source_ref["allowed_use"]
    assert payload["machine_proof"]["album_visual_workspace_source_if_present"] is True


def test_unknown_file_type_fails_closed(tmp_path, capsys):
    summary, payload = _import_fixture(tmp_path, capsys, "unknown")
    blockers = {item["blocker_type"] for item in payload["active_blockers_by_id"].values()}

    assert summary["readback_status"] == "BLOCKED_UNSUPPORTED_FILE_TYPE"
    assert payload["source_ref_record"] is None
    assert "UNSUPPORTED_FILE_TYPE" in blockers
    assert payload["machine_proof"]["unknown_file_type_blocked"] is True


def test_raw_body_included_is_blocked(tmp_path, capsys):
    summary, payload = _import_fixture(tmp_path, capsys, "raw_body")
    blockers = {item["blocker_type"] for item in payload["active_blockers_by_id"].values()}

    assert summary["readback_status"] == "BLOCKED_RAW_BODY_INCLUDED"
    assert payload["source_ref_record"] is None
    assert "RAW_FILE_BODY_INCLUDED" in blockers
    assert payload["machine_proof"]["raw_body_included"] is True


def test_folder_scan_is_blocked(tmp_path, capsys):
    summary, payload = _import_fixture(tmp_path, capsys, "folder")
    blockers = {item["blocker_type"] for item in payload["active_blockers_by_id"].values()}

    assert summary["readback_status"] == "BLOCKED_UNSCOPED_FOLDER_SCAN"
    assert "UNSCOPED_FOLDER_SCAN" in blockers
    assert payload["machine_proof"]["folder_scan_blocked"] is True
    assert payload["machine_proof"]["folder_scan_performed"] is False


def test_missing_idempotency_blocked(tmp_path, capsys):
    summary, payload = _import_fixture(tmp_path, capsys, "missing_idempotency")
    blockers = {item["blocker_type"] for item in payload["active_blockers_by_id"].values()}

    assert summary["readback_status"] == "BLOCKED_INVALID_REQUEST"
    assert "MISSING_IDEMPOTENCY_KEY" in blockers
    assert payload["machine_proof"]["missing_idempotency_blocked"] is True


def test_export_reads_existing_generated_readback(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert import_main(
        [
            "--fixture",
            "spreadsheet",
            "--export-root",
            str(export_root),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "summary",
        ]
    ) == 0
    capsys.readouterr()
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)

    assert summary["readback_status"] == "SOURCE_REF_CREATED"
    assert summary["safe_display_label"] == "Capital Hilton invoice.xlsx"
    assert summary["persistent_registry_write"] is False


def test_request_file_with_private_path_ref_hides_path(tmp_path, capsys):
    request = intake.make_fixture_request("spreadsheet", created_at=FIXED_NOW)
    request["mac_visible_path_ref"] = "/Users/example/private/Capital Hilton invoice.xlsx"
    request["payload_hash"] = intake.compute_request_payload_hash(request)
    request_path = tmp_path / "mission_control_file_intake_request_private_path.json"
    request_path.write_text(intake.stable_json(request), encoding="utf-8")
    export_root = tmp_path / "read_models"

    assert import_main(["--file", str(request_path), "--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    combined = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["operator_path"]).read_text(encoding="utf-8")

    assert payload["intake_request"]["local_path_ref_policy"] == "provided_path_ref_hidden_from_normal_read_model"
    assert payload["machine_proof"]["full_private_path_hidden"] is True
    assert "/Users/example/private" not in combined


def test_all_live_authority_false_and_no_body_processing(tmp_path, capsys):
    _, payload = _import_fixture(tmp_path, capsys)

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    assert payload["machine_proof"]["file_body_ingestion_performed"] is False
    assert payload["machine_proof"]["raw_body_extraction_performed"] is False
    assert payload["machine_proof"]["ocr_performed"] is False
    assert payload["machine_proof"]["spreadsheet_parse_performed"] is False
    assert payload["machine_proof"]["pdf_parse_performed"] is False
    assert payload["machine_proof"]["image_analysis_performed"] is False
    assert payload["machine_proof"]["folder_scan_performed"] is False
    assert payload["machine_proof"]["app_automation_performed"] is False
    assert payload["machine_proof"]["external_action_performed"] is False
    assert payload["machine_proof"]["model_call_performed"] is False
    for key, value in payload["authority_boundary"].items():
        assert value is False, key


def test_generated_outputs_have_no_raw_pii_secret_or_private_body(tmp_path, capsys):
    _import_fixture(tmp_path, capsys)
    export_root = tmp_path / "read_models"
    json_path = export_root / intake.JSON_EXPORT_NAME
    operator_path = export_root / intake.OPERATOR_EXPORT_NAME
    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")

    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert data["machine_proof"]["raw_pii_in_generated_outputs"] is False
    assert not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", combined)
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "raw email body:" not in combined.lower()
    assert "private key" not in combined.lower()
    assert "api_key" not in combined.lower()
    assert "RAW BODY OMITTED" not in combined


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "operator_file_metadata_intake.py",
            "scripts/import_operator_file_metadata.py",
            "scripts/export_operator_file_metadata_readback.py",
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
        ".read_bytes(",
        "send_message",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source
