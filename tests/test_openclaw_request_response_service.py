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


def _write_capital_hilton_status_request(path: Path) -> dict:
    request = chat_intake.make_capital_hilton_fixture_request(created_at=FIXED_NOW)
    request.update(
        {
            "request_id": "mission_control_chat_request_capital_hilton_status_service_fixture",
            "workflow_ref": "capital_hilton_invoice_workflow",
            "operator_message": "where are we with the Capital Hilton invoice?",
            "sanitized_message_summary": "where are we with the Capital Hilton invoice?",
            "idempotency_key": "mc_chat_capital_hilton_invoice_status_service_fixture",
        }
    )
    request["payload_hash"] = chat_intake.compute_request_payload_hash(request)
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


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


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
    latest = json.loads((response_dir / service.LATEST_RESPONSE_EXPORT_NAME).read_text(encoding="utf-8"))
    manifest = json.loads((response_dir / service.MANIFEST_EXPORT_NAME).read_text(encoding="utf-8"))

    assert payload["service_status"]["service_status"] == "REQUEST_PROCESSED"
    assert response_path.exists()
    assert (response_dir / service.LATEST_RESPONSE_EXPORT_NAME).exists()
    assert (response_dir / service.MANIFEST_EXPORT_NAME).exists()
    assert response["source_request_id"] == request["request_id"]
    assert latest["source_request_id"] == request["request_id"]
    assert manifest["latest_response_file"].endswith(service.LATEST_RESPONSE_EXPORT_NAME)
    assert response["terminal"] is True
    assert response["response_id"]
    assert response["audience_mode"] == "ELIWINSHIP"
    assert response["display_mode"] == "COMPACT_CHAT"
    assert response["response_author"] == "OPENCLAW_SYSTEM"
    assert response["voice_profile_ref"] == "voice:system:neutral"
    assert response["vibe_profile_ref"] == "vibe:system:neutral"
    assert response["voice_applied"] is True
    assert response["vibe_applied"] is True
    assert response["spoken_response_packet"]["response_author"] == "OPENCLAW_SYSTEM"
    assert response["spoken_response_packet"]["provider_policy"]["preferred_provider_family"] == "MAC_SYSTEM_TTS"
    assert response["spoken_response_packet"]["cloud_synthesis_allowed"] is False
    assert response["headline"]
    assert response["operator_message"]
    assert response["how_to_fix"]
    assert "RESPONSE_READY" not in response["operator_message"]
    assert request_path.exists()


def test_service_routes_capital_hilton_status_query_to_mac_response(tmp_path, capsys):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    request_path = inbox / "mission_control_chat_request_capital_hilton_status.json"
    request = _write_capital_hilton_status_request(request_path)

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
    latest_path = response_dir / service.LATEST_RESPONSE_EXPORT_NAME
    response = json.loads(response_path.read_text(encoding="utf-8"))
    latest = json.loads(latest_path.read_text(encoding="utf-8"))

    assert payload["service_status"]["service_status"] == "REQUEST_PROCESSED"
    assert response["source_request_id"] == request["request_id"]
    assert latest["source_request_id"] == request["request_id"]
    assert response["response_kind"] == "CAPITAL_HILTON_INVOICE_STATUS"
    assert response["response_author"] == "CHIEF"
    assert response["voice_profile_ref"] == "voice:chief:operational"
    assert response["vibe_profile_ref"] == "vibe:chief:command_center"
    assert response["voice_selection_reason"] == "finance workflow status / readiness / blocker summary"
    assert response["high_risk_override_applied"] is False
    assert response["headline"] == "Capital Hilton invoice is blocked"
    assert response["one_line_answer"] == (
        "OpenClaw has the delivery basis, but the workflow is locked because required approvals and proofs are missing."
    )
    assert response["eliwinship"] == (
        "The invoice basis and draft rails exist. "
        "The workflow is blocked until the Coupa PO/reference and approval receipts are confirmed. "
        "Nothing can send or submit yet."
    )
    assert response["primary_blocker"] == "Missing confirmed Coupa PO/reference"
    assert response["next_action"] == "Next: Confirm the Coupa PO/reference."
    assert response["missing_items_short"][:2] == [
        "Confirmed Coupa PO/reference",
        "Guardian and operator approval receipts",
    ]
    spoken = response["spoken_response_packet"]
    assert spoken["response_author"] == "CHIEF"
    assert spoken["spoken_script"] == (
        "Capital Hilton invoice is blocked. The invoice basis exists, but the Coupa PO reference and approval receipts are still missing. Nothing can send or submit yet."
    )
    assert spoken["provider_policy"]["preferred_provider_family"] == "MAC_SYSTEM_TTS"
    assert spoken["cloud_synthesis_allowed"] is False
    assert spoken["pronunciation_hints"]["Coupa"] == "coo pah"
    assert response["proof_refs"] == ["generated/read_models/capital_hilton_invoice_operator_readback.json"]
    assert response["operator_headline"] == "Capital Hilton invoice workflow is not ready yet"
    assert "Nothing has been sent, submitted, opened, approved, or marked complete" in response["operator_message"]
    assert response["how_to_fix"]
    assert response["detail_disclosure"]["can_mark_invoice_sent"] is False
    assert response["terminal"] is True
    assert any(path.endswith("capital_hilton_invoice_operator_readback.json") for path in response["readback_files"])


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
    assert response["response_kind"] == "FILE_METADATA_READBACK"
    assert response["response_author"] == "OPENCLAW_SYSTEM"
    assert response["voice_profile_ref"] == "voice:system:neutral"
    assert response["vibe_profile_ref"] == "vibe:system:neutral"
    assert response["headline"] == "File reference captured"
    assert response["eliwinship"] == (
        "OpenClaw captured the file reference. The body was not read. You can use it later as source context."
    )
    assert response["next_action"] == "Next: Choose how to use this source."
    spoken = response["spoken_response_packet"]
    assert spoken["response_author"] == "OPENCLAW_SYSTEM"
    assert spoken["spoken_script"] == "File reference captured. The body was not read. Choose whether to use it as source context."
    assert spoken["provider_policy"]["preferred_provider_family"] == "MAC_SYSTEM_TTS"
    assert spoken["provider_policy"]["cloud_transcription_allowed"] is False
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
    assert payload["service_status"]["mode"] == "stopped"
    assert payload["service_status"]["bounded_stop_reason"] == "watch_seconds_elapsed"
    assert payload["machine_proof"]["bounded_run_mode"] is True
    assert payload["machine_proof"]["unbounded_loop_default"] is False


