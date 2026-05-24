import json
import re
from pathlib import Path

import agent_conversation_handoff_step_packet_contract as contract
from scripts.export_agent_conversation_handoff_step_packet_contract import main as export_main


FIXED_NOW = "2026-05-23T20:00:00+00:00"


def _build() -> dict:
    return contract.build_agent_conversation_handoff_step_packet_contract(generated_at=FIXED_NOW)


def _sessions(payload: dict) -> dict:
    return payload["handoff_sessions_by_id"]


def _packets(payload: dict) -> dict:
    return payload["step_packets_by_id"]


def _exchanges(payload: dict) -> dict:
    return payload["agent_system_exchanges_by_id"]


def _handoffs(payload: dict) -> dict:
    return payload["operator_handoff_packets_by_id"]


def _statuses(payload: dict) -> dict:
    return payload["liveness_statuses_by_id"]


def _timeouts(payload: dict) -> dict:
    return payload["timeout_recovery_policies_by_id"]


def _visibility(payload: dict) -> dict:
    return payload["status_visibility_policies_by_id"]


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["doctrine"]["systems_engineering_not_loose_chat"] is True
    assert first["doctrine"]["conversations_own_canonical_workflow_state"] is False
    assert first["doctrine"]["operator_must_not_guess_progress"] is True
    assert first["hard_rule"]["read_model_only"] is True
    assert first["hard_rule"]["does_not_execute_agents"] is True
    assert first["hard_rule"]["does_not_call_models"] is True
    assert first["hard_rule"]["does_not_send_messages"] is True
    assert first["hard_rule"]["does_not_write_receipts"] is True
    assert first["hard_rule"]["does_not_mutate_workflow_state"] is True
    assert first["hard_rule"]["may_grant_authority"] is False


def test_models_and_required_fields_exist():
    payload = _build()

    assert payload["machine_proof"]["conversation_handoff_session_model_present"] is True
    assert payload["machine_proof"]["agent_step_packet_model_present"] is True
    assert payload["machine_proof"]["agent_system_exchange_model_present"] is True
    assert payload["machine_proof"]["operator_handoff_packet_model_present"] is True
    assert payload["machine_proof"]["liveness_progress_status_model_present"] is True
    assert payload["machine_proof"]["timeout_recovery_policy_model_present"] is True
    assert payload["machine_proof"]["status_visibility_policy_model_present"] is True
    assert payload["conversation_handoff_session_schema"]["required_fields"] == list(
        contract.REQUIRED_HANDOFF_SESSION_FIELDS
    )
    assert payload["agent_step_packet_schema"]["required_fields"] == list(contract.REQUIRED_STEP_PACKET_FIELDS)
    assert payload["agent_system_exchange_schema"]["required_fields"] == list(contract.REQUIRED_EXCHANGE_FIELDS)
    assert payload["operator_handoff_packet_schema"]["required_fields"] == list(
        contract.REQUIRED_OPERATOR_HANDOFF_FIELDS
    )
    assert payload["agent_liveness_progress_status_schema"]["required_fields"] == list(
        contract.REQUIRED_LIVENESS_FIELDS
    )
    assert payload["agent_handoff_timeout_recovery_policy_schema"]["required_fields"] == list(
        contract.REQUIRED_TIMEOUT_POLICY_FIELDS
    )
    assert payload["agent_status_visibility_policy_schema"]["required_fields"] == list(
        contract.REQUIRED_VISIBILITY_POLICY_FIELDS
    )
    assert set(payload["phases"]) == set(contract.PHASES)
    assert set(payload["packet_types"]) == set(contract.PACKET_TYPES)
    assert set(payload["exchange_types"]) == set(contract.EXCHANGE_TYPES)
    assert set(payload["handoff_types"]) == set(contract.HANDOFF_TYPES)
    assert set(payload["status_states"]) == set(contract.STATUS_STATES)


