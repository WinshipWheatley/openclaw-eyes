"""Package Compiler Contract v0 for OpenClaw.

This read-model defines the first deterministic package compiler skeleton for
Mission Control package previews. It is metadata only. It does not run a
package, call a model, activate an agent, launch a workbench, wire tools,
access browser/account surfaces, send, submit, approve, repair, delete, remount,
handle credentials, mutate the Mac app, or write OpenClaw artifacts to the PC
system drive.
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

SCHEMA_VERSION = "package_compiler_contract_v0"
JSON_EXPORT_NAME = "package_compiler_contract.json"
OPERATOR_EXPORT_NAME = "package_compiler_contract_OPERATOR.md"

PACKAGE_SCHEMA_FIELDS = (
    "package_id",
    "package_type",
    "source_lane_id",
    "source_lane_type",
    "steel_thread_template_id",
    "target_workbench_or_actor_host",
    "actor_model_candidate",
    "agent_character",
    "mission",
    "operator_eli5",
    "stakes_why_it_matters",
    "context_included",
    "context_excluded",
    "evidence_refs",
    "read_model_refs",
    "allowed_plugins_or_capabilities",
    "forbidden_plugins_or_capabilities",
    "security_clearance",
    "authority_boundary",
    "steps",
    "stop_conditions",
    "expected_outputs",
    "proof_requirements",
    "receipt_requirements",
    "confidence_state",
    "confidence_inputs",
    "detour_options",
    "current_availability",
    "failure_reset_behavior",
    "quiet_condition",
    "human_confirmation_required",
    "prompt_prose",
)

PACKAGE_TYPES = (
    "check_light_diagnostic_package",
    "helm_lane_awareness_package",
    "world_lane_work_package",
    "design_memory_discovery_package",
    "bridge_sync_diagnostic_package",
    "workbench_actor_review_package",
    "code_implementation_package",
    "verification_review_package",
    "tell_system_whats_missing_package",
    "confidence_detour_package",
)

STEEL_THREAD_TEMPLATE_IDS = (
    "helm_lane",
    "check_light_lane",
    "world_lane",
    "nested_lane",
    "proof_detail_lane",
    "package_preview_lane",
    "confidence_detour_lane",
    "parked_lane",
)

CURRENT_AVAILABILITY_STATES = (
    "preview_only",
    "copy_export_only",
    "request_only_future",
    "launch_future_gated",
    "launch_allowed_later",
)

DETERMINISTIC_REQUIRED_FIELDS = (
    "package_id",
    "package_type",
    "source_lane_id",
    "source_lane_type",
    "steel_thread_template_id",
    "target_workbench_or_actor_host",
    "actor_model_candidate",
    "agent_character",
    "context_included",
    "context_excluded",
    "evidence_refs",
    "read_model_refs",
    "allowed_plugins_or_capabilities",
    "forbidden_plugins_or_capabilities",
    "security_clearance",
    "authority_boundary",
    "steps",
    "stop_conditions",
    "proof_requirements",
    "receipt_requirements",
    "confidence_state",
    "confidence_inputs",
    "detour_options",
    "current_availability",
    "failure_reset_behavior",
    "quiet_condition",
    "human_confirmation_required",
)

LM_ASSISTED_ALLOWED_FIELDS_EARLY = (
    "operator_eli5",
    "mission",
    "stakes_why_it_matters",
    "detour_explanation",
    "package_summary",
    "prompt_prose",
    "risk_explanation",
)

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "metadata_only": True,
    "compiler_contract_only": True,
    "package_preview_only": True,
    "external_model_apis_called": False,
    "lm_called": False,
    "agents_activated": False,
    "agent_launch_authority_added": False,
    "model_or_agent_call_allowed": False,
    "tool_or_plugin_execution_authority_added": False,
    "tools_wired": False,
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
    "runtime_authority_added": False,
    "execution_authority_added": False,
    "automatic_repair_authority_added": False,
    "live_launch_buttons_created": False,
    "mission_control_app_changed": False,
    "mac_app_files_mutated": False,
    "delete_authority_added": False,
    "cleanup_authority_added": False,
    "remount_authority_added": False,
    "credential_handling_added": False,
    "c_drive_write_allowed": False,
    "c_drive_artifact_written": False,
    "raw_private_content_inspected": False,
    "raw_logs_stored": False,
    "broad_file_dump_stored": False,
}


@dataclass(frozen=True)
class SourceReadModel:
    key: str
    path: str
    role: str


@dataclass(frozen=True)
class PackageTypeSpec:
    package_type: str
    display_name: str
    purpose: str
    steel_thread_template_id: str
    default_agent_character: str
    likely_workbench_or_actor_host: str
    current_availability: str


@dataclass(frozen=True)
class PackageCompilerContractExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    package_type_count: int
    sample_package_count: int
    sqlite_receipt_supported: bool
    c_drive_artifact_written: bool
    runtime_authority_added: bool


SOURCE_READ_MODELS = (
    SourceReadModel(
        "steel_thread_lane_template_registry",
        "generated/read_models/steel_thread_lane_template_registry.json",
        "reusable steel-thread template catalog",
    ),
    SourceReadModel(
        "operator_workbench_actor_host_registry",
        "generated/read_models/operator_workbench_actor_host_registry.json",
        "actor/workbench host registry and routing metadata",
    ),
    SourceReadModel(
        "operator_nested_lane_mission_package_spine",
        "generated/read_models/operator_nested_lane_mission_package_spine.json",
        "nested lane and mission package doctrine",
    ),
    SourceReadModel(
        "operator_awareness_agent_package_spine",
        "generated/read_models/operator_awareness_agent_package_spine.json",
        "awareness gap package preview and confidence repair doctrine",
    ),
    SourceReadModel(
        "agent_work_packets",
        "generated/read_models/agent_work_packets.json",
        "existing bounded planning packet read-model substrate",
    ),
    SourceReadModel(
        "system_health_lights_taxonomy",
        "generated/read_models/system_health_lights_taxonomy.json",
        "check-light lane examples and current system-health posture",
    ),
)

SOURCE_FILES = (
    "agent_work_packet.py",
    "operator_awareness_agent_package_spine.py",
    "operator_nested_lane_mission_package_spine.py",
    "operator_workbench_actor_host_registry.py",
    "steel_thread_lane_template_registry.py",
    "business_ops_ledger.py",
)

DOCTRINE_SOURCE_LABELS = (
    "operator_prompt: Package Compiler Skeleton / Prompt Package Contract v0",
    "existing_contract: Steel Thread Lane Template Registry v0",
    "existing_contract: Operator Workbench / Actor Host Registry v0",
    "existing_contract: Operator Awareness + Agent Package Spine v0",
    "existing_contract: Operator Nested Lane Mission Package Spine v0",
    "existing_substrate: Agent Work Packet v0",
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
        "truth_status": "source_evidence_for_contract_not_runtime_authority",
        "metadata_only": True,
        "body_exported": False,
        "raw_private_content_read": False,
        "executed_or_dispatched": False,
    }


def _source_file_record(path: str, *, repo_root: str | Path) -> dict[str, Any]:
    target = _rooted(path, repo_root=repo_root)
    return {
        "path": path,
        "present": target.exists(),
        "role": "source_contract_or_existing_pattern_reference",
        "body_exported": False,
        "runtime_imported_for_execution": False,
        "executed_or_dispatched": False,
    }


def _relationship_to_existing_contracts() -> dict[str, Any]:
    return {
        "added_scope": "package schema, package types, compiler input rules, deterministic versus assisted field boundaries, routing hooks, sample outlines, and preview-only authority posture",
        "does_not_replace_agent_work_packets": True,
        "agent_work_packets_still_own": "SQLite-backed bounded planning packets derived from routed intents",
        "does_not_replace_awareness_or_nested_package_spines": True,
        "awareness_and_nested_spines_still_own": "specific awareness gap items, nested lane topology, and existing package preview examples",
        "does_not_replace_workbench_registry": True,
        "workbench_registry_still_owns": "actor/workbench host inventory, autonomy levels, and receipt expectations",
        "does_not_replace_steel_thread_template_registry": True,
        "steel_thread_template_registry_still_owns": "lane template rendering pattern and safe control behavior",
        "compiler_contract_role": "defines how future deterministic package compilation should shape package bodies before any launch authority exists",
    }


def _source_state_summary(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    workbench = sources.get("operator_workbench_actor_host_registry", {})
    routing = workbench.get("actor_routing_summary", {})
    steel = sources.get("steel_thread_lane_template_registry", {})
    return {
        "steel_thread_lane_template_registry": {
            "available": bool(steel),
            "template_type_count": steel.get("template_type_count"),
            "template_types": steel.get("template_types", []),
        },
        "operator_workbench_actor_host_registry": {
            "available": bool(workbench),
            "host_count": workbench.get("host_count"),
            "registered_host_ids": routing.get("registered_host_ids", []),
        },
        "operator_nested_lane_mission_package_spine": {
            "available": bool(sources.get("operator_nested_lane_mission_package_spine")),
            "package_preview_only": sources.get("operator_nested_lane_mission_package_spine", {}).get("package_preview_only"),
        },
        "operator_awareness_agent_package_spine": {
            "available": bool(sources.get("operator_awareness_agent_package_spine")),
            "package_preview_only": sources.get("operator_awareness_agent_package_spine", {}).get("package_preview_only"),
        },
        "agent_work_packets": {
            "available": bool(sources.get("agent_work_packets")),
            "mode": sources.get("agent_work_packets", {}).get("mode"),
            "execution_allowed": sources.get("agent_work_packets", {}).get("execution_allowed"),
        },
        "system_health_lights_taxonomy": {
            "available": bool(sources.get("system_health_lights_taxonomy")),
            "current_light_states": sources.get("system_health_lights_taxonomy", {}).get("current_light_states", {}),
        },
    }


def _package_schema() -> dict[str, Any]:
    return {
        "fields": list(PACKAGE_SCHEMA_FIELDS),
        "field_count": len(PACKAGE_SCHEMA_FIELDS),
        "schema_is_preview_contract_not_runner": True,
        "actor_does_not_self_assign_authority": True,
        "unknown_required_field_fails_closed": True,
        "current_availability_states": list(CURRENT_AVAILABILITY_STATES),
        "package_body_hash_required_before_future_dispatch": True,
        "human_confirmation_required_by_default": True,
    }


def _package_type_specs() -> tuple[PackageTypeSpec, ...]:
    return (
        PackageTypeSpec(
            "check_light_diagnostic_package",
            "Check-Light Diagnostic Package",
            "Diagnose a system health light such as Check Engine, Check Transmission, Resources, Parking Brake, or Traction Control.",
            "check_light_lane",
            "Chief with Guardian or Mirror Trust when appropriate",
            "pc_wsl_repo_a",
            "preview_only",
        ),
        PackageTypeSpec(
            "helm_lane_awareness_package",
            "Helm Lane Awareness Package",
            "Explain an active helm/build lane, its proof, and its next safe move.",
            "helm_lane",
            "Chief",
            "gpt_5_5_chatgpt_orchestrator",
            "preview_only",
        ),
        PackageTypeSpec(
            "world_lane_work_package",
            "World Lane Work Package",
            "Prepare domain/world work without cluttering the helm.",
            "world_lane",
            "domain_character_by_world",
            "operator_selected_future_host",
            "launch_future_gated",
        ),
        PackageTypeSpec(
            "design_memory_discovery_package",
            "Design Memory Discovery Package",
            "Raise design-memory awareness without ingesting broad raw archives.",
            "nested_lane",
            "Chief with Hermes advisory posture",
            "antigravity_gemini_flash_high",
            "preview_only",
        ),
        PackageTypeSpec(
            "bridge_sync_diagnostic_package",
            "Bridge Sync Diagnostic Package",
            "Inspect PC/Mac mirror proof, missing files, stale hashes, and safe next sync proof.",
            "check_light_lane",
            "Chief with Mirror Trust posture",
            "pc_wsl_repo_a",
            "preview_only",
        ),
        PackageTypeSpec(
            "workbench_actor_review_package",
            "Workbench Actor Review Package",
            "Review whether a workbench/actor host is suited for a lane.",
            "package_preview_lane",
            "Chief with Guardian boundary review",
            "gpt_5_5_chatgpt_orchestrator",
            "preview_only",
        ),
        PackageTypeSpec(
            "code_implementation_package",
            "Code Implementation Package",
            "Prepare scoped implementation work with file boundaries, tests, and receipt requirements.",
            "package_preview_lane",
            "Chief",
            "codex_vscode_mac_codex_desktop",
            "copy_export_only",
        ),
        PackageTypeSpec(
            "verification_review_package",
            "Verification Review Package",
            "Prepare bounded review/verification work for an independent actor.",
            "package_preview_lane",
            "Guardian or Chief",
            "antigravity_gemini_flash_high",
            "copy_export_only",
        ),
        PackageTypeSpec(
            "tell_system_whats_missing_package",
            "Tell System What's Missing Package",
            "Capture an operator memory comparison as a future context artifact, not as truth.",
            "confidence_detour_lane",
            "Chief",
            "pc_wsl_repo_a",
            "request_only_future",
        ),
        PackageTypeSpec(
            "confidence_detour_package",
            "Confidence Detour Package",
            "Raise confidence by adding bounded context, proof, classification, or operator memory comparison.",
            "confidence_detour_lane",
            "Chief with domain character if classified",
            "operator_selected_future_host",
            "preview_only",
        ),
    )


def _package_type_record(spec: PackageTypeSpec) -> dict[str, Any]:
    return {
        "package_type": spec.package_type,
        "display_name": spec.display_name,
        "purpose": spec.purpose,
        "steel_thread_template_id": spec.steel_thread_template_id,
        "default_agent_character": spec.default_agent_character,
        "likely_workbench_or_actor_host": spec.likely_workbench_or_actor_host,
        "current_availability": spec.current_availability,
        "runtime_authority_added": False,
        "launch_allowed_now": False,
        "dispatch_allowed_now": False,
        "requires_future_receipt_before_state_ingest": True,
    }


def _actor_workbench_routing_hooks(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    routing = sources.get("operator_workbench_actor_host_registry", {}).get("actor_routing_summary", {})
    return {
        "source_registry": "operator_workbench_actor_host_registry",
        "model_is_actor_agent_is_character_package_is_script": True,
        "model_definition": "The language model is the actor that may perform work later.",
        "agent_definition": "The agent is the character/persona the actor plays.",
        "package_definition": "The package is the script, context, tools, clearance, steps, boundaries, and proof requirements.",
        "system_decides_authority_before_launch": True,
        "actor_must_not_decide_own_authority_context_plugins_clearance_or_lane": True,
        "route_by": [
            "lane_type",
            "package_type",
            "risk",
            "domain",
            "required_proof",
            "allowed_authority",
            "workbench_fit",
        ],
        "registered_host_ids_from_source": routing.get("registered_host_ids", []),
        "example_routes": [
            {
                "actor_or_workbench": "Codex",
                "host_id": "codex_vscode_mac_codex_desktop",
                "fit": "scoped implementation worker, file edits, tests, builds, screenshots when explicitly prompted",
                "current_status": "package_preview_or_copy_export_only_in_this_contract",
            },
            {
                "actor_or_workbench": "Antigravity / Gemini",
                "host_id": "antigravity_gemini_flash_high",
                "fit": "fast planner, verifier, reviewer, package drafter",
                "current_status": "package_preview_or_copy_export_only_in_this_contract",
            },
            {
                "actor_or_workbench": "GPT-5.5 / ChatGPT orchestrator",
                "host_id": "gpt_5_5_chatgpt_orchestrator",
                "fit": "orchestration, architecture, taste, safety judgment, package authoring",
                "current_status": "metadata_reference_only_in_this_contract",
            },
            {
                "actor_or_workbench": "Repo A",
                "host_id": "pc_wsl_repo_a",
                "fit": "canonical contracts, read-model generation, focused tests, metadata receipts",
                "current_status": "available_for_this_backend_contract_lane",
            },
        ],
        "agent_character_examples": [
            {"agent_character": "Chief", "fit": "system diagnostic, coordination, build/work queue"},
            {"agent_character": "Guardian", "fit": "boundary, safety, clearance, security posture"},
            {"agent_character": "Niles", "fit": "music/art lanes"},
            {"agent_character": "Cassandra", "fit": "communications and operator-facing drafts/proof visibility"},
            {"agent_character": "Hermes", "fit": "bridge/state-transfer advisory and synthesis"},
        ],
        "unknown_actor_or_host": {
            "routing": "fail_closed",
            "confidence_posture": "UNKNOWN_FAIL_CLOSED",
            "safe_next_move": "add or update metadata registry entry before launch",
        },
        "model_actor_selected_now": False,
        "agent_character_activated_now": False,
        "workspace_launched_now": False,
    }


def _deterministic_vs_lm_assisted_generation() -> dict[str, Any]:
    return {
        "deterministic_required_fields": list(DETERMINISTIC_REQUIRED_FIELDS),
        "lm_assisted_allowed_fields_early": list(LM_ASSISTED_ALLOWED_FIELDS_EARLY),
        "deterministic_fields_explanation": "Authority, allowed context, clearance, tools, proof, receipts, stops, availability, and quiet conditions come from contracts/read-models, not model improvisation.",
        "lm_assisted_fields_explanation": "Operator prose may be drafted later, but it cannot add authority or missing proof.",
        "lm_must_not_add_authority_tools_paths_secrets_plugins_or_execution_steps": True,
        "unknown_or_unavailable_actor_fails_closed": True,
        "deterministic_compiler_inputs": [
            "lane type",
            "read-model/evidence inputs",
            "actor/workbench registry metadata",
            "agent character registry metadata",
            "clearance and authority boundary",
            "allowed/forbidden capabilities",
            "confidence and detour state",
            "proof and receipt requirements",
        ],
    }


def _confidence_detour_behavior() -> dict[str, Any]:
    return {
        "below_deterministic": {
            "show_confidence_issue": True,
            "show_detour_options": True,
            "show_missing_inputs": True,
            "do_not_pretend_missing_context_exists": True,
        },
        "deterministic_or_full_trust": {
            "hide_confidence_score": True,
            "hide_detour_ui": True,
            "display_quiet_when_no_attention_needed": True,
        },
        "job_failure": {
            "reset_confidence": True,
            "reopen_detour_path": True,
            "show_failed_proof_or_receipt": True,
        },
        "no_confidence_theater_when_proof_is_deterministic": True,
    }


def _current_authority_state() -> dict[str, Any]:
    return {
        "package_generation_now": ["preview_only", "copy_export_only", "future_gated"],
        "live_launch_allowed_now": False,
        "model_agent_tool_call_from_app_allowed_now": False,
        "send_submit_approval_runtime_allowed_now": False,
        "browser_oauth_account_access_allowed_now": False,
        "automatic_repair_allowed_now": False,
        "mission_control_buttons_added": False,
        "package_runner_created": False,
        "meaning": "This contract can show and export package structure, but it cannot dispatch or execute packages.",
    }


def _authority_boundary() -> dict[str, Any]:
    return {
        "metadata_only": True,
        "preview_only": True,
        "runtime_authority_added": False,
        "model_or_agent_call_allowed": False,
        "tool_or_plugin_execution_allowed": False,
        "send_submit_approval_allowed": False,
        "browser_oauth_account_access_allowed": False,
        "automatic_repair_allowed": False,
        "credential_handling_allowed": False,
        "c_drive_artifact_written": False,
    }


def _sample_package(
    *,
    package_id: str,
    package_type: str,
    source_lane_id: str,
    source_lane_type: str,
    steel_thread_template_id: str,
    target_workbench_or_actor_host: str,
    actor_model_candidate: str,
    agent_character: str,
    mission: str,
    operator_eli5: str,
    context_included: list[str],
    evidence_refs: list[str],
    read_model_refs: list[str],
) -> dict[str, Any]:
    body = {
        "package_id": package_id,
        "package_type": package_type,
        "source_lane_id": source_lane_id,
        "source_lane_type": source_lane_type,
        "steel_thread_template_id": steel_thread_template_id,
        "target_workbench_or_actor_host": target_workbench_or_actor_host,
        "actor_model_candidate": actor_model_candidate,
        "agent_character": agent_character,
        "mission": mission,
        "operator_eli5": operator_eli5,
        "stakes_why_it_matters": "The operator should see the right package before any future workbench receives it.",
        "context_included": context_included,
        "context_excluded": [
            "credentials",
            "raw private file bodies",
            "raw logs",
            "browser/account sessions",
            "unapproved external service data",
        ],
        "evidence_refs": evidence_refs,
        "read_model_refs": read_model_refs,
        "allowed_plugins_or_capabilities": ["read-model inspection metadata", "receipt review metadata"],
        "forbidden_plugins_or_capabilities": [
            "live plugin execution",
            "account access",
            "send/submit/approval",
            "runtime repair",
        ],
        "security_clearance": "metadata_review_only_no_live_authority",
        "authority_boundary": _authority_boundary(),
        "steps": [
            "Read operator orientation.",
            "Inspect machine proof references.",
            "Verify allowed and excluded context.",
            "Produce expected output only.",
            "Stop before any blocked authority.",
        ],
        "stop_conditions": [
            "missing deterministic authority boundary",
            "unknown actor or workbench host",
            "need for credentials or account access",
            "need for live model/tool/agent/browser/runtime execution",
        ],
        "expected_outputs": [
            "operator-readable diagnosis or review",
            "proof/receipt references",
            "safe next move",
            "blocked or missing inputs",
        ],
        "proof_requirements": ["source read-model references", "authority boundary confirmation", "validation or not-run reason"],
        "receipt_requirements": ["metadata-only receipt before any future state ingest"],
        "confidence_state": "below_deterministic_until_returned_receipt_or_proof",
        "confidence_inputs": ["source read-model presence", "hash/current proof where applicable", "explicit blocked authority list"],
        "detour_options": ["raise missing proof", "operator memory comparison", "classification review"],
        "current_availability": "preview_only",
        "available_modes": ["preview_only", "copy_export_only", "launch_future_gated"],
        "failure_reset_behavior": "failure resets confidence and reopens detour path",
        "quiet_condition": "quiet only when proof/receipt is current or lane is intentionally parked",
        "human_confirmation_required": True,
        "prompt_prose": "Example outline only; not dispatched.",
        "sample_only": True,
        "dispatch_allowed_now": False,
        "launch_allowed_now": False,
    }
    return {
        **body,
        "package_hash_or_deterministic_placeholder": _hash_payload(body),
    }


def _sample_packages() -> list[dict[str, Any]]:
    return [
        _sample_package(
            package_id="sample_check_transmission_diagnostic_package",
            package_type="bridge_sync_diagnostic_package",
            source_lane_id="check_transmission",
            source_lane_type="check_light_lane",
            steel_thread_template_id="check_light_lane",
            target_workbench_or_actor_host="pc_wsl_repo_a",
            actor_model_candidate="future selected model, not live",
            agent_character="Chief with Mirror Trust posture",
            mission="Diagnose whether PC proof, Mac manifest, and sync health agree without remounting or repairing anything.",
            operator_eli5="Check whether the bridge proof is current and what must happen next.",
            context_included=["sync health posture", "Mac completion marker metadata", "manifest counts", "missing/stale file names"],
            evidence_refs=["generated/read_models/sync_health.json", "shuttle completion marker metadata"],
            read_model_refs=["sync_health.json", "system_health_lights_taxonomy.json", "bridge_trust_sync_truth.json"],
        ),
        _sample_package(
            package_id="sample_mission_control_ui_implementation_package_for_codex",
            package_type="code_implementation_package",
            source_lane_id="mission_control_steel_thread_surface",
            source_lane_type="helm_lane",
            steel_thread_template_id="package_preview_lane",
            target_workbench_or_actor_host="codex_vscode_mac_codex_desktop",
            actor_model_candidate="Codex candidate label only",
            agent_character="Chief implementation worker",
            mission="Implement a scoped Mission Control surface after a future UI lane grants explicit Mac app authority.",
            operator_eli5="Show what Codex would receive later for a bounded UI implementation lane.",
            context_included=["steel-thread template fields", "Mac rendering guidance", "exact file boundaries when supplied later"],
            evidence_refs=["generated/read_models/steel_thread_lane_template_registry.json"],
            read_model_refs=["steel_thread_lane_template_registry.json", "operator_mission_priority_helm_declutter.json"],
        ),
        _sample_package(
            package_id="sample_antigravity_verification_review_package",
            package_type="verification_review_package",
            source_lane_id="package_contract_verification",
            source_lane_type="helm_lane",
            steel_thread_template_id="package_preview_lane",
            target_workbench_or_actor_host="antigravity_gemini_flash_high",
            actor_model_candidate="Gemini 3.5 Flash High candidate label only",
            agent_character="Guardian verification reviewer",
            mission="Review a bounded contract/read-model change for missing tests, authority creep, and proof gaps.",
            operator_eli5="Show what a fast verifier could review later without giving it control.",
            context_included=["diff summary", "test list", "authority boundary checklist"],
            evidence_refs=["focused test output", "generated JSON parse result", "diff check result"],
            read_model_refs=["package_compiler_contract.json", "operator_workbench_actor_host_registry.json"],
        ),
    ]


def _unknown_source_policy() -> dict[str, Any]:
    return {
        "do_not_invent_source_facts": True,
        "static_contract_still_renders": True,
        "missing_source_display": "unavailable_source_reference",
        "missing_source_never_becomes_truth": True,
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
        "stores_raw_private_file_bodies": False,
        "stores_raw_logs": False,
        "stores_broad_file_dumps": False,
        "stores_runtime_activation": False,
        "receipt_writer_function": "record_package_compiler_contract_receipt",
        "contract_hash": payload["contract_hash"],
    }


def build_package_compiler_contract(
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
    source_file_records = [
        _source_file_record(path, repo_root=repo_root)
        for path in SOURCE_FILES
    ]
    package_types = [_package_type_record(spec) for spec in _package_type_specs()]
    samples = _sample_packages()
    contract_hash = _hash_payload(
        {
            "schema_version": SCHEMA_VERSION,
            "package_schema_fields": list(PACKAGE_SCHEMA_FIELDS),
            "package_types": package_types,
            "deterministic_required_fields": list(DETERMINISTIC_REQUIRED_FIELDS),
            "lm_assisted_allowed_fields_early": list(LM_ASSISTED_ALLOWED_FIELDS_EARLY),
        }
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "package_compiler_contract",
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "lane": "Package Compiler Skeleton / Prompt Package Contract v0",
        "contract_status": "deterministic_metadata_only_package_compiler_skeleton",
        "purpose": "Define how Mission Control should compile previewable package bodies from deterministic lane, proof, actor, character, clearance, steps, confidence, and receipt inputs.",
        "what_is_a_package": {
            "model_is_actor": True,
            "agent_is_character": True,
            "package_is_script_context_tools_clearance_steps_boundaries_proof": True,
            "mission_impossible_doctrine": "The package should make the actor effective because the role, script, context, tools, boundaries, and proof requirements are prepared before launch.",
        },
        "relationship_to_existing_contracts": _relationship_to_existing_contracts(),
        "package_schema": _package_schema(),
        "package_types": package_types,
        "package_type_count": len(package_types),
        "actor_workbench_routing_hooks": _actor_workbench_routing_hooks(sources),
        "deterministic_vs_lm_assisted_generation": _deterministic_vs_lm_assisted_generation(),
        "confidence_detour_behavior": _confidence_detour_behavior(),
        "current_authority_state": _current_authority_state(),
        "sample_package_outlines": samples,
        "sample_package_count": len(samples),
        "source_state_summary": _source_state_summary(sources),
        "unknown_or_missing_source_policy": _unknown_source_policy(),
        "mac_mission_control_rendering": {
            "show_package_preview": True,
            "show_actor_agent_workbench_summary": True,
            "show_deterministic_boundary": True,
            "show_lm_assisted_prose_as_optional_not_authority": True,
            "show_future_gated_launch_target_without_launching": True,
            "do_not_render_as_live_button": True,
        },
        "machine_proof": {
            "source_read_models": source_records,
            "source_files": source_file_records,
            "source_read_models_present": {key: bool(value) for key, value in sources.items()},
            "ledger_pattern_present": _rooted("business_ops_ledger.py", repo_root=repo_root).exists(),
            "generated_outputs": [
                f"generated/read_models/{JSON_EXPORT_NAME}",
                f"generated/read_models/{OPERATOR_EXPORT_NAME}",
            ],
        },
        "contract_hash": contract_hash,
        "sqlite_ledger_receipt_contract": {},
        "next_safe_lane": "Mission Control Package Preview Readback Surface v0",
        "no_live_authority_statement": "This is a package compiler contract and preview skeleton only; no package runner, launch, model call, agent activation, tool execution, account access, send, submit, approval, repair, or runtime authority is added.",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    payload["sqlite_ledger_receipt_contract"] = _sqlite_receipt_contract(payload)
    return payload


def format_package_compiler_contract(payload: dict[str, Any]) -> str:
    generation = payload["deterministic_vs_lm_assisted_generation"]
    authority = payload["current_authority_state"]
    lines = [
        "# Package Compiler Contract v0",
        "",
        "Status:",
        "- Deterministic metadata-only package compiler skeleton.",
        "- Backend/read-model contract only; no live runner, model call, agent launch, or app UI lane.",
        "",
        "## What Is A Package?",
        "- The model is the actor.",
        "- The agent is the character/persona.",
        "- The package is the script, context, tools, clearance, steps, boundaries, and proof requirements.",
        "- The actor does not decide its own authority, context, plugins, clearance, or mission.",
        "",
        "## How Packages Are Compiled",
        "- Compile from lane type, read-model/evidence inputs, actor/workbench metadata, agent character, clearance, allowed/forbidden capabilities, steps, stop conditions, confidence/detour state, proof requirements, receipt requirements, authority boundary, and workspace/chat target.",
        "",
        "## Deterministic Fields",
        "- " + ", ".join(f"`{field}`" for field in generation["deterministic_required_fields"]) + ".",
        "",
        "## LM-Assisted Fields",
        "- " + ", ".join(f"`{field}`" for field in generation["lm_assisted_allowed_fields_early"]) + ".",
        "- LM-assisted prose cannot add authority, tools, paths, secrets, plugins, or execution steps.",
        "",
        "## Package Types",
    ]
    for package_type in payload["package_types"]:
        lines.append(f"- `{package_type['package_type']}`: {package_type['display_name']} -> `{package_type['steel_thread_template_id']}`.")
    lines.extend(
        [
            "",
            "## Actor / Workbench Routing",
            "- Source registry: `operator_workbench_actor_host_registry`.",
            "- Unknown actor or host fails closed.",
            "- Routes include Codex for scoped implementation, Antigravity/Gemini for bounded verification/review, GPT-5.5 orchestrator for synthesis, and Repo A for deterministic contract/export/test work.",
            "",
            "## Preview Only Now",
            "- " + ", ".join(f"`{item}`" for item in authority["package_generation_now"]) + ".",
            "- Live launch allowed now: `false`.",
            "- Model/agent/tool call from app allowed now: `false`.",
            "",
            "## Future-Gated",
            "- Launching a workbench, dispatching to an actor, ingesting returned state, send/submit/approval, browser/account access, and automatic repair remain future-gated.",
            "",
            "## Authority Boundary",
            "- No external model APIs, Codex/Antigravity/VS Code agent sessions, Mission Control app mutation, live launch buttons, runtime execution, browser/OAuth/Gmail/calendar/Coupa/Telegram/send/submit/approval authority, automatic repair, system-drive artifact writes, deletes, cleanup, repair, remount, or credential handling.",
            "",
            "## Sample Packages",
        ]
    )
    for sample in payload["sample_package_outlines"]:
        lines.append(f"- `{sample['package_id']}`: {sample['mission']}")
    lines.extend(
        [
            "",
            "## What Mission Control Can Render",
            "- Package schema fields, package type, source lane, steel-thread template, actor/workbench target, agent character, included/excluded context, confidence/detour state, authority boundary, and receipt requirements.",
            "- Mission Control can show the future chat/workspace target without launching it.",
            "",
            "## Next Safe Lane",
            f"- {payload['next_safe_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_package_compiler_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> PackageCompilerContractExportResult:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_package_compiler_contract(repo_root=root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_package_compiler_contract(payload), encoding="utf-8")
    return PackageCompilerContractExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        package_type_count=payload["package_type_count"],
        sample_package_count=payload["sample_package_count"],
        sqlite_receipt_supported=payload["sqlite_ledger_receipt_contract"]["supported_by_existing_pattern"],
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


def _find_existing_package_compiler_contract_receipt(
    *,
    contract_hash: str,
    commit_hash: str | None,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    for packet in _load_existing_receipt_payloads(db_path):
        payload_json = packet.get("payload_json")
        if not isinstance(payload_json, dict):
            continue
        if payload_json.get("contract_id") != SCHEMA_VERSION:
            continue
        if payload_json.get("contract_hash") != contract_hash:
            continue
        if commit_hash and packet.get("commit_hash") != commit_hash:
            continue
        return packet
    return None


def record_package_compiler_contract_receipt(
    *,
    repo_root: str | Path = ROOT,
    db_path: str | Path | None = None,
    commit_hash: str | None = None,
    generated_at: str | None = None,
    ensure: bool = True,
) -> str:
    payload = build_package_compiler_contract(repo_root=repo_root, generated_at=generated_at)
    contract_hash = payload["contract_hash"]
    if ensure:
        existing = _find_existing_package_compiler_contract_receipt(
            contract_hash=contract_hash,
            commit_hash=commit_hash,
            db_path=db_path,
        )
        if existing:
            return str(existing.get("receipt_id") or existing.get("packet_id") or "")

    init_business_ops_ledger(str(db_path) if db_path else None)
    receipt_payload = {
        "contract_id": SCHEMA_VERSION,
        "contract_hash": contract_hash,
        "generated_read_model_paths": [
            f"generated/read_models/{JSON_EXPORT_NAME}",
            f"generated/read_models/{OPERATOR_EXPORT_NAME}",
        ],
        "package_type_count": payload["package_type_count"],
        "sample_package_count": payload["sample_package_count"],
        "package_schema_fields": list(PACKAGE_SCHEMA_FIELDS),
        "doctrine_source_labels": list(DOCTRINE_SOURCE_LABELS),
        "metadata_only": True,
        "raw_logs_stored": False,
        "broad_file_dumps_stored": False,
        "raw_private_file_bodies_stored": False,
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
        artifact_type="package_compiler_contract",
        artifact_status="captured_metadata_only",
        authority_status="generated_status_only",
        runtime_activation=False,
        sqlite_meaning="receipt_record_only",
        source_basis=list(DOCTRINE_SOURCE_LABELS),
        actor="package_compiler_contract_v0",
        created_at=generated_at,
        db_path=str(db_path) if db_path else None,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Package Compiler Contract read-model.")
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
    result = export_package_compiler_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    receipt_id = ""
    if args.record_receipt:
        receipt_id = record_package_compiler_contract_receipt(
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
    "CURRENT_AVAILABILITY_STATES",
    "DETERMINISTIC_REQUIRED_FIELDS",
    "JSON_EXPORT_NAME",
    "LM_ASSISTED_ALLOWED_FIELDS_EARLY",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "PACKAGE_SCHEMA_FIELDS",
    "PACKAGE_TYPES",
    "SCHEMA_VERSION",
    "STEEL_THREAD_TEMPLATE_IDS",
    "build_package_compiler_contract",
    "export_package_compiler_contract",
    "format_package_compiler_contract",
    "record_package_compiler_contract_receipt",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
