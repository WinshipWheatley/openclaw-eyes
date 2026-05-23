import json
import re
from pathlib import Path

import automation_readiness_feasibility_evaluator_contract as contract
from scripts.export_automation_readiness_feasibility_evaluator_contract import main as export_main


FIXED_NOW = "2026-05-23T18:00:00+00:00"


def _build() -> dict:
    return contract.build_automation_readiness_feasibility_evaluator_contract(generated_at=FIXED_NOW)


def _assessments(payload: dict) -> dict:
    return payload["bottleneck_assessments_by_id"]


def _evaluations(payload: dict) -> dict:
    return payload["readiness_evaluations_by_id"]


def _infrastructure(payload: dict) -> dict:
    return payload["infrastructure_candidates_by_id"]


def _criteria(payload: dict) -> dict:
    return payload["dead_on_arrival_criteria_by_id"]


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["hard_rule"]["read_model_only"] is True
    assert first["hard_rule"]["does_not_execute_automation"] is True
    assert first["hard_rule"]["does_not_access_coupa_browser_network_or_accounts"] is True
    assert first["hard_rule"]["does_not_handle_credentials"] is True
    assert first["hard_rule"]["does_not_generate_invoice_or_email"] is True
    assert first["hard_rule"]["may_execute_automation_now"] is False
    assert first["hard_rule"]["may_access_external_system_now"] is False
    assert first["hard_rule"]["may_handle_credentials_now"] is False


def test_models_exist_with_required_fields_and_vocabularies():
    payload = _build()

    assert payload["machine_proof"]["bottleneck_assessment_model_present"] is True
    assert payload["machine_proof"]["readiness_evaluation_model_present"] is True
    assert payload["machine_proof"]["infrastructure_candidate_model_present"] is True
    assert payload["machine_proof"]["dead_on_arrival_criteria_present"] is True
    assert payload["automation_bottleneck_assessment_schema"]["required_fields"] == list(
        contract.REQUIRED_BOTTLENECK_ASSESSMENT_FIELDS
    )
    assert payload["automation_readiness_evaluation_schema"]["required_fields"] == list(
        contract.REQUIRED_READINESS_EVALUATION_FIELDS
    )
    assert payload["automation_infrastructure_candidate_schema"]["required_fields"] == list(
        contract.REQUIRED_INFRASTRUCTURE_CANDIDATE_FIELDS
    )
    assert payload["automation_dead_on_arrival_criterion_schema"]["required_fields"] == list(
        contract.REQUIRED_DEAD_ON_ARRIVAL_FIELDS
    )
    assert set(payload["automation_feasibility_values"]) == set(contract.AUTOMATION_FEASIBILITY)
    assert set(payload["automation_risk_values"]) == set(contract.AUTOMATION_RISK)
    assert set(payload["automation_recommendations"]) == set(contract.AUTOMATION_RECOMMENDATIONS)
    assert set(payload["infrastructure_types"]) == set(contract.INFRASTRUCTURE_TYPES)


def test_default_assessments_exist_and_include_required_bottlenecks():
    payload = _build()
    assessments = _assessments(payload)

    expected = {
        "capital_hilton_coupa_po_lookup_bottleneck",
        "capital_hilton_invoice_pdf_generation_bottleneck",
        "cassandra_email_send_bottleneck",
        "telegram_approval_split_brain_bottleneck",
        "work_terrain_consolidation_bottleneck",
        "check_engine_repair_bottleneck",
    }
    assert set(assessments) == expected
    for assessment_id, assessment in assessments.items():
        assert set(contract.REQUIRED_BOTTLENECK_ASSESSMENT_FIELDS) <= set(assessment), assessment_id
        assert assessment["automation_feasibility"] in contract.AUTOMATION_FEASIBILITY
        assert assessment["automation_risk"] in contract.AUTOMATION_RISK
        assert assessment["required_receipts"]
        assert assessment["next_safe_move"]
    assert payload["machine_proof"]["capital_hilton_coupa_po_bottleneck_present"] is True
    assert payload["machine_proof"]["telegram_approval_split_brain_bottleneck_present"] is True


