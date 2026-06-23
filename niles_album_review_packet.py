"""Niles album review packet from governed evidence v0.

Builds a review-only operator packet for the Niles music/album workflow from
Repo A governed evidence surfaces. It does not inspect private music folders,
open DAWs, mutate audio files, run Repo B, or grant runtime/send authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "niles_album_review_packet_v0"
JSON_EXPORT_NAME = "niles_album_review_packet.json"
OPERATOR_EXPORT_NAME = "niles_album_review_packet_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

NO_AUTHORITY_FLAGS = {
    "review_only": True,
    "daw_automation_allowed": False,
    "audio_file_mutation_allowed": False,
    "broad_private_drive_scan_allowed": False,
    "raw_audio_ingest_allowed": False,
    "logic_or_ableton_open_allowed": False,
    "finder_file_operation_allowed": False,
    "repo_b_authority_allowed": False,
    "runtime_authority_added": False,
    "tool_execution_authority_added": False,
    "model_execution_authority_added": False,
    "send_or_submit_authority_added": False,
    "mission_control_app_changed": False,
}

GOVERNED_EVIDENCE_SOURCES = (
    {
        "source_id": "niles_track_registry",
        "source_path": "generated/read_models/niles_track_registry.json",
        "source_role": "governed chief album track-registry CSV metadata (song roster + status)",
        "truth_status": "governed_operator_metadata_evidence_not_final_audio_truth",
        "confidence": "high",
    },
    {
        "source_id": "niles_album_evidence_intake_boundary",
        "source_path": "generated/read_models/niles_album_evidence_intake_boundary.json",
        "source_role": "metadata-only evidence intake boundary contract",
        "truth_status": "governed_read_model_evidence_not_truth",
        "confidence": "high",
    },
    {
        "source_id": "operator_workflow_atlas_niles_album_lane",
        "source_path": "generated/read_models/operator_workflow_atlas.json",
        "source_role": "lane recommendation and generic review-packet bottleneck evidence",
        "truth_status": "governed_read_model_evidence_not_truth",
        "confidence": "high",
    },
    {
        "source_id": "approved_module_registry_niles_album_matrix",
        "source_path": "generated/read_models/approved_module_registry.json",
        "source_role": "Niles Album Matrix planning module evidence",
        "truth_status": "governed_read_model_evidence_not_truth",
        "confidence": "high",
    },
    {
        "source_id": "cassandra_chief_memory_album_progress_deferred",
        "source_path": "generated/read_models/cassandra_chief_memory_dry_run.json",
        "source_role": "album/song progress deferred to Niles authority",
        "truth_status": "governed_read_model_evidence_not_truth",
        "confidence": "medium",
    },
    {
        "source_id": "agent_capability_migration_niles_album_matrix",
        "source_path": "generated/read_models/agent_capability_migration_map.json",
        "source_role": "legacy album helper migration evidence, not runtime authority",
        "truth_status": "governed_read_model_evidence_not_truth",
        "confidence": "medium",
    },
    {
        "source_id": "repo_b_runtime_intake_music_candidates",
        "source_path": "generated/read_models/repo_b_runtime_intake.json",
        "source_role": "Repo B reference-only music candidate counts",
        "truth_status": "reference_only_evidence_not_truth",
        "confidence": "low",
    },
    {
        "source_id": "agent_runtime_readiness_niles_metadata_only",
        "source_path": "generated/read_models/agent_runtime_readiness.json",
        "source_role": "Niles lane dry-run readiness and metadata-only Logic-file boundary",
        "truth_status": "governed_read_model_evidence_not_truth",
        "confidence": "medium",
    },
)


@dataclass(frozen=True)
class NilesAlbumReviewPacketResult:
    schema_version: str
    packet_status: str
    json_path: str
    operator_path: str
    confirmed_evidence_count: int
    missing_evidence_count: int
    blocker_count: int
    daw_automation_added: bool
    audio_file_mutation_added: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _read_json_if_present(path: str | Path) -> dict[str, Any]:
    target = _rooted(path)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _find_dicts(value: Any, predicate) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if predicate(node):
                matches.append(node)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return matches


def _source_status(source: dict[str, str]) -> dict[str, Any]:
    path = _rooted(source["source_path"])
    payload = _read_json_if_present(path)
    return {
        **source,
        "source_present": path.exists(),
        "source_payload_kind": payload.get("schema_version") or payload.get("export_version") or "unknown",
        "old_files_treated_as_evidence_not_truth": True,
        "source_promoted_to_truth": False,
    }


def _niles_workflow_posture(workflow_atlas: dict[str, Any]) -> dict[str, Any]:
    workflows = workflow_atlas.get("workflow_atlas", [])
    workflow = next(
        (
            item
            for item in workflows
            if isinstance(item, dict)
            and item.get("workflow_name") == "Niles album progress review"
        ),
        {},
    )
    return {
        "workflow_found": bool(workflow),
        "workflow_name": workflow.get("workflow_name", "Niles album progress review"),
        "current_implementation_status": workflow.get("current_implementation_status", "UNKNOWN_NEEDS_OPERATOR_CONFIRMATION"),
        "steel_thread_readiness": workflow.get("steel_thread_readiness", "needs_missing_facts_packet_before_any_album_csv_or_session_import"),
        "shared_bottleneck": workflow.get("shared_bottleneck", "generic_review_packet_non_finance_reuse"),
        "next_safe_lane": workflow.get("next_safe_lane", "Niles Album Evidence Intake Boundary v0"),
        "operator_confirmation_needed": workflow.get("operator_confirmation_needed", True),
        "confirmation_reason": workflow.get("confirmation_reason", "Album progress source of truth and inclusion rules remain unconfirmed."),
        "old_files_treated_as_evidence_not_truth": workflow.get("old_files_treated_as_evidence_not_truth", True),
    }


def _module_posture(module_registry: dict[str, Any]) -> dict[str, Any]:
    modules = module_registry.get("modules", [])
    module = next(
        (
            item
            for item in modules
            if isinstance(item, dict) and item.get("module_id") == "niles_album_matrix"
        ),
        {},
    )
    return {
        "module_found": bool(module),
        "module_id": module.get("module_id", "niles_album_matrix"),
        "display_name": module.get("display_name", "Niles Album Matrix"),
        "status": module.get("status", "draft"),
        "allowed_authority_level": module.get("allowed_authority_level", "planning_only"),
        "runtime_authority": module.get("runtime_authority", False),
        "required_inputs": module.get("required_inputs", ["album/project metadata"]),
        "no_go_data_classes": module.get(
            "no_go_data_classes",
            ["raw_daw_sessions", "unreleased_private_audio", "contracts", "credentials"],
        ),
        "sensitive_input_policy": module.get(
            "sensitive_input_policy",
            "metadata-only until music/session private-content boundaries are approved",
        ),
    }


def _memory_album_posture(memory_dry_run: dict[str, Any]) -> dict[str, Any]:
    album_records = _find_dicts(
        memory_dry_run,
        lambda item: item.get("category") == "album/song progress state"
        or item.get("source_id") == "memsrc_album_song_progress",
    )
    record = album_records[0] if album_records else {}
    return {
        "album_progress_evidence_found": bool(record),
        "category": record.get("category", "album/song progress state"),
        "source_name": record.get("source_name", "album work, content, and scheduler refs"),
        "recommended_fate": record.get("recommended_fate", "defer_operator_review"),
        "risk_level": record.get("risk_level", "medium"),
        "operator_decision_needed": True,
        "import_allowed_now": False,
        "raw_content_read": False,
        "album_state_confirmed": False,
        "reason": "Governed memory surfaces say album progress belongs to Niles/music authority, but do not provide confirmed album/session facts.",
    }


def _repo_b_music_candidate_posture(repo_b_intake: dict[str, Any]) -> dict[str, Any]:
    counts = repo_b_intake.get("counts", {}) if isinstance(repo_b_intake.get("counts"), dict) else {}
    return {
        "repo_b_reference_only": True,
        "music_candidate_count": counts.get("music_candidate_count", 0),
        "niles_candidate_count": counts.get("count_by_agent", {}).get("niles", 0)
        if isinstance(counts.get("count_by_agent"), dict)
        else 0,
        "authority_status": "reference_only_not_runtime_authority",
        "candidate_summary": "Legacy music/album helpers may contain useful ideas, but this packet does not run or port Repo B code.",
    }


def _runtime_readiness_posture(agent_runtime: dict[str, Any]) -> dict[str, Any]:
    agents = agent_runtime.get("agents", [])
    niles = next((item for item in agents if isinstance(item, dict) and item.get("agent_id") == "niles"), {})
    return {
        "niles_readiness_found": bool(niles),
        "readiness_status": niles.get("readiness_status", "unknown"),
        "lane_id": niles.get("lane_id", "music_art_production"),
        "next_safe_test": niles.get(
            "next_safe_test",
            "route a Logic-file request; metadata-only until file is resolved and approved",
        ),
        "can_execute_directly": niles.get("can_execute_directly", False),
        "can_bypass_approval": niles.get("can_bypass_approval", False),
        "metadata_only_until_file_resolved": True,
    }


def _track_registry_posture(track_registry: dict[str, Any]) -> dict[str, Any]:
    """Surface real song roster facts from the governed track-registry read-model."""
    source_present = bool(track_registry)
    tracks = track_registry.get("tracks", [])
    if not isinstance(tracks, list):
        tracks = []
    track_count = track_registry.get("track_count", len(tracks))
    status_summary = track_registry.get("status_summary", {})
    if not isinstance(status_summary, dict):
        status_summary = {}
    source_missing_gap = track_registry.get("source_missing_gap") or (
        None if source_present else "Track-registry CSV not found; song roster unavailable."
    )
    track_rows: list[dict[str, Any]] = []
    for t in tracks:
        if not isinstance(t, dict):
            continue
        track_rows.append(
            {
                "track_id": t.get("track_id"),
                "title": t.get("title"),
                "status": t.get("status"),
                "next_step": t.get("next_step"),
                "target_week": t.get("target_week"),
                "metadata_only": True,
                "album_state_confirmed": False,
                "source_ref": "generated/read_models/niles_track_registry.json",
            }
        )
    return {
        "source_present": source_present,
        "track_count": track_count,
        "status_summary": status_summary,
        "track_rows": track_rows,
        "source_missing_gap": source_missing_gap,
        "real_track_roster_available": source_present and track_count > 0,
        "metadata_only": True,
        "raw_audio_ingested": False,
        "album_state_confirmed": False,
        "source_ref": "generated/read_models/niles_track_registry.json",
        "truth_status": "governed_operator_metadata_evidence_not_final_audio_truth",
    }


def _generic_review_packet_identity() -> dict[str, Any]:
    return {
        "packet_identity": {
            "packet_id": "niles_album_review_packet",
            "packet_kind": "operator_review_packet",
            "review_packet_contract": "generic_review_packet_shape_v0",
        },
        "workflow_domain": "music_art",
        "workflow_name": "Niles album progress review",
        "request_summary": "Produce a review-only album/music workflow packet from governed Repo A evidence only.",
    }


def _metadata_present(value: Any) -> bool:
    return value not in (None, "", [], {})


def _metadata_label(record: dict[str, Any], index: int) -> str:
    return (
        record.get("song_title")
        or record.get("song_id_or_stable_operator_label")
        or record.get("album_project_name")
        or f"operator_metadata_record_{index + 1}"
    )


def _metadata_review_item(record: dict[str, Any], index: int) -> dict[str, Any]:
    supplied_fields = [
        key
        for key in (
            "album_project_name",
            "song_title",
            "song_id_or_stable_operator_label",
            "track_status_label",
            "production_stage_label",
            "source_reference_path_label",
            "daw_session_existence_flag",
            "last_known_operator_update",
            "blocker_labels",
            "next_safe_move_labels",
            "confidence",
            "evidence_status",
        )
        if _metadata_present(record.get(key))
    ]
    missing_fields = [
        key
        for key in (
            "album_project_name",
            "song_title",
            "song_id_or_stable_operator_label",
            "track_status_label",
            "production_stage_label",
            "confidence",
            "evidence_status",
        )
        if not _metadata_present(record.get(key))
    ]
    return {
        "item_id": f"niles_operator_metadata_item_{index + 1:03d}",
        "item_label": _metadata_label(record, index),
        "album_project_name": record.get("album_project_name"),
        "song_title": record.get("song_title"),
        "song_id_or_stable_operator_label": record.get("song_id_or_stable_operator_label"),
        "track_status_label": record.get("track_status_label"),
        "production_stage_label": record.get("production_stage_label"),
        "source_reference_path_label": record.get("source_reference_path_label"),
        "daw_session_existence_flag": record.get("daw_session_existence_flag"),
        "last_known_operator_update": record.get("last_known_operator_update"),
        "blocker_labels": record.get("blocker_labels", []),
        "next_safe_move_labels": record.get("next_safe_move_labels", []),
        "confidence": record.get("confidence"),
        "evidence_status": record.get("evidence_status"),
        "supplied_fields": supplied_fields,
        "missing_or_unknown_fields": missing_fields,
        "partial_metadata_supported": bool(missing_fields),
        "metadata_evidence_posture": "operator_supplied_metadata_evidence_not_album_truth",
        "album_state_confirmed": False,
        "operator_supplied": record.get("operator_supplied") is True,
        "metadata_only": record.get("metadata_only", True) is True,
        "raw_audio_stored": False,
        "daw_session_contents_stored": False,
        "file_opened_or_scanned": False,
    }


def _operator_metadata_review_items(intake_boundary: dict[str, Any]) -> list[dict[str, Any]]:
    records = intake_boundary.get("recorded_operator_metadata", [])
    if not isinstance(records, list):
        return []
    return [
        _metadata_review_item(record, index)
        for index, record in enumerate(records)
        if isinstance(record, dict)
        and record.get("operator_supplied") is True
        and record.get("metadata_only") is True
    ]


def build_niles_album_review_packet(*, repo_root: str | Path = ROOT, generated_at: str | None = None) -> dict[str, Any]:
    root = Path(repo_root)
    evidence_sources = [_source_status(source) for source in GOVERNED_EVIDENCE_SOURCES]
    workflow_atlas = _read_json_if_present(root / "generated/read_models/operator_workflow_atlas.json")
    module_registry = _read_json_if_present(root / "generated/read_models/approved_module_registry.json")
    memory_dry_run = _read_json_if_present(root / "generated/read_models/cassandra_chief_memory_dry_run.json")
    repo_b_intake = _read_json_if_present(root / "generated/read_models/repo_b_runtime_intake.json")
    agent_runtime = _read_json_if_present(root / "generated/read_models/agent_runtime_readiness.json")
    intake_boundary = _read_json_if_present(root / "generated/read_models/niles_album_evidence_intake_boundary.json")
    track_registry = _read_json_if_present(root / "generated/read_models/niles_track_registry.json")

    workflow = _niles_workflow_posture(workflow_atlas)
    module = _module_posture(module_registry)
    memory = _memory_album_posture(memory_dry_run)
    repo_b = _repo_b_music_candidate_posture(repo_b_intake)
    runtime = _runtime_readiness_posture(agent_runtime)
    track_posture = _track_registry_posture(track_registry)
    boundary_present = bool(intake_boundary)
    intake_status = intake_boundary.get("operator_metadata_intake_status", {}) if isinstance(intake_boundary, dict) else {}
    metadata_review_items = _operator_metadata_review_items(intake_boundary)
    metadata_consumed = bool(metadata_review_items)
    metadata_record_count = len(metadata_review_items)
    boundary_posture = {
        "boundary_present": boundary_present,
        "boundary_status": intake_boundary.get("boundary_status", "not_available"),
        "real_album_metadata_recorded": metadata_consumed,
        "metadata_record_count": metadata_record_count,
        "partial_metadata_intake_supported": intake_status.get("partial_metadata_intake_supported", False),
        "unknown_album_state_not_treated_as_confirmed": intake_status.get("unknown_album_state_not_treated_as_confirmed", True),
        "unknown_album_state_remains_unknown": intake_boundary.get("unknown_album_state_remains_unknown", True),
        "source_path": "generated/read_models/niles_album_evidence_intake_boundary.json",
    }
    metadata_consumption = {
        "metadata_consumed": metadata_consumed,
        "metadata_record_count": metadata_record_count,
        "review_packet_ready": metadata_consumed,
        "review_packet_status": "ready_for_review_from_governed_operator_metadata"
        if metadata_consumed
        else "blocked_needs_governed_album_evidence",
        "metadata_source": "generated/read_models/niles_album_evidence_intake_boundary.json",
        "metadata_evidence_posture": "operator_supplied_metadata_evidence_not_album_truth",
        "partial_metadata_supported": True,
        "unknown_fields_not_treated_as_confirmed": True,
        "album_state_confirmed": False,
        "raw_audio_ingested": False,
        "daw_session_content_ingested": False,
        "broad_private_drive_scan_triggered": False,
        "audio_file_mutation_allowed": False,
    }

    confirmed_evidence = [source for source in evidence_sources if source["source_present"]]
    missing_evidence = [source for source in evidence_sources if not source["source_present"]]
    confirmed_items = [
        {
            "item_id": "niles_album_matrix_planned",
            "label": "Niles Album Matrix is modeled as a planning-only module.",
            "source": "approved_module_registry_niles_album_matrix",
            "authority_status": "planning_only_not_runtime",
        },
        {
            "item_id": "niles_album_lane_recommended",
            "label": "Workflow Atlas recommends this Niles album review packet as the next non-finance generic packet proof.",
            "source": "operator_workflow_atlas_niles_album_lane",
            "authority_status": "review_packet_recommendation_not_album_truth",
        },
        {
            "item_id": "album_progress_deferred_to_niles",
            "label": "Cassandra/Chief memory surfaces defer album/song progress to Niles/music authority.",
            "source": "cassandra_chief_memory_album_progress_deferred",
            "authority_status": "deferred_evidence_not_imported_truth",
        },
        {
            "item_id": "niles_album_evidence_intake_boundary_defined",
            "label": "A metadata-only Niles album evidence intake boundary is defined." if boundary_present else "A metadata-only Niles album evidence intake boundary is still missing.",
            "source": "niles_album_evidence_intake_boundary",
            "authority_status": "operator_metadata_evidence_consumed_not_truth" if metadata_consumed else "contract_only_no_real_album_metadata",
        },
    ]
    if track_posture["real_track_roster_available"]:
        track_count = track_posture["track_count"]
        status_summary = track_posture["status_summary"]
        status_parts = ", ".join(f"{v} {k}" for k, v in sorted(status_summary.items()))
        confirmed_items.append(
            {
                "item_id": "track_registry_roster_available",
                "label": (
                    f"Governed track-registry CSV confirms {track_count} song(s) in the chief album roster: {status_parts}. "
                    "Titles are operator working titles; status is metadata-only, not final audio truth."
                ),
                "source": "niles_track_registry",
                "authority_status": "governed_metadata_evidence_not_final_audio_truth",
                "track_count": track_count,
                "status_summary": status_summary,
            }
        )
    elif not track_posture["source_present"]:
        confirmed_items.append(
            {
                "item_id": "track_registry_source_missing",
                "label": "GAP: track-registry CSV not found; no governed song roster in packet.",
                "source": "niles_track_registry",
                "authority_status": "source_missing_gap_flagged",
                "gap_detail": track_posture.get("source_missing_gap"),
            }
        )
    if metadata_consumed:
        confirmed_items.append(
            {
                "item_id": "operator_metadata_consumed_for_review",
                "label": f"{metadata_record_count} governed operator metadata record(s) are available for Niles review.",
                "source": "niles_album_evidence_intake_boundary_recorded_operator_metadata",
                "authority_status": "review_only_metadata_evidence_not_album_truth",
            }
        )
    inferred_or_desired = [
        {
            "item_id": "album_matrix_needed",
            "label": "A future album matrix should track album/project metadata, mix readiness, production packets, and operator decisions.",
            "basis": "approved module and migration-map evidence",
            "confirmation_required": True,
        },
        {
            "item_id": "logic_file_route_possible_metadata_only",
            "label": "Niles can route a Logic-file request as metadata-only after file identity is resolved and approved.",
            "basis": "agent runtime readiness smoke-test posture",
            "confirmation_required": True,
        },
    ]
    stale_legacy_evidence = [
        {
            "item_id": "repo_b_album_helpers_reference_only",
            "label": "Repo B album helpers are reference-only candidates, not executable authority.",
            "basis": "repo_b_runtime_intake and agent_capability_migration_map",
            "music_candidate_count": repo_b["music_candidate_count"],
            "niles_candidate_count": repo_b["niles_candidate_count"],
            "old_files_treated_as_evidence_not_truth": True,
        }
    ]
    missing = [
        {
            "item_id": "missing_confirmed_album_project_metadata",
            "label": "Governed operator metadata exists, but it is not final album truth." if metadata_consumed else "No governed album/project metadata packet exists yet.",
            "needed_for": "album/session status summary",
        },
        {
            "item_id": "missing_current_album_source_of_truth",
            "label": "Operator metadata does not confirm raw session, mix, or release status." if metadata_consumed else "No approved source of truth identifies current album, session, track, mix, or release status.",
            "needed_for": "operator-useful progress review",
        },
        {
            "item_id": "missing_real_governed_album_metadata",
            "label": "The metadata-only boundary exists, but no real operator-supplied album metadata has been recorded through it yet." if boundary_present and not boundary_posture["real_album_metadata_recorded"] else "Operator metadata exists but album state still needs scope/completeness review before confirmation." if boundary_posture["real_album_metadata_recorded"] else "No approved metadata-only ingestion/tagging boundary exists for music/session evidence.",
            "needed_for": "future Niles Album Matrix population",
        },
    ]
    blockers = [
        {
            "blocker_id": "album_source_of_truth_unconfirmed",
            "severity": "blocks_album_state_claims",
            "description": "Current governed evidence does not prove album/session status.",
            "next_safe_move": "Create a metadata-only Niles album evidence intake boundary before importing or summarizing album state.",
        },
        {
            "blocker_id": "raw_audio_and_daw_access_forbidden",
            "severity": "blocks_direct_session_review",
            "description": "OpenClaw may not open DAWs, inspect raw audio, or mutate music files from this packet.",
            "next_safe_move": "Operator supplies bounded metadata or approves a later no-raw-audio evidence template.",
        },
        {
            "blocker_id": "repo_b_reference_only",
            "severity": "blocks_legacy_runtime_reuse",
            "description": "Repo B music helpers are not runtime authority and cannot be executed or treated as truth.",
            "next_safe_move": "Port only safe metadata logic in a later reviewed Niles module lane.",
        },
    ]

    packet_status = (
        "ready_for_review_from_governed_operator_metadata"
        if metadata_consumed
        else "partial_track_registry_only_operator_metadata_still_needed"
        if track_posture["real_track_roster_available"]
        else "blocked_needs_governed_album_evidence"
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        **_generic_review_packet_identity(),
        "governed_evidence_only": True,
        "repo_a_canonical": True,
        "repo_b_reference_only": True,
        "packet_status": packet_status,
        "review_only": True,
        "actionable_for_manual_review": True,
        "album_state_confirmed": False,
        "unknown_album_state_not_treated_as_confirmed": True,
        "evidence_sufficient_for_album_status": False,
        "evidence_sufficient_for_review_packet": metadata_consumed,
        "metadata_consumption": metadata_consumption,
        "operator_metadata_review_items": metadata_review_items,
        "confirmed_governed_evidence": confirmed_items,
        "inferred_or_desired_album_workflow_evidence": inferred_or_desired,
        "stale_or_legacy_evidence": stale_legacy_evidence,
        "missing_evidence": missing,
        "blockers": blockers,
        "operator_confirmations_needed": [
            "Confirm the intended album/project scope for Niles.",
            "Confirm what metadata-only source can describe album/session status without opening DAWs or raw audio.",
            "Confirm whether legacy Repo B album helper logic is worth porting as metadata-only planning code later.",
        ],
        "next_safe_moves": [
            "Create a Niles Album Evidence Intake Boundary packet for operator-supplied metadata only.",
            "Define allowed album/project metadata fields before any music/session import.",
            "Keep Repo B music helpers reference-only until a separate port-logic lane is approved.",
        ],
        "source_evidence": evidence_sources,
        "source_summary": {
            "confirmed_evidence_source_count": len(confirmed_evidence),
            "missing_evidence_source_count": len(missing_evidence),
            "all_sources_repo_a_read_models_or_docs": True,
            "broad_private_drive_scan_triggered": False,
            "raw_audio_ingested": False,
            "operator_metadata_consumed": metadata_consumed,
            "operator_metadata_record_count": metadata_record_count,
        },
        "workflow_posture": workflow,
        "module_posture": module,
        "memory_album_posture": memory,
        "repo_b_music_candidate_posture": repo_b,
        "runtime_readiness_posture": runtime,
        "track_registry_posture": track_posture,
        "evidence_intake_boundary_posture": boundary_posture,
        "authority_boundary": dict(NO_AUTHORITY_FLAGS),
        "receipt_proof_status": {
            "read_model_written": True,
            "operator_packet_written": True,
            "external_action_taken": False,
            "old_docs_files_treated_as_evidence_not_truth": True,
        },
        "next_recommended_lane": "Niles Album Matrix Review Surface v0" if metadata_consumed else "Niles Album Evidence Intake Boundary v0",
        **NO_AUTHORITY_FLAGS,
    }
    return payload


def format_niles_album_review_packet(payload: dict[str, Any]) -> str:
    lines = [
        "# Niles Album Review Packet v0",
        "",
        "Status:",
        f"- Packet status: `{payload['packet_status']}`.",
        "- Review only: `true`.",
        "- Album state confirmed: `false`.",
        "- Evidence sufficient for album status: `false`.",
        f"- Operator metadata consumed: `{str(payload['metadata_consumption']['metadata_consumed']).lower()}`.",
        f"- Metadata records consumed: `{payload['metadata_consumption']['metadata_record_count']}`.",
        f"- Evidence sufficient for review packet: `{str(payload['evidence_sufficient_for_review_packet']).lower()}`.",
        "- DAW automation added: `false`.",
        "- Audio file mutation added: `false`.",
        "- Runtime authority added: `false`.",
        "",
        "## Operator Metadata Review Items",
    ]
    if payload["operator_metadata_review_items"]:
        for item in payload["operator_metadata_review_items"]:
            lines.append(
                f"- `{item['item_id']}` {item['item_label']}: album={item.get('album_project_name') or '[unknown]'}; "
                f"song={item.get('song_title') or item.get('song_id_or_stable_operator_label') or '[unknown]'}; "
                f"track_status={item.get('track_status_label') or '[unknown]'}; "
                f"production_stage={item.get('production_stage_label') or '[unknown]'}; "
                f"confidence={item.get('confidence') or '[unknown]'}; evidence={item.get('evidence_status') or '[unknown]'}; "
                f"posture={item['metadata_evidence_posture']}."
            )
            if item["blocker_labels"]:
                lines.append(f"  - Blockers: {', '.join(item['blocker_labels'])}.")
            if item["next_safe_move_labels"]:
                lines.append(f"  - Next safe moves: {', '.join(item['next_safe_move_labels'])}.")
            if item["missing_or_unknown_fields"]:
                lines.append(f"  - Missing/unknown fields: {', '.join(item['missing_or_unknown_fields'])}.")
    else:
        lines.append("- None. Review packet remains blocked until governed operator metadata exists.")
    # Track roster — surface real data from governed CSV
    track_posture = payload.get("track_registry_posture", {})
    lines.extend(["", "## Track Roster (governed CSV metadata — not final audio truth)"])
    if track_posture.get("real_track_roster_available"):
        tc = track_posture["track_count"]
        ss = track_posture.get("status_summary", {})
        status_str = ", ".join(f"{v} {k}" for k, v in sorted(ss.items()))
        lines.append(f"- Source: `{track_posture.get('source_ref', 'niles_track_registry')}` | {tc} tracks | statuses: {status_str}")
        for row in track_posture.get("track_rows", []):
            title = row.get("title") or row.get("track_id") or "[unknown]"
            track_id = row.get("track_id") or ""
            status = row.get("status") or "[unknown]"
            next_step = row.get("next_step") or "[unknown]"
            target = row.get("target_week") or "[unknown]"
            lines.append(
                f"  - {track_id} | {title} | status={status} | next={next_step} | target_week={target}"
            )
    elif track_posture.get("source_missing_gap"):
        lines.append(f"- GAP: {track_posture['source_missing_gap']}")
    else:
        lines.append("- Track registry not available; run scripts/export_niles_track_registry_read_model.py first.")
    lines.extend([
        "",
        "## Confirmed Governed Evidence",
    ]
    )
    for item in payload["confirmed_governed_evidence"]:
        lines.append(f"- {item['label']} Source: `{item['source']}`; authority={item['authority_status']}.")
    lines.extend(["", "## Inferred / Desired, Not Confirmed Album State"])
    for item in payload["inferred_or_desired_album_workflow_evidence"]:
        lines.append(f"- {item['label']} Basis: {item['basis']}; confirmation required: `true`.")
    lines.extend(["", "## Stale / Legacy Evidence"])
    for item in payload["stale_or_legacy_evidence"]:
        lines.append(f"- {item['label']} Old files treated as evidence, not truth: `true`.")
    lines.extend(["", "## Missing Evidence"])
    for item in payload["missing_evidence"]:
        lines.append(f"- {item['label']} Needed for: {item['needed_for']}.")
    lines.extend(["", "## Blockers"])
    for blocker in payload["blockers"]:
        lines.append(
            f"- `{blocker['blocker_id']}` ({blocker['severity']}): {blocker['description']} Next: {blocker['next_safe_move']}"
        )
    lines.extend(["", "## Operator Confirmations Needed"])
    for item in payload["operator_confirmations_needed"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Next Safe Moves"])
    for item in payload["next_safe_moves"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Authority Boundary"])
    for key, value in payload["authority_boundary"].items():
        lines.append(f"- `{key}` = `{str(value).lower()}`")
    lines.extend(["", "## Source Evidence"])
    for source in payload["source_evidence"]:
        lines.append(
            f"- `{source['source_path']}` present=`{str(source['source_present']).lower()}` role={source['source_role']} truth={source['truth_status']}"
        )
    lines.extend(["", "## Next Recommended Lane", f"- {payload['next_recommended_lane']}", ""])
    return '\n'.join(lines)


def export_niles_album_review_packet(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> NilesAlbumReviewPacketResult:
    payload = build_niles_album_review_packet(repo_root=repo_root, generated_at=generated_at)
    root = _rooted(export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_niles_album_review_packet(payload), encoding="utf-8")
    return NilesAlbumReviewPacketResult(
        schema_version=SCHEMA_VERSION,
        packet_status=payload["packet_status"],
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        confirmed_evidence_count=payload["source_summary"]["confirmed_evidence_source_count"],
        missing_evidence_count=payload["source_summary"]["missing_evidence_source_count"],
        blocker_count=len(payload["blockers"]),
        daw_automation_added=False,
        audio_file_mutation_added=False,
        runtime_authority_added=False,
        send_or_submit_authority_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Niles album review packet from governed evidence.")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_niles_album_review_packet(repo_root=args.repo_root, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        payload = build_niles_album_review_packet(repo_root=args.repo_root)
        print(format_niles_album_review_packet(payload), end="")
    return 0


__all__ = [
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_niles_album_review_packet",
    "export_niles_album_review_packet",
    "format_niles_album_review_packet",
    "main",
]
