import ast
import json
import sqlite3
from pathlib import Path

import steel_thread_lane_template_registry as registry
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_steel_thread_lane_template_registry import main as export_main


FIXED_NOW = "2026-05-20T22:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    fixtures = {
        "system_health_lights_taxonomy.json": {
            "schema_version": "system_health_lights_taxonomy_v0",
            "current_light_states": {"check_transmission": "QUIET"},
        },
        "operator_mission_priority_helm_declutter.json": {
            "schema_version": "operator_mission_priority_helm_declutter_v0",
            "steel_thread_pattern": {"flow": ["ELI5/operator orientation", "machine contract/proof", "package/detour/fix path"]},
        },
        "operator_nested_lane_mission_package_spine.json": {
            "schema_version": "operator_nested_lane_mission_package_spine_v0",
            "nested_lane_count": 14,
        },
        "operator_awareness_agent_package_spine.json": {
            "schema_version": "operator_awareness_agent_package_spine_v0",
            "package_preview_only": True,
        },
        "operator_workbench_actor_host_registry.json": {
            "schema_version": "operator_workbench_actor_host_registry_v0",
            "host_count": 8,
        },
        "chief_check_engine_diagnostic_package.json": {
            "schema_version": "chief_check_engine_diagnostic_package_v0",
            "package_type": "check_engine_diagnostic",
        },
        "bridge_manual_mount_recovery_packet.json": {
            "schema_version": "bridge_manual_mount_recovery_packet_v0",
            "status": "blocked_manual_mount_required",
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return registry.build_steel_thread_lane_template_registry(
        repo_root=repo,
        generated_at=FIXED_NOW,
    )


def _template(payload: dict, template_id: str) -> dict:
    return next(template for template in payload["templates"] if template["template_id"] == template_id)


def _control(payload: dict, control_id: str) -> dict:
    return next(control for control in payload["control_behavior_registry"]["controls"] if control["control_id"] == control_id)


def test_registry_is_deterministic_and_references_existing_contracts(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert registry.stable_json(first) == registry.stable_json(second)
    assert first["schema_version"] == registry.SCHEMA_VERSION
    assert first["read_model_id"] == "steel_thread_lane_template_registry"
    assert first["registry_status"] == "deterministic_metadata_only_steel_thread_template_registry"
    assert first["relationship_to_existing_contracts"]["does_not_replace_declutter_taxonomy"] is True
    assert first["relationship_to_existing_contracts"]["does_not_replace_nested_lane_spine"] is True
    assert first["relationship_to_existing_contracts"]["does_not_replace_awareness_spine"] is True
    assert first["machine_proof"]["source_read_models_present"]["operator_mission_priority_helm_declutter"] is True
    assert first["machine_proof"]["source_read_models_present"]["operator_workbench_actor_host_registry"] is True


def test_required_template_types_are_defined(tmp_path):
    payload = _build(tmp_path)

    assert [template["template_id"] for template in payload["templates"]] == [
        "helm_lane",
        "check_light_lane",
        "world_lane",
        "nested_lane",
        "proof_detail_lane",
        "package_preview_lane",
        "confidence_detour_lane",
        "parked_lane",
    ]
    assert payload["template_type_count"] == 8
    assert set(payload["template_types"]) == {
        "helm_lane",
        "check_light_lane",
        "world_lane",
        "nested_lane",
        "proof_detail_lane",
        "package_preview_lane",
        "confidence_detour_lane",
        "parked_lane",
    }


def test_three_layer_steel_thread_contract_is_explicit(tmp_path):
    payload = _build(tmp_path)
    layers = payload["steel_thread_layers"]

    assert [layer["layer_id"] for layer in layers] == [
        "operator_orientation",
        "machine_contract_proof",
        "package_detour_fix_path",
    ]
    assert "what_is_this" in layers[0]["fields"]
    assert "safe_next_move" in layers[0]["fields"]
    assert "read_model_refs" in layers[1]["fields"]
    assert "trusted_vs_not_yet_trusted" in layers[1]["fields"]
    assert "package_preview" in layers[2]["fields"]
    assert "detour_that_raises_confidence" in layers[2]["fields"]
    assert payload["top_layer_first_policy"]["operator_first"] is True
    assert payload["top_layer_first_policy"]["top_helm_does_not_show_all_layers_at_once"] is True


def test_each_template_has_required_shape_and_safe_boundaries(tmp_path):
    payload = _build(tmp_path)
    required = set(payload["template_record_contract"]["required_fields"])

    for template in payload["templates"]:
        assert required <= set(template)
        assert template["operator_orientation_fields"]
        assert template["machine_contract_fields"]
        assert template["package_detour_fields"]
        assert template["allowed_controls"]
        assert "live_execution" in template["forbidden_controls"]
        assert "send_submit_approval" in template["forbidden_controls"]
        assert template["proof_requirements"]
        assert template["confidence_behavior"]["deterministic_confidence_hides_score"] is True
        assert template["confidence_behavior"]["failed_deterministic_job_resets_confidence"] is True
        assert template["quiet_behavior"]["quiet_when_deterministic_and_no_attention_needed"] is True
        assert template["authority_boundary"]["runtime_authority_added"] is False
        assert template["authority_boundary"]["model_or_agent_call_allowed"] is False
        assert template["expected_receipt_shape"]["receipt_required_before_state_ingest"] is True
        assert template["mac_ui_rendering_guidance"]["do_not_render_machine_proof_as_front_door"] is True


def test_template_specific_visibility_and_ownership(tmp_path):
    payload = _build(tmp_path)

    helm = _template(payload, "helm_lane")
    check = _template(payload, "check_light_lane")
    world = _template(payload, "world_lane")
    nested = _template(payload, "nested_lane")
    proof = _template(payload, "proof_detail_lane")
    parked = _template(payload, "parked_lane")

    assert helm["front_door_visibility"] == "visible_summary"
    assert check["front_door_visibility"] == "health_light_row_when_on_or_warning"
    assert check["owner_agent_character_candidates"] == ["Chief", "Guardian", "Mirror Trust"]
    assert check["is_normal_work_lane"] is False
    assert world["front_door_visibility"] == "compact_world_launcher_unless_attention"
    assert nested["mac_ui_rendering_guidance"]["show_active_parent_and_immediate_focus_only"] is True
    assert proof["front_door_visibility"] == "proof_shelf_only"
    assert proof["top_level_card_allowed"] is False
    assert parked["quiet_behavior"]["parked_lanes_do_not_demand_attention"] is True


def test_control_behavior_is_safe_before_live_authority(tmp_path):
    payload = _build(tmp_path)
    controls = payload["control_behavior_registry"]

    assert controls["controls_are_metadata_only"] is True
    assert controls["controls_mutate_state_now"] is False
    assert controls["live_authority_required_before_mutation"] is True
    assert _control(payload, "explain_this")["behavior_before_live_authority"] == "local explanation/proof orientation only"
    assert _control(payload, "what_can_i_do")["behavior_before_live_authority"] == "show safe moves and future-gated actions"
    assert _control(payload, "tell_system_whats_missing")["mutation_allowed_now"] is False
    assert _control(payload, "raise_confidence")["behavior_before_live_authority"] == "show detours and evidence needed"
    assert _control(payload, "preview_package")["dispatch_allowed_now"] is False
    assert _control(payload, "show_proof")["behavior_before_live_authority"] == "reveal machine contract and evidence"
    assert _control(payload, "keep_parked")["mutation_allowed_now"] is False
    assert _control(payload, "future_chat_workspace_target")["launch_allowed_now"] is False
    assert "future_chat_workspace_target" in controls["future_gated_controls"]


def test_confidence_and_quiet_behavior_follow_doctrine(tmp_path):
    payload = _build(tmp_path)
    confidence = payload["confidence_doctrine"]
    quiet = payload["quiet_lane_doctrine"]

    assert confidence["below_deterministic"]["show_confidence_issue"] is True
    assert confidence["below_deterministic"]["show_detour_options"] is True
    assert confidence["deterministic_or_full_trust"]["hide_confidence_score"] is True
    assert confidence["deterministic_or_full_trust"]["hide_detour_ui"] is True
    assert confidence["failed_deterministic_job"]["reset_confidence"] is True
    assert quiet["lane_becomes_quiet_when"][0] == "operator orientation is understood"
    assert quiet["do_not_display_confidence_theater_when_proof_is_deterministic"] is True


def test_actor_workbench_routing_hooks_are_metadata_only(tmp_path):
    payload = _build(tmp_path)
    package = _template(payload, "package_preview_lane")

    assert package["actor_workbench_routing_hooks"]["source_registry"] == "operator_workbench_actor_host_registry"
    assert package["actor_workbench_routing_hooks"]["model_actor_selected_now"] is False
    assert package["actor_workbench_routing_hooks"]["agent_character_activated_now"] is False
    assert package["actor_workbench_routing_hooks"]["workspace_launched_now"] is False
    assert "actor_model_candidate" in package["package_detour_fields"]
    assert "agent_character" in package["package_detour_fields"]
    assert "proof_receipt_must_return" in package["package_detour_fields"]


def test_missing_sources_are_unavailable_without_blocking_static_doctrine(tmp_path):
    repo = tmp_path / "repo_a"
    payload = registry.build_steel_thread_lane_template_registry(repo_root=repo, generated_at=FIXED_NOW)

    assert payload["machine_proof"]["source_read_models_present"]["system_health_lights_taxonomy"] is False
    assert payload["source_state_summary"]["operator_mission_priority_helm_declutter"]["available"] is False
    assert payload["templates"]
    assert payload["unknown_or_missing_source_policy"]["do_not_invent_source_facts"] is True
    assert payload["unknown_or_missing_source_policy"]["static_template_doctrine_still_renders"] is True


def test_operator_output_answers_required_questions(tmp_path):
    payload = _build(tmp_path)
    output = registry.format_steel_thread_lane_template_registry(payload)

    assert "Steel Thread Lane Template Registry v0" in output
    assert "Steel-Thread Pattern" in output
    assert "Template Types" in output
    assert "Top / Operator Layer" in output
    assert "Middle / Proof Layer" in output
    assert "Bottom / Package Layer" in output
    assert "Allowed Now Controls" in output
    assert "Future-Gated Controls" in output
    assert "Confidence Behavior" in output
    assert "Quiet Behavior" in output
    assert "Mac Rendering Guidance" in output
    assert "What Should Not Be Built Yet" in output


def test_sqlite_receipt_is_metadata_only_and_non_executing(tmp_path):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    db_path = tmp_path / "template_registry_receipts.sqlite"

    receipt_id = registry.record_steel_thread_lane_template_registry_receipt(
        repo_root=repo,
        db_path=db_path,
        commit_hash="abc123",
        generated_at=FIXED_NOW,
        ensure=True,
    )
    second_receipt_id = registry.record_steel_thread_lane_template_registry_receipt(
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
    assert receipt_payload["contract_id"] == registry.SCHEMA_VERSION
    assert receipt_payload["metadata_only"] is True
    assert receipt_payload["raw_logs_stored"] is False
    assert receipt_payload["credentials_stored"] is False
    assert receipt_payload["raw_private_file_bodies_stored"] is False
    assert receipt_payload["c_drive_artifact_written"] is False


def test_export_writes_generated_json_operator_and_cli(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    result = registry.export_steel_thread_lane_template_registry(
        repo_root=repo,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )

    assert result.schema_version == registry.SCHEMA_VERSION
    assert result.template_type_count == 8
    assert result.sqlite_receipt_supported is True
    assert result.c_drive_artifact_written is False
    assert result.runtime_authority_added is False
    assert "steel_thread_lane_template_registry.json" in canonical_generated_read_model_expected_files(
        source_root=repo / "generated/read_models",
        repo_root=repo,
    )
    assert "steel_thread_lane_template_registry_OPERATOR.md" in canonical_generated_read_model_expected_files(
        source_root=repo / "generated/read_models",
        repo_root=repo,
    )

    assert export_main(["--repo-root", repo.as_posix(), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == registry.SCHEMA_VERSION

    assert export_main(["--repo-root", repo.as_posix(), "--format", "operator"]) == 0
    output = capsys.readouterr().out
    assert "Steel Thread Lane Template Registry v0" in output


def test_expected_set_allows_durable_template_read_models_but_still_blocks_temp_files(tmp_path):
    repo = tmp_path / "repo_a"
    export_root = repo / "generated/read_models"
    export_root.mkdir(parents=True)
    _write_json(export_root / "steel_thread_lane_template_registry.json", {"ok": True})
    _write_json(export_root / "temp_context.json", {"blocked": True})
    _write_json(export_root / "temporary_export.json", {"blocked": True})

    expected = set(
        canonical_generated_read_model_expected_files(
            source_root=export_root,
            repo_root=repo,
        )
    )

    assert "steel_thread_lane_template_registry.json" in expected
    assert "temp_context.json" not in expected
    assert "temporary_export.json" not in expected


def test_no_live_agent_model_tool_browser_or_c_drive_authority_is_added(tmp_path):
    payload = _build(tmp_path)

    for key, expected in registry.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["model_calls_made"] is False
    assert payload["agents_activated"] is False
    assert payload["browser_oauth_or_account_access_enabled"] is False
    assert payload["c_drive_artifact_written"] is False
    assert payload["execution_authority_added"] is False


def test_source_does_not_import_live_execution_or_account_mechanisms():
    source_files = [
        Path("steel_thread_lane_template_registry.py"),
        Path("scripts/export_steel_thread_lane_template_registry.py"),
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
    source = Path("steel_thread_lane_template_registry.py").read_text(encoding="utf-8")
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
