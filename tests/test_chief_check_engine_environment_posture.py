import ast
import json
import sqlite3
from pathlib import Path

import chief_check_engine_environment_posture as posture
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_chief_check_engine_environment_posture import main as export_main


FIXED_NOW = "2026-05-20T12:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    _write_json(
        root / "generated" / "read_models" / "sync_health.json",
        {
            "schema_version": "sync_health_read_model_v0",
            "generated_at": "2026-05-20T02:50:23+00:00",
            "trust_status": "stale_needs_mac_sync",
            "display_status": "sync_requested_waiting_for_mac",
            "sync_lifecycle_state": "sync_requested_waiting_for_mac",
            "mirror_status": "needs_mac_sync",
            "operator_action_required": False,
            "canonical_expected": 194,
            "observed": 192,
            "missing_expected": 2,
            "hash_mismatch": 0,
            "missing_files": [
                "operator_nested_lane_mission_package_spine.json",
                "operator_nested_lane_mission_package_spine_OPERATOR.md",
            ],
        },
    )


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return posture.build_chief_check_engine_environment_posture(
        repo_root=repo,
        generated_at=FIXED_NOW,
    )


def _signal(payload: dict, signal_id: str) -> dict:
    return next(signal for signal in payload["signals"] if signal["signal_id"] == signal_id)


