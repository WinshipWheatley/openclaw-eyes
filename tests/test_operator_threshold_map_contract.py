import ast
import json
from pathlib import Path

import operator_threshold_map_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_operator_threshold_map_contract import main as export_main


FIXED_NOW = "2026-05-21T16:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    fixtures = {
        "sync_health.json": {
            "schema_version": "sync_health_read_model_v0",
            "read_model_id": "sync_health",
            "generated_at": FIXED_NOW,
            "canonical_expected": 216,
            "observed": 216,
            "missing_expected": 0,
            "hash_mismatch": 0,
            "sync_lifecycle_state": "trusted_current",
            "trust_status": "trusted",
        },
        "system_health_lights_taxonomy.json": {
            "schema_version": "system_health_lights_taxonomy_v0",
            "read_model_id": "system_health_lights_taxonomy",
            "current_light_states": {"check_transmission": "ON"},
        },
        "operator_awareness_agent_package_spine.json": {
            "schema_version": "operator_awareness_agent_package_spine_v0",
            "read_model_id": "operator_awareness_agent_package_spine",
        },
        "operator_nested_lane_mission_package_spine.json": {
            "schema_version": "operator_nested_lane_mission_package_spine_v0",
            "read_model_id": "operator_nested_lane_mission_package_spine",
        },
        "steel_thread_lane_template_registry.json": {
            "schema_version": "steel_thread_lane_template_registry_v0",
            "read_model_id": "steel_thread_lane_template_registry",
        },
        "package_compiler_contract.json": {
            "schema_version": "package_compiler_contract_v0",
            "read_model_id": "package_compiler_contract",
        },
        "mission_control_design_memory_inventory.json": {
            "schema_version": "mission_control_design_memory_inventory_v0",
            "read_model_id": "mission_control_design_memory_inventory",
        },
        "operator_question_journey_registry.json": {
            "schema_version": "operator_question_journey_registry_v0",
            "read_model_id": "operator_question_journey_registry",
        },
        "operator_mission_priority_helm_declutter.json": {
            "schema_version": "operator_mission_priority_helm_declutter_v0",
            "read_model_id": "operator_mission_priority_helm_declutter",
        },
        "operator_workbench_actor_host_registry.json": {
            "schema_version": "operator_workbench_actor_host_registry_v0",
            "read_model_id": "operator_workbench_actor_host_registry",
        },
        "capital_hilton_actionable_review_packet.json": {
            "schema_version": "capital_hilton_actionable_review_packet_v1",
            "read_model_id": "capital_hilton_actionable_review_packet",
            "actionable_for_manual_review": True,
            "ready_for_submission": False,
            "no_authority_flags": {"review_only": True},
        },
        "capital_hilton_external_artifact_proof_capture.json": {
            "schema_version": "capital_hilton_external_artifact_proof_capture_v0",
            "read_model_id": "capital_hilton_external_artifact_proof_capture",
        },
        "capital_hilton_operator_proof_input_packet.json": {
            "schema_version": "capital_hilton_operator_proof_input_packet_v0",
            "read_model_id": "capital_hilton_operator_proof_input_packet",
        },
        "capital_hilton_coupa_execution_path.json": {
            "schema_version": "capital_hilton_coupa_execution_path_v0",
            "read_model_id": "capital_hilton_coupa_execution_path",
        },
        "chief_check_engine_diagnostic_package.json": {
            "schema_version": "chief_check_engine_diagnostic_package_v0",
            "read_model_id": "chief_check_engine_diagnostic_package",
        },
        "chief_check_engine_environment_posture.json": {
            "schema_version": "chief_check_engine_environment_posture_v0",
            "read_model_id": "chief_check_engine_environment_posture",
        },
        "capability_skill_registry_metadata_delta.json": {
            "schema_version": "capability_skill_registry_metadata_delta_v0",
            "read_model_id": "capability_skill_registry_metadata_delta",
        },
        "cross_repo_awareness_matrix.json": {
            "schema_version": "cross_repo_awareness_matrix_v0",
            "read_model_id": "cross_repo_awareness_matrix",
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return contract.build_operator_threshold_map_contract(
        repo_root=repo,
        generated_at=FIXED_NOW,
    )


def _lane(payload: dict, lane_id: str) -> dict:
    return next(item for item in payload["lane_inventory"] if item["lane_id"] == lane_id)


def test_threshold_contract_is_deterministic_and_pre_security_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "operator_threshold_map_contract"
    assert first["contract_status"] == "pre_security_threshold_map_metadata_only"
    assert first["strategic_correction"]["not_autonomy_queue_implementation"] is True
    assert first["package_preview_only"] is True
    assert first["live_package_dispatch_allowed"] is False
    assert first["autonomy_queue_created"] is False
    assert first["runtime_authority_added"] is False


def test_threshold_definition_has_required_checklist_and_states(tmp_path):
    payload = _build(tmp_path)
    fields = {item["field"] for item in payload["threshold_definition"]["required_checklist"]}

    for required in [
        "operator_summary",
        "current_status",
        "why_it_matters",
        "safe_next_move",
        "proof_refs",
        "missing_proof",
        "known_partly_known_known_unknown_not_discovered",
        "operator_memory_needed",
        "authority_boundary",
        "package_preview_availability",
        "detour_path",
        "what_would_make_quiet",
    ]:
        assert required in fields
    assert payload["threshold_state_vocab"] == list(contract.THRESHOLD_STATES)
    assert payload["resolution_route_vocab"] == list(contract.RESOLUTION_ROUTES)
    assert "READY_FOR_SECURITY_AUDIT" in payload["lane_ids_by_readiness_state"]
    assert "NEEDS_PROOF" in payload["lane_ids_by_readiness_state"]


def test_lane_inventory_contains_required_lanes_and_threshold_shape(tmp_path):
    payload = _build(tmp_path)
    required_lanes = {
        "system_awareness_discovery",
        "capital_hilton",
        "chief",
        "cassandra",
        "guardian",
        "niles_struna",
        "hermes",
        "repo_b_leftovers",
        "cue_parser_brain_dump_parser",
        "tool_plugin_registry",
        "model_router",
        "future_domain_workflow_lanes",
        "check_engine",
        "check_transmission",
        "resources",
        "parking_brake",
        "traction_control",
    }

    assert required_lanes == {lane["lane_id"] for lane in payload["lane_inventory"]}
    for lane in payload["lane_inventory"]:
        assert lane["readiness_state"] in contract.THRESHOLD_STATES
        assert lane["lane_kind"] in contract.LANE_KINDS
        assert lane["operator_summary"]
        assert lane["current_status"]
        assert lane["why_it_matters"]
        assert lane["safe_next_move"]
        assert "known" in lane["awareness"]
        assert "partly_known" in lane["awareness"]
        assert "known_unknown" in lane["awareness"]
        assert "not_discovered" in lane["awareness"]
        assert lane["operator_memory_is_proof"] is False
        assert lane["authority_boundary"]["live_execution_allowed_now"] is False
        assert lane["package_preview"]["live_dispatch_allowed"] is False
        assert lane["lane_destiny"]["resolution_route"] in contract.RESOLUTION_ROUTES
        assert lane["lane_destiny"]["not_currently_executable"] is True


def test_capital_hilton_is_helm_threshold_lane_destined_for_finance_world(tmp_path):
    payload = _build(tmp_path)
    lane = _lane(payload, "capital_hilton")
    steel = payload["first_steel_thread_capital_hilton"]

    assert lane["readiness_state"] == "NEEDS_PROOF"
    assert lane["lane_destiny"]["current_phase"] == "HELM_THRESHOLD_LANE"
    assert lane["lane_destiny"]["resolution_route"] == "MOVE_TO_WORLD_ACTION"
    assert lane["lane_destiny"]["target_world"] == "Finance"
    assert steel["current_phase"] == "HELM_THRESHOLD_LANE"
    assert steel["intended_destiny"] == "MOVE_TO_WORLD_ACTION"
    assert steel["target_world"] == "Finance"
    assert steel["not_currently_executable"] is True
    assert "approved Coupa proof metadata" in lane["missing_proof"]
    assert "Coupa proof metadata." in steel["missing_proof"]
    assert steel["future_package_candidate"]["dispatch_allowed_now"] is False
    assert "credentials" in steel["future_package_candidate"]["context_excluded"]


def test_system_awareness_steel_thread_separates_memory_from_proof(tmp_path):
    payload = _build(tmp_path)
    lane = _lane(payload, "system_awareness_discovery")
    steel = payload["second_steel_thread_system_awareness_discovery"]

    assert lane["readiness_state"] == "READY_FOR_SECURITY_AUDIT"
    assert lane["operator_memory_is_proof"] is False
    assert steel["current_readiness"] == "READY_FOR_SECURITY_AUDIT"
    assert steel["operator_memory_rule"]["must_be_recorded_as"] == "operator-provided context or memory comparison need"
    assert "become proof by itself" in steel["operator_memory_rule"]["may_not"]
    assert steel["tell_system_whats_missing_now"]["not_allowed_now"].startswith("live write")


def test_package_preview_and_cue_autonomy_are_future_gated(tmp_path):
    payload = _build(tmp_path)
    preview = payload["package_preview_now_vs_live_package_later"]
    cue = payload["cue_autonomy_placement"]

    assert preview["package_preview_now_allowed"] is True
    assert preview["live_chat_or_workbench_launch_now"] is False
    assert preview["model_actor_execution_now"] is False
    assert preview["agent_activation_now"] is False
    assert preview["plugin_or_tool_execution_now"] is False
    assert preview["send_submit_approval_account_flows_now"] is False
    assert preview["autonomy_queue_now"] is False
    assert cue["status"] == "post_threshold_post_security_candidate"
    assert cue["current_classification"]["planner_agent"] == "future_gated_not_active_authority"
    assert "live queue" in cue["not_created_by_this_contract"]


def test_holding_cell_and_mission_control_rendering_rules_are_explicit(tmp_path):
    payload = _build(tmp_path)
    holding = payload["holding_cell_rule"]
    rendering = payload["mission_control_rendering_guidance"]
    transition = payload["helm_to_world_transition_rule"]

    assert holding["mutates_state_now"] is False
    assert holding["live_queue_now"] is False
    assert "full nested lane tree by default" in rendering["hide_or_collapse_now"]
    assert "fake confidence percentages" in rendering["never_show_pre_security"]
    assert "post-security autonomy queue controls" in rendering["never_show_pre_security"]
    assert "lanes that affect system readiness" in transition["helm_shows"]
    assert "domain work that is ready to perform" in transition["worlds_show"]
    assert transition["backend_only_after_verified_completion"].startswith("Backend-only issues should disappear")


def test_check_transmission_source_truth_conflict_is_classified_not_repaired(tmp_path):
    payload = _build(tmp_path)
    lane = _lane(payload, "check_transmission")
    note = payload["check_transmission_source_truth_note"]

    assert note["canonical_sync_health_status"]["trusted_current"] is True
    assert note["canonical_sync_health_status"]["canonical_expected"] == 216
    assert note["canonical_sync_health_status"]["observed"] == 216
    assert note["canonical_sync_health_status"]["missing_expected"] == 0
    assert note["canonical_sync_health_status"]["hash_mismatch"] == 0
    assert note["system_health_taxonomy_check_transmission_status"] == "ON"
    assert note["source_truth_conflict_detected_in_read_models"] is True
    assert note["fix_owner_later"] == "Mac Codex"
    assert "classify only" in note["action_now"]
    assert lane["readiness_state"] == "NEEDS_SOURCE_TRUTH_RECONCILIATION"
    assert lane["lane_destiny"]["resolution_route"] == "QUIET_BACKEND_RESOLVED"


def test_no_forbidden_authority_flags_or_imports(tmp_path):
    payload = _build(tmp_path)

    for key, value in payload["no_authority_flags"].items():
        if key in {"read_model_only", "metadata_only", "contract_only", "package_preview_only"}:
            assert value is True
        else:
            assert value is False
    tree = ast.parse(Path("operator_threshold_map_contract.py").read_text(encoding="utf-8"))
    imported_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert "subprocess" not in imported_modules
    assert "requests" not in imported_modules
    assert "httpx" not in imported_modules
    assert "webbrowser" not in imported_modules


def test_export_script_writes_json_and_operator_outputs(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    export_root = repo / "generated" / "read_models"

    exit_code = export_main([
        "--repo-root",
        repo.as_posix(),
        "--export-root",
        export_root.as_posix(),
        "--format",
        "summary",
    ])
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["schema_version"] == contract.SCHEMA_VERSION
    assert summary["lane_count"] == 17
    assert (export_root / "operator_threshold_map_contract.json").is_file()
    assert (export_root / "operator_threshold_map_contract_OPERATOR.md").is_file()
    payload = json.loads((export_root / "operator_threshold_map_contract.json").read_text(encoding="utf-8"))
    assert payload["read_model_id"] == "operator_threshold_map_contract"
    operator = (export_root / "operator_threshold_map_contract_OPERATOR.md").read_text(encoding="utf-8")
    assert "Lane Destiny / Helm-To-World Transition" in operator
    expected = canonical_generated_read_model_expected_files(source_root=export_root, repo_root=repo)
    assert "operator_threshold_map_contract.json" in expected
    assert "operator_threshold_map_contract_OPERATOR.md" in expected
