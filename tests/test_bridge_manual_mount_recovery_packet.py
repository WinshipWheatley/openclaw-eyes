import ast
import json
import sqlite3
from pathlib import Path

import bridge_manual_mount_recovery_packet as packet
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_bridge_manual_mount_recovery_packet import main as export_main


FIXED_NOW = "2026-05-20T18:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    _write_json(
        read_models / "sync_health.json",
        {
            "schema_version": "sync_health_read_model_v0",
            "generated_at": "2026-05-20T17:58:00+00:00",
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
                "chief_check_engine_environment_posture.json",
                "chief_check_engine_environment_posture_OPERATOR.md",
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
        read_models / "bridge_trust_sync_truth.json",
        {
            "schema_version": "bridge_trust_sync_truth_v0",
            "bridge_trust_state": "bridge_mount_missing",
            "secondary_bridge_states": ["local_readback_only", "stale_pc_proof", "waiting_for_mac"],
            "check_engine_should_light": True,
            "operator_action_required": False,
            "shuttle_mount": {
                "shuttle_mount_status": "missing",
                "expected_mac_mount": "/Volumes/openclaw_e",
                "expected_windows_source": "E:\\openclaw / WSL /mnt/e/openclaw",
                "launch_agent_status_label": "share_missing",
            },
            "mac_local_mirror_presence": {
                "local_mac_manifest_count": 194,
                "local_readback_status": "partial",
                "is_canonical_bridge_proof": False,
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
                        "desktop_mac_manifest_path_records": 194,
                        "nested_lane_spine_local_json_parsed_lane_count": 14,
                    },
                }
            ],
        },
    )
    (read_models / "sync_health_OPERATOR.md").write_text("# Sync Health\n", encoding="utf-8")
    (read_models / "bridge_trust_sync_truth_OPERATOR.md").write_text("# Bridge Trust\n", encoding="utf-8")
    (read_models / "chief_check_engine_diagnostic_package_OPERATOR.md").write_text(
        "# Chief Diagnostic\n",
        encoding="utf-8",
    )


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return packet.build_bridge_manual_mount_recovery_packet(repo_root=repo, generated_at=FIXED_NOW)


