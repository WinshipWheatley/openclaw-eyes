import json
import re
from pathlib import Path

import entry_agnostic_workflow_block_chain_routing_contract as contract
from scripts.export_entry_agnostic_workflow_block_chain_routing_contract import (
    main as export_main,
)


FIXED_NOW = "2026-05-24T15:00:00+00:00"


def _build() -> dict:
    return contract.build_entry_agnostic_workflow_block_chain_routing_contract(
        generated_at=FIXED_NOW
    )


def _event(payload: dict, entry_id: str) -> dict:
    return payload["entry_events_by_id"][entry_id]


def _normalization(payload: dict, normalization_id: str) -> dict:
    return payload["intent_normalizations_by_id"][normalization_id]


def _proposal(payload: dict, proposal_id: str) -> dict:
    return payload["block_chain_proposals_by_id"][proposal_id]


def _block(payload: dict, block_id: str) -> dict:
    return payload["block_proposals_by_id"][block_id]


def _route(payload: dict, route_id: str) -> dict:
    return payload["routing_decisions_by_id"][route_id]


def _compat(payload: dict, proposal_id: str) -> dict:
    return payload["surface_compatibilities_by_id"][f"{proposal_id}_surface_compatibility"]


def _crew(payload: dict, deployment_id: str) -> dict:
    return payload["crew_deployment_proposals_by_id"][deployment_id]


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["doctrine"]["entry_point_is_metadata_not_ownership"] is True
    assert first["doctrine"]["surfaces_do_not_own_canonical_state"] is True
    assert first["doctrine"]["agents_do_not_own_canonical_state"] is True
    assert first["doctrine"]["all_origins_normalize_to_same_shape"] is True
    assert "entry event -> intent normalization" in first["doctrine"]["high_level_flow"]


def test_models_and_required_fields_exist():
    payload = _build()

    assert payload["machine_proof"]["entry_event_model_present"] is True
    assert payload["machine_proof"]["intent_normalization_model_present"] is True
    assert payload["machine_proof"]["block_chain_proposal_model_present"] is True
    assert payload["machine_proof"]["block_proposal_model_present"] is True
    assert payload["machine_proof"]["routing_decision_model_present"] is True
    assert payload["machine_proof"]["surface_compatibility_model_present"] is True
    assert payload["machine_proof"]["crew_deployment_proposal_model_present"] is True
    assert payload["entry_event_schema"]["required_fields"] == list(
        contract.REQUIRED_ENTRY_EVENT_FIELDS
    )
    assert payload["intent_normalization_schema"]["required_fields"] == list(
        contract.REQUIRED_INTENT_NORMALIZATION_FIELDS
    )
    assert payload["block_chain_proposal_schema"]["required_fields"] == list(
        contract.REQUIRED_CHAIN_PROPOSAL_FIELDS
    )
    assert payload["block_proposal_schema"]["required_fields"] == list(
        contract.REQUIRED_BLOCK_PROPOSAL_FIELDS
    )
    assert payload["routing_decision_schema"]["required_fields"] == list(
        contract.REQUIRED_ROUTING_DECISION_FIELDS
    )
    assert payload["surface_compatibility_schema"]["required_fields"] == list(
        contract.REQUIRED_SURFACE_COMPATIBILITY_FIELDS
    )
    assert payload["crew_deployment_schema"]["required_fields"] == list(
        contract.REQUIRED_CREW_DEPLOYMENT_FIELDS
    )
    assert set(payload["origin_surfaces"]) == set(contract.ORIGIN_SURFACES)
    assert set(payload["intent_types"]) == set(contract.INTENT_TYPES)
    assert set(payload["block_types"]) == set(contract.BLOCK_TYPES)
    assert set(payload["block_states"]) == set(contract.BLOCK_STATES)
    assert set(payload["route_destinations"]) == set(contract.ROUTE_DESTINATIONS)


