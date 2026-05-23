import json
import re
from pathlib import Path

import bridge_routing_operator_attention_contract as contract
from scripts.export_bridge_routing_operator_attention_contract import main as export_main


FIXED_NOW = "2026-05-23T18:00:00+00:00"


def _build() -> dict:
    return contract.build_bridge_routing_operator_attention_contract(generated_at=FIXED_NOW)


def _attention(payload: dict) -> dict:
    return payload["attention_records_by_id"]


def _routes(payload: dict) -> dict:
    return payload["routing_decisions_by_id"]


def _worlds(payload: dict) -> dict:
    return payload["world_surfaces_by_id"]


def _below_deck(payload: dict) -> dict:
    return payload["below_deck_details_by_id"]


def _briefings(payload: dict) -> dict:
    return payload["crew_briefings_by_id"]


def _shipyard(payload: dict) -> dict:
    return payload["shipyard_records_by_id"]


def _policies(payload: dict) -> dict:
    return payload["alert_policies_by_id"]


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["doctrine"]["bridge_rule"] == "Bridge routes; Worlds do work; Engineering stays below deck."
    assert first["doctrine"]["systems_engineering_not_theme"] is True
    assert first["hard_rule"]["read_model_only"] is True
    assert first["hard_rule"]["does_not_write_receipts"] is True
    assert first["hard_rule"]["does_not_write_state"] is True
    assert first["hard_rule"]["does_not_execute_workflow"] is True
    assert first["hard_rule"]["does_not_call_agents_or_models"] is True
    assert first["hard_rule"]["may_grant_authority"] is False


def test_models_and_required_fields_exist():
    payload = _build()

    assert payload["machine_proof"]["bridge_attention_record_model_present"] is True
    assert payload["machine_proof"]["attention_routing_decision_model_present"] is True
    assert payload["machine_proof"]["world_mission_surface_model_present"] is True
    assert payload["machine_proof"]["below_deck_engineering_detail_model_present"] is True
    assert payload["machine_proof"]["crew_briefing_model_present"] is True
    assert payload["machine_proof"]["shipyard_mode_record_model_present"] is True
    assert payload["machine_proof"]["bridge_alert_policy_model_present"] is True
    assert payload["bridge_attention_record_schema"]["required_fields"] == list(
        contract.REQUIRED_BRIDGE_ATTENTION_FIELDS
    )
    assert payload["attention_routing_decision_schema"]["required_fields"] == list(
        contract.REQUIRED_ROUTING_DECISION_FIELDS
    )
    assert payload["world_mission_surface_schema"]["required_fields"] == list(
        contract.REQUIRED_WORLD_SURFACE_FIELDS
    )
    assert payload["below_deck_engineering_detail_schema"]["required_fields"] == list(
        contract.REQUIRED_BELOW_DECK_FIELDS
    )
    assert payload["crew_briefing_schema"]["required_fields"] == list(contract.REQUIRED_CREW_BRIEFING_FIELDS)
    assert payload["shipyard_mode_schema"]["required_fields"] == list(contract.REQUIRED_SHIPYARD_FIELDS)
    assert payload["bridge_alert_policy_schema"]["required_fields"] == list(contract.REQUIRED_ALERT_POLICY_FIELDS)
    assert set(payload["attention_types"]) == set(contract.ATTENTION_TYPES)
    assert set(payload["alert_levels"]) == set(contract.ALERT_LEVELS)
    assert set(payload["routing_destinations"]) == set(contract.ROUTING_DESTINATIONS)