def test_check_engine_environment_posture_is_deterministic_chief_owned_read_model(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert posture.stable_json(first) == posture.stable_json(second)
    assert first["schema_version"] == posture.SCHEMA_VERSION
    assert first["posture_status"] == "deterministic_check_engine_read_model_only"
    assert first["owner"] == "Chief"
    assert first["lane_type"] == "system_workbench_reliability_check_engine"
    assert first["not_a_normal_domain_lane"] is True


def test_check_engine_is_on_for_system_workbench_not_domain_lane(tmp_path):
    payload = _build(tmp_path)
    check = payload["check_engine"]

    assert check["check_engine_on"] is True
    assert check["status"] == "blocked"
    assert check["owner"] == "Chief"
    assert check["domain_lane_issue"] is False
    assert check["system_workbench_issue"] is True
    assert check["doctrine"]["chief_diagnostic_package_problem"] is True
    assert "not a music, finance" in payload["operator_eli5_summary"]["why"]


def test_required_check_engine_signals_are_present_and_button_ready(tmp_path):
    payload = _build(tmp_path)
    signal_ids = {signal["signal_id"] for signal in payload["signals"]}

    assert signal_ids == {
        "google_access_authorisation_health",
        "c_drive_free_space_low",
        "rd_client_trace_growth",
        "shuttle_mount_missing",
        "sync_completion_proof_stale",
        "mac_local_mirror_ahead_of_pc_proof",
        "codex_mac_latency_or_validation_friction",
        "launch_window_screenshot_fragility",
        "no_c_drive_write_policy",
    }
    for signal in payload["signals"]:
        assert signal["status"] in posture.SIGNAL_STATUSES
        assert signal["owner"] == "Chief"
        assert signal["what_it_means_plain_language"]
        assert signal["why_it_matters"]
        assert signal["safe_next_diagnostic_step"]
        assert signal["forbidden_actions"]
        assert isinstance(signal["should_light_check_engine"], bool)


def test_operator_reported_vs_observed_evidence_is_labeled_without_promoting_memory_to_truth(tmp_path):
    payload = _build(tmp_path)
    c_drive = _signal(payload, "c_drive_free_space_low")
    sync = _signal(payload, "sync_completion_proof_stale")
    mirror = _signal(payload, "mac_local_mirror_ahead_of_pc_proof")

    assert {item["evidence_type"] for item in c_drive["evidence"]} == {"operator_reported"}
    assert sync["evidence"][0]["evidence_type"] == "operator_reported"
    assert sync["evidence"][0]["value"]["canonical_expected"] == 194
    assert sync["evidence"][0]["value"]["observed"] == 192
    assert sync["evidence"][1]["evidence_type"] == "observed"
    assert sync["evidence"][1]["source_path"] == "generated/read_models/sync_health.json"
    assert sync["evidence"][1]["value"]["canonical_expected"] == 194
    assert sync["evidence"][1]["value"]["observed"] == 192
    assert mirror["evidence"][0]["evidence_type"] == "operator_reported"
    assert mirror["evidence"][1]["evidence_type"] == "observed"
    assert payload["machine_proof"]["proof_limit"].startswith("operator reports are preserved")


def test_storage_pressure_rd_trace_growth_and_no_c_drive_policy_are_captured(tmp_path):
    payload = _build(tmp_path)
    rd_trace = _signal(payload, "rd_client_trace_growth")
    no_c_policy = _signal(payload, "no_c_drive_write_policy")

    assert _signal(payload, "c_drive_free_space_low")["status"] == "warning"
    assert rd_trace["status"] == "warning"
    assert "5,131 ETL" in rd_trace["evidence"][0]["value"]["file_count"]
    assert no_c_policy["status"] == "ok"
    assert no_c_policy["should_light_check_engine"] is False
    assert payload["storage_policy"]["do_not_write_openclaw_artifacts_to_pc_c_drive"] is True
    assert payload["storage_policy"]["allowed_openclaw_artifact_roots"] == ["/home/openclaw", "/mnt/e/openclaw"]
    assert payload["storage_policy"]["delete_anything_in_this_lane"] is False


def test_mac_shuttle_and_sync_completion_proof_are_check_engine_signals(tmp_path):
    payload = _build(tmp_path)
    mount = _signal(payload, "shuttle_mount_missing")
    sync = _signal(payload, "sync_completion_proof_stale")

    assert mount["status"] == "blocked"
    assert mount["should_light_check_engine"] is True
    assert mount["evidence"][0]["value"]["expected_mount"] == "/Volumes/openclaw_e"
    assert mount["evidence"][1]["value"]["status_label"] == "share_missing"
    assert sync["status"] == "warning"
    assert sync["should_light_check_engine"] is True
    assert sync["evidence"][0]["value"]["missing_expected"] == 2
    assert sync["evidence"][1]["value"]["missing_expected"] == 2


def test_chief_package_preview_is_metadata_only_future_gated_and_non_executing(tmp_path):
    payload = _build(tmp_path)
    package = payload["chief_package_preview"]

    assert package["future_gated"] is True
    assert package["dispatchable_now"] is False
    assert package["actor_model"]["candidate"] == "unspecified_candidate_not_live"
    assert package["actor_model"]["model_call_allowed"] is False
    assert package["character"] == "Chief"
    assert package["mission"] == "Diagnose environment, bridge, and tooling degradation without repair authority."
    assert "inspect-only diagnostics" in package["capabilities"]
    assert "deletes, remount credentials, app mutation, runtime execution, sends/submits" not in " ".join(
        package["forbidden"]
    )
    assert any("delete files" in item for item in package["forbidden"])
    assert any("remount" in item for item in package["forbidden"])


def test_future_gated_actions_and_authority_boundaries_are_explicit(tmp_path):
    payload = _build(tmp_path)

    assert payload["future_gated"]["repair_button"] is True
    assert payload["future_gated"]["delete_cleanup"] is True
    assert payload["future_gated"]["remount"] is True
    assert payload["future_gated"]["runtime_execution"] is True
    assert payload["authority_boundary_confirmation"]["no_delete_authority_granted"] is True
    assert payload["authority_boundary_confirmation"]["no_remount_authority_granted"] is True
    assert payload["authority_boundary_confirmation"]["no_c_drive_write_authority_granted"] is True
    for key, expected in posture.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected


def test_sqlite_receipt_uses_existing_metadata_only_pattern_without_raw_logs(tmp_path):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    db_path = tmp_path / "check_engine_receipts.sqlite"

    receipt_id = posture.record_chief_check_engine_environment_posture_receipt(
        repo_root=repo,
        db_path=db_path,
        commit_hash="abc123",
        generated_at=FIXED_NOW,
        ensure=True,
    )
    second_receipt_id = posture.record_chief_check_engine_environment_posture_receipt(
        repo_root=repo,
        db_path=db_path,
        commit_hash="abc123",
        generated_at=FIXED_NOW,
        ensure=True,
    )

    assert receipt_id
    assert second_receipt_id == receipt_id

    conn = sqlite3.connect(db_path)
    try:
        events = conn.execute("SELECT event_type, raw_sensitive_data_stored, replay_safe FROM events").fetchall()
        packets = conn.execute("SELECT packet_json_safe FROM packets").fetchall()
    finally:
        conn.close()

    assert events == [("generated_status", 0, 1)]
    assert len(packets) == 1
    packet = json.loads(packets[0][0])
    assert packet["receipt_type"] == "generated_status"
    assert packet["authority_status"] == "generated_status_only"
    assert packet["sqlite_meaning"] == "receipt_record_only"
    assert packet["runtime_activation"] is False
    assert packet["execution_authority"] == 0
    payload_json = packet["payload_json"]
    assert payload_json["contract_id"] == posture.SCHEMA_VERSION
    assert payload_json["metadata_only"] is True
    assert payload_json["raw_logs_stored"] is False
    assert payload_json["credentials_stored"] is False
    assert payload_json["broad_temp_listing_stored"] is False
    assert payload_json["c_drive_artifact_written"] is False
    packet_text = json.dumps(packet, sort_keys=True)
    assert "raw_log_body" not in packet_text
    assert "raw_log_contents" not in packet_text
    assert "raw_log_text" not in packet_text
    assert "full_markdown_body_stored" in packet_text
    assert packet["full_markdown_body_stored"] is False


def test_export_writes_generated_json_operator_and_cli(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    result = posture.export_chief_check_engine_environment_posture(
        repo_root=repo,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )

    assert result.schema_version == posture.SCHEMA_VERSION
    assert result.signal_count == 9
    assert result.check_engine_on is True
    assert result.sqlite_receipt_supported is True
    assert result.c_drive_artifact_written is False
    assert result.runtime_authority_added is False
    expected = set(
        canonical_generated_read_model_expected_files(
            source_root=repo / "generated/read_models",
            repo_root=repo,
        )
    )
    assert posture.JSON_EXPORT_NAME in expected
    assert posture.OPERATOR_EXPORT_NAME in expected

    assert export_main(["--repo-root", repo.as_posix(), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == posture.SCHEMA_VERSION

    assert export_main(["--repo-root", repo.as_posix(), "--format", "operator"]) == 0
    output = capsys.readouterr().out
    assert "Chief Check-Engine Environment Posture v0" in output
    assert "Check Engine: ON" in output
    assert "OpenClaw artifacts must not be written to C:" in output


def test_source_does_not_import_live_execution_or_account_mechanisms():
    source_files = [
        Path("chief_check_engine_environment_posture.py"),
        Path("scripts/export_chief_check_engine_environment_posture.py"),
    ]
    forbidden_import_roots = {
        "os",
        "subprocess",
        "requests",
        "httpx",
        "urllib",
        "smtplib",
        "imaplib",
        "webbrowser",
        "selenium",
        "playwright",
        "google_access_broker",
        "cassandra_brain",
        "chief_router",
        "shutil",
    }
    forbidden_text = [
        "unlink(",
        "rmdir(",
        "rmtree(",
        "remove(",
        "os.system",
        "send_message",
        "send_email",
        "ApplicationBuilder",
        "oauth_accessed=True",
        "credentials.json",
        "token.json",
    ]
    for path in source_files:
        source = path.read_text(encoding="utf-8")
        for needle in forbidden_text:
            assert needle not in source
        tree = ast.parse(source)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not (imports | modules) & forbidden_import_roots


def test_write_calls_are_limited_to_generated_read_model_exports_and_not_c_drive():
    source = Path("chief_check_engine_environment_posture.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]

    assert len(write_calls) == 2
    assert "c_drive_artifact_written=True" not in source
    assert "C:\\\\OpenClaw" in source
    assert "out_dir = _rooted(export_root, repo_root=repo_root)" in source