def test_manual_mount_packet_is_deterministic_companion_to_bridge_truth(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert packet.stable_json(first) == packet.stable_json(second)
    assert first["schema_version"] == packet.SCHEMA_VERSION
    assert first["packet_id"] == "bridge_manual_mount_recovery_packet_v0"
    assert first["owner"] == {"primary": "Chief", "trust_surface": "Mirror Trust"}
    assert first["status"] == "blocked_manual_mount_required"
    assert first["relationship_to_bridge_trust"]["extends_or_replaces"] == "companion_packet"


def test_packet_names_exact_expected_paths_and_current_blocker(tmp_path):
    payload = _build(tmp_path)

    assert payload["bridge_mount_expected_paths"] == {
        "windows_source": "E:\\openclaw",
        "wsl_source": "/mnt/e/openclaw",
        "mac_mount": "/Volumes/openclaw_e",
        "mac_sync_request_marker": "/Volumes/openclaw_e/shuttle/to_mac/read_model_sync_required.json",
        "wsl_sync_request_marker": "/mnt/e/openclaw/shuttle/to_mac/read_model_sync_required.json",
    }
    assert payload["current_blocker"]["blocker_id"] == "mac_bridge_mount_missing"
    assert payload["current_blocker"]["status"] == "blocked_manual_mount_required"
    assert "cannot complete" in payload["current_blocker"]["plain_language"]
    assert payload["current_blocker"]["must_be_resolved_by"] == "Winship manual Mac/Windows mount action"


def test_mac_and_pc_facts_preserve_basis_without_promoting_local_readback_to_truth(tmp_path):
    payload = _build(tmp_path)

    mac_facts = {item["fact_id"]: item for item in payload["observed_mac_facts"]}
    assert mac_facts["mac_mount_missing"]["basis"] == "operator_reported"
    assert mac_facts["mac_local_mirror_file_count"]["value"] == 194
    assert mac_facts["desktop_mac_manifest_path_records"]["value"] == 194
    assert mac_facts["nested_lane_spine_local_readback"]["value"] == "present_parsed_14_lanes"
    assert mac_facts["chief_posture_local_readback"]["value"] == "missing_locally"
    assert mac_facts["chief_diagnostic_local_readback"]["value"] == "missing_locally"
    assert mac_facts["local_readback_is_full_bridge_proof"]["value"] is False

    pc = payload["observed_pc_facts"]
    assert pc["current_sync_health"]["canonical_expected"] == 198
    assert pc["current_sync_health"]["observed"] == 192
    assert pc["current_sync_health"]["missing_expected"] == 6
    assert pc["bridge_trust"]["bridge_trust_state"] == "bridge_mount_missing"
    assert pc["operator_checkpoint_before_packet"]["canonical_expected"] == 198
    assert pc["operator_checkpoint_before_packet"]["basis"] == "operator_prompt_current_fact"


def test_manual_steps_are_explicit_manual_only_and_service_kick_is_future_gated(tmp_path):
    payload = _build(tmp_path)

    assert payload["manual_operator_steps"][0]["actor"] == "Winship"
    assert payload["manual_operator_steps"][0]["automatable_by_packet"] is False
    assert all(step["packet_runs_command"] is False for step in payload["manual_operator_steps"])
    assert payload["post_mount_verification_steps"] == [
        {
            "step_id": "verify_mount_path",
            "actor": "Winship_on_Mac",
            "command": "ls -la /Volumes/openclaw_e",
            "packet_runs_command": False,
            "success_signal": "/Volumes/openclaw_e lists the Windows E:\\openclaw share.",
        },
        {
            "step_id": "verify_sync_request_marker",
            "actor": "Winship_on_Mac",
            "command": "ls -la /Volumes/openclaw_e/shuttle/to_mac/read_model_sync_required.json",
            "packet_runs_command": False,
            "success_signal": "The bounded sync request marker is visible from the Mac mount.",
        },
    ]
    assert payload["safe_existing_service_kick"] == {
        "actor": "Winship_on_Mac_after_manual_mount",
        "command": "launchctl kickstart -k gui/$(id -u)/com.openclaw.read-model-sync",
        "packet_runs_command": False,
        "future_gated": True,
        "requires_prior_successful_mount_verification": True,
        "why_safe_after_mount": "It kicks the already installed LaunchAgent; it does not add remount, credential, repair, or send authority.",
    }


def test_success_partial_failure_and_mission_control_display_are_button_ready(tmp_path):
    payload = _build(tmp_path)

    assert "/Volumes/openclaw_e exists on Mac." in payload["expected_success_proof"]
    assert "Mac sync agent no longer reports share_missing." in payload["expected_success_proof"]
    assert any("Chief posture" in item for item in payload["expected_success_proof"])
    assert any(state["state_id"] == "mac_local_mirror_updates_pc_proof_stale" for state in payload["partial_success_proof"])
    assert any(state["state_id"] == "mount_still_missing" for state in payload["failure_states"])
    assert payload["what_would_make_check_engine_quiet"][-1] == "Bridge Trust / Sync Truth returns trusted_current or equivalent current proof."

    display = payload["mission_control_should_show"]
    assert display["check_engine"] == "on"
    assert display["primary_message"].startswith("Bridge sync is blocked")
    assert display["must_show_manual_mount_required"] is True
    assert display["must_not_show_as_mirror_current"] is True
    assert "manual mount required" in display["button_metadata"][0]["label"].lower()
    assert display["button_metadata"][0]["mode"] == "read_only"


def test_chief_package_preview_and_authority_boundary_are_non_executing(tmp_path):
    payload = _build(tmp_path)

    preview = payload["chief_package_preview"]
    assert preview["character"] == "Chief"
    assert preview["actor_model"] == "future_selected_model_unspecified_not_live"
    assert preview["allowed_capabilities"] == ["inspect_only_read_only_diagnostics"]
    assert preview["launch_posture"] == "future_gated_not_live"
    assert "credentials" in " ".join(preview["context_excluded"]).lower()
    assert "deletes" in " ".join(preview["forbidden"]).lower()

    for action in (
        "delete anything",
        "remount /Volumes/openclaw_e automatically",
        "handle or store credentials",
        "write OpenClaw artifacts to C:",
        "run Mac commands from PC",
    ):
        assert action in payload["forbidden_actions"]

    assert payload["authority_boundary"]["manual_packet_only"] is True
    assert payload["authority_boundary"]["remount_authority_added"] is False
    assert payload["authority_boundary"]["credential_or_oauth_accessed"] is False
    for key, expected in packet.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected


def test_sqlite_receipt_is_metadata_only_and_non_executing(tmp_path):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    db_path = tmp_path / "manual_mount_receipts.sqlite"

    receipt_id = packet.record_bridge_manual_mount_recovery_packet_receipt(
        repo_root=repo,
        db_path=db_path,
        commit_hash="abc123",
        generated_at=FIXED_NOW,
        ensure=True,
    )
    second_receipt_id = packet.record_bridge_manual_mount_recovery_packet_receipt(
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
    envelope = json.loads(packets[0][0])
    assert envelope["receipt_type"] == "generated_status"
    assert envelope["authority_status"] == "generated_status_only"
    assert envelope["sqlite_meaning"] == "receipt_record_only"
    assert envelope["runtime_activation"] is False
    assert envelope["execution_authority"] == 0
    receipt_payload = envelope["payload_json"]
    assert receipt_payload["contract_id"] == packet.SCHEMA_VERSION
    assert receipt_payload["metadata_only"] is True
    assert receipt_payload["credentials_stored"] is False
    assert receipt_payload["raw_logs_stored"] is False
    assert receipt_payload["raw_file_bodies_stored"] is False
    assert receipt_payload["c_drive_artifact_written"] is False


def test_export_writes_generated_json_operator_and_cli(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    result = packet.export_bridge_manual_mount_recovery_packet(
        repo_root=repo,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )

    assert result.schema_version == packet.SCHEMA_VERSION
    assert result.status == "blocked_manual_mount_required"
    assert result.sqlite_receipt_supported is True
    assert result.c_drive_artifact_written is False
    assert result.runtime_authority_added is False
    expected = set(
        canonical_generated_read_model_expected_files(
            source_root=repo / "generated/read_models",
            repo_root=repo,
        )
    )
    assert packet.JSON_EXPORT_NAME in expected
    assert packet.OPERATOR_EXPORT_NAME in expected

    assert export_main(["--repo-root", repo.as_posix(), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == packet.SCHEMA_VERSION

    assert export_main(["--repo-root", repo.as_posix(), "--format", "operator"]) == 0
    output = capsys.readouterr().out
    assert "Bridge Manual Mount Recovery Packet v0" in output
    assert "Why Bridge Sync Is Blocked" in output
    assert "What Winship Should Verify After Mounting" in output
    assert "What Must Not Be Done" in output


def test_source_does_not_import_live_execution_or_account_mechanisms():
    source_files = [
        Path("bridge_manual_mount_recovery_packet.py"),
        Path("scripts/export_bridge_manual_mount_recovery_packet.py"),
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
        "subprocess.",
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
    source = Path("bridge_manual_mount_recovery_packet.py").read_text(encoding="utf-8")
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