def test_telegram_cassandra_invoice_example_exists_and_is_gated():
    payload = _build()
    session = _sessions(payload)["telegram_cassandra_capital_hilton_invoice_handoff"]
    packet = _packets(payload)["cassandra_capital_hilton_block_fill_packet"]
    handoff = _handoffs(payload)["capital_hilton_missing_dates_operator_handoff"]
    example = payload["conversation_examples"]["telegram_cassandra_invoice"]

    assert set(contract.REQUIRED_HANDOFF_SESSION_FIELDS) <= set(session)
    assert session["originating_surface"] == "Telegram"
    assert session["target_agent"] == "Cassandra"
    assert session["workflow_session_ref"] == "capital_hilton_invoice_workflow_session"
    assert session["current_phase"] == "WAITING_ON_OPERATOR"
    assert "Send Capital Hilton" in session["user_utterance"]
    assert packet["packet_type"] == "BLOCK_FILL_PACKET"
    assert packet["assigned_agent"] == "Cassandra"
    assert "whole-system context" in packet["excluded_context_refs"]
    assert packet["allowed_tools"] == ()
    assert "invoice generation" in packet["blocked_tools"]
    assert "no invoice artifact" in packet["expected_return_shape"]
    assert handoff["handoff_type"] == "ANSWER_MISSING_BLOCK"
    assert handoff["response_expected"] is True
    assert "invoice draft review remains gated" in handoff["consequence_preview"]
    assert "Guardian/email approval remains required before send" in handoff["consequence_preview"]
    assert example["liveness_path"] == ("THINKING", "MAKING_PACKET", "WAITING_ON_OPERATOR", "RETURNING_BRIEFING")
    assert payload["machine_proof"]["telegram_cassandra_invoice_example_present"] is True


def test_mission_control_draft_example_uses_same_block_shape():
    payload = _build()
    session = _sessions(payload)["mission_control_capital_hilton_draft_handoff"]
    packet = _packets(payload)["mission_control_capital_hilton_draft_review_packet"]
    exchange = _exchanges(payload)["mission_control_draft_review_packet_delivery_exchange"]

    assert session["originating_surface"] == "Mission Control"
    assert session["draft_intent_refs"] == ("capital_hilton_mission_control_performance_dates_draft",)
    assert packet["packet_type"] == "DRAFT_REVIEW_PACKET"
    assert "same draft shape as Telegram" in packet["packet_purpose"]
    assert "active Finance World draft refs" in packet["allowed_context_refs"]
    assert "raw protected bodies" in packet["excluded_context_refs"]
    assert exchange["should_surface_to_operator"] is False
    assert exchange["next_safe_move"] == "Agent reviews/fills proof gaps and returns only if Winship is needed."
    assert payload["machine_proof"]["mission_control_draft_example_present"] is True


def test_chief_check_engine_example_uses_current_refs_only_and_returns_briefing():
    payload = _build()
    session = _sessions(payload)["chief_check_engine_conversation_handoff"]
    packet = _packets(payload)["chief_check_engine_diagnostic_packet"]
    exchange = _exchanges(payload)["chief_check_engine_diagnostic_return_exchange"]
    handoff = _handoffs(payload)["chief_check_engine_decision_operator_handoff"]

    assert session["target_agent"] == "Chief"
    assert session["current_status"] == "RETURNING_BRIEFING"
    assert packet["packet_type"] == "CHIEF_DIAGNOSTIC_PACKET"
    assert "current read-model/test refs only" in packet["packet_purpose"]
    assert "private raw files" in packet["excluded_context_refs"]
    assert exchange["should_surface_to_operator"] is True
    assert "no action ran" in exchange["operator_visible_summary"]
    assert handoff["handoff_type"] == "CHECK_ENGINE_DECISION"
    assert "no repair runs" in handoff["consequence_preview"]
    assert payload["machine_proof"]["chief_check_engine_example_present"] is True


def test_guardian_approval_example_exists_without_send_authority():
    payload = _build()
    session = _sessions(payload)["guardian_approval_handoff_session"]
    packet = _packets(payload)["guardian_capital_hilton_approval_prep_packet"]
    exchange = _exchanges(payload)["guardian_approval_prep_blocked_return_exchange"]
    handoff = _handoffs(payload)["capital_hilton_approval_review_operator_handoff"]

    assert session["target_agent"] == "Guardian"
    assert session["current_phase"] == "WAITING_ON_GUARDIAN"
    assert packet["packet_type"] == "APPROVAL_PREP_PACKET"
    assert "no submit/send action" in packet["expected_return_shape"]
    assert exchange["exchange_type"] == "BLOCKED_RETURN"
    assert "approval remains locked" in exchange["system_response_summary"]
    assert handoff["handoff_type"] == "APPROVE_PACKET"
    assert "approval alone does not send" in handoff["consequence_preview"]
    assert "no approval submission occurs here" in handoff["consequence_preview"]
    assert payload["machine_proof"]["guardian_approval_example_present"] is True


