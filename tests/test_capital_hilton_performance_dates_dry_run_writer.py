import json
import re
from dataclasses import replace
from pathlib import Path

import capital_hilton_performance_dates_dry_run_writer as writer
from scripts.export_capital_hilton_performance_dates_dry_run_writer import main as export_main


FIXED_NOW = "2026-05-24T14:00:00+00:00"


def _build() -> dict:
    return writer.build_capital_hilton_performance_dates_dry_run_writer(generated_at=FIXED_NOW)


def _input(payload: dict) -> dict:
    return payload["dry_run_inputs_by_id"][
        "capital_hilton_performance_dates_may_22_29_dry_run_input"
    ]


def _payload_preview(payload: dict) -> dict:
    return payload["receipt_payload_previews_by_id"][
        "capital_hilton_performance_dates_may_22_29_payload_preview"
    ]


def _state_preview(payload: dict) -> dict:
    return payload["state_update_previews_by_id"][
        "capital_hilton_performance_dates_may_22_29_state_update_preview"
    ]


def _invalidation_preview(payload: dict) -> dict:
    return payload["downstream_invalidation_previews_by_id"][
        "capital_hilton_performance_dates_may_22_29_invalidation_preview"
    ]


def _result(payload: dict) -> dict:
    return payload["dry_run_results_by_id"][
        "capital_hilton_performance_dates_may_22_29_dry_run_result"
    ]


def test_harness_is_deterministic_and_test_only():
    first = _build()
    second = _build()

    assert writer.stable_json(first) == writer.stable_json(second)
    assert first["schema_version"] == writer.SCHEMA_VERSION
    assert first["read_model_id"] == writer.READ_MODEL_ID
    assert first["contract_status"] == writer.CONTRACT_STATUS
    assert first["doctrine"]["drafts_are_not_truth"] is True
    assert first["doctrine"]["dry_run_is_not_capture"] is True
    assert first["doctrine"]["capture_is_not_execution"] is True
    assert first["hard_rule"]["test_only_harness"] is True
    assert first["hard_rule"]["does_not_write_receipts"] is True
    assert first["hard_rule"]["does_not_mutate_workflow_state"] is True
    assert first["hard_rule"]["does_not_generate_invoice_artifacts"] is True
    assert first["hard_rule"]["does_not_create_email_drafts"] is True
    assert first["hard_rule"]["may_grant_live_authority"] is False


def test_models_and_required_fields_exist():
    payload = _build()

    assert payload["machine_proof"]["dry_run_writer_input_model_present"] is True
    assert payload["machine_proof"]["receipt_payload_preview_model_present"] is True
    assert payload["machine_proof"]["state_update_preview_model_present"] is True
    assert payload["machine_proof"]["downstream_invalidation_preview_model_present"] is True
    assert payload["machine_proof"]["dry_run_result_model_present"] is True
    assert payload["dry_run_writer_input_schema"]["required_fields"] == list(
        writer.REQUIRED_INPUT_FIELDS
    )
    assert payload["receipt_payload_preview_schema"]["required_fields"] == list(
        writer.REQUIRED_PAYLOAD_PREVIEW_FIELDS
    )
    assert payload["state_update_preview_schema"]["required_fields"] == list(
        writer.REQUIRED_STATE_UPDATE_PREVIEW_FIELDS
    )
    assert payload["downstream_invalidation_preview_schema"]["required_fields"] == list(
        writer.REQUIRED_INVALIDATION_PREVIEW_FIELDS
    )
    assert payload["dry_run_writer_result_schema"]["required_fields"] == list(
        writer.REQUIRED_DRY_RUN_RESULT_FIELDS
    )
    assert set(payload["dry_run_statuses"]) == set(writer.DRY_RUN_STATUSES)


