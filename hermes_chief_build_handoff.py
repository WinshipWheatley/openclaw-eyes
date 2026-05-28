"""Hermes to Chief build handoff for the Live Arts MD critical path.

This is a developer-mode build package. It coordinates coding, tests,
contracts, and UI payload work only. It does not execute the business workflow,
send email, create Gmail drafts, access Coupa/browser/Gmail, read workbook
cells, generate invoices, post ledgers, start Repo B, call live models, or
mutate production business state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

import hermes_mission_sentinel
import model_router_policy


SCHEMA_VERSION = "hermes_chief_build_handoff_v0"
READ_MODEL_ID = "hermes_chief_build_handoff"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DEVELOPER_BUILD_HANDOFF_NO_PRODUCTION_AUTHORITY"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_GENERATED_AT = hermes_mission_sentinel.DEFAULT_GENERATED_AT

MODEL_CLASS_ALIASES = {
    "STRONG_CODE_ORCHESTRATOR_MODEL": model_router_policy.STRONG_STRUCTURED_ROLE_REASONER,
    "CODEX_5_5_STYLE_BUILD_AGENT": model_router_policy.STRONG_STRUCTURED_ROLE_REASONER,
    "GPT_5_5_STYLE_REASONER": model_router_policy.STRONG_STRUCTURED_ROLE_REASONER,
}

AUTHORITY_BOUNDARY = {
    "production_workflow_execution_allowed": False,
    "email_send_allowed": False,
    "gmail_draft_creation_allowed": False,
    "gmail_polling_allowed": False,
    "coupa_browser_allowed": False,
    "workbook_cell_read_allowed": False,
    "invoice_generation_allowed": False,
    "ledger_mutation_allowed": False,
    "production_business_state_mutation_allowed": False,
    "repo_b_runtime_start_allowed": False,
    "live_model_call_allowed": False,
    "tool_execution_allowed_for_business_actions": False,
    "approval_execution_allowed": False,
    "git_push_allowed": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(payload)))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _task(
    *,
    task_ref: str,
    title: str,
    target_repo: str,
    priority: str,
    why_it_matters: str,
    exact_files_to_inspect: tuple[str, ...],
    allowed_changes: tuple[str, ...],
    forbidden_changes: tuple[str, ...],
    expected_output: str,
    validation_required: tuple[str, ...],
    dependencies: tuple[str, ...] = (),
    can_run_parallel: bool = True,
    collision_scope: str = "LOW",
    human_trial_after: bool = False,
    model_class_recommended: str = "STRONG_CODE_ORCHESTRATOR_MODEL",
) -> dict[str, Any]:
    return {
        "task_ref": task_ref,
        "title": title,
        "target_repo": target_repo,
        "priority": priority,
        "deadline_relevance": "CRITICAL_BEFORE_4PM" if priority == "CRITICAL" else "SUPPORTS_CRITICAL_PATH",
        "why_it_matters": why_it_matters,
        "exact_files_to_inspect": exact_files_to_inspect,
        "allowed_changes": allowed_changes,
        "forbidden_changes": forbidden_changes,
        "expected_output": expected_output,
        "validation_required": validation_required,
        "dependencies": dependencies,
        "can_run_parallel": can_run_parallel,
        "collision_scope": collision_scope,
        "model_class_recommended": model_class_recommended,
        "resolved_model_class_alias": MODEL_CLASS_ALIASES[model_class_recommended],
        "model_policy_ref": "generated/read_models/model_router_policy.json",
        "human_trial_after": human_trial_after,
        "done_definition": (
            "Task is complete only when the read-model/payload/test path proves the blocker is handled "
            "without external action authority or fake business completion."
        ),
    }


def recommended_chief_tasks() -> tuple[dict[str, Any], ...]:
    return (
        _task(
            task_ref="chief_task:live_arts_invoice_candidate_selection",
            title="Build/verify Live Arts invoice candidate selection path",
            target_repo="BOTH",
            priority="CRITICAL",
            why_it_matters="Today's invoice cannot become send-ready until the operator selects 2026-1001 or 2026-1002.",
            exact_files_to_inspect=(
                "live_arts_md_workbook_handoff.py",
                "live_arts_md_invoice_review_bundle.py",
                "invoice_review_action_request_handler.py",
                "openclaw_request_processor.py",
                "Mission Control Finance invoice review side panel",
            ),
            allowed_changes=(
                "backend guided action/result payloads",
                "Mac developer-mode button wiring for existing payloads",
                "focused tests",
            ),
            forbidden_changes=("workbook cell read", "invoice send", "invoice generation/export"),
            expected_output="Operator can choose the Live Arts MD invoice candidate and receive a selection receipt/read-model update.",
            validation_required=("focused invoice candidate selection tests", "JSON parse", "bridge hash check"),
            human_trial_after=True,
        ),
        _task(
            task_ref="chief_task:manual_artifact_attach_link",
            title="Build/verify manual artifact attach/link rail",
            target_repo="BOTH",
            priority="CRITICAL",
            why_it_matters="The invoice attachment is the main current blocker before approval or manual-send package readiness.",
            exact_files_to_inspect=(
                "live_arts_md_invoice_review_bundle.py",
                "local_artifact_reference.py",
                "invoice_review_state_machine.py",
                "Mission Control file picker/open/reveal path",
            ),
            allowed_changes=("metadata-only artifact link receipts", "candidate attachment confirmation request", "Mac file selection payload handling"),
            forbidden_changes=("Excel/Office automation", "PDF/XLSX generation", "workbook body parse"),
            expected_output="Operator can attach/link the generated invoice artifact by metadata only; attachment-ready still requires confirmation receipt.",
            validation_required=("artifact metadata-only tests", "source/bridge bundle refresh", "static no-generation scan"),
            dependencies=("chief_task:live_arts_invoice_candidate_selection",),
            can_run_parallel=False,
            collision_scope="HIGH_SHARED_INVOICE_BUNDLE",
            human_trial_after=True,
        ),
        _task(
            task_ref="chief_task:recipient_confirmation",
            title="Build/verify recipient confirmation rail",
            target_repo="BOTH",
            priority="CRITICAL",
            why_it_matters="Dane, Draper, and Earnie emails are not invented; Winship copy is known but inclusion still needs confirmation.",
            exact_files_to_inspect=(
                "clara_invoice_email_draft_package.py",
                "live_arts_md_invoice_review_bundle.py",
                "client_comms_thread_rail.py",
                "Mission Control recipient confirmation UI",
            ),
            allowed_changes=("recipient confirmation result contract", "missing-email prompts", "focused tests"),
            forbidden_changes=("inventing emails", "creating Gmail drafts", "sending email"),
            expected_output="Recipient state can move only with explicit confirmation receipts.",
            validation_required=("recipient confirmation tests", "Clara draft package tests"),
            human_trial_after=True,
        ),
        _task(
            task_ref="chief_task:clara_send_ready_draft",
            title="Build/verify Clara send-ready draft transition",
            target_repo="PC",
            priority="HIGH",
            why_it_matters="The current Clara package is a target blueprint; it must become exact approval-ready copy only after prerequisites.",
            exact_files_to_inspect=(
                "clara_invoice_email_draft_package.py",
                "live_arts_md_invoice_review_bundle.py",
                "client_comms_thread_rail.py",
            ),
            allowed_changes=("draft readiness transitions", "proof-gated body/subject fields", "Guardian request candidate shape"),
            forbidden_changes=("backend status copy in client body", "send claim", "Gmail draft creation"),
            expected_output="Exact Live Arts MD email body is approval-ready only after artifact, invoice candidate, and recipients are confirmed.",
            validation_required=("Clara draft package tests", "Guardian separation tests"),
            dependencies=("chief_task:manual_artifact_attach_link", "chief_task:recipient_confirmation"),
            can_run_parallel=False,
            collision_scope="MEDIUM_SHARED_DRAFT_PACKAGE",
        ),
        _task(
            task_ref="chief_task:manual_send_proof_capture",
            title="Build/verify manual-send proof capture fallback",
            target_repo="BOTH",
            priority="CRITICAL",
            why_it_matters="If OpenClaw is not send-ready before cutoff, Winship still needs clean proof after manual send.",
            exact_files_to_inspect=(
                "hermes_mission_sentinel.py",
                "live_arts_md_invoice_review_bundle.py",
                "invoice_review_state_machine.py",
                "Mission Control proof capture surface",
            ),
            allowed_changes=("manual send receipt contract", "proof capture request payload", "payment watch readiness update"),
            forbidden_changes=("email send", "ledger posting", "bank ledger read"),
            expected_output="After manual send, OpenClaw can record recipient/subject/attachment/time/invoice/amount proof and start payment-watch readiness.",
            validation_required=("manual send receipt tests", "payment watch readiness tests"),
            can_run_parallel=True,
            collision_scope="MEDIUM_RECEIPT_STATE",
            human_trial_after=True,
        ),
        _task(
            task_ref="chief_task:payment_watch_readiness_after_send",
            title="Build/verify payment watch readiness after send proof",
            target_repo="PC",
            priority="MEDIUM",
            why_it_matters="Payment watch is needed after send proof, but it must not delay today's send.",
            exact_files_to_inspect=(
                "live_arts_md_workbook_handoff.py",
                "live_arts_md_invoice_review_bundle.py",
            ),
            allowed_changes=("readiness-only payment watch state", "proof refs"),
            forbidden_changes=("bank ledger read", "ledger mutation", "mark paid"),
            expected_output="Payment watch is ready to configure after manual/email send receipt without claiming payment.",
            validation_required=("payment watch readiness tests",),
            dependencies=("chief_task:manual_send_proof_capture",),
            can_run_parallel=True,
            collision_scope="LOW_READINESS_ONLY",
        ),
    )


def _split_tasks(tasks: tuple[dict[str, Any], ...], *, parallel: bool) -> tuple[str, ...]:
    return tuple(task["task_ref"] for task in tasks if bool(task["can_run_parallel"]) is parallel)


def build_hermes_chief_build_handoff(
    *,
    generated_at: str | None = None,
    sentinel_payload: Mapping[str, Any] | None = None,
    access_class: str = "WINSHIP_DEVELOPER",
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    sentinel = (
        dict(sentinel_payload)
        if sentinel_payload is not None
        else hermes_mission_sentinel.build_hermes_mission_sentinel(generated_at=generated_at)
    )
    developer_mode = access_class == "WINSHIP_DEVELOPER"
    tasks = recommended_chief_tasks() if developer_mode else ()
    handoff_ref = f"hermes_chief_build_handoff:{_short_hash(sentinel['mission_ref'], generated_at, access_class)}"
    hidden_payload = {
        "request_type": "CHIEF_BUILD_HANDOFF_REQUEST",
        "access_class": access_class,
        "mission_ref": sentinel["mission_ref"],
        "handoff_ref": handoff_ref,
        "no_production_action": True,
        "no_external_action": True,
        "no_business_state_mutation": True,
        "email_send_allowed": False,
        "gmail_draft_creation_allowed": False,
        "coupa_browser_allowed": False,
        "ledger_mutation_allowed": False,
        "workbook_cell_read_allowed": False,
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "handoff_ref": handoff_ref,
        "mission_ref": sentinel["mission_ref"],
        "urgent_goal": sentinel["urgent_goal"],
        "deadline_local": sentinel["deadline_local"],
        "current_mode": sentinel["current_mode"],
        "access_class": access_class,
        "operator_context": {
            "developer_mode_only": True,
            "customer_mode_visible": False,
            "customer_safe_copy": "This module needs setup or support before that feature can run.",
            "manual_fallback_required_by": sentinel["manual_fallback_required_by"],
        },
        "critical_path": sentinel["critical_path"],
        "current_blockers": sentinel["current_blockers"],
        "build_gaps": (
            "invoice candidate selection result path",
            "manual artifact attach/link rail",
            "recipient confirmation rail",
            "Clara exact draft readiness transition",
            "manual-send proof capture",
        ),
        "runtime_gaps": (
            "no live email send rail ready for today's cutoff",
            "attachment_ready=false",
            "recipient_confirmation_receipt missing",
            "approval/send readiness disabled",
        ),
        "human_trial_gaps": (
            "Mac needs a trial for invoice candidate selection",
            "Mac needs a trial for artifact attach/open/reveal",
            "Mac needs a trial for manual-send proof capture",
        ),
        "recommended_chief_tasks": tasks,
        "recommended_mac_tasks": tuple(task for task in tasks if task["target_repo"] in {"MAC", "BOTH"}),
        "recommended_pc_tasks": tuple(task for task in tasks if task["target_repo"] in {"PC", "BOTH"}),
        "parallelizable_tasks": _split_tasks(tasks, parallel=True),
        "serial_tasks": _split_tasks(tasks, parallel=False),
        "collision_risks": (
            "PC and Mac both touch invoice review bundle/action payload shape.",
            "Artifact link rail and Clara draft readiness both depend on selected invoice state.",
            "Do not let manual-send proof capture mark paid or ledger-posted.",
        ),
        "required_tests": (
            "tests/test_hermes_chief_build_handoff.py",
            "tests/test_hermes_mission_sentinel.py",
            "tests/test_workflow_operating_mode_policy.py",
            "tests/test_live_arts_md_invoice_review_bundle.py",
            "tests/test_clara_invoice_email_draft_package.py",
        ),
        "required_receipts": (
            "live_arts_md_invoice_candidate_selected_receipt",
            "operator_provided_invoice_artifact_linked_candidate_receipt",
            "invoice_attachment_confirmed_receipt",
            "recipient_confirmation_receipt",
            "clara_email_draft_receipt",
            "guardian_approval_request_receipt",
            "manual_send_receipt",
        ),
        "stop_conditions": (
            "4 PM cutoff reached without send-ready package",
            "manual send completed by Winship",
            "a task would require email/Gmail/Coupa/browser/workbook-cell/ledger authority",
            "Mac human trial reveals the UI cannot complete the step safely",
        ),
        "manual_fallback_plan": {
            "fallback_required_by": sentinel["manual_fallback_required_by"],
            "operator_action": "Winship manually sends the invoice if OpenClaw is not safely send-ready.",
            "proof_to_capture": sentinel["proof_to_capture_after_manual_send"],
            "after_manual_send": "Capture manual send receipt, then configure payment watch readiness.",
        },
        "orchestrator_summary": (
            "Hermes sees Live Arts MD as urgent and not send-ready. Chief should drive only the critical path: "
            "candidate selection, artifact attach/link, recipient confirmation, Clara exact draft readiness, "
            "manual-send proof capture, and payment-watch readiness after proof. Avoid general architecture work."
        ),
        "next_prompt_for_chief": (
            "Use the Hermes Chief handoff to build the shortest Live Arts MD critical path. Split PC and Mac work, "
            "keep receipts/tests tight, and stop at manual-send fallback if send-readiness is not safe before cutoff."
        )
        if developer_mode
        else None,
        "next_prompt_for_mac_codex": (
            "Implement or verify the Mission Control developer-mode surfaces for invoice candidate selection, artifact attach/open/reveal, recipient confirmation, and manual-send proof capture. Do not send email."
        )
        if developer_mode
        else None,
        "next_prompt_for_pc_codex": (
            "Implement or verify backend receipts/read-model refresh for Live Arts invoice candidate selection, artifact link, recipient confirmation, Clara draft readiness, and manual-send proof capture. Do not execute business actions."
        )
        if developer_mode
        else None,
        "next_prompt_for_other_agents": (
            "Audit the handoff for drift only. Do not start Telegram, email, Coupa, ledger, or runtime automation."
        )
        if developer_mode
        else None,
        "button_label": "Ask Chief to build the critical path" if developer_mode else None,
        "button_enabled": developer_mode,
        "button_disabled_reason": None if developer_mode else "Developer build handoff is hidden in customer mode.",
        "button_hidden_request_payload": hidden_payload if developer_mode else None,
        "customer_mode_projection": {
            "developer_tasks_visible": False,
            "button_visible": False,
            "operator_copy": "This module needs setup or support before that feature can run.",
        },
        "proof_refs": (
            "generated/read_models/hermes_mission_sentinel.json",
            "generated/read_models/workflow_operating_mode_policy.json",
            "generated/read_models/live_arts_md_invoice_review_bundle.json",
        ),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "developer_mode_only": True,
            "customer_mode_hides_developer_tasks": access_class != "CUSTOMER_OPERATOR" or not tasks,
            "read_model_only": True,
            "no_production_authority": True,
            "no_email_send": True,
            "no_gmail_draft": True,
            "no_coupa_browser": True,
            "no_workbook_cell_read": True,
            "no_invoice_generation": True,
            "no_ledger_mutation": True,
            "all_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def render_operator_summary(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Hermes -> Chief Build Handoff",
        "",
        f"Goal: {payload['urgent_goal']}",
        f"Cutoff: {payload['deadline_local']}",
        "",
        "Chief critical-path tasks:",
        *[f"- {task['title']} ({task['target_repo']}, {task['priority']})" for task in payload["recommended_chief_tasks"]],
        "",
        "Mac Codex should handle:",
        *[f"- {task['title']}" for task in payload["recommended_mac_tasks"]],
        "",
        "PC Codex should handle:",
        *[f"- {task['title']}" for task in payload["recommended_pc_tasks"]],
        "",
        "Manual fallback:",
        f"- {payload['manual_fallback_plan']['operator_action']}",
        "",
        "Do not touch: email send, Gmail drafts/polling, Coupa/browser, workbook cells, invoice generation/export, ledger mutation, production business state, Repo B runtime, live model/tool action, or push.",
    ]
    return "\n".join(lines) + "\n"


def export_read_model(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_hermes_chief_build_handoff(generated_at=generated_at)
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(render_operator_summary(payload), encoding="utf-8")
    bridge_path = None
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_export_root / JSON_EXPORT_NAME
        shutil.copy2(json_path, bridge_path)
    return {
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "bridge_path": bridge_path.as_posix() if bridge_path else None,
        "handoff_ref": payload["handoff_ref"],
        "button_enabled": payload["button_enabled"],
        "chief_task_count": len(payload["recommended_chief_tasks"]),
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Hermes Chief build handoff read-model.")
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--bridge-export-root", default=DEFAULT_BRIDGE_EXPORT_ROOT.as_posix())
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    args = parser.parse_args(argv)
    result = export_read_model(
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
