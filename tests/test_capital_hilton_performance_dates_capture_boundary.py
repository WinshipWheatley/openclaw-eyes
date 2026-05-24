import json
import re
from pathlib import Path

import capital_hilton_performance_dates_capture_boundary as contract
from scripts.export_capital_hilton_performance_dates_capture_boundary import main as export_main


FIXED_NOW = "2026-05-24T12:00:00+00:00"


def _build() -> dict:
    return contract.build_capital_hilton_performance_dates_capture_boundary(generated_at=FIXED_NOW)


def _candidate(payload: dict) -> dict:
    return payload["capture_candidates_by_id"][
        "capital_hilton_performance_dates_may_22_29_capture_candidate"
    ]


def _target(payload: dict) -> dict:
    return payload["receipt_state_targets_by_id"][
        "capital_hilton_performance_dates_may_22_29_receipt_state_target"
    ]


def _impact(payload: dict) -> dict:
    return payload["downstream_impacts_by_id"][
        "capital_hilton_performance_dates_may_22_29_downstream_impact"
    ]


def test_contract_is_deterministic_and_non_executing():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["doctrine"]["summary"] == "Live draft workspace -> explicit capture boundary -> receipt-backed state later."
    assert first["hard_rule"]["read_model_only"] is True
    assert first["hard_rule"]["does_not_write_receipts"] is True
    assert first["hard_rule"]["does_not_mutate_workflow_state"] is True
    assert first["hard_rule"]["does_not_generate_invoice_artifacts"] is True
    assert first["hard_rule"]["does_not_create_email_drafts"] is True
    assert first["hard_rule"]["does_not_send_anything"] is True
    assert first["hard_rule"]["may_grant_authority"] is False


def test_models_and_required_fields_exist():
    payload = _build()

    assert payload["machine_proof"]["capture_candidate_model_present"] is True
    assert payload["machine_proof"]["date_normalization_rules_present"] is True
    assert payload["machine_proof"]["receipt_state_target_model_present"] is True
    assert payload["machine_proof"]["downstream_impact_model_present"] is True
    assert payload["capital_hilton_performance_dates_capture_candidate_schema"]["required_fields"] == list(
        contract.REQUIRED_CAPTURE_CANDIDATE_FIELDS
    )
    assert payload["performance_date_normalization_rule_schema"]["required_fields"] == list(
        contract.REQUIRED_NORMALIZATION_RULE_FIELDS
    )
    assert payload["performance_dates_receipt_state_target_schema"]["required_fields"] == list(
        contract.REQUIRED_RECEIPT_STATE_TARGET_FIELDS
    )
    assert payload["performance_dates_downstream_impact_schema"]["required_fields"] == list(
        contract.REQUIRED_DOWNSTREAM_IMPACT_FIELDS
    )
    assert set(payload["validation_statuses"]) == set(contract.VALIDATION_STATUSES)
    assert set(payload["receipt_types"]) == set(contract.RECEIPT_TYPES)


def test_capital_hilton_may_22_29_example_exists_and_keeps_state_distinct():
    payload = _build()
    candidate = _candidate(payload)
    example = payload["capital_hilton_example"]

    assert payload["machine_proof"]["capital_hilton_may_22_29_example_present"] is True
    assert set(contract.REQUIRED_CAPTURE_CANDIDATE_FIELDS) <= set(candidate)
    assert candidate["block_id"] == "performance_dates"
    assert candidate["current_openclaw_dates"] == ("2026-05-08", "2026-05-15")
    assert candidate["proposed_draft_dates"] == (
        "2026-05-08",
        "2026-05-15",
        "2026-05-22",
        "2026-05-29",
    )
    assert candidate["current_openclaw_dates"] != candidate["proposed_draft_dates"]
    assert candidate["added_dates"] == ("2026-05-22", "2026-05-29")
    assert candidate["removed_dates"] == ()
    assert candidate["duplicate_dates"] == ()
    assert candidate["invalid_dates"] == ()
    assert candidate["validation_status"] == "VALID_CAPTURE_CANDIDATE"
    assert candidate["operator_confirmation_required"] is True
    assert candidate["proof_still_required"] is True
    assert candidate["capture_ready"] is True
    assert example["draft_input"] == "May 22 and May 29"
    assert example["validation_status"] == "VALID_CAPTURE_CANDIDATE"
    assert payload["machine_proof"]["current_dates_and_draft_dates_distinct"] is True
    assert payload["machine_proof"]["added_dates_represented"] is True


def test_date_normalization_rules_cover_inferred_year_duplicate_invalid_and_ambiguous_policies():
    payload = _build()
    rule = payload["normalization_rules_by_id"]["capital_hilton_performance_date_normalization_rule"]

    assert set(contract.REQUIRED_NORMALIZATION_RULE_FIELDS) <= set(rule)
    assert "May 22 and May 29" in rule["input_examples"]
    assert "Infer 2026 from session context only" in rule["inferred_year_policy"]
    assert "ISO date YYYY-MM-DD" in rule["accepted_formats"]
    assert "impossible calendar dates" in rule["rejected_formats"]
    assert rule["duplicate_policy"] == "Flag duplicate dates in duplicate_dates and do not add them twice."
    assert "Ambiguous dates require clarification" in rule["ambiguity_policy"]
    assert payload["performance_date_normalization_rule_schema"]["normalization_writes_state"] is False
    assert payload["performance_date_normalization_rule_schema"]["ambiguous_dates_fail_closed"] is True
    assert payload["performance_date_normalization_rule_schema"]["duplicate_dates_flagged_not_added_twice"] is True
    assert payload["machine_proof"]["duplicate_policy_present"] is True
    assert payload["machine_proof"]["invalid_ambiguous_date_policy_present"] is True