def test_dry_run_input_is_valid_capital_hilton_performance_dates_shape():
    payload = _build()
    dry_input = _input(payload)

    assert set(writer.REQUIRED_INPUT_FIELDS) <= set(dry_input)
    assert dry_input["workflow_session_ref"] == "capital_hilton_invoice_workflow_session"
    assert dry_input["block_id"] == "performance_dates"
    assert dry_input["current_dates"] == ("2026-05-08", "2026-05-15")
    assert dry_input["proposed_dates"] == (
        "2026-05-08",
        "2026-05-15",
        "2026-05-22",
        "2026-05-29",
    )
    assert dry_input["added_dates"] == ("2026-05-22", "2026-05-29")
    assert dry_input["validation_status"] == "VALID_CAPTURE_CANDIDATE"
    assert dry_input["requested_receipt_type"] == "OPERATOR_PERFORMANCE_DATES_ADDITION"
    assert dry_input["operator_action_label"] == "Use this draft"
    assert dry_input["current_live_write_authority"] is False
    assert payload["dry_run_writer_input_schema"]["block_id_must_be"] == "performance_dates"
    assert payload["dry_run_writer_input_schema"]["deterministic_test_only"] is True


def test_receipt_payload_preview_is_derived_and_explicit():
    payload = _build()
    preview = _payload_preview(payload)

    assert set(writer.REQUIRED_PAYLOAD_PREVIEW_FIELDS) <= set(preview)
    assert preview["receipt_type"] == "OPERATOR_PERFORMANCE_DATES_ADDITION"
    assert preview["block_id"] == "performance_dates"
    assert preview["previous_value"] == {
        "performance_dates": ("2026-05-08", "2026-05-15"),
        "show_count": 2,
    }
    assert preview["new_value"] == {
        "performance_dates": (
            "2026-05-08",
            "2026-05-15",
            "2026-05-22",
            "2026-05-29",
        ),
        "show_count": 4,
    }
    assert preview["added_dates"] == ("2026-05-22", "2026-05-29")
    assert preview["normalized_dates"] == (
        "2026-05-08",
        "2026-05-15",
        "2026-05-22",
        "2026-05-29",
    )
    assert preview["show_count_before"] == 2
    assert preview["show_count_after"] == 4
    assert preview["proof_status_after_capture"] == "operator_confirmed_dates_not_external_proof"
    assert preview["payload_hash"].startswith("sha256:")
    assert preview["idempotency_key"].startswith(
        "dry_run:capital_hilton_invoice_workflow_session:performance_dates:"
    )
    assert payload["machine_proof"]["previous_new_dates_explicit"] is True
    assert payload["machine_proof"]["added_dates_explicit"] is True
    assert payload["machine_proof"]["show_count_changes_2_to_4"] is True


def test_state_update_preview_derives_expected_target_without_mutating_state():
    payload = _build()
    state = _state_preview(payload)

    assert set(writer.REQUIRED_STATE_UPDATE_PREVIEW_FIELDS) <= set(state)
    assert state["canonical_workflow_state_ref"] == (
        "workflow_session.capital_hilton_invoice_workflow_session.blocks.performance_dates"
    )
    assert state["expected_new_performance_dates"] == (
        "2026-05-08",
        "2026-05-15",
        "2026-05-22",
        "2026-05-29",
    )
    assert state["expected_show_count"] == 4
    assert state["next_block_candidate"] == "rate_confirmation"
    assert "invoice_subtotal_after_rate_confirmation" in state["dependent_fields_to_recalculate"]
    assert "invoice_packet_dates" in state["dependent_fields_to_recalculate"]
    assert "email_attachment_preview_after_invoice_regeneration" in state[
        "dependent_fields_to_recalculate"
    ]
    assert "invoice_packet_artifact" in state["stale_artifact_refs"]
    assert "email_draft_attachment" in state["stale_artifact_refs"]
    assert "approval_packet_preview" in state["stale_preview_refs"]
    assert "PO/reference coverage may need all four dates" in state[
        "proof_requirements_after_update"
    ]
    assert state["current_state_write_authority"] is False
    assert payload["state_update_preview_schema"]["state_mutation_occurs"] is False


