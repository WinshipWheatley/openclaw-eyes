"""Capital Hilton Performance Dates Receipt Writer Contract v0.

This deterministic read-model defines the future receipt/state write target for
capturing the Capital Hilton performance dates block. It models the write
request, deterministic receipt payload, workflow state update target,
downstream invalidation record, idempotency policy, and dry-run write preview.
It does not write receipts, mutate canonical workflow state, generate invoices,
create email drafts, send messages, access external systems, call
models/agents/tools, or grant live authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "capital_hilton_performance_dates_receipt_writer_contract_v0"
READ_MODEL_ID = "capital_hilton_performance_dates_receipt_writer_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_RECEIPT_WRITER_TARGET_DRY_RUN_ONLY"

RECEIPT_TYPES = (
    "OPERATOR_PERFORMANCE_DATES_CONFIRMATION",
    "OPERATOR_PERFORMANCE_DATES_CORRECTION",
    "OPERATOR_PERFORMANCE_DATES_ADDITION",
    "OPERATOR_PERFORMANCE_DATES_REJECTION",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_WRITE_REQUEST_FIELDS = (
    "write_request_id",
    "source_capture_candidate_ref",
    "workflow_session_ref",
    "world",
    "lane",
    "block_id",
    "requested_receipt_type",
    "operator_action_label",
    "current_dates",
    "proposed_dates",
    "added_dates",
    "removed_dates",
    "replaced_dates",
    "validation_status_required",
    "operator_confirmation_required",
    "proof_still_required",
    "idempotency_key",
    "payload_hash",
    "precondition_checks",
    "blocked_actions",
    "current_write_authority",
    "next_safe_move",
)

REQUIRED_RECEIPT_PAYLOAD_FIELDS = (
    "receipt_payload_id",
    "receipt_type",
    "workflow_session_ref",
    "block_id",
    "operator_decision",
    "previous_value",
    "new_value",
    "delta_summary",
    "normalized_dates",
    "source_capture_candidate_ref",
    "source_draft_intent_ref",
    "created_from_surface",
    "created_from_actor",
    "proof_status_after_capture",
    "downstream_invalidations",
    "payload_hash",
    "authority_boundary",
    "next_safe_move",
)

REQUIRED_STATE_UPDATE_TARGET_FIELDS = (
    "state_update_target_id",
    "receipt_payload_ref",
    "canonical_workflow_state_ref",
    "block_state_before",
    "block_state_after",
    "field_updates",
    "expected_new_performance_dates",
    "expected_show_count",
    "dependent_fields_to_recalculate",
    "stale_artifact_refs",
    "stale_preview_refs",
    "proof_requirements_after_update",
    "next_block_candidate",
    "required_writer_component",
    "current_state_write_authority",
    "next_safe_move",
)

REQUIRED_DOWNSTREAM_INVALIDATION_FIELDS = (
    "invalidation_id",
    "receipt_payload_ref",
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

REQUIRED_IDEMPOTENCY_POLICY_FIELDS = (
    "policy_id",
    "idempotency_key_fields",
    "duplicate_detection_policy",
    "duplicate_receipt_policy",
    "same_payload_policy",
    "conflicting_payload_policy",
    "retry_policy",
    "next_safe_move",
)

REQUIRED_DRY_RUN_RESULT_FIELDS = (
    "dry_run_id",
    "write_request_ref",
    "would_write_receipt",
    "would_update_state",
    "would_invalidate_downstream",
    "receipt_payload_preview_ref",
    "state_update_preview_ref",
    "invalidation_preview_ref",
    "authority_missing",
    "blocked_actions",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "live_receipt_write_allowed": False,
    "live_state_write_allowed": False,
    "live_capture_execution_allowed": False,
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
    "file write or cleanup",
    "raw private body ingestion",
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


@dataclass(frozen=True)
class PerformanceDatesReceiptWriteRequest:
    write_request_id: str
    source_capture_candidate_ref: str
    workflow_session_ref: str
    world: str
    lane: str
    block_id: str
    requested_receipt_type: str
    operator_action_label: str
    current_dates: tuple[str, ...]
    proposed_dates: tuple[str, ...]
    added_dates: tuple[str, ...]
    removed_dates: tuple[str, ...]
    replaced_dates: tuple[dict[str, str], ...]
    validation_status_required: str
    operator_confirmation_required: bool
    proof_still_required: bool
    idempotency_key: str
    payload_hash: str
    precondition_checks: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    current_write_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class PerformanceDatesReceiptPayload:
    receipt_payload_id: str
    receipt_type: str
    workflow_session_ref: str
    block_id: str
    operator_decision: str
    previous_value: dict[str, Any]
    new_value: dict[str, Any]
    delta_summary: dict[str, Any]
    normalized_dates: tuple[str, ...]
    source_capture_candidate_ref: str
    source_draft_intent_ref: str
    created_from_surface: str
    created_from_actor: str
    proof_status_after_capture: str
    downstream_invalidations: tuple[str, ...]
    payload_hash: str
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class PerformanceDatesWorkflowStateUpdateTarget:
    state_update_target_id: str
    receipt_payload_ref: str
    canonical_workflow_state_ref: str
    block_state_before: dict[str, Any]
    block_state_after: dict[str, Any]
    field_updates: tuple[dict[str, Any], ...]
    expected_new_performance_dates: tuple[str, ...]
    expected_show_count: int
    dependent_fields_to_recalculate: tuple[str, ...]
    stale_artifact_refs: tuple[str, ...]
    stale_preview_refs: tuple[str, ...]
    proof_requirements_after_update: tuple[str, ...]
    next_block_candidate: str
    required_writer_component: str
    current_state_write_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class PerformanceDatesDownstreamInvalidation:
    invalidation_id: str
    receipt_payload_ref: str
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
class PerformanceDatesIdempotencyPolicy:
    policy_id: str
    idempotency_key_fields: tuple[str, ...]
    duplicate_detection_policy: str
    duplicate_receipt_policy: str
    same_payload_policy: str
    conflicting_payload_policy: str
    retry_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class PerformanceDatesDryRunWriteResult:
    dry_run_id: str
    write_request_ref: str
    would_write_receipt: bool
    would_update_state: bool
    would_invalidate_downstream: bool
    receipt_payload_preview_ref: str
    state_update_preview_ref: str
    invalidation_preview_ref: str
    authority_missing: bool
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class ReceiptWriterContractExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    write_request_count: int
    receipt_payload_count: int
    state_update_target_count: int
    downstream_invalidation_count: int
    idempotency_policy_count: int
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


def _all_authority_false() -> bool:
    return all(value is False for value in AUTHORITY_BOUNDARY.values())


def _authority_boundary() -> dict[str, bool]:
    return dict(AUTHORITY_BOUNDARY)


def _receipt_payload_hash() -> str:
    return _sha256(
        {
            "workflow_session_ref": "capital_hilton_invoice_workflow_session",
            "block_id": "performance_dates",
            "receipt_type": "OPERATOR_PERFORMANCE_DATES_ADDITION",
            "previous_value": CURRENT_DATES,
            "new_value": PROPOSED_DATES,
            "added_dates": ADDED_DATES,
            "proof_still_required": True,
        }
    )


def _idempotency_key() -> str:
    digest = hashlib.sha256(
        stable_json(
            {
                "workflow_session_ref": "capital_hilton_invoice_workflow_session",
                "block_id": "performance_dates",
                "source_capture_candidate_ref": "capital_hilton_performance_dates_may_22_29_capture_candidate",
                "requested_receipt_type": "OPERATOR_PERFORMANCE_DATES_ADDITION",
                "proposed_dates": PROPOSED_DATES,
            }
        ).encode("utf-8")
    ).hexdigest()
    return f"performance_dates:capital_hilton_invoice_workflow_session:{digest}"


def default_write_requests() -> tuple[PerformanceDatesReceiptWriteRequest, ...]:
    return (
        PerformanceDatesReceiptWriteRequest(
            write_request_id="capital_hilton_performance_dates_may_22_29_write_request",
            source_capture_candidate_ref="capital_hilton_performance_dates_capture_boundary.capital_hilton_performance_dates_may_22_29_capture_candidate",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            world="Finance",
            lane="Capital Hilton",
            block_id="performance_dates",
            requested_receipt_type="OPERATOR_PERFORMANCE_DATES_ADDITION",
            operator_action_label="Use this draft",
            current_dates=CURRENT_DATES,
            proposed_dates=PROPOSED_DATES,
            added_dates=ADDED_DATES,
            removed_dates=(),
            replaced_dates=(),
            validation_status_required="VALID_CAPTURE_CANDIDATE",
            operator_confirmation_required=True,
            proof_still_required=True,
            idempotency_key=_idempotency_key(),
            payload_hash=_receipt_payload_hash(),
            precondition_checks=(
                "source capture candidate exists",
                "source validation status is VALID_CAPTURE_CANDIDATE",
                "block_id is performance_dates",
                "current dates still match expected preimage",
                "proposed dates are normalized and ordered",
                "operator explicitly chose Use this draft",
                "idempotency key has not already been consumed",
            ),
            blocked_actions=BLOCKED_ACTIONS,
            current_write_authority=False,
            next_safe_move="Show a dry-run write preview; do not write until a future governed writer lane exists.",
        ),
    )


def default_receipt_payloads() -> tuple[PerformanceDatesReceiptPayload, ...]:
    return (
        PerformanceDatesReceiptPayload(
            receipt_payload_id="capital_hilton_performance_dates_may_22_29_receipt_payload",
            receipt_type="OPERATOR_PERFORMANCE_DATES_ADDITION",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            block_id="performance_dates",
            operator_decision="Use this draft",
            previous_value={"performance_dates": CURRENT_DATES, "show_count": 2},
            new_value={"performance_dates": PROPOSED_DATES, "show_count": 4},
            delta_summary={
                "added_dates": ADDED_DATES,
                "removed_dates": (),
                "replaced_dates": (),
                "previous_show_count": 2,
                "new_show_count": 4,
                "human_summary": "Add May 22 and May 29 to the Capital Hilton performance dates.",
            },
            normalized_dates=PROPOSED_DATES,
            source_capture_candidate_ref="capital_hilton_performance_dates_capture_boundary.capital_hilton_performance_dates_may_22_29_capture_candidate",
            source_draft_intent_ref="workflow_block_intent_live_draft_contract.capital_hilton_mission_control_performance_dates_draft",
            created_from_surface="Mission Control Finance World",
            created_from_actor="Winship",
            proof_status_after_capture="operator_confirmed_dates_not_external_proof",
            downstream_invalidations=INVALIDATED_ITEMS,
            payload_hash=_receipt_payload_hash(),
            authority_boundary=_authority_boundary(),
            next_safe_move="Future writer would store this receipt, then mark downstream previews stale.",
        ),
    )


def default_state_update_targets() -> tuple[PerformanceDatesWorkflowStateUpdateTarget, ...]:
    return (
        PerformanceDatesWorkflowStateUpdateTarget(
            state_update_target_id="capital_hilton_performance_dates_may_22_29_state_update_target",
            receipt_payload_ref="capital_hilton_performance_dates_may_22_29_receipt_payload",
            canonical_workflow_state_ref="workflow_session.capital_hilton_invoice_workflow_session.blocks.performance_dates",
            block_state_before={
                "block_id": "performance_dates",
                "status": "current_canonical_before_future_capture",
                "performance_dates": CURRENT_DATES,
                "show_count": 2,
            },
            block_state_after={
                "block_id": "performance_dates",
                "status": "operator_confirmed_after_future_capture",
                "performance_dates": PROPOSED_DATES,
                "show_count": 4,
                "proof_still_required": True,
            },
            field_updates=(
                {
                    "field": "performance_dates",
                    "operation": "replace_with_receipt_backed_value",
                    "before": CURRENT_DATES,
                    "after": PROPOSED_DATES,
                },
                {
                    "field": "show_count",
                    "operation": "recalculate_from_performance_dates",
                    "before": 2,
                    "after": 4,
                },
                {
                    "field": "proof_status",
                    "operation": "set",
                    "before": "proof_needed",
                    "after": "operator_confirmed_but_external_proof_needed",
                },
            ),
            expected_new_performance_dates=PROPOSED_DATES,
            expected_show_count=4,
            dependent_fields_to_recalculate=(
                "invoice_packet_dates",
                "invoice_subtotal_after_rate_confirmation",
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
            next_block_candidate="rate_confirmation",
            required_writer_component="future_receipt_backed_workflow_state_writer",
            current_state_write_authority=False,
            next_safe_move="After a future state write, route the operator to rate confirmation and proof coverage.",
        ),
    )


def default_downstream_invalidations() -> tuple[PerformanceDatesDownstreamInvalidation, ...]:
    return (
        PerformanceDatesDownstreamInvalidation(
            invalidation_id="capital_hilton_performance_dates_may_22_29_downstream_invalidation",
            receipt_payload_ref="capital_hilton_performance_dates_may_22_29_receipt_payload",
            invalidated_items=INVALIDATED_ITEMS,
            invalidation_reason="Performance date set changed from two dates to four dates.",
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
            next_safe_move="Keep invoice/email/approval previews stale until future regeneration and approval gates exist.",
        ),
    )


def default_idempotency_policies() -> tuple[PerformanceDatesIdempotencyPolicy, ...]:
    return (
        PerformanceDatesIdempotencyPolicy(
            policy_id="capital_hilton_performance_dates_receipt_idempotency_policy",
            idempotency_key_fields=(
                "workflow_session_ref",
                "block_id",
                "source_capture_candidate_ref",
                "requested_receipt_type",
                "proposed_dates",
            ),
            duplicate_detection_policy="Same workflow, block, candidate, receipt type, and proposed date set is a duplicate.",
            duplicate_receipt_policy="Future writer must return the existing receipt ref instead of writing another receipt.",
            same_payload_policy="Same payload hash is idempotent and must not duplicate downstream invalidations.",
            conflicting_payload_policy="Different proposed date set requires a new correction/review path before any write.",
            retry_policy="Retries may re-read the existing receipt/invalidation outcome but must not append duplicates.",
            next_safe_move="Use the idempotency key before any future receipt write.",
        ),
    )


def default_dry_run_results() -> tuple[PerformanceDatesDryRunWriteResult, ...]:
    return (
        PerformanceDatesDryRunWriteResult(
            dry_run_id="capital_hilton_performance_dates_may_22_29_dry_run_write_result",
            write_request_ref="capital_hilton_performance_dates_may_22_29_write_request",
            would_write_receipt=True,
            would_update_state=True,
            would_invalidate_downstream=True,
            receipt_payload_preview_ref="capital_hilton_performance_dates_may_22_29_receipt_payload",
            state_update_preview_ref="capital_hilton_performance_dates_may_22_29_state_update_target",
            invalidation_preview_ref="capital_hilton_performance_dates_may_22_29_downstream_invalidation",
            authority_missing=True,
            blocked_actions=BLOCKED_ACTIONS,
            next_safe_move="Display this as a Use this draft preview, not as a live write.",
        ),
    )


def build_capital_hilton_performance_dates_receipt_writer_contract(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    write_requests = default_write_requests()
    receipt_payloads = default_receipt_payloads()
    state_targets = default_state_update_targets()
    invalidations = default_downstream_invalidations()
    idempotency_policies = default_idempotency_policies()
    dry_runs = default_dry_run_results()

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": "capital_hilton_performance_dates_receipt_writer_contract_v0",
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "operator_summary": (
            "This is the first deterministic landing zone for a future Use this draft write. "
            "It defines the receipt payload, state update target, downstream invalidation, "
            "and idempotency rules for adding May 22 and May 29, but it does not write state."
        ),
        "doctrine": {
            "drafts_are_not_truth": True,
            "capture_is_not_execution": True,
            "receipts_prove_state_changes": True,
            "gates_execute_later": True,
            "summary": "Drafts are not truth. Capture is not execution. Receipts prove state changes. Gates execute later.",
        },
        "hard_rule": {
            "read_model_only": True,
            "dry_run_only": True,
            "does_not_write_receipts": True,
            "does_not_mutate_workflow_state": True,
            "does_not_generate_invoice_artifacts": True,
            "does_not_create_email_drafts": True,
            "does_not_send_anything": True,
            "does_not_access_external_systems": True,
            "does_not_call_models_agents_or_tools": True,
            "may_grant_authority": False,
        },
        "receipt_types": list(RECEIPT_TYPES),
        "performance_dates_receipt_write_request_schema": {
            "model_name": "PerformanceDatesReceiptWriteRequest",
            "required_fields": list(REQUIRED_WRITE_REQUEST_FIELDS),
            "block_id_must_be": "performance_dates",
            "validation_status_required_must_be": "VALID_CAPTURE_CANDIDATE",
            "current_write_authority_default": False,
            "idempotency_key_prevents_duplicate_additions": True,
            "payload_hash_binds_proposed_date_set": True,
            "request_generates_invoice_email_send": False,
        },
        "performance_dates_receipt_payload_schema": {
            "model_name": "PerformanceDatesReceiptPayload",
            "required_fields": list(REQUIRED_RECEIPT_PAYLOAD_FIELDS),
            "payload_is_deterministic": True,
            "previous_and_new_values_explicit": True,
            "proof_status_must_not_claim_external_proof": True,
            "raw_private_bodies_allowed": False,
        },
        "performance_dates_workflow_state_update_target_schema": {
            "model_name": "PerformanceDatesWorkflowStateUpdateTarget",
            "required_fields": list(REQUIRED_STATE_UPDATE_TARGET_FIELDS),
            "describes_future_state_update": True,
            "mutates_state_in_this_lane": False,
            "next_block_candidate_likely_rate_confirmation": True,
            "invoice_packet_and_email_attachment_stale_not_generated": True,
        },
        "performance_dates_downstream_invalidation_schema": {
            "model_name": "PerformanceDatesDownstreamInvalidation",
            "required_fields": list(REQUIRED_DOWNSTREAM_INVALIDATION_FIELDS),
            "artifact_regeneration_happens_here": False,
            "approval_send_readiness_resets_or_remains_locked": True,
            "guardian_send_approval_future_gated": True,
        },
        "performance_dates_idempotency_policy_schema": {
            "model_name": "PerformanceDatesIdempotencyPolicy",
            "required_fields": list(REQUIRED_IDEMPOTENCY_POLICY_FIELDS),
            "duplicate_receipts_blocked": True,
            "same_payload_idempotent": True,
            "conflicting_payload_requires_review": True,
        },
        "performance_dates_dry_run_write_result_schema": {
            "model_name": "PerformanceDatesDryRunWriteResult",
            "required_fields": list(REQUIRED_DRY_RUN_RESULT_FIELDS),
            "dry_run_writes_receipt_or_state": False,
            "suitable_for_use_this_draft_preview": True,
        },
        "write_requests": [asdict(item) for item in write_requests],
        "write_requests_by_id": {item.write_request_id: asdict(item) for item in write_requests},
        "receipt_payloads": [asdict(item) for item in receipt_payloads],
        "receipt_payloads_by_id": {
            item.receipt_payload_id: asdict(item) for item in receipt_payloads
        },
        "state_update_targets": [asdict(item) for item in state_targets],
        "state_update_targets_by_id": {
            item.state_update_target_id: asdict(item) for item in state_targets
        },
        "downstream_invalidations": [asdict(item) for item in invalidations],
        "downstream_invalidations_by_id": {
            item.invalidation_id: asdict(item) for item in invalidations
        },
        "idempotency_policies": [asdict(item) for item in idempotency_policies],
        "idempotency_policies_by_id": {
            item.policy_id: asdict(item) for item in idempotency_policies
        },
        "dry_run_write_results": [asdict(item) for item in dry_runs],
        "dry_run_write_results_by_id": {
            item.dry_run_id: asdict(item) for item in dry_runs
        },
        "capital_hilton_example": {
            "example_id": "capital_hilton_may_22_29_receipt_writer_example",
            "previous_dates": CURRENT_DATES,
            "new_dates": PROPOSED_DATES,
            "added_dates": ADDED_DATES,
            "receipt_type": "OPERATOR_PERFORMANCE_DATES_ADDITION",
            "previous_show_count": 2,
            "new_show_count": 4,
            "invoice_packet_preview_becomes_stale": True,
            "subtotal_recalculates_later_after_rate_confirmation": True,
            "proof_po_coverage_may_need_four_date_coverage": True,
            "next_block_candidate": "rate_confirmation",
            "no_invoice_email_send_action": True,
        },
        "relationship_to_existing_contracts": {
            "capital_hilton_performance_dates_capture_boundary": {
                "source_ref": "generated/read_models/capital_hilton_performance_dates_capture_boundary.json",
                "relationship": "consumes the valid May 22/29 capture candidate and turns it into deterministic future write targets",
            },
            "workflow_block_intent_live_draft_contract": {
                "source_ref": "generated/read_models/workflow_block_intent_live_draft_contract.json",
                "relationship": "source draft intent remains preview-only until explicit capture/write lane exists",
            },
            "workflow_session_channel_projection_approval_bus_contract": {
                "source_ref": "generated/read_models/workflow_session_channel_projection_approval_bus_contract.json",
                "relationship": "future state update targets one canonical workflow session, not channel-owned state",
            },
            "agent_execution_packet_compiler_contract": {
                "source_ref": "generated/read_models/agent_execution_packet_compiler_contract.json",
                "relationship": "agents may prepare focused support packets later but cannot write receipts",
            },
            "agent_conversation_handoff_step_packet_contract": {
                "source_ref": "generated/read_models/agent_conversation_handoff_step_packet_contract.json",
                "relationship": "future handoff may explain dry-run readiness without executing a write",
            },
            "bridge_routing_operator_attention_contract": {
                "source_ref": "generated/read_models/bridge_routing_operator_attention_contract.json",
                "relationship": "Bridge may route the Use this draft attention to Finance World without proof-wall promotion",
            },
            "capital_hilton_proof_resolution_batch": {
                "source_ref": "generated/read_models/capital_hilton_proof_resolution_batch_manifest.json",
                "relationship": "proof requirements remain active after operator date capture",
            },
            "capital_hilton_coupa_po_retrieval_automation_candidate": {
                "source_ref": "generated/read_models/capital_hilton_coupa_po_retrieval_automation_candidate.json",
                "relationship": "PO/reference coverage may need to cover the four-date set after future capture",
            },
        },
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_authority_flags_false": _all_authority_false(),
            "blocked_actions": list(BLOCKED_ACTIONS),
            "test_only_or_dry_run_writer_harness_used": False,
        },
        "machine_proof": {
            "receipt_write_request_model_present": True,
            "receipt_payload_model_present": True,
            "state_update_target_model_present": True,
            "downstream_invalidation_model_present": True,
            "idempotency_policy_present": True,
            "dry_run_write_result_present": True,
            "capital_hilton_may_22_29_example_present": True,
            "block_id_is_performance_dates": all(
                request.block_id == "performance_dates" for request in write_requests
            ),
            "validation_status_required_valid_capture_candidate": all(
                request.validation_status_required == "VALID_CAPTURE_CANDIDATE"
                for request in write_requests
            ),
            "receipt_type_is_addition": receipt_payloads[0].receipt_type
            == "OPERATOR_PERFORMANCE_DATES_ADDITION",
            "previous_new_values_explicit": bool(
                receipt_payloads[0].previous_value and receipt_payloads[0].new_value
            ),
            "added_dates_represented": receipt_payloads[0].delta_summary["added_dates"]
            == ADDED_DATES,
            "show_count_changes_from_2_to_4": (
                receipt_payloads[0].previous_value["show_count"] == 2
                and receipt_payloads[0].new_value["show_count"] == 4
                and state_targets[0].expected_show_count == 4
            ),
            "downstream_invalidations_include_required_items": set(INVALIDATED_ITEMS).issubset(
                set(invalidations[0].invalidated_items)
            ),
            "proof_still_required_after_capture": write_requests[0].proof_still_required,
            "send_remains_locked": AUTHORITY_BOUNDARY["email_send_allowed"] is False
            and AUTHORITY_BOUNDARY["approval_submission_allowed"] is False,
            "payload_hash_binds_proposed_dates": write_requests[0].payload_hash
            == receipt_payloads[0].payload_hash,
            "idempotency_duplicate_policy_present": bool(
                idempotency_policies[0].duplicate_receipt_policy
            ),
            "dry_run_authority_missing": dry_runs[0].authority_missing,
            "all_live_authority_flags_false": _all_authority_false(),
            "credential_or_secret_included": False,
            "raw_private_body_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_capital_hilton_performance_dates_receipt_writer_contract(payload: dict[str, Any]) -> str:
    example = payload["capital_hilton_example"]
    boundary = payload["authority_boundary"]
    lines = [
        "# Capital Hilton Performance Dates Receipt Writer Contract v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This is the first Use this draft backend landing zone. It still does not write real state. It defines the exact receipt payload, state update target, and stale-preview record a future writer would use.",
        "",
        "## What Would Be Captured Later",
        "",
        f"- Previous dates: `{', '.join(example['previous_dates'])}`",
        f"- New dates: `{', '.join(example['new_dates'])}`",
        f"- Added dates: `{', '.join(example['added_dates'])}`",
        f"- Receipt type: `{example['receipt_type']}`",
        f"- Show count: `{example['previous_show_count']}` -> `{example['new_show_count']}`",
        "",
        "May 22 and May 29 would become a deterministic addition receipt. The receipt would say exactly what changed, where it came from, and which previews became stale.",
        "",
        "## What Becomes Stale",
        "",
        "- Invoice packet preview.",
        "- Invoice packet artifact.",
        "- Email draft attachment.",
        "- Approval packet preview.",
        "- Prior subtotal preview.",
        "- Proof/PO coverage status.",
        "",
        "Subtotal recalculates later after rate confirmation. Proof and send remain gated. No invoice or email is generated here.",
        "",
        "## Why This Matters",
        "",
        "OpenClaw can make local drafts meaningful without unsafe automation: draft first, explicit capture second, receipt-backed state later, execution gates last.",
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
            f"- Live receipt write allowed: `{str(boundary['live_receipt_write_allowed']).lower()}`",
            f"- Live state write allowed: `{str(boundary['live_state_write_allowed']).lower()}`",
            f"- Invoice generation allowed: `{str(boundary['invoice_generation_allowed']).lower()}`",
            f"- Email send allowed: `{str(boundary['email_send_allowed']).lower()}`",
            f"- Test-only writer harness used: `{str(boundary['test_only_or_dry_run_writer_harness_used']).lower()}`",
        ]
    )
    return "\n".join(lines) + "\n"


def export_capital_hilton_performance_dates_receipt_writer_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ReceiptWriterContractExportResult:
    payload = build_capital_hilton_performance_dates_receipt_writer_contract(
        generated_at=generated_at
    )
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(
        format_capital_hilton_performance_dates_receipt_writer_contract(payload),
        encoding="utf-8",
    )
    return ReceiptWriterContractExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        write_request_count=len(payload["write_requests"]),
        receipt_payload_count=len(payload["receipt_payloads"]),
        state_update_target_count=len(payload["state_update_targets"]),
        downstream_invalidation_count=len(payload["downstream_invalidations"]),
        idempotency_policy_count=len(payload["idempotency_policies"]),
        dry_run_result_count=len(payload["dry_run_write_results"]),
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Capital Hilton Performance Dates Receipt Writer Contract read-model."
    )
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_performance_dates_receipt_writer_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "write_request_count": result.write_request_count,
        "receipt_payload_count": result.receipt_payload_count,
        "state_update_target_count": result.state_update_target_count,
        "downstream_invalidation_count": result.downstream_invalidation_count,
        "idempotency_policy_count": result.idempotency_policy_count,
        "dry_run_result_count": result.dry_run_result_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Capital Hilton Performance Dates Receipt Writer Contract: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "ADDED_DATES",
    "AUTHORITY_BOUNDARY",
    "BLOCKED_ACTIONS",
    "CONTRACT_STATUS",
    "CURRENT_DATES",
    "INVALIDATED_ITEMS",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "PROPOSED_DATES",
    "READ_MODEL_ID",
    "RECEIPT_TYPES",
    "REQUIRED_DOWNSTREAM_INVALIDATION_FIELDS",
    "REQUIRED_DRY_RUN_RESULT_FIELDS",
    "REQUIRED_IDEMPOTENCY_POLICY_FIELDS",
    "REQUIRED_RECEIPT_PAYLOAD_FIELDS",
    "REQUIRED_STATE_UPDATE_TARGET_FIELDS",
    "REQUIRED_WRITE_REQUEST_FIELDS",
    "SCHEMA_VERSION",
    "PerformanceDatesDownstreamInvalidation",
    "PerformanceDatesDryRunWriteResult",
    "PerformanceDatesIdempotencyPolicy",
    "PerformanceDatesReceiptPayload",
    "PerformanceDatesReceiptWriteRequest",
    "PerformanceDatesWorkflowStateUpdateTarget",
    "build_capital_hilton_performance_dates_receipt_writer_contract",
    "default_downstream_invalidations",
    "default_dry_run_results",
    "default_idempotency_policies",
    "default_receipt_payloads",
    "default_state_update_targets",
    "default_write_requests",
    "export_capital_hilton_performance_dates_receipt_writer_contract",
    "format_capital_hilton_performance_dates_receipt_writer_contract",
    "stable_json",
]
