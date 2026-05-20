import ast
import json
import sqlite3
from pathlib import Path

import operator_mission_priority_helm_declutter as declutter
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_operator_mission_priority_helm_declutter import main as export_main


FIXED_NOW = "2026-05-20T21:15:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    fixtures = {
        "system_health_lights_taxonomy.json": {
            "schema_version": "system_health_lights_taxonomy_v0",
            "current_light_states": {
                "check_engine": "WARNING",
                "check_transmission": "QUIET",
                "low_fuel_low_battery": "WARNING",
                "oil_pressure_coolant": "WARNING",
                "brake_parking_brake": "ON_NORMAL",
                "traction_control": "QUIET",
            },
        },
        "operator_nested_lane_mission_package_spine.json": {
            "schema_version": "operator_nested_lane_mission_package_spine_v0",
            "nested_lane_count": 14,
            "top_level_system_awareness_discovery_lane": {"lane_id": "system_awareness_discovery"},
        },
        "operator_awareness_agent_package_spine.json": {
            "schema_version": "operator_awareness_agent_package_spine_v0",
            "awareness_gap_items_are_button_ready": True,
        },
        "sync_health.json": {
            "schema_version": "sync_health_read_model_v0",
            "canonical_expected": 206,
            "observed": 206,
            "missing_expected": 0,
            "hash_mismatch": 0,
            "sync_lifecycle_state": "trusted_current",
            "trust_status": "trusted",
            "mirror_status": "ok",
        },
        "world_domain_registry.json": {
            "read_model_version": "world_domain_registry_v0",
            "world_count": 8,
            "worlds": [
                {"world_id": "music_art", "label": "Music / Art"},
                {"world_id": "finance", "label": "Finance"},
                {"world_id": "operations", "label": "Operations"},
                {"world_id": "security", "label": "Security"},
                {"world_id": "build", "label": "Build"},
                {"world_id": "research", "label": "Research"},
                {"world_id": "communications", "label": "Communications"},
                {"world_id": "business_development", "label": "Business Development"},
            ],
        },
        "operator_workbench_actor_host_registry.json": {
            "schema_version": "operator_workbench_actor_host_registry_v0",
            "host_count": 8,
        },
        "repo_a_known_rail_completion_map.json": {
            "schema_version": "repo_a_known_rail_completion_map_v0",
        },
        "cross_repo_awareness_matrix.json": {
            "schema_version": "cross_repo_awareness_matrix_v0",
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return declutter.build_operator_mission_priority_helm_declutter(
        repo_root=repo,
        generated_at=FIXED_NOW,
    )


def _item(payload: dict, item_id: str) -> dict:
    return next(item for item in payload["classification_items"] if item["item_id"] == item_id)


def test_declutter_taxonomy_is_deterministic_and_references_existing_contracts(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert declutter.stable_json(first) == declutter.stable_json(second)
    assert first["schema_version"] == declutter.SCHEMA_VERSION
    assert first["read_model_id"] == "operator_mission_priority_helm_declutter"
    assert first["taxonomy_status"] == "deterministic_metadata_only_mission_priority_declutter"
    assert first["relationship_to_existing_contracts"]["does_not_replace_helm_state"] is True
    assert first["relationship_to_existing_contracts"]["does_not_replace_system_health_lights"] is True
    assert first["relationship_to_existing_contracts"]["does_not_replace_world_registry"] is True
    assert first["machine_proof"]["source_read_models_present"]["sync_health"] is True
    assert first["machine_proof"]["source_read_models_present"]["operator_workbench_actor_host_registry"] is True


def test_current_mission_and_success_conditions_are_captured(tmp_path):
    payload = _build(tmp_path)

    assert payload["current_mission"]["mission_id"] == "mission_control_app_finish_sprint"
    assert "clean, calm, usable helm" in payload["current_mission"]["operator_summary"]
    assert payload["mission_deadline_label"] == "approximately_5_days_app_finish_sprint"
    assert payload["helm_mode"] == "DEVELOPER_MODE_BUILD_MODE"
    assert payload["target_future_mode"] == "QUIET_OPERATIONAL_HELM"
    assert payload["mission_success_conditions"] == [
        "system health is obvious",
        "current build/developer work is organized",
        "worlds/domains are visible and ready to enter",
        "package/detour/proof flow is consistent",
        "operator stops mentally tracking the system manually",
    ]


def test_bucket_classification_distinguishes_helm_lights_worlds_proof_future_and_parked(tmp_path):
    payload = _build(tmp_path)

    assert set(payload["classification_buckets"]) == {
        "helm_lanes",
        "check_lights",
        "worlds",
        "proof_detail",
        "future_gated",
        "parked",
    }
    assert _item(payload, "system_awareness_discovery")["bucket"] == "helm_lanes"
    assert _item(payload, "check_transmission")["bucket"] == "check_lights"
    assert _item(payload, "worlds_teleport_targets")["bucket"] == "worlds"
    assert _item(payload, "raw_contracts_receipts_long_paths")["bucket"] == "proof_detail"
    assert _item(payload, "live_execution_integrations")["bucket"] == "future_gated"
    assert _item(payload, "deep_domain_work")["bucket"] == "parked"


def test_priority_rules_rank_5_day_mission_blockers_first(tmp_path):
    payload = _build(tmp_path)
    rules = payload["priority_rules"]
    ranking = payload["current_priority_ranking"]

    assert rules[0]["rule_id"] == "blocks_app_finish_mission_first"
    assert [item["priority_id"] for item in ranking[:8]] == [
        "system_health_intelligible",
        "bridge_transmission_trusted",
        "helm_front_door_calm",
        "steel_thread_pattern_consistent",
        "workbench_actor_host_registry_clear",
        "package_preview_detour_flow",
        "worlds_as_teleport_targets",
        "deep_domain_work_waits",
    ]
    assert ranking[0]["blocks_current_mission_if_unresolved"] is True
    assert ranking[-1]["should_wait_unless_blocks_mission"] is True


def test_above_fold_collapsed_proof_and_not_top_level_card_policy(tmp_path):
    payload = _build(tmp_path)
    front = payload["front_door_render_contract"]

    assert "mode_and_mission_strip" in front["above_fold"]
    assert "system_health_light_row" in front["above_fold"]
    assert "active_mission_next_safe_move" in front["above_fold"]
    assert "every_read_model_as_equal_card" in front["must_not_render_as_top_level"]
    assert "deep_nested_lane_tree" in front["must_not_render_as_top_level"]
    assert "raw_contracts_and_receipts" in front["proof_detail_shelf"]
    assert "nested_lane_children" in front["collapsed_by_default"]
    assert _item(payload, "nested_lane_tree")["surface_policy"] == "collapsed_by_default"
    assert _item(payload, "raw_contracts_receipts_long_paths")["surface_policy"] == "proof_detail_shelf"


def test_worlds_are_teleport_targets_not_helm_clutter_unless_attention(tmp_path):
    payload = _build(tmp_path)
    worlds = _item(payload, "worlds_teleport_targets")

    assert worlds["bucket"] == "worlds"
    assert worlds["surface_policy"] == "collapsed_world_launcher"
    assert worlds["top_level_helm_card_allowed"] is False
    assert worlds["rise_to_helm_when"] == [
        "meaningful attention flag",
        "blocked workflow",
        "build-out need that affects current mission",
    ]
    assert "Gardening" in worlds["examples"]
    assert payload["world_policy"]["normal_domain_work_belongs_inside_worlds"] is True
    assert payload["world_policy"]["domain_attention_rises_to_helm_only_when_relevant"] is True


def test_check_lights_are_not_normal_lanes_and_sync_current_is_read(tmp_path):
    payload = _build(tmp_path)
    check_transmission = _item(payload, "check_transmission")

    assert check_transmission["bucket"] == "check_lights"
    assert check_transmission["is_normal_work_lane"] is False
    assert check_transmission["current_status_from_source"] == "QUIET"
    assert payload["source_state_summary"]["sync_health"]["sync_lifecycle_state"] == "trusted_current"
    assert payload["check_light_policy"]["visually_semantically_distinct_from_lanes"] is True
    assert payload["check_light_policy"]["quiet_when_resolved"] is True


def test_missing_sources_are_marked_unavailable_without_blocking_contract(tmp_path):
    repo = tmp_path / "repo_a"
    payload = declutter.build_operator_mission_priority_helm_declutter(
        repo_root=repo,
        generated_at=FIXED_NOW,
    )

    assert payload["machine_proof"]["source_read_models_present"]["sync_health"] is False
    assert payload["source_state_summary"]["sync_health"]["available"] is False
    assert payload["classification_items"]
    assert payload["unknown_or_missing_source_policy"]["do_not_invent_source_facts"] is True
    assert payload["unknown_or_missing_source_policy"]["classification_can_still_render_static_doctrine"] is True


def test_operator_output_answers_required_questions(tmp_path):
    payload = _build(tmp_path)
    output = declutter.format_operator_mission_priority_helm_declutter(payload)

    assert "Operator Mission Priority / Helm Declutter Taxonomy v0" in output
    assert "Current Mission" in output
    assert "What Belongs On The Helm" in output
    assert "What Belongs In Check Lights" in output
    assert "What Belongs In Worlds" in output
    assert "What Belongs Only In Proof / Detail" in output
    assert "What Should Be Collapsed" in output
    assert "What Mission Control Should Render Next" in output
    assert "The Mac app should not render every read-model as an equal card" in output


def test_sqlite_receipt_is_metadata_only_and_non_executing(tmp_path):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    db_path = tmp_path / "declutter_receipts.sqlite"

    receipt_id = declutter.record_operator_mission_priority_helm_declutter_receipt(
        repo_root=repo,
        db_path=db_path,
        commit_hash="abc123",
        generated_at=FIXED_NOW,
        ensure=True,
    )
    second_receipt_id = declutter.record_operator_mission_priority_helm_declutter_receipt(
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
    assert packet["runtime_activation"] is False
    assert packet["execution_authority"] == 0
    receipt_payload = packet["payload_json"]
    assert receipt_payload["contract_id"] == declutter.SCHEMA_VERSION
    assert receipt_payload["metadata_only"] is True
    assert receipt_payload["raw_logs_stored"] is False
    assert receipt_payload["credentials_stored"] is False
    assert receipt_payload["raw_private_file_bodies_stored"] is False
    assert receipt_payload["c_drive_artifact_written"] is False


def test_export_writes_generated_json_operator_and_cli(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    result = declutter.export_operator_mission_priority_helm_declutter(
        repo_root=repo,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )

    assert result.schema_version == declutter.SCHEMA_VERSION
    assert result.classification_item_count >= 12
    assert result.sqlite_receipt_supported is True
    assert result.c_drive_artifact_written is False
    assert result.runtime_authority_added is False
    assert "operator_mission_priority_helm_declutter.json" in canonical_generated_read_model_expected_files(
        source_root=repo / "generated/read_models",
        repo_root=repo,
    )
    assert "operator_mission_priority_helm_declutter_OPERATOR.md" in canonical_generated_read_model_expected_files(
        source_root=repo / "generated/read_models",
        repo_root=repo,
    )

    assert export_main(["--repo-root", repo.as_posix(), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == declutter.SCHEMA_VERSION

    assert export_main(["--repo-root", repo.as_posix(), "--format", "operator"]) == 0
    output = capsys.readouterr().out
    assert "Operator Mission Priority / Helm Declutter Taxonomy v0" in output


def test_no_live_agent_model_tool_browser_or_c_drive_authority_is_added(tmp_path):
    payload = _build(tmp_path)

    for key, expected in declutter.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["model_calls_made"] is False
    assert payload["agents_activated"] is False
    assert payload["browser_oauth_or_account_access_enabled"] is False
    assert payload["c_drive_artifact_written"] is False
    assert payload["execution_authority_added"] is False


def test_source_does_not_import_live_execution_or_account_mechanisms():
    source_files = [
        Path("operator_mission_priority_helm_declutter.py"),
        Path("scripts/export_operator_mission_priority_helm_declutter.py"),
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
        "/mnt/c/",
        "C:\\\\",
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
    source = Path("operator_mission_priority_helm_declutter.py").read_text(encoding="utf-8")
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
    assert "out_dir = _rooted(export_root, repo_root=root)" in source
