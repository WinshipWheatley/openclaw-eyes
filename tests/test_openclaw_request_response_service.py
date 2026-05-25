import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import conversational_workflow_router_intake as chat_intake
import openclaw_request_response_service as service
import operator_file_metadata_intake as file_intake
from scripts.run_openclaw_request_response_service import main as service_main


FIXED_NOW = "2026-05-25T18:30:00+00:00"


def _write_chat_request(path: Path) -> dict:
    request = chat_intake.make_capital_hilton_fixture_request(created_at=FIXED_NOW)
    path.write_text(chat_intake.stable_json(request), encoding="utf-8")
    return request


def _write_file_request(path: Path, *, fixture: str = "spreadsheet") -> dict:
    request = file_intake.make_fixture_request(fixture, created_at=FIXED_NOW)
    path.write_text(file_intake.stable_json(request), encoding="utf-8")
    return request


def _write_unique_file_request(path: Path, suffix: str) -> dict:
    request = file_intake.make_fixture_request("spreadsheet", created_at=FIXED_NOW)
    request["request_id"] = f"mission_control_file_intake_request_spreadsheet_fixture_{suffix}"
    request["idempotency_key"] = f"file_metadata_spreadsheet_fixture_{suffix}"
    request["payload_hash"] = file_intake.compute_request_payload_hash(request)
    path.write_text(file_intake.stable_json(request), encoding="utf-8")
    return request


def _read_status(export_root: Path) -> dict:
    return json.loads((export_root / service.STATUS_JSON_EXPORT_NAME).read_text(encoding="utf-8"))


def _safe_response_path(response_dir: Path, request_id: str) -> Path:
    return response_dir / f"openclaw_response_for_mac_{service._safe_filename_part(request_id)}.json"


