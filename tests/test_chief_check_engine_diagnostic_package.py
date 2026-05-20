import ast
import json
import sqlite3
from pathlib import Path

import chief_check_engine_diagnostic_package as package
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_chief_check_engine_diagnostic_package import main as export_main


FIXED_NOW = "2026-05-20T14:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    posture_payload = {
        "schema_version": "chief_check_engine_environment_posture_v0",
        "check_engine": {"check_engine_on": True, "status": "blocked"},
        "signal_count": 8,
        "signals": [
            {"signal_id": "c_drive_free_space_low"},
            {"signal_id": "rd_client_trace_growth"},
            {"signal_id": "shuttle_mount_missing"},
            {"signal_id": "sync_completion_proof_stale"},
            {"signal_id": "mac_local_mirror_ahead_of_pc_proof"},
            {"signal_id": "codex_mac_latency_or_validation_friction"},
            {"signal_id": "launch_window_screenshot_fragility"},
            {"signal_id": "no_c_drive_write_policy"},
        ],
    }
    sync_payload = {
        "schema_version": "sync_health_read_model_v0",
        "generated_at": "2026-05-20T13:55:00+00:00",
        "trust_status": "stale_needs_mac_sync",
        "display_status": "sync_requested_waiting_for_mac",
        "sync_lifecycle_state": "sync_requested_waiting_for_mac",
        "mirror_status": "needs_mac_sync",
        "operator_action_required": False,
        "canonical_expected": 196,
        "observed": 192,
        "missing_expected": 4,
        "hash_mismatch": 0,
        "missing_files": [
            "chief_check_engine_environment_posture.json",
            "chief_check_engine_environment_posture_OPERATOR.md",
            "operator_nested_lane_mission_package_spine.json",
            "operator_nested_lane_mission_package_spine_OPERATOR.md",
        ],
    }
    _write_json(read_models / "chief_check_engine_environment_posture.json", posture_payload)
    _write_json(read_models / "sync_health.json", sync_payload)
    (read_models / "chief_check_engine_environment_posture_OPERATOR.md").write_text(
        "# Chief Check-Engine Environment Posture\n",
        encoding="utf-8",
    )
    (read_models / "sync_health_OPERATOR.md").write_text("# OpenClaw Sync Health\n", encoding="utf-8")


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return package.build_chief_check_engine_diagnostic_package(
        repo_root=repo,
        generated_at=FIXED_NOW,
    )


def _signal(payload: dict, signal_id: str) -> dict:
    return next(signal for signal in payload["degraded_signals"] if signal["signal_id"] == signal_id)


def test_diagnostic_package_is_deterministic_chief_owned_and_inspect_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert package.stable_json(first) == package.stable_json(second)
    assert first["schema_version"] == package.SCHEMA_VERSION
    assert first["package_id"] == "chief_check_engine_diagnostic_package_v0"
    assert first["owner"] == "Chief"
    assert first["package_type"] == "check_engine_diagnostic"
    assert first["authority"] == "inspect_only_no_repair_authority"
    assert first["trigger"] == "check_engine_on"
    assert first["check_engine_on"] is True
    assert first["current_status"] == "blocked_needs_chief_diagnostic_package"


def test_package_includes_required_context_exclusions_evidence_and_mission(tmp_path):
    payload = _build(tmp_path)
    refs = {ref["ref_id"]: ref for ref in payload["evidence_references"]}

    assert "Chief check-engine environment posture summary" in payload["included_context"]
    assert "raw ETL trace contents" in payload["excluded_context"]
    assert refs["posture_json"]["evidence_type"] == "observed"
    assert refs["posture_json"]["fields"]["check_engine_on"] is True
    assert refs["sync_health_json"]["fields"]["canonical_expected"] == 196
    assert refs["operator_storage_report"]["evidence_type"] == "operator_reported"
    assert refs["operator_sync_checkpoint"]["fields"]["missing_expected"] == 4
    assert payload["diagnostic_mission"] == "Diagnose workbench, bridge, and tooling degradation without repair authority."


