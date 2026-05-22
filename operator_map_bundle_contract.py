"""Stable OpenClaw map-bundle sync contract v0.

This module defines the stable map bundle that Mission Control should consume
instead of treating every generated read-model file as a front-door app
dependency. It is deterministic metadata only: no Mac UI mutation, network,
model call, agent activation, remount, delete, repair, credential handling, or
runtime authority is added.
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

from generated_read_model_files import (
    VOLATILE_SELF_REPORT_READ_MODEL_FILES,
    canonical_generated_read_model_records,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_PC_TRANSFER_ROOT = Path("/mnt/e/openclaw")
DEFAULT_MAC_MOUNT_PATH = "/Volumes/openclaw_e"
DEFAULT_MAC_LOCAL_MAP_ROOT = "/Users/hwinshipwheatley/openclaw_generated_read_models"

CONTRACT_SCHEMA_VERSION = "operator_map_bundle_contract_v0"
MAP_MANIFEST_SCHEMA_VERSION = "openclaw_map_manifest_v0"
MAP_SNAPSHOT_SCHEMA_VERSION = "openclaw_map_snapshot_v0"
MAP_RECEIPT_SCHEMA_VERSION = "openclaw_map_receipt_v0"

CONTRACT_JSON_EXPORT_NAME = "operator_map_bundle_contract.json"
CONTRACT_OPERATOR_EXPORT_NAME = "operator_map_bundle_contract_OPERATOR.md"
MAP_MANIFEST_EXPORT_NAME = "openclaw_map_manifest.json"
MAP_SNAPSHOT_EXPORT_NAME = "openclaw_map_snapshot.json"
MAP_OPERATOR_EXPORT_NAME = "openclaw_map_OPERATOR.md"
MAP_SYNC_REQUIRED_SCHEMA_VERSION = "openclaw_map_sync_required_v0"
MAP_SYNC_REQUIRED_EXPORT_NAME = "openclaw_map_sync_required.json"

STABLE_APP_FACING_FILES = (
    MAP_SNAPSHOT_EXPORT_NAME,
    MAP_MANIFEST_EXPORT_NAME,
    MAP_OPERATOR_EXPORT_NAME,
)

MAP_BUNDLE_SELF_FILES = (
    CONTRACT_JSON_EXPORT_NAME,
    CONTRACT_OPERATOR_EXPORT_NAME,
    MAP_MANIFEST_EXPORT_NAME,
    MAP_SNAPSHOT_EXPORT_NAME,
    MAP_OPERATOR_EXPORT_NAME,
)
MAP_BUNDLE_HASH_EXCLUDED_FILES = frozenset(MAP_BUNDLE_SELF_FILES) | frozenset(
    VOLATILE_SELF_REPORT_READ_MODEL_FILES
)

AGENT_TERRAIN_READ_MODEL_PATH = "generated/read_models/agent_terrain_awareness_readback_contract.json"
PACKAGE_PREVIEW_RECEIPT_READ_MODEL_PATH = "generated/read_models/package_preview_receipt_contract.json"
TOOL_ADAPTER_RECEIPT_READ_MODEL_PATH = "generated/read_models/tool_adapter_receipt_contract.json"
CAPITAL_HILTON_PROOF_METADATA_READ_MODEL_PATH = "generated/read_models/capital_hilton_proof_metadata_packet.json"
SECURITY_AUDIT_READINESS_READ_MODEL_PATH = "generated/read_models/security_audit_readiness_packet.json"
SECURITY_PASS_CONTRACT_READ_MODEL_PATH = "generated/read_models/security_pass_contract.json"
POST_SECURITY_GOVERNANCE_BATCH_MANIFEST_READ_MODEL_PATH = "generated/read_models/post_security_governance_batch_manifest.json"
PARKED_AUTONOMOUS_CAPITAL_PIPELINE_EXPERIMENT_READ_MODEL_PATH = "generated/read_models/parked_autonomous_capital_pipeline_experiment.json"
SECURITY_DELTA_REVIEW_CONTRACT_READ_MODEL_PATH = "generated/read_models/security_delta_review_contract.json"
OPERATOR_ATTENTION_PROMOTION_CONTRACT_READ_MODEL_PATH = "generated/read_models/operator_attention_promotion_contract.json"
CHIEF_TEST_HARNESS_CROSS_OFF_RECEIPT_CONTRACT_READ_MODEL_PATH = "generated/read_models/chief_test_harness_cross_off_receipt_contract.json"

ESSENTIAL_SURFACES = (
    {
        "surface_id": "sync_health",
        "path": "generated/read_models/sync_health.json",
        "role": "current raw read-model mirror proof and lifecycle state",
    },
    {
        "surface_id": "system_health_lights_taxonomy",
        "path": "generated/read_models/system_health_lights_taxonomy.json",
        "role": "health light definitions and current light posture",
    },
    {
        "surface_id": "operator_threshold_map_contract",
        "path": "generated/read_models/operator_threshold_map_contract.json",
        "role": "pre-security threshold map, lane readiness, and lane destiny",
    },
    {
        "surface_id": "operator_mission_priority_helm_declutter",
        "path": "generated/read_models/operator_mission_priority_helm_declutter.json",
        "role": "current mission, helm mode, and declutter priority",
    },
    {
        "surface_id": "world_domain_registry",
        "path": "generated/read_models/world_domain_registry.json",
        "role": "world/domain list and current world posture",
    },
    {
        "surface_id": "package_compiler_contract",
        "path": "generated/read_models/package_compiler_contract.json",
        "role": "package preview schema and deterministic boundary validation",
    },
    {
        "surface_id": "package_preview_receipt_contract",
        "path": PACKAGE_PREVIEW_RECEIPT_READ_MODEL_PATH,
        "role": "package preview receipt grammar and example preview cards",
    },
    {
        "surface_id": "tool_adapter_receipt_contract",
        "path": TOOL_ADAPTER_RECEIPT_READ_MODEL_PATH,
        "role": "tool/protocol adapter receipt grammar and example adapter cards",
    },
    {
        "surface_id": "capital_hilton_proof_metadata_packet",
        "path": CAPITAL_HILTON_PROOF_METADATA_READ_MODEL_PATH,
        "role": "Capital Hilton Finance steel-thread proof metadata posture",
    },
    {
        "surface_id": "security_audit_readiness_packet",
        "path": SECURITY_AUDIT_READINESS_READ_MODEL_PATH,
        "role": "security audit readiness provenance, coverage gaps, parked breadcrumbs, and pass criteria",
    },
    {
        "surface_id": "security_pass_contract",
        "path": SECURITY_PASS_CONTRACT_READ_MODEL_PATH,
        "role": "security pass read-only, preview, metadata, worker intake, and trust-clearance decisions",
    },
    {
        "surface_id": "post_security_governance_batch_manifest",
        "path": POST_SECURITY_GOVERNANCE_BATCH_MANIFEST_READ_MODEL_PATH,
        "role": "post-security governance batch closure state and Mac import handoff",
    },
    {
        "surface_id": "parked_autonomous_capital_pipeline_experiment",
        "path": PARKED_AUTONOMOUS_CAPITAL_PIPELINE_EXPERIMENT_READ_MODEL_PATH,
        "role": "parked high-risk autonomous capital R&D thought experiment boundary",
    },
    {
        "surface_id": "security_delta_review_contract",
        "path": SECURITY_DELTA_REVIEW_CONTRACT_READ_MODEL_PATH,
        "role": "future addition delta review against the Security Pass baseline",
    },
    {
        "surface_id": "operator_attention_promotion_contract",
        "path": OPERATOR_ATTENTION_PROMOTION_CONTRACT_READ_MODEL_PATH,
        "role": "operator attention promotion, quiet helm, holding-cell, and cue classification rules",
    },
    {
        "surface_id": "chief_test_harness_cross_off_receipt_contract",
        "path": CHIEF_TEST_HARNESS_CROSS_OFF_RECEIPT_CONTRACT_READ_MODEL_PATH,
        "role": "Chief completion proof, cross-off receipt, requeue, and quiet-with-proof rules",
    },
    {
        "surface_id": "operator_workbench_actor_host_registry",
        "path": "generated/read_models/operator_workbench_actor_host_registry.json",
        "role": "workbench/actor host routing metadata",
    },
    {
        "surface_id": "steel_thread_lane_template_registry",
        "path": "generated/read_models/steel_thread_lane_template_registry.json",
        "role": "reusable lane rendering/workflow template",
    },
)

AGENT_DOSSIER_CARD_FIELDS = (
    "agent_id",
    "display_name",
    "card_type",
    "agent_class",
    "visual_archetype",
    "portrait_asset_status",
    "portrait_asset_ref",
    "tagline",
    "plain_english_role",
    "domains",
    "strengths",
    "known_capabilities",
    "partly_known_capabilities",
    "known_unknowns",
    "not_discovered",
    "current_allowed_actions",
    "current_blocked_actions",
    "future_eligible_actions",
    "authority_boundary",
    "permissions_summary",
    "memory_scope_summary",
    "tool_adapter_summary",
    "model_selection_summary",
    "package_types_supported",
    "package_preview_available",
    "required_gates",
    "required_receipts",
    "operator_questions",
    "safe_next_detour",
    "lane_destiny",
    "quiet_condition",
    "world_affinity",
    "relationship_to_other_agents",
    "mission_control_display_guidance",
)

FEATURED_AGENT_CARD_IDS = (
    "cassandra",
    "chief",
    "guardian",
    "hermes",
    "niles",
    "struna",
)

SYSTEM_LOOP_CARD_IDS = (
    "agentic_loop",
    "cue_parser_brain_dump_parser",
    "repo_b_planner_builder_orchestrator",
    "package_compiler",
    "model_router",
    "tool_plugin_registry",
)

NO_AUTHORITY_FLAGS = {
    "metadata_only": True,
    "read_model_only": True,
    "map_snapshot_only": True,
    "raw_private_bodies_included": False,
    "credentials_included": False,
    "secrets_included": False,
    "mission_control_app_changed": False,
    "network_operation_allowed": False,
    "external_model_api_allowed": False,
    "model_execution_allowed": False,
    "agent_activation_allowed": False,
    "tool_plugin_execution_allowed": False,
    "browser_oauth_account_access_allowed": False,
    "gmail_calendar_coupa_telegram_allowed": False,
    "send_submit_approval_allowed": False,
    "runtime_activation_allowed": False,
    "planner_builder_queue_allowed": False,
    "file_delete_allowed": False,
    "file_move_allowed": False,
    "cleanup_remount_repair_allowed": False,
    "pc_c_drive_artifact_write_allowed": False,
}

FORBIDDEN_ACTIONS = (
    "git push, pull, fetch, or external network operations",
    "Mission Control Swift or app mutation",
    "Mac remount, credential handling, or share repair",
    "browser, OAuth, account, Gmail, calendar, Coupa, or Telegram access",
    "model, agent, tool, planner, builder, queue, or autonomy execution",
    "send, submit, approve, or account-flow actions",
    "file delete, file move, cleanup, remount, or repair commands",
    "OpenClaw artifact writes to the PC C drive",
    "broad private file inspection or raw private body ingestion",
)


@dataclass(frozen=True)
class OperatorMapBundleExportResult:
    schema_version: str
    contract_json_path: str
    contract_operator_path: str
    map_manifest_path: str
    map_snapshot_path: str
    map_operator_path: str
    staged_bundle_path: str
    sync_request_marker_path: str
    map_generation_id: str
    bundle_hash: str
    stable_app_facing_file_count: int
    raw_private_bodies_included: bool
    runtime_activation_allowed: bool
    pc_c_drive_artifact_write_allowed: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _hash_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_payload(payload: Any) -> str:
    return _hash_text(stable_json(payload))


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_if_present(path: str | Path, *, repo_root: str | Path = ROOT) -> dict[str, Any]:
    candidate = Path(path)
    target = candidate if candidate.is_absolute() else Path(repo_root) / candidate
    if not target.is_file():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _display_path(path: str | Path, *, repo_root: str | Path = ROOT) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _strip_volatile(value: Any) -> Any:
    volatile_keys = {
        "created_at",
        "generated_at",
        "map_generation_id",
        "manifest_hash",
        "bundle_hash",
        "snapshot_hash",
        "contract_hash",
        "receipt_hash",
        "mac_imported_at",
    }
    if isinstance(value, dict):
        return {
            key: _strip_volatile(item)
            for key, item in value.items()
            if key not in volatile_keys
        }
    if isinstance(value, list):
        return [_strip_volatile(item) for item in value]
    return value


def _content_hash(payload: Any) -> str:
    return _hash_payload(_strip_volatile(payload))


def _local_git_head(repo_root: str | Path = ROOT) -> str | None:
    git_dir = Path(repo_root) / ".git"
    head_path = git_dir / "HEAD"
    try:
        head = head_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if head.startswith("ref: "):
        ref_path = git_dir / head[5:]
        try:
            return ref_path.read_text(encoding="utf-8").strip() or None
        except OSError:
            packed_refs = git_dir / "packed-refs"
            try:
                for line in packed_refs.read_text(encoding="utf-8").splitlines():
                    if line.startswith("#") or not line.strip():
                        continue
                    sha, _, ref = line.partition(" ")
                    if ref == head[5:]:
                        return sha
            except OSError:
                return None
            return None
    return head or None


def _read_model_records(repo_root: str | Path = ROOT) -> tuple[dict[str, Any], ...]:
    return canonical_generated_read_model_records(
        source_root=DEFAULT_EXPORT_ROOT,
        repo_root=repo_root,
        include_hash=True,
    )


def _manifest_hash_for_records(records: tuple[dict[str, Any], ...]) -> str:
    normalized = [
        {
            "relative_path": record["relative_path"],
            "size_bytes": record["size_bytes"],
            "sha256": record["sha256"],
        }
        for record in records
        if record["relative_path"] not in MAP_BUNDLE_HASH_EXCLUDED_FILES
    ]
    return _hash_payload(normalized)


def _surface_record(surface: dict[str, str], *, repo_root: str | Path) -> dict[str, Any]:
    payload = _read_json_if_present(surface["path"], repo_root=repo_root)
    path = Path(repo_root) / surface["path"]
    relative_name = Path(surface["path"]).name
    volatile_self_report = relative_name in VOLATILE_SELF_REPORT_READ_MODEL_FILES
    return {
        "surface_id": surface["surface_id"],
        "path": surface["path"],
        "role": surface["role"],
        "present": path.is_file() and bool(payload),
        "schema_version": payload.get("schema_version"),
        "read_model_id": payload.get("read_model_id"),
        "hash": "sha256:" + _sha256_file(path) if path.is_file() and not volatile_self_report else None,
        "hash_included_in_bundle": path.is_file() and not volatile_self_report,
        "hash_omitted_reason": (
            "volatile_self_report_read_model_excluded_from_map_bundle_hash"
            if path.is_file() and volatile_self_report
            else None
        ),
        "raw_body_imported": False,
        "front_door_file_dependency": False,
    }


def _essential_surface_records(repo_root: str | Path = ROOT) -> list[dict[str, Any]]:
    return [_surface_record(surface, repo_root=repo_root) for surface in ESSENTIAL_SURFACES]


def _summarize_health_lights(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_path": "generated/read_models/system_health_lights_taxonomy.json",
        "present": bool(payload),
        "current_light_states": payload.get("current_light_states", {}),
        "check_transmission_summary": payload.get("check_transmission_summary", {}),
        "mac_to_e_drive_to_pc_sync_proof_complete": payload.get(
            "mac_to_e_drive_to_pc_sync_proof_complete"
        ),
        "source_truth_rule": "sync_health controls Check Transmission freshness; taxonomy must not override fresher proof",
    }


def _summarize_sync_health(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_path": "generated/read_models/sync_health.json",
        "present": bool(payload),
        "canonical_expected": payload.get("canonical_expected"),
        "observed": payload.get("observed"),
        "missing_expected": payload.get("missing_expected"),
        "hash_mismatch": payload.get("hash_mismatch"),
        "sync_lifecycle_state": payload.get("sync_lifecycle_state"),
        "mirror_status": payload.get("mirror_status"),
        "display_status": payload.get("display_status"),
        "operator_action_required": payload.get("operator_action_required"),
        "recommended_fix": payload.get("recommended_fix"),
        "raw_file_count_is_not_front_door_app_truth": True,
    }


def _summarize_threshold(payload: dict[str, Any]) -> dict[str, Any]:
    lanes = payload.get("lane_inventory") if isinstance(payload.get("lane_inventory"), list) else []
    compact_lanes: list[dict[str, Any]] = []
    for lane in lanes:
        if not isinstance(lane, dict):
            continue
        destiny = lane.get("lane_destiny") if isinstance(lane.get("lane_destiny"), dict) else {}
        compact_lanes.append(
            {
                "lane_id": lane.get("lane_id"),
                "display_name": lane.get("display_name"),
                "readiness_state": lane.get("readiness_state"),
                "resolution_route": destiny.get("resolution_route"),
                "target_world": destiny.get("target_world"),
                "safe_next_move": lane.get("safe_next_move"),
                "operator_memory_is_proof": lane.get("operator_memory_is_proof"),
                "live_dispatch_allowed_now": destiny.get("live_dispatch_allowed_now"),
            }
        )
    capital = next((lane for lane in compact_lanes if lane.get("lane_id") == "capital_hilton"), {})
    awareness = next(
        (lane for lane in compact_lanes if lane.get("lane_id") == "system_awareness_discovery"),
        {},
    )
    return {
        "source_path": "generated/read_models/operator_threshold_map_contract.json",
        "present": bool(payload),
        "threshold_state_vocab": payload.get("threshold_state_vocab", []),
        "resolution_route_vocab": payload.get("resolution_route_vocab", []),
        "lane_count": len(compact_lanes),
        "lanes": compact_lanes,
        "capital_hilton_finance_destiny": capital,
        "system_awareness_discovery_steel_thread": awareness,
        "cue_autonomy_placement": payload.get("cue_autonomy_placement", {}),
        "operator_memory_rule": (
            payload.get("second_steel_thread_system_awareness_discovery", {}).get("operator_memory_rule", {})
            if isinstance(payload.get("second_steel_thread_system_awareness_discovery"), dict)
            else {}
        ),
    }


def _summarize_mission(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_path": "generated/read_models/operator_mission_priority_helm_declutter.json",
        "present": bool(payload),
        "current_mission": payload.get("current_mission", {}),
        "helm_mode": payload.get("helm_mode"),
        "target_future_mode": payload.get("target_future_mode"),
        "current_priority_ranking": payload.get("current_priority_ranking", []),
        "front_door_render_contract": payload.get("front_door_render_contract", {}),
    }


def _summarize_worlds(payload: dict[str, Any]) -> dict[str, Any]:
    worlds = payload.get("worlds") if isinstance(payload.get("worlds"), list) else []
    compact_worlds: list[dict[str, Any]] = []
    for world in worlds:
        if isinstance(world, dict):
            compact_worlds.append(
                {
                    "world_id": world.get("world_id") or world.get("id"),
                    "display_name": world.get("display_name") or world.get("name"),
                    "status": world.get("status") or world.get("current_status"),
                    "runtime_authority": world.get("runtime_authority", False),
                }
            )
    return {
        "source_path": "generated/read_models/world_domain_registry.json",
        "present": bool(payload),
        "world_count": payload.get("world_count", len(compact_worlds)),
        "worlds": compact_worlds,
        "capital_hilton_target_world": "Finance",
    }


def _summarize_package_compiler(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_path": "generated/read_models/package_compiler_contract.json",
        "present": bool(payload),
        "package_preview_status": "preview_only_future_gated",
        "current_authority_state": payload.get("current_authority_state", {}),
        "boundary_validation_contract": payload.get("boundary_validation_contract", {}),
        "compile_time_blockers": payload.get("compile_time_blockers", []),
        "live_dispatch_allowed": False,
    }


def _next_recommended_lane(payload: dict[str, Any]) -> str | None:
    stable = payload.get("stable_map_integration") if isinstance(payload.get("stable_map_integration"), dict) else {}
    safe_summary = (
        stable.get("safe_summary_to_include_next")
        if isinstance(stable.get("safe_summary_to_include_next"), dict)
        else {}
    )
    if isinstance(safe_summary.get("next_recommended_lane"), str):
        return safe_summary["next_recommended_lane"]
    lanes = payload.get("recommended_next_lanes") if isinstance(payload.get("recommended_next_lanes"), list) else []
    for lane in lanes:
        if isinstance(lane, dict) and isinstance(lane.get("lane_id"), str):
            return lane["lane_id"]
    return None


def _required_gates_from_example(example: dict[str, Any]) -> list[str]:
    gates: list[str] = []
    for key in ("operator_gate_status", "guardian_gate_status", "security_audit_status"):
        value = example.get(key)
        if not isinstance(value, str) or not value or value.startswith("not_required"):
            continue
        gates.append(value)
    return _unique_limited(gates, limit=6)


def _package_lane_destiny(example: dict[str, Any]) -> dict[str, Any]:
    target_world = example.get("target_world")
    example_id = example.get("example_id")
    if target_world == "Finance":
        resolution_route = "MOVE_TO_WORLD_ACTION_AFTER_PROOF_AND_GATES"
    elif target_world == "Music / Art":
        resolution_route = "MOVE_TO_WORLD_ACTION_AFTER_METADATA_PROOF"
    elif example_id == "agentic_loop_classification":
        resolution_route = "REQUEUE_FOR_SYSTEM_BUILD_AFTER_DISCOVERY"
    else:
        resolution_route = "KEEP_AS_PREVIEW_OR_PROOF_DETAIL_UNTIL_GATED"
    return {
        "resolution_route": resolution_route,
        "target_world": target_world,
        "live_dispatch_allowed_now": False,
    }


def _safe_package_preview_card(example: dict[str, Any]) -> dict[str, Any]:
    target_world = example.get("target_world")
    context_included = (
        example.get("context_included_refs")
        if isinstance(example.get("context_included_refs"), list)
        else []
    )
    context_excluded = (
        example.get("context_excluded_refs")
        if isinstance(example.get("context_excluded_refs"), list)
        else []
    )
    blocked_tool_adapters = (
        example.get("blocked_tool_adapters")
        if isinstance(example.get("blocked_tool_adapters"), list)
        else []
    )
    blocked_reasons = (
        example.get("blocked_reasons")
        if isinstance(example.get("blocked_reasons"), list)
        else []
    )
    return {
        "package_id": example.get("package_id"),
        "package_title": example.get("package_title"),
        "package_type": example.get("package_type"),
        "actor_id": example.get("actor_id"),
        "agent_character": example.get("agent_character"),
        "mission": example.get("mission"),
        "why_it_matters": example.get("why_it_matters"),
        "preview_status": example.get("preview_status"),
        "sensitivity": example.get("sensitivity"),
        "context_included_summary": _unique_limited(context_included, limit=8),
        "context_excluded_summary": _unique_limited(context_excluded, limit=8),
        "missing_proof": example.get("missing_proof") if isinstance(example.get("missing_proof"), list) else [],
        "required_gates": _required_gates_from_example(example),
        "required_receipts": example.get("receipt_requirements")
        if isinstance(example.get("receipt_requirements"), list)
        else [],
        "stop_conditions": example.get("stop_conditions") if isinstance(example.get("stop_conditions"), list) else [],
        "blocked_actions": _unique_limited([*blocked_tool_adapters, *blocked_reasons], limit=12),
        "future_gated_reasons": example.get("future_gated_reasons")
        if isinstance(example.get("future_gated_reasons"), list)
        else [],
        "what_would_make_dispatchable": example.get("what_would_make_dispatchable"),
        "what_makes_safe_to_display": example.get("what_makes_safe_to_display"),
        "world_affinity": [target_world] if isinstance(target_world, str) and target_world else [],
        "lane_destiny": _package_lane_destiny(example),
        "runtime_dispatch_allowed": False,
        "model_call_allowed": False,
        "tool_execution_allowed": False,
        "agent_activation_allowed": False,
        "send_submit_approval_allowed": False,
        "queue_execution_allowed": False,
        "account_access_allowed": False,
        "raw_body_included": False,
    }


def _summarize_package_preview_receipts(payload: dict[str, Any]) -> dict[str, Any]:
    examples = (
        payload.get("example_package_preview_receipts")
        if isinstance(payload.get("example_package_preview_receipts"), list)
        else []
    )
    cards = [_safe_package_preview_card(example) for example in examples if isinstance(example, dict)]
    return {
        "source_path": PACKAGE_PREVIEW_RECEIPT_READ_MODEL_PATH,
        "present": bool(payload),
        "primary_app_contract": True,
        "individual_contract_read_model_remains_proof_detail": True,
        "contract_id": payload.get("read_model_id", "package_preview_receipt_contract"),
        "contract_version": payload.get("schema_version"),
        "receipt_types_count": len(payload.get("receipt_types", [])) if isinstance(payload.get("receipt_types"), list) else 0,
        "preview_states_count": len(payload.get("preview_states", [])) if isinstance(payload.get("preview_states"), list) else 0,
        "example_package_previews_count": len(cards),
        "package_preview_cards": cards,
        "dispatch_authority_allowed": False,
        "model_call_allowed": False,
        "tool_execution_allowed": False,
        "agent_activation_allowed": False,
        "queue_execution_allowed": False,
        "account_access_allowed": False,
        "send_submit_approval_allowed": False,
        "raw_body_included": False,
        "next_recommended_lane": _next_recommended_lane(payload),
    }


def _safe_tool_adapter_receipt_card(example: dict[str, Any]) -> dict[str, Any]:
    return {
        "adapter_id": example.get("adapter_id"),
        "adapter_display_name": example.get("adapter_display_name"),
        "adapter_category": example.get("adapter_category"),
        "adapter_state": example.get("adapter_state"),
        "receipt_type": example.get("receipt_type"),
        "receipt_state": example.get("receipt_state"),
        "package_type": example.get("package_type"),
        "actor_id": example.get("actor_id"),
        "agent_character": example.get("agent_character"),
        "capability_class_requested": example.get("capability_class_requested"),
        "capability_class_granted": example.get("capability_class_granted"),
        "capability_class_blocked": example.get("capability_class_blocked"),
        "current_allowed_actions": example.get("current_allowed_actions")
        if isinstance(example.get("current_allowed_actions"), list)
        else [],
        "current_blocked_actions": example.get("current_blocked_actions")
        if isinstance(example.get("current_blocked_actions"), list)
        else [],
        "future_eligible_actions": example.get("future_eligible_actions")
        if isinstance(example.get("future_eligible_actions"), list)
        else [],
        "input_refs_allowed_summary": _unique_limited(
            example.get("input_refs_allowed") if isinstance(example.get("input_refs_allowed"), list) else [],
            limit=8,
        ),
        "input_refs_blocked_summary": _unique_limited(
            example.get("input_refs_blocked") if isinstance(example.get("input_refs_blocked"), list) else [],
            limit=8,
        ),
        "output_receipt_shape": example.get("output_receipt_shape")
        if isinstance(example.get("output_receipt_shape"), list)
        else [],
        "gates_required": example.get("gates_required") if isinstance(example.get("gates_required"), list) else [],
        "blocked_reasons": example.get("blocked_reasons") if isinstance(example.get("blocked_reasons"), list) else [],
        "future_gated_reasons": example.get("future_gated_reasons")
        if isinstance(example.get("future_gated_reasons"), list)
        else [],
        "what_would_make_adapter_available": example.get("what_would_make_adapter_available"),
        "what_keeps_adapter_blocked": example.get("what_keeps_adapter_blocked"),
        "tool_execution_performed": False,
        "network_allowed": False,
        "account_access_allowed": False,
        "browser_session_allowed": False,
        "send_submit_approval_allowed": False,
        "command_execution_allowed": False,
        "model_call_performed": False,
        "agent_activation_performed": False,
        "queue_execution_performed": False,
    }


def _summarize_tool_adapter_receipts(payload: dict[str, Any]) -> dict[str, Any]:
    examples = (
        payload.get("example_tool_adapter_receipts")
        if isinstance(payload.get("example_tool_adapter_receipts"), list)
        else []
    )
    cards = [_safe_tool_adapter_receipt_card(example) for example in examples if isinstance(example, dict)]
    allowed_read_only_count = sum(1 for card in cards if card.get("receipt_type") == "ADAPTER_ALLOWED_READ_ONLY_RECEIPT")
    preview_or_receipt_only_count = sum(
        1
        for card in cards
        if card.get("receipt_type")
        in {"ADAPTER_ALLOWED_PREVIEW_ONLY_RECEIPT", "ADAPTER_RECEIPT_ONLY_RECEIPT"}
    )
    return {
        "source_path": TOOL_ADAPTER_RECEIPT_READ_MODEL_PATH,
        "present": bool(payload),
        "primary_app_contract": True,
        "individual_contract_read_model_remains_proof_detail": True,
        "contract_id": payload.get("read_model_id", "tool_adapter_receipt_contract"),
        "contract_version": payload.get("schema_version"),
        "receipt_types_count": len(payload.get("receipt_types", [])) if isinstance(payload.get("receipt_types"), list) else 0,
        "receipt_states_count": len(payload.get("receipt_states", [])) if isinstance(payload.get("receipt_states"), list) else 0,
        "capability_classes_count": len(payload.get("capability_classes", [])) if isinstance(payload.get("capability_classes"), list) else 0,
        "adapter_examples_count": len(cards),
        "allowed_read_only_count": allowed_read_only_count,
        "preview_or_receipt_only_count": preview_or_receipt_only_count,
        "blocked_or_future_gated_count": len(cards) - allowed_read_only_count - preview_or_receipt_only_count,
        "adapter_receipt_cards": cards,
        "live_tool_execution_allowed": False,
        "network_allowed": False,
        "account_access_allowed": False,
        "browser_session_allowed": False,
        "send_submit_approval_allowed": False,
        "command_execution_allowed": False,
        "next_recommended_lane": _next_recommended_lane(payload),
    }


CAPITAL_HILTON_AUTHORITY_FLAG_FIELDS = (
    "coupa_access_allowed",
    "browser_oauth_allowed",
    "credential_handling_allowed",
    "gmail_calendar_access_allowed",
    "email_account_access_allowed",
    "excel_raw_body_ingestion_allowed",
    "raw_finance_body_ingestion_allowed",
    "invoice_generation_allowed",
    "send_submit_approval_allowed",
    "account_access_allowed",
    "model_call_allowed",
    "agent_activation_allowed",
    "tool_execution_allowed",
    "queue_execution_allowed",
    "runtime_dispatch_allowed",
)


def _safe_capital_hilton_candidate_fact(fact: dict[str, Any]) -> dict[str, Any]:
    proof_status = fact.get("proof_status")
    machine_proven = fact.get("machine_proven") is True
    source_reference = fact.get("source_reference")
    return {
        "fact_id": fact.get("fact_id"),
        "display_name": fact.get("display_name"),
        "current_value": fact.get("current_value"),
        "current_status": fact.get("current_status"),
        "proof_category": fact.get("proof_category"),
        "proof_status": proof_status,
        "candidate_not_machine_proven": not machine_proven,
        "machine_proven": machine_proven,
        "source_type": fact.get("source_authority_status"),
        "source_reference": source_reference,
        "proof_ref": source_reference if machine_proven else None,
        "proof_missing": not machine_proven,
        "protected_proof_required": fact.get("protected_proof_required") is True,
        "guardian_review_required": fact.get("guardian_review_required") is True,
        "operator_confirmation_required": fact.get("operator_confirmation_required") is True,
        "raw_body_included": False,
        "what_would_prove_it": fact.get("what_would_prove_it"),
    }


def _safe_capital_hilton_proof_metadata(record: dict[str, Any]) -> dict[str, Any]:
    protected = record.get("protected_proof_required") is True
    return {
        "proof_id": record.get("proof_metadata_id"),
        "display_name": str(record.get("proof_metadata_id") or "").replace("_", " ").title(),
        "current_status": record.get("current_status"),
        "proof_category": record.get("proof_category"),
        "required_for_security_audit": record.get("required_for_security_audit") is True,
        "required_for_finance_world_action": record.get("required_for_finance_world_action") is True,
        "raw_body_blocked": True,
        "protected_material": protected,
        "missing": record.get("current_proof_present") is not True,
        "safe_next_step": record.get("source_expectation"),
    }


def _summarize_capital_hilton_proof_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    lane = (
        payload.get("capital_hilton_lane_fact_posture")
        if isinstance(payload.get("capital_hilton_lane_fact_posture"), dict)
        else {}
    )
    candidate_facts = [
        _safe_capital_hilton_candidate_fact(fact)
        for fact in (
            payload.get("capital_hilton_candidate_facts")
            if isinstance(payload.get("capital_hilton_candidate_facts"), list)
            else []
        )
        if isinstance(fact, dict)
    ]
    proof_metadata = [
        _safe_capital_hilton_proof_metadata(record)
        for record in (
            payload.get("required_proof_metadata")
            if isinstance(payload.get("required_proof_metadata"), list)
            else []
        )
        if isinstance(record, dict)
    ]
    authority_source = (
        payload.get("authority_boundary")
        if isinstance(payload.get("authority_boundary"), dict)
        else payload
    )
    authority_boundary = {
        field: False if field == "email_account_access_allowed" else authority_source.get(field, False)
        for field in CAPITAL_HILTON_AUTHORITY_FLAG_FIELDS
    }
    known = lane.get("known") if isinstance(lane.get("known"), list) else []
    partly_known = lane.get("partly_known") if isinstance(lane.get("partly_known"), list) else []
    known_unknown = lane.get("known_unknown") if isinstance(lane.get("known_unknown"), list) else []
    not_discovered = lane.get("not_discovered") if isinstance(lane.get("not_discovered"), list) else []
    operator_questions = (
        payload.get("operator_memory_questions")
        if isinstance(payload.get("operator_memory_questions"), list)
        else []
    )
    missing_proof = (
        payload.get("missing_proof_checklist")
        if isinstance(payload.get("missing_proof_checklist"), list)
        else lane.get("machine_proof_needed", [])
    )
    return {
        "source_path": CAPITAL_HILTON_PROOF_METADATA_READ_MODEL_PATH,
        "present": bool(payload),
        "primary_app_contract": True,
        "individual_contract_read_model_remains_proof_detail": True,
        "contract_id": payload.get("read_model_id", "capital_hilton_proof_metadata_packet"),
        "contract_version": payload.get("schema_version"),
        "lane_id": lane.get("lane_id", "capital_hilton"),
        "current_phase": lane.get("current_phase"),
        "target_world": lane.get("target_world"),
        "lane_destiny": lane.get("lane_destiny"),
        "workflow_type": lane.get("workflow_type"),
        "current_status": lane.get("current_status"),
        "known": known,
        "partly_known": partly_known,
        "known_unknown": known_unknown,
        "not_discovered": not_discovered,
        "candidate_facts": candidate_facts,
        "proven_facts": [fact for fact in candidate_facts if fact["machine_proven"] is True],
        "missing_proof": missing_proof,
        "missing_proof_count": len(missing_proof),
        "protected_proof_required": (
            payload.get("machine_proof", {}).get("protected_proof_required") is True
            if isinstance(payload.get("machine_proof"), dict)
            else True
        ),
        "operator_memory_needed": lane.get("operator_memory_needed", []),
        "machine_proof_needed": lane.get("machine_proof_needed", missing_proof),
        "safe_next_detour": lane.get("safe_next_detour"),
        "quiet_condition": lane.get("quiet_condition"),
        "security_audit_readiness": lane.get("security_audit_readiness"),
        "finance_world_action_readiness": lane.get("finance_world_action_readiness"),
        "authority_boundary": authority_boundary,
        "next_safe_move": lane.get("safe_next_detour"),
        "proof_metadata_checklist": proof_metadata,
        "actor_package_adapter_summary": payload.get("actor_package_adapter_binding", {}),
        "operator_memory_questions": operator_questions,
        "operator_answers_become_memory_candidate_receipts_not_proof": True,
        "finance_world_preview": {
            "preview_only": True,
            "pre_security": True,
            "proof_metadata_needed": True,
            "target_world": "Finance",
            "not_executable": True,
            "no_coupa": True,
            "no_credentials": True,
            "no_send_submit_approval": True,
            "no_account_flow": True,
            "no_invoice_generation": True,
        },
        "all_candidate_facts_marked_not_proven": all(
            fact["machine_proven"] is False for fact in candidate_facts
        ),
        "raw_finance_body_included": False,
        "credential_or_secret_included": False,
        "live_execution_authority": False,
    }


def _display_name_from_breadcrumb_id(breadcrumb_id: str) -> str:
    special = {
        "operator_attention_promotion_contract_v0": "Operator Attention Promotion Contract v0",
        "breadcrumb_holding_cell_cue_queue_quiet_helm_doctrine": "Breadcrumb -> Holding Cell -> Cue -> Queue -> Quiet Helm Doctrine",
        "operator_sleep_mode_queue_priority_posture": "Operator Sleep Mode / Queue Priority Posture",
        "agent_lifecycle_telemetry_animation_contract": "Agent Lifecycle Telemetry / Animation Contract",
        "agent_chat_package_workspace_surface": "Agent Chat / Package Workspace Surface",
        "tell_system_whats_missing_capture_path": "Tell System What's Missing Capture Path",
        "holding_cell_future_trigger_registry": "Holding Cell / Future Trigger Registry",
        "chief_test_harness_receipt": "Chief Test Harness Receipt",
        "repo_b_planner_builder_classification_packet": "Repo B Planner/Builder Classification Packet",
        "package_execution_queue_doctrine": "Package Execution Queue Doctrine",
        "finance_world_action_shell": "Finance World Action Shell",
        "music_art_world_niles_struna_operating_surface": "Music / Art World - Niles + Struna Operating Surface",
        "world_graduation_rules": "World Graduation Rules",
        "operator_morning_midday_evening_brief_surfaces": "Operator Morning / Midday / Evening Brief Surfaces",
        "compromise_suspicion_kill_switch_posture": "Compromise / Suspicion / Kill-Switch Posture",
    }
    return special.get(breadcrumb_id, breadcrumb_id.replace("_", " ").title())


def _summarize_security_audit_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    criteria = (
        payload.get("security_pass_readiness_criteria")
        if isinstance(payload.get("security_pass_readiness_criteria"), dict)
        else {}
    )
    machine = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), dict) else {}
    coverage = (
        payload.get("coverage_gap_unmapped_terrain_registry")
        if isinstance(payload.get("coverage_gap_unmapped_terrain_registry"), dict)
        else {}
    )
    coverage_records = coverage.get("records") if isinstance(coverage.get("records"), list) else []
    coverage_ids = {
        record.get("coverage_item_id")
        for record in coverage_records
        if isinstance(record, dict)
    }
    breadcrumb_review = (
        payload.get("parked_breadcrumb_review")
        if isinstance(payload.get("parked_breadcrumb_review"), dict)
        else {}
    )
    breadcrumb_records = (
        breadcrumb_review.get("records")
        if isinstance(breadcrumb_review.get("records"), list)
        else []
    )
    breadcrumb_ids = [
        str(record.get("breadcrumb_id"))
        for record in breadcrumb_records
        if isinstance(record, dict) and record.get("breadcrumb_id")
    ]
    shared_paths = (
        payload.get("shared_execution_paths")
        if isinstance(payload.get("shared_execution_paths"), list)
        else []
    )
    shared_path_ids = {
        path.get("shared_execution_path_id")
        for path in shared_paths
        if isinstance(path, dict)
    }
    focus_modes = (
        payload.get("helm_issue_focus_modes")
        if isinstance(payload.get("helm_issue_focus_modes"), list)
        else []
    )
    focus_ids = {
        focus.get("issue_focus_id")
        for focus in focus_modes
        if isinstance(focus, dict)
    }
    quieting = (
        payload.get("question_quieting_rule")
        if isinstance(payload.get("question_quieting_rule"), dict)
        else {}
    )
    answer_capture = (
        payload.get("operator_answer_capture_contract")
        if isinstance(payload.get("operator_answer_capture_contract"), list)
        else []
    )
    capital = (
        payload.get("capital_hilton_security_readiness")
        if isinstance(payload.get("capital_hilton_security_readiness"), dict)
        else {}
    )
    capital_posture = (
        payload.get("capital_hilton_current_stable_map_posture")
        if isinstance(payload.get("capital_hilton_current_stable_map_posture"), dict)
        else {}
    )
    map_to_terrain = (
        payload.get("map_to_terrain_provenance")
        if isinstance(payload.get("map_to_terrain_provenance"), list)
        else []
    )
    package_rule = (
        payload.get("package_map_slice_rule")
        if isinstance(payload.get("package_map_slice_rule"), dict)
        else {}
    )
    supported_modalities = (
        payload.get("allowed_answer_modalities")
        if isinstance(payload.get("allowed_answer_modalities"), list)
        else []
    )
    next_safe_move = criteria.get("next_safe_move") or "Run security pass review; do not grant action authority from this map."
    known_breadcrumbs = [
        _display_name_from_breadcrumb_id(breadcrumb_id)
        for breadcrumb_id in breadcrumb_ids
    ]
    return {
        "source_path": SECURITY_AUDIT_READINESS_READ_MODEL_PATH,
        "source_operator_ref": "generated/read_models/security_audit_readiness_packet_OPERATOR.md",
        "present": bool(payload),
        "primary_app_contract": True,
        "individual_packet_read_model_remains_proof_detail": True,
        "packet_id": payload.get("read_model_id", "security_audit_readiness_packet"),
        "schema_version": payload.get("schema_version"),
        "ready_for_security_pass": criteria.get("ready_for_security_pass") is True,
        "security_approval_granted": False,
        "action_authority_granted": False,
        "map_to_terrain_provenance_present": bool(map_to_terrain),
        "package_map_slice_rule_present": bool(package_rule),
        "operator_answer_capture_present": bool(answer_capture),
        "question_quieting_model_present": bool(quieting),
        "shared_execution_paths_present": bool(shared_paths),
        "helm_issue_focus_mode_present": bool(focus_modes),
        "coverage_gap_registry_present": bool(coverage_records),
        "parked_breadcrumb_review_present": bool(breadcrumb_records),
        "capital_hilton_security_readiness_present": bool(capital),
        "all_authority_flags_false": machine.get("all_dangerous_authority_flags_false") is True
        or criteria.get("all_authority_flags_strictly_false") is True,
        "zero_execution_authority_leaked": criteria.get("zero_execution_authority_leaked") is True,
        "raw_private_bodies_excluded": criteria.get("raw_private_bodies_excluded") is True,
        "credentials_and_account_access_blocked": criteria.get("credentials_and_account_access_blocked") is True,
        "hidden_automation_absent": criteria.get("hidden_automation_absent") is True,
        "next_safe_move": next_safe_move,
        "readiness_blockers": criteria.get("readiness_blockers")
        if isinstance(criteria.get("readiness_blockers"), list)
        else [],
        "stable_map_generation_id": machine.get("map_generation_id"),
        "source_read_model_ref": SECURITY_AUDIT_READINESS_READ_MODEL_PATH,
        "map_to_terrain_provenance_summary": {
            "stable_map_is_source_truth": False,
            "stable_map_is_app_facing_reflection": True,
            "claims_require_source_or_candidate_status": True,
            "packages_use_map_slices_with_proof_refs": True,
            "candidate_claims_not_proof": True,
            "missing_proof_blocks_action": True,
            "provenance_claims_count": len(map_to_terrain),
        },
        "operator_answer_capture_summary": {
            "answer_capture_schema_present": bool(answer_capture),
            "operator_answers_are_memory_candidates": True,
            "operator_answers_are_not_proof": True,
            "question_quieting_states_count": len(quieting.get("question_states", []))
            if isinstance(quieting.get("question_states"), list)
            else 0,
            "supported_answer_modalities": supported_modalities,
            "capture_is_preview_only": True,
            "answer_popup_implemented": False,
        },
        "shared_execution_path_summary": {
            "shared_execution_paths_count": len(shared_paths),
            "protected_finance_proof_metadata_intake_present": "protected_finance_proof_metadata_intake" in shared_path_ids,
            "operator_memory_question_capture_present": "operator_memory_question_capture" in shared_path_ids,
            "stable_map_receipt_readback_present": "stable_map_receipt_readback" in shared_path_ids,
            "shared_paths_are_non_executing": True,
            "solving_once_can_update_multiple_lanes": True,
        },
        "helm_issue_focus_mode_summary": {
            "focus_mode_defined": bool(focus_modes),
            "issue_focus_cards_count": len(focus_modes),
            "unrelated_cards_collapse_when_selected": True,
            "proof_stays_behind_disclosure": True,
            "no_live_controls": True,
            "capital_hilton_focus_available": "focus_capital_hilton_missing_proof" in focus_ids,
            "protected_finance_shared_focus_available": "focus_capital_hilton_missing_proof" in focus_ids,
        },
        "coverage_gap_summary": {
            "coverage_gap_registry_present": bool(coverage_records),
            "coverage_gap_records_count": len(coverage_records),
            "markdown_document_terrain_present": "markdown_document_terrain" in coverage_ids,
            "tagging_system_capability_present": "tagging_system_capability" in coverage_ids,
            "mission_control_visibility_gap_present": "mission_control_visibility_gap" in coverage_ids,
            "operator_memory_gap_present": "operator_memory_gap" in coverage_ids,
            "repo_terrain_gap_present": "repo_terrain_gap" in coverage_ids,
            "broad_markdown_scan_allowed": False,
            "file_moves_allowed": False,
            "repo_b_body_inspection_allowed": False,
        },
        "parked_breadcrumb_summary": {
            "parked_breadcrumb_review_present": bool(breadcrumb_records),
            "parked_breadcrumb_count": len(breadcrumb_records),
            "auto_promotion_allowed": False,
            "queue_creation_allowed": False,
            "trigger_engine_allowed": False,
            "known_highlighted_breadcrumbs": known_breadcrumbs,
        },
        "capital_hilton_security_readiness_summary": {
            "current_phase": capital_posture.get("current_phase", "HELM_THRESHOLD_LANE"),
            "target_world": capital_posture.get("target_world", "Finance"),
            "lane_destiny": capital_posture.get("lane_destiny", "MOVE_TO_WORLD_ACTION"),
            "security_readiness_status": capital.get("readiness_status"),
            "missing_proof_count": capital.get("missing_proof_count"),
            "protected_proof_required": capital.get("protected_proof_required") is True,
            "candidate_facts_proven": capital.get("candidate_facts_proven") is True,
            "security_pass_complete": capital.get("security_pass_complete") is True,
            "action_authority_granted": False,
            "shared_execution_path_id": capital.get("shared_execution_path_id"),
            "finance_world_preview_exists": capital.get("finance_world_preview_exists") is True
            or capital_posture.get("target_world") == "Finance",
        },
        "no_authority_flags": {
            "security_approval_granted": False,
            "action_authority_granted": False,
            "answer_popup_implemented": False,
            "queue_creation_allowed": False,
            "trigger_engine_allowed": False,
            "tool_execution_allowed": False,
            "model_execution_allowed": False,
            "agent_activation_allowed": False,
            "browser_oauth_account_access_allowed": False,
            "send_submit_approval_allowed": False,
        },
    }


def _security_pass_bool(payload: dict[str, Any], *keys: str) -> bool:
    output = (
        payload.get("security_pass_output_summary")
        if isinstance(payload.get("security_pass_output_summary"), dict)
        else {}
    )
    machine = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), dict) else {}
    return any(source.get(key) is True for key in keys for source in (payload, output, machine))


def _security_pass_false(payload: dict[str, Any], *keys: str) -> bool:
    output = (
        payload.get("security_pass_output_summary")
        if isinstance(payload.get("security_pass_output_summary"), dict)
        else {}
    )
    machine = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), dict) else {}
    return any(source.get(key) is False for key in keys for source in (payload, output, machine))


def _surface_id_from_security_pass_decision(decision: dict[str, Any]) -> str:
    known = {
        "stable_map_bundle_read_only": "stable_map_bundle",
        "mission_control_mac_app_read_only": "mission_control",
        "agent_council_dossier_cards_preview": "agent_council",
        "package_preview_tool_receipt_surface": "package_preview_tool_receipt",
        "finance_world_capital_hilton_preview": "finance_world_capital_hilton",
        "security_readiness_eliwinship_surface": "security_readiness_eliwinship",
        "evidence_drawer_proof_rows": "evidence_drawer",
    }
    decision_id = str(decision.get("decision_id") or "")
    if decision_id in known:
        return known[decision_id]
    return decision_id or str(decision.get("target_surface") or "unknown_surface").lower().replace(" ", "_")


def _summarize_security_pass_surface_decisions(decisions: list[Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        authority = (
            decision.get("authority_flags")
            if isinstance(decision.get("authority_flags"), dict)
            else {}
        )
        summaries.append(
            {
                "surface_id": _surface_id_from_security_pass_decision(decision),
                "display_name": decision.get("target_surface"),
                "approved_posture": decision.get("allowed_posture")
                if isinstance(decision.get("allowed_posture"), list)
                else [],
                "blocked_posture": decision.get("blocked_posture")
                if isinstance(decision.get("blocked_posture"), list)
                else [],
                "authority_summary": {
                    "approval_status": decision.get("approval_status"),
                    "action_authority_granted": authority.get("action_authority_granted") is True,
                    "runtime_execution_authority_granted": authority.get("runtime_execution_authority_granted") is True,
                    "tool_execution_authority_granted": authority.get("tool_execution_authority_granted") is True,
                    "model_execution_authority_granted": authority.get("model_execution_authority_granted") is True,
                    "account_authority_granted": authority.get("account_authority_granted") is True,
                    "send_submit_approval_authority_granted": authority.get("send_submit_approval_authority_granted") is True,
                },
                "next_safe_move": decision.get("next_safe_move"),
            }
        )
    return summaries


def _summarize_security_pass(payload: dict[str, Any]) -> dict[str, Any]:
    machine = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), dict) else {}
    surface_decisions = (
        payload.get("surface_security_decisions")
        if isinstance(payload.get("surface_security_decisions"), list)
        else []
    )
    capital = (
        payload.get("capital_hilton_security_pass_decision")
        if isinstance(payload.get("capital_hilton_security_pass_decision"), dict)
        else {}
    )
    capital_blocked = capital.get("blocked") if isinstance(capital.get("blocked"), dict) else {}
    capital_decision = capital.get("decision") if isinstance(capital.get("decision"), dict) else {}
    capital_gates = capital.get("required_gates") if isinstance(capital.get("required_gates"), dict) else {}
    markdown = (
        payload.get("markdown_terrain_security_decision")
        if isinstance(payload.get("markdown_terrain_security_decision"), dict)
        else {}
    )
    markdown_decision = markdown.get("decision") if isinstance(markdown.get("decision"), dict) else {}
    markdown_blocked = markdown.get("blocked") if isinstance(markdown.get("blocked"), dict) else {}
    markdown_systems = (
        markdown.get("existing_systems")
        if isinstance(markdown.get("existing_systems"), list)
        else []
    )
    markdown_system_paths = {
        system.get("path")
        for system in markdown_systems
        if isinstance(system, dict)
    }
    worker_intake = (
        payload.get("worker_output_intake")
        if isinstance(payload.get("worker_output_intake"), dict)
        else {}
    )
    worker_records = (
        worker_intake.get("records")
        if isinstance(worker_intake.get("records"), list)
        else []
    )
    future_invoicing = next(
        (
            record
            for record in worker_records
            if isinstance(record, dict)
            and record.get("worker_output_id") == "future_invoicing_state_machine_audit"
        ),
        {},
    )
    orphaned = (
        payload.get("orphaned_capability_detection")
        if isinstance(payload.get("orphaned_capability_detection"), dict)
        else {}
    )
    orphaned_candidates = (
        orphaned.get("candidates")
        if isinstance(orphaned.get("candidates"), list)
        else []
    )
    orphaned_ids = {
        candidate.get("capability_id")
        for candidate in orphaned_candidates
        if isinstance(candidate, dict)
    }
    promotion = (
        payload.get("orphaned_capability_promotion_decisions")
        if isinstance(payload.get("orphaned_capability_promotion_decisions"), dict)
        else {}
    )
    promotion_rules = promotion.get("rules") if isinstance(promotion.get("rules"), list) else []
    trust = (
        payload.get("chief_hermes_trust_building_reconciliation")
        if isinstance(payload.get("chief_hermes_trust_building_reconciliation"), dict)
        else {}
    )
    chief = trust.get("chief_role") if isinstance(trust.get("chief_role"), dict) else {}
    hermes = trust.get("hermes_role") if isinstance(trust.get("hermes_role"), dict) else {}
    trust_model = (
        trust.get("trust_clearance_model")
        if isinstance(trust.get("trust_clearance_model"), dict)
        else {}
    )
    trust_rules = trust_model.get("rules") if isinstance(trust_model.get("rules"), dict) else {}
    cross_off = (
        payload.get("completion_cross_off_rule")
        if isinstance(payload.get("completion_cross_off_rule"), dict)
        else {}
    )
    detours = (
        payload.get("trust_building_detours")
        if isinstance(payload.get("trust_building_detours"), dict)
        else {}
    )
    automatic_activation_allowed = _security_pass_bool(
        payload,
        "automatic_activation_allowed",
        "automatic_activation_of_detected_capabilities_allowed",
    )
    automatic_cross_off_allowed = _security_pass_bool(payload, "automatic_cross_off_allowed")
    return {
        "source_path": SECURITY_PASS_CONTRACT_READ_MODEL_PATH,
        "source_operator_ref": "generated/read_models/security_pass_contract_OPERATOR.md",
        "present": bool(payload),
        "primary_app_contract": True,
        "individual_contract_read_model_remains_proof_detail": True,
        "contract_id": payload.get("read_model_id", "security_pass_contract"),
        "schema_version": payload.get("schema_version"),
        "security_pass_completed": _security_pass_bool(payload, "security_pass_completed"),
        "read_only_surfaces_approved": _security_pass_bool(
            payload, "security_approval_granted_for_read_only_surfaces", "read_only_surfaces_approved"
        ),
        "preview_surfaces_approved": _security_pass_bool(
            payload, "security_approval_granted_for_preview_surfaces", "preview_surfaces_approved"
        ),
        "metadata_only_surfaces_approved": _security_pass_bool(
            payload, "security_approval_granted_for_metadata_only_surfaces", "metadata_only_surfaces_approved"
        ),
        "worker_output_intake_metadata_approved": _security_pass_bool(
            payload,
            "security_approval_granted_for_worker_output_intake_metadata",
            "worker_output_intake_metadata_approved",
        ),
        "orphaned_capability_detection_approved": _security_pass_bool(
            payload,
            "security_approval_granted_for_orphaned_capability_detection",
            "orphaned_capability_detection_approved",
        ),
        "chief_reconciliation_metadata_approved": _security_pass_bool(
            payload,
            "security_approval_granted_for_chief_reconciliation_metadata",
            "chief_reconciliation_metadata_approved",
        ),
        "hermes_architecture_review_metadata_approved": _security_pass_bool(
            payload,
            "security_approval_granted_for_hermes_architecture_review_metadata",
            "hermes_architecture_review_metadata_approved",
        ),
        "trust_clearance_modeling_approved": _security_pass_bool(
            payload,
            "security_approval_granted_for_trust_clearance_modeling",
            "trust_clearance_modeling_approved",
        ),
        "action_authority_granted": _security_pass_bool(payload, "action_authority_granted"),
        "runtime_execution_authority_granted": _security_pass_bool(payload, "runtime_execution_authority_granted"),
        "tool_execution_authority_granted": _security_pass_bool(payload, "tool_execution_authority_granted"),
        "model_execution_authority_granted": _security_pass_bool(payload, "model_execution_authority_granted"),
        "queue_execution_authority_granted": _security_pass_bool(payload, "queue_execution_authority_granted"),
        "account_authority_granted": _security_pass_bool(payload, "account_authority_granted"),
        "send_submit_approval_authority_granted": _security_pass_bool(
            payload, "send_submit_approval_authority_granted"
        ),
        "chief_self_authorization_allowed": _security_pass_bool(payload, "chief_self_authorization_allowed"),
        "hermes_self_authorization_allowed": _security_pass_bool(payload, "hermes_self_authorization_allowed"),
        "automatic_activation_allowed": automatic_activation_allowed,
        "automatic_cross_off_allowed": automatic_cross_off_allowed,
        "next_safe_move": "Refresh stable map, import on Mac, then use read-only Security Pass surface for operator review.",
        "source_read_model_ref": SECURITY_PASS_CONTRACT_READ_MODEL_PATH,
        "source_operator_ref": "generated/read_models/security_pass_contract_OPERATOR.md",
        "surface_decision_summary": _summarize_security_pass_surface_decisions(surface_decisions),
        "capital_hilton_security_pass_decision_summary": {
            "current_phase": capital.get("current_phase", "HELM_THRESHOLD_LANE"),
            "target_world": capital.get("target_world", "Finance"),
            "lane_destiny": capital.get("lane_destiny", "MOVE_TO_WORLD_ACTION"),
            "missing_proof_count": capital.get("missing_proof_count"),
            "protected_proof_required": capital.get("protected_proof_required") is True,
            "candidate_facts_proven": capital.get("candidate_facts_proven") is True,
            "finance_world_preview_approved": capital_decision.get("finance_world_preview") == "approved",
            "proof_metadata_display_approved": capital_decision.get("proof_metadata_display") == "approved",
            "operator_questions_display_approved": capital_decision.get("operator_questions_display") == "approved",
            "invoice_generation_allowed": False,
            "coupa_access_allowed": False,
            "browser_oauth_account_access_allowed": not bool(
                capital_blocked.get("browser_oauth_account_access", True)
            ),
            "credential_handling_allowed": not bool(capital_blocked.get("credentials", True)),
            "gmail_calendar_email_access_allowed": not bool(
                capital_blocked.get("gmail_calendar_email_account_access", True)
            ),
            "raw_excel_body_ingestion_allowed": not bool(
                capital_blocked.get("excel_raw_body_ingestion", True)
            ),
            "raw_finance_body_ingestion_allowed": not bool(
                capital_blocked.get("raw_finance_body_ingestion", True)
            ),
            "send_submit_approval_allowed": not bool(capital_blocked.get("send_submit_approval", True)),
            "guardian_gate_required": bool(capital_gates.get("guardian_gate")),
            "operator_final_authority_required": bool(capital_gates.get("operator_final_authority")),
            "shared_execution_path_id": capital.get("shared_execution_path_id"),
        },
        "markdown_terrain_security_decision_summary": {
            "markdown_backend_ready": markdown.get("markdown_backend_capability_status") == "YES_READY",
            "markdown_knowledge_atlas_present": "markdown_knowledge_atlas.py" in markdown_system_paths,
            "approved_markdown_evidence_ingestion_present": "markdown_evidence_ingestion.py" in markdown_system_paths,
            "corpus_atlas_present": "corpus_atlas.py" in markdown_system_paths,
            "metadata_readback_approved": markdown_decision.get("metadata_only_markdown_atlas_readback") == "approved",
            "bounded_allowlisted_excerpt_metadata_approved": (
                markdown_decision.get("allowlisted_bounded_markdown_evidence_excerpts") == "approved"
            ),
            "broad_markdown_body_ingestion_allowed": not bool(
                markdown_blocked.get("broad_markdown_body_ingestion", True)
            ),
            "broad_doc_reorganization_allowed": not bool(
                markdown_blocked.get("broad_doc_reorganization", True)
            ),
            "file_moves_deletes_renames_allowed": not bool(
                markdown_blocked.get("file_moves_deletes_renames", True)
            ),
            "vector_index_creation_allowed": not bool(markdown_blocked.get("vector_index_creation", True)),
            "stale_doctrine_promotion_without_proof_allowed": not bool(
                markdown_blocked.get("stale_doctrine_promotion_without_proof", True)
            ),
            "app_visibility_future_gap": (
                markdown_decision.get("app_visibility_for_markdown_terrain")
                == "future_gated_visibility_gap_not_security_blocker"
            ),
        },
        "worker_output_orphaned_capability_summary": {
            "worker_output_intake_metadata_approved": _security_pass_bool(
                payload,
                "security_approval_granted_for_worker_output_intake_metadata",
                "worker_output_intake_metadata_approved",
            ),
            "orphaned_capability_detection_approved": _security_pass_bool(
                payload,
                "security_approval_granted_for_orphaned_capability_detection",
                "orphaned_capability_detection_approved",
            ),
            "detected_capabilities_auto_activate": automatic_activation_allowed,
            "promotion_decisions_are_recommendations_only": (
                machine.get("promotion_decisions_are_recommendations_only") is True
                or "recommendations_only" in " ".join(str(rule) for rule in promotion_rules)
            ),
            "markdown_knowledge_atlas_candidate_present": "markdown_knowledge_atlas" in orphaned_ids,
            "approved_markdown_evidence_ingestion_candidate_present": "approved_markdown_evidence_ingestion" in orphaned_ids,
            "corpus_atlas_candidate_present": "corpus_atlas_engine" in orphaned_ids,
            "future_invoicing_audit_captured": bool(future_invoicing),
            "future_invoicing_audit_status": future_invoicing.get("intake_status") or machine.get("future_invoicing_audit_status"),
            "ledger_write_allowed": False,
            "invoice_generation_allowed": False,
            "email_dispatch_allowed": False,
        },
        "chief_hermes_trust_summary": {
            "chief_reconciliation_metadata_approved": _security_pass_bool(
                payload,
                "security_approval_granted_for_chief_reconciliation_metadata",
                "chief_reconciliation_metadata_approved",
            ),
            "hermes_architecture_review_metadata_approved": _security_pass_bool(
                payload,
                "security_approval_granted_for_hermes_architecture_review_metadata",
                "hermes_architecture_review_metadata_approved",
            ),
            "trust_clearance_modeling_approved": _security_pass_bool(
                payload,
                "security_approval_granted_for_trust_clearance_modeling",
                "trust_clearance_modeling_approved",
            ),
            "full_trust_clearance_is_lm_confidence": False,
            "full_trust_clearance_grants_authority_by_itself": False,
            "below_full_trust_runs_unattended": False,
            "chief_self_authorization_allowed": chief.get("can_self_authorize") is True,
            "hermes_self_authorization_allowed": hermes.get("can_self_authorize") is True,
            "automatic_cross_off_allowed": automatic_cross_off_allowed,
            "cross_off_deletes_source_notes": "delete original note"
            not in (cross_off.get("cross_off_must_not") or []),
            "trust_detours_present": bool(detours.get("smallest_safe_detours")),
            "operator_babysitting_reduction_goal_present": bool(
                chief.get("operator_babysitting_reduction_goal")
                or detours.get("operator_babysitting_reduction_goal")
            ),
            "full_trust_rules": trust_rules,
        },
        "all_live_authority_false": bool(
            _security_pass_false(payload, "action_authority_granted")
            and _security_pass_false(payload, "runtime_execution_authority_granted")
            and _security_pass_false(payload, "tool_execution_authority_granted")
            and _security_pass_false(payload, "model_execution_authority_granted")
            and _security_pass_false(payload, "queue_execution_authority_granted")
            and _security_pass_false(payload, "account_authority_granted")
            and _security_pass_false(payload, "send_submit_approval_authority_granted")
            and not automatic_activation_allowed
            and not automatic_cross_off_allowed
        ),
        "no_authority_flags": {
            "action_authority_granted": False,
            "runtime_execution_authority_granted": False,
            "tool_execution_authority_granted": False,
            "model_execution_authority_granted": False,
            "queue_execution_authority_granted": False,
            "account_authority_granted": False,
            "send_submit_approval_authority_granted": False,
            "chief_self_authorization_allowed": False,
            "hermes_self_authorization_allowed": False,
            "automatic_activation_allowed": False,
            "automatic_cross_off_allowed": False,
        },
    }


def _summarize_post_security_governance_batch(payload: dict[str, Any]) -> dict[str, Any]:
    lanes_planned = payload.get("lanes_planned") if isinstance(payload.get("lanes_planned"), list) else []
    lanes_completed = payload.get("lanes_completed") if isinstance(payload.get("lanes_completed"), list) else []
    authority = payload.get("authority_boundary") if isinstance(payload.get("authority_boundary"), dict) else {}
    completed_lane_ids = [
        lane.get("lane_id")
        for lane in lanes_completed
        if isinstance(lane, dict) and lane.get("lane_id")
    ]
    return {
        "source_path": POST_SECURITY_GOVERNANCE_BATCH_MANIFEST_READ_MODEL_PATH,
        "source_operator_ref": "generated/read_models/post_security_governance_batch_manifest_OPERATOR.md",
        "present": bool(payload),
        "primary_app_contract": True,
        "individual_manifest_read_model_remains_proof_detail": True,
        "batch_id": payload.get("batch_id"),
        "batch_status": payload.get("batch_status"),
        "lane_count": len(lanes_planned),
        "completed_lanes": completed_lane_ids,
        "completed_lane_count": len(completed_lane_ids),
        "stable_map_refresh_deferred": payload.get("stable_map_refresh_deferred") is True,
        "commit_deferred_until_prompt_5": payload.get("commit_deferred_until_prompt_5") is True,
        "next_expected_actor": payload.get("next_expected_actor"),
        "authority_boundary": {
            "live_execution_allowed": authority.get("live_execution_allowed") is True,
            "model_api_execution_allowed": authority.get("model_api_execution_allowed") is True,
            "actor_agent_activation_allowed": authority.get("actor_agent_activation_allowed") is True,
            "tool_execution_allowed": authority.get("tool_execution_allowed") is True,
            "queue_autonomy_allowed": authority.get(
                "runtime_planner_builder_queue_autonomy_execution_allowed"
            )
            is True,
            "account_payment_financial_allowed": authority.get(
                "financial_payment_account_access_allowed"
            )
            is True,
            "send_submit_approval_allowed": authority.get("send_submit_approval_allowed") is True,
            "mac_sync_import_allowed": authority.get("mac_sync_import_allowed") is True,
            "network_operation_allowed": authority.get("network_operation_allowed") is True,
            "all_live_authority_false": all(value is False for value in authority.values()),
        },
        "action_authority_granted": False,
        "runtime_execution_authority_granted": False,
        "model_execution_authority_granted": False,
        "tool_execution_authority_granted": False,
        "queue_execution_authority_granted": False,
        "account_authority_granted": False,
        "send_submit_approval_authority_granted": False,
        "next_safe_move": "Mac import should consume the staged stable-map bundle; this PC pass performs no Mac import.",
    }


def _summarize_parked_autonomous_capital_pipeline_experiment(payload: dict[str, Any]) -> dict[str, Any]:
    phases = payload.get("five_phase_roadmap") if isinstance(payload.get("five_phase_roadmap"), list) else []
    future_gates = payload.get("required_future_gates") if isinstance(payload.get("required_future_gates"), dict) else {}
    authority = (
        payload.get("no_action_authority_matrix")
        if isinstance(payload.get("no_action_authority_matrix"), dict)
        else {}
    )
    tokens = payload.get("allowed_tokens") if isinstance(payload.get("allowed_tokens"), dict) else {}
    stress = (
        payload.get("security_stress_test_classification")
        if isinstance(payload.get("security_stress_test_classification"), dict)
        else {}
    )
    return {
        "source_path": PARKED_AUTONOMOUS_CAPITAL_PIPELINE_EXPERIMENT_READ_MODEL_PATH,
        "source_operator_ref": "generated/read_models/parked_autonomous_capital_pipeline_experiment_OPERATOR.md",
        "present": bool(payload),
        "primary_app_contract": True,
        "individual_experiment_read_model_remains_proof_detail": True,
        "experiment_name": payload.get("experiment_name"),
        "status": payload.get("experiment_status"),
        "parked_high_risk_r_and_d": payload.get("experiment_status")
        == "PARKED_HIGH_RISK_R_AND_D_EXPERIMENT",
        "phase_count": len(phases),
        "phases_captured": [phase.get("phase_id") for phase in phases if isinstance(phase, dict)],
        "all_authority_false": all(value is False for value in authority.values()),
        "future_gates_required": bool(future_gates) and all(value is True for value in future_gates.values()),
        "future_gate_count": len(future_gates),
        "token_concept_future_only": (
            tokens.get("status") == "FUTURE_CONCEPT_ONLY"
            and tokens.get("tokens_exist_now") is False
            and tokens.get("tokens_grant_external_spend") is False
            and tokens.get("tokens_grant_account_access") is False
        ),
        "token_types": tokens.get("token_types") if isinstance(tokens.get("token_types"), list) else [],
        "stress_test_classification": stress.get("is_security_stress_test_artifact") is True,
        "stress_test_areas": stress.get("stress_test_areas")
        if isinstance(stress.get("stress_test_areas"), list)
        else [],
        "action_authority_granted": False,
        "capital_spend_allowed": authority.get("capital_spend_allowed") is True,
        "account_creation_allowed": authority.get("account_creation_allowed") is True,
        "financial_account_access_allowed": authority.get("financial_account_access_allowed") is True,
        "network_operation_allowed": authority.get("network_operation_allowed") is True,
        "model_call_allowed": authority.get("model_call_allowed") is True,
        "agent_activation_allowed": authority.get("agent_activation_allowed") is True,
        "tool_execution_allowed": authority.get("tool_execution_allowed") is True,
        "queue_execution_allowed": authority.get("queue_execution_allowed") is True,
        "runtime_dispatch_allowed": authority.get("runtime_dispatch_allowed") is True,
        "next_safe_move": payload.get("next_safe_move"),
    }


def _summarize_security_delta_review(payload: dict[str, Any]) -> dict[str, Any]:
    examples = payload.get("default_examples") if isinstance(payload.get("default_examples"), list) else []
    repass_categories = sorted(
        {
            str(example.get("change_type"))
            for example in examples
            if isinstance(example, dict) and example.get("decision") == "REQUIRES_SECURITY_REPASS"
        }
    )
    machine = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), dict) else {}
    return {
        "source_path": SECURITY_DELTA_REVIEW_CONTRACT_READ_MODEL_PATH,
        "source_operator_ref": "generated/read_models/security_delta_review_contract_OPERATOR.md",
        "present": bool(payload),
        "primary_app_contract": True,
        "individual_contract_read_model_remains_proof_detail": True,
        "contract_id": payload.get("contract_id", "security_delta_review_contract"),
        "schema_version": payload.get("schema_version"),
        "delta_classes_count": len(payload.get("security_delta_classes", []))
        if isinstance(payload.get("security_delta_classes"), list)
        else 0,
        "decision_outcomes_count": len(payload.get("decision_outcomes", []))
        if isinstance(payload.get("decision_outcomes"), list)
        else 0,
        "default_examples_count": len(examples),
        "repass_required_categories": repass_categories,
        "action_authority_granted": machine.get("action_authority_granted") is True,
        "execution_authority_granted": machine.get("execution_authority_granted") is True,
        "auto_promotion_allowed": machine.get("auto_promotion_allowed") is True,
        "auto_queueing_allowed": machine.get("auto_queueing_allowed") is True,
        "operator_answers_are_not_proof": machine.get("operator_answers_are_not_proof") is True,
        "stable_map_summary_does_not_make_source_truth": True,
        "next_safe_move": "Use this contract when a new item asks for authority beyond an existing approved class.",
    }


def _summarize_operator_attention_promotion(payload: dict[str, Any]) -> dict[str, Any]:
    machine = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), dict) else {}
    shared_paths = payload.get("shared_fix_paths") if isinstance(payload.get("shared_fix_paths"), list) else []
    shared_ids = {
        path.get("shared_fix_path_id")
        for path in shared_paths
        if isinstance(path, dict)
    }
    return {
        "source_path": OPERATOR_ATTENTION_PROMOTION_CONTRACT_READ_MODEL_PATH,
        "source_operator_ref": "generated/read_models/operator_attention_promotion_contract_OPERATOR.md",
        "present": bool(payload),
        "primary_app_contract": True,
        "individual_contract_read_model_remains_proof_detail": True,
        "contract_id": payload.get("contract_id", "operator_attention_promotion_contract"),
        "schema_version": payload.get("schema_version"),
        "promotion_lifecycle_present": bool(payload.get("promotion_lifecycle_states")),
        "promotion_lifecycle_count": len(payload.get("promotion_lifecycle_states", []))
        if isinstance(payload.get("promotion_lifecycle_states"), list)
        else 0,
        "promotion_destinations_count": len(payload.get("promotion_destinations", []))
        if isinstance(payload.get("promotion_destinations"), list)
        else 0,
        "attention_classes_count": len(payload.get("attention_classes", []))
        if isinstance(payload.get("attention_classes"), list)
        else 0,
        "default_records_count": len(payload.get("default_records", []))
        if isinstance(payload.get("default_records"), list)
        else 0,
        "quiet_helm_policy_present": bool(payload.get("quiet_helm_policy")),
        "shared_fix_path_handling_present": "protected_finance_proof_metadata_intake" in shared_ids,
        "cue_candidates_executable": machine.get("cue_candidates_not_executable") is not True,
        "holding_cell_queued": machine.get("holding_cell_items_not_queued") is not True,
        "operator_answers_are_memory_candidates_not_proof": True,
        "new_authority_routes_to_security_delta_or_fail_closed": (
            machine.get("new_authority_routes_to_security_delta_or_fail_closed") is True
        ),
        "action_authority_granted": machine.get("action_authority_granted") is True,
        "auto_promotion_allowed": machine.get("auto_promotion_allowed") is True,
        "next_safe_move": "Use promotion as classification only; route authority requests to Security Delta Review.",
    }


def _summarize_chief_test_harness_cross_off(payload: dict[str, Any]) -> dict[str, Any]:
    machine = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), dict) else {}
    repair_requeue = (
        payload.get("default_repair_requeue_recommendations")
        if isinstance(payload.get("default_repair_requeue_recommendations"), list)
        else []
    )
    quiet_receipts = (
        payload.get("default_quiet_with_proof_receipts")
        if isinstance(payload.get("default_quiet_with_proof_receipts"), list)
        else []
    )
    return {
        "source_path": CHIEF_TEST_HARNESS_CROSS_OFF_RECEIPT_CONTRACT_READ_MODEL_PATH,
        "source_operator_ref": "generated/read_models/chief_test_harness_cross_off_receipt_contract_OPERATOR.md",
        "present": bool(payload),
        "primary_app_contract": True,
        "individual_contract_read_model_remains_proof_detail": True,
        "contract_id": payload.get("contract_id", "chief_test_harness_cross_off_receipt_contract"),
        "schema_version": payload.get("schema_version"),
        "test_harness_receipt_model_present": bool(payload.get("schemas", {}).get("ChiefTestHarnessReceipt"))
        if isinstance(payload.get("schemas"), dict)
        else False,
        "completion_status_count": len(payload.get("completion_statuses", []))
        if isinstance(payload.get("completion_statuses"), list)
        else 0,
        "reconciliation_state_count": len(payload.get("reconciliation_states", []))
        if isinstance(payload.get("reconciliation_states"), list)
        else 0,
        "default_harness_receipts_count": len(payload.get("default_harness_receipts", []))
        if isinstance(payload.get("default_harness_receipts"), list)
        else 0,
        "cross_off_rules_present": bool(payload.get("cross_off_decisions")),
        "source_mutation_allowed": False,
        "delete_source_allowed": False,
        "automatic_cross_off_allowed": machine.get("automatic_cross_off_allowed") is True,
        "repair_requeue_recommendations_metadata_only": bool(repair_requeue)
        and all(item.get("can_run_unattended") is False for item in repair_requeue if isinstance(item, dict)),
        "quiet_with_proof_model_present": bool(quiet_receipts),
        "action_authority_granted": machine.get("action_authority_granted") is True,
        "chief_self_authorization_allowed": machine.get("chief_self_authorization_allowed") is True,
        "chief_repair_execution_allowed": machine.get("chief_repair_execution_allowed") is True,
        "new_authority_routes_to_security_delta": machine.get("new_authority_routes_to_security_delta") is True,
        "next_safe_move": "Use Chief receipts to quiet, requeue, park, or quarantine with proof; do not mutate source notes.",
    }


def _safe_portrait_asset_ref(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "approved_asset_needed_before_render": value.get("approved_asset_needed_before_render", True),
        "image_embedded": False,
        "raw_image_body_stored": False,
        "repo_asset_path": value.get("repo_asset_path"),
        "source_note": value.get("source_note"),
    }


def _safe_dossier_card(card: dict[str, Any]) -> dict[str, Any]:
    safe_card = {field: card.get(field) for field in AGENT_DOSSIER_CARD_FIELDS}
    safe_card["portrait_asset_ref"] = _safe_portrait_asset_ref(card.get("portrait_asset_ref"))
    safe_card["portrait_raw_image_stored"] = False
    safe_card["live_activation_allowed"] = False
    safe_card["raw_private_context_allowed"] = False
    return safe_card


def _unique_limited(values: list[Any], *, limit: int) -> list[Any]:
    seen: set[str] = set()
    unique: list[Any] = []
    for value in values:
        marker = stable_json(value) if isinstance(value, (dict, list)) else str(value)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(value)
        if len(unique) >= limit:
            break
    return unique


def _summarize_agent_council(payload: dict[str, Any]) -> dict[str, Any]:
    raw_cards = payload.get("agent_dossier_cards") if isinstance(payload.get("agent_dossier_cards"), list) else []
    cards = [_safe_dossier_card(card) for card in raw_cards if isinstance(card, dict)]
    cards_by_id = {card.get("agent_id"): card for card in cards}
    summary = (
        payload.get("agent_council_dossier_summary", {})
        if isinstance(payload.get("agent_council_dossier_summary"), dict)
        else {}
    )
    featured_agents = (
        summary.get("featured_agents")
        if isinstance(summary.get("featured_agents"), list)
        else [agent_id for agent_id in FEATURED_AGENT_CARD_IDS if agent_id in cards_by_id]
    )
    system_component_cards = (
        summary.get("system_component_cards")
        if isinstance(summary.get("system_component_cards"), list)
        else [agent_id for agent_id in SYSTEM_LOOP_CARD_IDS if agent_id in cards_by_id]
    )
    top_missing_proof_items = _unique_limited(
        [
            item
            for card in cards
            for item in (
                card.get("not_discovered")
                if isinstance(card.get("not_discovered"), list)
                else []
            )
        ],
        limit=8,
    )
    next_operator_questions = [
        question
        for card in cards
        for question in (
            card.get("operator_questions")
            if isinstance(card.get("operator_questions"), list)
            else []
        )
    ]
    future_gated_cards_count = sum(
        1
        for card in cards
        if card.get("live_activation_allowed") is False
        and (
            bool(card.get("future_eligible_actions"))
            or card.get("package_preview_available") is True
            or (isinstance(card.get("lane_destiny"), dict) and bool(card["lane_destiny"].get("resolution_route")))
        )
    )
    return {
        "source_path": AGENT_TERRAIN_READ_MODEL_PATH,
        "present": bool(payload),
        "preview_only": True,
        "readback_only": True,
        "live_agent_activation_allowed": False,
        "live_chat_launch_allowed": False,
        "model_launch_allowed": False,
        "tool_execution_allowed": False,
        "raw_private_context_included": False,
        "image_body_embedded": False,
        "agent_dossier_cards_count": len(cards),
        "agent_dossier_cards": cards,
        "featured_agents": featured_agents,
        "system_component_cards": system_component_cards,
        "future_gated_cards_count": future_gated_cards_count,
        "top_missing_proof_items": top_missing_proof_items,
        "next_operator_questions_count": len(next_operator_questions),
        "allowed_interactions": summary.get("allowed_interactions", []),
        "forbidden_interactions": summary.get("forbidden_interactions", []),
        "mission_control_may_render": summary.get("mission_control_may_render", []),
        "cassandra_card_present": "cassandra" in cards_by_id,
        "system_loop_cards_present": all(agent_id in cards_by_id for agent_id in SYSTEM_LOOP_CARD_IDS),
        "agent_persona_cards_present": all(agent_id in cards_by_id for agent_id in FEATURED_AGENT_CARD_IDS),
        "cassandra_visual_archetype": (
            cards_by_id.get("cassandra", {}).get("visual_archetype") if cards_by_id else None
        ),
        "cassandra_portrait_asset_status": (
            cards_by_id.get("cassandra", {}).get("portrait_asset_status") if cards_by_id else None
        ),
        "cassandra_image_body_embedded": False,
        "primary_app_contract": True,
        "individual_terrain_read_model_remains_proof_detail": True,
    }


def _path_exists(path: str | Path) -> bool:
    try:
        return Path(path).exists()
    except OSError:
        return False


def _read_marker_summary(path: Path) -> dict[str, Any]:
    payload = _read_json_if_present(path)
    return {
        "path": path.as_posix(),
        "present": path.is_file(),
        "generated_at": payload.get("generated_at"),
        "status": payload.get("status"),
        "backend_head": payload.get("backend_head"),
        "copied_file_count": payload.get("copied_file_count"),
        "next_expected_responder": payload.get("next_expected_responder"),
        "reason": payload.get("reason"),
        "missing_expected_files": payload.get("missing_expected_files", []),
        "hash_mismatch_files": payload.get("hash_mismatch_files", []),
    }


def build_path_audit(
    *,
    repo_root: str | Path = ROOT,
    pc_transfer_root: str | Path = DEFAULT_PC_TRANSFER_ROOT,
) -> dict[str, Any]:
    repo = Path(repo_root)
    transfer = Path(pc_transfer_root)
    manifest_path = transfer / "mac_generated_read_models_manifest.json"
    request_marker = transfer / "shuttle" / "to_mac" / "read_model_sync_required.json"
    completion_marker = transfer / "shuttle" / "from_mac" / "read_model_sync_completed.json"
    pc_import_state = repo / ".openclaw" / "state" / "read_model_import_agent_state.json"
    pc_import_manifest = repo / "import_manifests" / "mac_generated_read_models_manifest.json"
    sync_health = _read_json_if_present(repo / "generated" / "read_models" / "sync_health.json")
    manifest = _read_json_if_present(manifest_path)
    path_records = manifest.get("path_records") if isinstance(manifest.get("path_records"), list) else []
    manifest_names = {
        record.get("relative_path")
        for record in path_records
        if isinstance(record, dict) and isinstance(record.get("relative_path"), str)
    }
    threshold_files = {
        "operator_threshold_map_contract.json",
        "operator_threshold_map_contract_OPERATOR.md",
    }
    threshold_missing_from_manifest = sorted(threshold_files - manifest_names)
    if threshold_missing_from_manifest:
        break_classification = "mac_manifest_missing_threshold_files"
        break_reason = "The returned Mac manifest does not yet include the threshold map files."
    elif sync_health.get("missing_expected") or sync_health.get("hash_mismatch"):
        break_classification = "pc_proof_or_hash_readback_stale_after_manifest"
        break_reason = "The returned Mac manifest has the threshold files, but PC sync health still sees missing or hash-mismatched canonical files."
    else:
        break_classification = "prior_churn_resolved_for_threshold_files"
        break_reason = "The current returned Mac manifest includes the threshold files and no threshold-file absence is visible."
    return {
        "repo_a_generated_read_model_source_path": (repo / "generated" / "read_models").as_posix(),
        "canonical_manifest_path": manifest_path.as_posix(),
        "e_drive_shuttle_export_path": (transfer / "shuttle" / "to_mac").as_posix(),
        "mac_expected_mount_path": DEFAULT_MAC_MOUNT_PATH,
        "mac_local_mirror_path": DEFAULT_MAC_LOCAL_MAP_ROOT,
        "sync_request_marker_path": request_marker.as_posix(),
        "mac_completion_receipt_marker_path": completion_marker.as_posix(),
        "pc_import_readback_receipt_path": pc_import_state.as_posix(),
        "pc_import_manifest_copy_path": pc_import_manifest.as_posix(),
        "pc_transfer_root_present": transfer.is_dir(),
        "returned_manifest_present": manifest_path.is_file(),
        "returned_manifest_path_record_count": len(path_records),
        "returned_manifest_absolute_root": manifest.get("absolute_root"),
        "returned_manifest_points_to_expected_mac_root": manifest.get("absolute_root")
        == DEFAULT_MAC_LOCAL_MAP_ROOT,
        "threshold_files_missing_from_returned_manifest": threshold_missing_from_manifest,
        "threshold_break_classification": break_classification,
        "threshold_break_reason": break_reason,
        "request_marker": _read_marker_summary(request_marker),
        "completion_marker": _read_marker_summary(completion_marker),
        "sync_health_summary": _summarize_sync_health(sync_health),
        "raw_private_body_read": False,
        "repair_attempted": False,
    }


def build_openclaw_map_snapshot(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    sync_health = _read_json_if_present("generated/read_models/sync_health.json", repo_root=repo_root)
    health_lights = _read_json_if_present(
        "generated/read_models/system_health_lights_taxonomy.json",
        repo_root=repo_root,
    )
    threshold = _read_json_if_present(
        "generated/read_models/operator_threshold_map_contract.json",
        repo_root=repo_root,
    )
    mission = _read_json_if_present(
        "generated/read_models/operator_mission_priority_helm_declutter.json",
        repo_root=repo_root,
    )
    worlds = _read_json_if_present("generated/read_models/world_domain_registry.json", repo_root=repo_root)
    package_compiler = _read_json_if_present(
        "generated/read_models/package_compiler_contract.json",
        repo_root=repo_root,
    )
    package_preview_receipt = _read_json_if_present(
        PACKAGE_PREVIEW_RECEIPT_READ_MODEL_PATH,
        repo_root=repo_root,
    )
    tool_adapter_receipt = _read_json_if_present(
        TOOL_ADAPTER_RECEIPT_READ_MODEL_PATH,
        repo_root=repo_root,
    )
    capital_hilton_proof_metadata = _read_json_if_present(
        CAPITAL_HILTON_PROOF_METADATA_READ_MODEL_PATH,
        repo_root=repo_root,
    )
    security_audit_readiness = _read_json_if_present(
        SECURITY_AUDIT_READINESS_READ_MODEL_PATH,
        repo_root=repo_root,
    )
    security_pass = _read_json_if_present(
        SECURITY_PASS_CONTRACT_READ_MODEL_PATH,
        repo_root=repo_root,
    )
    post_security_governance_batch = _read_json_if_present(
        POST_SECURITY_GOVERNANCE_BATCH_MANIFEST_READ_MODEL_PATH,
        repo_root=repo_root,
    )
    parked_capital_experiment = _read_json_if_present(
        PARKED_AUTONOMOUS_CAPITAL_PIPELINE_EXPERIMENT_READ_MODEL_PATH,
        repo_root=repo_root,
    )
    security_delta_review = _read_json_if_present(
        SECURITY_DELTA_REVIEW_CONTRACT_READ_MODEL_PATH,
        repo_root=repo_root,
    )
    operator_attention_promotion = _read_json_if_present(
        OPERATOR_ATTENTION_PROMOTION_CONTRACT_READ_MODEL_PATH,
        repo_root=repo_root,
    )
    chief_test_harness_cross_off = _read_json_if_present(
        CHIEF_TEST_HARNESS_CROSS_OFF_RECEIPT_CONTRACT_READ_MODEL_PATH,
        repo_root=repo_root,
    )
    terrain_awareness = _read_json_if_present(AGENT_TERRAIN_READ_MODEL_PATH, repo_root=repo_root)
    snapshot: dict[str, Any] = {
        "schema_version": MAP_SNAPSHOT_SCHEMA_VERSION,
        "read_model_id": "openclaw_map_snapshot",
        "created_at": generated_at,
        "map_generation_id": None,
        "source_repo": "Repo A /home/openclaw",
        "source_commit_if_available_local_only": _local_git_head(repo_root),
        "mission_control_front_door_contract": {
            "app_should_read_stable_map_bundle": True,
            "stable_app_facing_files": list(STABLE_APP_FACING_FILES),
            "raw_individual_read_models_are_proof_detail": True,
            "new_raw_read_model_files_do_not_require_new_app_paths": True,
        },
        "health_state": _summarize_health_lights(health_lights),
        "sync_state": _summarize_sync_health(sync_health),
        "current_mission": _summarize_mission(mission),
        "threshold_map": _summarize_threshold(threshold),
        "agent_council": _summarize_agent_council(terrain_awareness),
        "worlds": _summarize_worlds(worlds),
        "package_previews": _summarize_package_compiler(package_compiler),
        "package_preview_receipts": _summarize_package_preview_receipts(package_preview_receipt),
        "tool_adapter_receipts": _summarize_tool_adapter_receipts(tool_adapter_receipt),
        "capital_hilton_proof_metadata": _summarize_capital_hilton_proof_metadata(
            capital_hilton_proof_metadata
        ),
        "security_audit_readiness": _summarize_security_audit_readiness(security_audit_readiness),
        "security_pass": _summarize_security_pass(security_pass),
        "post_security_governance_batch": _summarize_post_security_governance_batch(
            post_security_governance_batch
        ),
        "parked_autonomous_capital_pipeline_experiment": _summarize_parked_autonomous_capital_pipeline_experiment(
            parked_capital_experiment
        ),
        "security_delta_review": _summarize_security_delta_review(security_delta_review),
        "operator_attention_promotion": _summarize_operator_attention_promotion(
            operator_attention_promotion
        ),
        "chief_test_harness_cross_off": _summarize_chief_test_harness_cross_off(
            chief_test_harness_cross_off
        ),
        "proof_references": {
            "policy": "proof references point to read-model paths and receipts; raw private bodies are not embedded",
            "essential_surfaces": _essential_surface_records(repo_root),
        },
        "missing_proof": {
            "from_threshold_map": [
                {
                    "lane_id": lane.get("lane_id"),
                    "missing_proof": lane.get("missing_proof", []),
                }
                for lane in (
                    threshold.get("lane_inventory")
                    if isinstance(threshold.get("lane_inventory"), list)
                    else []
                )
                if isinstance(lane, dict) and lane.get("missing_proof")
            ],
        },
        "receipts": {
            "map_receipt_expected": True,
            "mac_receipt_schema_version": MAP_RECEIPT_SCHEMA_VERSION,
            "current_pc_observed_receipt_status": "not_checked_by_snapshot",
        },
        "source_conflicts": {
            "check_transmission_source_truth": (
                threshold.get("check_transmission_source_truth_note", {})
                if isinstance(threshold.get("check_transmission_source_truth_note"), dict)
                else {}
            )
        },
        "authority_boundary": {
            "package_preview_allowed": True,
            "live_package_dispatch_allowed": False,
            "model_actor_execution_allowed": False,
            "agent_activation_allowed": False,
            "plugin_tool_execution_allowed": False,
            "send_submit_approval_allowed": False,
            "runtime_activation_allowed": False,
            "autonomy_queue_allowed": False,
            "future_gated_cue_autonomy": True,
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        },
        "raw_private_bodies_included": False,
        "credentials_included": False,
        "secrets_included": False,
    }
    snapshot_hash = _content_hash(snapshot)
    snapshot["snapshot_hash"] = snapshot_hash
    snapshot["map_generation_id"] = f"map_{snapshot_hash.removeprefix('sha256:')[:20]}"
    return snapshot


def build_openclaw_map_manifest(
    *,
    snapshot: dict[str, Any],
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    records = _read_model_records(repo_root)
    source_records = [
        record
        for record in records
        if record["relative_path"] not in MAP_BUNDLE_HASH_EXCLUDED_FILES
    ]
    snapshot_hash = _content_hash(snapshot)
    map_generation_id = snapshot.get("map_generation_id") or f"map_{snapshot_hash.removeprefix('sha256:')[:20]}"
    manifest_core = {
        "schema_version": MAP_MANIFEST_SCHEMA_VERSION,
        "read_model_id": "openclaw_map_manifest",
        "created_at": generated_at,
        "map_generation_id": map_generation_id,
        "source_repo": "Repo A /home/openclaw",
        "source_commit_if_available_local_only": _local_git_head(repo_root),
        "source_sqlite_receipt_hash_if_available": None,
        "source_sqlite_receipt_hash_note": "PC SQLite remains canonical terrain; map v0 does not hash live SQLite.",
        "read_model_manifest_hash": _manifest_hash_for_records(records),
        "canonical_read_model_count": len(source_records),
        "manifest_hash_excludes_files": sorted(MAP_BUNDLE_HASH_EXCLUDED_FILES),
        "raw_generated_read_model_file_count_including_map_bundle_self": len(records),
        "source_read_model_count_excluding_map_bundle_self_and_sync_health_self_report": len(source_records),
        "essential_surface_count": len(ESSENTIAL_SURFACES),
        "snapshot_hash": snapshot_hash,
        "bundle_hash": None,
        "included_surfaces": _essential_surface_records(repo_root),
        "excluded_surfaces": [
            {
                "category": "raw_private_bodies",
                "reason": "raw private content is never embedded in the stable map bundle",
            },
            {
                "category": "credentials_or_secrets",
                "reason": "credentials and secrets are never embedded in the stable map bundle",
            },
            {
                "category": "raw_generated_read_model_wall",
                "reason": "individual generated read-models remain proof/detail, not app front-door dependencies",
            },
        ],
        "missing_or_stale_surfaces": [
            surface
            for surface in _essential_surface_records(repo_root)
            if not surface["present"]
        ],
        "proof_reference_policy": "Map snapshot stores summaries and read-model references, not raw proof bodies.",
        "raw_private_body_policy": "blocked_excluded_from_bundle",
        "authority_boundary": dict(NO_AUTHORITY_FLAGS),
        "stable_app_facing_paths": {
            "mac_local_snapshot": f"{DEFAULT_MAC_LOCAL_MAP_ROOT}/{MAP_SNAPSHOT_EXPORT_NAME}",
            "mac_local_manifest": f"{DEFAULT_MAC_LOCAL_MAP_ROOT}/{MAP_MANIFEST_EXPORT_NAME}",
            "mac_local_operator_digest": f"{DEFAULT_MAC_LOCAL_MAP_ROOT}/{MAP_OPERATOR_EXPORT_NAME}",
            "mac_local_receipt": f"{DEFAULT_MAC_LOCAL_MAP_ROOT}/openclaw_map_receipt.json",
        },
    }
    manifest_core["bundle_hash"] = _content_hash(
        {
            "manifest": manifest_core,
            "snapshot": snapshot,
        }
    )
    return manifest_core


def validate_map_receipt(
    receipt: dict[str, Any] | None,
    *,
    expected_generation_id: str,
    expected_bundle_hash: str,
) -> dict[str, Any]:
    if not receipt:
        return {
            "status": "map_missing_from_mac",
            "valid": False,
            "fail_closed": True,
            "reason": "Mac map import receipt is missing.",
        }
    missing_files = receipt.get("missing_files") if isinstance(receipt.get("missing_files"), list) else []
    hash_mismatch = receipt.get("hash_mismatch") if isinstance(receipt.get("hash_mismatch"), list) else []
    if receipt.get("schema_version") != MAP_RECEIPT_SCHEMA_VERSION:
        return {
            "status": "unknown_fail_closed",
            "valid": False,
            "fail_closed": True,
            "reason": "Mac map receipt schema is not recognized.",
        }
    if receipt.get("map_generation_id") != expected_generation_id:
        return {
            "status": "map_generation_pending_mac_import",
            "valid": False,
            "fail_closed": True,
            "reason": "Mac map receipt generation_id does not match the requested generation.",
        }
    if receipt.get("bundle_hash") != expected_bundle_hash:
        return {
            "status": "map_hash_mismatch",
            "valid": False,
            "fail_closed": True,
            "reason": "Mac map receipt bundle_hash does not match the requested bundle.",
        }
    if missing_files or hash_mismatch or receipt.get("parse_passed") is not True:
        return {
            "status": "map_hash_mismatch",
            "valid": False,
            "fail_closed": True,
            "reason": "Mac map receipt reports parse, missing-file, or hash mismatch failure.",
            "missing_files": missing_files,
            "hash_mismatch": hash_mismatch,
        }
    return {
        "status": "map_current",
        "valid": True,
        "fail_closed": False,
        "reason": "Mac map receipt matches generation_id and bundle_hash.",
    }


def build_operator_map_bundle_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
    pc_transfer_root: str | Path = DEFAULT_PC_TRANSFER_ROOT,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    snapshot = build_openclaw_map_snapshot(repo_root=repo_root, generated_at=generated_at)
    manifest = build_openclaw_map_manifest(
        snapshot=snapshot,
        repo_root=repo_root,
        generated_at=generated_at,
    )
    receipt_path = Path(pc_transfer_root) / "shuttle" / "from_mac" / "openclaw_map_receipt.json"
    receipt = _read_json_if_present(receipt_path)
    receipt_validation = validate_map_receipt(
        receipt if receipt else None,
        expected_generation_id=str(manifest["map_generation_id"]),
        expected_bundle_hash=str(manifest["bundle_hash"]),
    )
    contract: dict[str, Any] = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "read_model_id": "operator_map_bundle_contract",
        "generated_at": generated_at,
        "contract_status": "stable_map_bundle_sync_contract_metadata_only",
        "problem_statement": "Raw generated read-model file counts are too volatile to be the Mission Control front-door app contract.",
        "strategic_correction": {
            "pc_wsl_owns_terrain": True,
            "mac_mission_control_consumes_stable_map_snapshot": True,
            "raw_read_models_remain_available_as_proof_detail": True,
            "not_a_one_off_file_copy": True,
            "not_a_ui_task": True,
            "not_a_live_execution_lane": True,
        },
        "path_audit": build_path_audit(repo_root=repo_root, pc_transfer_root=pc_transfer_root),
        "stable_artifacts": {
            "openclaw_map_manifest": {
                "file_name": MAP_MANIFEST_EXPORT_NAME,
                "schema_version": MAP_MANIFEST_SCHEMA_VERSION,
                "purpose": "stable generation, hash, included-surface, and authority manifest",
            },
            "openclaw_map_snapshot": {
                "file_name": MAP_SNAPSHOT_EXPORT_NAME,
                "schema_version": MAP_SNAPSHOT_SCHEMA_VERSION,
                "purpose": "Mission Control front-door system map snapshot",
            },
            "openclaw_map_operator_digest": {
                "file_name": MAP_OPERATOR_EXPORT_NAME,
                "purpose": "human-readable map digest",
            },
            "openclaw_map_receipt": {
                "file_name": "openclaw_map_receipt.json",
                "schema_version": MAP_RECEIPT_SCHEMA_VERSION,
                "purpose": "Mac import/readback receipt written by the Mac-side map importer later",
                "generated_by_pc_now": False,
            },
        },
        "stable_app_facing_file_set": list(STABLE_APP_FACING_FILES),
        "app_facing_paths_do_not_change_when_new_raw_read_model_added": True,
        "map_manifest": manifest,
        "map_snapshot_summary": {
            "map_generation_id": snapshot["map_generation_id"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "health_state": snapshot["health_state"],
            "threshold_capital_hilton": snapshot["threshold_map"]["capital_hilton_finance_destiny"],
            "threshold_system_awareness": snapshot["threshold_map"]["system_awareness_discovery_steel_thread"],
            "agent_dossier_cards_count": snapshot["agent_council"]["agent_dossier_cards_count"],
            "featured_agents": snapshot["agent_council"]["featured_agents"],
            "agent_council_preview_only": snapshot["agent_council"]["preview_only"],
            "package_preview_receipt_examples_count": snapshot["package_preview_receipts"]["example_package_previews_count"],
            "tool_adapter_receipt_examples_count": snapshot["tool_adapter_receipts"]["adapter_examples_count"],
            "capital_hilton_proof_metadata_present": snapshot["capital_hilton_proof_metadata"]["present"],
            "capital_hilton_missing_proof_count": snapshot["capital_hilton_proof_metadata"]["missing_proof_count"],
            "capital_hilton_protected_proof_required": snapshot["capital_hilton_proof_metadata"]["protected_proof_required"],
            "security_audit_readiness_present": snapshot["security_audit_readiness"]["present"],
            "security_ready_for_pass": snapshot["security_audit_readiness"]["ready_for_security_pass"],
            "security_approval_granted": snapshot["security_audit_readiness"]["security_approval_granted"],
            "security_action_authority_granted": snapshot["security_audit_readiness"]["action_authority_granted"],
            "security_coverage_gap_records": snapshot["security_audit_readiness"]["coverage_gap_summary"]["coverage_gap_records_count"],
            "security_parked_breadcrumb_count": snapshot["security_audit_readiness"]["parked_breadcrumb_summary"]["parked_breadcrumb_count"],
            "security_pass_present": snapshot["security_pass"]["present"],
            "security_pass_completed": snapshot["security_pass"]["security_pass_completed"],
            "security_pass_action_authority_granted": snapshot["security_pass"]["action_authority_granted"],
            "security_pass_worker_output_intake_metadata_approved": snapshot["security_pass"]["worker_output_intake_metadata_approved"],
            "security_pass_orphaned_capability_detection_approved": snapshot["security_pass"]["orphaned_capability_detection_approved"],
            "security_pass_chief_reconciliation_metadata_approved": snapshot["security_pass"]["chief_reconciliation_metadata_approved"],
            "security_pass_hermes_architecture_review_metadata_approved": snapshot["security_pass"]["hermes_architecture_review_metadata_approved"],
            "security_pass_trust_clearance_modeling_approved": snapshot["security_pass"]["trust_clearance_modeling_approved"],
            "post_security_governance_batch_present": snapshot["post_security_governance_batch"]["present"],
            "post_security_governance_batch_status": snapshot["post_security_governance_batch"]["batch_status"],
            "parked_capital_experiment_present": snapshot["parked_autonomous_capital_pipeline_experiment"]["present"],
            "parked_capital_experiment_status": snapshot["parked_autonomous_capital_pipeline_experiment"]["status"],
            "security_delta_review_present": snapshot["security_delta_review"]["present"],
            "security_delta_review_default_examples_count": snapshot["security_delta_review"]["default_examples_count"],
            "operator_attention_promotion_present": snapshot["operator_attention_promotion"]["present"],
            "operator_attention_promotion_quiet_helm_policy_present": snapshot["operator_attention_promotion"]["quiet_helm_policy_present"],
            "chief_test_harness_cross_off_present": snapshot["chief_test_harness_cross_off"]["present"],
            "chief_test_harness_cross_off_source_mutation_allowed": snapshot["chief_test_harness_cross_off"]["source_mutation_allowed"],
            "future_gated_cue_autonomy": snapshot["authority_boundary"]["future_gated_cue_autonomy"],
        },
        "atomic_sync_lifecycle": {
            "pc_steps": [
                "generate openclaw_map_snapshot.json",
                "generate openclaw_map_manifest.json",
                "hash the stable bundle",
                "write bundle to a generation folder under /mnt/e/openclaw/shuttle/to_mac/map_bundle/<generation_id>",
                "write openclaw_map_sync_required.json with generation_id and bundle_hash",
            ],
            "mac_steps": [
                "read map_sync_required.json",
                "import bundle into a temporary local generation path",
                "verify hash and parse stable JSON files",
                "atomically promote to current stable map files",
                "write map_sync_completed.json and openclaw_map_receipt.json",
            ],
            "pc_readback_steps": [
                "import Mac receipt",
                "compare generation_id and bundle_hash",
                "update sync_health map-bundle fields",
            ],
            "mission_control_steps": [
                "read current local openclaw_map_snapshot.json",
                "fail closed if missing",
                "show map sync pending if generation is stale",
                "render map when receipt/current proof agrees",
            ],
            "lifecycle_paths": {
                "pc_generation_root": "/mnt/e/openclaw/shuttle/to_mac/map_bundle/<generation_id>",
                "pc_request_marker": "/mnt/e/openclaw/shuttle/to_mac/openclaw_map_sync_required.json",
                "mac_completion_marker": "/mnt/e/openclaw/shuttle/from_mac/map_sync_completed.json",
                "pc_receipt_readback": "/mnt/e/openclaw/shuttle/from_mac/openclaw_map_receipt.json",
            },
        },
        "sync_health_reframe": {
            "raw_read_model_manifest_status": "continues to compare full generated/read_models proof/detail set",
            "map_bundle_generation_status": "new front-door app contract status",
            "mac_import_receipt_status": receipt_validation["status"],
            "app_visible_map_status": "map_current only when generation_id and bundle_hash receipt validates",
            "required_states": [
                "map_current",
                "map_generation_pending_mac_import",
                "map_imported_waiting_pc_readback",
                "map_hash_mismatch",
                "map_missing_from_mac",
                "mount_missing",
                "unknown_fail_closed",
            ],
            "check_transmission_future_source_truth": "controlled by map-generation agreement for app readiness, with raw count mismatch kept as proof/detail unless it blocks map generation",
        },
        "threshold_map_integration": {
            "threshold_map_included_in_snapshot": bool(snapshot["threshold_map"].get("present")),
            "capital_hilton_finance_destiny_included": snapshot["threshold_map"]["capital_hilton_finance_destiny"].get("target_world") == "Finance",
            "system_awareness_discovery_steel_thread_included": snapshot["threshold_map"]["system_awareness_discovery_steel_thread"].get("lane_id") == "system_awareness_discovery",
            "cue_autonomy_future_gated": snapshot["authority_boundary"]["future_gated_cue_autonomy"] is True,
            "individual_threshold_read_models_remain_proof_detail": True,
        },
        "agent_council_integration": {
            "agent_dossier_cards_included_in_snapshot": snapshot["agent_council"]["agent_dossier_cards_count"] > 0,
            "agent_dossier_cards_count": snapshot["agent_council"]["agent_dossier_cards_count"],
            "featured_agents": snapshot["agent_council"]["featured_agents"],
            "system_loop_cards_present": snapshot["agent_council"]["system_loop_cards_present"],
            "cassandra_card_present": snapshot["agent_council"]["cassandra_card_present"],
            "preview_only": snapshot["agent_council"]["preview_only"],
            "live_agent_activation_allowed": snapshot["agent_council"]["live_agent_activation_allowed"],
            "live_chat_launch_allowed": snapshot["agent_council"]["live_chat_launch_allowed"],
            "model_launch_allowed": snapshot["agent_council"]["model_launch_allowed"],
            "tool_execution_allowed": snapshot["agent_council"]["tool_execution_allowed"],
            "individual_terrain_read_model_remains_proof_detail": True,
        },
        "package_preview_receipt_integration": {
            "summary_included_in_snapshot": snapshot["package_preview_receipts"]["present"],
            "example_package_previews_count": snapshot["package_preview_receipts"]["example_package_previews_count"],
            "dispatch_authority_allowed": snapshot["package_preview_receipts"]["dispatch_authority_allowed"],
            "model_call_allowed": snapshot["package_preview_receipts"]["model_call_allowed"],
            "tool_execution_allowed": snapshot["package_preview_receipts"]["tool_execution_allowed"],
            "agent_activation_allowed": snapshot["package_preview_receipts"]["agent_activation_allowed"],
            "queue_execution_allowed": snapshot["package_preview_receipts"]["queue_execution_allowed"],
            "account_access_allowed": snapshot["package_preview_receipts"]["account_access_allowed"],
            "send_submit_approval_allowed": snapshot["package_preview_receipts"]["send_submit_approval_allowed"],
            "individual_contract_read_model_remains_proof_detail": True,
        },
        "tool_adapter_receipt_integration": {
            "summary_included_in_snapshot": snapshot["tool_adapter_receipts"]["present"],
            "adapter_examples_count": snapshot["tool_adapter_receipts"]["adapter_examples_count"],
            "allowed_read_only_count": snapshot["tool_adapter_receipts"]["allowed_read_only_count"],
            "preview_or_receipt_only_count": snapshot["tool_adapter_receipts"]["preview_or_receipt_only_count"],
            "blocked_or_future_gated_count": snapshot["tool_adapter_receipts"]["blocked_or_future_gated_count"],
            "live_tool_execution_allowed": snapshot["tool_adapter_receipts"]["live_tool_execution_allowed"],
            "network_allowed": snapshot["tool_adapter_receipts"]["network_allowed"],
            "account_access_allowed": snapshot["tool_adapter_receipts"]["account_access_allowed"],
            "browser_session_allowed": snapshot["tool_adapter_receipts"]["browser_session_allowed"],
            "send_submit_approval_allowed": snapshot["tool_adapter_receipts"]["send_submit_approval_allowed"],
            "command_execution_allowed": snapshot["tool_adapter_receipts"]["command_execution_allowed"],
            "individual_contract_read_model_remains_proof_detail": True,
        },
        "capital_hilton_proof_metadata_integration": {
            "summary_included_in_snapshot": snapshot["capital_hilton_proof_metadata"]["present"],
            "current_phase": snapshot["capital_hilton_proof_metadata"]["current_phase"],
            "target_world": snapshot["capital_hilton_proof_metadata"]["target_world"],
            "lane_destiny": snapshot["capital_hilton_proof_metadata"]["lane_destiny"],
            "missing_proof_count": snapshot["capital_hilton_proof_metadata"]["missing_proof_count"],
            "protected_proof_required": snapshot["capital_hilton_proof_metadata"]["protected_proof_required"],
            "candidate_facts_count": len(snapshot["capital_hilton_proof_metadata"]["candidate_facts"]),
            "all_candidate_facts_marked_not_proven": snapshot["capital_hilton_proof_metadata"]["all_candidate_facts_marked_not_proven"],
            "live_execution_authority": snapshot["capital_hilton_proof_metadata"]["live_execution_authority"],
            "individual_contract_read_model_remains_proof_detail": True,
        },
        "security_audit_readiness_integration": {
            "summary_included_in_snapshot": snapshot["security_audit_readiness"]["present"],
            "schema_version": snapshot["security_audit_readiness"]["schema_version"],
            "ready_for_security_pass": snapshot["security_audit_readiness"]["ready_for_security_pass"],
            "security_approval_granted": snapshot["security_audit_readiness"]["security_approval_granted"],
            "action_authority_granted": snapshot["security_audit_readiness"]["action_authority_granted"],
            "coverage_gap_records_count": snapshot["security_audit_readiness"]["coverage_gap_summary"]["coverage_gap_records_count"],
            "parked_breadcrumb_count": snapshot["security_audit_readiness"]["parked_breadcrumb_summary"]["parked_breadcrumb_count"],
            "capital_hilton_security_readiness_present": snapshot["security_audit_readiness"]["capital_hilton_security_readiness_present"],
            "individual_packet_read_model_remains_proof_detail": True,
        },
        "security_pass_integration": {
            "summary_included_in_snapshot": snapshot["security_pass"]["present"],
            "schema_version": snapshot["security_pass"]["schema_version"],
            "security_pass_completed": snapshot["security_pass"]["security_pass_completed"],
            "read_only_surfaces_approved": snapshot["security_pass"]["read_only_surfaces_approved"],
            "preview_surfaces_approved": snapshot["security_pass"]["preview_surfaces_approved"],
            "metadata_only_surfaces_approved": snapshot["security_pass"]["metadata_only_surfaces_approved"],
            "worker_output_intake_metadata_approved": snapshot["security_pass"]["worker_output_intake_metadata_approved"],
            "orphaned_capability_detection_approved": snapshot["security_pass"]["orphaned_capability_detection_approved"],
            "chief_reconciliation_metadata_approved": snapshot["security_pass"]["chief_reconciliation_metadata_approved"],
            "hermes_architecture_review_metadata_approved": snapshot["security_pass"]["hermes_architecture_review_metadata_approved"],
            "trust_clearance_modeling_approved": snapshot["security_pass"]["trust_clearance_modeling_approved"],
            "action_authority_granted": snapshot["security_pass"]["action_authority_granted"],
            "all_live_authority_false": snapshot["security_pass"]["all_live_authority_false"],
            "individual_contract_read_model_remains_proof_detail": True,
        },
        "post_security_governance_batch_integration": {
            "summary_included_in_snapshot": snapshot["post_security_governance_batch"]["present"],
            "batch_id": snapshot["post_security_governance_batch"]["batch_id"],
            "batch_status": snapshot["post_security_governance_batch"]["batch_status"],
            "lane_count": snapshot["post_security_governance_batch"]["lane_count"],
            "completed_lanes": snapshot["post_security_governance_batch"]["completed_lanes"],
            "next_expected_actor": snapshot["post_security_governance_batch"]["next_expected_actor"],
            "all_live_authority_false": snapshot["post_security_governance_batch"]["authority_boundary"]["all_live_authority_false"],
            "individual_manifest_read_model_remains_proof_detail": True,
        },
        "parked_autonomous_capital_pipeline_experiment_integration": {
            "summary_included_in_snapshot": snapshot["parked_autonomous_capital_pipeline_experiment"]["present"],
            "status": snapshot["parked_autonomous_capital_pipeline_experiment"]["status"],
            "phase_count": snapshot["parked_autonomous_capital_pipeline_experiment"]["phase_count"],
            "all_authority_false": snapshot["parked_autonomous_capital_pipeline_experiment"]["all_authority_false"],
            "future_gates_required": snapshot["parked_autonomous_capital_pipeline_experiment"]["future_gates_required"],
            "token_concept_future_only": snapshot["parked_autonomous_capital_pipeline_experiment"]["token_concept_future_only"],
            "stress_test_classification": snapshot["parked_autonomous_capital_pipeline_experiment"]["stress_test_classification"],
            "action_authority_granted": snapshot["parked_autonomous_capital_pipeline_experiment"]["action_authority_granted"],
            "individual_experiment_read_model_remains_proof_detail": True,
        },
        "security_delta_review_integration": {
            "summary_included_in_snapshot": snapshot["security_delta_review"]["present"],
            "delta_classes_count": snapshot["security_delta_review"]["delta_classes_count"],
            "default_examples_count": snapshot["security_delta_review"]["default_examples_count"],
            "repass_required_categories": snapshot["security_delta_review"]["repass_required_categories"],
            "action_authority_granted": snapshot["security_delta_review"]["action_authority_granted"],
            "execution_authority_granted": snapshot["security_delta_review"]["execution_authority_granted"],
            "auto_promotion_allowed": snapshot["security_delta_review"]["auto_promotion_allowed"],
            "auto_queueing_allowed": snapshot["security_delta_review"]["auto_queueing_allowed"],
            "individual_contract_read_model_remains_proof_detail": True,
        },
        "operator_attention_promotion_integration": {
            "summary_included_in_snapshot": snapshot["operator_attention_promotion"]["present"],
            "promotion_lifecycle_present": snapshot["operator_attention_promotion"]["promotion_lifecycle_present"],
            "quiet_helm_policy_present": snapshot["operator_attention_promotion"]["quiet_helm_policy_present"],
            "shared_fix_path_handling_present": snapshot["operator_attention_promotion"]["shared_fix_path_handling_present"],
            "cue_candidates_executable": snapshot["operator_attention_promotion"]["cue_candidates_executable"],
            "holding_cell_queued": snapshot["operator_attention_promotion"]["holding_cell_queued"],
            "action_authority_granted": snapshot["operator_attention_promotion"]["action_authority_granted"],
            "auto_promotion_allowed": snapshot["operator_attention_promotion"]["auto_promotion_allowed"],
            "individual_contract_read_model_remains_proof_detail": True,
        },
        "chief_test_harness_cross_off_integration": {
            "summary_included_in_snapshot": snapshot["chief_test_harness_cross_off"]["present"],
            "test_harness_receipt_model_present": snapshot["chief_test_harness_cross_off"]["test_harness_receipt_model_present"],
            "cross_off_rules_present": snapshot["chief_test_harness_cross_off"]["cross_off_rules_present"],
            "source_mutation_allowed": snapshot["chief_test_harness_cross_off"]["source_mutation_allowed"],
            "delete_source_allowed": snapshot["chief_test_harness_cross_off"]["delete_source_allowed"],
            "repair_requeue_recommendations_metadata_only": snapshot["chief_test_harness_cross_off"]["repair_requeue_recommendations_metadata_only"],
            "quiet_with_proof_model_present": snapshot["chief_test_harness_cross_off"]["quiet_with_proof_model_present"],
            "action_authority_granted": snapshot["chief_test_harness_cross_off"]["action_authority_granted"],
            "individual_contract_read_model_remains_proof_detail": True,
        },
        "sqlite_position": {
            "pc_sqlite_remains_durable_terrain_source": True,
            "mac_reads_immutable_exported_snapshot_not_live_pc_sqlite": True,
            "mac_mutates_sqlite": False,
            "snapshot_format_now": "json",
            "sqlite_snapshot_future_option": "v1 option after the JSON stable bundle is proven",
            "receipt_storage_now": "Mac receipt expected as metadata-only JSON; PC SQLite receipt rows may be added later if existing ledger pattern is explicitly chosen.",
        },
        "mac_side_change_required": {
            "stable_local_paths": {
                "snapshot": f"{DEFAULT_MAC_LOCAL_MAP_ROOT}/{MAP_SNAPSHOT_EXPORT_NAME}",
                "manifest": f"{DEFAULT_MAC_LOCAL_MAP_ROOT}/{MAP_MANIFEST_EXPORT_NAME}",
                "operator_digest": f"{DEFAULT_MAC_LOCAL_MAP_ROOT}/{MAP_OPERATOR_EXPORT_NAME}",
                "receipt": f"{DEFAULT_MAC_LOCAL_MAP_ROOT}/openclaw_map_receipt.json",
            },
            "entitlement_exception_needed_once": list(STABLE_APP_FACING_FILES),
            "loader_behavior": [
                "load openclaw_map_manifest.json first",
                "load and parse openclaw_map_snapshot.json",
                "verify manifest snapshot_hash when available",
                "render map from snapshot summaries",
                "treat individual read-model files as drill-in proof only",
            ],
            "fallback_behavior": [
                "if snapshot missing, show fail-closed map unavailable",
                "if manifest generation stale, show map sync pending",
                "if receipt/hash mismatch, show Check Transmission map warning",
                "do not fall back to claiming raw terrain absence just because a new proof-detail read-model was added",
            ],
            "no_per_new_file_entitlement_churn": True,
        },
        "receipt_validation": receipt_validation,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
    }
    contract["contract_hash"] = _content_hash(contract)
    return contract


def format_openclaw_map_operator(snapshot: dict[str, Any], manifest: dict[str, Any]) -> str:
    threshold = snapshot["threshold_map"]
    sync = snapshot["sync_state"]
    health = snapshot["health_state"]
    agent_council = snapshot.get("agent_council", {})
    package_receipts = snapshot.get("package_preview_receipts", {})
    tool_receipts = snapshot.get("tool_adapter_receipts", {})
    capital_hilton = snapshot.get("capital_hilton_proof_metadata", {})
    security = snapshot.get("security_audit_readiness", {})
    provenance = (
        security.get("map_to_terrain_provenance_summary", {})
        if isinstance(security.get("map_to_terrain_provenance_summary"), dict)
        else {}
    )
    answer_capture = (
        security.get("operator_answer_capture_summary", {})
        if isinstance(security.get("operator_answer_capture_summary"), dict)
        else {}
    )
    shared_paths = (
        security.get("shared_execution_path_summary", {})
        if isinstance(security.get("shared_execution_path_summary"), dict)
        else {}
    )
    focus_mode = (
        security.get("helm_issue_focus_mode_summary", {})
        if isinstance(security.get("helm_issue_focus_mode_summary"), dict)
        else {}
    )
    coverage_gap = (
        security.get("coverage_gap_summary", {})
        if isinstance(security.get("coverage_gap_summary"), dict)
        else {}
    )
    parked = (
        security.get("parked_breadcrumb_summary", {})
        if isinstance(security.get("parked_breadcrumb_summary"), dict)
        else {}
    )
    capital_security = (
        security.get("capital_hilton_security_readiness_summary", {})
        if isinstance(security.get("capital_hilton_security_readiness_summary"), dict)
        else {}
    )
    security_pass = (
        snapshot.get("security_pass", {})
        if isinstance(snapshot.get("security_pass"), dict)
        else {}
    )
    security_pass_capital = (
        security_pass.get("capital_hilton_security_pass_decision_summary", {})
        if isinstance(security_pass.get("capital_hilton_security_pass_decision_summary"), dict)
        else {}
    )
    security_pass_markdown = (
        security_pass.get("markdown_terrain_security_decision_summary", {})
        if isinstance(security_pass.get("markdown_terrain_security_decision_summary"), dict)
        else {}
    )
    security_pass_worker = (
        security_pass.get("worker_output_orphaned_capability_summary", {})
        if isinstance(security_pass.get("worker_output_orphaned_capability_summary"), dict)
        else {}
    )
    security_pass_trust = (
        security_pass.get("chief_hermes_trust_summary", {})
        if isinstance(security_pass.get("chief_hermes_trust_summary"), dict)
        else {}
    )
    governance_batch = (
        snapshot.get("post_security_governance_batch", {})
        if isinstance(snapshot.get("post_security_governance_batch"), dict)
        else {}
    )
    parked_experiment = (
        snapshot.get("parked_autonomous_capital_pipeline_experiment", {})
        if isinstance(snapshot.get("parked_autonomous_capital_pipeline_experiment"), dict)
        else {}
    )
    security_delta = (
        snapshot.get("security_delta_review", {})
        if isinstance(snapshot.get("security_delta_review"), dict)
        else {}
    )
    attention_promotion = (
        snapshot.get("operator_attention_promotion", {})
        if isinstance(snapshot.get("operator_attention_promotion"), dict)
        else {}
    )
    chief_cross_off = (
        snapshot.get("chief_test_harness_cross_off", {})
        if isinstance(snapshot.get("chief_test_harness_cross_off"), dict)
        else {}
    )
    capital_facts = (
        capital_hilton.get("candidate_facts")
        if isinstance(capital_hilton.get("candidate_facts"), list)
        else []
    )
    capital_questions = (
        capital_hilton.get("operator_memory_questions")
        if isinstance(capital_hilton.get("operator_memory_questions"), list)
        else []
    )
    lines = [
        "# OpenClaw Stable Map Bundle",
        "",
        "## What Mission Control Should Read",
        "",
        f"- Map generation: `{snapshot['map_generation_id']}`",
        f"- Bundle hash: `{manifest['bundle_hash']}`",
        f"- Stable files: `{MAP_SNAPSHOT_EXPORT_NAME}`, `{MAP_MANIFEST_EXPORT_NAME}`, `{MAP_OPERATOR_EXPORT_NAME}`",
        "- Raw generated read-models remain proof/detail, not the front-door app dependency.",
        "",
        "## Current Sync Truth",
        "",
        f"- Raw canonical expected: `{sync.get('canonical_expected')}`",
        f"- Raw observed: `{sync.get('observed')}`",
        f"- Raw missing expected: `{sync.get('missing_expected')}`",
        f"- Raw hash mismatch: `{sync.get('hash_mismatch')}`",
        f"- Raw lifecycle: `{sync.get('sync_lifecycle_state')}`",
        f"- Check Transmission source: `{health.get('source_truth_rule')}`",
        "",
        "## Threshold Map Included",
        "",
        f"- Capital Hilton route: `{threshold['capital_hilton_finance_destiny'].get('resolution_route')}` -> `{threshold['capital_hilton_finance_destiny'].get('target_world')}`",
        f"- System Awareness lane: `{threshold['system_awareness_discovery_steel_thread'].get('readiness_state')}`",
        "- Cue/autonomy remains future-gated and is not active authority.",
        "",
        "## Agent Council / Dossier Summary",
        "",
        f"- Cards available: `{agent_council.get('agent_dossier_cards_count')}`",
        f"- Featured agents: `{', '.join(agent_council.get('featured_agents', []))}`",
        f"- System-loop cards: `{', '.join(agent_council.get('system_component_cards', []))}`",
        f"- Future-gated cards: `{agent_council.get('future_gated_cards_count')}`",
        "- Cassandra, Chief, Guardian, Hermes, Niles, and Struna are available as read-only dossier cards.",
        "- Agentic Loop, Cue Parser / Brain Dump Parser, Repo B Planner / Builder / Orchestrator, Package Compiler, Model Router, and Tool / Plugin Registry are available as system-loop cards.",
        "- Cards are preview/readback only; live chat, agent activation, model launch, tool execution, credentials, browser/OAuth, Gmail/calendar/Coupa/Telegram, send/submit/approval, and raw private context remain blocked.",
        "- Mission Control should render a selected dossier card, roster rail, permission chips, strengths, missing proof, operator questions, and package preview route without adding a new per-contract file dependency.",
        "",
        "## Package Preview Receipt Summary",
        "",
        f"- Summary present: `{str(package_receipts.get('present')).lower()}`",
        f"- Contract: `{package_receipts.get('contract_id')}` / `{package_receipts.get('contract_version')}`",
        f"- Receipt types: `{package_receipts.get('receipt_types_count')}`",
        f"- Preview states: `{package_receipts.get('preview_states_count')}`",
        f"- Example preview cards: `{package_receipts.get('example_package_previews_count')}`",
        "- Mission Control can render package preview cards for Cassandra Capital Hilton, Chief Check Engine, Guardian Protected Evidence, Niles / Struna, Hermes, Codex, Gemini / Antigravity, and Agentic Loop Classification.",
        "- Package preview remains display-only: dispatch, model calls, tool execution, agent activation, queue execution, account access, send/submit/approval, raw body inclusion, and canonical memory writes are blocked.",
        "",
        "## Tool Adapter Receipt Summary",
        "",
        f"- Summary present: `{str(tool_receipts.get('present')).lower()}`",
        f"- Contract: `{tool_receipts.get('contract_id')}` / `{tool_receipts.get('contract_version')}`",
        f"- Receipt types: `{tool_receipts.get('receipt_types_count')}`",
        f"- Receipt states: `{tool_receipts.get('receipt_states_count')}`",
        f"- Capability classes: `{tool_receipts.get('capability_classes_count')}`",
        f"- Adapter receipt cards: `{tool_receipts.get('adapter_examples_count')}`",
        f"- Allowed read-only: `{tool_receipts.get('allowed_read_only_count')}`",
        f"- Preview/receipt-only: `{tool_receipts.get('preview_or_receipt_only_count')}`",
        f"- Blocked or future-gated: `{tool_receipts.get('blocked_or_future_gated_count')}`",
        "- Mission Control can render adapter receipt cards for the stable map reader, package preview exporter, Codex verifier, Cassandra/Capital Hilton proof adapter, Guardian gate, Chief harness, browser/OAuth, Gmail/calendar, Coupa, Telegram, Repo B planner/builder, and memory candidate writer.",
        "- Live tool execution, network/account/browser access, send/submit/approval, command execution, model calls, agent activation, and queue execution remain false.",
        "",
        "## Capital Hilton Proof Metadata Summary",
        "",
        f"- Summary present: `{str(capital_hilton.get('present')).lower()}`",
        f"- Phase: `{capital_hilton.get('current_phase')}`",
        f"- Target world: `{capital_hilton.get('target_world')}`",
        f"- Lane destiny: `{capital_hilton.get('lane_destiny')}`",
        f"- Missing proof count: `{capital_hilton.get('missing_proof_count')}`",
        f"- Protected proof required: `{str(capital_hilton.get('protected_proof_required')).lower()}`",
        "- Candidate facts are displayed as candidate/not machine-proven. Operator memory can clarify them, but it does not become proof by itself.",
        "- Missing proof includes performance date, rate, subtotal, Coupa/PO/payment, Excel/workbook, invoice source card, AP route, Guardian gate, operator confirmation, and future invoice generation receipt metadata.",
        "- Cassandra may review metadata and proof gaps; Guardian must gate protected proof; Finance World remains a preview-only target until proof and security are complete.",
        "- Coupa, browser/OAuth/account access, credentials, Gmail/calendar/email account access, Excel raw body ingestion, raw finance bodies, invoice generation, send/submit/approval, model calls, agent activation, tool execution, queue execution, and runtime dispatch remain blocked.",
        f"- Next safe move: {capital_hilton.get('next_safe_move')}",
        "",
        "### Capital Hilton Candidate Facts",
        "",
    ]
    for fact in capital_facts:
        lines.append(
            f"- `{fact.get('fact_id')}`: `{fact.get('current_value')}` -> `{fact.get('proof_status')}`"
        )
    lines.extend(
        [
            "",
            "### Capital Hilton Operator Memory Questions",
            "",
        ]
    )
    for question in capital_questions:
        lines.append(f"- `{question.get('classification')}`: {question.get('question')}")
    lines.extend(
        [
            "",
            "## Security Audit Readiness Summary",
            "",
            "- ELI5: OpenClaw is ready for a security pass review because the audit packet can show provenance, answer capture, quieting, shared paths, focus mode, coverage gaps, parked breadcrumbs, and Capital Hilton readiness without granting authority.",
            f"- Summary present: `{str(security.get('present')).lower()}`",
            f"- Schema: `{security.get('schema_version')}`",
            f"- Ready for security pass: `{str(security.get('ready_for_security_pass')).lower()}`",
            f"- Security approval granted: `{str(security.get('security_approval_granted')).lower()}`",
            f"- Action authority granted: `{str(security.get('action_authority_granted')).lower()}`",
            f"- All authority flags false: `{str(security.get('all_authority_flags_false')).lower()}`",
            f"- Zero execution authority leaked: `{str(security.get('zero_execution_authority_leaked')).lower()}`",
            "",
            "### Map-To-Terrain Provenance",
            "",
            f"- Stable map is source truth: `{str(provenance.get('stable_map_is_source_truth')).lower()}`",
            f"- Stable map is app-facing reflection: `{str(provenance.get('stable_map_is_app_facing_reflection')).lower()}`",
            f"- Claims require source/candidate status: `{str(provenance.get('claims_require_source_or_candidate_status')).lower()}`",
            f"- Candidate claims are not proof: `{str(provenance.get('candidate_claims_not_proof')).lower()}`",
            "",
            "### Operator Answer Capture",
            "",
            f"- Schema present: `{str(answer_capture.get('answer_capture_schema_present')).lower()}`",
            f"- Operator answers are memory candidates: `{str(answer_capture.get('operator_answers_are_memory_candidates')).lower()}`",
            f"- Operator answers are not proof: `{str(answer_capture.get('operator_answers_are_not_proof')).lower()}`",
            f"- Question quieting states: `{answer_capture.get('question_quieting_states_count')}`",
            f"- Answer popup implemented: `{str(answer_capture.get('answer_popup_implemented')).lower()}`",
            "",
            "### Shared Execution Paths",
            "",
            f"- Shared paths: `{shared_paths.get('shared_execution_paths_count')}`",
            f"- Protected finance proof metadata intake: `{str(shared_paths.get('protected_finance_proof_metadata_intake_present')).lower()}`",
            f"- Operator memory question capture: `{str(shared_paths.get('operator_memory_question_capture_present')).lower()}`",
            f"- Stable map receipt readback: `{str(shared_paths.get('stable_map_receipt_readback_present')).lower()}`",
            f"- Non-executing: `{str(shared_paths.get('shared_paths_are_non_executing')).lower()}`",
            "",
            "### Helm Issue Focus",
            "",
            f"- Focus mode defined: `{str(focus_mode.get('focus_mode_defined')).lower()}`",
            f"- Issue focus cards: `{focus_mode.get('issue_focus_cards_count')}`",
            f"- No live controls: `{str(focus_mode.get('no_live_controls')).lower()}`",
            f"- Capital Hilton focus available: `{str(focus_mode.get('capital_hilton_focus_available')).lower()}`",
            "",
            "### Coverage Gap / Unmapped Terrain",
            "",
            f"- Coverage gap records: `{coverage_gap.get('coverage_gap_records_count')}`",
            f"- Markdown terrain present: `{str(coverage_gap.get('markdown_document_terrain_present')).lower()}`",
            f"- Tagging system capability present: `{str(coverage_gap.get('tagging_system_capability_present')).lower()}`",
            f"- Mission Control visibility gap present: `{str(coverage_gap.get('mission_control_visibility_gap_present')).lower()}`",
            f"- Operator memory gap present: `{str(coverage_gap.get('operator_memory_gap_present')).lower()}`",
            f"- Repo terrain gap present: `{str(coverage_gap.get('repo_terrain_gap_present')).lower()}`",
            f"- Broad markdown scan allowed: `{str(coverage_gap.get('broad_markdown_scan_allowed')).lower()}`",
            f"- File moves allowed: `{str(coverage_gap.get('file_moves_allowed')).lower()}`",
            f"- Repo B body inspection allowed: `{str(coverage_gap.get('repo_b_body_inspection_allowed')).lower()}`",
            "",
            "### Parked Breadcrumbs",
            "",
            f"- Breadcrumbs reviewed: `{parked.get('parked_breadcrumb_count')}`",
            f"- Auto-promotion allowed: `{str(parked.get('auto_promotion_allowed')).lower()}`",
            f"- Queue creation allowed: `{str(parked.get('queue_creation_allowed')).lower()}`",
            f"- Trigger engine allowed: `{str(parked.get('trigger_engine_allowed')).lower()}`",
            "- Highlighted breadcrumbs: " + ", ".join(f"`{item}`" for item in parked.get("known_highlighted_breadcrumbs", [])),
            "",
            "### Capital Hilton Security Readiness",
            "",
            f"- Phase: `{capital_security.get('current_phase')}`",
            f"- Target world: `{capital_security.get('target_world')}`",
            f"- Lane destiny: `{capital_security.get('lane_destiny')}`",
            f"- Missing proof count: `{capital_security.get('missing_proof_count')}`",
            f"- Protected proof required: `{str(capital_security.get('protected_proof_required')).lower()}`",
            f"- Candidate facts proven: `{str(capital_security.get('candidate_facts_proven')).lower()}`",
            f"- Security pass complete: `{str(capital_security.get('security_pass_complete')).lower()}`",
            f"- Action authority granted: `{str(capital_security.get('action_authority_granted')).lower()}`",
            f"- Shared execution path: `{capital_security.get('shared_execution_path_id')}`",
            "",
            f"- Next safe move: {security.get('next_safe_move')}",
            "",
            "## Security Pass Summary",
            "",
            "- ELIWINSHIP: the security pass approves the current read-only, preview-only, metadata-only, proof/detail, stable-map, and world-preview posture. It also approves worker-output intake, orphaned-capability detection, Chief/Hermes review metadata, and FULL_TRUST modeling as non-executing map truth.",
            f"- Summary present: `{str(security_pass.get('present')).lower()}`",
            f"- Schema: `{security_pass.get('schema_version')}`",
            f"- Security pass completed: `{str(security_pass.get('security_pass_completed')).lower()}`",
            f"- Read-only surfaces approved: `{str(security_pass.get('read_only_surfaces_approved')).lower()}`",
            f"- Preview surfaces approved: `{str(security_pass.get('preview_surfaces_approved')).lower()}`",
            f"- Metadata-only surfaces approved: `{str(security_pass.get('metadata_only_surfaces_approved')).lower()}`",
            f"- Worker output intake metadata approved: `{str(security_pass.get('worker_output_intake_metadata_approved')).lower()}`",
            f"- Orphaned capability detection approved: `{str(security_pass.get('orphaned_capability_detection_approved')).lower()}`",
            f"- Chief reconciliation metadata approved: `{str(security_pass.get('chief_reconciliation_metadata_approved')).lower()}`",
            f"- Hermes architecture review metadata approved: `{str(security_pass.get('hermes_architecture_review_metadata_approved')).lower()}`",
            f"- Trust-clearance modeling approved: `{str(security_pass.get('trust_clearance_modeling_approved')).lower()}`",
            f"- Action authority granted: `{str(security_pass.get('action_authority_granted')).lower()}`",
            f"- Runtime/model/tool/queue/account/send authority granted: `{str(any(security_pass.get(key) is True for key in ('runtime_execution_authority_granted', 'model_execution_authority_granted', 'tool_execution_authority_granted', 'queue_execution_authority_granted', 'account_authority_granted', 'send_submit_approval_authority_granted'))).lower()}`",
            f"- Chief self-authorization allowed: `{str(security_pass.get('chief_self_authorization_allowed')).lower()}`",
            f"- Hermes self-authorization allowed: `{str(security_pass.get('hermes_self_authorization_allowed')).lower()}`",
            f"- Automatic activation allowed: `{str(security_pass.get('automatic_activation_allowed')).lower()}`",
            f"- Automatic cross-off allowed: `{str(security_pass.get('automatic_cross_off_allowed')).lower()}`",
            "",
            "### Security Pass Surface Decisions",
            "",
        ]
    )
    for surface in (
        security_pass.get("surface_decision_summary")
        if isinstance(security_pass.get("surface_decision_summary"), list)
        else []
    ):
        lines.append(
            f"- `{surface.get('surface_id')}`: {surface.get('display_name')} -> `{surface.get('authority_summary', {}).get('approval_status')}`; next: {surface.get('next_safe_move')}"
        )
    lines.extend(
        [
            "",
            "### Capital Hilton / Finance Security Pass",
            "",
            f"- Preview approved: `{str(security_pass_capital.get('finance_world_preview_approved')).lower()}`",
            f"- Proof metadata display approved: `{str(security_pass_capital.get('proof_metadata_display_approved')).lower()}`",
            f"- Operator questions display approved: `{str(security_pass_capital.get('operator_questions_display_approved')).lower()}`",
            f"- Missing proof count: `{security_pass_capital.get('missing_proof_count')}`",
            f"- Protected proof required: `{str(security_pass_capital.get('protected_proof_required')).lower()}`",
            f"- Candidate facts proven: `{str(security_pass_capital.get('candidate_facts_proven')).lower()}`",
            f"- Invoice generation allowed: `{str(security_pass_capital.get('invoice_generation_allowed')).lower()}`",
            f"- Coupa access allowed: `{str(security_pass_capital.get('coupa_access_allowed')).lower()}`",
            f"- Credentials allowed: `{str(security_pass_capital.get('credential_handling_allowed')).lower()}`",
            f"- Send/submit/approval allowed: `{str(security_pass_capital.get('send_submit_approval_allowed')).lower()}`",
            f"- Guardian gate required: `{str(security_pass_capital.get('guardian_gate_required')).lower()}`",
            f"- Operator final authority required: `{str(security_pass_capital.get('operator_final_authority_required')).lower()}`",
            "",
            "### Markdown / Terrain Security Pass",
            "",
            f"- Markdown backend ready: `{str(security_pass_markdown.get('markdown_backend_ready')).lower()}`",
            f"- Markdown Knowledge Atlas present: `{str(security_pass_markdown.get('markdown_knowledge_atlas_present')).lower()}`",
            f"- Approved Markdown Evidence ingestion present: `{str(security_pass_markdown.get('approved_markdown_evidence_ingestion_present')).lower()}`",
            f"- Corpus Atlas present: `{str(security_pass_markdown.get('corpus_atlas_present')).lower()}`",
            f"- Metadata readback approved: `{str(security_pass_markdown.get('metadata_readback_approved')).lower()}`",
            f"- Bounded allowlisted excerpt metadata approved: `{str(security_pass_markdown.get('bounded_allowlisted_excerpt_metadata_approved')).lower()}`",
            f"- Broad Markdown body ingestion allowed: `{str(security_pass_markdown.get('broad_markdown_body_ingestion_allowed')).lower()}`",
            f"- File moves/deletes/renames allowed: `{str(security_pass_markdown.get('file_moves_deletes_renames_allowed')).lower()}`",
            f"- App visibility future gap: `{str(security_pass_markdown.get('app_visibility_future_gap')).lower()}`",
            "",
            "### Worker Outputs / Orphaned Capabilities",
            "",
            f"- Worker output intake metadata approved: `{str(security_pass_worker.get('worker_output_intake_metadata_approved')).lower()}`",
            f"- Orphaned capability detection approved: `{str(security_pass_worker.get('orphaned_capability_detection_approved')).lower()}`",
            f"- Detected capabilities auto-activate: `{str(security_pass_worker.get('detected_capabilities_auto_activate')).lower()}`",
            f"- Promotion decisions are recommendations only: `{str(security_pass_worker.get('promotion_decisions_are_recommendations_only')).lower()}`",
            f"- Markdown Atlas candidate present: `{str(security_pass_worker.get('markdown_knowledge_atlas_candidate_present')).lower()}`",
            f"- Future invoicing audit captured: `{str(security_pass_worker.get('future_invoicing_audit_captured')).lower()}`",
            f"- Future invoicing audit status: `{security_pass_worker.get('future_invoicing_audit_status')}`",
            f"- Ledger write allowed: `{str(security_pass_worker.get('ledger_write_allowed')).lower()}`",
            f"- Email dispatch allowed: `{str(security_pass_worker.get('email_dispatch_allowed')).lower()}`",
            "",
            "### Chief / Hermes / FULL_TRUST",
            "",
            f"- Chief reconciliation metadata approved: `{str(security_pass_trust.get('chief_reconciliation_metadata_approved')).lower()}`",
            f"- Hermes architecture review metadata approved: `{str(security_pass_trust.get('hermes_architecture_review_metadata_approved')).lower()}`",
            f"- Trust-clearance modeling approved: `{str(security_pass_trust.get('trust_clearance_modeling_approved')).lower()}`",
            f"- FULL_TRUST is LM confidence: `{str(security_pass_trust.get('full_trust_clearance_is_lm_confidence')).lower()}`",
            f"- FULL_TRUST grants authority by itself: `{str(security_pass_trust.get('full_trust_clearance_grants_authority_by_itself')).lower()}`",
            f"- Below-FULL_TRUST runs unattended: `{str(security_pass_trust.get('below_full_trust_runs_unattended')).lower()}`",
            f"- Chief self-authorization allowed: `{str(security_pass_trust.get('chief_self_authorization_allowed')).lower()}`",
            f"- Hermes self-authorization allowed: `{str(security_pass_trust.get('hermes_self_authorization_allowed')).lower()}`",
            f"- Automatic cross-off allowed: `{str(security_pass_trust.get('automatic_cross_off_allowed')).lower()}`",
            f"- Cross-off deletes source notes: `{str(security_pass_trust.get('cross_off_deletes_source_notes')).lower()}`",
            f"- Trust detours present: `{str(security_pass_trust.get('trust_detours_present')).lower()}`",
            "",
            "## Post-Security Governance Batch Summary",
            "",
            "- ELIWINSHIP: the batch adds the governance rails for what comes after the Security Pass without making anything live. It parks a high-risk capital R&D idea, defines how future changes get delta-reviewed, decides what should reach operator attention, and defines how Chief can later verify/cross off work with proof.",
            f"- Summary present: `{str(governance_batch.get('present')).lower()}`",
            f"- Batch id: `{governance_batch.get('batch_id')}`",
            f"- Batch status: `{governance_batch.get('batch_status')}`",
            f"- Lane count: `{governance_batch.get('lane_count')}`",
            f"- Completed lanes: `{', '.join(governance_batch.get('completed_lanes', []))}`",
            f"- Next expected actor: `{governance_batch.get('next_expected_actor')}`",
            f"- Batch live authority false: `{str(governance_batch.get('authority_boundary', {}).get('all_live_authority_false')).lower()}`",
            "",
            "### Parked Capital R&D Experiment",
            "",
            f"- Status: `{parked_experiment.get('status')}`",
            f"- Phases captured: `{parked_experiment.get('phase_count')}`",
            f"- All authority false: `{str(parked_experiment.get('all_authority_false')).lower()}`",
            f"- Future gates required: `{str(parked_experiment.get('future_gates_required')).lower()}`",
            f"- Token concept is future-only: `{str(parked_experiment.get('token_concept_future_only')).lower()}`",
            f"- Stress-test artifact: `{str(parked_experiment.get('stress_test_classification')).lower()}`",
            "- It is parked R&D only: no spend, account creation, deployment, acquisition, payout, model/tool/agent/runtime, network, ledger, invoice, or queue authority.",
            "",
            "### Security Delta Review",
            "",
            f"- Summary present: `{str(security_delta.get('present')).lower()}`",
            f"- Delta classes: `{security_delta.get('delta_classes_count')}`",
            f"- Default examples: `{security_delta.get('default_examples_count')}`",
            f"- Repass-required categories: `{', '.join(security_delta.get('repass_required_categories', []))}`",
            f"- Action authority granted: `{str(security_delta.get('action_authority_granted')).lower()}`",
            "- Future additions inherit the Security Pass law when they match an approved class; authority-changing lanes route to delta review or security repass.",
            "",
            "### Operator Attention Promotion",
            "",
            f"- Promotion lifecycle present: `{str(attention_promotion.get('promotion_lifecycle_present')).lower()}`",
            f"- Quiet helm policy present: `{str(attention_promotion.get('quiet_helm_policy_present')).lower()}`",
            f"- Shared fix path handling present: `{str(attention_promotion.get('shared_fix_path_handling_present')).lower()}`",
            f"- Cue candidates executable: `{str(attention_promotion.get('cue_candidates_executable')).lower()}`",
            f"- Holding-cell items queued: `{str(attention_promotion.get('holding_cell_queued')).lower()}`",
            f"- Action authority granted: `{str(attention_promotion.get('action_authority_granted')).lower()}`",
            "- SQLite rows, receipts, breadcrumbs, worker reports, and stable-map facts do not automatically bother Winship; they need a promotion decision.",
            "",
            "### Chief Test Harness / Cross-Off",
            "",
            f"- Test harness receipt model present: `{str(chief_cross_off.get('test_harness_receipt_model_present')).lower()}`",
            f"- Cross-off rules present: `{str(chief_cross_off.get('cross_off_rules_present')).lower()}`",
            f"- Source mutation allowed: `{str(chief_cross_off.get('source_mutation_allowed')).lower()}`",
            f"- Source deletion allowed: `{str(chief_cross_off.get('delete_source_allowed')).lower()}`",
            f"- Repair/requeue recommendations metadata-only: `{str(chief_cross_off.get('repair_requeue_recommendations_metadata_only')).lower()}`",
            f"- Quiet-with-proof model present: `{str(chief_cross_off.get('quiet_with_proof_model_present')).lower()}`",
            f"- Action authority granted: `{str(chief_cross_off.get('action_authority_granted')).lower()}`",
            "- Cross-off means a completion receipt/candidate, not deleting or mutating the original note.",
            "",
            "## What Mission Control Can Render Next",
            "",
            "- Package Preview surface: preview cards, included/excluded context summaries, missing proof, gates, receipts, stop conditions, and future dispatch blockers.",
            "- Tool Adapter Receipt surface: requested adapter, package, actor, capability requested/granted/blocked, gates, blocked reasons, and output receipt shape.",
            "- Agent Council can link dossier cards to package/tool summaries through this stable map snapshot without new per-file app dependencies.",
            "",
            "## What Remains Blocked / Future-Gated",
            "",
            "- No live dispatch, model launch, tool execution, browser/OAuth/account access, Gmail/calendar/Coupa/Telegram controls, credentials, send/submit/approval, planner/builder/queue/autonomy, arbitrary commands, or raw private context.",
            "- Package and adapter records are proof/display surfaces only; they do not create authority.",
            "",
            "## What This Fixes",
            "",
            "- Adding a new backend read-model may update the map content or raw proof count, but it should not require a new Mission Control entitlement or app-facing file path.",
            "- Mission Control can fail closed on the stable map if the map receipt is stale without treating the whole raw terrain as absent.",
            "",
            "## Boundary",
            "",
            "- Metadata/read-model contract only.",
            "- No model calls, agent activation, browser/OAuth/account access, send/submit/approval, remount, repair, delete, file move, network operation, or C-drive artifact write.",
        ]
    )
    return "\n".join(lines) + "\n"


def format_operator_map_bundle_contract(payload: dict[str, Any]) -> str:
    audit = payload["path_audit"]
    manifest = payload["map_manifest"]
    receipt = payload["receipt_validation"]
    lines = [
        "# Operator Map Bundle Contract v0",
        "",
        "## Summary",
        "",
        "Mission Control should consume a stable map snapshot instead of treating the full generated read-model file set as the app contract.",
        "",
        "## Path Audit",
        "",
        f"- Repo A generated source: `{audit['repo_a_generated_read_model_source_path']}`",
        f"- Returned Mac manifest: `{audit['canonical_manifest_path']}`",
        f"- E-drive shuttle export path: `{audit['e_drive_shuttle_export_path']}`",
        f"- Mac expected mount path: `{audit['mac_expected_mount_path']}`",
        f"- Mac local mirror path: `{audit['mac_local_mirror_path']}`",
        f"- Sync request marker: `{audit['sync_request_marker_path']}`",
        f"- Mac completion marker: `{audit['mac_completion_receipt_marker_path']}`",
        f"- PC import/readback state: `{audit['pc_import_readback_receipt_path']}`",
        f"- Threshold break classification: `{audit['threshold_break_classification']}`",
        f"- Threshold break reason: {audit['threshold_break_reason']}",
        "",
        "## Stable App Contract",
        "",
        f"- Snapshot: `{MAP_SNAPSHOT_EXPORT_NAME}`",
        f"- Manifest: `{MAP_MANIFEST_EXPORT_NAME}`",
        f"- Operator digest: `{MAP_OPERATOR_EXPORT_NAME}`",
        f"- Map generation: `{manifest['map_generation_id']}`",
        f"- Bundle hash: `{manifest['bundle_hash']}`",
        f"- Stable app-facing file count: `{len(STABLE_APP_FACING_FILES)}`",
        "",
        "## Sync Health Split",
        "",
        "- Raw read-model count remains proof/detail.",
        "- Map generation/receipt agreement becomes the app-visible Check Transmission source truth once Mac implements the stable reader.",
        f"- Current map receipt validation: `{receipt['status']}`",
        "",
        "## Mac-Side Change Required",
        "",
        f"- Read `{DEFAULT_MAC_LOCAL_MAP_ROOT}/{MAP_MANIFEST_EXPORT_NAME}`.",
        f"- Read `{DEFAULT_MAC_LOCAL_MAP_ROOT}/{MAP_SNAPSHOT_EXPORT_NAME}`.",
        f"- Optionally show `{DEFAULT_MAC_LOCAL_MAP_ROOT}/{MAP_OPERATOR_EXPORT_NAME}`.",
        "- Entitle those stable paths once; do not add a new entitlement for every future proof-detail read-model.",
        "- If missing, fail closed as map unavailable; if stale, show map sync pending.",
        "",
        "## Boundary",
        "",
    ]
    lines.extend(f"- `{key}` = `{value}`" for key, value in sorted(payload["no_authority_flags"].items()))
    return "\n".join(lines) + "\n"


def _stage_openclaw_map_bundle(
    *,
    manifest: dict[str, Any],
    snapshot_path: Path,
    manifest_path: Path,
    operator_path: Path,
    pc_transfer_root: str | Path,
    generated_at: str,
) -> tuple[Path, Path]:
    transfer = Path(pc_transfer_root)
    to_mac = transfer / "shuttle" / "to_mac"
    map_generation_id = str(manifest["map_generation_id"])
    bundle_root = to_mac / "map_bundle" / map_generation_id
    bundle_root.mkdir(parents=True, exist_ok=True)

    staged_files = (
        (snapshot_path, bundle_root / MAP_SNAPSHOT_EXPORT_NAME),
        (manifest_path, bundle_root / MAP_MANIFEST_EXPORT_NAME),
        (operator_path, bundle_root / MAP_OPERATOR_EXPORT_NAME),
    )
    for source, target in staged_files:
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    marker_path = to_mac / MAP_SYNC_REQUIRED_EXPORT_NAME
    bundle_file_records = [
        {
            "relative_path": target.name,
            "source_path": f"generated/read_models/{target.name}",
            "bundle_source_path": target.as_posix(),
            "hash_algorithm": "sha256",
            "sha256": _sha256_file(target),
        }
        for _, target in staged_files
    ]
    required_file_records = [
        {
            "relative_path": record["relative_path"],
            "source_path": record["bundle_source_path"],
            "canonical_source_path": record["source_path"],
            "target_path": f"{DEFAULT_MAC_LOCAL_MAP_ROOT}/{record['relative_path']}",
            "hash_algorithm": "sha256",
            "sha256": record["sha256"],
        }
        for record in bundle_file_records
    ]
    marker = {
        "schema_version": MAP_SYNC_REQUIRED_SCHEMA_VERSION,
        "created_at": generated_at,
        "generated_at": generated_at,
        "status": "map_generation_pending_mac_import",
        "map_generation_id": map_generation_id,
        "bundle_hash": manifest["bundle_hash"],
        "source_path": bundle_root.as_posix(),
        "staged_bundle_path": bundle_root.as_posix(),
        "bundle_generation_path": bundle_root.as_posix(),
        "canonical_source_path": "generated/read_models",
        "bundle_files_written": bundle_file_records,
        "required_files": required_file_records,
        "target_mac_local_mirror_path": DEFAULT_MAC_LOCAL_MAP_ROOT,
        "target_mac_files": {
            "snapshot": f"{DEFAULT_MAC_LOCAL_MAP_ROOT}/{MAP_SNAPSHOT_EXPORT_NAME}",
            "manifest": f"{DEFAULT_MAC_LOCAL_MAP_ROOT}/{MAP_MANIFEST_EXPORT_NAME}",
            "operator_digest": f"{DEFAULT_MAC_LOCAL_MAP_ROOT}/{MAP_OPERATOR_EXPORT_NAME}",
        },
        "next_expected_actor": "mac_map_import_agent",
        "expected_next_actor": "mac_map_import_agent",
        "fallback_actor": "mac_read_model_sync_agent",
        "app_visible_current_claimed_by_pc": False,
        "do_not_fake_completion": True,
        "optional_future_receipt": {
            "relative_path": "openclaw_map_receipt.json",
            "schema_version": MAP_RECEIPT_SCHEMA_VERSION,
            "target_path": f"{DEFAULT_MAC_LOCAL_MAP_ROOT}/openclaw_map_receipt.json",
        },
        "boundary": {
            "no_execution": True,
            "no_credential": True,
            "no_network": True,
            "no_mac_import_performed_by_pc": True,
            "no_live_model_agent_tool_runtime": True,
            "no_account_payment_financial_authority": True,
            "no_send_submit_approval": True,
        },
        "no_execution_no_credential_no_network_boundary": {
            "execution_authority": False,
            "credential_handling_allowed": False,
            "network_authority": False,
        },
        "no_authority_flags": {
            "agent_activation_allowed": False,
            "browser_oauth_account_access_allowed": False,
            "cleanup_remount_repair_allowed": False,
            "credential_handling_allowed": False,
            "file_delete_allowed": False,
            "file_move_allowed": False,
            "gmail_calendar_coupa_telegram_allowed": False,
            "model_execution_allowed": False,
            "network_authority": False,
            "pc_c_drive_artifact_write_allowed": False,
            "runtime_authority": False,
            "send_submit_approval_allowed": False,
            "tool_plugin_execution_allowed": False,
        },
        "agent_activation_allowed": False,
        "browser_oauth_account_access_allowed": False,
        "cleanup_remount_repair_allowed": False,
        "credential_handling_allowed": False,
        "file_delete_allowed": False,
        "file_move_allowed": False,
        "gmail_calendar_coupa_telegram_allowed": False,
        "model_execution_allowed": False,
        "network_authority": False,
        "pc_c_drive_artifact_write_allowed": False,
        "runtime_authority": False,
        "send_submit_approval_allowed": False,
        "tool_plugin_execution_allowed": False,
    }
    marker_path.write_text(stable_json(marker), encoding="utf-8")
    return bundle_root, marker_path


def export_operator_map_bundle(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    pc_transfer_root: str | Path = DEFAULT_PC_TRANSFER_ROOT,
) -> OperatorMapBundleExportResult:
    generated_at = generated_at or utc_now()
    snapshot = build_openclaw_map_snapshot(repo_root=repo_root, generated_at=generated_at)
    manifest = build_openclaw_map_manifest(
        snapshot=snapshot,
        repo_root=repo_root,
        generated_at=generated_at,
    )
    contract = build_operator_map_bundle_contract(
        repo_root=repo_root,
        generated_at=generated_at,
        pc_transfer_root=pc_transfer_root,
    )
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)

    contract_json = root / CONTRACT_JSON_EXPORT_NAME
    contract_operator = root / CONTRACT_OPERATOR_EXPORT_NAME
    map_manifest = root / MAP_MANIFEST_EXPORT_NAME
    map_snapshot = root / MAP_SNAPSHOT_EXPORT_NAME
    map_operator = root / MAP_OPERATOR_EXPORT_NAME

    contract_json.write_text(stable_json(contract), encoding="utf-8")
    contract_operator.write_text(format_operator_map_bundle_contract(contract), encoding="utf-8")
    map_manifest.write_text(stable_json(manifest), encoding="utf-8")
    map_snapshot.write_text(stable_json(snapshot), encoding="utf-8")
    map_operator.write_text(format_openclaw_map_operator(snapshot, manifest), encoding="utf-8")
    staged_bundle_path, sync_request_marker_path = _stage_openclaw_map_bundle(
        manifest=manifest,
        snapshot_path=map_snapshot,
        manifest_path=map_manifest,
        operator_path=map_operator,
        pc_transfer_root=pc_transfer_root,
        generated_at=generated_at,
    )

    return OperatorMapBundleExportResult(
        schema_version=CONTRACT_SCHEMA_VERSION,
        contract_json_path=contract_json.as_posix(),
        contract_operator_path=contract_operator.as_posix(),
        map_manifest_path=map_manifest.as_posix(),
        map_snapshot_path=map_snapshot.as_posix(),
        map_operator_path=map_operator.as_posix(),
        staged_bundle_path=staged_bundle_path.as_posix(),
        sync_request_marker_path=sync_request_marker_path.as_posix(),
        map_generation_id=str(manifest["map_generation_id"]),
        bundle_hash=str(manifest["bundle_hash"]),
        stable_app_facing_file_count=len(STABLE_APP_FACING_FILES),
        raw_private_bodies_included=False,
        runtime_activation_allowed=False,
        pc_c_drive_artifact_write_allowed=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the stable OpenClaw map bundle contract.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--pc-transfer-root", default=DEFAULT_PC_TRANSFER_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_operator_map_bundle(
        repo_root=args.repo_root,
        export_root=args.export_root,
        pc_transfer_root=args.pc_transfer_root,
    )
    payload = {
        "schema_version": result.schema_version,
        "contract_json_path": result.contract_json_path,
        "contract_operator_path": result.contract_operator_path,
        "map_manifest_path": result.map_manifest_path,
        "map_snapshot_path": result.map_snapshot_path,
        "map_operator_path": result.map_operator_path,
        "staged_bundle_path": result.staged_bundle_path,
        "sync_request_marker_path": result.sync_request_marker_path,
        "map_generation_id": result.map_generation_id,
        "bundle_hash": result.bundle_hash,
        "stable_app_facing_file_count": result.stable_app_facing_file_count,
        "raw_private_bodies_included": result.raw_private_bodies_included,
        "runtime_activation_allowed": result.runtime_activation_allowed,
        "pc_c_drive_artifact_write_allowed": result.pc_c_drive_artifact_write_allowed,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(payload), end="")
    else:
        print(f"Operator Map Bundle Contract: `{result.map_generation_id}`")
        print(f"- Contract: `{result.contract_json_path}`")
        print(f"- Snapshot: `{result.map_snapshot_path}`")
        print(f"- Manifest: `{result.map_manifest_path}`")
        print(f"- Operator digest: `{result.map_operator_path}`")
        print(f"- Staged bundle: `{result.staged_bundle_path}`")
        print(f"- Sync request marker: `{result.sync_request_marker_path}`")
    return 0


__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "MAP_MANIFEST_EXPORT_NAME",
    "MAP_RECEIPT_SCHEMA_VERSION",
    "MAP_SNAPSHOT_EXPORT_NAME",
    "MAP_OPERATOR_EXPORT_NAME",
    "MAP_SYNC_REQUIRED_EXPORT_NAME",
    "MAP_SYNC_REQUIRED_SCHEMA_VERSION",
    "STABLE_APP_FACING_FILES",
    "SECURITY_AUDIT_READINESS_READ_MODEL_PATH",
    "SECURITY_PASS_CONTRACT_READ_MODEL_PATH",
    "build_openclaw_map_manifest",
    "build_openclaw_map_snapshot",
    "build_operator_map_bundle_contract",
    "build_path_audit",
    "export_operator_map_bundle",
    "format_openclaw_map_operator",
    "format_operator_map_bundle_contract",
    "stable_json",
    "validate_map_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
