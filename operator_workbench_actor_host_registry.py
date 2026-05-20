"""Operator Workbench / Actor Host Registry v0.

This read-model records known OpenClaw workbenches, actor hosts, and execution
surfaces as deterministic metadata only. It helps Mission Control reason about
where a future package belongs without launching agents, calling models, wiring
tools, opening accounts, writing PC C-drive artifacts, or creating runtime
authority.
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

SCHEMA_VERSION = "operator_workbench_actor_host_registry_v0"
JSON_EXPORT_NAME = "operator_workbench_actor_host_registry.json"
OPERATOR_EXPORT_NAME = "operator_workbench_actor_host_registry_OPERATOR.md"

HOST_CATEGORIES = (
    "canonical_repo",
    "helm_app",
    "implementation_worker",
    "fast_planner_verifier",
    "orchestrator",
    "build_environment",
    "terminal_surface",
    "agent_host_candidate",
)

HOST_STATUSES = (
    "available",
    "candidate",
    "future_gated",
    "blocked",
    "unknown",
)

AUTONOMY_LEVELS = (
    ("L0", "preview package only"),
    ("L1", "copy/open package in right workbench"),
    ("L2", "launch bounded session with package"),
    ("L3", "monitor session and ingest receipt"),
    ("L4", "auto-run safe maintenance lanes only"),
    ("L5", "broader execution after security/approval gates"),
)

HEALTH_LIGHTS = (
    "Check Engine",
    "Check Transmission",
    "Resources",
    "Parking Brake",
    "Traction Control",
)

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "metadata_only": True,
    "registry_only": True,
    "package_preview_only": True,
    "sqlite_receipt_metadata_only": True,
    "sqlite_schema_changed": False,
    "external_model_apis_called": False,
    "model_calls_made": False,
    "lm_called": False,
    "candidate_models_are_live_integrations": False,
    "agents_activated": False,
    "agent_launch_authority_added": False,
    "tools_enabled": False,
    "plugins_wired": False,
    "terminal_command_authority_added": False,
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
    "raw_tool_outputs_stored": False,
    "unknown_hosts_fail_closed": True,
}

FORBIDDEN_GLOBAL_ACTIONS = (
    "call external model APIs",
    "run Antigravity, Codex, VS Code agent, or other live sessions",
    "mutate Mission Control app files",
    "create live launch buttons",
    "open browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval flows",
    "create runtime execution authority",
    "write OpenClaw artifacts to the PC C: drive",
    "delete, cleanup, remount, or handle credentials",
)


@dataclass(frozen=True)
class SourceReadModel:
    key: str
    path: str
    role: str


@dataclass(frozen=True)
class WorkbenchHostSpec:
    host_id: str
    display_name: str
    category: str
    machine_location: str
    known_path_or_entrypoint: str
    best_roles: tuple[str, ...]
    risky_roles: tuple[str, ...]
    default_clearance: str
    allowed_autonomy_level_now: str
    future_autonomy_levels: tuple[str, ...]
    current_status: str
    health_light_relationship: tuple[str, ...]
    notes_for_prompting: str
    first_time_or_ambiguous_lane_default: str = "fail_closed_or_preview_only"
    observed_metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class OperatorWorkbenchActorHostRegistryExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    host_count: int
    sqlite_receipt_supported: bool
    c_drive_artifact_written: bool
    runtime_authority_added: bool


SOURCE_READ_MODELS = (
    SourceReadModel(
        "operator_nested_lane_mission_package_spine",
        "generated/read_models/operator_nested_lane_mission_package_spine.json",
        "lane/package grammar and future-gated workspace launch posture",
    ),
    SourceReadModel(
        "capability_skill_registry_metadata_delta",
        "generated/read_models/capability_skill_registry_metadata_delta.json",
        "metadata-only capability and skill posture",
    ),
    SourceReadModel(
        "system_health_lights_taxonomy",
        "generated/read_models/system_health_lights_taxonomy.json",
        "helm health lights and lane mapping",
    ),
    SourceReadModel(
        "sync_health",
        "generated/read_models/sync_health.json",
        "PC/Mac read-model mirror proof posture",
    ),
    SourceReadModel(
        "work_board",
        "generated/read_models/work_board.json",
        "bounded work visibility and parked/ready work posture",
    ),
    SourceReadModel(
        "operator_actions",
        "generated/read_models/operator_actions.json",
        "operator action posture and existing authority boundary",
    ),
    SourceReadModel(
        "business_ops_ledger",
        "business_ops_ledger.py",
        "existing metadata-only SQLite receipt pattern",
    ),
)

SOURCE_FILES = (
    "operator_nested_lane_mission_package_spine.py",
    "capability_skill_registry_metadata_delta.py",
    "system_health_lights_taxonomy.py",
    "business_ops_ledger.py",
    "generated_read_model_files.py",
)

DOCTRINE_SOURCE_LABELS = (
    "operator_prompt: Operator Workbench / Actor Host Registry v0",
    "existing_contract: Operator Awareness Nested Lane + Mission Package Spine v0",
    "existing_contract: System Health Lights Taxonomy v0",
    "repo_a_runtime_law: OPENCLAW_RUNTIME.md",
    "operator_identity_context: USER.md",
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
    target = _rooted(source.path, repo_root=repo_root)
    return {
        "key": source.key,
        "path": source.path,
        "present": target.exists(),
        "schema_version": payload.get("schema_version") or payload.get("read_model_version"),
        "role": source.role,
        "truth_status": "repo_a_source_or_read_model_evidence_not_external_tool_truth_by_itself",
        "metadata_only": True,
        "body_exported": False,
        "raw_tool_output_exported": False,
        "credentials_or_private_data_exported": False,
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


def _hash_payload(payload: Any) -> str:
    digest = hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _autonomy_level_progression() -> list[dict[str, str]]:
    return [
        {
            "level_id": level_id,
            "meaning": meaning,
            "status_now": "allowed_only_where_host_record_explicitly_allows_it",
        }
        for level_id, meaning in AUTONOMY_LEVELS
    ]


def _package_input_shape(spec: WorkbenchHostSpec) -> dict[str, Any]:
    return {
        "metadata_only": True,
        "live_launch_now": False,
        "package_id": "required_future_package_id",
        "lane_id": "required_future_lane_id",
        "actor_model_candidate": "metadata_label_or_unknown_fail_closed",
        "agent_character": "required_role_persona",
        "mission": "required_bounded_goal",
        "context_included": "read-model/proof/context references only",
        "context_excluded": "credentials, raw private bodies, broad logs, and unauthorized surfaces",
        "clearance": spec.default_clearance,
        "allowed_capabilities": "host-specific explicit list",
        "forbidden_capabilities": "host-specific explicit list",
        "steps_and_stop_conditions": "required_before_l2_or_higher",
        "proof_receipt_requirements": "required_before_result_ingest",
    }


def _expected_receipt_shape(spec: WorkbenchHostSpec) -> dict[str, Any]:
    return {
        "receipt_required_before_ingest": True,
        "metadata_only": True,
        "host_id": spec.host_id,
        "package_id": "same_as_package_or_fail_closed",
        "work_performed_summary": "bounded operator-readable summary",
        "files_changed": "explicit list or none",
        "commands_run": "explicit list or none",
        "tests_or_validation": "explicit result list or not_run_with_reason",
        "authority_boundary_confirmation": "required",
        "blocked_or_unknown_items": "required when incomplete",
        "raw_private_bodies_or_credentials_stored": False,
    }


def _credential_policy() -> dict[str, Any]:
    return {
        "credentials_stored_or_requested": False,
        "credential_prompts_handled_by_registry": False,
        "oauth_or_account_access_enabled": False,
        "unknown_credential_need_fails_closed": True,
    }


def _storage_policy() -> dict[str, Any]:
    return {
        "canonical_repo_outputs": "/home/openclaw/generated/read_models",
        "established_shuttle_root": "/mnt/e/openclaw",
        "openclaw_artifacts_on_c_drive_allowed": False,
        "raw_private_content_storage_allowed": False,
        "host_outputs_require_receipt_before_ingest": True,
    }


def _c_drive_policy(spec: WorkbenchHostSpec) -> dict[str, Any]:
    return {
        "applies": spec.machine_location in {"PC/WSL", "PC/Windows", "cross_machine"},
        "policy": "No OpenClaw artifacts, generated outputs, temp bundles, caches, or logs on the PC C: drive unless explicitly authorized by a later lane.",
        "current_lane_writes_to_c_drive": False,
        "safe_storage_roots": ["/home/openclaw", "/mnt/e/openclaw"],
    }


def _authority_boundary() -> dict[str, Any]:
    return {
        "read_model_only": True,
        "metadata_only": True,
        "live_launch_now": False,
        "model_call_made": False,
        "agent_activated": False,
        "tool_or_plugin_wired": False,
        "terminal_authority_added": False,
        "browser_oauth_account_authority_added": False,
        "send_submit_approval_authority_added": False,
        "runtime_authority_added": False,
        "c_drive_artifact_written": False,
    }


def _host_specs() -> tuple[WorkbenchHostSpec, ...]:
    return (
        WorkbenchHostSpec(
            host_id="pc_wsl_repo_a",
            display_name="PC/WSL Repo A",
            category="canonical_repo",
            machine_location="PC/WSL",
            known_path_or_entrypoint="/home/openclaw",
            best_roles=(
                "canonical backend/read-model contracts",
                "SQLite metadata receipts",
                "deterministic scripts and focused tests",
                "generated read-model export",
            ),
            risky_roles=(
                "live workflow execution by default",
                "account access",
                "external send or submit flows",
                "PC C: artifact storage",
            ),
            default_clearance="repo_a_contract_export_test_only_no_live_workflow_execution",
            allowed_autonomy_level_now="L2_SCOPED_READ_WRITE_EXPLICIT_PROMPT",
            future_autonomy_levels=("L3_MONITOR_SESSION_AND_INGEST_RECEIPT",),
            current_status="available",
            health_light_relationship=("Check Engine", "Check Transmission", "Resources", "Parking Brake"),
            notes_for_prompting="Use exact workspace, file scope, validation, no C-drive writes, receipt expectations, and stop conditions.",
        ),
        WorkbenchHostSpec(
            host_id="mac_mission_control_app",
            display_name="Mac Mission Control app",
            category="helm_app",
            machine_location="Mac",
            known_path_or_entrypoint="/Users/hwinshipwheatley/Developer/OpenClawMissionControl/OpenClaw Mission Controle",
            best_roles=(
                "helm UI display",
                "read-only local mirror consumption",
                "existing narrowly implemented sync marker write",
            ),
            risky_roles=(
                "backend command authority",
                "arbitrary filesystem mutation",
                "credential handling",
                "live repair control",
            ),
            default_clearance="display_local_mirror_and_existing_marker_write_only",
            allowed_autonomy_level_now="L1_DISPLAY_AND_EXISTING_MARKER_WRITE_ONLY",
            future_autonomy_levels=("L2_BOUNDED_UI_VALIDATION_PACKAGE", "L3_RECEIPT_READBACK"),
            current_status="available",
            health_light_relationship=("Check Transmission", "Parking Brake", "Traction Control"),
            notes_for_prompting="Treat as helm display, not backend executor; app code changes require a separate Mac app lane.",
        ),
        WorkbenchHostSpec(
            host_id="codex_vscode_mac_codex_desktop",
            display_name="Codex in VS Code / Mac Codex Desktop",
            category="implementation_worker",
            machine_location="PC/WSL or Mac",
            known_path_or_entrypoint="VS Code Codex or Mac Codex Desktop session",
            best_roles=(
                "scoped file edits",
                "tests and builds",
                "Xcode validation",
                "commits",
                "screenshots",
                "repo surgery",
            ),
            risky_roles=(
                "slow long-running loops",
                "tool friction",
                "window or screenshot fragility",
                "accidental scope drift if prompt is vague",
            ),
            default_clearance="scoped_read_write_workspace_when_explicitly_prompted",
            allowed_autonomy_level_now="L2_SCOPED_READ_WRITE_EXPLICIT_PROMPT",
            future_autonomy_levels=("L3_MONITOR_SESSION_AND_INGEST_RECEIPT",),
            current_status="available",
            health_light_relationship=("Check Engine", "Resources", "Traction Control"),
            notes_for_prompting="Give a clear lane, exact workspace, file boundaries, validation commands, commit rules, and stop conditions.",
        ),
        WorkbenchHostSpec(
            host_id="antigravity_gemini_flash_high",
            display_name="Antigravity CLI/Desktop with Gemini 3.5 Flash High",
            category="fast_planner_verifier",
            machine_location="external_workbench_candidate",
            known_path_or_entrypoint="Antigravity CLI/Desktop, Gemini 3.5 Flash High label",
            best_roles=(
                "fast bounded planning",
                "structured codebase critique",
                "refactoring within explicit boundaries",
                "verification and test authoring",
                "operator explanations",
            ),
            risky_roles=(
                "autonomous infrastructure administration",
                "unbounded shell execution",
                "final authority for security",
                "credential-bearing review",
                "out-of-workspace state transfer",
                "heavily creative visual design without tokens",
            ),
            default_clearance="scoped_read_write_workspace_for_explicit_lanes_only",
            allowed_autonomy_level_now="L2_SCOPED_READ_WRITE_EXPLICIT_LANE",
            future_autonomy_levels=("L3_RECEIPT_INGEST_AFTER_WORKER_RETURN",),
            current_status="available",
            health_light_relationship=("Traction Control", "Resources", "Parking Brake"),
            notes_for_prompting="Use a clear lane, exact workspace, exact file boundaries, validation, stop conditions, and receipt; sandbox or read-only when ambiguous.",
            first_time_or_ambiguous_lane_default="sandbox_or_read_only",
            observed_metadata=(
                ("account_tier_label", "Google AI Pro"),
                ("model_label", "Gemini 3.5 Flash High"),
                ("live_integration_from_this_registry", "false"),
            ),
        ),
        WorkbenchHostSpec(
            host_id="gpt_5_5_chatgpt_orchestrator",
            display_name="GPT-5.5 / ChatGPT orchestrator",
            category="orchestrator",
            machine_location="orchestration_surface",
            known_path_or_entrypoint="ChatGPT orchestration session",
            best_roles=(
                "architecture synthesis",
                "taste and safety judgment",
                "prompt package authoring",
                "cross-lane scope control",
                "worker target selection",
            ),
            risky_roles=(
                "claiming machine state it cannot observe",
                "granting authority without Repo A proof",
                "long implementation without local validation",
            ),
            default_clearance="orchestration_and_package_authoring_only",
            allowed_autonomy_level_now="L0_PREVIEW_PACKAGE_ONLY",
            future_autonomy_levels=("L1_OPEN_PACKAGE_IN_RIGHT_WORKBENCH",),
            current_status="available",
            health_light_relationship=("Traction Control", "Parking Brake"),
            notes_for_prompting="Use for scope, package, and decision framing; local machine truth must come from the workbench that can inspect it.",
        ),
        WorkbenchHostSpec(
            host_id="xcode_xcodebuild",
            display_name="Xcode / xcodebuild",
            category="build_environment",
            machine_location="Mac",
            known_path_or_entrypoint="Xcode GUI and xcodebuild command-line validation",
            best_roles=(
                "Mac app build validation",
                "compile diagnostics",
                "simulator or GUI validation when explicitly scoped",
            ),
            risky_roles=(
                "fragile window state",
                "screenshot validation drift",
                "slow UI launch loops",
                "app mutation outside a Mac app lane",
            ),
            default_clearance="build_validation_only_when_explicitly_scoped",
            allowed_autonomy_level_now="L1_EXPLICIT_BUILD_VALIDATION_ONLY",
            future_autonomy_levels=("L2_BOUNDED_VALIDATION_SESSION",),
            current_status="available",
            health_light_relationship=("Check Engine", "Resources", "Traction Control"),
            notes_for_prompting="Use exact scheme/project, validation target, timeout, and screenshot proof requirements.",
        ),
        WorkbenchHostSpec(
            host_id="terminal_shell",
            display_name="Terminal / shell",
            category="terminal_surface",
            machine_location="PC/WSL or Mac",
            known_path_or_entrypoint="bounded terminal command surface",
            best_roles=(
                "focused local reads",
                "tests",
                "export scripts",
                "non-interactive validation commands",
            ),
            risky_roles=(
                "interactive prompts",
                "credential prompts",
                "broad destructive commands",
                "unbounded shell loops",
            ),
            default_clearance="explicit_scoped_non_interactive_commands_only",
            allowed_autonomy_level_now="L1_EXPLICIT_SCOPED_COMMANDS_ONLY",
            future_autonomy_levels=("L2_BOUNDED_SESSION_WITH_PACKAGE",),
            current_status="available",
            health_light_relationship=("Check Engine", "Resources", "Parking Brake"),
            notes_for_prompting="Commands must be scoped, non-interactive where possible, and tied to validation or inspection.",
        ),
        WorkbenchHostSpec(
            host_id="vscode_agents_remote_ahp_candidate",
            display_name="VS Code 1.121+ / Agents / Remote Agents / AHP",
            category="agent_host_candidate",
            machine_location="candidate_remote_or_local_workbench",
            known_path_or_entrypoint="VS Code remote agents and Agent Host Protocol candidate surface",
            best_roles=(
                "future remote agent session coordination",
                "future persistent bounded sessions",
                "future mutation sequencing across clients",
                "Mermaid and HTML preview support",
            ),
            risky_roles=(
                "treating candidate features as active OpenClaw authority",
                "unsupervised remote mutation",
                "credential-bearing terminal prompts",
                "state transfer without intake",
            ),
            default_clearance="candidate_metadata_only_until_intake",
            allowed_autonomy_level_now="L0_PREVIEW_PACKAGE_ONLY",
            future_autonomy_levels=("L1_OPEN_PACKAGE_AFTER_INTAKE", "L2_BOUNDED_REMOTE_SESSION_AFTER_GATES"),
            current_status="candidate",
            health_light_relationship=("Check Engine", "Check Transmission", "Parking Brake", "Traction Control"),
            notes_for_prompting="Treat release-note features as candidate host metadata until a dedicated intake proves boundaries, receipts, and failure modes.",
            observed_metadata=(
                ("release_feature_remote_agents", "can run on remote machines and keep running after client disconnects"),
                ("release_feature_agent_host_protocol", "coordinates sessions across clients and sequences mutations"),
                ("release_feature_vscode_agent_env", "VSCODE_AGENT terminal marker exists as candidate signal"),
                ("release_feature_sensitive_prompts", "sensitive terminal prompts stay in terminal"),
            ),
        ),
    )


def _validate_spec(spec: WorkbenchHostSpec) -> None:
    if spec.category not in HOST_CATEGORIES:
        raise ValueError(f"unknown host category: {spec.category}")
    if spec.current_status not in HOST_STATUSES:
        raise ValueError(f"unknown host status: {spec.current_status}")
    for light in spec.health_light_relationship:
        if light not in HEALTH_LIGHTS:
            raise ValueError(f"unknown health light: {light}")


def _host_record(spec: WorkbenchHostSpec) -> dict[str, Any]:
    _validate_spec(spec)
    return {
        "host_id": spec.host_id,
        "display_name": spec.display_name,
        "category": spec.category,
        "machine_location": spec.machine_location,
        "known_path_or_entrypoint": spec.known_path_or_entrypoint,
        "best_roles": list(spec.best_roles),
        "risky_roles": list(spec.risky_roles),
        "default_clearance": spec.default_clearance,
        "allowed_autonomy_level_now": spec.allowed_autonomy_level_now,
        "future_autonomy_levels": list(spec.future_autonomy_levels),
        "first_time_or_ambiguous_lane_default": spec.first_time_or_ambiguous_lane_default,
        "package_input_shape": _package_input_shape(spec),
        "expected_receipt_shape": _expected_receipt_shape(spec),
        "proof_requirements": [
            "package id and lane id are echoed back",
            "changed files or no-changes result is explicit",
            "validation run or not-run reason is explicit",
            "authority boundary confirmation is explicit",
            "blocked and unknown items are returned without pretending context exists",
        ],
        "forbidden_actions": list(FORBIDDEN_GLOBAL_ACTIONS),
        "credential_policy": _credential_policy(),
        "storage_policy": _storage_policy(),
        "c_drive_policy": _c_drive_policy(spec),
        "current_status": spec.current_status,
        "health_light_relationship": list(spec.health_light_relationship),
        "notes_for_prompting": spec.notes_for_prompting,
        "observed_metadata": [
            {"key": key, "value": value, "truth_status": "operator_reported_or_release_note_label_not_live_authority"}
            for key, value in spec.observed_metadata
        ],
        "future_gated_until_intake": spec.current_status in {"candidate", "future_gated", "unknown"},
        "authority_boundary": _authority_boundary(),
    }


def _host_record_contract() -> dict[str, Any]:
    return {
        "required_fields": [
            "host_id",
            "display_name",
            "category",
            "machine_location",
            "known_path_or_entrypoint",
            "best_roles",
            "risky_roles",
            "default_clearance",
            "allowed_autonomy_level_now",
            "future_autonomy_levels",
            "package_input_shape",
            "expected_receipt_shape",
            "proof_requirements",
            "forbidden_actions",
            "credential_policy",
            "storage_policy",
            "c_drive_policy",
            "current_status",
            "health_light_relationship",
            "notes_for_prompting",
            "authority_boundary",
        ],
        "unknown_or_unavailable_hosts_fail_closed": True,
        "host_record_is_not_launch_authority": True,
    }


def _relationship_to_existing_contracts() -> dict[str, Any]:
    return {
        "added_scope": "external workbench, actor host, autonomy, receipt, storage, and routing registry",
        "does_not_replace_nested_lane_spine": True,
        "nested_lane_spine_still_owns": "lane topology, actor/agent/package grammar, confidence detours, and workspace posture",
        "does_not_replace_capability_registry": True,
        "capability_registry_still_owns": "OpenClaw capability/skill surfaces and blocked capability posture",
        "does_not_replace_system_health_lights": True,
        "system_health_lights_still_own": "helm warning/status taxonomy and clicked-lane mapping",
        "single_source_of_truth_posture": "companion read-model references existing contracts rather than duplicating their canonical fields",
    }


def _actor_routing_summary(hosts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model_is_actor_agent_is_character_package_is_script": True,
        "model_definition": "The language model is the actor that may perform work later.",
        "agent_definition": "The agent is the character/persona the actor plays, such as Chief, Cassandra, Guardian, Niles, or Hermes.",
        "package_definition": "The package is the script/context/tools/clearance/steps/boundaries/proof requirements.",
        "system_decides_authority_before_launch": True,
        "model_must_not_decide_own_authority_context_plugins_clearance_or_lane": True,
        "package_generation_target": "deterministic_package_builder_over_time",
        "early_package_assistance_allowed": "LM-assisted drafting may be used later only as bounded package authoring, not authority creation.",
        "external_model_apis_called": False,
        "browser_oauth_or_account_integrations_enabled": False,
        "registered_host_ids": [host["host_id"] for host in hosts],
        "domain_to_likely_host_examples": {
            "canonical_backend_contracts": ["pc_wsl_repo_a"],
            "mac_app_build_validation": ["codex_vscode_mac_codex_desktop", "xcode_xcodebuild"],
            "fast_planning_or_critique": ["antigravity_gemini_flash_high"],
            "orchestration_and_package_authoring": ["gpt_5_5_chatgpt_orchestrator"],
            "bounded_shell_validation": ["terminal_shell"],
            "future_remote_agent_hosting": ["vscode_agents_remote_ahp_candidate"],
        },
        "unknown_actor_or_host": {
            "routing": "fail_closed",
            "confidence_posture": "UNKNOWN_FAIL_CLOSED",
            "safe_next_move": "create or update metadata registry entry before launch",
        },
    }


def _how_this_helps_winship() -> list[str]:
    return [
        "Mission Control can show which workbench should receive a future package without requiring Winship to manually map every developer tool.",
        "OpenClaw can distinguish the helm from underlying workbenches, actor hosts, build environments, and terminal surfaces.",
        "The registry preserves what each host is good for, what it should never receive, and which receipt must come back.",
        "Autonomy is explicit and conservative now, with higher levels future-gated behind security and approval lanes.",
    ]


def _sqlite_receipt_contract(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "supported_by_existing_pattern": _rooted("business_ops_ledger.py", repo_root=ROOT).exists(),
        "pattern": "business_ops_ledger.record_receipt",
        "receipt_type": "generated_status",
        "sqlite_meaning": "receipt_record_only",
        "metadata_only": True,
        "stores_raw_tool_outputs": False,
        "stores_credentials": False,
        "stores_private_file_bodies": False,
        "stores_runtime_activation": False,
        "receipt_writer_function": "record_operator_workbench_actor_host_registry_receipt",
        "payload_hash": _hash_payload(
            {
                "schema_version": payload["schema_version"],
                "host_ids": [host["host_id"] for host in payload["hosts"]],
                "authority_flags": payload["no_authority_flags"],
            }
        ),
    }


def build_operator_workbench_actor_host_registry(
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
    hosts = [_host_record(spec) for spec in _host_specs()]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "operator_workbench_actor_host_registry",
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "lane": "Operator Workbench / Actor Host Registry v0",
        "registry_status": "deterministic_metadata_only_workbench_actor_host_registry",
        "purpose": "Define external workbenches and actor hosts OpenClaw can monitor, package work for, and eventually launch into without granting live integration authority now.",
        "operator_system_doctrine": {
            "openclaw_is_operator_system": True,
            "underlying_tools_are_not_the_helm": True,
            "underlying_tools": [
                "VS Code",
                "Codex",
                "Antigravity",
                "Xcode",
                "Terminal",
                "Git",
                "macOS",
                "Windows",
                "WSL",
                "future browser/app integrations",
            ],
            "determinism_and_ai_help_operator_navigate_execute_build_and_control": True,
            "current_contract_grants_execution": False,
        },
        "relationship_to_existing_contracts": _relationship_to_existing_contracts(),
        "host_categories": list(HOST_CATEGORIES),
        "host_statuses": list(HOST_STATUSES),
        "autonomy_level_progression": _autonomy_level_progression(),
        "current_allowed_defaults": {
            "codex": "scoped read/write workspace when explicitly prompted",
            "antigravity": "scoped read/write workspace for explicit lanes; sandbox/read-only for first-time or ambiguous lanes",
            "mac_app": "display/local marker-write only as already implemented",
            "terminal": "command execution only when explicitly scoped",
            "vscode_remote_agents_ahp": "candidate/future-gated until intake",
            "browser_oauth_gmail_calendar_coupa_telegram_send_submit_approval": "blocked/future-gated unless later lane grants narrow authority",
        },
        "host_record_contract": _host_record_contract(),
        "host_count": len(hosts),
        "hosts": hosts,
        "usable_now_host_ids": [
            host["host_id"]
            for host in hosts
            if host["current_status"] == "available" and not host["future_gated_until_intake"]
        ],
        "candidate_or_future_gated_host_ids": [
            host["host_id"]
            for host in hosts
            if host["future_gated_until_intake"] or host["current_status"] in {"candidate", "future_gated"}
        ],
        "actor_routing_summary": _actor_routing_summary(hosts),
        "proof_and_receipt_expectations": {
            "every_host_returns_receipt_before_ingest": True,
            "receipt_must_echo_package_and_lane": True,
            "receipt_must_list_changes_commands_validation_and_boundaries": True,
            "missing_context_must_be_reported_not_filled_in": True,
            "raw_credentials_private_bodies_and_broad_logs_are_excluded": True,
        },
        "what_should_never_be_delegated": {
            "security_credentials_legal_sensitive_final_authority": "never to fast planner/verifier without dedicated review",
            "destructive_cleanup_or_remount": "not from this registry",
            "send_submit_approval": "blocked unless future narrow authority lane grants it",
            "unbounded_shell_or_infrastructure_admin": "blocked by default",
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
        "sqlite_ledger_receipt_contract": {},
        "operator_output_questions_answered": [
            "what workbenches/actor hosts OpenClaw knows about",
            "which are usable now",
            "which are candidate/future-gated",
            "which actor is best for what kind of lane",
            "current safe autonomy levels",
            "proof/receipt each should return",
            "what should never be delegated",
            "how this helps Winship avoid manually learning every developer tool",
        ],
        "how_this_helps_winship": _how_this_helps_winship(),
        "next_safe_lane": "Workbench Actor Host Intake: VS Code Remote Agents / AHP Boundary Packet v0",
        "what_remains_future_gated": [
            "live launch/open package buttons",
            "external model API integrations",
            "agent sessions",
            "browser/OAuth/account bridges",
            "Gmail/calendar/Coupa/Telegram access",
            "send/submit/approval authority",
            "runtime execution authority",
            "auto-maintenance lanes above L3",
        ],
        "no_live_authority_statement": "No live integration, agent launch, model call, browser/OAuth, send, submit, approval, or runtime authority is added.",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    payload["sqlite_ledger_receipt_contract"] = _sqlite_receipt_contract(payload)
    payload["registry_hash"] = _hash_payload(
        {
            "schema_version": payload["schema_version"],
            "host_records": payload["hosts"],
            "autonomy_level_progression": payload["autonomy_level_progression"],
        }
    )
    return payload


def format_operator_workbench_actor_host_registry(payload: dict[str, Any]) -> str:
    lines = [
        "# Operator Workbench / Actor Host Registry v0",
        "",
        "Status:",
        "- Deterministic metadata-only registry.",
        f"- Hosts registered: `{payload['host_count']}`.",
        "- OpenClaw is the Operator System; these tools are workbenches, actor hosts, build environments, or execution surfaces, not the helm.",
        "- No live integration, agent launch, model call, browser/OAuth, send, submit, approval, or runtime authority is added.",
        "",
        "## Usable Now",
    ]
    for host in payload["hosts"]:
        if host["host_id"] in payload["usable_now_host_ids"]:
            lines.append(
                f"- `{host['host_id']}`: {host['display_name']} | {host['category']} | autonomy `{host['allowed_autonomy_level_now']}`"
            )
    lines.extend(["", "## Candidate / Future-Gated"])
    for host in payload["hosts"]:
        if host["host_id"] in payload["candidate_or_future_gated_host_ids"]:
            lines.append(
                f"- `{host['host_id']}`: {host['display_name']} | status `{host['current_status']}` | autonomy `{host['allowed_autonomy_level_now']}`"
            )
    lines.extend(["", "## Current Safe Autonomy"])
    for level in payload["autonomy_level_progression"]:
        lines.append(f"- `{level['level_id']}`: {level['meaning']}.")
    lines.extend(["", "## Actor Routing Summary"])
    routing = payload["actor_routing_summary"]
    lines.extend(
        [
            f"- Model/actor: {routing['model_definition']}",
            f"- Agent/character: {routing['agent_definition']}",
            f"- Package/script: {routing['package_definition']}",
            "- The system decides authority, context, tools, clearance, and lane before any future launch.",
            "- Unknown actor or host fails closed.",
        ]
    )
    lines.extend(["", "## Best-Fit Workbench Notes"])
    for host in payload["hosts"]:
        best = ", ".join(host["best_roles"][:3])
        risky = ", ".join(host["risky_roles"][:3])
        lines.append(f"- {host['display_name']}: best for {best}; risky for {risky}.")
    lines.extend(["", "## Proof / Receipt Expectations"])
    proof = payload["proof_and_receipt_expectations"]
    lines.extend(
        [
            f"- Every host returns receipt before ingest: `{str(proof['every_host_returns_receipt_before_ingest']).lower()}`.",
            "- Receipts must echo package/lane, list changes/commands/validation, confirm boundaries, and report blocked or unknown items.",
            "- Raw credentials, private bodies, and broad logs are excluded.",
        ]
    )
    lines.extend(["", "## What Should Never Be Delegated"])
    for key, value in payload["what_should_never_be_delegated"].items():
        lines.append(f"- `{key}`: {value}.")
    lines.extend(["", "## How This Helps Winship"])
    lines.extend(f"- {item}" for item in payload["how_this_helps_winship"])
    lines.extend(["", "## Future-Gated"])
    lines.extend(f"- {item}" for item in payload["what_remains_future_gated"])
    lines.extend(
        [
            "",
            "## SQLite / Ledger Receipt",
            "- Existing safe pattern: `business_ops_ledger.record_receipt`.",
            "- Receipt meaning: metadata-only `generated_status`, receipt-record-only, no runtime authority.",
            "- Raw tool outputs, credentials, private bodies, and broad logs are not stored.",
            "",
            "## Next Safe Lane",
            f"- {payload['next_safe_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_operator_workbench_actor_host_registry(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> OperatorWorkbenchActorHostRegistryExportResult:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_operator_workbench_actor_host_registry(
        repo_root=root,
        generated_at=generated_at,
    )
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_workbench_actor_host_registry(payload), encoding="utf-8")
    return OperatorWorkbenchActorHostRegistryExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        host_count=payload["host_count"],
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


def _find_existing_registry_receipt(
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


def record_operator_workbench_actor_host_registry_receipt(
    *,
    repo_root: str | Path = ROOT,
    db_path: str | Path | None = None,
    commit_hash: str | None = None,
    generated_at: str | None = None,
    ensure: bool = True,
) -> str:
    """Record a metadata-only generated-status receipt in the existing ledger."""
    root = Path(repo_root)
    payload = build_operator_workbench_actor_host_registry(
        repo_root=root,
        generated_at=generated_at,
    )
    registry_hash = payload["registry_hash"]
    if ensure:
        existing = _find_existing_registry_receipt(
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
        "host_count": payload["host_count"],
        "registered_host_ids": [host["host_id"] for host in payload["hosts"]],
        "doctrine_source_labels": list(DOCTRINE_SOURCE_LABELS),
        "metadata_only": True,
        "raw_tool_outputs_stored": False,
        "raw_private_bodies_stored": False,
        "credentials_stored": False,
        "broad_logs_stored": False,
        "c_drive_artifact_written": False,
        "runtime_activation": False,
        "authority_flags": dict(NO_AUTHORITY_FLAGS),
    }
    return record_receipt(
        receipt_type="generated_status",
        payload=receipt_payload,
        commit_hash=commit_hash,
        artifact_type="operator_workbench_actor_host_registry",
        artifact_status="captured_metadata_only",
        authority_status="generated_status_only",
        runtime_activation=False,
        sqlite_meaning="receipt_record_only",
        source_basis=list(DOCTRINE_SOURCE_LABELS),
        actor="operator_workbench_actor_host_registry_v0",
        created_at=generated_at,
        db_path=str(db_path) if db_path else None,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Operator Workbench / Actor Host Registry read-model.")
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
    result = export_operator_workbench_actor_host_registry(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    receipt_id = ""
    if args.record_receipt:
        receipt_id = record_operator_workbench_actor_host_registry_receipt(
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
    "AUTONOMY_LEVELS",
    "HEALTH_LIGHTS",
    "HOST_CATEGORIES",
    "HOST_STATUSES",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_operator_workbench_actor_host_registry",
    "export_operator_workbench_actor_host_registry",
    "format_operator_workbench_actor_host_registry",
    "record_operator_workbench_actor_host_registry_receipt",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