def test_capital_hilton_routes_to_finance_world_not_raw_helm_workspace():
    payload = _build()
    attention = _attention(payload)["capital_hilton_finance_mission_attention"]
    route = _routes(payload)["route_capital_hilton_to_finance_world"]
    finance = _worlds(payload)["finance_world_mission_surface"]

    assert set(contract.REQUIRED_BRIDGE_ATTENTION_FIELDS) <= set(attention)
    assert attention["world"] == "Finance"
    assert attention["lane"] == "Capital Hilton"
    assert attention["attention_type"] == "WORLD_NEEDS_ATTENTION"
    assert attention["alert_level"] == "YELLOW_ALERT"
    assert attention["should_show_on_helm"] is True
    assert attention["should_interrupt_captain"] is False
    assert attention["route_target"] == "WORLD"
    assert route["routing_destination"] == "WORLD"
    assert route["world_surface_target"] == "finance_world_mission_surface"
    assert "Raw proof" in route["suppress_from_helm_reason"]
    assert finance["world"] == "Finance"
    assert "Capital Hilton invoice" in finance["active_missions"]
    assert "performance_dates" in finance["unlocked_blocks"]
    assert finance["helm_summary"] == "Finance needs attention: Capital Hilton has one next invoice block."
    assert payload["machine_proof"]["capital_hilton_routes_to_finance_world"] is True
    assert payload["machine_proof"]["capital_hilton_not_raw_helm_workspace"] is True


def test_capital_hilton_approval_locked_stays_world_or_below_deck():
    payload = _build()
    attention = _attention(payload)["capital_hilton_approval_locked_attention"]
    route = _routes(payload)["route_capital_hilton_approval_locked_to_world"]
    guardian = _briefings(payload)["guardian_invoice_gate_briefing"]

    assert attention["captain_decision_needed"] is False
    assert attention["should_show_on_helm"] is False
    assert attention["should_stay_in_world"] is True
    assert "raw proof wall" in attention["quieting_policy"]
    assert route["requires_operator_decision"] is False
    assert "not ready" in route["suppress_from_helm_reason"]
    assert guardian["decision_needed"] is False
    assert guardian["should_promote_to_helm"] is False
    assert guardian["should_remain_in_world"] is True


def test_proof_debug_and_engineering_detail_stay_below_deck_by_default():
    payload = _build()
    proof_attention = _attention(payload)["proof_available_below_deck_attention"]
    sync_attention = _attention(payload)["sync_health_mismatch_attention"]
    proof_detail = _below_deck(payload)["capital_hilton_proof_below_deck_detail"]
    sync_detail = _below_deck(payload)["sync_health_below_deck_detail"]

    assert proof_attention["attention_type"] == "PROOF_AVAILABLE"
    assert proof_attention["should_show_on_helm"] is False
    assert proof_attention["should_stay_below_deck"] is True
    assert sync_attention["alert_level"] == "ENGINEERING_CONTAINED"
    assert sync_attention["should_interrupt_captain"] is False
    assert proof_detail["default_visibility"] == "collapsed"
    assert proof_detail["interrupt_allowed"] is False
    assert sync_detail["detail_type"] == "SYNC_HEALTH"
    assert sync_detail["default_visibility"] == "collapsed"
    assert sync_detail["interrupt_allowed"] is False
    assert payload["below_deck_engineering_detail_schema"]["proof_exists_but_does_not_dominate"] is True
    assert payload["below_deck_engineering_detail_schema"]["debug_detail_belongs_below_deck_or_shipyard"] is True
    assert payload["machine_proof"]["proof_debug_detail_below_deck_by_default"] is True
    assert payload["machine_proof"]["engineering_contained_does_not_interrupt"] is True


def test_chief_check_engine_routes_to_shipyard_unless_blocking_active_mission():
    payload = _build()
    attention = _attention(payload)["chief_check_engine_attention"]
    route = _routes(payload)["route_chief_check_engine_to_shipyard"]
    shipyard_record = _shipyard(payload)["chief_check_engine_shipyard_record"]
    chief = _briefings(payload)["chief_check_engine_briefing"]

    assert attention["attention_type"] == "CHECK_ENGINE"
    assert attention["alert_level"] == "SHIPYARD_MODE"
    assert attention["should_show_on_helm"] is False
    assert attention["should_interrupt_captain"] is False
    assert route["routing_destination"] == "SHIPYARD"
    assert "build/repair" in route["route_to_shipyard_reason"]
    assert shipyard_record["should_show_on_helm"] is False
    assert shipyard_record["should_show_in_shipyard"] is True
    assert shipyard_record["safe_to_ignore_in_normal_mode"] is True
    assert chief["should_promote_to_helm"] is False
    assert payload["shipyard_mode_schema"]["normal_bridge_suppresses_shipyard_noise"] is True
    assert payload["machine_proof"]["shipyard_separates_developer_noise"] is True


