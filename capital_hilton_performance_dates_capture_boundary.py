"""Capital Hilton Performance Dates Capture Boundary Contract v0.

This deterministic read-model defines the first narrow capture boundary for
the Capital Hilton performance dates workflow block. It models what would be
validated, what receipt/state target a future writer would need, and which
downstream previews become stale. It does not write receipts, mutate canonical
workflow state, generate invoices, create email drafts, send messages, access
external systems, call models/agents/tools, or grant live authority.
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

SCHEMA_VERSION = "capital_hilton_performance_dates_capture_boundary_v0"
READ_MODEL_ID = "capital_hilton_performance_dates_capture_boundary"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_CAPTURE_BOUNDARY_TARGET_ONLY"

VALIDATION_STATUSES = (
    "VALID_CAPTURE_CANDIDATE",
    "NEEDS_CLARIFICATION",
    "DUPLICATE_ONLY_NO_CHANGE",
    "INVALID_DATE_INPUT",
    "NEEDS_PROOF_BEFORE_FINAL_SEND",
    "BLOCKED_BY_AUTHORITY",
    "UNKNOWN_FAIL_CLOSED",
)

RECEIPT_TYPES = (
    "OPERATOR_PERFORMANCE_DATES_CONFIRMATION",
    "OPERATOR_PERFORMANCE_DATES_CORRECTION",
    "OPERATOR_PERFORMANCE_DATES_ADDITION",
    "OPERATOR_PERFORMANCE_DATES_REJECTION",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_CAPTURE_CANDIDATE_FIELDS = (
    "capture_candidate_id",
    "workflow_session_ref",
    "world",
    "lane",
    "block_id",
    "block_label",
    "source_draft_intent_ref",
    "current_openclaw_dates",
    "proposed_draft_dates",
    "added_dates",
    "removed_dates",
    "replaced_dates",
    "normalized_dates",
    "duplicate_dates",
    "invalid_dates",
    "ambiguity_flags",
    "validation_status",
    "operator_confirmation_required",
    "proof_still_required",
    "receipt_target_ref",
    "affected_downstream_refs",
    "authority_boundary",
    "capture_ready",
    "blocked_actions",
    "next_safe_move",
)

REQUIRED_NORMALIZATION_RULE_FIELDS = (
    "rule_id",
    "input_examples",
    "inferred_year_policy",
    "accepted_formats",
    "rejected_formats",
    "duplicate_policy",
    "ordering_policy",
    "ambiguity_policy",
    "out_of_range_policy",
    "timezone_policy",
    "next_safe_move",
)

REQUIRED_RECEIPT_STATE_TARGET_FIELDS = (
    "receipt_state_target_id",
    "capture_candidate_ref",
    "receipt_type",
    "intended_state_update",
    "canonical_workflow_state_ref",
    "affected_block_ref",
    "affected_proof_items",
    "downstream_invalidations",
    "stale_artifact_refs",
    "required_writer",
    "required_validation_status",
    "required_operator_action",
    "required_guardian_review",
    "current_receipt_write_authority",
    "current_state_write_authority",
    "current_execution_authority",
    "next_safe_move",
)

REQUIRED_DOWNSTREAM_IMPACT_FIELDS = (
    "impact_id",
    "capture_candidate_ref",
    "invoice_packet_effect",
    "invoice_subtotal_effect",
    "email_draft_effect",
    "approval_packet_effect",
    "proof_requirement_effect",
    "coupa_po_effect",
    "affected_blocks",
    "stale_blocks",
    "next_blocks",
    "blocked_actions",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "receipt_write_allowed": False,
    "state_write_allowed": False,
    "capture_execution_allowed": False,
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
    "receipt write",
    "canonical workflow state write",
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


@dataclass(frozen=True)
class CapitalHiltonPerformanceDatesCaptureCandidate:
    capture_candidate_id: str
    workflow_session_ref: str
    world: str
    lane: str
    block_id: str
    block_label: str
    source_draft_intent_ref: str
    current_openclaw_dates: tuple[str, ...]
    proposed_draft_dates: tuple[str, ...]
    added_dates: tuple[str, ...]
    removed_dates: tuple[str, ...]
    replaced_dates: tuple[dict[str, str], ...]
    normalized_dates: tuple[str, ...]
    duplicate_dates: tuple[str, ...]
    invalid_dates: tuple[str, ...]
    ambiguity_flags: tuple[str, ...]
    validation_status: str
    operator_confirmation_required: bool
    proof_still_required: bool
    receipt_target_ref: str
    affected_downstream_refs: tuple[str, ...]
    authority_boundary: dict[str, bool]
    capture_ready: bool
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class PerformanceDateNormalizationRule:
    rule_id: str
    input_examples: tuple[str, ...]
    inferred_year_policy: str
    accepted_formats: tuple[str, ...]
    rejected_formats: tuple[str, ...]
    duplicate_policy: str
    ordering_policy: str
    ambiguity_policy: str
    out_of_range_policy: str
    timezone_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class PerformanceDatesReceiptStateTarget:
    receipt_state_target_id: str
    capture_candidate_ref: str
    receipt_type: str
    intended_state_update: dict[str, Any]
    canonical_workflow_state_ref: str
    affected_block_ref: str
    affected_proof_items: tuple[str, ...]
    downstream_invalidations: tuple[str, ...]
    stale_artifact_refs: tuple[str, ...]
    required_writer: str
    required_validation_status: str
    required_operator_action: str
    required_guardian_review: bool
    current_receipt_write_authority: bool
    current_state_write_authority: bool
    current_execution_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class PerformanceDatesDownstreamImpact:
    impact_id: str
    capture_candidate_ref: str
    invoice_packet_effect: str
    invoice_subtotal_effect: str
    email_draft_effect: str
    approval_packet_effect: str
    proof_requirement_effect: str
    coupa_po_effect: str
    affected_blocks: tuple[str, ...]
    stale_blocks: tuple[str, ...]
    next_blocks: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class PerformanceDatesCaptureBoundaryExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    capture_candidate_count: int
    normalization_rule_count: int
    receipt_state_target_count: int
    downstream_impact_count: int
    action_authority_granted: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _all_authority_false() -> bool:
    return all(value is False for value in AUTHORITY_BOUNDARY.values())


def _authority_boundary() -> dict[str, bool]:
    return dict(AUTHORITY_BOUNDARY)


def default_capture_candidates() -> tuple[CapitalHiltonPerformanceDatesCaptureCandidate, ...]:
    return (
        CapitalHiltonPerformanceDatesCaptureCandidate(
            capture_candidate_id="capital_hilton_performance_dates_may_22_29_capture_candidate",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            world="Finance",
            lane="Capital Hilton",
            block_id="performance_dates",
            block_label="Performance dates",
            source_draft_intent_ref="workflow_block_intent_live_draft_contract.capital_hilton_mission_control_performance_dates_draft",
            current_openclaw_dates=("2026-05-08", "2026-05-15"),
            proposed_draft_dates=("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29"),
            added_dates=("2026-05-22", "2026-05-29"),
            removed_dates=(),
            replaced_dates=(),
            normalized_dates=("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29"),
            duplicate_dates=(),
            invalid_dates=(),
            ambiguity_flags=(),
            validation_status="VALID_CAPTURE_CANDIDATE",
            operator_confirmation_required=True,
            proof_still_required=True,
            receipt_target_ref="capital_hilton_performance_dates_may_22_29_receipt_state_target",
            affected_downstream_refs=(
                "capital_hilton_invoice_packet_dates",
                "capital_hilton_invoice_subtotal_preview",
                "capital_hilton_email_attachment_preview",
                "capital_hilton_approval_packet_preview",
                "capital_hilton_po_proof_coverage",
            ),
            authority_boundary=_authority_boundary(),
            capture_ready=True,
            blocked_actions=BLOCKED_ACTIONS,
            next_safe_move="When the future writer exists, ask Winship to explicitly use this draft before writing a receipt.",
        ),
    )


def default_normalization_rules() -> tuple[PerformanceDateNormalizationRule, ...]:
    return (
        PerformanceDateNormalizationRule(
            rule_id="capital_hilton_performance_date_normalization_rule",
            input_examples=(
                "May 22 and May 29",
                "2026-05-22",
                "05/22/2026",
                "May 22, 2026",
            ),
            inferred_year_policy=(
                "Infer 2026 from session context only when the active Capital Hilton workflow "
                "already contains 2026 candidate performance dates."
            ),
            accepted_formats=(
                "ISO date YYYY-MM-DD",
                "month name plus day when session year is deterministic",
                "month/day/year with four-digit year",
                "month name day comma year",
            ),
            rejected_formats=(
                "relative dates without deterministic session anchor",
                "month/day without inferable year",
                "impossible calendar dates",
                "date ranges that cannot be expanded deterministically",
                "freeform text that contains no date candidate",
            ),
            duplicate_policy="Flag duplicate dates in duplicate_dates and do not add them twice.",
            ordering_policy="Store normalized performance dates in ascending ISO date order.",
            ambiguity_policy="Ambiguous dates require clarification and cannot become capture-ready.",
            out_of_range_policy="Dates outside the active workflow service window require operator clarification.",
            timezone_policy="Performance dates are treated as local service dates, not instants or timezone conversions.",
            next_safe_move="Normalize to preview state only; do not write workflow state.",
        ),
    )


def default_receipt_state_targets() -> tuple[PerformanceDatesReceiptStateTarget, ...]:
    return (
        PerformanceDatesReceiptStateTarget(
            receipt_state_target_id="capital_hilton_performance_dates_may_22_29_receipt_state_target",
            capture_candidate_ref="capital_hilton_performance_dates_may_22_29_capture_candidate",
            receipt_type="OPERATOR_PERFORMANCE_DATES_ADDITION",
            intended_state_update={
                "field": "performance_dates",
                "operation": "replace_with_validated_set",
                "from": ("2026-05-08", "2026-05-15"),
                "to": ("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29"),
                "operator_confirmation_required": True,
                "proof_still_required": True,
            },
            canonical_workflow_state_ref="workflow_session.capital_hilton_invoice_workflow_session.performance_dates",
            affected_block_ref="performance_dates",
            affected_proof_items=(
                "performance_date_2026_05_08_proof",
                "performance_date_2026_05_15_proof",
                "performance_date_2026_05_22_proof_candidate",
                "performance_date_2026_05_29_proof_candidate",
            ),
            downstream_invalidations=(
                "invoice_packet_dates",
                "invoice_subtotal_preview",
                "invoice_artifact_preview",
                "email_attachment_preview",
                "approval_packet_preview",
            ),
            stale_artifact_refs=(
                "capital_hilton_invoice_packet_preview",
                "capital_hilton_email_attachment_preview",
                "capital_hilton_approval_packet_preview",
            ),
            required_writer="future_receipt_backed_workflow_state_writer",
            required_validation_status="VALID_CAPTURE_CANDIDATE",
            required_operator_action="Use this draft",
            required_guardian_review=False,
            current_receipt_write_authority=False,
            current_state_write_authority=False,
            current_execution_authority=False,
            next_safe_move="Hold this as a receipt/state target until a governed writer lane exists.",
        ),
    )


def default_downstream_impacts() -> tuple[PerformanceDatesDownstreamImpact, ...]:
    return (
        PerformanceDatesDownstreamImpact(
            impact_id="capital_hilton_performance_dates_may_22_29_downstream_impact",
            capture_candidate_ref="capital_hilton_performance_dates_may_22_29_capture_candidate",
            invoice_packet_effect="After future capture, invoice packet date inputs would update to four dates.",
            invoice_subtotal_effect="Subtotal preview would recalculate only after the rate block is confirmed.",
            email_draft_effect="Any email draft or attachment would need a regenerated invoice later. No draft is created now.",
            approval_packet_effect="Approval packet remains locked until invoice preview, proof, and approval bus prerequisites exist.",
            proof_requirement_effect="Proof remains required; operator confirmation is not external proof.",
            coupa_po_effect="PO/reference coverage may need to cover the four-date draft before final send.",
            affected_blocks=(
                "performance_dates",
                "rate",
                "invoice_packet",
                "po_reference",
                "email_review",
                "approval_send",
            ),
            stale_blocks=(
                "invoice_packet",
                "invoice_subtotal_preview",
                "email_attachment_preview",
                "approval_packet_preview",
            ),
            next_blocks=(
                "confirm_rate",
                "collect_or_point_to_performance_date_proof",
                "resolve_po_reference_if_needed",
            ),
            blocked_actions=BLOCKED_ACTIONS,
            next_safe_move="Show the stale downstream preview clearly and keep generation/send locked.",
        ),
    )


def build_capital_hilton_performance_dates_capture_boundary(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    capture_candidates = default_capture_candidates()
    normalization_rules = default_normalization_rules()
    receipt_targets = default_receipt_state_targets()
    downstream_impacts = default_downstream_impacts()

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": "capital_hilton_performance_dates_capture_boundary_v0",
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "operator_summary": (
            "The May 22 and May 29 Capital Hilton performance date draft can be modeled as a "
            "valid capture candidate, but no receipt, state write, invoice generation, email "
            "draft, send, or external access happens in this contract."
        ),
        "doctrine": {
            "summary": "Live draft workspace -> explicit capture boundary -> receipt-backed state later.",
            "local_preview_draft_is_not_canonical": True,
            "capture_boundary_is_explicit": True,
            "receipts_commit_later": True,
            "gates_execute_later": True,
        },
        "hard_rule": {
            "read_model_only": True,
            "does_not_write_receipts": True,
            "does_not_mutate_workflow_state": True,
            "does_not_generate_invoice_artifacts": True,
            "does_not_create_email_drafts": True,
            "does_not_send_anything": True,
            "does_not_access_external_systems": True,
            "does_not_call_models_agents_or_tools": True,
            "may_grant_authority": False,
        },
        "validation_statuses": list(VALIDATION_STATUSES),
        "receipt_types": list(RECEIPT_TYPES),
        "capital_hilton_performance_dates_capture_candidate_schema": {
            "model_name": "CapitalHiltonPerformanceDatesCaptureCandidate",
            "required_fields": list(REQUIRED_CAPTURE_CANDIDATE_FIELDS),
            "candidate_is_canonical_state": False,
            "block_id_must_be": "performance_dates",
            "current_and_draft_dates_distinct": True,
            "capture_ready_may_be_modeled_without_write_authority": True,
        },
        "performance_date_normalization_rule_schema": {
            "model_name": "PerformanceDateNormalizationRule",
            "required_fields": list(REQUIRED_NORMALIZATION_RULE_FIELDS),
            "normalization_writes_state": False,
            "ambiguous_dates_fail_closed": True,
            "duplicate_dates_flagged_not_added_twice": True,
        },
        "performance_dates_receipt_state_target_schema": {
            "model_name": "PerformanceDatesReceiptStateTarget",
            "required_fields": list(REQUIRED_RECEIPT_STATE_TARGET_FIELDS),
            "receipt_state_target_only": True,
            "receipt_written_here": False,
            "workflow_state_mutated_here": False,
            "send_remains_locked": True,
        },
        "performance_dates_downstream_impact_schema": {
            "model_name": "PerformanceDatesDownstreamImpact",
            "required_fields": list(REQUIRED_DOWNSTREAM_IMPACT_FIELDS),
            "invoice_generation_future_gated": True,
            "email_draft_send_future_gated": True,
            "approval_send_locked": True,
        },
        "capture_candidates": [asdict(candidate) for candidate in capture_candidates],
        "capture_candidates_by_id": {
            candidate.capture_candidate_id: asdict(candidate) for candidate in capture_candidates
        },
        "normalization_rules": [asdict(rule) for rule in normalization_rules],
        "normalization_rules_by_id": {rule.rule_id: asdict(rule) for rule in normalization_rules},
        "receipt_state_targets": [asdict(target) for target in receipt_targets],
        "receipt_state_targets_by_id": {
            target.receipt_state_target_id: asdict(target) for target in receipt_targets
        },
        "downstream_impacts": [asdict(impact) for impact in downstream_impacts],
        "downstream_impacts_by_id": {
            impact.impact_id: asdict(impact) for impact in downstream_impacts
        },
        "capital_hilton_example": {
            "example_id": "capital_hilton_may_22_29_performance_dates_capture_example",
            "current_openclaw_dates": ("2026-05-08", "2026-05-15"),
            "draft_input": "May 22 and May 29",
            "proposed_draft_dates": ("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29"),
            "added_dates": ("2026-05-22", "2026-05-29"),
            "validation_status": "VALID_CAPTURE_CANDIDATE",
            "proof_still_required": True,
            "capture_ready": True,
            "current_receipt_write_authority": False,
            "current_state_write_authority": False,
            "current_execution_authority": False,
            "downstream_effects": (
                "invoice packet dates would update after future capture",
                "subtotal preview would recalc after confirmed rate",
                "email attachment would need regenerated invoice later",
                "proof/PO may need to cover four-date draft",
                "approval/send remains locked",
            ),
        },
        "relationship_to_existing_contracts": {
            "workflow_block_intent_live_draft_contract": {
                "source_ref": "generated/read_models/workflow_block_intent_live_draft_contract.json",
                "relationship": "consumes live draft performance_dates intent as source_draft_intent_ref",
            },
            "agent_execution_packet_compiler_contract": {
                "source_ref": "generated/read_models/agent_execution_packet_compiler_contract.json",
                "relationship": "future packet compiler may prepare validation/support packets without execution authority",
            },
            "agent_conversation_handoff_step_packet_contract": {
                "source_ref": "generated/read_models/agent_conversation_handoff_step_packet_contract.json",
                "relationship": "future agent handoff may explain capture readiness without writing state",
            },
            "operator_solve_path_decision_node_contract": {
                "source_ref": "generated/read_models/operator_solve_path_decision_node_contract.json",
                "relationship": "extends performance-date decision path with a capture target",
            },
            "workflow_session_channel_projection_approval_bus_contract": {
                "source_ref": "generated/read_models/workflow_session_channel_projection_approval_bus_contract.json",
                "relationship": "targets canonical workflow session state later without channel-owned state",
            },
            "capital_hilton_proof_resolution_batch": {
                "source_ref": "generated/read_models/capital_hilton_proof_resolution_batch_manifest.json",
                "relationship": "preserves proof requirements; operator confirmation does not prove external truth",
            },
            "capital_hilton_coupa_po_retrieval_automation_candidate": {
                "source_ref": "generated/read_models/capital_hilton_coupa_po_retrieval_automation_candidate.json",
                "relationship": "PO/reference coverage may expand after four performance dates are captured later",
            },
            "automation_readiness_feasibility_evaluator_contract": {
                "source_ref": "generated/read_models/automation_readiness_feasibility_evaluator_contract.json",
                "relationship": "keeps automation future-gated and separate from this capture target",
            },
        },
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_authority_flags_false": _all_authority_false(),
            "blocked_actions": list(BLOCKED_ACTIONS),
        },
        "machine_proof": {
            "capture_candidate_model_present": True,
            "date_normalization_rules_present": True,
            "receipt_state_target_model_present": True,
            "downstream_impact_model_present": True,
            "capital_hilton_may_22_29_example_present": True,
            "block_id_is_performance_dates": all(
                candidate.block_id == "performance_dates" for candidate in capture_candidates
            ),
            "current_dates_and_draft_dates_distinct": capture_candidates[0].current_openclaw_dates
            != capture_candidates[0].proposed_draft_dates,
            "added_dates_represented": capture_candidates[0].added_dates == ("2026-05-22", "2026-05-29"),
            "duplicate_policy_present": bool(normalization_rules[0].duplicate_policy),
            "invalid_ambiguous_date_policy_present": bool(
                normalization_rules[0].ambiguity_policy and normalization_rules[0].rejected_formats
            ),
            "proof_still_required_after_operator_confirmation": capture_candidates[0].proof_still_required,
            "downstream_invoice_email_approval_effects_represented": True,
            "capture_ready_modeled": capture_candidates[0].capture_ready,
            "receipt_state_write_execution_authority_false": all(
                target.current_receipt_write_authority is False
                and target.current_state_write_authority is False
                and target.current_execution_authority is False
                for target in receipt_targets
            ),
            "all_authority_flags_false": _all_authority_false(),
            "credential_or_secret_included": False,
            "raw_private_body_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_capital_hilton_performance_dates_capture_boundary(payload: dict[str, Any]) -> str:
    example = payload["capital_hilton_example"]
    boundary = payload["authority_boundary"]
    lines = [
        "# Capital Hilton Performance Dates Capture Boundary v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This is the first backend capture boundary for a workflow block. It says what would happen later if Winship chooses Use this draft for the Capital Hilton Performance Dates block.",
        "",
        "It does not write the receipt yet. It does not change the real workflow state. It does not generate an invoice, create an email draft, send anything, or touch Coupa/Gmail/browser/Telegram.",
        "",
        "## What It Validates",
        "",
        f"- Current OpenClaw dates: `{', '.join(example['current_openclaw_dates'])}`",
        f"- Draft input: `{example['draft_input']}`",
        f"- Draft date set: `{', '.join(example['proposed_draft_dates'])}`",
        f"- Added dates: `{', '.join(example['added_dates'])}`",
        f"- Validation status: `{example['validation_status']}`",
        "",
        "Adding May 22 and May 29 can become a valid capture candidate because the active session already has 2026 Capital Hilton dates. The year inference is still deterministic, not guessed from thin air.",
        "",
        "## What Would Be Written Later",
        "",
        "A future receipt/state writer would need to write an operator performance-date receipt and update the canonical workflow block. This contract only names that target.",
        "",
        "## Downstream Effects",
        "",
        "- Captured dates would update invoice packet inputs later.",
        "- Subtotal preview would recalculate only after the rate is confirmed.",
        "- Any email attachment would need a regenerated invoice later.",
        "- Proof and PO/reference coverage may need to cover all four dates.",
        "- Approval and send remain locked.",
        "",
        "## Why This Matters",
        "",
        "This is how Use this draft eventually becomes real without jumping to unsafe automation. The live draft stays reversible until an explicit capture boundary, then a future receipt-backed writer can commit it safely.",
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
            f"- Receipt write allowed: `{str(boundary['receipt_write_allowed']).lower()}`",
            f"- State write allowed: `{str(boundary['state_write_allowed']).lower()}`",
            f"- Capture execution allowed: `{str(boundary['capture_execution_allowed']).lower()}`",
            f"- Invoice generation allowed: `{str(boundary['invoice_generation_allowed']).lower()}`",
            f"- Email send allowed: `{str(boundary['email_send_allowed']).lower()}`",
        ]
    )
    return "\n".join(lines) + "\n"


def export_capital_hilton_performance_dates_capture_boundary(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> PerformanceDatesCaptureBoundaryExportResult:
    payload = build_capital_hilton_performance_dates_capture_boundary(generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(
        format_capital_hilton_performance_dates_capture_boundary(payload),
        encoding="utf-8",
    )
    return PerformanceDatesCaptureBoundaryExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        capture_candidate_count=len(payload["capture_candidates"]),
        normalization_rule_count=len(payload["normalization_rules"]),
        receipt_state_target_count=len(payload["receipt_state_targets"]),
        downstream_impact_count=len(payload["downstream_impacts"]),
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Capital Hilton Performance Dates Capture Boundary read-model."
    )
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_performance_dates_capture_boundary(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "capture_candidate_count": result.capture_candidate_count,
        "normalization_rule_count": result.normalization_rule_count,
        "receipt_state_target_count": result.receipt_state_target_count,
        "downstream_impact_count": result.downstream_impact_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Capital Hilton Performance Dates Capture Boundary: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "AUTHORITY_BOUNDARY",
    "BLOCKED_ACTIONS",
    "CONTRACT_STATUS",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "RECEIPT_TYPES",
    "REQUIRED_CAPTURE_CANDIDATE_FIELDS",
    "REQUIRED_DOWNSTREAM_IMPACT_FIELDS",
    "REQUIRED_NORMALIZATION_RULE_FIELDS",
    "REQUIRED_RECEIPT_STATE_TARGET_FIELDS",
    "SCHEMA_VERSION",
    "VALIDATION_STATUSES",
    "CapitalHiltonPerformanceDatesCaptureCandidate",
    "PerformanceDateNormalizationRule",
    "PerformanceDatesDownstreamImpact",
    "PerformanceDatesReceiptStateTarget",
    "build_capital_hilton_performance_dates_capture_boundary",
    "default_capture_candidates",
    "default_downstream_impacts",
    "default_normalization_rules",
    "default_receipt_state_targets",
    "export_capital_hilton_performance_dates_capture_boundary",
    "format_capital_hilton_performance_dates_capture_boundary",
    "stable_json",
]
