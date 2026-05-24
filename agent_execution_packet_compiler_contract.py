"""Agent Execution Packet Compiler Contract v0.

This deterministic read-model defines how workflow blocks would compile into
narrow, focused agent execution packets. It is a contract only: an execution
packet is an assignment shape, not execution authority. The existing
Context Selection / Knowledge Packet substrate remains the lower-level evidence
packet compiler; this contract does not replace it or build runtime behavior.

No packet execution, agent execution, model call, tool/MCP/script/hook
execution, receipt/state write, invoice/email action, browser/Coupa/Gmail/
Telegram access, credential handling, queue/runtime dispatch, file write,
network operation, Mission Control Swift change, Mac sync/import, or authority
grant is performed here.
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

SCHEMA_VERSION = "agent_execution_packet_compiler_contract_v0"
READ_MODEL_ID = "agent_execution_packet_compiler_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_PACKET_COMPILER_CONTRACT"

PACKET_TYPES = (
    "INTENT_CLASSIFICATION",
    "BLOCK_FILL",
    "PROOF_DISCOVERY",
    "PROOF_LOOKUP",
    "GUIDED_CAPTURE_PREP",
    "DRAFT_GENERATION_PREP",
    "ARTIFACT_PREVIEW_PREP",
    "APPROVAL_PREP",
    "SEND_PREP",
    "CHIEF_DIAGNOSTIC",
    "HERMES_ADVISORY",
    "NILES_PROJECT",
    "GUARDIAN_REVIEW",
    "UNKNOWN_FAIL_CLOSED",
)

COMPILE_TRIGGERS = (
    "BLOCK_BECAME_ACTIVE",
    "AGENT_REQUESTED_PACKET",
    "OPERATOR_REQUESTED_AGENT_HELP",
    "DISCOVERY_PATH_SELECTED",
    "PROOF_REQUIRED",
    "DRAFT_READY_FOR_REVIEW",
    "APPROVAL_PREP_REQUIRED",
    "CHECK_ENGINE_REQUESTED",
    "WORKFLOW_RESUMED",
    "UNKNOWN_FAIL_CLOSED",
)

CONTEXT_CATEGORIES = (
    "CURRENT_BLOCK",
    "WORKFLOW_SESSION",
    "ACTIVE_DRAFT",
    "VALIDATION_RESULT",
    "PRIOR_RECEIPTS",
    "SOURCE_CARDS",
    "PROOF_REFS",
    "READ_MODELS",
    "CREW_BRIEFINGS",
    "OPERATOR_HANDOFFS",
    "TOOL_MANIFESTS",
    "DOMAIN_FAMILIARITY_HINTS",
    "RAW_PRIVATE_BODY",
    "PROTECTED_EVIDENCE",
    "DEBUG_LOGS",
    "UNKNOWN_FAIL_CLOSED",
)

CAPABILITY_CATEGORIES = (
    "READ_ONLY_CONTEXT_QUERY",
    "SOURCE_CARD_LOOKUP",
    "PROOF_REF_LOOKUP",
    "LOCAL_VALIDATION",
    "INVOICE_PREVIEW_RENDER",
    "DRAFT_TEXT_PREP",
    "EMAIL_DRAFT_PREP",
    "GUIDED_CAPTURE_PREP",
    "APPROVAL_PACKET_PREP",
    "SEND_ADAPTER",
    "BROWSER_AUTOMATION",
    "COUPA_PORTAL_ACCESS",
    "GMAIL_ACCESS",
    "TELEGRAM_SEND",
    "CREDENTIAL_ACCESS",
    "FILE_WRITE",
    "UNKNOWN_FAIL_CLOSED",
)

ALLOWED_RESULT_TYPES = (
    "DRAFT_INTENT_PROPOSAL",
    "NORMALIZED_FIELD_UPDATE",
    "DISCOVERY_SHAPE",
    "PROOF_REF_CANDIDATE",
    "SOURCE_CARD_REF",
    "VALIDATION_SUMMARY",
    "OPERATOR_QUESTION",
    "CREW_BRIEFING",
    "BLOCKED_RESULT",
    "PACKET_REQUEST",
    "UNKNOWN_FAIL_CLOSED",
)

COMPLETION_STATUSES = (
    "PACKET_COMPLETE",
    "NEEDS_OPERATOR",
    "NEEDS_SYSTEM_PACKET",
    "NEEDS_PROOF",
    "NEEDS_GUARDIAN",
    "BLOCKED",
    "STALLED",
    "UNKNOWN_FAIL_CLOSED",
)

CHAIN_STATES = (
    "NOT_STARTED",
    "PACKET_ACTIVE",
    "WAITING_ON_AGENT",
    "WAITING_ON_SYSTEM",
    "WAITING_ON_OPERATOR",
    "WAITING_ON_GUARDIAN",
    "PACKET_COMPLETE",
    "CHAIN_ADVANCING",
    "CHAIN_BLOCKED",
    "CHAIN_PARKED",
    "CHAIN_COMPLETE",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_EXECUTION_PACKET_FIELDS = (
    "execution_packet_id",
    "packet_title",
    "assigned_agent",
    "agent_role",
    "target_world",
    "target_lane",
    "workflow_session_ref",
    "block_ref",
    "block_state",
    "packet_type",
    "packet_objective",
    "current_state_refs",
    "active_draft_refs",
    "relevant_prior_receipt_refs",
    "allowed_context_refs",
    "excluded_context_refs",
    "allowed_tools",
    "blocked_tools",
    "allowed_mcp_refs",
    "blocked_mcp_refs",
    "allowed_script_refs",
    "blocked_script_refs",
    "allowed_hook_refs",
    "blocked_hook_refs",
    "proof_requirements",
    "validation_requirements",
    "expected_return_shape_ref",
    "timeout_policy_ref",
    "stop_conditions",
    "authority_boundary",
    "operator_visibility",
    "next_safe_move",
)

REQUIRED_COMPILER_FIELDS = (
    "compiler_id",
    "source_workflow_contract_refs",
    "source_handoff_contract_refs",
    "source_bridge_routing_refs",
    "compile_trigger",
    "input_block_ref",
    "input_draft_intent_ref",
    "input_handoff_session_ref",
    "packet_selection_policy",
    "context_selection_policy",
    "tool_selection_policy",
    "authority_filter_policy",
    "proof_filter_policy",
    "operator_visibility_policy",
    "compiled_packet_refs",
    "rejected_packet_reasons",
    "next_safe_move",
)

REQUIRED_CONTEXT_POLICY_FIELDS = (
    "policy_id",
    "packet_type",
    "include_context_categories",
    "exclude_context_categories",
    "max_context_scope",
    "required_context_refs",
    "optional_context_refs",
    "forbidden_context_refs",
    "raw_body_allowed",
    "protected_context_allowed",
    "summarization_required",
    "proof_refs_allowed",
    "source_card_refs_allowed",
    "read_model_refs_allowed",
    "operator_memory_hint_allowed",
    "next_safe_move",
)

REQUIRED_CAPABILITY_POLICY_FIELDS = (
    "policy_id",
    "packet_type",
    "allowed_capability_categories",
    "blocked_capability_categories",
    "allowed_tools",
    "allowed_mcp_refs",
    "allowed_script_refs",
    "allowed_hook_refs",
    "capability_prerequisites",
    "authority_required",
    "proof_required_before_use",
    "operator_approval_required",
    "guardian_gate_required",
    "fallback_if_unavailable",
    "next_safe_move",
)

REQUIRED_RETURN_SHAPE_FIELDS = (
    "return_shape_id",
    "packet_type",
    "expected_fields",
    "allowed_result_types",
    "rejected_result_types",
    "proof_refs_expected",
    "draft_intents_expected",
    "validation_result_expected",
    "operator_question_allowed",
    "confidence_required",
    "ambiguity_flags_required",
    "next_packet_request_allowed",
    "completion_status_values",
    "next_safe_move",
)

REQUIRED_PACKET_CHAIN_FIELDS = (
    "packet_chain_id",
    "workflow_session_ref",
    "originating_request",
    "packet_sequence",
    "current_packet_ref",
    "completed_packet_refs",
    "blocked_packet_refs",
    "pending_operator_handoff_refs",
    "downstream_packet_candidates",
    "chain_state",
    "context_budget_strategy",
    "packet_transition_policy",
    "next_safe_move",
)

REQUIRED_OPERATOR_HINT_FIELDS = (
    "hint_id",
    "target_operator_ref",
    "strong_domains",
    "weaker_or_context_dependent_domains",
    "preferred_explanation_modes",
    "support_style",
    "include_by_default",
    "escalation_policy",
    "deeper_support_packet_ref",
    "next_safe_move",
)

REQUIRED_UPSTREAM_CONTEXT_SELECTION_FIELDS = (
    "upstream_ref_id",
    "display_name",
    "classification",
    "upstream_role",
    "source_module_ref",
    "source_read_model_ref",
    "source_operator_read_model_ref",
    "consumable_ref_types",
    "consumed_by_contract_fields",
    "may_supply_allowed_context_refs",
    "may_supply_read_model_refs",
    "may_supply_source_card_refs",
    "may_supply_proof_refs",
    "may_grant_tool_authority",
    "may_grant_runtime_authority",
    "may_execute_packets",
    "may_mutate_workflow_state",
    "may_mutate_old_compiler",
    "is_replaced_by_this_contract",
    "is_duplicated_by_this_contract",
    "authority_boundary",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "packet_execution_allowed": False,
    "live_agent_execution_allowed": False,
    "model_call_allowed": False,
    "tool_execution_allowed": False,
    "mcp_execution_allowed": False,
    "script_execution_allowed": False,
    "hook_execution_allowed": False,
    "receipt_write_allowed": False,
    "state_write_allowed": False,
    "invoice_generation_allowed": False,
    "invoice_preview_render_allowed": False,
    "email_draft_allowed": False,
    "email_send_allowed": False,
    "browser_automation_allowed": False,
    "coupa_access_allowed": False,
    "gmail_access_allowed": False,
    "telegram_send_allowed": False,
    "credential_handling_allowed": False,
    "approval_submission_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "file_write_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_operation_allowed": False,
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

COMMON_BLOCKED_CAPABILITIES = (
    "SEND_ADAPTER",
    "BROWSER_AUTOMATION",
    "COUPA_PORTAL_ACCESS",
    "GMAIL_ACCESS",
    "TELEGRAM_SEND",
    "CREDENTIAL_ACCESS",
    "FILE_WRITE",
)

COMMON_BLOCKED_TOOLS = (
    "live model call",
    "agent runtime activation",
    "tool execution",
    "MCP execution",
    "script execution",
    "hook execution",
    "browser/Coupa/Gmail/Telegram access",
    "credential handling",
    "file write",
    "receipt/state writer",
)

COMMON_STOP_CONDITIONS = (
    "operator judgment required",
    "context is insufficient",
    "proof is missing",
    "Guardian gate required",
    "requested result would require authority not granted by this contract",
)

RELATIONSHIP_REF_PATHS = {
    "workflow_block_intent_live_draft_contract": "generated/read_models/workflow_block_intent_live_draft_contract.json",
    "agent_conversation_handoff_step_packet_contract": (
        "generated/read_models/agent_conversation_handoff_step_packet_contract.json"
    ),
    "bridge_routing_operator_attention_contract": "generated/read_models/bridge_routing_operator_attention_contract.json",
    "operator_solve_path_decision_node_contract": "generated/read_models/operator_solve_path_decision_node_contract.json",
    "guided_capture_protected_evidence_path_contract": (
        "generated/read_models/guided_capture_protected_evidence_path_contract.json"
    ),
    "automation_readiness_feasibility_evaluator_contract": (
        "generated/read_models/automation_readiness_feasibility_evaluator_contract.json"
    ),
    "workflow_session_channel_projection_approval_bus_contract": (
        "generated/read_models/workflow_session_channel_projection_approval_bus_contract.json"
    ),
    "context_selection_knowledge_packet_v0_existing_substrate": "generated/read_models/context_selection.json",
}


@dataclass(frozen=True)
class AgentExecutionPacket:
    execution_packet_id: str
    packet_title: str
    assigned_agent: str
    agent_role: str
    target_world: str
    target_lane: str
    workflow_session_ref: str
    block_ref: str
    block_state: str
    packet_type: str
    packet_objective: str
    current_state_refs: tuple[str, ...]
    active_draft_refs: tuple[str, ...]
    relevant_prior_receipt_refs: tuple[str, ...]
    allowed_context_refs: tuple[str, ...]
    excluded_context_refs: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    blocked_tools: tuple[str, ...]
    allowed_mcp_refs: tuple[str, ...]
    blocked_mcp_refs: tuple[str, ...]
    allowed_script_refs: tuple[str, ...]
    blocked_script_refs: tuple[str, ...]
    allowed_hook_refs: tuple[str, ...]
    blocked_hook_refs: tuple[str, ...]
    proof_requirements: tuple[str, ...]
    validation_requirements: tuple[str, ...]
    expected_return_shape_ref: str
    timeout_policy_ref: str
    stop_conditions: tuple[str, ...]
    authority_boundary: dict[str, bool]
    operator_visibility: str
    next_safe_move: str


@dataclass(frozen=True)
class AgentExecutionPacketCompiler:
    compiler_id: str
    source_workflow_contract_refs: tuple[str, ...]
    source_handoff_contract_refs: tuple[str, ...]
    source_bridge_routing_refs: tuple[str, ...]
    compile_trigger: str
    input_block_ref: str
    input_draft_intent_ref: str
    input_handoff_session_ref: str
    packet_selection_policy: str
    context_selection_policy: str
    tool_selection_policy: str
    authority_filter_policy: str
    proof_filter_policy: str
    operator_visibility_policy: str
    compiled_packet_refs: tuple[str, ...]
    rejected_packet_reasons: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class PacketContextSelectionPolicy:
    policy_id: str
    packet_type: str
    include_context_categories: tuple[str, ...]
    exclude_context_categories: tuple[str, ...]
    max_context_scope: str
    required_context_refs: tuple[str, ...]
    optional_context_refs: tuple[str, ...]
    forbidden_context_refs: tuple[str, ...]
    raw_body_allowed: bool
    protected_context_allowed: bool
    summarization_required: bool
    proof_refs_allowed: bool
    source_card_refs_allowed: bool
    read_model_refs_allowed: bool
    operator_memory_hint_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class PacketCapabilitySelectionPolicy:
    policy_id: str
    packet_type: str
    allowed_capability_categories: tuple[str, ...]
    blocked_capability_categories: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    allowed_mcp_refs: tuple[str, ...]
    allowed_script_refs: tuple[str, ...]
    allowed_hook_refs: tuple[str, ...]
    capability_prerequisites: tuple[str, ...]
    authority_required: tuple[str, ...]
    proof_required_before_use: tuple[str, ...]
    operator_approval_required: bool
    guardian_gate_required: bool
    fallback_if_unavailable: str
    next_safe_move: str


@dataclass(frozen=True)
class AgentPacketReturnShape:
    return_shape_id: str
    packet_type: str
    expected_fields: tuple[str, ...]
    allowed_result_types: tuple[str, ...]
    rejected_result_types: tuple[str, ...]
    proof_refs_expected: bool
    draft_intents_expected: bool
    validation_result_expected: bool
    operator_question_allowed: bool
    confidence_required: bool
    ambiguity_flags_required: bool
    next_packet_request_allowed: bool
    completion_status_values: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class AgentPacketChain:
    packet_chain_id: str
    workflow_session_ref: str
    originating_request: str
    packet_sequence: tuple[str, ...]
    current_packet_ref: str
    completed_packet_refs: tuple[str, ...]
    blocked_packet_refs: tuple[str, ...]
    pending_operator_handoff_refs: tuple[str, ...]
    downstream_packet_candidates: tuple[str, ...]
    chain_state: str
    context_budget_strategy: str
    packet_transition_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class OperatorContextHint:
    hint_id: str
    target_operator_ref: str
    strong_domains: tuple[str, ...]
    weaker_or_context_dependent_domains: tuple[str, ...]
    preferred_explanation_modes: tuple[str, ...]
    support_style: tuple[str, ...]
    include_by_default: bool
    escalation_policy: str
    deeper_support_packet_ref: str
    next_safe_move: str


@dataclass(frozen=True)
class UpstreamSubstrateContextSelectionRef:
    upstream_ref_id: str
    display_name: str
    classification: str
    upstream_role: str
    source_module_ref: str
    source_read_model_ref: str
    source_operator_read_model_ref: str
    consumable_ref_types: tuple[str, ...]
    consumed_by_contract_fields: tuple[str, ...]
    may_supply_allowed_context_refs: bool
    may_supply_read_model_refs: bool
    may_supply_source_card_refs: bool
    may_supply_proof_refs: bool
    may_grant_tool_authority: bool
    may_grant_runtime_authority: bool
    may_execute_packets: bool
    may_mutate_workflow_state: bool
    may_mutate_old_compiler: bool
    is_replaced_by_this_contract: bool
    is_duplicated_by_this_contract: bool
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class AgentExecutionPacketCompilerExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    execution_packet_count: int
    compiler_count: int
    context_policy_count: int
    capability_policy_count: int
    return_shape_count: int
    packet_chain_count: int
    operator_context_hint_count: int
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


def default_execution_packets() -> tuple[AgentExecutionPacket, ...]:
    return (
        AgentExecutionPacket(
            execution_packet_id="capital_hilton_performance_dates_execution_packet",
            packet_title="Normalize Capital Hilton Performance Dates",
            assigned_agent="Cassandra/Clara",
            agent_role="draft block normalizer",
            target_world="Finance",
            target_lane="Capital Hilton",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            block_ref="performance_dates",
            block_state="active_draft",
            packet_type="BLOCK_FILL",
            packet_objective="Normalize added performance dates and return field update plus ambiguity flags.",
            current_state_refs=("capital_hilton_invoice_workflow_session.current_state.performance_dates",),
            active_draft_refs=("workflow_block_intent_live_draft_contract.capital_hilton_mission_control_performance_dates_draft",),
            relevant_prior_receipt_refs=("operator_confirmation_receipt_targets_future",),
            allowed_context_refs=("current candidate dates", "active local draft", "rate ref", "Winship compact context hint"),
            excluded_context_refs=("whole-system context", "RAW_PRIVATE_BODY", "PROTECTED_EVIDENCE", "DEBUG_LOGS"),
            allowed_tools=(),
            blocked_tools=COMMON_BLOCKED_TOOLS,
            allowed_mcp_refs=(),
            blocked_mcp_refs=("all MCP execution refs",),
            allowed_script_refs=(),
            blocked_script_refs=("all script execution refs",),
            allowed_hook_refs=(),
            blocked_hook_refs=("all hook execution refs",),
            proof_requirements=("operator confirmation or proof pointer later before final send path",),
            validation_requirements=("normalize to ISO dates", "detect duplicates", "flag ambiguity explicitly"),
            expected_return_shape_ref="normalized_field_update_return_shape",
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            stop_conditions=COMMON_STOP_CONDITIONS,
            authority_boundary=_authority_boundary(),
            operator_visibility="World-visible as draft support; Bridge only if operator decision is needed.",
            next_safe_move="Return normalized updates only; do not write receipts or generate artifacts.",
        ),
        AgentExecutionPacket(
            execution_packet_id="capital_hilton_po_proof_discovery_execution_packet",
            packet_title="Find Capital Hilton PO Proof Target",
            assigned_agent="Cassandra/Clara",
            agent_role="proof discovery assistant",
            target_world="Finance",
            target_lane="Capital Hilton",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            block_ref="proof_po_reference",
            block_state="needs_proof",
            packet_type="PROOF_DISCOVERY",
            packet_objective="Identify likely PO/reference proof target from existing source cards and proof refs.",
            current_state_refs=("capital_hilton_invoice_workflow_session.proof_summary",),
            active_draft_refs=("capital_hilton_po_reference_draft_future",),
            relevant_prior_receipt_refs=("capital_hilton_proof_resolution_batch",),
            allowed_context_refs=("workflow state summary", "source cards if available", "proof refs if available"),
            excluded_context_refs=("whole-system context", "Coupa live access", "browser automation", "credentials"),
            allowed_tools=(),
            blocked_tools=COMMON_BLOCKED_TOOLS,
            allowed_mcp_refs=(),
            blocked_mcp_refs=("Coupa portal MCP", "browser MCP", "credential MCP"),
            allowed_script_refs=(),
            blocked_script_refs=("portal scraping scripts", "browser automation scripts"),
            allowed_hook_refs=(),
            blocked_hook_refs=("send hooks", "submission hooks", "capture hooks"),
            proof_requirements=("proof refs or operator question required before final invoice path",),
            validation_requirements=("return discovery shape", "mark unknowns", "do not claim proof complete"),
            expected_return_shape_ref="proof_discovery_return_shape",
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            stop_conditions=COMMON_STOP_CONDITIONS,
            authority_boundary=_authority_boundary(),
            operator_visibility="World-visible proof need; proof details stay below deck.",
            next_safe_move="Return candidate proof refs or ask an operator discovery question.",
        ),
        AgentExecutionPacket(
            execution_packet_id="capital_hilton_invoice_preview_execution_packet",
            packet_title="Prepare Capital Hilton Invoice Preview Packet",
            assigned_agent="Cassandra/Clara",
            agent_role="artifact preview preparer",
            target_world="Finance",
            target_lane="Capital Hilton",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            block_ref="invoice_preview",
            block_state="future_gate_required",
            packet_type="ARTIFACT_PREVIEW_PREP",
            packet_objective="Prepare the shape of an invoice preview packet from captured state when future gates allow.",
            current_state_refs=("captured_invoice_state_future", "math_validation_refs_future"),
            active_draft_refs=("invoice_preview_draft_packet_future",),
            relevant_prior_receipt_refs=("operator_answer_receipts_future", "math_validation_receipts_future"),
            allowed_context_refs=("captured state summary if available", "rate/date refs", "preview validation refs"),
            excluded_context_refs=("whole-system context", "RAW_PRIVATE_BODY", "email send path", "file write path"),
            allowed_tools=(),
            blocked_tools=COMMON_BLOCKED_TOOLS,
            allowed_mcp_refs=(),
            blocked_mcp_refs=("email MCP", "browser MCP", "file write MCP"),
            allowed_script_refs=(),
            blocked_script_refs=("invoice generator scripts", "PDF writer scripts", "email scripts"),
            allowed_hook_refs=(),
            blocked_hook_refs=("send hooks", "file write hooks"),
            proof_requirements=("captured state and math validation required before preview render in a future lane",),
            validation_requirements=("confirm captured state exists", "confirm invoice preview gate exists", "block if gate missing"),
            expected_return_shape_ref="artifact_preview_prep_return_shape",
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            stop_conditions=COMMON_STOP_CONDITIONS,
            authority_boundary=_authority_boundary(),
            operator_visibility="Preview-prep status only; no invoice generation.",
            next_safe_move="Return blocked/prep shape until future preview render authority exists.",
        ),
        AgentExecutionPacket(
            execution_packet_id="telegram_cassandra_invoice_intent_execution_packet",
            packet_title="Classify Telegram Invoice Request",
            assigned_agent="Cassandra",
            agent_role="conversation intent classifier",
            target_world="Finance",
            target_lane="Capital Hilton",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            block_ref="invoice_request",
            block_state="user_utterance_received",
            packet_type="INTENT_CLASSIFICATION",
            packet_objective="Classify Telegram request into known Capital Hilton workflow block sequence.",
            current_state_refs=("capital_hilton_invoice_workflow_session.summary",),
            active_draft_refs=("capital_hilton_telegram_invoice_request_draft",),
            relevant_prior_receipt_refs=(),
            allowed_context_refs=("user utterance", "workflow session summary", "known workflow block list"),
            excluded_context_refs=("whole-system context", "raw private thread history", "credentials", "unrelated worlds"),
            allowed_tools=(),
            blocked_tools=COMMON_BLOCKED_TOOLS,
            allowed_mcp_refs=(),
            blocked_mcp_refs=("Telegram send MCP", "Gmail MCP", "Coupa MCP"),
            allowed_script_refs=(),
            blocked_script_refs=("message send scripts", "invoice scripts"),
            allowed_hook_refs=(),
            blocked_hook_refs=("send hooks", "runtime hooks"),
            proof_requirements=("known workflow ref required before downstream packet",),
            validation_requirements=("return intent classification and next packet request only",),
            expected_return_shape_ref="intent_classification_return_shape",
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            stop_conditions=COMMON_STOP_CONDITIONS,
            authority_boundary=_authority_boundary(),
            operator_visibility="Compact Telegram/Mission Control liveness status.",
            next_safe_move="Request the next focused packet or ask for clarification.",
        ),
        AgentExecutionPacket(
            execution_packet_id="chief_check_engine_diagnostic_execution_packet",
            packet_title="Chief Check Engine Diagnostic Packet",
            assigned_agent="Chief",
            agent_role="diagnostic briefer",
            target_world="Build",
            target_lane="Check Engine",
            workflow_session_ref="check_engine_diagnostic_session",
            block_ref="current_blocker",
            block_state="diagnostic_requested",
            packet_type="CHIEF_DIAGNOSTIC",
            packet_objective="Return concise blocker briefing or Engineering Contained from current read-model/test refs only.",
            current_state_refs=("current read-model refs", "focused test refs", "dirty state summary refs"),
            active_draft_refs=("chief_check_engine_build_blocker_draft",),
            relevant_prior_receipt_refs=("diagnostic_summary_receipt_target_future",),
            allowed_context_refs=("current diagnostic read-model refs", "focused validation refs"),
            excluded_context_refs=("whole-system context", "broad private scan", "repair execution", "shell execution"),
            allowed_tools=(),
            blocked_tools=COMMON_BLOCKED_TOOLS + ("shell execution", "broad scan"),
            allowed_mcp_refs=(),
            blocked_mcp_refs=("runtime MCP", "browser MCP"),
            allowed_script_refs=(),
            blocked_script_refs=("repair scripts", "cleanup scripts", "test-running scripts"),
            allowed_hook_refs=(),
            blocked_hook_refs=("repair hooks", "runtime hooks"),
            proof_requirements=("current validation refs required before repair decision",),
            validation_requirements=("separate blocker summary from repair action", "mark no-action status"),
            expected_return_shape_ref="chief_diagnostic_return_shape",
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            stop_conditions=COMMON_STOP_CONDITIONS,
            authority_boundary=_authority_boundary(),
            operator_visibility="Shipyard/Engineering unless captain decision is required.",
            next_safe_move="Return blocker briefing; do not run repair.",
        ),
        AgentExecutionPacket(
            execution_packet_id="operator_out_of_depth_support_packet",
            packet_title="Non-Patronizing Domain Support Packet",
            assigned_agent="Cassandra/Clara",
            agent_role="operator support translator",
            target_world="Finance",
            target_lane="Capital Hilton",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            block_ref="po_reference_support",
            block_state="operator_support_requested",
            packet_type="HERMES_ADVISORY",
            packet_objective="Use compact operator context hints to explain PO/Coupa uncertainty without patronizing.",
            current_state_refs=("operator_context_hint_winship", "capital_hilton_po_proof_discovery_execution_packet"),
            active_draft_refs=("po_reference_discovery_draft_future",),
            relevant_prior_receipt_refs=(),
            allowed_context_refs=("compact operator context hint", "current block", "discovery options"),
            excluded_context_refs=("whole-system context", "personal dossier", "raw private bodies", "credentials"),
            allowed_tools=(),
            blocked_tools=COMMON_BLOCKED_TOOLS,
            allowed_mcp_refs=(),
            blocked_mcp_refs=("all MCP execution refs",),
            allowed_script_refs=(),
            blocked_script_refs=("all script execution refs",),
            allowed_hook_refs=(),
            blocked_hook_refs=("all hook execution refs",),
            proof_requirements=("support output must feed discovery block or operator question, not passive advice",),
            validation_requirements=("do not assume ignorance", "do not over-explain by default", "offer help-me-figure-it-out choices"),
            expected_return_shape_ref="operator_support_return_shape",
            timeout_policy_ref="standard_agent_handoff_timeout_policy",
            stop_conditions=COMMON_STOP_CONDITIONS,
            authority_boundary=_authority_boundary(),
            operator_visibility="Shown only when support would help a current unfamiliar-domain block.",
            next_safe_move="Offer compact choices that feed the discovery workflow.",
        ),
    )


def default_compilers() -> tuple[AgentExecutionPacketCompiler, ...]:
    return (
        AgentExecutionPacketCompiler(
            compiler_id="capital_hilton_performance_dates_packet_compiler",
            source_workflow_contract_refs=(
                "workflow_block_intent_live_draft_contract",
                "operator_solve_path_decision_node_contract",
            ),
            source_handoff_contract_refs=("agent_conversation_handoff_step_packet_contract",),
            source_bridge_routing_refs=("bridge_routing_operator_attention_contract",),
            compile_trigger="BLOCK_BECAME_ACTIVE",
            input_block_ref="performance_dates",
            input_draft_intent_ref="capital_hilton_mission_control_performance_dates_draft",
            input_handoff_session_ref="mission_control_capital_hilton_draft_handoff",
            packet_selection_policy="smallest useful BLOCK_FILL packet for active draft",
            context_selection_policy="block_fill_context_policy",
            tool_selection_policy="block_fill_capability_policy",
            authority_filter_policy="drop any capability requiring live execution or write authority",
            proof_filter_policy="include proof refs only as references, never as proof-complete claims",
            operator_visibility_policy="Finance World status unless decision needed",
            compiled_packet_refs=("capital_hilton_performance_dates_execution_packet",),
            rejected_packet_reasons=(),
            next_safe_move="Compile draft normalizer packet without execution authority.",
        ),
        AgentExecutionPacketCompiler(
            compiler_id="capital_hilton_po_proof_discovery_packet_compiler",
            source_workflow_contract_refs=("guided_capture_protected_evidence_path_contract", "automation_readiness_feasibility_evaluator_contract"),
            source_handoff_contract_refs=("agent_conversation_handoff_step_packet_contract",),
            source_bridge_routing_refs=("bridge_routing_operator_attention_contract",),
            compile_trigger="PROOF_REQUIRED",
            input_block_ref="proof_po_reference",
            input_draft_intent_ref="capital_hilton_po_reference_draft_future",
            input_handoff_session_ref="telegram_cassandra_capital_hilton_invoice_handoff",
            packet_selection_policy="PROOF_DISCOVERY packet before any guided capture or portal access",
            context_selection_policy="proof_discovery_context_policy",
            tool_selection_policy="proof_discovery_capability_policy",
            authority_filter_policy="reject Coupa/browser/credential capabilities",
            proof_filter_policy="source cards and proof refs only if available",
            operator_visibility_policy="Finance World proof-needed marker; below-deck proof detail",
            compiled_packet_refs=("capital_hilton_po_proof_discovery_execution_packet",),
            rejected_packet_reasons=("Coupa live access blocked", "browser automation blocked", "credential access blocked"),
            next_safe_move="Return discovery candidates or operator question; do not access Coupa.",
        ),
        AgentExecutionPacketCompiler(
            compiler_id="telegram_cassandra_invoice_request_chain_compiler",
            source_workflow_contract_refs=("workflow_block_intent_live_draft_contract", "workflow_session_channel_projection_approval_bus_contract"),
            source_handoff_contract_refs=("agent_conversation_handoff_step_packet_contract",),
            source_bridge_routing_refs=("bridge_routing_operator_attention_contract",),
            compile_trigger="OPERATOR_REQUESTED_AGENT_HELP",
            input_block_ref="invoice_request",
            input_draft_intent_ref="capital_hilton_telegram_invoice_request_draft",
            input_handoff_session_ref="telegram_cassandra_capital_hilton_invoice_handoff",
            packet_selection_policy="dispatch multiple focused packets rather than one huge packet",
            context_selection_policy="intent_then_block_then_preview_context_policy",
            tool_selection_policy="conversation_chain_capability_policy",
            authority_filter_policy="send, browser, Coupa, Gmail, Telegram send, credential, and file write capabilities blocked",
            proof_filter_policy="ask for missing proof instead of hallucinating",
            operator_visibility_policy="compact liveness status with handoff only when needed",
            compiled_packet_refs=(
                "telegram_cassandra_invoice_intent_execution_packet",
                "capital_hilton_performance_dates_execution_packet",
                "capital_hilton_invoice_preview_execution_packet",
            ),
            rejected_packet_reasons=("send packet rejected because send authority false",),
            next_safe_move="Advance packet chain until operator, proof, Guardian, or gate is needed.",
        ),
        AgentExecutionPacketCompiler(
            compiler_id="chief_check_engine_packet_compiler",
            source_workflow_contract_refs=("workflow_block_intent_live_draft_contract",),
            source_handoff_contract_refs=("agent_conversation_handoff_step_packet_contract",),
            source_bridge_routing_refs=("bridge_routing_operator_attention_contract",),
            compile_trigger="CHECK_ENGINE_REQUESTED",
            input_block_ref="current_blocker",
            input_draft_intent_ref="chief_check_engine_build_blocker_draft",
            input_handoff_session_ref="chief_check_engine_conversation_handoff",
            packet_selection_policy="Shipyard diagnostic packet with current read-model/test refs only",
            context_selection_policy="chief_diagnostic_context_policy",
            tool_selection_policy="chief_diagnostic_capability_policy",
            authority_filter_policy="drop repair, shell, broad scan, runtime, and cleanup authority",
            proof_filter_policy="require current diagnostic refs",
            operator_visibility_policy="Engineering Contained unless captain decision required",
            compiled_packet_refs=("chief_check_engine_diagnostic_execution_packet",),
            rejected_packet_reasons=("repair execution blocked", "shell execution blocked", "broad scan blocked"),
            next_safe_move="Return concise blocker briefing without repair execution.",
        ),
    )


def default_context_policies() -> tuple[PacketContextSelectionPolicy, ...]:
    return (
        PacketContextSelectionPolicy(
            policy_id="block_fill_context_policy",
            packet_type="BLOCK_FILL",
            include_context_categories=("CURRENT_BLOCK", "WORKFLOW_SESSION", "ACTIVE_DRAFT", "VALIDATION_RESULT", "DOMAIN_FAMILIARITY_HINTS"),
            exclude_context_categories=("RAW_PRIVATE_BODY", "PROTECTED_EVIDENCE", "DEBUG_LOGS"),
            max_context_scope="single active block plus direct workflow/draft refs",
            required_context_refs=("current block", "active draft", "workflow session"),
            optional_context_refs=("compact operator context hint", "validation result"),
            forbidden_context_refs=("whole-system context", "raw private bodies", "credentials"),
            raw_body_allowed=False,
            protected_context_allowed=False,
            summarization_required=True,
            proof_refs_allowed=True,
            source_card_refs_allowed=False,
            read_model_refs_allowed=True,
            operator_memory_hint_allowed=True,
            next_safe_move="Provide enough context to fill the block, not the whole workflow.",
        ),
        PacketContextSelectionPolicy(
            policy_id="proof_discovery_context_policy",
            packet_type="PROOF_DISCOVERY",
            include_context_categories=("CURRENT_BLOCK", "WORKFLOW_SESSION", "SOURCE_CARDS", "PROOF_REFS", "READ_MODELS"),
            exclude_context_categories=("RAW_PRIVATE_BODY", "PROTECTED_EVIDENCE", "DEBUG_LOGS"),
            max_context_scope="proof target block plus existing source/proof refs",
            required_context_refs=("workflow proof summary", "current proof-needed block"),
            optional_context_refs=("source cards", "prior proof refs"),
            forbidden_context_refs=("Coupa live portal", "credentials", "raw protected bodies"),
            raw_body_allowed=False,
            protected_context_allowed=False,
            summarization_required=True,
            proof_refs_allowed=True,
            source_card_refs_allowed=True,
            read_model_refs_allowed=True,
            operator_memory_hint_allowed=True,
            next_safe_move="Use refs and source cards only; ask for discovery if proof is missing.",
        ),
        PacketContextSelectionPolicy(
            policy_id="artifact_preview_context_policy",
            packet_type="ARTIFACT_PREVIEW_PREP",
            include_context_categories=("WORKFLOW_SESSION", "ACTIVE_DRAFT", "VALIDATION_RESULT", "PRIOR_RECEIPTS"),
            exclude_context_categories=("RAW_PRIVATE_BODY", "PROTECTED_EVIDENCE", "DEBUG_LOGS"),
            max_context_scope="captured invoice state summary and validation refs only",
            required_context_refs=("captured state summary future", "math validation refs future"),
            optional_context_refs=("prior receipt refs future",),
            forbidden_context_refs=("raw email bodies", "file system artifact paths for writing", "credentials"),
            raw_body_allowed=False,
            protected_context_allowed=False,
            summarization_required=True,
            proof_refs_allowed=True,
            source_card_refs_allowed=False,
            read_model_refs_allowed=True,
            operator_memory_hint_allowed=False,
            next_safe_move="Prepare preview shape only if future captured state exists.",
        ),
        PacketContextSelectionPolicy(
            policy_id="chief_diagnostic_context_policy",
            packet_type="CHIEF_DIAGNOSTIC",
            include_context_categories=("CURRENT_BLOCK", "READ_MODELS", "VALIDATION_RESULT", "DEBUG_LOGS"),
            exclude_context_categories=("RAW_PRIVATE_BODY", "PROTECTED_EVIDENCE"),
            max_context_scope="current read-model/test refs only; no broad scan",
            required_context_refs=("current read-model refs", "focused test refs"),
            optional_context_refs=("dirty state summary refs", "debug log summary refs"),
            forbidden_context_refs=("private raw files", "credentials", "unrelated repo scans"),
            raw_body_allowed=False,
            protected_context_allowed=False,
            summarization_required=True,
            proof_refs_allowed=True,
            source_card_refs_allowed=False,
            read_model_refs_allowed=True,
            operator_memory_hint_allowed=False,
            next_safe_move="Keep debug detail in Shipyard/Engineering and return concise summary.",
        ),
    )


def default_capability_policies() -> tuple[PacketCapabilitySelectionPolicy, ...]:
    return (
        PacketCapabilitySelectionPolicy(
            policy_id="block_fill_capability_policy",
            packet_type="BLOCK_FILL",
            allowed_capability_categories=("LOCAL_VALIDATION",),
            blocked_capability_categories=COMMON_BLOCKED_CAPABILITIES,
            allowed_tools=(),
            allowed_mcp_refs=(),
            allowed_script_refs=(),
            allowed_hook_refs=(),
            capability_prerequisites=("deterministic current block refs",),
            authority_required=("none in this contract",),
            proof_required_before_use=("proof not required for draft preview; required later for send path",),
            operator_approval_required=False,
            guardian_gate_required=False,
            fallback_if_unavailable="ask operator clarifying question",
            next_safe_move="Return normalized draft update only.",
        ),
        PacketCapabilitySelectionPolicy(
            policy_id="proof_discovery_capability_policy",
            packet_type="PROOF_DISCOVERY",
            allowed_capability_categories=("SOURCE_CARD_LOOKUP", "PROOF_REF_LOOKUP", "READ_ONLY_CONTEXT_QUERY"),
            blocked_capability_categories=COMMON_BLOCKED_CAPABILITIES,
            allowed_tools=(),
            allowed_mcp_refs=(),
            allowed_script_refs=(),
            allowed_hook_refs=(),
            capability_prerequisites=("source/proof refs already available in read-models",),
            authority_required=("no live portal authority",),
            proof_required_before_use=("source/proof refs must be metadata or safe summaries",),
            operator_approval_required=False,
            guardian_gate_required=False,
            fallback_if_unavailable="create operator discovery question",
            next_safe_move="Return discovery shape or proof candidate refs.",
        ),
        PacketCapabilitySelectionPolicy(
            policy_id="artifact_preview_capability_policy",
            packet_type="ARTIFACT_PREVIEW_PREP",
            allowed_capability_categories=("INVOICE_PREVIEW_RENDER",),
            blocked_capability_categories=COMMON_BLOCKED_CAPABILITIES,
            allowed_tools=(),
            allowed_mcp_refs=(),
            allowed_script_refs=(),
            allowed_hook_refs=(),
            capability_prerequisites=("future invoice preview gate", "captured state", "math validation"),
            authority_required=("invoice_preview_render_allowed future gate",),
            proof_required_before_use=("captured receipts and validation refs",),
            operator_approval_required=True,
            guardian_gate_required=True,
            fallback_if_unavailable="return BLOCKED_RESULT with missing gate refs",
            next_safe_move="Model preview prep only; do not render invoice here.",
        ),
        PacketCapabilitySelectionPolicy(
            policy_id="chief_diagnostic_capability_policy",
            packet_type="CHIEF_DIAGNOSTIC",
            allowed_capability_categories=("READ_ONLY_CONTEXT_QUERY", "LOCAL_VALIDATION"),
            blocked_capability_categories=COMMON_BLOCKED_CAPABILITIES + ("BROWSER_AUTOMATION",),
            allowed_tools=(),
            allowed_mcp_refs=(),
            allowed_script_refs=(),
            allowed_hook_refs=(),
            capability_prerequisites=("current read-model/test refs already available",),
            authority_required=("none in this contract",),
            proof_required_before_use=("diagnostic refs must be current",),
            operator_approval_required=False,
            guardian_gate_required=False,
            fallback_if_unavailable="return Engineering Contained or ask for updated refs",
            next_safe_move="Return blocker briefing; do not run tests or shell.",
        ),
        PacketCapabilitySelectionPolicy(
            policy_id="conversation_chain_capability_policy",
            packet_type="INTENT_CLASSIFICATION",
            allowed_capability_categories=("READ_ONLY_CONTEXT_QUERY", "LOCAL_VALIDATION"),
            blocked_capability_categories=COMMON_BLOCKED_CAPABILITIES,
            allowed_tools=(),
            allowed_mcp_refs=(),
            allowed_script_refs=(),
            allowed_hook_refs=(),
            capability_prerequisites=("handoff session ref", "workflow session ref"),
            authority_required=("none in this contract",),
            proof_required_before_use=("none for intent classification",),
            operator_approval_required=False,
            guardian_gate_required=False,
            fallback_if_unavailable="clarify intent with operator",
            next_safe_move="Classify intent, then request next packet.",
        ),
    )


def default_return_shapes() -> tuple[AgentPacketReturnShape, ...]:
    return (
        AgentPacketReturnShape(
            return_shape_id="normalized_field_update_return_shape",
            packet_type="BLOCK_FILL",
            expected_fields=("packet_ref", "normalized_updates", "ambiguity_flags", "confidence", "completion_status"),
            allowed_result_types=("NORMALIZED_FIELD_UPDATE", "OPERATOR_QUESTION", "BLOCKED_RESULT", "PACKET_REQUEST"),
            rejected_result_types=("freeform_only", "execution_complete", "proof_complete_without_refs"),
            proof_refs_expected=False,
            draft_intents_expected=True,
            validation_result_expected=True,
            operator_question_allowed=True,
            confidence_required=True,
            ambiguity_flags_required=True,
            next_packet_request_allowed=True,
            completion_status_values=COMPLETION_STATUSES,
            next_safe_move="Reject prose-only answers; require structured updates or explicit uncertainty.",
        ),
        AgentPacketReturnShape(
            return_shape_id="proof_discovery_return_shape",
            packet_type="PROOF_DISCOVERY",
            expected_fields=("packet_ref", "discovery_shape", "proof_ref_candidates", "operator_question", "completion_status"),
            allowed_result_types=("DISCOVERY_SHAPE", "PROOF_REF_CANDIDATE", "SOURCE_CARD_REF", "OPERATOR_QUESTION", "BLOCKED_RESULT"),
            rejected_result_types=("freeform_only", "live_portal_result", "proof_complete_without_receipt"),
            proof_refs_expected=True,
            draft_intents_expected=False,
            validation_result_expected=True,
            operator_question_allowed=True,
            confidence_required=True,
            ambiguity_flags_required=True,
            next_packet_request_allowed=True,
            completion_status_values=COMPLETION_STATUSES,
            next_safe_move="Return candidates or ask for discovery; do not claim external truth.",
        ),
        AgentPacketReturnShape(
            return_shape_id="artifact_preview_prep_return_shape",
            packet_type="ARTIFACT_PREVIEW_PREP",
            expected_fields=("packet_ref", "preview_prerequisites", "missing_gates", "blocked_reason", "completion_status"),
            allowed_result_types=("VALIDATION_SUMMARY", "BLOCKED_RESULT", "PACKET_REQUEST", "CREW_BRIEFING"),
            rejected_result_types=("freeform_only", "invoice_generated", "file_written", "email_drafted"),
            proof_refs_expected=True,
            draft_intents_expected=False,
            validation_result_expected=True,
            operator_question_allowed=True,
            confidence_required=True,
            ambiguity_flags_required=True,
            next_packet_request_allowed=True,
            completion_status_values=COMPLETION_STATUSES,
            next_safe_move="Return prep or blocked shape; never return generated artifact here.",
        ),
        AgentPacketReturnShape(
            return_shape_id="intent_classification_return_shape",
            packet_type="INTENT_CLASSIFICATION",
            expected_fields=("packet_ref", "inferred_intent", "workflow_ref", "next_packet_request", "confidence", "completion_status"),
            allowed_result_types=("DRAFT_INTENT_PROPOSAL", "PACKET_REQUEST", "OPERATOR_QUESTION", "BLOCKED_RESULT"),
            rejected_result_types=("freeform_only", "workflow_state_written", "message_sent"),
            proof_refs_expected=False,
            draft_intents_expected=True,
            validation_result_expected=True,
            operator_question_allowed=True,
            confidence_required=True,
            ambiguity_flags_required=True,
            next_packet_request_allowed=True,
            completion_status_values=COMPLETION_STATUSES,
            next_safe_move="Classify and request the next packet rather than improvising context.",
        ),
        AgentPacketReturnShape(
            return_shape_id="chief_diagnostic_return_shape",
            packet_type="CHIEF_DIAGNOSTIC",
            expected_fields=("packet_ref", "blocker_summary", "proof_refs", "captain_decision_needed", "completion_status"),
            allowed_result_types=("CREW_BRIEFING", "VALIDATION_SUMMARY", "BLOCKED_RESULT", "OPERATOR_QUESTION"),
            rejected_result_types=("freeform_only", "repair_executed", "shell_output_from_new_command"),
            proof_refs_expected=True,
            draft_intents_expected=False,
            validation_result_expected=True,
            operator_question_allowed=True,
            confidence_required=True,
            ambiguity_flags_required=True,
            next_packet_request_allowed=True,
            completion_status_values=COMPLETION_STATUSES,
            next_safe_move="Return concise blocker briefing or Engineering Contained.",
        ),
        AgentPacketReturnShape(
            return_shape_id="operator_support_return_shape",
            packet_type="HERMES_ADVISORY",
            expected_fields=("packet_ref", "plain_explanation", "familiar_analogy_if_useful", "workflow_choices", "completion_status"),
            allowed_result_types=("CREW_BRIEFING", "OPERATOR_QUESTION", "DISCOVERY_SHAPE", "PACKET_REQUEST"),
            rejected_result_types=("freeform_only", "personal_dossier", "passive_advice_without_workflow_choice"),
            proof_refs_expected=False,
            draft_intents_expected=False,
            validation_result_expected=False,
            operator_question_allowed=True,
            confidence_required=False,
            ambiguity_flags_required=True,
            next_packet_request_allowed=True,
            completion_status_values=COMPLETION_STATUSES,
            next_safe_move="Offer compact help-me-figure-it-out choices without patronizing.",
        ),
    )


def default_packet_chains() -> tuple[AgentPacketChain, ...]:
    return (
        AgentPacketChain(
            packet_chain_id="telegram_cassandra_invoice_request_packet_chain",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            originating_request="Send Capital Hilton an invoice for this week's and last week's job.",
            packet_sequence=(
                "telegram_cassandra_invoice_intent_execution_packet",
                "capital_hilton_performance_dates_execution_packet",
                "capital_hilton_invoice_preview_execution_packet",
                "guardian_capital_hilton_approval_prep_packet_future",
                "send_packet_blocked_future",
            ),
            current_packet_ref="capital_hilton_performance_dates_execution_packet",
            completed_packet_refs=("telegram_cassandra_invoice_intent_execution_packet",),
            blocked_packet_refs=("send_packet_blocked_future",),
            pending_operator_handoff_refs=("capital_hilton_missing_dates_operator_handoff",),
            downstream_packet_candidates=("capital_hilton_po_proof_discovery_execution_packet", "capital_hilton_invoice_preview_execution_packet"),
            chain_state="WAITING_ON_OPERATOR",
            context_budget_strategy="multiple small packets: intent, block fill, missing question, preview prep, approval prep; never one huge packet",
            packet_transition_policy="advance only after deterministic validation; pause for operator/proof/Guardian/gates",
            next_safe_move="Ask the missing question and keep send blocked.",
        ),
        AgentPacketChain(
            packet_chain_id="chief_check_engine_packet_chain",
            workflow_session_ref="check_engine_diagnostic_session",
            originating_request="What is blocking the build?",
            packet_sequence=("chief_check_engine_diagnostic_execution_packet",),
            current_packet_ref="chief_check_engine_diagnostic_execution_packet",
            completed_packet_refs=(),
            blocked_packet_refs=("repair_execution_packet_blocked_future",),
            pending_operator_handoff_refs=("chief_check_engine_decision_operator_handoff",),
            downstream_packet_candidates=("repair_plan_preview_packet_future",),
            chain_state="PACKET_ACTIVE",
            context_budget_strategy="single Shipyard packet with current read-model/test refs only",
            packet_transition_policy="return Engineering Contained unless captain decision is required",
            next_safe_move="Return concise blocker briefing without running repair.",
        ),
    )


def default_operator_context_hints() -> tuple[OperatorContextHint, ...]:
    return (
        OperatorContextHint(
            hint_id="operator_context_hint_winship",
            target_operator_ref="Winship",
            strong_domains=(
                "music production",
                "audio engineering",
                "live sound",
                "video production",
                "creative project workflows",
                "Mac/app workflow thinking",
            ),
            weaker_or_context_dependent_domains=(
                "legal process",
                "finance/AP/Coupa",
                "security engineering",
                "backend systems architecture",
            ),
            preferred_explanation_modes=(
                "cockpit/ship/captain analogy",
                "studio signal-flow analogy",
                "live-show routing analogy",
                "production pipeline analogy",
            ),
            support_style=(
                "explain jargon without hiding it",
                "do not patronize",
                "offer help me figure this out paths",
                "use familiar-domain analogies when useful",
                "include compact hints by default",
                "request deeper support packet only when needed",
            ),
            include_by_default=True,
            escalation_policy="Use compact hint first; request deeper support packet only when the current block needs it.",
            deeper_support_packet_ref="operator_out_of_depth_support_packet",
            next_safe_move="Help unfamiliar domains become workflow choices, not passive advice.",
        ),
    )


def default_upstream_context_selection_refs() -> tuple[UpstreamSubstrateContextSelectionRef, ...]:
    return (
        UpstreamSubstrateContextSelectionRef(
            upstream_ref_id="context_selection_knowledge_packet_v0",
            display_name="Context Selection / Knowledge Packet v0",
            classification="UPSTREAM_SUBSTRATE_CONTEXT_SELECTION",
            upstream_role=(
                "Existing deterministic evidence/knowledge packet compiler that may supply bounded context refs "
                "to a future workflow-block packet compiler."
            ),
            source_module_ref="context_selection.py",
            source_read_model_ref="generated/read_models/context_selection.json",
            source_operator_read_model_ref="generated/read_models/context_selection_OPERATOR.md",
            consumable_ref_types=("allowed_context_refs", "read_model_refs", "source_card_refs", "proof_refs"),
            consumed_by_contract_fields=(
                "AgentExecutionPacket.allowed_context_refs",
                "PacketContextSelectionPolicy.required_context_refs",
                "PacketContextSelectionPolicy.optional_context_refs",
                "PacketContextSelectionPolicy.proof_refs_allowed",
                "PacketContextSelectionPolicy.source_card_refs_allowed",
                "PacketContextSelectionPolicy.read_model_refs_allowed",
            ),
            may_supply_allowed_context_refs=True,
            may_supply_read_model_refs=True,
            may_supply_source_card_refs=True,
            may_supply_proof_refs=True,
            may_grant_tool_authority=False,
            may_grant_runtime_authority=False,
            may_execute_packets=False,
            may_mutate_workflow_state=False,
            may_mutate_old_compiler=False,
            is_replaced_by_this_contract=False,
            is_duplicated_by_this_contract=False,
            authority_boundary=_authority_boundary(),
            next_safe_move="Use as upstream context/proof/source/read-model input only; do not replace, mutate, or execute it.",
        ),
    )


def starship_operating_model_alignment() -> dict[str, Any]:
    return {
        "bridge": "compiles focused orders",
        "crew": "receives packets, not the whole ship",
        "engineering": "supplies proof/context below deck",
        "captain": "gets handoff only when needed",
        "guardian": "handles sensitive gates",
        "ship_logs": "future receipts/proofs prove later commits",
        "shipyard": "Shipyard packets are separate from normal world work",
        "core_rule": "The crew does not roam the whole ship looking for things to do.",
    }


def existing_build_boundary() -> dict[str, Any]:
    return {
        "inspected_existing_substrate": "context_selection_knowledge_packet_v0",
        "why_not_duplicate": "Context Selection already compiles deterministic evidence/knowledge packets from the substrate.",
        "this_contract_gap": "Defines workflow-block to agent assignment packet selection, capability filtering, return shapes, and packet chains.",
        "structured_upstream_ref": "context_selection_knowledge_packet_v0",
        "upstream_classification": "UPSTREAM_SUBSTRATE_CONTEXT_SELECTION",
        "future_packet_compiler_may_consume": ("allowed_context_refs", "read_model_refs", "source_card_refs", "proof_refs"),
        "does_not_replace_context_selection": True,
        "does_not_replace_handoff_contract": True,
        "does_not_mutate_context_selection": True,
        "does_not_build_runtime_compiler": True,
    }


def _asdict_items(items: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [asdict(item) for item in items]


def build_agent_execution_packet_compiler_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    packets = _asdict_items(default_execution_packets())
    compilers = _asdict_items(default_compilers())
    context_policies = _asdict_items(default_context_policies())
    capability_policies = _asdict_items(default_capability_policies())
    return_shapes = _asdict_items(default_return_shapes())
    chains = _asdict_items(default_packet_chains())
    hints = _asdict_items(default_operator_context_hints())
    upstream_context_selection_refs = _asdict_items(default_upstream_context_selection_refs())
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "doctrine": {
            "summary": "Agents should receive exactly what they need, only when they need it.",
            "systems_engineering_not_vibes": True,
            "packet_is_assignment_not_authority": True,
            "deterministic_validation_decides_next": True,
            "receipts_gates_handle_later_durable_state_action": True,
            "no_runtime_compiler_implemented": True,
        },
        "existing_build_boundary": existing_build_boundary(),
        "agent_execution_packet_schema": {
            "structure": "AgentExecutionPacket",
            "required_fields": list(REQUIRED_EXECUTION_PACKET_FIELDS),
            "packet_types": list(PACKET_TYPES),
            "packet_is_assignment_not_authority": True,
            "block_scoped_unless_justified": True,
            "whole_system_context_default": False,
            "raw_private_bodies_default": False,
            "executes_tools_in_this_contract": False,
        },
        "agent_execution_packet_compiler_schema": {
            "structure": "AgentExecutionPacketCompiler",
            "required_fields": list(REQUIRED_COMPILER_FIELDS),
            "compile_triggers": list(COMPILE_TRIGGERS),
            "smallest_useful_packet": True,
            "may_reject_if_authority_or_context_insufficient": True,
            "filters_irrelevant_context": True,
            "filters_unavailable_tools": True,
            "grants_authority_by_itself": False,
            "preserves_bridge_world_below_deck_routing": True,
        },
        "packet_context_selection_policy_schema": {
            "structure": "PacketContextSelectionPolicy",
            "required_fields": list(REQUIRED_CONTEXT_POLICY_FIELDS),
            "context_categories": list(CONTEXT_CATEGORIES),
            "raw_private_bodies_false_by_default": True,
            "protected_context_requires_future_gate": True,
            "domain_familiarity_hints_compact": True,
            "debug_logs_below_deck_unless_shipyard_diagnostic": True,
        },
        "packet_capability_selection_policy_schema": {
            "structure": "PacketCapabilitySelectionPolicy",
            "required_fields": list(REQUIRED_CAPABILITY_POLICY_FIELDS),
            "capability_categories": list(CAPABILITY_CATEGORIES),
            "tools_are_capabilities_not_authority": True,
            "blocked_categories_explicit": True,
            "sensitive_capabilities_require_future_gates": True,
            "executes_capability_in_this_contract": False,
            "send_browser_coupa_gmail_telegram_credentials_file_write_blocked_default": True,
        },
        "agent_packet_return_shape_schema": {
            "structure": "AgentPacketReturnShape",
            "required_fields": list(REQUIRED_RETURN_SHAPE_FIELDS),
            "allowed_result_types": list(ALLOWED_RESULT_TYPES),
            "completion_statuses": list(COMPLETION_STATUSES),
            "freeform_prose_alone_sufficient": False,
            "ambiguity_flags_required_when_unsure": True,
            "agent_may_request_next_packet": True,
            "agent_may_claim_execution_done_without_authority": False,
        },
        "agent_packet_chain_schema": {
            "structure": "AgentPacketChain",
            "required_fields": list(REQUIRED_PACKET_CHAIN_FIELDS),
            "chain_states": list(CHAIN_STATES),
            "multi_step_uses_focused_packets": True,
            "packet_transitions_preserve_validation_receipt_gate_boundaries": True,
            "chain_may_pause_for_operator": True,
            "chain_exposes_liveness_progress_status": True,
        },
        "operator_context_hint_schema": {
            "structure": "OperatorContextHint",
            "required_fields": list(REQUIRED_OPERATOR_HINT_FIELDS),
            "agents_should_not_assume_ignorance": True,
            "do_not_flood_personal_dossier": True,
            "compact_hints_may_travel": True,
            "deeper_support_only_when_needed": True,
            "unfamiliar_domain_support_becomes_workflow_options": True,
        },
        "upstream_substrate_context_selection_ref_schema": {
            "structure": "UpstreamSubstrateContextSelectionRef",
            "required_fields": list(REQUIRED_UPSTREAM_CONTEXT_SELECTION_FIELDS),
            "classification_required": "UPSTREAM_SUBSTRATE_CONTEXT_SELECTION",
            "may_supply_allowed_context_refs": True,
            "may_supply_read_model_refs": True,
            "may_supply_source_card_refs": True,
            "may_supply_proof_refs": True,
            "may_grant_tool_runtime_execution_authority": False,
            "may_replace_or_duplicate_old_compiler": False,
            "may_mutate_old_compiler": False,
        },
        "packet_types": list(PACKET_TYPES),
        "compile_triggers": list(COMPILE_TRIGGERS),
        "context_categories": list(CONTEXT_CATEGORIES),
        "capability_categories": list(CAPABILITY_CATEGORIES),
        "allowed_result_types": list(ALLOWED_RESULT_TYPES),
        "completion_statuses": list(COMPLETION_STATUSES),
        "chain_states": list(CHAIN_STATES),
        "execution_packets": packets,
        "execution_packets_by_id": {item["execution_packet_id"]: item for item in packets},
        "compilers": compilers,
        "compilers_by_id": {item["compiler_id"]: item for item in compilers},
        "context_policies": context_policies,
        "context_policies_by_id": {item["policy_id"]: item for item in context_policies},
        "capability_policies": capability_policies,
        "capability_policies_by_id": {item["policy_id"]: item for item in capability_policies},
        "return_shapes": return_shapes,
        "return_shapes_by_id": {item["return_shape_id"]: item for item in return_shapes},
        "packet_chains": chains,
        "packet_chains_by_id": {item["packet_chain_id"]: item for item in chains},
        "operator_context_hints": hints,
        "operator_context_hints_by_id": {item["hint_id"]: item for item in hints},
        "upstream_substrate_context_selection_refs": upstream_context_selection_refs,
        "upstream_substrate_context_selection_refs_by_id": {
            item["upstream_ref_id"]: item for item in upstream_context_selection_refs
        },
        "relationship_refs": _relationship_refs(repo_root),
        "starship_operating_model_alignment": starship_operating_model_alignment(),
        "authority_boundary": _authority_boundary(),
        "hard_rule": {
            "read_model_only": True,
            "does_not_implement_live_execution": True,
            "does_not_call_models": True,
            "does_not_run_tools_mcps_scripts_hooks": True,
            "does_not_write_receipts": True,
            "does_not_mutate_workflow_state": True,
            "does_not_send_messages": True,
            "does_not_generate_invoices_or_emails": True,
            "does_not_create_runtime_authority": True,
            "may_grant_authority": False,
        },
        "machine_proof": {
            "agent_execution_packet_model_present": True,
            "agent_execution_packet_compiler_model_present": True,
            "packet_context_selection_policy_model_present": True,
            "packet_capability_selection_policy_model_present": True,
            "agent_packet_return_shape_model_present": True,
            "agent_packet_chain_model_present": True,
            "operator_context_hint_model_present": True,
            "execution_packet_count": len(packets),
            "compiler_count": len(compilers),
            "context_policy_count": len(context_policies),
            "capability_policy_count": len(capability_policies),
            "return_shape_count": len(return_shapes),
            "packet_chain_count": len(chains),
            "operator_context_hint_count": len(hints),
            "upstream_context_selection_ref_count": len(upstream_context_selection_refs),
            "inspected_existing_context_selection_substrate": True,
            "does_not_duplicate_existing_context_selection": True,
            "does_not_replace_existing_context_selection": all(
                item["is_replaced_by_this_contract"] is False for item in upstream_context_selection_refs
            ),
            "does_not_mutate_existing_context_selection": all(
                item["may_mutate_old_compiler"] is False for item in upstream_context_selection_refs
            ),
            "upstream_compiler_referenced": any(
                item["upstream_ref_id"] == "context_selection_knowledge_packet_v0"
                for item in upstream_context_selection_refs
            ),
            "upstream_compiler_classified_as_substrate_context_selection": all(
                item["classification"] == "UPSTREAM_SUBSTRATE_CONTEXT_SELECTION"
                for item in upstream_context_selection_refs
            ),
            "upstream_compiler_sources_required_refs": all(
                {
                    "allowed_context_refs",
                    "read_model_refs",
                    "source_card_refs",
                    "proof_refs",
                }
                <= set(item["consumable_ref_types"])
                for item in upstream_context_selection_refs
            ),
            "upstream_compiler_grants_no_tool_runtime_execution_authority": all(
                item["may_grant_tool_authority"] is False
                and item["may_grant_runtime_authority"] is False
                and item["may_execute_packets"] is False
                for item in upstream_context_selection_refs
            ),
            "capital_hilton_dates_example_present": any(
                item["execution_packet_id"] == "capital_hilton_performance_dates_execution_packet"
                for item in packets
            ),
            "capital_hilton_po_proof_example_present": any(
                item["execution_packet_id"] == "capital_hilton_po_proof_discovery_execution_packet"
                for item in packets
            ),
            "invoice_preview_example_present": any(
                item["execution_packet_id"] == "capital_hilton_invoice_preview_execution_packet"
                for item in packets
            ),
            "telegram_cassandra_chain_example_present": any(
                item["packet_chain_id"] == "telegram_cassandra_invoice_request_packet_chain"
                for item in chains
            ),
            "chief_check_engine_example_present": any(
                item["execution_packet_id"] == "chief_check_engine_diagnostic_execution_packet"
                for item in packets
            ),
            "out_of_depth_support_example_present": any(
                item["execution_packet_id"] == "operator_out_of_depth_support_packet"
                for item in packets
            ),
            "packets_include_allowed_and_blocked_capabilities": all(
                "allowed_tools" in item and item["blocked_tools"] for item in packets
            ),
            "packets_are_narrow_focused": all(
                "whole-system context" in item["excluded_context_refs"] and len(item["allowed_context_refs"]) <= 4
                for item in packets
            ),
            "raw_private_body_excluded_by_default": all(
                item["raw_body_allowed"] is False for item in context_policies
            ),
            "protected_context_requires_future_gate": all(
                item["protected_context_allowed"] is False for item in context_policies
            ),
            "return_shapes_reject_freeform_only": all(
                "freeform_only" in item["rejected_result_types"] for item in return_shapes
            ),
            "multi_step_chain_present": any(len(item["packet_sequence"]) > 1 for item in chains),
            "operator_context_hint_compact_non_patronizing": any(
                item["include_by_default"] is True and "do not patronize" in item["support_style"]
                for item in hints
            ),
            "all_authority_flags_false": _all_authority_flags_false(),
            "credentials_or_secrets_included": False,
            "raw_private_bodies_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_agent_execution_packet_compiler_markdown(payload: dict[str, Any]) -> str:
    proof = payload["machine_proof"]
    boundary = payload["existing_build_boundary"]
    starship = payload["starship_operating_model_alignment"]
    lines = [
        "# Agent Execution Packet Compiler Contract v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "An execution packet is a focused assignment for an agent. It says: here is the current block, here is the exact objective, here is the allowed context, here is what is excluded, here are the allowed and blocked capabilities, here is the expected return shape, and here is when to stop.",
        "",
        "This does not build a new runtime. The existing Context Selection / Knowledge Packet layer already handles substrate evidence packet selection. This contract sits above it and defines how workflow blocks compile into agent assignment packets without giving the agent the whole system.",
        "",
        "Agents receive focused packets because one huge context dump makes them less reliable. Multi-step work should become multiple small packets: classify intent, fill the active block, ask the missing question, prepare a preview shape, prepare approval if prerequisites exist, and stop when send/execution would be required.",
        "",
        "Tools, MCPs, scripts, and hooks are capabilities, not authority. A packet can list what would be allowed or blocked, but this contract does not run any capability. Browser, Coupa, Gmail, Telegram send, credentials, file write, invoice generation, email send, and approval submission stay blocked.",
        "",
        "Telegram/Cassandra and Mission Control can share workflow state because both compile from the same block/draft/session refs. The surface can differ; the packet shape stays consistent.",
        "",
        "Compact operator context hints help an agent explain unfamiliar domains without being patronizing. The hint can say to use a studio signal-flow or ship/bridge analogy when useful, but it should not become a personal dossier or passive advice.",
        "",
        "No live execution exists yet. Deterministic validation decides what happens next. Receipts and gates handle durable state or action later.",
        "",
        "## Existing-Build Boundary",
        "",
        f"- Existing substrate inspected: `{boundary['inspected_existing_substrate']}`.",
        f"- Boundary: {boundary['why_not_duplicate']}",
        f"- This contract gap: {boundary['this_contract_gap']}",
        "",
        "## Examples",
        "",
        "- Capital Hilton dates: normalize added dates from the active draft and return structured field updates or ambiguity flags.",
        "- Capital Hilton PO proof: identify likely proof/reference targets from source cards and proof refs; no Coupa/browser/credential access.",
        "- Invoice preview: model preview-prep shape only; invoice preview render remains future-gated and not executed.",
        "- Telegram/Cassandra request chain: intent classification, block fill, missing-question handoff, draft preview prep, approval prep, send blocked.",
        "- Chief/check-engine: current read-model/test refs only; return concise blocker briefing or Engineering Contained; no shell/repair/broad scan.",
        "- Out-of-depth support: use compact operator context hints to explain PO/Coupa with familiar analogies and workflow choices, without patronizing.",
        "",
        "## Starship Alignment",
        "",
        f"- Bridge: {starship['bridge']}.",
        f"- Crew: {starship['crew']}.",
        f"- Engineering: {starship['engineering']}.",
        f"- Captain: {starship['captain']}.",
        f"- Guardian: {starship['guardian']}.",
        f"- Ship logs: {starship['ship_logs']}.",
        f"- Shipyard: {starship['shipyard']}.",
        "",
        "## Still Blocked",
        "",
        "- No packet execution, live agent execution, model call, tool/MCP/script/hook execution, receipt/state write, invoice generation, invoice preview render, email draft/send, browser/Coupa/Gmail/Telegram access, credential handling, approval submission, queue/runtime dispatch, file write/cleanup, raw body ingestion, network, Mac sync/import, Mission Control Swift change, or push.",
        "",
        "## Machine Proof Summary",
        "",
        f"- Execution packets: `{proof['execution_packet_count']}`.",
        f"- Compilers: `{proof['compiler_count']}`.",
        f"- Context policies: `{proof['context_policy_count']}`.",
        f"- Capability policies: `{proof['capability_policy_count']}`.",
        f"- Return shapes: `{proof['return_shape_count']}`.",
        f"- Packet chains: `{proof['packet_chain_count']}`.",
        f"- Operator context hints: `{proof['operator_context_hint_count']}`.",
        f"- Does not duplicate existing context selection: `{str(proof['does_not_duplicate_existing_context_selection']).lower()}`.",
        f"- Packets narrow/focused: `{str(proof['packets_are_narrow_focused']).lower()}`.",
        f"- All authority flags false: `{str(proof['all_authority_flags_false']).lower()}`.",
        f"- Content hash: `{proof['content_hash']}`.",
    ]
    return "\n".join(lines) + "\n"


def export_agent_execution_packet_compiler_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> AgentExecutionPacketCompilerExportResult:
    repo_root = Path(repo_root)
    export_path = repo_root / export_root
    export_path.mkdir(parents=True, exist_ok=True)
    payload = build_agent_execution_packet_compiler_contract(repo_root=repo_root, generated_at=generated_at)
    json_path = export_path / JSON_EXPORT_NAME
    operator_path = export_path / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_agent_execution_packet_compiler_markdown(payload), encoding="utf-8")
    proof = payload["machine_proof"]
    return AgentExecutionPacketCompilerExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        execution_packet_count=proof["execution_packet_count"],
        compiler_count=proof["compiler_count"],
        context_policy_count=proof["context_policy_count"],
        capability_policy_count=proof["capability_policy_count"],
        return_shape_count=proof["return_shape_count"],
        packet_chain_count=proof["packet_chain_count"],
        operator_context_hint_count=proof["operator_context_hint_count"],
        action_authority_granted=not proof["all_authority_flags_false"],
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Agent Execution Packet Compiler Contract v0.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--generated-at", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = export_agent_execution_packet_compiler_contract(
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
        print(f"execution_packet_count={result.execution_packet_count}")
        print(f"compiler_count={result.compiler_count}")
        print(f"context_policy_count={result.context_policy_count}")
        print(f"capability_policy_count={result.capability_policy_count}")
        print(f"return_shape_count={result.return_shape_count}")
        print(f"packet_chain_count={result.packet_chain_count}")
        print(f"operator_context_hint_count={result.operator_context_hint_count}")
        print(f"action_authority_granted={str(result.action_authority_granted).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
