"""Make Winship Life Easier Batch v0 manifest.

This manifest tracks the five-prompt backend/read-model batch that turns
machine-contract substrate into app-wide human work modes. All five backend
lanes are complete in metadata only. It grants no Mission Control Swift changes,
Mac sync/import, network use, external account access, model/tool/agent/runtime
execution, workflow execution, or live action authority.
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

SCHEMA_VERSION = "make_winship_life_easier_batch_manifest_v0"
READ_MODEL_ID = "make_winship_life_easier_batch_manifest"
BATCH_ID = "make_winship_life_easier_batch_v0"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

LANES_PLANNED = (
    "operator_work_mode_schema_bandwidth_policy",
    "operator_solve_path_and_decision_node_contract",
    "guided_capture_and_protected_evidence_path_contract",
    "workflow_session_channel_projection_approval_bus_contract",
    "automation_readiness_feasibility_and_integrated_stable_map_refresh",
)

PROMPT_TITLES = {
    "operator_work_mode_schema_bandwidth_policy": "Prompt 1 - App-Wide Operator Work Mode Schema and Bandwidth Policy",
    "operator_solve_path_and_decision_node_contract": "Prompt 2 - Operator Solve Path and Decision Node Contract",
    "guided_capture_and_protected_evidence_path_contract": "Prompt 3 - Guided Capture and Protected Evidence Path Contract",
    "workflow_session_channel_projection_approval_bus_contract": (
        "Prompt 4 - Workflow Session / Channel Projection / Approval Bus Contract"
    ),
    "automation_readiness_feasibility_and_integrated_stable_map_refresh": (
        "Prompt 5 - Automation Readiness / Feasibility and Integrated Stable Map Refresh"
    ),
}

PROMPT_1_CHANGED_FILES = (
    ".gitignore",
    "operator_work_mode_schema_bandwidth_policy.py",
    "scripts/export_operator_work_mode_schema_bandwidth_policy.py",
    "tests/test_operator_work_mode_schema_bandwidth_policy.py",
    "generated/read_models/operator_work_mode_schema_bandwidth_policy.json",
    "generated/read_models/operator_work_mode_schema_bandwidth_policy_OPERATOR.md",
    "make_winship_life_easier_batch_manifest.py",
    "scripts/export_make_winship_life_easier_batch_manifest.py",
    "tests/test_make_winship_life_easier_batch_manifest.py",
    "generated/read_models/make_winship_life_easier_batch_manifest.json",
    "generated/read_models/make_winship_life_easier_batch_manifest_OPERATOR.md",
)

PROMPT_1_VALIDATION_COMMANDS = (
    "python3 scripts/export_operator_work_mode_schema_bandwidth_policy.py --format summary",
    "python3 scripts/export_make_winship_life_easier_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_operator_work_mode_schema_bandwidth_policy.py tests/test_make_winship_life_easier_batch_manifest.py -q",
    "python3 -m pytest tests/test_operator_attention_promotion_contract.py tests/test_openclaw_work_terrain_gap_detector.py tests/test_capital_hilton_proof_quieting_progress_state.py tests/test_capital_hilton_coupa_po_retrieval_automation_candidate.py -q",
    "python3 -m json.tool generated/read_models/operator_work_mode_schema_bandwidth_policy.json >/dev/null",
    "python3 -m json.tool generated/read_models/make_winship_life_easier_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 1 artifacts",
    "active-authority scan on Prompt 1 artifacts",
    "C-drive path scan on Prompt 1 artifacts",
    "python3 -m py_compile operator_work_mode_schema_bandwidth_policy.py scripts/export_operator_work_mode_schema_bandwidth_policy.py make_winship_life_easier_batch_manifest.py scripts/export_make_winship_life_easier_batch_manifest.py",
    "git diff --check",
)

PROMPT_2_CHANGED_FILES = (
    ".gitignore",
    "operator_solve_path_decision_node_contract.py",
    "scripts/export_operator_solve_path_decision_node_contract.py",
    "tests/test_operator_solve_path_decision_node_contract.py",
    "generated/read_models/operator_solve_path_decision_node_contract.json",
    "generated/read_models/operator_solve_path_decision_node_contract_OPERATOR.md",
    "make_winship_life_easier_batch_manifest.py",
    "scripts/export_make_winship_life_easier_batch_manifest.py",
    "tests/test_make_winship_life_easier_batch_manifest.py",
    "generated/read_models/make_winship_life_easier_batch_manifest.json",
    "generated/read_models/make_winship_life_easier_batch_manifest_OPERATOR.md",
)

PROMPT_2_VALIDATION_COMMANDS = (
    "python3 scripts/export_operator_solve_path_decision_node_contract.py --format summary",
    "python3 scripts/export_make_winship_life_easier_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_operator_solve_path_decision_node_contract.py tests/test_make_winship_life_easier_batch_manifest.py -q",
    "python3 -m pytest tests/test_operator_work_mode_schema_bandwidth_policy.py tests/test_capital_hilton_answer_candidate_receipt.py tests/test_capital_hilton_proof_quieting_progress_state.py tests/test_capital_hilton_coupa_po_retrieval_automation_candidate.py -q",
    "python3 -m json.tool generated/read_models/operator_solve_path_decision_node_contract.json >/dev/null",
    "python3 -m json.tool generated/read_models/make_winship_life_easier_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 2 artifacts",
    "active-authority scan on Prompt 2 artifacts",
    "C-drive path scan on Prompt 2 artifacts",
    "python3 -m py_compile operator_solve_path_decision_node_contract.py scripts/export_operator_solve_path_decision_node_contract.py make_winship_life_easier_batch_manifest.py scripts/export_make_winship_life_easier_batch_manifest.py",
    "git diff --check",
)

PROMPT_3_CHANGED_FILES = (
    ".gitignore",
    "guided_capture_protected_evidence_path_contract.py",
    "scripts/export_guided_capture_protected_evidence_path_contract.py",
    "tests/test_guided_capture_protected_evidence_path_contract.py",
    "generated/read_models/guided_capture_protected_evidence_path_contract.json",
    "generated/read_models/guided_capture_protected_evidence_path_contract_OPERATOR.md",
    "make_winship_life_easier_batch_manifest.py",
    "scripts/export_make_winship_life_easier_batch_manifest.py",
    "tests/test_make_winship_life_easier_batch_manifest.py",
    "generated/read_models/make_winship_life_easier_batch_manifest.json",
    "generated/read_models/make_winship_life_easier_batch_manifest_OPERATOR.md",
)

PROMPT_3_VALIDATION_COMMANDS = (
    "python3 scripts/export_guided_capture_protected_evidence_path_contract.py --format summary",
    "python3 scripts/export_make_winship_life_easier_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_guided_capture_protected_evidence_path_contract.py tests/test_make_winship_life_easier_batch_manifest.py -q",
    "python3 -m pytest tests/test_operator_work_mode_schema_bandwidth_policy.py tests/test_operator_solve_path_decision_node_contract.py tests/test_capital_hilton_coupa_po_retrieval_automation_candidate.py tests/test_capital_hilton_protected_reference_placeholder.py tests/test_capital_hilton_guardian_review_packet.py -q",
    "python3 -m json.tool generated/read_models/guided_capture_protected_evidence_path_contract.json >/dev/null",
    "python3 -m json.tool generated/read_models/make_winship_life_easier_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 3 artifacts",
    "active-authority scan on Prompt 3 artifacts",
    "C-drive path scan on Prompt 3 artifacts",
    "python3 -m py_compile guided_capture_protected_evidence_path_contract.py scripts/export_guided_capture_protected_evidence_path_contract.py make_winship_life_easier_batch_manifest.py scripts/export_make_winship_life_easier_batch_manifest.py",
    "git diff --check",
)

PROMPT_4_CHANGED_FILES = (
    ".gitignore",
    "workflow_session_channel_projection_approval_bus_contract.py",
    "scripts/export_workflow_session_channel_projection_approval_bus_contract.py",
    "tests/test_workflow_session_channel_projection_approval_bus_contract.py",
    "generated/read_models/workflow_session_channel_projection_approval_bus_contract.json",
    "generated/read_models/workflow_session_channel_projection_approval_bus_contract_OPERATOR.md",
    "make_winship_life_easier_batch_manifest.py",
    "scripts/export_make_winship_life_easier_batch_manifest.py",
    "tests/test_make_winship_life_easier_batch_manifest.py",
    "generated/read_models/make_winship_life_easier_batch_manifest.json",
    "generated/read_models/make_winship_life_easier_batch_manifest_OPERATOR.md",
)

PROMPT_4_VALIDATION_COMMANDS = (
    "python3 scripts/export_workflow_session_channel_projection_approval_bus_contract.py --format summary",
    "python3 scripts/export_make_winship_life_easier_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_workflow_session_channel_projection_approval_bus_contract.py tests/test_make_winship_life_easier_batch_manifest.py -q",
    "python3 -m pytest tests/test_operator_work_mode_schema_bandwidth_policy.py tests/test_operator_solve_path_decision_node_contract.py tests/test_guided_capture_protected_evidence_path_contract.py tests/test_security_pass_contract.py tests/test_capital_hilton_proof_quieting_progress_state.py -q",
    "python3 -m json.tool generated/read_models/workflow_session_channel_projection_approval_bus_contract.json >/dev/null",
    "python3 -m json.tool generated/read_models/make_winship_life_easier_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 4 artifacts",
    "active-authority scan on Prompt 4 artifacts",
    "C-drive path scan on Prompt 4 artifacts",
    "python3 -m py_compile workflow_session_channel_projection_approval_bus_contract.py scripts/export_workflow_session_channel_projection_approval_bus_contract.py make_winship_life_easier_batch_manifest.py scripts/export_make_winship_life_easier_batch_manifest.py",
    "git diff --check",
)

PROMPT_5_CHANGED_FILES = (
    ".gitignore",
    "automation_readiness_feasibility_evaluator_contract.py",
    "scripts/export_automation_readiness_feasibility_evaluator_contract.py",
    "tests/test_automation_readiness_feasibility_evaluator_contract.py",
    "generated/read_models/automation_readiness_feasibility_evaluator_contract.json",
    "generated/read_models/automation_readiness_feasibility_evaluator_contract_OPERATOR.md",
    "make_winship_life_easier_batch_manifest.py",
    "scripts/export_make_winship_life_easier_batch_manifest.py",
    "tests/test_make_winship_life_easier_batch_manifest.py",
    "generated/read_models/make_winship_life_easier_batch_manifest.json",
    "generated/read_models/make_winship_life_easier_batch_manifest_OPERATOR.md",
)

PROMPT_5_VALIDATION_COMMANDS = (
    "python3 scripts/export_automation_readiness_feasibility_evaluator_contract.py --format summary",
    "python3 scripts/export_make_winship_life_easier_batch_manifest.py --format summary",
    "python3 -m pytest tests/test_automation_readiness_feasibility_evaluator_contract.py tests/test_make_winship_life_easier_batch_manifest.py -q",
    "python3 -m pytest tests/test_operator_work_mode_schema_bandwidth_policy.py tests/test_operator_solve_path_decision_node_contract.py tests/test_guided_capture_protected_evidence_path_contract.py tests/test_workflow_session_channel_projection_approval_bus_contract.py tests/test_capital_hilton_coupa_po_retrieval_automation_candidate.py tests/test_security_pass_contract.py -q",
    "python3 -m json.tool generated/read_models/automation_readiness_feasibility_evaluator_contract.json >/dev/null",
    "python3 -m json.tool generated/read_models/make_winship_life_easier_batch_manifest.json >/dev/null",
    "credential/secret scan on Prompt 5 artifacts",
    "active-authority scan on Prompt 5 artifacts",
    "C-drive path scan on Prompt 5 artifacts",
    "python3 -m py_compile automation_readiness_feasibility_evaluator_contract.py scripts/export_automation_readiness_feasibility_evaluator_contract.py make_winship_life_easier_batch_manifest.py scripts/export_make_winship_life_easier_batch_manifest.py",
    "git diff --check",
)

AUTHORITY_BOUNDARY = {
    "workflow_execution_allowed": False,
    "session_state_write_allowed": False,
    "channel_message_send_allowed": False,
    "operator_input_persistence_allowed": False,
    "screenshot_capture_allowed": False,
    "file_write_allowed": False,
    "file_upload_allowed": False,
    "automation_execution_allowed": False,
    "approval_submission_allowed": False,
    "invoice_generation_allowed": False,
    "ledger_write_allowed": False,
    "artifact_generation_allowed": False,
    "email_send_allowed": False,
    "telegram_send_allowed": False,
    "browser_automation_allowed": False,
    "coupa_access_allowed": False,
    "credential_handling_allowed": False,
    "protected_evidence_write_allowed": False,
    "receipt_write_allowed": False,
    "workflow_state_write_allowed": False,
    "live_model_calls_allowed": False,
    "auto_promotion_allowed": False,
    "unsupervised_browser_execution_allowed": False,
    "direct_credential_store_reads_allowed": False,
    "automatic_ledger_writes_allowed": False,
    "email_dispatch_without_operator_signature_allowed": False,
    "file_move_delete_cleanup_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "network_operation_allowed": False,
    "supervised_browser_execution_allowed": False,
    "read_only_portal_lookup_allowed": False,
    "credential_broker_active": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "stable_map_refresh_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "commit_allowed": False,
    "staging_allowed": False,
    "raw_private_body_ingestion_allowed": False,
    "raw_body_ingestion_allowed": False,
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
        lane_status = "COMPLETED"
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


def build_make_winship_life_easier_batch_manifest(
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
                + PROMPT_5_CHANGED_FILES
            )
        ),
        "validation_commands": list(
            PROMPT_1_VALIDATION_COMMANDS
            + PROMPT_2_VALIDATION_COMMANDS
            + PROMPT_3_VALIDATION_COMMANDS
            + PROMPT_4_VALIDATION_COMMANDS
            + PROMPT_5_VALIDATION_COMMANDS
        ),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "prior_lane_observation": {
            "operator_work_mode_schema_bandwidth_policy": "OBSERVED",
            "operator_solve_path_decision_node_contract": "OBSERVED",
            "guided_capture_protected_evidence_path_contract": "OBSERVED",
            "workflow_session_channel_projection_approval_bus_contract": "OBSERVED",
            "automation_readiness_feasibility_evaluator_contract": "OBSERVED",
            "prompt_1_read_model_ref": "generated/read_models/operator_work_mode_schema_bandwidth_policy.json",
            "prompt_1_operator_ref": "generated/read_models/operator_work_mode_schema_bandwidth_policy_OPERATOR.md",
            "prompt_2_read_model_ref": "generated/read_models/operator_solve_path_decision_node_contract.json",
            "prompt_2_operator_ref": "generated/read_models/operator_solve_path_decision_node_contract_OPERATOR.md",
            "prompt_3_read_model_ref": "generated/read_models/guided_capture_protected_evidence_path_contract.json",
            "prompt_3_operator_ref": "generated/read_models/guided_capture_protected_evidence_path_contract_OPERATOR.md",
            "prompt_4_read_model_ref": "generated/read_models/workflow_session_channel_projection_approval_bus_contract.json",
            "prompt_4_operator_ref": "generated/read_models/workflow_session_channel_projection_approval_bus_contract_OPERATOR.md",
            "prompt_5_read_model_ref": "generated/read_models/automation_readiness_feasibility_evaluator_contract.json",
            "prompt_5_operator_ref": "generated/read_models/automation_readiness_feasibility_evaluator_contract_OPERATOR.md",
        },
        "next_prompt": "Mac map import/sync agent - import staged stable map bundle",
        "next_expected_actor": "mac_map_import_agent",
        "next_recommended_worker": "Mac map import/sync agent",
        "batch_commit_policy": {
            "commit_allowed_now": False,
            "staging_allowed_now": False,
            "commit_deferred_until_final_prompt": False,
            "final_prompt_local_commit_required": True,
            "do_not_push": True,
            "no_future_batch_commit_authority_granted": True,
        },
        "stable_map_refresh_policy": {
            "stable_map_refresh_allowed_now": False,
            "stable_map_refresh_deferred": False,
            "integrated_stable_map_refresh_required_by_prompt_5": True,
            "mac_import_still_deferred_to_next_actor": True,
        },
        "hard_boundaries": {
            "no_git_push_pull_fetch": True,
            "local_batch_commit_completed_by_prompt_5": True,
            "stable_map_refresh_completed_by_prompt_5": True,
            "no_mac_sync_import": True,
            "no_mission_control_swift_change": True,
            "no_network": True,
            "no_runtime_actions": True,
        },
        "machine_proof": {
            "batch_id_is_expected": BATCH_ID == "make_winship_life_easier_batch_v0",
            "status_is_complete_pending_stable_map_import": True,
            "stable_map_refresh_deferred": False,
            "commit_deferred_until_final_prompt": False,
            "current_prompt_index_is_5": True,
            "total_prompts_is_5": True,
            "planned_lane_count": len(LANES_PLANNED),
            "prompt_1_marked_complete": "operator_work_mode_schema_bandwidth_policy" in completed_lanes,
            "prompt_2_marked_complete": "operator_solve_path_and_decision_node_contract" in completed_lanes,
            "prompt_3_marked_complete": "guided_capture_and_protected_evidence_path_contract" in completed_lanes,
            "prompt_4_marked_complete": (
                "workflow_session_channel_projection_approval_bus_contract" in completed_lanes
            ),
            "prompt_5_marked_complete": (
                "automation_readiness_feasibility_and_integrated_stable_map_refresh" in completed_lanes
            ),
            "prompt_1_observed": True,
            "prompt_2_observed": True,
            "prompt_3_observed": True,
            "prompt_4_observed": True,
            "prompt_5_observed": True,
            "completed_lane_count": len(completed_lanes),
            "authority_boundary_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "no_live_execution_or_external_authority": True,
            "credentials_or_secrets_included": False,
            "raw_private_bodies_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_make_winship_life_easier_batch_manifest(payload: dict[str, Any]) -> str:
    lines = [
        "# Make Winship Life Easier Batch v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This batch changes Mission Control's default posture from machine-contract cockpit to human work path. Prompt 1 defines the app-wide work mode and bandwidth schema. Prompt 2 adds deterministic solve paths and decision nodes. Prompt 3 adds guided capture and protected evidence path policy. Prompt 4 adds canonical workflow sessions, channel projections, and approval-bus policy. Prompt 5 adds automation readiness and bottleneck feasibility, then stages the stable map for Mac import. It does not build UI, perform Mac import, persist answers, write protected evidence, write receipts, send messages, submit approvals, or enable live actions.",
        "",
        "## Batch Status",
        "",
        f"- Batch id: `{payload['batch_id']}`",
        f"- Status: `{payload['batch_status']}`",
        f"- Current prompt: `{payload['current_prompt_index']}` of `{payload['total_prompts']}`",
        f"- Stable-map refresh deferred: `{str(payload['stable_map_refresh_deferred']).lower()}`",
        f"- Commit deferred until final prompt: `{str(payload['commit_deferred_until_final_prompt']).lower()}`",
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
            "- No git push/pull/fetch, Mac sync/import, Mission Control Swift changes, network, browser/OAuth/Gmail/calendar/Coupa/Telegram/account access, credentials, invoice/excel/pdf generation, email draft/send, approval submission, ledger write, model/tool/agent/runtime/queue execution, file moves/deletes/cleanup, or authority escalation.",
            "",
            "## Next Actor",
            "",
            f"- `{payload['next_prompt']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def export_make_winship_life_easier_batch_manifest(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> BatchManifestExportResult:
    payload = build_make_winship_life_easier_batch_manifest(generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_make_winship_life_easier_batch_manifest(payload), encoding="utf-8")
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
        authority_boundary_false=payload["machine_proof"]["authority_boundary_false"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Make Winship Life Easier Batch v0 manifest.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_make_winship_life_easier_batch_manifest(
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
        "authority_boundary_false": result.authority_boundary_false,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Make Winship Life Easier Batch: `{result.batch_id}`")
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
    "PROMPT_1_CHANGED_FILES",
    "PROMPT_1_VALIDATION_COMMANDS",
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
    "build_make_winship_life_easier_batch_manifest",
    "export_make_winship_life_easier_batch_manifest",
    "format_make_winship_life_easier_batch_manifest",
    "stable_json",
]
