import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import floor_gap_reconciliation as floor


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def _payload() -> dict:
    return floor.build_payload(generated_at=FIXED_NOW)


def test_floor_matrix_classifies_each_required_lane():
    payload = _payload()
    matrix = payload["floor_matrix"]

    assert payload["machine_proof"]["all_required_lanes_classified"] is True
    assert len(matrix) == 22
    for item in matrix:
        assert "lane_id" in item
        assert "maturity_label" in item
        assert "ready_for_live_review" in item
        assert "not_ready_reason" in item


def test_weak_lanes_are_identified_deterministically():
    payload = _payload()
    weakest_ids = [item["lane_id"] for item in payload["weakest_lanes"]]
    weakest_scores = [item["maturity_score"] for item in payload["weakest_lanes"]]

    assert payload["machine_proof"]["weak_lanes_identified"] is True
    assert weakest_scores == sorted(weakest_scores)
    assert "production_live_blockers" in {item["lane_id"] for item in payload["weakest_lanes"]}
    assert all(item["not_ready_reason"] for item in payload["weakest_lanes"])


def test_at_least_three_weak_lanes_get_floor_improvements():
    payload = _payload()
    raised_ids = {item["lane_id"] for item in payload["raised_this_pass"]}

    assert payload["machine_proof"]["raised_lane_count"] >= 3
    assert {
        "gate1_operational_snapshot",
        "live_lm_shadow_trial",
        "private_mode_readiness",
        "provider_activation_receipts",
        "read_model_mirror_visibility",
    }.issubset(raised_ids)
    assert payload["machine_proof"]["floor_was_uneven"] is True


def test_gate1_privacy_trigger_fixtures_exist():
    fixtures = floor.gate1_privacy_trigger_fixtures()
    by_input = {fixture["input_class"]: fixture for fixture in fixtures}

    assert by_input["normal"]["privacy_class"] == "LOW_METADATA"
    assert by_input["client_finance"]["tokenization_required"] is True
    assert by_input["legal_confidential"]["strict_local_only_required"] is True
    assert by_input["personal_private"]["private_mode_recommended"] is True
    assert by_input["strict_local_only"]["privacy_class"] == "STRICT_PRIVATE_CLIENT_METADATA"
    assert all(fixture["lm1_raw_values_allowed"] is False for fixture in fixtures)


def test_universal_intake_candidate_is_chain_compatible():
    payload = _payload()
    candidate = payload["universal_intake_chain_candidate"]

    assert candidate["lm1_chain_ready"] is True
    assert candidate["privacy_class"] == "CLIENT_FINANCE_FILE_METADATA"
    assert candidate["chain_contract"]["lm1_may_receive_raw_values"] is False
    assert candidate["submitted"] is False
    assert candidate["paid"] is False
    assert candidate["ledger_posted"] is False
    assert candidate["final"] is False


def test_lm1_package_consumes_intake_and_privacy_declarations():
    payload = _payload()
    package = payload["lm1_thread_context_package_ref"]

    assert package["tokenization_required"] is True
    assert package["privacy_classification"] == "CLIENT_FINANCE_FILE_METADATA"
    assert package["universal_intake_chain_contract"]["requires_tokenization_policy"] is True
    assert package["raw_values_included"] is False
    assert package["tools_allowed"] == ()
    assert package["read_model_ref"] == "generated/read_models/lm1_thread_context_package.json"
    assert package["ready_for_shadow"] is True
    assert package["gate1_operational_snapshot_ref"].startswith("gate1_operational_snapshot:")


def test_equalization_exports_low_beam_readiness_refs():
    payload = _payload()

    assert payload["gate1_privacy_request_readiness_ref"]["read_model_ref"] == "generated/read_models/gate1_privacy_request_readiness.json"
    assert payload["gate1_privacy_request_readiness_ref"]["lm1_may_receive_raw_values"] is False
    assert payload["gate1_operational_snapshot_ref"]["read_model_ref"] == "generated/read_models/gate1_operational_snapshot.json"
    assert payload["gate1_operational_snapshot_ref"]["capital_hilton_snapshot_safe_for_lm1"] is True
    assert payload["gate1_operational_snapshot_ref"]["privacy_policy_missing_blocks_lm1"] is True
    assert payload["request_response_bridge_readiness_ref"]["read_model_ref"] == "generated/read_models/request_response_bridge_readiness.json"
    assert payload["request_response_bridge_readiness_ref"]["scoped_response_filename_contract"] == "openclaw_response_for_mac_<source_request_id>.json"
    assert payload["machine_proof"]["gate1_privacy_readiness_exported"] is True
    assert payload["machine_proof"]["gate1_operational_snapshot_exported"] is True
    assert payload["machine_proof"]["gate1_operational_snapshot_connected"] is True
    assert payload["machine_proof"]["request_response_bridge_dashboard_visible"] is True
    assert payload["machine_proof"]["lm1_thread_context_package_exported"] is True
    assert payload["machine_proof"]["gate2_operator_readback_visible"] is True
    assert payload["machine_proof"]["gate3_operator_readback_visible"] is True
    assert payload["machine_proof"]["production_live_blockers_explicit"] is True
    assert payload["machine_proof"]["production_activation_beams_explicit"] is True
    assert payload["machine_proof"]["production_activation_beam_count"] == 7
    assert payload["machine_proof"]["activation_receipt_contract_count"] == 7
    assert payload["machine_proof"]["activation_receipt_contracts_ready"] is True
    assert payload["machine_proof"]["activation_receipt_fixtures_valid"] is True
    assert payload["machine_proof"]["activation_receipt_fixtures_satisfy_production"] is False
    assert payload["machine_proof"]["activation_receipt_substrate_contracts_backed"] is True
    assert payload["machine_proof"]["activation_receipt_substrate_fixtures_backed"] is True
    assert payload["machine_proof"]["activation_production_receipt_intake_ready"] is True
    assert payload["machine_proof"]["activation_production_receipt_writer_authority_free"] is True
    assert payload["machine_proof"]["activation_production_receipt_status_count"] == 7
    assert payload["machine_proof"]["activation_production_receipts_present_count"] == 0
    assert payload["machine_proof"]["activation_receipt_substrate_satisfies_production"] is False
    assert payload["machine_proof"]["live_lm_shadow_trial_exported"] is True
    assert payload["machine_proof"]["live_lm_shadow_trial_recorded"] is True
    assert payload["machine_proof"]["live_shadow_receipt_valid"] is True
    assert payload["machine_proof"]["provider_activation_receipts_required"] is True
    assert payload["machine_proof"]["shadow_provider_policy_receipt_present"] is True
    assert payload["machine_proof"]["shadow_model_selection_receipt_present"] is True
    assert payload["machine_proof"]["shadow_receipts_satisfy_production_activation"] is False
    assert payload["machine_proof"]["private_mode_policy_exported"] is True
    assert payload["machine_proof"]["read_model_mirror_visibility_no_sync_created"] is True


