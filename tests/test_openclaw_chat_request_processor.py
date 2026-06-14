import json
import os
from pathlib import Path

import conversational_workflow_router_intake as chat_intake
import openclaw_chat_request_processor as processor
import operator_file_metadata_intake as file_intake
from scripts.process_openclaw_chat_requests import main as process_main


FIXED_NOW = "2026-05-25T16:00:00+00:00"


def _write_chat_request(path: Path, *, created_at: str = FIXED_NOW) -> dict:
    request = chat_intake.make_capital_hilton_fixture_request(created_at=created_at)
    path.write_text(chat_intake.stable_json(request), encoding="utf-8")
    return request


def _write_file_request(path: Path, *, fixture: str = "spreadsheet", created_at: str = FIXED_NOW) -> dict:
    request = file_intake.make_fixture_request(fixture, created_at=created_at)
    path.write_text(file_intake.stable_json(request), encoding="utf-8")
    return request


def _read_response(export_root: Path) -> dict:
    return json.loads((export_root / processor.RESPONSE_JSON_EXPORT_NAME).read_text(encoding="utf-8"))


def _read_status(export_root: Path) -> dict:
    return json.loads((export_root / processor.STATUS_JSON_EXPORT_NAME).read_text(encoding="utf-8"))


def test_newest_chat_request_is_selected(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    old_path = inbox / "mission_control_chat_request_old.json"
    new_path = inbox / "mission_control_chat_request_new.json"
    _write_chat_request(old_path)
    _write_chat_request(new_path)
    os.utime(old_path, (1, 1))
    os.utime(new_path, (2, 2))

    assert processor.select_newest_request(inbox) == new_path


def test_newest_file_request_is_selected(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    old_path = inbox / "mission_control_file_intake_request_old.json"
    new_path = inbox / "mission_control_file_intake_request_new.json"
    _write_file_request(old_path)
    _write_file_request(new_path, fixture="album")
    os.utime(old_path, (1, 1))
    os.utime(new_path, (2, 2))

    assert processor.select_newest_request(inbox) == new_path


def test_file_argument_processes_specific_chat_request(tmp_path, capsys):
    request_path = tmp_path / "mission_control_chat_request_capital_hilton.json"
    request = _write_chat_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)
    status = _read_status(export_root)

    assert response["source_request_id"] == request["request_id"]
    assert response["request_type"] == "CHAT_WORKFLOW_REQUEST"
    assert response["internal_status"] == "RESPONSE_READY"
    assert response["operator_headline"] == "I found the PC readback"
    assert "Here's what OpenClaw understood" in response["operator_message"]
    assert "RESPONSE_READY" not in response["operator_headline"]
    assert "RESPONSE_READY" not in response["operator_message"]
    assert response["cards_available"] is True
    assert response["card_mirror_refs"]
    assert status["processor_status"]["terminal_result"] == "RESPONSE_READY"


def test_file_argument_processes_specific_file_request(tmp_path, capsys):
    request_path = tmp_path / "mission_control_file_intake_request_spreadsheet.json"
    request = _write_file_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["source_request_id"] == request["request_id"]
    assert response["request_type"] == "FILE_METADATA_REQUEST"
    assert response["internal_status"] == "RESPONSE_READY"
    assert response["operator_headline"] == "File reference captured"
    assert "Capital Hilton invoice.xlsx" in response["operator_message"]
    assert "RESPONSE_READY" not in response["operator_message"]
    assert response["file_readback_refs"]


def test_malformed_json_fails_with_operator_message_and_how_to_fix(tmp_path, capsys):
    request_path = tmp_path / "mission_control_chat_request_malformed.json"
    request_path.write_text("{not json", encoding="utf-8")
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["internal_status"] == "FAILED_WITH_REASON"
    assert response["operator_headline"] == "OpenClaw could not process the request"
    assert "Malformed JSON" in response["why_it_happened"]
    assert "Regenerate the request" in response["how_to_fix"]
    assert "FAILED_WITH_REASON" not in response["operator_message"]


def test_missing_required_field_fails_with_how_to_fix(tmp_path, capsys):
    request_path = tmp_path / "mission_control_chat_request_missing_workflow.json"
    request = chat_intake.make_capital_hilton_fixture_request(created_at=FIXED_NOW)
    del request["workflow_ref"]
    request["payload_hash"] = chat_intake.compute_request_payload_hash(request)
    request_path.write_text(chat_intake.stable_json(request), encoding="utf-8")
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["internal_status"] == "BLOCKED_WITH_REASON"
    assert "Missing required field" in response["why_it_happened"]
    assert "Regenerate or resend" in response["how_to_fix"]
    assert "BLOCKED_WITH_REASON" not in response["operator_message"]


def test_missing_idempotency_fails_with_how_to_fix(tmp_path, capsys):
    request_path = tmp_path / "mission_control_chat_request_missing_idempotency.json"
    request = chat_intake.make_capital_hilton_fixture_request(created_at=FIXED_NOW)
    request["idempotency_key"] = ""
    request["payload_hash"] = chat_intake.compute_request_payload_hash(request)
    request_path.write_text(chat_intake.stable_json(request), encoding="utf-8")
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["internal_status"] == "BLOCKED_WITH_REASON"
    assert "Missing idempotency key" in response["why_it_happened"]
    assert "idempotency_key" in response["how_to_fix"]


def test_missing_request_yields_operator_message(tmp_path, capsys):
    inbox = tmp_path / "empty_inbox"
    inbox.mkdir()
    export_root = tmp_path / "read_models"

    assert process_main(["--once", "--inbox", str(inbox), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["internal_status"] == "NO_REQUEST_AVAILABLE"
    assert response["operator_headline"] == "No Mac request is waiting"
    assert "did not find a supported Mac chat or file request" in response["operator_message"]
    assert "Send a new message" in response["how_to_fix"]
    assert "NO_REQUEST_AVAILABLE" not in response["operator_message"]


def test_request_id_argument_processes_matching_request(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    request_path = inbox / "mission_control_file_intake_request_spreadsheet.json"
    request = _write_file_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(
        [
            "--request-id",
            request["request_id"],
            "--inbox",
            str(inbox),
            "--export-root",
            str(export_root),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "json",
        ]
    ) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["source_request_id"] == request["request_id"]
    assert response["source_request_filename"] == request_path.name
    assert response["operator_headline"] == "File reference captured"


def test_duplicate_noop_includes_existing_readback(tmp_path, capsys):
    request_path = tmp_path / "mission_control_file_intake_request_spreadsheet.json"
    _write_file_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    capsys.readouterr()
    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["internal_status"] == "DUPLICATE_NOOP_WITH_READBACK"
    assert "already processed this request" in response["operator_message"]
    assert "existing readback" in response["operator_message"]
    assert response["readback_files"]
    assert "DUPLICATE_NOOP_WITH_READBACK" not in response["operator_message"]


def test_blocked_file_raw_body_has_why_and_how_to_fix(tmp_path, capsys):
    request_path = tmp_path / "mission_control_file_intake_request_raw_body.json"
    _write_file_request(request_path, fixture="raw_body")
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["internal_status"] == "BLOCKED_WITH_REASON"
    assert "raw body content" in response["why_it_happened"].lower()
    assert "metadata-only" in response["how_to_fix"]
    assert response["operator_message"]


def test_processor_does_not_delete_request_or_broad_scan(tmp_path, capsys):
    request_path = tmp_path / "mission_control_file_intake_request_spreadsheet.json"
    _write_file_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert request_path.exists()
    assert response["machine_proof"]["broad_scan_performed"] is False
    assert response["machine_proof"]["request_deleted_or_mutated"] is False
    assert response["machine_proof"]["infinite_loop_possible"] is False


def test_all_external_authority_false_and_no_raw_body_ingestion(tmp_path, capsys):
    request_path = tmp_path / "mission_control_chat_request_capital_hilton.json"
    _write_chat_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "json"]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["machine_proof"]["all_live_authority_flags_false"] is True
    assert response["machine_proof"]["workflow_execution_performed"] is False
    assert response["machine_proof"]["model_call_performed"] is False
    assert response["machine_proof"]["tool_execution_performed"] is False
    assert response["machine_proof"]["external_action_performed"] is False
    assert response["machine_proof"]["credential_handling_performed"] is False
    assert response["machine_proof"]["raw_body_ingestion_performed"] is False
    for key, value in response["authority_boundary"].items():
        assert value is False, key


def test_status_and_response_json_are_parseable_and_correlated(tmp_path, capsys):
    request_path = tmp_path / "mission_control_chat_request_capital_hilton.json"
    request = _write_chat_request(request_path)
    export_root = tmp_path / "read_models"

    assert process_main(["--file", str(request_path), "--export-root", str(export_root), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    response = _read_response(export_root)
    status = _read_status(export_root)

    assert summary["source_request_id"] == request["request_id"]
    assert response["source_request_id"] == request["request_id"]
    assert status["processor_status"]["latest_processed_request"]["source_request_id"] == request["request_id"]
    assert status["machine_proof"]["terminal_quality_passed"] is True
    assert response["machine_proof"]["terminal_quality_passed"] is True


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "openclaw_chat_request_processor.py",
            "scripts/process_openclaw_chat_requests.py",
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
        "send_message",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source
