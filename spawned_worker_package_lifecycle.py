"""Spawned Worker Package Lifecycle V0.

Defines a PR-like lifecycle for bounded worker package outputs from PC_CODEX
and MAC_CODEX. This is a local read-model contract only. It does not spawn
workers, run child agents, push git state, send email, open browser/Gmail/Coupa,
mutate ledgers or workbooks, export PDFs, submit portals, or grant authority.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Spawned Worker Package Lifecycle.md")

SCHEMA_VERSION = "spawned_worker_package_lifecycle_v0"
READ_MODEL_ID = "spawned_worker_package_lifecycle"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
LIFECYCLE_STATUS = "SPAWNED_WORKER_PACKAGE_LIFECYCLE_READY"
MODULE_ROLE = "contract_only"
CANONICAL_RUNTIME_SPINE_REF = "codex_work_package_lifecycle.py"
MIGRATION_NOTE = (
    "Retained as a spawned-worker lifecycle contract/read model. Runtime queue, dispatch, "
    "result ingest, proof verification, and Watch Desk projection are canonical in "
    "codex_work_package_lifecycle.py."
)

LIFECYCLE_STATES = (
    "PACKAGE_STAGED",
    "WORKER_ASSIGNED",
    "WORKER_RUNNING",
    "RESULT_READY",
    "REVIEW_PACKET_READY",
    "OPERATOR_APPROVED",
    "MERGED_OR_RECORDED",
    "REWORK_REQUIRED",
    "BLOCKED_BY_GATE",
)

REVIEW_PACKET_REQUIRED_FIELDS = (
    "package_id",
    "worker_ref",
    "channel_ref",
    "files_changed",
    "tests_run",
    "receipts",
    "screenshots",
    "proof_refs",
    "unsafe_scan_result",
    "human_summary",
    "next_safe_action",
)

SUPPORTED_WORKERS = (
    {
        "worker_ref": "pc_codex",
        "display_name": "PC_CODEX",
        "scope": "PC backend implementation and validation packets only",
        "default_channel_ref": "build_openclaw_backend",
        "allowed_package_types": [
            "pc_codex_backend_worker_packet",
            "spawned_worker_review_packet",
        ],
    },
    {
        "worker_ref": "mac_codex",
        "display_name": "MAC_CODEX",
        "scope": "Mac Mission Control UI, Excel review surface, and GUI operator-assist packets only",
        "default_channel_ref": "build_mission_control_mac",
        "allowed_package_types": [
            "mac_codex_operator_assist_worker_packet",
            "spawned_worker_review_packet",
        ],
    },
)

AUTHORITY_RULES = (
    "Worker does not inherit speaker authority.",
    "speaker_ref does not grant tools.",
    "All business actions remain gated.",
    "No child spawning unless LM2 cage/Guardian allows.",
    "Review packet readiness is not approval.",
    "Operator approval is required before merge or recorded completion.",
)

COMMON_BLOCKED_ACTIONS = (
    "spawn_worker",
    "run_child_agent",
    "launch_agent_loop",
    "call_external_llm",
    "connect_external_tool",
    "push_git",
    "send_email",
    "open_gmail",
    "open_browser",
    "open_coupa",
    "mutate_ledger",
    "mutate_workbook",
    "export_pdf",
    "submit_portal",
    "mark_paid",
    "grant_tool_authority_from_speaker_ref",
    "grant_business_authority_from_worker_result",
)

AUTHORITY_BOUNDARY = {
    "worker_spawn_allowed": False,
    "child_agent_run_allowed": False,
    "agent_loop_allowed": False,
    "external_llm_allowed": False,
    "external_tool_connect_allowed": False,
    "git_push_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "speaker_tool_grant_allowed": False,
    "business_action_allowed": False,
    "sent": False,
    "paid": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def build_state_definitions() -> list[dict[str, Any]]:
    definitions = {
        "PACKAGE_STAGED": {
            "meaning": "A package exists locally and is ready for assignment review.",
            "entry_requirements": ["package_id", "package_type", "channel_ref"],
            "exit_requirements": ["operator or package gate selects worker_ref"],
        },
        "WORKER_ASSIGNED": {
            "meaning": "A bounded worker_ref is assigned, but no worker has been run by this lifecycle.",
            "entry_requirements": ["worker_ref", "assignment_receipt_ref"],
            "exit_requirements": ["separate approved worker execution receipt"],
        },
        "WORKER_RUNNING": {
            "meaning": "A separate approved process reports worker execution in progress.",
            "entry_requirements": ["running_receipt_ref"],
            "exit_requirements": ["worker result receipt or gate blocker"],
        },
        "RESULT_READY": {
            "meaning": "Worker output exists and is ready to shape into a review packet.",
            "entry_requirements": ["worker_result_receipt", "files_changed", "tests_run"],
            "exit_requirements": ["review packet fields complete"],
        },
        "REVIEW_PACKET_READY": {
            "meaning": "A PR-like review packet is available for operator review.",
            "entry_requirements": list(REVIEW_PACKET_REQUIRED_FIELDS),
            "exit_requirements": ["operator approval, rework decision, or gate blocker"],
        },
        "OPERATOR_APPROVED": {
            "meaning": "The operator approved the review packet for merge or recording.",
            "entry_requirements": ["operator_approval_receipt"],
            "exit_requirements": ["merge receipt or recorded completion receipt"],
        },
        "MERGED_OR_RECORDED": {
            "meaning": "The approved work was merged or recorded with proof refs.",
            "entry_requirements": ["merge_or_record_receipt"],
            "exit_requirements": [],
        },
        "REWORK_REQUIRED": {
            "meaning": "The review packet needs revision before approval.",
            "entry_requirements": ["review_feedback"],
            "exit_requirements": ["updated package or reassignment decision"],
        },
        "BLOCKED_BY_GATE": {
            "meaning": "A safety, authority, missing-proof, or package gate blocks progress.",
            "entry_requirements": ["gate_ref", "block_reason"],
            "exit_requirements": ["resolved gate receipt"],
        },
    }
    return [
        {
            "state": state,
            "ordinal": index + 1,
            **definitions[state],
        }
        for index, state in enumerate(LIFECYCLE_STATES)
    ]


def build_transitions() -> list[dict[str, Any]]:
    return [
        {
            "from_state": "PACKAGE_STAGED",
            "to_state": "WORKER_ASSIGNED",
            "trigger": "bounded worker assignment selected",
            "receipt_required": True,
            "operator_review_required": True,
        },
        {
            "from_state": "PACKAGE_STAGED",
            "to_state": "BLOCKED_BY_GATE",
            "trigger": "package, authority, proof, or worker gate blocks assignment",
            "receipt_required": True,
            "operator_review_required": True,
        },
        {
            "from_state": "WORKER_ASSIGNED",
            "to_state": "WORKER_RUNNING",
            "trigger": "separate approved worker runner reports start",
            "receipt_required": True,
            "operator_review_required": True,
        },
        {
            "from_state": "WORKER_RUNNING",
            "to_state": "RESULT_READY",
            "trigger": "worker result receipt arrives",
            "receipt_required": True,
            "operator_review_required": False,
        },
        {
            "from_state": "WORKER_RUNNING",
            "to_state": "BLOCKED_BY_GATE",
            "trigger": "worker reports blocker or unsafe action request",
            "receipt_required": True,
            "operator_review_required": True,
        },
        {
            "from_state": "RESULT_READY",
            "to_state": "REVIEW_PACKET_READY",
            "trigger": "review packet contract is complete",
            "receipt_required": True,
            "operator_review_required": False,
        },
        {
            "from_state": "RESULT_READY",
            "to_state": "REWORK_REQUIRED",
            "trigger": "required review packet fields or validation proof are missing",
            "receipt_required": True,
            "operator_review_required": True,
        },
        {
            "from_state": "REVIEW_PACKET_READY",
            "to_state": "OPERATOR_APPROVED",
            "trigger": "operator explicitly approves review packet",
            "receipt_required": True,
            "operator_review_required": True,
        },
        {
            "from_state": "REVIEW_PACKET_READY",
            "to_state": "REWORK_REQUIRED",
            "trigger": "operator requests changes",
            "receipt_required": True,
            "operator_review_required": True,
        },
        {
            "from_state": "REVIEW_PACKET_READY",
            "to_state": "BLOCKED_BY_GATE",
            "trigger": "unsafe scan, authority request, or missing proof blocks approval",
            "receipt_required": True,
            "operator_review_required": True,
        },
        {
            "from_state": "OPERATOR_APPROVED",
            "to_state": "MERGED_OR_RECORDED",
            "trigger": "approved merge or recording receipt is present",
            "receipt_required": True,
            "operator_review_required": True,
        },
        {
            "from_state": "REWORK_REQUIRED",
            "to_state": "WORKER_ASSIGNED",
            "trigger": "bounded rework packet is assigned",
            "receipt_required": True,
            "operator_review_required": True,
        },
        {
            "from_state": "BLOCKED_BY_GATE",
            "to_state": "PACKAGE_STAGED",
            "trigger": "gate is resolved and package returns to staged review",
            "receipt_required": True,
            "operator_review_required": True,
        },
    ]


def build_review_packet_contract() -> dict[str, Any]:
    field_contract = {
        "package_id": {
            "type": "string",
            "required": True,
            "meaning": "Stable package identifier from package queue or handoff packet.",
        },
        "worker_ref": {
            "type": "enum",
            "required": True,
            "allowed_values": [worker["worker_ref"] for worker in SUPPORTED_WORKERS],
            "meaning": "Bounded worker output lane, not a speaker authority grant.",
        },
        "channel_ref": {
            "type": "string",
            "required": True,
            "meaning": "Workroom channel that owns review visibility.",
        },
        "files_changed": {
            "type": "list[string]",
            "required": True,
            "meaning": "Changed file paths or artifact refs summarized for review.",
        },
        "tests_run": {
            "type": "list[string]",
            "required": True,
            "meaning": "Validation commands or checks the worker reports.",
        },
        "receipts": {
            "type": "list[string]",
            "required": True,
            "meaning": "Assignment, worker result, validation, approval, or merge receipts.",
        },
        "screenshots": {
            "type": "list[string]",
            "required": True,
            "meaning": "Screenshot refs if any; empty list is valid.",
        },
        "proof_refs": {
            "type": "list[string]",
            "required": True,
            "meaning": "Collapsed proof refs for files, tests, receipts, and read models.",
        },
        "unsafe_scan_result": {
            "type": "object",
            "required": True,
            "required_subfields": ["status", "unsafe_true_grants", "blocked_actions_reviewed"],
            "meaning": "Unsafe authority scan summary; no raw row dump required.",
        },
        "human_summary": {
            "type": "string",
            "required": True,
            "meaning": "Plain explanation of what changed and why it is ready or blocked.",
        },
        "next_safe_action": {
            "type": "string",
            "required": True,
            "meaning": "One operator-safe next step.",
        },
    }
    return {
        "packet_ref": "spawned_worker_review_packet_v0",
        "purpose": "PR-like review packet for bounded spawned worker outputs.",
        "required_fields": list(REVIEW_PACKET_REQUIRED_FIELDS),
        "field_contract": field_contract,
        "proof_collapsed_by_default": True,
        "raw_diff_body_by_default": False,
        "operator_approval_required_before_merge_or_record": True,
        "review_outcomes": [
            "approve",
            "request_rework",
            "block_by_gate",
        ],
    }


def build_examples() -> list[dict[str, Any]]:
    return [
        {
            "example_ref": "pc_backend_package_review",
            "package_id": "pkg:example:backend_registry_patch",
            "worker_ref": "pc_codex",
            "channel_ref": "build_openclaw_backend",
            "state_path": [
                "PACKAGE_STAGED",
                "WORKER_ASSIGNED",
                "WORKER_RUNNING",
                "RESULT_READY",
                "REVIEW_PACKET_READY",
            ],
            "review_packet_summary": {
                "files_changed": ["example_backend_module.py", "tests/test_example_backend_module.py"],
                "tests_run": ["pytest -q tests/test_example_backend_module.py"],
                "screenshots": [],
                "unsafe_scan_result": {
                    "status": "PASS",
                    "unsafe_true_grants": [],
                    "blocked_actions_reviewed": list(COMMON_BLOCKED_ACTIONS),
                },
                "human_summary": "PC_CODEX changed backend code and returned local validation proof for operator review.",
                "next_safe_action": "Review the packet and approve, request rework, or block by gate.",
            },
            "authority_note": "PC_CODEX output is reviewable; it does not push or inherit Chief/Hermes/Guardian authority.",
        },
        {
            "example_ref": "mac_ui_package_review",
            "package_id": "pkg:example:mission_control_ui_patch",
            "worker_ref": "mac_codex",
            "channel_ref": "build_mission_control_mac",
            "state_path": [
                "PACKAGE_STAGED",
                "WORKER_ASSIGNED",
                "WORKER_RUNNING",
                "RESULT_READY",
                "REVIEW_PACKET_READY",
            ],
            "review_packet_summary": {
                "files_changed": ["MissionControlView.swift", "tests/test_mission_control_view_contract.py"],
                "tests_run": ["pytest -q tests/test_mission_control_view_contract.py"],
                "screenshots": ["generated/screenshots/example_mission_control_review.png"],
                "unsafe_scan_result": {
                    "status": "PASS",
                    "unsafe_true_grants": [],
                    "blocked_actions_reviewed": list(COMMON_BLOCKED_ACTIONS),
                },
                "human_summary": "MAC_CODEX returned UI work with screenshot proof for operator review.",
                "next_safe_action": "Inspect the screenshot and validation refs before approval.",
            },
            "authority_note": "MAC_CODEX output is reviewable; it does not mutate workbooks or run GUI automation from this lifecycle.",
        },
    ]


def build_read_model(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    states = build_state_definitions()
    transitions = build_transitions()
    review_packet_contract = build_review_packet_contract()
    all_states_present = tuple(state["state"] for state in states) == LIFECYCLE_STATES
    all_review_fields_present = (
        tuple(review_packet_contract["required_fields"]) == REVIEW_PACKET_REQUIRED_FIELDS
        and set(review_packet_contract["field_contract"]) == set(REVIEW_PACKET_REQUIRED_FIELDS)
    )
    all_transitions_have_receipts = all(transition["receipt_required"] is True for transition in transitions)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": LIFECYCLE_STATUS,
        "purpose": "Defines a PR-like review lifecycle for bounded spawned worker package outputs.",
        "mode": "local_read_model_contract_only_no_worker_spawn",
        "lifecycle_states": list(LIFECYCLE_STATES),
        "state_definitions": states,
        "transitions": transitions,
        "review_packet_contract": review_packet_contract,
        "supported_workers": list(SUPPORTED_WORKERS),
        "authority_rules": list(AUTHORITY_RULES),
        "blocked_actions": list(COMMON_BLOCKED_ACTIONS),
        "examples": build_examples(),
        "source_refs": [
            "generated/read_models/agent_handoff_registry.json",
            "generated/read_models/openclaw_workroom_registry.json",
            "generated/read_models/openclaw_lm_child_package_gate.json",
            "generated/read_models/workflow_package_queue_contract.json",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "local_only": True,
            "read_model_contract_only": True,
            "all_lifecycle_states_present": all_states_present,
            "all_review_packet_fields_present": all_review_fields_present,
            "all_transitions_require_receipts": all_transitions_have_receipts,
            "worker_spawn_performed": False,
            "child_agent_run_performed": False,
            "git_push_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "submit_performed": False,
            "paid_marking_performed": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Spawned Worker Package Lifecycle",
        "",
        f"Status: `{read_model['status']}`",
        "",
        "This contract defines a PR-like lifecycle for bounded worker outputs from PC_CODEX and MAC_CODEX. It does not spawn workers, run child agents, push, or grant tool authority.",
        "",
        "## Lifecycle States",
        "",
    ]
    for state in read_model["state_definitions"]:
        lines.append(f"- `{state['state']}`: {state['meaning']}")
    lines.extend(
        [
            "",
            "## Review Packet",
            "",
            "Required fields:",
            "",
        ]
    )
    lines.extend(f"- `{field}`" for field in read_model["review_packet_contract"]["required_fields"])
    lines.extend(
        [
            "",
            "## Authority",
            "",
        ]
    )
    lines.extend(f"- {rule}" for rule in read_model["authority_rules"])
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No worker spawn.",
            "- No child agents.",
            "- No git push.",
            "- No email send.",
            "- No Gmail/browser/Coupa access.",
            "- No ledger or workbook mutation.",
            "- No PDF export.",
            "- No submit or mark-paid.",
            "- Review packet readiness is not approval.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_spawned_worker_package_lifecycle(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    read_model_path.write_text(stable_json(read_model), encoding="utf-8")

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_file = bridge_export_root / JSON_EXPORT_NAME
        bridge_file.write_text(stable_json(read_model), encoding="utf-8")
        bridge_path = bridge_file.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
        "state_count": str(len(read_model["lifecycle_states"])),
        "review_packet_field_count": str(len(read_model["review_packet_contract"]["required_fields"])),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Spawned Worker Package Lifecycle V0.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_spawned_worker_package_lifecycle(
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
