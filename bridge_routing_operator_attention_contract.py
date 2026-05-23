"""Bridge Routing / Operator Attention Contract v0.

This deterministic read-model defines how OpenClaw routes attention between
the Bridge/Helm, Worlds, Crew Briefings, Below Deck/Engineering, and Shipyard
Mode. It models visibility and interruption policy only. It does not write
state or receipts, execute workflows, call models/tools/agents/runtimes, access
external systems, send messages, generate invoices, submit approvals, modify
Mission Control Swift code, run Mac sync/import, use network, or grant live
authority.
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

SCHEMA_VERSION = "bridge_routing_operator_attention_contract_v0"
READ_MODEL_ID = "bridge_routing_operator_attention_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_BRIDGE_ROUTING_CONTRACT"

ATTENTION_TYPES = (
    "CAPTAIN_DECISION_REQUIRED",
    "WORLD_NEEDS_ATTENTION",
    "CREW_BRIEFING",
    "MISSION_STATUS_UPDATE",
    "ENGINEERING_CONTAINED",
    "CHECK_ENGINE",
    "SHIPYARD_TASK",
    "PROOF_AVAILABLE",
    "DEBUG_DETAIL",
    "UNKNOWN_FAIL_CLOSED",
)

ALERT_LEVELS = (
    "NORMAL_FLIGHT",
    "YELLOW_ALERT",
    "RED_ALERT",
    "ENGINEERING_CONTAINED",
    "SHIPYARD_MODE",
    "UNKNOWN_FAIL_CLOSED",
)

ROUTING_DESTINATIONS = (
    "HELM",
    "WORLD",
    "BELOW_DECK",
    "CREW_BRIEFING",
    "SHIPYARD",
    "RED_ALERT",
    "QUIET_LOG_ONLY",
    "UNKNOWN_FAIL_CLOSED",
)

DETAIL_TYPES = (
    "PROOF_DETAIL",
    "SOURCE_DETAIL",
    "RECEIPT_DETAIL",
    "SYNC_HEALTH",
    "STABLE_MAP_DETAIL",
    "TEST_RESULT_DETAIL",
    "AUTHORITY_GATE_DETAIL",
    "DEBUG_DETAIL",
    "TOOLING_DETAIL",
    "UNKNOWN_FAIL_CLOSED",
)

BRIEFING_TYPES = (
    "DECISION_REQUEST",
    "STATUS_UPDATE",
    "DRAFT_READY",
    "PROOF_NEEDED",
    "APPROVAL_NEEDED",
    "BLOCKER_FOUND",
    "ENGINEERING_CONTAINED",
    "SECURITY_GATE",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_BRIDGE_ATTENTION_FIELDS = (
    "attention_id",
    "title",
    "world",
    "lane",
    "workflow_session_ref",
    "source_actor",
    "source_surface",
    "attention_type",
    "alert_level",
    "captain_level_summary",
    "captain_decision_needed",
    "decision_prompt",
    "available_choices",
    "next_safe_move",
    "route_target",
    "world_destination",
    "supporting_crew_refs",
    "proof_refs",
    "below_deck_refs",
    "authority_boundary",
    "quieting_policy",
    "expiry_or_staleness_policy",
    "should_interrupt_captain",
    "should_show_on_helm",
    "should_stay_in_world",
    "should_stay_below_deck",
)

REQUIRED_ROUTING_DECISION_FIELDS = (
    "routing_id",
    "source_record_ref",
    "routing_destination",
    "reason",
    "captain_visible_summary",
    "world_surface_target",
    "below_deck_target",
    "crew_briefing_target",
    "suppress_from_helm_reason",
    "promote_to_helm_reason",
    "route_to_shipyard_reason",
    "requires_operator_decision",
    "requires_immediate_attention",
    "can_be_summarized",
    "can_be_quieted",
    "proof_detail_available",
    "next_safe_move",
)

REQUIRED_WORLD_SURFACE_FIELDS = (
    "world_surface_id",
    "world",
    "active_missions",
    "current_workflow_sessions",
    "unlocked_blocks",
    "captain_needed_blocks",
    "crew_deployed",
    "local_draft_refs",
    "proof_needed_refs",
    "approval_needed_refs",
    "downstream_artifact_refs",
    "below_deck_refs",
    "helm_summary",
    "next_safe_move",
)

REQUIRED_BELOW_DECK_FIELDS = (
    "detail_id",
    "detail_type",
    "source_world",
    "source_lane",
    "source_actor",
    "summary",
    "proof_refs",
    "receipt_refs",
    "sync_refs",
    "stable_map_refs",
    "test_refs",
    "debug_refs",
    "authority_gate_refs",
    "captain_visibility",
    "summon_label",
    "default_visibility",
    "interrupt_allowed",
    "next_safe_move",
)

REQUIRED_CREW_BRIEFING_FIELDS = (
    "briefing_id",
    "crew_actor",
    "world",
    "lane",
    "briefing_type",
    "captain_summary",
    "decision_needed",
    "recommended_action",
    "choices",
    "evidence_refs",
    "workflow_block_refs",
    "draft_intent_refs",
    "authority_boundary",
    "urgency",
    "should_promote_to_helm",
    "should_remain_in_world",
    "next_safe_move",
)

REQUIRED_SHIPYARD_FIELDS = (
    "shipyard_record_id",
    "build_lane",
    "issue_summary",
    "source_actor",
    "affected_systems",
    "developer_action_needed",
    "check_engine_status",
    "validation_refs",
    "test_refs",
    "git_refs",
    "dirty_state_refs",
    "safe_to_ignore_in_normal_mode",
    "should_show_on_helm",
    "should_show_in_shipyard",
    "next_safe_move",
)

REQUIRED_ALERT_POLICY_FIELDS = (
    "policy_id",
    "alert_level",
    "promotion_criteria",
    "suppression_criteria",
    "captain_interrupt_allowed",
    "visible_surface",
    "quieting_rule",
    "expiry_rule",
    "examples",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "helm_action_execution_allowed": False,
    "world_action_execution_allowed": False,
    "crew_action_execution_allowed": False,
    "receipt_write_allowed": False,
    "state_write_allowed": False,
    "approval_submission_allowed": False,
    "invoice_generation_allowed": False,
    "email_send_allowed": False,
    "browser_automation_allowed": False,
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
    "coupa_access_allowed": False,
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

COMMON_BLOCKED_ACTIONS = (
    "receipt write",
    "workflow state write",
    "workflow execution",
    "invoice generation",
    "email or Telegram send",
    "approval submission",
    "browser/Coupa/Gmail/Calendar/account access",
    "credential handling",
    "model/tool/agent/runtime/queue execution",
    "ledger write",
    "file write or cleanup",
    "raw body ingestion",
)

RELATIONSHIP_REF_PATHS = {
    "workflow_block_intent_live_draft_contract": "generated/read_models/workflow_block_intent_live_draft_contract.json",
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
    "openclaw_work_terrain_gap_detector": "generated/read_models/openclaw_work_terrain_gap_detector.json",
    "capital_hilton_proof_resolution_batch": "generated/read_models/capital_hilton_proof_resolution_batch_manifest.json",
    "security_pass_contract": "generated/read_models/security_pass_contract.json",
}


@dataclass(frozen=True)
class BridgeAttentionRecord:
    attention_id: str
    title: str
    world: str
    lane: str
    workflow_session_ref: str
    source_actor: str
    source_surface: str
    attention_type: str
    alert_level: str
    captain_level_summary: str
    captain_decision_needed: bool
    decision_prompt: str
    available_choices: tuple[str, ...]
    next_safe_move: str
    route_target: str
    world_destination: str
    supporting_crew_refs: tuple[str, ...]
    proof_refs: tuple[str, ...]
    below_deck_refs: tuple[str, ...]
    authority_boundary: dict[str, bool]
    quieting_policy: str
    expiry_or_staleness_policy: str
    should_interrupt_captain: bool
    should_show_on_helm: bool
    should_stay_in_world: bool
    should_stay_below_deck: bool


@dataclass(frozen=True)
class AttentionRoutingDecision:
    routing_id: str
    source_record_ref: str
    routing_destination: str
    reason: str
    captain_visible_summary: str
    world_surface_target: str
    below_deck_target: str
    crew_briefing_target: str
    suppress_from_helm_reason: str
    promote_to_helm_reason: str
    route_to_shipyard_reason: str
    requires_operator_decision: bool
    requires_immediate_attention: bool
    can_be_summarized: bool
    can_be_quieted: bool
    proof_detail_available: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorldMissionSurface:
    world_surface_id: str
    world: str
    active_missions: tuple[str, ...]
    current_workflow_sessions: tuple[str, ...]
    unlocked_blocks: tuple[str, ...]
    captain_needed_blocks: tuple[str, ...]
    crew_deployed: tuple[str, ...]
    local_draft_refs: tuple[str, ...]
    proof_needed_refs: tuple[str, ...]
    approval_needed_refs: tuple[str, ...]
    downstream_artifact_refs: tuple[str, ...]
    below_deck_refs: tuple[str, ...]
    helm_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class BelowDeckEngineeringDetail:
    detail_id: str
    detail_type: str
    source_world: str
    source_lane: str
    source_actor: str
    summary: str
    proof_refs: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    sync_refs: tuple[str, ...]
    stable_map_refs: tuple[str, ...]
    test_refs: tuple[str, ...]
    debug_refs: tuple[str, ...]
    authority_gate_refs: tuple[str, ...]
    captain_visibility: str
    summon_label: str
    default_visibility: str
    interrupt_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class CrewBriefing:
    briefing_id: str
    crew_actor: str
    world: str
    lane: str
    briefing_type: str
    captain_summary: str
    decision_needed: bool
    recommended_action: str
    choices: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    workflow_block_refs: tuple[str, ...]
    draft_intent_refs: tuple[str, ...]
    authority_boundary: dict[str, bool]
    urgency: str
    should_promote_to_helm: bool
    should_remain_in_world: bool
    next_safe_move: str


@dataclass(frozen=True)
class ShipyardModeRecord:
    shipyard_record_id: str
    build_lane: str
    issue_summary: str
    source_actor: str
    affected_systems: tuple[str, ...]
    developer_action_needed: bool
    check_engine_status: str
    validation_refs: tuple[str, ...]
    test_refs: tuple[str, ...]
    git_refs: tuple[str, ...]
    dirty_state_refs: tuple[str, ...]
    safe_to_ignore_in_normal_mode: bool
    should_show_on_helm: bool
    should_show_in_shipyard: bool
    next_safe_move: str


@dataclass(frozen=True)
class BridgeAlertPolicy:
    policy_id: str
    alert_level: str
    promotion_criteria: tuple[str, ...]
    suppression_criteria: tuple[str, ...]
    captain_interrupt_allowed: bool
    visible_surface: str
    quieting_rule: str
    expiry_rule: str
    examples: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class BridgeRoutingExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    attention_record_count: int
    routing_decision_count: int
    world_surface_count: int
    below_deck_detail_count: int
    crew_briefing_count: int
    shipyard_record_count: int
    alert_policy_count: int
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


def default_attention_records() -> tuple[BridgeAttentionRecord, ...]:
    return (
        BridgeAttentionRecord(
            attention_id="capital_hilton_finance_mission_attention",
            title="Finance needs attention",
            world="Finance",
            lane="Capital Hilton",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            source_actor="Mission Control",
            source_surface="Helm summary",
            attention_type="WORLD_NEEDS_ATTENTION",
            alert_level="YELLOW_ALERT",
            captain_level_summary="Capital Hilton has an unlocked invoice block in Finance World.",
            captain_decision_needed=True,
            decision_prompt="Open the Finance World and pick what is true about the next invoice block?",
            available_choices=("Open Finance World", "Park this for later", "Summon proof detail"),
            next_safe_move="Route Winship to the Capital Hilton workflow inside Finance World.",
            route_target="WORLD",
            world_destination="Finance World",
            supporting_crew_refs=("cassandra_clara_finance_briefing", "guardian_invoice_gate_briefing"),
            proof_refs=(
                "capital_hilton_proof_resolution_batch",
                "capital_hilton_coupa_po_retrieval_automation_candidate",
            ),
            below_deck_refs=("capital_hilton_proof_below_deck_detail",),
            authority_boundary=_authority_boundary(),
            quieting_policy="Quiet once the unlocked block is parked, captured by future receipt, or no longer needs a captain choice.",
            expiry_or_staleness_policy="Revalidate against the workflow session before display if upstream invoice state changes.",
            should_interrupt_captain=False,
            should_show_on_helm=True,
            should_stay_in_world=False,
            should_stay_below_deck=False,
        ),
        BridgeAttentionRecord(
            attention_id="capital_hilton_approval_locked_attention",
            title="Capital Hilton approval is locked",
            world="Finance",
            lane="Capital Hilton",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            source_actor="Guardian",
            source_surface="Finance World",
            attention_type="MISSION_STATUS_UPDATE",
            alert_level="NORMAL_FLIGHT",
            captain_level_summary="Approval/send is locked until prerequisites are ready.",
            captain_decision_needed=False,
            decision_prompt="",
            available_choices=("Inspect prerequisites", "Keep locked"),
            next_safe_move="Keep approval detail in Finance World and below deck until an approval is actually ready.",
            route_target="WORLD",
            world_destination="Finance World",
            supporting_crew_refs=("guardian_invoice_gate_briefing",),
            proof_refs=("capital_hilton_proof_resolution_batch",),
            below_deck_refs=("capital_hilton_approval_gate_below_deck_detail",),
            authority_boundary=_authority_boundary(),
            quieting_policy="Do not promote raw proof walls; show only locked prerequisite summary.",
            expiry_or_staleness_policy="Refresh prerequisite status when the workflow session changes.",
            should_interrupt_captain=False,
            should_show_on_helm=False,
            should_stay_in_world=True,
            should_stay_below_deck=False,
        ),
        BridgeAttentionRecord(
            attention_id="chief_check_engine_attention",
            title="Check Engine",
            world="Build",
            lane="Chief / Check Engine",
            workflow_session_ref="check_engine_diagnostic_session",
            source_actor="Chief",
            source_surface="Shipyard",
            attention_type="CHECK_ENGINE",
            alert_level="SHIPYARD_MODE",
            captain_level_summary="Build troubleshooting belongs in Shipyard unless it blocks an active mission.",
            captain_decision_needed=False,
            decision_prompt="",
            available_choices=("Open Shipyard", "Keep below deck"),
            next_safe_move="Route diagnostic detail to Shipyard and interrupt Helm only if active mission progress is blocked.",
            route_target="SHIPYARD",
            world_destination="Shipyard / Build",
            supporting_crew_refs=("chief_check_engine_briefing",),
            proof_refs=("focused_test_refs", "check_engine_diagnostic_solve_path"),
            below_deck_refs=("check_engine_test_below_deck_detail",),
            authority_boundary=_authority_boundary(),
            quieting_policy="Suppress in normal bridge mode when engineering has contained the issue.",
            expiry_or_staleness_policy="Stale diagnostic results must be marked stale before they drive a captain decision.",
            should_interrupt_captain=False,
            should_show_on_helm=False,
            should_stay_in_world=False,
            should_stay_below_deck=False,
        ),
        BridgeAttentionRecord(
            attention_id="sync_health_mismatch_attention",
            title="Read-model sync health mismatch",
            world="Engineering",
            lane="Sync Health",
            workflow_session_ref="sync_health_read_model",
            source_actor="Engineering",
            source_surface="Below Deck",
            attention_type="ENGINEERING_CONTAINED",
            alert_level="ENGINEERING_CONTAINED",
            captain_level_summary="Sync mismatch is contained unless it blocks Mac app read-model availability.",
            captain_decision_needed=False,
            decision_prompt="",
            available_choices=("Inspect sync detail", "Keep quiet"),
            next_safe_move="Keep contained sync proof below deck; promote only if the app cannot show current mission state.",
            route_target="BELOW_DECK",
            world_destination="Engineering",
            supporting_crew_refs=("chief_sync_health_briefing",),
            proof_refs=("sync_health", "openclaw_map_receipt"),
            below_deck_refs=("sync_health_below_deck_detail",),
            authority_boundary=_authority_boundary(),
            quieting_policy="Quiet after proof says mirror current or after mismatch is logged as nonblocking.",
            expiry_or_staleness_policy="Promote to Yellow/Red only when current mission state cannot be trusted.",
            should_interrupt_captain=False,
            should_show_on_helm=False,
            should_stay_in_world=False,
            should_stay_below_deck=True,
        ),
        BridgeAttentionRecord(
            attention_id="telegram_cassandra_request_attention",
            title="Draft request ready for review",
            world="Finance",
            lane="Capital Hilton / Conversation",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            source_actor="Cassandra",
            source_surface="Telegram",
            attention_type="CREW_BRIEFING",
            alert_level="YELLOW_ALERT",
            captain_level_summary="Cassandra compiled a draft request; Finance World owns the workflow.",
            captain_decision_needed=True,
            decision_prompt="Review the draft request in Finance World?",
            available_choices=("Review draft", "Ask a missing question", "Park request"),
            next_safe_move="Route the proposal to the shared workflow block draft inside Finance World.",
            route_target="WORLD",
            world_destination="Finance World",
            supporting_crew_refs=("cassandra_telegram_request_briefing",),
            proof_refs=("workflow_block_intent_live_draft_contract.capital_hilton_telegram_invoice_request_draft",),
            below_deck_refs=("telegram_request_below_deck_detail",),
            authority_boundary=_authority_boundary(),
            quieting_policy="Quiet once draft is reviewed, parked, or superseded by the workflow session.",
            expiry_or_staleness_policy="Conversation proposals must revalidate if workflow session changes.",
            should_interrupt_captain=False,
            should_show_on_helm=True,
            should_stay_in_world=False,
            should_stay_below_deck=False,
        ),
        BridgeAttentionRecord(
            attention_id="security_red_alert_attention",
            title="Security decision required",
            world="Security",
            lane="Guardian",
            workflow_session_ref="security_pass_contract",
            source_actor="Guardian",
            source_surface="Security World",
            attention_type="CAPTAIN_DECISION_REQUIRED",
            alert_level="RED_ALERT",
            captain_level_summary="Safe continuation requires a security decision.",
            captain_decision_needed=True,
            decision_prompt="Decide whether this authority change needs security review before continuing?",
            available_choices=("Require review", "Park", "Reject authority change"),
            next_safe_move="Stop continuation until the captain chooses a safe security route.",
            route_target="RED_ALERT",
            world_destination="Security World",
            supporting_crew_refs=("guardian_security_gate_briefing",),
            proof_refs=("security_pass_contract",),
            below_deck_refs=("security_gate_below_deck_detail",),
            authority_boundary=_authority_boundary(),
            quieting_policy="Do not quiet until decision is captured by a future receipt lane or the item is parked/rejected.",
            expiry_or_staleness_policy="Red alerts remain visible until resolved, parked, quarantined, or superseded.",
            should_interrupt_captain=True,
            should_show_on_helm=True,
            should_stay_in_world=False,
            should_stay_below_deck=False,
        ),
        BridgeAttentionRecord(
            attention_id="proof_available_below_deck_attention",
            title="Proof available",
            world="Finance",
            lane="Capital Hilton",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            source_actor="Engineering",
            source_surface="Below Deck",
            attention_type="PROOF_AVAILABLE",
            alert_level="NORMAL_FLIGHT",
            captain_level_summary="Proof exists one level down.",
            captain_decision_needed=False,
            decision_prompt="",
            available_choices=("Inspect proof drawer",),
            next_safe_move="Keep proof inspectable below deck without promoting it to Helm.",
            route_target="BELOW_DECK",
            world_destination="Finance World",
            supporting_crew_refs=(),
            proof_refs=("capital_hilton_proof_resolution_batch",),
            below_deck_refs=("capital_hilton_proof_below_deck_detail",),
            authority_boundary=_authority_boundary(),
            quieting_policy="Stay collapsed unless summoned or blocking a required decision.",
            expiry_or_staleness_policy="Mark stale if source proof refs change.",
            should_interrupt_captain=False,
            should_show_on_helm=False,
            should_stay_in_world=False,
            should_stay_below_deck=True,
        ),
    )


def default_routing_decisions() -> tuple[AttentionRoutingDecision, ...]:
    return (
        AttentionRoutingDecision(
            routing_id="route_capital_hilton_to_finance_world",
            source_record_ref="capital_hilton_finance_mission_attention",
            routing_destination="WORLD",
            reason="Finance workflow work belongs in Finance World; Helm should only route the captain to the item.",
            captain_visible_summary="Finance needs attention: Capital Hilton has an unlocked block.",
            world_surface_target="finance_world_mission_surface",
            below_deck_target="capital_hilton_proof_below_deck_detail",
            crew_briefing_target="cassandra_clara_finance_briefing",
            suppress_from_helm_reason="Raw proof and workflow cards would turn Helm into the whole workspace.",
            promote_to_helm_reason="Captain has a concise next decision to route into Finance World.",
            route_to_shipyard_reason="",
            requires_operator_decision=True,
            requires_immediate_attention=False,
            can_be_summarized=True,
            can_be_quieted=True,
            proof_detail_available=True,
            next_safe_move="Show a calm Helm marker and route into Finance World.",
        ),
        AttentionRoutingDecision(
            routing_id="route_capital_hilton_approval_locked_to_world",
            source_record_ref="capital_hilton_approval_locked_attention",
            routing_destination="WORLD",
            reason="Locked approval is prerequisite status, not a captain interrupt.",
            captain_visible_summary="Approval/send remains locked.",
            world_surface_target="finance_world_mission_surface",
            below_deck_target="capital_hilton_approval_gate_below_deck_detail",
            crew_briefing_target="guardian_invoice_gate_briefing",
            suppress_from_helm_reason="Approval is not ready, so a Helm interrupt would be noise.",
            promote_to_helm_reason="",
            route_to_shipyard_reason="",
            requires_operator_decision=False,
            requires_immediate_attention=False,
            can_be_summarized=True,
            can_be_quieted=True,
            proof_detail_available=True,
            next_safe_move="Keep approval locked in Finance World until prerequisites make a real choice available.",
        ),
        AttentionRoutingDecision(
            routing_id="route_chief_check_engine_to_shipyard",
            source_record_ref="chief_check_engine_attention",
            routing_destination="SHIPYARD",
            reason="Build troubleshooting is developer mode unless it blocks active mission safety or progress.",
            captain_visible_summary="Check Engine is in Shipyard.",
            world_surface_target="",
            below_deck_target="check_engine_test_below_deck_detail",
            crew_briefing_target="chief_check_engine_briefing",
            suppress_from_helm_reason="Developer/build noise should not dominate normal bridge mode.",
            promote_to_helm_reason="Only promote if the blocker stops active mission progress.",
            route_to_shipyard_reason="This is build/repair validation work.",
            requires_operator_decision=False,
            requires_immediate_attention=False,
            can_be_summarized=True,
            can_be_quieted=True,
            proof_detail_available=True,
            next_safe_move="Open Shipyard when Winship is in build/troubleshooting posture.",
        ),
        AttentionRoutingDecision(
            routing_id="route_sync_health_mismatch_contained_below_deck",
            source_record_ref="sync_health_mismatch_attention",
            routing_destination="BELOW_DECK",
            reason="Contained sync proof should log below deck and not interrupt unless app state is stale or unavailable.",
            captain_visible_summary="Sync is contained.",
            world_surface_target="",
            below_deck_target="sync_health_below_deck_detail",
            crew_briefing_target="chief_sync_health_briefing",
            suppress_from_helm_reason="Contained engineering status is not a captain-level decision.",
            promote_to_helm_reason="Promote only if Mac app read-model availability blocks a mission.",
            route_to_shipyard_reason="If repair is needed, handle in Shipyard.",
            requires_operator_decision=False,
            requires_immediate_attention=False,
            can_be_summarized=True,
            can_be_quieted=True,
            proof_detail_available=True,
            next_safe_move="Keep as Engineering Contained unless mirror staleness affects visible mission work.",
        ),
        AttentionRoutingDecision(
            routing_id="route_telegram_cassandra_request_to_finance_world",
            source_record_ref="telegram_cassandra_request_attention",
            routing_destination="WORLD",
            reason="Telegram and Cassandra originate a proposal, but the Finance workflow session owns state.",
            captain_visible_summary="Draft request ready in Finance World.",
            world_surface_target="finance_world_mission_surface",
            below_deck_target="telegram_request_below_deck_detail",
            crew_briefing_target="cassandra_telegram_request_briefing",
            suppress_from_helm_reason="Conversation transcript and draft internals stay out of Helm.",
            promote_to_helm_reason="A concise review decision is available.",
            route_to_shipyard_reason="",
            requires_operator_decision=True,
            requires_immediate_attention=False,
            can_be_summarized=True,
            can_be_quieted=True,
            proof_detail_available=True,
            next_safe_move="Show the short draft-ready marker and route to the relevant World.",
        ),
        AttentionRoutingDecision(
            routing_id="route_security_decision_to_red_alert",
            source_record_ref="security_red_alert_attention",
            routing_destination="RED_ALERT",
            reason="Safe continuation is blocked until the captain chooses a security route.",
            captain_visible_summary="Security decision required before safe continuation.",
            world_surface_target="security_world_mission_surface",
            below_deck_target="security_gate_below_deck_detail",
            crew_briefing_target="guardian_security_gate_briefing",
            suppress_from_helm_reason="",
            promote_to_helm_reason="Red Alert requires immediate operator decision.",
            route_to_shipyard_reason="",
            requires_operator_decision=True,
            requires_immediate_attention=True,
            can_be_summarized=True,
            can_be_quieted=False,
            proof_detail_available=True,
            next_safe_move="Interrupt only with the captain decision and keep proof one level down.",
        ),
        AttentionRoutingDecision(
            routing_id="route_proof_available_to_below_deck",
            source_record_ref="proof_available_below_deck_attention",
            routing_destination="BELOW_DECK",
            reason="Proof availability is inspectable support, not a captain interrupt by itself.",
            captain_visible_summary="Proof is available.",
            world_surface_target="finance_world_mission_surface",
            below_deck_target="capital_hilton_proof_below_deck_detail",
            crew_briefing_target="",
            suppress_from_helm_reason="Proof/debug/status detail should not promote to Helm by default.",
            promote_to_helm_reason="",
            route_to_shipyard_reason="",
            requires_operator_decision=False,
            requires_immediate_attention=False,
            can_be_summarized=True,
            can_be_quieted=True,
            proof_detail_available=True,
            next_safe_move="Leave proof collapsed until summoned or required by a decision node.",
        ),
    )


def default_world_surfaces() -> tuple[WorldMissionSurface, ...]:
    return (
        WorldMissionSurface(
            world_surface_id="finance_world_mission_surface",
            world="Finance",
            active_missions=("Capital Hilton invoice", "Coupa / PO lookup candidate"),
            current_workflow_sessions=("capital_hilton_invoice_workflow_session",),
            unlocked_blocks=("performance_dates", "po_reference", "rate_source"),
            captain_needed_blocks=("performance_dates",),
            crew_deployed=("Cassandra/Clara", "Guardian", "Chief"),
            local_draft_refs=(
                "workflow_block_intent_live_draft_contract.capital_hilton_mission_control_performance_dates_draft",
                "workflow_block_intent_live_draft_contract.capital_hilton_telegram_invoice_request_draft",
            ),
            proof_needed_refs=("capital_hilton_proof_resolution_batch",),
            approval_needed_refs=("future_invoice_artifact_approval", "future_send_email_approval"),
            downstream_artifact_refs=("invoice_packet_preview_future", "email_attachment_preview_future"),
            below_deck_refs=("capital_hilton_proof_below_deck_detail", "capital_hilton_approval_gate_below_deck_detail"),
            helm_summary="Finance needs attention: Capital Hilton has one next invoice block.",
            next_safe_move="Solve the invoice block inside Finance World, not on Helm.",
        ),
        WorldMissionSurface(
            world_surface_id="operations_build_world_mission_surface",
            world="Operations / Build",
            active_missions=("Chief terrain reconciliation", "Check Engine diagnostics"),
            current_workflow_sessions=("chief_terrain_reconciliation_session", "check_engine_diagnostic_session"),
            unlocked_blocks=("terrain_gap_review", "diagnostic_summary"),
            captain_needed_blocks=("repair_risk_decision_if_needed",),
            crew_deployed=("Chief", "Hermes", "Guardian if needed"),
            local_draft_refs=("workflow_block_intent_live_draft_contract.chief_check_engine_build_blocker_draft",),
            proof_needed_refs=("openclaw_work_terrain_gap_detector", "focused_test_refs"),
            approval_needed_refs=("repair_authority_gate_future",),
            downstream_artifact_refs=("repair_plan_preview_future",),
            below_deck_refs=("check_engine_test_below_deck_detail", "terrain_gap_below_deck_detail"),
            helm_summary="Build work is available in Shipyard when Winship is in troubleshooting mode.",
            next_safe_move="Keep build noise out of normal Bridge mode unless it blocks a mission.",
        ),
        WorldMissionSurface(
            world_surface_id="security_world_mission_surface",
            world="Security",
            active_missions=("Guardian review", "Security Pass"),
            current_workflow_sessions=("security_pass_contract",),
            unlocked_blocks=("authority_delta_review",),
            captain_needed_blocks=("security_review_required_choice",),
            crew_deployed=("Guardian",),
            local_draft_refs=(),
            proof_needed_refs=("security_pass_contract",),
            approval_needed_refs=("security_delta_approval_future",),
            downstream_artifact_refs=(),
            below_deck_refs=("security_gate_below_deck_detail",),
            helm_summary="Security only interrupts when safe continuation needs a captain decision.",
            next_safe_move="Route normal security review into Security World; use Red Alert only for blocking decisions.",
        ),
        WorldMissionSurface(
            world_surface_id="communications_world_mission_surface",
            world="Communications",
            active_missions=("Cassandra/Clara draft review", "Telegram-originated requests"),
            current_workflow_sessions=("cassandra_clara_draft_review_session",),
            unlocked_blocks=("draft_review",),
            captain_needed_blocks=("send_review_choice",),
            crew_deployed=("Cassandra/Clara", "Guardian"),
            local_draft_refs=("workflow_block_intent_live_draft_contract.capital_hilton_telegram_invoice_request_draft",),
            proof_needed_refs=("draft_packet_refs_future",),
            approval_needed_refs=("send_email_approval_bus_future",),
            downstream_artifact_refs=("draft_preview_packet_future",),
            below_deck_refs=("telegram_request_below_deck_detail",),
            helm_summary="A communications draft should appear on Helm only when a review choice exists.",
            next_safe_move="Keep draft work in the relevant World and keep send blocked.",
        ),
    )


def default_below_deck_details() -> tuple[BelowDeckEngineeringDetail, ...]:
    return (
        BelowDeckEngineeringDetail(
            detail_id="capital_hilton_proof_below_deck_detail",
            detail_type="PROOF_DETAIL",
            source_world="Finance",
            source_lane="Capital Hilton",
            source_actor="Engineering",
            summary="Capital Hilton proof, Coupa refs, receipts, and source detail live one level down.",
            proof_refs=("capital_hilton_proof_resolution_batch", "capital_hilton_coupa_po_retrieval_automation_candidate"),
            receipt_refs=("capital_hilton_receipt_refs_future",),
            sync_refs=(),
            stable_map_refs=("openclaw_map_snapshot",),
            test_refs=(),
            debug_refs=(),
            authority_gate_refs=("invoice_generation_gate_false", "email_send_gate_false"),
            captain_visibility="inspectable when summoned or when a decision node needs proof context",
            summon_label="Show proof",
            default_visibility="collapsed",
            interrupt_allowed=False,
            next_safe_move="Keep proof available without making it the default app surface.",
        ),
        BelowDeckEngineeringDetail(
            detail_id="capital_hilton_approval_gate_below_deck_detail",
            detail_type="AUTHORITY_GATE_DETAIL",
            source_world="Finance",
            source_lane="Capital Hilton",
            source_actor="Guardian",
            summary="Approval/send authority is locked until prerequisites and future approval bus exist.",
            proof_refs=("capital_hilton_proof_resolution_batch",),
            receipt_refs=("future_approval_receipt_refs",),
            sync_refs=(),
            stable_map_refs=(),
            test_refs=(),
            debug_refs=(),
            authority_gate_refs=("approval_submission_allowed_false", "email_send_allowed_false"),
            captain_visibility="world summary only until an actual approval decision is ready",
            summon_label="Show locked gates",
            default_visibility="collapsed",
            interrupt_allowed=False,
            next_safe_move="Do not promote locked approval to Helm as if it were actionable.",
        ),
        BelowDeckEngineeringDetail(
            detail_id="check_engine_test_below_deck_detail",
            detail_type="TEST_RESULT_DETAIL",
            source_world="Build",
            source_lane="Check Engine",
            source_actor="Chief",
            summary="Build, repair, validation, test, dirty-state, and diagnostic detail belong in Shipyard/Engineering.",
            proof_refs=("check_engine_diagnostic_solve_path",),
            receipt_refs=(),
            sync_refs=(),
            stable_map_refs=(),
            test_refs=("focused_test_refs",),
            debug_refs=("developer_diagnostics",),
            authority_gate_refs=("repair_execution_gate_false",),
            captain_visibility="visible in Shipyard or when blocking active mission progress",
            summon_label="Open Shipyard detail",
            default_visibility="shipyard_only",
            interrupt_allowed=False,
            next_safe_move="Keep diagnostic detail below deck unless a captain repair/risk decision is required.",
        ),
        BelowDeckEngineeringDetail(
            detail_id="sync_health_below_deck_detail",
            detail_type="SYNC_HEALTH",
            source_world="Engineering",
            source_lane="Read-model sync",
            source_actor="Engineering",
            summary="Sync health and stable-map receipts are operational proof, not normal Helm content.",
            proof_refs=("openclaw_map_receipt",),
            receipt_refs=("openclaw_map_receipt",),
            sync_refs=("sync_health",),
            stable_map_refs=("openclaw_map_snapshot", "openclaw_map_manifest"),
            test_refs=(),
            debug_refs=("map_bundle_readback_metadata",),
            authority_gate_refs=("mac_sync_import_allowed_false",),
            captain_visibility="promote only when stale read-models block app mission state",
            summon_label="Show sync proof",
            default_visibility="collapsed",
            interrupt_allowed=False,
            next_safe_move="Log contained sync mismatches below deck and route repair to Shipyard when needed.",
        ),
        BelowDeckEngineeringDetail(
            detail_id="security_gate_below_deck_detail",
            detail_type="AUTHORITY_GATE_DETAIL",
            source_world="Security",
            source_lane="Guardian",
            source_actor="Guardian",
            summary="Security proof and gate refs support the captain decision without flooding Helm.",
            proof_refs=("security_pass_contract",),
            receipt_refs=("future_security_delta_receipt",),
            sync_refs=(),
            stable_map_refs=(),
            test_refs=(),
            debug_refs=(),
            authority_gate_refs=("security_delta_approval_future", "authority_change_blocked"),
            captain_visibility="shown one level down during Red Alert or Security World review",
            summon_label="Show security proof",
            default_visibility="collapsed",
            interrupt_allowed=True,
            next_safe_move="Use Red Alert only for the decision; keep proof detail below deck.",
        ),
        BelowDeckEngineeringDetail(
            detail_id="telegram_request_below_deck_detail",
            detail_type="SOURCE_DETAIL",
            source_world="Communications",
            source_lane="Telegram / Cassandra",
            source_actor="Cassandra",
            summary="Conversation-originated requests become draft intents; raw telemetry stays below deck.",
            proof_refs=("workflow_block_intent_live_draft_contract",),
            receipt_refs=("future_operator_answer_receipt",),
            sync_refs=(),
            stable_map_refs=(),
            test_refs=(),
            debug_refs=("draft_compiler_trace_refs_future",),
            authority_gate_refs=("telegram_send_allowed_false", "email_send_allowed_false"),
            captain_visibility="short briefing only unless the operator opens source detail",
            summon_label="Show request source",
            default_visibility="collapsed",
            interrupt_allowed=False,
            next_safe_move="Render a concise draft-ready briefing and route work to the owning World.",
        ),
        BelowDeckEngineeringDetail(
            detail_id="terrain_gap_below_deck_detail",
            detail_type="SOURCE_DETAIL",
            source_world="Operations / Build",
            source_lane="Work Terrain",
            source_actor="Chief",
            summary="Terrain query, relationship, classification, and gap details support reconciliation below deck.",
            proof_refs=("openclaw_work_terrain_gap_detector",),
            receipt_refs=(),
            sync_refs=(),
            stable_map_refs=("openclaw_map_snapshot",),
            test_refs=("tests/test_openclaw_work_terrain_gap_detector.py",),
            debug_refs=(),
            authority_gate_refs=("file_move_delete_cleanup_allowed_false",),
            captain_visibility="summon when reconciling current/stale/source gaps",
            summon_label="Show terrain refs",
            default_visibility="collapsed",
            interrupt_allowed=False,
            next_safe_move="Keep terrain details inspectable without turning Helm into an index browser.",
        ),
    )


def default_crew_briefings() -> tuple[CrewBriefing, ...]:
    return (
        CrewBriefing(
            briefing_id="cassandra_clara_finance_briefing",
            crew_actor="Cassandra/Clara",
            world="Finance",
            lane="Capital Hilton",
            briefing_type="DRAFT_READY",
            captain_summary="I can prepare a draft path after you answer the unlocked invoice block.",
            decision_needed=True,
            recommended_action="Open the Finance World block and pick what is true.",
            choices=("Open Finance World", "Park", "Show proof"),
            evidence_refs=("capital_hilton_proof_resolution_batch",),
            workflow_block_refs=("performance_dates", "po_reference", "rate_source"),
            draft_intent_refs=("capital_hilton_mission_control_performance_dates_draft",),
            authority_boundary=_authority_boundary(),
            urgency="YELLOW_ALERT",
            should_promote_to_helm=True,
            should_remain_in_world=False,
            next_safe_move="Brief the decision, not the whole proof shelf.",
        ),
        CrewBriefing(
            briefing_id="guardian_invoice_gate_briefing",
            crew_actor="Guardian",
            world="Finance",
            lane="Capital Hilton",
            briefing_type="APPROVAL_NEEDED",
            captain_summary="Invoice/send approval is locked until prerequisites are ready.",
            decision_needed=False,
            recommended_action="Keep approval locked.",
            choices=("Inspect prerequisites", "Keep locked"),
            evidence_refs=("capital_hilton_proof_resolution_batch",),
            workflow_block_refs=("approval_gate", "send_gate"),
            draft_intent_refs=(),
            authority_boundary=_authority_boundary(),
            urgency="NORMAL_FLIGHT",
            should_promote_to_helm=False,
            should_remain_in_world=True,
            next_safe_move="Do not ask for approval until approval is actually ready.",
        ),
        CrewBriefing(
            briefing_id="chief_check_engine_briefing",
            crew_actor="Chief",
            world="Build",
            lane="Check Engine",
            briefing_type="BLOCKER_FOUND",
            captain_summary="Build status can be summarized; detail stays in Shipyard unless you ask.",
            decision_needed=False,
            recommended_action="Open Shipyard only if you are in troubleshooting mode.",
            choices=("Open Shipyard", "Keep quiet"),
            evidence_refs=("focused_test_refs",),
            workflow_block_refs=("diagnostic_summary",),
            draft_intent_refs=("chief_check_engine_build_blocker_draft",),
            authority_boundary=_authority_boundary(),
            urgency="SHIPYARD_MODE",
            should_promote_to_helm=False,
            should_remain_in_world=False,
            next_safe_move="Contain build noise unless it blocks a mission.",
        ),
        CrewBriefing(
            briefing_id="chief_sync_health_briefing",
            crew_actor="Chief",
            world="Engineering",
            lane="Sync Health",
            briefing_type="ENGINEERING_CONTAINED",
            captain_summary="Sync proof is contained unless the app cannot see current read-models.",
            decision_needed=False,
            recommended_action="Keep below deck.",
            choices=("Inspect sync proof", "Keep quiet"),
            evidence_refs=("sync_health", "openclaw_map_receipt"),
            workflow_block_refs=(),
            draft_intent_refs=(),
            authority_boundary=_authority_boundary(),
            urgency="ENGINEERING_CONTAINED",
            should_promote_to_helm=False,
            should_remain_in_world=False,
            next_safe_move="Promote only if stale state blocks the operator's current mission.",
        ),
        CrewBriefing(
            briefing_id="cassandra_telegram_request_briefing",
            crew_actor="Cassandra",
            world="Finance",
            lane="Capital Hilton / Conversation",
            briefing_type="DRAFT_READY",
            captain_summary="Telegram request compiled into a Finance draft proposal.",
            decision_needed=True,
            recommended_action="Review the draft in Finance World.",
            choices=("Review draft", "Ask missing question", "Park"),
            evidence_refs=("workflow_block_intent_live_draft_contract",),
            workflow_block_refs=("invoice_request", "date_scope", "review_packet"),
            draft_intent_refs=("capital_hilton_telegram_invoice_request_draft",),
            authority_boundary=_authority_boundary(),
            urgency="YELLOW_ALERT",
            should_promote_to_helm=True,
            should_remain_in_world=False,
            next_safe_move="Show the captain one review choice and keep conversation details collapsible.",
        ),
        CrewBriefing(
            briefing_id="guardian_security_gate_briefing",
            crew_actor="Guardian",
            world="Security",
            lane="Authority Delta",
            briefing_type="SECURITY_GATE",
            captain_summary="Security decision required before safe continuation.",
            decision_needed=True,
            recommended_action="Choose whether this requires security review.",
            choices=("Require review", "Park", "Reject"),
            evidence_refs=("security_pass_contract",),
            workflow_block_refs=("authority_delta_review",),
            draft_intent_refs=(),
            authority_boundary=_authority_boundary(),
            urgency="RED_ALERT",
            should_promote_to_helm=True,
            should_remain_in_world=False,
            next_safe_move="Interrupt only because safe continuation needs a captain decision.",
        ),
    )


def default_shipyard_records() -> tuple[ShipyardModeRecord, ...]:
    return (
        ShipyardModeRecord(
            shipyard_record_id="chief_check_engine_shipyard_record",
            build_lane="Check Engine / diagnostics",
            issue_summary="Developer/build troubleshooting is active but not normal Bridge content.",
            source_actor="Chief",
            affected_systems=("read-model exporters", "focused tests", "stable map summaries if stale"),
            developer_action_needed=True,
            check_engine_status="SHIPYARD_MODE",
            validation_refs=("focused test refs", "py_compile refs", "git diff --check refs"),
            test_refs=("tests/test_workflow_block_intent_live_draft_contract.py",),
            git_refs=("local dirty state refs only; no push/pull/fetch authority",),
            dirty_state_refs=("generated/read_models/sync_health.json if dirty",),
            safe_to_ignore_in_normal_mode=True,
            should_show_on_helm=False,
            should_show_in_shipyard=True,
            next_safe_move="Keep build repair work in Shipyard unless it blocks active mission operation.",
        ),
        ShipyardModeRecord(
            shipyard_record_id="sync_health_shipyard_record",
            build_lane="Read-model sync proof",
            issue_summary="Sync proof repair is engineering work unless current app state is blocked.",
            source_actor="Engineering",
            affected_systems=("sync_health", "openclaw_map_receipt", "Mac mirror readback"),
            developer_action_needed=False,
            check_engine_status="ENGINEERING_CONTAINED",
            validation_refs=("JSON parse checks", "stable-map checks"),
            test_refs=("tests/test_operator_map_bundle_contract.py if touched",),
            git_refs=("local generated read-model state",),
            dirty_state_refs=("sync health generated file refs when dirty",),
            safe_to_ignore_in_normal_mode=True,
            should_show_on_helm=False,
            should_show_in_shipyard=True,
            next_safe_move="Expose as below deck proof, not a captain interrupt, when contained.",
        ),
    )


def default_alert_policies() -> tuple[BridgeAlertPolicy, ...]:
    return (
        BridgeAlertPolicy(
            policy_id="normal_flight_policy",
            alert_level="NORMAL_FLIGHT",
            promotion_criteria=("no captain decision required", "workflow can continue or remain quiet"),
            suppression_criteria=("proof available only", "status update only", "approval locked but not ready"),
            captain_interrupt_allowed=False,
            visible_surface="World or Below Deck when summoned",
            quieting_rule="Quiet by default; keep detail inspectable.",
            expiry_rule="Refresh quietly when source refs change.",
            examples=("proof available", "approval locked prerequisites", "completed/quieted status"),
            next_safe_move="Keep the Bridge calm.",
        ),
        BridgeAlertPolicy(
            policy_id="yellow_alert_policy",
            alert_level="YELLOW_ALERT",
            promotion_criteria=("captain-level choice exists", "workflow needs attention but safe continuation is not blocked"),
            suppression_criteria=("raw proof/debug details", "duplicate status cards"),
            captain_interrupt_allowed=False,
            visible_surface="Helm marker routing into World",
            quieting_rule="Can be parked, quieted, or resolved by future receipt.",
            expiry_rule="Stale after workflow session changes; revalidate before display.",
            examples=("Capital Hilton unlocked block", "Telegram draft ready for review"),
            next_safe_move="Show one calm route to the relevant World.",
        ),
        BridgeAlertPolicy(
            policy_id="red_alert_policy",
            alert_level="RED_ALERT",
            promotion_criteria=("safe continuation blocked", "captain decision required before proceeding"),
            suppression_criteria=("nonblocking status", "developer noise", "proof availability alone"),
            captain_interrupt_allowed=True,
            visible_surface="Helm / Red Alert with proof one level down",
            quieting_rule="Cannot be quieted until decided, parked, rejected, quarantined, expired, or superseded.",
            expiry_rule="Remain active until resolution state is receipt-backed in a future lane.",
            examples=("security decision required before safe continuation",),
            next_safe_move="Interrupt with only the decision and available safe choices.",
        ),
        BridgeAlertPolicy(
            policy_id="engineering_contained_policy",
            alert_level="ENGINEERING_CONTAINED",
            promotion_criteria=("engineering handled or logged issue", "no captain decision required"),
            suppression_criteria=("telemetry-only", "test/debug/sync detail not blocking missions"),
            captain_interrupt_allowed=False,
            visible_surface="Below Deck / Engineering",
            quieting_rule="Log below deck and summarize only when summoned.",
            expiry_rule="Promote only if containment fails or active mission state becomes stale/unavailable.",
            examples=("sync mismatch repaired", "nonblocking test detail", "proof receipt available"),
            next_safe_move="Keep engine-room telemetry out of normal Helm.",
        ),
        BridgeAlertPolicy(
            policy_id="shipyard_mode_policy",
            alert_level="SHIPYARD_MODE",
            promotion_criteria=("operator explicitly enters build/troubleshooting posture", "build issue blocks active mission"),
            suppression_criteria=("normal flight mode", "developer noise not blocking operator mission"),
            captain_interrupt_allowed=False,
            visible_surface="Shipyard",
            quieting_rule="Suppress in normal Bridge mode unless mission-blocking.",
            expiry_rule="Clear from normal view when validation passes or issue is parked.",
            examples=("Chief Check Engine", "dirty-state review", "focused test failure"),
            next_safe_move="Route build work to Shipyard, not Helm.",
        ),
        BridgeAlertPolicy(
            policy_id="quiet_log_only_policy",
            alert_level="ENGINEERING_CONTAINED",
            promotion_criteria=("never captain-level by itself", "audit/proof only"),
            suppression_criteria=("all quiet-log records suppress from Helm"),
            captain_interrupt_allowed=False,
            visible_surface="Below Deck log only",
            quieting_rule="Always quiet unless explicitly summoned.",
            expiry_rule="Retain traceability; do not display as active work.",
            examples=("duplicate proof row", "debug detail", "completed quieted step"),
            next_safe_move="Keep traceable without interrupting.",
        ),
    )


def bridge_routing_doctrine() -> dict[str, Any]:
    return {
        "north_star": "Winship is the captain; Mission Control is the bridge; OpenClaw is the ship.",
        "systems_engineering_not_theme": True,
        "bridge_rule": "Bridge routes; Worlds do work; Engineering stays below deck.",
        "captain_rule": "Captain sees decisions, not raw telemetry.",
        "world_rule": "Worlds are where real domain work happens.",
        "engineering_rule": "Proof, sync, status, receipts, tests, and debug stay below deck unless blocking or summoned.",
        "crew_rule": "Agents brief, not spam; agent proposals do not own truth.",
        "shipyard_rule": "Shipyard Mode is explicit developer/build/troubleshooting posture.",
        "normal_flight_rule": "The ship should be calm, relaxed, and powerful when nothing needs the captain.",
    }


def _asdict_items(items: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [asdict(item) for item in items]


def build_bridge_routing_operator_attention_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    attention_records = _asdict_items(default_attention_records())
    routing_decisions = _asdict_items(default_routing_decisions())
    world_surfaces = _asdict_items(default_world_surfaces())
    below_deck_details = _asdict_items(default_below_deck_details())
    crew_briefings = _asdict_items(default_crew_briefings())
    shipyard_records = _asdict_items(default_shipyard_records())
    alert_policies = _asdict_items(default_alert_policies())
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "doctrine": bridge_routing_doctrine(),
        "attention_types": list(ATTENTION_TYPES),
        "alert_levels": list(ALERT_LEVELS),
        "routing_destinations": list(ROUTING_DESTINATIONS),
        "detail_types": list(DETAIL_TYPES),
        "briefing_types": list(BRIEFING_TYPES),
        "bridge_attention_record_schema": {
            "structure": "BridgeAttentionRecord",
            "required_fields": list(REQUIRED_BRIDGE_ATTENTION_FIELDS),
            "helm_shows_captain_level_attention_only": True,
            "proof_debug_status_promote_by_default": False,
            "engineering_contained_interrupts_captain": False,
            "red_alert_requires_captain_decision": True,
            "yellow_alert_visible_not_urgent": True,
            "normal_flight_quiet": True,
            "shipyard_mode_explicit": True,
        },
        "attention_routing_decision_schema": {
            "structure": "AttentionRoutingDecision",
            "required_fields": list(REQUIRED_ROUTING_DECISION_FIELDS),
            "helm_routes_to_worlds": True,
            "helm_is_not_entire_workspace": True,
            "below_deck_contains_proof_sync_receipt_debug": True,
            "shipyard_contains_developer_build_repair_noise": True,
            "crew_briefing_is_concise_decision_or_update": True,
        },
        "world_mission_surface_schema": {
            "structure": "WorldMissionSurface",
            "required_fields": list(REQUIRED_WORLD_SURFACE_FIELDS),
            "worlds_do_domain_work": True,
            "capital_hilton_belongs_in_finance_world": True,
            "security_review_belongs_in_security_world_unless_red_alert": True,
            "helm_shows_world_attention_marker_only": True,
        },
        "below_deck_engineering_detail_schema": {
            "structure": "BelowDeckEngineeringDetail",
            "required_fields": list(REQUIRED_BELOW_DECK_FIELDS),
            "default_visibility": "collapsed_or_hidden_unless_blocking_or_summoned",
            "proof_exists_but_does_not_dominate": True,
            "debug_detail_belongs_below_deck_or_shipyard": True,
            "captain_can_inspect_without_being_forced": True,
        },
        "crew_briefing_schema": {
            "structure": "CrewBriefing",
            "required_fields": list(REQUIRED_CREW_BRIEFING_FIELDS),
            "agents_brief_not_spam": True,
            "raw_agent_telemetry_on_helm": False,
            "crew_may_prepare_block_drafts": True,
            "crew_owns_truth": False,
            "guardian_may_red_alert_when_safe_continuation_requires_decision": True,
        },
        "shipyard_mode_schema": {
            "structure": "ShipyardModeRecord",
            "required_fields": list(REQUIRED_SHIPYARD_FIELDS),
            "contains_build_repair_validation_sync_dirty_state_noise": True,
            "normal_bridge_suppresses_shipyard_noise": True,
            "check_engine_is_ship_troubleshooting": True,
        },
        "bridge_alert_policy_schema": {
            "structure": "BridgeAlertPolicy",
            "required_fields": list(REQUIRED_ALERT_POLICY_FIELDS),
            "normal_flight_quiet": True,
            "yellow_alert_nonblocking_attention": True,
            "red_alert_requires_captain_decision_before_safe_continuation": True,
            "engineering_contained_logs_below_deck": True,
            "quiet_log_only_never_interrupts": True,
        },
        "attention_records": attention_records,
        "attention_records_by_id": {item["attention_id"]: item for item in attention_records},
        "routing_decisions": routing_decisions,
        "routing_decisions_by_id": {item["routing_id"]: item for item in routing_decisions},
        "world_surfaces": world_surfaces,
        "world_surfaces_by_id": {item["world_surface_id"]: item for item in world_surfaces},
        "below_deck_details": below_deck_details,
        "below_deck_details_by_id": {item["detail_id"]: item for item in below_deck_details},
        "crew_briefings": crew_briefings,
        "crew_briefings_by_id": {item["briefing_id"]: item for item in crew_briefings},
        "shipyard_records": shipyard_records,
        "shipyard_records_by_id": {item["shipyard_record_id"]: item for item in shipyard_records},
        "alert_policies": alert_policies,
        "alert_policies_by_id": {item["policy_id"]: item for item in alert_policies},
        "relationship_refs": _relationship_refs(repo_root),
        "authority_boundary": _authority_boundary(),
        "hard_rule": {
            "read_model_only": True,
            "does_not_modify_mission_control_swift": True,
            "does_not_run_mac_sync_import": True,
            "does_not_use_network": True,
            "does_not_write_receipts": True,
            "does_not_write_state": True,
            "does_not_execute_workflow": True,
            "does_not_call_agents_or_models": True,
            "does_not_access_external_accounts": True,
            "may_grant_authority": False,
        },
        "machine_proof": {
            "bridge_attention_record_model_present": True,
            "attention_routing_decision_model_present": True,
            "world_mission_surface_model_present": True,
            "below_deck_engineering_detail_model_present": True,
            "crew_briefing_model_present": True,
            "shipyard_mode_record_model_present": True,
            "bridge_alert_policy_model_present": True,
            "attention_record_count": len(attention_records),
            "routing_decision_count": len(routing_decisions),
            "world_surface_count": len(world_surfaces),
            "below_deck_detail_count": len(below_deck_details),
            "crew_briefing_count": len(crew_briefings),
            "shipyard_record_count": len(shipyard_records),
            "alert_policy_count": len(alert_policies),
            "capital_hilton_routes_to_finance_world": (
                {item["routing_id"]: item for item in routing_decisions}[
                    "route_capital_hilton_to_finance_world"
                ]["routing_destination"]
                == "WORLD"
            ),
            "capital_hilton_not_raw_helm_workspace": True,
            "proof_debug_detail_below_deck_by_default": all(
                item["should_show_on_helm"] is False
                for item in attention_records
                if item["attention_type"] in {"PROOF_AVAILABLE", "DEBUG_DETAIL", "ENGINEERING_CONTAINED", "CHECK_ENGINE"}
            ),
            "engineering_contained_does_not_interrupt": all(
                item["should_interrupt_captain"] is False
                for item in attention_records
                if item["alert_level"] == "ENGINEERING_CONTAINED"
            ),
            "red_alert_interrupts_only_when_captain_decision_required": all(
                item["should_interrupt_captain"] is item["captain_decision_needed"]
                for item in attention_records
                if item["alert_level"] == "RED_ALERT"
            ),
            "shipyard_separates_developer_noise": True,
            "crew_briefings_action_oriented": all(item["recommended_action"] for item in crew_briefings),
            "agents_do_not_own_truth": True,
            "relationship_refs_represented": all(ref_id in _relationship_refs(repo_root) for ref_id in RELATIONSHIP_REF_PATHS),
            "all_authority_flags_false": _all_authority_flags_false(),
            "credentials_or_secrets_included": False,
            "raw_private_bodies_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_bridge_routing_operator_attention_markdown(payload: dict[str, Any]) -> str:
    proof = payload["machine_proof"]
    doctrine = payload["doctrine"]
    lines = [
        "# Bridge Routing / Operator Attention Contract v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "Bridge routes. Worlds do work. Engineering stays below deck.",
        "",
        "The Helm should feel calm because it only shows captain-level attention: a real decision, a real route into a World, or a true safety block. It should not become a wall of proof, sync status, debug cards, or completed machine details.",
        "",
        "Normal flight should be quiet. If the ship is working, Winship should not have to stare at engine-room telemetry. Proof, receipts, sync health, tests, generated read-model detail, and debug state remain inspectable one level down.",
        "",
        "Worlds are where domain work happens. Capital Hilton belongs in Finance World, with Helm showing only a short marker like Finance needs attention. Security review belongs in Security World unless safe continuation requires a Red Alert decision.",
        "",
        "Shipyard Mode is for building or repairing the ship. Chief/check-engine, dirty state, validation, sync repair, and developer noise live there unless they block an active mission.",
        "",
        "Crew briefings are concise decision or update packets. Cassandra, Clara, Chief, Guardian, Hermes, Niles, and future agents brief; they do not spam Helm, own truth, approve actions, or execute work.",
        "",
        "This is systems engineering, not Star Trek theming. The metaphor is just the routing model: captain, bridge, worlds, crew, engineering, logs, and shipyard each have a job.",
        "",
        "## Routing Examples",
        "",
        "- Capital Hilton: Helm shows Finance needs attention, Finance World shows invoice blocks and local draft, Below Deck holds proof/Coupa refs/receipts/source detail.",
        "- Capital Hilton approval locked: Helm does not show a raw proof wall; Finance World shows locked prerequisites; Guardian briefs only when approval is actually ready or needed.",
        "- Chief/check-engine: Shipyard handles build troubleshooting. Helm is interrupted only when an active mission cannot proceed without a captain decision.",
        "- Sync health mismatch: repaired or contained mismatch stays Engineering Contained or Quiet Log Only; mission-blocking read-model staleness can promote to Yellow or Red.",
        "- Telegram/Cassandra request: a conversation proposal becomes a workflow block draft; Helm may show a draft-ready marker only if a captain review choice exists.",
        "",
        "## Alert Policy",
        "",
        "- Normal Flight: quiet by default.",
        "- Yellow Alert: visible, nonblocking attention that routes to a World.",
        "- Red Alert: safe continuation requires a captain decision.",
        "- Engineering Contained: crew handled or logged it below deck.",
        "- Shipyard Mode: explicit build/troubleshooting surface.",
        "- Quiet Log Only: traceable and inspectable, never interrupting.",
        "",
        "## Still Blocked",
        "",
        "- No Helm/World/Crew action execution, receipt write, state write, approval submission, invoice generation, email/Telegram send, browser/Coupa/Gmail/Calendar/account access, credential handling, model/tool/agent/runtime/queue execution, file write/cleanup, raw body ingestion, network, Mac sync/import, Mission Control Swift change, or push.",
        "",
        "## Machine Proof Summary",
        "",
        f"- Doctrine: {doctrine['bridge_rule']}",
        f"- Attention records: `{proof['attention_record_count']}`.",
        f"- Routing decisions: `{proof['routing_decision_count']}`.",
        f"- World surfaces: `{proof['world_surface_count']}`.",
        f"- Below deck details: `{proof['below_deck_detail_count']}`.",
        f"- Crew briefings: `{proof['crew_briefing_count']}`.",
        f"- Shipyard records: `{proof['shipyard_record_count']}`.",
        f"- Alert policies: `{proof['alert_policy_count']}`.",
        f"- Capital Hilton routes to Finance World: `{str(proof['capital_hilton_routes_to_finance_world']).lower()}`.",
        f"- Proof/debug below deck by default: `{str(proof['proof_debug_detail_below_deck_by_default']).lower()}`.",
        f"- All authority flags false: `{str(proof['all_authority_flags_false']).lower()}`.",
        f"- Content hash: `{proof['content_hash']}`.",
    ]
    return "\n".join(lines) + "\n"


def export_bridge_routing_operator_attention_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> BridgeRoutingExportResult:
    repo_root = Path(repo_root)
    export_path = repo_root / export_root
    export_path.mkdir(parents=True, exist_ok=True)
    payload = build_bridge_routing_operator_attention_contract(
        repo_root=repo_root,
        generated_at=generated_at,
    )
    json_path = export_path / JSON_EXPORT_NAME
    operator_path = export_path / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_bridge_routing_operator_attention_markdown(payload), encoding="utf-8")
    proof = payload["machine_proof"]
    return BridgeRoutingExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        attention_record_count=proof["attention_record_count"],
        routing_decision_count=proof["routing_decision_count"],
        world_surface_count=proof["world_surface_count"],
        below_deck_detail_count=proof["below_deck_detail_count"],
        crew_briefing_count=proof["crew_briefing_count"],
        shipyard_record_count=proof["shipyard_record_count"],
        alert_policy_count=proof["alert_policy_count"],
        action_authority_granted=not proof["all_authority_flags_false"],
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Bridge Routing / Operator Attention Contract v0.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--generated-at", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = export_bridge_routing_operator_attention_contract(
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
        print(f"attention_record_count={result.attention_record_count}")
        print(f"routing_decision_count={result.routing_decision_count}")
        print(f"world_surface_count={result.world_surface_count}")
        print(f"below_deck_detail_count={result.below_deck_detail_count}")
        print(f"crew_briefing_count={result.crew_briefing_count}")
        print(f"shipyard_record_count={result.shipyard_record_count}")
        print(f"alert_policy_count={result.alert_policy_count}")
        print(f"action_authority_granted={str(result.action_authority_granted).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
