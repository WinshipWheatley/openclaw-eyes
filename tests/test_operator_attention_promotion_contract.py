import json
import re
from pathlib import Path

import operator_attention_promotion_contract as contract


FIXED_NOW = "2026-05-22T20:00:00+00:00"


def _build() -> dict:
    return contract.build_operator_attention_promotion_contract(generated_at=FIXED_NOW)


def _records(payload: dict) -> dict:
    return {item["promotion_id"]: item for item in payload["default_records"]}


def test_contract_is_deterministic_and_classification_only():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == "DETERMINISTIC_NON_EXECUTING_PROMOTION_CLASSIFICATION"
    assert first["hard_rule"]["promotion_is_classification_not_execution"] is True
    assert first["hard_rule"]["may_run"] is False
    assert first["hard_rule"]["may_queue"] is False
    assert first["hard_rule"]["may_activate_agents"] is False


def test_lifecycle_destinations_and_attention_classes_exist():
    payload = _build()

    assert payload["promotion_lifecycle_states"] == list(contract.PROMOTION_LIFECYCLE_STATES)
    assert payload["promotion_destinations"] == list(contract.PROMOTION_DESTINATIONS)
    assert payload["attention_classes"] == list(contract.ATTENTION_CLASSES)
    assert payload["machine_proof"]["all_lifecycle_states_present"] is True
    assert payload["machine_proof"]["all_destinations_present"] is True
    assert payload["machine_proof"]["all_attention_classes_present"] is True
    for state in ["OBSERVED", "HELM_ATTENTION", "CUE_CANDIDATE", "QUIET_WITH_PROOF", "UNKNOWN_FAIL_CLOSED"]:
        assert state in payload["promotion_lifecycle_states"]
    for destination in ["HELM_ATTENTION", "SECURITY_DELTA_REVIEW", "CHIEF_RECONCILIATION", "QUIET_WITH_PROOF"]:
        assert destination in payload["promotion_destinations"]
    for attention_class in ["NEEDS_PROOF", "BUILT_NOT_SURFACED", "CUE_CANDIDATE", "QUIET_WITH_PROOF"]:
        assert attention_class in payload["attention_classes"]


def test_record_schema_and_default_records_exist():
    payload = _build()
    records = _records(payload)

    assert payload["operator_attention_promotion_record_schema"]["required_fields"] == list(contract.REQUIRED_RECORD_FIELDS)
    assert payload["machine_proof"]["default_record_count"] == 8
    assert set(records) == {
        "capital_hilton_proof_gap",
        "stable_map_receipt_current",
        "markdown_knowledge_atlas_visibility_gap",
        "future_invoicing_state_machine_audit",
        "autonomous_capital_pipeline_experiment",
        "orphaned_capability_found",
        "operator_missing_terrain_memory",
        "security_delta_needed_for_new_tool",
    }
    for record in records.values():
        assert set(contract.REQUIRED_RECORD_FIELDS) <= set(record)
        assert record["authority_granted"] is False


def test_capital_hilton_and_stable_map_examples_have_expected_destinations():
    records = _records(_build())

    capital = records["capital_hilton_proof_gap"]
    assert capital["attention_class"] == "NEEDS_PROOF"
    assert capital["promotion_destination"] == "HELM_ATTENTION"
    assert capital["world_id"] == "Finance"
    assert capital["guardian_review_required"] is True
    assert "no finance action authority" in capital["what_blocks_execution"]

    stable = records["stable_map_receipt_current"]
    assert stable["attention_class"] == "QUIET_WITH_PROOF"
    assert stable["current_lifecycle_state"] == "QUIET_WITH_PROOF"
    assert stable["promotion_destination"] == "PROOF_EVIDENCE_DRAWER"
    assert "raw mirror mismatch" in stable["next_safe_move"].lower()


def test_holding_cell_and_cue_candidate_rules_are_non_executing():
    payload = _build()
    rules = {item["rule_id"]: item for item in payload["promotion_decision_rules"]}

    assert rules["holding_cell"]["destination"] == "HOLDING_CELL"
    assert rules["holding_cell"]["executes"] is False
    assert rules["cue_candidate"]["destination"] == "CUE_CANDIDATE"
    assert rules["cue_candidate"]["executes"] is False
    assert payload["machine_proof"]["cue_candidates_not_executable"] is True
    assert payload["machine_proof"]["holding_cell_items_not_queued"] is True


