import json
import re
from pathlib import Path

import capital_hilton_performance_dates_receipt_writer_contract as contract
from scripts.export_capital_hilton_performance_dates_receipt_writer_contract import (
    main as export_main,
)


FIXED_NOW = "2026-05-24T13:00:00+00:00"


def _build() -> dict:
    return contract.build_capital_hilton_performance_dates_receipt_writer_contract(
        generated_at=FIXED_NOW
    )


def _request(payload: dict) -> dict:
    return payload["write_requests_by_id"][
        "capital_hilton_performance_dates_may_22_29_write_request"
    ]


def _receipt(payload: dict) -> dict:
    return payload["receipt_payloads_by_id"][
        "capital_hilton_performance_dates_may_22_29_receipt_payload"
    ]


def _state_target(payload: dict) -> dict:
    return payload["state_update_targets_by_id"][
        "capital_hilton_performance_dates_may_22_29_state_update_target"
    ]


def _invalidation(payload: dict) -> dict:
    return payload["downstream_invalidations_by_id"][
        "capital_hilton_performance_dates_may_22_29_downstream_invalidation"
    ]


def _idempotency(payload: dict) -> dict:
    return payload["idempotency_policies_by_id"][
        "capital_hilton_performance_dates_receipt_idempotency_policy"
    ]


def _dry_run(payload: dict) -> dict:
    return payload["dry_run_write_results_by_id"][
        "capital_hilton_performance_dates_may_22_29_dry_run_write_result"
    ]


def test_contract_is_deterministic_and_dry_run_only():
    first = _build()
    second = _build()

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == contract.READ_MODEL_ID
    assert first["contract_status"] == contract.CONTRACT_STATUS
    assert first["doctrine"]["drafts_are_not_truth"] is True
    assert first["doctrine"]["capture_is_not_execution"] is True
    assert first["doctrine"]["receipts_prove_state_changes"] is True
    assert first["hard_rule"]["read_model_only"] is True
    assert first["hard_rule"]["dry_run_only"] is True
    assert first["hard_rule"]["does_not_write_receipts"] is True
    assert first["hard_rule"]["does_not_mutate_workflow_state"] is True
    assert first["hard_rule"]["does_not_generate_invoice_artifacts"] is True
    assert first["hard_rule"]["does_not_create_email_drafts"] is True
    assert first["hard_rule"]["does_not_send_anything"] is True
    assert first["hard_rule"]["may_grant_authority"] is False


def test_models_and_required_fields_exist():
    payload = _build()

    assert payload["machine_proof"]["receipt_write_request_model_present"] is True
    assert payload["machine_proof"]["receipt_payload_model_present"] is True
    assert payload["machine_proof"]["state_update_target_model_present"] is True
    assert payload["machine_proof"]["downstream_invalidation_model_present"] is True
    assert payload["machine_proof"]["idempotency_policy_present"] is True
    assert payload["machine_proof"]["dry_run_write_result_present"] is True
    assert payload["performance_dates_receipt_write_request_schema"]["required_fields"] == list(
        contract.REQUIRED_WRITE_REQUEST_FIELDS
    )
    assert payload["performance_dates_receipt_payload_schema"]["required_fields"] == list(
        contract.REQUIRED_RECEIPT_PAYLOAD_FIELDS
    )
    assert payload["performance_dates_workflow_state_update_target_schema"]["required_fields"] == list(
        contract.REQUIRED_STATE_UPDATE_TARGET_FIELDS
    )
    assert payload["performance_dates_downstream_invalidation_schema"]["required_fields"] == list(
        contract.REQUIRED_DOWNSTREAM_INVALIDATION_FIELDS
    )
    assert payload["performance_dates_idempotency_policy_schema"]["required_fields"] == list(
        contract.REQUIRED_IDEMPOTENCY_POLICY_FIELDS
    )
    assert payload["performance_dates_dry_run_write_result_schema"]["required_fields"] == list(
        contract.REQUIRED_DRY_RUN_RESULT_FIELDS
    )
    assert set(payload["receipt_types"]) == set(contract.RECEIPT_TYPES)