def test_capital_hilton_coupa_po_lookup_bottleneck_models_fallback_and_future_path():
    coupa = _assessments(_build())["capital_hilton_coupa_po_lookup_bottleneck"]

    assert coupa["workflow_ref"] == "capital_hilton_invoice_workflow_session"
    assert coupa["world"] == "Finance"
    assert coupa["lane"] == "Capital Hilton"
    assert coupa["current_fallback"] == "guided manual capture"
    assert coupa["best_near_term_path"] == "build assisted capture first"
    assert "supervised/read-only automation" in coupa["best_future_path"]
    assert coupa["automation_feasibility"] == "ASSISTED_CAPTURE_FEASIBLE"
    assert coupa["automation_risk"] == "HIGH"
    assert "APPROVED_SITE_REGISTRY" in coupa["required_infrastructure"]
    assert "PROTECTED_CREDENTIAL_BROKER" in coupa["required_infrastructure"]
    assert "SUPERVISED_BROWSER_SESSION" in coupa["required_infrastructure"]
    assert "RECEIPT_WRITER" in coupa["required_infrastructure"]
    assert "Guardian review" in coupa["required_gates"]
    assert "automation trial receipt" in coupa["required_receipts"]
    assert "Do not access Coupa" in coupa["next_safe_move"]


def test_readiness_evaluations_model_future_gated_paths():
    payload = _build()
    evaluations = _evaluations(payload)
    coupa = evaluations["capital_hilton_coupa_po_lookup_readiness"]

    assert len(evaluations) == 4
    assert coupa["manual_fallback_available"] is True
    assert coupa["assisted_path_available"] is True
    assert coupa["supervised_path_candidate"] is True
    assert coupa["autonomous_path_candidate"] is False
    assert coupa["recommendation"] == "BUILD_ASSISTED_CAPTURE_NEXT"
    assert coupa["terms_or_compliance_unknown"] is True
    assert coupa["technical_feasibility_unknown"] is True
    assert "PROTECTED_CREDENTIAL_BROKER" in coupa["missing_infrastructure"]
    assert payload["automation_stage_policy"]["manual_fallback_treated_as_target"] is False
    assert payload["automation_stage_policy"]["supervised_path_future_gated"] is True
    assert payload["automation_stage_policy"]["autonomous_path_future_gated"] is True
    assert payload["automation_stage_policy"]["autonomous_path_candidate_grants_authority"] is False
    assert payload["machine_proof"]["manual_fallback_is_not_target"] is True
    assert payload["machine_proof"]["assisted_supervised_autonomous_paths_future_gated"] is True


def test_infrastructure_candidates_exist_and_grant_no_authority():
    payload = _build()
    candidates = _infrastructure(payload)

    expected = {
        "approved_site_registry",
        "protected_credential_broker",
        "supervised_browser_session",
        "read_only_portal_lookup",
        "capture_artifact_store",
        "receipt_writer",
        "approval_bus",
        "workflow_session_store",
        "source_card_registry",
        "protected_evidence_store",
    }
    assert set(candidates) == expected
    for candidate_id, candidate in candidates.items():
        assert set(contract.REQUIRED_INFRASTRUCTURE_CANDIDATE_FIELDS) <= set(candidate), candidate_id
        assert candidate["infrastructure_type"] in contract.INFRASTRUCTURE_TYPES
        assert candidate["current_authority_granted"] is False
        assert candidate["blocked_actions"]
    assert candidates["protected_credential_broker"]["infrastructure_type"] == "PROTECTED_CREDENTIAL_BROKER"
    assert candidates["approval_bus"]["infrastructure_type"] == "APPROVAL_BUS"


def test_dead_on_arrival_criteria_exist_and_stop_unsafe_automation():
    payload = _build()
    criteria = _criteria(payload)

    expected = {
        "credentials_cannot_be_handled_safely",
        "external_terms_prohibit_automation",
        "no_safe_read_only_path_exists",
        "portal_requires_uncontrolled_mutation_risk",
        "no_receipt_can_prove_no_mutation_occurred",
        "privacy_leakage_cannot_be_bounded",
        "operator_approval_cannot_be_made_atomic",
        "cost_complexity_exceeds_workflow_payoff",
        "external_system_changes_too_often",
        "legal_compliance_review_required",
    }
    assert set(criteria) == expected
    assert criteria["credentials_cannot_be_handled_safely"]["can_be_mitigated"] is True
    assert criteria["external_terms_prohibit_automation"]["can_be_mitigated"] is False
    assert criteria["operator_approval_cannot_be_made_atomic"]["mitigation_candidate"] == "APPROVAL_BUS"
    assert criteria["privacy_leakage_cannot_be_bounded"]["mitigation_candidate"] == "PROTECTED_EVIDENCE_STORE"
    for criterion_id, criterion in criteria.items():
        assert set(contract.REQUIRED_DEAD_ON_ARRIVAL_FIELDS) <= set(criterion), criterion_id
        assert criterion["operator_visibility"]
        assert criterion["next_safe_move"]
    assert payload["automation_stage_policy"]["dead_on_arrival_stops_build"] is True


