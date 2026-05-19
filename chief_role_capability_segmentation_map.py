"""Chief role and capability segmentation map v0.

This module builds a Repo A evidence-grounded map of what Chief is currently
safe to claim. It does not import Chief runtime modules, inspect Repo B
directly, run listeners/watchers/LLM services, or grant execution authority.
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

from post_preflight_batch_gate import PASS, evaluate_post_preflight_lane


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "chief_role_capability_segmentation_map_v0"
JSON_EXPORT_NAME = "chief_role_capability_segmentation_map.json"
OPERATOR_EXPORT_NAME = "chief_role_capability_segmentation_map_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_REPO_A_BASELINE_PATH = DEFAULT_EXPORT_ROOT / "repo_a_known_rail_completion_map.json"
DEFAULT_REPO_B_DELTA_PATH = DEFAULT_EXPORT_ROOT / "repo_b_remaining_capability_delta_map.json"

CLASSIFICATIONS = (
    "PROVEN_CANONICAL",
    "TESTED_SUPPORTING_CONTRACT",
    "PARTIALLY_REPRESENTED",
    "INFERRED_NOT_PROVEN",
    "OPERATOR_MEMORY_ONLY",
    "SEGMENTATION_REQUIRED",
    "LEGACY_OR_REFERENCE",
    "UNSAFE_OR_BLOCKED",
    "UNKNOWN_NEEDS_REVIEW",
)

NO_AUTHORITY_FLAGS = {
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
    "chief_runtime_modules_imported": False,
    "chief_modeled_as_executor": False,
    "execution_authority_added": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "approval_execution_authority_added": False,
    "browser_or_coupa_authority_added": False,
    "credential_or_pii_access_added": False,
    "planner_builder_automation_activated": False,
    "repair_fix_loop_activated": False,
    "telegram_send_triggered": False,
    "telegram_notification_live": False,
    "llm_ollama_called": False,
    "llm_ollama_authority_added": False,
    "tool_or_browser_authority_added": False,
    "gmail_calendar_coupa_credentials_accessed": False,
    "arbitrary_shell_allowed": False,
    "mission_control_app_changed": False,
    "security_pass_started": False,
    "client_deployment_authority_added": False,
    "old_files_treated_as_truth": False,
}


@dataclass(frozen=True)
class EvidenceSpec:
    path: str
    role: str
    evidence_type: str
    truth_status: str = "repo_a_evidence_not_truth"
    body_read: bool = False


@dataclass(frozen=True)
class ChiefSubAreaSpec:
    sub_area_id: str
    display_name: str
    classification: str
    claim_level: str
    evidence: tuple[EvidenceSpec, ...]
    proven_current_repo_a_behavior: tuple[str, ...]
    inferred_role_from_filenames_or_contracts: tuple[str, ...]
    operator_memory_guidance: tuple[str, ...]
    repo_b_delta_reference_ids: tuple[str, ...]
    overlaps: tuple[str, ...]
    authority_boundary: str
    blocked_or_future_gated: tuple[str, ...]
    next_safe_lane: str
    needs_operator_memory_review: bool = False
    ready_for_status_rail: bool = False


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
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _spec(
    path: str,
    role: str,
    evidence_type: str,
    truth_status: str = "repo_a_evidence_not_truth",
) -> EvidenceSpec:
    return EvidenceSpec(
        path=path,
        role=role,
        evidence_type=evidence_type,
        truth_status=truth_status,
        body_read=False,
    )


def _evidence_record(spec: EvidenceSpec, *, repo_root: str | Path) -> dict[str, Any]:
    path = _rooted(spec.path, repo_root=repo_root)
    return {
        "path": spec.path,
        "present": path.exists(),
        "role": spec.role,
        "evidence_type": spec.evidence_type,
        "truth_status": spec.truth_status,
        "repo_a_only": True,
        "body_read": spec.body_read,
    }


def _sub_area_specs() -> tuple[ChiefSubAreaSpec, ...]:
    return (
        ChiefSubAreaSpec(
            sub_area_id="chief_identity_role_boundaries",
            display_name="Chief identity / role / boundaries",
            classification="SEGMENTATION_REQUIRED",
            claim_level="proven_partial_inferred_broad",
            evidence=(
                _spec("agent_lane_registry.py", "canonical lane seed for Chief role and authority", "code_metadata"),
                _spec("generated/read_models/repo_a_known_rail_completion_map.json", "Repo A rail baseline", "read_model", "read_model_evidence_not_truth"),
                _spec("generated/read_models/repo_b_remaining_capability_delta_map.json", "Repo B delta baseline", "read_model", "read_model_evidence_not_truth"),
            ),
            proven_current_repo_a_behavior=(
                "Agent Lane Registry describes Chief as request-only coordination that can prepare plans, routing decisions, and Codex work packets.",
                "Repo A rail map classifies Chief orchestration/work packets as visible but not authority-ready.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "Chief appears to be a coordination spine across status, routing, work packets, and domain-specific brains.",
                "Chief should not be collapsed to only planner unless a later rail proves that narrower identity.",
            ),
            operator_memory_guidance=(
                "Older memory suggests Chief may have been a central listener/router/session/approval/domain-brain system.",
            ),
            repo_b_delta_reference_ids=("chief_orchestrator_planner_status",),
            overlaps=("Cassandra", "Guardian", "Niles", "Report Bridge", "Mission Control", "custom-build"),
            authority_boundary="Chief may be represented as coordination/status/planning substrate only; executor authority fails closed.",
            blocked_or_future_gated=("direct execution", "approval decisions", "live runtime control", "client deployment"),
            next_safe_lane="Chief Status Rail Completion v0",
            needs_operator_memory_review=True,
            ready_for_status_rail=True,
        ),
        ChiefSubAreaSpec(
            sub_area_id="chief_listener_router_session",
            display_name="Chief listener / router / session concepts",
            classification="LEGACY_OR_REFERENCE",
            claim_level="repo_a_files_present_but_live_runtime_blocked",
            evidence=(
                _spec("chief_listener.py", "legacy/live-adjacent Telegram listener", "code_path"),
                _spec("chief_router.py", "legacy router importing many runtime brains", "code_path"),
                _spec("chief_session_manager.py", "legacy session state helper", "code_path"),
                _spec("generated/read_models/active_machinery_high_risk_quarantine.json", "warning-only machinery read-model", "read_model", "read_model_evidence_not_truth"),
            ),
            proven_current_repo_a_behavior=(
                "Chief listener/router/session files exist in Repo A.",
                "Active machinery read-models classify Chief listener surfaces as warning-only/high-risk rather than canonical live authority.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "The filenames imply an older Telegram-to-router-to-session flow.",
            ),
            operator_memory_guidance=(
                "Older memory map names Telegram to Chief Listener to Chief Router to Chief Session Manager.",
            ),
            repo_b_delta_reference_ids=("chief_orchestrator_planner_status",),
            overlaps=("Telegram intake", "Cassandra intake", "Guardian", "work packets"),
            authority_boundary="Existing listener/router/session files are evidence/reference unless later gated; this map does not run them.",
            blocked_or_future_gated=("Telegram replies", "route_message runtime", "session mutation as authority", "systemd listener activation"),
            next_safe_lane="Chief Listener Router Reference Disposition v0",
            needs_operator_memory_review=True,
        ),
        ChiefSubAreaSpec(
            sub_area_id="chief_status_posture",
            display_name="Chief status posture",
            classification="PARTIALLY_REPRESENTED",
            claim_level="partially_proven_read_model_gap",
            evidence=(
                _spec("generated/read_models/work_board.json", "work board visibility", "read_model", "read_model_evidence_not_truth"),
                _spec("generated/read_models/agent_work_packets.json", "agent work packet visibility", "read_model", "read_model_evidence_not_truth"),
                _spec("generated/read_models/intent_router.json", "intent route visibility", "read_model", "read_model_evidence_not_truth"),
                _spec("generated/read_models/repo_b_remaining_capability_delta_map.json", "Chief status delta recommendation", "read_model", "read_model_evidence_not_truth"),
            ),
            proven_current_repo_a_behavior=(
                "Work Board, Agent Work Packet, and Intent Router read-models contain Chief-routed planning/status artifacts.",
                "Repo B delta recommends Chief status/readiness semantics as the next safe harvest, not runtime brains.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "Chief status likely needs a separate rail because status is spread across work board, packets, intent routing, and old Chief files.",
            ),
            operator_memory_guidance=(
                "Chief may have been where real work flowed, but Repo A has not yet completed a single Chief status proof rail.",
            ),
            repo_b_delta_reference_ids=("chief_orchestrator_planner_status",),
            overlaps=("work_board", "agent_work_packet", "intent_router", "Mission Control"),
            authority_boundary="Status visibility only; no work execution, service control, or live notification.",
            blocked_or_future_gated=("live status daemon", "automatic status push", "runtime watcher"),
            next_safe_lane="Chief Status Rail Completion v0",
            ready_for_status_rail=True,
        ),
        ChiefSubAreaSpec(
            sub_area_id="chief_work_packets",
            display_name="Chief work packets",
            classification="TESTED_SUPPORTING_CONTRACT",
            claim_level="proven_control_plane_artifact",
            evidence=(
                _spec("work_board.py", "safe work board control-plane module", "code_metadata"),
                _spec("agent_work_packet.py", "safe agent work packet module", "code_metadata"),
                _spec("generated/read_models/work_board.json", "work board read-model", "read_model", "read_model_evidence_not_truth"),
                _spec("generated/read_models/agent_work_packets.json", "agent work packet read-model", "read_model", "read_model_evidence_not_truth"),
                _spec("tests/test_work_board.py", "work board tests", "test"),
                _spec("tests/test_agent_work_packet.py", "agent packet tests", "test"),
            ),
            proven_current_repo_a_behavior=(
                "Work Board and Agent Work Packet modules explicitly deny direct execution, agent activation, model calls, and tool execution.",
                "Generated read-models show Chief-routed cards/packets as planning artifacts.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "Chief appears connected to bounded planning/work packet flow rather than execution authority.",
            ),
            operator_memory_guidance=(
                "This may be the safer Repo A replacement for older Chief flow-through work machinery.",
            ),
            repo_b_delta_reference_ids=("chief_orchestrator_planner_status", "dropped_intent_task_queue_timing"),
            overlaps=("Chief status", "operator intent routing", "Codex work", "Mission Control"),
            authority_boundary="Work packets are review/planning artifacts; they do not execute commands or activate agents.",
            blocked_or_future_gated=("auto-execute", "agent activation", "model/tool execution", "approval bypass"),
            next_safe_lane="Chief Status Rail Completion v0",
            ready_for_status_rail=True,
        ),
        ChiefSubAreaSpec(
            sub_area_id="operator_intent_routing",
            display_name="Operator intent routing",
            classification="TESTED_SUPPORTING_CONTRACT",
            claim_level="proven_non_executing_route_contract",
            evidence=(
                _spec("intent_router.py", "deterministic non-executing intent router", "code_metadata"),
                _spec("operator_intent_core.py", "surface-neutral intent classifier", "code_metadata"),
                _spec("generated/read_models/intent_router.json", "intent router read-model", "read_model", "read_model_evidence_not_truth"),
                _spec("tests/test_operator_intent_core.py", "intent core tests", "test"),
            ),
            proven_current_repo_a_behavior=(
                "Intent Router records deterministic routes to agent lanes and denies direct execution, model execution, tool execution, and approval bypass.",
                "Intent Router maps the phrase Chief to the Chief lane for routing, not execution.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "Chief is one target in a broader operator-intent routing substrate.",
            ),
            operator_memory_guidance=(
                "Cassandra may have accessed Chief flow indirectly through routing rather than owning the flow.",
            ),
            repo_b_delta_reference_ids=("dropped_intent_task_queue_timing", "brain_dump_inbox_parser"),
            overlaps=("Cassandra", "work_board", "agent_lane_registry", "operator_action"),
            authority_boundary="Routing metadata only; unknown authority fails closed.",
            blocked_or_future_gated=("action auto-create", "approval auto-execute", "runtime command dispatch"),
            next_safe_lane="Build Now Vs Hold Queue Posture v0",
            ready_for_status_rail=True,
        ),
        ChiefSubAreaSpec(
            sub_area_id="build_now_vs_hold_queue_posture",
            display_name="Build-now-vs-hold queue posture",
            classification="PARTIALLY_REPRESENTED",
            claim_level="concept_partly_represented_execution_blocked",
            evidence=(
                _spec("generated/read_models/dropped_intents.json", "dropped intent visibility", "read_model", "read_model_evidence_not_truth"),
                _spec("queue_balancer.py", "legacy queue balancer path", "code_path", "legacy_or_reference_evidence_only"),
                _spec("queue_validator.py", "legacy queue validator path", "code_path", "legacy_or_reference_evidence_only"),
                _spec("generated/read_models/repo_b_remaining_capability_delta_map.json", "queue timing delta", "read_model", "read_model_evidence_not_truth"),
            ),
            proven_current_repo_a_behavior=(
                "Dropped Intent read-model tracks deferred/unresolved operator directions as metadata.",
                "Repo B delta identifies queue timing as worth bringing forward as decision support only.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "Old queue files imply timing and workload-balancing concepts, but not safe current authority.",
            ),
            operator_memory_guidance=(
                "The remembered build-now-vs-hold workflow may belong under Chief status/queue posture.",
            ),
            repo_b_delta_reference_ids=("dropped_intent_task_queue_timing", "automatic_fix_repair_loops"),
            overlaps=("dropped_intents", "work_board", "planner_builder_guardrails"),
            authority_boundary="Queue posture may classify work timing; it must not generate or run work automatically.",
            blocked_or_future_gated=("queue auto-generation", "polish loop activation", "cron/supervisor execution"),
            next_safe_lane="Build Now Vs Hold Queue Posture v0",
            needs_operator_memory_review=True,
            ready_for_status_rail=True,
        ),
        ChiefSubAreaSpec(
            sub_area_id="brain_dump_cue_parser_intake",
            display_name="Brain-dump / cue parser intake",
            classification="LEGACY_OR_REFERENCE",
            claim_level="legacy_file_present_safe_governance_not_complete",
            evidence=(
                _spec("brain_dump_parser.py", "legacy parser with LLM/file movement behavior", "code_path", "legacy_or_reference_evidence_only"),
                _spec("dropped_intent_registry.py", "governed dropped intent metadata registry", "code_metadata"),
                _spec("generated/read_models/dropped_intents.json", "dropped intent read-model", "read_model", "read_model_evidence_not_truth"),
            ),
            proven_current_repo_a_behavior=(
                "Dropped Intent Registry is metadata/read-model only and denies autonomous prompting, model calls, notifications, and raw private scans.",
                "A legacy brain dump parser exists but is not proven as a governed current rail.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "Cue parsing likely overlaps with Chief intake and queue posture.",
            ),
            operator_memory_guidance=(
                "Older memory mentions brain-dump/cue parsing as part of the work intake environment.",
            ),
            repo_b_delta_reference_ids=("brain_dump_inbox_parser",),
            overlaps=("operator_intent", "dropped_intents", "Chief status"),
            authority_boundary="Use only governed metadata/intents until a cue parser rail proves boundaries.",
            blocked_or_future_gated=("broad Markdown ingestion", "Ollama parsing", "file moves", "raw note truth promotion"),
            next_safe_lane="Governed Cue Parser Delta v0",
            needs_operator_memory_review=True,
        ),
        ChiefSubAreaSpec(
            sub_area_id="planner_builder_coordination",
            display_name="Planner/builder coordination",
            classification="UNSAFE_OR_BLOCKED",
            claim_level="guardrail_only_until_security_threshold",
            evidence=(
                _spec("generated/read_models/active_machinery_block_later_guardrail.json", "block-later machinery guardrails", "read_model", "read_model_evidence_not_truth"),
                _spec("generated/read_models/repo_a_known_rail_completion_map.json", "planner/builder guardrail baseline", "read_model", "read_model_evidence_not_truth"),
                _spec("polish_loop/orchestrator.py", "legacy/high-risk orchestrator path", "code_path", "legacy_or_reference_evidence_only"),
            ),
            proven_current_repo_a_behavior=(
                "Repo A active-machinery guardrails mark high-risk surfaces as warning/read-model only.",
                "Repo A known rail map says planner/builder automation guardrails are not ready for authority.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "Chief may be adjacent to planner/builder coordination, but current proof is guardrail-only.",
            ),
            operator_memory_guidance=(
                "Older memory suggests deterministic and agentic planner/builder automation existed around Chief.",
            ),
            repo_b_delta_reference_ids=("planner_builder_automation_loops",),
            overlaps=("Chief", "Codex", "builder", "active_machinery", "operator_sovereignty"),
            authority_boundary="Planner/builder coordination remains blocked until later authority/security threshold work.",
            blocked_or_future_gated=("agentic builder loop", "runner activation", "tool/model execution", "self-repair"),
            next_safe_lane="Planner Builder Status Contract v0",
            needs_operator_memory_review=True,
        ),
        ChiefSubAreaSpec(
            sub_area_id="automatic_fix_repair_loop_concepts",
            display_name="Automatic fix / repair loop concepts",
            classification="UNSAFE_OR_BLOCKED",
            claim_level="unsafe_reference_only",
            evidence=(
                _spec("generated/read_models/active_machinery_quarantine_decision_packet.json", "quarantine decision packet", "read_model", "read_model_evidence_not_truth"),
                _spec("generated/read_models/operator_sovereignty_power_stage_gate.json", "power-stage gate", "read_model", "read_model_evidence_not_truth"),
                _spec("queue_balancer.py", "legacy queue automation concept", "code_path", "legacy_or_reference_evidence_only"),
            ),
            proven_current_repo_a_behavior=(
                "Operator Sovereignty gate blocks higher-power runtime/automation until controls exist.",
                "Active machinery quarantine rails keep high-risk machinery warning-only.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "Queue and repair-loop concepts may exist as old automation ideas, not current safe behavior.",
            ),
            operator_memory_guidance=(
                "Older automatic fix loops may have been part of the older Chief/planner ecosystem.",
            ),
            repo_b_delta_reference_ids=("automatic_fix_repair_loops",),
            overlaps=("planner_builder_coordination", "operator_sovereignty", "active_machinery"),
            authority_boundary="Automatic repair is not modeled as current Chief authority.",
            blocked_or_future_gated=("self-repair", "auto mutation", "unattended test/fix loop", "service restart"),
            next_safe_lane="Automatic Repair Loop Contract Harvest v0",
            needs_operator_memory_review=True,
        ),
        ChiefSubAreaSpec(
            sub_area_id="capability_skill_registry_metadata",
            display_name="Capability / skill registry metadata",
            classification="PARTIALLY_REPRESENTED",
            claim_level="metadata_only_partially_represented",
            evidence=(
                _spec("module_registry.py", "module planning registry", "code_metadata"),
                _spec("capability_registry.py", "legacy capability registry", "code_path", "legacy_or_reference_evidence_only"),
                _spec("custom_build_module_detangling_contract.py", "custom-build detangling contract", "code_metadata"),
                _spec("generated/read_models/repo_b_remaining_capability_delta_map.json", "capability registry delta", "read_model", "read_model_evidence_not_truth"),
            ),
            proven_current_repo_a_behavior=(
                "Module Registry is planning-only and grants no runtime/tool/deployment/network/model/agent authority.",
                "Custom-build detangling contract treats capabilities as modular planning substrate.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "Chief may need capability metadata to route work without loading executable skills.",
            ),
            operator_memory_guidance=(
                "Older memory names many domain brains; a safe registry could describe them without activating them.",
            ),
            repo_b_delta_reference_ids=("capability_skill_registry",),
            overlaps=("module_registry", "custom_build", "Chief domains", "Report Bridge"),
            authority_boundary="Capability registry metadata may inform routing; executable skill loading remains blocked.",
            blocked_or_future_gated=("skill execution", "tool execution", "runtime plugin loading"),
            next_safe_lane="Capability Skill Registry Metadata Delta v0",
            needs_operator_memory_review=True,
            ready_for_status_rail=True,
        ),
        ChiefSubAreaSpec(
            sub_area_id="protected_access_broker_concepts",
            display_name="Protected access / broker concepts",
            classification="UNSAFE_OR_BLOCKED",
            claim_level="future_stage_3_or_4_only",
            evidence=(
                _spec("generated/read_models/operator_sovereignty_power_stage_gate.json", "power-stage gate", "read_model", "read_model_evidence_not_truth"),
                _spec("generated/read_models/cassandra_email_calendar_capability_reconciliation.json", "email/calendar boundary", "read_model", "read_model_evidence_not_truth"),
            ),
            proven_current_repo_a_behavior=(
                "Operator Sovereignty gate blocks credential/PII broker and browser automation controls until future stages.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "Protected access may eventually support Chief-routed work, but current Chief should not access secrets.",
            ),
            operator_memory_guidance=(
                "Older memory and Repo B delta mention protected access/OAuth/PII concepts.",
            ),
            repo_b_delta_reference_ids=("oauth_tool_browser_credential_bridges", "pii_vault_protected_broker_concept"),
            overlaps=("Guardian", "Cassandra", "finance", "operator_sovereignty"),
            authority_boundary="No credentials, OAuth, browser, or private data access are available to Chief.",
            blocked_or_future_gated=("credential access", "PII broker", "OAuth", "browser automation"),
            next_safe_lane="Protected Access Broker Concept Delta v0",
        ),
        ChiefSubAreaSpec(
            sub_area_id="telegram_notification_concepts",
            display_name="Telegram / notification concepts",
            classification="UNSAFE_OR_BLOCKED",
            claim_level="legacy_live_adjacency_blocked",
            evidence=(
                _spec("chief_notify.py", "legacy Telegram notification path", "code_path", "legacy_or_reference_evidence_only"),
                _spec("chief_sender.py", "legacy sender path", "code_path", "legacy_or_reference_evidence_only"),
                _spec("generated/read_models/active_machinery_high_risk_quarantine.json", "notification surfaces warning-only", "read_model", "read_model_evidence_not_truth"),
            ),
            proven_current_repo_a_behavior=(
                "Active machinery quarantine identifies Chief sender/listener surfaces as high-risk warning-only.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "Legacy Chief could notify/push via Telegram, but that is not current safe authority.",
            ),
            operator_memory_guidance=(
                "Older memory mentions chief_notify.py and Telegram push.",
            ),
            repo_b_delta_reference_ids=("chief_orchestrator_planner_status", "guardian_legacy_approval_hitl"),
            overlaps=("Telegram", "Guardian", "Cassandra"),
            authority_boundary="No live Chief Telegram notification or send path is granted.",
            blocked_or_future_gated=("Telegram send", "Guardian live notification", "reply authority", "service activation"),
            next_safe_lane="Chief Notification Boundary Review v0",
        ),
        ChiefSubAreaSpec(
            sub_area_id="llm_ollama_service_concepts",
            display_name="LLM / Ollama service concepts",
            classification="UNSAFE_OR_BLOCKED",
            claim_level="legacy_service_concept_blocked",
            evidence=(
                _spec("chief_llm.py", "legacy LLM helper path", "code_path", "legacy_or_reference_evidence_only"),
                _spec("brain_dump_parser.py", "legacy Ollama caller path", "code_path", "legacy_or_reference_evidence_only"),
                _spec("generated/read_models/operator_sovereignty_power_stage_gate.json", "power-stage gate", "read_model", "read_model_evidence_not_truth"),
            ),
            proven_current_repo_a_behavior=(
                "Work packet and intent-router rails deny model execution authority.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "Old Chief code appears to include LLM/Ollama helper concepts.",
            ),
            operator_memory_guidance=(
                "Older memory map includes Chief LLM / Ollama service.",
            ),
            repo_b_delta_reference_ids=("planner_builder_automation_loops", "brain_dump_inbox_parser"),
            overlaps=("brain_dump", "planner_builder", "operator_sovereignty"),
            authority_boundary="No LLM/Ollama call is part of current Chief proof.",
            blocked_or_future_gated=("Ollama call", "model execution", "tool-augmented LLM flow"),
            next_safe_lane="Chief LLM Boundary Contract v0",
        ),
        ChiefSubAreaSpec(
            sub_area_id="domain_brain_overlaps",
            display_name="Domain brain overlaps",
            classification="SEGMENTATION_REQUIRED",
            claim_level="many_domain_paths_memory_guidance_only_until_subrails",
            evidence=(
                _spec("chief_album_brain.py", "legacy album domain path", "code_path", "legacy_or_reference_evidence_only"),
                _spec("chief_financial_brain.py", "legacy finance domain path", "code_path", "legacy_or_reference_evidence_only"),
                _spec("chief_email_brain.py", "legacy communications domain path", "code_path", "legacy_or_reference_evidence_only"),
                _spec("generated/read_models/niles_album_review_packet.json", "Niles music read-model evidence", "read_model", "read_model_evidence_not_truth"),
                _spec("generated/read_models/capital_hilton_actionable_review_packet.json", "finance read-model evidence", "read_model", "read_model_evidence_not_truth"),
                _spec("generated/read_models/cassandra_draft_review_packet.json", "communications read-model evidence", "read_model", "read_model_evidence_not_truth"),
            ),
            proven_current_repo_a_behavior=(
                "Repo A has separate safer rails for Niles/music, Capital Hilton finance, and Cassandra communications.",
                "Chief domain brain files exist but are not the canonical authority for those current rails.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "Chief may historically have coordinated many domains; current Repo A should split those overlaps into bounded rails.",
            ),
            operator_memory_guidance=(
                "Older memory names domain brains for album production, finance, marketing, communications, health, infrastructure, website, research, analytics, consulting, Fundo, and Trinity audit.",
            ),
            repo_b_delta_reference_ids=("niles_music_producer_album", "budget_tracker_finance_legacy", "report_bridge_client_company_reporting"),
            overlaps=("Niles", "Capital Hilton finance", "Cassandra", "Report Bridge", "custom-build", "website"),
            authority_boundary="Domain overlaps should route to their governed rails; legacy domain brains remain evidence/reference.",
            blocked_or_future_gated=("domain brain activation", "raw creative/client scans", "finance/spreadsheet execution"),
            next_safe_lane="Chief Domain Overlap Segmentation Review v0",
            needs_operator_memory_review=True,
        ),
        ChiefSubAreaSpec(
            sub_area_id="mission_control_visibility",
            display_name="Mission Control visibility",
            classification="PARTIALLY_REPRESENTED",
            claim_level="read_model_visibility_no_app_change",
            evidence=(
                _spec("generated/read_models/work_board.json", "work board app-consumable read-model", "read_model", "read_model_evidence_not_truth"),
                _spec("generated/read_models/agent_work_packets.json", "agent packet app-consumable read-model", "read_model", "read_model_evidence_not_truth"),
                _spec("generated/read_models/sync_health.json", "mirror trust read-model", "read_model", "read_model_evidence_not_truth"),
            ),
            proven_current_repo_a_behavior=(
                "Repo A emits Chief-adjacent read-models that can be mirrored as visibility artifacts.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "Chief-specific Mission Control status likely needs a future read-model surface rather than app changes in this lane.",
            ),
            operator_memory_guidance=(
                "Winship needs to know where work should flow without staring at backend plumbing.",
            ),
            repo_b_delta_reference_ids=("chief_orchestrator_planner_status",),
            overlaps=("Mission Control", "sync/mirror trust", "work board"),
            authority_boundary="Visibility only; no Mission Control execution path is added.",
            blocked_or_future_gated=("app action buttons", "service controls", "send/submit controls"),
            next_safe_lane="Chief Status Rail Completion v0",
            ready_for_status_rail=True,
        ),
        ChiefSubAreaSpec(
            sub_area_id="execution_security_threshold_boundaries",
            display_name="Execution/security-threshold boundaries",
            classification="UNSAFE_OR_BLOCKED",
            claim_level="explicitly_future_threshold",
            evidence=(
                _spec("generated/read_models/operator_sovereignty_power_stage_gate.json", "operator sovereignty stage gate", "read_model", "read_model_evidence_not_truth"),
                _spec("generated/read_models/repo_a_known_rail_completion_map.json", "known rails maturity baseline", "read_model", "read_model_evidence_not_truth"),
                _spec("generated/read_models/repo_b_remaining_capability_delta_map.json", "Repo B delta boundary", "read_model", "read_model_evidence_not_truth"),
            ),
            proven_current_repo_a_behavior=(
                "Current OpenClaw power stage is visibility/read-model/review-packet oriented.",
                "Repo A and Repo B maps both say live execution/security threshold work is future, not current.",
            ),
            inferred_role_from_filenames_or_contracts=(
                "Chief might eventually coordinate higher-power workflows, but only after separate gated authority lanes.",
            ),
            operator_memory_guidance=(
                "Operator wants the broader system raised to known steel-thread maturity before real live authority.",
            ),
            repo_b_delta_reference_ids=("planner_builder_automation_loops", "oauth_tool_browser_credential_bridges"),
            overlaps=("Guardian", "operator_sovereignty", "active_machinery", "Estate node registry"),
            authority_boundary="Unknown Chief authority fails closed; this map is not a security pass.",
            blocked_or_future_gated=("live execution", "browser/Coupa", "credentials", "approval execution", "client deployment", "autonomous repair"),
            next_safe_lane="Chief Status Rail Completion v0",
        ),
    )


def _sub_area_record(spec: ChiefSubAreaSpec, *, repo_root: str | Path) -> dict[str, Any]:
    if spec.classification not in CLASSIFICATIONS:
        raise ValueError(f"unsupported Chief classification: {spec.classification}")
    return {
        "sub_area_id": spec.sub_area_id,
        "display_name": spec.display_name,
        "classification": spec.classification,
        "claim_level": spec.claim_level,
        "evidence_sources": [_evidence_record(item, repo_root=repo_root) for item in spec.evidence],
        "proven_current_repo_a_behavior": list(spec.proven_current_repo_a_behavior),
        "inferred_role_from_filenames_or_contracts": list(spec.inferred_role_from_filenames_or_contracts),
        "operator_memory_guidance": list(spec.operator_memory_guidance),
        "repo_b_delta_reference_ids": list(spec.repo_b_delta_reference_ids),
        "overlaps": list(spec.overlaps),
        "authority_boundary": spec.authority_boundary,
        "blocked_or_future_gated": list(spec.blocked_or_future_gated),
        "next_safe_lane": spec.next_safe_lane,
        "needs_operator_memory_review": spec.needs_operator_memory_review,
        "ready_for_status_rail": spec.ready_for_status_rail,
        "unknown_authority_fails_closed": True,
        "chief_executor_authority": False,
        "live_runtime_authority": False,
    }


def _baseline_excerpt(baseline: dict[str, Any]) -> dict[str, Any]:
    rails = baseline.get("rails", [])
    chief_rails = [
        {
            "rail_id": item.get("rail_id"),
            "rail_name": item.get("rail_name"),
            "maturity": item.get("maturity"),
            "steel_thread_stage_reached": item.get("steel_thread_stage_reached"),
            "authority_boundary": item.get("authority_boundary"),
        }
        for item in rails
        if "chief" in str(item.get("rail_id", "")).lower()
        or "chief" in str(item.get("rail_name", "")).lower()
    ]
    return {
        "present": bool(baseline),
        "schema_version": baseline.get("schema_version"),
        "known_rail_count": baseline.get("known_rail_count", 0),
        "chief_related_rails": chief_rails,
        "security_pass_current": bool(baseline.get("security_pass_current", False)),
        "live_workflow_ready_count": (baseline.get("readiness_counts") or {}).get("live_workflow", 0),
    }


def _repo_b_delta_excerpt(delta: dict[str, Any]) -> dict[str, Any]:
    capabilities = delta.get("capability_delta_list", [])
    interesting_ids = {
        "chief_orchestrator_planner_status",
        "dropped_intent_task_queue_timing",
        "brain_dump_inbox_parser",
        "planner_builder_automation_loops",
        "automatic_fix_repair_loops",
        "capability_skill_registry",
        "oauth_tool_browser_credential_bridges",
        "pii_vault_protected_broker_concept",
        "niles_music_producer_album",
        "budget_tracker_finance_legacy",
        "report_bridge_client_company_reporting",
        "guardian_legacy_approval_hitl",
    }
    selected = [
        {
            "capability_id": item.get("capability_id"),
            "classification": item.get("classification"),
            "short_description": item.get("short_description"),
            "authority_risk": item.get("authority_risk"),
            "suggested_future_lane": item.get("suggested_future_lane"),
            "reference_only": bool(item.get("reference_only", True)),
            "repo_b_body_read": bool(item.get("repo_b_body_read", False)),
            "repo_b_code_executed": bool(item.get("repo_b_code_executed", False)),
        }
        for item in capabilities
        if item.get("capability_id") in interesting_ids
    ]
    return {
        "present": bool(delta),
        "schema_version": delta.get("schema_version"),
        "repo_b_reference_only": bool(delta.get("repo_b_reference_only", True)),
        "repo_b_filesystem_reinspected_by_this_lane": False,
        "selected_capabilities": selected,
    }


def _recommendations() -> list[dict[str, Any]]:
    lanes = (
        (
            "Chief Status Rail Completion v0",
            "Turn the segmented Chief status evidence into one review-only Chief status/readiness packet.",
            "Winship needs truthful Chief status/readiness without running Chief.",
            "chief_status_readiness_gap",
            "chief_role_capability_segmentation_map_v0",
            "Reusable status/readiness substrate for broad coordination rails.",
            "Chief status read-model and operator packet with runtime blocked.",
        ),
        (
            "Build Now Vs Hold Queue Posture v0",
            "Model build-now-vs-hold timing from dropped-intent/work-board evidence without executing queues.",
            "Winship needs deferred ideas separated from work that is ready to build.",
            "queue_timing_decision_gap",
            "dropped_intents_work_board_read_models",
            "Reusable timing posture for Chief/work-board planning.",
            "Queue posture read-model showing build-now, hold, and memory-review buckets.",
        ),
        (
            "Chief Domain Overlap Segmentation Review v0",
            "Split Chief domain-brain overlaps into owned rails like Cassandra, Niles, finance, Report Bridge, and custom-build.",
            "Winship needs old Chief domain concepts mapped to current steel-thread rails.",
            "chief_domain_overlap_gap",
            "chief_role_capability_segmentation_map_v0",
            "Reusable overlap mapping that prevents old Chief domain brains from becoming default authority.",
            "Domain-overlap read-model with future rail ownership recommendations.",
        ),
    )
    recommendations: list[dict[str, Any]] = []
    for lane_name, summary, workflow, bottleneck, contract, substrate, proof in lanes:
        gate = evaluate_post_preflight_lane(
            lane_name=lane_name,
            lane_summary=summary,
            named_operator_workflow=workflow,
            shared_bottleneck=bottleneck,
            steel_thread_contract_link=contract,
            reusable_substrate_improvement=substrate,
            workflow_proof_output=proof,
            detangling_scope={
                "serves_lane_directly": True,
                "opportunistic_only": True,
                "physical_module_extraction_requested": False,
                "client_repo_generation_requested": False,
                "detangling_required_before_workflow_proof": False,
                "notes": "Segment Chief role safely before any runtime or module extraction work.",
            },
            module_split_disposition={
                "disposition": "record_future_work",
                "recorded_future_work": True,
                "reason": "Chief sub-rails should be recorded and lifted incrementally, not extracted or activated here.",
            },
            authority_change_requested={
                "requested": False,
                "authority_types": [],
                "reason": "Read-model/contract/status work only.",
            },
            expected_artifacts=[
                {"artifact_kind": "read_model", "path_or_contract": "generated/read_models/<future>.json"},
                {"artifact_kind": "operator_packet", "path_or_contract": "generated/read_models/<future>_OPERATOR.md"},
                {"artifact_kind": "test_proof", "path_or_contract": "focused tests"},
            ],
            validation_required=("focused tests", "JSON validation", "authority flags"),
            synthetic_example=False,
        )
        recommendations.append(
            {
                "lane_name": lane_name,
                "why_next": summary,
                "post_preflight_batch_gate_evaluation": gate,
            }
        )
    return recommendations


def _eli5_summary(
    *,
    sub_areas: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    proven = [
        item["display_name"]
        for item in sub_areas
        if item["classification"] in {"PROVEN_CANONICAL", "TESTED_SUPPORTING_CONTRACT", "PARTIALLY_REPRESENTED"}
    ]
    blocked = [
        item["display_name"]
        for item in sub_areas
        if item["classification"] in {"UNSAFE_OR_BLOCKED", "LEGACY_OR_REFERENCE"}
    ]
    memory = [
        item["display_name"]
        for item in sub_areas
        if item["needs_operator_memory_review"] or item["classification"] == "OPERATOR_MEMORY_ONLY"
    ]
    return {
        "summary_text": (
            "Repo A proves pieces of Chief, not one finished Chief rail. The safest current read is that Chief is "
            "a coordination/status/work-packet area: it can be represented in routing, Work Board, and packet "
            "read-models, but it is not proven as a live executor. The older memory map points to a much larger "
            "Chief with listeners, sessions, domain brains, notifications, LLMs, and workers. Those ideas should be "
            "split into sub-rails before anything runs."
        ),
        "what_chief_is_proven_to_be_in_repo_a": (
            "A request-only coordination and planning lane with work-board, intent-routing, and agent-work-packet evidence."
        ),
        "what_chief_might_be_but_is_not_yet_proven": (
            "A broader central orchestration spine spanning listener/router/session/status/domain-brain concepts."
        ),
        "can_chief_be_completed_as_one_rail_now": False,
        "safe_help_now": (
            "Use Chief-adjacent read-models for status, routing, deferred-work posture, and bounded work packets."
        ),
        "cannot_do_yet": (
            "No live Telegram push, LLM/Ollama calls, watcher loops, arbitrary shell, planner/builder automation, "
            "approval execution, credentials, or repair loops."
        ),
        "older_repo_b_vault_map_implication": (
            "The old map looks like a dense multi-domain Chief system; Repo A should harvest concepts through bounded "
            "sub-rails, not treat the old shape as current truth."
        ),
        "tracked_or_partially_tracked": proven,
        "blocked_or_reference_only": blocked,
        "needs_winship_memory_review": memory,
        "next_1_to_3_chief_lanes": [item["lane_name"] for item in recommendations[:3]],
    }


def build_chief_role_capability_segmentation_map(
    *,
    repo_root: str | Path = ROOT,
    repo_a_baseline_json: str | Path = DEFAULT_REPO_A_BASELINE_PATH,
    repo_b_delta_json: str | Path = DEFAULT_REPO_B_DELTA_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    baseline = _read_json_if_present(repo_a_baseline_json, repo_root=repo_root)
    repo_b_delta = _read_json_if_present(repo_b_delta_json, repo_root=repo_root)
    sub_areas = [
        _sub_area_record(spec, repo_root=repo_root)
        for spec in _sub_area_specs()
    ]
    classification_counts = Counter(item["classification"] for item in sub_areas)
    claim_level_counts = Counter(item["claim_level"] for item in sub_areas)
    recommendations = _recommendations()
    gate_pass_count = sum(
        1
        for item in recommendations
        if item["post_preflight_batch_gate_evaluation"]["gate_status"] == PASS
    )
    proven = [
        item
        for item in sub_areas
        if item["classification"] in {"PROVEN_CANONICAL", "TESTED_SUPPORTING_CONTRACT", "PARTIALLY_REPRESENTED"}
    ]
    inferred = [
        item
        for item in sub_areas
        if item["classification"] in {"INFERRED_NOT_PROVEN", "SEGMENTATION_REQUIRED"}
    ]
    memory_only = [
        item
        for item in sub_areas
        if item["needs_operator_memory_review"] or item["operator_memory_guidance"]
    ]
    unsafe = [
        item
        for item in sub_areas
        if item["classification"] in {"UNSAFE_OR_BLOCKED", "LEGACY_OR_REFERENCE"}
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "path_used": "Path B - Chief Role + Capability Segmentation Map",
        "path_a_smallest_status_rail_completed": False,
        "path_b_segmentation_map_used": True,
        "chief_complete_as_one_rail_now": False,
        "segmentation_required": True,
        "repo_a_only_inspection": True,
        "repo_b_delta_read_model_used": bool(repo_b_delta),
        "repo_b_filesystem_inspected": False,
        "repo_a_baseline": _baseline_excerpt(baseline),
        "repo_b_delta_reference": _repo_b_delta_excerpt(repo_b_delta),
        "classification_labels": list(CLASSIFICATIONS),
        "classification_counts": dict(sorted(classification_counts.items())),
        "claim_level_counts": dict(sorted(claim_level_counts.items())),
        "chief_sub_area_count": len(sub_areas),
        "chief_sub_areas": sub_areas,
        "proven_current_repo_a_behavior": proven,
        "inferred_not_proven": inferred,
        "operator_memory_or_repo_b_vault_map_guidance": memory_only,
        "unsafe_or_blocked": unsafe,
        "unknown_authority_fails_closed": True,
        "work_packets_are_visibility_review_planning_only": True,
        "old_automation_fix_loop_concepts_blocked": True,
        "telegram_notification_concepts_non_live": True,
        "llm_ollama_tool_concepts_non_live": True,
        "security_pass_current": False,
        "live_execution_recommended": False,
        "future_lane_recommendations": recommendations,
        "recommended_next_lanes_all_gate_pass": gate_pass_count == len(recommendations),
        "operator_eli5_summary": _eli5_summary(
            sub_areas=sub_areas,
            recommendations=recommendations,
        ),
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_chief_role_capability_segmentation_map(payload: dict[str, Any]) -> str:
    eli5 = payload["operator_eli5_summary"]
    lines = [
        "# Chief Role + Capability Segmentation Map v0",
        "",
        "Status:",
        f"- Path used: `{payload['path_used']}`.",
        f"- Chief complete as one rail now: `{str(payload['chief_complete_as_one_rail_now']).lower()}`.",
        f"- Chief sub-areas mapped: `{payload['chief_sub_area_count']}`.",
        "- Repo B filesystem inspected: `false`.",
        "- Live execution recommended: `false`.",
        "",
        "## ELI5 Summary",
        eli5["summary_text"],
        "",
        "What Chief is proven to be in Repo A:",
        f"- {eli5['what_chief_is_proven_to_be_in_repo_a']}",
        "",
        "What Chief might be, but is not proven yet:",
        f"- {eli5['what_chief_might_be_but_is_not_yet_proven']}",
        "",
        "Safe help now:",
        f"- {eli5['safe_help_now']}",
        "",
        "Cannot do yet:",
        f"- {eli5['cannot_do_yet']}",
        "",
        "## Classification Counts",
    ]
    for classification, count in payload["classification_counts"].items():
        lines.append(f"- `{classification}`: {count}")
    lines.extend(["", "## Proven Or Partially Tracked"])
    for item in eli5["tracked_or_partially_tracked"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Blocked Or Reference-Only"])
    for item in eli5["blocked_or_reference_only"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Needs Winship Memory Review"])
    for item in eli5["needs_winship_memory_review"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Recommended Next Chief Lanes"])
    for item in payload["future_lane_recommendations"]:
        gate = item["post_preflight_batch_gate_evaluation"]
        lines.append(f"- `{item['lane_name']}`: gate `{gate['gate_status']}` - {item['why_next']}")
    lines.extend(
        [
            "",
            "## Boundaries",
            "- Chief is not modeled as an executor.",
            "- Work packets remain visibility/review/planning artifacts.",
            "- Old listener/router/session/notification/LLM/fix-loop concepts remain reference-only or future-gated.",
            "- No runtime, send, approval execution, browser, credential, model, or client deployment authority was added.",
        ]
    )
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class ChiefRoleCapabilitySegmentationMapExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    path_used: str
    chief_sub_area_count: int
    runtime_authority_added: bool
    send_or_submit_authority_added: bool
    repo_b_filesystem_inspected: bool


def export_chief_role_capability_segmentation_map(
    *,
    repo_root: str | Path = ROOT,
    repo_a_baseline_json: str | Path = DEFAULT_REPO_A_BASELINE_PATH,
    repo_b_delta_json: str | Path = DEFAULT_REPO_B_DELTA_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ChiefRoleCapabilitySegmentationMapExportResult:
    root = Path(repo_root)
    out_dir = root / export_root
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_chief_role_capability_segmentation_map(
        repo_root=repo_root,
        repo_a_baseline_json=repo_a_baseline_json,
        repo_b_delta_json=repo_b_delta_json,
        generated_at=generated_at,
    )
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_chief_role_capability_segmentation_map(payload), encoding="utf-8")
    return ChiefRoleCapabilitySegmentationMapExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        path_used=payload["path_used"],
        chief_sub_area_count=payload["chief_sub_area_count"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload.get("send_or_submit_authority_added", False),
        repo_b_filesystem_inspected=payload["repo_b_filesystem_inspected"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Chief role/capability segmentation map.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--repo-a-baseline-json", default=str(DEFAULT_REPO_A_BASELINE_PATH), help="Repo A rail baseline JSON.")
    parser.add_argument("--repo-b-delta-json", default=str(DEFAULT_REPO_B_DELTA_PATH), help="Repo B delta read-model JSON.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator"), default="operator", help="Print JSON or operator Markdown.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_chief_role_capability_segmentation_map(
        repo_root=args.repo_root,
        repo_a_baseline_json=args.repo_a_baseline_json,
        repo_b_delta_json=args.repo_b_delta_json,
        export_root=args.export_root,
    )
    root = Path(args.repo_root)
    export_root = root / args.export_root
    output_path = export_root / (JSON_EXPORT_NAME if args.format == "json" else OPERATOR_EXPORT_NAME)
    print(output_path.read_text(encoding="utf-8"), end="")
    return 0 if result.schema_version == SCHEMA_VERSION else 1


if __name__ == "__main__":
    raise SystemExit(main())