def test_all_current_diagnostic_signals_are_represented_with_confidence_and_distinctions(tmp_path):
    payload = _build(tmp_path)
    signal_ids = {signal["signal_id"] for signal in payload["degraded_signals"]}

    assert signal_ids == {
        "c_drive_free_space_pressure",
        "rd_client_trace_growth",
        "shuttle_mount_missing",
        "sync_proof_stale",
        "mac_local_mirror_vs_pc_proof_mismatch",
        "mac_codex_latency_validation_friction",
        "screenshot_window_validation_fragility",
        "no_c_drive_write_policy",
    }
    for signal in payload["degraded_signals"]:
        assert signal["observed_facts"] or signal["operator_reported_facts"]
        assert "confidence_posture" in signal
        assert signal["confidence_posture"] in package.CONFIDENCE_POSTURES
        assert signal["confidence_is_deterministic_posture_not_probability"] is True
        assert signal["unknowns"] is not None
        assert signal["safe_diagnostic_steps"]
        assert signal["forbidden_actions"]
        assert signal["what_would_make_quiet"]


def test_storage_and_rd_trace_signals_keep_likely_cause_separate_from_proof(tmp_path):
    payload = _build(tmp_path)
    storage = _signal(payload, "c_drive_free_space_pressure")
    rd_trace = _signal(payload, "rd_client_trace_growth")

    assert "94.8 MB" in " ".join(storage["operator_reported_facts"])
    assert "22 GB" in " ".join(storage["operator_reported_facts"])
    assert "Repo A bloat" in rd_trace["inferred_likely_causes"][0] or "Remote Desktop" in rd_trace["inferred_likely_causes"][0]
    assert "not proven" in payload["likely_causes"][0]["not_proven"]
    assert any("raw ETL trace contents" in action for action in rd_trace["forbidden_actions"])
    assert payload["storage_policy"]["do_not_write_openclaw_artifacts_to_pc_c_drive"] is True


def test_sync_signal_preserves_checkpoint_and_current_observed_sync_health(tmp_path):
    payload = _build(tmp_path)
    sync = _signal(payload, "sync_proof_stale")
    current = payload["current_sync_health_posture"]["observed_current"]

    assert payload["current_sync_health_posture"]["checkpoint_before_package"]["canonical_expected"] == 196
    assert payload["current_sync_health_posture"]["checkpoint_before_package"]["observed"] == 192
    assert current["canonical_expected"] == 196
    assert current["observed"] == 192
    assert current["missing_expected"] == 4
    assert current["hash_mismatch"] == 0
    assert sync["confidence_posture"] == "HIGH_TRUST"
    assert any("expected=196 observed=192 missing=4" in fact for fact in sync["observed_facts"])


def test_mac_mount_mismatch_latency_and_screenshot_fragility_are_distinct(tmp_path):
    payload = _build(tmp_path)
    mount = _signal(payload, "shuttle_mount_missing")
    mismatch = _signal(payload, "mac_local_mirror_vs_pc_proof_mismatch")
    latency = _signal(payload, "mac_codex_latency_validation_friction")
    screenshot = _signal(payload, "screenshot_window_validation_fragility")

    assert mount["status"] == "blocked"
    assert "/Volumes/openclaw_e" in " ".join(mount["operator_reported_facts"])
    assert mismatch["evidence_class"] == "operator_reported_mac_local_state_not_canonical_truth"
    assert "54 minutes" in " ".join(latency["operator_reported_facts"])
    assert "window-state" in " ".join(screenshot["operator_reported_facts"])
    assert any("auto-remount" in action for action in mount["forbidden_actions"])


def test_safe_steps_forbidden_actions_stop_conditions_and_quieting_are_complete(tmp_path):
    payload = _build(tmp_path)

    step_ids = {step["step_id"] for step in payload["safe_diagnostic_steps"]}
    assert step_ids == {
        "inspect_current_read_models",
        "compare_operator_report_to_observed_proof",
        "separate_bridge_from_app_correctness",
        "identify_manual_operator_action",
    }
    assert any("write OpenClaw artifacts to C:" in action for action in payload["forbidden_actions"])
    assert any("auto-remount" in action for action in payload["forbidden_actions"])
    assert "fail closed if proof is missing or contradictory" in payload["stop_conditions"]
    assert any("missing_expected=0" in item for item in payload["what_would_make_check_engine_quiet"])
    assert payload["winship_manual_action"]["required_now_by_this_package"] is False
    assert "manually check or restore" in payload["winship_manual_action"]["likely_manual_action"]


