"""Workflow Block Intent / Live Draft Contract v0.

This deterministic read-model defines how workflow block edits, conversational
requests, and agent-assisted proposals remain live draft workspace state until
an explicit capture boundary. It does not persist operator answers, write
receipts, execute workflows, call agents/models/tools/runtimes, access external
systems, generate invoices, send messages, submit approvals, or grant authority.
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

SCHEMA_VERSION = "workflow_block_intent_live_draft_contract_v0"
READ_MODEL_ID = "workflow_block_intent_live_draft_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_LIVE_DRAFT_CONTRACT"

OPERATIONS = (
    "add_dates",
    "change_value",
    "set_value",
    "clear_value",
    "explore_branch",
    "compile_request",
    "propose_workflow",
    "fill_from_evidence",
    "request_operator_answer",
    "UNKNOWN_FAIL_CLOSED",
)

ORIGIN_SURFACES = (
    "MISSION_CONTROL",
    "TELEGRAM",
    "CASSANDRA_CLARA",
    "CHIEF",
    "HERMES",
    "NILES",
    "GUARDIAN",
    "FUTURE_WORKFLOW_AGENT",
    "UNKNOWN_FAIL_CLOSED",
)

COMPATIBLE_SURFACES = (
    "Mission Control",
    "Telegram",
    "Cassandra/Clara",
    "Chief",
    "Guardian",
    "Hermes",
    "Niles",
    "future workflow agents",
)

COMPATIBLE_AGENTS = (
    "Cassandra/Clara",
    "Chief",
    "Hermes",
    "Niles",
    "Guardian",
    "future workflow agents",
)

VALIDATION_STATUSES = (
    "VALID_PREVIEW",
    "NEEDS_CLARIFICATION",
    "NEEDS_OPERATOR_REVIEW",
    "NEEDS_PROOF",
    "NEEDS_GUARDIAN_REVIEW",
    "REJECTED_INVALID",
    "BLOCKED_BY_AUTHORITY",
    "UNKNOWN_FAIL_CLOSED",
)

REVIEW_MODES = (
    "REVIEW_REQUIRED",
    "REVIEW_RECOMMENDED",
    "REVIEW_OPTIONAL",
    "SKIP_REVIEW_ALLOWED",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_DRAFT_INTENT_FIELDS = (
    "draft_intent_id",
    "workflow_session_ref",
    "world",
    "lane",
    "workflow_type",
    "block_id",
    "block_label",
    "operation",
    "origin_surface",
    "origin_actor",
    "origin_channel",
    "compatible_surfaces",
    "compatible_agents",
    "current_state_refs",
    "operator_input_raw",
    "operator_input_structured",
    "proposed_updates",
    "resulting_fields",
    "downstream_effects",
    "validation_requirements",
    "receipt_target",
    "approval_guardian_boundary",
    "authority_state",
    "preview_only",
    "capture_ready",
    "blocked_actions",
    "next_safe_move",
)

REQUIRED_WORKSPACE_FIELDS = (
    "workspace_id",
    "workflow_session_ref",
    "active_blocks",
    "locked_blocks",
    "current_block_id",
    "inspected_block_id",
    "current_openclaw_state",
    "active_local_draft_state",
    "future_captured_state_preview",
    "block_draft_intents",
    "downstream_preview",
    "reversible_exploration_state",
    "capture_candidates",
    "commit_boundary",
    "stale_preview_policy",
    "reset_policy",
    "authority_state",
    "next_safe_move",
)

REQUIRED_AGENT_PROPOSAL_FIELDS = (
    "proposal_id",
    "source_request",
    "source_actor",
    "source_surface",
    "target_workflow_session_ref",
    "proposed_block_sequence",
    "proposed_block_intents",
    "blocks_system_can_fill",
    "blocks_operator_must_answer",
    "ambiguity_flags",
    "confidence",
    "validation_required",
    "operator_review_recommended",
    "can_skip_operator_review",
    "skip_review_reason",
    "blocked_actions",
    "next_safe_move",
)

REQUIRED_VALIDATION_RESULT_FIELDS = (
    "validation_id",
    "draft_intent_ref",
    "validation_status",
    "normalized_updates",
    "rejected_updates",
    "ambiguity_flags",
    "missing_required_fields",
    "duplicate_or_conflict_warnings",
    "downstream_invalidations",
    "proof_requirements",
    "approval_requirements",
    "receipt_requirements",
    "capture_allowed",
    "canonical_write_allowed",
    "execution_allowed",
    "next_safe_move",
)

REQUIRED_CAPTURE_BOUNDARY_FIELDS = (
    "capture_boundary_id",
    "draft_intent_ref",
    "capture_label",
    "capture_meaning",
    "required_validation_status",
    "required_operator_action",
    "required_receipt_type",
    "required_state_writer",
    "affected_workflow_state",
    "affected_downstream_artifacts",
    "approval_gate_refs",
    "current_capture_authority",
    "current_write_authority",
    "current_execution_authority",
    "next_safe_move",
)

REQUIRED_CONVERSATIONAL_FLOW_FIELDS = (
    "flow_id",
    "example_request",
    "originating_agent",
    "originating_surface",
    "target_workflow",
    "inferred_blocks",
    "system_filled_blocks",
    "operator_needed_blocks",
    "review_mode",
    "conversation_steps",
    "draft_intents_created",
    "approval_boundaries",
    "final_response_shape",
    "blocked_actions",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "canonical_state_write_allowed": False,
    "receipt_write_allowed": False,
    "capture_write_allowed": False,
    "execution_allowed": False,
    "invoice_generation_allowed": False,
    "email_draft_allowed": False,
    "email_send_allowed": False,
    "browser_automation_allowed": False,
    "coupa_access_allowed": False,
    "credential_handling_allowed": False,
    "telegram_send_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "file_write_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_operation_allowed": False,
    "gmail_access_allowed": False,
    "calendar_access_allowed": False,
    "ledger_write_allowed": False,
    "approval_submission_allowed": False,
    "operator_input_persistence_allowed": False,
    "workflow_execution_allowed": False,
    "file_move_delete_cleanup_allowed": False,
    "archive_action_allowed": False,
    "rewrite_action_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

COMMON_BLOCKED_ACTIONS = (
    "canonical workflow state write",
    "operator answer persistence",
    "receipt write",
    "capture write",
    "workflow execution",
    "invoice generation",
    "email draft or send",
    "approval submission",
    "browser/Coupa/Gmail/Calendar/Telegram/account access",
    "credential handling",
    "model/tool/agent/runtime/queue execution",
    "ledger write",
    "file write or cleanup",
)


@dataclass(frozen=True)
class WorkflowBlockDraftIntent:
    draft_intent_id: str
    workflow_session_ref: str
    world: str
    lane: str
    workflow_type: str
    block_id: str
    block_label: str
    operation: str
    origin_surface: str
    origin_actor: str
    origin_channel: str
    compatible_surfaces: tuple[str, ...]
    compatible_agents: tuple[str, ...]
    current_state_refs: tuple[str, ...]
    operator_input_raw: str
    operator_input_structured: dict[str, Any]
    proposed_updates: tuple[dict[str, Any], ...]
    resulting_fields: dict[str, Any]
    downstream_effects: tuple[str, ...]
    validation_requirements: tuple[str, ...]
    receipt_target: str
    approval_guardian_boundary: str
    authority_state: dict[str, bool]
    preview_only: bool
    capture_ready: bool
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class LiveWorkflowDraftWorkspace:
    workspace_id: str
    workflow_session_ref: str
    active_blocks: tuple[str, ...]
    locked_blocks: tuple[str, ...]
    current_block_id: str
    inspected_block_id: str
    current_openclaw_state: dict[str, Any]
    active_local_draft_state: dict[str, Any]
    future_captured_state_preview: dict[str, Any]
    block_draft_intents: tuple[str, ...]
    downstream_preview: dict[str, Any]
    reversible_exploration_state: dict[str, Any]
    capture_candidates: tuple[str, ...]
    commit_boundary: str
    stale_preview_policy: str
    reset_policy: str
    authority_state: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowBlockAgentCompilerProposal:
    proposal_id: str
    source_request: str
    source_actor: str
    source_surface: str
    target_workflow_session_ref: str
    proposed_block_sequence: tuple[str, ...]
    proposed_block_intents: tuple[str, ...]
    blocks_system_can_fill: tuple[str, ...]
    blocks_operator_must_answer: tuple[str, ...]
    ambiguity_flags: tuple[str, ...]
    confidence: str
    validation_required: bool
    operator_review_recommended: bool
    can_skip_operator_review: bool
    skip_review_reason: str
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowBlockIntentValidationResult:
    validation_id: str
    draft_intent_ref: str
    validation_status: str
    normalized_updates: tuple[dict[str, Any], ...]
    rejected_updates: tuple[dict[str, Any], ...]
    ambiguity_flags: tuple[str, ...]
    missing_required_fields: tuple[str, ...]
    duplicate_or_conflict_warnings: tuple[str, ...]
    downstream_invalidations: tuple[str, ...]
    proof_requirements: tuple[str, ...]
    approval_requirements: tuple[str, ...]
    receipt_requirements: tuple[str, ...]
    capture_allowed: bool
    canonical_write_allowed: bool
    execution_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowBlockCaptureBoundary:
    capture_boundary_id: str
    draft_intent_ref: str
    capture_label: str
    capture_meaning: str
    required_validation_status: str
    required_operator_action: str
    required_receipt_type: str
    required_state_writer: str
    affected_workflow_state: tuple[str, ...]
    affected_downstream_artifacts: tuple[str, ...]
    approval_gate_refs: tuple[str, ...]
    current_capture_authority: bool
    current_write_authority: bool
    current_execution_authority: bool
    next_safe_move: str


@dataclass(frozen=True)
class ConversationalWorkflowBlockFlow:
    flow_id: str
    example_request: str
    originating_agent: str
    originating_surface: str
    target_workflow: str
    inferred_blocks: tuple[str, ...]
    system_filled_blocks: tuple[str, ...]
    operator_needed_blocks: tuple[str, ...]
    review_mode: str
    conversation_steps: tuple[str, ...]
    draft_intents_created: tuple[str, ...]
    approval_boundaries: tuple[str, ...]
    final_response_shape: str
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowBlockExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    draft_intent_count: int
    workspace_count: int
    agent_proposal_count: int
    validation_result_count: int
    capture_boundary_count: int
    conversational_flow_count: int
    action_authority_granted: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _all_authority_flags_false() -> bool:
    return all(value is False for value in AUTHORITY_BOUNDARY.values())


def _authority_state() -> dict[str, bool]:
    return {
        "canonical_state_write_allowed": False,
        "receipt_write_allowed": False,
        "capture_write_allowed": False,
        "execution_allowed": False,
        "invoice_generation_allowed": False,
        "email_draft_allowed": False,
        "email_send_allowed": False,
        "browser_automation_allowed": False,
        "coupa_access_allowed": False,
        "credential_handling_allowed": False,
        "telegram_send_allowed": False,
        "model_call_allowed": False,
        "agent_activation_allowed": False,
        "tool_execution_allowed": False,
        "queue_execution_allowed": False,
        "runtime_dispatch_allowed": False,
        "file_write_allowed": False,
        "raw_body_ingestion_allowed": False,
    }


def default_draft_intents() -> tuple[WorkflowBlockDraftIntent, ...]:
    return (
        WorkflowBlockDraftIntent(
            draft_intent_id="capital_hilton_mission_control_performance_dates_draft",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            world="Finance",
            lane="Capital Hilton",
            workflow_type="INVOICE_WORKFLOW",
            block_id="performance_dates",
            block_label="Performance dates",
            operation="add_dates",
            origin_surface="MISSION_CONTROL",
            origin_actor="Winship",
            origin_channel="mission_control_finance_world",
            compatible_surfaces=COMPATIBLE_SURFACES,
            compatible_agents=COMPATIBLE_AGENTS,
            current_state_refs=(
                "capital_hilton_invoice_workflow_session.current_state.performance_dates",
                "operator_solve_path_decision_node_contract.confirm_performance_dates",
            ),
            operator_input_raw="May 22 and May 29",
            operator_input_structured={
                "date_values": ("2026-05-22", "2026-05-29"),
                "input_interpretation": "add two performance dates to the active draft",
            },
            proposed_updates=(
                {
                    "field": "performance_dates",
                    "operation": "append",
                    "value": "2026-05-22",
                    "source": "operator_live_draft_input",
                },
                {
                    "field": "performance_dates",
                    "operation": "append",
                    "value": "2026-05-29",
                    "source": "operator_live_draft_input",
                },
            ),
            resulting_fields={
                "performance_dates": ("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29"),
                "date_count": 4,
                "state_status": "draft_preview_only",
            },
            downstream_effects=(
                "invoice packet dates preview updates",
                "invoice subtotal preview becomes stale until recalculated",
                "email attachment preview becomes stale",
                "approval packet remains blocked until capture and receipt writer exist",
            ),
            validation_requirements=(
                "normalize natural-language dates to ISO dates",
                "check duplicate dates",
                "check active workflow session still matches Capital Hilton",
                "require operator review before future capture",
            ),
            receipt_target="capital_hilton_performance_dates_operator_correction_or_confirmation_receipt_target",
            approval_guardian_boundary="invoice draft review and Guardian/email approval remain required before send",
            authority_state=_authority_state(),
            preview_only=True,
            capture_ready=False,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Preview the date change and decide whether to use this draft later.",
        ),
        WorkflowBlockDraftIntent(
            draft_intent_id="capital_hilton_telegram_invoice_request_draft",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            world="Finance",
            lane="Capital Hilton",
            workflow_type="INVOICE_WORKFLOW",
            block_id="invoice_request",
            block_label="Invoice request",
            operation="compile_request",
            origin_surface="TELEGRAM",
            origin_actor="Winship via Cassandra",
            origin_channel="telegram_cassandra_conversation",
            compatible_surfaces=COMPATIBLE_SURFACES,
            compatible_agents=COMPATIBLE_AGENTS,
            current_state_refs=(
                "workflow_session_channel_projection_approval_bus_contract.capital_hilton_invoice_workflow_session",
                "operator_work_mode_schema_bandwidth_policy.capital_hilton_invoice_work_mode",
            ),
            operator_input_raw="Send Capital Hilton an invoice for this week's and last week's job.",
            operator_input_structured={
                "client": "Capital Hilton",
                "requested_action": "prepare_invoice_draft",
                "date_scope": "this_week_and_last_week",
            },
            proposed_updates=(
                {"field": "client", "operation": "set_if_known", "value": "Capital Hilton"},
                {"field": "invoice_route", "operation": "set_if_known", "value": "known_route_if_available"},
                {"field": "performance_dates", "operation": "infer_scope_for_review", "value": "this_week_and_last_week"},
            ),
            resulting_fields={
                "client": "Capital Hilton",
                "rate": "known_rate_if_available",
                "invoice_route": "known_route_if_available",
                "missing_questions": ("confirm exact performance dates",),
            },
            downstream_effects=(
                "invoice draft preview can be prepared after deterministic validation",
                "review packet remains gated",
                "Guardian/email approval remains required before send",
            ),
            validation_requirements=(
                "confirm known client and rate refs",
                "resolve natural-language date scope",
                "require proof or operator confirmation before capture",
            ),
            receipt_target="capital_hilton_invoice_request_memory_candidate_or_confirmation_target",
            approval_guardian_boundary="send and invoice approval stay blocked behind future approval bus",
            authority_state=_authority_state(),
            preview_only=True,
            capture_ready=False,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Ask only for missing invoice facts, then preview the draft path.",
        ),
        WorkflowBlockDraftIntent(
            draft_intent_id="monthly_client_recap_new_workflow_draft",
            workflow_session_ref="new_monthly_client_recap_workflow_session_candidate",
            world="Client Delivery",
            lane="Client X",
            workflow_type="NEW_WORKFLOW_CANDIDATE",
            block_id="workflow_outline",
            block_label="Workflow outline",
            operation="propose_workflow",
            origin_surface="CASSANDRA_CLARA",
            origin_actor="future workflow agent",
            origin_channel="conversation",
            compatible_surfaces=COMPATIBLE_SURFACES,
            compatible_agents=COMPATIBLE_AGENTS,
            current_state_refs=("current_client_delivery_read_models_if_available",),
            operator_input_raw="Set up a monthly client recap workflow for Client X.",
            operator_input_structured={
                "workflow_goal": "monthly client recap",
                "client": "Client X",
                "cadence": "monthly",
            },
            proposed_updates=(
                {"field": "workflow_blocks", "operation": "propose", "value": "client, cadence, sources, recap format, approval route"},
            ),
            resulting_fields={
                "proposed_block_chain": ("client", "cadence", "source_materials", "recap_format", "review_route"),
                "needs_operator_review": True,
            },
            downstream_effects=(
                "new workflow preview appears as proposal only",
                "no scheduler, message, or file action is created",
            ),
            validation_requirements=(
                "operator reviews proposed block chain",
                "deterministic validator checks required fields before future capture",
            ),
            receipt_target="new_workflow_proposal_receipt_target_future",
            approval_guardian_boundary="new workflow activation remains blocked until governed capture and approval",
            authority_state=_authority_state(),
            preview_only=True,
            capture_ready=False,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Ask Winship whether to review and fill the proposed workflow blocks together.",
        ),
        WorkflowBlockDraftIntent(
            draft_intent_id="chief_check_engine_build_blocker_draft",
            workflow_session_ref="check_engine_diagnostic_session",
            world="Build",
            lane="Check Engine",
            workflow_type="DEVELOPER_SYSTEM_REPAIR",
            block_id="current_blocker",
            block_label="Current blocker",
            operation="fill_from_evidence",
            origin_surface="CHIEF",
            origin_actor="Chief",
            origin_channel="mission_control_chief_or_helm",
            compatible_surfaces=COMPATIBLE_SURFACES,
            compatible_agents=COMPATIBLE_AGENTS,
            current_state_refs=(
                "check_engine_diagnostic_solve_path",
                "generated read-model summaries",
                "focused test status refs",
            ),
            operator_input_raw="What is blocking the build?",
            operator_input_structured={
                "request_type": "diagnostic_summary",
                "detail_level": "captain_decision_first",
            },
            proposed_updates=(
                {"field": "diagnostic_blocker_summary", "operation": "fill_from_current_read_models", "value": "current evidence summary"},
            ),
            resulting_fields={
                "blocker_summary": "filled from current diagnostics when available",
                "captain_decision_needed": "only if repair or risk choice is required",
            },
            downstream_effects=(
                "engineering detail stays below deck unless blocking or summoned",
                "repair execution remains blocked",
            ),
            validation_requirements=(
                "diagnostic refs must be current",
                "repair recommendation must remain preview-only",
            ),
            receipt_target="check_engine_diagnostic_summary_receipt_target_future",
            approval_guardian_boundary="repair execution remains separately gated",
            authority_state=_authority_state(),
            preview_only=True,
            capture_ready=False,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Show the blocker summary and ask only for a captain decision if needed.",
        ),
    )


def default_workspaces() -> tuple[LiveWorkflowDraftWorkspace, ...]:
    return (
        LiveWorkflowDraftWorkspace(
            workspace_id="capital_hilton_invoice_live_draft_workspace",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            active_blocks=("performance_dates", "rate", "po_reference", "invoice_route", "review_packet"),
            locked_blocks=("client_identity", "send_authority"),
            current_block_id="performance_dates",
            inspected_block_id="performance_dates",
            current_openclaw_state={
                "state_kind": "canonical_current",
                "performance_dates": ("2026-05-08", "2026-05-15"),
                "source": "receipt_backed_or_current_read_model_refs",
            },
            active_local_draft_state={
                "state_kind": "active_draft_not_canonical",
                "performance_dates": ("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29"),
                "changed_by": "capital_hilton_mission_control_performance_dates_draft",
            },
            future_captured_state_preview={
                "state_kind": "future_captured_preview_not_written",
                "would_capture_dates": ("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29"),
                "requires_receipt_writer": True,
            },
            block_draft_intents=("capital_hilton_mission_control_performance_dates_draft",),
            downstream_preview={
                "invoice_packet_dates": "updated in preview",
                "subtotal": "stale_until_recalculated",
                "email_attachment": "stale_until_invoice_preview_regenerated",
                "approval_packet": "blocked_until_capture_and_review",
            },
            reversible_exploration_state={
                "can_reset_to_current_openclaw_state": True,
                "draft_history_commits_to_canonical_state": False,
                "branches_can_be_parked": True,
            },
            capture_candidates=("capital_hilton_performance_dates_capture_boundary",),
            commit_boundary="Use this draft requires explicit capture through a future receipt/state writer lane.",
            stale_preview_policy="Any upstream block edit invalidates dependent subtotal, artifact, and approval previews.",
            reset_policy="Reset drops local draft changes and returns to current OpenClaw state without receipts.",
            authority_state=_authority_state(),
            next_safe_move="Let the operator inspect the preview, reset it, or wait for a future capture writer.",
        ),
        LiveWorkflowDraftWorkspace(
            workspace_id="app_wide_conversational_workflow_live_draft_workspace",
            workflow_session_ref="channel_neutral_workflow_session_candidate",
            active_blocks=("request", "known_fields", "missing_questions", "review_route"),
            locked_blocks=("canonical_state", "execution_authority"),
            current_block_id="request",
            inspected_block_id="known_fields",
            current_openclaw_state={
                "state_kind": "canonical_current",
                "owner": "workflow session",
                "surface_owner": "none",
            },
            active_local_draft_state={
                "state_kind": "active_draft_not_canonical",
                "origin_can_be": ("Mission Control", "Telegram", "agent conversation"),
            },
            future_captured_state_preview={
                "state_kind": "future_captured_preview_not_written",
                "requires": ("validation", "operator capture action", "receipt writer"),
            },
            block_draft_intents=(
                "capital_hilton_telegram_invoice_request_draft",
                "monthly_client_recap_new_workflow_draft",
                "chief_check_engine_build_blocker_draft",
            ),
            downstream_preview={
                "visible_surfaces": "may render same draft",
                "canonical_state": "unchanged",
                "execution": "blocked",
            },
            reversible_exploration_state={
                "branching_allowed": True,
                "branch_commit_implicit": False,
                "stale_branches_must_revalidate": True,
            },
            capture_candidates=(
                "conversation_request_capture_boundary",
                "new_workflow_outline_capture_boundary",
                "diagnostic_summary_capture_boundary",
            ),
            commit_boundary="All channels converge on the same explicit capture boundary.",
            stale_preview_policy="When a prior block changes, dependent draft previews must be marked stale before display.",
            reset_policy="A channel can abandon its local draft view without deleting canonical workflow state.",
            authority_state=_authority_state(),
            next_safe_move="Keep current, draft, and future captured state separate across every surface.",
        ),
    )


def default_agent_proposals() -> tuple[WorkflowBlockAgentCompilerProposal, ...]:
    return (
        WorkflowBlockAgentCompilerProposal(
            proposal_id="cassandra_capital_hilton_invoice_request_compiler_proposal",
            source_request="Send Capital Hilton an invoice for this week's and last week's job.",
            source_actor="Cassandra",
            source_surface="TELEGRAM",
            target_workflow_session_ref="capital_hilton_invoice_workflow_session",
            proposed_block_sequence=("client", "date_scope", "rate", "invoice_route", "review_packet"),
            proposed_block_intents=("capital_hilton_telegram_invoice_request_draft",),
            blocks_system_can_fill=("client", "known_rate_if_available", "known_invoice_route_if_available"),
            blocks_operator_must_answer=("exact performance dates if not deterministically known",),
            ambiguity_flags=("this week and last week require date resolution",),
            confidence="MEDIUM_UNTIL_DATE_SCOPE_VALIDATED",
            validation_required=True,
            operator_review_recommended=True,
            can_skip_operator_review=False,
            skip_review_reason="Invoice draft and send path are sensitive and gated.",
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Compile a preview packet and ask only the missing date/proof questions.",
        ),
        WorkflowBlockAgentCompilerProposal(
            proposal_id="new_monthly_client_recap_workflow_compiler_proposal",
            source_request="Set up a monthly client recap workflow for Client X.",
            source_actor="future workflow agent",
            source_surface="CASSANDRA_CLARA",
            target_workflow_session_ref="new_monthly_client_recap_workflow_session_candidate",
            proposed_block_sequence=("client", "cadence", "source_materials", "recap_format", "review_route"),
            proposed_block_intents=("monthly_client_recap_new_workflow_draft",),
            blocks_system_can_fill=("cadence_from_request", "workflow_goal_from_request"),
            blocks_operator_must_answer=("source_materials", "recap_format", "review_route"),
            ambiguity_flags=("Client X identity may need deterministic match",),
            confidence="LOW_UNTIL_CLIENT_AND_SOURCES_VALIDATED",
            validation_required=True,
            operator_review_recommended=True,
            can_skip_operator_review=False,
            skip_review_reason="New workflow chain must be reviewed before capture.",
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Ask whether Winship wants to review and fill the proposed blocks together.",
        ),
        WorkflowBlockAgentCompilerProposal(
            proposal_id="chief_check_engine_blocker_compiler_proposal",
            source_request="What is blocking the build?",
            source_actor="Chief",
            source_surface="MISSION_CONTROL",
            target_workflow_session_ref="check_engine_diagnostic_session",
            proposed_block_sequence=("diagnostic_sources", "current_blocker", "captain_decision_needed"),
            proposed_block_intents=("chief_check_engine_build_blocker_draft",),
            blocks_system_can_fill=("diagnostic_sources", "current_blocker_from_read_models"),
            blocks_operator_must_answer=("repair_risk_decision_if_needed",),
            ambiguity_flags=(),
            confidence="HIGH_IF_TEST_AND_READ_MODEL_REFS_ARE_CURRENT",
            validation_required=True,
            operator_review_recommended=True,
            can_skip_operator_review=False,
            skip_review_reason="Repair or runtime action still requires captain review.",
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Brief the blocker and keep engineering detail below deck unless summoned.",
        ),
    )


def default_validation_results() -> tuple[WorkflowBlockIntentValidationResult, ...]:
    return (
        WorkflowBlockIntentValidationResult(
            validation_id="capital_hilton_performance_dates_preview_validation",
            draft_intent_ref="capital_hilton_mission_control_performance_dates_draft",
            validation_status="VALID_PREVIEW",
            normalized_updates=(
                {"field": "performance_dates", "operation": "append", "value": "2026-05-22"},
                {"field": "performance_dates", "operation": "append", "value": "2026-05-29"},
            ),
            rejected_updates=(),
            ambiguity_flags=(),
            missing_required_fields=(),
            duplicate_or_conflict_warnings=(),
            downstream_invalidations=(
                "invoice_subtotal_preview",
                "invoice_artifact_preview",
                "email_attachment_preview",
                "approval_request_preview",
            ),
            proof_requirements=("operator confirmation or proof pointer required before final send path",),
            approval_requirements=("Guardian/email approval remains required before send",),
            receipt_requirements=("operator correction or confirmation receipt target required before canonical state write",),
            capture_allowed=False,
            canonical_write_allowed=False,
            execution_allowed=False,
            next_safe_move="Show valid preview and keep capture blocked until a future writer lane exists.",
        ),
        WorkflowBlockIntentValidationResult(
            validation_id="telegram_invoice_request_needs_review_validation",
            draft_intent_ref="capital_hilton_telegram_invoice_request_draft",
            validation_status="NEEDS_OPERATOR_REVIEW",
            normalized_updates=(
                {"field": "client", "operation": "set_if_known", "value": "Capital Hilton"},
                {"field": "date_scope", "operation": "needs_resolution", "value": "this_week_and_last_week"},
            ),
            rejected_updates=(),
            ambiguity_flags=("relative date phrase requires deterministic date packet",),
            missing_required_fields=("exact performance dates or source refs",),
            duplicate_or_conflict_warnings=(),
            downstream_invalidations=("invoice_draft_preview", "send_approval_preview"),
            proof_requirements=("performance date confirmation or source proof",),
            approval_requirements=("invoice draft review", "Guardian/email approval before send"),
            receipt_requirements=("future operator answer receipt",),
            capture_allowed=False,
            canonical_write_allowed=False,
            execution_allowed=False,
            next_safe_move="Ask the missing date/proof question before preparing a draft preview.",
        ),
        WorkflowBlockIntentValidationResult(
            validation_id="new_workflow_outline_needs_clarification_validation",
            draft_intent_ref="monthly_client_recap_new_workflow_draft",
            validation_status="NEEDS_CLARIFICATION",
            normalized_updates=(
                {"field": "workflow_goal", "operation": "set", "value": "monthly client recap"},
                {"field": "cadence", "operation": "set", "value": "monthly"},
            ),
            rejected_updates=(),
            ambiguity_flags=("Client X must be resolved to a deterministic client ref",),
            missing_required_fields=("source_materials", "review_route"),
            duplicate_or_conflict_warnings=(),
            downstream_invalidations=("new_workflow_preview",),
            proof_requirements=("client/source refs if workflow becomes durable",),
            approval_requirements=("operator approval before activation",),
            receipt_requirements=("future workflow proposal receipt",),
            capture_allowed=False,
            canonical_write_allowed=False,
            execution_allowed=False,
            next_safe_move="Ask whether to review the proposed block chain.",
        ),
        WorkflowBlockIntentValidationResult(
            validation_id="chief_check_engine_blocker_preview_validation",
            draft_intent_ref="chief_check_engine_build_blocker_draft",
            validation_status="NEEDS_PROOF",
            normalized_updates=(
                {"field": "diagnostic_blocker_summary", "operation": "fill_from_read_models", "value": "current evidence summary"},
            ),
            rejected_updates=(),
            ambiguity_flags=(),
            missing_required_fields=("current diagnostic proof refs",),
            duplicate_or_conflict_warnings=(),
            downstream_invalidations=("repair_plan_preview",),
            proof_requirements=("focused test/read-model refs required before repair recommendation capture",),
            approval_requirements=("operator review before any repair path",),
            receipt_requirements=("diagnostic summary receipt target future",),
            capture_allowed=False,
            canonical_write_allowed=False,
            execution_allowed=False,
            next_safe_move="Show diagnostic summary only when proof refs are attached.",
        ),
    )


def default_capture_boundaries() -> tuple[WorkflowBlockCaptureBoundary, ...]:
    return (
        WorkflowBlockCaptureBoundary(
            capture_boundary_id="capital_hilton_performance_dates_capture_boundary",
            draft_intent_ref="capital_hilton_mission_control_performance_dates_draft",
            capture_label="Use these dates",
            capture_meaning="Future writer would capture the validated date edits into workflow state with an operator receipt.",
            required_validation_status="VALID_PREVIEW",
            required_operator_action="explicit operator capture action",
            required_receipt_type="OPERATOR_CONFIRMATION_OR_CORRECTION_RECEIPT",
            required_state_writer="future receipt-backed workflow state writer",
            affected_workflow_state=("performance_dates", "date_confirmation_status"),
            affected_downstream_artifacts=("invoice packet", "subtotal preview", "email attachment preview"),
            approval_gate_refs=("invoice_draft_review_gate", "Guardian/email approval gate"),
            current_capture_authority=False,
            current_write_authority=False,
            current_execution_authority=False,
            next_safe_move="Keep as preview until the governed capture writer exists.",
        ),
        WorkflowBlockCaptureBoundary(
            capture_boundary_id="conversation_request_capture_boundary",
            draft_intent_ref="capital_hilton_telegram_invoice_request_draft",
            capture_label="Prepare draft packet",
            capture_meaning="Future writer would capture operator-confirmed invoice facts before any draft artifact path.",
            required_validation_status="NEEDS_OPERATOR_REVIEW",
            required_operator_action="answer missing questions and explicitly request capture",
            required_receipt_type="OPERATOR_ANSWER_RECEIPT",
            required_state_writer="future workflow block receipt writer",
            affected_workflow_state=("invoice_request", "missing_question_answers"),
            affected_downstream_artifacts=("invoice draft preview packet",),
            approval_gate_refs=("invoice_artifact_approval_bus", "send_email_approval_bus"),
            current_capture_authority=False,
            current_write_authority=False,
            current_execution_authority=False,
            next_safe_move="Ask missing questions; do not draft, send, or submit.",
        ),
        WorkflowBlockCaptureBoundary(
            capture_boundary_id="new_workflow_outline_capture_boundary",
            draft_intent_ref="monthly_client_recap_new_workflow_draft",
            capture_label="Save workflow outline",
            capture_meaning="Future writer would store a reviewed workflow outline as a governed workflow candidate.",
            required_validation_status="NEEDS_CLARIFICATION",
            required_operator_action="review and fill required blocks",
            required_receipt_type="WORKFLOW_PROPOSAL_RECEIPT",
            required_state_writer="future workflow proposal writer",
            affected_workflow_state=("workflow_candidate_outline",),
            affected_downstream_artifacts=("workflow preview",),
            approval_gate_refs=("operator_workflow_activation_gate",),
            current_capture_authority=False,
            current_write_authority=False,
            current_execution_authority=False,
            next_safe_move="Review the proposed block chain together before any durable state exists.",
        ),
        WorkflowBlockCaptureBoundary(
            capture_boundary_id="diagnostic_summary_capture_boundary",
            draft_intent_ref="chief_check_engine_build_blocker_draft",
            capture_label="Keep this diagnostic summary",
            capture_meaning="Future writer would capture a proof-backed diagnostic summary, not execute repair.",
            required_validation_status="NEEDS_PROOF",
            required_operator_action="review proof refs and choose whether to capture summary",
            required_receipt_type="DIAGNOSTIC_SUMMARY_RECEIPT",
            required_state_writer="future diagnostic receipt writer",
            affected_workflow_state=("diagnostic_summary",),
            affected_downstream_artifacts=("repair plan preview",),
            approval_gate_refs=("repair_authority_gate",),
            current_capture_authority=False,
            current_write_authority=False,
            current_execution_authority=False,
            next_safe_move="Capture summary only in a future writer lane; repair remains blocked.",
        ),
    )


def default_conversational_flows() -> tuple[ConversationalWorkflowBlockFlow, ...]:
    return (
        ConversationalWorkflowBlockFlow(
            flow_id="telegram_cassandra_capital_hilton_invoice_request_flow",
            example_request="Send Capital Hilton an invoice for this week's and last week's job.",
            originating_agent="Cassandra",
            originating_surface="Telegram",
            target_workflow="Capital Hilton invoice workflow",
            inferred_blocks=("client", "date_scope", "rate", "invoice_route", "review_packet"),
            system_filled_blocks=("client", "rate if deterministic ref exists", "invoice route if deterministic ref exists"),
            operator_needed_blocks=("exact performance dates if date scope is not deterministic", "proof pointer if required"),
            review_mode="REVIEW_REQUIRED",
            conversation_steps=(
                "Compile request into draft block intents.",
                "Fill known client, rate, and route blocks from deterministic state if available.",
                "Ask only missing questions.",
                "If all answers are known, respond: Cool, I can prepare the draft.",
                "Keep invoice draft review, Guardian review, and email send approval gated.",
            ),
            draft_intents_created=("capital_hilton_telegram_invoice_request_draft",),
            approval_boundaries=("conversation_request_capture_boundary", "invoice_draft_review_gate", "send_email_approval_bus"),
            final_response_shape="Plain response plus preview packet reference; no send or durable capture now.",
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Use conversation to fill the same draft shape Mission Control would render.",
        ),
        ConversationalWorkflowBlockFlow(
            flow_id="new_monthly_client_recap_workflow_request_flow",
            example_request="Set up a monthly client recap workflow for Client X.",
            originating_agent="future workflow agent",
            originating_surface="Cassandra/Clara",
            target_workflow="New monthly client recap workflow candidate",
            inferred_blocks=("client", "cadence", "source_materials", "recap_format", "review_route"),
            system_filled_blocks=("cadence", "workflow goal"),
            operator_needed_blocks=("client canonical ref", "source materials", "recap format", "review route"),
            review_mode="REVIEW_REQUIRED",
            conversation_steps=(
                "Propose a block chain.",
                "Say which blocks the system can fill.",
                "Ask if Winship wants to review and fill it together.",
                "Keep the workflow candidate preview-only.",
            ),
            draft_intents_created=("monthly_client_recap_new_workflow_draft",),
            approval_boundaries=("new_workflow_outline_capture_boundary",),
            final_response_shape="Short proposal with review invitation; no scheduler, send path, or durable workflow.",
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Treat the new flow as a draft proposal until capture and approval exist.",
        ),
        ConversationalWorkflowBlockFlow(
            flow_id="chief_check_engine_build_blocker_flow",
            example_request="What is blocking the build?",
            originating_agent="Chief",
            originating_surface="Mission Control",
            target_workflow="Check Engine diagnostic session",
            inferred_blocks=("diagnostic_sources", "current_blocker", "captain_decision_needed"),
            system_filled_blocks=("diagnostic sources", "current blocker summary if refs are current"),
            operator_needed_blocks=("captain repair/risk decision only if needed",),
            review_mode="REVIEW_RECOMMENDED",
            conversation_steps=(
                "Read current diagnostic read-model/test refs.",
                "Brief the blocker in plain language.",
                "Keep engineering detail below deck unless blocking or summoned.",
                "Ask only for a captain decision if repair risk is present.",
            ),
            draft_intents_created=("chief_check_engine_build_blocker_draft",),
            approval_boundaries=("diagnostic_summary_capture_boundary", "repair_authority_gate"),
            final_response_shape="Captain-facing blocker summary with proof/detail one level down.",
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Show what is blocking the build without running repair.",
        ),
        ConversationalWorkflowBlockFlow(
            flow_id="trusted_low_risk_future_skip_review_shape",
            example_request="Update the label on a low-risk internal note.",
            originating_agent="future workflow agent",
            originating_surface="Mission Control or Telegram",
            target_workflow="Trusted low-risk future workflow",
            inferred_blocks=("note_ref", "label"),
            system_filled_blocks=("note_ref if deterministic",),
            operator_needed_blocks=("label if ambiguous",),
            review_mode="SKIP_REVIEW_ALLOWED",
            conversation_steps=(
                "Only future trusted workflows may model skip-review.",
                "Deterministic validator still checks the update.",
                "Sensitive actions still require receipts, gates, and approval.",
            ),
            draft_intents_created=(),
            approval_boundaries=("future_low_risk_capture_boundary",),
            final_response_shape="Preview-only statement of what would be captured later.",
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Keep skip-review as future-gated and non-executing in this contract.",
        ),
    )


def starship_operating_model_alignment() -> dict[str, Any]:
    return {
        "captain": "operator/final authority",
        "bridge_helm": "command and attention surface that routes work",
        "worlds": "domain work surfaces where workflows are inspected and solved",
        "away_missions": "workflow sessions with one canonical state",
        "crew": "agents that brief, translate, and propose without owning truth",
        "engineering": "proof, sync, tests, receipts, read-models, and diagnostics below deck",
        "ship_logs": "receipts and proof that make durable state auditable",
        "shipyard_mode": "developer/build noise that should not dominate operator surfaces",
        "rules": (
            "Helm routes; worlds do work.",
            "Engineering details stay below deck unless blocking or summoned.",
            "Agents brief, not spam.",
            "Captain sees decisions, not raw telemetry.",
        ),
    }


def _asdict_items(items: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [asdict(item) for item in items]


def build_workflow_block_intent_live_draft_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    del repo_root
    draft_intents = _asdict_items(default_draft_intents())
    workspaces = _asdict_items(default_workspaces())
    proposals = _asdict_items(default_agent_proposals())
    validations = _asdict_items(default_validation_results())
    capture_boundaries = _asdict_items(default_capture_boundaries())
    flows = _asdict_items(default_conversational_flows())
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "doctrine": {
            "summary": "Live draft workspace -> explicit commit boundary -> receipt-backed state.",
            "agents_translate": True,
            "determinism_validates": True,
            "receipts_commit": True,
            "gates_execute": True,
            "this_contract_executes": False,
        },
        "workflow_block_draft_intent_schema": {
            "structure": "WorkflowBlockDraftIntent",
            "required_fields": list(REQUIRED_DRAFT_INTENT_FIELDS),
            "preview_only_default": True,
            "capture_ready_default": False,
            "draft_intent_is_canonical_state": False,
            "mission_control_and_telegram_are_surfaces_not_state_owners": True,
        },
        "live_workflow_draft_workspace_schema": {
            "structure": "LiveWorkflowDraftWorkspace",
            "required_fields": list(REQUIRED_WORKSPACE_FIELDS),
            "stepping_through_blocks_commits_state": False,
            "editing_updates_downstream_preview": True,
            "exploration_is_reversible": True,
            "current_draft_captured_state_distinct": True,
            "commit_capture_explicit": True,
            "stale_previews_invalidate_on_upstream_change": True,
        },
        "workflow_block_agent_compiler_proposal_schema": {
            "structure": "WorkflowBlockAgentCompilerProposal",
            "required_fields": list(REQUIRED_AGENT_PROPOSAL_FIELDS),
            "agent_may_translate_human_language": True,
            "agent_may_fill_from_deterministic_evidence": True,
            "agent_may_propose_new_block_chains": True,
            "agent_may_commit_canonical_state": False,
            "agent_may_approve_send_execute": False,
            "deterministic_validator_decides_validity": True,
        },
        "workflow_block_intent_validation_result_schema": {
            "structure": "WorkflowBlockIntentValidationResult",
            "required_fields": list(REQUIRED_VALIDATION_RESULT_FIELDS),
            "validation_statuses": list(VALIDATION_STATUSES),
            "canonical_write_allowed_by_contract": False,
            "execution_allowed_by_contract": False,
            "normalizes_without_writing_receipts": True,
        },
        "workflow_block_capture_boundary_schema": {
            "structure": "WorkflowBlockCaptureBoundary",
            "required_fields": list(REQUIRED_CAPTURE_BOUNDARY_FIELDS),
            "capture_is_execution": False,
            "capture_requires_future_writer_lane": True,
            "execution_remains_separately_gated": True,
        },
        "conversational_workflow_block_flow_schema": {
            "structure": "ConversationalWorkflowBlockFlow",
            "required_fields": list(REQUIRED_CONVERSATIONAL_FLOW_FIELDS),
            "review_modes": list(REVIEW_MODES),
            "conversation_maps_to_same_draft_shape": True,
        },
        "operations": list(OPERATIONS),
        "origin_surfaces": list(ORIGIN_SURFACES),
        "compatible_surfaces_required": list(COMPATIBLE_SURFACES),
        "compatible_agents_required": list(COMPATIBLE_AGENTS),
        "validation_statuses": list(VALIDATION_STATUSES),
        "review_modes": list(REVIEW_MODES),
        "draft_intents": draft_intents,
        "draft_intents_by_id": {item["draft_intent_id"]: item for item in draft_intents},
        "live_workspaces": workspaces,
        "live_workspaces_by_id": {item["workspace_id"]: item for item in workspaces},
        "agent_compiler_proposals": proposals,
        "agent_compiler_proposals_by_id": {item["proposal_id"]: item for item in proposals},
        "validation_results": validations,
        "validation_results_by_id": {item["validation_id"]: item for item in validations},
        "capture_boundaries": capture_boundaries,
        "capture_boundaries_by_id": {item["capture_boundary_id"]: item for item in capture_boundaries},
        "conversational_flows": flows,
        "conversational_flows_by_id": {item["flow_id"]: item for item in flows},
        "starship_operating_model_alignment": starship_operating_model_alignment(),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "hard_rule": {
            "read_model_only": True,
            "does_not_implement_live_ui": True,
            "does_not_persist_operator_answers": True,
            "does_not_write_receipts": True,
            "does_not_execute_workflow": True,
            "does_not_call_agents_or_models": True,
            "does_not_create_telegram_integration": True,
            "does_not_generate_invoices": True,
            "does_not_send_email": True,
            "may_grant_authority": False,
        },
        "machine_proof": {
            "workflow_block_draft_intent_model_present": True,
            "live_workflow_draft_workspace_model_present": True,
            "agent_compiler_proposal_model_present": True,
            "deterministic_validation_result_model_present": True,
            "capture_boundary_model_present": True,
            "conversational_workflow_block_flow_model_present": True,
            "draft_intent_count": len(draft_intents),
            "workspace_count": len(workspaces),
            "agent_proposal_count": len(proposals),
            "validation_result_count": len(validations),
            "capture_boundary_count": len(capture_boundaries),
            "conversational_flow_count": len(flows),
            "capital_hilton_mission_control_example_present": any(
                item["draft_intent_id"] == "capital_hilton_mission_control_performance_dates_draft"
                for item in draft_intents
            ),
            "telegram_cassandra_invoice_request_example_present": any(
                item["flow_id"] == "telegram_cassandra_capital_hilton_invoice_request_flow" for item in flows
            ),
            "new_workflow_request_example_present": any(
                item["flow_id"] == "new_monthly_client_recap_workflow_request_flow" for item in flows
            ),
            "chief_check_engine_example_present": any(
                item["flow_id"] == "chief_check_engine_build_blocker_flow" for item in flows
            ),
            "current_vs_draft_vs_captured_state_distinct": True,
            "draft_input_updates_downstream_preview": True,
            "agent_proposal_cannot_commit_truth": all(
                item["can_skip_operator_review"] is False
                for item in proposals
                if item["proposal_id"] != "trusted_low_risk_future_skip_review_shape"
            ),
            "validator_cannot_execute": all(item["execution_allowed"] is False for item in validations),
            "capture_boundary_is_explicit": True,
            "channel_agent_neutrality_present": True,
            "all_authority_flags_false": _all_authority_flags_false(),
            "credentials_or_secrets_included": False,
            "raw_private_bodies_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_workflow_block_intent_live_draft_markdown(payload: dict[str, Any]) -> str:
    proof = payload["machine_proof"]
    starship = payload["starship_operating_model_alignment"]
    lines = [
        "# Workflow Block Intent / Live Draft Contract v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "A live draft workspace is a place to try workflow answers before they become permanent. Winship can step through blocks, change values, explore branches, and see previews update without committing canonical state.",
        "",
        "Stepping through blocks is not permanent. Editing a value changes the active draft and downstream preview only. Current OpenClaw state, active draft state, and future captured state stay visibly separate.",
        "",
        "A future Use this draft moment is the capture boundary. That boundary would require deterministic validation, an explicit operator action, a receipt type, and a governed state writer. This contract defines the boundary but does not write anything.",
        "",
        "Agents can help conversationally. Cassandra, Chief, Hermes, Niles, Guardian, Clara, and future workflow agents may translate a request into candidate blocks, fill what is known from deterministic evidence, and ask only the missing questions. Their proposals are not truth.",
        "",
        "Mission Control, Telegram, and agent conversations all use the same draft-intent shape. No surface owns workflow state. The workflow session owns state; surfaces render and propose.",
        "",
        "Deterministic validation and receipts are required because a helpful phrase is not a durable fact. Agents translate. Determinism validates. Receipts commit. Gates execute.",
        "",
        "This is the backend shape that can eventually make the app feel like: that was easy.",
        "",
        "## Examples",
        "",
        "- Capital Hilton Mission Control: adding May 22 and May 29 updates the draft performance dates, marks invoice subtotal and attachment previews stale, and stays preview-only.",
        "- Telegram/Cassandra invoice request: Cassandra can compile the request, fill known client/rate/route fields, ask missing date questions, and keep draft review/send approval gated.",
        "- New workflow request: an agent proposes a block chain and asks whether Winship wants to review and fill it together.",
        "- Chief/check-engine: Chief can brief what is blocking the build from current proof refs and keep engineering detail below deck unless needed.",
        "",
        "## Starship Operating Model",
        "",
        f"- Captain: {starship['captain']}.",
        f"- Bridge/Helm: {starship['bridge_helm']}.",
        f"- Worlds: {starship['worlds']}.",
        f"- Away Missions: {starship['away_missions']}.",
        f"- Crew: {starship['crew']}.",
        f"- Engineering: {starship['engineering']}.",
        f"- Ship Logs: {starship['ship_logs']}.",
        f"- Shipyard Mode: {starship['shipyard_mode']}.",
        "",
        "Helm routes; worlds do work. Engineering details stay below deck unless blocking or summoned. Agents brief, not spam. Captain sees decisions, not raw telemetry.",
        "",
        "## Still Blocked",
        "",
        "- No canonical state write, receipt write, capture write, execution, invoice generation, email draft/send, browser/Coupa/Gmail/Calendar/Telegram access, credential handling, model/tool/agent/runtime/queue execution, ledger write, file write, raw body ingestion, Mac UI work, Mac sync/import, network, or push.",
        "",
        "## Machine Proof Summary",
        "",
        f"- Draft intents: `{proof['draft_intent_count']}`.",
        f"- Live workspaces: `{proof['workspace_count']}`.",
        f"- Agent proposals: `{proof['agent_proposal_count']}`.",
        f"- Validation results: `{proof['validation_result_count']}`.",
        f"- Capture boundaries: `{proof['capture_boundary_count']}`.",
        f"- Conversational flows: `{proof['conversational_flow_count']}`.",
        f"- All authority flags false: `{str(proof['all_authority_flags_false']).lower()}`.",
        f"- Content hash: `{proof['content_hash']}`.",
    ]
    return "\n".join(lines) + "\n"


def export_workflow_block_intent_live_draft_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> WorkflowBlockExportResult:
    payload = build_workflow_block_intent_live_draft_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_workflow_block_intent_live_draft_markdown(payload), encoding="utf-8")
    return WorkflowBlockExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        draft_intent_count=len(payload["draft_intents"]),
        workspace_count=len(payload["live_workspaces"]),
        agent_proposal_count=len(payload["agent_compiler_proposals"]),
        validation_result_count=len(payload["validation_results"]),
        capture_boundary_count=len(payload["capture_boundaries"]),
        conversational_flow_count=len(payload["conversational_flows"]),
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Workflow Block Intent / Live Draft Contract.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_workflow_block_intent_live_draft_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "draft_intent_count": result.draft_intent_count,
        "workspace_count": result.workspace_count,
        "agent_proposal_count": result.agent_proposal_count,
        "validation_result_count": result.validation_result_count,
        "capture_boundary_count": result.capture_boundary_count,
        "conversational_flow_count": result.conversational_flow_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print("Workflow Block Intent / Live Draft Contract exported")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "AUTHORITY_BOUNDARY",
    "COMPATIBLE_AGENTS",
    "COMPATIBLE_SURFACES",
    "CONTRACT_STATUS",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "REQUIRED_AGENT_PROPOSAL_FIELDS",
    "REQUIRED_CAPTURE_BOUNDARY_FIELDS",
    "REQUIRED_CONVERSATIONAL_FLOW_FIELDS",
    "REQUIRED_DRAFT_INTENT_FIELDS",
    "REQUIRED_VALIDATION_RESULT_FIELDS",
    "REQUIRED_WORKSPACE_FIELDS",
    "REVIEW_MODES",
    "SCHEMA_VERSION",
    "VALIDATION_STATUSES",
    "build_workflow_block_intent_live_draft_contract",
    "default_agent_proposals",
    "default_capture_boundaries",
    "default_conversational_flows",
    "default_draft_intents",
    "default_validation_results",
    "default_workspaces",
    "export_workflow_block_intent_live_draft_contract",
    "format_workflow_block_intent_live_draft_markdown",
    "stable_json",
]