def test_write_request_targets_valid_performance_dates_candidate_without_authority():
    payload = _build()
    request = _request(payload)

    assert set(contract.REQUIRED_WRITE_REQUEST_FIELDS) <= set(request)
    assert request["block_id"] == "performance_dates"
    assert request["requested_receipt_type"] == "OPERATOR_PERFORMANCE_DATES_ADDITION"
    assert request["operator_action_label"] == "Use this draft"
    assert request["current_dates"] == ("2026-05-08", "2026-05-15")
    assert request["proposed_dates"] == (
        "2026-05-08",
        "2026-05-15",
        "2026-05-22",
        "2026-05-29",
    )
    assert request["added_dates"] == ("2026-05-22", "2026-05-29")
    assert request["validation_status_required"] == "VALID_CAPTURE_CANDIDATE"
    assert request["operator_confirmation_required"] is True
    assert request["proof_still_required"] is True
    assert request["idempotency_key"].startswith(
        "performance_dates:capital_hilton_invoice_workflow_session:"
    )
    assert request["payload_hash"].startswith("sha256:")
    assert "idempotency key has not already been consumed" in request["precondition_checks"]
    assert request["current_write_authority"] is False
    assert payload["performance_dates_receipt_write_request_schema"]["request_generates_invoice_email_send"] is False
    assert payload["machine_proof"]["validation_status_required_valid_capture_candidate"] is True


def test_receipt_payload_is_deterministic_and_explicit_without_external_proof_claim():
    payload = _build()
    request = _request(payload)
    receipt = _receipt(payload)

    assert set(contract.REQUIRED_RECEIPT_PAYLOAD_FIELDS) <= set(receipt)
    assert receipt["receipt_type"] == "OPERATOR_PERFORMANCE_DATES_ADDITION"
    assert receipt["block_id"] == "performance_dates"
    assert receipt["operator_decision"] == "Use this draft"
    assert receipt["previous_value"] == {
        "performance_dates": ("2026-05-08", "2026-05-15"),
        "show_count": 2,
    }
    assert receipt["new_value"] == {
        "performance_dates": (
            "2026-05-08",
            "2026-05-15",
            "2026-05-22",
            "2026-05-29",
        ),
        "show_count": 4,
    }
    assert receipt["delta_summary"]["added_dates"] == ("2026-05-22", "2026-05-29")
    assert receipt["delta_summary"]["previous_show_count"] == 2
    assert receipt["delta_summary"]["new_show_count"] == 4
    assert "May 22 and May 29" in receipt["delta_summary"]["human_summary"]
    assert receipt["proof_status_after_capture"] == "operator_confirmed_dates_not_external_proof"
    assert set(contract.INVALIDATED_ITEMS) <= set(receipt["downstream_invalidations"])
    assert receipt["payload_hash"] == request["payload_hash"]
    assert payload["performance_dates_receipt_payload_schema"]["previous_and_new_values_explicit"] is True
    assert payload["performance_dates_receipt_payload_schema"]["proof_status_must_not_claim_external_proof"] is True
    assert payload["machine_proof"]["receipt_type_is_addition"] is True
    assert payload["machine_proof"]["previous_new_values_explicit"] is True
    assert payload["machine_proof"]["added_dates_represented"] is True