def test_receipt_state_target_is_modeled_but_not_written():
    payload = _build()
    target = _target(payload)

    assert set(contract.REQUIRED_RECEIPT_STATE_TARGET_FIELDS) <= set(target)
    assert target["receipt_type"] == "OPERATOR_PERFORMANCE_DATES_ADDITION"
    assert target["required_validation_status"] == "VALID_CAPTURE_CANDIDATE"
    assert target["required_operator_action"] == "Use this draft"
    assert target["required_writer"] == "future_receipt_backed_workflow_state_writer"
    assert target["intended_state_update"]["to"] == (
        "2026-05-08",
        "2026-05-15",
        "2026-05-22",
        "2026-05-29",
    )
    assert "performance_date_2026_05_22_proof_candidate" in target["affected_proof_items"]
    assert "invoice_artifact_preview" in target["downstream_invalidations"]
    assert target["current_receipt_write_authority"] is False
    assert target["current_state_write_authority"] is False
    assert target["current_execution_authority"] is False
    assert payload["performance_dates_receipt_state_target_schema"]["receipt_state_target_only"] is True
    assert payload["performance_dates_receipt_state_target_schema"]["receipt_written_here"] is False
    assert payload["performance_dates_receipt_state_target_schema"]["workflow_state_mutated_here"] is False
    assert payload["machine_proof"]["receipt_state_write_execution_authority_false"] is True


def test_downstream_invoice_email_approval_effects_are_represented_and_locked():
    payload = _build()
    impact = _impact(payload)

    assert set(contract.REQUIRED_DOWNSTREAM_IMPACT_FIELDS) <= set(impact)
    assert "invoice packet date inputs would update" in impact["invoice_packet_effect"]
    assert "rate block is confirmed" in impact["invoice_subtotal_effect"]
    assert "No draft is created now" in impact["email_draft_effect"]
    assert "Approval packet remains locked" in impact["approval_packet_effect"]
    assert "operator confirmation is not external proof" in impact["proof_requirement_effect"]
    assert "four-date draft" in impact["coupa_po_effect"]
    assert "invoice_packet" in impact["stale_blocks"]
    assert "approval_packet_preview" in impact["stale_blocks"]
    assert "confirm_rate" in impact["next_blocks"]
    assert payload["performance_dates_downstream_impact_schema"]["invoice_generation_future_gated"] is True
    assert payload["performance_dates_downstream_impact_schema"]["email_draft_send_future_gated"] is True
    assert payload["performance_dates_downstream_impact_schema"]["approval_send_locked"] is True
    assert payload["machine_proof"]["downstream_invoice_email_approval_effects_represented"] is True


def test_relationships_to_existing_contracts_are_referenced_without_duplication():
    payload = _build()
    refs = payload["relationship_to_existing_contracts"]

    for key in [
        "workflow_block_intent_live_draft_contract",
        "agent_execution_packet_compiler_contract",
        "agent_conversation_handoff_step_packet_contract",
        "operator_solve_path_decision_node_contract",
        "workflow_session_channel_projection_approval_bus_contract",
        "capital_hilton_proof_resolution_batch",
        "capital_hilton_coupa_po_retrieval_automation_candidate",
        "automation_readiness_feasibility_evaluator_contract",
    ]:
        assert key in refs
        assert refs[key]["source_ref"].startswith("generated/read_models/")
    assert "consumes live draft performance_dates intent" in refs[
        "workflow_block_intent_live_draft_contract"
    ]["relationship"]
    assert "preserves proof requirements" in refs["capital_hilton_proof_resolution_batch"][
        "relationship"
    ]


def test_all_authority_flags_false_and_sensitive_access_blocked():
    payload = _build()
    boundary = payload["authority_boundary"]
    candidate = _candidate(payload)
    target = _target(payload)

    for key, value in contract.AUTHORITY_BOUNDARY.items():
        assert boundary[key] is False
        assert candidate["authority_boundary"][key] is False
    assert boundary["all_authority_flags_false"] is True
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert target["current_receipt_write_authority"] is False
    assert target["current_state_write_authority"] is False
    assert target["current_execution_authority"] is False
    for key in [
        "invoice_generation_allowed",
        "invoice_preview_render_allowed",
        "email_draft_allowed",
        "email_send_allowed",
        "approval_submission_allowed",
        "browser_automation_allowed",
        "coupa_access_allowed",
        "gmail_access_allowed",
        "telegram_send_allowed",
        "credential_handling_allowed",
        "model_call_allowed",
        "agent_activation_allowed",
        "tool_execution_allowed",
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
    assert summary["capture_candidate_count"] == 1
    assert summary["normalization_rule_count"] == 1
    assert summary["receipt_state_target_count"] == 1
    assert summary["downstream_impact_count"] == 1
    assert summary["action_authority_granted"] is False

    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    payload = json.loads(json_path.read_text())
    operator_text = operator_path.read_text()
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert "first backend capture boundary" in operator_text
    assert "It does not write the receipt yet." in operator_text
    assert "Adding May 22 and May 29 can become a valid capture candidate" in operator_text
    assert "Approval and send remain locked." in operator_text
