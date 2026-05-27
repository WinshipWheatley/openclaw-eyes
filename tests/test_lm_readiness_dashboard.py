import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import guardian_output_gate
import intent_ingest_gate
import lm_readiness_dashboard as dashboard
import model_router_policy
import provider_policy_registry
import role_package_gate
import universal_intake_contract


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def _payload() -> dict:
    return dashboard.build_payload(generated_at=FIXED_NOW)


def test_readiness_dashboard_aggregates_all_seeded_lanes():
    payload = _payload()
    lanes = payload["aggregated_lanes"]

    for lane in (
        "gate_chain_harness",
        "guardian_trust_ramp_simulator",
        "model_router_policy",
        "provider_policy_registry",
        "live_lm_readiness_gate",
        "shadow_lm_mode",
        "token_vault_status",
        "universal_intake_contract",
        "gate1_privacy_request_readiness",
        "gate1_operational_snapshot",
        "request_response_bridge_readiness",
        "live_lm_activation_requirements",
        "private_mode_policy_readiness",
        "read_model_mirror_visibility",
    ):
        assert lane in lanes
    assert payload["machine_proof"]["dashboard_aggregates_seeded_lanes"] is True
    assert payload["dashboard_summary"]["lm1_shadow"] == "READY"
    assert payload["dashboard_summary"]["lm1_shadow_comparison"] == "READY"
    assert payload["dashboard_summary"]["lm2_package_shadow"] == "READY"
    assert payload["dashboard_summary"]["lm2_shadow_comparison"] == "READY"
    assert payload["dashboard_summary"]["provider_policy_registry"] == "SEEDED"
    assert payload["dashboard_summary"]["gate1_operational_snapshot"] == "EXPORTED_CONNECTED"
    assert payload["dashboard_summary"]["gate1_privacy_request"] == "EXPORTED"
    assert payload["dashboard_summary"]["lm1_thread_context_package"] == "CONNECTED_TO_GATE1"
    assert payload["dashboard_summary"]["request_response_bridge"] in {
        "READY_FOR_LIVE_REVIEW",
        "SEEDED_NEEDS_OPERATOR_SERVICE_CHECK",
    }
    assert payload["dashboard_summary"]["production_live_blockers"] == "EXPLICIT"
    assert payload["dashboard_summary"]["production_activation_beams"] == "EXPLICIT_SEVEN_BEAMS"
    assert payload["dashboard_summary"]["provider_activation_receipts"] == "RECEIPTS_REQUIRED_NOT_PRESENT"
    assert payload["dashboard_summary"]["live_lm_shadow_trial"] == "LIVE_SHADOW_PASSED"
    assert payload["dashboard_summary"]["live_shadow_receipt"] == "PRESENT"
    assert payload["dashboard_summary"]["private_mode_policy"] == "PRIVATE_MODE_POLICY_READY_INACTIVE"


def test_lm1_thread_context_package_includes_universal_intake_and_token_declarations():
    package = dashboard.build_lm1_thread_context_package(source_request_id="test_lm1_context")

    assert package["source_request_id"] == "test_lm1_context"
    assert package["gate1_operational_snapshot_ref"].startswith("gate1_operational_snapshot:")
    assert package["gate1_privacy_flags"]["safe_to_package_for_lm1"] is True
    assert package["source_device_ref"] == "mission_control_mac"
    assert package["universal_intake_inference"]["client_ref"] == "capital_hilton"
    assert package["universal_intake_inference"]["artifact_kind"] == "running_invoice_workbook"
    assert package["universal_intake_chain_contract"]["candidate_may_enter_gate_2_after_lm1_proposal"] is True
    assert package["privacy_classification"] == "CLIENT_FINANCE_FILE_METADATA"
    assert package["tokenization_required"] is True
    assert package["tokenization_policy"]["tokenization_required"] is True
    assert package["tokenization_policy"]["model_may_see_raw_values"] is False
    assert package["privacy"]["tokenization_applied"] is True
    assert package["privacy"]["raw_values_included"] is False
    assert package["model_router_result"]["selected_model_class"] == model_router_policy.FAST_STRUCTURED_INTENT_SMALL
    assert package["model_router_result"]["selected_provider_ref"] == "provider_class:local_or_private_structured_stub"
    assert package["raw_values_included"] is False
    assert "MachineIntentCandidate" not in package["output_schema"]
    assert "source_request_id" in package["output_schema"]
    assert package["tools_allowed"] == ()