def test_state_update_target_changes_show_count_and_marks_dependents_stale():
    payload = _build()
    target = _state_target(payload)

    assert set(contract.REQUIRED_STATE_UPDATE_TARGET_FIELDS) <= set(target)
    assert target["block_state_before"]["show_count"] == 2
    assert target["block_state_after"]["show_count"] == 4
    assert target["expected_new_performance_dates"] == (
        "2026-05-08",
        "2026-05-15",
        "2026-05-22",
        "2026-05-29",
    )
    assert target["expected_show_count"] == 4
    assert "invoice_subtotal_after_rate_confirmation" in target["dependent_fields_to_recalculate"]
    assert "invoice_packet_artifact" in target["stale_artifact_refs"]
    assert "email_draft_attachment" in target["stale_artifact_refs"]
    assert "invoice_packet_preview" in target["stale_preview_refs"]
    assert "approval_packet_preview" in target["stale_preview_refs"]
    assert "PO/reference coverage may need all four dates" in target["proof_requirements_after_update"]
    assert target["next_block_candidate"] == "rate_confirmation"
    assert target["current_state_write_authority"] is False
    assert payload["performance_dates_workflow_state_update_target_schema"]["mutates_state_in_this_lane"] is False
    assert payload["machine_proof"]["show_count_changes_from_2_to_4"] is True


def test_downstream_invalidation_includes_invoice_email_approval_subtotal_and_proof_po():
    payload = _build()
    invalidation = _invalidation(payload)

    assert set(contract.REQUIRED_DOWNSTREAM_INVALIDATION_FIELDS) <= set(invalidation)
    for item in [
        "invoice_packet_preview",
        "invoice_packet_artifact",
        "email_draft_attachment",
        "approval_packet_preview",
        "prior_subtotal_preview",
        "proof_po_coverage_status",
    ]:
        assert item in invalidation["invalidated_items"]
    assert invalidation["invalidation_reason"] == "Performance date set changed from two dates to four dates."
    assert invalidation["regeneration_required"] is True
    assert invalidation["approval_reset_required"] is True
    assert invalidation["guardian_review_required"] is False
    assert invalidation["proof_coverage_required"] is True
    assert payload["performance_dates_downstream_invalidation_schema"]["artifact_regeneration_happens_here"] is False
    assert payload["performance_dates_downstream_invalidation_schema"]["approval_send_readiness_resets_or_remains_locked"] is True
    assert payload["machine_proof"]["downstream_invalidations_include_required_items"] is True


def test_idempotency_policy_prevents_duplicate_receipts_and_conflicting_payloads():
    payload = _build()
    policy = _idempotency(payload)

    assert set(contract.REQUIRED_IDEMPOTENCY_POLICY_FIELDS) <= set(policy)
    assert "workflow_session_ref" in policy["idempotency_key_fields"]
    assert "proposed_dates" in policy["idempotency_key_fields"]
    assert "duplicate" in policy["duplicate_detection_policy"].lower()
    assert "existing receipt ref" in policy["duplicate_receipt_policy"]
    assert "must not duplicate downstream invalidations" in policy["same_payload_policy"]
    assert "requires a new correction/review path" in policy["conflicting_payload_policy"]
    assert "must not append duplicates" in policy["retry_policy"]
    assert payload["performance_dates_idempotency_policy_schema"]["duplicate_receipts_blocked"] is True
    assert payload["performance_dates_idempotency_policy_schema"]["same_payload_idempotent"] is True
    assert payload["machine_proof"]["idempotency_duplicate_policy_present"] is True


def test_dry_run_result_proves_future_write_shape_but_does_not_write_now():
    payload = _build()
    dry_run = _dry_run(payload)

    assert set(contract.REQUIRED_DRY_RUN_RESULT_FIELDS) <= set(dry_run)
    assert dry_run["would_write_receipt"] is True
    assert dry_run["would_update_state"] is True
    assert dry_run["would_invalidate_downstream"] is True
    assert dry_run["receipt_payload_preview_ref"] == "capital_hilton_performance_dates_may_22_29_receipt_payload"
    assert dry_run["state_update_preview_ref"] == "capital_hilton_performance_dates_may_22_29_state_update_target"
    assert dry_run["invalidation_preview_ref"] == "capital_hilton_performance_dates_may_22_29_downstream_invalidation"
    assert dry_run["authority_missing"] is True
    assert payload["performance_dates_dry_run_write_result_schema"]["dry_run_writes_receipt_or_state"] is False
    assert payload["performance_dates_dry_run_write_result_schema"]["suitable_for_use_this_draft_preview"] is True
    assert payload["machine_proof"]["dry_run_authority_missing"] is True