def test_quiet_helm_policy_preserves_evidence_and_retrieval():
    payload = _build()
    policy = payload["quiet_helm_policy"]

    assert payload["machine_proof"]["quiet_helm_policy_present"] is True
    assert "does not mean forgotten" in policy["definition"]
    assert "proof drawer, holding cell, memory inbox, or lane drill-down" in policy["default_quiet_item"]["retrieval_path"]
    assert policy["default_quiet_item"]["operator_visibility_level"] == "summary_or_drill_down_not_helm_noise"
    assert payload["machine_proof"]["quiet_with_proof_preserves_evidence"] is True


def test_shared_fix_path_example_exists():
    payload = _build()
    shared_paths = {item["shared_fix_path_id"]: item for item in payload["shared_fix_paths"]}

    assert "protected_finance_proof_metadata_intake" in shared_paths
    path = shared_paths["protected_finance_proof_metadata_intake"]
    assert "Capital Hilton" in path["linked_lanes"]
    assert "Cassandra" in path["linked_lanes"]
    assert "Finance World" in path["linked_worlds"]
    assert "Guardian gate" in path["linked_gates"]
    assert path["solving_once_can_update_multiple_lanes"] is True
    assert path["updates_only_after_receipts_and_gates_exist"] is True
    assert path["executes"] is False
    assert payload["machine_proof"]["shared_fix_path_present"] is True


def test_operator_answer_capture_stays_candidate_not_proof():
    payload = _build()
    tie_in = payload["operator_answer_capture_tie_in"]
    operator_memory = _records(payload)["operator_missing_terrain_memory"]

    assert tie_in["operator_answers_are_memory_candidates"] is True
    assert tie_in["operator_answers_are_proof"] is False
    assert tie_in["capture_equals_action_authority"] is False
    assert "i_dont_know" in tie_in["valid_capture_outcomes"]
    assert "needs_discovery" in tie_in["valid_capture_outcomes"]
    assert operator_memory["promotion_destination"] == "MEMORY_CANDIDATE_INBOX"
    assert operator_memory["proof_status"] == "operator_answer_is_not_proof"
    assert payload["machine_proof"]["operator_answers_are_candidates_not_proof"] is True


def test_new_authority_routes_to_security_delta_or_fails_closed():
    payload = _build()
    relation = payload["relationship_to_security_delta"]
    security_delta = _records(payload)["security_delta_needed_for_new_tool"]

    assert relation["new_authority_routes_to_security_delta"] is True
    assert relation["new_tool_use_routes_to_security_delta"] is True
    assert relation["new_account_access_routes_to_security_delta"] is True
    assert relation["new_automation_routes_to_security_delta"] is True
    assert relation["new_runtime_behavior_routes_to_security_delta"] is True
    assert relation["new_financial_action_routes_to_security_delta"] is True
    assert relation["fail_closed_if_not_reviewed"] is True
    assert security_delta["promotion_destination"] == "SECURITY_DELTA_REVIEW"
    assert security_delta["security_delta_required"] is True
    assert security_delta["security_status"] == "fail_closed_until_reviewed"
    assert payload["machine_proof"]["new_authority_routes_to_security_delta_or_fail_closed"] is True


def test_no_action_authority_or_auto_promotion_is_granted():
    payload = _build()

    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert payload["machine_proof"]["action_authority_granted"] is False
    assert payload["machine_proof"]["auto_promotion_allowed"] is False
    assert payload["core_doctrine"]["breadcrumb_is_not_queued_work"] is True
    assert payload["core_doctrine"]["memory_candidate_is_not_proof"] is True
    assert payload["core_doctrine"]["cue_candidate_is_not_executable"] is True
    assert payload["core_doctrine"]["world_lane_is_not_action_authority"] is True


def test_no_credentials_or_raw_private_bodies_are_included():
    payload = _build()
    text = contract.stable_json(payload)

    assert payload["machine_proof"]["credentials_or_secrets_included"] is False
    assert payload["machine_proof"]["raw_private_bodies_included"] is False
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


def test_export_writes_json_and_operator_markdown(tmp_path):
    result = contract.export_operator_attention_promotion_contract(
        repo_root=tmp_path,
        export_root="generated/read_models",
        generated_at=FIXED_NOW,
    )
    json_path = Path(result.json_path)
    operator_path = Path(result.operator_path)

    assert json_path.exists()
    assert operator_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator_text = operator_path.read_text(encoding="utf-8")
    assert payload["contract_id"] == "operator_attention_promotion_contract_v0"
    assert payload["machine_proof"]["default_record_count"] == 8
    assert payload["machine_proof"]["action_authority_granted"] is False
    assert "ELIWINSHIP Summary" in operator_text
    assert "Quiet means classified, receipted, and retrievable" in operator_text