def test_offline_stalled_example_surfaces_no_action_taken():
    payload = _build()
    session = _sessions(payload)["cassandra_invoice_packet_stalled_handoff"]
    status = _statuses(payload)["cassandra_invoice_packet_stalled_status"]
    exchange = _exchanges(payload)["cassandra_stalled_status_exchange"]
    handoff = _handoffs(payload)["cassandra_stalled_operator_handoff"]
    policy = _timeouts(payload)["stalled_agent_recovery_policy"]

    assert session["current_phase"] == "TIMED_OUT"
    assert session["current_status"] == "STALLED"
    assert status["status_state"] == "STALLED"
    assert status["operator_visible"] is True
    assert exchange["should_surface_to_operator"] is True
    assert "No action was taken" in exchange["operator_visible_summary"]
    assert handoff["captain_summary"] == (
        "Cassandra appears stalled while preparing the invoice packet. No action was taken."
    )
    assert handoff["choices"] == ("Resume", "Retry once", "Park this", "Open Finance World")
    assert policy["retry_allowed"] is True
    assert policy["retry_limit"] == 1
    assert "No action was taken" in policy["recovery_message_shape"]
    assert payload["machine_proof"]["offline_stalled_example_present"] is True


def test_operator_system_update_marks_packet_stale_and_updates_agent():
    payload = _build()
    session = _sessions(payload)["operator_block_change_updates_agent_handoff"]
    packet = _packets(payload)["cassandra_capital_hilton_block_fill_packet_v2"]
    exchange = _exchanges(payload)["system_update_agent_packet_stale_exchange"]
    status = _statuses(payload)["cassandra_updating_from_latest_draft_status"]
    handoff = _handoffs(payload)["operator_block_change_status_handoff"]

    assert session["current_phase"] == "WAITING_ON_SYSTEM"
    assert session["visible_status_label"] == "Cassandra is updating from your latest draft."
    assert packet["step_packet_id"].endswith("_v2")
    assert "stale prior packet as truth" in packet["excluded_context_refs"]
    assert exchange["system_response_summary"] == "Performance dates draft changed; prior packet stale."
    assert exchange["operator_visible_summary"] == "Cassandra is updating from your latest draft."
    assert status["system_updates_agent_policy"] == (
        "system sends packet delta: Performance dates draft changed; prior packet stale."
    )
    assert handoff["response_expected"] is False
    assert payload["machine_proof"]["operator_system_update_example_present"] is True


def test_packets_are_focused_narrow_and_tools_are_not_authority():
    payload = _build()

    for packet in payload["step_packets"]:
        assert set(contract.REQUIRED_STEP_PACKET_FIELDS) <= set(packet)
        assert "whole-system context" in packet["excluded_context_refs"]
        assert len(packet["allowed_context_refs"]) <= 4
        assert packet["allowed_tools"] == ()
        assert packet["allowed_mcp_refs"] == ()
        assert packet["allowed_script_refs"] == ()
        assert packet["allowed_hook_refs"] == ()
        for key, value in packet["authority_boundary"].items():
            assert value is False, key
    assert payload["agent_step_packet_schema"]["focused_context_only"] is True
    assert payload["agent_step_packet_schema"]["whole_system_context_default"] is False
    assert payload["agent_step_packet_schema"]["tools_are_capabilities_not_authority"] is True
    assert payload["machine_proof"]["packets_are_focused_narrow"] is True