def test_red_alert_interrupts_only_when_captain_decision_required():
    payload = _build()
    attention = _attention(payload)["security_red_alert_attention"]
    route = _routes(payload)["route_security_decision_to_red_alert"]
    guardian = _briefings(payload)["guardian_security_gate_briefing"]
    red_policy = _policies(payload)["red_alert_policy"]

    assert attention["alert_level"] == "RED_ALERT"
    assert attention["captain_decision_needed"] is True
    assert attention["should_interrupt_captain"] is True
    assert attention["should_show_on_helm"] is True
    assert route["routing_destination"] == "RED_ALERT"
    assert route["requires_operator_decision"] is True
    assert route["requires_immediate_attention"] is True
    assert guardian["urgency"] == "RED_ALERT"
    assert guardian["decision_needed"] is True
    assert red_policy["captain_interrupt_allowed"] is True
    assert "safe continuation blocked" in red_policy["promotion_criteria"]
    assert payload["bridge_alert_policy_schema"]["red_alert_requires_captain_decision_before_safe_continuation"] is True
    assert payload["machine_proof"]["red_alert_interrupts_only_when_captain_decision_required"] is True


def test_crew_briefings_are_action_oriented_and_agents_do_not_own_truth():
    payload = _build()
    briefings = _briefings(payload)

    for briefing in briefings.values():
        assert set(contract.REQUIRED_CREW_BRIEFING_FIELDS) <= set(briefing)
        assert briefing["captain_summary"]
        assert briefing["recommended_action"]
        for value in briefing["authority_boundary"].values():
            assert value is False
    cassandra = briefings["cassandra_telegram_request_briefing"]
    assert cassandra["crew_actor"] == "Cassandra"
    assert cassandra["briefing_type"] == "DRAFT_READY"
    assert cassandra["should_promote_to_helm"] is True
    assert cassandra["should_remain_in_world"] is False
    assert payload["crew_briefing_schema"]["agents_brief_not_spam"] is True
    assert payload["crew_briefing_schema"]["raw_agent_telemetry_on_helm"] is False
    assert payload["crew_briefing_schema"]["crew_owns_truth"] is False
    assert payload["machine_proof"]["crew_briefings_action_oriented"] is True
    assert payload["machine_proof"]["agents_do_not_own_truth"] is True


def test_sync_health_mismatch_policy_can_stay_contained_or_promote_if_mission_blocking():
    payload = _build()
    attention = _attention(payload)["sync_health_mismatch_attention"]
    route = _routes(payload)["route_sync_health_mismatch_contained_below_deck"]
    contained = _policies(payload)["engineering_contained_policy"]
    quiet = _policies(payload)["quiet_log_only_policy"]

    assert attention["alert_level"] == "ENGINEERING_CONTAINED"
    assert attention["should_stay_below_deck"] is True
    assert "blocks Mac app read-model availability" in attention["captain_level_summary"]
    assert "Promote to Yellow/Red" in attention["expiry_or_staleness_policy"]
    assert route["routing_destination"] == "BELOW_DECK"
    assert "Promote only if" in route["promote_to_helm_reason"]
    assert contained["captain_interrupt_allowed"] is False
    assert quiet["captain_interrupt_allowed"] is False
    assert payload["bridge_alert_policy_schema"]["engineering_contained_logs_below_deck"] is True
    assert payload["bridge_alert_policy_schema"]["quiet_log_only_never_interrupts"] is True


