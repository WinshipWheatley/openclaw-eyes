"""Agent Identity + Actor Router Contract v0 for OpenClaw.

This read-model defines deterministic actor/agent identity and routing metadata
before any agent-platform behavior can become executable. It does not call
models, activate agents, run tools, access accounts, handle credentials, mutate
Mission Control, or create runtime routing authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "agent_identity_actor_router_contract_v0"
JSON_EXPORT_NAME = "agent_identity_actor_router_contract.json"
OPERATOR_EXPORT_NAME = "agent_identity_actor_router_contract_OPERATOR.md"

ACTOR_CLASSES = (
    "human_operator",
    "governed_agent",
    "implementation_worker",
    "advisory_actor",
)

ROUTING_MODES = (
    "single_actor_review",
    "paired_review",
    "group_review",
    "all_agent_review",
    "implementation_worker_lane",
    "operator_only_decision",
)

CLEARANCE_LEVELS = (
    "operator_final_authority",
    "public_or_repo_safe",
    "internal_operator_safe",
    "sensitive_metadata_only",
    "protected_context_required_future_gate",
    "blocked_no_go",
)

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "activation_allowed": False,
    "model_call_authority": False,
    "agent_call_authority": False,
    "external_tool_authority": False,
    "credential_authority": False,
    "actor_self_authority": False,
    "routing_execution_authority": False,
    "operator_final_authority": True,
    "browser_oauth_account_access_enabled": False,
    "gmail_calendar_coupa_telegram_enabled": False,
    "send_submit_approval_enabled": False,
    "network_execution_enabled": False,
    "runtime_daemon_enabled": False,
    "hidden_memory_capture_enabled": False,
    "background_surveillance_enabled": False,
    "pc_c_drive_artifact_write_allowed": False,
    "mission_control_app_authority_added": False,
}

GLOBAL_BLOCKED_ACTOR_AUTHORITIES = (
    "self-assign clearance, tools, memory, workspace, or authority",
    "call a model or agent from this contract",
    "activate a tool protocol, plugin, browser, OAuth, Gmail, calendar, Coupa, or Telegram bridge",
    "send, submit, approve, mutate accounts, or perform external actions",
    "handle, request, persist, or infer credentials",
    "run background surveillance, hidden memory capture, or broad file indexing",
    "write OpenClaw artifacts to PC C: drive",
    "convert future-gated package preview into live dispatch",
)


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    path: str
    role: str


@dataclass(frozen=True)
class ActorIdentity:
    actor_id: str
    display_name: str
    actor_class: str
    primary_role: str
    suitable_domains: tuple[str, ...]
    unsuitable_domains: tuple[str, ...]
    can_receive_packages: bool
    package_types: tuple[str, ...]
    allowed_current_actions: tuple[str, ...]
    blocked_current_actions: tuple[str, ...]
    future_model_guidance: str
    future_tool_guidance: str
    clearance_level: str
    requires_operator_preview: bool
    requires_guardian_gate: bool
    notes_for_mission_control: str


@dataclass(frozen=True)
class RoutingRule:
    rule_id: str
    trigger: str
    primary_actor_ids: tuple[str, ...]
    secondary_actor_ids: tuple[str, ...]
    routing_mode: str
    deterministic_order: tuple[str, ...]
    why: str
    execution_boundary: str


@dataclass(frozen=True)
class RecommendedLane:
    lane_id: str
    title: str
    priority: str
    why_next: str
    hard_boundary: str


@dataclass(frozen=True)
class AgentIdentityActorRouterExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    actor_count: int
    routing_rule_count: int
    runtime_authority_added: bool
    model_call_authority_added: bool


EVIDENCE_SOURCES = (
    EvidenceSource(
        "agent_platform_alignment",
        "generated/read_models/agent_platform_alignment.json",
        "upstream alignment lane that identified this actor/router contract as next safe work",
    ),
    EvidenceSource(
        "package_compiler_contract",
        "generated/read_models/package_compiler_contract.json",
        "deterministic package schema, boundary validation, and preview-only package posture",
    ),
    EvidenceSource(
        "operator_workbench_actor_host_registry",
        "generated/read_models/operator_workbench_actor_host_registry.json",
        "workbench/actor host metadata and conservative autonomy levels",
    ),
    EvidenceSource(
        "capability_skill_registry_metadata_delta",
        "generated/read_models/capability_skill_registry_metadata_delta.json",
        "capability/skill metadata; descriptive only, not tool authority",
    ),
    EvidenceSource(
        "guardian_protected_access_gate_spec",
        "generated/read_models/guardian_protected_access_gate_spec.json",
        "protected access and authority gate posture",
    ),
    EvidenceSource(
        "cassandra_email_calendar_delta_detangle",
        "generated/read_models/cassandra_email_calendar_delta_detangle.json",
        "Cassandra communication/calendar visibility boundary",
    ),
    EvidenceSource(
        "operator_nested_lane_mission_package_spine",
        "generated/read_models/operator_nested_lane_mission_package_spine.json",
        "nested lane and actor/agent/package doctrine",
    ),
    EvidenceSource(
        "agent_platform_alignment_operator_output",
        "generated/read_models/agent_platform_alignment_OPERATOR.md",
        "human-readable upstream lane output",
    ),
)

ACTORS = (
    ActorIdentity(
        actor_id="operator_winship",
        display_name="Operator / Winship",
        actor_class="human_operator",
        primary_role="final human authority and memory comparison source",
        suitable_domains=(
            "final decisions",
            "operator memory comparison",
            "authority grant or denial",
            "taste/product judgment",
        ),
        unsuitable_domains=("automated execution", "hidden background processing"),
        can_receive_packages=True,
        package_types=(
            "operator_decision_package",
            "authority_review_package",
            "memory_comparison_package",
            "package_preview_review",
        ),
        allowed_current_actions=(
            "inspect package preview",
            "compare system map against memory",
            "approve future lane scope outside this contract",
            "keep work parked or request further classification",
        ),
        blocked_current_actions=(
            "this contract cannot execute operator approval",
            "this contract cannot send, submit, or mutate accounts",
        ),
        future_model_guidance="Human authority is not a model actor.",
        future_tool_guidance="Operator may later authorize tools through explicit gates; no automatic tool grant exists here.",
        clearance_level="operator_final_authority",
        requires_operator_preview=False,
        requires_guardian_gate=False,
        notes_for_mission_control="Final action authority remains with Winship; operator memory can identify gaps but is not machine proof.",
    ),
    ActorIdentity(
        actor_id="chief",
        display_name="Chief",
        actor_class="governed_agent",
        primary_role="coordination, work-board, check-engine, and queue posture",
        suitable_domains=("Build", "Operations", "System Health", "Work Board", "Check Engine"),
        unsuitable_domains=("protected access approval", "private content access without Guardian", "creative taste final authority"),
        can_receive_packages=True,
        package_types=(
            "check_light_diagnostic_package",
            "helm_lane_awareness_package",
            "workbench_actor_review_package",
            "verification_review_package",
        ),
        allowed_current_actions=("receive package preview", "explain current work posture", "recommend safe diagnostic detour"),
        blocked_current_actions=("runtime repair", "queue execution", "delete/remount/credential handling", "agent activation"),
        future_model_guidance="Use a planning/coordination-capable model only after package compiler and security gates validate authority.",
        future_tool_guidance="Inspect-only diagnostics first; no repair tools without future receipts and operator/Guardian gates.",
        clearance_level="internal_operator_safe",
        requires_operator_preview=True,
        requires_guardian_gate=False,
        notes_for_mission_control="Route work-board, check-engine, and build coordination questions to Chief first.",
    ),
    ActorIdentity(
        actor_id="guardian",
        display_name="Guardian",
        actor_class="governed_agent",
        primary_role="safety, security, protected access, approval, and authority boundaries",
        suitable_domains=("Security", "Authority Boundary", "Protected Access", "Approval Gates", "Risk Review"),
        unsuitable_domains=("creative production", "routine implementation without risk", "finance facts without source proof"),
        can_receive_packages=True,
        package_types=(
            "authority_review_package",
            "protected_access_review_package",
            "security_boundary_review_package",
            "verification_review_package",
        ),
        allowed_current_actions=("review authority metadata", "fail closed on ambiguity", "state blocked actions"),
        blocked_current_actions=("grant live access", "handle credentials", "approve sends/submits from this contract"),
        future_model_guidance="Use a careful risk review model class; unavailable/unknown model fails closed.",
        future_tool_guidance="Guardian can review tool requests later; tool execution remains blocked here.",
        clearance_level="protected_context_required_future_gate",
        requires_operator_preview=True,
        requires_guardian_gate=True,
        notes_for_mission_control="Safety, approval, protected data, and unclear authority route Guardian first.",
    ),
    ActorIdentity(
        actor_id="cassandra",
        display_name="Cassandra",
        actor_class="governed_agent",
        primary_role="communications, email/calendar review, and finance/AP-facing workflow visibility",
        suitable_domains=("Communications", "Finance", "Operations", "AP Review", "Email/Calendar Review"),
        unsuitable_domains=("autonomous send", "calendar mutation", "credentialed account operation"),
        can_receive_packages=True,
        package_types=(
            "communications_review_package",
            "finance_ap_review_package",
            "calendar_context_review_package",
            "world_lane_work_package",
        ),
        allowed_current_actions=("review/draft visibility package", "classify finance/AP context", "surface missing proof"),
        blocked_current_actions=("send email", "mutate calendar", "open Gmail/Coupa/OAuth", "approve payments"),
        future_model_guidance="Use a communications/detail-oriented model only through package preview and Guardian gates when sensitive.",
        future_tool_guidance="Email/calendar/Coupa tools remain blocked until explicit adapter registry and security audit.",
        clearance_level="sensitive_metadata_only",
        requires_operator_preview=True,
        requires_guardian_gate=True,
        notes_for_mission_control="Route communications, finance/AP, email, and calendar review to Cassandra; add Guardian when approval/protected access appears.",
    ),
    ActorIdentity(
        actor_id="hermes",
        display_name="Hermes",
        actor_class="advisory_actor",
        primary_role="systems review, architecture, doctrine, horizon checks, and coherence review",
        suitable_domains=("Architecture", "Doctrine", "Research", "Horizon Checks", "System Coherence"),
        unsuitable_domains=("final approval", "credentials", "live implementation", "private data ingestion"),
        can_receive_packages=True,
        package_types=(
            "doctrine_review_package",
            "architecture_review_package",
            "horizon_check_package",
            "all_agent_review_package",
        ),
        allowed_current_actions=("review package preview", "surface system-level tradeoffs", "recommend next lane"),
        blocked_current_actions=("execute code", "call tools", "assert live facts without proof", "grant authority"),
        future_model_guidance="Use a broad-reasoning advisory model; pair with Chief for system build posture.",
        future_tool_guidance="No tools by default; use read-model/proof references only.",
        clearance_level="internal_operator_safe",
        requires_operator_preview=True,
        requires_guardian_gate=False,
        notes_for_mission_control="Route big-picture doctrine/app architecture/system coherence to Hermes, often paired with Chief.",
    ),
    ActorIdentity(
        actor_id="niles",
        display_name="Niles",
        actor_class="governed_agent",
        primary_role="music, art, producer, and creative operator context",
        suitable_domains=("Music / Art", "Struna", "Album Metadata", "Creative Production", "Producer Workflow"),
        unsuitable_domains=("backend implementation", "security approval", "finance/AP execution"),
        can_receive_packages=True,
        package_types=(
            "world_lane_work_package",
            "music_metadata_review_package",
            "creative_context_package",
            "confidence_detour_package",
        ),
        allowed_current_actions=("review creative/music package metadata", "identify missing album/project context", "recommend creative detour"),
        blocked_current_actions=("publish/release/send", "mutate catalog data", "call music services", "execute code"),
        future_model_guidance="Use creative/domain-fit model candidates once source context and proof boundaries are defined.",
        future_tool_guidance="Music/art tools remain future-gated and receipt-backed.",
        clearance_level="internal_operator_safe",
        requires_operator_preview=True,
        requires_guardian_gate=False,
        notes_for_mission_control="Route music/art/Struna/creative production to Niles first; use Codex only for implementation lanes.",
    ),
    ActorIdentity(
        actor_id="codex",
        display_name="Codex",
        actor_class="implementation_worker",
        primary_role="scoped implementation worker for backend/code/test lanes",
        suitable_domains=("Build", "Backend", "Tests", "Read-Models", "Xcode/Swift when explicitly scoped"),
        unsuitable_domains=("final product authority", "credentialed integrations", "autonomous business actions"),
        can_receive_packages=True,
        package_types=(
            "code_implementation_package",
            "verification_review_package",
            "read_model_contract_package",
            "mac_app_validation_package",
        ),
        allowed_current_actions=("receive scoped package", "edit files inside explicit workspace", "run focused tests when prompted"),
        blocked_current_actions=("self-expand workspace", "activate external services", "handle credentials", "send/submit/approve"),
        future_model_guidance="Use coding-strong model candidates; package must define paths, tests, stop conditions, and receipts.",
        future_tool_guidance="Shell/file/test tools only when manually invoked in bounded workspace; Mission Control does not launch Codex here.",
        clearance_level="public_or_repo_safe",
        requires_operator_preview=True,
        requires_guardian_gate=False,
        notes_for_mission_control="Route implementation lanes to Codex only through scoped package compiler boundaries.",
    ),
    ActorIdentity(
        actor_id="gemini_antigravity",
        display_name="Gemini / Antigravity",
        actor_class="implementation_worker",
        primary_role="scoped implementation, refactor, proof, planner/verifier worker",
        suitable_domains=("Build", "Verification", "Refactor", "Fast Planning", "Proof Review"),
        unsuitable_domains=("security final authority", "credentials", "legal/sensitive final review", "unbounded shell administration"),
        can_receive_packages=True,
        package_types=(
            "verification_review_package",
            "code_implementation_package",
            "workbench_actor_review_package",
            "confidence_detour_package",
        ),
        allowed_current_actions=("receive explicit bounded package", "perform scoped review/refactor when separately invoked"),
        blocked_current_actions=("autonomous infrastructure administration", "credential handling", "out-of-workspace state transfer", "self-granted tools"),
        future_model_guidance="Gemini/Antigravity candidates can be strong fast workers; selection must be deterministic and package-bound.",
        future_tool_guidance="Can receive scoped workspace access only when the lane/package explicitly grants it; default ambiguous lanes fail closed.",
        clearance_level="public_or_repo_safe",
        requires_operator_preview=True,
        requires_guardian_gate=False,
        notes_for_mission_control="Not permanently neutered, but bounded by the same package compiler, proof, and receipt rules as Codex.",
    ),
)

ROUTING_RULES = (
    RoutingRule(
        "safety_security_protected_access_first",
        "safety, security, protected access, approval, or authority ambiguity",
        ("guardian",),
        ("chief", "operator_winship"),
        "single_actor_review",
        ("guardian", "chief", "operator_winship"),
        "Guardian owns fail-closed risk and authority review.",
        "No access, approval, send, or tool execution is granted.",
    ),
    RoutingRule(
        "code_implementation_scoped_worker",
        "backend/code/test/read-model implementation",
        ("codex", "gemini_antigravity"),
        ("chief", "guardian"),
        "implementation_worker_lane",
        ("chief", "codex", "gemini_antigravity", "guardian", "operator_winship"),
        "Implementation workers need a compiled package with explicit paths, tests, stop conditions, and receipts.",
        "No autonomous launch from Mission Control; explicit package preview first.",
    ),
    RoutingRule(
        "music_art_creative_first",
        "music, art, Struna, album metadata, creative production",
        ("niles",),
        ("codex", "guardian"),
        "single_actor_review",
        ("niles", "codex", "guardian", "operator_winship"),
        "Niles owns music/art context; Codex only joins for implementation artifacts.",
        "No publishing, release, catalog mutation, or external music-service tool use.",
    ),
    RoutingRule(
        "communications_finance_ap_first",
        "communications, finance/AP, email, calendar, or Capital Hilton-style workflow review",
        ("cassandra",),
        ("guardian", "operator_winship"),
        "paired_review",
        ("cassandra", "guardian", "operator_winship"),
        "Cassandra owns comms/finance visibility; Guardian joins for approval/protected-access implications.",
        "No Gmail, calendar, Coupa, send, submit, or approval authority.",
    ),
    RoutingRule(
        "big_picture_architecture_doctrine",
        "doctrine, app architecture, system coherence, horizon checks",
        ("hermes",),
        ("chief", "guardian"),
        "paired_review",
        ("hermes", "chief", "guardian", "operator_winship"),
        "Hermes reviews coherence and doctrine, often paired with Chief for build posture.",
        "Advisory only; no code execution or authority grant.",
    ),
    RoutingRule(
        "work_board_check_engine_queue",
        "work-board, check-engine, queue posture, active build coordination",
        ("chief",),
        ("guardian", "codex"),
        "single_actor_review",
        ("chief", "guardian", "codex", "operator_winship"),
        "Chief owns coordination and diagnostic posture.",
        "No repair, queue execution, or hidden worker activation.",
    ),
    RoutingRule(
        "final_action_authority",
        "final action, approval, send, submit, credential, or irreversible decision",
        ("operator_winship",),
        ("guardian",),
        "operator_only_decision",
        ("guardian", "operator_winship"),
        "Operator remains final authority; Guardian supplies boundary review.",
        "This contract cannot execute the decision.",
    ),
    RoutingRule(
        "whole_system_uncertainty",
        "cross-domain ambiguity, major doctrine shift, or pre-security audit review",
        ("chief", "hermes", "guardian"),
        ("cassandra", "niles", "codex", "gemini_antigravity", "operator_winship"),
        "all_agent_review",
        ("chief", "hermes", "guardian", "cassandra", "niles", "codex", "gemini_antigravity", "operator_winship"),
        "All-agent review is a future review mode for broad system posture, not live group chat.",
        "Preview-only until live chat/workspace routing is separately gated.",
    ),
)

RECOMMENDED_NEXT_LANES = (
    RecommendedLane(
        "model_selection_policy_contract_v0",
        "Model Selection Policy Contract v0",
        "P0",
        "Define model candidate classes, risk fit, task fit, unavailable-model fail-closed behavior, and no API-call boundary.",
        "Read-model only; no model endpoint, key, or runtime selection.",
    ),
    RecommendedLane(
        "agent_package_preview_contract_v0",
        "Agent Package Preview Contract v0",
        "P1",
        "Unify actor identity, package compiler, workbench target, clearance, steps, stop conditions, and receipt requirements.",
        "Preview only; no dispatch.",
    ),
    RecommendedLane(
        "mission_control_actor_routing_surface_v0",
        "Mission Control Actor Routing Surface v0",
        "P1",
        "Give the Mac helm a calm way to show who should inspect a lane without implying live agents are present.",
        "Mac UI display only; no backend command authority.",
    ),
    RecommendedLane(
        "tool_protocol_adapter_registry_v0",
        "Tool Protocol Adapter Registry v0",
        "P2",
        "Define future protocol/tool adapters, credential posture, activation gates, and revocation requirements.",
        "No browser/OAuth/tool activation.",
    ),
    RecommendedLane(
        "agent_memory_scope_contract_v0",
        "Agent Memory Scope Contract v0",
        "P2",
        "Define what each actor may know, which read-models are authoritative, and how memory is revoked or corrected.",
        "No hidden memory capture or broad file indexing.",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _read_json_if_present(path: str | Path, *, repo_root: str | Path = ROOT) -> dict[str, Any]:
    target = Path(path)
    if not target.is_absolute():
        target = Path(repo_root) / target
    if not target.is_file():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _source_record(source: EvidenceSource, *, repo_root: str | Path) -> dict[str, Any]:
    payload = _read_json_if_present(source.path, repo_root=repo_root)
    return {
        "source_id": source.source_id,
        "path": source.path,
        "role": source.role,
        "present": bool(payload),
        "schema_version": payload.get("schema_version") or payload.get("read_model_version"),
        "read_model_id": payload.get("read_model_id"),
        "raw_private_body_imported": False,
        "authority_granted_by_source_presence": False,
    }


def _actor_record(actor: ActorIdentity) -> dict[str, Any]:
    return {
        "actor_id": actor.actor_id,
        "display_name": actor.display_name,
        "class": actor.actor_class,
        "primary_role": actor.primary_role,
        "suitable_domains": list(actor.suitable_domains),
        "unsuitable_domains": list(actor.unsuitable_domains),
        "can_receive_packages": actor.can_receive_packages,
        "package_types": list(actor.package_types),
        "allowed_current_actions": list(actor.allowed_current_actions),
        "blocked_current_actions": list(actor.blocked_current_actions),
        "future_model_guidance": actor.future_model_guidance,
        "future_tool_guidance": actor.future_tool_guidance,
        "clearance_level": actor.clearance_level,
        "requires_operator_preview": actor.requires_operator_preview,
        "requires_guardian_gate": actor.requires_guardian_gate,
        "can_self_assign_authority": False,
        "notes_for_mission_control": actor.notes_for_mission_control,
    }


def _routing_rule_record(rule: RoutingRule) -> dict[str, Any]:
    return {
        "rule_id": rule.rule_id,
        "trigger": rule.trigger,
        "primary_actor_ids": list(rule.primary_actor_ids),
        "secondary_actor_ids": list(rule.secondary_actor_ids),
        "routing_mode": rule.routing_mode,
        "deterministic_order": list(rule.deterministic_order),
        "why": rule.why,
        "execution_boundary": rule.execution_boundary,
        "package_preview_required_before_execution": True,
        "future_executable_only_after_security_audit": True,
    }


def _recommended_lane_record(lane: RecommendedLane) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "title": lane.title,
        "priority": lane.priority,
        "why_next": lane.why_next,
        "hard_boundary": lane.hard_boundary,
    }


def build_agent_identity_actor_router_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    evidence_sources = [_source_record(source, repo_root=repo_root) for source in EVIDENCE_SOURCES]
    actors = [_actor_record(actor) for actor in ACTORS]
    actor_by_id = {actor["actor_id"]: actor for actor in actors}
    routing_rules = [_routing_rule_record(rule) for rule in ROUTING_RULES]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "agent_identity_actor_router_contract",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_identity_and_routing_metadata_only",
        "operator_summary": (
            "OpenClaw now has a deterministic identity/routing contract for known actors. "
            "It can say who should inspect a lane, why, what package types they may preview, "
            "and what remains blocked. It does not launch agents or call models."
        ),
        "mission_impossible_package_doctrine": {
            "actor_looks_smart_because": (
                "the deterministic package supplies role, context, constraints, tools metadata, clearance, proof, "
                "and stop conditions before any future action"
            ),
            "actor_may_not_invent": ["authority", "memory scope", "tool access", "workspace", "clearance"],
            "package_preview_before_any_future_send_or_execution": True,
        },
        "evidence_sources": evidence_sources,
        "actors": actors,
        "actor_roles": {
            actor["actor_id"]: {
                "display_name": actor["display_name"],
                "class": actor["class"],
                "primary_role": actor["primary_role"],
            }
            for actor in actors
        },
        "actor_domain_affinities": {
            actor["actor_id"]: {
                "suitable_domains": actor["suitable_domains"],
                "unsuitable_domains": actor["unsuitable_domains"],
            }
            for actor in actors
        },
        "actor_package_types": {
            actor["actor_id"]: actor["package_types"]
            for actor in actors
        },
        "actor_clearance_boundaries": {
            actor["actor_id"]: {
                "clearance_level": actor["clearance_level"],
                "requires_operator_preview": actor["requires_operator_preview"],
                "requires_guardian_gate": actor["requires_guardian_gate"],
                "can_self_assign_authority": actor["can_self_assign_authority"],
            }
            for actor in actors
        },
        "actor_model_guidance": {
            actor["actor_id"]: actor["future_model_guidance"]
            for actor in actors
        },
        "blocked_actor_authorities": list(GLOBAL_BLOCKED_ACTOR_AUTHORITIES),
        "routing_modes": [
            {
                "routing_mode": mode,
                "current_availability": "preview_only_future_gated",
                "live_chat_or_execution_allowed": False,
            }
            for mode in ROUTING_MODES
        ],
        "routing_decision_rules": routing_rules,
        "package_preview_requirements": {
            "required_before_any_future_route": True,
            "must_include": [
                "source_lane_id",
                "actor_id",
                "agent_character",
                "actor/model candidate",
                "workspace/read-model scope",
                "context included/excluded",
                "authority boundary",
                "clearance level",
                "allowed and forbidden capabilities",
                "proof requirements",
                "receipt requirements",
                "stop conditions",
            ],
            "must_not_include": [
                "credentials",
                "private raw bodies",
                "unbounded tool authority",
                "model-selected clearance",
                "send/submit/approval authority",
            ],
        },
        "future_receipt_requirements": {
            "required_before_routing_executable": [
                "valid package compiler boundary receipt",
                "actor identity contract receipt",
                "model selection policy receipt",
                "memory scope receipt",
                "tool adapter registry receipt if any tool is requested",
                "Guardian gate receipt for protected or approval-adjacent work",
                "operator preview/confirmation receipt for action-capable packages",
                "post-action result receipt once action authority exists",
            ],
            "natural_language_success_claims_count_as_proof": False,
        },
        "uncertainty_and_confidence_policy": {
            "show_confidence_only_when": "uncertainty changes the operator's next safe move",
            "hide_when": "routing is deterministic and no action is being dispatched",
            "unknown_actor_or_model": "UNKNOWN_FAIL_CLOSED",
            "unavailable_model_candidate": "route_to_operator_or_hold_for_model_selection_policy",
        },
        "mission_control_surface_guidance": {
            "top_layer": "Who should look at this?",
            "middle_layer": "Why this actor, what they can inspect, and what they must not do.",
            "lower_layer": "Package preview, contract refs, proof refs, clearance, and receipt requirements.",
            "full_inspection": "Complete actor package preview and future routing receipt.",
            "do_not_present_as": [
                "generic backend table",
                "live agent presence",
                "fake availability",
                "runtime chat launcher",
                "confidence theater",
            ],
        },
        "recommended_next_lanes": [_recommended_lane_record(lane) for lane in RECOMMENDED_NEXT_LANES],
        "machine_proof": {
            "source_read_models_present": {source["source_id"]: source["present"] for source in evidence_sources},
            "actor_ids": sorted(actor_by_id),
            "routing_rule_ids": [rule["rule_id"] for rule in routing_rules],
            "raw_private_bodies_included": False,
            "credentials_or_secrets_included": False,
            "runtime_activation_added": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_agent_identity_actor_router_contract(payload: dict[str, Any]) -> str:
    lines = [
        "# Agent Identity + Actor Router Contract v0",
        "",
        "## Operator Summary",
        payload["operator_summary"],
        "",
        "## Known Actors",
    ]
    for actor in payload["actors"]:
        lines.append(
            f"- `{actor['actor_id']}`: {actor['display_name']} — {actor['primary_role']} "
            f"({actor['class']}, clearance `{actor['clearance_level']}`)."
        )
    lines.extend(["", "## Routing Rules"])
    for rule in payload["routing_decision_rules"]:
        order = " -> ".join(rule["deterministic_order"])
        lines.append(f"- `{rule['rule_id']}`: {rule['trigger']} routes `{order}`.")
    lines.extend(["", "## Mission Control Guidance"])
    guidance = payload["mission_control_surface_guidance"]
    lines.append(f"- Top layer: {guidance['top_layer']}")
    lines.append(f"- Middle layer: {guidance['middle_layer']}")
    lines.append(f"- Lower layer: {guidance['lower_layer']}")
    lines.append("- Do not imply live agents are running.")
    lines.extend(["", "## Blocked Actor Authorities"])
    for item in payload["blocked_actor_authorities"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Next Lanes"])
    for lane in payload["recommended_next_lanes"]:
        lines.append(f"- `{lane['lane_id']}` ({lane['priority']}): {lane['title']}")
    lines.extend(["", "## Authority Boundary"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    return "\n".join(lines).rstrip() + "\n"


def export_agent_identity_actor_router_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> AgentIdentityActorRouterExportResult:
    payload = build_agent_identity_actor_router_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_agent_identity_actor_router_contract(payload), encoding="utf-8")
    return AgentIdentityActorRouterExportResult(
        schema_version=payload["schema_version"],
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        actor_count=len(payload["actors"]),
        routing_rule_count=len(payload["routing_decision_rules"]),
        runtime_authority_added=bool(payload["runtime_authority"]),
        model_call_authority_added=bool(payload["model_call_authority"]),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Agent Identity + Actor Router Contract read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_agent_identity_actor_router_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(build_agent_identity_actor_router_contract(repo_root=args.repo_root)), end="")
    elif args.format == "operator":
        payload = build_agent_identity_actor_router_contract(repo_root=args.repo_root)
        print(format_agent_identity_actor_router_contract(payload), end="")
    else:
        print(
            stable_json(
                {
                    "schema_version": result.schema_version,
                    "json_path": result.json_path,
                    "operator_path": result.operator_path,
                    "actor_count": result.actor_count,
                    "routing_rule_count": result.routing_rule_count,
                    "runtime_authority_added": result.runtime_authority_added,
                    "model_call_authority_added": result.model_call_authority_added,
                }
            ),
            end="",
        )
    return 0


__all__ = [
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_agent_identity_actor_router_contract",
    "export_agent_identity_actor_router_contract",
    "format_agent_identity_actor_router_contract",
    "main",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
