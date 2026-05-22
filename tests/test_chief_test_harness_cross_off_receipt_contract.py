import json
import re
from pathlib import Path

import chief_test_harness_cross_off_receipt_contract as contract


FIXED_NOW = "2026-05-22T21:00:00+00:00"


def _build() -> dict:
    return contract.build_chief_test_harness_cross_off_receipt_contract(generated_at=FIXED_NOW)


def _receipts(payload: dict) -> dict:
    return {item["receipt_id"]: item for item in payload["default_harness_receipts"]}


def _decisions(payload: dict) -> dict:
    return {item["cross_off_id"]: item for item in payload["default_cross_off_decisions"]}


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == "DETERMINISTIC_NON_EXECUTING_CHIEF_TEST_HARNESS_CROSS_OFF_RECEIPTS"
    assert first["core_doctrine"]["worker_said_done_is_not_enough"] is True
    assert first["core_doctrine"]["cross_off_is_not_deletion"] is True
    assert first["core_doctrine"]["chief_cannot_self_authorize"] is True


def test_completion_statuses_and_reconciliation_states_exist():
    payload = _build()

    assert payload["completion_statuses"] == list(contract.COMPLETION_STATUSES)
    assert payload["reconciliation_states"] == list(contract.RECONCILIATION_STATES)
    assert payload["machine_proof"]["all_completion_statuses_present"] is True
    assert payload["machine_proof"]["all_reconciliation_states_present"] is True
    for status in ["COMPLETED_WITH_PROOF", "PARTIAL_REQUEUE_REQUIRED", "FAILED_REPAIR_REQUIRED", "PARKED_WITH_PROOF", "QUARANTINED"]:
        assert status in payload["completion_statuses"]
    for state in ["MATCHED_TO_MARKDOWN_ITEM", "MATCHED_TO_RECEIPT", "BUILT_NOT_SURFACED", "RECONCILED_WITH_PROOF"]:
        assert state in payload["reconciliation_states"]


def test_default_examples_exist_and_have_schema_fields():
    payload = _build()
    receipts = _receipts(payload)

    assert payload["machine_proof"]["default_harness_receipt_count"] == 6
    assert set(receipts) == {
        "security_pass_surface_checkpoint",
        "security_pass_contract_pass_1",
        "markdown_knowledge_atlas_capability",
        "future_invoicing_state_machine_audit",
        "capital_hilton_finance_preview",
        "autonomous_capital_pipeline_experiment",
    }
    for receipt in receipts.values():
        assert set(payload["schemas"]["ChiefTestHarnessReceipt"]) <= set(receipt)


def test_cross_off_decision_records_do_not_allow_source_deletion_or_mutation():
    payload = _build()
    decisions = _decisions(payload)

    assert payload["cross_off_decisions"] == list(contract.CROSS_OFF_DECISIONS)
    assert payload["machine_proof"]["all_cross_off_decisions_present"] is True
    assert payload["machine_proof"]["cross_off_never_deletes_or_mutates_source"] is True
    for decision in decisions.values():
        assert decision["source_mutation_allowed"] is False
        assert decision["delete_source_allowed"] is False
        assert decision["archive_source_allowed"] is False
    assert decisions["security_pass_surface_checkpoint_cross_off"]["decision"] == "CROSS_OFF_ALLOWED_WITH_PROOF"
    assert decisions["future_invoicing_audit_cross_off"]["decision"] == "PARK_WITH_PROOF"


def test_automatic_cross_off_is_false_and_chief_cannot_self_authorize_or_execute_repairs():
    payload = _build()
    boundary = payload["chief_test_harness_boundary"]

    assert payload["hard_rules"]["automatic_cross_off_allowed"] is False
    assert payload["machine_proof"]["automatic_cross_off_allowed"] is False
    assert boundary["chief_self_authorization_allowed"] is False
    assert boundary["chief_repair_execution_allowed"] is False
    assert "run repairs automatically" in boundary["chief_may_not"]
    assert "delete source tasks" in boundary["chief_may_not"]
    assert payload["machine_proof"]["chief_self_authorization_allowed"] is False
    assert payload["machine_proof"]["chief_repair_execution_allowed"] is False