def test_telegram_cassandra_invoice_example_routes_to_finance_world_without_send_authority():
    payload = _build()
    event = _event(payload, "telegram_cassandra_capital_hilton_invoice_entry")
    normalization = _normalization(
        payload, "telegram_cassandra_capital_hilton_invoice_normalization"
    )
    proposal = _proposal(payload, "telegram_cassandra_capital_hilton_invoice_chain_proposal")
    route = _route(payload, "telegram_cassandra_capital_hilton_invoice_route")
    compatibility = _compat(payload, proposal["proposal_id"])

    assert payload["machine_proof"]["telegram_cassandra_invoice_example_present"] is True
    assert event["origin_surface"] == "TELEGRAM"
    assert event["origin_actor"] == "Winship via Cassandra"
    assert event["source_message_or_signal_summary"] == (
        "Send Capital Hilton an invoice for this week's and last week's job."
    )
    assert normalization["normalized_intent_type"] == "FINANCE_INVOICE_REQUEST"
    assert normalization["target_world_candidate"] == "Finance"
    assert normalization["needs_operator_clarification"] is True
    assert normalization["needs_agent_compiler"] is True
    assert proposal["proposed_world"] == "Finance"
    assert proposal["proposed_lane"] == "Capital Hilton"
    assert "performance_dates" in proposal["operator_needed_blocks"]
    assert "rate_if_receipt_ref_exists" in proposal["system_fillable_blocks"]
    assert "po_proof" in proposal["proposed_blocks"]
    assert "invoice_packet" in proposal["future_gated_blocks"]
    assert "approval_send" in proposal["locked_blocks"]
    assert route["route_destination"] == "WORLD_WORK_SURFACE"
    assert route["world_destination"] == "Finance World / Capital Hilton"
    assert route["should_show_on_helm"] is True
    assert route["should_open_world"] is True
    assert compatibility["canonical_session_required"] is True
    assert "Telegram" in compatibility["compatible_surfaces"]
    assert payload["examples"]["telegram_cassandra_invoice"]["send_authority"] is False


def test_capital_hilton_blocks_distinguish_visible_hidden_future_gated_and_below_deck():
    payload = _build()
    client = _block(payload, "capital_hilton_client_lane_block")
    dates = _block(payload, "capital_hilton_performance_dates_block")
    po = _block(payload, "capital_hilton_po_proof_block")
    packet = _block(payload, "capital_hilton_invoice_packet_block")
    approval = _block(payload, "capital_hilton_approval_send_block")

    assert client["block_state"] == "SYSTEM_FILLED"
    assert client["visible_by_default"] is False
    assert dates["block_state"] == "NEEDS_OPERATOR"
    assert dates["visible_by_default"] is True
    assert dates["editable_by_operator"] is True
    assert dates["guided_capture_candidate"] is True
    assert po["block_type"] == "PROOF_REQUIREMENT"
    assert po["discovery_required"] is True
    assert po["automation_candidate"] is True
    assert packet["block_state"] == "FUTURE_GATED"
    assert packet["visible_by_default"] is False
    assert approval["block_type"] == "EXECUTION_GATE"
    assert approval["block_state"] == "FUTURE_GATED"
    assert payload["block_proposal_schema"]["visible_blocks_are_work_relevant"] is True
    assert payload["machine_proof"]["visible_and_hidden_blocks_represented"] is True


def test_mission_control_draft_uses_same_workflow_shape_without_mac_ownership():
    payload = _build()
    event = _event(payload, "mission_control_capital_hilton_performance_dates_entry")
    proposal = _proposal(payload, "mission_control_capital_hilton_draft_chain_proposal")
    route = _route(payload, "mission_control_capital_hilton_draft_route")

    assert payload["machine_proof"]["mission_control_draft_example_present"] is True
    assert event["origin_surface"] == "MISSION_CONTROL"
    assert proposal["proposed_workflow_session_ref"] == "capital_hilton_invoice_workflow_session"
    assert proposal["proposed_world"] == "Finance"
    assert "performance_dates_capture_choice" in proposal["operator_needed_blocks"]
    assert route["world_destination"] == "Finance World / Capital Hilton"
    assert route["should_open_world"] is True
    assert route["should_show_on_helm"] is False
    assert payload["examples"]["mission_control_draft"]["same_workflow_session_shape"] is True
    assert payload["examples"]["mission_control_draft"]["mac_only_ownership"] is False


def test_chief_check_engine_routes_to_shipyard_with_below_deck_refs_and_no_repair_execution():
    payload = _build()
    normalization = _normalization(payload, "chief_check_engine_normalization")
    proposal = _proposal(payload, "chief_check_engine_chain_proposal")
    route = _route(payload, "chief_check_engine_route")
    crew = _crew(payload, "chief_check_engine_crew_deployment")

    assert payload["machine_proof"]["chief_check_engine_example_present"] is True
    assert normalization["normalized_intent_type"] == "CHECK_ENGINE_REQUEST"
    assert normalization["target_world_candidate"] == "Shipyard"
    assert proposal["proposed_world"] == "Shipyard"
    assert "test_refs" in proposal["below_deck_blocks"]
    assert "repair_execution" in proposal["future_gated_blocks"]
    assert route["route_destination"] == "SHIPYARD_WORK_SURFACE"
    assert route["should_route_to_shipyard"] is True
    assert route["should_show_on_helm"] is False
    assert "Chief" in crew["recommended_crew"]
    assert "chief_diagnostic_packet_candidate" in crew["crew_packet_candidates"]
    assert payload["examples"]["chief_check_engine"]["repair_execution"] is False


