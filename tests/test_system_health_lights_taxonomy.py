import ast
import json
import sqlite3
from pathlib import Path

import system_health_lights_taxonomy as lights
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_system_health_lights_taxonomy import main as export_main


FIXED_NOW = "2026-05-20T16:30:00+00:00"
EXPECTED_BACKEND_HEAD = "3c7620c324edbf9883930ec465749f8ca99403f0"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> dict[str, Path]:
    read_models = root / "generated" / "read_models"
    share = root / "mnt_e" / "openclaw"
    state_path = root / ".openclaw" / "state" / "read_model_import_agent_state.json"
    manifest_path = share / "mac_generated_read_models_manifest.json"
    completion_path = share / "shuttle" / "from_mac" / "read_model_sync_completed.json"
    heartbeat_path = share / "shuttle" / "from_mac" / "read_model_sync_agent_status.json"
    request_marker_path = share / "shuttle" / "to_mac" / "read_model_sync_required.json"

    manifest_records = [
        {"relative_path": f"read_model_{index}.json", "content_hash": f"hash{index}"}
        for index in range(198)
    ] + [
        {"relative_path": "chief_check_engine_environment_posture.json", "content_hash": "chief-posture"},
        {"relative_path": "chief_check_engine_diagnostic_package.json", "content_hash": "chief-diagnostic"},
        {"relative_path": "bridge_manual_mount_recovery_packet.json", "content_hash": "bridge-manual"},
        {"relative_path": "bridge_manual_mount_recovery_packet_OPERATOR.md", "content_hash": "bridge-manual-md"},
    ]
    _write_json(
        read_models / "sync_health.json",
        {
            "schema_version": "sync_health_read_model_v0",
            "generated_at": "2026-05-20T15:54:48+00:00",
            "trust_status": "trusted",
            "mirror_status": "ok",
            "display_status": "current",
            "sync_lifecycle_state": "trusted_current",
            "operator_action_required": False,
            "next_expected_actor": "none",
            "canonical_expected": 202,
            "observed": 202,
            "missing_expected": 0,
            "extra": 0,
            "hash_mismatch": 0,
            "matched_hash": 202,
            "missing_files": [],
            "last_mac_completion": {"status": "synced", "time": "2026-05-20T15:52:06+00:00"},
            "last_mac_heartbeat": {
                "status": "synced",
                "time": "2026-05-20T15:52:06+00:00",
                "manifest_written": True,
                "marker_seen": True,
            },
            "last_pc_import": {
                "status": "success",
                "time": "2026-05-20T15:54:48+00:00",
                "manifest_hash": "manifest-sha",
            },
            "recommended_fix": {
                "kind": "none",
                "request_marker_path": share.joinpath("shuttle/to_mac/read_model_sync_required.json").as_posix(),
                "app_request_marker_path": "/Volumes/openclaw_e/shuttle/to_mac/read_model_sync_required.json",
                "can_request_fix_from_app": False,
            },
        },
    )
    _write_json(
        read_models / "bridge_trust_sync_truth.json",
        {
            "schema_version": "bridge_trust_sync_truth_v0",
            "generated_at": "2026-05-20T15:54:50+00:00",
            "bridge_trust_state": "trusted_current",
            "check_engine_should_light": False,
            "operator_action_required": False,
        },
    )
    _write_json(
        read_models / "chief_check_engine_environment_posture.json",
        {
            "schema_version": "chief_check_engine_environment_posture_v0",
            "generated_at": "2026-05-20T04:00:00+00:00",
            "check_engine": {"check_engine_on": True, "status": "blocked"},
            "signals": [
                {"signal_id": "c_drive_free_space_low", "status": "warning"},
                {"signal_id": "rd_client_trace_growth", "status": "warning"},
                {"signal_id": "sync_completion_proof_stale", "status": "warning"},
            ],
        },
    )
    _write_json(
        state_path,
        {
            "status": "skipped_unchanged",
            "updated_at": "2026-05-20T15:59:13+00:00",
            "last_imported_at": "2026-05-20T15:54:48+00:00",
            "last_path_count": 202,
            "last_mirror_counts": {
                "canonical_expected": 202,
                "observed": 202,
                "missing_expected": 0,
                "hash_mismatch": 0,
                "matched_hash": 202,
            },
            "last_final_mac_mirror_request": {
                "final_mac_mirror_marker_needed": True,
                "final_mac_mirror_marker_written": True,
                "sync_lifecycle_state": "health_exported_waiting_for_mac_mirror",
                "reason": "Canonical sync-health self-report is newer than the Mac-visible copy.",
                "self_report_mirror_state": {
                    "status": "stale_self_report_needs_mac_mirror",
                    "stale_files": ["sync_health.json", "sync_health_OPERATOR.md"],
                    "operator_action_required": False,
                },
            },
        },
    )
    _write_json(
        completion_path,
        {
            "status": "synced",
            "generated_at": "2026-05-20T15:52:06+00:00",
            "backend_head": EXPECTED_BACKEND_HEAD,
            "copied_file_count": 202,
            "manifest_path": "/Volumes/openclaw_e/mac_generated_read_models_manifest.json",
        },
    )
    _write_json(
        heartbeat_path,
        {
            "status": "idle",
            "generated_at": "2026-05-20T15:57:07+00:00",
            "backend_head": EXPECTED_BACKEND_HEAD,
            "manifest_path": "/Volumes/openclaw_e/mac_generated_read_models_manifest.json",
        },
    )
    _write_json(manifest_path, {"generated_at": "2026-05-20T15:52:06+00:00", "path_records": manifest_records})
    _write_json(request_marker_path, {"requested_at": "2026-05-20T15:59:13+00:00"})
    return {
        "pc_share_root": share,
        "state_path": state_path,
    }


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    paths = _fixture_repo(repo)
    return lights.build_system_health_lights_taxonomy(
        repo_root=repo,
        pc_share_root=paths["pc_share_root"],
        pc_import_state_path=paths["state_path"],
        generated_at=FIXED_NOW,
    )