def test_repair_requeue_recommendations_do_not_queue_or_execute():
    payload = _build()
    recommendations = {item["recommendation_id"]: item for item in payload["default_repair_requeue_recommendations"]}

    assert payload["machine_proof"]["default_repair_requeue_count"] == 2
    assert payload["hard_rules"]["repair_requeue_is_recommendation_metadata_only"] is True
    assert payload["hard_rules"]["repair_requeue_executes"] is False
    for recommendation in recommendations.values():
        assert recommendation["can_run_unattended"] is False
        assert "contract only recommends" in recommendation["why_not_unattended"] or "Security Delta Review" in recommendation["why_not_unattended"]
    assert payload["machine_proof"]["repair_requeue_recommendations_do_not_execute"] is True


def test_quiet_with_proof_preserves_retrieval_path_and_proof_refs():
    payload = _build()
    quiet_receipts = {item["quiet_receipt_id"]: item for item in payload["default_quiet_with_proof_receipts"]}

    assert payload["machine_proof"]["default_quiet_receipt_count"] == 2
    assert payload["machine_proof"]["quiet_with_proof_preserves_retrieval_path_and_proof_refs"] is True
    for quiet in quiet_receipts.values():
        assert quiet["proof_refs"]
        assert quiet["retrieval_path"]
        assert quiet["evidence_drawer_ref"]
        assert quiet["authority_granted"] is False


def test_new_authority_routes_to_security_delta_and_full_trust_grants_no_execution():
    payload = _build()

    assert payload["relationship_to_security_delta"]["new_authority_routes_to_security_delta"] is True
    assert payload["relationship_to_security_delta"]["fail_closed_if_security_delta_missing"] is True
    assert payload["relationship_to_security_delta"]["repair_path_grants_new_authority"] is False
    assert payload["relationship_to_full_trust"]["full_trust_clearance_referenced_as_future_eligibility_state"] is True
    assert payload["relationship_to_full_trust"]["required_for_all_current_cross_off_examples"] is False
    assert payload["relationship_to_full_trust"]["full_trust_grants_execution_by_itself"] is False
    assert payload["machine_proof"]["new_authority_routes_to_security_delta"] is True


def test_completed_items_quiet_only_with_proof_and_partial_items_are_candidates():
    payload = _build()
    receipts = _receipts(payload)
    relation = payload["relationship_to_operator_attention_promotion"]

    assert relation["completed_with_proof"] == "quiet_with_proof"
    assert relation["partial"] == "requeue_candidate"
    assert relation["failed"] == "repair_required"
    assert relation["unsafe"] == "quarantine"
    assert receipts["security_pass_surface_checkpoint"]["completion_status"] == "COMPLETED_WITH_PROOF"
    assert receipts["security_pass_surface_checkpoint"]["quiet_with_proof_allowed"] is True
    assert receipts["future_invoicing_state_machine_audit"]["completion_status"] == "PARKED_WITH_PROOF"
    assert receipts["future_invoicing_state_machine_audit"]["park_required"] is True
    assert payload["machine_proof"]["completed_items_can_quiet_only_with_proof"] is True
    assert payload["machine_proof"]["failed_partial_items_are_candidates_only"] is True


def test_no_action_authority_is_granted():
    payload = _build()

    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert payload["machine_proof"]["action_authority_granted"] is False
    assert payload["authority_boundary"]["chief_self_authorization_allowed"] is False
    assert payload["authority_boundary"]["repair_execution_allowed"] is False
    assert payload["authority_boundary"]["queue_execution_allowed"] is False
    assert payload["authority_boundary"]["source_mutation_allowed"] is False
    assert payload["authority_boundary"]["delete_source_allowed"] is False


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
    result = contract.export_chief_test_harness_cross_off_receipt_contract(
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
    assert payload["contract_id"] == "chief_test_harness_cross_off_receipt_contract_v0"
    assert payload["machine_proof"]["default_harness_receipt_count"] == 6
    assert payload["machine_proof"]["action_authority_granted"] is False
    assert "ELIWINSHIP Summary" in operator_text
    assert "Cross-off never deletes the source note" in operator_text
