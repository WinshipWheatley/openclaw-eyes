"""Operator Mission Priority / Helm Declutter Taxonomy v0.

This read-model tells Mission Control what belongs on the helm, what belongs
in check lights, what belongs inside worlds, and what should collapse into
proof/detail until needed. It is deterministic metadata only. It does not add
UI, live integration, model calls, agents, browser/account access, runtime
execution, send/submit/approval authority, cleanup, remount, credential
handling, or PC C-drive artifact writes.
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

SCHEMA_VERSION = "operator_mission_priority_helm_declutter_v0"
JSON_EXPORT_NAME = "operator_mission_priority_helm_declutter.json"
OPERATOR_EXPORT_NAME = "operator_mission_priority_helm_declutter_OPERATOR.md"

CLASSIFICATION_BUCKETS = (
    "helm_lanes",
    "check_lights",
    "worlds",
    "proof_detail",
    "future_gated",
    "parked",
)

SURFACE_POLICIES = (
    "above_fold",
    "visible_summary",
    "collapsed_by_default",
    "collapsed_world_launcher",
    "proof_detail_shelf",
    "hidden_until_relevant",
    "future_gated_hidden",
    "parked_until_mission_relevant",
)

STEEL_THREAD_FLOW = (
    "ELI5/operator orientation",
    "machine contract/proof",
    "package/detour/fix path",
)

MISSION_SUCCESS_CONDITIONS = (
    "system health is obvious",
    "current build/developer work is organized",
    "worlds/domains are visible and ready to enter",
    "package/detour/proof flow is consistent",
    "operator stops mentally tracking the system manually",
)

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "metadata_only": True,
    "taxonomy_only": True,
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
    "raw_logs_stored": False,
    "broad_file_dump_stored": False,
    "unknown_sources_fail_closed_or_static_doctrine_only": True,
}

FORBIDDEN_ACTIONS = (
    "call external model APIs",
    "run Codex, Antigravity, VS Code agent, browser, or other live sessions",
    "mutate Mission Control app files",
    "create live launch buttons",
    "create runtime execution authority",
    "create browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval authority",
    "write OpenClaw artifacts to the PC C: drive",
    "delete, cleanup, remount, or handle credentials",
)


@dataclass(frozen=True)
class SourceReadModel:
    key: str
    path: str
    role: str


@dataclass(frozen=True)
class DeclutterItemSpec:
    item_id: str
    display_name: str
    bucket: str
    item_kind: str
    priority_rank: int
    surface_policy: str
    top_level_helm_card_allowed: bool
    why_belongs_where: str
    source_refs: tuple[str, ...]
    next_safe_move: str
    examples: tuple[str, ...] = ()
    rise_to_helm_when: tuple[str, ...] = ()
    is_normal_work_lane: bool = True
    mission_relevance: str = "supports_app_finish_mission"
    blocks_current_mission_if_unresolved: bool = False


@dataclass(frozen=True)
class OperatorMissionPriorityHelmDeclutterExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    classification_item_count: int
    sqlite_receipt_supported: bool
    c_drive_artifact_written: bool
    runtime_authority_added: bool


SOURCE_READ_MODELS = (
    SourceReadModel(
        "system_health_lights_taxonomy",
        "generated/read_models/system_health_lights_taxonomy.json",
        "check-light taxonomy and current light states",
    ),
    SourceReadModel(
        "operator_nested_lane_mission_package_spine",
        "generated/read_models/operator_nested_lane_mission_package_spine.json",
        "nested-lane and mission-package grammar",
    ),
    SourceReadModel(
        "operator_awareness_agent_package_spine",
        "generated/read_models/operator_awareness_agent_package_spine.json",
        "awareness/gap/package/confidence spine",
    ),
    SourceReadModel(
        "chief_check_engine_environment_posture",
        "generated/read_models/chief_check_engine_environment_posture.json",
        "Chief-owned workbench degradation posture",
    ),
    SourceReadModel(
        "chief_check_engine_diagnostic_package",
        "generated/read_models/chief_check_engine_diagnostic_package.json",
        "inspect-only Chief diagnostic package",
    ),
    SourceReadModel(
        "bridge_manual_mount_recovery_packet",
        "generated/read_models/bridge_manual_mount_recovery_packet.json",
        "manual bridge recovery packet when mount is blocked",
    ),
    SourceReadModel(
        "sync_health",
        "generated/read_models/sync_health.json",
        "PC/Mac mirror proof and trusted-current state",
    ),
    SourceReadModel(
        "world_domain_registry",
        "generated/read_models/world_domain_registry.json",
        "world/domain registry and teleport-target vocabulary",
    ),
    SourceReadModel(
        "repo_a_known_rail_completion_map",
        "generated/read_models/repo_a_known_rail_completion_map.json",
        "known Repo A rail completion posture",
    ),
    SourceReadModel(
        "cross_repo_awareness_matrix",
        "generated/read_models/cross_repo_awareness_matrix.json",
        "cross-repo awareness and leftover classification posture",
    ),
    SourceReadModel(
        "operator_workbench_actor_host_registry",
        "generated/read_models/operator_workbench_actor_host_registry.json",
        "workbench, actor host, autonomy, and receipt registry",
    ),
    SourceReadModel(
        "business_ops_ledger",
        "business_ops_ledger.py",
        "existing metadata-only SQLite receipt pattern",
    ),
)

SOURCE_FILES = (
    "scripts/build_helm_state.py",
    "scripts/build_world_domain_registry.py",
    "system_health_lights_taxonomy.py",
    "operator_nested_lane_mission_package_spine.py",
    "operator_awareness_agent_package_spine.py",
    "operator_workbench_actor_host_registry.py",
    "business_ops_ledger.py",
)

DOCTRINE_SOURCE_LABELS = (
    "operator_prompt: Operator Mission Priority / Helm Declutter Taxonomy v0",
    "existing_contract: System Health Lights Taxonomy v0",
    "existing_contract: Operator Nested Lane Mission Package Spine v0",
    "existing_contract: Operator Workbench Actor Host Registry v0",
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
        "truth_status": "repo_a_source_or_read_model_evidence_not_front_door_truth_by_itself",
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
        "added_scope": "mission priority, helm declutter, front-door classification, and render guidance",
        "does_not_replace_helm_state": True,
        "helm_state_still_owns": "low-level deterministic helm state vocabulary and status checks",
        "does_not_replace_system_health_lights": True,
        "system_health_lights_still_own": "car-style check lights, current light states, and clicked-lane mapping",
        "does_not_replace_world_registry": True,
        "world_registry_still_owns": "durable domain/world vocabulary",
        "does_not_replace_nested_lane_spine": True,
        "nested_lane_spine_still_owns": "lane topology, package grammar, confidence detours, and workspace posture",
        "does_not_replace_workbench_registry": True,
        "workbench_registry_still_owns": "actor hosts, autonomy, proof, and receipt expectations",
        "single_source_of_truth_posture": "companion taxonomy classifies surfaces for display without duplicating canonical source contracts",
    }


def _current_mission() -> dict[str, Any]:
    return {
        "mission_id": "mission_control_app_finish_sprint",
        "operator_summary": "Finish Mission Control into a clean, calm, usable helm so Winship can start working from it.",
        "mission_meaning": "OpenClaw is an Operator System that uses determinism and AI to help the operator navigate, execute, build, and control anything they can and should control.",
        "not_the_mission": [
            "build every future world now",
            "execute live workflows",
            "turn every read-model into a top-level card",
            "grant model, browser, account, send, submit, approval, or runtime authority",
        ],
    }


def _source_state_summary(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    lights = sources.get("system_health_lights_taxonomy", {})
    sync = sources.get("sync_health", {})
    nested = sources.get("operator_nested_lane_mission_package_spine", {})
    worlds = sources.get("world_domain_registry", {})
    workbench = sources.get("operator_workbench_actor_host_registry", {})
    awareness = sources.get("operator_awareness_agent_package_spine", {})
    world_records = worlds.get("worlds") if isinstance(worlds.get("worlds"), list) else []
    return {
        "system_health_lights": {
            "available": bool(lights),
            "current_light_states": lights.get("current_light_states", {}),
            "generated_at": lights.get("generated_at"),
        },
        "sync_health": {
            "available": bool(sync),
            "canonical_expected": sync.get("canonical_expected"),
            "observed": sync.get("observed"),
            "missing_expected": sync.get("missing_expected"),
            "hash_mismatch": sync.get("hash_mismatch"),
            "sync_lifecycle_state": sync.get("sync_lifecycle_state"),
            "trust_status": sync.get("trust_status"),
            "mirror_status": sync.get("mirror_status"),
        },
        "nested_lane_spine": {
            "available": bool(nested),
            "nested_lane_count": nested.get("nested_lane_count"),
            "top_lane_id": (nested.get("top_level_system_awareness_discovery_lane") or {}).get("lane_id")
            if isinstance(nested.get("top_level_system_awareness_discovery_lane"), dict)
            else None,
        },
        "awareness_spine": {
            "available": bool(awareness),
            "button_ready_gap_items": awareness.get("awareness_gap_items_are_button_ready"),
        },
        "world_domain_registry": {
            "available": bool(worlds),
            "world_count": worlds.get("world_count"),
            "world_labels": [record.get("label") for record in world_records if isinstance(record, dict)],
        },
        "workbench_actor_host_registry": {
            "available": bool(workbench),
            "host_count": workbench.get("host_count"),
        },
    }


def _light_state(source_state: dict[str, Any], light_id: str, default: str = "UNKNOWN") -> str:
    states = source_state["system_health_lights"].get("current_light_states") or {}
    value = states.get(light_id)
    return str(value) if value else default


def _sync_is_trusted(source_state: dict[str, Any]) -> bool:
    sync = source_state["sync_health"]
    return bool(
        sync.get("available")
        and sync.get("sync_lifecycle_state") == "trusted_current"
        and sync.get("trust_status") == "trusted"
        and sync.get("missing_expected") == 0
        and sync.get("hash_mismatch") == 0
    )


def _declutter_specs(source_state: dict[str, Any]) -> tuple[DeclutterItemSpec, ...]:
    bridge_next = (
        "Keep Check Transmission quiet and show only proof/detail while sync remains trusted."
        if _sync_is_trusted(source_state)
        else "Use the existing sync lifecycle to restore trusted/current mirror proof."
    )
    return (
        DeclutterItemSpec(
            item_id="current_mission_app_finish",
            display_name="Current mission: Mission Control app finish sprint",
            bucket="helm_lanes",
            item_kind="mission_orientation",
            priority_rank=1,
            surface_policy="above_fold",
            top_level_helm_card_allowed=True,
            why_belongs_where="The current mission is the front-door orientation for all other prioritization.",
            source_refs=("operator_prompt",),
            next_safe_move="Render the mission, mode, first attention item, and next safe move before any proof shelves.",
            blocks_current_mission_if_unresolved=True,
        ),
        DeclutterItemSpec(
            item_id="system_awareness_discovery",
            display_name="System Awareness / Discovery",
            bucket="helm_lanes",
            item_kind="operator_system_build_lane",
            priority_rank=2,
            surface_policy="visible_summary",
            top_level_helm_card_allowed=True,
            why_belongs_where="It is about building and mapping OpenClaw itself, so it belongs on the helm in Developer Mode.",
            source_refs=("operator_nested_lane_mission_package_spine.json", "operator_awareness_agent_package_spine.json"),
            next_safe_move="Show the top lane and one immediate child/focus, not the whole nested tree.",
            examples=("known/partly-known/known-unknown/undiscovered map", "operator memory comparison"),
            blocks_current_mission_if_unresolved=True,
        ),
        DeclutterItemSpec(
            item_id="agent_awareness_tracking",
            display_name="Chief / Cassandra / Guardian / Niles / Hermes awareness tracking",
            bucket="helm_lanes",
            item_kind="operator_system_build_lane",
            priority_rank=3,
            surface_policy="collapsed_by_default",
            top_level_helm_card_allowed=True,
            why_belongs_where="These are active awareness/build sublanes, but the helm should show only the relevant immediate focus.",
            source_refs=("operator_nested_lane_mission_package_spine.json",),
            next_safe_move="Collapse agent sublanes into the System Awareness parent unless one has a mission-relevant attention flag.",
            examples=("Chief", "Cassandra", "Guardian", "Niles", "Hermes"),
            rise_to_helm_when=("meaningful attention flag", "blocked workflow", "build-out need that affects current mission"),
        ),
        DeclutterItemSpec(
            item_id="mission_control_visual_ux_app_finish",
            display_name="Mission Control visual/UX and app finish work",
            bucket="helm_lanes",
            item_kind="operator_system_build_lane",
            priority_rank=4,
            surface_policy="above_fold",
            top_level_helm_card_allowed=True,
            why_belongs_where="Developer/app finish work is about making the operator system usable within the sprint.",
            source_refs=("operator_prompt", "work_board.json"),
            next_safe_move="Render the next Mac UI change from this taxonomy rather than showing every backend artifact.",
            blocks_current_mission_if_unresolved=True,
        ),
        DeclutterItemSpec(
            item_id="workbench_actor_host_registry",
            display_name="Workbench / Actor Host Registry",
            bucket="helm_lanes",
            item_kind="operator_system_build_lane",
            priority_rank=5,
            surface_policy="visible_summary",
            top_level_helm_card_allowed=True,
            why_belongs_where="It tells the helm which tool or actor host should receive future packages.",
            source_refs=("operator_workbench_actor_host_registry.json",),
            next_safe_move="Show a small routing summary; keep per-host proof and policies in detail.",
            blocks_current_mission_if_unresolved=False,
        ),
        DeclutterItemSpec(
            item_id="package_preview_detour_flow",
            display_name="Package preview / detour / proof flow",
            bucket="helm_lanes",
            item_kind="operator_system_build_lane",
            priority_rank=6,
            surface_policy="visible_summary",
            top_level_helm_card_allowed=True,
            why_belongs_where="The steel-thread flow must be consistent before live worlds become useful.",
            source_refs=("operator_awareness_agent_package_spine.json", "operator_nested_lane_mission_package_spine.json"),
            next_safe_move="Show only orientation and next move above the fold; put package/proof lower.",
            blocks_current_mission_if_unresolved=True,
        ),
        DeclutterItemSpec(
            item_id="design_memory_inventory",
            display_name="Design memory inventory",
            bucket="helm_lanes",
            item_kind="operator_system_build_lane",
            priority_rank=7,
            surface_policy="collapsed_by_default",
            top_level_helm_card_allowed=True,
            why_belongs_where="Design memory matters to app finish, but raw archives and long design trees should not be front-door content.",
            source_refs=("operator_prompt", "operator_nested_lane_mission_package_spine.json"),
            next_safe_move="Keep as a bounded classification lane; do not ingest broad old archives here.",
            rise_to_helm_when=("blocks current UI decision", "operator memory comparison needed"),
        ),
        DeclutterItemSpec(
            item_id="check_engine",
            display_name="Check Engine",
            bucket="check_lights",
            item_kind="system_health_light",
            priority_rank=8,
            surface_policy="above_fold",
            top_level_helm_card_allowed=False,
            why_belongs_where="It is a system/workbench condition, not a normal domain lane.",
            source_refs=("system_health_lights_taxonomy.json", "chief_check_engine_diagnostic_package.json"),
            next_safe_move="Open the Chief diagnostic/system health lane when inspected.",
            is_normal_work_lane=False,
            blocks_current_mission_if_unresolved=True,
        ),
        DeclutterItemSpec(
            item_id="check_transmission",
            display_name="Check Transmission",
            bucket="check_lights",
            item_kind="system_health_light",
            priority_rank=9,
            surface_policy="above_fold",
            top_level_helm_card_allowed=False,
            why_belongs_where="PC/Mac bridge and state-transfer proof should be a drivetrain light, not a backend card.",
            source_refs=("system_health_lights_taxonomy.json", "sync_health.json", "bridge_manual_mount_recovery_packet.json"),
            next_safe_move=bridge_next,
            is_normal_work_lane=False,
            blocks_current_mission_if_unresolved=not _sync_is_trusted(source_state),
        ),
        DeclutterItemSpec(
            item_id="resources",
            display_name="Resources",
            bucket="check_lights",
            item_kind="system_health_light",
            priority_rank=10,
            surface_policy="above_fold",
            top_level_helm_card_allowed=False,
            why_belongs_where="Disk, credits, compute, storage, and tool availability are resource lights.",
            source_refs=("system_health_lights_taxonomy.json", "chief_check_engine_environment_posture.json"),
            next_safe_move="Show only if resource pressure materially affects the mission.",
            is_normal_work_lane=False,
        ),
        DeclutterItemSpec(
            item_id="parking_brake",
            display_name="Parking Brake",
            bucket="check_lights",
            item_kind="authority_lock_light",
            priority_rank=11,
            surface_policy="visible_summary",
            top_level_helm_card_allowed=False,
            why_belongs_where="Intentional authority locks are not failures and should be visually distinct from work lanes.",
            source_refs=("system_health_lights_taxonomy.json",),
            next_safe_move="Show as intentional lock posture; do not imply malfunction.",
            is_normal_work_lane=False,
        ),
        DeclutterItemSpec(
            item_id="traction_control",
            display_name="Traction Control",
            bucket="check_lights",
            item_kind="confidence_detour_light",
            priority_rank=12,
            surface_policy="hidden_until_relevant",
            top_level_helm_card_allowed=False,
            why_belongs_where="Confidence/detour state should appear only when it materially affects an action.",
            source_refs=("system_health_lights_taxonomy.json", "operator_awareness_agent_package_spine.json"),
            next_safe_move="Keep quiet unless a package is below deterministic confidence.",
            is_normal_work_lane=False,
        ),
        DeclutterItemSpec(
            item_id="worlds_teleport_targets",
            display_name="Worlds / domains as teleport targets",
            bucket="worlds",
            item_kind="world_launcher",
            priority_rank=13,
            surface_policy="collapsed_world_launcher",
            top_level_helm_card_allowed=False,
            why_belongs_where="Worlds are places to enter after the helm is calm; they should not clutter the front door.",
            source_refs=("world_domain_registry.json",),
            next_safe_move="Render as compact destination targets, not as equal helm cards.",
            examples=(
                "Music / Art",
                "Finance",
                "Operations",
                "Security",
                "Build",
                "Research",
                "Communications",
                "Business Development",
                "Gardening",
            ),
            rise_to_helm_when=("meaningful attention flag", "blocked workflow", "build-out need that affects current mission"),
            mission_relevance="visible_destination_not_current_build_blocker",
        ),
        DeclutterItemSpec(
            item_id="raw_contracts_receipts_long_paths",
            display_name="Raw contracts, receipts, paths, and machine proof",
            bucket="proof_detail",
            item_kind="proof_shelf",
            priority_rank=14,
            surface_policy="proof_detail_shelf",
            top_level_helm_card_allowed=False,
            why_belongs_where="Machine proof belongs underneath operator orientation, not in the front-door helm.",
            source_refs=("generated/read_models", "business_ops_ledger.py"),
            next_safe_move="Expose through drill-in/proof shelves only when the operator asks or a lane needs evidence.",
            examples=("raw contracts", "receipts", "long paths", "machine tokens", "source refs"),
            is_normal_work_lane=False,
        ),
        DeclutterItemSpec(
            item_id="nested_lane_tree",
            display_name="Deep nested lane tree",
            bucket="proof_detail",
            item_kind="collapsed_structure",
            priority_rank=15,
            surface_policy="collapsed_by_default",
            top_level_helm_card_allowed=False,
            why_belongs_where="Nested lanes may exist in backend contracts, but the UI should expose parent plus immediate focus by default.",
            source_refs=("operator_nested_lane_mission_package_spine.json",),
            next_safe_move="Show active parent lane, immediate child/focus, and next safe move.",
            is_normal_work_lane=False,
        ),
        DeclutterItemSpec(
            item_id="live_execution_integrations",
            display_name="Live execution integrations",
            bucket="future_gated",
            item_kind="blocked_future_authority",
            priority_rank=16,
            surface_policy="future_gated_hidden",
            top_level_helm_card_allowed=False,
            why_belongs_where="Live model/tool/agent/browser/account work is not part of the app-finish backend declutter lane.",
            source_refs=("operator_workbench_actor_host_registry.json", "system_health_lights_taxonomy.json"),
            next_safe_move="Keep blocked until a later authority lane grants a narrow path.",
            examples=("model APIs", "agent launch", "browser/OAuth", "send/submit/approval"),
            is_normal_work_lane=False,
        ),
        DeclutterItemSpec(
            item_id="browser_oauth_account_workflows",
            display_name="Browser/OAuth/account workflows",
            bucket="future_gated",
            item_kind="blocked_future_authority",
            priority_rank=17,
            surface_policy="future_gated_hidden",
            top_level_helm_card_allowed=False,
            why_belongs_where="Account-bearing workflows must remain future-gated and not appear as front-door action cards.",
            source_refs=("capability_skill_registry_metadata_delta.json", "operator_workbench_actor_host_registry.json"),
            next_safe_move="Represent as blocked/future-gated only.",
            examples=("Gmail", "calendar", "Coupa", "Telegram"),
            is_normal_work_lane=False,
        ),
        DeclutterItemSpec(
            item_id="deep_domain_work",
            display_name="Deep domain work",
            bucket="parked",
            item_kind="parked_domain_work",
            priority_rank=18,
            surface_policy="parked_until_mission_relevant",
            top_level_helm_card_allowed=False,
            why_belongs_where="Domain work should wait unless it blocks the app-finish mission or needs operator attention.",
            source_refs=("world_domain_registry.json", "cross_repo_awareness_matrix.json"),
            next_safe_move="Park deep domain work until the helm is calm, unless a domain has a mission-relevant attention flag.",
            examples=("deep music metadata", "finance workflow execution", "research backlog", "future Gardening world"),
            rise_to_helm_when=("blocks current mission", "meaningful attention flag", "explicit operator request"),
        ),
    )


def _item_record(spec: DeclutterItemSpec, source_state: dict[str, Any]) -> dict[str, Any]:
    if spec.bucket not in CLASSIFICATION_BUCKETS:
        raise ValueError(f"unknown bucket: {spec.bucket}")
    if spec.surface_policy not in SURFACE_POLICIES:
        raise ValueError(f"unknown surface policy: {spec.surface_policy}")
    current_status = None
    if spec.item_id == "check_engine":
        current_status = _light_state(source_state, "check_engine")
    elif spec.item_id == "check_transmission":
        current_status = _light_state(source_state, "check_transmission")
    elif spec.item_id == "resources":
        current_status = _light_state(source_state, "low_fuel_low_battery")
    elif spec.item_id == "parking_brake":
        current_status = _light_state(source_state, "brake_parking_brake")
    elif spec.item_id == "traction_control":
        current_status = _light_state(source_state, "traction_control")
    return {
        "item_id": spec.item_id,
        "display_name": spec.display_name,
        "bucket": spec.bucket,
        "item_kind": spec.item_kind,
        "priority_rank": spec.priority_rank,
        "surface_policy": spec.surface_policy,
        "top_level_helm_card_allowed": spec.top_level_helm_card_allowed,
        "why_belongs_where": spec.why_belongs_where,
        "current_status_from_source": current_status,
        "source_refs": list(spec.source_refs),
        "examples": list(spec.examples),
        "rise_to_helm_when": list(spec.rise_to_helm_when),
        "is_normal_work_lane": spec.is_normal_work_lane,
        "mission_relevance": spec.mission_relevance,
        "blocks_current_mission_if_unresolved": spec.blocks_current_mission_if_unresolved,
        "next_safe_move": spec.next_safe_move,
        "steel_thread_flow": list(STEEL_THREAD_FLOW),
        "proof_belongs_underneath": spec.bucket in {"proof_detail", "check_lights", "helm_lanes"},
        "machine_detail_front_door": False,
        "authority_boundary_preserved": True,
    }


def _priority_rules() -> list[dict[str, Any]]:
    return [
        {
            "rule_id": "blocks_app_finish_mission_first",
            "rank": 1,
            "meaning": "Rank first anything that blocks the approximately five-day Mission Control app finish mission.",
        },
        {
            "rule_id": "check_lights_before_lane_noise",
            "rank": 2,
            "meaning": "System health, bridge proof, resources, authority locks, and confidence conditions must be intelligible before showing lane detail.",
        },
        {
            "rule_id": "operator_orientation_before_machine_proof",
            "rank": 3,
            "meaning": "The front door shows operator orientation and next safe move; proof and package detail sit lower.",
        },
        {
            "rule_id": "worlds_are_destinations_not_card_wall",
            "rank": 4,
            "meaning": "Worlds are compact teleport targets unless they have meaningful attention or block the current mission.",
        },
        {
            "rule_id": "deep_domain_work_waits",
            "rank": 5,
            "meaning": "Deep domain work waits unless it blocks app finish, carries a meaningful attention flag, or is explicitly requested.",
        },
    ]


def _current_priority_ranking(source_state: dict[str, Any]) -> list[dict[str, Any]]:
    bridge_trusted = _sync_is_trusted(source_state)
    return [
        {
            "priority_id": "system_health_intelligible",
            "rank": 1,
            "summary": "System health/check lights must be obvious and quiet when resolved.",
            "blocks_current_mission_if_unresolved": True,
            "current_posture": "visible_health_row_needed",
        },
        {
            "priority_id": "bridge_transmission_trusted",
            "rank": 2,
            "summary": "PC/Mac bridge proof must be trusted before Mission Control can claim mirror current.",
            "blocks_current_mission_if_unresolved": not bridge_trusted,
            "current_posture": "trusted_current" if bridge_trusted else "needs_sync_or_review",
        },
        {
            "priority_id": "helm_front_door_calm",
            "rank": 3,
            "summary": "The helm front door must stop being a backend card wall.",
            "blocks_current_mission_if_unresolved": True,
            "current_posture": "taxonomy_ready_for_ui_readback",
        },
        {
            "priority_id": "steel_thread_pattern_consistent",
            "rank": 4,
            "summary": "Every lane/light/world should use orientation, proof, then package/detour path.",
            "blocks_current_mission_if_unresolved": True,
            "current_posture": "contract_defined",
        },
        {
            "priority_id": "workbench_actor_host_registry_clear",
            "rank": 5,
            "summary": "Mission Control must know which tools do what before package launch is useful.",
            "blocks_current_mission_if_unresolved": False,
            "current_posture": "registry_available" if source_state["workbench_actor_host_registry"]["available"] else "registry_unavailable",
        },
        {
            "priority_id": "package_preview_detour_flow",
            "rank": 6,
            "summary": "Package preview/detour workflow must exist before live worlds matter.",
            "blocks_current_mission_if_unresolved": True,
            "current_posture": "spine_available" if source_state["nested_lane_spine"]["available"] else "spine_unavailable",
        },
        {
            "priority_id": "worlds_as_teleport_targets",
            "rank": 7,
            "summary": "Worlds/domains should become compact destinations after the helm is clean.",
            "blocks_current_mission_if_unresolved": False,
            "current_posture": "registry_available" if source_state["world_domain_registry"]["available"] else "registry_unavailable",
        },
        {
            "priority_id": "deep_domain_work_waits",
            "rank": 8,
            "summary": "Deep domain work waits unless it blocks app finish.",
            "blocks_current_mission_if_unresolved": False,
            "should_wait_unless_blocks_mission": True,
            "current_posture": "parked",
        },
    ]


def _front_door_render_contract() -> dict[str, Any]:
    return {
        "front_door_questions": [
            "What mode am I in?",
            "Is the system healthy?",
            "What is the active mission?",
            "What needs my attention first?",
            "What is the next safe move?",
            "What is blocked/future-gated?",
            "Where can I inspect proof?",
        ],
        "above_fold": [
            "mode_and_mission_strip",
            "system_health_light_row",
            "active_mission_next_safe_move",
            "top_priority_stack_limited_to_current_mission",
            "compact_world_launcher_hint",
        ],
        "collapsed_by_default": [
            "nested_lane_children",
            "agent_awareness_sublanes",
            "workbench_host_detail",
            "design_memory_inventory",
            "domain_world_detail",
        ],
        "proof_detail_shelf": [
            "raw_contracts_and_receipts",
            "machine_proof",
            "long_paths",
            "source_refs",
            "package_body_preview",
        ],
        "must_not_render_as_top_level": [
            "every_read_model_as_equal_card",
            "deep_nested_lane_tree",
            "raw_machine_tokens",
            "receipt_rows",
            "long_path_lists",
            "future_gated_live_actions",
        ],
        "top_helm_layer_shows": [
            "operator orientation",
            "current mission",
            "health-light status",
            "next safe move",
        ],
        "lower_layers_show": [
            "machine proof",
            "package preview",
            "detour/fix path",
        ],
    }


def _check_light_policy() -> dict[str, Any]:
    return {
        "visually_semantically_distinct_from_lanes": True,
        "quiet_when_resolved": True,
        "not_normal_work_lanes": True,
        "owned_by": {
            "Check Engine": "Chief",
            "Check Transmission": "Mirror Trust / sync",
            "Resources": "Chief",
            "Parking Brake": "Guardian / authority boundary",
            "Traction Control": "confidence/detour spine",
        },
    }


def _world_policy() -> dict[str, Any]:
    return {
        "normal_domain_work_belongs_inside_worlds": True,
        "domain_attention_rises_to_helm_only_when_relevant": True,
        "worlds_are_teleport_targets_after_helm_is_calm": True,
        "worlds_should_not_clutter_helm_without_attention": True,
        "examples": [
            "Music / Art",
            "Finance",
            "Operations",
            "Security",
            "Build",
            "Research",
            "Communications",
            "Business Development",
            "Gardening",
        ],
    }


def _mac_ui_should_render_next() -> list[dict[str, Any]]:
    return [
        {
            "render_id": "mode_mission_health_strip",
            "summary": "Developer Mode / app finish sprint strip plus health-light row.",
            "source": "current_mission and system_health_lights_taxonomy",
        },
        {
            "render_id": "top_priority_next_move",
            "summary": "Show the top current priority and next safe move, not a full read-model wall.",
            "source": "current_priority_ranking",
        },
        {
            "render_id": "system_awareness_single_focus",
            "summary": "Show active parent lane and one immediate focus child.",
            "source": "operator_nested_lane_mission_package_spine",
        },
        {
            "render_id": "compact_world_launcher",
            "summary": "Render worlds/domains as compact teleport targets with attention badges only when relevant.",
            "source": "world_domain_registry",
        },
        {
            "render_id": "proof_detail_shelf",
            "summary": "Move raw contracts, receipts, long paths, machine proof, and package bodies behind inspect/drill-in affordances.",
            "source": "machine_proof",
        },
    ]


def _unknown_source_policy() -> dict[str, Any]:
    return {
        "do_not_invent_source_facts": True,
        "classification_can_still_render_static_doctrine": True,
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
        "receipt_writer_function": "record_operator_mission_priority_helm_declutter_receipt",
        "payload_hash": _hash_payload(
            {
                "schema_version": payload["schema_version"],
                "classification_item_ids": [item["item_id"] for item in payload["classification_items"]],
                "priority_ids": [item["priority_id"] for item in payload["current_priority_ranking"]],
                "authority_flags": payload["no_authority_flags"],
            }
        ),
    }


def build_operator_mission_priority_helm_declutter(
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
    source_state = _source_state_summary(sources)
    classification_items = [_item_record(spec, source_state) for spec in _declutter_specs(source_state)]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "operator_mission_priority_helm_declutter",
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "lane": "Operator Mission Priority / Helm Declutter Taxonomy v0",
        "taxonomy_status": "deterministic_metadata_only_mission_priority_declutter",
        "current_mission": _current_mission(),
        "mission_deadline_label": "approximately_5_days_app_finish_sprint",
        "mission_success_conditions": list(MISSION_SUCCESS_CONDITIONS),
        "helm_mode": "DEVELOPER_MODE_BUILD_MODE",
        "target_future_mode": "QUIET_OPERATIONAL_HELM",
        "relationship_to_existing_contracts": _relationship_to_existing_contracts(),
        "classification_buckets": list(CLASSIFICATION_BUCKETS),
        "surface_policies": list(SURFACE_POLICIES),
        "classification_items": classification_items,
        "classification_counts": {
            bucket: sum(1 for item in classification_items if item["bucket"] == bucket)
            for bucket in CLASSIFICATION_BUCKETS
        },
        "priority_rules": _priority_rules(),
        "current_priority_ranking": _current_priority_ranking(source_state),
        "front_door_render_contract": _front_door_render_contract(),
        "check_light_policy": _check_light_policy(),
        "world_policy": _world_policy(),
        "steel_thread_pattern": {
            "flow": list(STEEL_THREAD_FLOW),
            "top_helm_should_not_show_all_layers_at_once": True,
            "top_helm_shows_operator_orientation_and_next_move": True,
            "proof_and_package_layers_lower": True,
        },
        "source_state_summary": source_state,
        "unknown_or_missing_source_policy": _unknown_source_policy(),
        "what_mac_ui_should_render_next": _mac_ui_should_render_next(),
        "what_should_not_be_built_yet": [
            "live workflow execution",
            "all future worlds",
            "browser/OAuth/account integrations",
            "send/submit/approval flows",
            "full deep nested lane tree on the front door",
            "every read-model as an equal card",
        ],
        "mac_ui_explicit_warning": "The Mac app should not render every read-model as an equal card.",
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
        "next_safe_lane": "Mission Control Helm Declutter Readback Surface v0",
        "no_live_authority_statement": "No UI mutation, live integration, model call, agent launch, browser/OAuth, send, submit, approval, or runtime authority is added.",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    payload["sqlite_ledger_receipt_contract"] = _sqlite_receipt_contract(payload)
    payload["taxonomy_hash"] = _hash_payload(
        {
            "schema_version": payload["schema_version"],
            "current_mission": payload["current_mission"],
            "classification_items": payload["classification_items"],
            "current_priority_ranking": payload["current_priority_ranking"],
        }
    )
    return payload


def _items_by_bucket(payload: dict[str, Any], bucket: str) -> list[dict[str, Any]]:
    return [item for item in payload["classification_items"] if item["bucket"] == bucket]


def format_operator_mission_priority_helm_declutter(payload: dict[str, Any]) -> str:
    mission = payload["current_mission"]
    front = payload["front_door_render_contract"]
    lines = [
        "# Operator Mission Priority / Helm Declutter Taxonomy v0",
        "",
        "Status:",
        "- Deterministic metadata-only taxonomy.",
        "- Backend/read-model contract only; no UI lane, execution lane, or integration lane.",
        "- The Mac app should not render every read-model as an equal card.",
        "",
        "## Current Mission",
        f"- {mission['operator_summary']}",
        f"- Deadline label: `{payload['mission_deadline_label']}`.",
        f"- Helm mode: `{payload['helm_mode']}`; target: `{payload['target_future_mode']}`.",
        "",
        "## Mission Success Conditions",
    ]
    lines.extend(f"- {item}" for item in payload["mission_success_conditions"])
    lines.extend(["", "## What Belongs On The Helm"])
    for item in _items_by_bucket(payload, "helm_lanes"):
        lines.append(f"- `{item['item_id']}`: {item['display_name']} | {item['surface_policy']} | {item['next_safe_move']}")
    lines.extend(["", "## What Belongs In Check Lights"])
    for item in _items_by_bucket(payload, "check_lights"):
        status = item.get("current_status_from_source") or "static"
        lines.append(f"- `{item['item_id']}`: {item['display_name']} | status `{status}` | {item['next_safe_move']}")
    lines.extend(["", "## What Belongs In Worlds"])
    for item in _items_by_bucket(payload, "worlds"):
        lines.append(f"- `{item['item_id']}`: {item['display_name']} | {item['why_belongs_where']}")
    lines.extend(["", "## What Belongs Only In Proof / Detail"])
    for item in _items_by_bucket(payload, "proof_detail"):
        lines.append(f"- `{item['item_id']}`: {item['display_name']} | {item['surface_policy']}")
    lines.extend(["", "## What Should Be Collapsed"])
    lines.extend(f"- {item}" for item in front["collapsed_by_default"])
    lines.extend(["", "## What Should Be Worked First"])
    for item in payload["current_priority_ranking"]:
        lines.append(f"- `{item['rank']}` `{item['priority_id']}`: {item['summary']}")
    lines.extend(["", "## What Mission Control Should Render Next"])
    for item in payload["what_mac_ui_should_render_next"]:
        lines.append(f"- `{item['render_id']}`: {item['summary']}")
    lines.extend(["", "## What Should Not Be Built Yet"])
    lines.extend(f"- {item}" for item in payload["what_should_not_be_built_yet"])
    lines.extend(
        [
            "",
            "## Front Door Rule",
            "- Above fold: " + ", ".join(front["above_fold"]) + ".",
            "- Proof shelf: " + ", ".join(front["proof_detail_shelf"]) + ".",
            "- Do not top-level: " + ", ".join(front["must_not_render_as_top_level"]) + ".",
            "",
            "## Boundary",
            "- No external model APIs, Codex/Antigravity/VS Code agent sessions, Mission Control app mutation, live launch buttons, runtime execution, browser/OAuth/Gmail/calendar/Coupa/Telegram/send/submit/approval authority, C-drive artifact writes, deletes, cleanup, remount, or credential handling.",
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


def export_operator_mission_priority_helm_declutter(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> OperatorMissionPriorityHelmDeclutterExportResult:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_operator_mission_priority_helm_declutter(
        repo_root=root,
        generated_at=generated_at,
    )
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_mission_priority_helm_declutter(payload), encoding="utf-8")
    return OperatorMissionPriorityHelmDeclutterExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        classification_item_count=len(payload["classification_items"]),
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


def _find_existing_declutter_receipt(
    *,
    taxonomy_hash: str,
    commit_hash: str | None,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    for packet in _load_existing_receipt_payloads(db_path):
        payload_json = packet.get("payload_json")
        if not isinstance(payload_json, dict):
            continue
        if payload_json.get("contract_id") != SCHEMA_VERSION:
            continue
        if payload_json.get("taxonomy_hash") != taxonomy_hash:
            continue
        if commit_hash and packet.get("commit_hash") != commit_hash:
            continue
        return packet
    return None


def record_operator_mission_priority_helm_declutter_receipt(
    *,
    repo_root: str | Path = ROOT,
    db_path: str | Path | None = None,
    commit_hash: str | None = None,
    generated_at: str | None = None,
    ensure: bool = True,
) -> str:
    """Record a bounded metadata-only generated-status receipt."""
    root = Path(repo_root)
    payload = build_operator_mission_priority_helm_declutter(
        repo_root=root,
        generated_at=generated_at,
    )
    taxonomy_hash = payload["taxonomy_hash"]
    if ensure:
        existing = _find_existing_declutter_receipt(
            taxonomy_hash=taxonomy_hash,
            commit_hash=commit_hash,
            db_path=db_path,
        )
        if existing:
            return str(existing.get("receipt_id") or existing.get("packet_id") or "")

    init_business_ops_ledger(str(db_path) if db_path else None)
    receipt_payload = {
        "contract_id": SCHEMA_VERSION,
        "taxonomy_hash": taxonomy_hash,
        "generated_read_model_paths": [
            f"generated/read_models/{JSON_EXPORT_NAME}",
            f"generated/read_models/{OPERATOR_EXPORT_NAME}",
        ],
        "current_mission_id": payload["current_mission"]["mission_id"],
        "classification_item_count": len(payload["classification_items"]),
        "classification_buckets": list(CLASSIFICATION_BUCKETS),
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
        artifact_type="operator_mission_priority_helm_declutter",
        artifact_status="captured_metadata_only",
        authority_status="generated_status_only",
        runtime_activation=False,
        sqlite_meaning="receipt_record_only",
        source_basis=list(DOCTRINE_SOURCE_LABELS),
        actor="operator_mission_priority_helm_declutter_v0",
        created_at=generated_at,
        db_path=str(db_path) if db_path else None,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Operator Mission Priority / Helm Declutter taxonomy.")
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
    result = export_operator_mission_priority_helm_declutter(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    receipt_id = ""
    if args.record_receipt:
        receipt_id = record_operator_mission_priority_helm_declutter_receipt(
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
    "CLASSIFICATION_BUCKETS",
    "JSON_EXPORT_NAME",
    "MISSION_SUCCESS_CONDITIONS",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "SURFACE_POLICIES",
    "build_operator_mission_priority_helm_declutter",
    "export_operator_mission_priority_helm_declutter",
    "format_operator_mission_priority_helm_declutter",
    "record_operator_mission_priority_helm_declutter_receipt",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
