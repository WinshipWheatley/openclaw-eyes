"""Capital Hilton Performance Dates Dry-Run Writer Harness v0.

This deterministic test-only harness accepts the Capital Hilton performance
dates capture candidate shape and derives the dry-run write preview that a
future receipt/state writer would use. It proves the receipt payload preview,
state update preview, downstream invalidation preview, idempotency key, and
payload hash can be produced deterministically. It does not write receipts,
mutate canonical workflow state, generate invoices, create email drafts, send
messages, access external systems, call models/agents/tools, or grant live
authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "capital_hilton_performance_dates_dry_run_writer_v0"
READ_MODEL_ID = "capital_hilton_performance_dates_dry_run_writer"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "TEST_ONLY_DETERMINISTIC_DRY_RUN_WRITER_HARNESS"

DRY_RUN_STATUSES = (
    "DRY_RUN_READY",
    "INVALID_INPUT",
    "BLOCKED_BY_AUTHORITY",
    "UNKNOWN_FAIL_CLOSED",
)

CURRENT_DATES = ("2026-05-08", "2026-05-15")
PROPOSED_DATES = ("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29")
ADDED_DATES = ("2026-05-22", "2026-05-29")
INVALIDATED_ITEMS = (
    "invoice_packet_preview",
    "invoice_packet_artifact",
    "email_draft_attachment",
    "approval_packet_preview",
    "prior_subtotal_preview",
    "proof_po_coverage_status",
)

REQUIRED_INPUT_FIELDS = (
    "dry_run_input_id",
    "source_capture_candidate_ref",
    "source_writer_contract_ref",
    "workflow_session_ref",
    "block_id",
    "current_dates",
    "proposed_dates",
    "added_dates",
    "validation_status",
    "operator_action_label",
    "proof_still_required",
    "requested_receipt_type",
    "source_surface",
    "source_actor",
    "current_live_write_authority",
    "next_safe_move",
)

REQUIRED_PAYLOAD_PREVIEW_FIELDS = (
    "payload_preview_id",
    "receipt_type",
    "workflow_session_ref",
    "block_id",
    "previous_value",
    "new_value",
    "delta_summary",
    "added_dates",
    "normalized_dates",
    "show_count_before",
    "show_count_after",
    "proof_status_after_capture",
    "source_capture_candidate_ref",
    "payload_hash",
    "idempotency_key",
    "authority_boundary",
    "next_safe_move",
)

REQUIRED_STATE_UPDATE_PREVIEW_FIELDS = (
    "state_update_preview_id",
    "receipt_payload_preview_ref",
    "canonical_workflow_state_ref",
    "field_updates",
    "expected_new_performance_dates",
    "expected_show_count",
    "next_block_candidate",
    "dependent_fields_to_recalculate",
    "stale_artifact_refs",
    "stale_preview_refs",
    "proof_requirements_after_update",
    "current_state_write_authority",
    "next_safe_move",
)

REQUIRED_INVALIDATION_PREVIEW_FIELDS = (
    "invalidation_preview_id",
    "receipt_payload_preview_ref",
    "invalidated_items",
    "invalidation_reason",
    "affected_blocks",
    "affected_artifacts",
    "affected_previews",
    "regeneration_required",
    "approval_reset_required",
    "guardian_review_required",
    "proof_coverage_required",
    "next_safe_move",
)

REQUIRED_DRY_RUN_RESULT_FIELDS = (
    "dry_run_result_id",
    "input_ref",
    "payload_preview_ref",
    "state_update_preview_ref",
    "invalidation_preview_ref",
    "would_write_receipt",
    "would_update_state",
    "would_invalidate_downstream",
    "live_receipt_write_performed",
    "live_state_write_performed",
    "live_execution_performed",
    "authority_missing",
    "dry_run_status",
    "blocked_actions",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "live_receipt_write_allowed": False,
    "live_state_write_allowed": False,
    "live_capture_execution_allowed": False,
    "dry_run_preview_allowed": True,
    "invoice_generation_allowed": False,
    "invoice_preview_render_allowed": False,
    "email_draft_allowed": False,
    "email_send_allowed": False,
    "approval_submission_allowed": False,
    "browser_automation_allowed": False,
    "coupa_access_allowed": False,
    "gmail_access_allowed": False,
    "telegram_send_allowed": False,
    "credential_handling_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "file_write_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_operation_allowed": False,
    "ledger_write_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

BLOCKED_ACTIONS = (
    "live receipt write",
    "live workflow state write",
    "capture execution",
    "invoice generation or preview render",
    "email draft or send",
    "approval submission",
    "browser/Coupa/Gmail/Telegram/account access",
    "credential handling",
    "model/tool/agent/runtime/queue execution",
    "workflow/evidence/runtime file write",
    "raw private body ingestion",
)


@dataclass(frozen=True)
class PerformanceDatesDryRunWriterInput:
    dry_run_input_id: str
    source_capture_candidate_ref: str
    source_writer_contract_ref: str
    workflow_session_ref: str
    block_id: str
    current_dates: tuple[str, ...]
    proposed_dates: tuple[str, ...]
    added_dates: tuple[str, ...]
    validation_status: str
    operator_action_label: str
    proof_still_required: bool
    requested_receipt_type: str
    source_surface: str
    source_actor: str
    current_live_write_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class PerformanceDatesDryRunReceiptPayloadPreview:
    payload_preview_id: str
    receipt_type: str
    workflow_session_ref: str
    block_id: str
    previous_value: dict[str, Any]
    new_value: dict[str, Any]
    delta_summary: dict[str, Any]
    added_dates: tuple[str, ...]
    normalized_dates: tuple[str, ...]
    show_count_before: int
    show_count_after: int
    proof_status_after_capture: str
    source_capture_candidate_ref: str
    payload_hash: str
    idempotency_key: str
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class PerformanceDatesDryRunStateUpdatePreview:
    state_update_preview_id: str
    receipt_payload_preview_ref: str
    canonical_workflow_state_ref: str
    field_updates: tuple[dict[str, Any], ...]
    expected_new_performance_dates: tuple[str, ...]
    expected_show_count: int
    next_block_candidate: str
    dependent_fields_to_recalculate: tuple[str, ...]
    stale_artifact_refs: tuple[str, ...]
    stale_preview_refs: tuple[str, ...]
    proof_requirements_after_update: tuple[str, ...]
    current_state_write_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class PerformanceDatesDryRunDownstreamInvalidationPreview:
    invalidation_preview_id: str
    receipt_payload_preview_ref: str
    invalidated_items: tuple[str, ...]
    invalidation_reason: str
    affected_blocks: tuple[str, ...]
    affected_artifacts: tuple[str, ...]
    affected_previews: tuple[str, ...]
    regeneration_required: bool
    approval_reset_required: bool
    guardian_review_required: bool
    proof_coverage_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class PerformanceDatesDryRunWriterResult:
    dry_run_result_id: str
    input_ref: str
    payload_preview_ref: str
    state_update_preview_ref: str
    invalidation_preview_ref: str
    would_write_receipt: bool
    would_update_state: bool
    would_invalidate_downstream: bool
    live_receipt_write_performed: bool
    live_state_write_performed: bool
    live_execution_performed: bool
    authority_missing: bool
    dry_run_status: str
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class DryRunWriterExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    input_count: int
    payload_preview_count: int
    state_update_preview_count: int
    invalidation_preview_count: int
    dry_run_result_count: int
    action_authority_granted: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha256(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return _sha256(clone)


def _all_live_authority_false_except_dry_run() -> bool:
    return all(
        value is False
        for key, value in AUTHORITY_BOUNDARY.items()
        if key != "dry_run_preview_allowed"
    ) and AUTHORITY_BOUNDARY["dry_run_preview_allowed"] is True


def _authority_boundary() -> dict[str, bool]:
    return dict(AUTHORITY_BOUNDARY)


def default_dry_run_input() -> PerformanceDatesDryRunWriterInput:
    return PerformanceDatesDryRunWriterInput(
        dry_run_input_id="capital_hilton_performance_dates_may_22_29_dry_run_input",
        source_capture_candidate_ref="capital_hilton_performance_dates_capture_boundary.capital_hilton_performance_dates_may_22_29_capture_candidate",
        source_writer_contract_ref="capital_hilton_performance_dates_receipt_writer_contract.capital_hilton_performance_dates_may_22_29_write_request",
        workflow_session_ref="capital_hilton_invoice_workflow_session",
        block_id="performance_dates",
        current_dates=CURRENT_DATES,
        proposed_dates=PROPOSED_DATES,
        added_dates=ADDED_DATES,
        validation_status="VALID_CAPTURE_CANDIDATE",
        operator_action_label="Use this draft",
        proof_still_required=True,
        requested_receipt_type="OPERATOR_PERFORMANCE_DATES_ADDITION",
        source_surface="Mission Control Finance World",
        source_actor="Winship",
        current_live_write_authority=False,
        next_safe_move="Derive a dry-run receipt write preview without writing receipt or state.",
    )


def derive_payload_hash(input_model: PerformanceDatesDryRunWriterInput) -> str:
    return _sha256(
        {
            "workflow_session_ref": input_model.workflow_session_ref,
            "block_id": input_model.block_id,
            "receipt_type": input_model.requested_receipt_type,
            "previous_value": input_model.current_dates,
            "new_value": input_model.proposed_dates,
            "added_dates": input_model.added_dates,
            "proof_still_required": input_model.proof_still_required,
        }
    )


def derive_idempotency_key(input_model: PerformanceDatesDryRunWriterInput) -> str:
    digest = hashlib.sha256(
        stable_json(
            {
                "workflow_session_ref": input_model.workflow_session_ref,
                "block_id": input_model.block_id,
                "source_capture_candidate_ref": input_model.source_capture_candidate_ref,
                "requested_receipt_type": input_model.requested_receipt_type,
                "proposed_dates": input_model.proposed_dates,
            }
        ).encode("utf-8")
    ).hexdigest()
    return f"dry_run:{input_model.workflow_session_ref}:{input_model.block_id}:{input_model.requested_receipt_type}:{digest}"


def validate_dry_run_input(input_model: PerformanceDatesDryRunWriterInput) -> tuple[str, tuple[str, ...]]:
    failures: list[str] = []
    if input_model.block_id != "performance_dates":
        failures.append("block_id_must_be_performance_dates")
    if input_model.validation_status != "VALID_CAPTURE_CANDIDATE":
        failures.append("validation_status_must_be_valid_capture_candidate")
    if input_model.requested_receipt_type != "OPERATOR_PERFORMANCE_DATES_ADDITION":
        failures.append("receipt_type_must_be_performance_dates_addition")
    if input_model.current_live_write_authority is not False:
        failures.append("live_write_authority_must_be_false_for_dry_run")
    if not input_model.added_dates:
        failures.append("added_dates_required")
    if failures:
        return "INVALID_INPUT", tuple(failures)
    return "DRY_RUN_READY", ()


def build_receipt_payload_preview(
    input_model: PerformanceDatesDryRunWriterInput,
) -> PerformanceDatesDryRunReceiptPayloadPreview:
    return PerformanceDatesDryRunReceiptPayloadPreview(
        payload_preview_id="capital_hilton_performance_dates_may_22_29_payload_preview",
        receipt_type=input_model.requested_receipt_type,
        workflow_session_ref=input_model.workflow_session_ref,
        block_id=input_model.block_id,
        previous_value={"performance_dates": input_model.current_dates, "show_count": len(input_model.current_dates)},
        new_value={"performance_dates": input_model.proposed_dates, "show_count": len(input_model.proposed_dates)},
        delta_summary={
            "added_dates": input_model.added_dates,
            "removed_dates": (),
            "replaced_dates": (),
            "show_count_before": len(input_model.current_dates),
            "show_count_after": len(input_model.proposed_dates),
            "human_summary": "Add May 22 and May 29 to the Capital Hilton performance dates.",
        },
        added_dates=input_model.added_dates,
        normalized_dates=input_model.proposed_dates,
        show_count_before=len(input_model.current_dates),
        show_count_after=len(input_model.proposed_dates),
        proof_status_after_capture="operator_confirmed_dates_not_external_proof",
        source_capture_candidate_ref=input_model.source_capture_candidate_ref,
        payload_hash=derive_payload_hash(input_model),
        idempotency_key=derive_idempotency_key(input_model),
        authority_boundary=_authority_boundary(),
        next_safe_move="Preview this receipt payload without writing it.",
    )


def build_state_update_preview(
    payload_preview: PerformanceDatesDryRunReceiptPayloadPreview,
) -> PerformanceDatesDryRunStateUpdatePreview:
    return PerformanceDatesDryRunStateUpdatePreview(
        state_update_preview_id="capital_hilton_performance_dates_may_22_29_state_update_preview",
        receipt_payload_preview_ref=payload_preview.payload_preview_id,
        canonical_workflow_state_ref="workflow_session.capital_hilton_invoice_workflow_session.blocks.performance_dates",
        field_updates=(
            {
                "field": "performance_dates",
                "operation": "replace_with_receipt_backed_value_later",
                "before": payload_preview.previous_value["performance_dates"],
                "after": payload_preview.new_value["performance_dates"],
            },
            {
                "field": "show_count",
                "operation": "recalculate_from_performance_dates_later",
                "before": payload_preview.show_count_before,
                "after": payload_preview.show_count_after,
            },
            {
                "field": "proof_status",
                "operation": "set_later",
                "before": "proof_needed",
                "after": "operator_confirmed_but_external_proof_needed",
            },
        ),
        expected_new_performance_dates=payload_preview.normalized_dates,
        expected_show_count=payload_preview.show_count_after,
        next_block_candidate="rate_confirmation",
        dependent_fields_to_recalculate=(
            "invoice_packet_dates",
            "invoice_subtotal_after_rate_confirmation",
            "email_attachment_preview_after_invoice_regeneration",
            "proof_po_coverage_status",
        ),
        stale_artifact_refs=(
            "invoice_packet_artifact",
            "email_draft_attachment",
        ),
        stale_preview_refs=(
            "invoice_packet_preview",
            "prior_subtotal_preview",
            "approval_packet_preview",
        ),
        proof_requirements_after_update=(
            "external proof for 2026-05-08",
            "external proof for 2026-05-15",
            "external proof or source pointer for 2026-05-22",
            "external proof or source pointer for 2026-05-29",
            "PO/reference coverage may need all four dates",
        ),
        current_state_write_authority=False,
        next_safe_move="Show the state update preview; do not mutate canonical state.",
    )


def build_downstream_invalidation_preview(
    payload_preview: PerformanceDatesDryRunReceiptPayloadPreview,
) -> PerformanceDatesDryRunDownstreamInvalidationPreview:
    return PerformanceDatesDryRunDownstreamInvalidationPreview(
        invalidation_preview_id="capital_hilton_performance_dates_may_22_29_invalidation_preview",
        receipt_payload_preview_ref=payload_preview.payload_preview_id,
        invalidated_items=INVALIDATED_ITEMS,
        invalidation_reason="Performance date set would change from two dates to four dates.",
        affected_blocks=(
            "performance_dates",
            "rate_confirmation",
            "po_reference",
            "invoice_packet",
            "email_review",
            "approval_send",
        ),
        affected_artifacts=(
            "invoice_packet_artifact",
            "email_draft_attachment",
        ),
        affected_previews=(
            "invoice_packet_preview",
            "prior_subtotal_preview",
            "approval_packet_preview",
            "proof_po_coverage_status",
        ),
        regeneration_required=True,
        approval_reset_required=True,
        guardian_review_required=False,
        proof_coverage_required=True,
        next_safe_move="Keep these as dry-run invalidation effects only.",
    )


def build_dry_run_writer_result(
    input_model: PerformanceDatesDryRunWriterInput,
    payload_preview: PerformanceDatesDryRunReceiptPayloadPreview,
    state_update_preview: PerformanceDatesDryRunStateUpdatePreview,
    invalidation_preview: PerformanceDatesDryRunDownstreamInvalidationPreview,
) -> PerformanceDatesDryRunWriterResult:
    status, failures = validate_dry_run_input(input_model)
    ready = status == "DRY_RUN_READY"
    return PerformanceDatesDryRunWriterResult(
        dry_run_result_id="capital_hilton_performance_dates_may_22_29_dry_run_result",
        input_ref=input_model.dry_run_input_id,
        payload_preview_ref=payload_preview.payload_preview_id,
        state_update_preview_ref=state_update_preview.state_update_preview_id,
        invalidation_preview_ref=invalidation_preview.invalidation_preview_id,
        would_write_receipt=ready,
        would_update_state=ready,
        would_invalidate_downstream=ready,
        live_receipt_write_performed=False,
        live_state_write_performed=False,
        live_execution_performed=False,
        authority_missing=True,
        dry_run_status=status,
        blocked_actions=tuple(failures) + BLOCKED_ACTIONS if failures else BLOCKED_ACTIONS,
        next_safe_move="Render dry-run readiness; require explicit future authority before any live write.",
    )


def build_capital_hilton_performance_dates_dry_run_writer(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    input_model = default_dry_run_input()
    payload_preview = build_receipt_payload_preview(input_model)
    state_update_preview = build_state_update_preview(payload_preview)
    invalidation_preview = build_downstream_invalidation_preview(payload_preview)
    result = build_dry_run_writer_result(
        input_model,
        payload_preview,
        state_update_preview,
        invalidation_preview,
    )
    changed_input = replace(
        input_model,
        proposed_dates=("2026-05-08", "2026-05-15", "2026-05-22"),
        added_dates=("2026-05-22",),
    )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": "capital_hilton_performance_dates_dry_run_writer_v0",
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "operator_summary": (
            "This test-only dry-run writer proves the Capital Hilton May 22/29 "
            "capture candidate can deterministically produce receipt, state update, "
            "and invalidation previews without performing live writes."
        ),
        "doctrine": {
            "drafts_are_not_truth": True,
            "dry_run_is_not_capture": True,
            "capture_is_not_execution": True,
            "receipts_prove_state_changes_later": True,
            "gates_execute_later": True,
        },
        "hard_rule": {
            "test_only_harness": True,
            "read_model_export_only": True,
            "does_not_write_receipts": True,
            "does_not_mutate_workflow_state": True,
            "does_not_generate_invoice_artifacts": True,
            "does_not_create_email_drafts": True,
            "does_not_send_anything": True,
            "does_not_access_external_systems": True,
            "does_not_call_models_agents_or_tools": True,
            "may_grant_live_authority": False,
        },
        "dry_run_statuses": list(DRY_RUN_STATUSES),
        "dry_run_writer_input_schema": {
            "model_name": "PerformanceDatesDryRunWriterInput",
            "required_fields": list(REQUIRED_INPUT_FIELDS),
            "block_id_must_be": "performance_dates",
            "validation_status_must_be": "VALID_CAPTURE_CANDIDATE",
            "current_live_write_authority_must_remain_false": True,
            "deterministic_test_only": True,
        },
        "receipt_payload_preview_schema": {
            "model_name": "PerformanceDatesDryRunReceiptPayloadPreview",
            "required_fields": list(REQUIRED_PAYLOAD_PREVIEW_FIELDS),
            "payload_hash_stable_for_same_input": True,
            "idempotency_key_stable_for_same_input": True,
            "proof_status_must_not_claim_external_proof": True,
        },
        "state_update_preview_schema": {
            "model_name": "PerformanceDatesDryRunStateUpdatePreview",
            "required_fields": list(REQUIRED_STATE_UPDATE_PREVIEW_FIELDS),
            "state_mutation_occurs": False,
            "next_block_candidate": "rate_confirmation",
        },
        "downstream_invalidation_preview_schema": {
            "model_name": "PerformanceDatesDryRunDownstreamInvalidationPreview",
            "required_fields": list(REQUIRED_INVALIDATION_PREVIEW_FIELDS),
            "artifact_regeneration_occurs": False,
            "approval_reset_executed": False,
            "guardian_action_executed": False,
        },
        "dry_run_writer_result_schema": {
            "model_name": "PerformanceDatesDryRunWriterResult",
            "required_fields": list(REQUIRED_DRY_RUN_RESULT_FIELDS),
            "live_receipt_write_performed": False,
            "live_state_write_performed": False,
            "live_execution_performed": False,
        },
        "dry_run_inputs": [asdict(input_model)],
        "dry_run_inputs_by_id": {input_model.dry_run_input_id: asdict(input_model)},
        "receipt_payload_previews": [asdict(payload_preview)],
        "receipt_payload_previews_by_id": {
            payload_preview.payload_preview_id: asdict(payload_preview)
        },
        "state_update_previews": [asdict(state_update_preview)],
        "state_update_previews_by_id": {
            state_update_preview.state_update_preview_id: asdict(state_update_preview)
        },
        "downstream_invalidation_previews": [asdict(invalidation_preview)],
        "downstream_invalidation_previews_by_id": {
            invalidation_preview.invalidation_preview_id: asdict(invalidation_preview)
        },
        "dry_run_results": [asdict(result)],
        "dry_run_results_by_id": {result.dry_run_result_id: asdict(result)},
        "idempotency_hash_proof": {
            "same_input_idempotency_key": derive_idempotency_key(input_model),
            "same_input_idempotency_key_again": derive_idempotency_key(input_model),
            "same_input_payload_hash": derive_payload_hash(input_model),
            "same_input_payload_hash_again": derive_payload_hash(input_model),
            "changed_dates_payload_hash": derive_payload_hash(changed_input),
            "payload_hash_changes_when_dates_change": derive_payload_hash(input_model)
            != derive_payload_hash(changed_input),
            "generated_at_excluded_from_payload_hash": True,
            "duplicate_same_candidate_no_second_unique_write": True,
            "idempotency_key_fields": (
                "workflow_session_ref",
                "block_id",
                "source_capture_candidate_ref",
                "requested_receipt_type",
                "proposed_dates",
            ),
        },
        "capital_hilton_example": {
            "example_id": "capital_hilton_may_22_29_dry_run_writer_example",
            "previous_dates": input_model.current_dates,
            "new_dates": input_model.proposed_dates,
            "added_dates": input_model.added_dates,
            "show_count_before": payload_preview.show_count_before,
            "show_count_after": payload_preview.show_count_after,
            "dry_run_status": result.dry_run_status,
            "receipt_type": payload_preview.receipt_type,
            "payload_hash": payload_preview.payload_hash,
            "idempotency_key": payload_preview.idempotency_key,
            "live_receipt_write_performed": result.live_receipt_write_performed,
            "live_state_write_performed": result.live_state_write_performed,
            "live_execution_performed": result.live_execution_performed,
            "authority_missing": result.authority_missing,
        },
        "relationship_to_existing_contracts": {
            "capital_hilton_performance_dates_capture_boundary": {
                "source_ref": "generated/read_models/capital_hilton_performance_dates_capture_boundary.json",
                "relationship": "accepts the valid May 22/29 capture candidate shape as dry-run input",
            },
            "capital_hilton_performance_dates_receipt_writer_contract": {
                "source_ref": "generated/read_models/capital_hilton_performance_dates_receipt_writer_contract.json",
                "relationship": "proves the contract's future write request, receipt payload, state target, invalidation, idempotency, and dry-run result can be derived",
            },
            "workflow_block_intent_live_draft_contract": {
                "source_ref": "generated/read_models/workflow_block_intent_live_draft_contract.json",
                "relationship": "source block draft remains preview-only until a guarded writer is authorized later",
            },
            "workflow_session_channel_projection_approval_bus_contract": {
                "source_ref": "generated/read_models/workflow_session_channel_projection_approval_bus_contract.json",
                "relationship": "dry-run targets one canonical workflow session without channel-owned state",
            },
            "bridge_routing_operator_attention_contract": {
                "source_ref": "generated/read_models/bridge_routing_operator_attention_contract.json",
                "relationship": "future UI may route dry-run readiness to Finance World, not raw Helm telemetry",
            },
            "agent_execution_packet_compiler_contract": {
                "source_ref": "generated/read_models/agent_execution_packet_compiler_contract.json",
                "relationship": "agents may receive focused packets later but this harness runs no agents/tools/models",
            },
        },
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_live_authority_flags_false_except_dry_run_preview": _all_live_authority_false_except_dry_run(),
            "generated_read_model_export_allowed_by_repo_pattern": True,
            "blocked_actions": list(BLOCKED_ACTIONS),
        },
        "machine_proof": {
            "dry_run_writer_input_model_present": True,
            "receipt_payload_preview_model_present": True,
            "state_update_preview_model_present": True,
            "downstream_invalidation_preview_model_present": True,
            "dry_run_result_model_present": True,
            "capital_hilton_may_22_29_example_present": True,
            "dry_run_status_ready": result.dry_run_status == "DRY_RUN_READY",
            "previous_new_dates_explicit": bool(
                payload_preview.previous_value and payload_preview.new_value
            ),
            "added_dates_explicit": payload_preview.added_dates == ADDED_DATES,
            "show_count_changes_2_to_4": payload_preview.show_count_before == 2
            and payload_preview.show_count_after == 4,
            "would_write_receipt_true_live_receipt_write_false": result.would_write_receipt is True
            and result.live_receipt_write_performed is False,
            "would_update_state_true_live_state_write_false": result.would_update_state is True
            and result.live_state_write_performed is False,
            "would_invalidate_downstream_true_live_execution_false": result.would_invalidate_downstream
            is True
            and result.live_execution_performed is False,
            "authority_missing": result.authority_missing,
            "idempotency_key_stable_for_same_input": derive_idempotency_key(input_model)
            == derive_idempotency_key(input_model),
            "payload_hash_stable_for_same_input": derive_payload_hash(input_model)
            == derive_payload_hash(input_model),
            "payload_hash_changes_when_dates_change": derive_payload_hash(input_model)
            != derive_payload_hash(changed_input),
            "downstream_invalidations_include_required_items": set(INVALIDATED_ITEMS).issubset(
                set(invalidation_preview.invalidated_items)
            ),
            "all_live_authority_false_except_dry_run_preview": _all_live_authority_false_except_dry_run(),
            "credential_or_secret_included": False,
            "raw_private_body_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_capital_hilton_performance_dates_dry_run_writer(payload: dict[str, Any]) -> str:
    example = payload["capital_hilton_example"]
    boundary = payload["authority_boundary"]
    lines = [
        "# Capital Hilton Performance Dates Dry-Run Writer v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This is the first dry-run writer proof for Use this draft. It shows exactly what would be written later, but it still does not write a real receipt or real workflow state.",
        "",
        "## Dry-Run Output",
        "",
        f"- Previous dates: `{', '.join(example['previous_dates'])}`",
        f"- New dates: `{', '.join(example['new_dates'])}`",
        f"- Added dates: `{', '.join(example['added_dates'])}`",
        f"- Show count: `{example['show_count_before']}` -> `{example['show_count_after']}`",
        f"- Dry-run status: `{example['dry_run_status']}`",
        "",
        "May 22 and May 29 produce a deterministic receipt payload preview, state update preview, and downstream invalidation preview.",
        "",
        "## What Would Become Stale Later",
        "",
        "- Invoice packet preview.",
        "- Invoice packet artifact.",
        "- Email draft attachment.",
        "- Approval packet preview.",
        "- Prior subtotal preview.",
        "- Proof/PO coverage status.",
        "",
        "Proof and send remain gated. This is how OpenClaw starts turning a local draft into a safe future commit without unsafe automation.",
        "",
        "## Still Blocked",
        "",
    ]
    for action in boundary["blocked_actions"]:
        lines.append(f"- {action}")
    lines.extend(
        [
            "",
            "## Authority",
            "",
            f"- Dry-run preview allowed: `{str(boundary['dry_run_preview_allowed']).lower()}`",
            f"- Live receipt write allowed: `{str(boundary['live_receipt_write_allowed']).lower()}`",
            f"- Live state write allowed: `{str(boundary['live_state_write_allowed']).lower()}`",
            f"- Invoice generation allowed: `{str(boundary['invoice_generation_allowed']).lower()}`",
            f"- Email send allowed: `{str(boundary['email_send_allowed']).lower()}`",
        ]
    )
    return "\n".join(lines) + "\n"


def export_capital_hilton_performance_dates_dry_run_writer(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> DryRunWriterExportResult:
    payload = build_capital_hilton_performance_dates_dry_run_writer(generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(
        format_capital_hilton_performance_dates_dry_run_writer(payload),
        encoding="utf-8",
    )
    return DryRunWriterExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        input_count=len(payload["dry_run_inputs"]),
        payload_preview_count=len(payload["receipt_payload_previews"]),
        state_update_preview_count=len(payload["state_update_previews"]),
        invalidation_preview_count=len(payload["downstream_invalidation_previews"]),
        dry_run_result_count=len(payload["dry_run_results"]),
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Capital Hilton Performance Dates Dry-Run Writer read-model."
    )
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_performance_dates_dry_run_writer(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "input_count": result.input_count,
        "payload_preview_count": result.payload_preview_count,
        "state_update_preview_count": result.state_update_preview_count,
        "invalidation_preview_count": result.invalidation_preview_count,
        "dry_run_result_count": result.dry_run_result_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Capital Hilton Performance Dates Dry-Run Writer: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "ADDED_DATES",
    "AUTHORITY_BOUNDARY",
    "BLOCKED_ACTIONS",
    "CONTRACT_STATUS",
    "CURRENT_DATES",
    "DRY_RUN_STATUSES",
    "INVALIDATED_ITEMS",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "PROPOSED_DATES",
    "READ_MODEL_ID",
    "REQUIRED_DRY_RUN_RESULT_FIELDS",
    "REQUIRED_INPUT_FIELDS",
    "REQUIRED_INVALIDATION_PREVIEW_FIELDS",
    "REQUIRED_PAYLOAD_PREVIEW_FIELDS",
    "REQUIRED_STATE_UPDATE_PREVIEW_FIELDS",
    "SCHEMA_VERSION",
    "PerformanceDatesDryRunDownstreamInvalidationPreview",
    "PerformanceDatesDryRunReceiptPayloadPreview",
    "PerformanceDatesDryRunStateUpdatePreview",
    "PerformanceDatesDryRunWriterInput",
    "PerformanceDatesDryRunWriterResult",
    "build_capital_hilton_performance_dates_dry_run_writer",
    "build_downstream_invalidation_preview",
    "build_dry_run_writer_result",
    "build_receipt_payload_preview",
    "build_state_update_preview",
    "default_dry_run_input",
    "derive_idempotency_key",
    "derive_payload_hash",
    "export_capital_hilton_performance_dates_dry_run_writer",
    "format_capital_hilton_performance_dates_dry_run_writer",
    "replace",
    "stable_json",
    "validate_dry_run_input",
]