def test_chief_actor_character_package_doctrine_is_future_gated(tmp_path):
    payload = _build(tmp_path)
    body = payload["chief_package_body_preview"]
    gate = payload["future_gated_repair_cleanup_remount_posture"]

    assert body["actor_model"] == "future_selected_model_not_live"
    assert body["character"] == "Chief"
    assert body["allowed_capability"] == "inspect_only_read_only_diagnostics"
    assert "plain-language diagnosis" in body["expected_output"]
    assert gate["this_package_may_execute_repair"] is False
    assert gate["this_package_may_delete"] is False
    assert gate["this_package_may_remount"] is False
    assert gate["this_package_may_handle_credentials"] is False


def test_no_model_tool_agent_browser_oauth_send_runtime_or_c_drive_authority_is_added(tmp_path):
    payload = _build(tmp_path)

    for key, expected in package.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["c_drive_artifact_written"] is False
    assert payload["delete_authority_added"] is False
    assert payload["remount_authority_added"] is False
    assert payload["runtime_authority_added"] is False


def test_sqlite_receipt_uses_existing_metadata_only_pattern_without_raw_logs_or_trace_bodies(tmp_path):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    db_path = tmp_path / "diagnostic_package_receipts.sqlite"

    receipt_id = package.record_chief_check_engine_diagnostic_package_receipt(
        repo_root=repo,
        db_path=db_path,
        commit_hash="abc123",
        generated_at=FIXED_NOW,
        ensure=True,
    )
    second_receipt_id = package.record_chief_check_engine_diagnostic_package_receipt(
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
    packet = json.loads(packets[0][0])
    assert packet["receipt_type"] == "generated_status"
    assert packet["authority_status"] == "generated_status_only"
    assert packet["sqlite_meaning"] == "receipt_record_only"
    assert packet["runtime_activation"] is False
    assert packet["execution_authority"] == 0
    payload_json = packet["payload_json"]
    assert payload_json["contract_id"] == package.SCHEMA_VERSION
    assert payload_json["metadata_only"] is True
    assert payload_json["raw_logs_stored"] is False
    assert payload_json["raw_trace_contents_stored"] is False
    assert payload_json["credentials_stored"] is False
    assert payload_json["broad_temp_listing_stored"] is False
    assert payload_json["cleanup_proof_stored"] is False
    assert payload_json["c_drive_artifact_written"] is False


def test_export_writes_generated_json_operator_and_cli(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    result = package.export_chief_check_engine_diagnostic_package(
        repo_root=repo,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )

    assert result.schema_version == package.SCHEMA_VERSION
    assert result.package_id == "chief_check_engine_diagnostic_package_v0"
    assert result.signal_count == 8
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
    assert package.JSON_EXPORT_NAME in expected
    assert package.OPERATOR_EXPORT_NAME in expected

    assert export_main(["--repo-root", repo.as_posix(), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == package.SCHEMA_VERSION

    assert export_main(["--repo-root", repo.as_posix(), "--format", "operator"]) == 0
    output = capsys.readouterr().out
    assert "Chief Check-Engine Diagnostic Package v0" in output
    assert "Check Engine: ON" in output
    assert "OpenClaw artifacts must not be written to C:" in output
    assert "What Would Make Check Engine Quiet" in output


def test_source_does_not_import_live_execution_or_account_mechanisms():
    source_files = [
        Path("chief_check_engine_diagnostic_package.py"),
        Path("scripts/export_chief_check_engine_diagnostic_package.py"),
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
    source = Path("chief_check_engine_diagnostic_package.py").read_text(encoding="utf-8")
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
    assert "out_dir = _rooted(export_root, repo_root=repo_root)" in source