def test_prior_lane_refs_are_represented_if_available():
    payload = _build()
    relationships = {item["lane_id"]: item for item in payload["relationship_to_prior_lanes"]}

    expected = {
        "operator_work_mode_schema_bandwidth_policy",
        "operator_solve_path_decision_node_contract",
        "guided_capture_protected_evidence_path_contract",
        "workflow_session_channel_projection_approval_bus_contract",
        "capital_hilton_coupa_po_retrieval_automation_candidate",
        "capital_hilton_proof_resolution_batch",
        "openclaw_work_terrain_reconciliation_batch",
        "security_pass_contract",
        "protected_access_broker_concept",
    }
    assert set(relationships) == expected
    for relationship in relationships.values():
        assert relationship["read_model_ref"]
        assert "without duplicating" in relationship["relationship"]
    assert payload["machine_proof"]["prior_lane_ref_count"] == len(expected)


def test_all_authority_flags_false_and_no_external_authority():
    payload = _build()
    text = contract.stable_json(payload)

    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    assert payload["authority_boundary"]["automation_execution_allowed"] is False
    assert payload["authority_boundary"]["supervised_browser_execution_allowed"] is False
    assert payload["authority_boundary"]["read_only_portal_lookup_allowed"] is False
    assert payload["authority_boundary"]["credential_broker_active"] is False
    assert payload["authority_boundary"]["credential_handling_allowed"] is False
    assert payload["authority_boundary"]["network_operation_allowed"] is False
    assert payload["authority_boundary"]["coupa_access_allowed"] is False
    assert payload["authority_boundary"]["browser_automation_allowed"] is False
    assert payload["authority_boundary"]["email_send_allowed"] is False
    assert payload["authority_boundary"]["invoice_generation_allowed"] is False
    assert payload["authority_boundary"]["ledger_write_allowed"] is False
    assert payload["authority_boundary"]["approval_submission_allowed"] is False
    assert payload["authority_boundary"]["model_call_allowed"] is False
    assert payload["authority_boundary"]["agent_activation_allowed"] is False
    assert payload["authority_boundary"]["tool_execution_allowed"] is False
    assert payload["authority_boundary"]["queue_execution_allowed"] is False
    assert payload["authority_boundary"]["runtime_dispatch_allowed"] is False
    assert payload["machine_proof"]["all_current_authority_flags_false"] is True
    assert payload["machine_proof"]["credential_handling_allowed"] is False
    assert payload["machine_proof"]["network_coupa_browser_authority"] is False
    assert payload["machine_proof"]["invoice_email_ledger_approval_authority"] is False
    assert payload["machine_proof"]["credentials_or_secrets_included"] is False
    assert payload["machine_proof"]["raw_private_bodies_included"] is False
    for pattern in [
        r"sk-[A-Za-z0-9_-]{20,}",
        r"xox[baprs]-[A-Za-z0-9-]{10,}",
        r"ghp_[A-Za-z0-9_]{20,}",
        r"AKIA[0-9A-Z]{16}",
        r"AIza[0-9A-Za-z_-]{20,}",
        r"BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY",
    ]:
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
        ]
    )

    assert result == 0
    json_path = tmp_path / "generated" / "read_models" / contract.JSON_EXPORT_NAME
    operator_path = tmp_path / "generated" / "read_models" / contract.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert payload["machine_proof"]["bottleneck_assessment_count"] == 6
    assert payload["machine_proof"]["capital_hilton_coupa_po_bottleneck_present"] is True
    assert payload["machine_proof"]["all_current_authority_flags_false"] is True
    assert "ELIWINSHIP Summary" in operator
    assert "Manual forever is not the goal" in operator
    assert "Coupa, browser, network, credentials, and automation remain blocked now" in operator


def test_source_has_no_disallowed_runtime_behavior():
    text = Path("automation_readiness_feasibility_evaluator_contract.py").read_text(
        encoding="utf-8"
    ).lower()
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
