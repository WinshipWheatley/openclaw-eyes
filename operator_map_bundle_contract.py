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

AGENT_TERRAIN_READ_MODEL_PATH = "generated/read_models/agent_terrain_awareness_readback_contract.json"

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

    return OperatorMapBundleExportResult(
        schema_version=CONTRACT_SCHEMA_VERSION,
        contract_json_path=contract_json.as_posix(),
        contract_operator_path=contract_operator.as_posix(),
        map_manifest_path=map_manifest.as_posix(),
        map_snapshot_path=map_snapshot.as_posix(),
        map_operator_path=map_operator.as_posix(),
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
    return 0


__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "MAP_MANIFEST_EXPORT_NAME",
    "MAP_RECEIPT_SCHEMA_VERSION",
    "MAP_SNAPSHOT_EXPORT_NAME",
    "MAP_OPERATOR_EXPORT_NAME",
    "STABLE_APP_FACING_FILES",
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
