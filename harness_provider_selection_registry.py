"""Harness Provider Selection Registry V0.

Deterministic registry for choosing the right model/tool harness class per
outcome. Planning/registry only: no models are invoked, no external providers
are connected, no Codex automation is run, and no business authority is granted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Harness Provider Selection Registry.md")

SCHEMA_VERSION = "harness_provider_selection_registry_v0"
READ_MODEL_ID = "harness_provider_selection_registry"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "HARNESS_PROVIDER_SELECTION_READY"
NOT_READY_STATUS = "HARNESS_PROVIDER_SELECTION_NOT_READY"

PROVIDER_CLASSES = (
    "openclaw_local_deterministic",
    "pc_codex_backend_worker",
    "mac_codex_ui_worker",
    "codex_desktop_operator_assist",
    "local_llm_shadow_mode",
    "future_local_open_model",
    "external_llm_blocked_by_default",
    "google_workspace_connector_sunk_cost_exception",
    "browser_coupa_operator_assist",
)

REQUIRED_PRECONDITIONS = {
    "operator_assist_provider_registry": {
        "filename": "operator_assist_provider_registry.json",
        "required_status": "OPERATOR_ASSIST_PROVIDER_REGISTRY_READY",
    },
    "local_llm_intent_privacy_plan": {
        "filename": "local_llm_intent_privacy_upgrade_plan.json",
        "required_status": "LOCAL_LLM_INTENT_PRIVACY_PLAN_READY",
    },
}

OPTIONAL_PRECONDITIONS = {
    "worker_sandbox_policy": {
        "filename": "worker_sandbox_policy.json",
        "required_status": "WORKER_SANDBOX_POLICY_READY",
    },
    "sleep_safe_automation_registry": {
        "filename": "sleep_safe_automation_registry.json",
        "required_status": "SLEEP_SAFE_AUTOMATION_REGISTRY_READY",
    },
}

AUTHORITY_BOUNDARY = {
    "model_invocation_allowed": False,
    "external_provider_connect_allowed": False,
    "provider_key_material_access_allowed": False,
    "codex_automation_allowed": False,
    "worker_spawn_allowed": False,
    "worker_execution_allowed": False,
    "child_agent_run_allowed": False,
    "agent_loop_allowed": False,
    "tool_execution_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "calendar_write_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_open_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "business_action_allowed": False,
    "authority_grant_allowed": False,
    "credential_use_allowed": False,
    "git_push_allowed": False,
    "push_allowed": False,
    "sent": False,
    "paid": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "model_invoked",
    "external_provider_connected",
    "codex_automation_run",
    "email_send_performed",
    "gmail_access_performed",
    "calendar_write_performed",
    "browser_access_performed",
    "coupa_access_performed",
    "coupa_submit_performed",
    "ledger_mutation_performed",
    "workbook_open_performed",
    "workbook_body_read_performed",
    "spreadsheet_cell_read_performed",
    "workbook_mutation_performed",
    "pdf_export_performed",
    "paid_marking_performed",
    "submit_performed",
    "business_action_performed",
    "worker_spawn_performed",
    "worker_execution_performed",
    "child_agent_run_performed",
    "agent_loop_started",
    "git_push_performed",
}

SELECTION_CRITERIA = (
    "data_sensitivity",
    "local_file_access_needed",
    "gui_needed",
    "code_generation_needed",
    "writing_taste_needed",
    "deterministic_safety_needed",
    "unattended_eligibility",
    "cost_latency",
    "proof_receipt_needs",
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


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:12]


def _slug(value: object) -> str:
    text = str(value or "").strip().lower()
    cleaned = "".join(char if char.isalnum() else "_" for char in text).strip("_")
    return cleaned or "outcome"


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("contract_status") or "")


def _precondition_rows(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, spec in REQUIRED_PRECONDITIONS.items():
        payload = _load_json(root / str(spec["filename"]))
        observed = _status(payload)
        required = str(spec["required_status"])
        rows.append(
            {
                "precondition_ref": ref,
                "required": True,
                "present": bool(payload),
                "required_status": required,
                "observed_status": observed,
                "ready": observed == required,
                "source_ref": f"generated/read_models/{spec['filename']}",
            }
        )
    for ref, spec in OPTIONAL_PRECONDITIONS.items():
        path = root / str(spec["filename"])
        payload = _load_json(path)
        observed = _status(payload) if payload else "ABSENT_OPTIONAL"
        required = str(spec["required_status"])
        rows.append(
            {
                "precondition_ref": ref,
                "required": False,
                "present": bool(payload),
                "required_status": required,
                "observed_status": observed,
                "ready": (observed == required) if payload else True,
                "source_ref": f"generated/read_models/{spec['filename']}",
                "absence_policy": "non_blocking_optional" if not payload else "must_match_when_present",
            }
        )
    return rows


def _provider_record(
    *,
    provider_class: str,
    display_name: str,
    best_for: tuple[str, ...],
    data_boundary: str,
    default_use_policy: str,
    unattended_policy: str,
    cost_latency: str,
    proof_receipt_needs: tuple[str, ...],
    selection_notes: tuple[str, ...],
) -> dict[str, Any]:
    if provider_class not in PROVIDER_CLASSES:
        raise ValueError(f"unknown provider_class: {provider_class}")
    return {
        "provider_class": provider_class,
        "display_name": display_name,
        "best_for": list(best_for),
        "data_boundary": data_boundary,
        "default_use_policy": default_use_policy,
        "unattended_policy": unattended_policy,
        "cost_latency": cost_latency,
        "proof_receipt_needs": list(proof_receipt_needs),
        "selection_notes": list(selection_notes),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "provider_choice_grants_authority": False,
        "execution_now": False,
    }


def provider_records() -> list[dict[str, Any]]:
    return [
        _provider_record(
            provider_class="openclaw_local_deterministic",
            display_name="OpenClaw Local Deterministic Rails",
            best_for=("private invoices", "local metadata", "governed routing", "high-safety deterministic decisions"),
            data_boundary="local_generated_read_models_and_metadata",
            default_use_policy="default_for_private_invoices_and_deterministic_safety",
            unattended_policy="review_only_possible_no_business_action",
            cost_latency="lowest_cost_low_latency",
            proof_receipt_needs=("input criteria", "selected rule", "rejected provider reasons"),
            selection_notes=("Use when sensitive data or deterministic proof matters more than generative quality.",),
        ),
        _provider_record(
            provider_class="pc_codex_backend_worker",
            display_name="PC Codex Backend Worker Packet",
            best_for=("backend code generation", "Python tests", "generated read-model work", "local repository changes"),
            data_boundary="local_repo_only_after_operator_packet",
            default_use_policy="default_for_backend_code_tasks",
            unattended_policy="not_unattended_from_registry",
            cost_latency="local_codex_session_cost_known_latency_variable",
            proof_receipt_needs=("diff summary", "focused tests", "git diff check", "review packet receipt"),
            selection_notes=("Selection only means a future PC_CODEX packet is appropriate; it does not run Codex.",),
        ),
        _provider_record(
            provider_class="mac_codex_ui_worker",
            display_name="Mac Codex UI Worker Packet",
            best_for=("Mac UI work", "Mission Control display", "Excel GUI review surfaces", "screenshot receipts"),
            data_boundary="Mac-visible UI/context after operator packet",
            default_use_policy="default_for_mac_ui_or_gui_helper_outcomes",
            unattended_policy="not_unattended_from_registry",
            cost_latency="local_codex_session_cost_known_latency_variable",
            proof_receipt_needs=("screenshot proof", "UI contract tests", "review packet receipt"),
            selection_notes=("Use for GUI-required or Mac-only interface work; no workbook mutation authority is implied.",),
        ),
        _provider_record(
            provider_class="codex_desktop_operator_assist",
            display_name="Codex Desktop Operator Assist",
            best_for=("operator-present desktop assistance", "manual GUI checklist", "artifact inspection guidance"),
            data_boundary="operator_present_local_desktop",
            default_use_policy="only_behind_operator_present_gate",
            unattended_policy="never_unattended",
            cost_latency="operator_time_cost_latency_human_bound",
            proof_receipt_needs=("operator_assisted=true", "final human gate recorded", "artifact receipt"),
            selection_notes=("This is assistive guidance, not autonomous OpenClaw execution.",),
        ),
        _provider_record(
            provider_class="local_llm_shadow_mode",
            display_name="Local LLM Shadow Mode",
            best_for=("intent comparison", "privacy-gated shadow classification", "non-authoritative quality checks"),
            data_boundary="redacted_local_prompt_only",
            default_use_policy="shadow_only_until_local_runtime_gate_exists",
            unattended_policy="shadow_review_only_no_execution",
            cost_latency="local_runtime_cost_latency_unknown",
            proof_receipt_needs=("redaction proof", "deterministic comparison", "confidence score"),
            selection_notes=("Does not replace deterministic rails and cannot create business truth.",),
        ),
        _provider_record(
            provider_class="future_local_open_model",
            display_name="Future Local Open Model",
            best_for=("privacy-preserving writing help", "local summarization", "offline reasoning after approval"),
            data_boundary="future_local_runtime_only",
            default_use_policy="future_candidate_not_current_execution",
            unattended_policy="not_unattended_until_sleep_safe_registry_approves",
            cost_latency="future_local_compute_cost_latency_unknown",
            proof_receipt_needs=("runtime receipt", "privacy gate receipt", "output review receipt"),
            selection_notes=("Candidate class only; no runtime is connected by this registry.",),
        ),
        _provider_record(
            provider_class="external_llm_blocked_by_default",
            display_name="External LLM Blocked By Default",
            best_for=("explicit refusal class", "future approved low-sensitivity tokenized packets"),
            data_boundary="none_by_default",
            default_use_policy="blocked_for_local_code_client_files_and_private_invoices_unless_approved",
            unattended_policy="never_unattended_by_default",
            cost_latency="external_cost_latency_requires_gate",
            proof_receipt_needs=("approval receipt", "minimization receipt", "provider receipt"),
            selection_notes=("External LLM is a blocked class until a separate provider/privacy approval exists.",),
        ),
        _provider_record(
            provider_class="google_workspace_connector_sunk_cost_exception",
            display_name="Google Workspace Connector Sunk-Cost Exception",
            best_for=("Gmail or Calendar metadata/operator-assist where connector already exists",),
            data_boundary="connector_scope_only_after_gate",
            default_use_policy="may_be_considered_only_behind_google_workspace_gate",
            unattended_policy="never_unattended",
            cost_latency="sunk_cost_connector_but_permission_expensive",
            proof_receipt_needs=("gate receipt", "scope receipt", "operator-present receipt"),
            selection_notes=("Sunk cost is not authority; Gmail/Calendar use still needs a gate.",),
        ),
        _provider_record(
            provider_class="browser_coupa_operator_assist",
            display_name="Browser/Coupa Operator Assist",
            best_for=("Coupa portal assist", "browser-based submission checklist", "operator-present portal proof"),
            data_boundary="operator_present_browser_only_after_gate",
            default_use_policy="only_for_coupa_or_browser_outcomes_with_final_human_gate",
            unattended_policy="never_unattended",
            cost_latency="operator_time_cost_latency_human_bound",
            proof_receipt_needs=("operator_assisted=true", "final Submit gate receipt", "portal status receipt"),
            selection_notes=("Coupa is operator-assist only; this registry cannot open browser/Coupa or submit.",),
        ),
    ]


def _rejection(provider_class: str, reasons: tuple[str, ...]) -> dict[str, Any]:
    return {
        "provider_class": provider_class,
        "usable": False,
        "reject_reasons": list(reasons),
    }


def select_provider_for_outcome(
    *,
    outcome_ref: str,
    outcome_label: str,
    data_sensitivity: str,
    local_file_access_needed: bool = False,
    gui_needed: bool = False,
    code_generation_needed: bool = False,
    writing_taste_needed: bool = False,
    deterministic_safety_needed: bool = False,
    unattended_requested: bool = False,
    cost_latency_priority: str = "balanced",
    proof_receipt_needs: tuple[str, ...] = (),
    target_platform: str = "",
    google_workspace_needed: bool = False,
    coupa_browser_needed: bool = False,
    external_llm_requested: bool = False,
    provider_gate_approved: bool = False,
) -> dict[str, Any]:
    text = f"{outcome_ref} {outcome_label} {data_sensitivity} {target_platform}".lower()
    rejected: list[dict[str, Any]] = []
    selected = "openclaw_local_deterministic"
    selection_reason = "Default to local deterministic rails for safety."
    usable_now = True
    gate_required = False
    blocked_by_default = False
    unattended_eligible = False

    private_or_local = any(
        token in data_sensitivity.lower()
        for token in ("private", "client", "invoice", "workbook", "proprietary", "local_code", "strict")
    ) or local_file_access_needed

    if external_llm_requested:
        selected = "external_llm_blocked_by_default"
        selection_reason = "External LLM was requested, but it is blocked by default for local code/client/private data."
        usable_now = False
        gate_required = True
        blocked_by_default = True
    elif coupa_browser_needed or "coupa" in text:
        selected = "browser_coupa_operator_assist"
        selection_reason = "Coupa/browser work requires operator-present browser assist with a final human gate."
        usable_now = False
        gate_required = True
        blocked_by_default = True
    elif google_workspace_needed or "gmail" in text or "calendar" in text:
        selected = "google_workspace_connector_sunk_cost_exception"
        selection_reason = "Google Workspace may use the sunk-cost connector exception only behind a gate."
        usable_now = False
        gate_required = True
        blocked_by_default = True
    elif code_generation_needed and ("backend" in text or "pc" in target_platform.lower()):
        selected = "pc_codex_backend_worker"
        selection_reason = "Backend code generation belongs in a future PC_CODEX worker packet with receipts."
        usable_now = False
        gate_required = True
    elif gui_needed or "ui" in text or "mac" in target_platform.lower() or "excel" in text or "workbook" in text:
        selected = "mac_codex_ui_worker"
        selection_reason = "GUI/Mac/workbook-helper work belongs in a future MAC_CODEX UI packet, not an external model."
        usable_now = False
        gate_required = True
    elif writing_taste_needed and not private_or_local:
        selected = "future_local_open_model"
        selection_reason = "Writing/taste work can prefer a future local open model candidate; no runtime is connected now."
        usable_now = False
        gate_required = True
    elif deterministic_safety_needed or private_or_local:
        selected = "openclaw_local_deterministic"
        selection_reason = "Sensitive or deterministic-safety work defaults to OpenClaw local deterministic rails."
        usable_now = True

    if private_or_local:
        rejected.append(
            _rejection(
                "external_llm_blocked_by_default",
                ("local_or_private_data", "provider_gate_missing" if not provider_gate_approved else "external_still_not_selected"),
            )
        )
    if selected != "browser_coupa_operator_assist":
        rejected.append(_rejection("browser_coupa_operator_assist", ("coupa_or_browser_gui_not_primary_outcome",)))
    if selected != "google_workspace_connector_sunk_cost_exception":
        rejected.append(_rejection("google_workspace_connector_sunk_cost_exception", ("gmail_calendar_not_primary_outcome",)))
    if unattended_requested and selected in {
        "browser_coupa_operator_assist",
        "google_workspace_connector_sunk_cost_exception",
        "codex_desktop_operator_assist",
        "pc_codex_backend_worker",
        "mac_codex_ui_worker",
        "external_llm_blocked_by_default",
    }:
        unattended_eligible = False
        gate_required = True
        blocked_by_default = True
    elif selected == "openclaw_local_deterministic" and not coupa_browser_needed and not google_workspace_needed:
        unattended_eligible = not private_or_local and deterministic_safety_needed

    return {
        "selection_id": f"harness_selection:{_slug(outcome_ref)}:{_short_hash(outcome_ref, outcome_label, data_sensitivity)}",
        "outcome_ref": outcome_ref,
        "outcome_label": outcome_label,
        "selected_provider_class": selected,
        "selection_reason": selection_reason,
        "usable_now": usable_now,
        "gate_required_before_use": gate_required,
        "blocked_by_default": blocked_by_default,
        "unattended_eligible": unattended_eligible,
        "provider_choice_grants_authority": False,
        "safe_to_invoke_model_now": False,
        "safe_to_connect_provider_now": False,
        "safe_to_run_codex_automation_now": False,
        "criteria": {
            "data_sensitivity": data_sensitivity,
            "local_file_access_needed": local_file_access_needed,
            "gui_needed": gui_needed,
            "code_generation_needed": code_generation_needed,
            "writing_taste_needed": writing_taste_needed,
            "deterministic_safety_needed": deterministic_safety_needed,
            "unattended_requested": unattended_requested,
            "cost_latency_priority": cost_latency_priority,
            "proof_receipt_needs": list(proof_receipt_needs),
            "target_platform": target_platform,
            "google_workspace_needed": google_workspace_needed,
            "coupa_browser_needed": coupa_browser_needed,
            "external_llm_requested": external_llm_requested,
            "provider_gate_approved": provider_gate_approved,
        },
        "rejected_provider_classes": rejected,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "required_receipts": list(
            dict.fromkeys(
                (
                    "selection_rule_receipt",
                    "authority_boundary_all_false",
                    "operator_gate_receipt_required_before_execution",
                    *proof_receipt_needs,
                )
            )
        ),
    }


def example_selections() -> list[dict[str, Any]]:
    return [
        select_provider_for_outcome(
            outcome_ref="private_workbook_workflow",
            outcome_label="Review private invoice workbook workflow and prepare GUI helper packet.",
            data_sensitivity="private_client_invoice_workbook",
            local_file_access_needed=True,
            gui_needed=True,
            proof_receipt_needs=("no_workbook_mutation", "screenshot_or_review_receipt"),
            target_platform="mac",
        ),
        select_provider_for_outcome(
            outcome_ref="backend_code_task",
            outcome_label="Implement backend read-model change with focused tests.",
            data_sensitivity="proprietary_local_code",
            local_file_access_needed=True,
            code_generation_needed=True,
            proof_receipt_needs=("diff_receipt", "focused_test_receipt"),
            target_platform="pc_backend",
        ),
        select_provider_for_outcome(
            outcome_ref="ui_task",
            outcome_label="Improve Mission Control Mac UI hierarchy.",
            data_sensitivity="internal_ui_code",
            local_file_access_needed=True,
            gui_needed=True,
            code_generation_needed=True,
            proof_receipt_needs=("screenshot_receipt", "ui_contract_test_receipt"),
            target_platform="mac_ui",
        ),
        select_provider_for_outcome(
            outcome_ref="coupa_operator_assist",
            outcome_label="Guide Coupa invoice submission with final human gate.",
            data_sensitivity="private_client_invoice_portal",
            gui_needed=True,
            coupa_browser_needed=True,
            proof_receipt_needs=("operator_assisted_receipt", "final_submit_gate_receipt"),
            target_platform="browser_coupa",
            unattended_requested=True,
        ),
        select_provider_for_outcome(
            outcome_ref="external_llm_request",
            outcome_label="Ask external LLM to reason over local client files.",
            data_sensitivity="private_client_files",
            local_file_access_needed=True,
            writing_taste_needed=True,
            external_llm_requested=True,
            proof_receipt_needs=("provider_gate_receipt", "data_minimization_receipt"),
        ),
        select_provider_for_outcome(
            outcome_ref="gmail_calendar_sunk_cost",
            outcome_label="Use Gmail or Calendar connector for operator-assisted metadata review.",
            data_sensitivity="private_operator_workspace",
            google_workspace_needed=True,
            proof_receipt_needs=("workspace_gate_receipt", "scope_receipt"),
        ),
    ]


def _walk_values(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    return sorted({key for key, value in _walk_values(payload) if key in UNSAFE_TRUE_KEYS and value is True})


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _precondition_rows(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    selections = example_selections()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Select the appropriate harness/provider class per outcome without invoking models, connecting providers, or granting authority.",
        "provider_classes": provider_records(),
        "selection_criteria": list(SELECTION_CRITERIA),
        "selection_rules": [
            "Proprietary code and local files default to local harnesses.",
            "Private invoices and workbooks default to local or Mac helper paths, not external LLMs.",
            "Gmail/Calendar may use the sunk-cost Google Workspace exception only behind a gate.",
            "Coupa/browser work is operator-assist only and never unattended by default.",
            "External LLMs are blocked by default for local code, client files, and private invoices unless a separate provider/privacy gate approves a minimized packet.",
            "Provider choice does not grant authority.",
            "Harness choice is per outcome, not brand loyalty.",
        ],
        "example_selections": selections,
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_refs": [
            "generated/read_models/operator_assist_provider_registry.json",
            "generated/read_models/local_llm_intent_privacy_upgrade_plan.json",
            "generated/read_models/worker_sandbox_policy.json (optional if present)",
            "generated/read_models/sleep_safe_automation_registry.json (optional if present)",
        ],
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "registry_only": True,
            "provider_choice_grants_authority": False,
            "models_invoked": False,
            "external_provider_connected": False,
            "codex_automation_run": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "calendar_write_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "coupa_submit_performed": False,
            "ledger_mutation_performed": False,
            "workbook_open_performed": False,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_action_performed": False,
            "worker_spawn_performed": False,
            "worker_execution_performed": False,
            "child_agent_run_performed": False,
            "agent_loop_started": False,
            "git_push_performed": False,
            "all_provider_classes_present": set(PROVIDER_CLASSES)
            == {record["provider_class"] for record in provider_records()},
            "external_llm_blocked_by_default": any(
                selection["selected_provider_class"] == "external_llm_blocked_by_default"
                and selection["blocked_by_default"] is True
                for selection in selections
            ),
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    return payload


def build_wiki(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Harness Provider Selection Registry",
        "",
        f"Status: `{payload.get('status', NOT_READY_STATUS)}`",
        "",
        "This registry chooses the right harness/provider class per outcome. It is planning-only and does not invoke models, connect providers, run Codex automation, or grant authority.",
        "",
        "## Provider Classes",
        "",
    ]
    for record in payload.get("provider_classes") or []:
        if not isinstance(record, Mapping):
            continue
        lines.extend(
            [
                f"### `{record.get('provider_class')}`",
                "",
                f"- Default policy: {record.get('default_use_policy')}",
                f"- Data boundary: {record.get('data_boundary')}",
                f"- Unattended policy: {record.get('unattended_policy')}",
                "",
            ]
        )
    lines.extend(["## Example Selections", ""])
    for selection in payload.get("example_selections") or []:
        if not isinstance(selection, Mapping):
            continue
        lines.extend(
            [
                f"- `{selection.get('outcome_ref')}` -> `{selection.get('selected_provider_class')}`",
                f"  - Reason: {selection.get('selection_reason')}",
                f"  - Usable now: `{str(selection.get('usable_now')).lower()}`",
                f"  - Gate required: `{str(selection.get('gate_required_before_use')).lower()}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No model invocation.",
            "- No external provider connection.",
            "- No Codex automation run.",
            "- No email, Gmail, browser, Coupa, ledger, workbook, PDF, submit, mark-paid, worker, child-agent, agent-loop, or git push authority.",
            "- Provider choice is per outcome and never grants authority.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_harness_provider_selection_registry(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    payload = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")

    bridge_path = ""
    if bridge_root is not None:
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_file = bridge_root / JSON_EXPORT_NAME
        shutil.copy2(json_path, bridge_file)
        bridge_path = bridge_file.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(payload), encoding="utf-8")
    return {
        "status": str(payload["status"]),
        "read_model_path": json_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
        "provider_class_count": str(len(payload["provider_classes"])),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Harness Provider Selection Registry V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_harness_provider_selection_registry(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['provider_class_count']} provider classes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