def test_service_scans_only_selected_inbox(tmp_path, capsys):
    inbox = tmp_path / "approved_inbox"
    outside = tmp_path / "outside"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    outside.mkdir()
    outside_request = outside / "mission_control_chat_request_outside.json"
    _write_chat_request(outside_request)

    assert service_main(
        [
            "--once",
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
    payload = json.loads(capsys.readouterr().out)

    assert payload["service_status"]["service_status"] == "IDLE_NO_REQUEST_AVAILABLE"
    assert not response_dir.exists()
    assert outside_request.exists()


def test_service_processes_chat_request_and_writes_per_request_response(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    request_path = inbox / "mission_control_chat_request_capital_hilton.json"
    request = _write_chat_request(request_path)

    assert service_main(
        [
            "--once",
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
    payload = json.loads(capsys.readouterr().out)
    response_path = _safe_response_path(response_dir, request["request_id"])
    response = json.loads(response_path.read_text(encoding="utf-8"))

    assert payload["service_status"]["service_status"] == "REQUEST_PROCESSED"
    assert response_path.exists()
    assert (response_dir / service.LATEST_RESPONSE_EXPORT_NAME).exists()
    assert (response_dir / service.MANIFEST_EXPORT_NAME).exists()
    assert response["source_request_id"] == request["request_id"]
    assert response["terminal"] is True
    assert response["operator_message"]
    assert response["how_to_fix"]
    assert "RESPONSE_READY" not in response["operator_message"]
    assert request_path.exists()


def test_service_processes_file_metadata_request_and_writes_response(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    request_path = inbox / "mission_control_file_intake_request_spreadsheet.json"
    request = _write_file_request(request_path)

    assert service_main(
        [
            "--once",
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
    capsys.readouterr()
    response_path = _safe_response_path(response_dir, request["request_id"])
    response = json.loads(response_path.read_text(encoding="utf-8"))

    assert response["request_type"] == "FILE_METADATA"
    assert response["operator_headline"] == "File reference captured"
    assert response["operator_message"]
    assert response["how_to_fix"]
    assert response["terminal"] is True
    assert request_path.exists()


def test_duplicate_request_is_skipped_without_endless_processing(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    request_path = inbox / "mission_control_file_intake_request_spreadsheet.json"
    request = _write_file_request(request_path)

    args = [
        "--once",
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
    assert service_main(args) == 0
    capsys.readouterr()
    assert service_main(args) == 0
    payload = json.loads(capsys.readouterr().out)
    response_path = _safe_response_path(response_dir, request["request_id"])

    assert payload["service_status"]["service_status"] == "REQUEST_SKIPPED_DUPLICATE"
    assert payload["service_status"]["processed_count"] == 0
    assert payload["service_status"]["skipped_duplicate_count"] >= 1
    assert response_path.exists()
    assert request_path.exists()


def test_duplicate_idempotency_key_is_skipped_before_reprocessing(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    first_path = inbox / "mission_control_file_intake_request_spreadsheet_one.json"
    second_path = inbox / "mission_control_file_intake_request_spreadsheet_two.json"
    request = _write_file_request(first_path)

    args = [
        "--once",
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
    assert service_main(args) == 0
    capsys.readouterr()

    duplicate = dict(request)
    duplicate["request_id"] = request["request_id"] + "_second"
    second_path.write_text(file_intake.stable_json(duplicate), encoding="utf-8")

    assert service_main(args) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["service_status"]["service_status"] == "REQUEST_SKIPPED_DUPLICATE"
    assert payload["service_status"]["processed_count"] == 0
    skipped = payload["service_status"]["skipped_duplicates"]
    assert any("idempotency:" + request["idempotency_key"] in item["matched_duplicate_keys"] for item in skipped)
    assert second_path.exists()


def test_failed_processing_writes_failure_response_with_fix_path(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    request_path = inbox / "mission_control_chat_request_malformed.json"
    request_path.write_text("{not json", encoding="utf-8")

    assert service_main(
        [
            "--once",
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
    payload = json.loads(capsys.readouterr().out)
    latest = payload["service_status"]["latest_response"]
    response = json.loads(Path(latest["response_file"]).read_text(encoding="utf-8"))

    assert response["internal_status"] == "FAILED_WITH_REASON"
    assert "Malformed JSON" in response["why_it_happened"]
    assert response["how_to_fix"]
    assert response["terminal"] is True
    assert "FAILED_WITH_REASON" not in response["operator_message"]


def test_watch_seconds_exits_without_unbounded_loop(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()

    assert service_main(
        [
            "--watch-seconds",
            "0",
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
    payload = json.loads(capsys.readouterr().out)

    assert payload["service_status"]["service_status"] == "WATCH_TIMED_OUT_IDLE"
    assert payload["machine_proof"]["bounded_run_mode"] is True
    assert payload["machine_proof"]["unbounded_loop_default"] is False


def test_watch_seconds_with_pending_request_does_not_reprocess_same_file_forever(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    request_path = inbox / "mission_control_file_intake_request_spreadsheet.json"
    _write_file_request(request_path)

    assert service_main(
        [
            "--watch-seconds",
            "1",
            "--poll-interval",
            "0.05",
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
    payload = json.loads(capsys.readouterr().out)

    assert payload["service_status"]["processed_count"] == 1
    assert len(payload["service_status"]["all_processed_request_records"]) == 1
    assert payload["machine_proof"]["unbounded_loop_default"] is False
    assert request_path.exists()


def test_watch_mode_notices_request_created_after_start(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    request_path = inbox / "mission_control_file_intake_request_fresh.json"

    def delayed_write() -> None:
        time.sleep(0.1)
        _write_unique_file_request(request_path, "fresh")

    writer = threading.Thread(target=delayed_write)
    writer.start()
    try:
        assert service_main(
            [
                "--watch-seconds",
                "2",
                "--poll-interval",
                "0.05",
                "--max-requests",
                "1",
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
    finally:
        writer.join(timeout=2)
    payload = json.loads(capsys.readouterr().out)

    assert payload["service_status"]["service_status"] == "REQUEST_PROCESSED"
    assert payload["service_status"]["processed_count"] == 1
    assert request_path.exists()
    latest = payload["service_status"]["latest_response"]
    response = json.loads(Path(latest["response_file"]).read_text(encoding="utf-8"))
    assert response["source_request_id"] == "mission_control_file_intake_request_spreadsheet_fixture_fresh"
    assert response["terminal"] is True


def test_watch_mode_honors_max_requests(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    _write_unique_file_request(inbox / "mission_control_file_intake_request_one.json", "one")
    _write_unique_file_request(inbox / "mission_control_file_intake_request_two.json", "two")

    assert service_main(
        [
            "--watch-seconds",
            "1",
            "--poll-interval",
            "0.05",
            "--max-requests",
            "1",
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
    payload = json.loads(capsys.readouterr().out)

    assert payload["service_status"]["processed_count"] == 1
    assert payload["service_status"]["run_mode"] == "watch_seconds=1,max_requests=1"


def test_no_request_deletion_no_raw_body_ingestion_no_external_authority(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    request_path = inbox / "mission_control_file_intake_request_raw_body.json"
    _write_file_request(request_path, fixture="raw_body")

    assert service_main(
        [
            "--once",
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
    payload = json.loads(capsys.readouterr().out)
    status = _read_status(export_root)

    assert request_path.exists()
    assert payload["machine_proof"]["no_request_deletion"] is True
    assert payload["machine_proof"]["raw_body_ingestion_performed"] is False
    assert payload["machine_proof"]["external_action_performed"] is False
    assert payload["machine_proof"]["model_call_performed"] is False
    assert payload["machine_proof"]["tool_execution_performed"] is False
    for key, value in status["authority_boundary"].items():
        assert value is False, key


def test_symlink_request_is_not_followed(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    outside = tmp_path / "outside"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    outside.mkdir()
    target = outside / "mission_control_chat_request_outside.json"
    _write_chat_request(target)
    link = inbox / "mission_control_chat_request_link.json"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        return

    assert service_main(
        [
            "--once",
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
    payload = json.loads(capsys.readouterr().out)

    assert payload["service_status"]["service_status"] == "IDLE_NO_REQUEST_AVAILABLE"
    assert payload["machine_proof"]["no_symlink_follow"] is True
