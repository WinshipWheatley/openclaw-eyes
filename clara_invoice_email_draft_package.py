"""Reusable Clara invoice email draft package.

This module builds client-facing draft packages only. It does not create Gmail
drafts, send email, poll inboxes, read workbooks, generate invoice artifacts,
open browsers, access supplier portals, post ledgers, or mutate production
business state.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


CLARA_SELECTED_VOICE = "CLARA"
CLARA_EXTERNAL_IDENTITY = "CLARA_REID"
CASSANDRA_INTERNAL_IDENTITY = "CASSANDRA"

FINAL_DRAFT_READY_FOR_APPROVAL = "FINAL_DRAFT_READY_FOR_APPROVAL"
DRAFT_PREVIEW_NOT_SEND_READY = "DRAFT_PREVIEW_NOT_SEND_READY"
DRAFT_BLOCKED_PENDING_PREREQUISITES = "DRAFT_BLOCKED_PENDING_PREREQUISITES"
DRAFT_PLACEHOLDER_FOR_OPERATOR_REVIEW = "DRAFT_PLACEHOLDER_FOR_OPERATOR_REVIEW"

DRAFT_STATUSES = (
    FINAL_DRAFT_READY_FOR_APPROVAL,
    DRAFT_PREVIEW_NOT_SEND_READY,
    DRAFT_BLOCKED_PENDING_PREREQUISITES,
    DRAFT_PLACEHOLDER_FOR_OPERATOR_REVIEW,
)

CLIENT_ALIAS_READINESS = {
    "arts_alive_md": {
        "canonical_client_ref": "live_arts_md",
        "aliases": ("Arts Alive MD!", "Arts Alive MD", "arts_alive_md"),
        "status": "ALIAS_CORRECTION_CANDIDATE",
        "operator_copy": "Treat Arts Alive MD as a possible operator alias for Live Arts MD until confirmed.",
    }
}

CLIENT_FACING_FORBIDDEN_TERMS = (
    "draft path prepared",
    "guardian validated outputs",
    "guardian output validation",
    "artifact candidate",
    "proof missing",
    "approval blocked",
    "request-response",
    "gate 2",
    "gate 3",
    "receipt rail",
    "bundle state",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _recipient(
    display_name: str,
    role: str,
    lane: str,
    *,
    email: str | None = None,
    confirmed: bool = False,
    proof_ref: str | None = None,
) -> dict[str, Any]:
    return {
        "display_name": display_name,
        "role": role,
        "lane": lane,
        "email": email,
        "email_status": "KNOWN_OPERATOR_PROVIDED" if email else "MISSING",
        "confirmation_status": "CONFIRMED_BY_RECEIPT" if confirmed else "CANDIDATE_UNCONFIRMED",
        "proof_ref": proof_ref,
        "email_invented": False,
    }


def capital_hilton_recipient_package(*, confirmed: bool = False) -> dict[str, Any]:
    recipients = (
        _recipient("Annette", "finance_primary", "to", confirmed=confirmed),
        _recipient("Chyna", "finance_secondary", "cc", confirmed=confirmed),
        _recipient("Will", "relationship_contact", "cc", confirmed=confirmed),
    )
    return _recipient_package(recipients)


def live_arts_md_recipient_package(*, confirmed: bool = False) -> dict[str, Any]:
    recipients = (
        _recipient("Dance", "primary_invoice_contact", "to", confirmed=confirmed),
        _recipient("Draper", "cc_candidate", "cc", confirmed=confirmed),
        _recipient("Earnie", "cc_candidate", "cc", confirmed=confirmed),
        _recipient(
            "Winship",
            "operator_copy",
            "cc",
            email="winshiplive@gmail.com",
            confirmed=confirmed,
            proof_ref="operator_known_email:winshiplive@gmail.com",
        ),
    )
    return _recipient_package(recipients)


def _recipient_package(recipients: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    to_recipients = tuple(item for item in recipients if item["lane"] == "to")
    cc_recipients = tuple(item for item in recipients if item["lane"] == "cc")
    missing = tuple(item["display_name"] for item in recipients if not item["email"])
    confirmed = all(item["confirmation_status"] == "CONFIRMED_BY_RECEIPT" for item in recipients)
    return {
        "to_recipients": to_recipients,
        "cc_recipients": cc_recipients,
        "recipient_confirmation_status": "CONFIRMED_BY_RECEIPT" if confirmed else "CANDIDATE_UNCONFIRMED",
        "recipient_info_missing": missing,
        "recipient_email_invented": False,
        "confirmation_receipt_required": "recipient_confirmation_receipt",
    }


def _safe_subject(client_display_name: str, invoice_period_label: str | None) -> str:
    suffix = f" - {invoice_period_label}" if invoice_period_label else ""
    return f"{client_display_name} invoice{suffix}"


def _intro_line(
    *,
    first_contact_intro_required: bool,
    recipient_name: str,
    client_display_name: str,
    supplier_portal_provider: str | None,
) -> str:
    if not first_contact_intro_required:
        return f"Hi {recipient_name},"
    if supplier_portal_provider == "COUPA":
        return (
            f"Hi {recipient_name} - I'm Clara Reid, helping Winship keep the "
            f"{client_display_name} invoice details organized."
        )
    return (
        f"Hi {recipient_name} - I'm Clara Reid, helping Winship keep the "
        f"{client_display_name} invoice package organized."
    )


def _capital_hilton_body(
    *,
    first_contact_intro_required: bool,
    attachment_ready: bool,
    invoice_period_label: str | None,
    invoice_dates_covered: tuple[str, ...],
    portal_submission_status: str,
) -> str:
    lines = [_intro_line(
        first_contact_intro_required=first_contact_intro_required,
        recipient_name="Annette",
        client_display_name="Capital Hilton",
        supplier_portal_provider="COUPA",
    ), ""]
    if attachment_ready:
        if invoice_dates_covered:
            covered = ", ".join(invoice_dates_covered)
            lines.append(f"Attached is the Excel invoice for your records covering {covered}.")
        elif invoice_period_label:
            lines.append(f"Attached is the Excel invoice for your records for {invoice_period_label}.")
        else:
            lines.append("Attached is the Excel invoice for your records.")
    else:
        lines.append("I'm preparing the Excel invoice note for your records once Winship confirms the invoice file.")
    if portal_submission_status == "SUBMITTED_RECEIPT_CONFIRMED":
        lines.append("The matching invoice has been submitted through the Coupa supplier portal.")
    lines.extend(("", "Best,", "Clara Reid"))
    return "\n".join(lines)


def _live_arts_md_body(
    *,
    first_contact_intro_required: bool,
    attachment_ready: bool,
    invoice_period_label: str | None,
    invoice_dates_covered: tuple[str, ...],
) -> str:
    lines = [_intro_line(
        first_contact_intro_required=first_contact_intro_required,
        recipient_name="Dance",
        client_display_name="Live Arts MD",
        supplier_portal_provider=None,
    ), ""]
    if attachment_ready:
        if invoice_dates_covered:
            covered = ", ".join(invoice_dates_covered)
            lines.append(f"Attached is Winship's invoice covering {covered}.")
        elif invoice_period_label:
            lines.append(f"Attached is Winship's invoice for {invoice_period_label}.")
        else:
            lines.append("Attached is Winship's invoice.")
        lines.append("Please let us know if anything else is needed for processing.")
    else:
        lines.append("Once Winship confirms the invoice file and recipient details, I'll send over the invoice for this period.")
    lines.extend(("", "Best,", "Clara Reid"))
    return "\n".join(lines)


def body_contains_backend_status_language(body: str) -> bool:
    lowered = body.lower()
    return any(term in lowered for term in CLIENT_FACING_FORBIDDEN_TERMS)


def _missing_prerequisites(
    *,
    recipient_package: Mapping[str, Any],
    attachment_ready: bool,
    invoice_period_label: str | None,
    invoice_dates_covered: tuple[str, ...],
    supplier_portal_required: bool,
    portal_submission_status: str | None,
    clara_draft_receipt_present: bool,
) -> tuple[str, ...]:
    missing: list[str] = []
    if not attachment_ready:
        missing.append("attachment_readiness")
    if not invoice_period_label and not invoice_dates_covered:
        missing.append("invoice_period_or_dates")
    if recipient_package.get("recipient_confirmation_status") != "CONFIRMED_BY_RECEIPT":
        missing.append("recipient_confirmation")
    if supplier_portal_required and portal_submission_status != "SUBMITTED_RECEIPT_CONFIRMED":
        missing.append("supplier_portal_submission_proof")
    if not clara_draft_receipt_present:
        missing.append("clara_draft_receipt")
    return tuple(missing)


def build_clara_invoice_email_draft_package(
    *,
    client_ref: str,
    workflow_ref: str,
    client_display_name: str,
    recipient_package: Mapping[str, Any],
    attachment_ready: bool,
    attachment_refs: tuple[str, ...] = (),
    invoice_period_label: str | None = None,
    invoice_dates_covered: tuple[str, ...] = (),
    supplier_portal_required: bool = False,
    supplier_portal_provider: str | None = None,
    portal_submission_status: str | None = None,
    first_contact_intro_required: bool = True,
    first_contact_intro_policy_ref: str | None = None,
    proof_refs: tuple[str, ...] = (),
    present_receipts: set[str] | tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    receipts = {str(item) for item in present_receipts}
    recipients_confirmed = recipient_package.get("recipient_confirmation_status") == "CONFIRMED_BY_RECEIPT"
    clara_receipt_present = "clara_email_draft_receipt" in receipts
    portal_status = portal_submission_status or "NOT_REQUIRED_BY_RECIPE"
    dates = tuple(str(item) for item in invoice_dates_covered if str(item).strip())
    missing = _missing_prerequisites(
        recipient_package=recipient_package,
        attachment_ready=attachment_ready,
        invoice_period_label=invoice_period_label,
        invoice_dates_covered=dates,
        supplier_portal_required=supplier_portal_required,
        portal_submission_status=portal_status,
        clara_draft_receipt_present=clara_receipt_present,
    )
    if client_ref == "capital_hilton":
        body = _capital_hilton_body(
            first_contact_intro_required=first_contact_intro_required,
            attachment_ready=attachment_ready,
            invoice_period_label=invoice_period_label,
            invoice_dates_covered=dates,
            portal_submission_status=portal_status,
        )
    elif client_ref == "live_arts_md":
        body = _live_arts_md_body(
            first_contact_intro_required=first_contact_intro_required,
            attachment_ready=attachment_ready,
            invoice_period_label=invoice_period_label,
            invoice_dates_covered=dates,
        )
    else:
        body = (
            f"Hi [Name] - I'm Clara Reid, helping Winship keep the {client_display_name} invoice organized.\n\n"
            "Once Winship confirms the invoice file and recipient details, I'll send it over.\n\n"
            "Best,\nClara Reid"
        )
    send_ready = not missing
    draft_status = FINAL_DRAFT_READY_FOR_APPROVAL if send_ready else DRAFT_PREVIEW_NOT_SEND_READY
    if not recipients_confirmed or not attachment_ready:
        draft_status = DRAFT_BLOCKED_PENDING_PREREQUISITES
    if body_contains_backend_status_language(body):
        draft_status = DRAFT_PLACEHOLDER_FOR_OPERATOR_REVIEW
    subject = _safe_subject(client_display_name, invoice_period_label)
    draft_ref = f"clara_invoice_email_draft:{client_ref}:{_short_hash(workflow_ref, subject, body)}"
    return {
        "client_ref": client_ref,
        "workflow_ref": workflow_ref,
        "draft_ref": draft_ref,
        "selected_voice": CLARA_SELECTED_VOICE,
        "internal_identity": CASSANDRA_INTERNAL_IDENTITY,
        "external_identity": CLARA_EXTERNAL_IDENTITY,
        "draft_status": draft_status,
        "draft_only": True,
        "sent": False,
        "send_allowed": False,
        "subject": subject,
        "body": body,
        "to_recipients": tuple(recipient_package.get("to_recipients", ())),
        "cc_recipients": tuple(recipient_package.get("cc_recipients", ())),
        "recipient_confirmation_status": recipient_package.get("recipient_confirmation_status", "CANDIDATE_UNCONFIRMED"),
        "recipient_email_invented": False,
        "attachment_refs": tuple(attachment_refs) if attachment_ready else (),
        "attachment_ready": attachment_ready,
        "invoice_period_label": invoice_period_label,
        "invoice_dates_covered": dates,
        "portal_submission_status": portal_status if supplier_portal_required else None,
        "supplier_portal_provider": supplier_portal_provider if supplier_portal_required else None,
        "first_contact_intro_required": first_contact_intro_required,
        "first_contact_intro_policy_ref": first_contact_intro_policy_ref,
        "missing_prerequisites": missing,
        "send_readiness": "READY_FOR_GUARDIAN_APPROVAL_REQUEST" if send_ready else "BLOCKED_PREREQUISITES",
        "guardian_approval_required": True,
        "guardian_approval_request_status": "NOT_CREATED",
        "send_execution_receipt_required": True,
        "send_execution_status": "NOT_SENT",
        "proof_refs": tuple(proof_refs),
        "client_facing_body_has_backend_status_language": body_contains_backend_status_language(body),
        "allowed_draft_statuses": DRAFT_STATUSES,
        "authority_boundary": {
            "email_send_performed": False,
            "gmail_draft_created": False,
            "gmail_polling_performed": False,
            "browser_or_supplier_portal_access_performed": False,
            "workbook_cell_read_performed": False,
            "invoice_generation_performed": False,
            "ledger_posting_performed": False,
            "production_mutation_performed": False,
        },
    }