def test_agent_system_exchanges_are_below_deck_by_default_and_summarizable():
    payload = _build()

    assert payload["agent_system_exchange_schema"]["below_deck_by_default"] is True
    assert payload["agent_system_exchange_schema"]["raw_agent_telemetry_spams_operator"] is False
    assert payload["agent_system_exchange_schema"]["summarizable_into_crew_briefing"] is True
    request = _exchanges(payload)["cassandra_invoice_packet_request_exchange"]
    assert request["should_surface_to_operator"] is False
    assert request["operator_visible_summary"] == ""
    surfaced = [
        exchange
        for exchange in payload["agent_system_exchanges"]
        if exchange["should_surface_to_operator"]
    ]
    assert surfaced
    for exchange in surfaced:
        assert exchange["operator_visible_summary"]


def test_operator_handoff_is_concise_and_only_when_needed():
    payload = _build()

    assert payload["operator_handoff_packet_schema"]["must_be_concise"] is True
    assert payload["operator_handoff_packet_schema"]["must_explain_why_operator_needed"] is True
    assert payload["operator_handoff_packet_schema"]["clear_choices_when_possible"] is True
    assert payload["operator_handoff_packet_schema"]["proof_refs_below_deck"] is True
    assert payload["operator_handoff_packet_schema"]["handoff_executes_action"] is False
    for handoff in payload["operator_handoff_packets"]:
        assert handoff["captain_summary"]
        assert handoff["why_operator_needed"]
        assert handoff["choices"]
        for key, value in handoff["authority_boundary"].items():
            assert value is False, key
    assert payload["machine_proof"]["operator_handoff_only_when_needed"] is True


def test_liveness_status_states_include_required_distinctions():
    payload = _build()
    states = set(payload["status_states"])
    required = {
        "THINKING",
        "TYPING",
        "MAKING_PACKET",
        "WAITING_ON_SYSTEM",
        "WAITING_ON_OPERATOR",
        "OFFLINE",
        "STALLED",
    }

    assert required <= states
    assert payload["agent_liveness_progress_status_schema"]["typing_indicator_is_sufficient"] is False
    assert payload["agent_liveness_progress_status_schema"][
        "distinguishes_thinking_typing_making_packet_waiting_offline"
    ] is True
    assert payload["agent_liveness_progress_status_schema"]["stalled_offline_timeout_operator_visible"] is True
    assert payload["machine_proof"]["required_status_states_present"] is True
    status_states = {status["status_state"] for status in payload["liveness_statuses"]}
    assert {"THINKING", "MAKING_PACKET", "WAITING_ON_OPERATOR", "WAITING_ON_SYSTEM", "VALIDATING", "STALLED"} <= status_states


def test_timeout_recovery_policy_has_explicit_fallback_and_no_auto_loops():
    payload = _build()
    standard = _timeouts(payload)["standard_agent_handoff_timeout_policy"]
    stalled = _timeouts(payload)["stalled_agent_recovery_policy"]

    assert payload["agent_handoff_timeout_recovery_policy_schema"]["soft_timeout_may_show_still_working"] is True
    assert payload["agent_handoff_timeout_recovery_policy_schema"]["hard_timeout_shows_blocked_offline_stalled"] is True
    assert payload["agent_handoff_timeout_recovery_policy_schema"]["fallback_explicit"] is True
    assert payload["agent_handoff_timeout_recovery_policy_schema"]["automatic_retry_loops_allowed"] is False
    assert standard["retry_limit"] == 1
    assert stalled["fallback_to_world_surface"] is True
    assert stalled["fallback_to_bridge_attention"] is True
    assert "No action was taken" in stalled["recovery_message_shape"]


def test_status_visibility_policy_prevents_spam_across_surfaces():
    payload = _build()
    visibility = _visibility(payload)["calm_agent_status_visibility_policy"]
    below = _visibility(payload)["below_deck_exchange_log_visibility_policy"]

    assert visibility["suppress_minor_transitions"] is True
    assert "TYPING" in visibility["hidden_states"]
    assert "Bridge sees only captain-relevant" in visibility["escalation_rule"]
    assert "status chip" in visibility["world_visibility_rule"]
    assert "Cassandra is preparing packet" in visibility["telegram_visibility_rule"]
    assert below["bridge_visibility_rule"] == "never show raw exchange log on Bridge"
    assert payload["agent_status_visibility_policy_schema"]["status_informs_not_annoys"] is True
    assert payload["agent_status_visibility_policy_schema"]["frequent_internal_transitions_aggregated"] is True


