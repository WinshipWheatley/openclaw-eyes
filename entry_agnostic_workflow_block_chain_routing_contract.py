"""Entry-Agnostic Workflow Block Chain Proposal / World Routing Contract v0.

This deterministic read-model defines how any request, signal, or agent/system
entry point becomes a workflow/session/block-chain proposal routed to the right
World, Bridge, Shipyard, or Below Deck surface. It is proposal/routing metadata
only. It does not activate workflows, write sessions or blocks, launch crew,
execute packets/tools/models/runtimes, write receipts/state, generate invoices,
send messages, access external systems, or grant live authority.
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

SCHEMA_VERSION = "entry_agnostic_workflow_block_chain_routing_contract_v0"
READ_MODEL_ID = "entry_agnostic_workflow_block_chain_routing_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_ENTRY_ROUTING_CONTRACT"

ORIGIN_SURFACES = (
    "MISSION_CONTROL",
    "TELEGRAM",
    "CASSANDRA_CLARA",
    "CHIEF",
    "GUARDIAN",
    "HERMES",
    "NILES",
    "VOICE_FUTURE",
    "SCHEDULED_TRIGGER_FUTURE",
    "FILE_OR_SOURCE_CARD_DISCOVERY",
    "CHECK_ENGINE_EVENT",
    "SYSTEM_HEALTH_EVENT",
    "UNKNOWN_FAIL_CLOSED",
)

INTENT_TYPES = (
    "EXISTING_WORKFLOW_REQUEST",
    "NEW_WORKFLOW_REQUEST",
    "WORLD_WORK_REQUEST",
    "CHECK_ENGINE_REQUEST",
    "SECURITY_REVIEW_REQUEST",
    "COMMUNICATION_REQUEST",
    "CREATIVE_PROJECT_REQUEST",
    "FINANCE_INVOICE_REQUEST",
    "CLIENT_DELIVERY_REQUEST",
    "PROOF_DISCOVERY_REQUEST",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCK_TYPES = (
    "DECISION",
    "DATA_FIELD",
    "PROOF_REQUIREMENT",
    "DISCOVERY_PATH",
    "GUIDED_CAPTURE",
    "DRAFT_ARTIFACT",
    "APPROVAL_GATE",
    "EXECUTION_GATE",
    "AUTOMATION_READINESS",
    "STATUS_OR_DIAGNOSTIC",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCK_STATES = (
    "LOCKED_DURABLE",
    "CURRENT_UNLOCKED",
    "SYSTEM_FILLED",
    "AGENT_PROPOSED",
    "NEEDS_OPERATOR",
    "NEEDS_PROOF",
    "NEEDS_DISCOVERY",
    "FUTURE_GATED",
    "BELOW_DECK_ONLY",
    "BLOCKED",
    "PARKED",
    "UNKNOWN_FAIL_CLOSED",
)

ROUTE_DESTINATIONS = (
    "HELM_MARKER_ONLY",
    "WORLD_WORK_SURFACE",
    "SHIPYARD_WORK_SURFACE",
    "BELOW_DECK_DETAIL",
    "CREW_BRIEFING",
    "RED_ALERT",
    "QUIET_LOG_ONLY",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_ENTRY_EVENT_FIELDS = (
    "entry_event_id",
    "origin_surface",
    "origin_actor",
    "origin_channel",
    "origin_trigger",
    "source_message_or_signal_summary",
    "entry_text_or_intent_summary",
    "source_refs",
    "initial_confidence",
    "sensitivity_hint",
    "urgency_hint",
    "operator_visible",
    "requires_immediate_attention",
    "blocked_actions",
    "next_safe_move",
)

REQUIRED_INTENT_NORMALIZATION_FIELDS = (
    "normalization_id",
    "entry_event_ref",
    "normalized_intent_title",
    "normalized_intent_type",
    "target_world_candidate",
    "target_lane_candidate",
    "target_workflow_type_candidate",
    "inferred_actor_or_crew",
    "known_fields",
    "unknown_fields",
    "ambiguity_flags",
    "confidence",
    "needs_operator_clarification",
    "needs_agent_compiler",
    "needs_guardian_review",
    "next_safe_move",
)

REQUIRED_CHAIN_PROPOSAL_FIELDS = (
    "proposal_id",
    "source_entry_event_ref",
    "normalized_intent_ref",
    "proposed_workflow_session_ref",
    "proposed_world",
    "proposed_lane",
    "proposed_workflow_type",
    "proposed_blocks",
    "locked_blocks",
    "current_or_unlocked_blocks",
    "hidden_blocks",
    "below_deck_blocks",
    "future_gated_blocks",
    "operator_needed_blocks",
    "system_fillable_blocks",
    "agent_fillable_blocks",
    "recommended_crew",
    "proof_requirements",
    "approval_requirements",
    "downstream_artifact_candidates",
    "confidence",
    "operator_review_recommended",
    "operator_review_required",
    "ready_to_activate_as_draft",
    "authority_boundary",
    "next_safe_move",
)

REQUIRED_BLOCK_PROPOSAL_FIELDS = (
    "block_proposal_id",
    "proposal_ref",
    "block_id",
    "block_label",
    "block_type",
    "block_state",
    "visible_by_default",
    "editable_by_operator",
    "system_fillable",
    "agent_fillable",
    "proof_required",
    "discovery_required",
    "guided_capture_candidate",
    "automation_candidate",
    "downstream_effects",
    "source_refs",
    "help_assist_refs",
    "required_actor_or_crew",
    "authority_boundary",
    "next_safe_move",
)

REQUIRED_ROUTING_DECISION_FIELDS = (
    "routing_decision_id",
    "proposal_ref",
    "route_destination",
    "helm_marker",
    "world_destination",
    "shipyard_destination",
    "below_deck_destination",
    "crew_briefing_refs",
    "alert_level",
    "captain_attention_required",
    "should_show_on_helm",
    "should_open_world",
    "should_route_to_shipyard",
    "should_stay_below_deck",
    "routing_reason",
    "next_safe_move",
)

REQUIRED_SURFACE_COMPATIBILITY_FIELDS = (
    "compatibility_id",
    "proposal_ref",
    "compatible_surfaces",
    "compatible_agents",
    "surfaces_allowed_to_originate",
    "surfaces_allowed_to_render",
    "surfaces_allowed_to_review",
    "surfaces_allowed_to_capture_future",
    "channels_allowed_for_handoff",
    "split_brain_prevention_policy",
    "canonical_session_required",
    "local_state_allowed",
    "next_safe_move",
)

REQUIRED_CREW_DEPLOYMENT_FIELDS = (
    "deployment_id",
    "proposal_ref",
    "recommended_crew",
    "crew_roles",
    "crew_packet_candidates",
    "operator_handoff_candidates",
    "guardian_gate_candidates",
    "chief_check_candidates",
    "hermes_review_candidates",
    "niles_project_candidates",
    "cassandra_clara_candidates",
    "crew_not_needed_reason",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "workflow_activation_allowed": False,
    "workflow_session_write_allowed": False,
    "block_chain_write_allowed": False,
    "crew_activation_allowed": False,
    "agent_activation_allowed": False,
    "packet_execution_allowed": False,
    "model_call_allowed": False,
    "tool_execution_allowed": False,
    "mcp_execution_allowed": False,
    "script_execution_allowed": False,
    "hook_execution_allowed": False,
    "receipt_write_allowed": False,
    "state_write_allowed": False,
    "invoice_generation_allowed": False,
    "email_send_allowed": False,
    "telegram_send_allowed": False,
    "browser_automation_allowed": False,
    "coupa_access_allowed": False,
    "credential_handling_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "file_write_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_operation_allowed": False,
    "gmail_access_allowed": False,
    "calendar_access_allowed": False,
    "approval_submission_allowed": False,
    "ledger_write_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "file_cleanup_archive_promotion_allowed": False,
}

BLOCKED_ACTIONS = (
    "workflow activation",
    "workflow/session/block-chain write",
    "crew or agent activation",
    "packet/model/tool/MCP/script/hook/runtime/queue execution",
    "receipt or state write",
    "invoice generation",
    "email or Telegram send",
    "approval submission",
    "browser/Coupa/Gmail/account access",
    "credential handling",
    "workflow/evidence/runtime file write",
    "raw private body ingestion",
)

COMPATIBLE_SURFACES = (
    "Mission Control",
    "Telegram",
    "Cassandra/Clara conversation",
    "Chief conversation",
    "Guardian review",
    "Hermes advisory",
    "Niles project flow",
    "future voice surface",
)

COMPATIBLE_AGENTS = (
    "Cassandra/Clara",
    "Chief",
    "Guardian",
    "Hermes",
    "Niles",
    "future workflow agents",
)


@dataclass(frozen=True)
class EntryAgnosticWorkflowEntryEvent:
    entry_event_id: str
    origin_surface: str
    origin_actor: str
    origin_channel: str
    origin_trigger: str
    source_message_or_signal_summary: str
    entry_text_or_intent_summary: str
    source_refs: tuple[str, ...]
    initial_confidence: str
    sensitivity_hint: str
    urgency_hint: str
    operator_visible: bool
    requires_immediate_attention: bool
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowIntentNormalization:
    normalization_id: str
    entry_event_ref: str
    normalized_intent_title: str
    normalized_intent_type: str
    target_world_candidate: str
    target_lane_candidate: str
    target_workflow_type_candidate: str
    inferred_actor_or_crew: tuple[str, ...]
    known_fields: dict[str, Any]
    unknown_fields: tuple[str, ...]
    ambiguity_flags: tuple[str, ...]
    confidence: str
    needs_operator_clarification: bool
    needs_agent_compiler: bool
    needs_guardian_review: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowBlockChainProposal:
    proposal_id: str
    source_entry_event_ref: str
    normalized_intent_ref: str
    proposed_workflow_session_ref: str
    proposed_world: str
    proposed_lane: str
    proposed_workflow_type: str
    proposed_blocks: tuple[str, ...]
    locked_blocks: tuple[str, ...]
    current_or_unlocked_blocks: tuple[str, ...]
    hidden_blocks: tuple[str, ...]
    below_deck_blocks: tuple[str, ...]
    future_gated_blocks: tuple[str, ...]
    operator_needed_blocks: tuple[str, ...]
    system_fillable_blocks: tuple[str, ...]
    agent_fillable_blocks: tuple[str, ...]
    recommended_crew: tuple[str, ...]
    proof_requirements: tuple[str, ...]
    approval_requirements: tuple[str, ...]
    downstream_artifact_candidates: tuple[str, ...]
    confidence: str
    operator_review_recommended: bool
    operator_review_required: bool
    ready_to_activate_as_draft: bool
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowBlockProposal:
    block_proposal_id: str
    proposal_ref: str
    block_id: str
    block_label: str
    block_type: str
    block_state: str
    visible_by_default: bool
    editable_by_operator: bool
    system_fillable: bool
    agent_fillable: bool
    proof_required: bool
    discovery_required: bool
    guided_capture_candidate: bool
    automation_candidate: bool
    downstream_effects: tuple[str, ...]
    source_refs: tuple[str, ...]
    help_assist_refs: tuple[str, ...]
    required_actor_or_crew: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowProposalRoutingDecision:
    routing_decision_id: str
    proposal_ref: str
    route_destination: str
    helm_marker: str
    world_destination: str | None
    shipyard_destination: str | None
    below_deck_destination: str | None
    crew_briefing_refs: tuple[str, ...]
    alert_level: str
    captain_attention_required: bool
    should_show_on_helm: bool
    should_open_world: bool
    should_route_to_shipyard: bool
    should_stay_below_deck: bool
    routing_reason: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowSurfaceCompatibility:
    compatibility_id: str
    proposal_ref: str
    compatible_surfaces: tuple[str, ...]
    compatible_agents: tuple[str, ...]
    surfaces_allowed_to_originate: tuple[str, ...]
    surfaces_allowed_to_render: tuple[str, ...]
    surfaces_allowed_to_review: tuple[str, ...]
    surfaces_allowed_to_capture_future: tuple[str, ...]
    channels_allowed_for_handoff: tuple[str, ...]
    split_brain_prevention_policy: str
    canonical_session_required: bool
    local_state_allowed: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowCrewDeploymentProposal:
    deployment_id: str
    proposal_ref: str
    recommended_crew: tuple[str, ...]
    crew_roles: dict[str, str]
    crew_packet_candidates: tuple[str, ...]
    operator_handoff_candidates: tuple[str, ...]
    guardian_gate_candidates: tuple[str, ...]
    chief_check_candidates: tuple[str, ...]
    hermes_review_candidates: tuple[str, ...]
    niles_project_candidates: tuple[str, ...]
    cassandra_clara_candidates: tuple[str, ...]
    crew_not_needed_reason: str | None
    next_safe_move: str


@dataclass(frozen=True)
class EntryRoutingExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    entry_event_count: int
    normalization_count: int
    proposal_count: int
    block_proposal_count: int
    routing_decision_count: int
    compatibility_count: int
    crew_deployment_count: int
    action_authority_granted: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _authority_boundary() -> dict[str, bool]:
    return dict(AUTHORITY_BOUNDARY)


def _all_authority_false() -> bool:
    return all(value is False for value in AUTHORITY_BOUNDARY.values())


def default_entry_events() -> tuple[EntryAgnosticWorkflowEntryEvent, ...]:
    return (
        EntryAgnosticWorkflowEntryEvent(
            entry_event_id="telegram_cassandra_capital_hilton_invoice_entry",
            origin_surface="TELEGRAM",
            origin_actor="Winship via Cassandra",
            origin_channel="telegram_cassandra_conversation",
            origin_trigger="operator_message",
            source_message_or_signal_summary="Send Capital Hilton an invoice for this week's and last week's job.",
            entry_text_or_intent_summary="Prepare a Capital Hilton invoice workflow draft.",
            source_refs=("agent_conversation_handoff_step_packet_contract.telegram_cassandra_invoice_request",),
            initial_confidence="MEDIUM",
            sensitivity_hint="finance_sensitive",
            urgency_hint="normal_attention",
            operator_visible=True,
            requires_immediate_attention=False,
            blocked_actions=BLOCKED_ACTIONS,
            next_safe_move="Normalize to a finance invoice workflow proposal without sending anything.",
        ),
        EntryAgnosticWorkflowEntryEvent(
            entry_event_id="mission_control_capital_hilton_performance_dates_entry",
            origin_surface="MISSION_CONTROL",
            origin_actor="Winship",
            origin_channel="mission_control_finance_world",
            origin_trigger="operator_block_edit",
            source_message_or_signal_summary="Operator edits Performance Dates in the app.",
            entry_text_or_intent_summary="Update the Capital Hilton performance dates draft.",
            source_refs=("workflow_block_intent_live_draft_contract.capital_hilton_mission_control_performance_dates_draft",),
            initial_confidence="HIGH",
            sensitivity_hint="finance_sensitive",
            urgency_hint="normal_attention",
            operator_visible=True,
            requires_immediate_attention=False,
            blocked_actions=BLOCKED_ACTIONS,
            next_safe_move="Keep the edit inside the shared Finance World workflow draft.",
        ),
        EntryAgnosticWorkflowEntryEvent(
            entry_event_id="chief_check_engine_entry",
            origin_surface="CHIEF",
            origin_actor="Winship via Chief",
            origin_channel="chief_check_engine_conversation",
            origin_trigger="operator_question",
            source_message_or_signal_summary="What is blocking the build?",
            entry_text_or_intent_summary="Diagnose current build/system blocker.",
            source_refs=("bridge_routing_operator_attention_contract.chief_check_engine",),
            initial_confidence="HIGH",
            sensitivity_hint="developer_system",
            urgency_hint="shipyard_attention",
            operator_visible=True,
            requires_immediate_attention=False,
            blocked_actions=BLOCKED_ACTIONS,
            next_safe_move="Route to Shipyard/Build diagnostic proposal without repair execution.",
        ),
        EntryAgnosticWorkflowEntryEvent(
            entry_event_id="new_client_recap_workflow_entry",
            origin_surface="CASSANDRA_CLARA",
            origin_actor="Winship",
            origin_channel="conversation",
            origin_trigger="operator_request",
            source_message_or_signal_summary="Set up a monthly client recap workflow.",
            entry_text_or_intent_summary="Propose a new recurring client delivery workflow.",
            source_refs=("workflow_block_intent_live_draft_contract.monthly_client_recap_new_workflow_draft",),
            initial_confidence="MEDIUM",
            sensitivity_hint="client_delivery",
            urgency_hint="normal_attention",
            operator_visible=True,
            requires_immediate_attention=False,
            blocked_actions=BLOCKED_ACTIONS,
            next_safe_move="Propose blocks and ask whether Winship wants to review/fill together.",
        ),
        EntryAgnosticWorkflowEntryEvent(
            entry_event_id="source_card_build_cue_discovery_entry",
            origin_surface="FILE_OR_SOURCE_CARD_DISCOVERY",
            origin_actor="Work Terrain",
            origin_channel="source_card_or_terrain_record",
            origin_trigger="build_cue_candidate",
            source_message_or_signal_summary="A source card or terrain record suggests a build cue.",
            entry_text_or_intent_summary="Route a possible build/reconciliation candidate.",
            source_refs=(
                "work_terrain_surface_map_build_cue_scout.source_records",
                "work_terrain_build_cue_reconciliation_queue.candidates",
            ),
            initial_confidence="LOW_TO_MEDIUM",
            sensitivity_hint="terrain_metadata_only",
            urgency_hint="quiet_unless_operator_decision_needed",
            operator_visible=False,
            requires_immediate_attention=False,
            blocked_actions=BLOCKED_ACTIONS,
            next_safe_move="Place in Work Terrain/Build Cue routing without auto-build.",
        ),
    )


def default_intent_normalizations() -> tuple[WorkflowIntentNormalization, ...]:
    return (
        WorkflowIntentNormalization(
            normalization_id="telegram_cassandra_capital_hilton_invoice_normalization",
            entry_event_ref="telegram_cassandra_capital_hilton_invoice_entry",
            normalized_intent_title="Capital Hilton invoice draft request",
            normalized_intent_type="FINANCE_INVOICE_REQUEST",
            target_world_candidate="Finance",
            target_lane_candidate="Capital Hilton",
            target_workflow_type_candidate="INVOICE_WORKFLOW",
            inferred_actor_or_crew=("Cassandra/Clara", "Guardian if approval later", "Chief for completion check later"),
            known_fields={"client": "Capital Hilton", "requested_action": "prepare invoice draft"},
            unknown_fields=("exact performance dates", "proof/PO/reference coverage", "send approval readiness"),
            ambiguity_flags=("this week's and last week's job requires deterministic date resolution",),
            confidence="MEDIUM",
            needs_operator_clarification=True,
            needs_agent_compiler=True,
            needs_guardian_review=False,
            next_safe_move="Propose Finance World blocks and ask only missing questions.",
        ),
        WorkflowIntentNormalization(
            normalization_id="mission_control_capital_hilton_draft_normalization",
            entry_event_ref="mission_control_capital_hilton_performance_dates_entry",
            normalized_intent_title="Capital Hilton performance dates draft edit",
            normalized_intent_type="EXISTING_WORKFLOW_REQUEST",
            target_world_candidate="Finance",
            target_lane_candidate="Capital Hilton",
            target_workflow_type_candidate="INVOICE_WORKFLOW",
            inferred_actor_or_crew=("Cassandra/Clara for proof review later",),
            known_fields={"block_id": "performance_dates", "surface": "Mission Control"},
            unknown_fields=("whether operator will capture the draft", "proof refs for all dates"),
            ambiguity_flags=(),
            confidence="HIGH",
            needs_operator_clarification=False,
            needs_agent_compiler=False,
            needs_guardian_review=False,
            next_safe_move="Keep the edit in the same workflow/session/block chain shape.",
        ),
        WorkflowIntentNormalization(
            normalization_id="chief_check_engine_normalization",
            entry_event_ref="chief_check_engine_entry",
            normalized_intent_title="Check Engine build blocker request",
            normalized_intent_type="CHECK_ENGINE_REQUEST",
            target_world_candidate="Shipyard",
            target_lane_candidate="Build",
            target_workflow_type_candidate="SYSTEM_DIAGNOSTIC_WORKFLOW",
            inferred_actor_or_crew=("Chief",),
            known_fields={"question": "what is blocking the build"},
            unknown_fields=("current failing check refs", "whether captain decision is required"),
            ambiguity_flags=(),
            confidence="HIGH",
            needs_operator_clarification=False,
            needs_agent_compiler=True,
            needs_guardian_review=False,
            next_safe_move="Propose diagnostic blocks and keep proof/test detail below deck.",
        ),
        WorkflowIntentNormalization(
            normalization_id="new_client_recap_workflow_normalization",
            entry_event_ref="new_client_recap_workflow_entry",
            normalized_intent_title="Monthly client recap workflow proposal",
            normalized_intent_type="NEW_WORKFLOW_REQUEST",
            target_world_candidate="Client Delivery",
            target_lane_candidate="Client Recap",
            target_workflow_type_candidate="NEW_WORKFLOW_CANDIDATE",
            inferred_actor_or_crew=("Cassandra/Clara", "Hermes if workflow architecture review needed"),
            known_fields={"cadence": "monthly", "goal": "client recap"},
            unknown_fields=("client identity", "source materials", "recap format", "review route"),
            ambiguity_flags=("client may need deterministic match",),
            confidence="MEDIUM",
            needs_operator_clarification=True,
            needs_agent_compiler=True,
            needs_guardian_review=False,
            next_safe_move="Ask whether to review/fill proposed blocks together.",
        ),
        WorkflowIntentNormalization(
            normalization_id="source_card_build_cue_normalization",
            entry_event_ref="source_card_build_cue_discovery_entry",
            normalized_intent_title="Work Terrain build cue candidate",
            normalized_intent_type="WORLD_WORK_REQUEST",
            target_world_candidate="Operations / Build",
            target_lane_candidate="Work Terrain / Build Cue",
            target_workflow_type_candidate="RECONCILIATION_CANDIDATE",
            inferred_actor_or_crew=("Hermes", "Chief if build readiness check needed"),
            known_fields={"source_kind": "source card or terrain record"},
            unknown_fields=("readiness", "risk", "owner decision"),
            ambiguity_flags=("source card metadata may not be enough to build",),
            confidence="LOW_TO_MEDIUM",
            needs_operator_clarification=False,
            needs_agent_compiler=False,
            needs_guardian_review=False,
            next_safe_move="Route as build-cue queue candidate unless operator decision is required.",
        ),
    )


def default_chain_proposals() -> tuple[WorkflowBlockChainProposal, ...]:
    return (
        WorkflowBlockChainProposal(
            proposal_id="telegram_cassandra_capital_hilton_invoice_chain_proposal",
            source_entry_event_ref="telegram_cassandra_capital_hilton_invoice_entry",
            normalized_intent_ref="telegram_cassandra_capital_hilton_invoice_normalization",
            proposed_workflow_session_ref="capital_hilton_invoice_workflow_session",
            proposed_world="Finance",
            proposed_lane="Capital Hilton",
            proposed_workflow_type="INVOICE_WORKFLOW",
            proposed_blocks=("client_lane", "performance_dates", "rate", "po_proof", "invoice_packet", "approval_send"),
            locked_blocks=("client_lane", "approval_send"),
            current_or_unlocked_blocks=("performance_dates", "rate", "po_proof"),
            hidden_blocks=("client_lane",),
            below_deck_blocks=("proof_refs", "source_refs", "receipt_refs"),
            future_gated_blocks=("invoice_packet", "approval_send"),
            operator_needed_blocks=("performance_dates", "po_proof_if_unknown"),
            system_fillable_blocks=("client_lane", "rate_if_receipt_ref_exists"),
            agent_fillable_blocks=("invoice_request_interpretation", "proof_discovery_question"),
            recommended_crew=("Cassandra/Clara", "Guardian later", "Chief later"),
            proof_requirements=("performance date proof", "rate proof", "PO/reference coverage"),
            approval_requirements=("invoice review", "send approval"),
            downstream_artifact_candidates=("invoice packet", "email attachment"),
            confidence="MEDIUM",
            operator_review_recommended=True,
            operator_review_required=True,
            ready_to_activate_as_draft=True,
            authority_boundary=_authority_boundary(),
            next_safe_move="Route to Finance World and show only the next answerable block.",
        ),
        WorkflowBlockChainProposal(
            proposal_id="mission_control_capital_hilton_draft_chain_proposal",
            source_entry_event_ref="mission_control_capital_hilton_performance_dates_entry",
            normalized_intent_ref="mission_control_capital_hilton_draft_normalization",
            proposed_workflow_session_ref="capital_hilton_invoice_workflow_session",
            proposed_world="Finance",
            proposed_lane="Capital Hilton",
            proposed_workflow_type="INVOICE_WORKFLOW",
            proposed_blocks=("performance_dates", "rate", "po_proof", "invoice_packet", "approval_send"),
            locked_blocks=("approval_send",),
            current_or_unlocked_blocks=("performance_dates", "rate", "po_proof"),
            hidden_blocks=("stable_client_identity",),
            below_deck_blocks=("proof_refs", "receipt_refs"),
            future_gated_blocks=("invoice_packet", "approval_send"),
            operator_needed_blocks=("performance_dates_capture_choice",),
            system_fillable_blocks=("existing_current_dates",),
            agent_fillable_blocks=("proof_review_later",),
            recommended_crew=("Cassandra/Clara later",),
            proof_requirements=("external proof remains needed after operator confirmation",),
            approval_requirements=("send approval remains locked"),
            downstream_artifact_candidates=("invoice packet later",),
            confidence="HIGH",
            operator_review_recommended=True,
            operator_review_required=True,
            ready_to_activate_as_draft=True,
            authority_boundary=_authority_boundary(),
            next_safe_move="Keep the draft in Finance World with no Mac-only ownership.",
        ),
        WorkflowBlockChainProposal(
            proposal_id="chief_check_engine_chain_proposal",
            source_entry_event_ref="chief_check_engine_entry",
            normalized_intent_ref="chief_check_engine_normalization",
            proposed_workflow_session_ref="check_engine_diagnostic_session",
            proposed_world="Shipyard",
            proposed_lane="Build",
            proposed_workflow_type="SYSTEM_DIAGNOSTIC_WORKFLOW",
            proposed_blocks=("diagnostic_question", "current_status_refs", "blocker_summary", "captain_decision_if_needed"),
            locked_blocks=("repair_execution",),
            current_or_unlocked_blocks=("diagnostic_question", "current_status_refs"),
            hidden_blocks=("raw_debug_logs",),
            below_deck_blocks=("test_refs", "sync_refs", "debug_refs"),
            future_gated_blocks=("repair_execution",),
            operator_needed_blocks=("captain_decision_if_needed",),
            system_fillable_blocks=("current_status_refs",),
            agent_fillable_blocks=("blocker_summary",),
            recommended_crew=("Chief",),
            proof_requirements=("focused test/read-model refs",),
            approval_requirements=("operator review before repair path"),
            downstream_artifact_candidates=(),
            confidence="HIGH",
            operator_review_recommended=True,
            operator_review_required=False,
            ready_to_activate_as_draft=True,
            authority_boundary=_authority_boundary(),
            next_safe_move="Route to Shipyard unless an active mission is blocked.",
        ),
        WorkflowBlockChainProposal(
            proposal_id="new_client_recap_workflow_chain_proposal",
            source_entry_event_ref="new_client_recap_workflow_entry",
            normalized_intent_ref="new_client_recap_workflow_normalization",
            proposed_workflow_session_ref="monthly_client_recap_workflow_session_candidate",
            proposed_world="Client Delivery",
            proposed_lane="Client Recap",
            proposed_workflow_type="NEW_WORKFLOW_CANDIDATE",
            proposed_blocks=("client", "cadence", "source_materials", "recap_format", "review_route", "activation_gate"),
            locked_blocks=("activation_gate",),
            current_or_unlocked_blocks=("client", "cadence", "source_materials", "recap_format", "review_route"),
            hidden_blocks=(),
            below_deck_blocks=("terrain_refs",),
            future_gated_blocks=("activation_gate",),
            operator_needed_blocks=("client", "source_materials", "recap_format", "review_route"),
            system_fillable_blocks=("cadence", "workflow_goal"),
            agent_fillable_blocks=("proposed_block_chain",),
            recommended_crew=("Cassandra/Clara", "Hermes if needed"),
            proof_requirements=("source refs if workflow becomes durable",),
            approval_requirements=("operator approval before activation"),
            downstream_artifact_candidates=("client recap draft later",),
            confidence="MEDIUM",
            operator_review_recommended=True,
            operator_review_required=True,
            ready_to_activate_as_draft=True,
            authority_boundary=_authority_boundary(),
            next_safe_move="Ask whether to review and fill the proposed workflow together.",
        ),
        WorkflowBlockChainProposal(
            proposal_id="source_card_build_cue_chain_proposal",
            source_entry_event_ref="source_card_build_cue_discovery_entry",
            normalized_intent_ref="source_card_build_cue_normalization",
            proposed_workflow_session_ref="work_terrain_build_cue_candidate_session",
            proposed_world="Operations / Build",
            proposed_lane="Work Terrain / Build Cue",
            proposed_workflow_type="RECONCILIATION_CANDIDATE",
            proposed_blocks=("source_card_summary", "readiness", "risk", "operator_decision_if_needed", "build_gate"),
            locked_blocks=("build_gate",),
            current_or_unlocked_blocks=("source_card_summary", "readiness", "risk"),
            hidden_blocks=("raw_source_body",),
            below_deck_blocks=("source_refs", "terrain_refs", "proof_refs"),
            future_gated_blocks=("build_gate",),
            operator_needed_blocks=("operator_decision_if_needed",),
            system_fillable_blocks=("source_card_summary", "terrain_refs"),
            agent_fillable_blocks=("hermes_review_candidate", "chief_check_candidate"),
            recommended_crew=("Hermes", "Chief if needed"),
            proof_requirements=("source card metadata", "terrain relationship refs"),
            approval_requirements=("operator approval before any build"),
            downstream_artifact_candidates=(),
            confidence="LOW_TO_MEDIUM",
            operator_review_recommended=True,
            operator_review_required=False,
            ready_to_activate_as_draft=False,
            authority_boundary=_authority_boundary(),
            next_safe_move="Queue as build cue or keep below deck unless a decision is needed.",
        ),
    )


def _block(
    *,
    block_proposal_id: str,
    proposal_ref: str,
    block_id: str,
    block_label: str,
    block_type: str,
    block_state: str,
    visible_by_default: bool,
    editable_by_operator: bool,
    system_fillable: bool,
    agent_fillable: bool,
    proof_required: bool,
    discovery_required: bool,
    guided_capture_candidate: bool,
    automation_candidate: bool,
    downstream_effects: tuple[str, ...],
    source_refs: tuple[str, ...] = (),
    help_assist_refs: tuple[str, ...] = (),
    required_actor_or_crew: tuple[str, ...] = (),
    next_safe_move: str,
) -> WorkflowBlockProposal:
    return WorkflowBlockProposal(
        block_proposal_id=block_proposal_id,
        proposal_ref=proposal_ref,
        block_id=block_id,
        block_label=block_label,
        block_type=block_type,
        block_state=block_state,
        visible_by_default=visible_by_default,
        editable_by_operator=editable_by_operator,
        system_fillable=system_fillable,
        agent_fillable=agent_fillable,
        proof_required=proof_required,
        discovery_required=discovery_required,
        guided_capture_candidate=guided_capture_candidate,
        automation_candidate=automation_candidate,
        downstream_effects=downstream_effects,
        source_refs=source_refs,
        help_assist_refs=help_assist_refs,
        required_actor_or_crew=required_actor_or_crew,
        authority_boundary=_authority_boundary(),
        next_safe_move=next_safe_move,
    )


def default_block_proposals() -> tuple[WorkflowBlockProposal, ...]:
    return (
        _block(
            block_proposal_id="capital_hilton_client_lane_block",
            proposal_ref="telegram_cassandra_capital_hilton_invoice_chain_proposal",
            block_id="client_lane",
            block_label="Client / lane",
            block_type="DATA_FIELD",
            block_state="SYSTEM_FILLED",
            visible_by_default=False,
            editable_by_operator=False,
            system_fillable=True,
            agent_fillable=False,
            proof_required=False,
            discovery_required=False,
            guided_capture_candidate=False,
            automation_candidate=False,
            downstream_effects=("anchors Finance World routing",),
            source_refs=("capital_hilton_invoice_workflow_session",),
            next_safe_move="Keep stable client identity hidden unless questioned.",
        ),
        _block(
            block_proposal_id="capital_hilton_performance_dates_block",
            proposal_ref="telegram_cassandra_capital_hilton_invoice_chain_proposal",
            block_id="performance_dates",
            block_label="Performance dates",
            block_type="DATA_FIELD",
            block_state="NEEDS_OPERATOR",
            visible_by_default=True,
            editable_by_operator=True,
            system_fillable=False,
            agent_fillable=True,
            proof_required=True,
            discovery_required=False,
            guided_capture_candidate=True,
            automation_candidate=False,
            downstream_effects=("invoice packet dates", "subtotal preview", "proof coverage"),
            source_refs=("capital_hilton_performance_dates_capture_boundary",),
            help_assist_refs=("operator_question_assist_scope_expansion_contract.rate_confirmation_help",),
            required_actor_or_crew=("Winship", "Cassandra/Clara if proof help needed"),
            next_safe_move="Ask what dates are true or show the capture-ready draft.",
        ),
        _block(
            block_proposal_id="capital_hilton_rate_block",
            proposal_ref="telegram_cassandra_capital_hilton_invoice_chain_proposal",
            block_id="rate",
            block_label="Rate",
            block_type="DATA_FIELD",
            block_state="CURRENT_UNLOCKED",
            visible_by_default=True,
            editable_by_operator=True,
            system_fillable=True,
            agent_fillable=True,
            proof_required=True,
            discovery_required=False,
            guided_capture_candidate=False,
            automation_candidate=False,
            downstream_effects=("subtotal calculation",),
            source_refs=("capital_hilton_proof_resolution_batch",),
            help_assist_refs=("operator_question_assist_scope_expansion_contract.rate_confirmation_help",),
            required_actor_or_crew=("Winship",),
            next_safe_move="Confirm or point to rate proof.",
        ),
        _block(
            block_proposal_id="capital_hilton_po_proof_block",
            proposal_ref="telegram_cassandra_capital_hilton_invoice_chain_proposal",
            block_id="po_proof",
            block_label="PO / proof",
            block_type="PROOF_REQUIREMENT",
            block_state="NEEDS_DISCOVERY",
            visible_by_default=True,
            editable_by_operator=True,
            system_fillable=False,
            agent_fillable=True,
            proof_required=True,
            discovery_required=True,
            guided_capture_candidate=True,
            automation_candidate=True,
            downstream_effects=("send readiness", "payment routing confidence"),
            source_refs=("capital_hilton_coupa_po_retrieval_automation_candidate",),
            help_assist_refs=("operator_question_assist_scope_expansion_contract.capital_hilton_po_coupa_help",),
            required_actor_or_crew=("Cassandra/Clara", "Guardian later if protected proof"),
            next_safe_move="Offer discovery/capture choices without Coupa access.",
        ),
        _block(
            block_proposal_id="capital_hilton_invoice_packet_block",
            proposal_ref="telegram_cassandra_capital_hilton_invoice_chain_proposal",
            block_id="invoice_packet",
            block_label="Invoice packet",
            block_type="DRAFT_ARTIFACT",
            block_state="FUTURE_GATED",
            visible_by_default=False,
            editable_by_operator=False,
            system_fillable=False,
            agent_fillable=False,
            proof_required=True,
            discovery_required=False,
            guided_capture_candidate=False,
            automation_candidate=False,
            downstream_effects=("future invoice artifact preview",),
            required_actor_or_crew=(),
            next_safe_move="Keep hidden/locked until receipt-backed inputs exist.",
        ),
        _block(
            block_proposal_id="capital_hilton_approval_send_block",
            proposal_ref="telegram_cassandra_capital_hilton_invoice_chain_proposal",
            block_id="approval_send",
            block_label="Approval / send",
            block_type="EXECUTION_GATE",
            block_state="FUTURE_GATED",
            visible_by_default=False,
            editable_by_operator=False,
            system_fillable=False,
            agent_fillable=False,
            proof_required=True,
            discovery_required=False,
            guided_capture_candidate=False,
            automation_candidate=False,
            downstream_effects=("future send gate",),
            required_actor_or_crew=("Guardian later",),
            next_safe_move="Keep locked; no send authority exists.",
        ),
        _block(
            block_proposal_id="mission_control_performance_dates_block",
            proposal_ref="mission_control_capital_hilton_draft_chain_proposal",
            block_id="performance_dates",
            block_label="Performance dates draft",
            block_type="DATA_FIELD",
            block_state="CURRENT_UNLOCKED",
            visible_by_default=True,
            editable_by_operator=True,
            system_fillable=False,
            agent_fillable=True,
            proof_required=True,
            discovery_required=False,
            guided_capture_candidate=True,
            automation_candidate=False,
            downstream_effects=("dry-run receipt writer readiness",),
            source_refs=("capital_hilton_performance_dates_dry_run_writer",),
            required_actor_or_crew=("Winship",),
            next_safe_move="Render the same block shape as Telegram would.",
        ),
        _block(
            block_proposal_id="chief_current_status_refs_block",
            proposal_ref="chief_check_engine_chain_proposal",
            block_id="current_status_refs",
            block_label="Current status refs",
            block_type="STATUS_OR_DIAGNOSTIC",
            block_state="SYSTEM_FILLED",
            visible_by_default=True,
            editable_by_operator=False,
            system_fillable=True,
            agent_fillable=True,
            proof_required=True,
            discovery_required=False,
            guided_capture_candidate=False,
            automation_candidate=False,
            downstream_effects=("blocker briefing",),
            source_refs=("focused tests/read-model refs",),
            required_actor_or_crew=("Chief",),
            next_safe_move="Give Chief current refs only; do not repair.",
        ),
        _block(
            block_proposal_id="client_recap_source_materials_block",
            proposal_ref="new_client_recap_workflow_chain_proposal",
            block_id="source_materials",
            block_label="Source materials",
            block_type="DISCOVERY_PATH",
            block_state="NEEDS_OPERATOR",
            visible_by_default=True,
            editable_by_operator=True,
            system_fillable=False,
            agent_fillable=True,
            proof_required=False,
            discovery_required=True,
            guided_capture_candidate=True,
            automation_candidate=False,
            downstream_effects=("future recap draft scope",),
            required_actor_or_crew=("Winship", "Cassandra/Clara"),
            next_safe_move="Ask what sources should feed the recap.",
        ),
        _block(
            block_proposal_id="source_card_build_cue_readiness_block",
            proposal_ref="source_card_build_cue_chain_proposal",
            block_id="readiness",
            block_label="Build cue readiness",
            block_type="AUTOMATION_READINESS",
            block_state="BELOW_DECK_ONLY",
            visible_by_default=False,
            editable_by_operator=False,
            system_fillable=True,
            agent_fillable=True,
            proof_required=True,
            discovery_required=False,
            guided_capture_candidate=False,
            automation_candidate=True,
            downstream_effects=("build cue queue priority",),
            source_refs=("work_terrain_build_cue_reconciliation_queue",),
            required_actor_or_crew=("Hermes", "Chief if needed"),
            next_safe_move="Keep below deck unless operator decision is needed.",
        ),
    )


def default_routing_decisions() -> tuple[WorkflowProposalRoutingDecision, ...]:
    return (
        WorkflowProposalRoutingDecision(
            routing_decision_id="telegram_cassandra_capital_hilton_invoice_route",
            proposal_ref="telegram_cassandra_capital_hilton_invoice_chain_proposal",
            route_destination="WORLD_WORK_SURFACE",
            helm_marker="Finance needs attention: Capital Hilton invoice draft has answerable blocks.",
            world_destination="Finance World / Capital Hilton",
            shipyard_destination=None,
            below_deck_destination="Finance proof/source detail",
            crew_briefing_refs=("cassandra_capital_hilton_invoice_briefing_candidate",),
            alert_level="YELLOW_ALERT",
            captain_attention_required=True,
            should_show_on_helm=True,
            should_open_world=True,
            should_route_to_shipyard=False,
            should_stay_below_deck=False,
            routing_reason="Capital Hilton invoice work belongs in Finance World; Helm should show a marker only.",
            next_safe_move="Open Finance World if Winship chooses the marker.",
        ),
        WorkflowProposalRoutingDecision(
            routing_decision_id="mission_control_capital_hilton_draft_route",
            proposal_ref="mission_control_capital_hilton_draft_chain_proposal",
            route_destination="WORLD_WORK_SURFACE",
            helm_marker="Capital Hilton draft updated in Finance World.",
            world_destination="Finance World / Capital Hilton",
            shipyard_destination=None,
            below_deck_destination="Finance proof/source detail",
            crew_briefing_refs=(),
            alert_level="NORMAL_FLIGHT",
            captain_attention_required=False,
            should_show_on_helm=False,
            should_open_world=True,
            should_route_to_shipyard=False,
            should_stay_below_deck=False,
            routing_reason="Mission Control entry uses the same workflow session shape, not app-owned state.",
            next_safe_move="Keep the operator inside the Finance World block draft.",
        ),
        WorkflowProposalRoutingDecision(
            routing_decision_id="chief_check_engine_route",
            proposal_ref="chief_check_engine_chain_proposal",
            route_destination="SHIPYARD_WORK_SURFACE",
            helm_marker="Check Engine has a Shipyard diagnostic route.",
            world_destination=None,
            shipyard_destination="Shipyard / Build",
            below_deck_destination="Engineering proof/test refs",
            crew_briefing_refs=("chief_blocker_briefing_candidate",),
            alert_level="SHIPYARD_MODE",
            captain_attention_required=False,
            should_show_on_helm=False,
            should_open_world=False,
            should_route_to_shipyard=True,
            should_stay_below_deck=False,
            routing_reason="Build/repair noise belongs in Shipyard unless it blocks an active mission.",
            next_safe_move="Route to Shipyard diagnostic surface without repair execution.",
        ),
        WorkflowProposalRoutingDecision(
            routing_decision_id="new_client_recap_workflow_route",
            proposal_ref="new_client_recap_workflow_chain_proposal",
            route_destination="WORLD_WORK_SURFACE",
            helm_marker="Client Delivery has a new workflow proposal.",
            world_destination="Client Delivery World",
            shipyard_destination=None,
            below_deck_destination="Terrain/source refs",
            crew_briefing_refs=("cassandra_client_recap_briefing_candidate",),
            alert_level="YELLOW_ALERT",
            captain_attention_required=True,
            should_show_on_helm=True,
            should_open_world=True,
            should_route_to_shipyard=False,
            should_stay_below_deck=False,
            routing_reason="New client workflow needs captain review before any activation.",
            next_safe_move="Ask whether to review/fill the proposed blocks together.",
        ),
        WorkflowProposalRoutingDecision(
            routing_decision_id="source_card_build_cue_route",
            proposal_ref="source_card_build_cue_chain_proposal",
            route_destination="BELOW_DECK_DETAIL",
            helm_marker="Build cue candidate parked below deck unless a decision is needed.",
            world_destination="Operations / Build",
            shipyard_destination="Shipyard if build readiness escalates",
            below_deck_destination="Work Terrain / Build Cue queue",
            crew_briefing_refs=("hermes_build_cue_briefing_candidate",),
            alert_level="ENGINEERING_CONTAINED",
            captain_attention_required=False,
            should_show_on_helm=False,
            should_open_world=False,
            should_route_to_shipyard=False,
            should_stay_below_deck=True,
            routing_reason="Source-card discovery is not a captain interruption unless it needs a decision.",
            next_safe_move="Keep in Build Cue queue without auto-build.",
        ),
    )


def default_surface_compatibilities() -> tuple[WorkflowSurfaceCompatibility, ...]:
    return tuple(
        WorkflowSurfaceCompatibility(
            compatibility_id=f"{proposal.proposal_id}_surface_compatibility",
            proposal_ref=proposal.proposal_id,
            compatible_surfaces=COMPATIBLE_SURFACES,
            compatible_agents=COMPATIBLE_AGENTS,
            surfaces_allowed_to_originate=("Mission Control", "Telegram", "agent conversation", "source-card discovery"),
            surfaces_allowed_to_render=("Mission Control", "Telegram", "World surfaces", "Bridge markers"),
            surfaces_allowed_to_review=("Mission Control", "Telegram handoff", "World surfaces"),
            surfaces_allowed_to_capture_future=("Mission Control future capture boundary", "governed Telegram handoff future"),
            channels_allowed_for_handoff=("Mission Control", "Telegram", "Crew briefing"),
            split_brain_prevention_policy="All surfaces must attach to the same proposed/canonical workflow_session_ref before durable state.",
            canonical_session_required=True,
            local_state_allowed="draft_preview_only_until_captured",
            next_safe_move="Render or hand off the same proposal shape; do not create channel-owned state.",
        )
        for proposal in default_chain_proposals()
    )


def default_crew_deployments() -> tuple[WorkflowCrewDeploymentProposal, ...]:
    return (
        WorkflowCrewDeploymentProposal(
            deployment_id="telegram_cassandra_capital_hilton_invoice_crew_deployment",
            proposal_ref="telegram_cassandra_capital_hilton_invoice_chain_proposal",
            recommended_crew=("Cassandra/Clara", "Guardian later", "Chief later"),
            crew_roles={
                "Cassandra/Clara": "finance/comms draft and proof question support",
                "Guardian": "future protected proof or send approval gate",
                "Chief": "future completion/reconciliation check",
            },
            crew_packet_candidates=("capital_hilton_invoice_block_fill_packet", "po_proof_discovery_packet"),
            operator_handoff_candidates=("confirm_performance_dates", "choose_po_discovery_path"),
            guardian_gate_candidates=("send_approval_gate_future",),
            chief_check_candidates=("completion_cross_check_future",),
            hermes_review_candidates=(),
            niles_project_candidates=(),
            cassandra_clara_candidates=("invoice_request_interpretation", "draft_review_future"),
            crew_not_needed_reason=None,
            next_safe_move="Prepare packet candidates only after operator chooses a block needing help.",
        ),
        WorkflowCrewDeploymentProposal(
            deployment_id="mission_control_capital_hilton_draft_crew_deployment",
            proposal_ref="mission_control_capital_hilton_draft_chain_proposal",
            recommended_crew=("Cassandra/Clara later",),
            crew_roles={"Cassandra/Clara": "optional proof/draft review support"},
            crew_packet_candidates=("performance_dates_proof_review_packet_future",),
            operator_handoff_candidates=("use_this_draft_capture_preview",),
            guardian_gate_candidates=(),
            chief_check_candidates=(),
            hermes_review_candidates=(),
            niles_project_candidates=(),
            cassandra_clara_candidates=("optional_proof_review",),
            crew_not_needed_reason=None,
            next_safe_move="No crew activation; keep optional support as packet candidate.",
        ),
        WorkflowCrewDeploymentProposal(
            deployment_id="chief_check_engine_crew_deployment",
            proposal_ref="chief_check_engine_chain_proposal",
            recommended_crew=("Chief",),
            crew_roles={"Chief": "diagnostic blocker briefing from focused refs"},
            crew_packet_candidates=("chief_diagnostic_packet_candidate",),
            operator_handoff_candidates=("captain_repair_decision_if_needed",),
            guardian_gate_candidates=(),
            chief_check_candidates=("current_build_blocker_check",),
            hermes_review_candidates=(),
            niles_project_candidates=(),
            cassandra_clara_candidates=(),
            crew_not_needed_reason=None,
            next_safe_move="Chief packet candidate only; no repair execution.",
        ),
        WorkflowCrewDeploymentProposal(
            deployment_id="new_client_recap_crew_deployment",
            proposal_ref="new_client_recap_workflow_chain_proposal",
            recommended_crew=("Cassandra/Clara", "Hermes if needed"),
            crew_roles={
                "Cassandra/Clara": "conversation and draft workflow support",
                "Hermes": "workflow architecture/advisory review if needed",
            },
            crew_packet_candidates=("client_recap_block_chain_packet_candidate",),
            operator_handoff_candidates=("review_new_workflow_blocks",),
            guardian_gate_candidates=(),
            chief_check_candidates=(),
            hermes_review_candidates=("recap_workflow_architecture_review",),
            niles_project_candidates=(),
            cassandra_clara_candidates=("recap_request_clarifier",),
            crew_not_needed_reason=None,
            next_safe_move="Ask whether Winship wants crew help filling the blocks.",
        ),
        WorkflowCrewDeploymentProposal(
            deployment_id="source_card_build_cue_crew_deployment",
            proposal_ref="source_card_build_cue_chain_proposal",
            recommended_crew=("Hermes", "Chief if needed"),
            crew_roles={
                "Hermes": "architecture/reconciliation review",
                "Chief": "build readiness/check-engine validation if escalated",
            },
            crew_packet_candidates=("build_cue_reconciliation_packet_candidate",),
            operator_handoff_candidates=("build_cue_decision_if_ready",),
            guardian_gate_candidates=(),
            chief_check_candidates=("build_readiness_check_if_needed",),
            hermes_review_candidates=("terrain_reconciliation_review",),
            niles_project_candidates=(),
            cassandra_clara_candidates=(),
            crew_not_needed_reason=None,
            next_safe_move="Keep as proposal; do not auto-build or activate crew.",
        ),
    )


def build_entry_agnostic_workflow_block_chain_routing_contract(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    entry_events = default_entry_events()
    normalizations = default_intent_normalizations()
    proposals = default_chain_proposals()
    block_proposals = default_block_proposals()
    routing_decisions = default_routing_decisions()
    compatibilities = default_surface_compatibilities()
    crew_deployments = default_crew_deployments()

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": "entry_agnostic_workflow_block_chain_routing_contract_v0",
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "operator_summary": (
            "Any entry point can become a workflow proposal, but entry point is "
            "metadata, not ownership. Surfaces and agents normalize into one "
            "proposal/session/block-chain shape, then route to Bridge, World, "
            "Shipyard, or Below Deck without activation."
        ),
        "doctrine": {
            "entry_point_is_metadata_not_ownership": True,
            "surfaces_do_not_own_canonical_state": True,
            "agents_do_not_own_canonical_state": True,
            "all_origins_normalize_to_same_shape": True,
            "high_level_flow": (
                "entry event -> intent normalization -> workflow/session candidate -> "
                "block-chain proposal -> routing decision -> visible surface -> "
                "agent packets/operator handoffs -> capture/receipt/gated execution later"
            ),
        },
        "origin_surfaces": list(ORIGIN_SURFACES),
        "intent_types": list(INTENT_TYPES),
        "block_types": list(BLOCK_TYPES),
        "block_states": list(BLOCK_STATES),
        "route_destinations": list(ROUTE_DESTINATIONS),
        "entry_event_schema": {
            "model_name": "EntryAgnosticWorkflowEntryEvent",
            "required_fields": list(REQUIRED_ENTRY_EVENT_FIELDS),
            "entry_event_owns_workflow_state": False,
            "entry_event_can_start_proposal": True,
            "entry_event_executes_action": False,
        },
        "intent_normalization_schema": {
            "model_name": "WorkflowIntentNormalization",
            "required_fields": list(REQUIRED_INTENT_NORMALIZATION_FIELDS),
            "many_entry_styles_one_candidate_shape": True,
            "low_confidence_creates_clarification_not_execution": True,
            "unknown_intents_fail_closed": True,
        },
        "block_chain_proposal_schema": {
            "model_name": "WorkflowBlockChainProposal",
            "required_fields": list(REQUIRED_CHAIN_PROPOSAL_FIELDS),
            "proposal_is_canonical_state": False,
            "system_fillable_requires_deterministic_evidence": True,
            "agent_fillable_requires_packet_handoff_contracts": True,
            "activation_capture_future_gated": True,
        },
        "block_proposal_schema": {
            "model_name": "WorkflowBlockProposal",
            "required_fields": list(REQUIRED_BLOCK_PROPOSAL_FIELDS),
            "visible_blocks_are_work_relevant": True,
            "hidden_blocks_are_durable_system_filled_or_below_deck": True,
            "visible_block_should_not_be_inert": True,
            "maps_to_live_draft_semantics_later": True,
        },
        "routing_decision_schema": {
            "model_name": "WorkflowProposalRoutingDecision",
            "required_fields": list(REQUIRED_ROUTING_DECISION_FIELDS),
            "helm_routes_worlds_do_work": True,
            "helm_is_not_workflow_editor": True,
            "proof_debug_source_stay_below_deck_by_default": True,
        },
        "surface_compatibility_schema": {
            "model_name": "WorkflowSurfaceCompatibility",
            "required_fields": list(REQUIRED_SURFACE_COMPATIBILITY_FIELDS),
            "mission_control_and_telegram_are_surfaces_not_owners": True,
            "canonical_session_required_before_durable_state": True,
            "local_state_draft_preview_only_until_captured": True,
            "split_brain_prevention_required": True,
        },
        "crew_deployment_schema": {
            "model_name": "WorkflowCrewDeploymentProposal",
            "required_fields": list(REQUIRED_CREW_DEPLOYMENT_FIELDS),
            "crew_deployment_is_proposal_only": True,
            "agents_receive_packets_only_when_needed": True,
            "crew_activation_allowed_now": False,
        },
        "entry_events": [asdict(item) for item in entry_events],
        "entry_events_by_id": {item.entry_event_id: asdict(item) for item in entry_events},
        "intent_normalizations": [asdict(item) for item in normalizations],
        "intent_normalizations_by_id": {
            item.normalization_id: asdict(item) for item in normalizations
        },
        "block_chain_proposals": [asdict(item) for item in proposals],
        "block_chain_proposals_by_id": {
            item.proposal_id: asdict(item) for item in proposals
        },
        "block_proposals": [asdict(item) for item in block_proposals],
        "block_proposals_by_id": {
            item.block_proposal_id: asdict(item) for item in block_proposals
        },
        "routing_decisions": [asdict(item) for item in routing_decisions],
        "routing_decisions_by_id": {
            item.routing_decision_id: asdict(item) for item in routing_decisions
        },
        "surface_compatibilities": [asdict(item) for item in compatibilities],
        "surface_compatibilities_by_id": {
            item.compatibility_id: asdict(item) for item in compatibilities
        },
        "crew_deployment_proposals": [asdict(item) for item in crew_deployments],
        "crew_deployment_proposals_by_id": {
            item.deployment_id: asdict(item) for item in crew_deployments
        },
        "examples": {
            "telegram_cassandra_invoice": {
                "entry_event_ref": "telegram_cassandra_capital_hilton_invoice_entry",
                "normalization_ref": "telegram_cassandra_capital_hilton_invoice_normalization",
                "proposal_ref": "telegram_cassandra_capital_hilton_invoice_chain_proposal",
                "routing_ref": "telegram_cassandra_capital_hilton_invoice_route",
                "expected_intent_type": "FINANCE_INVOICE_REQUEST",
                "expected_world": "Finance",
                "send_authority": False,
            },
            "mission_control_draft": {
                "entry_event_ref": "mission_control_capital_hilton_performance_dates_entry",
                "proposal_ref": "mission_control_capital_hilton_draft_chain_proposal",
                "same_workflow_session_shape": True,
                "mac_only_ownership": False,
            },
            "chief_check_engine": {
                "entry_event_ref": "chief_check_engine_entry",
                "proposal_ref": "chief_check_engine_chain_proposal",
                "routes_to_shipyard": True,
                "repair_execution": False,
            },
            "new_client_recap_workflow": {
                "entry_event_ref": "new_client_recap_workflow_entry",
                "proposal_ref": "new_client_recap_workflow_chain_proposal",
                "asks_operator_to_review_fill_together": True,
                "activation_execution": False,
            },
            "file_source_card_discovery": {
                "entry_event_ref": "source_card_build_cue_discovery_entry",
                "proposal_ref": "source_card_build_cue_chain_proposal",
                "routes_to_work_terrain_build_cue": True,
                "auto_build": False,
            },
        },
        "relationship_to_existing_contracts": {
            "workflow_block_intent_live_draft_contract": {
                "source_ref": "generated/read_models/workflow_block_intent_live_draft_contract.json",
                "relationship": "block-chain proposals map into live draft/block intent semantics later",
            },
            "bridge_routing_operator_attention_contract": {
                "source_ref": "generated/read_models/bridge_routing_operator_attention_contract.json",
                "relationship": "routing decisions choose Helm, World, Shipyard, Below Deck, or crew briefing visibility",
            },
            "agent_conversation_handoff_step_packet_contract": {
                "source_ref": "generated/read_models/agent_conversation_handoff_step_packet_contract.json",
                "relationship": "conversation entries and operator handoffs attach to the same proposal shape",
            },
            "agent_execution_packet_compiler_contract": {
                "source_ref": "generated/read_models/agent_execution_packet_compiler_contract.json",
                "relationship": "crew packet candidates can become focused packets later without execution authority",
            },
            "operator_question_assist_scope_expansion_contract": {
                "source_ref": "generated/read_models/operator_question_assist_scope_expansion_contract.json",
                "relationship": "question assist can feed block choices, discovery paths, and scope expansion proposals",
            },
            "workflow_session_channel_projection_approval_bus_contract": {
                "source_ref": "generated/read_models/workflow_session_channel_projection_approval_bus_contract.json",
                "relationship": "canonical workflow session prevents channel split-brain before durable state",
            },
            "work_terrain_surface_map_build_cue_scout": {
                "source_ref": "generated/read_models/work_terrain_surface_map_build_cue_scout.json",
                "relationship": "terrain/source-card entries can become build cue proposal candidates",
            },
            "work_terrain_build_cue_reconciliation_queue": {
                "source_ref": "generated/read_models/work_terrain_build_cue_reconciliation_queue.json",
                "relationship": "build cue proposals feed queue readiness without auto-build",
            },
        },
        "starship_operating_model_alignment": {
            "any_entry_can_become_mission_proposal": True,
            "helm_routes_but_does_not_own": True,
            "worlds_do_domain_work": True,
            "shipyard_handles_build_repair": True,
            "engineering_stays_below_deck": True,
            "crew_deployment_is_proposed_not_activated": True,
            "captain_sees_relevant_decisions_markers_only": True,
            "ship_remains_calm_by_routing_correctly": True,
        },
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_authority_flags_false": _all_authority_false(),
            "blocked_actions": list(BLOCKED_ACTIONS),
        },
        "machine_proof": {
            "entry_event_model_present": True,
            "intent_normalization_model_present": True,
            "block_chain_proposal_model_present": True,
            "block_proposal_model_present": True,
            "routing_decision_model_present": True,
            "surface_compatibility_model_present": True,
            "crew_deployment_proposal_model_present": True,
            "telegram_cassandra_invoice_example_present": True,
            "mission_control_draft_example_present": True,
            "chief_check_engine_example_present": True,
            "new_client_recap_workflow_example_present": True,
            "file_source_card_discovery_example_present": True,
            "entry_point_does_not_own_state": True,
            "mission_control_and_telegram_surfaces_not_owners": True,
            "helm_routes_worlds_do_work": True,
            "visible_and_hidden_blocks_represented": any(
                block.visible_by_default for block in block_proposals
            )
            and any(not block.visible_by_default for block in block_proposals),
            "split_brain_prevention_represented": all(
                compatibility.canonical_session_required for compatibility in compatibilities
            ),
            "all_authority_flags_false": _all_authority_false(),
            "credential_or_secret_included": False,
            "raw_private_body_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_entry_agnostic_workflow_block_chain_routing_contract(payload: dict[str, Any]) -> str:
    lines = [
        "# Entry-Agnostic Workflow Block Chain Routing Contract v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "Entry point is metadata, not ownership. Mission Control, Telegram, Cassandra, Chief, Guardian, and future surfaces all normalize into the same workflow proposal shape.",
        "",
        "A custom task request becomes a proposed workflow/session/block chain. Some blocks show because they help Winship do the work. Some blocks hide because they are durable, proof/detail, below deck, or future-gated.",
        "",
        "Helm routes. Worlds do work. Shipyard handles build and repair. Below Deck keeps proof, source, sync, and debug detail. No workflow is activated yet and no agent is launched yet.",
        "",
        "## Examples",
        "",
        "- Telegram/Cassandra Capital Hilton invoice request routes to Finance World.",
        "- Mission Control Capital Hilton draft edit uses the same workflow/session/block shape.",
        "- Chief Check Engine routes to Shipyard/Build unless it becomes mission-blocking.",
        "- New client recap request becomes a workflow block-chain proposal.",
        "- Source-card discovery can become a Work Terrain / Build Cue candidate without auto-build.",
        "",
        "## Why This Matters",
        "",
        "This prevents split-brain and app-only workflows. Telegram is not a separate workflow system. Mission Control is not a separate workflow owner. Agents brief and help, but canonical state belongs to future workflow/session/receipt rails.",
        "",
        "## Still Blocked",
        "",
    ]
    for action in payload["authority_boundary"]["blocked_actions"]:
        lines.append(f"- {action}")
    lines.extend(
        [
            "",
            "## Authority",
            "",
            f"- Workflow activation allowed: `{str(payload['authority_boundary']['workflow_activation_allowed']).lower()}`",
            f"- Session write allowed: `{str(payload['authority_boundary']['workflow_session_write_allowed']).lower()}`",
            f"- Crew activation allowed: `{str(payload['authority_boundary']['crew_activation_allowed']).lower()}`",
            f"- Agent activation allowed: `{str(payload['authority_boundary']['agent_activation_allowed']).lower()}`",
            f"- Receipt/state write allowed: `{str(payload['authority_boundary']['receipt_write_allowed'] or payload['authority_boundary']['state_write_allowed']).lower()}`",
        ]
    )
    return "\n".join(lines) + "\n"


def export_entry_agnostic_workflow_block_chain_routing_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> EntryRoutingExportResult:
    payload = build_entry_agnostic_workflow_block_chain_routing_contract(
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
        format_entry_agnostic_workflow_block_chain_routing_contract(payload),
        encoding="utf-8",
    )
    return EntryRoutingExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        entry_event_count=len(payload["entry_events"]),
        normalization_count=len(payload["intent_normalizations"]),
        proposal_count=len(payload["block_chain_proposals"]),
        block_proposal_count=len(payload["block_proposals"]),
        routing_decision_count=len(payload["routing_decisions"]),
        compatibility_count=len(payload["surface_compatibilities"]),
        crew_deployment_count=len(payload["crew_deployment_proposals"]),
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Entry-Agnostic Workflow Block Chain Routing Contract read-model."
    )
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_entry_agnostic_workflow_block_chain_routing_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "entry_event_count": result.entry_event_count,
        "normalization_count": result.normalization_count,
        "proposal_count": result.proposal_count,
        "block_proposal_count": result.block_proposal_count,
        "routing_decision_count": result.routing_decision_count,
        "compatibility_count": result.compatibility_count,
        "crew_deployment_count": result.crew_deployment_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Entry-Agnostic Workflow Block Chain Routing Contract: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "AUTHORITY_BOUNDARY",
    "BLOCKED_ACTIONS",
    "BLOCK_STATES",
    "BLOCK_TYPES",
    "CONTRACT_STATUS",
    "INTENT_TYPES",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "ORIGIN_SURFACES",
    "READ_MODEL_ID",
    "REQUIRED_BLOCK_PROPOSAL_FIELDS",
    "REQUIRED_CHAIN_PROPOSAL_FIELDS",
    "REQUIRED_CREW_DEPLOYMENT_FIELDS",
    "REQUIRED_ENTRY_EVENT_FIELDS",
    "REQUIRED_INTENT_NORMALIZATION_FIELDS",
    "REQUIRED_ROUTING_DECISION_FIELDS",
    "REQUIRED_SURFACE_COMPATIBILITY_FIELDS",
    "ROUTE_DESTINATIONS",
    "SCHEMA_VERSION",
    "EntryAgnosticWorkflowEntryEvent",
    "WorkflowBlockChainProposal",
    "WorkflowBlockProposal",
    "WorkflowCrewDeploymentProposal",
    "WorkflowIntentNormalization",
    "WorkflowProposalRoutingDecision",
    "WorkflowSurfaceCompatibility",
    "build_entry_agnostic_workflow_block_chain_routing_contract",
    "default_block_proposals",
    "default_chain_proposals",
    "default_crew_deployments",
    "default_entry_events",
    "default_intent_normalizations",
    "default_routing_decisions",
    "default_surface_compatibilities",
    "export_entry_agnostic_workflow_block_chain_routing_contract",
    "format_entry_agnostic_workflow_block_chain_routing_contract",
    "stable_json",
]
