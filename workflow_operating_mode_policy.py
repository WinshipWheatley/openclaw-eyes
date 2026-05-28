"""Workflow operating mode and channel runtime policy v0.

This compact policy distinguishes developer/build work from customer/operator
runtime work and describes what each channel can safely show. It is a
read-model contract only: no Telegram, email, browser, invoice generation,
ledger, model, tool, runtime, or production action authority is enabled here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "workflow_operating_mode_policy_v0"
READ_MODEL_ID = "workflow_operating_mode_policy"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_MODE_AND_CHANNEL_POLICY"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-28T00:00:00+00:00"

ACCESS_CLASSES = (
    "WINSHIP_DEVELOPER",
    "WINSHIP_OPERATOR",
    "CUSTOMER_OPERATOR",
    "CUSTOMER_ADMIN",
    "SYSTEM_DEVELOPER_AGENT",
)

OPERATING_MODES = (
    "WORKFLOW_SETUP",
    "HUMAN_TRIAL",
    "SHADOW_OR_DRY_RUN",
    "OPERATOR_RUNTIME",
    "CAPABILITY_GAP",
    "OPERATOR_CORRECTION",
    "MODULE_RUNTIME",
)

CHANNELS = ("APP", "TELEGRAM", "CLI", "EMAIL", "UNKNOWN")

WORKFLOW_RESPONSE_MODES = (
    "CHANNEL_NATIVE",
    "CHANNEL_NATIVE_WITH_LIMITS",
    "APP_HANDOFF_REQUIRED",
    "DEV_MODE_REQUIRED",
    "HUMAN_TRIAL_REQUIRED",
    "BLOCKED",
)

AUTHORITY_BOUNDARY = {
    "live_telegram_polling_allowed": False,
    "telegram_send_allowed": False,
    "email_send_allowed": False,
    "gmail_draft_creation_allowed": False,
    "gmail_polling_allowed": False,
    "coupa_access_allowed": False,
    "browser_automation_allowed": False,
    "workbook_cell_read_allowed": False,
    "invoice_generation_allowed": False,
    "ledger_posting_allowed": False,
    "production_mutation_allowed": False,
    "live_model_call_allowed": False,
    "tool_execution_allowed": False,
    "approval_execution_allowed": False,
    "file_delete_allowed": False,
    "network_action_allowed": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(payload)))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def access_class_policy() -> dict[str, dict[str, Any]]:
    return {
        "WINSHIP_DEVELOPER": {
            "can_receive_developer_tasks": True,
            "can_receive_tests_and_contract_gaps": True,
            "customer_safe_only": False,
            "operator_authority_supersedes_local_assumption": True,
            "can_bypass_external_action_receipts": False,
            "primary_copy_policy": "Developer details allowed only when setup, build, human trial, or capability gap mode calls for them.",
        },
        "WINSHIP_OPERATOR": {
            "can_receive_developer_tasks": False,
            "can_receive_tests_and_contract_gaps": False,
            "customer_safe_only": False,
            "operator_authority_supersedes_local_assumption": True,
            "can_bypass_external_action_receipts": False,
            "primary_copy_policy": "Runtime copy should say what happened, what is next, and what needs Winship's decision.",
        },
        "CUSTOMER_OPERATOR": {
            "can_receive_developer_tasks": False,
            "can_receive_tests_and_contract_gaps": False,
            "customer_safe_only": True,
            "operator_authority_supersedes_local_assumption": True,
            "can_bypass_external_action_receipts": False,
            "primary_copy_policy": "No backend contract language, Codex prompts, tests, or implementation details.",
        },
        "CUSTOMER_ADMIN": {
            "can_receive_developer_tasks": False,
            "can_receive_tests_and_contract_gaps": False,
            "customer_safe_only": True,
            "operator_authority_supersedes_local_assumption": True,
            "can_bypass_external_action_receipts": False,
            "primary_copy_policy": "Show module setup, connection, policy, and admin approval requirements without code tasks.",
        },
        "SYSTEM_DEVELOPER_AGENT": {
            "can_receive_developer_tasks": True,
            "can_receive_tests_and_contract_gaps": True,
            "customer_safe_only": False,
            "operator_authority_supersedes_local_assumption": False,
            "can_bypass_external_action_receipts": False,
            "primary_copy_policy": "Code-level tasks and tests allowed; production actions remain gated.",
        },
    }


def operating_mode_policy() -> dict[str, dict[str, Any]]:
    return {
        "WORKFLOW_SETUP": {
            "purpose": "Teach, refine, or build a workflow/module.",
            "default_response_mode": "CHANNEL_NATIVE_WITH_LIMITS",
            "developer_task_allowed_for": ("WINSHIP_DEVELOPER", "SYSTEM_DEVELOPER_AGENT"),
            "customer_copy": "This workflow needs setup before it can run.",
        },
        "HUMAN_TRIAL": {
            "purpose": "Try the workflow in the app or channel and record friction.",
            "default_response_mode": "HUMAN_TRIAL_REQUIRED",
            "developer_task_allowed_for": ("WINSHIP_DEVELOPER", "SYSTEM_DEVELOPER_AGENT"),
            "customer_copy": "Try this step and confirm what you see.",
        },
        "SHADOW_OR_DRY_RUN": {
            "purpose": "Run locally as proposed/draft/candidate output only.",
            "default_response_mode": "CHANNEL_NATIVE",
            "developer_task_allowed_for": (),
            "customer_copy": "Draft result only. Nothing external happened.",
        },
        "OPERATOR_RUNTIME": {
            "purpose": "Use an already-configured workflow.",
            "default_response_mode": "CHANNEL_NATIVE_WITH_LIMITS",
            "developer_task_allowed_for": (),
            "customer_copy": "Use the configured rails and ask only for missing proof, authority, ambiguity, or correction.",
        },
        "CAPABILITY_GAP": {
            "purpose": "The requested workflow needs an unbuilt or unauthorized capability.",
            "default_response_mode": "BLOCKED",
            "developer_task_allowed_for": ("WINSHIP_DEVELOPER", "SYSTEM_DEVELOPER_AGENT"),
            "customer_copy": "This module needs setup or does not support that feature yet.",
        },
        "OPERATOR_CORRECTION": {
            "purpose": "The operator corrected a workflow assumption.",
            "default_response_mode": "CHANNEL_NATIVE",
            "developer_task_allowed_for": (),
            "customer_copy": "Correction recorded. OpenClaw will not delete files or fake proof.",
        },
        "MODULE_RUNTIME": {
            "purpose": "Future packaged customer module runtime.",
            "default_response_mode": "CHANNEL_NATIVE_WITH_LIMITS",
            "developer_task_allowed_for": (),
            "customer_copy": "Show module readiness, setup needs, proof, approvals, and safe blockers only.",
        },
    }


def channel_capability_policy() -> dict[str, dict[str, Any]]:
    return {
        "APP": {
            "channel_ref": "APP",
            "supports_text_summary": True,
            "supports_structured_buttons": True,
            "supports_file_preview": True,
            "supports_image_preview": True,
            "supports_pdf_preview": True,
            "supports_file_upload": True,
            "supports_local_file_picker": True,
            "supports_rich_proof_disclosure": True,
            "supports_guardian_approval": True,
            "supports_thread_context": True,
            "supports_receipt_display": True,
            "supports_artifact_open_or_reveal": True,
            "known_limitations": (),
            "untested_capabilities": (),
            "safe_actions": ("summarize", "open_file_picker", "show_preview", "record_correction", "show_approval_button"),
            "blocked_actions": ("external_send_without_receipt", "submit_without_receipt", "ledger_post_without_receipt"),
            "handoff_required_when": (),
        },
        "TELEGRAM": {
            "channel_ref": "TELEGRAM",
            "supports_text_summary": True,
            "supports_structured_buttons": False,
            "supports_file_preview": False,
            "supports_image_preview": False,
            "supports_pdf_preview": False,
            "supports_file_upload": False,
            "supports_local_file_picker": False,
            "supports_rich_proof_disclosure": False,
            "supports_guardian_approval": False,
            "supports_thread_context": True,
            "supports_receipt_display": True,
            "supports_artifact_open_or_reveal": False,
            "known_limitations": ("No live Telegram integration is activated by this policy.",),
            "untested_capabilities": (
                "telegram_structured_buttons",
                "telegram_file_upload",
                "telegram_artifact_preview",
                "telegram_guardian_approval",
            ),
            "safe_actions": ("channel_native_summary", "record_correction", "request_operator_text_confirmation_if_policy_allows"),
            "blocked_actions": ("telegram_send", "telegram_polling", "guardian_approval_from_telegram_until_proven"),
            "handoff_required_when": (
                "local_file_picker_required",
                "artifact_open_or_reveal_required",
                "high_fidelity_artifact_review_required",
                "guardian_approval_requires_rich_proof",
            ),
        },
        "CLI": {
            "channel_ref": "CLI",
            "supports_text_summary": True,
            "supports_structured_buttons": False,
            "supports_file_preview": False,
            "supports_image_preview": False,
            "supports_pdf_preview": False,
            "supports_file_upload": False,
            "supports_local_file_picker": False,
            "supports_rich_proof_disclosure": True,
            "supports_guardian_approval": False,
            "supports_thread_context": True,
            "supports_receipt_display": True,
            "supports_artifact_open_or_reveal": False,
            "known_limitations": ("CLI is suitable for developer diagnostics, not rich customer approval UX.",),
            "untested_capabilities": (),
            "safe_actions": ("developer_diagnostics", "read_model_inspection", "dry_run_summary"),
            "blocked_actions": ("external_action_without_receipt",),
            "handoff_required_when": ("customer_rich_approval_required", "native_file_picker_required"),
        },
        "EMAIL": {
            "channel_ref": "EMAIL",
            "supports_text_summary": True,
            "supports_structured_buttons": False,
            "supports_file_preview": False,
            "supports_image_preview": False,
            "supports_pdf_preview": False,
            "supports_file_upload": False,
            "supports_local_file_picker": False,
            "supports_rich_proof_disclosure": False,
            "supports_guardian_approval": False,
            "supports_thread_context": True,
            "supports_receipt_display": False,
            "supports_artifact_open_or_reveal": False,
            "known_limitations": ("No live email/Gmail integration is activated by this policy.",),
            "untested_capabilities": ("email_reply_capture", "email_attachment_intake"),
            "safe_actions": ("plain_text_summary", "thread_context_reference"),
            "blocked_actions": ("email_send", "gmail_draft_creation", "gmail_polling"),
            "handoff_required_when": ("approval_required", "local_file_picker_required"),
        },
        "UNKNOWN": {
            "channel_ref": "UNKNOWN",
            "supports_text_summary": True,
            "supports_structured_buttons": False,
            "supports_file_preview": False,
            "supports_image_preview": False,
            "supports_pdf_preview": False,
            "supports_file_upload": False,
            "supports_local_file_picker": False,
            "supports_rich_proof_disclosure": False,
            "supports_guardian_approval": False,
            "supports_thread_context": False,
            "supports_receipt_display": False,
            "supports_artifact_open_or_reveal": False,
            "known_limitations": ("Unknown channel; fail closed to text summary and correction capture.",),
            "untested_capabilities": (),
            "safe_actions": ("plain_text_summary",),
            "blocked_actions": ("approval", "external_action", "file_selection", "artifact_preview"),
            "handoff_required_when": ("anything_beyond_plain_text_summary_required",),
        },
    }


def _normalize_channel(channel: str | None) -> str:
    value = (channel or "UNKNOWN").strip().upper()
    if value in {"MISSION_CONTROL", "MISSION_CONTROL_APP", "MAC_APP", "FINANCE_APP"}:
        return "APP"
    return value if value in CHANNELS else "UNKNOWN"


def _infer_mode(intent: str, *, customer_module: bool = False) -> str:
    lowered = intent.lower()
    if any(term in lowered for term in ("wrong workbook", "wrong client", "wrong page", "wrong recipient", "already gave you", "system is wrong", "no, that")):
        return "OPERATOR_CORRECTION"
    if "try" in lowered and "app" in lowered:
        return "HUMAN_TRIAL"
    if any(term in lowered for term in ("build", "setup", "teach", "refine", "needs to work from telegram")):
        return "WORKFLOW_SETUP"
    if any(term in lowered for term in ("generate the invoice pdf", "export selected", "generate pdf")):
        return "CAPABILITY_GAP"
    if customer_module:
        return "MODULE_RUNTIME"
    return "OPERATOR_RUNTIME"


def _live_arts_runtime_summary() -> tuple[str, ...]:
    return (
        "Invoice: 2026-1001",
        "Work: June 2026 Speaker Rental",
        "Amount: $900",
        "Status: draft, not sent",
        "Receipt status: unpaid",
        "Recipient package: Dane pending confirmation; CC Draper, Earnie, Winship",
        "Attachment: not ready",
        "Next step: confirm/generate/link invoice artifact.",
    )


def _package_plan_for(intent: str, *, client_ref: str | None, mode: str) -> dict[str, Any]:
    parent_ref = f"package_plan:{_short_hash(intent, client_ref, mode)}"
    steps: list[dict[str, Any]] = []
    if client_ref == "live_arts_md" and "invoice" in intent.lower():
        steps = [
            {
                "step_ref": "live_arts_md_step:select_invoice_candidate",
                "role": "Chief",
                "task": "Identify the selected Live Arts MD invoice candidate and current blockers.",
                "required_inputs": ("client_ref", "workflow_ref", "operator-provided candidate register"),
                "allowed_context": ("read-model refs", "operator-provided handoff facts"),
                "forbidden_context": ("workbook cells", "email/Gmail", "ledger transactions"),
                "authority_required": (),
                "expected_receipt": "invoice_candidate_selection_or_blocker_readback",
                "stop_condition": "invoice candidate missing or ambiguous",
                "next_step_if_passes": "live_arts_md_step:artifact_link",
                "next_step_if_blocked": "ask operator to choose invoice candidate",
            },
            {
                "step_ref": "live_arts_md_step:artifact_link",
                "role": "Finance",
                "task": "Link or request a generated invoice artifact without reading workbook cells.",
                "required_inputs": ("selected invoice candidate", "operator-provided artifact or generation authority"),
                "allowed_context": ("artifact metadata", "receipt refs"),
                "forbidden_context": ("workbook body", "PDF/XLSX generation without authority", "email send"),
                "authority_required": ("artifact link/generation authority receipt",),
                "expected_receipt": "operator_provided_invoice_artifact_linked_candidate_receipt",
                "stop_condition": "artifact missing or generation not authorized",
                "next_step_if_passes": "live_arts_md_step:recipient_confirmation",
                "next_step_if_blocked": "request manual export/link path",
            },
            {
                "step_ref": "live_arts_md_step:recipient_confirmation",
                "role": "Clara",
                "task": "Prepare recipient confirmation and draft package.",
                "required_inputs": ("Dane candidate", "Draper/Earnie/Winship CC candidates"),
                "allowed_context": ("confirmed contacts", "operator-provided emails"),
                "forbidden_context": ("invented emails", "Gmail send"),
                "authority_required": ("recipient_confirmation_receipt",),
                "expected_receipt": "clara_email_draft_receipt",
                "stop_condition": "recipient emails missing or unconfirmed",
                "next_step_if_passes": "live_arts_md_step:approval_request",
                "next_step_if_blocked": "ask operator to confirm recipients",
            },
            {
                "step_ref": "live_arts_md_step:approval_request",
                "role": "Guardian",
                "task": "Validate approval request readiness without sending.",
                "required_inputs": ("artifact receipt", "recipient receipt", "draft hash"),
                "allowed_context": ("proof refs", "draft package"),
                "forbidden_context": ("email send", "Gmail draft creation"),
                "authority_required": ("guardian_approval_request_receipt", "operator_approval_receipt"),
                "expected_receipt": "approval_request_or_blocker_receipt",
                "stop_condition": "approval prerequisites missing",
                "next_step_if_passes": "manual/send execution rail future gate",
                "next_step_if_blocked": "show approval prerequisites",
            },
        ]
    else:
        steps = [
            {
                "step_ref": "generic_step:scope_request",
                "role": "Chief",
                "task": "Classify request, workflow, channel, and missing capability.",
                "required_inputs": ("operator_intent", "channel", "access_class"),
                "allowed_context": ("read-model refs", "receipt refs"),
                "forbidden_context": ("external action", "credentials", "private raw bodies"),
                "authority_required": (),
                "expected_receipt": "classification_readback_receipt",
                "stop_condition": "missing workflow or capability",
                "next_step_if_passes": "bounded next package",
                "next_step_if_blocked": "capability gap or setup prompt",
            }
        ]
    return {
        "parent_intent": intent,
        "plan_ref": parent_ref,
        "package_steps": tuple(steps),
        "bounded": True,
        "receipt_oriented": True,
        "giant_vague_model_call_allowed": False,
    }


def classify_operating_context(
    *,
    operator_intent: str,
    access_class: str = "WINSHIP_OPERATOR",
    channel: str = "APP",
    client_ref: str | None = None,
    workflow_ref: str | None = None,
    module_ref: str | None = None,
    configured_workflow_available: bool = True,
    module_capability_available: bool = True,
    missing_capabilities: tuple[str, ...] = (),
    active_thread_ref: str | None = None,
) -> dict[str, Any]:
    access = access_class if access_class in ACCESS_CLASSES else "CUSTOMER_OPERATOR"
    normalized_channel = _normalize_channel(channel)
    mode = _infer_mode(operator_intent, customer_module=access.startswith("CUSTOMER") and bool(module_ref))
    if missing_capabilities or not module_capability_available:
        mode = "CAPABILITY_GAP" if mode != "OPERATOR_CORRECTION" else mode
    channel_policy = channel_capability_policy()[normalized_channel]
    requires_artifact_preview = any(term in operator_intent.lower() for term in ("preview", "open file", "file picker", "artifact review"))
    requires_approval = "approve" in operator_intent.lower()
    app_handoff_reason = None
    should_handoff = False
    if normalized_channel == "TELEGRAM":
        if requires_artifact_preview:
            should_handoff = True
            app_handoff_reason = "high_fidelity_artifact_review_required"
        elif requires_approval and not channel_policy["supports_guardian_approval"]:
            should_handoff = True
            app_handoff_reason = "guardian_approval_requires_rich_proof"
    should_surface_dev = access_class_policy()[access]["can_receive_developer_tasks"] and mode in {
        "WORKFLOW_SETUP",
        "CAPABILITY_GAP",
        "HUMAN_TRIAL",
    }
    response_mode = "APP_HANDOFF_REQUIRED" if should_handoff else operating_mode_policy()[mode]["default_response_mode"]
    if mode == "CAPABILITY_GAP" and should_surface_dev:
        response_mode = "DEV_MODE_REQUIRED"
    if mode == "CAPABILITY_GAP" and access.startswith("CUSTOMER"):
        response_mode = "BLOCKED"
    safe_next_step = _safe_next_step(
        operator_intent=operator_intent,
        mode=mode,
        access_class=access,
        channel=normalized_channel,
        client_ref=client_ref,
        missing_capabilities=tuple(missing_capabilities),
    )
    return {
        "access_class": access,
        "mode": mode,
        "confidence": "HIGH",
        "operator_intent_summary": operator_intent,
        "workflow_ref": workflow_ref,
        "client_ref": client_ref,
        "world_ref": "finance" if client_ref in {"live_arts_md", "capital_hilton"} else None,
        "module_ref": module_ref,
        "channel": normalized_channel,
        "active_thread_ref": active_thread_ref,
        "configured_workflow_available": configured_workflow_available,
        "module_capability_available": module_capability_available,
        "missing_capabilities": tuple(missing_capabilities),
        "required_receipts": _required_receipts_for(client_ref=client_ref, intent=operator_intent),
        "safe_next_step": safe_next_step,
        "should_run_workflow": mode in {"OPERATOR_RUNTIME", "MODULE_RUNTIME", "SHADOW_OR_DRY_RUN"} and not should_handoff,
        "should_start_human_trial": mode == "HUMAN_TRIAL",
        "should_surface_dev_task": should_surface_dev,
        "should_request_operator_input": mode in {"OPERATOR_CORRECTION", "OPERATOR_RUNTIME", "CAPABILITY_GAP"},
        "should_request_approval": False,
        "should_handoff_to_app": should_handoff,
        "app_handoff_reason": app_handoff_reason,
        "workflow_response_mode": response_mode,
        "right_sized_package_plan": _package_plan_for(operator_intent, client_ref=client_ref, mode=mode),
        "proof_refs": ("workflow_session_channel_projection_approval_bus_contract.json",),
        "operator_copy": _operator_copy(
            operator_intent=operator_intent,
            mode=mode,
            access_class=access,
            channel=normalized_channel,
            safe_next_step=safe_next_step,
            missing_capabilities=tuple(missing_capabilities),
            app_handoff_reason=app_handoff_reason,
        ),
        "channel_runtime": {
            "channel_policy": channel_policy,
            "telegram_unproven_not_impossible": normalized_channel != "TELEGRAM"
            or "telegram_artifact_preview" in channel_policy["untested_capabilities"],
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _required_receipts_for(*, client_ref: str | None, intent: str) -> tuple[str, ...]:
    if client_ref == "live_arts_md" and "invoice" in intent.lower():
        return (
            "source_workbook_reference_confirmed_receipt",
            "live_arts_md_invoice_candidate_selected_receipt",
            "invoice_attachment_confirmed_receipt",
            "recipient_confirmation_receipt",
            "guardian_approval_request_receipt",
            "operator_approval_receipt",
            "email_send_receipt",
        )
    return ("classification_readback_receipt",)


def _safe_next_step(
    *,
    operator_intent: str,
    mode: str,
    access_class: str,
    channel: str,
    client_ref: str | None,
    missing_capabilities: tuple[str, ...],
) -> str:
    lowered = operator_intent.lower()
    if mode == "OPERATOR_CORRECTION":
        if "wrong workbook" in lowered or "already gave" in lowered:
            return "Record the correction and ask the operator to choose or confirm the correct source workbook."
        return "Record the correction, preserve proof, and ask only for the missing confirmation."
    if mode == "HUMAN_TRIAL":
        return "Try this in the app or current channel and record what actually happens."
    if mode == "WORKFLOW_SETUP":
        if access_class == "CUSTOMER_OPERATOR":
            return "Start module setup and ask only for required configuration."
        return "Create a bounded build task for the missing workflow rails."
    if mode == "CAPABILITY_GAP":
        if missing_capabilities:
            missing = ", ".join(missing_capabilities)
        else:
            missing = "selected-sheet export/generation authority"
        if access_class in {"WINSHIP_DEVELOPER", "SYSTEM_DEVELOPER_AGENT"}:
            return f"Produce a bounded developer task for: {missing}."
        return f"This needs setup before it can run: {missing}."
    if client_ref == "live_arts_md" and "invoice" in lowered:
        return "Choose or confirm the invoice candidate, then link the invoice artifact and confirm recipients."
    if channel == "TELEGRAM":
        return "Provide a channel-native summary and offer only safe text/correction actions."
    return "Run the configured rails until missing proof, authority, ambiguity, or correction is reached."


def _operator_copy(
    *,
    operator_intent: str,
    mode: str,
    access_class: str,
    channel: str,
    safe_next_step: str,
    missing_capabilities: tuple[str, ...],
    app_handoff_reason: str | None,
) -> str:
    if mode == "OPERATOR_RUNTIME" and channel == "TELEGRAM" and "live arts" in operator_intent.lower():
        facts = "\n- ".join(_live_arts_runtime_summary())
        handoff = (
            f"\nApp handoff reason: {app_handoff_reason}."
            if app_handoff_reason
            else "\nTelegram artifact review is not proven yet; this summary can still continue the workflow safely."
        )
        return f"I started the Live Arts invoice flow. OpenClaw knows:\n- {facts}{handoff}"
    if mode == "CAPABILITY_GAP" and access_class in {"CUSTOMER_OPERATOR", "CUSTOMER_ADMIN"}:
        return "This module needs setup before that feature can run. No action was taken."
    if mode == "CAPABILITY_GAP":
        gap = ", ".join(missing_capabilities) if missing_capabilities else "missing generation/export authority"
        return f"Capability gap found: {gap}. {safe_next_step}"
    if mode == "OPERATOR_CORRECTION":
        return "Correction recorded as operator-provided. OpenClaw will not delete files, read workbook cells, or fake proof."
    return safe_next_step


def example_classifications() -> dict[str, dict[str, Any]]:
    return {
        "telegram_live_arts_send_invoice": classify_operating_context(
            operator_intent="Send the Live Arts invoice",
            access_class="WINSHIP_OPERATOR",
            channel="TELEGRAM",
            client_ref="live_arts_md",
            workflow_ref="live_arts_md_invoice_workflow",
        ),
        "winship_build_live_arts": classify_operating_context(
            operator_intent="Help me build the Live Arts invoice workflow",
            access_class="WINSHIP_DEVELOPER",
            channel="CLI",
            client_ref="live_arts_md",
            workflow_ref="live_arts_md_invoice_workflow",
            missing_capabilities=("manual artifact link rail",),
        ),
        "customer_build_live_arts": classify_operating_context(
            operator_intent="Help me build the Live Arts invoice workflow",
            access_class="CUSTOMER_OPERATOR",
            channel="APP",
            client_ref="live_arts_md",
            workflow_ref="live_arts_md_invoice_workflow",
            module_ref="simple_invoice_module",
            missing_capabilities=("module setup",),
        ),
        "wrong_workbook": classify_operating_context(
            operator_intent="No, that is the wrong workbook",
            access_class="WINSHIP_OPERATOR",
            channel="APP",
            client_ref="capital_hilton",
            workflow_ref="capital_hilton_invoice_workflow",
        ),
        "human_trial": classify_operating_context(
            operator_intent="Try this in the app",
            access_class="WINSHIP_DEVELOPER",
            channel="CLI",
        ),
        "telegram_setup_gap": classify_operating_context(
            operator_intent="This needs to work from Telegram",
            access_class="WINSHIP_DEVELOPER",
            channel="CLI",
            missing_capabilities=("telegram artifact review adapter",),
        ),
        "generate_invoice_pdf": classify_operating_context(
            operator_intent="Generate the invoice PDF",
            access_class="WINSHIP_OPERATOR",
            channel="APP",
            client_ref="live_arts_md",
            workflow_ref="live_arts_md_invoice_workflow",
            missing_capabilities=("selected-sheet export rail authorization",),
        ),
        "customer_runtime_module": classify_operating_context(
            operator_intent="Send this invoice",
            access_class="CUSTOMER_OPERATOR",
            channel="APP",
            client_ref="live_arts_md",
            workflow_ref="live_arts_md_invoice_workflow",
            module_ref="simple_invoice_module",
            module_capability_available=False,
            missing_capabilities=("module admin setup",),
        ),
    }


def build_workflow_operating_mode_policy(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "access_classes": ACCESS_CLASSES,
        "access_class_policy": access_class_policy(),
        "operating_modes": OPERATING_MODES,
        "operating_mode_policy": operating_mode_policy(),
        "channels": CHANNELS,
        "channel_capability_policy": channel_capability_policy(),
        "workflow_response_modes": WORKFLOW_RESPONSE_MODES,
        "channel_doctrine": {
            "telegram_first_class_operator_surface_until_proven_otherwise": True,
            "mission_control_is_richest_surface_not_only_real_surface": True,
            "do_not_default_to_open_mission_control": True,
            "handoff_requires_specific_limitation": True,
            "untested_capabilities_are_not_impossible": True,
            "channels_share_canonical_workflow_state": True,
            "related_contract_ref": "workflow_session_channel_projection_approval_bus_contract.json",
        },
        "operator_correction_policy": {
            "correction_first_class": True,
            "operator_authority_supersedes_local_assumption_inside_safe_bounds": True,
            "record_correction": True,
            "delete_files": False,
            "fake_proof": False,
            "explain_conflict_only_when_evidence_matters": True,
        },
        "right_sized_package_planner_policy": {
            "bounded_steps_required": True,
            "receipt_oriented": True,
            "giant_vague_model_calls_allowed": False,
            "external_action_stops_at_approval_or_request_receipt": True,
            "customer_operator_sees_customer_safe_copy_only": True,
            "winship_developer_can_receive_build_prompt": True,
        },
        "example_classifications": example_classifications(),
        "current_live_arts_md_mode_recommendation": classify_operating_context(
            operator_intent="Send the Live Arts invoice",
            access_class="WINSHIP_OPERATOR",
            channel="APP",
            client_ref="live_arts_md",
            workflow_ref="live_arts_md_invoice_workflow",
        ),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "read_model_only": True,
            "no_live_telegram_polling": True,
            "no_telegram_send": True,
            "no_email_send": True,
            "no_gmail_draft_creation": True,
            "no_coupa_browser": True,
            "no_workbook_cell_read": True,
            "no_invoice_generation": True,
            "no_ledger_posting": True,
            "no_production_mutation": True,
            "all_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def render_operator_summary(payload: Mapping[str, Any]) -> str:
    live = payload["current_live_arts_md_mode_recommendation"]
    lines = [
        "# Workflow Operating Mode Policy",
        "",
        "Read-model only. No Telegram, email, Coupa, browser, invoice generation, ledger, model, tool, or production action authority is enabled.",
        "",
        "## Access Classes",
        "",
        "- WINSHIP_DEVELOPER: build/debug details allowed when the mode calls for them.",
        "- WINSHIP_OPERATOR: runtime use with concise next steps and correction authority.",
        "- CUSTOMER_OPERATOR: no developer prompts; customer-safe setup/blocker copy only.",
        "- CUSTOMER_ADMIN: module setup and policy/admin approval, no code mode.",
        "- SYSTEM_DEVELOPER_AGENT: code-level tasks allowed, production actions still gated.",
        "",
        "## Channels",
        "",
        "- Mission Control app: rich preview, file picker, proof disclosure, approval buttons.",
        "- Telegram: first-class text operator surface; artifact review and approval are untested, not declared impossible.",
        "- CLI/dev: diagnostics and build tasks for developer access.",
        "",
        "## Current Live Arts MD Recommendation",
        "",
        f"- Mode: `{live['mode']}`",
        f"- Channel: `{live['channel']}`",
        f"- Next: {live['safe_next_step']}",
        "",
        "## Boundary",
        "",
        "- No live Telegram polling or send.",
        "- No email/Gmail, Coupa/browser, workbook/cell read, invoice generation/export, ledger posting, production mutation, live model call, or tool action.",
    ]
    return "\n".join(lines) + "\n"


def export_read_model(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_workflow_operating_mode_policy(generated_at=generated_at)
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
        "read_model_id": READ_MODEL_ID,
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export workflow operating mode policy read-model.")
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
