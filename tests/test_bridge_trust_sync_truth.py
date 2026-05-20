import ast
import json
import sqlite3
from pathlib import Path

import bridge_trust_sync_truth as bridge
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_bridge_trust_sync_truth import main as export_main


FIXED_NOW = "2026-05-20T16:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    _write_json(
        read_models / "sync_health.json",
        {
            "schema_version": "sync_health_read_model_v0",
            "generated_at": "2026-05-20T15:58:00+00:00",
            "trust_status": "stale_needs_mac_sync",
            "mirror_status": "needs_mac_sync",
            "display_status": "sync_requested_waiting_for_mac",
            "sync_lifecycle_state": "sync_requested_waiting_for_mac",
            "operator_action_required": False,
            "next_expected_actor": "mac_sync_agent",
            "canonical_expected": 198,
            "observed": 192,
            "missing_expected": 6,
            "extra": 0,
            "hash_mismatch": 0,
            "matched_hash": 192,
            "missing_files": [
                "chief_check_engine_diagnostic_package.json",
                "chief_check_engine_diagnostic_package_OPERATOR.md",
            ],
            "last_mac_completion": {"status": "synced", "time": "2026-05-19T17:55:07+00:00"},
            "recommended_fix": {
                "kind": "wait_for_mac_sync",
                "request_marker_path": "/mnt/e/openclaw/shuttle/to_mac/read_model_sync_required.json",
                "app_request_marker_path": "/Volumes/openclaw_e/shuttle/to_mac/read_model_sync_required.json",
                "can_request_fix_from_app": False,
            },
        },
    )
    _write_json(
        read_models / "chief_check_engine_diagnostic_package.json",
        {
            "schema_version": "chief_check_engine_diagnostic_package_v0",
            "check_engine_on": True,
            "evidence_references": [
                {
                    "ref_id": "operator_mac_bridge_report",
                    "evidence_type": "operator_reported",
                    "fields": {
                        "expected_mac_mount": "/Volumes/openclaw_e",
                        "expected_windows_source": "E:\\openclaw / WSL /mnt/e/openclaw",
                        "current_mount_status": "missing_on_mac",
                        "launch_agent_status_label": "share_missing",
                        "mac_local_mirror_file_count_after_helper_pull": 194,
                    },
                }
            ],
        },
    )
    _write_json(
        read_models / "chief_check_engine_environment_posture.json",
        {
            "schema_version": "chief_check_engine_environment_posture_v0",
            "check_engine": {"check_engine_on": True},
        },
    )
    (read_models / "sync_health_OPERATOR.md").write_text("# OpenClaw Sync Health\n", encoding="utf-8")
    (read_models / "chief_check_engine_diagnostic_package_OPERATOR.md").write_text(
        "# Chief Check-Engine Diagnostic Package\n",
        encoding="utf-8",
    )


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return bridge.build_bridge_trust_sync_truth(repo_root=repo, generated_at=FIXED_NOW)


