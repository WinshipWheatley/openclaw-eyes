"""Capability/skill registry metadata delta v0.

This read-model records known OpenClaw capability and skill surfaces as
metadata only. It does not activate tools, agents, planner/builder loops,
repair loops, Repo B code, OAuth, browser automation, credentials, sends,
approvals, or runtime execution.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "capability_skill_registry_metadata_delta_v0"
JSON_EXPORT_NAME = "capability_skill_registry_metadata_delta.json"
OPERATOR_EXPORT_NAME = "capability_skill_registry_metadata_delta_OPERATOR.md"

CAPABILITY_STATES = (
    "METADATA_ONLY",
    "READ_MODEL_VISIBLE",
    "REVIEW_PACKET_CAPABLE",
    "WORK_PACKET_CAPABLE",
    "PROOF_RAIL_CAPABLE",
    "APPROVAL_REQUEST_CAPABLE",
    "PROTECTED_ACCESS_GATED",
    "SECURITY_THRESHOLD_REQUIRED",
    "REFERENCE_ONLY",
    "UNSAFE_OR_BLOCKED",
    "UNKNOWN_FAIL_CLOSED",
)

NO_AUTHORITY_FLAGS = {
    "metadata_only": True,
    "metadata_only_registry": True,
    "tools_enabled": False,
    "agents_activated": False,
    "tool_activation_authority_added": False,
    "agent_activation_authority_added": False,
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
    "repo_b_modules_imported": False,
    "repo_b_code_migrated": False,
    "planner_builder_automation_activated": False,
    "repair_fix_loop_activated": False,
    "browser_automation_added": False,
    "oauth_access_enabled": False,
    "credentials_accessed": False,
    "credential_or_pii_access_added": False,
    "gmail_calendar_coupa_accessed": False,
    "telegram_send_triggered": False,
    "email_send_triggered": False,
    "approval_authority_added": False,
    "approval_receipt_created": False,
    "execution_authority_added": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "mission_control_app_changed": False,
    "security_pass_started": False,
    "client_deployment_authority_added": False,
    "unknown_capabilities_fail_closed": True,
}


@dataclass(frozen=True)
class SourceReadModel:
    key: str
    path: str
    role: str


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    display_name: str
    domain: str
    primary_state: str
    state_labels: tuple[str, ...]
    repo_a_evidence: tuple[str, ...]
    repo_b_delta_posture: str
    safe_routing_posture: str
    safe_to_route_as_work_packet_or_read_model_lane: bool
    requires_protected_access_gate: bool
    requires_guardian_gate: bool
    requires_security_threshold_before_live_use: bool
    blocked_authorities: tuple[str, ...]
    next_safe_lane: str
    operator_note: str


@dataclass(frozen=True)
class CapabilitySkillRegistryMetadataDeltaExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    capability_count: int
    metadata_only: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


SOURCE_READ_MODELS = (
    SourceReadModel("repo_a_known_rail_completion_map", "generated/read_models/repo_a_known_rail_completion_map.json", "Repo A rail baseline"),
    SourceReadModel("repo_b_remaining_capability_delta_map", "generated/read_models/repo_b_remaining_capability_delta_map.json", "Repo B delta read-model reference from Repo A only"),
    SourceReadModel("chief_role_capability_segmentation_map", "generated/read_models/chief_role_capability_segmentation_map.json", "Chief segmentation evidence"),
    SourceReadModel("chief_status_rail", "generated/read_models/chief_status_rail.json", "Chief safe status posture"),
    SourceReadModel("build_now_vs_hold_queue_posture", "generated/read_models/build_now_vs_hold_queue_posture.json", "build-now-vs-hold posture"),
    SourceReadModel("protected_access_broker_concept", "generated/read_models/protected_access_broker_concept.json", "protected access concept"),
    SourceReadModel("protected_evidence_reference_receipt", "generated/read_models/protected_evidence_reference_receipt.json", "protected reference receipt contract"),
    SourceReadModel("guardian_protected_access_gate_spec", "generated/read_models/guardian_protected_access_gate_spec.json", "Guardian protected-access gate"),
    SourceReadModel("cassandra_email_calendar_capability_reconciliation", "generated/read_models/cassandra_email_calendar_capability_reconciliation.json", "Cassandra email/calendar reconciliation"),
    SourceReadModel("cassandra_draft_review_packet", "generated/read_models/cassandra_draft_review_packet.json", "Cassandra draft review packet"),
    SourceReadModel("capital_hilton_send_approval_gate", "generated/read_models/capital_hilton_send_approval_gate.json", "Capital Hilton final-send gate"),
    SourceReadModel("capital_hilton_external_artifact_proof_capture", "generated/read_models/capital_hilton_external_artifact_proof_capture.json", "Capital Hilton proof rail"),
    SourceReadModel("guardian_draft_approval_request_contract", "generated/read_models/guardian_draft_approval_request_contract.json", "Guardian draft approval request contract"),
    SourceReadModel("tool_inventory", "generated/read_models/tool_inventory.json", "tool inventory metadata"),
    SourceReadModel("tool_intake", "generated/read_models/tool_intake.json", "tool intake metadata"),
    SourceReadModel("intent_router", "generated/read_models/intent_router.json", "operator intent routing metadata"),
    SourceReadModel("work_board", "generated/read_models/work_board.json", "work-board visibility"),
    SourceReadModel("agent_work_packets", "generated/read_models/agent_work_packets.json", "agent work packet metadata"),
    SourceReadModel("operator_actions", "generated/read_models/operator_actions.json", "operator action posture"),
    SourceReadModel("repo_a_known_legacy_capability_registry", "capability_registry.py", "legacy cross-agent capability registry code path"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _read_json_if_present(path: str | Path, *, repo_root: str | Path = ROOT) -> dict[str, Any]:
    target = _rooted(path, repo_root=repo_root)
    if not target.exists() or target.suffix.lower() != ".json":
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _source_record(source: SourceReadModel, *, repo_root: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    path = _rooted(source.path, repo_root=repo_root)
    is_repo_b_delta = source.key == "repo_b_remaining_capability_delta_map"
    return {
        "key": source.key,
        "path": source.path,
        "present": path.exists(),
        "schema_version": payload.get("schema_version") or payload.get("read_model_version"),
        "role": source.role,
        "truth_status": "repo_a_evidence_not_truth",
        "metadata_only": True,
        "repo_a_only": True,
        "repo_b_delta_read_model_used": is_repo_b_delta and bool(payload),
        "repo_b_filesystem_inspected": False,
        "repo_b_code_executed": False,
        "raw_private_content_read": False,
        "executed_or_dispatched": False,
    }


def _capability_specs() -> tuple[CapabilitySpec, ...]:
    return (
        CapabilitySpec(
            capability_id="cassandra_draft_review_email_calendar",
            display_name="Cassandra draft/review/email/calendar",
            domain="cassandra_comms",
            primary_state="REVIEW_PACKET_CAPABLE",
            state_labels=("READ_MODEL_VISIBLE", "REVIEW_PACKET_CAPABLE", "APPROVAL_REQUEST_CAPABLE", "PROTECTED_ACCESS_GATED", "SECURITY_THRESHOLD_REQUIRED"),
            repo_a_evidence=(
                "cassandra_draft_review_packet.json",
                "cassandra_email_calendar_capability_reconciliation.json",
                "guardian_draft_approval_request_contract.json",
            ),
            repo_b_delta_posture="partially_represented_live_email_calendar_oauth_blocked",
            safe_routing_posture="safe_as_review_packet_or_approval_request_contract_lane_only",
            safe_to_route_as_work_packet_or_read_model_lane=True,
            requires_protected_access_gate=True,
            requires_guardian_gate=True,
            requires_security_threshold_before_live_use=True,
            blocked_authorities=("Gmail draft creation", "email send", "calendar access", "OAuth", "Telegram notification", "runtime execution"),
            next_safe_lane="Cassandra Email Calendar Delta Detangle v0",
            operator_note="Cassandra may produce review/draft metadata; live account and send behavior remain blocked.",
        ),
        CapabilitySpec(
            capability_id="guardian_approval_hitl_protected_access",
            display_name="Guardian approval/HITL/protected-access",
            domain="guardian_safety",
            primary_state="APPROVAL_REQUEST_CAPABLE",
            state_labels=("READ_MODEL_VISIBLE", "APPROVAL_REQUEST_CAPABLE", "PROTECTED_ACCESS_GATED", "SECURITY_THRESHOLD_REQUIRED"),
            repo_a_evidence=(
                "guardian_responsibility_dna_audit.json",
                "guardian_draft_approval_request_contract.json",
                "guardian_protected_access_gate_spec.json",
            ),
            repo_b_delta_posture="legacy_hitl_paths_reference_only_current_contracts_non_executable",
            safe_routing_posture="safe_as_specific_approval_request_spec_or_guardian_gate_metadata",
            safe_to_route_as_work_packet_or_read_model_lane=True,
            requires_protected_access_gate=True,
            requires_guardian_gate=True,
            requires_security_threshold_before_live_use=True,
            blocked_authorities=("approval receipt creation", "live Guardian notification", "generic approval authority", "execution activation"),
            next_safe_lane="Guardian Approval Receipt Boundary v0",
            operator_note="Guardian can be modeled as a gatekeeper; approval, receipt, and execution remain distinct.",
        ),
        CapabilitySpec(
            capability_id="chief_status_work_packets_build_now_hold",
            display_name="Chief status/work packets/build-now-vs-hold",
            domain="chief_coordination",
            primary_state="WORK_PACKET_CAPABLE",
            state_labels=("READ_MODEL_VISIBLE", "WORK_PACKET_CAPABLE", "METADATA_ONLY"),
            repo_a_evidence=(
                "chief_status_rail.json",
                "build_now_vs_hold_queue_posture.json",
                "work_board.json",
                "agent_work_packets.json",
                "intent_router.json",
            ),
            repo_b_delta_posture="chief_orchestration_concepts_partially_represented_runtime_loops_blocked",
            safe_routing_posture="safe_as_coordination_status_work_packet_or_queue_posture_only",
            safe_to_route_as_work_packet_or_read_model_lane=True,
            requires_protected_access_gate=False,
            requires_guardian_gate=False,
            requires_security_threshold_before_live_use=True,
            blocked_authorities=("planner/builder automation", "repair loop", "Telegram send", "LLM/Ollama call", "arbitrary shell", "runtime execution"),
            next_safe_lane="Chief Domain Overlap Segmentation Review v0",
            operator_note="Chief is safe as coordination/status/work-packet substrate, not an executor.",
        ),
        CapabilitySpec(
            capability_id="niles_struna_music",
            display_name="Niles/Struna/music",
            domain="music_project",
            primary_state="READ_MODEL_VISIBLE",
            state_labels=("READ_MODEL_VISIBLE", "METADATA_ONLY"),
            repo_a_evidence=(
                "niles_album_review_packet.json",
                "niles_album_metadata_intake_packet.json",
                "struna_obscura_project_capsule.json",
            ),
            repo_b_delta_posture="music_producer_concepts_partially_or_read_model_represented",
            safe_routing_posture="safe_as_music_metadata_or_review_packet_lane_when bounded",
            safe_to_route_as_work_packet_or_read_model_lane=True,
            requires_protected_access_gate=False,
            requires_guardian_gate=False,
            requires_security_threshold_before_live_use=False,
            blocked_authorities=("producer bot send", "audio/file automation", "client/public release execution", "runtime agent activation"),
            next_safe_lane="Niles Struna Review Packet Rail v0",
            operator_note="Music rails are visible as packets/metadata; live producer/runtime behavior is not granted.",
        ),
        CapabilitySpec(
            capability_id="hermes_advisory",
            display_name="Hermes advisory synthesis",
            domain="advisory_synthesis",
            primary_state="METADATA_ONLY",
            state_labels=("METADATA_ONLY", "REFERENCE_ONLY"),
            repo_a_evidence=("repo_a_known_rail_completion_map.json", "repo_b_remaining_capability_delta_map.json"),
            repo_b_delta_posture="remembered_or_delta_surface_not_yet_steel_thread_complete",
            safe_routing_posture="safe_as_advisory_status_or_gap_scan_lane_only",
            safe_to_route_as_work_packet_or_read_model_lane=True,
            requires_protected_access_gate=False,
            requires_guardian_gate=False,
            requires_security_threshold_before_live_use=False,
            blocked_authorities=("live synthesis agent activation", "LLM/Ollama calls", "external research/tool execution"),
            next_safe_lane="Hermes Advisory Status Rail v0",
            operator_note="Hermes is known enough to track, not enough to activate.",
        ),
        CapabilitySpec(
            capability_id="report_bridge_client_reporting",
            display_name="Report Bridge/client reporting",
            domain="client_reporting",
            primary_state="READ_MODEL_VISIBLE",
            state_labels=("READ_MODEL_VISIBLE", "REVIEW_PACKET_CAPABLE", "METADATA_ONLY"),
            repo_a_evidence=("report_bridge.json", "project_capsules.json", "custom_build_module_detangling_contract.json"),
            repo_b_delta_posture="client_reporting_concepts_partially_represented_no_deployment",
            safe_routing_posture="safe_as_client_capsule_or_reporting_read_model_lane",
            safe_to_route_as_work_packet_or_read_model_lane=True,
            requires_protected_access_gate=False,
            requires_guardian_gate=False,
            requires_security_threshold_before_live_use=True,
            blocked_authorities=("customer deployment", "remote reporting node activation", "send/share authority", "credentialed client access"),
            next_safe_lane="Report Bridge Review Packet Rail v0",
            operator_note="Client reporting can be represented as packets/read-models; deployment remains blocked.",
        ),
        CapabilitySpec(
            capability_id="capital_hilton_finance_proof_request",
            display_name="Capital Hilton finance proof/request rails",
            domain="finance_capital_hilton",
            primary_state="PROOF_RAIL_CAPABLE",
            state_labels=("READ_MODEL_VISIBLE", "REVIEW_PACKET_CAPABLE", "PROOF_RAIL_CAPABLE", "APPROVAL_REQUEST_CAPABLE", "PROTECTED_ACCESS_GATED", "SECURITY_THRESHOLD_REQUIRED"),
            repo_a_evidence=(
                "capital_hilton_actionable_review_packet.json",
                "capital_hilton_external_artifact_proof_capture.json",
                "capital_hilton_send_approval_gate.json",
                "capital_hilton_operator_proof_input_packet.json",
            ),
            repo_b_delta_posture="capital_hilton_steel_thread_current_repo_a_canonical",
            safe_routing_posture="safe_as_review_proof_or_approval_request_contract_lane",
            safe_to_route_as_work_packet_or_read_model_lane=True,
            requires_protected_access_gate=True,
            requires_guardian_gate=True,
            requires_security_threshold_before_live_use=True,
            blocked_authorities=("Coupa submit", "browser automation", "Gmail/email send", "spreadsheet write", "credential/PII access", "payment status change"),
            next_safe_lane="Capital Hilton Protected Proof Intake Receipt v0",
            operator_note="Finance proof/request rails are useful, but final send/execution remains unavailable until proof and future gates exist.",
        ),
        CapabilitySpec(
            capability_id="tool_inventory_intake",
            display_name="Tool inventory/intake",
            domain="tool_metadata",
            primary_state="METADATA_ONLY",
            state_labels=("METADATA_ONLY", "READ_MODEL_VISIBLE"),
            repo_a_evidence=("tool_inventory.json", "tool_intake.json", "tool_inventory.py", "tool_intake.py"),
            repo_b_delta_posture="tool_and_skill_metadata_worth_bringing_forward_as_metadata_only",
            safe_routing_posture="safe_as_candidate_metadata_review_lane_only",
            safe_to_route_as_work_packet_or_read_model_lane=True,
            requires_protected_access_gate=False,
            requires_guardian_gate=False,
            requires_security_threshold_before_live_use=True,
            blocked_authorities=("tool execution", "tool installation", "network calls", "model runs", "containers", "runtime integration"),
            next_safe_lane="Tool Candidate Review Packet v0",
            operator_note="Tool records are observations/candidates, not approvals or live integrations.",
        ),
        CapabilitySpec(
            capability_id="operator_action_path",
            display_name="Operator action path",
            domain="operator_action",
            primary_state="APPROVAL_REQUEST_CAPABLE",
            state_labels=("READ_MODEL_VISIBLE", "APPROVAL_REQUEST_CAPABLE", "SECURITY_THRESHOLD_REQUIRED"),
            repo_a_evidence=("operator_actions.json", "operator_action.py", "operator_action_inbox.py", "operator_action_covenant.py"),
            repo_b_delta_posture="operator_action_concepts_repo_a_current_but_execution_separate",
            safe_routing_posture="safe_as_request_or_covenant_metadata_only",
            safe_to_route_as_work_packet_or_read_model_lane=True,
            requires_protected_access_gate=False,
            requires_guardian_gate=True,
            requires_security_threshold_before_live_use=True,
            blocked_authorities=("approval bypass", "execution path", "send/submit action", "runtime action dispatch"),
            next_safe_lane="Operator Action Receipt Boundary v0",
            operator_note="Action requests can be represented; approval receipts/execution are separate gates.",
        ),
        CapabilitySpec(
            capability_id="legacy_capability_registry_cross_agent_lookup",
            display_name="Legacy capability registry cross-agent lookup",
            domain="legacy_capability_metadata",
            primary_state="REFERENCE_ONLY",
            state_labels=("REFERENCE_ONLY", "METADATA_ONLY"),
            repo_a_evidence=("capability_registry.py", "chief_role_capability_segmentation_map.json"),
            repo_b_delta_posture="legacy_reference_or_repo_b_delta_evidence_only",
            safe_routing_posture="safe_only_as_legacy_evidence_to_compare_against_current_read_models",
            safe_to_route_as_work_packet_or_read_model_lane=False,
            requires_protected_access_gate=False,
            requires_guardian_gate=False,
            requires_security_threshold_before_live_use=True,
            blocked_authorities=("connected=True legacy claims as authority", "live broker/OAuth/email/calendar claims", "Chief/Cassandra execution claims"),
            next_safe_lane="Legacy Capability Registry Reconciliation v0",
            operator_note="Legacy registry claims are evidence to reconcile, not current authority.",
        ),
        CapabilitySpec(
            capability_id="planner_builder_automation_loops",
            display_name="Planner/builder automation loops",
            domain="automation",
            primary_state="UNSAFE_OR_BLOCKED",
            state_labels=("UNSAFE_OR_BLOCKED", "SECURITY_THRESHOLD_REQUIRED", "REFERENCE_ONLY"),
            repo_a_evidence=("repo_b_remaining_capability_delta_map.json", "build_now_vs_hold_queue_posture.json", "operator_sovereignty_power_stage_gate.json"),
            repo_b_delta_posture="repo_b_delta_reference_only_old_loops_blocked",
            safe_routing_posture="not_safe_to_activate; safe_only_as_future_security_threshold_planning_metadata",
            safe_to_route_as_work_packet_or_read_model_lane=False,
            requires_protected_access_gate=False,
            requires_guardian_gate=True,
            requires_security_threshold_before_live_use=True,
            blocked_authorities=("autonomous build execution", "agent activation", "shell execution", "repo mutation outside bounded lanes"),
            next_safe_lane="Planner Builder Safety Threshold Contract v0",
            operator_note="Automation loops remain blocked until explicit security/live-authority threshold work.",
        ),
        CapabilitySpec(
            capability_id="automatic_repair_loops",
            display_name="Automatic repair/fix loops",
            domain="automation_repair",
            primary_state="UNSAFE_OR_BLOCKED",
            state_labels=("UNSAFE_OR_BLOCKED", "SECURITY_THRESHOLD_REQUIRED", "REFERENCE_ONLY"),
            repo_a_evidence=("repo_b_remaining_capability_delta_map.json", "operator_sovereignty_power_stage_gate.json"),
            repo_b_delta_posture="repo_b_delta_reference_only_automatic_repair_blocked",
            safe_routing_posture="not_safe_to_activate; failures should become review packets not repairs",
            safe_to_route_as_work_packet_or_read_model_lane=False,
            requires_protected_access_gate=False,
            requires_guardian_gate=True,
            requires_security_threshold_before_live_use=True,
            blocked_authorities=("self-repair", "service restart", "runtime mutation", "unattended git/file changes"),
            next_safe_lane="Automatic Repair Threat Boundary v0",
            operator_note="Repair loops are intentionally not live; use receipts/read-models instead.",
        ),
        CapabilitySpec(
            capability_id="browser_oauth_credential_bridges",
            display_name="Browser/OAuth/credential bridges",
            domain="protected_access",
            primary_state="PROTECTED_ACCESS_GATED",
            state_labels=("PROTECTED_ACCESS_GATED", "SECURITY_THRESHOLD_REQUIRED", "UNSAFE_OR_BLOCKED", "REFERENCE_ONLY"),
            repo_a_evidence=("protected_access_broker_concept.json", "protected_evidence_reference_receipt.json", "guardian_protected_access_gate_spec.json"),
            repo_b_delta_posture="repo_b_delta_reference_only_oauth_tool_browser_credential_bridges_blocked",
            safe_routing_posture="safe_as_protected_access_gate_metadata_only",
            safe_to_route_as_work_packet_or_read_model_lane=False,
            requires_protected_access_gate=True,
            requires_guardian_gate=True,
            requires_security_threshold_before_live_use=True,
            blocked_authorities=("credential access", "OAuth", "browser automation", "Coupa/Gmail/calendar access", "tool bridge execution"),
            next_safe_lane="Protected Access Security Threshold Design v0",
            operator_note="Protected references can be tracked, but access/use remains blocked.",
        ),
        CapabilitySpec(
            capability_id="unknown_capability",
            display_name="Unknown or unclassified capability",
            domain="unknown",
            primary_state="UNKNOWN_FAIL_CLOSED",
            state_labels=("UNKNOWN_FAIL_CLOSED",),
            repo_a_evidence=(),
            repo_b_delta_posture="not_found_or_not_classified",
            safe_routing_posture="fail_closed_until_a_named_metadata_lane_classifies_it",
            safe_to_route_as_work_packet_or_read_model_lane=False,
            requires_protected_access_gate=True,
            requires_guardian_gate=True,
            requires_security_threshold_before_live_use=True,
            blocked_authorities=("all live authority", "tool activation", "agent activation", "private data access", "send/submit/runtime"),
            next_safe_lane="Capability Classification Intake v0",
            operator_note="Unknown capability surfaces must be classified before routing or use.",
        ),
    )


def _capability_record(spec: CapabilitySpec) -> dict[str, Any]:
    invalid = [state for state in (spec.primary_state, *spec.state_labels) if state not in CAPABILITY_STATES]
    if invalid:
        raise ValueError(f"unknown capability state(s): {invalid}")
    return {
        "capability_id": spec.capability_id,
        "display_name": spec.display_name,
        "domain": spec.domain,
        "primary_state": spec.primary_state,
        "state_labels": list(spec.state_labels),
        "repo_a_evidence": list(spec.repo_a_evidence),
        "repo_b_delta_posture": spec.repo_b_delta_posture,
        "safe_routing_posture": spec.safe_routing_posture,
        "safe_to_route_as_work_packet_or_read_model_lane": spec.safe_to_route_as_work_packet_or_read_model_lane,
        "requires_protected_access_gate": spec.requires_protected_access_gate,
        "requires_guardian_gate": spec.requires_guardian_gate,
        "requires_security_threshold_before_live_use": spec.requires_security_threshold_before_live_use,
        "blocked_authorities": list(spec.blocked_authorities),
        "activation_allowed_now": False,
        "execution_allowed_now": False,
        "tool_activation_allowed_now": False,
        "agent_activation_allowed_now": False,
        "approval_authority_added": False,
        "send_or_submit_authority_added": False,
        "runtime_authority_added": False,
        "unknown_fails_closed": spec.primary_state == "UNKNOWN_FAIL_CLOSED",
        "next_safe_lane": spec.next_safe_lane,
        "operator_note": spec.operator_note,
    }


def _state_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(record["primary_state"] for record in records)
    return {state: counts.get(state, 0) for state in CAPABILITY_STATES}


def _label_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        counts.update(record["state_labels"])
    return {state: counts.get(state, 0) for state in CAPABILITY_STATES}


def _safe_source_summary(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    repo_a = sources.get("repo_a_known_rail_completion_map", {})
    repo_b = sources.get("repo_b_remaining_capability_delta_map", {})
    return {
        "repo_a_known_rail_count": repo_a.get("known_rail_count", 0),
        "repo_a_schema_version": repo_a.get("schema_version"),
        "repo_b_delta_schema_version": repo_b.get("schema_version"),
        "repo_b_delta_reference_only": bool(repo_b.get("repo_b_reference_only", True)),
        "repo_b_code_executed": False,
        "repo_b_filesystem_inspected": False,
        "old_files_treated_as_evidence_not_truth": True,
    }


def _routing_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    safe = [
        record["capability_id"]
        for record in records
        if record["safe_to_route_as_work_packet_or_read_model_lane"]
    ]
    protected = [
        record["capability_id"]
        for record in records
        if record["requires_protected_access_gate"]
    ]
    security = [
        record["capability_id"]
        for record in records
        if record["requires_security_threshold_before_live_use"]
    ]
    blocked = [
        record["capability_id"]
        for record in records
        if record["primary_state"] in {"UNSAFE_OR_BLOCKED", "UNKNOWN_FAIL_CLOSED"}
    ]
    return {
        "safe_work_packet_or_read_model_lane_capabilities": safe,
        "protected_access_gated_capabilities": protected,
        "security_threshold_required_capabilities": security,
        "blocked_or_fail_closed_capabilities": blocked,
        "safe_routing_is_execution_authority": False,
        "tool_or_agent_activation_allowed_from_registry": False,
    }


def _eli5_summary() -> dict[str, Any]:
    return {
        "what_openclaw_knows_how_to_talk_about": (
            "Here is what OpenClaw knows how to talk about: Cassandra review/email/calendar, Guardian approvals, "
            "Chief work packets, Capital Hilton finance proof, Niles/music, Hermes, Report Bridge, tools, and operator actions."
        ),
        "what_can_become_a_safe_packet_or_rail": (
            "Capital Hilton, Cassandra draft review, Guardian request specs, Chief status/work packets, Report Bridge, "
            "and Niles-style project packets can become safe read-model or review lanes when scoped."
        ),
        "what_is_only_metadata_right_now": (
            "Tool inventory/intake, Hermes, legacy capability registry claims, and Repo B-derived concepts are metadata or reference only."
        ),
        "what_is_blocked_until_security_live_authority_work": (
            "Planner/builder loops, repair loops, browser/OAuth/credential bridges, live Gmail/calendar/Coupa access, sends, submits, "
            "agent activation, and runtime execution are blocked until security/live-authority work."
        ),
        "what_should_not_be_activated": (
            "Do not activate tools, agents, Repo B code, old live loops, LLM/Ollama, OAuth, browser, credentials, send paths, or repair loops."
        ),
        "next_1_to_3_sensible_lanes": [
            "Cassandra Email Calendar Delta Detangle v0",
            "Chief Domain Overlap Segmentation Review v0",
            "Niles Struna Review Packet Rail v0",
        ],
    }


def build_capability_skill_registry_metadata_delta(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    sources = {
        source.key: _read_json_if_present(source.path, repo_root=repo_root)
        for source in SOURCE_READ_MODELS
    }
    source_records = [
        _source_record(source, repo_root=repo_root, payload=sources[source.key])
        for source in SOURCE_READ_MODELS
    ]
    records = [_capability_record(spec) for spec in _capability_specs()]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "registry_delta_status": "metadata_only_capability_skill_registry_delta",
        "purpose": "Classify known, partial, blocked, reference-only, and future-gated OpenClaw capability/skill surfaces as metadata only.",
        "capability_states": list(CAPABILITY_STATES),
        "capability_count": len(records),
        "capability_records": records,
        "primary_state_counts": _state_counts(records),
        "state_label_counts": _label_counts(records),
        "routing_summary": _routing_summary(records),
        "repo_a_baseline_summary": _safe_source_summary(sources),
        "repo_b_delta_handling": {
            "used_existing_repo_a_delta_read_model_only": bool(sources.get("repo_b_remaining_capability_delta_map")),
            "repo_b_derived_items_remain_reference_only_unless_promoted": True,
            "repo_b_filesystem_inspected": False,
            "repo_b_code_executed": False,
            "repo_b_modules_imported": False,
            "repo_b_code_migrated": False,
        },
        "source_read_models": source_records,
        "operator_eli5_summary": _eli5_summary(),
        "legacy_capability_registry_posture": {
            "path": "capability_registry.py",
            "treated_as": "legacy_reference_evidence_not_canonical_authority",
            "connected_true_claims_promoted": False,
            "requires_reconciliation_before_use": True,
        },
        "blocked_capability_posture": {
            "planner_builder_automation_loops_blocked": True,
            "automatic_repair_loops_blocked": True,
            "browser_oauth_credential_bridges_blocked": True,
            "unknown_capabilities_fail_closed": True,
        },
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "next_recommended_lane": "Cassandra Email Calendar Delta Detangle v0",
    }


def format_capability_skill_registry_metadata_delta(payload: dict[str, Any]) -> str:
    eli5 = payload["operator_eli5_summary"]
    lines = [
        "# Capability Skill Registry Metadata Delta v0",
        "",
        "Status:",
        "- Registry posture: metadata-only.",
        f"- Capability records: `{payload['capability_count']}`.",
        "- Tools enabled: `false`.",
        "- Agents activated: `false`.",
        "- Repo B code executed: `false`.",
        "- Runtime/send/submit/approval authority added: `false`.",
        "",
        "## ELI5 Summary",
        f"- {eli5['what_openclaw_knows_how_to_talk_about']}",
        f"- {eli5['what_can_become_a_safe_packet_or_rail']}",
        f"- {eli5['what_is_only_metadata_right_now']}",
        f"- {eli5['what_is_blocked_until_security_live_authority_work']}",
        f"- {eli5['what_should_not_be_activated']}",
        "",
        "## Capability State Counts",
    ]
    for state in CAPABILITY_STATES:
        lines.append(f"- `{state}`: {payload['primary_state_counts'].get(state, 0)} primary / {payload['state_label_counts'].get(state, 0)} labels")
    lines.extend(["", "## Safe Packet / Read-Model Routes"])
    for capability_id in payload["routing_summary"]["safe_work_packet_or_read_model_lane_capabilities"]:
        lines.append(f"- `{capability_id}`")
    lines.extend(["", "## Protected / Security-Gated"])
    for capability_id in payload["routing_summary"]["protected_access_gated_capabilities"]:
        lines.append(f"- `{capability_id}`")
    for capability_id in payload["routing_summary"]["security_threshold_required_capabilities"]:
        if capability_id not in payload["routing_summary"]["protected_access_gated_capabilities"]:
            lines.append(f"- `{capability_id}`")
    lines.extend(["", "## Blocked Or Fail-Closed"])
    for capability_id in payload["routing_summary"]["blocked_or_fail_closed_capabilities"]:
        lines.append(f"- `{capability_id}`")
    lines.extend(["", "## Boundaries"])
    lines.extend(
        [
            "- No tools, agents, browser/OAuth/credentials, sends, approvals, Repo B execution, planner/builder, repair, or runtime authority were activated.",
            "- Legacy capability-registry claims are reference evidence only, not current authority.",
            "- Unknown capability surfaces fail closed.",
            "",
            f"Next safe lane: {payload['next_recommended_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_capability_skill_registry_metadata_delta(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> CapabilitySkillRegistryMetadataDeltaExportResult:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_capability_skill_registry_metadata_delta(repo_root=root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capability_skill_registry_metadata_delta(payload), encoding="utf-8")
    return CapabilitySkillRegistryMetadataDeltaExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        capability_count=len(payload["capability_records"]),
        metadata_only=payload["metadata_only"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export capability/skill registry metadata delta read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capability_skill_registry_metadata_delta(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    root = _rooted(args.export_root, repo_root=args.repo_root)
    if args.format == "json":
        print((root / JSON_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print((root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    else:
        print(stable_json(result.__dict__), end="")
    return 0 if result.schema_version == SCHEMA_VERSION else 1


__all__ = [
    "CAPABILITY_STATES",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_capability_skill_registry_metadata_delta",
    "export_capability_skill_registry_metadata_delta",
    "format_capability_skill_registry_metadata_delta",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