def test_downstream_invalidation_preview_contains_required_items_without_execution():
    payload = _build()
    invalidation = _invalidation_preview(payload)

    assert set(writer.REQUIRED_INVALIDATION_PREVIEW_FIELDS) <= set(invalidation)
    for item in [
        "invoice_packet_preview",
        "invoice_packet_artifact",
        "email_draft_attachment",
        "approval_packet_preview",
        "prior_subtotal_preview",
        "proof_po_coverage_status",
    ]:
        assert item in invalidation["invalidated_items"]
    assert invalidation["regeneration_required"] is True
    assert invalidation["approval_reset_required"] is True
    assert invalidation["guardian_review_required"] is False
    assert invalidation["proof_coverage_required"] is True
    assert payload["downstream_invalidation_preview_schema"]["artifact_regeneration_occurs"] is False
    assert payload["downstream_invalidation_preview_schema"]["approval_reset_executed"] is False
    assert payload["downstream_invalidation_preview_schema"]["guardian_action_executed"] is False
    assert payload["machine_proof"]["downstream_invalidations_include_required_items"] is True


def test_dry_run_result_is_ready_but_performs_no_live_write_or_execution():
    payload = _build()
    result = _result(payload)

    assert set(writer.REQUIRED_DRY_RUN_RESULT_FIELDS) <= set(result)
    assert result["dry_run_status"] == "DRY_RUN_READY"
    assert result["would_write_receipt"] is True
    assert result["would_update_state"] is True
    assert result["would_invalidate_downstream"] is True
    assert result["live_receipt_write_performed"] is False
    assert result["live_state_write_performed"] is False
    assert result["live_execution_performed"] is False
    assert result["authority_missing"] is True
    assert payload["dry_run_writer_result_schema"]["live_receipt_write_performed"] is False
    assert payload["dry_run_writer_result_schema"]["live_state_write_performed"] is False
    assert payload["dry_run_writer_result_schema"]["live_execution_performed"] is False
    assert payload["machine_proof"]["dry_run_status_ready"] is True
    assert payload["machine_proof"]["would_write_receipt_true_live_receipt_write_false"] is True
    assert payload["machine_proof"]["would_update_state_true_live_state_write_false"] is True
    assert payload["machine_proof"]["would_invalidate_downstream_true_live_execution_false"] is True
    assert payload["machine_proof"]["authority_missing"] is True


def test_idempotency_and_payload_hash_are_stable_and_date_sensitive():
    input_model = writer.default_dry_run_input()
    changed_dates = replace(
        input_model,
        proposed_dates=("2026-05-08", "2026-05-15", "2026-05-22"),
        added_dates=("2026-05-22",),
    )

    assert writer.derive_idempotency_key(input_model) == writer.derive_idempotency_key(
        input_model
    )
    assert writer.derive_payload_hash(input_model) == writer.derive_payload_hash(input_model)
    assert writer.derive_payload_hash(input_model) != writer.derive_payload_hash(changed_dates)

    payload = _build()
    proof = payload["idempotency_hash_proof"]
    assert proof["same_input_idempotency_key"] == proof["same_input_idempotency_key_again"]
    assert proof["same_input_payload_hash"] == proof["same_input_payload_hash_again"]
    assert proof["payload_hash_changes_when_dates_change"] is True
    assert proof["generated_at_excluded_from_payload_hash"] is True
    assert proof["duplicate_same_candidate_no_second_unique_write"] is True
    assert payload["machine_proof"]["idempotency_key_stable_for_same_input"] is True
    assert payload["machine_proof"]["payload_hash_stable_for_same_input"] is True
    assert payload["machine_proof"]["payload_hash_changes_when_dates_change"] is True


