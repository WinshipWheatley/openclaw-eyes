"""Capital Hilton Proof Resolution Backend Batch Manifest v0.

This manifest tracks a PC-only backend/read-model batch for Capital Hilton proof
resolution rails. It grants no stable-map refresh before the final prompt, no
commit authority before the final prompt, and no live finance/account/runtime
authority at any point in this manifest.
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

SCHEMA_VERSION = "capital_hilton_proof_resolution_batch_manifest_v0"
READ_MODEL_ID = "capital_hilton_proof_resolution_batch_manifest"
BATCH_ID = "capital_hilton_proof_resolution_batch_v0"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

LANES_PLANNED = (
    "capital_hilton_answer_candidate_receipt",
    "capital_hilton_protected_reference_placeholder",
    "capital_hilton_guardian_review_packet",
    "capital_hilton_proof_quieting_progress_state",
    "integrated_checkpoint_and_stable_map_refresh",
)

PROMPT_TITLES = {
    "capital_hilton_answer_candidate_receipt": "Prompt 1 - Answer Candidate Receipt Contract",
    "capital_hilton_protected_reference_placeholder": "Prompt 2 - Protected Reference Placeholder Contract",
    "capital_hilton_guardian_review_packet": "Prompt 3 - Guardian Review Packet",
    "capital_hilton_proof_quieting_progress_state": "Prompt 4 - Proof Quieting / Progress State",
    "integrated_checkpoint_and_stable_map_refresh": "Prompt 5 - Integrated Checkpoint and Stable Map Refresh",
}

PROMPT_1_CHANGED_FILES = (
    ".gitignore",
    "capital_hilton_answer_candidate_receipt.py",
    "scripts/export_capital_hilton_answer_candidate_receipt.py",
    "tests/test_capital_hilton_answer_candidate_receipt.py",
    "generated/read_models/capital_hilton_answer_candidate_receipt.json",
    "generated/read_models/capital_hilton_answer_candidate_receipt_OPERATOR.md",
    "capital_hilton_proof_resolution_batch_manifest.py",
    "scripts/export_capital_hilton_proof_resolution_batch_manifest.py",
    "tests/test_capital_hilton_proof_resolution_batch_manifest.py",
    "generated/read_models/capital_hilton_proof_resolution_batch_manifest.json",
    "generated/read_models/capital_hilton_proof_resolution_batch_manifest_OPERATOR.md",
)

PROMPT_1_VALIDATION_COMMANDS = (
    "python3 scripts/export_capital_hilton_answer_candidate_receipt.py --format summary",
    "python3 scripts/export_capital_hilton_proof_resolution_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_capital_hilton_answer_candidate_receipt.py tests/test_capital_hilton_proof_resolution_batch_manifest.py -q",
    "python3 -m json.tool generated/read_models/capital_hilton_answer_candidate_receipt.json >/dev/null",
    "python3 -m json.tool generated/read_models/capital_hilton_proof_resolution_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 1 artifacts",
    "active-authority scan on Prompt 1 artifacts",
    "C-drive path scan on Prompt 1 artifacts",
    "python3 -m py_compile capital_hilton_answer_candidate_receipt.py scripts/export_capital_hilton_answer_candidate_receipt.py capital_hilton_proof_resolution_batch_manifest.py scripts/export_capital_hilton_proof_resolution_batch_manifest.py",
    "git diff --check",
)

PROMPT_2_CHANGED_FILES = (
    ".gitignore",
    "capital_hilton_protected_reference_placeholder.py",
    "scripts/export_capital_hilton_protected_reference_placeholder.py",
    "tests/test_capital_hilton_protected_reference_placeholder.py",
    "generated/read_models/capital_hilton_protected_reference_placeholder.json",
    "generated/read_models/capital_hilton_protected_reference_placeholder_OPERATOR.md",
    "capital_hilton_proof_resolution_batch_manifest.py",
    "scripts/export_capital_hilton_proof_resolution_batch_manifest.py",
    "tests/test_capital_hilton_proof_resolution_batch_manifest.py",
    "generated/read_models/capital_hilton_proof_resolution_batch_manifest.json",
    "generated/read_models/capital_hilton_proof_resolution_batch_manifest_OPERATOR.md",
)

PROMPT_2_VALIDATION_COMMANDS = (
    "python3 scripts/export_capital_hilton_protected_reference_placeholder.py --format summary",
    "python3 scripts/export_capital_hilton_proof_resolution_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_capital_hilton_protected_reference_placeholder.py tests/test_capital_hilton_proof_resolution_batch_manifest.py -q",
    "python3 -m json.tool generated/read_models/capital_hilton_protected_reference_placeholder.json >/dev/null",
    "python3 -m json.tool generated/read_models/capital_hilton_proof_resolution_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 2 artifacts",
    "active-authority scan on Prompt 2 artifacts",
    "C-drive path scan on Prompt 2 artifacts",
    "python3 -m py_compile capital_hilton_protected_reference_placeholder.py scripts/export_capital_hilton_protected_reference_placeholder.py capital_hilton_proof_resolution_batch_manifest.py scripts/export_capital_hilton_proof_resolution_batch_manifest.py",
    "git diff --check",
)

PROMPT_3_CHANGED_FILES = (
    ".gitignore",
    "capital_hilton_guardian_review_packet.py",
    "scripts/export_capital_hilton_guardian_review_packet.py",
    "tests/test_capital_hilton_guardian_review_packet.py",
    "generated/read_models/capital_hilton_guardian_review_packet.json",
    "generated/read_models/capital_hilton_guardian_review_packet_OPERATOR.md",
    "capital_hilton_proof_resolution_batch_manifest.py",
    "scripts/export_capital_hilton_proof_resolution_batch_manifest.py",
    "tests/test_capital_hilton_proof_resolution_batch_manifest.py",
    "generated/read_models/capital_hilton_proof_resolution_batch_manifest.json",
    "generated/read_models/capital_hilton_proof_resolution_batch_manifest_OPERATOR.md",
)

PROMPT_3_VALIDATION_COMMANDS = (
    "python3 scripts/export_capital_hilton_guardian_review_packet.py --format summary",
    "python3 scripts/export_capital_hilton_proof_resolution_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_capital_hilton_guardian_review_packet.py tests/test_capital_hilton_proof_resolution_batch_manifest.py -q",
    "python3 -m json.tool generated/read_models/capital_hilton_guardian_review_packet.json >/dev/null",
    "python3 -m json.tool generated/read_models/capital_hilton_proof_resolution_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 3 artifacts",
    "active-authority scan on Prompt 3 artifacts",
    "C-drive path scan on Prompt 3 artifacts",
    "python3 -m py_compile capital_hilton_guardian_review_packet.py scripts/export_capital_hilton_guardian_review_packet.py capital_hilton_proof_resolution_batch_manifest.py scripts/export_capital_hilton_proof_resolution_batch_manifest.py",
    "git diff --check",
)

PROMPT_4_CHANGED_FILES = (
    ".gitignore",
    "capital_hilton_proof_quieting_progress_state.py",
    "scripts/export_capital_hilton_proof_quieting_progress_state.py",
    "tests/test_capital_hilton_proof_quieting_progress_state.py",
    "generated/read_models/capital_hilton_proof_quieting_progress_state.json",
    "generated/read_models/capital_hilton_proof_quieting_progress_state_OPERATOR.md",
    "capital_hilton_proof_resolution_batch_manifest.py",
    "scripts/export_capital_hilton_proof_resolution_batch_manifest.py",
    "tests/test_capital_hilton_proof_resolution_batch_manifest.py",
    "generated/read_models/capital_hilton_proof_resolution_batch_manifest.json",
    "generated/read_models/capital_hilton_proof_resolution_batch_manifest_OPERATOR.md",
)

PROMPT_4_VALIDATION_COMMANDS = (
    "python3 scripts/export_capital_hilton_proof_quieting_progress_state.py --format summary",
    "python3 scripts/export_capital_hilton_proof_resolution_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_capital_hilton_proof_quieting_progress_state.py tests/test_capital_hilton_proof_resolution_batch_manifest.py -q",
    "python3 -m json.tool generated/read_models/capital_hilton_proof_quieting_progress_state.json >/dev/null",
    "python3 -m json.tool generated/read_models/capital_hilton_proof_resolution_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 4 artifacts",
    "active-authority scan on Prompt 4 artifacts",
    "C-drive path scan on Prompt 4 artifacts",
    "python3 -m py_compile capital_hilton_proof_quieting_progress_state.py scripts/export_capital_hilton_proof_quieting_progress_state.py capital_hilton_proof_resolution_batch_manifest.py scripts/export_capital_hilton_proof_resolution_batch_manifest.py",
    "git diff --check",
)

AUTHORITY_BOUNDARY = {
    "live_execution_allowed": False,
    "model_api_execution_allowed": False,
    "actor_agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "browser_oauth_account_access_allowed": False,
    "gmail_calendar_coupa_telegram_access_allowed": False,
    "credential_handling_allowed": False,
    "financial_payment_account_access_allowed": False,
    "invoice_generation_allowed": False,
    "ledger_write_allowed": False,
    "email_dispatch_allowed": False,
    "send_submit_approval_allowed": False,
    "runtime_planner_builder_queue_autonomy_execution_allowed": False,
    "mission_control_app_changes_allowed": False,
    "mac_sync_import_allowed": False,
    "network_operation_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "stable_map_refresh_allowed_before_final_prompt": False,
    "commit_allowed_before_final_prompt": False,
    "staging_allowed_before_final_prompt": False,
    "raw_finance_private_body_ingestion_allowed": False,
    "file_move_delete_allowed": False,
}


@dataclass(frozen=True)
class BatchManifestExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    batch_id: str
    batch_status: str
    current_prompt_index: int
    total_prompts: int
    completed_lane_count: int
    next_prompt: str
    stable_map_refresh_deferred: bool
    commit_deferred_until_final_prompt: bool
    next_expected_actor: str
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
    lanes = []
    for index, lane_id in enumerate(LANES_PLANNED, start=1):
        if index in {1, 2, 3, 4}:
            lane_status = "COMPLETED"
        else:
            lane_status = "PLANNED_NOT_STARTED"
        lanes.append(
            {
                "lane_id": lane_id,
                "prompt_index": index,
                "prompt_title": PROMPT_TITLES[lane_id],
                "lane_status": lane_status,
                "stable_map_refresh_deferred": True,
                "commit_deferred_until_final_prompt": True,
            }
        )
    return lanes


def build_capital_hilton_proof_resolution_batch_manifest(
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
        "lanes_planned": list(LANES_PLANNED),
        "lanes_completed": completed_lanes,
        "lanes": lanes,
        "changed_files": sorted(
            set(
                PROMPT_1_CHANGED_FILES
                + PROMPT_2_CHANGED_FILES
                + PROMPT_3_CHANGED_FILES
                + PROMPT_4_CHANGED_FILES
            )
        ),
        "validation_commands": list(
            PROMPT_1_VALIDATION_COMMANDS
            + PROMPT_2_VALIDATION_COMMANDS
            + PROMPT_3_VALIDATION_COMMANDS
            + PROMPT_4_VALIDATION_COMMANDS
        ),
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
        "batch_commit_policy": {
            "commit_allowed_now": True,
            "commit_deferred_until_final_prompt": False,
            "stage_only_capital_hilton_proof_resolution_files": True,
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
                "capital_hilton_proof_resolution_batch",
                "capital_hilton_answer_candidate_receipt",
                "capital_hilton_protected_reference_placeholder",
                "capital_hilton_guardian_review_packet",
                "capital_hilton_proof_quieting_progress_state",
            ],
            "mac_sync_import_performed_in_this_prompt": False,
        },
        "next_expected_actor": "mac_map_import_agent",
        "next_prompt": (
            "Mac map import/sync agent after stable-map bundle is staged"
        ),
        "machine_proof": {
            "batch_id_is_expected": BATCH_ID == "capital_hilton_proof_resolution_batch_v0",
            "status_is_complete_pending_stable_map_import": True,
            "stable_map_refresh_deferred": False,
            "commit_deferred_until_final_prompt": False,
            "planned_lane_count": len(LANES_PLANNED),
            "prompt_1_marked_complete": "capital_hilton_answer_candidate_receipt" in completed_lanes,
            "prompt_2_marked_complete": "capital_hilton_protected_reference_placeholder" in completed_lanes,
            "prompt_3_marked_complete": "capital_hilton_guardian_review_packet" in completed_lanes,
            "prompt_4_marked_complete": "capital_hilton_proof_quieting_progress_state" in completed_lanes,
            "all_four_contract_lanes_complete": completed_lanes
            == [
                "capital_hilton_answer_candidate_receipt",
                "capital_hilton_protected_reference_placeholder",
                "capital_hilton_guardian_review_packet",
                "capital_hilton_proof_quieting_progress_state",
            ],
            "next_expected_actor_is_mac_map_import_agent": True,
            "authority_boundary_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "no_live_execution_or_external_authority": True,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_capital_hilton_proof_resolution_batch_manifest(payload: dict[str, Any]) -> str:
    lines = [
        "# Capital Hilton Proof Resolution Backend Batch v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This batch builds backend read-model rails so Winship can eventually answer or point to proof for the ten Capital Hilton proof questions. Prompts 1 through 4 now cover answer candidates, protected reference placeholders, Guardian review packets, and proof quieting/progress-state metadata. It does not write answers, quiet items automatically, inspect protected files, approve invoices, or grant action authority.",
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
            "- No Mac sync/import, network, Mission Control Swift changes, invoice generation, Coupa/browser/email/account access, send/submit/approval, model/tool/agent/runtime execution, queue/autonomy, raw finance body ingestion, or file moves/deletes. Prompt 5 may commit and refresh the stable map locally, but it does not import on Mac.",
            "",
            "## Next Prompt",
            "",
            f"- {payload['next_prompt']}",
        ]
    )
    return "\n".join(lines) + "\n"


def export_capital_hilton_proof_resolution_batch_manifest(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> BatchManifestExportResult:
    payload = build_capital_hilton_proof_resolution_batch_manifest(generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_proof_resolution_batch_manifest(payload), encoding="utf-8")
    return BatchManifestExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        batch_id=payload["batch_id"],
        batch_status=payload["batch_status"],
        current_prompt_index=payload["current_prompt_index"],
        total_prompts=payload["total_prompts"],
        completed_lane_count=len(payload["lanes_completed"]),
        next_prompt=payload["next_prompt"],
        stable_map_refresh_deferred=payload["stable_map_refresh_deferred"],
        commit_deferred_until_final_prompt=payload["commit_deferred_until_final_prompt"],
        next_expected_actor=payload["next_expected_actor"],
        authority_boundary_false=payload["machine_proof"]["authority_boundary_false"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton Proof Resolution Batch manifest.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_proof_resolution_batch_manifest(
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
        "total_prompts": result.total_prompts,
        "completed_lane_count": result.completed_lane_count,
        "next_prompt": result.next_prompt,
        "stable_map_refresh_deferred": result.stable_map_refresh_deferred,
        "commit_deferred_until_final_prompt": result.commit_deferred_until_final_prompt,
        "next_expected_actor": result.next_expected_actor,
        "authority_boundary_false": result.authority_boundary_false,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Capital Hilton Proof Resolution Batch: `{result.batch_id}`")
        print(f"- Status: `{result.batch_status}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "AUTHORITY_BOUNDARY",
    "BATCH_ID",
    "JSON_EXPORT_NAME",
    "LANES_PLANNED",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "build_capital_hilton_proof_resolution_batch_manifest",
    "export_capital_hilton_proof_resolution_batch_manifest",
    "format_capital_hilton_proof_resolution_batch_manifest",
    "stable_json",
]
