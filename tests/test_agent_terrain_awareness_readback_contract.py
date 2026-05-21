import json
from pathlib import Path

import agent_terrain_awareness_readback_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_agent_terrain_awareness_readback_contract import main as export_main


FIXED_NOW = "2026-05-22T05:30:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    fixtures = {
        "operator_awareness_agent_package_spine.json": {
            "schema_version": "operator_awareness_agent_package_spine_v0",
            "read_model_id": "operator_awareness_agent_package_spine",
        },
        "operator_nested_lane_mission_package_spine.json": {
            "schema_version": "operator_nested_lane_mission_package_spine_v0",
            "read_model_id": "operator_nested_lane_mission_package_spine",
        },
        "agent_platform_alignment.json": {
            "schema_version": "agent_platform_alignment_v0",
            "read_model_id": "agent_platform_alignment",
        },
        "agent_identity_actor_router_contract.json": {
            "schema_version": "agent_identity_actor_router_contract_v0",
            "read_model_id": "agent_identity_actor_router_contract",
        },
        "model_selection_policy_contract.json": {
            "schema_version": "model_selection_policy_contract_v0",
            "read_model_id": "model_selection_policy_contract",
        },
        "agent_package_preview_contract.json": {
            "schema_version": "agent_package_preview_contract_v0",
            "read_model_id": "agent_package_preview_contract",
        },
        "agent_memory_scope_contract.json": {
            "schema_version": "agent_memory_scope_contract_v0",
            "read_model_id": "agent_memory_scope_contract",
        },
        "tool_protocol_adapter_registry_contract.json": {
            "schema_version": "tool_protocol_adapter_registry_contract_v0",
            "read_model_id": "tool_protocol_adapter_registry_contract",
        },
        "memory_candidate_receipt_contract.json": {
            "schema_version": "memory_candidate_receipt_contract_v0",
            "read_model_id": "memory_candidate_receipt_contract",
        },
        "model_selection_receipt_contract.json": {
            "schema_version": "model_selection_receipt_contract_v0",
            "read_model_id": "model_selection_receipt_contract",
        },
        "package_compiler_contract.json": {
            "schema_version": "package_compiler_contract_v0",
            "read_model_id": "package_compiler_contract",
        },
        "operator_threshold_map_contract.json": {
            "schema_version": "operator_threshold_map_contract_v0",
            "read_model_id": "operator_threshold_map_contract",
        },
        "guardian_protected_access_gate_spec.json": {
            "schema_version": "guardian_protected_access_gate_spec_v0",
            "read_model_id": "guardian_protected_access_gate_spec",
        },
        "cassandra_email_calendar_delta_detangle.json": {
            "schema_version": "cassandra_email_calendar_delta_detangle_v0",
            "read_model_id": "cassandra_email_calendar_delta_detangle",
        },
        "niles_album_metadata_intake_packet.json": {
            "schema_version": "niles_album_metadata_intake_packet_v0",
            "read_model_id": "niles_album_metadata_intake_packet",
        },
        "struna_obscura_project_capsule.json": {
            "schema_version": "struna_obscura_project_capsule_v0",
            "read_model_id": "struna_obscura_project_capsule",
        },
        "capital_hilton_actionable_review_packet.json": {
            "schema_version": "capital_hilton_actionable_review_packet_v0",
            "read_model_id": "capital_hilton_actionable_review_packet",
        },
        "capital_hilton_external_artifact_proof_capture.json": {
            "schema_version": "capital_hilton_external_artifact_proof_capture_v0",
            "read_model_id": "capital_hilton_external_artifact_proof_capture",
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return contract.build_agent_terrain_awareness_readback_contract(repo_root=tmp_path, generated_at=FIXED_NOW)


def _lanes(payload: dict) -> dict:
    return {item["lane_id"]: item for item in payload["terrain_inventory"]}


def _cards(payload: dict) -> dict:
    return {item["agent_id"]: item for item in payload["agent_dossier_cards"]}


def test_contract_is_deterministic_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "agent_terrain_awareness_readback_contract"
    assert first["contract_status"] == "deterministic_terrain_awareness_readback_metadata_only"
    assert first["runtime_authority"] is False
    assert first["model_call_authority"] is False
    assert first["actor_agent_activation_authority"] is False
    assert first["tool_execution_authority"] is False
    assert first["planner_builder_execution_enabled"] is False
    assert first["queue_autonomy_execution_enabled"] is False
    assert first["repo_b_mutation_enabled"] is False
    assert first["repo_b_body_inspection_enabled"] is False
    assert first["operator_final_authority"] is True
    assert first["machine_proof"]["cassandra_reference_image_stored"] is False
    assert first["machine_proof"]["cassandra_reference_image_embedded"] is False


def test_all_required_lanes_are_inventoried_with_matrix_rows(tmp_path):
    payload = _build(tmp_path)
    lanes = _lanes(payload)
    matrix = {row["lane_id"]: row for row in payload["readback_matrix"]["rows"]}

    assert set(lanes) == set(contract.REQUIRED_LANE_IDS)
    assert set(matrix) == set(contract.REQUIRED_LANE_IDS)
    assert payload["readback_matrix"]["columns"] == list(contract.MATRIX_COLUMNS)
    assert payload["machine_proof"]["missing_required_lane_ids"] == []
    assert payload["machine_proof"]["lane_count"] == len(contract.REQUIRED_LANE_IDS)
    for lane in lanes.values():
        assert lane["known"]
        assert "known_unknown" in lane
        assert "not_discovered" in lane
        assert lane["safe_next_detour"]
        assert lane["lane_destiny"]["resolution_route"] in contract.LANE_DESTINY_ROUTES
        assert lane["what_makes_quiet"]
        assert 3 <= len(lane["recommended_operator_questions"]) <= 7


def test_operator_questions_become_memory_candidates_not_proof(tmp_path):
    payload = _build(tmp_path)
    questions = payload["operator_memory_comparison_questions"]

    assert payload["machine_proof"]["operator_question_count"] == len(questions)
    assert len(questions) >= len(contract.REQUIRED_LANE_IDS) * 3
    classifications = {question["classification"] for question in questions}
    assert classifications <= set(contract.OPERATOR_QUESTION_TYPES)
    assert "memory_only_clarification" in classifications
    assert "proof_needed" in classifications
    assert "security_gate_needed" in classifications
    assert all(question["operator_answer_becomes"] == "memory_candidate_not_machine_proof" for question in questions)
    assert all(question["execution_authority_created"] is False for question in questions)


def test_agent_dossier_cards_include_required_fields_and_preview_only_authority(tmp_path):
    payload = _build(tmp_path)
    cards = _cards(payload)

    assert "agent_dossier_cards" in payload
    assert len(cards) == 12
    assert payload["machine_proof"]["agent_dossier_card_count"] == 12
    assert payload["agent_dossier_card_model"]["required_fields"] == list(contract.DOSSIER_REQUIRED_FIELDS)
    assert set(payload["agent_dossier_card_model"]["card_types"]) == set(contract.DOSSIER_CARD_TYPES)
    assert set(payload["agent_dossier_card_model"]["portrait_asset_statuses"]) == set(contract.PORTRAIT_ASSET_STATUSES)
    assert payload["agent_dossier_card_model"]["asset_policy"]["raw_images_stored_in_repo_a"] is False
    assert payload["agent_dossier_card_model"]["asset_policy"]["image_embedding_allowed"] is False
    for card in cards.values():
        for field in contract.DOSSIER_REQUIRED_FIELDS:
            assert field in card
        assert card["card_type"] in contract.DOSSIER_CARD_TYPES
        assert card["portrait_asset_status"] in contract.PORTRAIT_ASSET_STATUSES
        assert card["current_interaction_authority"] == "read_only_capture_only_preview_only"
        assert card["live_activation_allowed"] is False
        assert card["raw_private_context_allowed"] is False
        assert card["portrait_raw_image_stored"] is False


def test_cassandra_dossier_card_captures_visual_archetype_and_blocked_account_actions(tmp_path):
    cassandra = _cards(_build(tmp_path))["cassandra"]

    assert cassandra["card_type"] == "agent_persona"
    assert cassandra["agent_class"] == "finance_comms_cassandra"
    assert "classy cyberpunk executive analyst" in cassandra["visual_archetype"]
    assert cassandra["portrait_asset_status"] == "OPERATOR_PROVIDED_REFERENCE"
    assert cassandra["portrait_asset_ref"]["raw_image_body_stored"] is False
    assert cassandra["portrait_asset_ref"]["image_embedded"] is False
    assert "Capital Hilton" in " ".join(cassandra["relationship_to_other_agents"])
    for blocked in ["Coupa access", "Gmail/calendar access", "OAuth/browser/account flows", "send/submit/approval", "credential handling"]:
        assert blocked in cassandra["current_blocked_actions"]
    assert "Finance" in cassandra["world_affinity"]
    assert "Communications" in cassandra["world_affinity"]


def test_agent_persona_dossier_cards_cover_chief_guardian_hermes_niles_struna(tmp_path):
    cards = _cards(_build(tmp_path))

    chief = cards["chief"]
    assert chief["agent_class"] == "diagnostic_chief"
    assert "system health" in chief["strengths"]
    assert "can verify others but cannot self-authorize success" in chief["relationship_to_other_agents"]
    assert "repair/remount/cleanup" in chief["current_blocked_actions"]

    guardian = cards["guardian"]
    assert guardian["agent_class"] == "protected_access_guardian"
    assert "redaction" in guardian["strengths"]
    assert "self-authorization" in guardian["current_blocked_actions"]
    assert "recommend allow/block/redact/quarantine/revoke" in guardian["current_allowed_actions"]

    hermes = cards["hermes"]
    assert hermes["agent_class"] == "architecture_hermes"
    assert "system framing" in hermes["strengths"]
    assert hermes["known_unknowns"]

    niles = cards["niles"]
    assert niles["agent_class"] == "creative_niles"
    assert "Music / Art" in niles["world_affinity"]
    assert "broad private archive ingestion" in niles["current_blocked_actions"]

    struna = cards["struna"]
    assert struna["card_type"] == "project_lane"
    assert struna["agent_class"] == "music_project_struna"
    assert "belongs under Niles" in struna["relationship_to_other_agents"]


def test_system_loop_and_registry_dossier_cards_are_future_gated(tmp_path):
    cards = _cards(_build(tmp_path))

    agentic = cards["agentic_loop"]
    assert agentic["card_type"] == "system_loop_component"
    assert "parser, queue, planner, builder, orchestrator" in agentic["tagline"].lower()
    assert "queue/autonomy execution" in agentic["current_blocked_actions"]
    assert "Chief harness receipt" in agentic["required_receipts"]

    cue = cards["cue_parser_brain_dump_parser"]
    assert cue["card_type"] == "system_loop_component"
    assert any("now/later/holding-cell" in item for item in cue["strengths"])
    assert "raw private note scans" in cue["current_blocked_actions"]

    repo_b_loop = cards["repo_b_planner_builder_orchestrator"]
    assert repo_b_loop["card_type"] == "system_loop_component"
    assert "No broad Repo B body inspection" in repo_b_loop["permissions_summary"]
    assert "Repo B execution" in repo_b_loop["current_blocked_actions"]

    package_compiler = cards["package_compiler"]
    assert package_compiler["card_type"] == "registry_component"
    assert package_compiler["agent_class"] == "package_compiler_component"
    assert "Mission Impossible" in package_compiler["visual_archetype"]
    assert "live package dispatch" in package_compiler["current_blocked_actions"]

    model_router = cards["model_router"]
    assert model_router["agent_class"] == "model_router_component"
    assert "blocked_no_model" in model_router["model_selection_summary"]
    assert "hidden routing" in model_router["current_blocked_actions"]

    tool_registry = cards["tool_plugin_registry"]
    assert tool_registry["agent_class"] == "tool_registry_component"
    assert "No live tool execution" in tool_registry["permissions_summary"]
    assert "browser/OAuth/account flows" in tool_registry["current_blocked_actions"]


def test_agentic_loop_and_repo_b_fail_closed_without_execution(tmp_path):
    payload = _build(tmp_path)
    lanes = _lanes(payload)
    focus = payload["agentic_loop_focus"]

    for lane_id in [
        "agentic_loop",
        "cue_parser_brain_dump_parser",
        "planner_builder_orchestrator_loop",
        "repo_b_leftovers",
    ]:
        lane = lanes[lane_id]
        assert lane["operator_reported_only"] is True
        assert lane["machine_proven"] is False
        assert lane["live_execution_authority"] is False
        assert lane["confidence_state"] in {"LOW_TRUST", "UNKNOWN_FAIL_CLOSED"}
    assert focus["operator_reported_architecture_candidate"] is True
    assert focus["machine_proven_current_runtime"] is False
    assert focus["current_execution_authority"] is False
    assert "Repo B execution" in focus["blocked"]
    assert "planner/builder loop execution" in focus["blocked"]
    assert lanes["repo_b_leftovers"]["current_authority_boundary"].startswith("Repo B is reference-only")


def test_chief_focus_distinguishes_character_package_harness_and_live_authority(tmp_path):
    focus = _build(tmp_path)["agent_persona_focus"]

    distinctions = focus["distinctions"]
    assert distinctions["chief_character"].startswith("persona")
    assert distinctions["chief_package"].startswith("deterministic")
    assert "unclassified" in distinctions["chief_test_harness"]
    assert distinctions["chief_live_execution_authority"] == "absent and blocked"
    assert focus["chief"]["package_preview_available"] is True
    assert focus["chief_test_harness"]["package_preview_available"] is False
    assert "model calls" in focus["chief"]["blocked_authorities"]


def test_agent_persona_sections_cover_hermes_cassandra_guardian_niles_struna(tmp_path):
    lanes = _lanes(_build(tmp_path))

    assert lanes["hermes"]["readiness_state"] == "NEEDS_CONTEXT"
    assert lanes["hermes"]["safe_next_detour"] == "Hermes Status Memory/Proof Review"
    assert lanes["cassandra"]["target_world"] == "Finance"
    assert "Coupa access" in lanes["cassandra"]["blocked_authorities"]
    assert lanes["guardian"]["readiness_state"] == "READY_FOR_SECURITY_AUDIT"
    assert lanes["guardian"]["resolution_route"] == "PARK_WITH_PROOF"
    assert lanes["niles"]["target_world"] == "Music / Art"
    assert lanes["struna"]["target_world"] == "Music / Art"
    assert "raw creative archive scan" in lanes["struna"]["blocked_authorities"]


def test_model_tool_package_focus_preserves_blocked_runtime_defaults(tmp_path):
    payload = _build(tmp_path)
    lanes = _lanes(payload)
    focus = payload["model_tool_package_focus"]

    assert "blocked_no_model" in focus["current_live_default"]
    assert lanes["model_router"]["readiness_state"] == "SECURITY_AUDIT_REQUIRED"
    assert lanes["tool_plugin_registry"]["readiness_state"] == "SECURITY_AUDIT_REQUIRED"
    assert lanes["package_compiler"]["readiness_state"] == "READY_FOR_SECURITY_AUDIT"
    assert "live model calls" in lanes["model_router"]["blocked_authorities"]
    assert "browser/OAuth/account flows" in lanes["tool_plugin_registry"]["blocked_authorities"]
    assert "live package dispatch" in lanes["package_compiler"]["blocked_authorities"]


def test_capital_hilton_is_finance_world_preview_only(tmp_path):
    payload = _build(tmp_path)
    capital = payload["capital_hilton_focus"]

    assert capital["current_phase"] == "HELM_THRESHOLD_LANE"
    assert capital["intended_destiny"] == "MOVE_TO_WORLD_ACTION"
    assert capital["target_world"] == "Finance"
    assert capital["not_currently_executable"] is True
    assert capital["lane_destiny"]["resolution_route"] == "MOVE_TO_WORLD_ACTION"
    assert "Coupa access" in capital["no_current_authority"]
    assert "send/submit/approval" in capital["blocked_authorities"]
    assert any(item.startswith("Coupa/Excel protected metadata receipt") for item in capital["missing_machine_proof"])


def test_mission_control_guidance_avoids_card_wall_and_live_controls(tmp_path):
    payload = _build(tmp_path)
    guidance = payload["mission_control_surface_guidance"]
    dossier = payload["agent_council_dossier_summary"]

    assert "one System Awareness / Terrain Map surface" in guidance["show"]
    assert "agent/persona lanes collapsed by default" in guidance["show"]
    assert "operator memory as candidate context, not truth" in guidance["show"]
    assert "every nested lane as a card wall" in guidance["hide_or_collapse"]
    assert "live execution controls" in guidance["hide_or_collapse"]
    assert "queue/autonomy controls" in guidance["hide_or_collapse"]
    assert "fake confidence percentages" in guidance["hide_or_collapse"]
    assert dossier["cards_count"] == 12
    assert "one featured selected card" in dossier["mission_control_may_render"]
    assert "Inspect Dossier" in dossier["allowed_interactions"]
    assert "Show Package Preview" in dossier["allowed_interactions"]
    assert "live chat launch" in dossier["forbidden_interactions"]
    assert "Gmail/calendar/Coupa/Telegram controls" in dossier["forbidden_interactions"]


def test_stable_map_summary_is_deferred_to_avoid_churn(tmp_path):
    stable = _build(tmp_path)["stable_map_integration"]

    assert stable["registry_generated_as_read_model"] is True
    assert stable["summary_included_in_stable_map_bundle_now"] is False
    assert "does not reopen bridge churn" in stable["reason_not_included_now"]
    assert stable["safe_summary_to_include_next"]["contract_id"] == "agent_terrain_awareness_readback_contract"
    assert stable["safe_summary_to_include_next"]["lanes_inventoried_count"] == len(contract.REQUIRED_LANE_IDS)
    assert stable["safe_summary_to_include_next"]["agent_dossier_cards_count"] == 12
    assert "cassandra" in stable["safe_summary_to_include_next"]["featured_agents"]
    assert stable["safe_summary_to_include_next"]["next_operator_questions_count"] >= 48


def test_export_writes_json_and_operator_outputs(tmp_path):
    _fixture_repo(tmp_path)
    result = contract.export_agent_terrain_awareness_readback_contract(
        repo_root=tmp_path,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )
    json_path = Path(result.json_path)
    operator_path = Path(result.operator_path)

    assert json_path.is_file()
    assert operator_path.is_file()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["read_model_id"] == "agent_terrain_awareness_readback_contract"
    assert result.lane_count == len(contract.REQUIRED_LANE_IDS)
    assert result.operator_question_count == payload["machine_proof"]["operator_question_count"]
    assert result.dossier_card_count == payload["machine_proof"]["agent_dossier_card_count"]
    assert result.runtime_authority_added is False
    assert result.repo_b_mutation_added is False
    operator_text = operator_path.read_text(encoding="utf-8")
    assert "Agent Terrain Awareness Readback Contract v0" in operator_text
    assert "Agent Council / Dossier Summary" in operator_text


def test_script_summary_export_and_canonical_safe_file_selection(tmp_path, capsys):
    _fixture_repo(tmp_path)
    rc = export_main(["--repo-root", tmp_path.as_posix(), "--export-root", "generated/read_models", "--format", "summary"])
    captured = capsys.readouterr()
    summary = json.loads(captured.out)

    assert rc == 0
    assert summary["schema_version"] == contract.SCHEMA_VERSION
    assert summary["lane_count"] == len(contract.REQUIRED_LANE_IDS)
    assert summary["dossier_card_count"] == 12
    assert summary["runtime_authority_added"] is False
    assert summary["repo_b_mutation_added"] is False
    expected = canonical_generated_read_model_expected_files(repo_root=tmp_path)
    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected
