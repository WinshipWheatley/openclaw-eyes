"""Workflow Session / Channel Projection / Approval Bus Contract v0.

This read-model defines one canonical workflow session state with multiple
channel projections and one approval bus per approval event. It prevents
split-brain sessions, duplicate approvals, stale approval mirrors, and stale
channel-local state. It does not implement live Telegram, approval buttons,
email send, invoice generation, workflow-state writes, model/tool/agent/runtime
execution, browser/account access, credential handling, stable-map refresh, or
any live action authority.
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

SCHEMA_VERSION = "workflow_session_channel_projection_approval_bus_contract_v0"
READ_MODEL_ID = "workflow_session_channel_projection_approval_bus_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_WORKFLOW_SESSION_CONTRACT"

WORKFLOW_STATES = (
    "INTAKE_STARTED",
    "WORK_MODE_ACTIVE",
    "DECISION_NODE_ACTIVE",
    "ANSWER_RECEIPTS_COLLECTING",
    "GUIDED_CAPTURE_ACTIVE",
    "PROTECTED_REFERENCE_PENDING",
    "GUARDIAN_REVIEW_PENDING",
    "ARTIFACT_PREVIEW_PENDING",
    "ARTIFACT_PREVIEW_READY",
    "DRAFT_PREVIEW_PENDING",
    "DRAFT_PREVIEW_READY",
    "APPROVAL_REQUEST_READY",
    "APPROVAL_PENDING",
    "APPROVED",
    "ACTION_EXECUTION_PENDING",
    "SENT_OR_SUBMITTED",
    "COMPLETED_WITH_RECEIPT",
    "QUIETED",
    "PARKED",
    "BLOCKED",
    "QUARANTINED",
    "EXPIRED",
    "UNKNOWN_FAIL_CLOSED",
)

CHANNEL_TYPES = (
    "MISSION_CONTROL_FINANCE_WORLD",
    "MISSION_CONTROL_HELM",
    "TELEGRAM",
    "CASSANDRA_CLARA",
    "GUARDIAN",
    "CHIEF",
    "HERMES",
    "UNKNOWN_FAIL_CLOSED",
)

APPROVAL_STATUSES = (
    "NOT_REQUESTED",
    "READY_TO_REQUEST",
    "REQUEST_VISIBLE",
    "PENDING",
    "APPROVED",
    "REJECTED",
    "CANCELLED",
    "EXPIRED",
    "SUPERSEDED",
    "QUARANTINED",
    "UNKNOWN_FAIL_CLOSED",
)

APPROVAL_TYPES = (
    "SEND_EMAIL_APPROVAL",
    "INVOICE_ARTIFACT_APPROVAL",
    "PROTECTED_METADATA_APPROVAL",
    "SECURITY_DELTA_APPROVAL",
    "AUTOMATION_TRIAL_APPROVAL",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_WORKFLOW_SESSION_FIELDS = (
    "workflow_session_id",
    "display_name",
    "workflow_type",
    "world",
    "lane",
    "primary_actor",
    "supporting_actors",
    "entry_channels",
    "current_state",
    "current_step_id",
    "active_solve_path_ref",
    "active_decision_node_ref",
    "guided_capture_refs",
    "answer_receipt_refs",
    "artifact_refs",
    "draft_packet_refs",
    "approval_bus_ref",
    "channel_projection_refs",
    "quieted_step_refs",
    "blocked_actions",
    "stale_state_policy_ref",
    "reopen_policy_ref",
    "next_safe_move",
)

REQUIRED_CHANNEL_PROJECTION_FIELDS = (
    "channel_projection_id",
    "workflow_session_ref",
    "channel_id",
    "channel_type",
    "display_name",
    "can_start_session",
    "can_show_current_step",
    "can_show_choices",
    "can_capture_answer",
    "can_show_guided_capture",
    "can_show_approval",
    "can_submit_approval",
    "local_state_allowed",
    "canonical_state_required",
    "duplicate_session_allowed",
    "stale_projection_policy",
    "blocked_actions",
    "current_authority_granted",
    "next_safe_move",
)

REQUIRED_APPROVAL_BUS_FIELDS = (
    "approval_bus_id",
    "workflow_session_ref",
    "approval_request_id",
    "approval_type",
    "approval_status",
    "approval_question",
    "approval_payload_refs",
    "visible_in_channels",
    "single_signature_required",
    "approval_receipt_ref",
    "invalidation_receipt_refs",
    "stale_mirror_refs",
    "expires_at_policy",
    "can_approve_from_any_channel",
    "can_approve_more_than_once",
    "can_execute_without_approval",
    "operator_final_authority_required",
    "guardian_gate_required",
    "blocked_actions",
    "next_safe_move",
)

REQUIRED_STALE_APPROVAL_POLICY_FIELDS = (
    "policy_id",
    "single_source_of_truth",
    "atomic_invalidation_required",
    "duplicate_approval_blocked",
    "channel_local_state_blocked",
    "approval_expiry_required",
    "supersession_policy",
    "quarantine_policy",
    "receipt_required",
    "next_safe_move",
)

REQUIRED_SESSION_STALENESS_POLICY_FIELDS = (
    "policy_id",
    "idle_state_detection",
    "soft_stale_after",
    "hard_expire_after",
    "stale_state_effect",
    "operator_visibility",
    "approval_state_effect",
    "artifact_state_effect",
    "reopen_allowed",
    "reopen_requires_receipt",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "session_state_write_allowed": False,
    "channel_message_send_allowed": False,
    "telegram_send_allowed": False,
    "approval_submission_allowed": False,
    "email_send_allowed": False,
    "invoice_generation_allowed": False,
    "ledger_write_allowed": False,
    "artifact_generation_allowed": False,
    "browser_automation_allowed": False,
    "credential_handling_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "workflow_execution_allowed": False,
    "operator_input_persistence_allowed": False,
    "network_operation_allowed": False,
    "coupa_access_allowed": False,
    "gmail_calendar_account_access_allowed": False,
    "receipt_write_allowed": False,
    "protected_evidence_write_allowed": False,
    "stable_map_refresh_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "raw_private_body_ingestion_allowed": False,
    "raw_body_ingestion_allowed": False,
    "file_move_delete_cleanup_allowed": False,
}

COMMON_BLOCKED_ACTIONS = (
    "session state write",
    "channel message send",
    "approval submission",
    "email send",
    "invoice generation",
    "ledger write",
    "artifact generation",
    "browser/account access",
    "credential handling",
    "model/tool/agent/runtime/queue execution",
)

PRIOR_LANE_REFS = {
    "operator_work_mode_schema_bandwidth_policy": (
        "generated/read_models/operator_work_mode_schema_bandwidth_policy.json"
    ),
    "operator_solve_path_decision_node_contract": (
        "generated/read_models/operator_solve_path_decision_node_contract.json"
    ),
    "guided_capture_protected_evidence_path_contract": (
        "generated/read_models/guided_capture_protected_evidence_path_contract.json"
    ),
    "capital_hilton_proof_resolution_batch": (
        "generated/read_models/capital_hilton_proof_resolution_batch_manifest.json"
    ),
    "capital_hilton_coupa_po_retrieval_automation_candidate": (
        "generated/read_models/capital_hilton_coupa_po_retrieval_automation_candidate.json"
    ),
    "operator_attention_promotion_contract": "generated/read_models/operator_attention_promotion_contract.json",
    "chief_test_harness_cross_off_receipt_contract": (
        "generated/read_models/chief_test_harness_cross_off_receipt_contract.json"
    ),
    "security_pass_contract": "generated/read_models/security_pass_contract.json",
}


@dataclass(frozen=True)
class OperatorWorkflowSession:
    workflow_session_id: str
    display_name: str
    workflow_type: str
    world: str
    lane: str
    primary_actor: str
    supporting_actors: tuple[str, ...]
    entry_channels: tuple[str, ...]
    current_state: str
    current_step_id: str
    active_solve_path_ref: str
    active_decision_node_ref: str
    guided_capture_refs: tuple[str, ...]
    answer_receipt_refs: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    draft_packet_refs: tuple[str, ...]
    approval_bus_ref: str
    channel_projection_refs: tuple[str, ...]
    quieted_step_refs: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    stale_state_policy_ref: str
    reopen_policy_ref: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowChannelProjection:
    channel_projection_id: str
    workflow_session_ref: str
    channel_id: str
    channel_type: str
    display_name: str
    can_start_session: bool
    can_show_current_step: bool
    can_show_choices: bool
    can_capture_answer: bool
    can_show_guided_capture: bool
    can_show_approval: bool
    can_submit_approval: bool
    local_state_allowed: bool
    canonical_state_required: bool
    duplicate_session_allowed: bool
    stale_projection_policy: str
    blocked_actions: tuple[str, ...]
    current_authority_granted: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowApprovalBus:
    approval_bus_id: str
    workflow_session_ref: str
    approval_request_id: str
    approval_type: str
    approval_status: str
    approval_question: str
    approval_payload_refs: tuple[str, ...]
    visible_in_channels: tuple[str, ...]
    single_signature_required: bool
    approval_receipt_ref: str
    invalidation_receipt_refs: tuple[str, ...]
    stale_mirror_refs: tuple[str, ...]
    expires_at_policy: str
    can_approve_from_any_channel: bool
    can_approve_more_than_once: bool
    can_execute_without_approval: bool
    operator_final_authority_required: bool
    guardian_gate_required: bool
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class StaleApprovalPreventionPolicy:
    policy_id: str
    single_source_of_truth: str
    atomic_invalidation_required: bool
    duplicate_approval_blocked: bool
    channel_local_state_blocked: bool
    approval_expiry_required: bool
    supersession_policy: str
    quarantine_policy: str
    receipt_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowSessionStalenessPolicy:
    policy_id: str
    idle_state_detection: str
    soft_stale_after: str
    hard_expire_after: str
    stale_state_effect: str
    operator_visibility: str
    approval_state_effect: str
    artifact_state_effect: str
    reopen_allowed: bool
    reopen_requires_receipt: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowSessionExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    workflow_session_count: int
    channel_projection_count: int
    approval_bus_count: int
    action_authority_granted: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _generated_at(value: str | None) -> str:
    return value or datetime.now(timezone.utc).isoformat(timespec="seconds")


def _all_authority_flags_false() -> bool:
    return all(value is False for value in AUTHORITY_BOUNDARY.values())


def stale_approval_prevention_policy() -> StaleApprovalPreventionPolicy:
    return StaleApprovalPreventionPolicy(
        policy_id="default_stale_approval_prevention_policy",
        single_source_of_truth="SQLite/receipt-backed workflow session",
        atomic_invalidation_required=True,
        duplicate_approval_blocked=True,
        channel_local_state_blocked=True,
        approval_expiry_required=True,
        supersession_policy=(
            "new approval request supersedes prior visible mirrors only through an invalidation receipt"
        ),
        quarantine_policy=(
            "conflicting channel state, duplicate signatures, or stale payload refs quarantine the approval bus"
        ),
        receipt_required=True,
        next_safe_move="Model one approval object and invalidate stale mirrors before any future action.",
    )


def workflow_session_staleness_policy() -> WorkflowSessionStalenessPolicy:
    return WorkflowSessionStalenessPolicy(
        policy_id="default_workflow_session_staleness_policy",
        idle_state_detection="session has no fresh receipts, answer changes, approval changes, or proof updates",
        soft_stale_after="policy_defined_duration_later",
        hard_expire_after="policy_defined_expiry_later",
        stale_state_effect="session becomes stale/quiet/blocked without live authority",
        operator_visibility="show stale label or quiet with proof; completed and quieted steps remain inspectable",
        approval_state_effect="pending approvals expire or invalidate when stale, cancelled, quarantined, or superseded",
        artifact_state_effect="artifacts remain traceable but cannot imply action readiness",
        reopen_allowed=True,
        reopen_requires_receipt=True,
        next_safe_move="Reopen only through a receipt-backed state change.",
    )


def _session(
    workflow_session_id: str,
    *,
    display_name: str,
    workflow_type: str,
    world: str,
    lane: str,
    primary_actor: str,
    supporting_actors: tuple[str, ...],
    entry_channels: tuple[str, ...],
    current_state: str,
    current_step_id: str,
    active_solve_path_ref: str,
    active_decision_node_ref: str,
    guided_capture_refs: tuple[str, ...],
    answer_receipt_refs: tuple[str, ...],
    artifact_refs: tuple[str, ...],
    draft_packet_refs: tuple[str, ...],
    approval_bus_ref: str,
    channel_projection_refs: tuple[str, ...],
    quieted_step_refs: tuple[str, ...],
    next_safe_move: str,
    blocked_actions: tuple[str, ...] = COMMON_BLOCKED_ACTIONS,
    stale_state_policy_ref: str = "default_workflow_session_staleness_policy",
    reopen_policy_ref: str = "receipt_required_reopen_policy",
) -> OperatorWorkflowSession:
    return OperatorWorkflowSession(
        workflow_session_id=workflow_session_id,
        display_name=display_name,
        workflow_type=workflow_type,
        world=world,
        lane=lane,
        primary_actor=primary_actor,
        supporting_actors=supporting_actors,
        entry_channels=entry_channels,
        current_state=current_state,
        current_step_id=current_step_id,
        active_solve_path_ref=active_solve_path_ref,
        active_decision_node_ref=active_decision_node_ref,
        guided_capture_refs=guided_capture_refs,
        answer_receipt_refs=answer_receipt_refs,
        artifact_refs=artifact_refs,
        draft_packet_refs=draft_packet_refs,
        approval_bus_ref=approval_bus_ref,
        channel_projection_refs=channel_projection_refs,
        quieted_step_refs=quieted_step_refs,
        blocked_actions=blocked_actions,
        stale_state_policy_ref=stale_state_policy_ref,
        reopen_policy_ref=reopen_policy_ref,
        next_safe_move=next_safe_move,
    )


def default_workflow_sessions() -> tuple[OperatorWorkflowSession, ...]:
    return (
        _session(
            "capital_hilton_invoice_workflow_session",
            display_name="Capital Hilton Invoice Workflow Session",
            workflow_type="FINANCE_WORKFLOW",
            world="Finance",
            lane="Capital Hilton",
            primary_actor="Cassandra",
            supporting_actors=("Guardian", "Chief"),
            entry_channels=(
                "MISSION_CONTROL_FINANCE_WORLD",
                "TELEGRAM",
                "CASSANDRA_CLARA",
                "GUARDIAN",
                "CHIEF",
            ),
            current_state="DECISION_NODE_ACTIVE",
            current_step_id="confirm_performance_dates",
            active_solve_path_ref="capital_hilton_invoice_solve_path",
            active_decision_node_ref="confirm_performance_dates",
            guided_capture_refs=("capital_hilton_coupa_po_screen_capture_path", "capital_hilton_rate_source_capture_path"),
            answer_receipt_refs=(),
            artifact_refs=(),
            draft_packet_refs=(),
            approval_bus_ref="capital_hilton_invoice_approval_bus",
            channel_projection_refs=(
                "finance_world_projection",
                "telegram_projection",
                "cassandra_clara_projection",
                "guardian_projection",
                "chief_projection",
                "helm_summary_projection",
            ),
            quieted_step_refs=(),
            next_safe_move="Render one Capital Hilton session across all channels; do not request approval yet.",
        ),
        _session(
            "chief_terrain_reconciliation_session",
            display_name="Chief Terrain Reconciliation Session",
            workflow_type="CONCEPT_TERRAIN_RECONCILIATION",
            world="Operations / Build",
            lane="Chief terrain reconciliation",
            primary_actor="Chief",
            supporting_actors=("Hermes",),
            entry_channels=("MISSION_CONTROL_HELM", "CHIEF", "HERMES"),
            current_state="WORK_MODE_ACTIVE",
            current_step_id="chief_terrain_currentness",
            active_solve_path_ref="chief_terrain_reconciliation_solve_path",
            active_decision_node_ref="chief_terrain_currentness",
            guided_capture_refs=("chief_terrain_source_note_capture_path",),
            answer_receipt_refs=(),
            artifact_refs=(),
            draft_packet_refs=(),
            approval_bus_ref="chief_terrain_reconciliation_approval_bus",
            channel_projection_refs=("chief_terrain_helm_projection", "chief_terrain_chief_projection", "chief_terrain_hermes_projection"),
            quieted_step_refs=(),
            next_safe_move="Keep terrain state canonical; no source rewrite or archive action.",
        ),
        _session(
            "check_engine_diagnostic_session",
            display_name="Check Engine Diagnostic Session",
            workflow_type="DEVELOPER_SYSTEM_REPAIR",
            world="Build",
            lane="Check Engine",
            primary_actor="Chief",
            supporting_actors=("Guardian",),
            entry_channels=("MISSION_CONTROL_HELM", "CHIEF", "GUARDIAN"),
            current_state="WORK_MODE_ACTIVE",
            current_step_id="check_engine_actual_breakage",
            active_solve_path_ref="check_engine_diagnostic_solve_path",
            active_decision_node_ref="check_engine_actual_breakage",
            guided_capture_refs=("check_engine_diagnostic_screenshot_capture_path",),
            answer_receipt_refs=(),
            artifact_refs=(),
            draft_packet_refs=(),
            approval_bus_ref="check_engine_diagnostic_approval_bus",
            channel_projection_refs=("check_engine_helm_projection", "check_engine_chief_projection", "check_engine_guardian_projection"),
            quieted_step_refs=(),
            next_safe_move="Classify diagnostic evidence; do not execute repair.",
        ),
        _session(
            "cassandra_clara_draft_review_session",
            display_name="Cassandra / Clara Draft Review Session",
            workflow_type="COMMUNICATION_DRAFT_SEND_WORKFLOW",
            world="Communications",
            lane="Cassandra / Clara drafts",
            primary_actor="Cassandra",
            supporting_actors=("Guardian",),
            entry_channels=("MISSION_CONTROL_HELM", "TELEGRAM", "CASSANDRA_CLARA", "GUARDIAN"),
            current_state="DRAFT_PREVIEW_PENDING",
            current_step_id="draft_review_state",
            active_solve_path_ref="cassandra_clara_draft_work_mode",
            active_decision_node_ref="draft_review_state",
            guided_capture_refs=("cassandra_draft_review_capture_path",),
            answer_receipt_refs=(),
            artifact_refs=(),
            draft_packet_refs=("generated/read_models/cassandra_draft_review_packet.json",),
            approval_bus_ref="cassandra_clara_draft_approval_bus",
            channel_projection_refs=(
                "draft_review_helm_projection",
                "draft_review_telegram_projection",
                "draft_review_cassandra_projection",
                "draft_review_guardian_projection",
            ),
            quieted_step_refs=(),
            next_safe_move="Preview draft review state only; no send authority.",
        ),
        _session(
            "automation_trial_session",
            display_name="Automation Trial Session",
            workflow_type="AUTOMATION_CANDIDATE",
            world="Finance / Automation Candidate",
            lane="Coupa / PO automation candidate",
            primary_actor="Chief",
            supporting_actors=("Guardian",),
            entry_channels=("MISSION_CONTROL_HELM", "GUARDIAN", "CHIEF"),
            current_state="BLOCKED",
            current_step_id="coupa_po_manual_or_automation",
            active_solve_path_ref="coupa_po_automation_candidate_solve_path",
            active_decision_node_ref="coupa_po_manual_or_automation",
            guided_capture_refs=("capital_hilton_coupa_po_screen_capture_path",),
            answer_receipt_refs=(),
            artifact_refs=(),
            draft_packet_refs=(),
            approval_bus_ref="automation_trial_approval_bus",
            channel_projection_refs=("automation_trial_helm_projection", "automation_trial_guardian_projection", "automation_trial_chief_projection"),
            quieted_step_refs=(),
            next_safe_move="Keep automation trial parked or blocked until future authority exists.",
        ),
    )


def _projection(
    channel_projection_id: str,
    *,
    workflow_session_ref: str,
    channel_id: str,
    channel_type: str,
    display_name: str,
    can_start_session: bool,
    can_show_current_step: bool = True,
    can_show_choices: bool = True,
    can_capture_answer: bool = False,
    can_show_guided_capture: bool = True,
    can_show_approval: bool = True,
    can_submit_approval: bool = False,
    local_state_allowed: bool = False,
    canonical_state_required: bool = True,
    duplicate_session_allowed: bool = False,
    stale_projection_policy: str = "must_refresh_from_canonical_session_or_show_stale",
    current_authority_granted: bool = False,
    blocked_actions: tuple[str, ...] = COMMON_BLOCKED_ACTIONS,
    next_safe_move: str = "Render canonical session state only.",
) -> WorkflowChannelProjection:
    return WorkflowChannelProjection(
        channel_projection_id=channel_projection_id,
        workflow_session_ref=workflow_session_ref,
        channel_id=channel_id,
        channel_type=channel_type,
        display_name=display_name,
        can_start_session=can_start_session,
        can_show_current_step=can_show_current_step,
        can_show_choices=can_show_choices,
        can_capture_answer=can_capture_answer,
        can_show_guided_capture=can_show_guided_capture,
        can_show_approval=can_show_approval,
        can_submit_approval=can_submit_approval,
        local_state_allowed=local_state_allowed,
        canonical_state_required=canonical_state_required,
        duplicate_session_allowed=duplicate_session_allowed,
        stale_projection_policy=stale_projection_policy,
        blocked_actions=blocked_actions,
        current_authority_granted=current_authority_granted,
        next_safe_move=next_safe_move,
    )


def default_channel_projections() -> tuple[WorkflowChannelProjection, ...]:
    capital_session = "capital_hilton_invoice_workflow_session"
    return (
        _projection(
            "finance_world_projection",
            workflow_session_ref=capital_session,
            channel_id="mission_control_finance_world",
            channel_type="MISSION_CONTROL_FINANCE_WORLD",
            display_name="Finance World Projection",
            can_start_session=True,
            can_capture_answer=False,
            next_safe_move="Show Capital Hilton's canonical session in Finance World only.",
        ),
        _projection(
            "telegram_projection",
            workflow_session_ref=capital_session,
            channel_id="telegram",
            channel_type="TELEGRAM",
            display_name="Telegram Projection",
            can_start_session=True,
            can_capture_answer=False,
            can_show_guided_capture=True,
            next_safe_move="Telegram may mirror the session later, but cannot own local state or send now.",
        ),
        _projection(
            "cassandra_clara_projection",
            workflow_session_ref=capital_session,
            channel_id="cassandra_clara",
            channel_type="CASSANDRA_CLARA",
            display_name="Cassandra / Clara Projection",
            can_start_session=False,
            can_capture_answer=False,
            next_safe_move="Render drafts or candidate state later without owning workflow state.",
        ),
        _projection(
            "guardian_projection",
            workflow_session_ref=capital_session,
            channel_id="guardian",
            channel_type="GUARDIAN",
            display_name="Guardian Projection",
            can_start_session=False,
            can_show_choices=False,
            can_show_guided_capture=True,
            next_safe_move="Render review/approval posture later without owning invoice workflow.",
        ),
        _projection(
            "chief_projection",
            workflow_session_ref=capital_session,
            channel_id="chief",
            channel_type="CHIEF",
            display_name="Chief Projection",
            can_start_session=False,
            can_capture_answer=False,
            next_safe_move="Verify/reconcile later without executing workflow.",
        ),
        _projection(
            "helm_summary_projection",
            workflow_session_ref=capital_session,
            channel_id="mission_control_helm",
            channel_type="MISSION_CONTROL_HELM",
            display_name="Helm Summary Projection",
            can_start_session=False,
            can_show_guided_capture=False,
            next_safe_move="Show one summary card for the canonical session.",
        ),
        _projection(
            "chief_terrain_helm_projection",
            workflow_session_ref="chief_terrain_reconciliation_session",
            channel_id="mission_control_helm",
            channel_type="MISSION_CONTROL_HELM",
            display_name="Chief Terrain Helm Projection",
            can_start_session=True,
        ),
        _projection(
            "chief_terrain_chief_projection",
            workflow_session_ref="chief_terrain_reconciliation_session",
            channel_id="chief",
            channel_type="CHIEF",
            display_name="Chief Terrain Chief Projection",
            can_start_session=False,
        ),
        _projection(
            "chief_terrain_hermes_projection",
            workflow_session_ref="chief_terrain_reconciliation_session",
            channel_id="hermes",
            channel_type="HERMES",
            display_name="Chief Terrain Hermes Projection",
            can_start_session=False,
            can_show_approval=False,
        ),
        _projection(
            "check_engine_helm_projection",
            workflow_session_ref="check_engine_diagnostic_session",
            channel_id="mission_control_helm",
            channel_type="MISSION_CONTROL_HELM",
            display_name="Check Engine Helm Projection",
            can_start_session=True,
        ),
        _projection(
            "check_engine_chief_projection",
            workflow_session_ref="check_engine_diagnostic_session",
            channel_id="chief",
            channel_type="CHIEF",
            display_name="Check Engine Chief Projection",
            can_start_session=False,
        ),
        _projection(
            "check_engine_guardian_projection",
            workflow_session_ref="check_engine_diagnostic_session",
            channel_id="guardian",
            channel_type="GUARDIAN",
            display_name="Check Engine Guardian Projection",
            can_start_session=False,
            can_show_approval=True,
        ),
        _projection(
            "draft_review_helm_projection",
            workflow_session_ref="cassandra_clara_draft_review_session",
            channel_id="mission_control_helm",
            channel_type="MISSION_CONTROL_HELM",
            display_name="Draft Review Helm Projection",
            can_start_session=True,
        ),
        _projection(
            "draft_review_telegram_projection",
            workflow_session_ref="cassandra_clara_draft_review_session",
            channel_id="telegram",
            channel_type="TELEGRAM",
            display_name="Draft Review Telegram Projection",
            can_start_session=True,
            next_safe_move="Telegram may mirror draft review later; no send or local state.",
        ),
        _projection(
            "draft_review_cassandra_projection",
            workflow_session_ref="cassandra_clara_draft_review_session",
            channel_id="cassandra_clara",
            channel_type="CASSANDRA_CLARA",
            display_name="Draft Review Cassandra / Clara Projection",
            can_start_session=False,
        ),
        _projection(
            "draft_review_guardian_projection",
            workflow_session_ref="cassandra_clara_draft_review_session",
            channel_id="guardian",
            channel_type="GUARDIAN",
            display_name="Draft Review Guardian Projection",
            can_start_session=False,
        ),
        _projection(
            "automation_trial_helm_projection",
            workflow_session_ref="automation_trial_session",
            channel_id="mission_control_helm",
            channel_type="MISSION_CONTROL_HELM",
            display_name="Automation Trial Helm Projection",
            can_start_session=True,
        ),
        _projection(
            "automation_trial_guardian_projection",
            workflow_session_ref="automation_trial_session",
            channel_id="guardian",
            channel_type="GUARDIAN",
            display_name="Automation Trial Guardian Projection",
            can_start_session=False,
        ),
        _projection(
            "automation_trial_chief_projection",
            workflow_session_ref="automation_trial_session",
            channel_id="chief",
            channel_type="CHIEF",
            display_name="Automation Trial Chief Projection",
            can_start_session=False,
        ),
    )


def _approval_bus(
    approval_bus_id: str,
    *,
    workflow_session_ref: str,
    approval_request_id: str,
    approval_type: str,
    approval_status: str,
    approval_question: str,
    approval_payload_refs: tuple[str, ...],
    visible_in_channels: tuple[str, ...],
    guardian_gate_required: bool,
    next_safe_move: str,
    approval_receipt_ref: str = "future_approval_receipt_ref",
    invalidation_receipt_refs: tuple[str, ...] = (),
    stale_mirror_refs: tuple[str, ...] = (),
    expires_at_policy: str = "approval expires under default stale approval prevention policy",
    single_signature_required: bool = True,
    can_approve_from_any_channel: bool = True,
    can_approve_more_than_once: bool = False,
    can_execute_without_approval: bool = False,
    operator_final_authority_required: bool = True,
    blocked_actions: tuple[str, ...] = COMMON_BLOCKED_ACTIONS,
) -> WorkflowApprovalBus:
    return WorkflowApprovalBus(
        approval_bus_id=approval_bus_id,
        workflow_session_ref=workflow_session_ref,
        approval_request_id=approval_request_id,
        approval_type=approval_type,
        approval_status=approval_status,
        approval_question=approval_question,
        approval_payload_refs=approval_payload_refs,
        visible_in_channels=visible_in_channels,
        single_signature_required=single_signature_required,
        approval_receipt_ref=approval_receipt_ref,
        invalidation_receipt_refs=invalidation_receipt_refs,
        stale_mirror_refs=stale_mirror_refs,
        expires_at_policy=expires_at_policy,
        can_approve_from_any_channel=can_approve_from_any_channel,
        can_approve_more_than_once=can_approve_more_than_once,
        can_execute_without_approval=can_execute_without_approval,
        operator_final_authority_required=operator_final_authority_required,
        guardian_gate_required=guardian_gate_required,
        blocked_actions=blocked_actions,
        next_safe_move=next_safe_move,
    )


def default_approval_buses() -> tuple[WorkflowApprovalBus, ...]:
    return (
        _approval_bus(
            "capital_hilton_invoice_approval_bus",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            approval_request_id="capital_hilton_invoice_approval_request_future",
            approval_type="INVOICE_ARTIFACT_APPROVAL",
            approval_status="NOT_REQUESTED",
            approval_question="Should the Capital Hilton invoice artifact be approved later?",
            approval_payload_refs=(),
            visible_in_channels=("finance_world_projection", "telegram_projection", "guardian_projection"),
            guardian_gate_required=True,
            next_safe_move="Do not request approval until proof, artifact preview, and gates exist.",
        ),
        _approval_bus(
            "chief_terrain_reconciliation_approval_bus",
            workflow_session_ref="chief_terrain_reconciliation_session",
            approval_request_id="chief_terrain_reconciliation_approval_request_future",
            approval_type="UNKNOWN_FAIL_CLOSED",
            approval_status="NOT_REQUESTED",
            approval_question="Should terrain reconciliation state be accepted later?",
            approval_payload_refs=("generated/read_models/openclaw_work_terrain_gap_detector.json",),
            visible_in_channels=("chief_terrain_helm_projection", "chief_terrain_chief_projection", "chief_terrain_hermes_projection"),
            guardian_gate_required=False,
            next_safe_move="Keep as reconciliation preview only.",
        ),
        _approval_bus(
            "check_engine_diagnostic_approval_bus",
            workflow_session_ref="check_engine_diagnostic_session",
            approval_request_id="check_engine_repair_approval_request_future",
            approval_type="SECURITY_DELTA_APPROVAL",
            approval_status="NOT_REQUESTED",
            approval_question="Should a repair lane be approved later?",
            approval_payload_refs=("generated/read_models/chief_check_engine_diagnostic_package.json",),
            visible_in_channels=("check_engine_helm_projection", "check_engine_chief_projection", "check_engine_guardian_projection"),
            guardian_gate_required=True,
            next_safe_move="Do not request repair approval here.",
        ),
        _approval_bus(
            "cassandra_clara_draft_approval_bus",
            workflow_session_ref="cassandra_clara_draft_review_session",
            approval_request_id="cassandra_clara_send_approval_request_future",
            approval_type="SEND_EMAIL_APPROVAL",
            approval_status="NOT_REQUESTED",
            approval_question="Should the draft be sent later?",
            approval_payload_refs=("generated/read_models/cassandra_draft_review_packet.json",),
            visible_in_channels=("draft_review_helm_projection", "draft_review_telegram_projection", "draft_review_guardian_projection"),
            guardian_gate_required=True,
            next_safe_move="Show draft approval as not requested; no send authority.",
        ),
        _approval_bus(
            "automation_trial_approval_bus",
            workflow_session_ref="automation_trial_session",
            approval_request_id="automation_trial_approval_request_future",
            approval_type="AUTOMATION_TRIAL_APPROVAL",
            approval_status="NOT_REQUESTED",
            approval_question="Should a future supervised automation trial be approved?",
            approval_payload_refs=("generated/read_models/capital_hilton_coupa_po_retrieval_automation_candidate.json",),
            visible_in_channels=("automation_trial_helm_projection", "automation_trial_guardian_projection", "automation_trial_chief_projection"),
            guardian_gate_required=True,
            next_safe_move="Keep automation trial blocked or parked.",
        ),
    )


def relationship_to_prior_lanes(repo_root: str | Path = ROOT) -> list[dict[str, Any]]:
    root = Path(repo_root)
    return [
        {
            "lane_id": lane_id,
            "read_model_ref": ref,
            "observation_status": "OBSERVED" if (root / ref).exists() else "NOT_OBSERVED_OR_PENDING",
            "relationship": "workflow session projection references prior deterministic rails without duplicating them",
        }
        for lane_id, ref in PRIOR_LANE_REFS.items()
    ]


def build_workflow_session_channel_projection_approval_bus_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    sessions = [asdict(item) for item in default_workflow_sessions()]
    projections = [asdict(item) for item in default_channel_projections()]
    approval_buses = [asdict(item) for item in default_approval_buses()]
    stale_approval_policy = asdict(stale_approval_prevention_policy())
    staleness_policy = asdict(workflow_session_staleness_policy())
    prior_lanes = relationship_to_prior_lanes(repo_root)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": f"{READ_MODEL_ID}_v0",
        "generated_at": _generated_at(generated_at),
        "contract_status": CONTRACT_STATUS,
        "core_doctrine": {
            "workflow_session_owns_state": True,
            "surfaces_render_state": True,
            "operator_answers_once": True,
            "receipts_update_everywhere": True,
            "approval_exists_once": True,
            "approve_from_one_channel_closes_all_mirrors": True,
            "no_stale_approvals_survive_terminal_state": True,
            "capital_hilton_is_steel_thread_example_not_boundary": True,
            "app_wide_workflow_agnostic_contract": True,
        },
        "workflow_states": list(WORKFLOW_STATES),
        "channel_types": list(CHANNEL_TYPES),
        "approval_statuses": list(APPROVAL_STATUSES),
        "approval_types": list(APPROVAL_TYPES),
        "operator_workflow_session_schema": {
            "structure": "OperatorWorkflowSession",
            "required_fields": list(REQUIRED_WORKFLOW_SESSION_FIELDS),
            "one_canonical_session_per_active_intent": True,
            "duplicate_session_requires_explicit_fork_receipt": True,
        },
        "workflow_channel_projection_schema": {
            "structure": "WorkflowChannelProjection",
            "required_fields": list(REQUIRED_CHANNEL_PROJECTION_FIELDS),
            "channels_own_independent_state": False,
            "canonical_state_required": True,
        },
        "workflow_approval_bus_schema": {
            "structure": "WorkflowApprovalBus",
            "required_fields": list(REQUIRED_APPROVAL_BUS_FIELDS),
            "single_approval_object_per_approval_event": True,
            "approval_requires_session_ref": True,
            "stale_mirrors_close_on_receipt": True,
        },
        "stale_approval_prevention_policy_schema": {
            "structure": "StaleApprovalPreventionPolicy",
            "required_fields": list(REQUIRED_STALE_APPROVAL_POLICY_FIELDS),
        },
        "workflow_session_staleness_policy_schema": {
            "structure": "WorkflowSessionStalenessPolicy",
            "required_fields": list(REQUIRED_SESSION_STALENESS_POLICY_FIELDS),
        },
        "workflow_sessions": sessions,
        "workflow_sessions_by_id": {item["workflow_session_id"]: item for item in sessions},
        "channel_projections": projections,
        "channel_projections_by_id": {item["channel_projection_id"]: item for item in projections},
        "approval_buses": approval_buses,
        "approval_buses_by_id": {item["approval_bus_id"]: item for item in approval_buses},
        "stale_approval_prevention_policy": stale_approval_policy,
        "workflow_session_staleness_policy": staleness_policy,
        "session_integrity_policy": {
            "one_canonical_session_per_active_workflow_intent": True,
            "channels_may_request_display_update_only_through_canonical_receipt_state_model": True,
            "channel_owns_independent_workflow_state": False,
            "duplicate_workflow_sessions_for_same_intent_allowed": False,
            "explicit_fork_requires_receipt": True,
        },
        "approval_invariants": {
            "single_approval_object_per_event": True,
            "approving_one_channel_invalidates_all_visible_mirrors": True,
            "approval_cannot_be_submitted_twice": True,
            "approval_cannot_exist_without_session_ref": True,
            "approval_cannot_execute_action_without_future_authority_and_gates": True,
            "approval_receipt_must_close_stale_projections": True,
            "stale_approvals_expire_or_invalidate": True,
        },
        "relationship_to_prior_lanes": prior_lanes,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "hard_rule": {
            "read_model_only": True,
            "does_not_implement_live_telegram": True,
            "does_not_implement_live_approval_buttons": True,
            "does_not_implement_email_send": True,
            "does_not_implement_invoice_generation": True,
            "does_not_write_workflow_state": True,
            "does_not_refresh_stable_map": True,
            "may_submit_approval_now": False,
            "may_send_message_now": False,
            "may_execute_action_now": False,
        },
        "machine_proof": {
            "workflow_session_model_present": True,
            "channel_projection_model_present": True,
            "approval_bus_model_present": True,
            "stale_approval_policy_present": True,
            "session_staleness_policy_present": True,
            "workflow_session_count": len(sessions),
            "channel_projection_count": len(projections),
            "approval_bus_count": len(approval_buses),
            "capital_hilton_session_present": any(
                item["workflow_session_id"] == "capital_hilton_invoice_workflow_session" for item in sessions
            ),
            "finance_world_and_telegram_attach_same_session": (
                {item["channel_projection_id"]: item["workflow_session_ref"] for item in projections}[
                    "finance_world_projection"
                ]
                == {item["channel_projection_id"]: item["workflow_session_ref"] for item in projections}[
                    "telegram_projection"
                ]
            ),
            "duplicate_sessions_blocked": True,
            "channel_local_state_blocked": all(item["local_state_allowed"] is False for item in projections),
            "duplicate_projection_sessions_blocked": all(
                item["duplicate_session_allowed"] is False for item in projections
            ),
            "single_approval_object_invariant": True,
            "approval_more_than_once_blocked": all(
                item["can_approve_more_than_once"] is False for item in approval_buses
            ),
            "approval_execute_without_approval_blocked": all(
                item["can_execute_without_approval"] is False for item in approval_buses
            ),
            "stale_approval_invalidation_required": stale_approval_policy[
                "atomic_invalidation_required"
            ]
            is True,
            "session_staleness_reopen_requires_receipt": staleness_policy["reopen_requires_receipt"] is True,
            "all_authority_flags_false": _all_authority_flags_false(),
            "action_authority_granted": False,
            "credentials_or_secrets_included": False,
            "raw_private_bodies_included": False,
            "prior_lane_ref_count": len(prior_lanes),
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_workflow_session_operator_markdown(payload: dict[str, Any]) -> str:
    proof = payload["machine_proof"]
    capital = payload["workflow_sessions_by_id"]["capital_hilton_invoice_workflow_session"]
    lines = [
        "# Workflow Session / Channel Projection / Approval Bus Contract v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "A workflow session is the one canonical state for a piece of work. Finance World, Telegram, Cassandra/Clara, Guardian, Chief, and the Helm may show that same state, but they do not each get their own separate version of the workflow.",
        "",
        "This prevents split-brain. Winship answers once. A future receipt updates the canonical session. Every surface reads that state instead of keeping a private copy.",
        "",
        "## Why Approve Once Matters",
        "",
        "Stale approval mirrors are dangerous because one channel might show an old approval after another channel already approved, rejected, expired, cancelled, quarantined, or superseded it. The approval bus says approval exists once, approving from one channel closes every mirror, and duplicate approval is blocked.",
        "",
        "## Capital Hilton Session",
        "",
        f"- Session: `{capital['workflow_session_id']}`.",
        f"- Current state: `{capital['current_state']}`.",
        f"- Active solve path: `{capital['active_solve_path_ref']}`.",
        "- Finance World and Telegram attach to the same canonical session.",
        "- Invoice/send authority remains false.",
        "",
        "## Channel Roles",
        "",
        "- Finance World may later be an entry/control surface, but it reads the session.",
        "- Telegram may later mirror or control the same session, but it cannot keep split local state.",
        "- Cassandra/Clara may render draft or communication state later, but does not own workflow truth.",
        "- Guardian may render review/approval state later, but does not own the invoice workflow.",
        "- Chief may verify completion or reconciliation later, but does not execute the workflow.",
        "",
        "## Modeled, Not Live",
        "",
        "- No live Telegram, approval buttons, email send, invoice generation, workflow-state writes, ledger writes, browser/account access, model/tool/agent/runtime/queue execution, or stable-map refresh.",
        "",
        "## Prompt 5",
        "",
        "- Prompt 5 should add automation readiness / feasibility and the integrated stable-map refresh plan for this batch.",
        "",
        "## Machine Proof Summary",
        "",
        f"- Workflow sessions: `{proof['workflow_session_count']}`.",
        f"- Channel projections: `{proof['channel_projection_count']}`.",
        f"- Approval buses: `{proof['approval_bus_count']}`.",
        f"- Finance World and Telegram same session: `{str(proof['finance_world_and_telegram_attach_same_session']).lower()}`.",
        f"- Approval more than once blocked: `{str(proof['approval_more_than_once_blocked']).lower()}`.",
        f"- All authority flags false: `{str(proof['all_authority_flags_false']).lower()}`.",
        f"- Content hash: `{proof['content_hash']}`.",
    ]
    return "\n".join(lines) + "\n"


def export_workflow_session_channel_projection_approval_bus_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> WorkflowSessionExportResult:
    payload = build_workflow_session_channel_projection_approval_bus_contract(
        repo_root=repo_root,
        generated_at=generated_at,
    )
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_workflow_session_operator_markdown(payload), encoding="utf-8")
    return WorkflowSessionExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        workflow_session_count=len(payload["workflow_sessions"]),
        channel_projection_count=len(payload["channel_projections"]),
        approval_bus_count=len(payload["approval_buses"]),
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Workflow Session / Channel Projection / Approval Bus Contract."
    )
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_workflow_session_channel_projection_approval_bus_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "workflow_session_count": result.workflow_session_count,
        "channel_projection_count": result.channel_projection_count,
        "approval_bus_count": result.approval_bus_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print("Workflow Session / Channel Projection / Approval Bus Contract exported")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "APPROVAL_STATUSES",
    "APPROVAL_TYPES",
    "AUTHORITY_BOUNDARY",
    "CHANNEL_TYPES",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "REQUIRED_APPROVAL_BUS_FIELDS",
    "REQUIRED_CHANNEL_PROJECTION_FIELDS",
    "REQUIRED_SESSION_STALENESS_POLICY_FIELDS",
    "REQUIRED_STALE_APPROVAL_POLICY_FIELDS",
    "REQUIRED_WORKFLOW_SESSION_FIELDS",
    "SCHEMA_VERSION",
    "WORKFLOW_STATES",
    "build_workflow_session_channel_projection_approval_bus_contract",
    "default_approval_buses",
    "default_channel_projections",
    "default_workflow_sessions",
    "export_workflow_session_channel_projection_approval_bus_contract",
    "format_workflow_session_operator_markdown",
    "relationship_to_prior_lanes",
    "stable_json",
    "stale_approval_prevention_policy",
    "workflow_session_staleness_policy",
]
