"""OpenClaw Work Terrain Reconciliation Batch Manifest v0.

This manifest tracks a PC-only backend/read-model batch for reconciling
OpenClaw work terrain. It defers commits and stable-map refresh until the final
prompt and grants no raw-body, private-root, mutation, runtime, network, or
Mac-sync authority.
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

SCHEMA_VERSION = "openclaw_work_terrain_reconciliation_batch_manifest_v0"
READ_MODEL_ID = "openclaw_work_terrain_reconciliation_batch_manifest"
BATCH_ID = "openclaw_work_terrain_reconciliation_v0"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

PLANNED_LANES = (
    "work_terrain_query_contract",
    "work_terrain_relationship_index",
    "work_terrain_classification_staleness_candidate",
    "work_terrain_gap_detector",
    "integrated_checkpoint_and_stable_map_refresh",
)

PROMPT_TITLES = {
    "work_terrain_query_contract": "Prompt 1 - Work Terrain Query Contract",
    "work_terrain_relationship_index": "Prompt 2 - Work Terrain Relationship Index",
    "work_terrain_classification_staleness_candidate": (
        "Prompt 3 - Work Terrain Classification / Staleness Candidate"
    ),
    "work_terrain_gap_detector": "Prompt 4 - Work Terrain Gap Detector",
    "integrated_checkpoint_and_stable_map_refresh": "Prompt 5 - Integrated Checkpoint and Stable Map Refresh",
}

PROMPT_1_CHANGED_FILES = (
    ".gitignore",
    "openclaw_work_terrain_query_contract.py",
    "scripts/export_openclaw_work_terrain_query_contract.py",
    "tests/test_openclaw_work_terrain_query_contract.py",
    "generated/read_models/openclaw_work_terrain_query_contract.json",
    "generated/read_models/openclaw_work_terrain_query_contract_OPERATOR.md",
    "openclaw_work_terrain_reconciliation_batch_manifest.py",
    "scripts/export_openclaw_work_terrain_reconciliation_batch_manifest.py",
    "tests/test_openclaw_work_terrain_reconciliation_batch_manifest.py",
    "generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest.json",
    "generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest_OPERATOR.md",
)

PROMPT_1_VALIDATION_COMMANDS = (
    "python3 scripts/export_openclaw_work_terrain_query_contract.py --format summary",
    "python3 scripts/export_openclaw_work_terrain_reconciliation_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_openclaw_work_terrain_query_contract.py tests/test_openclaw_work_terrain_reconciliation_batch_manifest.py -q",
    "python3 -m json.tool generated/read_models/openclaw_work_terrain_query_contract.json >/dev/null",
    "python3 -m json.tool generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 1 artifacts",
    "active-authority scan on Prompt 1 artifacts",
    "C-drive path scan on Prompt 1 artifacts",
    "python3 -m py_compile openclaw_work_terrain_query_contract.py scripts/export_openclaw_work_terrain_query_contract.py openclaw_work_terrain_reconciliation_batch_manifest.py scripts/export_openclaw_work_terrain_reconciliation_batch_manifest.py",
    "git diff --check",
)

PROMPT_2_CHANGED_FILES = (
    ".gitignore",
    "openclaw_work_terrain_relationship_index.py",
    "scripts/export_openclaw_work_terrain_relationship_index.py",
    "tests/test_openclaw_work_terrain_relationship_index.py",
    "generated/read_models/openclaw_work_terrain_relationship_index.json",
    "generated/read_models/openclaw_work_terrain_relationship_index_OPERATOR.md",
    "openclaw_work_terrain_reconciliation_batch_manifest.py",
    "scripts/export_openclaw_work_terrain_reconciliation_batch_manifest.py",
    "tests/test_openclaw_work_terrain_reconciliation_batch_manifest.py",
    "generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest.json",
    "generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest_OPERATOR.md",
)

PROMPT_2_VALIDATION_COMMANDS = (
    "python3 scripts/export_openclaw_work_terrain_relationship_index.py --format summary",
    "python3 scripts/export_openclaw_work_terrain_reconciliation_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_openclaw_work_terrain_relationship_index.py tests/test_openclaw_work_terrain_reconciliation_batch_manifest.py -q",
    "python3 -m pytest tests/test_openclaw_work_terrain_query_contract.py -q",
    "python3 -m json.tool generated/read_models/openclaw_work_terrain_relationship_index.json >/dev/null",
    "python3 -m json.tool generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 2 artifacts",
    "active-authority scan on Prompt 2 artifacts",
    "C-drive path scan on Prompt 2 artifacts",
    "python3 -m py_compile openclaw_work_terrain_relationship_index.py scripts/export_openclaw_work_terrain_relationship_index.py openclaw_work_terrain_reconciliation_batch_manifest.py scripts/export_openclaw_work_terrain_reconciliation_batch_manifest.py",
    "git diff --check",
)

PROMPT_3_CHANGED_FILES = (
    ".gitignore",
    "openclaw_work_terrain_classification_candidate.py",
    "scripts/export_openclaw_work_terrain_classification_candidate.py",
    "tests/test_openclaw_work_terrain_classification_candidate.py",
    "generated/read_models/openclaw_work_terrain_classification_candidate.json",
    "generated/read_models/openclaw_work_terrain_classification_candidate_OPERATOR.md",
    "openclaw_work_terrain_reconciliation_batch_manifest.py",
    "scripts/export_openclaw_work_terrain_reconciliation_batch_manifest.py",
    "tests/test_openclaw_work_terrain_reconciliation_batch_manifest.py",
    "generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest.json",
    "generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest_OPERATOR.md",
)

PROMPT_3_VALIDATION_COMMANDS = (
    "python3 scripts/export_openclaw_work_terrain_classification_candidate.py --format summary",
    "python3 scripts/export_openclaw_work_terrain_reconciliation_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_openclaw_work_terrain_classification_candidate.py tests/test_openclaw_work_terrain_reconciliation_batch_manifest.py -q",
    "python3 -m pytest tests/test_openclaw_work_terrain_query_contract.py tests/test_openclaw_work_terrain_relationship_index.py -q",
    "python3 -m json.tool generated/read_models/openclaw_work_terrain_classification_candidate.json >/dev/null",
    "python3 -m json.tool generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 3 artifacts",
    "active-authority scan on Prompt 3 artifacts",
    "C-drive path scan on Prompt 3 artifacts",
    "python3 -m py_compile openclaw_work_terrain_classification_candidate.py scripts/export_openclaw_work_terrain_classification_candidate.py openclaw_work_terrain_reconciliation_batch_manifest.py scripts/export_openclaw_work_terrain_reconciliation_batch_manifest.py",
    "git diff --check",
)

PROMPT_4_CHANGED_FILES = (
    ".gitignore",
    "openclaw_work_terrain_gap_detector.py",
    "scripts/export_openclaw_work_terrain_gap_detector.py",
    "tests/test_openclaw_work_terrain_gap_detector.py",
    "generated/read_models/openclaw_work_terrain_gap_detector.json",
    "generated/read_models/openclaw_work_terrain_gap_detector_OPERATOR.md",
    "openclaw_work_terrain_reconciliation_batch_manifest.py",
    "scripts/export_openclaw_work_terrain_reconciliation_batch_manifest.py",
    "tests/test_openclaw_work_terrain_reconciliation_batch_manifest.py",
    "generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest.json",
    "generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest_OPERATOR.md",
)

PROMPT_4_VALIDATION_COMMANDS = (
    "python3 scripts/export_openclaw_work_terrain_gap_detector.py --format summary",
    "python3 scripts/export_openclaw_work_terrain_reconciliation_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_openclaw_work_terrain_gap_detector.py tests/test_openclaw_work_terrain_reconciliation_batch_manifest.py -q",
    "python3 -m pytest tests/test_openclaw_work_terrain_query_contract.py tests/test_openclaw_work_terrain_relationship_index.py tests/test_openclaw_work_terrain_classification_candidate.py -q",
    "python3 -m json.tool generated/read_models/openclaw_work_terrain_gap_detector.json >/dev/null",
    "python3 -m json.tool generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 4 artifacts",
    "active-authority scan on Prompt 4 artifacts",
    "C-drive path scan on Prompt 4 artifacts",
    "python3 -m py_compile openclaw_work_terrain_gap_detector.py scripts/export_openclaw_work_terrain_gap_detector.py openclaw_work_terrain_reconciliation_batch_manifest.py scripts/export_openclaw_work_terrain_reconciliation_batch_manifest.py",
    "git diff --check",
)

AUTHORITY_BOUNDARY = {
    "commit_allowed": False,
    "staging_allowed": False,
    "stable_map_refresh_allowed": False,
    "mac_sync_import_allowed": False,
    "broad_raw_body_ingestion_allowed": False,
    "broad_private_root_scan_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "file_rename_allowed": False,
    "file_rewrite_allowed": False,
    "file_archive_allowed": False,
    "vector_indexing_allowed": False,
    "model_api_execution_allowed": False,
    "actor_agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "planner_builder_queue_autonomy_allowed": False,
    "network_operation_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "mission_control_swift_change_allowed": False,
    "c_drive_scan_or_artifact_write_allowed": False,
    "credential_account_browser_email_coupa_access_allowed": False,
    "authority_escalation_allowed": False,
}


@dataclass(frozen=True)
class WorkTerrainBatchManifestExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    batch_id: str
    batch_status: str
    current_prompt_index: int
    planned_lane_count: int
    completed_lane_count: int
    next_prompt: str
    next_expected_actor: str
    stable_map_refresh_deferred: bool
    commit_deferred_until_final_prompt: bool
    authority_boundary_false: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _lanes() -> list[dict[str, Any]]:
    lanes: list[dict[str, Any]] = []
    for index, lane_id in enumerate(PLANNED_LANES, start=1):
        lane_status = "COMPLETED" if index <= 4 else "PLANNED_NOT_STARTED"
        lanes.append(
            {
                "lane_id": lane_id,
                "prompt_index": index,
                "prompt_title": PROMPT_TITLES[lane_id],
                "lane_status": lane_status,
                "stable_map_refresh_deferred": False,
                "commit_deferred_until_final_prompt": False,
            }
        )
    return lanes


def build_openclaw_work_terrain_reconciliation_batch_manifest(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    lanes = _lanes()
    completed_lanes = [lane["lane_id"] for lane in lanes if lane["lane_status"] == "COMPLETED"]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "batch_id": BATCH_ID,
        "generated_at": generated_at or utc_now(),
        "batch_status": "COMPLETE_PENDING_STABLE_MAP_IMPORT",
        "stable_map_refresh_deferred": False,
        "commit_deferred_until_final_prompt": False,
        "current_prompt_index": 5,
        "total_prompts": 5,
        "planned_lanes": list(PLANNED_LANES),
        "lanes_planned": list(PLANNED_LANES),
        "lanes_completed": completed_lanes,
        "lanes": lanes,
        "changed_files": sorted(
            set(PROMPT_1_CHANGED_FILES)
            | set(PROMPT_2_CHANGED_FILES)
            | set(PROMPT_3_CHANGED_FILES)
            | set(PROMPT_4_CHANGED_FILES)
        ),
        "validation_commands": (
            list(PROMPT_1_VALIDATION_COMMANDS)
            + list(PROMPT_2_VALIDATION_COMMANDS)
            + list(PROMPT_3_VALIDATION_COMMANDS)
            + list(PROMPT_4_VALIDATION_COMMANDS)
        ),
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
        "batch_commit_policy": {
            "commit_allowed_now": True,
            "commit_deferred_until_final_prompt": False,
            "stage_only_work_terrain_reconciliation_files": True,
            "final_prompt_handles_integrated_checkpoint": True,
        },
        "stable_map_refresh_policy": {
            "stable_map_refresh_allowed_now": True,
            "stable_map_refresh_deferred": False,
            "final_prompt_handles_single_stable_map_refresh": True,
        },
        "final_stable_map_refresh_requirement": {
            "required": True,
            "summaries_required": [
                "openclaw_work_terrain_reconciliation_batch",
                "openclaw_work_terrain_query_contract",
                "openclaw_work_terrain_relationship_index",
                "openclaw_work_terrain_classification_candidate",
                "openclaw_work_terrain_gap_detector",
            ],
            "preserve_capital_hilton_proof_resolution_summaries": True,
            "mac_sync_import_performed_in_this_prompt": False,
        },
        "next_expected_actor": "mac_map_import_agent",
        "next_prompt": (
            "Mac map import/sync agent after stable-map bundle is staged"
        ),
        "machine_proof": {
            "batch_id_is_expected": BATCH_ID == "openclaw_work_terrain_reconciliation_v0",
            "status_is_complete_pending_stable_map_import": True,
            "stable_map_refresh_deferred": False,
            "commit_deferred_until_final_prompt": False,
            "planned_lane_count": len(PLANNED_LANES),
            "prompt_1_marked_complete": "work_terrain_query_contract" in completed_lanes,
            "prompt_2_marked_complete": "work_terrain_relationship_index" in completed_lanes,
            "prompt_3_marked_complete": "work_terrain_classification_staleness_candidate" in completed_lanes,
            "prompt_4_marked_complete": "work_terrain_gap_detector" in completed_lanes,
            "all_four_contract_lanes_complete": completed_lanes
            == [
                "work_terrain_query_contract",
                "work_terrain_relationship_index",
                "work_terrain_classification_staleness_candidate",
                "work_terrain_gap_detector",
            ],
            "next_expected_actor_is_mac_map_import_agent": True,
            "authority_boundary_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_openclaw_work_terrain_reconciliation_batch_manifest(payload: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Work Terrain Reconciliation Batch v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This batch builds the backend read-model rails for asking focused questions about OpenClaw's work terrain before any cleanup, archive operation, or Mac import. Prompt 1 added the query grammar; Prompt 2 added metadata-only relationship records; Prompt 3 added classification/staleness candidates; Prompt 4 adds review-only gap detection with negative filters and built-status validation.",
        "",
        "## Batch Status",
        "",
        f"- Batch id: `{payload['batch_id']}`",
        f"- Status: `{payload['batch_status']}`",
        f"- Current prompt: `{payload['current_prompt_index']}` of `{payload['total_prompts']}`",
        f"- Stable-map refresh deferred: `{str(payload['stable_map_refresh_deferred']).lower()}`",
        f"- Commit deferred until final prompt: `{str(payload['commit_deferred_until_final_prompt']).lower()}`",
        f"- Next expected actor: `{payload['next_expected_actor']}`",
        "",
        "## Lanes",
        "",
    ]
    for lane in payload["lanes"]:
        lines.append(f"- `{lane['lane_id']}`: `{lane['lane_status']}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Metadata-first only. No Mac sync/import, broad raw body ingestion, broad private-root scan, file moves/deletes/renames/rewrites/archive actions, AI semantic review, automatic truth promotion, vector indexing, model/tool/agent/runtime execution, network, git push/pull/fetch, Mission Control Swift changes, C-drive scanning, credential/account/browser/email/Coupa access, or authority escalation.",
            "",
            "## Next Prompt",
            "",
            f"- {payload['next_prompt']}",
        ]
    )
    return "\n".join(lines) + "\n"


def export_openclaw_work_terrain_reconciliation_batch_manifest(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> WorkTerrainBatchManifestExportResult:
    payload = build_openclaw_work_terrain_reconciliation_batch_manifest(generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_openclaw_work_terrain_reconciliation_batch_manifest(payload), encoding="utf-8")
    return WorkTerrainBatchManifestExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        batch_id=payload["batch_id"],
        batch_status=payload["batch_status"],
        current_prompt_index=payload["current_prompt_index"],
        planned_lane_count=len(payload["planned_lanes"]),
        completed_lane_count=len(payload["lanes_completed"]),
        next_prompt=payload["next_prompt"],
        next_expected_actor=payload["next_expected_actor"],
        stable_map_refresh_deferred=payload["stable_map_refresh_deferred"],
        commit_deferred_until_final_prompt=payload["commit_deferred_until_final_prompt"],
        authority_boundary_false=payload["machine_proof"]["authority_boundary_false"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export OpenClaw Work Terrain Reconciliation Batch manifest.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_openclaw_work_terrain_reconciliation_batch_manifest(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "batch_id": result.batch_id,
        "batch_status": result.batch_status,
        "current_prompt_index": result.current_prompt_index,
        "planned_lane_count": result.planned_lane_count,
        "completed_lane_count": result.completed_lane_count,
        "next_prompt": result.next_prompt,
        "next_expected_actor": result.next_expected_actor,
        "stable_map_refresh_deferred": result.stable_map_refresh_deferred,
        "commit_deferred_until_final_prompt": result.commit_deferred_until_final_prompt,
        "authority_boundary_false": result.authority_boundary_false,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"OpenClaw Work Terrain Reconciliation Batch: `{result.batch_id}`")
        print(f"- Status: `{result.batch_status}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "AUTHORITY_BOUNDARY",
    "BATCH_ID",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "PLANNED_LANES",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "build_openclaw_work_terrain_reconciliation_batch_manifest",
    "export_openclaw_work_terrain_reconciliation_batch_manifest",
    "format_openclaw_work_terrain_reconciliation_batch_manifest",
    "stable_json",
]