def test_gate3_role_package_includes_tokenization_fields():
    payload = _payload()
    package = payload["representative_flow"]["gate3_package_summary"]

    assert package["package_status"] == role_package_gate.PACKAGE_COMPILED
    assert package["tokenization_applied"] is True
    assert package["raw_values_included"] is False
    assert package["token_vault_ref"] == "generated/read_models/token_vault_status.json"
    assert package["detokenization_policy_ref"] == "detokenization_denied_without_explicit_policy_receipt"
    assert package["privacy_level"] == "metadata_only_tokenized_refs"
    assert package["model_may_see_raw_values"] is False


def test_model_router_integration_selects_lm1_and_lm2_model_classes():
    payload = _payload()

    assert payload["representative_flow"]["lm1_model_decision"]["selected_model_class"] == model_router_policy.FAST_STRUCTURED_INTENT_SMALL
    assert payload["representative_flow"]["lm2_model_decision"]["selected_model_class"] in {
        model_router_policy.STRONG_STRUCTURED_ROLE_REASONER,
        model_router_policy.CONSERVATIVE_SENSITIVE_STRUCTURED,
    }
    assert payload["representative_flow"]["provider_policy_decisions"]["lm1"]["selected_model_class"] == provider_policy_registry.FAST_STRUCTURED_INTENT_SMALL
    assert payload["machine_proof"]["provider_policy_lm1_selected"] is True
    assert payload["machine_proof"]["provider_policy_lm2_selected"] is True


def test_model_router_returns_no_safe_model_when_privacy_is_insufficient():
    decision = model_router_policy.select_for_lm2_role_package(
        {
            "package_id": "unsafe_raw_package",
            "role_identity": "CASSANDRA",
            "task": "Prepare response.",
            "tokenization_applied": False,
            "raw_values_included": True,
            "privacy_level": "protected",
        }
    )

    assert decision["selected_model_class"] == model_router_policy.NO_SAFE_MODEL
    assert "RAW_SENSITIVE_VALUES_REQUIRE_TOKENIZATION" in decision["blocked_reasons"]


def test_universal_intake_fixture_stays_draft_source_only():
    inference = universal_intake_contract.infer_universal_intake(
        {
            "source_request_id": "test_universal",
            "file_display_name": "Invoice Capitol Hilton Running.xlsx",
            "file_extension": ".xlsx",
            "file_type": "spreadsheet",
            "user_note": "these are invoice workbooks for the clients named in the files",
            "current_world_ref": "finance",
        }
    )

    assert inference["artifact_kind"] == "running_invoice_workbook"
    assert inference["submitted"] is False
    assert inference["paid"] is False
    assert inference["ledger_posted"] is False
    assert inference["final"] is False
    assert inference["proposed_facts_only"] is True


def test_dashboard_includes_universal_intake_batch_fixture_and_privacy_readiness():
    payload = _payload()
    batch = payload["representative_flow"]["universal_intake_batch_fixture"]
    privacy = payload["representative_flow"]["privacy_readiness_result"]

    assert len(batch["candidates"]) == 3
    assert {candidate["client_ref"] for candidate in batch["candidates"]} == {"capital_hilton", "live_arts_md", "st_annes"}
    assert payload["dashboard_summary"]["universal_intake_batch"] == "READY"
    assert privacy["production_token_vault_ready"] is True
    assert privacy["synthetic_tokenization_ready"] is True
    assert (
        payload["dashboard_summary"]["privacy_readiness_status"]
        == "PRODUCTION_TOKEN_VAULT_SUBSTRATE_READY_PRIVACY_RECEIPT_PRESENT_NO_LIVE_LM"
    )


def test_dashboard_exposes_bridge_and_gate1_without_expanding_authority():
    payload = _payload()
    flow = payload["representative_flow"]

    assert flow["gate1_privacy_request_readiness"]["chain_contract"]["lm1_may_receive_raw_values"] is False
    assert flow["gate1_operational_snapshot"]["safe_to_package_for_lm1"] is True
    assert flow["request_response_bridge_readiness"]["safe_delivery_policy"]["arbitrary_destination_allowed"] is False
    assert payload["machine_proof"]["gate1_privacy_request_readiness_aggregated"] is True
    assert payload["machine_proof"]["gate1_operational_snapshot_aggregated"] is True
    assert payload["machine_proof"]["gate1_snapshot_connected_to_lm1_package"] is True
    assert payload["machine_proof"]["lm1_package_connected_to_gate1"] is True
    assert payload["machine_proof"]["request_response_bridge_readiness_aggregated"] is True
    assert payload["machine_proof"]["model_call_performed"] is False
    assert payload["machine_proof"]["tool_execution_performed"] is False


