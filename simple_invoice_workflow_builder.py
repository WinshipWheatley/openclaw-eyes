"""Reusable helpers for simple invoice workflow read-model readiness."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import simple_invoice_workflow_fixtures

ALLOWED_ARTIFACT_EXTENSIONS = (".pdf", ".xlsx", ".xls", ".png", ".jpg", ".jpeg")

PROOF_CAPTURE_TYPE_REFERENCE_ONLY = "REFERENCE_ONLY"
PROOF_CAPTURE_TYPE_FILE_BACKED = "FILE_BACKED"
PROOF_STRENGTH_OPERATOR_ATTESTED_REFERENCE = "OPERATOR_ATTESTED_REFERENCE"
PROOF_STRENGTH_FILE_VERIFIED = "FILE_VERIFIED"

MANUAL_SEND_PROOF_STATUS_PENDING = "MANUAL_SEND_PROOF_PENDING"
MANUAL_SEND_PROOF_STATUS_CONFIRMED = "MANUAL_SEND_PROOF_CONFIRMED"
MANUAL_SEND_PROOF_CONFIRMED_RECEIPT = "manual_send_proof_confirmed_receipt"

PDF_EXPORT_PACKAGE_READY_FOR_MAC = "PDF_EXPORT_PACKAGE_READY_FOR_MAC"
PDF_EXPORT_BLOCKED_MISSING_MAC_CAPABILITY = "PDF_EXPORT_BLOCKED_MISSING_MAC_CAPABILITY"
PDF_EXPORT_BLOCKED_MISSING_PRINT_SCOPE = "BLOCKED_MISSING_EXPORT_SCOPE"
PDF_EXPORT_BLOCKED_OUTPUT_PATH_CONTRACT = "BLOCKED_OUTPUT_PATH_CONTRACT"
PDF_EXPORT_COMPLETED_CANDIDATE = "PDF_EXPORT_COMPLETED_CANDIDATE"
PDF_EXPORT_REQUIRES_OPERATOR_REVIEW = "PDF_EXPORT_REQUIRES_OPERATOR_REVIEW"
PDF_EXPORT_REQUIRED_CAPABILITY = "MAC_EXCEL_PDF_EXPORT"
PDF_EXPORT_EXECUTION_VENUE = "MAC_LOCAL"
PDF_EXPORT_OUTPUT_ARTIFACT_KIND = "PDF"
PDF_EXPORT_PACKAGE_REQUESTED_RECEIPT = "selected_invoice_pdf_export_requested_receipt"
PDF_EXPORT_COMPLETION_RECEIPT = "selected_invoice_pdf_export_completed_candidate"
MAC_OPENCLAW_INVOICE_ARTIFACT_ROOT = "/Volumes/openclaw_e/artifacts/invoice_workbooks"
BRIDGE_OPENCLAW_INVOICE_ARTIFACT_ROOT = "/mnt/e/openclaw/artifacts/invoice_workbooks"

PAYMENT_WATCH_STATUS_READY_TO_CONFIGURE = "READY_TO_CONFIGURE"
PAYMENT_WATCH_STATUS_ACTIVE_PENDING_PAYMENT = "ACTIVE_PENDING_PAYMENT"
PAYMENT_WATCH_STATUS_READINESS_ONLY = "READINESS_ONLY_NOT_ACTIVE"
PAYMENT_WATCH_EXPECTED_STATUS_OPEN = "OPEN"
PAYMENT_WATCH_REVIEW_STATUS_WAITING_FOR_PAYMENT = "WAITING_FOR_PAYMENT"
PAYMENT_WATCH_REVIEW_STATUS_WAITING_FOR_PROOF = "WAITING_FOR_MANUAL_SEND_PROOF"
PAYMENT_WATCH_LEDGER_MATCH_NOT_MATCHED = "NOT_MATCHED"
PAYMENT_WATCH_LEDGER_MATCH_NOT_ATTEMPTED = "NOT_ATTEMPTED"
PAYMENT_WATCH_LEDGER_HANDOFF_PLANNING_ONLY = "PLANNING_ONLY_NO_MUTATION"


def _as_sequence(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
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
        or (len(value) >= 3 and value[1] == ":" and value[2] in ("/", "\\"))
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


def build_artifact_transport_policy(
    *,
    bridge_available: bool = True,
) -> dict[str, Any]:
    if not bridge_available:
        return {
            "transport_status": "REMOTE_EDGE_TRANSPORT_NOT_CONFIGURED",
            "developer_task": "expose developer task for remote edge transport later",
            "data_egress_allowed": False,
            "remote_mac_supported": False,
        }
    return {
        "preferred_transport": "LOCAL_BRIDGE",
        "fallback_transports": ["LOCAL_NETWORK_DIRECT"],
        "data_egress_allowed": False,
        "local_network_preferred": True,
        "remote_mac_supported": False,
        "artifact_should_exist_on_mac": True,
        "artifact_should_be_registered_on_pc": True,
        "artifact_should_be_mirrored_to_bridge": True,
        "telegram_artifact_preview_supported": False,
    }


def _pdf_output_mac_path(*, client_ref: str, invoice_id: str, output_filename: str) -> str:
    artifact_invoice_id = invoice_id or "selected-invoice"
    return f"{MAC_OPENCLAW_INVOICE_ARTIFACT_ROOT}/{client_ref}/{artifact_invoice_id}/{output_filename}"


def _pdf_output_bridge_path(*, client_ref: str, invoice_id: str, output_filename: str) -> str:
    artifact_invoice_id = invoice_id or "selected-invoice"
    return f"{BRIDGE_OPENCLAW_INVOICE_ARTIFACT_ROOT}/{client_ref}/{artifact_invoice_id}/{output_filename}"


def _pdf_output_path_contract_errors(package: Mapping[str, Any]) -> tuple[str, ...]:
    output_pdf_mac_path = str(package.get("output_pdf_mac_path") or "")
    output_bridge_path = str(package.get("output_bridge_path") or "")
    errors: list[str] = []
    if not output_pdf_mac_path:
        errors.append("output_pdf_mac_path")
    elif not output_pdf_mac_path.startswith(f"{MAC_OPENCLAW_INVOICE_ARTIFACT_ROOT}/"):
        errors.append("output_pdf_mac_path_allowed_root")
    if not output_bridge_path:
        errors.append("output_bridge_path")
    elif not output_bridge_path.startswith(f"{BRIDGE_OPENCLAW_INVOICE_ARTIFACT_ROOT}/"):
        errors.append("output_bridge_path_allowed_root")
    if output_pdf_mac_path and output_bridge_path:
        mac_relative = output_pdf_mac_path.removeprefix(MAC_OPENCLAW_INVOICE_ARTIFACT_ROOT)
        bridge_relative = output_bridge_path.removeprefix(BRIDGE_OPENCLAW_INVOICE_ARTIFACT_ROOT)
        if mac_relative != bridge_relative:
            errors.append("mac_bridge_output_path_mismatch")
    return tuple(errors)


def build_selected_invoice_pdf_export_package(
    *,
    fixture: Mapping[str, Any],
    selected_candidate: Mapping[str, Any] | None,
    source_workbook: Mapping[str, Any] | None,
    present_receipts: set[str],
) -> tuple[dict[str, Any], str]:
    invoice_id = str((selected_candidate or {}).get("invoice_id") or "")
    selected_sheet_label = str((selected_candidate or {}).get("sheet_label") or "")
    selected_page_label = str((selected_candidate or {}).get("selected_page_label") or "").strip() or None
    selected_print_areas = tuple(_as_sequence((selected_candidate or {}).get("operator_provided_ranges")))
    source_path = str(
        (source_workbook or {}).get("workbook_path_ref")
        or (source_workbook or {}).get("source_workbook_mac_path")
        or (source_workbook or {}).get("workbook_path")
        or ""
    ) if source_workbook is not None else ""
    output_sheet_slug = (selected_sheet_label or "unknown-sheet").replace(" ", "_").replace("/", "_")
    output_path_policy = fixture.get("pdf_export_output_path_template", "scoped/{client_ref}_export/{selected_sheet_slug}/{invoice_id}.pdf").format(
        client_ref=fixture.get("client_ref", "client"),
        invoice_id=invoice_id or "selected-invoice",
        selected_sheet_slug=output_sheet_slug,
    )
    completion_receipt = PDF_EXPORT_COMPLETION_RECEIPT
    required_receipts = (completion_receipt,)
    
    client_ref = fixture.get("client_ref", "client")
    selected_sheet_slug = selected_sheet_label.replace(" ", "_").replace("/", "_")
    output_filename_parts = [
        "Invoice",
        invoice_id,
        str(fixture.get("client_display_name", "client")).replace(" ", "_"),
    ]
    if selected_sheet_slug:
        output_filename_parts.append(selected_sheet_slug)
    output_filename = "_".join(part for part in output_filename_parts if part) + ".pdf"
    output_pdf_mac_path = _pdf_output_mac_path(
        client_ref=str(client_ref),
        invoice_id=invoice_id,
        output_filename=output_filename,
    )
    output_bridge_path = _pdf_output_bridge_path(
        client_ref=str(client_ref),
        invoice_id=invoice_id,
        output_filename=output_filename,
    )
    selected_invoice_summary = None
    if selected_candidate:
        work_or_period = (
            (selected_candidate or {}).get("work_or_period")
            or selected_sheet_label
            or (selected_candidate or {}).get("work_type")
        )
        amount = (selected_candidate or {}).get("amount")
        amount_display = (selected_candidate or {}).get("amount_display") or (
            f"${amount:,.0f}" if isinstance(amount, (int, float)) else f"${amount}" if amount not in (None, "") else ""
        )
        selected_invoice_summary = " — ".join(
            part
            for part in (
                invoice_id,
                str(work_or_period or "").strip(),
                str(amount_display or "").strip(),
            )
            if part
        )
    
    package = {
        "job_ref": f"mac_edge_job_{invoice_id}_{hashlib.sha256(str(invoice_id).encode()).hexdigest()[:8]}",
        "job_type": "SELECTED_INVOICE_PDF_EXPORT",
        "client_ref": client_ref,
        "workflow_ref": fixture.get("workflow_ref"),
        "invoice_id": invoice_id,
        "invoice_candidate_ref": str((selected_candidate or {}).get("candidate_ref") or invoice_id),
        "source_workbook_mac_path": source_path,
        "source_workbook_bridge_ref": source_path,
        "selected_sheet_label": selected_sheet_label,
        "selected_print_area": selected_print_areas[0] if selected_print_areas else None,
        "selected_page_label": selected_page_label,
        "selected_invoice_summary": selected_invoice_summary,
        "output_artifact_kind": PDF_EXPORT_OUTPUT_ARTIFACT_KIND,
        "output_filename": output_filename,
        "output_pdf_mac_path": output_pdf_mac_path,
        "output_mac_path": output_path_policy,
        "output_bridge_path": output_bridge_path,
        "output_pc_reference_path": output_bridge_path,
        "artifact_storage_policy": {},
        "execution_venue": "MAC_LOCAL",
        "required_capability": "MAC_EXCEL_PDF_EXPORT",
        "transport_policy": build_artifact_transport_policy(bridge_available=True),
        "result_intended_use": "selected_invoice_pdf_export_completed_candidate",
        "operator_review_required": True,
        "no_physical_printing": True,
        "no_email_send": True,
        "no_gmail": True,
        "no_browser": True,
        "no_ledger_post": True,
        "no_coupa": True,
        "no_source_workbook_mutation": True,
        "no_workbook_cell_read": True,

        # Legacy backward-compatibility mapping
        "source_workbook_path": source_path,
        "selected_print_areas": selected_print_areas,
        "output_path_policy": output_path_policy,
        "workbook_cell_read_required": False,
        "operator_review_required_after_export": True,
        "required_receipts": required_receipts,
        "request_receipt": PDF_EXPORT_PACKAGE_REQUESTED_RECEIPT,
        "missing_requirements": (),
        "proof_refs": tuple(),
        "request_payload_ready": bool(selected_candidate) and bool(source_path) and bool(selected_print_areas),
        "request_copy": fixture.get("pdf_package_request_template", "Prepare the selected invoice PDF from {selected_sheet_label} on Mac with scoped print area.").format(
            client_ref=client_ref,
            selected_sheet_label=selected_sheet_label or "unknown sheet",
        ),
    }
    if not selected_candidate:
        package.update(
            {
                "status": PDF_EXPORT_REQUIRES_OPERATOR_REVIEW,
                "missing_requirements": ("selected_invoice_candidate",),
                "operator_review_prompt": fixture.get("pdf_scope_review_template", "Confirm the selected invoice scope").format(
                    invoice_id="selected invoice"
                ),
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
    missing_scope = []
    if not selected_sheet_label:
        missing_scope.append("selected_sheet_label")
    if not selected_print_areas:
        missing_scope.append("selected_print_areas")
    if missing_scope:
        if not selected_print_areas and selected_sheet_label:
            operator_review_prompt = f"Confirm selected print area for invoice {invoice_id}."
        elif not selected_sheet_label:
            operator_review_prompt = f"Confirm selected sheet for invoice {invoice_id}."
        else:
            operator_review_prompt = fixture.get("pdf_scope_review_template", "Confirm the selected invoice scope").format(
                invoice_id=invoice_id
            )
        package.update(
            {
                "status": PDF_EXPORT_BLOCKED_MISSING_PRINT_SCOPE,
                "missing_requirements": tuple(missing_scope),
                "operator_review_prompt": operator_review_prompt,
                "prompt_invoice_id": invoice_id,
            }
        )
        return package, completion_receipt
    path_contract_errors = _pdf_output_path_contract_errors(package)
    if path_contract_errors:
        package.update(
            {
                "status": PDF_EXPORT_BLOCKED_OUTPUT_PATH_CONTRACT,
                "missing_requirements": path_contract_errors,
                "operator_review_prompt": "Fix the explicit Mac/bridge output paths before preparing invoice PDF.",
                "prompt_invoice_id": invoice_id,
                "request_payload_ready": False,
            }
        )
        return package, completion_receipt
    if completion_receipt in present_receipts:
        package["status"] = PDF_EXPORT_COMPLETED_CANDIDATE
    else:
        package["status"] = PDF_EXPORT_PACKAGE_READY_FOR_MAC
    return package, completion_receipt


def normalize_manual_send_proof(
    *,
    fixture: Mapping[str, Any],
    manual_send_proof: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(manual_send_proof or {})
    defaults = dict(fixture.get("known_manual_send_defaults", {}))
    payload.setdefault("execution_context", {
        "execution_venue": defaults.get("execution_venue", "MAC_LOCAL"),
        "execution_actor": defaults.get("execution_actor", "OPERATOR"),
        "assistant_actor": defaults.get("assistant_actor", "CODEX_DESKTOP_SPARK"),
        "openclaw_executed": defaults.get("openclaw_executed", False),
        "manual_execution": defaults.get("manual_execution", True),
        "send_method": defaults.get("send_method", "manual_gmail"),
        "artifact_exported_on": defaults.get("artifact_exported_on", "MAC_EXCEL"),
        "proof_required": defaults.get("proof_required", True),
    })
    execution = payload.get("execution_context")
    if not isinstance(execution, Mapping):
        execution = {}
    payload["execution_context"] = dict(execution)
    for key, value in defaults.items():
        if key not in payload:
            payload[key] = value
    proof_refs = payload.get("proof_refs")
    if not isinstance(proof_refs, tuple):
        proof_refs = tuple(_as_sequence(proof_refs))
    payload["proof_refs"] = proof_refs
    payload.setdefault("proof_required", True)
    payload.setdefault("no_openclaw_send_claim", True)
    payload.setdefault("manual_send_receipt_available", False)
    payload.setdefault(
        "proof_capture_required",
        tuple(fixture.get("proof_capture_required", ("screenshot_ref", "sent_mail_proof_ref"))),
    )
    return payload


def evaluate_manual_send_proof_status(
    *,
    fixture: Mapping[str, Any],
    manual_send_proof: Mapping[str, Any] | None,
    present_receipts: set[str],
) -> tuple[dict[str, Any], str]:
    payload = normalize_manual_send_proof(fixture=fixture, manual_send_proof=manual_send_proof)
    required_fields = (
        "sent_timestamp",
        "to",
        "cc",
        "subject",
        "attachment_filename",
        "invoice_id",
        "amount",
        "work_or_period",
    )
    missing_required_fields = [
        field for field in required_fields if not _is_present_field(payload.get(field))
    ]
    sent_proof_ref = (
        payload.get("screenshot_ref")
        or payload.get("sent_mail_proof_ref")
        or payload.get("manual_send_proof_ref")
    )
    has_screenshot_or_mail_proof = bool(sent_proof_ref)
    proof_capture_metadata = _proof_capture_metadata(sent_proof_ref)
    if proof_capture_metadata.get("is_path") and proof_capture_metadata.get("exists"):
        proof_capture_type = PROOF_CAPTURE_TYPE_FILE_BACKED
        proof_strength = PROOF_STRENGTH_FILE_VERIFIED
        file_backed_proof = True
        screenshot_file_verified = proof_capture_metadata.get("proof_path_status") == "metadata_valid"
    elif sent_proof_ref:
        proof_capture_type = PROOF_CAPTURE_TYPE_REFERENCE_ONLY
        proof_strength = PROOF_STRENGTH_OPERATOR_ATTESTED_REFERENCE
        file_backed_proof = False
        screenshot_file_verified = False
    else:
        proof_capture_type = None
        proof_strength = None
        file_backed_proof = False
        screenshot_file_verified = False
    missing_capture_fields: list[str] = []
    proof_capture_required = payload.get("proof_capture_required", ("screenshot_ref", "sent_mail_proof_ref"))
    if proof_capture_required is not False:
        if not has_screenshot_or_mail_proof:
            missing_capture_fields.append("proof screenshot/ref")
        elif proof_capture_metadata.get("is_path") and not proof_capture_metadata.get("exists"):
            missing_capture_fields.append("proof screenshot/ref")
    has_manual_send_receipt = "manual_send_receipt" in present_receipts
    has_confirmed_receipt = has_manual_send_receipt or payload.get("manual_send_receipt_available") is True
    proof_capture_complete = bool(
        (proof_capture_required is False)
        or (has_screenshot_or_mail_proof and not (proof_capture_metadata.get("is_path") and not proof_capture_metadata.get("exists")))
    )
    proof_state = {
        "execution_context": payload.get("execution_context", {}),
        "artifact_path": payload.get("artifact_path"),
        "attachment_filename": payload.get("attachment_filename"),
        "invoice_id": payload.get("invoice_id"),
        "work_or_period": payload.get("work_or_period"),
        "amount": payload.get("amount"),
        "sent_timestamp": payload.get("sent_timestamp"),
        "subject": payload.get("subject"),
        "to": tuple(_as_sequence(payload.get("to"))),
        "cc": tuple(_as_sequence(payload.get("cc"))),
        "manual_send_receipt_available": bool(payload.get("manual_send_receipt_available", False)),
        "proof_required": bool(payload.get("proof_required", True)),
        "receipt_received": bool(has_confirmed_receipt),
        "proof_refs": tuple(_as_sequence(payload.get("proof_refs"))),
        "required_fields": required_fields,
        "missing_required_fields": tuple([*missing_required_fields, *missing_capture_fields]),
        "proof_capture_provided": bool(bool(sent_proof_ref)),
        "proof_capture_fields": tuple(_as_sequence(payload.get("proof_capture_required")),
        ),
        "proof_capture_metadata": proof_capture_metadata,
        "proof_capture_type": proof_capture_type,
        "proof_strength": proof_strength,
        "file_backed_proof": file_backed_proof,
        "screenshot_file_verified": screenshot_file_verified,
        "proof_capture_request": None
        if not missing_capture_fields
        else (
            f"Add sent-email screenshot or sent-mail proof for {fixture.get('client_display_name', 'client')} invoice {payload.get('invoice_id') or 'selected'}."
        ),
        "proof_receipts": (
            (MANUAL_SEND_PROOF_CONFIRMED_RECEIPT,)
            if (has_confirmed_receipt or proof_capture_complete) and not missing_required_fields and not missing_capture_fields
            else ()
        ),
    }
    complete = (
        (has_confirmed_receipt or proof_capture_complete)
        and not missing_required_fields
        and not missing_capture_fields
        and ((payload.get("proof_required") is False) or has_screenshot_or_mail_proof or (proof_capture_required is False))
    )
    proof_state["proof_status"] = MANUAL_SEND_PROOF_STATUS_CONFIRMED if complete else MANUAL_SEND_PROOF_STATUS_PENDING
    return proof_state, proof_state["proof_status"]


def build_expected_receivable_state(
    *,
    fixture: Mapping[str, Any],
    manual_send_proof: Mapping[str, Any] | None,
    selected_invoice_summary: Mapping[str, Any] | None,
    payment_watch_status: str,
    manual_send_status: str,
) -> dict[str, Any]:
    manual_send_payload = dict(manual_send_proof or {})
    send_proof_ref = str(
        manual_send_payload.get("screenshot_ref")
        or manual_send_payload.get("sent_mail_proof_ref")
        or manual_send_payload.get("manual_send_proof_ref")
        or ""
    ).strip()
    proof_refs = tuple(item for item in _as_sequence(manual_send_payload.get("proof_refs")) if item)
    if send_proof_ref and send_proof_ref not in proof_refs:
        proof_refs = (send_proof_ref, *proof_refs)
    invoice_id = str(
        (selected_invoice_summary or {}).get("invoice_id")
        or manual_send_payload.get("invoice_id")
        or fixture.get("known_manual_send_defaults", {}).get("invoice_id")
        or ""
    )
    selected_lookup = selected_invoice_summary if isinstance(selected_invoice_summary, Mapping) else None
    if selected_lookup is None and invoice_id:
        lookup = fixture.get("candidate_lookup")
        if callable(lookup):
            selected_lookup = lookup(invoice_id)
    candidate = dict(selected_lookup or {}) if isinstance(selected_lookup, Mapping) else {}
    expected_amount = candidate.get("amount")
    if expected_amount is None:
        try:
            expected_amount = int(manual_send_payload.get("amount", fixture.get("known_manual_send_defaults", {}).get("amount", 0)))
        except (TypeError, ValueError):
            expected_amount = fixture.get("known_manual_send_defaults", {}).get("amount", 0)
    expected_work_type = candidate.get("work_type") or candidate.get("work_or_period")
    expected_work_or_period = candidate.get("sheet_label") or candidate.get("work_or_period")
    if not expected_work_or_period:
        expected_work_or_period = str(
            manual_send_payload.get("work_or_period")
            or expected_work_type
            or fixture.get("known_manual_send_defaults", {}).get("work_or_period", "")
        )
    if expected_work_type is None:
        expected_work_type = str(
            manual_send_payload.get("work_or_period")
            or fixture.get("known_manual_send_defaults", {}).get("work_or_period", "")
        )
    expected_receipt_status = candidate.get("receipt_status") or "UNPAID"
    expected_review_status = (
        PAYMENT_WATCH_REVIEW_STATUS_WAITING_FOR_PAYMENT
        if payment_watch_status != PAYMENT_WATCH_STATUS_READINESS_ONLY
        else PAYMENT_WATCH_REVIEW_STATUS_WAITING_FOR_PROOF
    )
    ledger_match_status = (
        PAYMENT_WATCH_LEDGER_MATCH_NOT_MATCHED
        if payment_watch_status != PAYMENT_WATCH_STATUS_READINESS_ONLY
        else PAYMENT_WATCH_LEDGER_MATCH_NOT_ATTEMPTED
    )
    matching_requirements = (
        "manual_send_proof",
        "bank_payment_confirmation_receipt",
    )
    allowed_next_steps = (
        f"Capture bank/payment proof for invoice {invoice_id}.",
        "Confirm ledger match status before any posting attempt.",
    )
    proof_strength = manual_send_payload.get("proof_strength")
    if proof_strength is None:
        if manual_send_payload.get("proof_capture_type") == PROOF_CAPTURE_TYPE_FILE_BACKED:
            proof_strength = PROOF_STRENGTH_FILE_VERIFIED
        elif manual_send_payload.get("proof_capture_type") == PROOF_CAPTURE_TYPE_REFERENCE_ONLY:
            proof_strength = PROOF_STRENGTH_OPERATOR_ATTESTED_REFERENCE
    return {
        "expected_payer_client": fixture.get("client_display_name", "Client"),
        "invoice_id": invoice_id,
        "expected_amount": expected_amount,
        "work_type": expected_work_type,
        "work_or_period": expected_work_or_period,
        "receipt_status": expected_receipt_status,
        "payment_watch_status": payment_watch_status,
        "ledger_match_status": ledger_match_status,
        "ledger_handoff_status": PAYMENT_WATCH_LEDGER_HANDOFF_PLANNING_ONLY,
        "review_status": expected_review_status,
        "matching_requirements": matching_requirements,
        "allowed_next_steps": allowed_next_steps,
        "send_proof_ref": proof_refs,
        "send_proof_strength": proof_strength,
        "proof_capture_type": manual_send_payload.get("proof_capture_type"),
        "expected_receivable_status": PAYMENT_WATCH_EXPECTED_STATUS_OPEN if manual_send_status == MANUAL_SEND_PROOF_STATUS_CONFIRMED else "BLOCKED",
        "bank_ledger_match_required": True,
        "receipt_required": True,
    }


def build_client_invoice_rails(client_ref: str, workflow_ref: str | None = None) -> dict[str, Any]:
    """Return the reusable simple-rail shape for client invoice workflows."""
    import client_invoice_workflow_framework as framework

    recipe = framework.recipes_by_client_ref()[client_ref]
    selected_rails = tuple(rail["rail_ref"] for rail in recipe["selected_rails"])
    return {
        "client_ref": client_ref,
        "workflow_ref": workflow_ref or recipe["workflow_ref"],
        "selected_rails": selected_rails,
        "rails_required": tuple(
            item["rail_ref"]
            for item in recipe["selected_rails"]
            if item["required_for_recipe"]
        ),
        "supplier_portal_required": bool(
            framework.recipe_selects_rail(recipe, framework.SUPPLIER_PORTAL_RAIL)
        ),
        "purchase_order_required": bool(framework.recipe_selects_rail(recipe, framework.PURCHASE_ORDER_RAIL)),
        "client_specific_portal_requirements": dict(recipe["client_specific_portal_requirements"]),
    }

def build_generic_candidate_selection_rail(
    *,
    client_ref: str,
    selection_mode: str,
    candidate_selection_status: str,
    selected_invoice_ids: tuple[str, ...],
    selected_invoice_candidates: tuple[Mapping[str, Any], ...],
    selected_invoice_summary: str | None,
    allow_multiple: bool,
    max_candidates: int | None,
) -> dict[str, Any]:
    return {
        "rail_ref": f"{client_ref}_generic_candidate_selection_rail",
        "selection_mode": selection_mode,
        "candidate_selection_status": candidate_selection_status,
        "candidate_selection_set": (),
        "selected_invoice_candidates": selected_invoice_candidates,
        "selected_invoice_ids": selected_invoice_ids,
        "selected_invoice_summary": selected_invoice_summary,
        "allow_multiple": allow_multiple,
        "max_candidates": max_candidates,
        "primary_action": "commit_selected_invoice_candidates",
        "secondary_actions": ("add_another_invoice", "clear_selection", "no_other_invoices_continue"),
        "required_receipt": "invoice_candidate_selection_confirmed_receipt",
        "presentation_hints": {
            "collapse_candidates_after_selection": True,
            "show_selected_summary": True,
            "ask_for_more_invoices_after_first_selection": True,
            "selected_summary_primary": True,
            "candidate_cards_hidden_when_confirmed": True,
        },
    }