def test_relationship_refs_and_starship_alignment_exist():
    payload = _build()
    refs = payload["relationship_refs"]
    starship = payload["starship_operating_model_alignment"]

    for ref_id in [
        "workflow_block_intent_live_draft_contract",
        "bridge_routing_operator_attention_contract",
        "operator_solve_path_decision_node_contract",
        "workflow_session_channel_projection_approval_bus_contract",
        "guided_capture_protected_evidence_path_contract",
        "automation_readiness_feasibility_evaluator_contract",
    ]:
        assert ref_id in refs
        assert refs[ref_id]["path"].endswith(".json")
        assert "present" in refs[ref_id]
    assert starship["captain"] == "operator"
    assert starship["bridge"] == "captain-level attention"
    assert "packet compilation" in starship["engineering"]
    assert starship["crew_briefings"] == "operator handoff packets"
    assert "Red Alert only" in starship["red_alert_rule"]


def test_no_live_authority_credentials_or_raw_private_bodies():
    payload = _build()
    text = contract.stable_json(payload)

    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for session in payload["handoff_sessions"]:
        for key, value in session["authority_boundary"].items():
            assert value is False, key
    for packet in payload["step_packets"]:
        for key, value in packet["authority_boundary"].items():
            assert value is False, key
    for handoff in payload["operator_handoff_packets"]:
        for key, value in handoff["authority_boundary"].items():
            assert value is False, key
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert payload["machine_proof"]["credentials_or_secrets_included"] is False
    assert payload["machine_proof"]["raw_private_bodies_included"] is False
    for key in [
        "live_agent_execution_allowed",
        "model_call_allowed",
        "telegram_send_allowed",
        "message_send_allowed",
        "tool_execution_allowed",
        "mcp_execution_allowed",
        "script_execution_allowed",
        "hook_execution_allowed",
        "receipt_write_allowed",
        "state_write_allowed",
        "invoice_generation_allowed",
        "email_draft_allowed",
        "email_send_allowed",
        "browser_automation_allowed",
        "coupa_access_allowed",
        "credential_handling_allowed",
        "approval_submission_allowed",
        "queue_execution_allowed",
        "runtime_dispatch_allowed",
        "file_write_allowed",
        "raw_body_ingestion_allowed",
    ]:
        assert payload["authority_boundary"][key] is False
    secret_patterns = [
        r"sk-[A-Za-z0-9_-]{20,}",
        r"xox[baprs]-[A-Za-z0-9-]{10,}",
        r"ghp_[A-Za-z0-9_]{20,}",
        r"AKIA[0-9A-Z]{16}",
        r"AIza[0-9A-Za-z_-]{20,}",
        r"BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY",
    ]
    for pattern in secret_patterns:
        assert re.search(pattern, text) is None


def test_exporter_writes_json_and_eliwinship_operator_markdown(tmp_path):
    result = export_main(
        [
            "--repo-root",
            tmp_path.as_posix(),
            "--export-root",
            "generated/read_models",
            "--format",
            "summary",
            "--generated-at",
            FIXED_NOW,
        ]
    )

    assert result == 0
    json_path = tmp_path / "generated" / "read_models" / contract.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated" / "read_models" / contract.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert payload["machine_proof"]["handoff_session_count"] == 6
    assert payload["machine_proof"]["step_packet_count"] == 6
    assert "ELIWINSHIP Summary" in operator
    assert "typing is not enough" in operator
    assert "Cassandra appears stalled while preparing the invoice packet" in operator
    assert "No live authority exists here" in operator
    assert "All authority flags false" in operator


def test_source_has_no_disallowed_runtime_behavior():
    text = Path("agent_conversation_handoff_step_packet_contract.py").read_text(encoding="utf-8").lower()
    for token in [
        "subprocess",
        "shell=true",
        "os.system",
        "requests.",
        "urllib",
        "shutil.rmtree",
        "shutil.move",
        ".unlink(",
        ".rename(",
        "openai",
    ]:
        assert token not in text
