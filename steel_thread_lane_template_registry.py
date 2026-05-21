"""Steel Thread Lane Template Registry v0.

This read-model defines reusable templates for helm lanes, check-light lanes,
world lanes, nested lanes, proof/detail lanes, package previews, confidence
detours, and parked lanes. It is deterministic metadata only. It does not add
UI code, live integrations, model calls, agents, tools, browser/account access,
runtime execution, send/submit/approval authority, cleanup, remount,
credential handling, SQLite mutation beyond optional metadata-only receipt, or
PC C-drive artifact writes.
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

SCHEMA_VERSION = "steel_thread_lane_template_registry_v0"
JSON_EXPORT_NAME = "steel_thread_lane_template_registry.json"
OPERATOR_EXPORT_NAME = "steel_thread_lane_template_registry_OPERATOR.md"

TEMPLATE_TYPES = (
    "helm_lane",
    "check_light_lane",
    "world_lane",
    "nested_lane",
    "proof_detail_lane",
    "package_preview_lane",
    "confidence_detour_lane",
    "parked_lane",
)

OPERATOR_ORIENTATION_FIELDS = (
    "what_is_this",
    "why_it_matters",
    "current_status",
    "safe_next_move",
    "operator_seconds_summary",
)

MACHINE_CONTRACT_FIELDS = (
    "read_model_refs",
    "receipt_refs",
    "marker_refs",
    "evidence_refs",
    "known",
    "partly_known",
    "unknown",
    "stale",
    "blocked",
    "trusted_vs_not_yet_trusted",
    "proof_that_would_make_quiet",
)

PACKAGE_DETOUR_FIELDS = (
    "package_preview",
    "actor_model_candidate",
    "agent_character",
    "context_included",
    "context_excluded",
    "plugins_capabilities_tools_allowed",
    "security_clearance",
    "steps",
    "stop_conditions",
    "proof_receipt_must_return",
    "confidence_state_if_below_deterministic",
    "detour_that_raises_confidence",
    "available_now_vs_future_gated",
)

SAFE_CONTROL_IDS = (
    "explain_this",
    "what_can_i_do",
    "tell_system_whats_missing",
    "raise_confidence",
    "preview_package",
    "show_proof",
    "keep_parked",
    "future_chat_workspace_target",
    "inspect_detail",
)

FORBIDDEN_CONTROL_IDS = (
    "live_execution",
    "send_submit_approval",
    "model_agent_calls",
    "tool_plugin_execution",
    "remount_credential_handling",
    "generated_read_model_mutation",
    "sqlite_mutation",
    "broad_file_writes",
    "c_drive_artifact_writes",
    "cleanup_delete_repair",
)

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "metadata_only": True,
    "registry_only": True,
    "template_only": True,
    "sqlite_receipt_metadata_only": True,
    "sqlite_schema_changed": False,
    "sqlite_mutation_authority_added": False,
    "model_calls_made": False,
    "lm_called": False,
    "external_model_apis_called": False,
    "agents_activated": False,
    "agent_launch_authority_added": False,
    "tools_enabled": False,
    "plugins_wired": False,
    "tool_plugin_execution_authority_added": False,
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
    "repair_authority_added": False,
    "remount_authority_added": False,
    "credential_handling_added": False,
    "generated_read_model_mutation_authority_added": False,
    "broad_file_write_authority_added": False,
    "c_drive_write_allowed": False,
    "c_drive_artifact_written": False,
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
    "raw_private_content_inspected": False,
    "raw_logs_stored": False,
    "broad_file_dump_stored": False,
    "unknown_sources_fail_closed_or_static_doctrine_only": True,
}

FORBIDDEN_ACTIONS = (
    "live execution",
    "send, submit, or approval",
    "model or agent calls",
    "tool or plugin execution",
    "remount or credential handling",
    "generated read-model mutation",
    "SQLite mutation beyond metadata-only receipt",
    "broad file writes",
    "PC C-drive artifact writes",
    "cleanup, delete, or repair",
)


@dataclass(frozen=True)
class SourceReadModel:
    key: str
    path: str
    role: str


@dataclass(frozen=True)
class TemplateSpec:
    template_id: str
    display_name: str
    purpose: str
    when_used: str
    front_door_visibility: str
    owner_agent_character_candidates: tuple[str, ...]
    mac_guidance: tuple[str, ...]
    top_level_card_allowed: bool
    is_normal_work_lane: bool
    allowed_control_ids: tuple[str, ...] = SAFE_CONTROL_IDS


@dataclass(frozen=True)
class SteelThreadLaneTemplateRegistryExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    template_type_count: int
    sqlite_receipt_supported: bool
    c_drive_artifact_written: bool
    runtime_authority_added: bool


SOURCE_READ_MODELS = (
    SourceReadModel(
        "system_health_lights_taxonomy",
        "generated/read_models/system_health_lights_taxonomy.json",
        "check-light lanes and current health-light states",
    ),
    SourceReadModel(
        "operator_mission_priority_helm_declutter",
        "generated/read_models/operator_mission_priority_helm_declutter.json",
        "front-door declutter and surface-priority policy",
    ),
    SourceReadModel(
        "operator_nested_lane_mission_package_spine",
        "generated/read_models/operator_nested_lane_mission_package_spine.json",
        "nested lane topology and package-builder grammar",
    ),
    SourceReadModel(
        "operator_awareness_agent_package_spine",
        "generated/read_models/operator_awareness_agent_package_spine.json",
        "awareness gaps, button-ready metadata, confidence, detours, and package preview",
    ),
    SourceReadModel(
        "operator_workbench_actor_host_registry",
        "generated/read_models/operator_workbench_actor_host_registry.json",
        "actor/workbench routing and receipt expectations",
    ),
    SourceReadModel(
        "chief_check_engine_diagnostic_package",
        "generated/read_models/chief_check_engine_diagnostic_package.json",
        "Chief diagnostic package example for check-light lanes",
    ),
    SourceReadModel(
        "bridge_manual_mount_recovery_packet",
        "generated/read_models/bridge_manual_mount_recovery_packet.json",
        "bridge blocker package example for fix/detour path",
    ),
    SourceReadModel(
        "business_ops_ledger",
        "business_ops_ledger.py",
        "existing metadata-only SQLite receipt pattern",
    ),
)

SOURCE_FILES = (
    "system_health_lights_taxonomy.py",
    "operator_mission_priority_helm_declutter.py",
    "operator_nested_lane_mission_package_spine.py",
    "operator_awareness_agent_package_spine.py",
    "operator_workbench_actor_host_registry.py",
    "business_ops_ledger.py",
)

DOCTRINE_SOURCE_LABELS = (
    "operator_prompt: Steel Thread Lane Template Registry v0",
    "existing_contract: Operator Mission Priority / Helm Declutter Taxonomy v0",
    "existing_contract: Operator Awareness + Agent Package Spine v0",
    "existing_contract: Operator Nested Lane Mission Package Spine v0",
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
        "truth_status": "repo_a_source_or_read_model_evidence_not_template_truth_by_itself",
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


def _hash_payload(payload: Any) -> str:
    digest = hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _relationship_to_existing_contracts() -> dict[str, Any]:
    return {
        "added_scope": "reusable lane template types, layer fields, safe controls, confidence behavior, quiet behavior, receipts, and Mac rendering guidance",
        "does_not_replace_declutter_taxonomy": True,
        "declutter_taxonomy_still_owns": "what belongs on the helm, in check lights, worlds, proof/detail, future-gated, or parked",
        "does_not_replace_nested_lane_spine": True,
        "nested_lane_spine_still_owns": "actual lane topology and mission package grammar",
        "does_not_replace_awareness_spine": True,
        "awareness_spine_still_owns": "specific gap items, confidence repair, and package preview examples",
        "does_not_replace_workbench_registry": True,
        "workbench_registry_still_owns": "actor/workbench host inventory, autonomy, and routing metadata",
        "single_source_of_truth_posture": "template registry defines reusable patterns and references existing contracts for source state",
    }


def _source_state_summary(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "system_health_lights_taxonomy": {
            "available": bool(sources.get("system_health_lights_taxonomy")),
            "current_light_states": sources.get("system_health_lights_taxonomy", {}).get("current_light_states", {}),
        },
        "operator_mission_priority_helm_declutter": {
            "available": bool(sources.get("operator_mission_priority_helm_declutter")),
            "taxonomy_status": sources.get("operator_mission_priority_helm_declutter", {}).get("taxonomy_status"),
        },
        "operator_nested_lane_mission_package_spine": {
            "available": bool(sources.get("operator_nested_lane_mission_package_spine")),
            "nested_lane_count": sources.get("operator_nested_lane_mission_package_spine", {}).get("nested_lane_count"),
        },
        "operator_awareness_agent_package_spine": {
            "available": bool(sources.get("operator_awareness_agent_package_spine")),
            "package_preview_only": sources.get("operator_awareness_agent_package_spine", {}).get("package_preview_only"),
        },
        "operator_workbench_actor_host_registry": {
            "available": bool(sources.get("operator_workbench_actor_host_registry")),
            "host_count": sources.get("operator_workbench_actor_host_registry", {}).get("host_count"),
        },
    }


def _steel_thread_layers() -> list[dict[str, Any]]:
    return [
        {
            "layer_id": "operator_orientation",
            "display_name": "Top layer - Operator Orientation",
            "purpose": "Help Winship understand the lane in seconds before inspecting machine proof.",
            "fields": list(OPERATOR_ORIENTATION_FIELDS),
            "front_door_default": True,
            "machine_detail_default": False,
        },
        {
            "layer_id": "machine_contract_proof",
            "display_name": "Middle layer - Machine Contract / Proof",
            "purpose": "Show the deterministic evidence, receipts, markers, status, blockers, and trust posture underneath the operator layer.",
            "fields": list(MACHINE_CONTRACT_FIELDS),
            "front_door_default": False,
            "machine_detail_default": True,
        },
        {
            "layer_id": "package_detour_fix_path",
            "display_name": "Bottom layer - Package / Detour / Fix Path",
            "purpose": "Show what package would be sent, which actor/agent would receive it later, what is blocked, and which detour raises confidence.",
            "fields": list(PACKAGE_DETOUR_FIELDS),
            "front_door_default": False,
            "machine_detail_default": True,
        },
    ]


def _control_registry() -> dict[str, Any]:
    controls = [
        {
            "control_id": "explain_this",
            "label": "Explain This",
            "interaction_mode": "read_only",
            "behavior_before_live_authority": "local explanation/proof orientation only",
            "mutation_allowed_now": False,
            "dispatch_allowed_now": False,
            "launch_allowed_now": False,
        },
        {
            "control_id": "what_can_i_do",
            "label": "What Can I Do?",
            "interaction_mode": "read_only",
            "behavior_before_live_authority": "show safe moves and future-gated actions",
            "mutation_allowed_now": False,
            "dispatch_allowed_now": False,
            "launch_allowed_now": False,
        },
        {
            "control_id": "tell_system_whats_missing",
            "label": "Tell System What's Missing",
            "interaction_mode": "capture_preview",
            "behavior_before_live_authority": "preview or generate future context artifact; no live write unless later gated",
            "mutation_allowed_now": False,
            "dispatch_allowed_now": False,
            "launch_allowed_now": False,
        },
        {
            "control_id": "raise_confidence",
            "label": "Raise Confidence",
            "interaction_mode": "read_only_detour",
            "behavior_before_live_authority": "show detours and evidence needed",
            "mutation_allowed_now": False,
            "dispatch_allowed_now": False,
            "launch_allowed_now": False,
        },
        {
            "control_id": "preview_package",
            "label": "Preview Package",
            "interaction_mode": "read_only_package_preview",
            "behavior_before_live_authority": "show package contents, not dispatch",
            "mutation_allowed_now": False,
            "dispatch_allowed_now": False,
            "launch_allowed_now": False,
        },
        {
            "control_id": "show_proof",
            "label": "Show Proof",
            "interaction_mode": "read_only_proof",
            "behavior_before_live_authority": "reveal machine contract and evidence",
            "mutation_allowed_now": False,
            "dispatch_allowed_now": False,
            "launch_allowed_now": False,
        },
        {
            "control_id": "keep_parked",
            "label": "Keep Parked",
            "interaction_mode": "local_status_only",
            "behavior_before_live_authority": "local/status display only unless later request-write authority exists",
            "mutation_allowed_now": False,
            "dispatch_allowed_now": False,
            "launch_allowed_now": False,
        },
        {
            "control_id": "future_chat_workspace_target",
            "label": "Future Chat/Workspace Target",
            "interaction_mode": "future_gated",
            "behavior_before_live_authority": "show intended target, do not launch",
            "mutation_allowed_now": False,
            "dispatch_allowed_now": False,
            "launch_allowed_now": False,
        },
        {
            "control_id": "inspect_detail",
            "label": "Inspect Detail",
            "interaction_mode": "read_only_detail",
            "behavior_before_live_authority": "open detail/proof view only",
            "mutation_allowed_now": False,
            "dispatch_allowed_now": False,
            "launch_allowed_now": False,
        },
    ]
    return {
        "controls_are_metadata_only": True,
        "controls_mutate_state_now": False,
        "live_authority_required_before_mutation": True,
        "allowed_now_controls": [
            "explain_this",
            "what_can_i_do",
            "raise_confidence",
            "preview_package",
            "show_proof",
            "inspect_detail",
        ],
        "capture_preview_controls": ["tell_system_whats_missing", "keep_parked"],
        "future_gated_controls": ["future_chat_workspace_target"],
        "controls": controls,
        "forbidden_by_default": list(FORBIDDEN_CONTROL_IDS),
    }


def _confidence_behavior(template_id: str) -> dict[str, Any]:
    return {
        "deterministic_confidence_hides_score": True,
        "below_deterministic_shows_issue_and_detours": True,
        "failed_deterministic_job_resets_confidence": True,
        "confidence_theater_for_deterministic_proof_forbidden": True,
        "template_specific_note": (
            "Confidence detour lane foregrounds missing evidence."
            if template_id == "confidence_detour_lane"
            else "Show confidence only when it materially changes the operator decision."
        ),
    }


def _quiet_behavior(template_id: str) -> dict[str, Any]:
    return {
        "quiet_when_deterministic_and_no_attention_needed": True,
        "quiet_when_blocked_or_parked_on_purpose": template_id in {"parked_lane", "proof_detail_lane"},
        "parked_lanes_do_not_demand_attention": template_id == "parked_lane",
        "proof_only_lanes_do_not_clutter_front_door": template_id == "proof_detail_lane",
        "if_failure_then_reset_confidence_and_surface_detour": True,
    }


def _actor_workbench_routing_hooks(template_id: str) -> dict[str, Any]:
    return {
        "source_registry": "operator_workbench_actor_host_registry",
        "route_by": [
            "lane_kind",
            "risk",
            "domain",
            "required_proof",
            "allowed_authority",
        ],
        "model_actor_selected_now": False,
        "agent_character_activated_now": False,
        "workspace_launched_now": False,
        "package_dispatch_allowed_now": False,
        "template_id": template_id,
    }


def _authority_boundary() -> dict[str, Any]:
    return {
        "read_model_only": True,
        "metadata_only": True,
        "model_or_agent_call_allowed": False,
        "tool_or_plugin_execution_allowed": False,
        "runtime_authority_added": False,
        "send_submit_approval_allowed": False,
        "sqlite_mutation_allowed": False,
        "generated_read_model_mutation_allowed": False,
        "c_drive_artifact_written": False,
    }


def _expected_receipt_shape() -> dict[str, Any]:
    return {
        "receipt_required_before_state_ingest": True,
        "metadata_only": True,
        "fields": [
            "template_id",
            "lane_id",
            "package_id_if_any",
            "operator_summary",
            "proof_refs",
            "actions_taken_or_none",
            "files_changed_or_none",
            "validation_run_or_not_run_reason",
            "blocked_items",
            "authority_boundary_confirmation",
        ],
        "raw_private_bodies_or_credentials_stored": False,
        "runtime_activation_recorded": False,
    }


def _mac_ui_rendering_guidance(template_id: str, guidance: tuple[str, ...]) -> dict[str, Any]:
    return {
        "render_operator_orientation_first": True,
        "do_not_render_machine_proof_as_front_door": True,
        "proof_and_package_lower_or_drill_in": True,
        "show_active_parent_and_immediate_focus_only": template_id == "nested_lane",
        "avoid_backend_inventory_or_card_browser_feel": True,
        "guidance": list(guidance),
    }


def _proof_requirements(template_id: str) -> list[str]:
    base = [
        "read-model or source reference exists, or source is marked unavailable",
        "known/partial/unknown/stale/blocked/trusted status is explicit",
        "quiet condition is named",
        "authority boundary is explicit",
    ]
    if template_id == "check_light_lane":
        base.append("current check-light status and owner are named")
    if template_id == "package_preview_lane":
        base.append("package body is reviewable but not dispatched")
    if template_id == "confidence_detour_lane":
        base.append("missing evidence and detour path are named")
    return base


def _template_specs() -> tuple[TemplateSpec, ...]:
    return (
        TemplateSpec(
            template_id="helm_lane",
            display_name="Helm Lane",
            purpose="Represent active operator-system build, mapping, or app-finish work.",
            when_used="Use for Developer Mode lanes that build, fix, map, or operate OpenClaw itself.",
            front_door_visibility="visible_summary",
            owner_agent_character_candidates=("Chief", "Guardian", "Hermes"),
            mac_guidance=("Show mission relevance, current status, and next safe move.", "Keep proof and package preview below orientation."),
            top_level_card_allowed=True,
            is_normal_work_lane=True,
        ),
        TemplateSpec(
            template_id="check_light_lane",
            display_name="Check-Light Lane",
            purpose="Represent a system, bridge, resource, authority, or confidence condition.",
            when_used="Use when a car-style helm light is on, warning, unknown, or intentionally locked.",
            front_door_visibility="health_light_row_when_on_or_warning",
            owner_agent_character_candidates=("Chief", "Guardian", "Mirror Trust"),
            mac_guidance=("Render as a light/status, not a normal lane card.", "Clicking opens orientation, proof, and diagnostic/detour path."),
            top_level_card_allowed=False,
            is_normal_work_lane=False,
        ),
        TemplateSpec(
            template_id="world_lane",
            display_name="World Lane",
            purpose="Represent a domain/world the operator may enter after the helm is calm.",
            when_used="Use for Music / Art, Finance, Operations, Security, Build, Research, Communications, Business Development, and future worlds.",
            front_door_visibility="compact_world_launcher_unless_attention",
            owner_agent_character_candidates=("Niles", "Cassandra", "Guardian", "Chief", "Hermes"),
            mac_guidance=("Render as compact teleport target.", "Raise to helm only for meaningful attention, blocker, or mission-relevant build-out."),
            top_level_card_allowed=False,
            is_normal_work_lane=True,
        ),
        TemplateSpec(
            template_id="nested_lane",
            display_name="Nested Lane",
            purpose="Represent a backend child lane without exposing deep trees by default.",
            when_used="Use when a parent lane has immediate relevant child/focus work.",
            front_door_visibility="parent_plus_immediate_focus",
            owner_agent_character_candidates=("Chief", "Guardian", "Cassandra", "Niles", "Hermes"),
            mac_guidance=("Show active parent, immediate child/focus, and next safe move.", "Hide deep tree until inspect/drill-in."),
            top_level_card_allowed=False,
            is_normal_work_lane=True,
        ),
        TemplateSpec(
            template_id="proof_detail_lane",
            display_name="Proof / Detail Lane",
            purpose="Hold machine contracts, proof, receipts, markers, long paths, and raw package detail.",
            when_used="Use when operator asks to inspect evidence or when a lane needs machine proof.",
            front_door_visibility="proof_shelf_only",
            owner_agent_character_candidates=("Chief", "Guardian"),
            mac_guidance=("Never front-door raw proof as the main card.", "Use a detail shelf or drill-in."),
            top_level_card_allowed=False,
            is_normal_work_lane=False,
        ),
        TemplateSpec(
            template_id="package_preview_lane",
            display_name="Package Preview Lane",
            purpose="Show the exact context package that would be sent later without dispatching it.",
            when_used="Use when the operator needs to inspect actor, agent character, context, clearance, steps, and receipts.",
            front_door_visibility="visible_when_package_relevant",
            owner_agent_character_candidates=("Chief", "Guardian"),
            mac_guidance=("Show package summary first.", "Full package body is reviewable in detail and never dispatched by this template."),
            top_level_card_allowed=False,
            is_normal_work_lane=True,
        ),
        TemplateSpec(
            template_id="confidence_detour_lane",
            display_name="Confidence Detour Lane",
            purpose="Expose missing evidence and bounded detours when confidence is below deterministic.",
            when_used="Use when a lane/package is not fully trusted or a deterministic job failed.",
            front_door_visibility="visible_only_when_confidence_blocks_or_changes_action",
            owner_agent_character_candidates=("Chief", "Guardian", "Hermes"),
            mac_guidance=("Show why confidence is not full.", "Hide when proof is deterministic."),
            top_level_card_allowed=False,
            is_normal_work_lane=True,
        ),
        TemplateSpec(
            template_id="parked_lane",
            display_name="Parked Lane",
            purpose="Keep a lane intentionally quiet until it becomes mission-relevant or operator-requested.",
            when_used="Use for deep domain work, future-gated work, or intentionally deferred lanes.",
            front_door_visibility="hidden_until_relevant_or_requested",
            owner_agent_character_candidates=("Chief",),
            mac_guidance=("Do not demand attention.", "Show parked reason and safe re-entry condition if inspected."),
            top_level_card_allowed=False,
            is_normal_work_lane=True,
            allowed_control_ids=("explain_this", "what_can_i_do", "show_proof", "keep_parked", "inspect_detail"),
        ),
    )


def _template_record(spec: TemplateSpec) -> dict[str, Any]:
    if spec.template_id not in TEMPLATE_TYPES:
        raise ValueError(f"unknown template type: {spec.template_id}")
    return {
        "template_id": spec.template_id,
        "display_name": spec.display_name,
        "purpose": spec.purpose,
        "when_used": spec.when_used,
        "front_door_visibility": spec.front_door_visibility,
        "operator_orientation_fields": list(OPERATOR_ORIENTATION_FIELDS),
        "machine_contract_fields": list(MACHINE_CONTRACT_FIELDS),
        "package_detour_fields": list(PACKAGE_DETOUR_FIELDS),
        "allowed_controls": list(spec.allowed_control_ids),
        "forbidden_controls": list(FORBIDDEN_CONTROL_IDS),
        "proof_requirements": _proof_requirements(spec.template_id),
        "confidence_behavior": _confidence_behavior(spec.template_id),
        "quiet_behavior": _quiet_behavior(spec.template_id),
        "owner_agent_character_candidates": list(spec.owner_agent_character_candidates),
        "actor_workbench_routing_hooks": _actor_workbench_routing_hooks(spec.template_id),
        "authority_boundary": _authority_boundary(),
        "expected_receipt_shape": _expected_receipt_shape(),
        "mac_ui_rendering_guidance": _mac_ui_rendering_guidance(spec.template_id, spec.mac_guidance),
        "top_level_card_allowed": spec.top_level_card_allowed,
        "is_normal_work_lane": spec.is_normal_work_lane,
    }


def _template_record_contract() -> dict[str, Any]:
    return {
        "required_fields": [
            "template_id",
            "display_name",
            "purpose",
            "when_used",
            "front_door_visibility",
            "operator_orientation_fields",
            "machine_contract_fields",
            "package_detour_fields",
            "allowed_controls",
            "forbidden_controls",
            "proof_requirements",
            "confidence_behavior",
            "quiet_behavior",
            "owner_agent_character_candidates",
            "actor_workbench_routing_hooks",
            "authority_boundary",
            "expected_receipt_shape",
            "mac_ui_rendering_guidance",
        ],
        "templates_are_not_runtime_authority": True,
        "unknown_template_fails_closed": True,
    }


def _confidence_doctrine() -> dict[str, Any]:
    return {
        "below_deterministic": {
            "show_confidence_issue": True,
            "show_detour_options": True,
            "show_missing_evidence": True,
        },
        "deterministic_or_full_trust": {
            "hide_confidence_score": True,
            "hide_detour_ui": True,
            "do_not_display_confidence_theater": True,
        },
        "failed_deterministic_job": {
            "reset_confidence": True,
            "detours_reappear": True,
            "proof_failure_becomes_visible": True,
        },
    }


def _quiet_lane_doctrine() -> dict[str, Any]:
    return {
        "lane_becomes_quiet_when": [
            "operator orientation is understood",
            "machine proof is deterministic or the blocker is intentional",
            "no mission-relevant attention flag remains",
            "package/detour/fix path is either unnecessary, parked, or explicitly future-gated",
        ],
        "do_not_display_confidence_theater_when_proof_is_deterministic": True,
        "parked_lanes_stay_quiet_until_requested_or_relevant": True,
        "check_lights_quiet_when_resolved": True,
    }


def _mac_rendering_guidance() -> dict[str, Any]:
    return {
        "render_consistent_pattern": True,
        "front_door_operator_first": True,
        "do_not_become_backend_inventory_or_card_browser": True,
        "show_top_layer_by_default": True,
        "show_middle_layer_on_show_proof_or_inspect_detail": True,
        "show_bottom_layer_on_preview_package_or_raise_confidence": True,
        "nested_lanes_show_parent_immediate_focus_next_safe_move": True,
        "hide_confidence_when_deterministic": True,
    }


def _unknown_source_policy() -> dict[str, Any]:
    return {
        "do_not_invent_source_facts": True,
        "static_template_doctrine_still_renders": True,
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
        "receipt_writer_function": "record_steel_thread_lane_template_registry_receipt",
        "payload_hash": _hash_payload(
            {
                "schema_version": payload["schema_version"],
                "template_types": payload["template_types"],
                "control_ids": [control["control_id"] for control in payload["control_behavior_registry"]["controls"]],
                "authority_flags": payload["no_authority_flags"],
            }
        ),
    }


def build_steel_thread_lane_template_registry(
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
    templates = [_template_record(spec) for spec in _template_specs()]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "steel_thread_lane_template_registry",
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "lane": "Steel Thread Lane Template Registry v0",
        "registry_status": "deterministic_metadata_only_steel_thread_template_registry",
        "purpose": "Define reusable templates so helm lanes, check lights, worlds, proof shelves, packages, detours, and parked lanes share one operator-first workflow pattern.",
        "steel_thread_pattern": {
            "summary": "Every lane, check light, and world follows operator orientation, machine proof, then package/detour/fix path.",
            "steps": [
                "ELI5 / operator orientation",
                "Machine contract / proof",
                "Package / detour / fix path",
            ],
        },
        "relationship_to_existing_contracts": _relationship_to_existing_contracts(),
        "template_types": list(TEMPLATE_TYPES),
        "template_type_count": len(templates),
        "template_record_contract": _template_record_contract(),
        "steel_thread_layers": _steel_thread_layers(),
        "top_layer_first_policy": {
            "operator_first": True,
            "top_helm_does_not_show_all_layers_at_once": True,
            "machine_proof_below_operator_orientation": True,
            "package_preview_below_or_on_request": True,
        },
        "control_behavior_registry": _control_registry(),
        "templates": templates,
        "confidence_doctrine": _confidence_doctrine(),
        "quiet_lane_doctrine": _quiet_lane_doctrine(),
        "mac_rendering_guidance": _mac_rendering_guidance(),
        "source_state_summary": _source_state_summary(sources),
        "unknown_or_missing_source_policy": _unknown_source_policy(),
        "what_should_not_be_built_yet": [
            "live execution controls",
            "send/submit/approval controls",
            "model or agent calls from buttons",
            "tool or plugin execution from buttons",
            "remount or credential handling",
            "generated read-model mutation controls",
            "SQLite mutation controls beyond metadata-only receipts",
            "broad file write controls",
            "PC C-drive artifact writes",
            "cleanup/delete/repair controls",
        ],
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
        "next_safe_lane": "Mission Control Steel Thread Template Readback Surface v0",
        "no_live_authority_statement": "No UI mutation, live integration, model call, agent launch, browser/OAuth, send, submit, approval, runtime, C-drive write, cleanup, remount, credential, or repair authority is added.",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    payload["sqlite_ledger_receipt_contract"] = _sqlite_receipt_contract(payload)
    payload["registry_hash"] = _hash_payload(
        {
            "schema_version": payload["schema_version"],
            "template_types": payload["template_types"],
            "templates": payload["templates"],
            "controls": payload["control_behavior_registry"]["controls"],
            "confidence_doctrine": payload["confidence_doctrine"],
            "quiet_lane_doctrine": payload["quiet_lane_doctrine"],
        }
    )
    return payload


def format_steel_thread_lane_template_registry(payload: dict[str, Any]) -> str:
    layers = {layer["layer_id"]: layer for layer in payload["steel_thread_layers"]}
    controls = payload["control_behavior_registry"]
    lines = [
        "# Steel Thread Lane Template Registry v0",
        "",
        "Status:",
        "- Deterministic metadata-only template registry.",
        "- Backend/read-model contract only; no UI lane, execution lane, or live integration lane.",
        "- Mission Control should render one consistent workflow instead of inventing a new pattern per lane.",
        "",
        "## Steel-Thread Pattern",
        "- Top: ELI5 / operator orientation.",
        "- Middle: machine contract / proof.",
        "- Bottom: package / detour / fix path.",
        "",
        "## Template Types",
    ]
    for template in payload["templates"]:
        lines.append(f"- `{template['template_id']}`: {template['display_name']} | {template['front_door_visibility']}")
    lines.extend(
        [
            "",
            "## Top / Operator Layer",
            "- " + ", ".join(layers["operator_orientation"]["fields"]) + ".",
            "",
            "## Middle / Proof Layer",
            "- " + ", ".join(layers["machine_contract_proof"]["fields"]) + ".",
            "",
            "## Bottom / Package Layer",
            "- " + ", ".join(layers["package_detour_fix_path"]["fields"]) + ".",
            "",
            "## Allowed Now Controls",
            "- " + ", ".join(f"`{control}`" for control in controls["allowed_now_controls"]) + ".",
            "",
            "## Future-Gated Controls",
            "- " + ", ".join(f"`{control}`" for control in controls["future_gated_controls"]) + ".",
            "",
            "## Capture Preview Controls",
            "- " + ", ".join(f"`{control}`" for control in controls["capture_preview_controls"]) + ".",
            "",
            "## Confidence Behavior",
            "- Below deterministic: show confidence issue, missing evidence, and detours.",
            "- Deterministic/full trust: hide confidence score and detour UI.",
            "- Failed deterministic job: reset confidence and surface proof failure/detours.",
            "",
            "## Quiet Behavior",
            "- Lanes become quiet when proof is deterministic or blocker/parking is intentional and no attention is needed.",
            "- Do not display confidence theater when proof is deterministic.",
            "",
            "## Mac Rendering Guidance",
            "- Render operator orientation first.",
            "- Put machine proof and package bodies behind Show Proof, Preview Package, Raise Confidence, or Inspect Detail.",
            "- Nested lanes show active parent, immediate focus, and next safe move by default.",
            "- Do not make the helm a backend inventory or card browser.",
            "",
            "## What Should Not Be Built Yet",
        ]
    )
    lines.extend(f"- {item}" for item in payload["what_should_not_be_built_yet"])
    lines.extend(
        [
            "",
            "## Boundary",
            "- No external model APIs, Codex/Antigravity/VS Code agent sessions, Mission Control app mutation, live launch buttons, runtime execution, browser/OAuth/Gmail/calendar/Coupa/Telegram/send/submit/approval authority, generated read-model mutation controls, SQLite mutation controls, C-drive artifact writes, deletes, cleanup, repair, remount, or credential handling.",
            "",
            "## SQLite / Ledger Receipt",
            "- Existing safe pattern: `business_ops_ledger.record_receipt`.",
            "- Receipt meaning: metadata-only `generated_status`, receipt-record-only, no runtime authority.",
            "- Secrets, credentials, raw private file bodies, raw logs, and broad file dumps are not stored.",
            "",
            "## Next Safe Lane",
            f"- {payload['next_safe_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_steel_thread_lane_template_registry(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> SteelThreadLaneTemplateRegistryExportResult:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_steel_thread_lane_template_registry(
        repo_root=root,
        generated_at=generated_at,
    )
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_steel_thread_lane_template_registry(payload), encoding="utf-8")
    return SteelThreadLaneTemplateRegistryExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        template_type_count=len(payload["templates"]),
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


def _find_existing_template_registry_receipt(
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


def record_steel_thread_lane_template_registry_receipt(
    *,
    repo_root: str | Path = ROOT,
    db_path: str | Path | None = None,
    commit_hash: str | None = None,
    generated_at: str | None = None,
    ensure: bool = True,
) -> str:
    """Record a bounded metadata-only generated-status receipt."""
    root = Path(repo_root)
    payload = build_steel_thread_lane_template_registry(
        repo_root=root,
        generated_at=generated_at,
    )
    registry_hash = payload["registry_hash"]
    if ensure:
        existing = _find_existing_template_registry_receipt(
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
        "template_type_count": len(payload["templates"]),
        "template_types": list(payload["template_types"]),
        "control_ids": [control["control_id"] for control in payload["control_behavior_registry"]["controls"]],
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
        artifact_type="steel_thread_lane_template_registry",
        artifact_status="captured_metadata_only",
        authority_status="generated_status_only",
        runtime_activation=False,
        sqlite_meaning="receipt_record_only",
        source_basis=list(DOCTRINE_SOURCE_LABELS),
        actor="steel_thread_lane_template_registry_v0",
        created_at=generated_at,
        db_path=str(db_path) if db_path else None,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Steel Thread Lane Template Registry read-model.")
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
    result = export_steel_thread_lane_template_registry(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    receipt_id = ""
    if args.record_receipt:
        receipt_id = record_steel_thread_lane_template_registry_receipt(
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
    "FORBIDDEN_CONTROL_IDS",
    "JSON_EXPORT_NAME",
    "MACHINE_CONTRACT_FIELDS",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "OPERATOR_ORIENTATION_FIELDS",
    "PACKAGE_DETOUR_FIELDS",
    "SAFE_CONTROL_IDS",
    "SCHEMA_VERSION",
    "TEMPLATE_TYPES",
    "build_steel_thread_lane_template_registry",
    "export_steel_thread_lane_template_registry",
    "format_steel_thread_lane_template_registry",
    "record_steel_thread_lane_template_registry_receipt",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