def test_capital_hilton_example_summarizes_required_outcome():
    payload = _build()
    example = payload["capital_hilton_example"]

    assert payload["machine_proof"]["capital_hilton_may_22_29_example_present"] is True
    assert example["previous_dates"] == ("2026-05-08", "2026-05-15")
    assert example["new_dates"] == (
        "2026-05-08",
        "2026-05-15",
        "2026-05-22",
        "2026-05-29",
    )
    assert example["added_dates"] == ("2026-05-22", "2026-05-29")
    assert example["receipt_type"] == "OPERATOR_PERFORMANCE_DATES_ADDITION"
    assert example["previous_show_count"] == 2
    assert example["new_show_count"] == 4
    assert example["invoice_packet_preview_becomes_stale"] is True
    assert example["subtotal_recalculates_later_after_rate_confirmation"] is True
    assert example["proof_po_coverage_may_need_four_date_coverage"] is True
    assert example["next_block_candidate"] == "rate_confirmation"
    assert example["no_invoice_email_send_action"] is True


def test_relationships_to_existing_contracts_are_referenced_without_duplication():
    payload = _build()
    refs = payload["relationship_to_existing_contracts"]

    for key in [
        "capital_hilton_performance_dates_capture_boundary",
        "workflow_block_intent_live_draft_contract",
        "workflow_session_channel_projection_approval_bus_contract",
        "agent_execution_packet_compiler_contract",
        "agent_conversation_handoff_step_packet_contract",
        "bridge_routing_operator_attention_contract",
        "capital_hilton_proof_resolution_batch",
        "capital_hilton_coupa_po_retrieval_automation_candidate",
    ]:
        assert key in refs
        assert refs[key]["source_ref"].startswith("generated/read_models/")
    assert "consumes the valid May 22/29 capture candidate" in refs[
        "capital_hilton_performance_dates_capture_boundary"
    ]["relationship"]
    assert "proof requirements remain active" in refs["capital_hilton_proof_resolution_batch"][
        "relationship"
    ]


def test_all_live_authority_flags_false_and_sensitive_access_blocked():
    payload = _build()
    boundary = payload["authority_boundary"]
    receipt = _receipt(payload)
    request = _request(payload)
    target = _state_target(payload)

    for key in contract.AUTHORITY_BOUNDARY:
        assert boundary[key] is False
        assert receipt["authority_boundary"][key] is False
    assert boundary["all_authority_flags_false"] is True
    assert request["current_write_authority"] is False
    assert target["current_state_write_authority"] is False
    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    assert payload["machine_proof"]["send_remains_locked"] is True
    for key in [
        "live_receipt_write_allowed",
        "live_state_write_allowed",
        "live_capture_execution_allowed",
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
    assert payload["performance_dates_receipt_payload_schema"]["raw_private_bodies_allowed"] is False
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
    assert summary["write_request_count"] == 1
    assert summary["receipt_payload_count"] == 1
    assert summary["state_update_target_count"] == 1
    assert summary["downstream_invalidation_count"] == 1
    assert summary["idempotency_policy_count"] == 1
    assert summary["dry_run_result_count"] == 1
    assert summary["action_authority_granted"] is False

    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    payload = json.loads(json_path.read_text())
    operator_text = operator_path.read_text()
    assert payload["read_model_id"] == contract.READ_MODEL_ID
    assert "first Use this draft backend landing zone" in operator_text
    assert "still does not write real state" in operator_text
    assert "May 22 and May 29 would become a deterministic addition receipt" in operator_text
    assert "Proof and send remain gated" in operator_text
