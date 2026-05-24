"""Agent Conversation Handoff / Step Packet Contract v0.

This deterministic read-model defines how operator conversations, agent
handoffs, focused system step packets, below-deck agent/system exchanges,
operator handoff packets, liveness status, and timeout/recovery policy fit
together. It models protocol and visibility only. It does not execute agents,
call models, send messages, write receipts or state, access external systems,
run queues/runtimes, modify Mission Control Swift code, run Mac sync/import, use
network, or grant live authority.
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

SCHEMA_VERSION = "agent_conversation_handoff_step_packet_contract_v0"
READ_MODEL_ID = "agent_conversation_handoff_step_packet_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_AGENT_HANDOFF_CONTRACT"

PHASES = (
    "USER_UTTERANCE_RECEIVED",
    "AGENT_INTERPRETING",
    "SYSTEM_PACKET_REQUESTED",
    "SYSTEM_PACKET_READY",
    "AGENT_WORKING_PACKET",
    "AGENT_RETURNING_BRIEFING",
    "WAITING_ON_OPERATOR",
    "WAITING_ON_SYSTEM",
    "WAITING_ON_GUARDIAN",
    "WAITING_ON_PROOF",
    "HANDOFF_COMPLETE",
    "PARKED",
    "BLOCKED",
    "OFFLINE",
    "TIMED_OUT",
    "UNKNOWN_FAIL_CLOSED",
)

PACKET_TYPES = (
    "INTENT_CLASSIFICATION_PACKET",
    "BLOCK_FILL_PACKET",
    "DISCOVERY_PACKET",
    "PROOF_LOOKUP_PACKET",
    "DRAFT_REVIEW_PACKET",
    "APPROVAL_PREP_PACKET",
    "CHIEF_DIAGNOSTIC_PACKET",
    "GUARDIAN_REVIEW_PACKET",
    "HERMES_ADVISORY_PACKET",
    "NILES_PROJECT_PACKET",
    "UNKNOWN_FAIL_CLOSED",
)

EXCHANGE_TYPES = (
    "PACKET_REQUEST",
    "PACKET_DELIVERY",
    "CONTEXT_REQUEST",
    "PROOF_REF_REQUEST",
    "VALIDATION_REQUEST",
    "DRAFT_INTENT_RETURN",
    "BLOCKED_RETURN",
    "OPERATOR_HANDOFF_REQUEST",
    "STATUS_UPDATE",
    "UNKNOWN_FAIL_CLOSED",
)

HANDOFF_TYPES = (
    "CLARIFY_INTENT",
    "ANSWER_MISSING_BLOCK",
    "REVIEW_DRAFT",
    "APPROVE_PACKET",
    "APPROVE_SEND",
    "CHOOSE_DISCOVERY_PATH",
    "SECURITY_DECISION",
    "CHECK_ENGINE_DECISION",
    "STATUS_UPDATE_ONLY",
    "UNKNOWN_FAIL_CLOSED",
)

STATUS_STATES = (
    "IDLE",
    "THINKING",
    "TYPING",
    "MAKING_PACKET",
    "WAITING_ON_SYSTEM",
    "WAITING_ON_OPERATOR",
    "WAITING_ON_TOOL_AUTHORITY",
    "WAITING_ON_PROOF",
    "VALIDATING",
    "RETURNING_BRIEFING",
    "OFFLINE",
    "STALLED",
    "TIMED_OUT",
    "BLOCKED",
    "HANDOFF_COMPLETE",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_HANDOFF_SESSION_FIELDS = (
    "handoff_session_id",
    "originating_surface",
    "originating_actor",
    "target_agent",
    "target_world",
    "target_lane",
    "workflow_session_ref",
    "user_utterance",
    "inferred_intent",
    "current_phase",
    "current_status",
    "visible_status_label",
    "agent_liveness_ref",
    "active_step_packet_ref",
    "pending_operator_question_ref",
    "pending_system_request_ref",
    "draft_intent_refs",
    "crew_briefing_refs",
    "authority_boundary",
    "timeout_policy_ref",
    "handoff_return_target",
    "next_safe_move",
)

REQUIRED_STEP_PACKET_FIELDS = (
    "step_packet_id",
    "handoff_session_ref",
    "assigned_agent",
    "packet_type",
    "packet_purpose",
    "workflow_session_ref",
    "block_refs",
    "current_state_refs",
    "active_draft_refs",
    "allowed_context_refs",
    "excluded_context_refs",
    "allowed_tools",
    "blocked_tools",
    "allowed_mcp_refs",
    "allowed_script_refs",
    "allowed_hook_refs",
    "proof_requirements",
    "authority_boundary",
    "expected_return_shape",
    "stop_conditions",
    "timeout_policy_ref",
    "next_safe_move",
)

REQUIRED_EXCHANGE_FIELDS = (
    "exchange_id",
    "handoff_session_ref",
    "agent_ref",
    "step_packet_ref",
    "exchange_type",
    "request_summary",
    "system_response_summary",
    "packet_delta_refs",
    "proof_refs_returned",
    "draft_intents_returned",
    "validation_refs",
    "blocked_reason",
    "should_surface_to_operator",
    "operator_visible_summary",
    "next_safe_move",
)

REQUIRED_OPERATOR_HANDOFF_FIELDS = (
    "operator_handoff_id",
    "handoff_session_ref",
    "from_agent",
    "target_surface",
    "handoff_type",
    "captain_summary",
    "why_operator_needed",
    "question",
    "choices",
    "freeform_allowed",
    "draft_preview_refs",
    "workflow_block_refs",
    "consequence_preview",
    "proof_refs",
    "authority_boundary",
    "response_expected",
    "timeout_or_reminder_policy",
    "next_safe_move",
)

REQUIRED_LIVENESS_FIELDS = (
    "status_id",
    "handoff_session_ref",
    "agent_ref",
    "surface_ref",
    "status_state",
    "visible_status_label",
    "operator_visible",
    "last_heartbeat_policy",
    "timeout_policy_ref",
    "stale_after_policy",
    "offline_after_policy",
    "recovery_policy",
    "notify_operator_policy",
    "system_updates_agent_policy",
    "next_safe_move",
)

REQUIRED_TIMEOUT_POLICY_FIELDS = (
    "policy_id",
    "applies_to_statuses",
    "soft_timeout",
    "hard_timeout",
    "operator_notification_threshold",
    "retry_allowed",
    "retry_limit",
    "fallback_agent_allowed",
    "fallback_to_world_surface",
    "fallback_to_bridge_attention",
    "recovery_message_shape",
    "receipt_or_log_required_later",
    "next_safe_move",
)

REQUIRED_VISIBILITY_POLICY_FIELDS = (
    "policy_id",
    "visible_states",
    "hidden_states",
    "aggregation_rule",
    "minimum_display_duration",
    "suppress_minor_transitions",
    "escalation_rule",
    "bridge_visibility_rule",
    "world_visibility_rule",
    "telegram_visibility_rule",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "live_agent_execution_allowed": False,
    "model_call_allowed": False,
    "telegram_send_allowed": False,
    "message_send_allowed": False,
    "tool_execution_allowed": False,
    "mcp_execution_allowed": False,
    "script_execution_allowed": False,
    "hook_execution_allowed": False,
    "receipt_write_allowed": False,
    "state_write_allowed": False,
    "invoice_generation_allowed": False,
    "email_draft_allowed": False,
    "email_send_allowed": False,
    "browser_automation_allowed": False,
    "coupa_access_allowed": False,
    "credential_handling_allowed": False,
    "approval_submission_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "file_write_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_operation_allowed": False,
    "gmail_access_allowed": False,
    "calendar_access_allowed": False,
    "ledger_write_allowed": False,
    "operator_input_persistence_allowed": False,
    "workflow_execution_allowed": False,
    "file_move_delete_cleanup_allowed": False,
    "archive_action_allowed": False,
    "rewrite_action_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

COMMON_BLOCKED_TOOLS = (
    "live model call",
    "agent runtime activation",
    "Telegram send",
    "Gmail or email send",
    "Coupa/browser/account access",
    "credential handling",
    "receipt/state writer",
    "invoice generation",
    "approval submission",
    "queue/runtime dispatch",
    "file write or cleanup",
)

COMMON_STOP_CONDITIONS = (
    "operator judgment is required",
    "proof is missing",
    "Guardian approval is required",
    "packet context is stale",
    "requested action would require authority not granted here",
)

RELATIONSHIP_REF_PATHS = {
    "workflow_block_intent_live_draft_contract": "generated/read_models/workflow_block_intent_live_draft_contract.json",
    "bridge_routing_operator_attention_contract": "generated/read_models/bridge_routing_operator_attention_contract.json",
    "operator_solve_path_decision_node_contract": "generated/read_models/operator_solve_path_decision_node_contract.json",
    "workflow_session_channel_projection_approval_bus_contract": (
        "generated/read_models/workflow_session_channel_projection_approval_bus_contract.json"
    ),
    "guided_capture_protected_evidence_path_contract": (
        "generated/read_models/guided_capture_protected_evidence_path_contract.json"
    ),
    "automation_readiness_feasibility_evaluator_contract": (
        "generated/read_models/automation_readiness_feasibility_evaluator_contract.json"
    ),
}


@dataclass(frozen=True)
class AgentConversationHandoffSession:
    handoff_session_id: str
    originating_surface: str
    originating_actor: str
    target_agent: str
    target_world: str
    target_lane: str
    workflow_session_ref: str
    user_utterance: str
    inferred_intent: str
    current_phase: str
    current_status: str
    visible_status_label: str
    agent_liveness_ref: str
    active_step_packet_ref: str
    pending_operator_question_ref: str
    pending_system_request_ref: str
    draft_intent_refs: tuple[str, ...]
    crew_briefing_refs: tuple[str, ...]
    authority_boundary: dict[str, bool]
    timeout_policy_ref: str
    handoff_return_target: str
    next_safe_move: str


@dataclass(frozen=True)
class AgentStepPacket:
    step_packet_id: str
    handoff_session_ref: str
    assigned_agent: str
    packet_type: str
    packet_purpose: str
    workflow_session_ref: str
    block_refs: tuple[str, ...]
    current_state_refs: tuple[str, ...]
    active_draft_refs: tuple[str, ...]
    allowed_context_refs: tuple[str, ...]
    excluded_context_refs: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    blocked_tools: tuple[str, ...]
    allowed_mcp_refs: tuple[str, ...]
    allowed_script_refs: tuple[str, ...]
    allowed_hook_refs: tuple[str, ...]
    proof_requirements: tuple[str, ...]
    authority_boundary: dict[str, bool]
    expected_return_shape: str
    stop_conditions: tuple[str, ...]
    timeout_policy_ref: str
    next_safe_move: str


@dataclass(frozen=True)
class AgentSystemExchange:
    exchange_id: str
    handoff_session_ref: str
    agent_ref: str
    step_packet_ref: str
    exchange_type: str
    request_summary: str
    system_response_summary: str
    packet_delta_refs: tuple[str, ...]
    proof_refs_returned: tuple[str, ...]
    draft_intents_returned: tuple[str, ...]
    validation_refs: tuple[str, ...]
    blocked_reason: str
    should_surface_to_operator: bool
    operator_visible_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class OperatorHandoffPacket:
    operator_handoff_id: str
    handoff_session_ref: str
    from_agent: str
    target_surface: str
    handoff_type: str
    captain_summary: str
    why_operator_needed: str
    question: str
    choices: tuple[str, ...]
    freeform_allowed: bool
    draft_preview_refs: tuple[str, ...]
    workflow_block_refs: tuple[str, ...]
    consequence_preview: tuple[str, ...]
    proof_refs: tuple[str, ...]
    authority_boundary: dict[str, bool]
    response_expected: bool
    timeout_or_reminder_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class AgentLivenessProgressStatus:
    status_id: str
    handoff_session_ref: str
    agent_ref: str
    surface_ref: str
    status_state: str
    visible_status_label: str
    operator_visible: bool
    last_heartbeat_policy: str
    timeout_policy_ref: str
    stale_after_policy: str
    offline_after_policy: str
    recovery_policy: str
    notify_operator_policy: str
    system_updates_agent_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class AgentHandoffTimeoutRecoveryPolicy:
    policy_id: str
    applies_to_statuses: tuple[str, ...]
    soft_timeout: str
    hard_timeout: str
    operator_notification_threshold: str
    retry_allowed: bool
    retry_limit: int
    fallback_agent_allowed: bool
    fallback_to_world_surface: bool
    fallback_to_bridge_attention: bool
    recovery_message_shape: str
    receipt_or_log_required_later: str
    next_safe_move: str


@dataclass(frozen=True)
class AgentStatusVisibilityPolicy:
    policy_id: str
    visible_states: tuple[str, ...]
    hidden_states: tuple[str, ...]
    aggregation_rule: str
    minimum_display_duration: str
    suppress_minor_transitions: bool
    escalation_rule: str
    bridge_visibility_rule: str
    world_visibility_rule: str
    telegram_visibility_rule: str
    next_safe_move: str


@dataclass(frozen=True)
class AgentConversationHandoffExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    handoff_session_count: int
    step_packet_count: int
    exchange_count: int
    operator_handoff_count: int
    liveness_status_count: int
    timeout_policy_count: int
    visibility_policy_count: int
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


def _authority_boundary() -> dict[str, bool]:
    return dict(AUTHORITY_BOUNDARY)


def _relationship_refs(repo_root: str | Path) -> dict[str, dict[str, Any]]:
    root = Path(repo_root)
    return {
        ref_id: {
            "path": path,
            "present": (root / path).exists(),
        }
        for ref_id, path in RELATIONSHIP_REF_PATHS.items()
    }


def default_handoff_sessions() -> tuple[AgentConversationHandoffSession, ...]:
    return (
        AgentConversationHandoffSession(
            handoff_session_id="telegram_cassandra_capital_hilton_invoice_handoff",
            originating_surface="Telegram",
            originating_actor="Winship",
            target_agent="Cassandra",
            target_world="Finance",
            target_lane="Capital Hilton",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            user_utterance="Send Capital Hilton an invoice for this week's and last week's job.",
            inferred_intent="prepare Capital Hilton invoice draft path",
            current_phase="WAITING_ON_OPERATOR",
            current_status="WAITING_ON_OPERATOR",
            visible_status_label="Cassandra needs one invoice fact before preparing the draft path.",
            agent_liveness_ref="cassandra_invoice_waiting_on_operator_status",
            active_step_packet_ref="cassandra_capital_hilton_block_fill_packet",
            pending_operator_question_ref="capital_hilton_missing_dates_operator_handoff",
            pending_system_request_ref="",
            draft_intent_refs=("capital_hilton_telegram_invoice_request_draft",),
            crew_briefing_refs=("cassandra_telegram_request_briefing",),
            authority_boundary=_authority_boundary(),
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            handoff_return_target="Telegram compact status and Finance World draft review",
            next_safe_move="Ask only the missing invoice block question; keep draft/send gated.",
        ),
        AgentConversationHandoffSession(
            handoff_session_id="mission_control_capital_hilton_draft_handoff",
            originating_surface="Mission Control",
            originating_actor="Winship",
            target_agent="Cassandra/Clara",
            target_world="Finance",
            target_lane="Capital Hilton",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            user_utterance="Operator edited performance dates block in Finance World.",
            inferred_intent="agent review of live draft/proof needs",
            current_phase="SYSTEM_PACKET_READY",
            current_status="MAKING_PACKET",
            visible_status_label="Finance draft review packet is ready for agent review.",
            agent_liveness_ref="mission_control_draft_packet_ready_status",
            active_step_packet_ref="mission_control_capital_hilton_draft_review_packet",
            pending_operator_question_ref="",
            pending_system_request_ref="",
            draft_intent_refs=("capital_hilton_mission_control_performance_dates_draft",),
            crew_briefing_refs=("cassandra_clara_finance_briefing",),
            authority_boundary=_authority_boundary(),
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            handoff_return_target="Mission Control Finance World",
            next_safe_move="Let an agent review the same draft shape without changing canonical state.",
        ),
        AgentConversationHandoffSession(
            handoff_session_id="chief_check_engine_conversation_handoff",
            originating_surface="Mission Control",
            originating_actor="Winship",
            target_agent="Chief",
            target_world="Build",
            target_lane="Check Engine",
            workflow_session_ref="check_engine_diagnostic_session",
            user_utterance="What is blocking the build?",
            inferred_intent="diagnostic blocker briefing",
            current_phase="AGENT_RETURNING_BRIEFING",
            current_status="RETURNING_BRIEFING",
            visible_status_label="Chief is returning a concise blocker briefing.",
            agent_liveness_ref="chief_check_engine_returning_briefing_status",
            active_step_packet_ref="chief_check_engine_diagnostic_packet",
            pending_operator_question_ref="",
            pending_system_request_ref="",
            draft_intent_refs=("chief_check_engine_build_blocker_draft",),
            crew_briefing_refs=("chief_check_engine_briefing",),
            authority_boundary=_authority_boundary(),
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            handoff_return_target="Shipyard or Bridge attention only if captain decision required",
            next_safe_move="Return blocker summary and keep engineering detail below deck unless action is needed.",
        ),
        AgentConversationHandoffSession(
            handoff_session_id="guardian_approval_handoff_session",
            originating_surface="Finance World",
            originating_actor="workflow_session",
            target_agent="Guardian",
            target_world="Security",
            target_lane="Approval Prep",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            user_utterance="Approval prerequisites may be ready for Guardian review.",
            inferred_intent="prepare approval question only if prerequisites exist",
            current_phase="WAITING_ON_GUARDIAN",
            current_status="VALIDATING",
            visible_status_label="Guardian is checking whether approval is actually ready.",
            agent_liveness_ref="guardian_approval_validating_status",
            active_step_packet_ref="guardian_capital_hilton_approval_prep_packet",
            pending_operator_question_ref="capital_hilton_approval_review_operator_handoff",
            pending_system_request_ref="",
            draft_intent_refs=(),
            crew_briefing_refs=("guardian_invoice_gate_briefing",),
            authority_boundary=_authority_boundary(),
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            handoff_return_target="Finance World approval area",
            next_safe_move="Return an approval question only when prerequisites exist; do not send.",
        ),
        AgentConversationHandoffSession(
            handoff_session_id="cassandra_invoice_packet_stalled_handoff",
            originating_surface="Telegram",
            originating_actor="Winship",
            target_agent="Cassandra",
            target_world="Finance",
            target_lane="Capital Hilton",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            user_utterance="Send Capital Hilton an invoice for this week's and last week's job.",
            inferred_intent="prepare invoice packet but agent liveness stalled",
            current_phase="TIMED_OUT",
            current_status="STALLED",
            visible_status_label="Cassandra appears stalled while preparing the invoice packet.",
            agent_liveness_ref="cassandra_invoice_packet_stalled_status",
            active_step_packet_ref="cassandra_capital_hilton_block_fill_packet",
            pending_operator_question_ref="cassandra_stalled_operator_handoff",
            pending_system_request_ref="",
            draft_intent_refs=("capital_hilton_telegram_invoice_request_draft",),
            crew_briefing_refs=(),
            authority_boundary=_authority_boundary(),
            timeout_policy_ref="stalled_agent_recovery_policy",
            handoff_return_target="Telegram and Finance World status",
            next_safe_move="Tell Winship nothing was done and offer resume, retry, or park.",
        ),
        AgentConversationHandoffSession(
            handoff_session_id="operator_block_change_updates_agent_handoff",
            originating_surface="Mission Control",
            originating_actor="Winship",
            target_agent="Cassandra",
            target_world="Finance",
            target_lane="Capital Hilton",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            user_utterance="Performance dates draft changed while Cassandra was working.",
            inferred_intent="invalidate stale packet and update agent",
            current_phase="WAITING_ON_SYSTEM",
            current_status="WAITING_ON_SYSTEM",
            visible_status_label="Cassandra is updating from your latest draft.",
            agent_liveness_ref="cassandra_updating_from_latest_draft_status",
            active_step_packet_ref="cassandra_capital_hilton_block_fill_packet_v2",
            pending_operator_question_ref="",
            pending_system_request_ref="system_update_agent_packet_stale_exchange",
            draft_intent_refs=("capital_hilton_mission_control_performance_dates_draft",),
            crew_briefing_refs=("cassandra_telegram_request_briefing",),
            authority_boundary=_authority_boundary(),
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            handoff_return_target="Mission Control Finance World and Telegram compact status",
            next_safe_move="Mark old packet stale and update the agent without spamming Winship.",
        ),
    )


def default_step_packets() -> tuple[AgentStepPacket, ...]:
    return (
        AgentStepPacket(
            step_packet_id="cassandra_capital_hilton_intent_packet",
            handoff_session_ref="telegram_cassandra_capital_hilton_invoice_handoff",
            assigned_agent="Cassandra",
            packet_type="INTENT_CLASSIFICATION_PACKET",
            packet_purpose="Classify the user request into known workflow/block intent without whole-system context.",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            block_refs=("invoice_request", "date_scope"),
            current_state_refs=("capital_hilton_invoice_workflow_session.summary",),
            active_draft_refs=(),
            allowed_context_refs=(
                "operator utterance",
                "Capital Hilton workflow session summary",
                "workflow_block_intent_live_draft_contract shape",
            ),
            excluded_context_refs=("whole-system context", "raw private message bodies", "credentials", "unrelated worlds"),
            allowed_tools=(),
            blocked_tools=COMMON_BLOCKED_TOOLS,
            allowed_mcp_refs=(),
            allowed_script_refs=(),
            allowed_hook_refs=(),
            proof_requirements=("deterministic workflow/session refs required before block fill",),
            authority_boundary=_authority_boundary(),
            expected_return_shape="intent label, candidate workflow ref, needed block packet refs, no action",
            stop_conditions=COMMON_STOP_CONDITIONS,
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            next_safe_move="Return a candidate invoice request intent or ask for clarification.",
        ),
        AgentStepPacket(
            step_packet_id="cassandra_capital_hilton_block_fill_packet",
            handoff_session_ref="telegram_cassandra_capital_hilton_invoice_handoff",
            assigned_agent="Cassandra",
            packet_type="BLOCK_FILL_PACKET",
            packet_purpose="Fill only known Capital Hilton invoice blocks and identify missing questions.",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            block_refs=("client", "date_scope", "rate", "invoice_route", "review_packet"),
            current_state_refs=(
                "workflow_session_channel_projection_approval_bus_contract.capital_hilton_invoice_workflow_session",
                "operator_solve_path_decision_node_contract.capital_hilton_invoice_solve_path",
            ),
            active_draft_refs=("workflow_block_intent_live_draft_contract.capital_hilton_telegram_invoice_request_draft",),
            allowed_context_refs=("Capital Hilton current session summary", "known rate refs", "known invoice route refs"),
            excluded_context_refs=("whole-system context", "raw emails", "Coupa credentials", "unrelated client projects"),
            allowed_tools=(),
            blocked_tools=COMMON_BLOCKED_TOOLS,
            allowed_mcp_refs=(),
            allowed_script_refs=(),
            allowed_hook_refs=(),
            proof_requirements=("operator confirmation or proof refs before any future invoice/send path",),
            authority_boundary=_authority_boundary(),
            expected_return_shape="draft intents returned plus missing block questions; no invoice artifact",
            stop_conditions=COMMON_STOP_CONDITIONS,
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            next_safe_move="Ask only missing required questions or return that a draft can be prepared later.",
        ),
        AgentStepPacket(
            step_packet_id="mission_control_capital_hilton_draft_review_packet",
            handoff_session_ref="mission_control_capital_hilton_draft_handoff",
            assigned_agent="Cassandra/Clara",
            packet_type="DRAFT_REVIEW_PACKET",
            packet_purpose="Review a Mission Control live draft and identify proof/fill gaps using the same draft shape as Telegram.",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            block_refs=("performance_dates", "rate_source", "po_reference"),
            current_state_refs=("capital_hilton_invoice_workflow_session.current_state",),
            active_draft_refs=("workflow_block_intent_live_draft_contract.capital_hilton_mission_control_performance_dates_draft",),
            allowed_context_refs=("active Finance World draft refs", "proof summary refs", "decision node refs"),
            excluded_context_refs=("whole-system context", "raw protected bodies", "credential stores", "external account state"),
            allowed_tools=(),
            blocked_tools=COMMON_BLOCKED_TOOLS,
            allowed_mcp_refs=(),
            allowed_script_refs=(),
            allowed_hook_refs=(),
            proof_requirements=("proof drawer refs or operator confirmation target",),
            authority_boundary=_authority_boundary(),
            expected_return_shape="concise draft review briefing and missing proof questions",
            stop_conditions=COMMON_STOP_CONDITIONS,
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            next_safe_move="Return proof gaps without writing receipts or changing state.",
        ),
        AgentStepPacket(
            step_packet_id="chief_check_engine_diagnostic_packet",
            handoff_session_ref="chief_check_engine_conversation_handoff",
            assigned_agent="Chief",
            packet_type="CHIEF_DIAGNOSTIC_PACKET",
            packet_purpose="Summarize what is blocking the build from current read-model/test refs only.",
            workflow_session_ref="check_engine_diagnostic_session",
            block_refs=("diagnostic_sources", "current_blocker", "captain_decision_needed"),
            current_state_refs=("focused test refs", "generated read-model summaries", "git dirty summary refs"),
            active_draft_refs=("workflow_block_intent_live_draft_contract.chief_check_engine_build_blocker_draft",),
            allowed_context_refs=("current diagnostic read-model refs", "focused validation refs"),
            excluded_context_refs=("whole-system context", "private raw files", "credentials", "runtime actions"),
            allowed_tools=(),
            blocked_tools=COMMON_BLOCKED_TOOLS,
            allowed_mcp_refs=(),
            allowed_script_refs=(),
            allowed_hook_refs=(),
            proof_requirements=("test/read-model refs must be current before a repair decision is requested",),
            authority_boundary=_authority_boundary(),
            expected_return_shape="blocker summary, proof refs, captain decision needed yes/no",
            stop_conditions=COMMON_STOP_CONDITIONS,
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            next_safe_move="Return concise blocker briefing; keep engineering detail below deck.",
        ),
        AgentStepPacket(
            step_packet_id="guardian_capital_hilton_approval_prep_packet",
            handoff_session_ref="guardian_approval_handoff_session",
            assigned_agent="Guardian",
            packet_type="APPROVAL_PREP_PACKET",
            packet_purpose="Determine whether an approval question is actually ready to ask.",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            block_refs=("approval_gate", "send_gate", "proof_prerequisites"),
            current_state_refs=(
                "workflow_session_channel_projection_approval_bus_contract.capital_hilton_invoice_workflow_session",
                "capital_hilton_proof_resolution_batch",
            ),
            active_draft_refs=(),
            allowed_context_refs=("approval prerequisite summary", "proof summary refs", "authority gate refs"),
            excluded_context_refs=("whole-system context", "raw emails", "protected bodies", "credentials"),
            allowed_tools=(),
            blocked_tools=COMMON_BLOCKED_TOOLS,
            allowed_mcp_refs=(),
            allowed_script_refs=(),
            allowed_hook_refs=(),
            proof_requirements=("approval prerequisites must exist before operator approval question",),
            authority_boundary=_authority_boundary(),
            expected_return_shape="approval-ready status or locked prerequisite briefing; no submit/send action",
            stop_conditions=COMMON_STOP_CONDITIONS,
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            next_safe_move="Return an approval packet only if prerequisites exist; otherwise keep locked.",
        ),
        AgentStepPacket(
            step_packet_id="cassandra_capital_hilton_block_fill_packet_v2",
            handoff_session_ref="operator_block_change_updates_agent_handoff",
            assigned_agent="Cassandra",
            packet_type="BLOCK_FILL_PACKET",
            packet_purpose="Replace stale packet after operator changed the Mission Control draft.",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            block_refs=("performance_dates", "review_packet"),
            current_state_refs=("capital_hilton_invoice_workflow_session.current_state",),
            active_draft_refs=("workflow_block_intent_live_draft_contract.capital_hilton_mission_control_performance_dates_draft",),
            allowed_context_refs=("latest active draft refs", "packet stale reason", "dependent preview invalidations"),
            excluded_context_refs=("stale prior packet as truth", "whole-system context", "raw private bodies", "credentials"),
            allowed_tools=(),
            blocked_tools=COMMON_BLOCKED_TOOLS,
            allowed_mcp_refs=(),
            allowed_script_refs=(),
            allowed_hook_refs=(),
            proof_requirements=("revalidate prior packet against latest draft before any briefing",),
            authority_boundary=_authority_boundary(),
            expected_return_shape="updated draft briefing or missing question based on latest packet",
            stop_conditions=COMMON_STOP_CONDITIONS,
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            next_safe_move="Update the agent with a stale-packet notice and wait for a refreshed briefing.",
        ),
    )


def default_exchanges() -> tuple[AgentSystemExchange, ...]:
    return (
        AgentSystemExchange(
            exchange_id="cassandra_invoice_packet_request_exchange",
            handoff_session_ref="telegram_cassandra_capital_hilton_invoice_handoff",
            agent_ref="Cassandra",
            step_packet_ref="cassandra_capital_hilton_intent_packet",
            exchange_type="PACKET_REQUEST",
            request_summary="Cassandra requests a focused packet for a Capital Hilton invoice utterance.",
            system_response_summary="System returns only invoice intent/session refs and blocks excluded raw context.",
            packet_delta_refs=("cassandra_capital_hilton_intent_packet",),
            proof_refs_returned=(),
            draft_intents_returned=(),
            validation_refs=(),
            blocked_reason="",
            should_surface_to_operator=False,
            operator_visible_summary="",
            next_safe_move="Keep packet request below deck unless it stalls or needs operator input.",
        ),
        AgentSystemExchange(
            exchange_id="cassandra_invoice_draft_intent_return_exchange",
            handoff_session_ref="telegram_cassandra_capital_hilton_invoice_handoff",
            agent_ref="Cassandra",
            step_packet_ref="cassandra_capital_hilton_block_fill_packet",
            exchange_type="DRAFT_INTENT_RETURN",
            request_summary="Cassandra returns candidate invoice block draft intents and missing date question.",
            system_response_summary="System validates known blocks and marks missing dates/rate proof as operator questions if needed.",
            packet_delta_refs=(),
            proof_refs_returned=("known Capital Hilton proof summary refs if available",),
            draft_intents_returned=("capital_hilton_telegram_invoice_request_draft",),
            validation_refs=("telegram_invoice_request_needs_review_validation",),
            blocked_reason="invoice draft/send remains gated",
            should_surface_to_operator=True,
            operator_visible_summary="Cassandra can prepare the draft path after the missing invoice fact is answered.",
            next_safe_move="Return a concise operator handoff packet.",
        ),
        AgentSystemExchange(
            exchange_id="mission_control_draft_review_packet_delivery_exchange",
            handoff_session_ref="mission_control_capital_hilton_draft_handoff",
            agent_ref="Cassandra/Clara",
            step_packet_ref="mission_control_capital_hilton_draft_review_packet",
            exchange_type="PACKET_DELIVERY",
            request_summary="System gives an agent the active Mission Control draft packet.",
            system_response_summary="Packet contains current/draft refs and proof summary only, not raw protected bodies.",
            packet_delta_refs=("mission_control_capital_hilton_draft_review_packet",),
            proof_refs_returned=("capital_hilton_proof_resolution_batch",),
            draft_intents_returned=("capital_hilton_mission_control_performance_dates_draft",),
            validation_refs=("capital_hilton_performance_dates_preview_validation",),
            blocked_reason="",
            should_surface_to_operator=False,
            operator_visible_summary="",
            next_safe_move="Agent reviews/fills proof gaps and returns only if Winship is needed.",
        ),
        AgentSystemExchange(
            exchange_id="chief_check_engine_diagnostic_return_exchange",
            handoff_session_ref="chief_check_engine_conversation_handoff",
            agent_ref="Chief",
            step_packet_ref="chief_check_engine_diagnostic_packet",
            exchange_type="STATUS_UPDATE",
            request_summary="Chief evaluates current diagnostic packet refs.",
            system_response_summary="System accepts concise blocker briefing; repair remains blocked.",
            packet_delta_refs=(),
            proof_refs_returned=("focused test refs", "generated read-model summaries"),
            draft_intents_returned=("chief_check_engine_build_blocker_draft",),
            validation_refs=("chief_check_engine_blocker_preview_validation",),
            blocked_reason="repair execution authority false",
            should_surface_to_operator=True,
            operator_visible_summary="Chief has a blocker briefing; no action ran.",
            next_safe_move="Route to Shipyard or Bridge attention depending on whether a captain decision is required.",
        ),
        AgentSystemExchange(
            exchange_id="guardian_approval_prep_blocked_return_exchange",
            handoff_session_ref="guardian_approval_handoff_session",
            agent_ref="Guardian",
            step_packet_ref="guardian_capital_hilton_approval_prep_packet",
            exchange_type="BLOCKED_RETURN",
            request_summary="Guardian checks whether approval/send question is ready.",
            system_response_summary="Prerequisites are not fully ready, so approval remains locked.",
            packet_delta_refs=(),
            proof_refs_returned=("capital_hilton_proof_resolution_batch",),
            draft_intents_returned=(),
            validation_refs=("approval_prerequisites_locked_validation_future",),
            blocked_reason="approval prerequisites missing or not receipt-backed",
            should_surface_to_operator=True,
            operator_visible_summary="Approval is not ready yet; no send authority exists.",
            next_safe_move="Keep locked in Finance World and below deck until an actual approval is ready.",
        ),
        AgentSystemExchange(
            exchange_id="cassandra_stalled_status_exchange",
            handoff_session_ref="cassandra_invoice_packet_stalled_handoff",
            agent_ref="Cassandra",
            step_packet_ref="cassandra_capital_hilton_block_fill_packet",
            exchange_type="STATUS_UPDATE",
            request_summary="System detects missed heartbeat while packet work was active.",
            system_response_summary="System marks handoff stalled and prepares a no-action operator handoff.",
            packet_delta_refs=(),
            proof_refs_returned=(),
            draft_intents_returned=(),
            validation_refs=(),
            blocked_reason="agent heartbeat missed hard timeout",
            should_surface_to_operator=True,
            operator_visible_summary="Cassandra appears stalled while preparing the invoice packet. No action was taken.",
            next_safe_move="Offer resume, retry, or park without automatic retry loop.",
        ),
        AgentSystemExchange(
            exchange_id="system_update_agent_packet_stale_exchange",
            handoff_session_ref="operator_block_change_updates_agent_handoff",
            agent_ref="Cassandra",
            step_packet_ref="cassandra_capital_hilton_block_fill_packet",
            exchange_type="PACKET_DELIVERY",
            request_summary="Operator changed a block while agent was working.",
            system_response_summary="Performance dates draft changed; prior packet stale.",
            packet_delta_refs=("cassandra_capital_hilton_block_fill_packet_v2",),
            proof_refs_returned=(),
            draft_intents_returned=("capital_hilton_mission_control_performance_dates_draft",),
            validation_refs=("capital_hilton_performance_dates_preview_validation",),
            blocked_reason="prior packet stale",
            should_surface_to_operator=True,
            operator_visible_summary="Cassandra is updating from your latest draft.",
            next_safe_move="Update the agent and show calm status rather than stale results.",
        ),
    )


def default_operator_handoff_packets() -> tuple[OperatorHandoffPacket, ...]:
    return (
        OperatorHandoffPacket(
            operator_handoff_id="capital_hilton_missing_dates_operator_handoff",
            handoff_session_ref="telegram_cassandra_capital_hilton_invoice_handoff",
            from_agent="Cassandra",
            target_surface="Telegram compact prompt and Finance World",
            handoff_type="ANSWER_MISSING_BLOCK",
            captain_summary="I can prepare the Capital Hilton draft path after the date scope is confirmed.",
            why_operator_needed="The phrase this week's and last week's job needs exact performance dates before the draft is safe.",
            question="Which performance dates should the draft use?",
            choices=("Use known dates", "Add dates", "I do not know", "Needs discovery", "Park this"),
            freeform_allowed=True,
            draft_preview_refs=("capital_hilton_telegram_invoice_request_draft",),
            workflow_block_refs=("performance_dates", "date_scope"),
            consequence_preview=(
                "dates become draft inputs only",
                "invoice draft review remains gated",
                "Guardian/email approval remains required before send",
            ),
            proof_refs=("capital_hilton_proof_resolution_batch",),
            authority_boundary=_authority_boundary(),
            response_expected=True,
            timeout_or_reminder_policy="standard_agent_handoff_timeout_policy",
            next_safe_move="Ask the missing question; do not create invoice or send anything.",
        ),
        OperatorHandoffPacket(
            operator_handoff_id="capital_hilton_draft_review_operator_handoff",
            handoff_session_ref="mission_control_capital_hilton_draft_handoff",
            from_agent="Cassandra/Clara",
            target_surface="Mission Control Finance World",
            handoff_type="REVIEW_DRAFT",
            captain_summary="The Mission Control draft can be reviewed for proof gaps.",
            why_operator_needed="Only Winship can choose whether the draft should be used, corrected, or parked.",
            question="Review this draft path or keep editing blocks?",
            choices=("Review draft", "Keep editing", "Show proof", "Park"),
            freeform_allowed=False,
            draft_preview_refs=("capital_hilton_mission_control_performance_dates_draft",),
            workflow_block_refs=("performance_dates", "rate_source", "po_reference"),
            consequence_preview=("review remains preview-only", "capture/commit requires future receipt writer"),
            proof_refs=("capital_hilton_proof_resolution_batch",),
            authority_boundary=_authority_boundary(),
            response_expected=True,
            timeout_or_reminder_policy="standard_agent_handoff_timeout_policy",
            next_safe_move="Show concise review choices inside Finance World.",
        ),
        OperatorHandoffPacket(
            operator_handoff_id="chief_check_engine_decision_operator_handoff",
            handoff_session_ref="chief_check_engine_conversation_handoff",
            from_agent="Chief",
            target_surface="Shipyard or Bridge if blocking",
            handoff_type="CHECK_ENGINE_DECISION",
            captain_summary="Chief found a build blocker summary.",
            why_operator_needed="A captain decision is needed only if repair risk or mission impact requires a choice.",
            question="Open Shipyard detail or keep it contained?",
            choices=("Open Shipyard", "Keep contained", "Show proof refs"),
            freeform_allowed=False,
            draft_preview_refs=("chief_check_engine_build_blocker_draft",),
            workflow_block_refs=("diagnostic_sources", "current_blocker"),
            consequence_preview=("no repair runs", "engineering detail remains below deck unless opened"),
            proof_refs=("focused test refs",),
            authority_boundary=_authority_boundary(),
            response_expected=False,
            timeout_or_reminder_policy="standard_agent_handoff_timeout_policy",
            next_safe_move="Return blocker briefing without repair execution.",
        ),
        OperatorHandoffPacket(
            operator_handoff_id="capital_hilton_approval_review_operator_handoff",
            handoff_session_ref="guardian_approval_handoff_session",
            from_agent="Guardian",
            target_surface="Finance World approval area",
            handoff_type="APPROVE_PACKET",
            captain_summary="Guardian will only ask for approval when prerequisites exist.",
            why_operator_needed="Approval is a captain authority decision and cannot be inferred by agent/system state.",
            question="Approve this packet after prerequisites are receipt-backed?",
            choices=("Approve later when ready", "Reject", "Park", "Show prerequisites"),
            freeform_allowed=False,
            draft_preview_refs=("approval_packet_preview_future",),
            workflow_block_refs=("approval_gate", "send_gate"),
            consequence_preview=("approval alone does not send", "send remains separately gated", "no approval submission occurs here"),
            proof_refs=("capital_hilton_proof_resolution_batch",),
            authority_boundary=_authority_boundary(),
            response_expected=True,
            timeout_or_reminder_policy="standard_agent_handoff_timeout_policy",
            next_safe_move="Keep approval modeled but not executable.",
        ),
        OperatorHandoffPacket(
            operator_handoff_id="cassandra_stalled_operator_handoff",
            handoff_session_ref="cassandra_invoice_packet_stalled_handoff",
            from_agent="System",
            target_surface="Telegram and Mission Control Finance World",
            handoff_type="STATUS_UPDATE_ONLY",
            captain_summary="Cassandra appears stalled while preparing the invoice packet. No action was taken.",
            why_operator_needed="The task is no longer progressing and the operator should know instead of waiting silently.",
            question="Resume, retry, or park?",
            choices=("Resume", "Retry once", "Park this", "Open Finance World"),
            freeform_allowed=False,
            draft_preview_refs=("capital_hilton_telegram_invoice_request_draft",),
            workflow_block_refs=("invoice_request",),
            consequence_preview=("no automatic retry loop", "no send or invoice generation occurred", "draft state remains preview-only"),
            proof_refs=(),
            authority_boundary=_authority_boundary(),
            response_expected=True,
            timeout_or_reminder_policy="stalled_agent_recovery_policy",
            next_safe_move="Make the stall visible and wait for operator choice.",
        ),
        OperatorHandoffPacket(
            operator_handoff_id="operator_block_change_status_handoff",
            handoff_session_ref="operator_block_change_updates_agent_handoff",
            from_agent="System",
            target_surface="Mission Control and Telegram compact status",
            handoff_type="STATUS_UPDATE_ONLY",
            captain_summary="Cassandra is updating from your latest draft.",
            why_operator_needed="No input is needed unless the refreshed packet finds a missing block.",
            question="",
            choices=("Keep working", "Park", "Open Finance World"),
            freeform_allowed=False,
            draft_preview_refs=("capital_hilton_mission_control_performance_dates_draft",),
            workflow_block_refs=("performance_dates",),
            consequence_preview=("prior packet marked stale", "agent receives latest draft", "operator is not spammed with raw exchange log"),
            proof_refs=(),
            authority_boundary=_authority_boundary(),
            response_expected=False,
            timeout_or_reminder_policy="standard_agent_handoff_timeout_policy",
            next_safe_move="Show calm status and wait for meaningful return.",
        ),
    )


def default_liveness_statuses() -> tuple[AgentLivenessProgressStatus, ...]:
    return (
        AgentLivenessProgressStatus(
            status_id="cassandra_invoice_thinking_status",
            handoff_session_ref="telegram_cassandra_capital_hilton_invoice_handoff",
            agent_ref="Cassandra",
            surface_ref="Telegram",
            status_state="THINKING",
            visible_status_label="Cassandra is reading your request.",
            operator_visible=True,
            last_heartbeat_policy="heartbeat expected while session active",
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            stale_after_policy="stale if workflow session changes before packet delivery",
            offline_after_policy="offline after hard timeout or missed liveness proof",
            recovery_policy="show stalled/offline handoff; no automatic retry loop",
            notify_operator_policy="show compact status only on meaningful transition",
            system_updates_agent_policy="send updated packet if workflow/session state changes",
            next_safe_move="Move to making packet or ask a clarification question.",
        ),
        AgentLivenessProgressStatus(
            status_id="cassandra_invoice_making_packet_status",
            handoff_session_ref="telegram_cassandra_capital_hilton_invoice_handoff",
            agent_ref="Cassandra",
            surface_ref="Telegram",
            status_state="MAKING_PACKET",
            visible_status_label="Cassandra is preparing the invoice packet.",
            operator_visible=True,
            last_heartbeat_policy="heartbeat expected while packet is active",
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            stale_after_policy="stale if draft/session refs change",
            offline_after_policy="offline after hard timeout",
            recovery_policy="surface stalled packet if no heartbeat",
            notify_operator_policy="do not repeat minor packet transitions",
            system_updates_agent_policy="packet delta replaces stale context",
            next_safe_move="Return briefing or missing question.",
        ),
        AgentLivenessProgressStatus(
            status_id="cassandra_invoice_waiting_on_operator_status",
            handoff_session_ref="telegram_cassandra_capital_hilton_invoice_handoff",
            agent_ref="Cassandra",
            surface_ref="Telegram and Finance World",
            status_state="WAITING_ON_OPERATOR",
            visible_status_label="Cassandra is waiting for your invoice answer.",
            operator_visible=True,
            last_heartbeat_policy="no agent heartbeat needed while blocked on operator",
            timeout_policy_ref="operator_wait_timeout_policy",
            stale_after_policy="stale if operator edits the same block elsewhere",
            offline_after_policy="not applicable while waiting on operator",
            recovery_policy="keep handoff visible but quiet",
            notify_operator_policy="show one prompt plus optional reminder later",
            system_updates_agent_policy="agent resumes only after operator/system state update",
            next_safe_move="Wait for operator answer or park.",
        ),
        AgentLivenessProgressStatus(
            status_id="mission_control_draft_packet_ready_status",
            handoff_session_ref="mission_control_capital_hilton_draft_handoff",
            agent_ref="Cassandra/Clara",
            surface_ref="Mission Control Finance World",
            status_state="MAKING_PACKET",
            visible_status_label="Draft review packet is ready.",
            operator_visible=True,
            last_heartbeat_policy="heartbeat expected after agent accepts packet",
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            stale_after_policy="stale after any upstream block change",
            offline_after_policy="offline after hard timeout",
            recovery_policy="return stale/blocked packet status",
            notify_operator_policy="show only if packet is waiting, stale, or complete",
            system_updates_agent_policy="replace packet on block changes",
            next_safe_move="Let agent review/fill proof gap and return concise briefing.",
        ),
        AgentLivenessProgressStatus(
            status_id="chief_check_engine_returning_briefing_status",
            handoff_session_ref="chief_check_engine_conversation_handoff",
            agent_ref="Chief",
            surface_ref="Shipyard",
            status_state="RETURNING_BRIEFING",
            visible_status_label="Chief is returning a blocker briefing.",
            operator_visible=True,
            last_heartbeat_policy="heartbeat expected until briefing returned",
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            stale_after_policy="stale if test/read-model refs change",
            offline_after_policy="offline after hard timeout",
            recovery_policy="show stalled diagnostic status",
            notify_operator_policy="surface only blocker summary or stall",
            system_updates_agent_policy="send new diagnostic refs when validation changes",
            next_safe_move="Show concise blocker briefing.",
        ),
        AgentLivenessProgressStatus(
            status_id="guardian_approval_validating_status",
            handoff_session_ref="guardian_approval_handoff_session",
            agent_ref="Guardian",
            surface_ref="Finance World",
            status_state="VALIDATING",
            visible_status_label="Guardian is checking approval prerequisites.",
            operator_visible=True,
            last_heartbeat_policy="heartbeat expected during prerequisite check",
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            stale_after_policy="stale if approval packet refs change",
            offline_after_policy="offline after hard timeout",
            recovery_policy="show approval prep stalled or locked status",
            notify_operator_policy="surface only approval ready, locked, or stalled",
            system_updates_agent_policy="update Guardian when proof/session state changes",
            next_safe_move="Return approval-ready or locked prerequisite briefing.",
        ),
        AgentLivenessProgressStatus(
            status_id="cassandra_invoice_packet_stalled_status",
            handoff_session_ref="cassandra_invoice_packet_stalled_handoff",
            agent_ref="Cassandra",
            surface_ref="Telegram and Mission Control Finance World",
            status_state="STALLED",
            visible_status_label="Cassandra appears stalled while preparing the invoice packet.",
            operator_visible=True,
            last_heartbeat_policy="missed heartbeat after hard timeout",
            timeout_policy_ref="stalled_agent_recovery_policy",
            stale_after_policy="packet considered stale until refreshed",
            offline_after_policy="offline if heartbeat remains absent after recovery window",
            recovery_policy="offer resume, retry, or park; no automatic retry loop",
            notify_operator_policy="operator-visible update required",
            system_updates_agent_policy="agent must receive fresh packet before resume",
            next_safe_move="Show no-action stall handoff.",
        ),
        AgentLivenessProgressStatus(
            status_id="cassandra_updating_from_latest_draft_status",
            handoff_session_ref="operator_block_change_updates_agent_handoff",
            agent_ref="Cassandra",
            surface_ref="Mission Control and Telegram",
            status_state="WAITING_ON_SYSTEM",
            visible_status_label="Cassandra is updating from your latest draft.",
            operator_visible=True,
            last_heartbeat_policy="heartbeat resumes after fresh packet delivery",
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            stale_after_policy="prior packet stale immediately after operator block change",
            offline_after_policy="offline after hard timeout if update not acknowledged",
            recovery_policy="show stalled update if no acknowledgement",
            notify_operator_policy="show calm status once, not every internal exchange",
            system_updates_agent_policy="system sends packet delta: Performance dates draft changed; prior packet stale.",
            next_safe_move="Wait for refreshed agent briefing or missing question.",
        ),
    )


def default_timeout_policies() -> tuple[AgentHandoffTimeoutRecoveryPolicy, ...]:
    return (
        AgentHandoffTimeoutRecoveryPolicy(
            policy_id="standard_agent_handoff_timeout_policy",
            applies_to_statuses=("THINKING", "MAKING_PACKET", "WAITING_ON_SYSTEM", "WAITING_ON_PROOF", "VALIDATING"),
            soft_timeout="show quiet still working status after a bounded wait",
            hard_timeout="mark STALLED or TIMED_OUT when heartbeat/progress proof is absent",
            operator_notification_threshold="notify only at meaningful wait, stall, blocked, or handoff state",
            retry_allowed=True,
            retry_limit=1,
            fallback_agent_allowed=False,
            fallback_to_world_surface=True,
            fallback_to_bridge_attention=True,
            recovery_message_shape="Agent appears stalled. No action was taken. Resume, retry, or park?",
            receipt_or_log_required_later="future receipt/log required for retry or fallback decisions",
            next_safe_move="Make progress state visible without automatic loops.",
        ),
        AgentHandoffTimeoutRecoveryPolicy(
            policy_id="operator_wait_timeout_policy",
            applies_to_statuses=("WAITING_ON_OPERATOR",),
            soft_timeout="keep prompt visible without nagging",
            hard_timeout="park or mark stale according to workflow/session policy",
            operator_notification_threshold="optional quiet reminder only if workflow remains relevant",
            retry_allowed=False,
            retry_limit=0,
            fallback_agent_allowed=False,
            fallback_to_world_surface=True,
            fallback_to_bridge_attention=False,
            recovery_message_shape="This is waiting on your answer. You can answer, park, or open the World.",
            receipt_or_log_required_later="future log may record parked handoff",
            next_safe_move="Keep handoff calm and waiting; do not execute anything.",
        ),
        AgentHandoffTimeoutRecoveryPolicy(
            policy_id="stalled_agent_recovery_policy",
            applies_to_statuses=("STALLED", "OFFLINE", "TIMED_OUT", "BLOCKED"),
            soft_timeout="not applicable after stall detected",
            hard_timeout="show offline/stalled status and stop progress assumption",
            operator_notification_threshold="operator-visible update required when progress is no longer happening",
            retry_allowed=True,
            retry_limit=1,
            fallback_agent_allowed=False,
            fallback_to_world_surface=True,
            fallback_to_bridge_attention=True,
            recovery_message_shape="Cassandra appears stalled while preparing the invoice packet. No action was taken. Resume, retry, or park?",
            receipt_or_log_required_later="future log required for stall/retry lifecycle",
            next_safe_move="Do not silently wait; ask for explicit recovery choice.",
        ),
    )


def default_visibility_policies() -> tuple[AgentStatusVisibilityPolicy, ...]:
    return (
        AgentStatusVisibilityPolicy(
            policy_id="calm_agent_status_visibility_policy",
            visible_states=(
                "THINKING",
                "MAKING_PACKET",
                "WAITING_ON_OPERATOR",
                "WAITING_ON_SYSTEM",
                "WAITING_ON_PROOF",
                "RETURNING_BRIEFING",
                "OFFLINE",
                "STALLED",
                "TIMED_OUT",
                "BLOCKED",
                "HANDOFF_COMPLETE",
            ),
            hidden_states=("IDLE", "TYPING"),
            aggregation_rule="aggregate frequent internal transitions into one calm status label",
            minimum_display_duration="long enough to avoid flicker, short enough not to imply progress after timeout",
            suppress_minor_transitions=True,
            escalation_rule="Bridge sees only captain-relevant waiting, blocked, stalled, or handoff states.",
            bridge_visibility_rule="show only captain decision/update, stalled/offline, or mission-blocking state",
            world_visibility_rule="show workflow status chip/badge plus active handoff packet summary",
            telegram_visibility_rule="compact text such as Cassandra is preparing packet or Cassandra is waiting for your answer",
            next_safe_move="Inform without annoying; keep full exchange log below deck.",
        ),
        AgentStatusVisibilityPolicy(
            policy_id="below_deck_exchange_log_visibility_policy",
            visible_states=STATUS_STATES,
            hidden_states=(),
            aggregation_rule="below deck may retain full exchange sequence for inspection",
            minimum_display_duration="not user-facing by default",
            suppress_minor_transitions=False,
            escalation_rule="summarize into crew briefing before surfacing to operator",
            bridge_visibility_rule="never show raw exchange log on Bridge",
            world_visibility_rule="show detail only when summoned",
            telegram_visibility_rule="do not stream raw telemetry",
            next_safe_move="Keep raw exchanges inspectable below deck, not spammy.",
        ),
    )


def starship_operating_model_alignment() -> dict[str, Any]:
    return {
        "captain": "operator",
        "bridge": "captain-level attention",
        "worlds": "domain work",
        "crew": "agents that translate, propose, and brief",
        "engineering": "packet compilation, proof, validation, liveness, and status below deck",
        "ship_logs": "future receipts/proofs",
        "crew_briefings": "operator handoff packets",
        "status_liveness": "calm crew visibility so the captain knows thinking, making packet, waiting, offline, or stalled",
        "red_alert_rule": "Red Alert only when captain decision is required before safe continuation.",
        "core_flow": "Captain gives command. Crew consults ship systems. System provides focused step packets. Crew returns concise briefing, decision request, draft, or status.",
    }


def conversation_examples() -> dict[str, Any]:
    return {
        "telegram_cassandra_invoice": {
            "user_says": "Send Capital Hilton an invoice for this week's and last week's job.",
            "flow": (
                "user utterance received",
                "Cassandra interpreting",
                "system provides intent classification packet",
                "Cassandra proposes workflow block draft intents",
                "system validates known/missing blocks",
                "if dates/rate known, Cassandra says: I can prepare the draft",
                "if missing, Cassandra asks only required questions",
                "invoice draft review remains gated",
                "Guardian/email approval required before send",
            ),
            "liveness_path": ("THINKING", "MAKING_PACKET", "WAITING_ON_OPERATOR", "RETURNING_BRIEFING"),
        },
        "mission_control_capital_hilton_draft": {
            "flow": (
                "user edits block in Mission Control",
                "system may create a draft review packet for an agent",
                "agent receives the same block draft shape as Telegram",
                "agent returns only proof gaps or clean briefing",
            ),
        },
        "chief_check_engine": {
            "user_says": "What is blocking the build?",
            "flow": (
                "Chief receives diagnostic packet",
                "system gives current read-model/test refs only",
                "Chief returns concise blocker briefing",
                "Engineering Contained if no captain decision",
                "Bridge attention if captain decision needed",
            ),
        },
        "guardian_approval": {
            "flow": (
                "Guardian receives approval-prep packet",
                "Guardian returns approval question only when prerequisites exist",
                "no send authority",
            ),
        },
        "agent_offline_stalled": {
            "operator_message": (
                "Cassandra appears stalled while preparing the invoice packet. "
                "No action was taken. Resume, retry, or park?"
            ),
        },
        "system_updates_agent_operator": {
            "system_to_agent": "Performance dates draft changed; prior packet stale.",
            "operator_status": "Cassandra is updating from your latest draft.",
        },
    }


def _asdict_items(items: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [asdict(item) for item in items]


def build_agent_conversation_handoff_step_packet_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    sessions = _asdict_items(default_handoff_sessions())
    packets = _asdict_items(default_step_packets())
    exchanges = _asdict_items(default_exchanges())
    handoffs = _asdict_items(default_operator_handoff_packets())
    statuses = _asdict_items(default_liveness_statuses())
    timeout_policies = _asdict_items(default_timeout_policies())
    visibility_policies = _asdict_items(default_visibility_policies())
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "doctrine": {
            "summary": "Captain gives command. Crew consults ship systems. System provides focused step packets. Crew returns concise briefing, decision request, draft, or status.",
            "systems_engineering_not_loose_chat": True,
            "conversations_own_canonical_workflow_state": False,
            "agents_propose_translate_brief": True,
            "receipts_gates_own_durable_truth_action": True,
            "operator_must_not_guess_progress": True,
        },
        "conversation_handoff_session_schema": {
            "structure": "AgentConversationHandoffSession",
            "required_fields": list(REQUIRED_HANDOFF_SESSION_FIELDS),
            "phases": list(PHASES),
            "conversation_owns_canonical_state": False,
            "all_operator_relevant_phases_visible": True,
        },
        "agent_step_packet_schema": {
            "structure": "AgentStepPacket",
            "required_fields": list(REQUIRED_STEP_PACKET_FIELDS),
            "packet_types": list(PACKET_TYPES),
            "focused_context_only": True,
            "whole_system_context_default": False,
            "tools_are_capabilities_not_authority": True,
            "authority_false_unless_future_gate": True,
        },
        "agent_system_exchange_schema": {
            "structure": "AgentSystemExchange",
            "required_fields": list(REQUIRED_EXCHANGE_FIELDS),
            "exchange_types": list(EXCHANGE_TYPES),
            "below_deck_by_default": True,
            "surface_only_when_captain_decision_or_update_needed": True,
            "raw_agent_telemetry_spams_operator": False,
            "summarizable_into_crew_briefing": True,
        },
        "operator_handoff_packet_schema": {
            "structure": "OperatorHandoffPacket",
            "required_fields": list(REQUIRED_OPERATOR_HANDOFF_FIELDS),
            "handoff_types": list(HANDOFF_TYPES),
            "must_be_concise": True,
            "must_explain_why_operator_needed": True,
            "clear_choices_when_possible": True,
            "proof_refs_below_deck": True,
            "handoff_executes_action": False,
        },
        "agent_liveness_progress_status_schema": {
            "structure": "AgentLivenessProgressStatus",
            "required_fields": list(REQUIRED_LIVENESS_FIELDS),
            "status_states": list(STATUS_STATES),
            "typing_indicator_is_sufficient": False,
            "distinguishes_thinking_typing_making_packet_waiting_offline": True,
            "stalled_offline_timeout_operator_visible": True,
            "calm_not_spammy": True,
        },
        "agent_handoff_timeout_recovery_policy_schema": {
            "structure": "AgentHandoffTimeoutRecoveryPolicy",
            "required_fields": list(REQUIRED_TIMEOUT_POLICY_FIELDS),
            "soft_timeout_may_show_still_working": True,
            "hard_timeout_shows_blocked_offline_stalled": True,
            "fallback_explicit": True,
            "automatic_retry_loops_allowed": False,
        },
        "agent_status_visibility_policy_schema": {
            "structure": "AgentStatusVisibilityPolicy",
            "required_fields": list(REQUIRED_VISIBILITY_POLICY_FIELDS),
            "status_informs_not_annoys": True,
            "frequent_internal_transitions_aggregated": True,
            "bridge_only_captain_relevant": True,
            "world_can_show_more_detail": True,
            "below_deck_keeps_full_exchange_log": True,
        },
        "phases": list(PHASES),
        "packet_types": list(PACKET_TYPES),
        "exchange_types": list(EXCHANGE_TYPES),
        "handoff_types": list(HANDOFF_TYPES),
        "status_states": list(STATUS_STATES),
        "handoff_sessions": sessions,
        "handoff_sessions_by_id": {item["handoff_session_id"]: item for item in sessions},
        "step_packets": packets,
        "step_packets_by_id": {item["step_packet_id"]: item for item in packets},
        "agent_system_exchanges": exchanges,
        "agent_system_exchanges_by_id": {item["exchange_id"]: item for item in exchanges},
        "operator_handoff_packets": handoffs,
        "operator_handoff_packets_by_id": {item["operator_handoff_id"]: item for item in handoffs},
        "liveness_statuses": statuses,
        "liveness_statuses_by_id": {item["status_id"]: item for item in statuses},
        "timeout_recovery_policies": timeout_policies,
        "timeout_recovery_policies_by_id": {item["policy_id"]: item for item in timeout_policies},
        "status_visibility_policies": visibility_policies,
        "status_visibility_policies_by_id": {item["policy_id"]: item for item in visibility_policies},
        "conversation_examples": conversation_examples(),
        "relationship_refs": _relationship_refs(repo_root),
        "starship_operating_model_alignment": starship_operating_model_alignment(),
        "authority_boundary": _authority_boundary(),
        "hard_rule": {
            "read_model_only": True,
            "does_not_implement_live_telegram": True,
            "does_not_execute_agents": True,
            "does_not_call_models": True,
            "does_not_create_runtime": True,
            "does_not_send_messages": True,
            "does_not_write_receipts": True,
            "does_not_mutate_workflow_state": True,
            "may_grant_authority": False,
        },
        "machine_proof": {
            "conversation_handoff_session_model_present": True,
            "agent_step_packet_model_present": True,
            "agent_system_exchange_model_present": True,
            "operator_handoff_packet_model_present": True,
            "liveness_progress_status_model_present": True,
            "timeout_recovery_policy_model_present": True,
            "status_visibility_policy_model_present": True,
            "handoff_session_count": len(sessions),
            "step_packet_count": len(packets),
            "exchange_count": len(exchanges),
            "operator_handoff_count": len(handoffs),
            "liveness_status_count": len(statuses),
            "timeout_policy_count": len(timeout_policies),
            "visibility_policy_count": len(visibility_policies),
            "telegram_cassandra_invoice_example_present": "telegram_cassandra_invoice" in conversation_examples(),
            "mission_control_draft_example_present": "mission_control_capital_hilton_draft" in conversation_examples(),
            "chief_check_engine_example_present": "chief_check_engine" in conversation_examples(),
            "guardian_approval_example_present": "guardian_approval" in conversation_examples(),
            "offline_stalled_example_present": "agent_offline_stalled" in conversation_examples(),
            "operator_system_update_example_present": "system_updates_agent_operator" in conversation_examples(),
            "packets_are_focused_narrow": all(
                "whole-system context" in packet["excluded_context_refs"] and len(packet["allowed_context_refs"]) <= 4
                for packet in packets
            ),
            "agent_system_exchanges_below_deck_by_default": True,
            "operator_handoff_only_when_needed": all(item["why_operator_needed"] for item in handoffs),
            "required_status_states_present": all(
                state in STATUS_STATES
                for state in ("THINKING", "TYPING", "MAKING_PACKET", "WAITING_ON_SYSTEM", "WAITING_ON_OPERATOR", "OFFLINE", "STALLED")
            ),
            "all_authority_flags_false": _all_authority_flags_false(),
            "credentials_or_secrets_included": False,
            "raw_private_bodies_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_agent_conversation_handoff_step_packet_markdown(payload: dict[str, Any]) -> str:
    proof = payload["machine_proof"]
    starship = payload["starship_operating_model_alignment"]
    examples = payload["conversation_examples"]
    lines = [
        "# Agent Conversation Handoff / Step Packet Contract v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "Winship can talk to an agent in Telegram, Mission Control, or a future surface. The agent does not get the whole ship. The system gives the agent a focused step packet with only the workflow refs, draft refs, proof refs, stop conditions, and return shape needed for that step.",
        "",
        "The agent talks to the system below deck. Packet requests, proof lookup requests, validation requests, and draft returns do not spam Winship. They are summarized only when they become a crew briefing, decision request, draft review, or useful status update.",
        "",
        "When operator judgment is needed, the agent hands back cleanly: here is the concise summary, here is why you are needed, here are the choices, and here is what will stay blocked. Proof stays one level down unless summoned.",
        "",
        "Liveness matters because typing is not enough. Complex workflow help needs to distinguish thinking, making packet, waiting on the system, waiting on Winship, validating, returning briefing, stalled, offline, and timed out. The operator should never wonder whether something is working or silently dead.",
        "",
        "Telegram and Mission Control can render the same handoff state. Telegram may show compact text like Cassandra is preparing packet. Mission Control may show a calm status chip. Bridge shows only captain-relevant waiting, blocked, stalled, or handoff states.",
        "",
        "No live authority exists here. No agent runs, no model is called, no message is sent, no receipt/state write happens, no invoice/email/browser/Coupa/Gmail/Telegram action occurs, and no workflow state is mutated.",
        "",
        "## Examples",
        "",
        f"- Telegram/Cassandra invoice: {examples['telegram_cassandra_invoice']['user_says']} Cassandra receives focused packets, returns draft intents or missing questions, and keeps invoice draft/send approval gated.",
        "- Mission Control draft: a block edit can create the same draft-review packet shape an agent would receive from Telegram.",
        f"- Chief/check-engine: {examples['chief_check_engine']['user_says']} Chief gets current read-model/test refs only and returns a concise blocker briefing.",
        "- Guardian approval: Guardian prepares an approval question only when prerequisites exist; no send authority is created.",
        f"- Offline/stalled: {examples['agent_offline_stalled']['operator_message']}",
        f"- Operator/system update: system tells the agent `{examples['system_updates_agent_operator']['system_to_agent']}` and shows Winship `{examples['system_updates_agent_operator']['operator_status']}`.",
        "",
        "## Starship Alignment",
        "",
        f"- Captain: {starship['captain']}.",
        f"- Bridge: {starship['bridge']}.",
        f"- Worlds: {starship['worlds']}.",
        f"- Crew: {starship['crew']}.",
        f"- Engineering: {starship['engineering']}.",
        f"- Ship Logs: {starship['ship_logs']}.",
        f"- Crew briefings: {starship['crew_briefings']}.",
        f"- Status/liveness: {starship['status_liveness']}.",
        f"- Red Alert: {starship['red_alert_rule']}",
        "",
        "## Still Blocked",
        "",
        "- No live agent execution, model call, Telegram/message send, tool/MCP/script/hook execution, receipt/state write, invoice generation, email draft/send, browser/Coupa/Gmail/Calendar/account access, credential handling, approval submission, queue/runtime dispatch, file write/cleanup, raw body ingestion, network, Mac sync/import, Mission Control Swift change, or push.",
        "",
        "## Machine Proof Summary",
        "",
        f"- Handoff sessions: `{proof['handoff_session_count']}`.",
        f"- Step packets: `{proof['step_packet_count']}`.",
        f"- Agent/system exchanges: `{proof['exchange_count']}`.",
        f"- Operator handoff packets: `{proof['operator_handoff_count']}`.",
        f"- Liveness statuses: `{proof['liveness_status_count']}`.",
        f"- Timeout policies: `{proof['timeout_policy_count']}`.",
        f"- Visibility policies: `{proof['visibility_policy_count']}`.",
        f"- Packets focused/narrow: `{str(proof['packets_are_focused_narrow']).lower()}`.",
        f"- Required status states present: `{str(proof['required_status_states_present']).lower()}`.",
        f"- All authority flags false: `{str(proof['all_authority_flags_false']).lower()}`.",
        f"- Content hash: `{proof['content_hash']}`.",
    ]
    return "\n".join(lines) + "\n"


def export_agent_conversation_handoff_step_packet_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> AgentConversationHandoffExportResult:
    repo_root = Path(repo_root)
    export_path = repo_root / export_root
    export_path.mkdir(parents=True, exist_ok=True)
    payload = build_agent_conversation_handoff_step_packet_contract(
        repo_root=repo_root,
        generated_at=generated_at,
    )
    json_path = export_path / JSON_EXPORT_NAME
    operator_path = export_path / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_agent_conversation_handoff_step_packet_markdown(payload), encoding="utf-8")
    proof = payload["machine_proof"]
    return AgentConversationHandoffExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        handoff_session_count=proof["handoff_session_count"],
        step_packet_count=proof["step_packet_count"],
        exchange_count=proof["exchange_count"],
        operator_handoff_count=proof["operator_handoff_count"],
        liveness_status_count=proof["liveness_status_count"],
        timeout_policy_count=proof["timeout_policy_count"],
        visibility_policy_count=proof["visibility_policy_count"],
        action_authority_granted=not proof["all_authority_flags_false"],
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Agent Conversation Handoff / Step Packet Contract v0.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--generated-at", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = export_agent_conversation_handoff_step_packet_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(asdict(result)), end="")
    else:
        print(f"schema_version={result.schema_version}")
        print(f"json_path={result.json_path}")
        print(f"operator_path={result.operator_path}")
        print(f"handoff_session_count={result.handoff_session_count}")
        print(f"step_packet_count={result.step_packet_count}")
        print(f"exchange_count={result.exchange_count}")
        print(f"operator_handoff_count={result.operator_handoff_count}")
        print(f"liveness_status_count={result.liveness_status_count}")
        print(f"timeout_policy_count={result.timeout_policy_count}")
        print(f"visibility_policy_count={result.visibility_policy_count}")
        print(f"action_authority_granted={str(result.action_authority_granted).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