def test_new_client_recap_workflow_proposes_blocks_without_activation():
    payload = _build()
    normalization = _normalization(payload, "new_client_recap_workflow_normalization")
    proposal = _proposal(payload, "new_client_recap_workflow_chain_proposal")
    route = _route(payload, "new_client_recap_workflow_route")
    block = _block(payload, "client_recap_source_materials_block")

    assert payload["machine_proof"]["new_client_recap_workflow_example_present"] is True
    assert normalization["normalized_intent_type"] == "NEW_WORKFLOW_REQUEST"
    assert "source_materials" in proposal["operator_needed_blocks"]
    assert "cadence" in proposal["system_fillable_blocks"]
    assert "activation_gate" in proposal["future_gated_blocks"]
    assert proposal["ready_to_activate_as_draft"] is True
    assert block["block_state"] == "NEEDS_OPERATOR"
    assert block["guided_capture_candidate"] is True
    assert route["world_destination"] == "Client Delivery World"
    assert payload["examples"]["new_client_recap_workflow"]["activation_execution"] is False


def test_file_source_card_discovery_routes_to_build_cue_without_auto_build():
    payload = _build()
    event = _event(payload, "source_card_build_cue_discovery_entry")
    normalization = _normalization(payload, "source_card_build_cue_normalization")
    proposal = _proposal(payload, "source_card_build_cue_chain_proposal")
    route = _route(payload, "source_card_build_cue_route")
    block = _block(payload, "source_card_build_cue_readiness_block")
    crew = _crew(payload, "source_card_build_cue_crew_deployment")

    assert payload["machine_proof"]["file_source_card_discovery_example_present"] is True
    assert event["origin_surface"] == "FILE_OR_SOURCE_CARD_DISCOVERY"
    assert event["operator_visible"] is False
    assert normalization["target_lane_candidate"] == "Work Terrain / Build Cue"
    assert proposal["proposed_lane"] == "Work Terrain / Build Cue"
    assert proposal["ready_to_activate_as_draft"] is False
    assert "build_gate" in proposal["future_gated_blocks"]
    assert route["route_destination"] == "BELOW_DECK_DETAIL"
    assert route["should_stay_below_deck"] is True
    assert route["should_show_on_helm"] is False
    assert block["block_state"] == "BELOW_DECK_ONLY"
    assert block["automation_candidate"] is True
    assert "Hermes" in crew["recommended_crew"]
    assert payload["examples"]["file_source_card_discovery"]["auto_build"] is False


def test_entry_point_and_surfaces_do_not_own_state_and_split_brain_is_prevented():
    payload = _build()

    assert payload["entry_event_schema"]["entry_event_owns_workflow_state"] is False
    assert payload["entry_event_schema"]["entry_event_executes_action"] is False
    assert payload["surface_compatibility_schema"]["mission_control_and_telegram_are_surfaces_not_owners"] is True
    assert payload["surface_compatibility_schema"]["split_brain_prevention_required"] is True
    assert payload["machine_proof"]["entry_point_does_not_own_state"] is True
    assert payload["machine_proof"]["mission_control_and_telegram_surfaces_not_owners"] is True
    assert payload["machine_proof"]["split_brain_prevention_represented"] is True
    for compatibility in payload["surface_compatibilities"]:
        assert compatibility["canonical_session_required"] is True
        assert compatibility["local_state_allowed"] == "draft_preview_only_until_captured"
        assert "same proposed/canonical workflow_session_ref" in compatibility[
            "split_brain_prevention_policy"
        ]


def test_helm_world_shipyard_below_deck_routing_policy_is_represented():
    payload = _build()

    assert payload["routing_decision_schema"]["helm_routes_worlds_do_work"] is True
    assert payload["routing_decision_schema"]["helm_is_not_workflow_editor"] is True
    assert payload["routing_decision_schema"]["proof_debug_source_stay_below_deck_by_default"] is True
    assert payload["machine_proof"]["helm_routes_worlds_do_work"] is True
    assert payload["starship_operating_model_alignment"]["helm_routes_but_does_not_own"] is True
    assert payload["starship_operating_model_alignment"]["worlds_do_domain_work"] is True
    assert payload["starship_operating_model_alignment"]["shipyard_handles_build_repair"] is True
    assert payload["starship_operating_model_alignment"]["engineering_stays_below_deck"] is True
    destinations = {route["route_destination"] for route in payload["routing_decisions"]}
    assert "WORLD_WORK_SURFACE" in destinations
    assert "SHIPYARD_WORK_SURFACE" in destinations
    assert "BELOW_DECK_DETAIL" in destinations


