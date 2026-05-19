import ast
import json
from pathlib import Path

import operator_awareness_agent_package_spine as spine
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_operator_awareness_agent_package_spine import main as export_main


FIXED_NOW = "2026-05-19T04:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    fixtures = {
        "cross_repo_awareness_matrix.json": {
            "schema_version": "cross_repo_awareness_matrix_v0",
            "classification_counts": {
                "REPO_A_TRACKED": 5,
                "REPO_A_PARTIALLY_TRACKED": 1,
                "OPERATOR_MEMORY_ONLY": 1,
                "UNKNOWN_NEEDS_REVIEW": 1,
            },
            "repo_b_code_executed": False,
        },
        "capability_skill_registry_metadata_delta.json": {
            "schema_version": "capability_skill_registry_metadata_delta_v0",
            "registry_delta_status": "metadata_only_capability_skill_registry_delta",
        },
        "build_now_vs_hold_queue_posture.json": {
            "schema_version": "build_now_vs_hold_queue_posture_v0",
            "posture_scope": "visibility_routing_work_packet_posture_only",
        },
        "chief_status_rail.json": {
            "schema_version": "chief_status_rail_v0",
            "rail_status": "completed_visibility_planning_only",
        },
        "chief_role_capability_segmentation_map.json": {
            "schema_version": "chief_role_capability_segmentation_map_v0",
        },
        "protected_access_broker_concept.json": {
            "schema_version": "protected_access_broker_concept_v0",
            "live_access_blocked": True,
        },
        "protected_evidence_reference_receipt.json": {
            "schema_version": "protected_evidence_reference_receipt_v0",
            "receipt_records": [],
        },
        "guardian_protected_access_gate_spec.json": {
            "schema_version": "guardian_protected_access_gate_spec_v0",
            "current_availability_status": "protected_access_blocked_now",
        },
        "cassandra_email_calendar_delta_detangle.json": {
            "schema_version": "cassandra_email_calendar_delta_detangle_v0",
            "live_gmail_access_enabled": False,
            "live_google_calendar_access_enabled": False,
        },
        "agent_work_packets.json": {
            "schema_version": "agent_work_packets_read_model_v0",
            "packets": [],
            "execution_allowed": False,
        },
        "operator_actions.json": {
            "schema_version": "operator_actions_read_model_v0",
            "runtime_activation_allowed": False,
        },
        "intent_router.json": {
            "schema_version": "intent_router_read_model_v0",
            "runtime_authority": False,
        },
        "dropped_intents.json": {
            "schema_version": "dropped_intents_read_model_v0",
            "raw_private_scan_allowed": False,
        },
        "work_board.json": {
            "schema_version": "work_board_read_model_v0",
            "direct_execution_allowed": False,
        },
        "niles_album_review_packet.json": {
            "schema_version": "niles_album_review_packet_v0",
        },
        "niles_album_metadata_intake_packet.json": {
            "schema_version": "niles_album_metadata_intake_packet_v0",
        },
        "struna_obscura_project_capsule.json": {
            "schema_version": "struna_obscura_project_capsule_v0",
        },
        "report_bridge.json": {
            "schema_version": "report_bridge_read_model_v0",
        },
        "repo_a_known_rail_completion_map.json": {
            "schema_version": "repo_a_known_rail_completion_map_v0",
        },
        "repo_b_remaining_capability_delta_map.json": {
            "schema_version": "repo_b_remaining_capability_delta_map_v0",
            "repo_b_reference_only": True,
            "repo_b_code_executed": False,
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return spine.build_operator_awareness_agent_package_spine(repo_root=repo, generated_at=FIXED_NOW)


def _gap(payload: dict, gap_id: str) -> dict:
    return next(item for item in payload["awareness_gap_items"] if item["gap_id"] == gap_id)


def test_spine_is_deterministic_and_has_all_five_layers(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert spine.stable_json(first) == spine.stable_json(second)
    assert first["schema_version"] == spine.SCHEMA_VERSION
    assert first["spine_status"] == "deterministic_read_model_contract_only"
    assert first["machine_proof_stays_underneath"] is True
    assert first["mission_control_primary_human_layers"] == [
        "layer_1_eli5_current_truth",
        "layer_2_human_operator_detail",
    ]

    layers = first["agent_package_spine_contract_layers"]
    assert set(layers) == {
        "layer_1_eli5_current_truth",
        "layer_2_human_operator_detail",
        "layer_3_machine_proof",
        "layer_4_full_agent_package_preview",
        "layer_5_confidence_raise_confidence_path",
    }
    assert layers["layer_2_human_operator_detail"]["machine_proof_is_primary_human_layer"] is False
    assert layers["layer_3_machine_proof"]["machine_proof_is_not_main_human_layer"] is True


def test_eli5_summary_covers_operator_workflow_and_no_live_run(tmp_path):
    payload = _build(tmp_path)
    eli5 = payload["operator_eli5_summary"]

    assert "SQLite-backed records and generated read-models" in eli5["openclaw_remembers_in_sqlite_read_models"]
    assert "Winship compares" in eli5["winship_compares_memory"]
    assert "Agents/characters" in eli5["agents_interpret_domain_context"]
    assert "Actors/models" in eli5["actors_models_perform_role"]
    assert "Machine proof stays underneath" in eli5["proof_sits_underneath"]
    assert "package preview shows" in eli5["package_preview_shows_exact_context"]
    assert "confidence stays display-quiet" in eli5["confidence_quiet_when_full"]
    assert "Nothing live runs" in eli5["nothing_live_runs_from_this_contract"]


def test_awareness_gap_items_are_button_ready_and_include_current_examples(tmp_path):
    payload = _build(tmp_path)
    ids = {item["gap_id"] for item in payload["awareness_gap_items"]}

    assert payload["awareness_gap_items_are_button_ready"] is True
    assert ids >= {
        "capital_hilton_coupa_excel_proof",
        "niles_real_album_metadata",
        "hermes_status_memory_proof_review",
        "google_apple_calendar_merge_clarification",
        "agentic_loop_workflow_classification",
        "chief_test_harness_classification",
        "brain_dump_cue_parser_classification",
        "repo_b_leftovers_tag_or_block",
    }
    for item in payload["awareness_gap_items"]:
        assert item["title"]
        assert item["short_eli5_description"]
        assert item["why_it_matters"]
        assert item["future_button_ids"]
        assert item["button_ready_metadata"]["mutates_state_now"] is False
        assert "SHOW_PACKAGE_PREVIEW" in item["future_button_ids"]


def test_gap_items_distinguish_known_partly_known_known_unknown_undiscovered_and_blocked(tmp_path):
    payload = _build(tmp_path)
    capital = _gap(payload, "capital_hilton_coupa_excel_proof")
    repo_b = _gap(payload, "repo_b_leftovers_tag_or_block")
    loop = _gap(payload, "agentic_loop_workflow_classification")

    assert capital["awareness_state_breakdown"]["known"] is True
    assert capital["awareness_state_breakdown"]["partly_known"] is True
    assert capital["awareness_state_breakdown"]["known_unknown"] is True
    assert capital["awareness_state_breakdown"]["undiscovered"] is True
    assert capital["awareness_state_breakdown"]["blocked"] is True

    assert repo_b["current_awareness_state"] == "KNOWN_UNKNOWN"
    assert repo_b["awareness_state_breakdown"]["known_unknown"] is True
    assert loop["current_awareness_state"] == "DISCOVERY_OR_CLASSIFICATION_NEEDED"
    assert loop["confidence_posture"] == "UNKNOWN_FAIL_CLOSED"
    assert loop["safe_to_proceed_at_lower_confidence"] is False


def test_operator_memory_comparison_is_represented_without_treating_memory_as_truth(tmp_path):
    payload = _build(tmp_path)

    for gap_id in [
        "hermes_status_memory_proof_review",
        "google_apple_calendar_merge_clarification",
    ]:
        item = _gap(payload, gap_id)
        assert item["what_winship_may_remember"]
        assert item["operator_memory_is_treated_as_truth"] is False
        assert "memory_can_point_to_a_gap" in item["operator_memory_comparison_mode"]
        assert "MARK_NEEDS_OPERATOR_MEMORY_COMPARISON" in item["future_button_ids"]

    assert payload["output_supports_aware_of_x_not_y"]["operator_memory_items_are_discovery_needs_not_facts"] is True


def test_package_preview_exists_without_execution_or_dispatch(tmp_path):
    payload = _build(tmp_path)
    preview = payload["agent_package_spine_contract_layers"]["layer_4_full_agent_package_preview"]

    assert preview["package_preview_exists_without_executing_anything"] is True
    assert preview["package_hash_or_deterministic_placeholder"].startswith("sha256:")
    assert "capital_hilton_external_artifact_proof_capture.json" in preview["included_read_models"]
    assert "raw Gmail bodies" in preview["excluded_sensitive_surfaces"]
    assert "call any model" in preview["blocked_actions"]
    assert preview["model_call_allowed"] is False
    assert preview["agent_activation_allowed"] is False
    assert preview["tool_execution_allowed"] is False
    assert preview["runtime_authority_added"] is False
    assert "not sent or executed" in preview["copyable_reviewable_package_body_placeholder"]


def test_button_behavior_contract_is_metadata_only(tmp_path):
    payload = _build(tmp_path)
    buttons = {button["button_id"]: button for button in payload["button_behavior_contract"]["button_types"]}

    assert payload["button_behavior_contract"]["buttons_are_metadata_only"] is True
    assert payload["button_behavior_contract"]["buttons_mutate_state_now"] is False
    for button_id in [
        "INSPECT_LARGER_DESCRIPTION",
        "SHOW_PACKAGE_PREVIEW",
        "WHY_NOT_FULL_CONFIDENCE",
        "DETOUR_TO_RAISE_CONFIDENCE",
        "PROCEED_ANYWAY_IF_SAFE",
        "KEEP_PARKED",
        "MARK_NEEDS_OPERATOR_MEMORY_COMPARISON",
        "START_DISCOVERY_CLASSIFICATION",
    ]:
        assert button_id in buttons
        assert buttons[button_id]["interaction_mode"] in spine.BUTTON_INTERACTION_MODES
        assert "must not" in buttons[button_id]["what_it_must_not_do"].lower()


def test_agent_actor_routing_is_metadata_only_and_unknown_actor_fails_closed(tmp_path):
    payload = _build(tmp_path)
    routing = payload["agent_actor_routing_metadata"]
    domains = {item["domain"]: item["likely_agents"] for item in routing["domain_to_likely_agents"]}

    assert routing["metadata_only"] is True
    assert domains["music"] == ["Niles"]
    assert domains["comms/finance"] == ["Cassandra", "Guardian"]
    assert domains["safety/security"] == ["Guardian"]
    assert domains["coordination/work queue"] == ["Chief"]
    assert domains["big-picture/advisory"] == ["Hermes"]
    assert routing["unavailable_or_unknown_actor_fails_closed"] is True
    assert routing["no_real_api_key_credential_endpoint_or_execution_path"] is True
    assert all(mode["live_chat_created_now"] is False for mode in routing["possible_chat_modes"])


def test_confidence_repair_path_exposes_missing_inputs_and_display_quiet_full_trust_policy(tmp_path):
    payload = _build(tmp_path)
    repair = payload["confidence_repair_behavior"]
    layer_5 = payload["agent_package_spine_contract_layers"]["layer_5_confidence_raise_confidence_path"]

    assert repair["full_trust_display_policy"]["posture"] == "FULL_TRUST_DISPLAY_QUIET"
    assert repair["full_trust_display_policy"]["confidence_should_be_visible_in_helm"] is False
    assert repair["below_full_trust_policy"]["confidence_should_be_visible_in_helm"] is True
    assert repair["below_full_trust_policy"]["must_surface_why_not_full"] is True
    assert repair["default_unknown_or_missing_context"]["confidence_posture"] == "UNKNOWN_FAIL_CLOSED"
    assert repair["default_unknown_or_missing_context"]["fail_closed"] is True
    assert layer_5["missing_memory_context_proof_read_models"]
    assert layer_5["fail_closed_for_unknown_or_live_authority"] is True

    repair_lanes = {item["suggested_detour_lane"] for item in repair["repair_paths"]}
    assert {
        "Hermes Status Memory/Proof Review",
        "Calendar Context Discovery / Memory Comparison",
        "Capital Hilton Protected Proof Metadata Population",
        "Repo B Leftover Classification Packet",
        "Cassandra Draft Identity Reference Rail",
        "Agentic Loop Workflow Classification",
        "Chief Test Harness Capability Classification",
        "Cue Parser Intake Classification",
    } <= repair_lanes
    assert all(item["bounded"] is True and item["non_live"] is True for item in repair["repair_paths"])


def test_detour_workspace_types_are_represented_and_non_live(tmp_path):
    payload = _build(tmp_path)
    layer_5 = payload["agent_package_spine_contract_layers"]["layer_5_confidence_raise_confidence_path"]

    assert tuple(payload["detour_workspace_types"]) == spine.DETOUR_WORKSPACE_TYPES
    for workspace_type in spine.DETOUR_WORKSPACE_TYPES:
        assert workspace_type in layer_5["detour_workspace_type_policy"]

    for item in payload["awareness_gap_items"]:
        detour = item["detour_to_raise_confidence"]
        assert detour["workspace_type"] in spine.DETOUR_WORKSPACE_TYPES
        assert detour["bounded"] is True
        assert detour["non_live"] is True
        assert detour["preserves_blocked_authorities"] is True


def test_current_awareness_examples_include_cross_repo_chief_protected_and_cassandra(tmp_path):
    payload = _build(tmp_path)
    examples = payload["current_awareness_examples_from_existing_read_models"]

    assert set(examples["cross_repo_awareness"]["aware_of"]) >= {"Capital Hilton", "Cassandra", "Chief", "Guardian", "Niles/Struna"}
    assert examples["cross_repo_awareness"]["repo_b_leftovers_not_fully_classified"] == "represented_as_gap_item_not_fact"
    assert examples["chief_queue_work_board"]["execution_authority"] is False
    assert examples["protected_access"]["receipt_is_key_approval_or_execution"] is False
    assert examples["protected_access"]["guardian_gate_blocks_access_now"] is True
    assert examples["cassandra"]["gmail_calendar_telegram_live_send_blocked"] is True


def test_no_model_tool_agent_browser_oauth_credential_send_runtime_authority_is_added(tmp_path):
    payload = _build(tmp_path)

    for key, expected in spine.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["model_calls_made"] is False
    assert payload["tools_enabled"] is False
    assert payload["agents_activated"] is False
    assert payload["browser_accessed"] is False
    assert payload["oauth_or_credentials_accessed"] is False
    assert payload["gmail_calendar_coupa_accessed"] is False
    assert payload["send_or_submit_authority_added"] is False
    assert payload["runtime_authority_added"] is False


def test_export_writes_generated_json_operator_and_cli(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    result = spine.export_operator_awareness_agent_package_spine(
        repo_root=repo,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )

    assert result.schema_version == spine.SCHEMA_VERSION
    assert result.package_preview_only is True
    assert result.runtime_authority_added is False
    assert "operator_awareness_agent_package_spine.json" in canonical_generated_read_model_expected_files(
        source_root=repo / "generated/read_models",
        repo_root=repo,
    )
    assert "operator_awareness_agent_package_spine_OPERATOR.md" in canonical_generated_read_model_expected_files(
        source_root=repo / "generated/read_models",
        repo_root=repo,
    )

    assert export_main(["--repo-root", repo.as_posix(), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == spine.SCHEMA_VERSION

    assert export_main(["--repo-root", repo.as_posix(), "--format", "operator"]) == 0
    output = capsys.readouterr().out
    assert "Operator Awareness + Agent Package Spine Contract v0" in output
    assert "Machine proof stays underneath" in output
    assert "No Repo B body inspection" in output


def test_source_does_not_import_live_execution_or_account_mechanisms():
    source_files = [
        Path("operator_awareness_agent_package_spine.py"),
        Path("scripts/export_operator_awareness_agent_package_spine.py"),
    ]
    forbidden_import_roots = {
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
        "operator_action",
    }
    for path in source_files:
        source = path.read_text(encoding="utf-8")
        assert "/home/openclaw_external/openclaw-runtime" not in source
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


def test_write_calls_are_limited_to_generated_read_model_exports():
    tree = ast.parse(Path("operator_awareness_agent_package_spine.py").read_text(encoding="utf-8"))
    write_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]

    assert len(write_calls) == 2