def test_invalid_input_status_fails_closed():
    bad_input = replace(writer.default_dry_run_input(), block_id="rate")
    status, failures = writer.validate_dry_run_input(bad_input)
    payload_preview = writer.build_receipt_payload_preview(bad_input)
    state_preview = writer.build_state_update_preview(payload_preview)
    invalidation_preview = writer.build_downstream_invalidation_preview(payload_preview)
    result = writer.build_dry_run_writer_result(
        bad_input, payload_preview, state_preview, invalidation_preview
    )

    assert status == "INVALID_INPUT"
    assert "block_id_must_be_performance_dates" in failures
    assert result.dry_run_status == "INVALID_INPUT"
    assert result.would_write_receipt is False
    assert result.would_update_state is False
    assert result.would_invalidate_downstream is False
    assert result.live_receipt_write_performed is False
    assert result.live_state_write_performed is False
    assert result.live_execution_performed is False


def test_capital_hilton_example_matches_known_may_22_29_case():
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
    assert example["show_count_before"] == 2
    assert example["show_count_after"] == 4
    assert example["dry_run_status"] == "DRY_RUN_READY"
    assert example["receipt_type"] == "OPERATOR_PERFORMANCE_DATES_ADDITION"
    assert example["live_receipt_write_performed"] is False
    assert example["live_state_write_performed"] is False
    assert example["live_execution_performed"] is False
    assert example["authority_missing"] is True


def test_relationships_to_existing_contracts_are_referenced():
    payload = _build()
    refs = payload["relationship_to_existing_contracts"]

    for key in [
        "capital_hilton_performance_dates_capture_boundary",
        "capital_hilton_performance_dates_receipt_writer_contract",
        "workflow_block_intent_live_draft_contract",
        "workflow_session_channel_projection_approval_bus_contract",
        "bridge_routing_operator_attention_contract",
        "agent_execution_packet_compiler_contract",
    ]:
        assert key in refs
        assert refs[key]["source_ref"].startswith("generated/read_models/")
    assert "valid May 22/29 capture candidate" in refs[
        "capital_hilton_performance_dates_capture_boundary"
    ]["relationship"]
    assert "proves the contract's future write request" in refs[
        "capital_hilton_performance_dates_receipt_writer_contract"
    ]["relationship"]


def test_all_live_authority_false_except_dry_run_preview_allowed():
    payload = _build()
    boundary = payload["authority_boundary"]
    preview = _payload_preview(payload)
    result = _result(payload)

    for key, value in writer.AUTHORITY_BOUNDARY.items():
        if key == "dry_run_preview_allowed":
            assert boundary[key] is True
            assert preview["authority_boundary"][key] is True
        else:
            assert value is False
            assert boundary[key] is False
            assert preview["authority_boundary"][key] is False
    assert boundary["all_live_authority_flags_false_except_dry_run_preview"] is True
    assert payload["machine_proof"]["all_live_authority_false_except_dry_run_preview"] is True
    assert result["live_receipt_write_performed"] is False
    assert result["live_state_write_performed"] is False
    assert result["live_execution_performed"] is False
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
    serialized = writer.stable_json(payload)

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
    assert summary["schema_version"] == writer.SCHEMA_VERSION
    assert summary["input_count"] == 1
    assert summary["payload_preview_count"] == 1
    assert summary["state_update_preview_count"] == 1
    assert summary["invalidation_preview_count"] == 1
    assert summary["dry_run_result_count"] == 1
    assert summary["action_authority_granted"] is False

    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    payload = json.loads(json_path.read_text())
    operator_text = operator_path.read_text()
    assert payload["read_model_id"] == writer.READ_MODEL_ID
    assert "first dry-run writer proof for Use this draft" in operator_text
    assert "still does not write a real receipt or real workflow state" in operator_text
    assert "May 22 and May 29 produce a deterministic receipt payload preview" in operator_text
    assert "Proof and send remain gated" in operator_text
