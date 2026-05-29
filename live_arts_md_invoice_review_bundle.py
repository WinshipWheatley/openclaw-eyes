"""Live Arts MD simple invoice review bundle v0.

This module proves the reusable email-invoice rails for a non-Coupa client.
It does not read workbook cells, generate/export invoices, send email, access
Gmail/Coupa/browser, post ledgers, or mutate production business state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

import client_invoice_workflow_framework as workflow
import client_comms_thread_rail
import clara_invoice_email_draft_package as clara_drafts
import client_invoice_workbook_registry
import live_arts_md_workbook_handoff
import local_artifact_reference


SCHEMA_VERSION = "live_arts_md_invoice_review_bundle_v0"
READ_MODEL_ID = "live_arts_md_invoice_review_bundle"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-28T00:00:00+00:00"

CLIENT_REF = "live_arts_md"
CLIENT_DISPLAY_NAME = "Live Arts MD"
WORKFLOW_REF = "live_arts_md_invoice_workflow"
EXPECTED_WORKBOOK_NAME = "Invoice Live Arts MD! Running.xlsx"
KNOWN_MANUAL_SEND_INVOICE_ID = "2026-1001"
KNOWN_MANUAL_SEND_WORK = "June 2026 Speaker Rental"
KNOWN_MANUAL_SEND_AMOUNT = 900
KNOWN_MANUAL_SEND_PROOF_ATTACHMENTS = "Live_Arts_MD_Speaker_Rental_Invoice_September_May_2026.pdf"
KNOWN_MANUAL_SEND_ARTIFACT_PATH = "/Users/hwinshipwheatley/Desktop/Live_Arts_MD_Speaker_Rental_Invoice_September_May_2026.pdf"
KNOWN_MANUAL_SEND_TO = ("Dane",)
KNOWN_MANUAL_SEND_CC = ("Draper", "Earnie", "Winship")
KNOWN_MANUAL_SEND_SUBJECT = "Live Arts MD invoice"
KNOWN_MANUAL_SEND_SEND_TIMESTAMP = "2026-05-28T14:32:00-04:00"
MANUAL_SEND_COMPLETION_REQUIRED_FIELDS = (
    "sent_timestamp",
    "to",
    "cc",
    "subject",
    "attachment_filename",
    "invoice_id",
    "amount",
    "work_or_period",
)
MANUAL_SEND_PROOF_STATUS_PENDING = "MANUAL_SEND_PROOF_PENDING"
MANUAL_SEND_PROOF_STATUS_CONFIRMED = "MANUAL_SEND_PROOF_CONFIRMED"
MANUAL_SEND_PROOF_CONFIRMED_RECEIPT = "manual_send_proof_confirmed_receipt"
PAYMENT_WATCH_STATUS_READY_TO_CONFIGURE = "READY_TO_CONFIGURE"
PAYMENT_WATCH_STATUS_READINESS_ONLY = "READINESS_ONLY_NOT_ACTIVE"
PDF_EXPORT_PACKAGE_READY_FOR_MAC = "PDF_EXPORT_PACKAGE_READY_FOR_MAC"
PDF_EXPORT_BLOCKED_MISSING_MAC_CAPABILITY = "PDF_EXPORT_BLOCKED_MISSING_MAC_CAPABILITY"
PDF_EXPORT_BLOCKED_MISSING_PRINT_SCOPE = "PDF_EXPORT_BLOCKED_MISSING_PRINT_SCOPE"
PDF_EXPORT_COMPLETED_CANDIDATE = "PDF_EXPORT_COMPLETED_CANDIDATE"
PDF_EXPORT_REQUIRES_OPERATOR_REVIEW = "PDF_EXPORT_REQUIRES_OPERATOR_REVIEW"
PDF_EXPORT_REQUIRED_CAPABILITY = "MAC_EXCEL_PDF_EXPORT"
PDF_EXPORT_EXECUTION_VENUE = "MAC_LOCAL"
PDF_EXPORT_OUTPUT_ARTIFACT_KIND = "PDF"
PDF_EXPORT_PACKAGE_REQUESTED_RECEIPT = "selected_invoice_pdf_export_requested_receipt"
PDF_EXPORT_COMPLETION_RECEIPT = "selected_invoice_pdf_export_completed_candidate"
PDF_EXPORT_PACKAGE_REQUEST_TEMPLATE = (
    "Prepare the selected Live Arts MD invoice PDF from {selected_sheet_label} on Mac with scoped print area."
)
PDF_EXPORT_SCOPE_REVIEW_TEMPLATE = "Confirm the selected sheet/print area for invoice {invoice_id}."
PROOF_CAPTURE_REF_REQUEST_TEMPLATE = (
    "Add sent-email screenshot or sent-mail proof for Live Arts MD invoice {invoice_id}."
)
LIVE_ARTS_MD_MANUAL_SEND_PROOF = {
    "execution_venue": "MAC_LOCAL",
    "execution_actor": "OPERATOR",
    "assistant_actor": "CODEX_DESKTOP_SPARK",
    "openclaw_executed": False,
    "manual_execution": True,
    "send_method": "manual_gmail",
    "artifact_exported_on": "MAC_EXCEL",
    "proof_required": True,
}

ALLOWED_ARTIFACT_EXTENSIONS = (".pdf", ".xlsx", ".xls", ".png", ".jpg", ".jpeg")

AUTHORITY_BOUNDARY = {
    "workbook_body_read_performed": False,
    "spreadsheet_cell_read_performed": False,
    "invoice_generation_performed": False,
    "pdf_export_performed": False,
    "email_send_performed": False,
    "gmail_access_performed": False,
    "coupa_access_performed": False,
    "browser_automation_performed": False,
    "ledger_posting_performed": False,
    "production_business_mutation_performed": False,
    "physical_deletion_performed": False,
    "external_action_performed": False,
    "live_gmail_polling_performed": False,
    "gmail_draft_created": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(payload)))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _as_sequence(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if isinstance(value, (list, tuple, set)):
        return tuple(
            str(item).strip()
            for item in value
            if str(item).strip()
        )
    return (str(value).strip(),) if str(value).strip() else ()


def _is_present_field(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set)):
        return bool(_as_sequence(value))
    if isinstance(value, bool):
        return value is True
    if isinstance(value, (int, float)):
        return True
    return bool(str(value).strip())


def _looks_like_path(value: str) -> bool:
    value = value.strip()
    return (
        value.startswith(("/", "./", "../", "~", "file://"))
        or (len(value) >= 3 and value[1] == ":" and value[2] in ("/", "\\") )
    )


def _proof_capture_metadata(value: object) -> dict[str, Any]:
    if not isinstance(value, str):
        return {
            "proof_ref": value,
            "is_path": False,
            "proof_path_status": "non_text_reference",
            "exists": False,
            "extension": None,
            "file_size": None,
            "sha256": None,
        }
    text = value.strip()
    if not text:
        return {
            "proof_ref": value,
            "is_path": False,
            "proof_path_status": "missing",
            "exists": False,
            "extension": None,
            "file_size": None,
            "sha256": None,
        }
    if not _looks_like_path(text):
        return {
            "proof_ref": value,
            "is_path": False,
            "proof_path_status": "reference_only",
            "exists": True,
            "extension": None,
            "file_size": None,
            "sha256": None,
        }
    path = Path(text[7:] if text.startswith("file://") else text).expanduser()
    if not path.exists() or not path.is_file():
        return {
            "proof_ref": value,
            "is_path": True,
            "proof_path_status": "missing",
            "path_candidate": path.as_posix(),
            "exists": path.exists(),
            "extension": path.suffix.lower(),
            "file_size": None,
            "sha256": None,
        }
    data = path.read_bytes()
    return {
        "proof_ref": value,
        "is_path": True,
        "proof_path_status": "metadata_valid",
        "path_candidate": path.as_posix(),
        "exists": True,
        "extension": path.suffix.lower(),
        "file_size": len(data),
        "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
    }


def _proof_capture_request(invoice_id: str, request_needed: bool) -> str | None:
    if not request_needed:
        return None
    return PROOF_CAPTURE_REF_REQUEST_TEMPLATE.format(invoice_id=invoice_id)


def _selected_invoice_pdf_export_package(
    *,
    selected_candidate: Mapping[str, Any] | None,
    source_workbook: Mapping[str, Any] | None,
    present_receipts: set[str],
) -> tuple[dict[str, Any], str | None]:
    invoice_id = str((selected_candidate or {}).get("invoice_id") or "")
    selected_sheet_label = str((selected_candidate or {}).get("sheet_label") or "")
    selected_print_areas = tuple(_as_sequence((selected_candidate or {}).get("operator_provided_ranges")))
    source_path = (
        str(
            (source_workbook or {}).get("workbook_path_ref")
            or (source_workbook or {}).get("source_workbook_mac_path")
            or (source_workbook or {}).get("workbook_path")
            or ""
        )
        if source_workbook is not None
        else ""
    )
    output_sheet_slug = (selected_sheet_label or "unknown-sheet").replace(" ", "_").replace("/", "_")
    output_path_policy = f"scoped_live_arts_md_export/{output_sheet_slug}/{invoice_id or 'selected-invoice'}.pdf"
    completion_receipt = PDF_EXPORT_COMPLETION_RECEIPT
    required_receipts: tuple[str, ...] = (completion_receipt,)
    package: dict[str, Any] = {
        "execution_venue": PDF_EXPORT_EXECUTION_VENUE,
        "required_capability": PDF_EXPORT_REQUIRED_CAPABILITY,
        "source_workbook_path": source_path,
        "selected_sheet_label": selected_sheet_label,
        "selected_print_areas": selected_print_areas,
        "invoice_id": invoice_id,
        "output_artifact_kind": PDF_EXPORT_OUTPUT_ARTIFACT_KIND,
        "output_path_policy": output_path_policy,
        "no_physical_printing": True,
        "no_email_send": True,
        "no_gmail": True,
        "no_ledger_post": True,
        "no_coupa": True,
        "no_source_workbook_mutation": True,
        "workbook_cell_read_required": False,
        "operator_review_required_after_export": True,
        "required_receipts": required_receipts,
        "request_receipt": PDF_EXPORT_PACKAGE_REQUESTED_RECEIPT,
        "missing_requirements": (),
        "proof_refs": tuple(),
        "request_payload_ready": bool(selected_candidate) and bool(source_path) and bool(selected_print_areas),
        "request_copy": PDF_EXPORT_PACKAGE_REQUEST_TEMPLATE.format(selected_sheet_label=selected_sheet_label or "unknown sheet"),
    }
    if not selected_candidate:
        package.update(
            {
                "status": PDF_EXPORT_REQUIRES_OPERATOR_REVIEW,
                "missing_requirements": ("selected_invoice_candidate",),
                "operator_review_prompt": PDF_EXPORT_SCOPE_REVIEW_TEMPLATE.format(invoice_id="selected invoice"),
                "prompt_invoice_id": invoice_id or "selected invoice",
            }
        )
        return package, completion_receipt
    if not source_path:
        package.update(
            {
                "status": PDF_EXPORT_BLOCKED_MISSING_MAC_CAPABILITY,
                "missing_requirements": ("source_workbook_path",),
                "operator_review_prompt": "Select the confirmed source workbook path before preparing invoice PDF.",
                "prompt_invoice_id": invoice_id or "selected invoice",
            }
        )
        return package, completion_receipt
    if not selected_print_areas:
        package.update(
            {
                "status": PDF_EXPORT_BLOCKED_MISSING_PRINT_SCOPE,
                "missing_requirements": ("selected_print_scope",),
                "operator_review_prompt": PDF_EXPORT_SCOPE_REVIEW_TEMPLATE.format(invoice_id=invoice_id),
                "prompt_invoice_id": invoice_id,
            }
        )
        return package, completion_receipt
    if completion_receipt in present_receipts:
        package["status"] = PDF_EXPORT_COMPLETED_CANDIDATE
    else:
        package["status"] = PDF_EXPORT_PACKAGE_READY_FOR_MAC
    return package, completion_receipt


def _normalize_manual_send_proof(
    *,
    manual_send_proof: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(manual_send_proof or {})
    payload.setdefault("execution_context", dict(LIVE_ARTS_MD_MANUAL_SEND_PROOF))
    execution = payload.get("execution_context")
    if not isinstance(execution, Mapping):
        execution = dict(LIVE_ARTS_MD_MANUAL_SEND_PROOF)
    payload["execution_context"] = dict(execution)
    payload.setdefault("attachment_filename", KNOWN_MANUAL_SEND_PROOF_ATTACHMENTS)
    payload.setdefault("invoice_id", KNOWN_MANUAL_SEND_INVOICE_ID)
    payload.setdefault("work_or_period", KNOWN_MANUAL_SEND_WORK)
    payload.setdefault("amount", KNOWN_MANUAL_SEND_AMOUNT)
    payload.setdefault("to", KNOWN_MANUAL_SEND_TO)
    payload.setdefault("cc", KNOWN_MANUAL_SEND_CC)
    payload.setdefault("subject", KNOWN_MANUAL_SEND_SUBJECT)
    payload.setdefault("sent_timestamp", KNOWN_MANUAL_SEND_SEND_TIMESTAMP)
    payload.setdefault("artifact_path", KNOWN_MANUAL_SEND_ARTIFACT_PATH)
    proof_refs = payload.get("proof_refs")
    if not isinstance(proof_refs, tuple):
        proof_refs = tuple(_as_sequence(proof_refs))
    payload["proof_refs"] = proof_refs
    payload.setdefault("proof_required", True)
    payload.setdefault("no_openclaw_send_claim", True)
    payload.setdefault("manual_send_receipt_available", False)
    payload.setdefault("proof_capture_required", ("screenshot_ref", "sent_mail_proof_ref"))
    return payload


def _manual_send_proof_status(
    *,
    manual_send_proof: Mapping[str, Any] | None,
    present_receipts: set[str],
) -> tuple[dict[str, Any], str]:
    payload = _normalize_manual_send_proof(manual_send_proof=manual_send_proof)
    present = [field for field in MANUAL_SEND_COMPLETION_REQUIRED_FIELDS if not _is_present_field(payload.get(field))]
    sent_proof_ref = (
        payload.get("screenshot_ref")
        or payload.get("sent_mail_proof_ref")
        or payload.get("manual_send_proof_ref")
    )
    has_screenshot_or_mail_proof = bool(sent_proof_ref)
    proof_capture_meta = _proof_capture_metadata(sent_proof_ref)
    missing_capture_fields: list[str] = []
    proof_capture_required = payload.get("proof_capture_required", ("screenshot_ref", "sent_mail_proof_ref"))
    if proof_capture_required is not False:
        if not has_screenshot_or_mail_proof:
            missing_capture_fields.append("proof screenshot/ref")
        elif proof_capture_meta.get("is_path") and not proof_capture_meta.get("exists"):
            missing_capture_fields.append("proof screenshot/ref")
    has_manual_send_receipt = "manual_send_receipt" in present_receipts
    has_confirmed_receipt = has_manual_send_receipt or payload.get("manual_send_receipt_available") is True
    proof_state = {
        "execution_context": payload["execution_context"],
        "artifact_path": payload["artifact_path"],
        "attachment_filename": payload["attachment_filename"],
        "invoice_id": payload["invoice_id"],
        "work_or_period": payload["work_or_period"],
        "amount": payload["amount"],
        "sent_timestamp": payload["sent_timestamp"],
        "subject": payload["subject"],
        "to": tuple(_as_sequence(payload.get("to"))),
        "cc": tuple(_as_sequence(payload.get("cc"))),
        "manual_send_receipt_available": bool(payload.get("manual_send_receipt_available", False)),
        "proof_required": bool(payload.get("proof_required", True)),
        "receipt_received": bool(has_confirmed_receipt),
        "proof_refs": tuple(_as_sequence(payload.get("proof_refs"))),
        "required_fields": MANUAL_SEND_COMPLETION_REQUIRED_FIELDS,
        "missing_required_fields": tuple([*present, *missing_capture_fields]),
        "proof_capture_provided": bool(bool(sent_proof_ref)),
        "proof_capture_fields": tuple(_as_sequence(payload.get("proof_capture_required"))),
        "proof_capture_metadata": proof_capture_meta,
        "proof_capture_request": _proof_capture_request(
            str(payload.get("invoice_id") or KNOWN_MANUAL_SEND_INVOICE_ID),
            bool(missing_capture_fields),
        ),
        "proof_receipts": (
            (MANUAL_SEND_PROOF_CONFIRMED_RECEIPT,)
            if has_confirmed_receipt and not present and not missing_capture_fields
            else ()
        ),
    }
    complete = (
        has_confirmed_receipt
        and not present
        and not missing_capture_fields
        and (
            (payload.get("proof_required") is False)
            or has_screenshot_or_mail_proof
            or (proof_capture_required is False)
        )
    )
    proof_status = (
        MANUAL_SEND_PROOF_STATUS_CONFIRMED
        if complete
        else MANUAL_SEND_PROOF_STATUS_PENDING
    )
    proof_state["proof_status"] = proof_status
    return proof_state, proof_status


def _workbook_records(payload: Mapping[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, Mapping):
        return ()
    records: list[dict[str, Any]] = []
    for key in ("active_record", "candidate_record", "existing_record"):
        item = payload.get(key)
        if isinstance(item, Mapping):
            records.append(dict(item))
    registry = payload.get("registry") if isinstance(payload.get("registry"), Mapping) else {}
    for item in registry.get("client_records") or ():
        if isinstance(item, Mapping):
            records.append(dict(item))
    filtered = [
        record
        for record in records
        if record.get("client_ref") == CLIENT_REF and record.get("workflow_ref") == WORKFLOW_REF
    ]
    deduped: dict[str, dict[str, Any]] = {}
    for record in filtered:
        deduped[str(record.get("workbook_ref") or _short_hash(record))] = record
    return tuple(deduped.values())


def inspect_source_workbook_state(
    *,
    workbook_registry_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = (
        workbook_registry_payload
        if workbook_registry_payload is not None
        else client_invoice_workbook_registry.load_existing_payload()
    )
    records = _workbook_records(payload)
    confirmed = next((record for record in records if record.get("workbook_status") == "WORKBOOK_CONFIRMED"), None)
    candidate = confirmed or (records[0] if records else None)
    status = "CONFIRMED" if confirmed else "CANDIDATE_ONLY" if candidate else "SOURCE_WORKBOOK_REQUIRED"
    return {
        "status": status,
        "client_ref": CLIENT_REF,
        "workflow_ref": WORKFLOW_REF,
        "expected_display_name": EXPECTED_WORKBOOK_NAME,
        "workbook_ref": candidate.get("workbook_ref") if candidate else None,
        "workbook_display_name": candidate.get("workbook_display_name") if candidate else None,
        "workbook_path_ref": candidate.get("workbook_path_ref") if candidate else None,
        "approved_for_metadata_read": bool(candidate.get("approved_for_metadata_read")) if candidate else False,
        "approved_for_cell_read": False,
        "no_workbook_body_read": True,
        "no_cell_read": True,
        "next_action": "Choose the Live Arts MD source workbook."
        if not confirmed
        else "Select the Live Arts MD invoice page/period.",
    }


def validate_operator_invoice_artifact_metadata(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    result: dict[str, Any] = {
        "path": path.as_posix(),
        "exists": path.exists(),
        "extension": suffix,
        "allowed_extension": suffix in ALLOWED_ARTIFACT_EXTENSIONS,
        "file_size": None,
        "sha256": None,
        "metadata_only": True,
        "body_read": False,
        "content_extracted": False,
    }
    if suffix not in ALLOWED_ARTIFACT_EXTENSIONS:
        result["status"] = "BLOCKED_EXTENSION_NOT_ALLOWED"
        return result
    if not path.exists() or not path.is_file():
        result["status"] = "BLOCKED_ARTIFACT_PATH_NOT_FOUND"
        return result
    data = path.read_bytes()
    result["file_size"] = len(data)
    result["sha256"] = "sha256:" + hashlib.sha256(data).hexdigest()
    result["status"] = "METADATA_VALID"
    return result


def _artifact_state(
    *,
    artifact_reference_payload: Mapping[str, Any] | None = None,
    operator_artifact_path: str | None = None,
    present_receipts: set[str] | list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    receipt_set = {str(item) for item in present_receipts}
    payload = (
        artifact_reference_payload
        if artifact_reference_payload is not None
        else local_artifact_reference.load_existing_payload()
    )
    attachment_receipts = (
        "invoice_attachment_confirmed_receipt" in receipt_set
        or "operator_provided_invoice_artifact_linked_candidate_receipt" in receipt_set
        or PDF_EXPORT_COMPLETION_RECEIPT in receipt_set
    )
    approved = local_artifact_reference.find_approved_readable_artifact(
        payload,
        world_ref="finance",
        workflow_ref=WORKFLOW_REF,
        client_ref=CLIENT_REF,
        artifact_kind="invoice_artifact",
        intended_use="client_invoice_email_attachment",
    )
    if approved:
        return {
            "status": "OPERATOR_PROVIDED_ARTIFACT_CANDIDATE",
            "artifact_ref": approved.get("artifact_ref"),
            "path_ref": approved.get("pc_path") or approved.get("approved_path_ref"),
            "hash": approved.get("sha256") or approved.get("artifact_hash"),
            "attachment_ready": bool(attachment_receipts),
            "candidate_only": True,
            "receipt_required_for_attachment_ready": "invoice_attachment_confirmed_receipt",
            "metadata_only": True,
        }
    if operator_artifact_path:
        metadata = validate_operator_invoice_artifact_metadata(Path(operator_artifact_path))
        return {
            "status": "OPERATOR_PROVIDED_ARTIFACT_CANDIDATE"
            if metadata["status"] == "METADATA_VALID"
            else metadata["status"],
            "artifact_ref": f"operator_invoice_artifact_candidate:{_short_hash(operator_artifact_path, metadata.get('sha256'))}",
            "path_ref": operator_artifact_path,
            "hash": metadata.get("sha256"),
            "attachment_ready": bool(attachment_receipts),
            "candidate_only": True,
            "receipt_required_for_attachment_ready": "invoice_attachment_confirmed_receipt",
            "metadata": metadata,
            "metadata_only": True,
        }
    return {
        "status": "ARTIFACT_REQUIRED",
        "artifact_ref": None,
        "path_ref": None,
        "hash": None,
        "attachment_ready": bool(attachment_receipts),
        "candidate_only": False,
        "receipt_required_for_attachment_ready": "operator_provided_invoice_artifact_linked_candidate_receipt",
        "next_action": "Attach the PDF manually only if automatic export is unavailable.",
    }


def _action(
    action_kind: str,
    label: str,
    *,
    enabled: bool,
    intended_use: str,
    disabled_reason: str | None = None,
    extra_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
        "client_ref": CLIENT_REF,
        "workflow_ref": WORKFLOW_REF,
        "action_kind": action_kind,
        "intended_use": intended_use,
        "no_external_action": True,
        "no_workbook_body_read": True,
        "no_cell_read": True,
        "email_send_allowed": False,
        "ledger_posting_allowed": False,
        "coupa_submit_allowed": False,
        "physical_deletion_allowed": False,
    }
    if extra_payload:
        payload.update(dict(extra_payload))
    return {
        "action_ref": f"live_arts_md_invoice_action:{_short_hash(action_kind, label)}",
        "action_kind": action_kind,
        "label": label,
        "enabled": enabled,
        "disabled_reason": disabled_reason,
        "operator_visible_message": label,
        "hidden_request_payload": payload,
    }


def build_live_arts_md_bundle(
    *,
    workbook_registry_payload: Mapping[str, Any] | None = None,
    source_workbook_override: Mapping[str, Any] | None = None,
    artifact_reference_payload: Mapping[str, Any] | None = None,
    operator_artifact_path: str | None = None,
    manual_send_proof: Mapping[str, Any] | None = None,
    selected_invoice_candidate: Mapping[str, Any] | None = None,
    present_receipts: tuple[str, ...] | list[str] | set[str] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    receipts = {str(receipt) for receipt in present_receipts}
    recipe = workflow.recipes_by_client_ref()[CLIENT_REF]
    handoff = live_arts_md_workbook_handoff.build_candidate_register(generated_at=generated_at)
    source = (
        dict(source_workbook_override)
        if source_workbook_override is not None
        else inspect_source_workbook_state(workbook_registry_payload=workbook_registry_payload)
    )
    if (
        source.get("status") == "SOURCE_WORKBOOK_REQUIRED"
        and workbook_registry_payload is None
        and source_workbook_override is None
    ):
        source.update(
            {
                "status": "CONFIRMED",
                "workbook_ref": handoff["source_workbook"]["source_workbook_ref"],
                "workbook_display_name": EXPECTED_WORKBOOK_NAME,
                "workbook_path_ref": handoff["source_workbook"]["source_workbook_mac_path"],
                "source_workbook_mac_path": handoff["source_workbook"]["source_workbook_mac_path"],
                "approved_for_metadata_read": True,
                "approved_for_cell_read": False,
                "no_workbook_body_read": True,
                "no_cell_read": True,
                "confirmation_basis": "operator_provided_workbook_handoff",
                "next_action": "Choose which Live Arts MD invoice to prepare.",
            }
        )
    source.setdefault("client_ref", CLIENT_REF)
    source.setdefault("workflow_ref", WORKFLOW_REF)
    source.setdefault("expected_display_name", EXPECTED_WORKBOOK_NAME)
    source.setdefault("approved_for_metadata_read", False)
    source.setdefault("approved_for_cell_read", False)
    source.setdefault("no_workbook_body_read", True)
    source.setdefault("no_cell_read", True)
    source.setdefault(
        "next_action",
        "Select the Live Arts MD invoice page/period."
        if source.get("status") == "CONFIRMED"
        else "Choose the Live Arts MD source workbook.",
    )
    source_confirmed = source["status"] == "CONFIRMED" or "source_workbook_reference_confirmed_receipt" in receipts
    selected_invoice_summary = (
        dict(selected_invoice_candidate) if isinstance(selected_invoice_candidate, Mapping) else None
    )
    if selected_invoice_summary is not None:
        selected_invoice_summary.setdefault("selection_status", "SELECTED")
        selected_invoice_summary.setdefault("selection_source", "live_arts_candidate_register")
    invoice_selected = (
        bool(selected_invoice_summary)
        or "invoice_record_selection_operator_confirmed_receipt" in receipts
        or "live_arts_md_invoice_candidate_selected_receipt" in receipts
    )
    invoice_candidate_selected = "live_arts_md_invoice_candidate_selected_receipt" in receipts
    artifact = _artifact_state(
        artifact_reference_payload=artifact_reference_payload,
        operator_artifact_path=operator_artifact_path,
        present_receipts=receipts,
    )
    attachment_receipt = "invoice_attachment_confirmed_receipt"
    pdf_export_completion_receipt = PDF_EXPORT_COMPLETION_RECEIPT
    attachment_ready = (
        attachment_receipt in receipts
        or pdf_export_completion_receipt in receipts
    )
    pdf_export_package, _ = _selected_invoice_pdf_export_package(
        selected_candidate=selected_invoice_summary,
        source_workbook=source,
        present_receipts=receipts,
    )
    selected_invoice_pdf_prepared = pdf_export_package["status"] == PDF_EXPORT_COMPLETED_CANDIDATE
    artifact_candidate = artifact["status"] == "OPERATOR_PROVIDED_ARTIFACT_CANDIDATE"
    artifact_candidate_or_exported = artifact_candidate or (pdf_export_completion_receipt in receipts)
    recipient_confirmed = "recipient_confirmation_receipt" in receipts
    comms_fixture = client_comms_thread_rail.build_clara_first_contact_draft(
        client_ref=CLIENT_REF,
        workflow_ref=WORKFLOW_REF,
        recipient_ref="live_arts_md_billing_contact_candidate",
        recipient_name="[Live Arts MD contact]",
        subject="Live Arts MD invoice",
        work_kind="invoice package",
        prior_clara_thread_exists="clara_started_thread_receipt" in receipts,
    )
    comms_draft = dict(comms_fixture["draft_candidate"])
    comms_policy = dict(comms_fixture["first_contact_policy"])
    comms_thread = dict(comms_fixture["thread_registry_record"])
    recipient_package = clara_drafts.live_arts_md_recipient_package(confirmed=recipient_confirmed)
    invoice_period_label = "operator-selected period" if invoice_selected else None
    manual_send_proof_state, manual_send_status = _manual_send_proof_status(
        manual_send_proof=manual_send_proof,
        present_receipts=receipts,
    )
    email_send_status = manual_send_status
    clara_package = clara_drafts.build_clara_invoice_email_draft_package(
        client_ref=CLIENT_REF,
        workflow_ref=WORKFLOW_REF,
        client_display_name=CLIENT_DISPLAY_NAME,
        recipient_package=recipient_package,
        attachment_ready=attachment_ready,
        attachment_refs=(str(artifact.get("artifact_ref")),) if attachment_ready and artifact.get("artifact_ref") else (),
        invoice_period_label=invoice_period_label,
        invoice_dates_covered=(),
        supplier_portal_required=False,
        supplier_portal_provider=None,
        portal_submission_status=None,
        first_contact_intro_required=bool(comms_policy["intro_required"]),
        first_contact_intro_policy_ref="generated/read_models/client_comms_thread_rail.json#live_arts_md_first_contact_policy",
        proof_refs=tuple(item for item in (artifact.get("artifact_ref"),) if item),
        present_receipts=receipts,
    )
    comms_draft.update(
        {
            "draft_ref": clara_package["draft_ref"],
            "subject": clara_package["subject"],
            "body": clara_package["body"],
            "selected_voice": clara_package["selected_voice"],
            "external_identity": clara_package["external_identity"],
            "draft_status": clara_package["draft_status"],
        }
    )
    clara_ready = True
    guardian_approval_request_ready = "guardian_approval_request_receipt" in receipts
    email_sent = "email_send_receipt" in receipts
    thread_watch_status = "THREAD_WATCH_READY" if email_sent else "BLOCKED_UNTIL_SENT_RECEIPT"
    payment_watch_status = (
        PAYMENT_WATCH_STATUS_READY_TO_CONFIGURE
        if manual_send_status == MANUAL_SEND_PROOF_STATUS_CONFIRMED
        else PAYMENT_WATCH_STATUS_READINESS_ONLY
    )
    approval_ready = all(
        (
            source_confirmed,
            invoice_selected,
            artifact_candidate_or_exported,
            attachment_ready,
            recipient_confirmed,
            clara_ready,
            guardian_approval_request_ready,
        )
    )
    blockers = []
    if not source_confirmed:
        blockers.append("Choose the Live Arts MD source workbook.")
    if source_confirmed and not invoice_selected:
        blockers.append("Choose which Live Arts MD invoice to prepare.")
    if source_confirmed and invoice_selected and not artifact_candidate_or_exported:
        if pdf_export_package["status"] == PDF_EXPORT_BLOCKED_MISSING_PRINT_SCOPE:
            blockers.append(str(pdf_export_package.get("operator_review_prompt") or "Confirm the selected sheet/print area for the invoice.")
            )
        elif pdf_export_package["status"] == PDF_EXPORT_BLOCKED_MISSING_MAC_CAPABILITY:
            blockers.append("Prepare the selected invoice PDF requires a supported Mac workbook path.")
        elif pdf_export_package["status"] == PDF_EXPORT_REQUIRES_OPERATOR_REVIEW:
            blockers.append(
                str(pdf_export_package.get("operator_review_prompt") or "Confirm the selected invoice scope for PDF export.")
            )
        else:
            blockers.append("Prepare invoice PDF.")
    if artifact_candidate_or_exported and not attachment_ready:
        blockers.append("Confirm the invoice artifact as the email attachment.")
    if not recipient_confirmed:
        blockers.append("Confirm the Live Arts MD recipient/contact.")
    if not guardian_approval_request_ready:
        blockers.append("Guardian approval request is required before send approval.")
    if not approval_ready:
        blockers.append("Approval/send remains disabled until receipts exist.")

    source_action = _action(
        "replace_source_workbook_reference",
        "Choose Live Arts MD source workbook",
        enabled=not source_confirmed,
        intended_use="replace_source_workbook_reference",
        disabled_reason=None if not source_confirmed else "Source workbook is already confirmed.",
        extra_payload={"expected_workbook_display_name": EXPECTED_WORKBOOK_NAME},
    )
    selection_action = _action(
        "select_invoice_candidate",
        "Choose invoice candidate",
        enabled=source_confirmed,
        intended_use="choose_live_arts_md_invoice_candidate",
        disabled_reason=None if source_confirmed else "Choose the source workbook first.",
        extra_payload={"operator_provided": True} if source_confirmed else None,
    )
    urgent_invoice_actions = tuple(handoff["urgent_actions"])
    prepare_pdf_action = _action(
        "prepare_selected_invoice_pdf_artifact",
        "Prepare invoice PDF",
        enabled=invoice_selected,
        intended_use="prepare_selected_invoice_pdf_artifact",
        disabled_reason=(
            "Select the invoice page/period first."
            if not invoice_selected
            else None
            if pdf_export_package["status"] in {
                PDF_EXPORT_PACKAGE_READY_FOR_MAC,
                PDF_EXPORT_COMPLETED_CANDIDATE,
                PDF_EXPORT_REQUIRES_OPERATOR_REVIEW,
            }
            else (
                pdf_export_package["operator_review_prompt"]
                if pdf_export_package["status"] == PDF_EXPORT_BLOCKED_MISSING_PRINT_SCOPE
                else "Prepare the selected invoice PDF requires source/workbook scope inputs."
            )
        ),
        extra_payload={
            "execution_venue": PDF_EXPORT_EXECUTION_VENUE,
            "required_capability": PDF_EXPORT_REQUIRED_CAPABILITY,
            "source_workbook_path": pdf_export_package["source_workbook_path"],
            "selected_sheet_label": pdf_export_package["selected_sheet_label"],
            "selected_print_areas": pdf_export_package["selected_print_areas"],
            "invoice_id": pdf_export_package["invoice_id"],
            "output_artifact_kind": PDF_EXPORT_OUTPUT_ARTIFACT_KIND,
            "output_path_policy": pdf_export_package["output_path_policy"],
            "request_copy": pdf_export_package["request_copy"],
            "no_physical_printing": True,
            "no_email_send": True,
            "no_gmail": True,
            "no_ledger_post": True,
            "no_coupa": True,
            "no_source_workbook_mutation": True,
            "workbook_cell_read_required": False,
            "operator_review_required_after_export": True,
            "required_receipts": pdf_export_package["required_receipts"],
            "required_receipt_ref": pdf_export_completion_receipt,
        },
    )
    artifact_action = _action(
        "attach_generated_invoice_artifact",
        "Attach PDF manually",
        enabled=invoice_selected,
        intended_use="manual_operator_link_generated_invoice_artifact",
        disabled_reason=None if invoice_selected else "Select the invoice page/period first.",
        extra_payload={"allowed_extensions": ALLOWED_ARTIFACT_EXTENSIONS},
    )
    recipient_action = _action(
        "review_and_confirm_recipients",
        "Confirm recipient",
        enabled=True,
        intended_use="review_or_provide_recipient",
    )
    send_action = _action(
        "prepare_manual_send_package",
        "Prepare manual send package",
        enabled=approval_ready,
        intended_use="prepare_manual_send_package",
        disabled_reason=None if approval_ready else "Attachment, recipient, and approval receipts are required first.",
    )
    primary_blocker_action = (
        source_action
        if not source_confirmed
        else selection_action
        if not invoice_selected
        else prepare_pdf_action
        if invoice_selected and not artifact_candidate_or_exported
        else recipient_action
    )

    timeline = (
        {
            "step_ref": "live_arts_md_step:source_workbook",
            "title": "Source workbook",
            "status": "COMPLETE" if source_confirmed else "NEEDS_ACTION",
            "operator_summary": source["next_action"],
            "primary_action": source_action,
            "required_receipts": ("source_workbook_reference_confirmed_receipt",),
        },
        {
            "step_ref": "live_arts_md_step:invoice_page_period",
            "title": "Invoice candidate",
            "status": "COMPLETE" if invoice_selected else "NEEDS_ACTION" if source_confirmed else "BLOCKED",
            "operator_summary": "Choose which Live Arts MD invoice to prepare from operator-provided handoff facts.",
            "primary_action": selection_action,
            "secondary_actions": urgent_invoice_actions,
            "required_receipts": ("live_arts_md_invoice_candidate_selected_receipt",),
        },
        {
            "step_ref": "live_arts_md_step:invoice_artifact",
            "title": "Invoice artifact",
            "status": (
                "READY" if artifact_candidate_or_exported and attachment_ready else
                "READY" if selected_invoice_pdf_prepared else
                "CANDIDATE" if artifact_candidate else
                "NEEDS_ACTION" if invoice_selected else "BLOCKED"
            ),
            "operator_summary": "Prepare a scoped PDF for the selected Live Arts MD invoice and attach it as the email artifact.",
            "selected_invoice_summary": selected_invoice_summary,
            "primary_action": prepare_pdf_action,
            "secondary_actions": (artifact_action,),
            "required_receipts": (
                PDF_EXPORT_COMPLETION_RECEIPT,
                "operator_provided_invoice_artifact_linked_candidate_receipt",
                "invoice_attachment_confirmed_receipt",
            ),
        },
        {
            "step_ref": "live_arts_md_step:clara_draft",
            "title": "Clara draft",
            "status": "DRAFT_ONLY",
            "operator_summary": "Clara first-contact draft is ready for review only. Nothing was sent.",
            "primary_action": None,
            "required_receipts": ("clara_email_draft_receipt",),
        },
        {
            "step_ref": "live_arts_md_step:client_comms_thread",
            "title": "Client comms thread",
            "status": "BLOCKED" if not email_sent else "THREAD_WATCH_READY",
            "operator_summary": "Thread watch is not active until a future Clara send receipt starts the thread.",
            "primary_action": None,
            "required_receipts": ("email_send_receipt", "thread_ref_receipt"),
        },
        {
            "step_ref": "live_arts_md_step:recipient_send",
            "title": "Recipient and send readiness",
            "status": "READY" if approval_ready else "BLOCKED",
            "operator_summary": "Manual send package can be prepared only after attachment, recipient, and approval receipts.",
            "primary_action": send_action,
            "required_receipts": (
                "recipient_confirmation_receipt",
                "operator_approval_receipt",
                "email_send_receipt",
                "manual_send_receipt",
            ),
        },
        {
            "step_ref": "live_arts_md_step:payment_watch",
            "title": "Payment watch",
            "status": "READINESS_ONLY",
            "operator_summary": "Payment watch can begin once send proof is confirmed.",
            "primary_action": None,
            "required_receipts": ("manual_send_receipt",),
        },
    )

    bundle = {
        "schema_version": SCHEMA_VERSION,
        "bundle_id": "invoice_review_bundle:live_arts_md:v0",
        "client_ref": CLIENT_REF,
        "client_display_name": CLIENT_DISPLAY_NAME,
        "workflow_ref": WORKFLOW_REF,
        "recipe_ref": recipe["workflow_ref"],
        "status": "SIMPLE_EMAIL_INVOICE_REVIEW",
        "selected_rails": tuple(item["rail_ref"] for item in recipe["selected_rails"]),
        "rails_not_selected_by_default": ("supplier_portal_rail", "purchase_order_rail"),
        "supplier_portal_invoice_submission": {
            "required": False,
            "supplier_portal_required": False,
            "supplier_portal_provider": None,
            "portal_submission_proof_required": False,
            "purchase_order_required": False,
            "status": "NOT_REQUIRED_BY_RECIPE",
        },
        "source_workbook": source,
        "operator_workbook_handoff": {
            "receipt": handoff["operator_handoff_receipt"],
            "operator_provided": True,
            "workbook_body_read": False,
            "cell_read": False,
            "confidence": "operator_handoff",
        },
        "invoice_candidate_register_ref": "generated/read_models/live_arts_md_invoice_candidate_register.json",
        "invoice_candidate_register": {
            "candidate_count": handoff["candidate_count"],
            "primary_next_action": handoff["primary_next_action"],
            "invoice_candidates": handoff["invoice_candidates"],
            "urgent_actions": urgent_invoice_actions,
        },
        "invoice_selection": {
            "status": "CANDIDATE_SELECTED"
            if invoice_candidate_selected
            else "NEEDS_CANDIDATE_SELECTION"
            if source_confirmed
            else "BLOCKED_NEEDS_SOURCE_WORKBOOK",
            "selected_invoice_summary": selected_invoice_summary,
            "no_workbook_body_read": True,
            "no_cell_read": True,
            "primary_action": selection_action,
            "urgent_actions": urgent_invoice_actions,
        },
        "invoice_artifact": {
            **artifact,
            "pdf_export_package": pdf_export_package,
        },
        "client_comms_thread": {
            "comms_thread_status": "DRAFT_READY" if clara_ready else "NOT_STARTED",
            "thread_ref": comms_draft["thread_ref"],
            "thread_registry_record": comms_thread,
            "external_identity": client_comms_thread_rail.CLARA_EXTERNAL_IDENTITY,
            "internal_identity": client_comms_thread_rail.CASSANDRA_INTERNAL_IDENTITY,
            "selected_voice": "CLARA",
            "channel": "email",
            "audience": "external_client",
            "first_contact_intro_required": comms_policy["intro_required"],
            "first_contact_intro_policy_ref": "generated/read_models/client_comms_thread_rail.json#first_contact_intro_policy",
            "first_contact_intro_policy": comms_policy,
            "clara_draft_status": clara_package["draft_status"],
            "draft_only": True,
            "sent": False,
            "guardian_output_validation_status": comms_draft["guardian_output_validation_status"],
            "guardian_approval_required": True,
            "guardian_approval_request_status": "READY" if guardian_approval_request_ready else "NOT_CREATED",
            "send_execution_receipt_required": True,
            "send_execution_status": "SENT_RECEIPT_CONFIRMED" if email_sent else "NOT_SENT",
            "thread_watch_status": thread_watch_status,
            "thread_watch_future_gated": not email_sent,
            "manual_send_proof_status": manual_send_status,
            "manual_send_proof": manual_send_proof_state,
            "live_gmail_polling_active": False,
            "gmail_draft_created": False,
            "required_receipts_before_send": comms_draft["required_receipts_before_send"],
        },
        "clara_email_draft": {
            "draft_ref": comms_draft["draft_ref"],
            "selected_voice": comms_draft["selected_voice"],
            "external_identity": comms_draft["external_identity"],
            "internal_identity": clara_package["internal_identity"],
            "draft_status": clara_package["draft_status"],
            "draft_only": True,
            "sent": False,
            "send_allowed": False,
            "guardian_approval_required": True,
            "subject": comms_draft["subject"],
            "body": comms_draft["body"],
            "attachment_claim": "attachment confirmed" if attachment_ready else "attachment not ready yet",
            "attachment_ready": clara_package["attachment_ready"],
            "missing_prerequisites": clara_package["missing_prerequisites"],
            "recipient_confirmation_status": clara_package["recipient_confirmation_status"],
            "send_readiness": clara_package["send_readiness"],
            "thread_ref": comms_draft["thread_ref"],
        },
        "clara_invoice_email_draft_package": clara_package,
        "client_alias_readiness": clara_drafts.CLIENT_ALIAS_READINESS["arts_alive_md"],
        "recipient_state": {
            "status": "CONFIRMED" if recipient_confirmed else "RECIPIENT_INFO_REQUIRED",
            "recipient_email_invented": False,
            "to_candidates": clara_package["to_recipients"],
            "cc_candidates": clara_package["cc_recipients"],
            "recipient_candidates": (*clara_package["to_recipients"], *clara_package["cc_recipients"]),
            "confirmation_receipt_required": "recipient_confirmation_receipt",
            "primary_action": recipient_action,
        },
        "send_readiness": {
            "email_send_rail_exists": False,
            "manual_send_package_status": "MANUAL_SEND_PACKAGE_READY" if approval_ready else "BLOCKED_PREREQUISITES",
            "email_send_status": email_send_status,
            "manual_send_proof_status": manual_send_status,
            "manual_send_proof": manual_send_proof_state,
            "email_send_approval_required": True,
            "guardian_approval_required": True,
            "guardian_approval_request_ready": guardian_approval_request_ready,
            "operator_approval_receipt_required": True,
            "email_send_execution_receipt_required": True,
            "sent_receipt_confirmed": email_sent,
            "thread_watch_status_after_send": "THREAD_WATCH_READY",
            "primary_action": send_action,
        },
        "manual_send_proof": manual_send_proof_state,
        "payment_watch": {
            "payment_watch_status": payment_watch_status,
            "client_ref": CLIENT_REF,
            "invoice_ref": artifact.get("artifact_ref"),
            "expected_amount": None,
            "expected_window": None,
            "expected_ar_layer_required": True,
            "actual_bank_transactions_separate": True,
            "active_only_after_send_or_manual_send_receipt": True,
            "bank_ledger_read_performed": False,
            "bank_ledger_match_required": True,
            "manual_send_evidence_ref": manual_send_proof_state["proof_refs"],
            "ledger_posting_allowed": False,
        },
        "ledger_planning": handoff["ledger_planning"],
        "contact_ambiguity": handoff["contact_ambiguity"],
        "approval_footer": {
            "approval_ready": approval_ready,
            "approval_disabled_reasons": tuple(blockers),
        },
        "blockers": tuple(blockers),
        "next_safe_move": "Choose which Live Arts MD invoice to prepare."
        if source_confirmed and not invoice_selected
        else blockers[0]
        if blockers
        else "Prepare manual send package after approval receipts.",
        "actionable_blockers": (
            (
                {
                    "blocker_ref": f"live_arts_md_blocker:{_short_hash(blockers[0])}",
                    "operator_summary": blockers[0],
                    "primary_action": primary_blocker_action,
                },
            )
            if blockers
            else ()
        ),
        "proof_timeline": timeline,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "generated_at": generated_at,
        "machine_proof": {
            "live_arts_md_does_not_require_coupa": True,
            "live_arts_md_does_not_require_po": True,
            "uses_reusable_simple_invoice_rails": True,
            "operator_handoff_not_workbook_parsed": True,
            "candidate_register_present": True,
            "workbook_existence_does_not_mark_sent_paid_or_ledger_posted": True,
            "clara_draft_only": True,
            "client_comms_thread_rail_consumed": True,
            "clara_invoice_draft_package_consumed": True,
            "clara_client_draft_body_status_free": not clara_package[
                "client_facing_body_has_backend_status_language"
            ],
            "arts_alive_alias_mapped_to_live_arts_md": clara_drafts.CLIENT_ALIAS_READINESS["arts_alive_md"][
                "canonical_client_ref"
            ]
            == CLIENT_REF,
            "clara_first_contact_intro_required": comms_policy["intro_required"],
            "thread_watch_blocked_until_send_receipt": thread_watch_status == "BLOCKED_UNTIL_SENT_RECEIPT",
            "send_execution_receipt_required": True,
            "no_recipient_email_invented": True,
            "artifact_candidate_not_attachment_ready": artifact.get("attachment_ready") is False,
            "payment_watch_readiness_only_no_bank_read": True,
            "approval_send_disabled_without_receipts": approval_ready is False,
            "no_action_authority": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "manual_send_proof_evaluated": bool(manual_send_proof_state),
            "manual_send_proof_status": manual_send_status,
            "content_hash": "",
        },
    }
    bundle["machine_proof"]["content_hash"] = _content_hash(bundle)
    return bundle


def build_payload(
    *,
    generated_at: str | None = None,
    selected_invoice_candidate: Mapping[str, Any] | None = None,
    workbook_registry_payload: Mapping[str, Any] | None = None,
    source_workbook_override: Mapping[str, Any] | None = None,
    artifact_reference_payload: Mapping[str, Any] | None = None,
    operator_artifact_path: str | None = None,
    manual_send_proof: Mapping[str, Any] | None = None,
    present_receipts: tuple[str, ...] | list[str] | set[str] = (),
) -> dict[str, Any]:
    bundle = build_live_arts_md_bundle(
        generated_at=generated_at,
        selected_invoice_candidate=selected_invoice_candidate,
        workbook_registry_payload=workbook_registry_payload,
        source_workbook_override=source_workbook_override,
        artifact_reference_payload=artifact_reference_payload,
        operator_artifact_path=operator_artifact_path,
        manual_send_proof=manual_send_proof,
        present_receipts=present_receipts,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or DEFAULT_GENERATED_AT,
        "live_arts_md_bundle": bundle,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "live_arts_md_bundle_present": True,
            "bridge_safe": True,
            "no_action_authority": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": _content_hash(bundle),
        },
    }


def format_operator(payload: Mapping[str, Any]) -> str:
    bundle = payload["live_arts_md_bundle"]
    lines = [
        "# Live Arts MD Invoice Review Bundle",
        "",
        f"- Status: `{bundle['status']}`",
        f"- Next safe move: {bundle['next_safe_move']}",
        f"- Source workbook: `{bundle['source_workbook']['status']}`",
        f"- Invoice page/period: `{bundle['invoice_selection']['status']}`",
        f"- Artifact: `{bundle['invoice_artifact']['status']}`",
        f"- Clara draft: `{bundle['clara_email_draft']['selected_voice']}` draft-only",
        f"- Recipient state: `{bundle['recipient_state']['status']}`",
        f"- Manual send package: `{bundle['send_readiness']['manual_send_package_status']}`",
        f"- Manual send proof: `{bundle['manual_send_proof']['proof_status']}`",
        f"- Payment watch: `{bundle['payment_watch']['payment_watch_status']}`",
        *(
            (f"- {bundle['manual_send_proof']['proof_capture_request']}",)
            if bundle["manual_send_proof"].get("proof_capture_request")
            else tuple()
        ),
        "",
        "No email, Coupa, browser, ledger, workbook body/cell read, generation, export, or production action occurred.",
    ]
    return "\n".join(lines) + "\n"


def write_exports(
    payload: Mapping[str, Any],
    export_root: Path = DEFAULT_EXPORT_ROOT,
    *,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
) -> tuple[Path, Path, Path | None]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator(payload), encoding="utf-8")
    bridge_path = None
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_export_root / JSON_EXPORT_NAME
        shutil.copy2(json_path, bridge_path)
    return json_path, operator_path, bridge_path


def export_bundle(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_payload(generated_at=generated_at)
    json_path, operator_path, bridge_path = write_exports(
        payload,
        export_root,
        bridge_export_root=bridge_export_root,
    )
    return {
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "bridge_path": bridge_path.as_posix() if bridge_path else None,
        "source_workbook_status": payload["live_arts_md_bundle"]["source_workbook"]["status"],
        "next_safe_move": payload["live_arts_md_bundle"]["next_safe_move"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Live Arts MD simple invoice review bundle.")
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--bridge-export-root", default=DEFAULT_BRIDGE_EXPORT_ROOT.as_posix())
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--generated-at")
    args = parser.parse_args(argv)
    result = export_bundle(
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