def test_watch_mode_uses_idle_poll_interval_when_idle(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    clock = _FakeClock()
    monkeypatch.setattr(service.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(service.time, "sleep", clock.sleep)

    result = service.run_watch(
        inbox=inbox,
        response_dir=response_dir,
        export_root=export_root,
        generated_at=FIXED_NOW,
        watch_seconds=2,
        poll_interval=1.0,
        active_poll_interval=0.05,
        active_window_seconds=1.0,
        max_requests=1,
    )
    payload = service.build_service_status_payload(result, export_root=export_root, generated_at=FIXED_NOW)

    assert result.processed_count == 0
    assert clock.sleeps == [1.0, 1.0]
    assert payload["service_status"]["mode"] == "stopped"
    assert payload["service_status"]["last_watch_mode_before_stop"] == "idle"
    assert payload["service_status"]["current_poll_interval"] == 0.0
    assert payload["service_status"]["idle_poll_interval"] == 1.0
    assert payload["service_status"]["active_poll_interval"] == 0.05
    assert payload["service_status"]["bounded_stop_reason"] == "watch_seconds_elapsed"


def test_watch_mode_uses_active_poll_window_then_backs_off(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    _write_unique_file_request(inbox / "mission_control_file_intake_request_active.json", "active_window")
    clock = _FakeClock()
    monkeypatch.setattr(service.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(service.time, "sleep", clock.sleep)

    result = service.run_watch(
        inbox=inbox,
        response_dir=response_dir,
        export_root=export_root,
        generated_at=FIXED_NOW,
        watch_seconds=1.2,
        poll_interval=1.0,
        active_poll_interval=0.05,
        active_window_seconds=0.11,
        max_requests=2,
    )
    payload = service.build_service_status_payload(result, export_root=export_root, generated_at=FIXED_NOW)
    latest = result.latest_response or {}

    assert result.processed_count == 1
    assert 0.05 in clock.sleeps
    assert any(seconds >= 1.0 for seconds in clock.sleeps)
    assert payload["service_status"]["mode"] == "stopped"
    assert payload["service_status"]["last_watch_mode_before_stop"] == "idle"
    assert payload["service_status"]["last_processed_request_id"] == (
        "mission_control_file_intake_request_spreadsheet_fixture_active_window"
    )
    assert payload["service_status"]["last_response_path"] == latest.get("response_file")
    assert payload["machine_proof"]["active_session_watch_present"] is True
    assert payload["machine_proof"]["atomic_response_writes"] is True
    assert json.loads(Path(latest["response_file"]).read_text(encoding="utf-8"))["terminal"] is True


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
    assert payload["service_status"]["run_mode"].startswith("watch_seconds=1,max_requests=1")
    assert payload["service_status"]["bounded_stop_reason"] == "max_requests_reached"


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
