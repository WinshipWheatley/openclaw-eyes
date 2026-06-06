"""Goldilocks gate calibration V0.

Contract/read-model only. This defines how much agentic work is safe at each
gate level without loosening live gates, granting business authority, invoking
models, connecting providers, spawning workers, or touching ledgers/workbooks.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Goldilocks Gate Calibration.md")

SCHEMA_VERSION = "goldilocks_gate_calibration_v0"
READ_MODEL_ID = "goldilocks_gate_calibration"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "GOLDILOCKS_GATE_CALIBRATION_READY"
NOT_READY_STATUS = "GOLDILOCKS_GATE_CALIBRATION_NOT_READY"

PRECONDITIONS = {
    "operator_controller_protocol": {
        "filename": "operator_controller_protocol.json",
        "accepted_statuses": ("OPERATOR_CONTROLLER_PROTOCOL_READY",),
    },
    "objective_advancement_protocol": {
        "filename": "objective_advancement_protocol.json",
        "accepted_statuses": ("OBJECTIVE_ADVANCEMENT_PROTOCOL_READY",),
    },
    "proof_to_response_tdd_spec": {
        "filename": "proof_to_response_tdd_spec.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_TDD_SPEC_READY",),
    },
    "harness_provider_selection": {
        "filename": "harness_provider_selection_registry.json",
        "accepted_statuses": ("HARNESS_PROVIDER_SELECTION_READY",),
    },
    "gate_decision_ledger": {
        "filename": "gate_decision_ledger.json",
        "accepted_statuses": ("GATE_DECISION_LEDGER_READY",),
    },
    "approval_request_queue": {
        "filename": "approval_request_queue.json",
        "accepted_statuses": ("APPROVAL_REQUEST_QUEUE_READY",),
    },
}

AUTHORITY_BOUNDARY = {
    "authority_grant_allowed": False,
    "protected_actions_allowed": False,
    "external_action_allowed": False,
    "business_action_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "workbook_source_mutation_allowed": False,
    "pdf_export_allowed": False,
    "credential_use_allowed": False,
    "secret_access_allowed": False,
    "external_llm_allowed": False,
    "local_model_runtime_allowed": False,
    "provider_expansion_allowed": False,
    "worker_spawn_allowed": False,
    "live_loop_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "sent": False,
    "paid": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "authority_granted",
    "business_action_performed",
    "email_send_performed",
    "gmail_access_performed",
    "browser_access_performed",
    "coupa_access_performed",
    "portal_submit_performed",
    "submit_performed",
    "ledger_posting_performed",
    "ledger_mutation_performed",
    "paid_marking_performed",
    "workbook_mutation_performed",
    "workbook_source_mutation_performed",
    "pdf_export_performed",
    "credential_use_performed",
    "secret_access_performed",
    "external_llm_invoked",
    "external_provider_connected",
    "local_model_runtime_connected",
    "provider_expansion_performed",
    "worker_spawn_performed",
    "live_loop_started",
    "git_push_performed",
    "merge_performed",
}

PROTECTED_FINAL_CAPABILITIES = (
    "send_email",
    "open_gmail",
    "open_browser_or_coupa",
    "submit_portal",
    "post_ledger",
    "mark_paid",
    "mutate_source_workbook",
    "export_pdf",
    "use_credentials_or_secrets",
    "invoke_external_llm",
    "connect_local_model_runtime",
    "expand_live_provider_or_tool",
    "spawn_worker_or_live_loop",
    "git_push",
    "git_merge",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("contract_status") or "")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, spec in PRECONDITIONS.items():
        payload = _load_json(root / str(spec["filename"]))
        observed = _status(payload)
        accepted = list(spec["accepted_statuses"])
        rows.append(
            {
                "precondition_ref": ref,
                "source_ref": f"generated/read_models/{spec['filename']}",
                "accepted_statuses": accepted,
                "observed_status": observed,
                "ready": observed in accepted,
            }
        )
    return rows


def _level(
    *,
    level: int,
    gate_ref: str,
    name: str,
    allowed_capabilities: tuple[str, ...],
    forbidden_capabilities: tuple[str, ...],
    required_proof: tuple[str, ...],
    required_receipt: tuple[str, ...],
    allowed_agent_behavior: tuple[str, ...],
    required_stop_conditions: tuple[str, ...],
    examples: tuple[str, ...],
    failure_mode_if_too_strict: str,
    failure_mode_if_too_loose: str,
    future_gated_only: bool = False,
    currently_available: bool = True,
) -> dict[str, Any]:
    return {
        "level": level,
        "gate_ref": gate_ref,
        "name": name,
        "currently_available": currently_available,
        "future_gated_only": future_gated_only,
        "allowed_capabilities": list(allowed_capabilities),
        "forbidden_capabilities": list(forbidden_capabilities),
        "required_proof": list(required_proof),
        "required_receipt": list(required_receipt),
        "allowed_agent_behavior": list(allowed_agent_behavior),
        "required_stop_conditions": list(required_stop_conditions),
        "examples": list(examples),
        "failure_mode_if_too_strict": failure_mode_if_too_strict,
        "failure_mode_if_too_loose": failure_mode_if_too_loose,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "authority_granted": False,
    }


def gate_levels() -> list[dict[str, Any]]:
    return [
        _level(
            level=0,
            gate_ref="readback",
            name="Readback",
            allowed_capabilities=(
                "answer_from_existing_proof",
                "summarize_verified_read_models",
                "explain_missing_proof",
                "name_blocked_gate",
            ),
            forbidden_capabilities=(
                "mutation",
                "command_execution",
                "stage_package",
                "create_draft_artifact",
                "external_action",
                "authority_grant",
            ),
            required_proof=(
                "proof/read-model/receipt reference for factual claims",
                "explicit no-mutation boundary",
            ),
            required_receipt=("source_refs_only_no_state_change_receipt",),
            allowed_agent_behavior=(
                "answer briefly from proof",
                "ask the smallest missing-proof question",
                "stop before changing state",
            ),
            required_stop_conditions=(
                "operator asks for mutation or execution",
                "proof is missing for a factual claim",
                "answer would imply paid/sent/submitted truth without receipt",
            ),
            examples=(
                "explain why a payment remains on watch",
                "read back which gate blocks Coupa submit",
            ),
            failure_mode_if_too_strict="Agents become status surfaces that cannot explain blockers or next safe moves.",
            failure_mode_if_too_loose="Generated text becomes unproven truth or quietly triggers state changes.",
        ),
        _level(
            level=1,
            gate_ref="plan",
            name="Plan",
            allowed_capabilities=(
                "propose_plan",
                "decompose_scope",
                "identify_required_proof",
                "recommend_next_gate_level",
                "draft_package_outline_in_response_only",
            ),
            forbidden_capabilities=(
                "stage_package",
                "create_package_or_draft_artifact",
                "edit_files",
                "run_checks",
                "external_action",
                "authority_grant",
            ),
            required_proof=(
                "objective reference",
                "scope boundary",
                "known precondition refs",
            ),
            required_receipt=("planning_receipt_no_artifact_created",),
            allowed_agent_behavior=(
                "propose a package or plan",
                "state assumptions and blockers",
                "request promotion before staging",
            ),
            required_stop_conditions=(
                "package artifact would be created",
                "execution would begin",
                "scope or authority is ambiguous",
            ),
            examples=(
                "repair proposal",
                "approval path design",
                "test plan before a code package",
            ),
            failure_mode_if_too_strict="Agents ask for too much babysitting before they can reason through the work.",
            failure_mode_if_too_loose="Plans quietly become staged artifacts or execution without promotion.",
        ),
        _level(
            level=2,
            gate_ref="stage",
            name="Stage",
            allowed_capabilities=(
                "stage_package",
                "create_draft_artifact_in_approved_workspace",
                "create_review_packet",
                "collect_proof_refs",
                "prepare_non_executing_artifact_manifest",
            ),
            forbidden_capabilities=(
                "external_action",
                "send_submit_post_or_mark_paid",
                "source_workbook_mutation",
                "git_push_or_merge",
                "worker_spawn",
                "authority_grant",
            ),
            required_proof=(
                "package scope and approved workspace path",
                "artifact manifest",
                "source/proof refs for claims in the staged package",
            ),
            required_receipt=(
                "staging_receipt",
                "artifact_manifest_receipt",
                "no_external_action_receipt",
            ),
            allowed_agent_behavior=(
                "create drafts and review artifacts",
                "attach proof refs",
                "leave final actions blocked",
            ),
            required_stop_conditions=(
                "artifact would leave approved workspace",
                "request asks for final external action",
                "draft would claim completed business truth",
            ),
            examples=(
                "email draft for review",
                "ledger review packet",
                "approval package skeleton",
            ),
            failure_mode_if_too_strict="Useful drafts, review packets, and proof packages never materialize.",
            failure_mode_if_too_loose="A staged artifact is mistaken for send/submit/ledger authority.",
        ),
        _level(
            level=3,
            gate_ref="safe_internal_work",
            name="Safe Internal Work",
            allowed_capabilities=(
                "local_deterministic_checks",
                "local_draft_generation",
                "local_artifact_prep",
                "repo_inspect_edit_test",
                "commit_after_validation_if_package_grants",
                "read_model_generation",
            ),
            forbidden_capabilities=PROTECTED_FINAL_CAPABILITIES,
            required_proof=(
                "package grants local workspace/repo scope",
                "diff or artifact manifest",
                "focused test/check receipt",
                "no protected action proof",
            ),
            required_receipt=(
                "command/test receipt",
                "diff summary",
                "artifact manifest",
                "commit hash only when package grants commit and validation passes",
            ),
            allowed_agent_behavior=(
                "inspect, patch, test, and prepare local artifacts inside scope",
                "commit local repo changes when package grants it and validation passes",
                "stop at protected boundaries",
            ),
            required_stop_conditions=(
                "protected external action requested",
                "scope expands beyond package/workspace",
                "secret or credential access is required",
                "network/provider/runtime connection would be needed",
                "git push or merge would be needed",
            ),
            examples=(
                "Codex-like code patch inside repo",
                "OpenClaw self-repair patch with focused tests",
                "deterministic read-model generation",
            ),
            failure_mode_if_too_strict="OpenClaw collapses into forms/cards/status and cannot repair or prepare useful work.",
            failure_mode_if_too_loose="Local work crosses into protected business, external, provider, or source-data authority.",
        ),
        _level(
            level=4,
            gate_ref="prepare_approval",
            name="Prepare Approval",
            allowed_capabilities=(
                "fill_approval_package",
                "prepare_operator_review_packet",
                "attach_operator_provided_screenshot_or_proof",
                "draft_exact_payload_for_future_gate",
                "queue_non_executing_approval_request",
            ),
            forbidden_capabilities=(
                "final_submit",
                "send_email",
                "post_ledger",
                "mark_paid",
                "git_push_or_merge",
                "execute_approval_as_action",
                "authority_grant",
            ),
            required_proof=(
                "exact requested action and scope",
                "payload hash or artifact id",
                "supporting proof refs",
                "explicit list of blocked final actions",
            ),
            required_receipt=(
                "approval_request_receipt",
                "proof_package_manifest",
                "no_execution_receipt",
            ),
            allowed_agent_behavior=(
                "prepare the approval decision surface",
                "make the risk and blocked action explicit",
                "stop before final execution",
            ),
            required_stop_conditions=(
                "payload is broad or ambiguous",
                "supporting proof is missing",
                "operator wording could be interpreted as final execution authority",
            ),
            examples=(
                "Coupa submit approval package from captured proof",
                "email send approval packet",
                "Excel helper/export approval checklist",
            ),
            failure_mode_if_too_strict="Protected work never reaches an operator-ready decision package.",
            failure_mode_if_too_loose="Approval preparation is treated as send/submit/post/paid/push execution.",
        ),
        _level(
            level=5,
            gate_ref="execute_after_approval",
            name="Execute After Approval",
            allowed_capabilities=(
                "future_scoped_execution_after_verified_operator_approval",
                "guardian_gate_required",
                "receipt_requirements_required",
                "rollback_or_stop_conditions_required",
            ),
            forbidden_capabilities=(
                "current_execution_from_this_read_model",
                "execution_without_verified_operator_approval",
                "execution_without_guardian_gate",
                "execution_without_receipt",
                "broad_or_ambient_authority",
            ),
            required_proof=(
                "verified operator approval",
                "Guardian gate decision",
                "exact payload hash and scope",
                "preflight proof",
                "rollback/stop plan",
            ),
            required_receipt=(
                "execution_receipt",
                "post_action_verification_receipt",
                "rollback_or_stop_receipt_when_triggered",
            ),
            allowed_agent_behavior=(
                "future executor may act only after all gates and receipts exist",
                "fail closed on any mismatch",
            ),
            required_stop_conditions=(
                "approval missing or stale",
                "payload hash mismatch",
                "receipt path unavailable",
                "rollback/stop condition unavailable",
                "operator revokes or scope changes",
            ),
            examples=(
                "future gated email send",
                "future scoped Coupa submit",
                "future ledger posting with payment evidence",
            ),
            failure_mode_if_too_strict="Even explicitly approved work cannot complete, so operators must do everything manually.",
            failure_mode_if_too_loose="Final protected actions happen without a verified, scoped, receipted approval chain.",
            future_gated_only=True,
            currently_available=False,
        ),
        _level(
            level=6,
            gate_ref="never_or_future_gated",
            name="Never Or Future-Gated",
            allowed_capabilities=(
                "model_as_blocked",
                "draft_future_risk_analysis",
                "route_to_guardian_or_operator_for_new_contract",
            ),
            forbidden_capabilities=(
                "secrets_or_broad_credentials",
                "unbounded_browser_gmail_or_coupa",
                "ledger_posting",
                "paid_marking",
                "source_workbook_mutation",
                "git_push_or_merge",
                "live_worker_swarms",
                "live_provider_or_tool_expansion",
                "business_authority_grant",
            ),
            required_proof=(
                "separate explicit authority contract before any future consideration",
                "risk analysis and owner",
                "rollback/decommission plan for any future exception",
            ),
            required_receipt=(
                "blocked_gate_receipt",
                "future_contract_required_receipt",
            ),
            allowed_agent_behavior=(
                "refuse or hold the direct action",
                "explain exact future gate needed",
                "avoid using protected material",
            ),
            required_stop_conditions=(
                "direct request for secret/credential/material authority",
                "unbounded or ambient access requested",
                "ledger/paid/source-workbook/push/merge authority requested",
                "live swarm or provider expansion requested",
            ),
            examples=(
                "broad Gmail/Coupa/browser access",
                "marking paid without payment proof",
                "source workbook rewrite",
                "push/merge request",
                "live worker swarm",
            ),
            failure_mode_if_too_strict="Safe local planning or repo work gets overclassified as impossible.",
            failure_mode_if_too_loose="The system crosses protected authority boundaries that LMs must never invent.",
            future_gated_only=True,
            currently_available=False,
        ),
    ]


def gate_level_by_ref() -> dict[str, dict[str, Any]]:
    return {level["gate_ref"]: level for level in gate_levels()}


def scenario_calibrations() -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": "codex_like_code_patch_inside_repo",
            "title": "Codex-like code patch inside repo",
            "calibrated_gate_ref": "safe_internal_work",
            "allowed_now": [
                "inspect_repo",
                "edit_repo_files_in_package_scope",
                "run_focused_tests",
                "run_py_compile",
                "run_git_diff_check",
                "commit_after_validation_if_package_grants",
            ],
            "blocked_now": ["git_push", "git_merge", "external_llm", "worker_spawn"],
            "required_proof": ["package grants repo scope", "diff", "focused tests", "git diff --check"],
            "required_receipt": ["test receipt", "diff summary", "commit hash if committed"],
            "calibration_note": "Local repo work is useful safe_internal_work; push remains protected.",
        },
        {
            "scenario_id": "finance_payment_watch",
            "title": "Finance payment watch",
            "calibrated_gate_ref": "stage",
            "allowed_now": [
                "readback_payment_state_from_proof",
                "attach_payment_proof_reference",
                "stage_ledger_review_packet",
            ],
            "blocked_now": ["post_ledger", "mark_paid", "create_paid_truth_without_receipt"],
            "required_proof": ["payment proof refs", "ledger review refs", "no paid receipt present"],
            "required_receipt": ["evidence intake receipt", "ledger review staging receipt"],
            "calibration_note": "Proof attachment and review staging are useful; ledger/paid truth stays gated.",
        },
        {
            "scenario_id": "coupa_invoice_submit",
            "title": "Coupa invoice submit",
            "calibrated_gate_ref": "prepare_approval",
            "allowed_now": [
                "prepare_coupa_approval_package",
                "attach_operator_provided_screenshot",
                "draft_exact_submit_payload_for_review",
            ],
            "blocked_now": ["open_coupa_unbounded", "final_submit", "mark_submitted_without_receipt"],
            "required_proof": ["invoice packet refs", "operator-provided screenshot/proof refs", "payload hash"],
            "required_receipt": ["approval request receipt", "no-submit receipt"],
            "calibration_note": "Approval prep can become operator-ready; final submit waits for a future explicit gate.",
        },
        {
            "scenario_id": "excel_invoice_export",
            "title": "Excel invoice export",
            "calibrated_gate_ref": "prepare_approval",
            "allowed_now": [
                "stage_export_helper_package",
                "prepare_scoped_permission_request",
                "prepare_export_review_checklist",
            ],
            "future_scoped_only": [
                "run_helper_with_scoped_permission_and_receipt",
            ],
            "blocked_now": [
                "source_workbook_mutation",
                "pdf_export_without_gate",
                "open_or_rewrite_private_workbook_unbounded",
            ],
            "required_proof": ["source workbook identity", "helper scope", "operator permission", "receipt path"],
            "required_receipt": ["scoped helper receipt", "artifact/export receipt if future gate allows"],
            "calibration_note": "A helper may run only under scoped permission with receipts; source mutation needs its own explicit gate.",
        },
        {
            "scenario_id": "business_development_follow_up",
            "title": "Business Development follow-up",
            "calibrated_gate_ref": "stage",
            "allowed_now": ["draft_followup", "stage_review_copy", "prepare_send_approval_request"],
            "blocked_now": ["send_email", "open_gmail", "mark_sent_without_receipt"],
            "required_proof": ["thread/context refs", "draft artifact ref", "recipient/scope review"],
            "required_receipt": ["draft staging receipt", "no-send receipt"],
            "calibration_note": "Drafting and staging keep momentum; sending remains a protected action.",
        },
        {
            "scenario_id": "openclaw_self_repair",
            "title": "OpenClaw self-repair",
            "calibrated_gate_ref": "safe_internal_work",
            "allowed_now": [
                "diagnose_local_failure",
                "patch_repo_scope",
                "run_focused_tests",
                "commit_after_validation_if_package_grants",
            ],
            "blocked_now": ["service_restart_without_explicit_package", "live_loops", "worker_spawn", "git_push"],
            "required_proof": ["repo/package scope", "failure proof", "diff", "test receipt"],
            "required_receipt": ["repair receipt", "test receipt", "commit hash if committed"],
            "calibration_note": "Self-repair can patch and test locally; restart/live loops require explicit package authority.",
        },
    ]


def unsafe_true_grants(payload: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_path = f"{path}.{key}"
            if key in UNSAFE_TRUE_KEYS and value is True:
                findings.append(next_path)
            findings.extend(unsafe_true_grants(value, next_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(unsafe_true_grants(value, f"{path}[{index}]"))
    return findings


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    levels = gate_levels()
    scenarios = scenario_calibrations()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Define the Goldilocks zone for useful bounded agentic work without protected authority leakage.",
        "preconditions": preconditions,
        "gate_level_count": len(levels),
        "gate_levels": levels,
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "goldilocks_zone": {
            "freedom_for": [
                "planning",
                "drafting",
                "local inspection",
                "staging",
                "repair proposals",
                "proof collection",
                "review packets",
                "safe local deterministic checks",
                "repo patch/test/commit when package grants it",
            ],
            "strict_gates_for": [
                "external effects",
                "money",
                "sending",
                "submission",
                "ledger",
                "credentials",
                "source workbook mutation",
                "push/merge",
                "live provider/tool expansion",
                "live workers or loops",
            ],
            "core_rule": "Authority must be specific, scoped, receipted, and proven; generated language never creates truth or authority.",
        },
        "calibration_rules": [
            "Readback answers from proof and never mutates.",
            "Planning may propose packages but may not stage them without promotion.",
            "Staging creates local review artifacts only.",
            "Safe internal work may inspect, patch, test, generate, and commit locally when the package grants scope.",
            "Approval preparation creates exact proof packages but never executes final protected actions.",
            "Execute-after-approval is future-gated and unavailable from this read model.",
            "Never/future-gated actions require separate explicit contracts before any future execution path.",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "protected_final_capabilities": list(PROTECTED_FINAL_CAPABILITIES),
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "authority_granted": False,
            "business_action_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "portal_submit_performed": False,
            "submit_performed": False,
            "ledger_posting_performed": False,
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "workbook_mutation_performed": False,
            "workbook_source_mutation_performed": False,
            "pdf_export_performed": False,
            "credential_use_performed": False,
            "secret_access_performed": False,
            "external_llm_invoked": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
            "provider_expansion_performed": False,
            "worker_spawn_performed": False,
            "live_loop_started": False,
            "git_push_performed": False,
            "merge_performed": False,
            "execute_after_approval_currently_available": False,
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
        },
        "source_refs": [
            "generated/read_models/operator_controller_protocol.json",
            "generated/read_models/objective_advancement_protocol.json",
            "generated/read_models/proof_to_response_tdd_spec.json",
            "generated/read_models/harness_provider_selection_registry.json",
            "generated/read_models/gate_decision_ledger.json",
            "generated/read_models/approval_request_queue.json",
        ],
    }
    findings = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = findings
    payload["machine_proof"]["unsafe_true_grants_absent"] = not findings
    return payload


def format_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Goldilocks Gate Calibration",
        "",
        f"Status: {read_model['status']}",
        "",
        "This is a contract/read-model calibration surface. It does not loosen live gates, grant business authority, invoke LMs, connect providers, spawn workers, send, submit, mutate ledgers/workbooks, export PDFs, mark paid, or push.",
        "",
        "## Goldilocks Zone",
        "",
        "Agents should have enough room to plan, draft, inspect locally, stage packets, collect proof, prepare review packets, and perform scoped deterministic repo work. Protected external, financial, credential, source-data, provider, worker, push, and merge actions stay gated.",
        "",
        "## Gate Levels",
        "",
    ]
    for level in read_model["gate_levels"]:
        lines.extend(
            [
                f"### {level['level']}. {level['gate_ref']}",
                "",
                f"- Allowed: {', '.join(level['allowed_capabilities'])}",
                f"- Forbidden: {', '.join(level['forbidden_capabilities'])}",
                f"- Required proof: {', '.join(level['required_proof'])}",
                f"- Required receipt: {', '.join(level['required_receipt'])}",
                f"- Stop conditions: {', '.join(level['required_stop_conditions'])}",
                f"- Too strict: {level['failure_mode_if_too_strict']}",
                f"- Too loose: {level['failure_mode_if_too_loose']}",
                "",
            ]
        )
    lines.extend(["## Scenarios", ""])
    for scenario in read_model["scenarios"]:
        lines.extend(
            [
                f"### {scenario['title']}",
                "",
                f"- Gate: `{scenario['calibrated_gate_ref']}`",
                f"- Allowed now: {', '.join(scenario['allowed_now'])}",
                f"- Blocked now: {', '.join(scenario['blocked_now'])}",
                f"- Note: {scenario['calibration_note']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundary",
            "",
            "No email, Gmail/browser/Coupa access, portal submit, ledger post/mutation, paid marking, source workbook mutation, PDF export, credential/secret use, external LLM invocation, local model runtime connection, provider expansion, worker spawn, live loop, git push, or merge authority is granted here.",
            "",
        ]
    )
    return "\n".join(lines)


def export_goldilocks_gate_calibration(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_path = _rooted(export_root) / JSON_EXPORT_NAME
    bridge_path = _rooted(bridge_root) / JSON_EXPORT_NAME
    wiki_path = _rooted(wiki_path)
    _write_json(export_path, read_model)
    _write_json(bridge_path, read_model)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(format_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": str(export_path),
        "bridge_read_model_path": str(bridge_path),
        "wiki_path": str(wiki_path),
        "gate_level_count": str(read_model["gate_level_count"]),
        "scenario_count": str(read_model["scenario_count"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish Goldilocks Gate Calibration V0.")
    parser.add_argument("--read-model-root", type=Path, default=DEFAULT_READ_MODEL_ROOT)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--bridge-root", type=Path, default=DEFAULT_BRIDGE_ROOT)
    parser.add_argument("--wiki-path", type=Path, default=DEFAULT_WIKI_PATH)
    parser.add_argument("--format", choices=("summary", "json", "wiki"), default="summary")
    args = parser.parse_args(argv)
    result = export_goldilocks_gate_calibration(
        read_model_root=args.read_model_root,
        export_root=args.export_root,
        bridge_root=args.bridge_root,
        wiki_path=args.wiki_path,
    )
    if args.format == "json":
        print(Path(result["read_model_path"]).read_text(encoding="utf-8"), end="")
    elif args.format == "wiki":
        print(Path(result["wiki_path"]).read_text(encoding="utf-8"), end="")
    else:
        print(stable_json(result), end="")
    return 0


__all__ = [
    "AUTHORITY_BOUNDARY",
    "DEFAULT_BRIDGE_ROOT",
    "DEFAULT_EXPORT_ROOT",
    "DEFAULT_READ_MODEL_ROOT",
    "DEFAULT_WIKI_PATH",
    "JSON_EXPORT_NAME",
    "NOT_READY_STATUS",
    "PRECONDITIONS",
    "PROTECTED_FINAL_CAPABILITIES",
    "READY_STATUS",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "UNSAFE_TRUE_KEYS",
    "build_read_model",
    "export_goldilocks_gate_calibration",
    "format_wiki",
    "gate_level_by_ref",
    "gate_levels",
    "scenario_calibrations",
    "stable_json",
    "unsafe_true_grants",
]


if __name__ == "__main__":
    raise SystemExit(main())