def test_telegram_cassandra_request_becomes_world_draft_not_channel_owned_state():
    payload = _build()
    attention = _attention(payload)["telegram_cassandra_request_attention"]
    route = _routes(payload)["route_telegram_cassandra_request_to_finance_world"]
    detail = _below_deck(payload)["telegram_request_below_deck_detail"]

    assert attention["source_surface"] == "Telegram"
    assert attention["source_actor"] == "Cassandra"
    assert attention["attention_type"] == "CREW_BRIEFING"
    assert attention["should_show_on_helm"] is True
    assert attention["route_target"] == "WORLD"
    assert route["routing_destination"] == "WORLD"
    assert route["world_surface_target"] == "finance_world_mission_surface"
    assert "workflow session owns state" in route["reason"]
    assert detail["default_visibility"] == "collapsed"
    assert "raw telemetry" in detail["summary"]


def test_relationship_refs_to_existing_contracts_are_represented():
    payload = _build()
    refs = payload["relationship_refs"]

    for ref_id in [
        "workflow_block_intent_live_draft_contract",
        "operator_solve_path_decision_node_contract",
        "workflow_session_channel_projection_approval_bus_contract",
        "guided_capture_protected_evidence_path_contract",
        "automation_readiness_feasibility_evaluator_contract",
        "openclaw_work_terrain_gap_detector",
        "capital_hilton_proof_resolution_batch",
        "security_pass_contract",
    ]:
        assert ref_id in refs
        assert refs[ref_id]["path"].endswith(".json")
        assert "present" in refs[ref_id]
    assert payload["machine_proof"]["relationship_refs_represented"] is True


def test_alert_policies_exist_and_match_required_semantics():
    payload = _build()
    policies = _policies(payload)

    expected = {
        "normal_flight_policy",
        "yellow_alert_policy",
        "red_alert_policy",
        "engineering_contained_policy",
        "shipyard_mode_policy",
        "quiet_log_only_policy",
    }
    assert expected <= set(policies)
    assert policies["normal_flight_policy"]["captain_interrupt_allowed"] is False
    assert policies["yellow_alert_policy"]["captain_interrupt_allowed"] is False
    assert policies["red_alert_policy"]["captain_interrupt_allowed"] is True
    assert policies["engineering_contained_policy"]["visible_surface"] == "Below Deck / Engineering"
    assert policies["shipyard_mode_policy"]["visible_surface"] == "Shipyard"
    assert policies["quiet_log_only_policy"]["visible_surface"] == "Below Deck log only"


def test_no_live_authority_credentials_or_raw_private_bodies():
    payload = _build()
    text = contract.stable_json(payload)

    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for record in payload["attention_records"]:
        for key, value in record["authority_boundary"].items():
            assert value is False, key
    for briefing in payload["crew_briefings"]:
        for key, value in briefing["authority_boundary"].items():
            assert value is False, key
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert payload["machine_proof"]["credentials_or_secrets_included"] is False
    assert payload["machine_proof"]["raw_private_bodies_included"] is False
    for key in [
        "helm_action_execution_allowed",
        "world_action_execution_allowed",
        "crew_action_execution_allowed",
        "receipt_write_allowed",
        "state_write_allowed",
        "approval_submission_allowed",
        "invoice_generation_allowed",
        "email_send_allowed",
        "browser_automation_allowed",
        "credential_handling_allowed",
        "telegram_send_allowed",
        "model_call_allowed",
        "agent_activation_allowed",
        "tool_execution_allowed",
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
    assert payload["machine_proof"]["attention_record_count"] == 7
    assert payload["machine_proof"]["alert_policy_count"] == 6
    assert "ELIWINSHIP Summary" in operator
    assert "Bridge routes. Worlds do work. Engineering stays below deck." in operator
    assert "This is systems engineering, not Star Trek theming." in operator
    assert "Capital Hilton belongs in Finance World" in operator
    assert "All authority flags false" in operator


def test_source_has_no_disallowed_runtime_behavior():
    text = Path("bridge_routing_operator_attention_contract.py").read_text(encoding="utf-8").lower()
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
