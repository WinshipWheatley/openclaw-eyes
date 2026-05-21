"""Operator Question Journey / Doctrine Candidate Registry v0.

This read-model treats bounded operator questions, objections, corrections, and
follow-up refinements as first-class doctrine candidates. It is metadata only.
It does not ingest broad chat history, inspect private raw data, call models,
activate agents, mutate Mac app files, grant runtime authority, or write
OpenClaw artifacts to the PC C-drive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger, record_receipt


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "operator_question_journey_registry_v0"
JSON_EXPORT_NAME = "operator_question_journey_registry.json"
OPERATOR_EXPORT_NAME = "operator_question_journey_registry_OPERATOR.md"

SOURCE_TYPES = (
    "operator_provided_context",
    "approved_repo_artifact",
    "generated_read_model",
    "memory_comparison_needed",
)

JOURNEY_CLASSIFICATIONS = (
    "question",
    "objection",
    "correction",
    "doctrine_candidate",
    "promoted_doctrine",
    "known_unknown",
    "taste_signal",
)

JOURNEY_STATUSES = (
    "captured",
    "candidate",
    "promoted",
    "needs_winship_memory",
    "needs_source_artifact",
    "superseded",
    "rejected",
)

AFFECTED_SYSTEM_AREAS = (
    "helm_front_door",
    "health_lights",
    "worlds",
    "steel_thread",
    "package_compiler",
    "actor_router",
    "design_memory",
    "bridge_sync",
    "authority_boundary",
    "operator_workbenches",
)

CONFIDENCE_STATES = (
    "HIGH_TRUST_OPERATOR_PROVIDED_AND_PROMOTED",
    "MEDIUM_TRUST_OPERATOR_PROVIDED_CANDIDATE",
    "LOW_TRUST_SOURCE_ARTIFACT_MISSING",
    "UNKNOWN_FAIL_CLOSED",
)

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "metadata_only": True,
    "registry_only": True,
    "sqlite_receipt_metadata_only": True,
    "sqlite_schema_changed": False,
    "model_calls_made": False,
    "lm_called": False,
    "external_model_apis_called": False,
    "agents_activated": False,
    "agent_launch_authority_added": False,
    "tools_enabled": False,
    "plugins_wired": False,
    "browser_oauth_or_account_access_enabled": False,
    "browser_accessed": False,
    "oauth_or_credentials_accessed": False,
    "credentials_stored": False,
    "gmail_calendar_coupa_accessed": False,
    "telegram_send_triggered": False,
    "email_send_triggered": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "execution_authority_added": False,
    "runtime_authority_added": False,
    "live_launch_buttons_created": False,
    "mission_control_app_changed": False,
    "mac_app_files_mutated": False,
    "mac_commands_run_from_pc": False,
    "delete_authority_added": False,
    "cleanup_authority_added": False,
    "remount_authority_added": False,
    "credential_handling_added": False,
    "c_drive_write_allowed": False,
    "c_drive_artifact_written": False,
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
    "raw_private_content_inspected": False,
    "broad_private_chat_ingested": False,
    "chatgpt_history_ingested": False,
    "raw_private_file_bodies_stored": False,
    "raw_logs_stored": False,
    "broad_file_dump_stored": False,
}

FORBIDDEN_ACTIONS = (
    "ingest broad ChatGPT history",
    "inspect private raw data",
    "call external model APIs",
    "run Codex, Antigravity, VS Code agent, browser, or other live sessions",
    "mutate Mission Control app files",
    "create live launch buttons",
    "create runtime execution authority",
    "create browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval authority",
    "write OpenClaw artifacts to the PC system drive",
    "delete, cleanup, remount, or handle credentials",
)


@dataclass(frozen=True)
class SourceReadModel:
    key: str
    path: str
    role: str


@dataclass(frozen=True)
class QuestionJourneySpec:
    journey_id: str
    source_type: str
    journey_classification: str
    question_or_objection: str
    response_or_prior_framing: str
    correction_or_refinement: str
    resulting_doctrine_candidate: str
    confidence: str
    status: str
    affected_system_area: tuple[str, ...]
    why_it_matters: str
    safe_next_move: str
    promotion_rule: str
    proof_required_before_promotion: tuple[str, ...]
    what_not_to_claim_yet: str
    source_refs: tuple[str, ...] = ()
    promoted_read_model_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class OperatorQuestionJourneyRegistryExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    journey_count: int
    sqlite_receipt_supported: bool
    broad_private_chat_ingested: bool
    c_drive_artifact_written: bool
    runtime_authority_added: bool


SOURCE_READ_MODELS = (
    SourceReadModel(
        "mission_control_design_memory_inventory",
        "generated/read_models/mission_control_design_memory_inventory.json",
        "design doctrine, taste, known unknowns, and source-needed posture",
    ),
    SourceReadModel(
        "operator_mission_priority_helm_declutter",
        "generated/read_models/operator_mission_priority_helm_declutter.json",
        "helm declutter, mission priority, and front-door classification",
    ),
    SourceReadModel(
        "steel_thread_lane_template_registry",
        "generated/read_models/steel_thread_lane_template_registry.json",
        "reusable lane/check-light/world steel-thread template",
    ),
    SourceReadModel(
        "package_compiler_contract",
        "generated/read_models/package_compiler_contract.json",
        "deterministic package compiler and boundary validation contract",
    ),
    SourceReadModel(
        "system_health_lights_taxonomy",
        "generated/read_models/system_health_lights_taxonomy.json",
        "health light taxonomy and Check Engine versus Check Transmission split",
    ),
    SourceReadModel(
        "operator_workbench_actor_host_registry",
        "generated/read_models/operator_workbench_actor_host_registry.json",
        "operator-system workbench and actor-host registry",
    ),
    SourceReadModel(
        "operator_question_response",
        "operator_question_response.py",
        "static non-authorizing operator question response path",
    ),
)

DOCTRINE_SOURCE_LABELS = (
    "operator_prompt: Operator Question Journey / Doctrine Candidate Registry v0",
    "existing_read_model: Mission Control Design Memory Inventory v0",
    "existing_read_model: Operator Mission Priority / Helm Declutter Taxonomy v0",
    "existing_read_model: Steel Thread Lane Template Registry v0",
    "existing_read_model: Package Compiler Contract v0",
    "existing_read_model: System Health Lights Taxonomy v0",
    "existing_read_model: Operator Workbench / Actor Host Registry v0",
    "existing_static_module: operator_question_response.py",
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


def _hash_payload(payload: Any) -> str:
    digest = hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _source_record(source: SourceReadModel, *, repo_root: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    target = _rooted(source.path, repo_root=repo_root)
    return {
        "key": source.key,
        "path": source.path,
        "present": target.exists(),
        "schema_version": payload.get("schema_version") or payload.get("read_model_version"),
        "role": source.role,
        "source_kind": "approved_repo_artifact_or_generated_read_model",
        "raw_body_exported": False,
        "raw_private_content_read": False,
        "broad_private_chat_ingested": False,
        "executed_or_dispatched": False,
    }


def _areas(*areas: str) -> tuple[str, ...]:
    invalid = sorted(set(areas) - set(AFFECTED_SYSTEM_AREAS))
    if invalid:
        raise ValueError(f"unknown affected areas: {invalid}")
    return tuple(areas)


def _question_journey_specs() -> tuple[QuestionJourneySpec, ...]:
    return (
        QuestionJourneySpec(
            journey_id="check_engine_light_visibility",
            source_type="operator_provided_context",
            journey_classification="question",
            question_or_objection="I don't see a check engine light.",
            response_or_prior_framing="System health existed in backend/check-engine posture but could be buried in detail.",
            correction_or_refinement="A system fault should be visible as a helm-level lamp when it materially affects operator trust.",
            resulting_doctrine_candidate="Check Engine must be a visible helm-level health light when active, not only a detail row.",
            confidence="HIGH_TRUST_OPERATOR_PROVIDED_AND_PROMOTED",
            status="promoted",
            affected_system_area=_areas("helm_front_door", "health_lights", "steel_thread"),
            why_it_matters="The operator cannot trust the helm if a system/workbench fault is invisible.",
            safe_next_move="Keep the health-light taxonomy linked to the helm declutter and steel-thread lane templates.",
            promotion_rule="Promote when reflected by a health-light taxonomy/read-model plus operator-facing summary.",
            proof_required_before_promotion=("system_health_lights_taxonomy", "operator_mission_priority_helm_declutter"),
            what_not_to_claim_yet="Do not claim the Mac UI visual lamp is finished from this backend registry alone.",
            source_refs=("operator_prompt: Operator Question Journey / Doctrine Candidate Registry v0",),
            promoted_read_model_refs=(
                "generated/read_models/system_health_lights_taxonomy.json",
                "generated/read_models/operator_mission_priority_helm_declutter.json",
            ),
        ),
        QuestionJourneySpec(
            journey_id="helm_clutter_objection",
            source_type="operator_provided_context",
            journey_classification="objection",
            question_or_objection="All I see is a lot of shit.",
            response_or_prior_framing="Mission Control accumulated correct backend information but risked rendering every read-model or lane equally.",
            correction_or_refinement="The front door must reduce clutter, prioritize operator orientation, and keep proof/details lower.",
            resulting_doctrine_candidate="The helm should answer mode, health, active mission, attention, next safe move, blocks, and proof access without becoming a card wall.",
            confidence="HIGH_TRUST_OPERATOR_PROVIDED_AND_PROMOTED",
            status="promoted",
            affected_system_area=_areas("helm_front_door", "design_memory", "steel_thread"),
            why_it_matters="A correct backend still fails the operator if the UI makes him mentally track everything manually.",
            safe_next_move="Use helm declutter and design-memory inventory to guide the next Mac UI finish pass.",
            promotion_rule="Promote when captured in helm priority/declutter taxonomy and design-memory guidance.",
            proof_required_before_promotion=(
                "operator_mission_priority_helm_declutter",
                "mission_control_design_memory_inventory",
            ),
            what_not_to_claim_yet="Do not claim the front door is visually calm until the Mac app renders it.",
            source_refs=("operator_prompt: Operator Question Journey / Doctrine Candidate Registry v0",),
            promoted_read_model_refs=(
                "generated/read_models/operator_mission_priority_helm_declutter.json",
                "generated/read_models/mission_control_design_memory_inventory.json",
            ),
        ),
        QuestionJourneySpec(
            journey_id="nested_lanes_backend_not_ui_tree",
            source_type="operator_provided_context",
            journey_classification="correction",
            question_or_objection="Keep nested lanes in the backend if possible.",
            response_or_prior_framing="Nested lanes could be exposed as a deep tree in Mission Control.",
            correction_or_refinement="The backend may model nested lanes, while the UI should show active parent, immediate focus, next safe move, and drill-in only when needed.",
            resulting_doctrine_candidate="Nested-lane topology belongs mostly in deterministic read-models; the helm should not default to deep tree navigation.",
            confidence="HIGH_TRUST_OPERATOR_PROVIDED_AND_PROMOTED",
            status="promoted",
            affected_system_area=_areas("helm_front_door", "steel_thread", "design_memory"),
            why_it_matters="This keeps the backend expressive without making the operator front door noisy.",
            safe_next_move="Keep nested lane read-models as proof/detail inputs for steel-thread rendering.",
            promotion_rule="Promote when captured by nested lane spine, helm declutter, and steel-thread template registry.",
            proof_required_before_promotion=(
                "operator_nested_lane_mission_package_spine",
                "operator_mission_priority_helm_declutter",
                "steel_thread_lane_template_registry",
            ),
            what_not_to_claim_yet="Do not assume nested lane UI is built.",
            source_refs=("operator_prompt: Operator Question Journey / Doctrine Candidate Registry v0",),
            promoted_read_model_refs=(
                "generated/read_models/operator_mission_priority_helm_declutter.json",
                "generated/read_models/steel_thread_lane_template_registry.json",
            ),
        ),
        QuestionJourneySpec(
            journey_id="actor_model_agent_character_split",
            source_type="operator_provided_context",
            journey_classification="correction",
            question_or_objection="The model is the actor; the agent is the character.",
            response_or_prior_framing="Model and agent could be conflated in package/routing language.",
            correction_or_refinement="Actor/model and agent/character are separate deterministic package fields.",
            resulting_doctrine_candidate="A package chooses the model actor, attaches the agent character, and defines context, tools, clearance, steps, stops, and receipts before any future launch.",
            confidence="HIGH_TRUST_OPERATOR_PROVIDED_AND_PROMOTED",
            status="promoted",
            affected_system_area=_areas("package_compiler", "actor_router", "operator_workbenches"),
            why_it_matters="It prevents the model from deciding its own role, authority, or tools.",
            safe_next_move="Keep package compiler and workbench registry using separate actor/model and agent/character fields.",
            promotion_rule="Promote when package compiler and workbench registry expose separate routing metadata.",
            proof_required_before_promotion=("package_compiler_contract", "operator_workbench_actor_host_registry"),
            what_not_to_claim_yet="Do not claim any actor/model integration is live.",
            source_refs=("operator_prompt: Operator Question Journey / Doctrine Candidate Registry v0",),
            promoted_read_model_refs=(
                "generated/read_models/package_compiler_contract.json",
                "generated/read_models/operator_workbench_actor_host_registry.json",
            ),
        ),
        QuestionJourneySpec(
            journey_id="deterministic_package_generation",
            source_type="operator_provided_context",
            journey_classification="doctrine_candidate",
            question_or_objection="Package generation should become deterministic.",
            response_or_prior_framing="Early prompt packages could be improvised in natural language.",
            correction_or_refinement="Authority, context, tools, clearance, proof, receipts, and success validation must compile from deterministic fields.",
            resulting_doctrine_candidate="Package compiler maturity path: LM prose may help wording, but deterministic contract fields decide authority and validity.",
            confidence="HIGH_TRUST_OPERATOR_PROVIDED_AND_PROMOTED",
            status="promoted",
            affected_system_area=_areas("package_compiler", "authority_boundary", "steel_thread"),
            why_it_matters="This blocks prompt text from granting authority or claiming success without proof.",
            safe_next_move="Keep boundary validation tests as a contract gate for future package preview UI.",
            promotion_rule="Promote when package compiler defines explicit schema/enums/blockers/tests.",
            proof_required_before_promotion=("package_compiler_contract", "tests/test_package_compiler_contract.py"),
            what_not_to_claim_yet="Do not claim a live package runner exists.",
            source_refs=("operator_prompt: Operator Question Journey / Doctrine Candidate Registry v0",),
            promoted_read_model_refs=("generated/read_models/package_compiler_contract.json",),
        ),
        QuestionJourneySpec(
            journey_id="tell_system_whats_missing_button",
            source_type="operator_provided_context",
            journey_classification="question",
            question_or_objection="I want a button to tell the system what it is missing.",
            response_or_prior_framing="Awareness gaps could remain passive read-only labels.",
            correction_or_refinement="Mission Control should support future capture of operator memory comparison without treating memory as truth.",
            resulting_doctrine_candidate="Tell System What's Missing is a future-gated capture/package path that records missing-memory posture and requests safe discovery/classification.",
            confidence="MEDIUM_TRUST_OPERATOR_PROVIDED_CANDIDATE",
            status="candidate",
            affected_system_area=_areas("helm_front_door", "design_memory", "steel_thread", "package_compiler"),
            why_it_matters="Operator corrections are often the shortest path from partial awareness to trackable proof.",
            safe_next_move="Represent as package preview/capture metadata until a later write-authority receipt lane exists.",
            promotion_rule="Promote only after a capture schema, receipt requirement, and Mac UI control boundary exist.",
            proof_required_before_promotion=(
                "steel_thread_lane_template_registry",
                "package_compiler_contract",
                "future capture receipt contract",
            ),
            what_not_to_claim_yet="Do not claim the button mutates state yet.",
            source_refs=("operator_prompt: Operator Question Journey / Doctrine Candidate Registry v0",),
            promoted_read_model_refs=("generated/read_models/package_compiler_contract.json",),
        ),
        QuestionJourneySpec(
            journey_id="check_transmission_not_check_engine",
            source_type="operator_provided_context",
            journey_classification="correction",
            question_or_objection="This should be Check Transmission, not Check Engine.",
            response_or_prior_framing="Bridge/sync faults could be collapsed into generic Check Engine.",
            correction_or_refinement="PC/Mac bridge, mirror, mount, shuttle markers, stale proof, and manifest mismatch deserve their own Check Transmission light.",
            resulting_doctrine_candidate="Check Transmission owns state-transfer faults; Check Engine should not duplicate bridge faults as a catchall.",
            confidence="HIGH_TRUST_OPERATOR_PROVIDED_AND_PROMOTED",
            status="promoted",
            affected_system_area=_areas("health_lights", "bridge_sync", "helm_front_door"),
            why_it_matters="The operator needs to know whether the backend/app is broken or the bridge between them is untrusted.",
            safe_next_move="Keep sync health and system health taxonomy separate but linked.",
            promotion_rule="Promote when health-light taxonomy and sync health distinguish bridge trust from core system fault.",
            proof_required_before_promotion=("system_health_lights_taxonomy", "sync_health"),
            what_not_to_claim_yet="Do not quiet Check Transmission while sync proof remains stale.",
            source_refs=("operator_prompt: Operator Question Journey / Doctrine Candidate Registry v0",),
            promoted_read_model_refs=("generated/read_models/system_health_lights_taxonomy.json",),
        ),
        QuestionJourneySpec(
            journey_id="doom_space_station_visual_metaphor",
            source_type="operator_provided_context",
            journey_classification="taste_signal",
            question_or_objection="The helm is like Doom Eternal's space station.",
            response_or_prior_framing="Repo A source-backed design memory had cockpit/studio-console language but lacked this exact source artifact.",
            correction_or_refinement="Use helm/base/teleport metaphor as an operator-provided taste signal, while keeping exact source provenance separate.",
            resulting_doctrine_candidate="Mission Control should feel like a helm/base where the operator orients, stages packages, upgrades/prepares, and enters worlds.",
            confidence="MEDIUM_TRUST_OPERATOR_PROVIDED_CANDIDATE",
            status="needs_source_artifact",
            affected_system_area=_areas("design_memory", "helm_front_door", "worlds"),
            why_it_matters="It clarifies that the desired UI is spatial/operator-first, not a generic admin dashboard.",
            safe_next_move="Link to design memory inventory and ask for a bounded source artifact or visual reference before overfitting the UI.",
            promotion_rule="Promote after an approved design source artifact or explicit operator memory capture record is added.",
            proof_required_before_promotion=("mission_control_design_memory_inventory", "approved design source artifact"),
            what_not_to_claim_yet="Do not claim this is source-backed beyond the current operator-provided context.",
            source_refs=("operator_prompt: Operator Question Journey / Doctrine Candidate Registry v0",),
            promoted_read_model_refs=("generated/read_models/mission_control_design_memory_inventory.json",),
        ),
        QuestionJourneySpec(
            journey_id="operator_system_above_operating_systems",
            source_type="operator_provided_context",
            journey_classification="promoted_doctrine",
            question_or_objection="I am building an Operator System above operating systems.",
            response_or_prior_framing="OpenClaw could be framed as a set of apps, agents, or developer tools.",
            correction_or_refinement="OpenClaw should be the operator system above macOS, Windows, WSL, VS Code, Codex, Antigravity, Xcode, Terminal, files, apps, and future tools.",
            resulting_doctrine_candidate="OpenClaw is the helm/router/package layer that lets the operator navigate and control underlying workbenches safely.",
            confidence="HIGH_TRUST_OPERATOR_PROVIDED_AND_PROMOTED",
            status="promoted",
            affected_system_area=_areas("operator_workbenches", "actor_router", "helm_front_door", "package_compiler"),
            why_it_matters="This sets product identity and prevents underlying tools from becoming the helm.",
            safe_next_move="Keep workbench/actor host registry and package compiler as deterministic operator-system infrastructure.",
            promotion_rule="Promote when reflected in workbench actor host registry and helm mission priority taxonomy.",
            proof_required_before_promotion=("operator_workbench_actor_host_registry", "operator_mission_priority_helm_declutter"),
            what_not_to_claim_yet="Do not claim OpenClaw controls external systems without explicit future authority gates.",
            source_refs=("operator_prompt: Operator Question Journey / Doctrine Candidate Registry v0",),
            promoted_read_model_refs=(
                "generated/read_models/operator_workbench_actor_host_registry.json",
                "generated/read_models/operator_mission_priority_helm_declutter.json",
            ),
        ),
        QuestionJourneySpec(
            journey_id="avoid_developer_tool_power_user_requirement",
            source_type="operator_provided_context",
            journey_classification="objection",
            question_or_objection="I should not need to become a VS Code/Codex/Antigravity power user.",
            response_or_prior_framing="Winship might need to manually know every workbench and actor host.",
            correction_or_refinement="OpenClaw should route packages to the right workbench/actor with explicit clearance, context, receipts, and safe autonomy level.",
            resulting_doctrine_candidate="Mission Control should hide workbench complexity behind deterministic package routing and proof/receipt expectations.",
            confidence="HIGH_TRUST_OPERATOR_PROVIDED_AND_PROMOTED",
            status="promoted",
            affected_system_area=_areas("operator_workbenches", "actor_router", "package_compiler", "helm_front_door"),
            why_it_matters="The operator-system value is reduced if the operator must become a developer-tool power user to use it.",
            safe_next_move="Use workbench registry plus package compiler boundary fields in future package preview surfaces.",
            promotion_rule="Promote when workbench registry captures host roles, autonomy, proof, and forbidden actions.",
            proof_required_before_promotion=("operator_workbench_actor_host_registry", "package_compiler_contract"),
            what_not_to_claim_yet="Do not claim automatic launch or monitoring is available yet.",
            source_refs=("operator_prompt: Operator Question Journey / Doctrine Candidate Registry v0",),
            promoted_read_model_refs=(
                "generated/read_models/operator_workbench_actor_host_registry.json",
                "generated/read_models/package_compiler_contract.json",
            ),
        ),
        QuestionJourneySpec(
            journey_id="prior_question_answer_source_artifacts_missing",
            source_type="memory_comparison_needed",
            journey_classification="known_unknown",
            question_or_objection="There were prior question, answer, correction, and design-taste discussions that may contain product truth.",
            response_or_prior_framing="The system has only bounded current prompt examples and approved Repo A artifacts in this lane.",
            correction_or_refinement="The absence of a source artifact should be tracked as a known unknown, not interpreted as absence of the doctrine.",
            resulting_doctrine_candidate="Question journeys from prior discussions need an approved source artifact or metadata-only capture packet before promotion.",
            confidence="LOW_TRUST_SOURCE_ARTIFACT_MISSING",
            status="needs_source_artifact",
            affected_system_area=_areas("design_memory", "helm_front_door", "authority_boundary"),
            why_it_matters="The real doctrine may live in the operator's correction path, but broad private chat ingestion is blocked.",
            safe_next_move="Ask Winship for a bounded approved artifact or create a future metadata-only source capture packet.",
            promotion_rule="Promote only after bounded source refs, summaries, and receipt metadata exist.",
            proof_required_before_promotion=(
                "approved source artifact",
                "metadata-only receipt",
                "design memory inventory link",
            ),
            what_not_to_claim_yet="Do not claim broad prior conversations were inspected or ingested.",
            source_refs=("operator_prompt: Operator Question Journey / Doctrine Candidate Registry v0",),
            promoted_read_model_refs=("generated/read_models/mission_control_design_memory_inventory.json",),
        ),
    )


def _journey_record(spec: QuestionJourneySpec) -> dict[str, Any]:
    return {
        "journey_id": spec.journey_id,
        "source_type": spec.source_type,
        "journey_classification": spec.journey_classification,
        "question_or_objection": spec.question_or_objection,
        "response_or_prior_framing": spec.response_or_prior_framing,
        "correction_or_refinement": spec.correction_or_refinement,
        "resulting_doctrine_candidate": spec.resulting_doctrine_candidate,
        "confidence": spec.confidence,
        "status": spec.status,
        "affected_system_area": list(spec.affected_system_area),
        "why_it_matters": spec.why_it_matters,
        "safe_next_move": spec.safe_next_move,
        "promotion_rule": spec.promotion_rule,
        "proof_required_before_promotion": list(spec.proof_required_before_promotion),
        "what_not_to_claim_yet": spec.what_not_to_claim_yet,
        "source_refs": list(spec.source_refs),
        "promoted_read_model_refs": list(spec.promoted_read_model_refs),
        "operator_context_is_bounded_summary": True,
        "raw_private_chat_body_stored": False,
        "live_authority_added": False,
    }


def _journeys() -> list[dict[str, Any]]:
    return [_journey_record(spec) for spec in _question_journey_specs()]


def _group_by(items: list[dict[str, Any]], key: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for item in items:
        grouped.setdefault(str(item[key]), []).append(item["journey_id"])
    return grouped


def _source_state_summary(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    design = sources.get("mission_control_design_memory_inventory", {})
    package = sources.get("package_compiler_contract", {})
    health = sources.get("system_health_lights_taxonomy", {})
    workbench = sources.get("operator_workbench_actor_host_registry", {})
    return {
        "available_sources": {key: bool(value) for key, value in sources.items()},
        "design_memory_theme_count": design.get("theme_count"),
        "package_compiler_status": package.get("contract_status"),
        "package_compiler_boundary_hardened": package.get("contract_status")
        == "deterministic_metadata_only_package_compiler_boundary_hardened",
        "current_light_states": health.get("current_light_states", {}),
        "workbench_host_count": workbench.get("host_count"),
    }


def _sqlite_receipt_contract(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "supported_by_existing_pattern": _rooted("business_ops_ledger.py", repo_root=ROOT).exists(),
        "pattern": "business_ops_ledger.record_receipt",
        "receipt_type": "generated_status",
        "sqlite_meaning": "receipt_record_only",
        "metadata_only": True,
        "stores_secrets": False,
        "stores_credentials": False,
        "stores_raw_private_chat_bodies": False,
        "stores_raw_private_file_bodies": False,
        "stores_raw_logs": False,
        "stores_broad_file_dumps": False,
        "stores_runtime_activation": False,
        "receipt_writer_function": "record_operator_question_journey_registry_receipt",
        "registry_hash": payload["registry_hash"],
    }


def build_operator_question_journey_registry(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    sources = {
        source.key: _read_json_if_present(source.path, repo_root=repo_root)
        for source in SOURCE_READ_MODELS
    }
    journeys = _journeys()
    registry_hash = _hash_payload(
        {
            "schema_version": SCHEMA_VERSION,
            "journeys": [
                {
                    "journey_id": journey["journey_id"],
                    "source_type": journey["source_type"],
                    "classification": journey["journey_classification"],
                    "status": journey["status"],
                    "candidate": journey["resulting_doctrine_candidate"],
                }
                for journey in journeys
            ],
        }
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "operator_question_journey_registry",
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "lane": "Operator Question Journey / Doctrine Candidate Registry v0",
        "contract_status": "deterministic_metadata_only_operator_question_journey_registry",
        "purpose": "Capture bounded operator questions, objections, corrections, and refinements as doctrine candidates without ingesting broad private chat history.",
        "why_operator_questions_matter": [
            "They expose confusion points and missing affordances.",
            "They correct system framing before it hardens into UI or package contracts.",
            "They identify taste constraints and workflow friction that polished summaries may erase.",
            "They can become doctrine candidates, but they are not promoted truth until source/proof/read-model criteria are met.",
        ],
        "source_type_vocab": list(SOURCE_TYPES),
        "journey_classification_vocab": list(JOURNEY_CLASSIFICATIONS),
        "status_vocab": list(JOURNEY_STATUSES),
        "affected_system_area_vocab": list(AFFECTED_SYSTEM_AREAS),
        "confidence_vocab": list(CONFIDENCE_STATES),
        "journeys": journeys,
        "journey_count": len(journeys),
        "journey_ids_by_status": _group_by(journeys, "status"),
        "journey_ids_by_classification": _group_by(journeys, "journey_classification"),
        "doctrine_candidates": [
            journey["journey_id"]
            for journey in journeys
            if journey["status"] in {"candidate", "needs_source_artifact", "needs_winship_memory"}
        ],
        "promoted_doctrine_links": [
            {
                "journey_id": journey["journey_id"],
                "read_model_refs": journey["promoted_read_model_refs"],
            }
            for journey in journeys
            if journey["status"] == "promoted"
        ],
        "known_unknowns_and_memory_comparison_needs": [
            journey["journey_id"]
            for journey in journeys
            if journey["status"] in {"needs_winship_memory", "needs_source_artifact"}
            or journey["journey_classification"] == "known_unknown"
        ],
        "design_memory_links": [
            journey["journey_id"]
            for journey in journeys
            if "design_memory" in journey["affected_system_area"]
        ],
        "mac_ui_next_influences": [
            "check_engine_light_visibility",
            "helm_clutter_objection",
            "nested_lanes_backend_not_ui_tree",
            "tell_system_whats_missing_button",
            "doom_space_station_visual_metaphor",
        ],
        "promotion_policy": {
            "operator_provided_context_can_seed_candidate": True,
            "operator_context_is_not_broad_chat_ingestion": True,
            "operator_question_is_not_automatically_truth": True,
            "promotion_requires": [
                "approved repo artifact or generated read-model reflection",
                "explicit source refs or receipt",
                "safe authority boundary",
                "tests when code/read-model behavior changes",
            ],
            "memory_comparison_without_source_status": "needs_source_artifact",
        },
        "what_not_to_overclaim": [
            "do not claim broad private chat history was ingested",
            "do not claim the Mac UI has implemented these journeys",
            "do not claim a candidate is promoted without source/read-model proof",
            "do not claim live model/tool/agent/workbench authority",
            "do not treat operator memory as canonical truth without a receipt/source path",
        ],
        "source_state_summary": _source_state_summary(sources),
        "machine_proof": {
            "source_read_models": [
                _source_record(source, repo_root=repo_root, payload=sources[source.key])
                for source in SOURCE_READ_MODELS
            ],
            "source_read_models_present": {key: bool(value) for key, value in sources.items()},
            "ledger_pattern_present": _rooted("business_ops_ledger.py", repo_root=repo_root).exists(),
            "generated_outputs": [
                f"generated/read_models/{JSON_EXPORT_NAME}",
                f"generated/read_models/{OPERATOR_EXPORT_NAME}",
            ],
        },
        "registry_hash": registry_hash,
        "sqlite_ledger_receipt_contract": {},
        "safe_next_lane": "Mission Control Question Journey Readback / Missing Doctrine Capture v0",
        "no_live_authority_statement": "This registry captures bounded doctrine-candidate metadata only; it does not ingest broad chat history, call models, launch agents, mutate the Mac app, or grant runtime authority.",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    payload["sqlite_ledger_receipt_contract"] = _sqlite_receipt_contract(payload)
    return payload


def format_operator_question_journey_registry(payload: dict[str, Any]) -> str:
    lines = [
        "# Operator Question Journey Registry v0",
        "",
        "Status:",
        "- Deterministic metadata-only registry.",
        "- Bounded operator-provided context only; no broad private chat ingestion.",
        "",
        "## Why Questions Matter",
    ]
    for item in payload["why_operator_questions_matter"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Captured Journeys"])
    for journey in payload["journeys"]:
        lines.append(
            f"- `{journey['journey_id']}`: {journey['journey_classification']} / {journey['status']} -> {journey['resulting_doctrine_candidate']}"
        )
    lines.extend(["", "## Doctrine Candidates"])
    for journey_id in payload["doctrine_candidates"]:
        lines.append(f"- `{journey_id}`")
    lines.extend(["", "## Promoted Doctrine Links"])
    for item in payload["promoted_doctrine_links"]:
        refs = ", ".join(f"`{ref}`" for ref in item["read_model_refs"])
        lines.append(f"- `{item['journey_id']}`: {refs}")
    lines.extend(["", "## Known Unknowns / Memory Comparison"])
    for journey_id in payload["known_unknowns_and_memory_comparison_needs"]:
        lines.append(f"- `{journey_id}`")
    lines.extend(["", "## Linked To Design Memory"])
    for journey_id in payload["design_memory_links"]:
        lines.append(f"- `{journey_id}`")
    lines.extend(["", "## Mac UI Next Influences"])
    for journey_id in payload["mac_ui_next_influences"]:
        lines.append(f"- `{journey_id}`")
    lines.extend(["", "## What Not To Overclaim"])
    for item in payload["what_not_to_overclaim"]:
        lines.append(f"- {item}.")
    lines.extend(
        [
            "",
            "## Authority Boundary",
            "- No broad private chat ingestion, private raw data inspection, external model calls, browser/OAuth/Gmail/calendar/Coupa/Telegram, credentials, runtime execution, Mac app mutation, or PC system-drive artifact writes.",
            "",
            "## Next Safe Lane",
            f"- {payload['safe_next_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_operator_question_journey_registry(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> OperatorQuestionJourneyRegistryExportResult:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_operator_question_journey_registry(repo_root=root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_question_journey_registry(payload), encoding="utf-8")
    return OperatorQuestionJourneyRegistryExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        journey_count=payload["journey_count"],
        sqlite_receipt_supported=payload["sqlite_ledger_receipt_contract"]["supported_by_existing_pattern"],
        broad_private_chat_ingested=payload["broad_private_chat_ingested"],
        c_drive_artifact_written=payload["c_drive_artifact_written"],
        runtime_authority_added=payload["runtime_authority_added"],
    )


def _load_existing_receipt_payloads(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    path = Path(db_path or DEFAULT_DB_PATH)
    if not path.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                """