def test_bridge_truth_is_deterministic_companion_to_sync_health(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert bridge.stable_json(first) == bridge.stable_json(second)
    assert first["schema_version"] == bridge.SCHEMA_VERSION
    assert first["relationship_to_sync_health"]["extends_or_replaces"] == "companion_read_model"
    assert first["relationship_to_sync_health"]["sync_health_remains_backward_compatible"] is True


def test_pc_canonical_pc_observed_and_mac_local_readback_are_separate(tmp_path):
    payload = _build(tmp_path)

    assert payload["pc_canonical_expected_set"]["canonical_expected_count"] == 198
    assert payload["pc_observed_mac_proof"]["pc_observed_mac_count"] == 192
    assert payload["pc_observed_mac_proof"]["missing_expected_count"] == 6
    assert payload["pc_observed_mac_proof"]["is_full_bridge_trust"] is False
    assert payload["mac_local_mirror_presence"]["local_mac_manifest_count"] == 194
    assert payload["mac_local_mirror_presence"]["local_readback_status"] == "partial"
    assert payload["mac_local_mirror_presence"]["is_canonical_bridge_proof"] is False
    assert payload["mac_local_mirror_presence"]["can_be_used_as_full_trust"] is False


def test_mount_completion_marker_and_trust_state_are_classified(tmp_path):
    payload = _build(tmp_path)

    assert payload["shuttle_mount"]["shuttle_mount_status"] == "missing"
    assert payload["shuttle_mount"]["expected_mac_mount"] == "/Volumes/openclaw_e"
    assert payload["shuttle_completion"]["shuttle_completion_status"] == "stale"
    assert payload["sync_marker_request_state"]["sync_lifecycle_state"] == "sync_requested_waiting_for_mac"
    assert payload["sync_marker_request_state"]["operator_action_required"] is False
    assert payload["bridge_trust_state"] == "bridge_mount_missing"
    assert set(payload["secondary_bridge_states"]) == {"local_readback_only", "stale_pc_proof", "waiting_for_mac"}
    assert payload["bridge_trust_state"] in bridge.BRIDGE_TRUST_STATES


def test_check_engine_lights_without_operator_action_required(tmp_path):
    payload = _build(tmp_path)

    assert payload["check_engine_should_light"] is True
    assert payload["operator_action_required"] is False
    assert payload["system_condition_not_operator_interrupt"] is True
    assert "system/workbench reliability" in payload["current_classification_explanation"]["why_this_is_check_engine"]


def test_operator_output_questions_are_answerable_from_payload(tmp_path):
    payload = _build(tmp_path)
    explanation = payload["current_classification_explanation"]

    assert "PC canonical expected=198" in explanation["what_pc_knows"]
    assert "Mac-local helper report saw 194 files" in explanation["what_mac_local_mirror_appears_to_know"]
    assert "Mac mount availability proof for /Volumes/openclaw_e" in explanation["what_proof_is_missing"]
    assert "PC canonical expected set count" in explanation["what_can_be_trusted"]
    assert "Mac-local file presence as full PC-Mac bridge proof" in explanation["what_cannot_be_trusted_yet"]
    assert payload["safe_next_step"].startswith("Keep Mission Control in Check Engine detail")


def test_forbidden_actions_storage_policy_and_authority_flags_are_closed(tmp_path):
    payload = _build(tmp_path)

    assert any("write OpenClaw artifacts to C:" in action for action in payload["forbidden_actions"])
    assert any("remount /Volumes/openclaw_e" in action for action in payload["forbidden_actions"])
    assert any("manual-copy generated files" in action for action in payload["forbidden_actions"])
    assert payload["storage_policy"]["do_not_write_openclaw_artifacts_to_pc_c_drive"] is True
    assert payload["storage_policy"]["allowed_openclaw_artifact_roots"] == ["/home/openclaw", "/mnt/e/openclaw"]
    for key, expected in bridge.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected


def test_sqlite_receipt_uses_existing_metadata_only_pattern_without_raw_bodies(tmp_path):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    db_path = tmp_path / "bridge_truth_receipts.sqlite"

    receipt_id = bridge.record_bridge_trust_sync_truth_receipt(
        repo_root=repo,
        db_path=db_path,
        commit_hash="abc123",
        generated_at=FIXED_NOW,
        ensure=True,
    )
    second_receipt_id = bridge.record_bridge_trust_sync_truth_receipt(
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
    assert payload_json["contract_id"] == bridge.SCHEMA_VERSION
    assert payload_json["metadata_only"] is True
    assert payload_json["raw_logs_stored"] is False
    assert payload_json["credentials_stored"] is False
    assert payload_json["broad_temp_listing_stored"] is False
    assert payload_json["raw_file_bodies_stored"] is False
    assert payload_json["c_drive_artifact_written"] is False


def test_export_writes_generated_json_operator_and_cli(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    result = bridge.export_bridge_trust_sync_truth(
        repo_root=repo,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )

    assert result.schema_version == bridge.SCHEMA_VERSION
    assert result.bridge_trust_state == "bridge_mount_missing"
    assert result.check_engine_should_light is True
    assert result.sqlite_receipt_supported is True
    assert result.c_drive_artifact_written is False
    assert result.runtime_authority_added is False
    expected = set(
        canonical_generated_read_model_expected_files(
            source_root=repo / "generated/read_models",
            repo_root=repo,
        )
    )
    assert bridge.JSON_EXPORT_NAME in expected
    assert bridge.OPERATOR_EXPORT_NAME in expected

    assert export_main(["--repo-root", repo.as_posix(), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == bridge.SCHEMA_VERSION

    assert export_main(["--repo-root", repo.as_posix(), "--format", "operator"]) == 0
    output = capsys.readouterr().out
    assert "Bridge Trust / Sync Truth v0" in output
    assert "Bridge trust state: `bridge_mount_missing`" in output
    assert "What Cannot Be Trusted Yet" in output


def test_source_does_not_import_live_execution_or_account_mechanisms():
    source_files = [
        Path("bridge_trust_sync_truth.py"),
        Path("scripts/export_bridge_trust_sync_truth.py"),
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
    source = Path("bridge_trust_sync_truth.py").read_text(encoding="utf-8")
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