def _light(payload: dict, light_id: str) -> dict:
    return next(light for light in payload["lights"] if light["light_id"] == light_id)


def test_taxonomy_is_deterministic_and_defines_required_lights(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert lights.stable_json(first) == lights.stable_json(second)
    assert first["schema_version"] == lights.SCHEMA_VERSION
    assert first["read_model_id"] == "system_health_lights_taxonomy"
    assert {light["light_id"] for light in first["lights"]} == {
        "check_engine",
        "check_transmission",
        "low_fuel_low_battery",
        "oil_pressure_coolant",
        "brake_parking_brake",
        "traction_control",
    }


def test_pc_import_proof_classifies_core_bridge_current_with_backend_match(tmp_path):
    payload = _build(tmp_path)
    proof = payload["pc_import_proof"]

    assert proof["canonical_expected"] == 202
    assert proof["observed"] == 202
    assert proof["missing_expected"] == 0
    assert proof["hash_mismatch"] == 0
    assert proof["pc_proof_agrees_with_mac_sync_completion"] is True
    assert proof["backend_head"] == EXPECTED_BACKEND_HEAD
    assert proof["backend_head_matches_expected"] is True
    assert proof["completion_copied_file_count"] == 202
    assert proof["manifest_path_record_count"] == 202
    assert proof["required_files_in_mac_manifest"] == {
        "chief_check_engine_environment_posture.json": True,
        "chief_check_engine_diagnostic_package.json": True,
        "bridge_manual_mount_recovery_packet.json": True,
    }


def test_transmission_quiets_when_trusted_current_overrides_stale_self_report_state(tmp_path):
    payload = _build(tmp_path)
    transmission = _light(payload, "check_transmission")

    assert transmission["current_status"] == "QUIET"
    assert transmission["current_state_kind"] == "transport_warning"
    assert transmission["current_reason"] == (
        "PC proof agrees with Mac completion and no final Mac-visible self-report echo is pending."
    )
    assert transmission["current_evidence"]["core_pc_import_proof_complete"] is True
    assert transmission["current_evidence"]["final_mac_self_report_mirror_pending"] is False
    assert transmission["current_evidence"]["self_report_stale_files"] == []
    assert transmission["when_quiet"][0].startswith("PC proof agrees")


def test_engine_is_not_used_as_bridge_catchall_when_transmission_owns_fault(tmp_path):
    payload = _build(tmp_path)
    engine = _light(payload, "check_engine")

    assert engine["current_status"] == "WARNING"
    assert engine["current_state_kind"] == "fault"
    assert engine["current_evidence"]["bridge_fault_owned_by_check_transmission"] is True
    assert engine["current_evidence"]["legacy_chief_posture_still_on"] is True
    assert "Chief diagnostic/system health lane" == engine["opens_lane"]
    assert "fresh machine proof should beat stale operator-reported bridge facts" in payload["field_observation_upgrade"]["source_precedence_rule"]


def test_resource_maintenance_authority_and_confidence_lights_have_distinct_meanings(tmp_path):
    payload = _build(tmp_path)

    low_fuel = _light(payload, "low_fuel_low_battery")
    maintenance = _light(payload, "oil_pressure_coolant")
    brake = _light(payload, "brake_parking_brake")
    traction = _light(payload, "traction_control")

    assert low_fuel["current_status"] == "WARNING"
    assert low_fuel["current_state_kind"] == "resource_warning"
    assert "C: was recently near full" in low_fuel["current_reason"]
    assert maintenance["current_status"] == "WARNING"
    assert maintenance["current_state_kind"] == "maintenance_warning"
    assert brake["current_status"] == "ON_NORMAL"
    assert brake["current_state_kind"] == "intentional_lock"
    assert brake["is_failure"] is False
    assert traction["current_status"] == "QUIET"
    assert traction["current_state_kind"] == "confidence_state"


def test_each_light_has_steel_thread_lane_mapping_and_boundaries(tmp_path):
    payload = _build(tmp_path)
    for light in payload["lights"]:
        assert light["display_name"]
        assert light["analogy"]
        assert light["owner"]
        assert light["meaning"]
        assert light["when_on"]
        assert light["when_quiet"]
        assert light["severity_status_options"] == list(lights.LIGHT_STATUS_OPTIONS)
        assert light["opens_lane"]
        assert light["steel_thread_flow"] == [
            "ELI5/operator orientation",
            "machine contract/proof",
            "package/detour/fix path",
        ]
        assert light["evidence_inputs"]
        assert light["safe_next_move"]
        assert light["forbidden_actions"]
        assert light["authority_boundary"]["read_model_only"] is True
        assert light["authority_boundary"]["runtime_authority_added"] is False


def test_operator_output_answers_current_light_questions(tmp_path):
    payload = _build(tmp_path)
    output = lights.format_system_health_lights_taxonomy(payload)

    assert "System Health Lights Taxonomy v0" in output
    assert "Check Transmission" in output
    assert "Core PC import proof is complete" in output
    assert "Mac-to-E-drive-to-PC sync proof" in output
    assert "WARNING" in output
    assert "Brake / Parking Brake" in output
    assert "What Must Not Be Done Automatically" in output


def test_sqlite_receipt_is_metadata_only_and_non_executing(tmp_path):
    repo = tmp_path / "repo_a"
    paths = _fixture_repo(repo)
    db_path = tmp_path / "system_health_lights_receipts.sqlite"

    receipt_id = lights.record_system_health_lights_taxonomy_receipt(
        repo_root=repo,
        pc_share_root=paths["pc_share_root"],
        pc_import_state_path=paths["state_path"],
        db_path=db_path,
        commit_hash="abc123",
        generated_at=FIXED_NOW,
        ensure=True,
    )
    second_receipt_id = lights.record_system_health_lights_taxonomy_receipt(
        repo_root=repo,
        pc_share_root=paths["pc_share_root"],
        pc_import_state_path=paths["state_path"],
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
    assert envelope["runtime_activation"] is False
    assert envelope["execution_authority"] == 0
    receipt_payload = envelope["payload_json"]
    assert receipt_payload["contract_id"] == lights.SCHEMA_VERSION
    assert receipt_payload["metadata_only"] is True
    assert receipt_payload["raw_logs_stored"] is False
    assert receipt_payload["credentials_stored"] is False
    assert receipt_payload["raw_file_bodies_stored"] is False
    assert receipt_payload["c_drive_artifact_written"] is False


def test_export_writes_generated_json_operator_and_cli(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    paths = _fixture_repo(repo)

    result = lights.export_system_health_lights_taxonomy(
        repo_root=repo,
        export_root="generated/read_models",
        pc_share_root=paths["pc_share_root"],
        pc_import_state_path=paths["state_path"],
        generated_at=FIXED_NOW,
    )

    assert result.schema_version == lights.SCHEMA_VERSION
    assert result.check_transmission_status == "QUIET"
    assert result.pc_proof_agrees_with_mac_sync_completion is True
    assert result.sqlite_receipt_supported is True
    assert result.c_drive_artifact_written is False
    assert result.runtime_authority_added is False
    expected = set(
        canonical_generated_read_model_expected_files(
            source_root=repo / "generated/read_models",
            repo_root=repo,
        )
    )
    assert lights.JSON_EXPORT_NAME in expected
    assert lights.OPERATOR_EXPORT_NAME in expected

    assert export_main(
        [
            "--repo-root",
            repo.as_posix(),
            "--pc-share-root",
            paths["pc_share_root"].as_posix(),
            "--pc-import-state",
            paths["state_path"].as_posix(),
            "--format",
            "json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == lights.SCHEMA_VERSION

    assert export_main(
        [
            "--repo-root",
            repo.as_posix(),
            "--pc-share-root",
            paths["pc_share_root"].as_posix(),
            "--pc-import-state",
            paths["state_path"].as_posix(),
            "--format",
            "operator",
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "System Health Lights Taxonomy v0" in output
    assert "Check Transmission" in output


def test_source_does_not_import_live_execution_or_account_mechanisms():
    source_files = [
        Path("system_health_lights_taxonomy.py"),
        Path("scripts/export_system_health_lights_taxonomy.py"),
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
    source = Path("system_health_lights_taxonomy.py").read_text(encoding="utf-8")
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