def test_floor_matrix_includes_v2_required_lanes():
    payload = _payload()
    lane_ids = {item["lane_id"] for item in payload["floor_matrix"]}

    assert {
        "provider_activation_receipts",
        "gate1_operational_snapshot",
        "live_lm_shadow_trial",
        "shadow_comparison",
        "tokenized_package_readiness",
        "read_model_mirror_visibility",
    }.issubset(lane_ids)
    assert payload["live_lm_activation_requirements_ref"]["live_lm1_activation_status"] == "NOT_READY"
    assert len(payload["live_lm_activation_requirements_ref"]["production_activation_beams"]) == 7
    beams = {item["beam_id"]: item for item in payload["live_lm_activation_requirements_ref"]["production_activation_beams"]}
    assert beams["real_lm_production_policy"]["receipt_types"] == (
        "real_lm1_production_policy_receipt",
        "real_lm2_production_policy_receipt",
    )
    assert {
        "device_trust_live_activation",
        "real_lm_production_policy",
    }.issubset(beams)
    assert len(payload["live_lm_activation_requirements_ref"]["activation_receipt_contracts"]) == 7
    assert payload["live_lm_activation_requirements_ref"]["activation_receipt_substrate"]["contracts_backed_by_sqlite"] is True
    assert payload["live_lm_activation_requirements_ref"]["activation_receipt_substrate"]["fixtures_backed_by_sqlite"] is True
    assert (
        payload["live_lm_activation_requirements_ref"]["activation_receipt_substrate"][
            "production_receipt_intake_ready"
        ]
        is True
    )
    assert payload["live_lm_activation_requirements_ref"]["activation_receipt_substrate"]["production_receipt_rows_present"] == 0
    assert payload["live_lm_activation_requirements_ref"]["activation_production_receipt_intake"]["metadata_only"] is True
    assert payload["live_lm_activation_requirements_ref"]["activation_production_receipt_intake"]["writer_authority_free"] is True
    assert len(payload["live_lm_activation_requirements_ref"]["activation_production_receipt_statuses"]) == 7
    assert payload["live_lm_activation_requirements_ref"]["live_shadow_receipt"]["present"] is True
    assert payload["live_lm_activation_requirements_ref"]["shadow_test_receipts"]["provider_policy_receipt"]["present"] is True
    assert (
        payload["live_lm_activation_requirements_ref"]["shadow_test_receipts"]["provider_policy_receipt"][
            "satisfies_production_activation"
        ]
        is False
    )
    assert payload["live_lm_shadow_trial_ref"]["trial_status"] == "LIVE_SHADOW_PASSED"
    assert payload["private_mode_policy_readiness_ref"]["private_mode_active"] is False
    assert payload["read_model_mirror_visibility_ref"]["new_sync_system_created"] is False


def test_tokenization_proof_does_not_leak_synthetic_raw_values():
    payload = _payload()
    proof_text = json.dumps(payload["tokenization_proof"], sort_keys=True)

    assert payload["tokenization_proof"]["raw_values_exported"] is False
    for raw in ("Synthetic Example Person", "synthetic.person@example.invalid", "555-0100", "000123456789", "00-0000000"):
        assert raw not in proof_text


def test_negative_shadow_cases_remain_blocked_or_clarified():
    payload = _payload()
    shadow = payload["shadow_negative_case_summary"]

    assert shadow["negative_case_count"] == 3
    assert shadow["negative_cases_passed"] is True
    assert shadow["shadow_comparison_failed_count"] == 0


def test_dashboard_stays_live_lm_not_active():
    payload = _payload()
    honesty = payload["dashboard_honesty"]

    assert honesty["lm1_live"] == "NOT_ACTIVE"
    assert honesty["lm2_live"] == "NOT_ACTIVE"


def test_exported_readmodel_parses(tmp_path):
    payload = _payload()
    json_path, operator_path = floor.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == floor.READ_MODEL_ID
    assert parsed["machine_proof"]["live_model_call_performed"] is False
    assert "Raised this pass:" in operator_path.read_text(encoding="utf-8")
