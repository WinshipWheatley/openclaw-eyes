"""Post-Security Governance Batch Manifest v0.

This read-model records a PC-only governance batch plan. It is deterministic
batch metadata only: no stable-map refresh, commit, staging, Mac sync/import,
network, runtime, planner/builder, queue/autonomy, tool, model, agent, account,
financial, payment, marketplace, or Mission Control authority is created here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "post_security_governance_batch_manifest_v0"
READ_MODEL_ID = "post_security_governance_batch_manifest"
BATCH_ID = "post_security_governance_batch_v0"
BATCH_STATUS = "COMPLETE_PENDING_STABLE_MAP_IMPORT"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

LANES_PLANNED = (
    "parked_autonomous_capital_pipeline_experiment",
    "security_delta_review_contract",
    "operator_attention_promotion_contract",
    "chief_test_harness_cross_off_receipt_contract",
    "integrated_checkpoint_and_stable_map_refresh",
)

PROMPT_TITLES = {
    "parked_autonomous_capital_pipeline_experiment": "Prompt 1 - Batch Manifest + Parked R&D Experiment",
    "security_delta_review_contract": "Prompt 2 - Security Delta Review Contract",
    "operator_attention_promotion_contract": "Prompt 3 - Operator Attention Promotion Contract",
    "chief_test_harness_cross_off_receipt_contract": "Prompt 4 - Chief Test Harness / Cross-Off Receipt Contract",
    "integrated_checkpoint_and_stable_map_refresh": "Prompt 5 - Integrated Checkpoint and Stable Map Refresh",
}

PROMPT_1_CHANGED_FILES = (
    ".gitignore",
    "parked_autonomous_capital_pipeline_experiment.py",
    "scripts/export_parked_autonomous_capital_pipeline_experiment.py",
    "tests/test_parked_autonomous_capital_pipeline_experiment.py",
    "generated/read_models/parked_autonomous_capital_pipeline_experiment.json",
    "generated/read_models/parked_autonomous_capital_pipeline_experiment_OPERATOR.md",
    "post_security_governance_batch_manifest.py",
    "scripts/export_post_security_governance_batch_manifest.py",
    "tests/test_post_security_governance_batch_manifest.py",
    "generated/read_models/post_security_governance_batch_manifest.json",
    "generated/read_models/post_security_governance_batch_manifest_OPERATOR.md",
)

PROMPT_2_CHANGED_FILES = (
    ".gitignore",
    "security_delta_review_contract.py",
    "scripts/export_security_delta_review_contract.py",
    "tests/test_security_delta_review_contract.py",
    "generated/read_models/security_delta_review_contract.json",
    "generated/read_models/security_delta_review_contract_OPERATOR.md",
    "post_security_governance_batch_manifest.py",
    "scripts/export_post_security_governance_batch_manifest.py",
    "tests/test_post_security_governance_batch_manifest.py",
    "generated/read_models/post_security_governance_batch_manifest.json",
    "generated/read_models/post_security_governance_batch_manifest_OPERATOR.md",
)

PROMPT_3_CHANGED_FILES = (
    ".gitignore",
    "operator_attention_promotion_contract.py",
    "scripts/export_operator_attention_promotion_contract.py",
    "tests/test_operator_attention_promotion_contract.py",
    "generated/read_models/operator_attention_promotion_contract.json",
    "generated/read_models/operator_attention_promotion_contract_OPERATOR.md",
    "post_security_governance_batch_manifest.py",
    "scripts/export_post_security_governance_batch_manifest.py",
    "tests/test_post_security_governance_batch_manifest.py",
    "generated/read_models/post_security_governance_batch_manifest.json",
    "generated/read_models/post_security_governance_batch_manifest_OPERATOR.md",
)

PROMPT_4_CHANGED_FILES = (
    ".gitignore",
    "chief_test_harness_cross_off_receipt_contract.py",
    "scripts/export_chief_test_harness_cross_off_receipt_contract.py",
    "tests/test_chief_test_harness_cross_off_receipt_contract.py",
    "generated/read_models/chief_test_harness_cross_off_receipt_contract.json",
    "generated/read_models/chief_test_harness_cross_off_receipt_contract_OPERATOR.md",
    "post_security_governance_batch_manifest.py",
    "scripts/export_post_security_governance_batch_manifest.py",
    "tests/test_post_security_governance_batch_manifest.py",
    "generated/read_models/post_security_governance_batch_manifest.json",
    "generated/read_models/post_security_governance_batch_manifest_OPERATOR.md",
)

PROMPT_5_CHANGED_FILES = (
    "operator_map_bundle_contract.py",
    "tests/test_operator_map_bundle_contract.py",
    "generated/read_models/openclaw_map_snapshot.json",
    "generated/read_models/openclaw_map_manifest.json",
    "generated/read_models/openclaw_map_OPERATOR.md",
    "generated/read_models/operator_map_bundle_contract.json",
    "generated/read_models/operator_map_bundle_contract_OPERATOR.md",
    "generated/read_models/sync_health.json",
    "generated/read_models/sync_health_OPERATOR.md",
)

VALIDATION_COMMANDS = (
    "python3 scripts/export_parked_autonomous_capital_pipeline_experiment.py --format summary",
    "python3 scripts/export_post_security_governance_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_parked_autonomous_capital_pipeline_experiment.py tests/test_post_security_governance_batch_manifest.py -q",
    "python3 -m json.tool generated/read_models/parked_autonomous_capital_pipeline_experiment.json >/dev/null",
    "python3 -m json.tool generated/read_models/post_security_governance_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 1 artifacts",
    "active-authority scan on Prompt 1 artifacts",
    "C-drive path scan on Prompt 1 artifacts",
    "external URL scan on Prompt 1 artifacts",
    "python3 -m py_compile parked_autonomous_capital_pipeline_experiment.py scripts/export_parked_autonomous_capital_pipeline_experiment.py post_security_governance_batch_manifest.py scripts/export_post_security_governance_batch_manifest.py",
    "git diff --check",
)

PROMPT_2_VALIDATION_COMMANDS = (
    "python3 scripts/export_security_delta_review_contract.py --format summary",
    "python3 scripts/export_post_security_governance_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_security_delta_review_contract.py tests/test_post_security_governance_batch_manifest.py -q",
    "python3 -m json.tool generated/read_models/security_delta_review_contract.json >/dev/null",
    "python3 -m json.tool generated/read_models/post_security_governance_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 2 artifacts",
    "active-authority scan on Prompt 2 artifacts",
    "C-drive path scan on Prompt 2 artifacts",
    "python3 -m py_compile security_delta_review_contract.py scripts/export_security_delta_review_contract.py post_security_governance_batch_manifest.py scripts/export_post_security_governance_batch_manifest.py",
    "git diff --check",
)

PROMPT_3_VALIDATION_COMMANDS = (
    "python3 scripts/export_operator_attention_promotion_contract.py --format summary",
    "python3 scripts/export_post_security_governance_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_operator_attention_promotion_contract.py tests/test_post_security_governance_batch_manifest.py -q",
    "python3 -m json.tool generated/read_models/operator_attention_promotion_contract.json >/dev/null",
    "python3 -m json.tool generated/read_models/post_security_governance_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 3 artifacts",
    "active-authority scan on Prompt 3 artifacts",
    "C-drive path scan on Prompt 3 artifacts",
    "python3 -m py_compile operator_attention_promotion_contract.py scripts/export_operator_attention_promotion_contract.py post_security_governance_batch_manifest.py scripts/export_post_security_governance_batch_manifest.py",
    "git diff --check",
)

PROMPT_4_VALIDATION_COMMANDS = (
    "python3 scripts/export_chief_test_harness_cross_off_receipt_contract.py --format summary",
    "python3 scripts/export_post_security_governance_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_chief_test_harness_cross_off_receipt_contract.py tests/test_post_security_governance_batch_manifest.py -q",
    "python3 -m json.tool generated/read_models/chief_test_harness_cross_off_receipt_contract.json >/dev/null",
    "python3 -m json.tool generated/read_models/post_security_governance_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 4 artifacts",
    "active-authority scan on Prompt 4 artifacts",
    "C-drive path scan on Prompt 4 artifacts",
    "python3 -m py_compile chief_test_harness_cross_off_receipt_contract.py scripts/export_chief_test_harness_cross_off_receipt_contract.py post_security_governance_batch_manifest.py scripts/export_post_security_governance_batch_manifest.py",
    "git diff --check",
)

PROMPT_5_VALIDATION_COMMANDS = (
    "python3 scripts/export_operator_map_bundle.py --format summary",
    "python3 -m pytest tests/test_operator_map_bundle_contract.py -q",
    "JSON parse validation for stable map bundle and sync marker",
    "validate post-security governance batch summaries in stable map",
    "credential/secret scan on stable-map artifacts",
    "active-authority scan on stable-map artifacts",
    "C-drive path scan on stable-map artifacts",
    "git diff --check",
)

BATCH_AUTHORITY_BOUNDARY = {
    "live_execution_allowed": False,
    "model_api_execution_allowed": False,
    "actor_agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "browser_oauth_account_access_allowed": False,
    "financial_payment_account_access_allowed": False,
    "send_submit_approval_allowed": False,
    "runtime_planner_builder_queue_autonomy_execution_allowed": False,
    "mission_control_app_changes_allowed": False,
    "mac_sync_import_allowed": False,
    "network_operation_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "stable_map_refresh_allowed_before_prompt_5": False,
    "commit_allowed_before_prompt_5": False,
    "staging_allowed_before_prompt_5": False,
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
    planned_lane_count: int
    completed_lane_count: int
    next_prompt: str
    stable_map_refresh_deferred: bool
    commit_deferred_until_prompt_5: bool
    authority_boundary_false: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _generated_at(value: str | None) -> str:
    return value or datetime.now(timezone.utc).isoformat(timespec="seconds")


def _lanes() -> list[dict[str, Any]]:
    lanes: list[dict[str, Any]] = []
    for index, lane_id in enumerate(LANES_PLANNED, start=1):
        lanes.append(
            {
                "lane_id": lane_id,
                "prompt_index": index,
                "prompt_title": PROMPT_TITLES[lane_id],
                "lane_status": (
                    "COMPLETED_PROMPT_1"
                    if index == 1
                    else "COMPLETED_PROMPT_2"
                    if index == 2
                    else "COMPLETED_PROMPT_3"
                    if index == 3
                    else "COMPLETED_PROMPT_4"
                    if index == 4
                    else "COMPLETED_PROMPT_5_PENDING_MAC_IMPORT"
                    if index == 5
                    else "PLANNED_NOT_STARTED"
                ),
                "stable_map_refresh_deferred": True,
                "commit_deferred_until_prompt_5": True,
            }
        )
    return lanes


def _authority_boundary_false() -> bool:
    return all(value is False for value in BATCH_AUTHORITY_BOUNDARY.values())


def build_post_security_governance_batch_manifest(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    del repo_root
    lanes_planned = _lanes()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "batch_id": BATCH_ID,
        "batch_status": BATCH_STATUS,
        "generated_at": _generated_at(generated_at),
        "contract_type": "post_security_governance_batch_manifest",
        "current_prompt_index": 5,
        "total_prompts": 5,
        "stable_map_refresh_deferred": False,
        "commit_deferred_until_prompt_5": False,
        "staging_deferred_until_prompt_5": False,
        "lanes_planned": lanes_planned,
        "lanes_completed": [
            {
                "lane_id": "parked_autonomous_capital_pipeline_experiment",
                "completion_status": "PROMPT_1_EXPORT_VALIDATION_TARGET",
                "generated_read_models": [
                    "generated/read_models/parked_autonomous_capital_pipeline_experiment.json",
                    "generated/read_models/parked_autonomous_capital_pipeline_experiment_OPERATOR.md",
                ],
                "stable_map_refresh_deferred": True,
                "commit_deferred_until_prompt_5": True,
            },
            {
                "lane_id": "security_delta_review_contract",
                "completion_status": "PROMPT_2_EXPORT_VALIDATION_TARGET",
                "generated_read_models": [
                    "generated/read_models/security_delta_review_contract.json",
                    "generated/read_models/security_delta_review_contract_OPERATOR.md",
                ],
                "stable_map_refresh_deferred": True,
                "commit_deferred_until_prompt_5": True,
            },
            {
                "lane_id": "operator_attention_promotion_contract",
                "completion_status": "PROMPT_3_EXPORT_VALIDATION_TARGET",
                "generated_read_models": [
                    "generated/read_models/operator_attention_promotion_contract.json",
                    "generated/read_models/operator_attention_promotion_contract_OPERATOR.md",
                ],
                "stable_map_refresh_deferred": True,
                "commit_deferred_until_prompt_5": True,
            },
            {
                "lane_id": "chief_test_harness_cross_off_receipt_contract",
                "completion_status": "PROMPT_4_EXPORT_VALIDATION_TARGET",
                "generated_read_models": [
                    "generated/read_models/chief_test_harness_cross_off_receipt_contract.json",
                    "generated/read_models/chief_test_harness_cross_off_receipt_contract_OPERATOR.md",
                ],
                "stable_map_refresh_deferred": True,
                "commit_deferred_until_prompt_5": True,
            },
            {
                "lane_id": "integrated_checkpoint_and_stable_map_refresh",
                "completion_status": "PROMPT_5_BATCH_CLOSURE_PENDING_MAC_IMPORT",
                "generated_read_models": [
                    "generated/read_models/openclaw_map_snapshot.json",
                    "generated/read_models/openclaw_map_manifest.json",
                    "generated/read_models/openclaw_map_OPERATOR.md",
                ],
                "stable_map_refresh_deferred": False,
                "commit_deferred_until_prompt_5": False,
            },
        ],
        "changed_files": list(
            dict.fromkeys(
                (
                    *PROMPT_1_CHANGED_FILES,
                    *PROMPT_2_CHANGED_FILES,
                    *PROMPT_3_CHANGED_FILES,
                    *PROMPT_4_CHANGED_FILES,
                    *PROMPT_5_CHANGED_FILES,
                )
            )
        ),
        "validation_commands": list(
            dict.fromkeys(
                (
                    *VALIDATION_COMMANDS,
                    *PROMPT_2_VALIDATION_COMMANDS,
                    *PROMPT_3_VALIDATION_COMMANDS,
                    *PROMPT_4_VALIDATION_COMMANDS,
                    *PROMPT_5_VALIDATION_COMMANDS,
                )
            )
        ),
        "authority_boundary": dict(BATCH_AUTHORITY_BOUNDARY),
        "next_prompt": {
            "prompt_index": None,
            "lane_id": "mac_map_import_agent",
            "title": "Mac map import/sync agent",
        },
        "next_expected_actor": "mac_map_import_agent",
        "batch_commit_policy": {
            "commit_now_allowed": True,
            "stage_now_allowed": True,
            "commit_deferred_until_prompt_5": False,
            "final_commit_scope": "batch-related files only after Prompt 5 validation",
            "unrelated_dirty_files_policy": "do_not_stage_clean_reset_or_delete",
        },
        "stable_map_refresh_policy": {
            "refresh_now_allowed": True,
            "stable_map_refresh_deferred": False,
            "refresh_prompt_index": 5,
            "mac_import_now_allowed": False,
            "pc_readback_now_allowed": False,
            "stage_bundle_for_mac_import": True,
            "next_expected_actor": "mac_map_import_agent",
        },
        "final_stable_map_refresh_requirement": {
            "include_post_security_governance_batch_summary": True,
            "include_parked_autonomous_capital_pipeline_experiment_summary": True,
            "include_security_delta_review_summary": True,
            "include_operator_attention_promotion_summary": True,
            "include_chief_test_harness_cross_off_summary": True,
            "stage_for_mac_import": True,
            "mac_import_performed_by_this_prompt": False,
        },
        "machine_proof": {
            "batch_id_expected": BATCH_ID == "post_security_governance_batch_v0",
            "batch_status_expected": BATCH_STATUS == "COMPLETE_PENDING_STABLE_MAP_IMPORT",
            "planned_lane_count": len(lanes_planned),
            "prompt_1_lane_marked_complete": lanes_planned[0]["lane_status"] == "COMPLETED_PROMPT_1",
            "prompt_1_observed": True,
            "prompt_2_lane_marked_complete": lanes_planned[1]["lane_status"] == "COMPLETED_PROMPT_2",
            "prompt_2_observed": True,
            "prompt_3_lane_marked_complete": lanes_planned[2]["lane_status"] == "COMPLETED_PROMPT_3",
            "prompt_3_observed": True,
            "prompt_4_lane_marked_complete": lanes_planned[3]["lane_status"] == "COMPLETED_PROMPT_4",
            "prompt_4_observed": True,
            "prompt_5_lane_marked_complete_pending_mac_import": lanes_planned[4]["lane_status"] == "COMPLETED_PROMPT_5_PENDING_MAC_IMPORT",
            "stable_map_refresh_deferred_until_prompt_5": False,
            "commit_deferred_until_prompt_5": False,
            "staging_deferred_until_prompt_5": False,
            "next_expected_actor_is_mac_map_import_agent": True,
            "authority_boundary_all_false": _authority_boundary_false(),
            "live_authority_created": False,
            "stable_map_refresh_required": True,
            "mac_import_performed": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    proof = payload["machine_proof"]
    lines = [
        "# Post-Security Governance Batch Manifest v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This closes the PC-only governance batch. Prompt 1 preserved the parked autonomous capital R&D experiment. Prompt 2 added the Security Delta Review Contract. Prompt 3 added the Operator Attention Promotion Contract. Prompt 4 added the Chief Test Harness / Cross-Off Receipt Contract. Prompt 5 validates and checkpoints the batch, refreshes the stable map once, stages the bundle for Mac import, and leaves actual Mac import to `mac_map_import_agent`.",
        "",
        "## Batch Status",
        "",
        f"- Batch id: `{payload['batch_id']}`.",
        f"- Status: `{payload['batch_status']}`.",
        f"- Current prompt: `{payload['current_prompt_index']}` of `{payload['total_prompts']}`.",
        f"- Stable-map refresh deferred: `{str(payload['stable_map_refresh_deferred']).lower()}`.",
        f"- Commit deferred until Prompt 5: `{str(payload['commit_deferred_until_prompt_5']).lower()}`.",
        f"- Next expected actor: `{payload['next_expected_actor']}`.",
        "",
        "## Planned Lanes",
        "",
    ]
    for lane in payload["lanes_planned"]:
        lines.append(f"- `{lane['lane_id']}`: {lane['prompt_title']}. Status: `{lane['lane_status']}`.")
    lines.extend(
        [
            "",
            "## Completed So Far",
            "",
        ]
    )
    for lane in payload["lanes_completed"]:
        lines.append(f"- `{lane['lane_id']}`: `{lane['completion_status']}`.")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
        ]
    )
    for key, value in payload["authority_boundary"].items():
        lines.append(f"- `{key}` = `{str(value).lower()}`")
    lines.extend(
        [
            "",
            "## Next Prompt",
            "",
            f"- `{payload['next_prompt']['title']}`.",
            "",
            "## Machine Proof",
            "",
            f"- Planned lane count: `{proof['planned_lane_count']}`.",
            f"- Prompt 1 lane marked complete: `{str(proof['prompt_1_lane_marked_complete']).lower()}`.",
            f"- Prompt 2 lane marked complete: `{str(proof['prompt_2_lane_marked_complete']).lower()}`.",
            f"- Prompt 3 lane marked complete: `{str(proof['prompt_3_lane_marked_complete']).lower()}`.",
            f"- Prompt 4 lane marked complete: `{str(proof['prompt_4_lane_marked_complete']).lower()}`.",
            f"- Prompt 5 lane marked complete pending Mac import: `{str(proof['prompt_5_lane_marked_complete_pending_mac_import']).lower()}`.",
            f"- Authority boundary all false: `{str(proof['authority_boundary_all_false']).lower()}`.",
            f"- Stable map refresh required: `{str(proof['stable_map_refresh_required']).lower()}`.",
            f"- Mac import performed: `{str(proof['mac_import_performed']).lower()}`.",
            f"- Content hash: `{proof['content_hash']}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_post_security_governance_batch_manifest(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> BatchManifestExportResult:
    payload = build_post_security_governance_batch_manifest(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return BatchManifestExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        batch_id=BATCH_ID,
        batch_status=BATCH_STATUS,
        current_prompt_index=payload["current_prompt_index"],
        total_prompts=payload["total_prompts"],
        planned_lane_count=len(payload["lanes_planned"]),
        completed_lane_count=len(payload["lanes_completed"]),
        next_prompt=payload["next_prompt"]["lane_id"],
        stable_map_refresh_deferred=payload["stable_map_refresh_deferred"],
        commit_deferred_until_prompt_5=payload["commit_deferred_until_prompt_5"],
        authority_boundary_false=payload["machine_proof"]["authority_boundary_all_false"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the Post-Security Governance Batch Manifest v0 read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_post_security_governance_batch_manifest(repo_root=args.repo_root, export_root=args.export_root)
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "batch_id": result.batch_id,
        "batch_status": result.batch_status,
        "current_prompt_index": result.current_prompt_index,
        "total_prompts": result.total_prompts,
        "planned_lane_count": result.planned_lane_count,
        "completed_lane_count": result.completed_lane_count,
        "next_prompt": result.next_prompt,
        "stable_map_refresh_deferred": result.stable_map_refresh_deferred,
        "commit_deferred_until_prompt_5": result.commit_deferred_until_prompt_5,
        "authority_boundary_false": result.authority_boundary_false,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Post-security governance batch: `{result.batch_status}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
        print(f"- Next prompt: `{result.next_prompt}`")
    return 0


__all__ = [
    "BATCH_AUTHORITY_BOUNDARY",
    "BATCH_ID",
    "BATCH_STATUS",
    "LANES_PLANNED",
    "PROMPT_2_CHANGED_FILES",
    "PROMPT_2_VALIDATION_COMMANDS",
    "PROMPT_3_CHANGED_FILES",
    "PROMPT_3_VALIDATION_COMMANDS",
    "PROMPT_4_CHANGED_FILES",
    "PROMPT_4_VALIDATION_COMMANDS",
    "PROMPT_5_CHANGED_FILES",
    "PROMPT_5_VALIDATION_COMMANDS",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "build_post_security_governance_batch_manifest",
    "export_post_security_governance_batch_manifest",
    "format_operator_markdown",
    "stable_json",
]
