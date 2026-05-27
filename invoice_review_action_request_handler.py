"""Invoice review guided action request handler v0.

Consumes invoice review bundle action payloads and returns guided fix-path
readbacks only. It does not execute external actions, open Coupa/browser/Gmail,
send email, generate/export invoices, read workbook cells, or mutate production
state.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import invoice_review_bundle
import invoice_review_state_machine


READ_MODEL_ID = "invoice_review_action_request_receipt"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
SCHEMA_VERSION = "invoice_review_action_request_handler_v0"

SUPPORTED_ACTIONS = {
    "confirm_source_workbook_reference",
    "replace_source_workbook_reference",
    "start_invoice_record_selection",
    "regenerate_or_link_invoice_artifact",
    "request_coupa_submission_proof",
    "review_and_confirm_recipients",
    "show_approval_prerequisites",
    "review_clara_draft_prerequisites",
    "edit_clara_draft_request",
    "prepare_send_approval_request",
    "setup_payment_watch_after_submission",
    "explain_invoice_review",
    "confirm_invoice_review_candidate",
    "open_invoice_workbook_candidate",
}

REQUEST_KINDS = {
    "INVOICE_REVIEW_ACTION_REQUEST",
    "INVOICE_REVIEW_GUIDED_ACTION_REQUEST",
    "invoice_review_guided_action_request",
}

AUTHORITY_BOUNDARY = {
    "coupa_browser_automation_allowed": False,
    "email_send_allowed": False,
    "gmail_access_allowed": False,
    "ledger_posting_allowed": False,
    "invoice_generation_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "production_mutation_allowed": False,
    "live_model_call_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _action_payload(raw_request: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = raw_request.get("hidden_request_payload")
    if isinstance(nested, Mapping):
        merged = dict(nested)
        for key in (
            "request_id",
            "source_request_id",
            "idempotency_key",
            "payload_hash",
            "created_at",
            "authority_boundary",
            "source_request_filename",
        ):
            if key in raw_request and key not in merged:
                merged[key] = raw_request[key]
        return merged
    return raw_request


def is_invoice_review_action_request(raw_request: Mapping[str, Any]) -> bool:
    payload = _action_payload(raw_request)
    request_type = str(payload.get("request_type") or payload.get("type") or raw_request.get("request_type") or raw_request.get("type") or "")
    action_kind = str(payload.get("action_kind") or raw_request.get("action_kind") or "")
    intended_use = str(payload.get("intended_use") or raw_request.get("intended_use") or "")
    return (
        request_type in REQUEST_KINDS
        or action_kind in SUPPORTED_ACTIONS
        or intended_use in SUPPORTED_ACTIONS
    )


def _current_action_index() -> dict[str, dict[str, Any]]:
    bundle = invoice_review_bundle.build_capital_hilton_bundle()
    actions: dict[str, dict[str, Any]] = {}
    for action in bundle.get("correction_actions") or ():
        if isinstance(action, Mapping):
            actions[str(action.get("action_kind") or "")] = dict(action)
    for step in bundle.get("review_proof_timeline") or ():
        if not isinstance(step, Mapping):
            continue
        for action in (step.get("primary_action"), *(step.get("secondary_actions") or ())):
            if isinstance(action, Mapping):
                actions[str(action.get("action_kind") or "")] = dict(action)
    return actions


def _missing_prerequisites() -> tuple[str, ...]:
    bundle = invoice_review_bundle.build_capital_hilton_bundle()
    return tuple(bundle.get("approval_footer", {}).get("approval_disabled_reasons") or ())


def _operator_copy(action_kind: str) -> tuple[str, str, str, str, tuple[str, ...]]:
    missing = _missing_prerequisites()
    if action_kind == "start_invoice_record_selection":
        return (
            "Starting invoice page selection",
            "Let's select the Capital Hilton invoice page/period.",
            "OpenClaw needs the invoice record before it can link the generated artifact.",
            "Choose the invoice page or period in Mission Control.",
            ("invoice_record_selection_request_receipt",),
        )
    if action_kind == "request_coupa_submission_proof":
        return (
            "Starting Coupa proof step",
            "Coupa proof is required before this invoice can be treated as sent.",
            "Upload or provide the Coupa submission proof when it is available. Nothing will be submitted from this step.",
            "Provide Coupa submission proof when available.",
            ("coupa_submission_proof_intake_receipt",),
        )
    if action_kind == "review_and_confirm_recipients":
        return (
            "Review recipients",
            "Review the Capital Hilton recipient candidates: Annette, Chyna, and Will.",
            "Confirm or edit the contact details before any email approval request can be prepared.",
            "Confirm or edit recipient details.",
            ("recipient_confirmation_request_receipt",),
        )
    if action_kind == "show_approval_prerequisites":
        missing_text = ", ".join(missing) if missing else "approval prerequisites"
        return (
            "Approval is not ready yet",
            f"Missing: {missing_text}.",
            "Guardian output validation is only safe-to-show proof. It is not operator approval or send authority.",
            "Resolve the missing prerequisites first.",
            ("approval_prerequisite_review_receipt",),
        )
    if action_kind == "replace_source_workbook_reference":
        return (
            "Choose the correct source workbook",
            "Choose the correct source workbook.",
            "OpenClaw will replace the reference only after the new workbook is selected and approved. No file will be deleted.",
            "Choose the correct workbook in Mission Control.",
            ("source_workbook_replacement_request_receipt",),
        )
    if action_kind == "regenerate_or_link_invoice_artifact":
        return (
            "Invoice artifact needs linkage",
            "OpenClaw needs to regenerate or link the invoice artifact after the correct invoice page/period is selected.",
            "No invoice was generated or exported from this step.",
            "Select the invoice page/period, then link or regenerate the artifact through the governed path.",
            ("generated_invoice_artifact_linkage_request_receipt",),
        )
    if action_kind == "review_clara_draft_prerequisites":
        return (
            "Review Clara draft prerequisites",
            "Clara's draft can stay visible as draft-only.",
            "Recipients, invoice selection, artifact linkage, Coupa proof, and approval remain separate.",
            "Review the missing prerequisites before requesting approval.",
            ("clara_draft_prerequisite_review_receipt",),
        )
    if action_kind == "edit_clara_draft_request":
        return (
            "Draft edit is not wired yet",
            "The Clara draft edit path is not wired yet.",
            "Nothing was changed or sent.",
            "Use the visible draft text for manual review until the edit path is connected.",
            ("clara_draft_edit_request_receipt",),
        )
    if action_kind == "prepare_send_approval_request":
        missing_text = ", ".join(missing) if missing else "send prerequisites"
        return (
            "Send approval is blocked",
            f"Prepare-send is blocked until prerequisites are ready. Missing: {missing_text}.",
            "No send approval, email send, or Coupa submission happened.",
            "Resolve the invoice review blockers first.",
            ("send_approval_preparation_receipt",),
        )
    if action_kind == "setup_payment_watch_after_submission":
        return (
            "Payment watch is not ready",
            "Payment watch can be set up after submission/send proof exists.",
            "No payment status, ledger, or tax record was changed.",
            "Capture portal/email receipts first.",
            ("payment_watch_setup_receipt",),
        )
    if action_kind == "confirm_source_workbook_reference":
        return (
            "Confirm source workbook",
            "Confirm the source workbook for the Capital Hilton invoice review.",
            "This starts workbook-reference confirmation only. It does not read workbook cells.",
            "Confirm or replace the workbook reference.",
            ("active_workbook_confirmed_receipt",),
        )
    if action_kind == "confirm_invoice_review_candidate":
        return (
            "Invoice review confirmation started",
            "Confirm this invoice only after the workbook, page/period, artifact linkage, Coupa proof, and recipients are right.",
            "This does not approve sending or submitting anything.",
            "Review the missing prerequisites before approval.",
            ("invoice_review_confirmation_intake_receipt",),
        )
    if action_kind == "open_invoice_workbook_candidate":
        return (
            "Open workbook candidate",
            "Open the Mac-visible candidate file for inspection.",
            "This is an inspection action only. It does not mark the artifact current or attachment-ready.",
            "Inspect the candidate file, then confirm or correct the invoice page.",
            ("local_artifact_inspection_receipt",),
        )
    return (
        "Explain this review",
        "This review separates draft display, Coupa proof, Guardian approval, operator approval, and execution receipts.",
        "Nothing has been sent, submitted, posted, generated, or changed.",
        "Use a timeline action to start the next safe fix path.",
        ("invoice_review_explanation_receipt",),
    )


def process_action_request(
    raw_request: Mapping[str, Any],
    *,
    generated_at: str | None = None,
    db_path: Path = invoice_review_state_machine.DEFAULT_DB_PATH,
    export_root: Path = invoice_review_state_machine.DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = invoice_review_state_machine.DEFAULT_BRIDGE_EXPORT_ROOT,
) -> dict[str, Any]:
    payload = _action_payload(raw_request)
    request_id = str(raw_request.get("request_id") or payload.get("request_id") or payload.get("source_request_id") or "unknown_invoice_review_action")
    action_kind = str(payload.get("action_kind") or payload.get("request_kind") or payload.get("intended_use") or "")
    if action_kind == "invoice_review_guided_action_request":
        action_kind = str(payload.get("request_kind") or "")
    bundle_id = str(payload.get("source_bundle_id") or raw_request.get("bundle_id") or raw_request.get("source_bundle_id") or "")
    workflow_ref = str(payload.get("source_workflow_id") or raw_request.get("workflow_ref") or payload.get("workflow_ref") or "")
    client_ref = str(payload.get("client_ref") or raw_request.get("client_ref") or "")
    no_external = payload.get("no_external_action") is True and not any(
        payload.get(flag) is True
        for flag in (
            "browser_automation_allowed",
            "email_send_allowed",
            "coupa_submit_allowed",
            "ledger_posting_allowed",
            "physical_deletion_allowed",
        )
    )
    current_actions = _current_action_index()
    bundle_action = current_actions.get(action_kind)
    valid_scope = (
        bundle_id == invoice_review_bundle.CAPITAL_HILTON_BUNDLE_ID
        and workflow_ref == invoice_review_bundle.CAPITAL_HILTON_WORKFLOW_REF
        and client_ref == "capital_hilton"
    )
    supported = action_kind in SUPPORTED_ACTIONS
    action_enabled = bool(bundle_action.get("enabled")) if bundle_action else supported
    action_disabled_reason = str((bundle_action or {}).get("disabled_reason") or "")
    can_start = valid_scope and supported and no_external and action_enabled
    if action_kind in {"prepare_send_approval_request", "setup_payment_watch_after_submission", "edit_clara_draft_request"}:
        can_start = False
        action_disabled_reason = action_disabled_reason or "This guided path is blocked until prerequisites exist."
    progress_result = None
    if valid_scope and supported and no_external:
        progress_result = invoice_review_state_machine.process_action(
            raw_request,
            db_path=db_path,
            export_root=export_root,
            bridge_export_root=bridge_export_root,
            generated_at=generated_at,
        )
        headline = progress_result.headline
        body = progress_result.body
        detail = progress_result.detail
        next_action = progress_result.next_action
        expected = (progress_result.action_receipt["receipt_name"],)
        status = "BLOCKED_PREREQUISITES" if str(progress_result.status).startswith("BLOCKED") else "GUIDED_ACTION_STARTED"
    elif not valid_scope:
        headline = "Invoice review action blocked"
        body = "OpenClaw could not start that invoice review action because the bundle, workflow, or client did not match."
        detail = "No guided path started; the current invoice review bundle scope did not match the request."
        status = "BLOCKED_SCOPE_MISMATCH"
        next_action = "Use the current Capital Hilton invoice review card."
        expected = ()
    elif not no_external:
        headline = "Invoice review action blocked"
        body = "OpenClaw blocked this action because the request tried to include external authority."
        detail = "No guided path started; invoice review buttons cannot carry external action authority."
        status = "BLOCKED_EXTERNAL_AUTHORITY"
        next_action = "Retry with no external action authority."
        expected = ()
    elif not supported:
        headline = "Invoice review action not wired"
        body = "That invoice review action is not wired yet."
        detail = "No guided path started; the backend has no supported handler for this invoice review action."
        status = "BLOCKED_UNSUPPORTED_ACTION"
        next_action = "Use one of the visible enabled invoice review actions."
        expected = ()
    elif not can_start:
        headline, body, detail, next_action, expected = _operator_copy(action_kind)
        status = "BLOCKED_PREREQUISITES"
        if action_disabled_reason:
            body = f"{body} {action_disabled_reason}"
    else:
        headline, body, detail, next_action, expected = _operator_copy(action_kind)
        status = "GUIDED_ACTION_STARTED"
    receipt = {
        "receipt_id": f"invoice_review_action_start:{_short_hash(request_id, action_kind, status)}",
        "receipt_type": "guided_action_start_receipt",
        "source_request_id": request_id,
        "bundle_id": bundle_id,
        "workflow_ref": workflow_ref,
        "client_ref": client_ref,
        "action_kind": action_kind,
        "status": status,
        "expected_receipt_types": expected,
        "underlying_blocker_completed": False,
        "completion_receipt_written": False,
        "external_action_performed": False,
        "generated_at": generated_at,
    }
    if progress_result is not None:
        receipt["receipt_id"] = progress_result.action_receipt["receipt_id"]
        receipt["receipt_type"] = progress_result.action_receipt["receipt_type"]
        receipt["receipt_name"] = progress_result.action_receipt["receipt_name"]
        receipt["progress_status"] = progress_result.status
        receipt["underlying_blocker_completed"] = progress_result.action_receipt["underlying_blocker_completed"]
        receipt["completion_receipt_written"] = progress_result.action_receipt["completion_receipt_written"]
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "source_request_id": request_id,
        "action_kind": action_kind,
        "status": status,
        "headline": headline,
        "body": body,
        "detail": detail,
        "next_action": next_action,
        "expected_receipt_types": expected,
        "action_start_receipt": receipt,
        "state_machine_progress": {
            "used": progress_result is not None,
            "progress_status": progress_result.status if progress_result else None,
            "state_snapshot": progress_result.state_snapshot if progress_result else None,
            "action_progress_receipt": progress_result.action_receipt if progress_result else None,
            "source_bundle_path": progress_result.source_bundle_path if progress_result else None,
            "bridge_bundle_path": progress_result.bridge_bundle_path if progress_result else None,
            "bridge_mirror_written": progress_result.bridge_mirror_written if progress_result else False,
        },
        "bundle_action": bundle_action,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "bundle_scope_valid": valid_scope,
            "supported_action": supported,
            "current_bundle_action_found": bundle_action is not None,
            "no_external_action": no_external,
            "guided_path_started": status == "GUIDED_ACTION_STARTED",
            "completion_receipt_written": bool(progress_result.action_receipt["completion_receipt_written"]) if progress_result else False,
            "underlying_blocker_completed": bool(progress_result.action_receipt["underlying_blocker_completed"]) if progress_result else False,
            "bundle_refreshed": bool(progress_result),
            "bridge_bundle_mirrored": bool(progress_result and progress_result.bridge_mirror_written),
            "coupa_browser_automation_performed": False,
            "email_send_performed": False,
            "ledger_posting_performed": False,
            "invoice_generation_performed": False,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "production_mutation_performed": False,
            "all_authority_boundary_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def write_exports(payload: Mapping[str, Any], export_root: Path) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    lines = [
        "# Invoice Review Action Request",
        "",
        str(payload["headline"]),
        str(payload["body"]),
        "",
        f"- Action: {payload['action_kind']}",
        f"- Status: {payload['status']}",
        f"- Next: {payload['next_action']}",
        "- No email, Coupa, browser, ledger, generation, workbook read, or production action occurred.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path