def test_dashboard_exposes_activation_private_and_visibility_without_live_enablement():
    payload = _payload()
    flow = payload["representative_flow"]

    assert flow["live_lm_activation_requirements"]["live_lm1_activation_status"] == "NOT_READY"
    assert flow["live_lm_activation_requirements"]["provider_activation_status"] == "RECEIPTS_REQUIRED_NOT_PRESENT"
    assert len(flow["live_lm_activation_requirements"]["production_activation_beams"]) == 7
    beams = {item["beam_id"]: item for item in flow["live_lm_activation_requirements"]["production_activation_beams"]}
    assert beams["production_token_vault"]["status"] == "PRESENT"
    assert beams["privacy_receipt"]["status"] == "PRESENT"
    assert {
        "device_trust_live_activation",
        "real_lm_production_policy",
    }.issubset(beams)
    assert flow["live_lm_activation_requirements"]["live_shadow_receipt"]["present"] is True
    assert flow["live_lm_activation_requirements"]["shadow_test_receipts"]["provider_policy_receipt"]["present"] is True
    assert flow["live_lm_activation_requirements"]["shadow_test_receipts"]["provider_policy_receipt"][
        "satisfies_production_activation"
    ] is False
    assert flow["live_lm_shadow_trial"]["live_model_call_performed"] is True
    assert flow["live_lm_shadow_trial"]["live_shadow_receipt_valid"] is True
    assert flow["private_mode_policy_readiness"]["active_state"] == "standard"
    assert flow["private_mode_policy_readiness"]["package_effect_summary"]["raw_values_included"] is False
    assert flow["read_model_mirror_visibility"]["mirror_policy"]["new_sync_system_allowed"] is False
    assert payload["machine_proof"]["live_activation_requirements_aggregated"] is True
    assert payload["machine_proof"]["production_activation_beams_explicit"] is True
    assert payload["machine_proof"]["production_activation_beam_count"] == 7
    assert payload["machine_proof"]["live_lm_shadow_trial_aggregated"] is True
    assert payload["machine_proof"]["live_shadow_model_call_recorded"] is True
    assert payload["machine_proof"]["live_shadow_receipt_valid"] is True
    assert payload["machine_proof"]["shadow_provider_policy_receipt_present"] is True
    assert payload["machine_proof"]["shadow_model_selection_receipt_present"] is True
    assert payload["machine_proof"]["provider_activation_receipts_present"] is False
    assert payload["machine_proof"]["private_mode_policy_active"] is False
    assert payload["machine_proof"]["read_model_mirror_visibility_mac_visible_guaranteed"] is False


def test_representative_flow_reaches_gate2_gate3_gate4_without_live_status():
    payload = _payload()
    flow = payload["representative_flow"]

    assert flow["gate2_result_summary"]["outcome"] == intent_ingest_gate.ACCEPTED_INTENT
    assert flow["gate2_result_summary"]["operator_readback"]["outcome"] == intent_ingest_gate.ACCEPTED_INTENT
    assert flow["gate3_package_summary"]["package_status"] == role_package_gate.PACKAGE_COMPILED
    assert flow["gate3_package_summary"]["operator_readback"]["gate4_readiness_state"] == "READY_FOR_GUARDIAN_OUTPUT_GATE"
    assert flow["gate4_result_summary"]["verdict"] == guardian_output_gate.VALIDATED
    assert flow["shadow_comparison_summary"]["failed"] == 0
    assert flow["shadow_comparison_summary"]["negative_case_count"] == 3
    assert payload["dashboard_summary"]["lm1_live"] == "NOT_ACTIVE"
    assert payload["dashboard_summary"]["lm2_live"] == "NOT_ACTIVE"
    assert payload["machine_proof"]["end_to_end_non_live_chain_passed"] is True
    assert payload["machine_proof"]["gate2_readback_operator_visible"] is True
    assert payload["machine_proof"]["gate3_readback_operator_visible"] is True


def test_private_mode_fields_are_seeded_but_inactive():
    payload = _payload()
    private_mode = payload["representative_flow"]["private_mode_readiness"]

    assert private_mode["private_mode_available"] is True
    assert private_mode["private_mode_active"] is False
    assert private_mode["strict_private_mode_available"] is True
    assert private_mode["strict_private_mode_active"] is False
    assert private_mode["cloud_lm_allowed_when_private"] is False
    assert private_mode["local_only_required_when_strict"] is True
    assert private_mode["production_token_vault_ready"] is True
    assert payload["machine_proof"]["private_mode_active"] is False
    assert payload["machine_proof"]["strict_private_mode_active"] is False


def test_exported_readmodel_parses(tmp_path):
    payload = _payload()
    json_path, operator_path = dashboard.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == dashboard.READ_MODEL_ID
    assert parsed["machine_proof"]["model_call_performed"] is False
    assert parsed["machine_proof"]["workbook_body_read_performed"] is False
    assert parsed["machine_proof"]["shadow_comparison_failed_count"] == 0
    assert "Live LM calls remain off" in operator_path.read_text(encoding="utf-8")