SELECT e.ts, p.packet_json_safe
FROM events e
JOIN packets p ON p.event_id = e.event_id
WHERE e.event_type = 'generated_status'
ORDER BY e.ts DESC
LIMIT 500
""".strip()
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []
    payloads: list[dict[str, Any]] = []
    for ts, packet_json_safe in rows:
        try:
            packet = json.loads(packet_json_safe or "{}")
        except json.JSONDecodeError:
            continue
        packet["_event_ts"] = ts
        payloads.append(packet)
    return payloads


def _find_existing_operator_question_journey_registry_receipt(
    *,
    registry_hash: str,
    commit_hash: str | None,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    for packet in _load_existing_receipt_payloads(db_path):
        payload_json = packet.get("payload_json")
        if not isinstance(payload_json, dict):
            continue
        if payload_json.get("contract_id") != SCHEMA_VERSION:
            continue
        if payload_json.get("registry_hash") != registry_hash:
            continue
        if commit_hash and packet.get("commit_hash") != commit_hash:
            continue
        return packet
    return None


def record_operator_question_journey_registry_receipt(
    *,
    repo_root: str | Path = ROOT,
    db_path: str | Path | None = None,
    commit_hash: str | None = None,
    generated_at: str | None = None,
    ensure: bool = True,
) -> str:
    payload = build_operator_question_journey_registry(repo_root=repo_root, generated_at=generated_at)
    registry_hash = payload["registry_hash"]
    if ensure:
        existing = _find_existing_operator_question_journey_registry_receipt(
            registry_hash=registry_hash,
            commit_hash=commit_hash,
            db_path=db_path,
        )
        if existing:
            return str(existing.get("receipt_id") or existing.get("packet_id") or "")

    init_business_ops_ledger(str(db_path) if db_path else None)
    receipt_payload = {
        "contract_id": SCHEMA_VERSION,
        "registry_hash": registry_hash,
        "generated_read_model_paths": [
            f"generated/read_models/{JSON_EXPORT_NAME}",
            f"generated/read_models/{OPERATOR_EXPORT_NAME}",
        ],
        "journey_count": payload["journey_count"],
        "source_type_vocab": list(SOURCE_TYPES),
        "journey_classification_vocab": list(JOURNEY_CLASSIFICATIONS),
        "status_vocab": list(JOURNEY_STATUSES),
        "doctrine_source_labels": list(DOCTRINE_SOURCE_LABELS),
        "metadata_only": True,
        "raw_private_chat_bodies_stored": False,
        "raw_private_file_bodies_stored": False,
        "raw_logs_stored": False,
        "broad_file_dumps_stored": False,
        "credentials_stored": False,
        "secrets_stored": False,
        "c_drive_artifact_written": False,
        "runtime_activation": False,
        "authority_flags": dict(NO_AUTHORITY_FLAGS),
    }
    return record_receipt(
        receipt_type="generated_status",
        payload=receipt_payload,
        commit_hash=commit_hash,
        artifact_type="operator_question_journey_registry",
        artifact_status="captured_metadata_only",
        authority_status="generated_status_only",
        runtime_activation=False,
        sqlite_meaning="receipt_record_only",
        source_basis=list(DOCTRINE_SOURCE_LABELS),
        actor="operator_question_journey_registry_v0",
        created_at=generated_at,
        db_path=str(db_path) if db_path else None,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Operator Question Journey Registry read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    parser.add_argument(
        "--record-receipt",
        action="store_true",
        help="Also record a metadata-only generated_status receipt in the existing ledger.",
    )
    parser.add_argument("--db", help="SQLite ledger path. Defaults to the Business Ops ledger.")
    parser.add_argument("--commit-hash", help="Optional commit hash to bind to the metadata receipt.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_operator_question_journey_registry(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    receipt_id = ""
    if args.record_receipt:
        receipt_id = record_operator_question_journey_registry_receipt(
            repo_root=args.repo_root,
            db_path=args.db,
            commit_hash=args.commit_hash,
            ensure=True,
        )

    root = _rooted(args.export_root, repo_root=args.repo_root)
    if args.format == "json":
        print((root / JSON_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print((root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    else:
        summary = result.__dict__.copy()
        if args.record_receipt:
            summary["sqlite_receipt_id"] = receipt_id
            summary["sqlite_receipt_recorded"] = bool(receipt_id)
        print(stable_json(summary), end="")
    return 0 if result.schema_version == SCHEMA_VERSION and (not args.record_receipt or receipt_id) else 1


__all__ = [
    "AFFECTED_SYSTEM_AREAS",
    "CONFIDENCE_STATES",
    "JOURNEY_CLASSIFICATIONS",
    "JOURNEY_STATUSES",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "SOURCE_TYPES",
    "build_operator_question_journey_registry",
    "export_operator_question_journey_registry",
    "format_operator_question_journey_registry",
    "record_operator_question_journey_registry_receipt",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