def test_crew_deployment_is_proposal_only_and_not_activation():
    payload = _build()

    assert payload["crew_deployment_schema"]["crew_deployment_is_proposal_only"] is True
    assert payload["crew_deployment_schema"]["agents_receive_packets_only_when_needed"] is True
    assert payload["crew_deployment_schema"]["crew_activation_allowed_now"] is False
    for deployment in payload["crew_deployment_proposals"]:
        assert set(contract.REQUIRED_CREW_DEPLOYMENT_FIELDS) <= set(deployment)
        assert deployment["next_safe_move"]


def test_relationships_to_existing_contracts_are_represented():
    payload = _build()
    refs = payload["relationship_to_existing_contracts"]

    for key in [
        "workflow_block_intent_live_draft_contract",
        "bridge_routing_operator_attention_contract",
        "agent_conversation_handoff_step_packet_contract",
        "agent_execution_packet_compiler_contract",
        "operator_question_assist_scope_expansion_contract",
        "workflow_session_channel_projection_approval_bus_contract",
        "work_terrain_surface_map_build_cue_scout",
        "work_terrain_build_cue_reconciliation_queue",
    ]:
        assert key in refs
        assert refs[key]["source_ref"].startswith("generated/read_models/")
    assert "entry-to-workflow proposal/routing" not in refs[
        "workflow_block_intent_live_draft_contract"
    ]["relationship"]
    assert "canonical workflow session prevents channel split-brain" in refs[
        "workflow_session_channel_projection_approval_bus_contract"
    ]["relationship"]


def test_all_authority_flags_false_and_sensitive_access_blocked():
    payload = _build()
    boundary = payload["authority_boundary"]

    for key, value in contract.AUTHORITY_BOUNDARY.items():
        assert value is False
        assert boundary[key] is False
    assert boundary["all_authority_flags_false"] is True
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    for proposal in payload["block_chain_proposals"]:
        for key in contract.AUTHORITY_BOUNDARY:
            assert proposal["authority_boundary"][key] is False
    for block in payload["block_proposals"]:
        for key in contract.AUTHORITY_BOUNDARY:
            assert block["authority_boundary"][key] is False
    for key in [
        "workflow_activation_allowed",
        "workflow_session_write_allowed",
        "block_chain_write_allowed",
        "crew_activation_allowed",
        "agent_activation_allowed",
        "packet_execution_allowed",
        "model_call_allowed",
        "tool_execution_allowed",
        "mcp_execution_allowed",
        "script_execution_allowed",
        "hook_execution_allowed",
        "receipt_write_allowed",
        "state_write_allowed",
        "invoice_generation_allowed",
        "email_send_allowed",
        "telegram_send_allowed",
        "browser_automation_allowed",
        "coupa_access_allowed",
        "credential_handling_allowed",
        "queue_execution_allowed",
        "runtime_dispatch_allowed",
        "file_write_allowed",
        "raw_body_ingestion_allowed",
    ]:
        assert boundary[key] is False


def test_no_credentials_or_raw_private_bodies():
    payload = _build()
    serialized = contract.stable_json(payload)

    assert payload["machine_proof"]["credential_or_secret_included"] is False
    assert payload["machine_proof"]["raw_private_body_included"] is False
    secret_like = re.compile(
        r"(AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|xox[baprs]-|AIza[0-9A-Za-z_-]{35}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,})"
    )
    assert not secret_like.search(serialized)


def test_exporter_writes_json_and_operator_markdown(tmp_path, capsys):
    rc = export_main(["--export-root", tmp_path.as_posix(), "--format", "summary"])
    captured = capsys.readouterr()
    summary = json.loads(captured.out)

    assert rc == 0
    assert summary["schema_version"] == contract.SCHEMA_VERSION
    assert summary["entry_event_count"] == 5
    assert summary["normalization_count"] == 5
    assert summary["proposal_count"] == 5
    assert summary["block_proposal_count"] >= 10
    assert summary["routing_decision_count"] == 5
    assert summary["compatibility_count"] == 5
    assert summary["crew_deployment_count"] == 5
    assert summary["action_authority_granted"] is False

    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    payload = json.loads(json_path.read_text())
    operator_text = operator_path.read_text()
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert "Entry point is metadata, not ownership." in operator_text
    assert "Helm routes. Worlds do work." in operator_text
    assert "No workflow is activated yet" in operator_text
    assert "prevents split-brain and app-only workflows" in operator_text
