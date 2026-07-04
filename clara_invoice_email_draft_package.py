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
TARGET_BLUEPRINT_NOT_SEND_READY = "TARGET_BLUEPRINT_NOT_SEND_READY"
CLIENT_FACING_DRAFT_BLOCKED = "CLIENT_FACING_DRAFT_BLOCKED"
SENT_EMAIL_NOT_SENT = "NOT_SENT"

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
    "once winship confirms",
    "i'm preparing",
    "backend",
    "proof ui",
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
        _recipient("Dane", "primary_invoice_contact", "to", confirmed=confirmed),
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
        lines.append("Invoice attachment: [confirmed Excel invoice for Annette's records].")
        lines.append("Period covered: [confirmed Capital Hilton invoice dates or period].")
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
        recipient_name="Dane",
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
        lines.append("Invoice attachment: [confirmed Live Arts MD invoice].")
        lines.append("Work covered: [selected invoice period or work type].")
        lines.append("Recipient action: [review and process the confirmed invoice].")
    lines.extend(("", "Best,", "Clara Reid"))
    return "\n".join(lines)


def _capital_hilton_target_blueprint(
    *,
    first_contact_intro_required: bool,
    invoice_period_label: str | None,
    invoice_dates_covered: tuple[str, ...],
    portal_submission_status: str,
    attachment_ready: bool,
    missing_prerequisites: tuple[str, ...],
    subject: str,
) -> dict[str, Any]:
    body_template = _capital_hilton_body(
        first_contact_intro_required=first_contact_intro_required,
        attachment_ready=attachment_ready,
        invoice_period_label=invoice_period_label,
        invoice_dates_covered=invoice_dates_covered,
        portal_submission_status=portal_submission_status,
    )
    gated_claims = [
        {
            "claim_ref": "capital_hilton_excel_invoice_attached",
            "claim": "Excel invoice is attached for Annette's records.",
            "allowed": attachment_ready,
            "required_receipt": "invoice_attachment_confirmed_receipt",
        },
        {
            "claim_ref": "capital_hilton_invoice_period_dates",
            "claim": "Invoice period or performance dates are stated.",
            "allowed": bool(invoice_period_label or invoice_dates_covered),
            "required_receipt": "invoice_period_confirmed_receipt",
        },
        {
            "claim_ref": "capital_hilton_portal_submission",
            "claim": "Supplier portal invoice has been submitted.",
            "allowed": portal_submission_status == "SUBMITTED_RECEIPT_CONFIRMED",
            "required_receipt": "portal_invoice_submission_receipt",
            "supplier_portal_provider": "COUPA",
        },
    ]
    return {
        "status": TARGET_BLUEPRINT_NOT_SEND_READY if missing_prerequisites else FINAL_DRAFT_READY_FOR_APPROVAL,
        "purpose": "Target final client email blueprint with gated claims.",
        "subject_template": subject,
        "body_template": body_template,
        "unresolved_slots": tuple(missing_prerequisites),
        "gated_claims": tuple(gated_claims),
        "send_ready": False,
    }


def _live_arts_md_target_blueprint(
    *,
    first_contact_intro_required: bool,
    invoice_period_label: str | None,
    invoice_dates_covered: tuple[str, ...],
    attachment_ready: bool,
    missing_prerequisites: tuple[str, ...],
    subject: str,
) -> dict[str, Any]:
    body_template = _live_arts_md_body(
        first_contact_intro_required=first_contact_intro_required,
        attachment_ready=attachment_ready,
        invoice_period_label=invoice_period_label,
        invoice_dates_covered=invoice_dates_covered,
    )
    gated_claims = (
        {
            "claim_ref": "live_arts_md_invoice_attached",
            "claim": "Invoice is attached.",
            "allowed": attachment_ready,
            "required_receipt": "invoice_attachment_confirmed_receipt",
        },
        {
            "claim_ref": "live_arts_md_invoice_period_or_work_type",
            "claim": "Invoice period or work type is stated.",
            "allowed": bool(invoice_period_label or invoice_dates_covered),
            "required_receipt": "live_arts_md_invoice_candidate_selected_receipt",
        },
    )
    return {
        "status": TARGET_BLUEPRINT_NOT_SEND_READY if missing_prerequisites else FINAL_DRAFT_READY_FOR_APPROVAL,
        "purpose": "Target final client email blueprint with gated claims.",
        "subject_template": subject,
        "body_template": body_template,
        "unresolved_slots": tuple(missing_prerequisites),
        "gated_claims": gated_claims,
        "send_ready": False,
    }


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and _clean_text(value):
            return value
    return None


def _amounts_are_minor_units(line_items: tuple[Mapping[str, Any], ...]) -> bool:
    """Mirror invoice_generator: all line-item amounts are ints >= 1000 => cents (minor units)."""
    amounts = [item.get("amount") for item in line_items]
    return bool(amounts) and all(
        isinstance(a, int) and not isinstance(a, bool) and abs(a) >= 1000 for a in amounts
    )


def _format_money(value: Any, *, minor_units: bool = False) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        number = (value / 100) if minor_units else float(value)
        return f"${number:,.2f}"
    text = _clean_text(value)
    if not text:
        return None
    if text.startswith("$"):
        try:
            number = float(text[1:].replace(",", ""))
        except ValueError:
            return text
        return f"${number:,.2f}"
    try:
        number = float(text.replace(",", ""))
    except ValueError:
        return text
    return f"${number:,.2f}"


def _money_number(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    text = _clean_text(value).replace("$", "").replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _natural_join(items: tuple[str, ...]) -> str:
    if not items:
        return "the listed work"
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _line_items_from_invoice_data(invoice_data: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    raw_items = _first_present(invoice_data, "line_items", "items", "charges", "events") or ()
    if isinstance(raw_items, Mapping):
        raw_items = (raw_items,)
    items: list[dict[str, Any]] = []
    iterable_items = raw_items if isinstance(raw_items, (list, tuple)) else ()
    for raw_item in iterable_items:
        if not isinstance(raw_item, Mapping):
            continue
        event = _first_present(raw_item, "event", "description", "service", "work", "name", "title", "item", "label")
        date = _first_present(raw_item, "date", "event_date", "service_date", "performed_on", "performance_date")
        amount = _first_present(raw_item, "amount", "total", "subtotal", "price", "fee")
        if event or date or amount is not None:
            items.append({"event": event, "date": date, "amount": amount})
    return tuple(items)


def _format_line_item(item: Mapping[str, Any], *, minor_units: bool = False) -> str:
    event = _clean_text(item.get("event"))
    date = _clean_text(item.get("date"))
    amount = _format_money(item.get("amount"), minor_units=minor_units)
    description = event or "service"
    if date:
        description = f"{description} on {date}"
    if amount:
        description = f"{description} ({amount})"
    return description


def _invoice_total(invoice_data: Mapping[str, Any], line_items: tuple[Mapping[str, Any], ...], *, minor_units: bool = False) -> str | None:
    total = _first_present(invoice_data, "total", "total_amount", "invoice_total", "balance_due", "amount_due", "amount_total", "amount")
    if total is not None:
        total_minor = minor_units and isinstance(total, int) and not isinstance(total, bool) and abs(total) >= 1000
        return _format_money(total, minor_units=total_minor)
    amounts = [_money_number(item.get("amount")) for item in line_items]
    numeric_amounts = [amount for amount in amounts if amount is not None]
    if numeric_amounts and len(numeric_amounts) == len(line_items):
        return _format_money(sum(numeric_amounts), minor_units=minor_units)
    return None


def _contact_greeting(contact: Mapping[str, Any] | None) -> str:
    if not contact:
        return "Hello,"
    name = _first_present(contact, "first_name", "given_name", "name", "display_name", "recipient_name")
    if not name:
        return "Hello,"
    name_text = _clean_text(name)
    if not name_text or "@" in name_text:
        return "Hello,"
    return f"Hi {name_text.split()[0]},"


def _general_contact_from_recipient_package(
    recipient_package: Mapping[str, Any],
    contact: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if contact:
        return dict(contact)
    recipients = tuple(recipient_package.get("to_recipients", ())) + tuple(recipient_package.get("cc_recipients", ()))
    for recipient in recipients:
        if not isinstance(recipient, Mapping):
            continue
        name = _first_present(recipient, "display_name", "name", "recipient_name", "label")
        email = _first_present(recipient, "email")
        if name or email:
            return {"name": name, "email": email}
    return {}


def _general_recipient_package_with_contact(
    recipient_package: Mapping[str, Any],
    invoice_data: Mapping[str, Any],
    contact: Mapping[str, Any],
) -> dict[str, Any]:
    email = _first_present(contact, "email", "email_address", "recipient_email", "to_email")
    if not email:
        email = _first_present(invoice_data, "recipient_email", "to_email", "contact_email", "billing_contact_email")
    name = _first_present(contact, "name", "display_name", "recipient_name", "first_name", "given_name")
    if not name:
        name = _first_present(invoice_data, "recipient_name", "contact_name", "billing_contact_name")
    if not email and not name:
        return dict(recipient_package)

    to_recipients = [dict(item) for item in recipient_package.get("to_recipients", ()) if isinstance(item, Mapping)]
    cc_recipients = [dict(item) for item in recipient_package.get("cc_recipients", ()) if isinstance(item, Mapping)]
    if to_recipients:
        primary = dict(to_recipients[0])
        if email and not primary.get("email"):
            primary["email"] = _clean_text(email)
            primary["email_status"] = "KNOWN_OPERATOR_PROVIDED"
            primary["email_invented"] = False
        if name and not primary.get("display_name"):
            primary["display_name"] = _clean_text(name)
        to_recipients[0] = primary
    else:
        confirmed = recipient_package.get("recipient_confirmation_status") == "CONFIRMED_BY_RECEIPT"
        to_recipients.append(
            _recipient(
                _clean_text(name) or "Invoice contact",
                "primary_invoice_contact",
                "to",
                email=_clean_text(email) or None,
                confirmed=confirmed,
            )
        )
    return _recipient_package(tuple(to_recipients + cc_recipients))


def _general_invoice_data_from_package_args(
    *,
    client_display_name: str,
    attachment_ready: bool,
    invoice_period_label: str | None,
    invoice_dates_covered: tuple[str, ...],
    invoice_data: Mapping[str, Any] | None,
) -> dict[str, Any]:
    data = dict(invoice_data or {})
    data.setdefault("client_name", client_display_name)
    data.setdefault("attachment_ready", attachment_ready)
    if not _line_items_from_invoice_data(data):
        if invoice_dates_covered:
            label = invoice_period_label or "invoice work"
            data["line_items"] = tuple({"event": label, "date": date} for date in invoice_dates_covered)
        elif invoice_period_label:
            data["line_items"] = ({"event": invoice_period_label},)
    return data


def build_general_client_invoice_body(invoice_data: Mapping[str, Any], contact: Mapping[str, Any] | None) -> str:
    """Build a reusable Clara invoice email body for clients without bespoke recipes."""
    client_name = _clean_text(
        _first_present(invoice_data, "client_name", "client_display_name", "client", "customer_name")
    ) or "your organization"
    line_items = _line_items_from_invoice_data(invoice_data)
    minor_units = _amounts_are_minor_units(line_items)
    covered = _natural_join(tuple(_format_line_item(item, minor_units=minor_units) for item in line_items))
    total = _invoice_total(invoice_data, line_items, minor_units=minor_units)
    attachment_filename = _clean_text(
        _first_present(invoice_data, "attachment_filename", "pdf_filename", "attachment_name", "invoice_pdf_filename")
    )
    attachment_ready = invoice_data.get("attachment_ready", True) is not False

    lines = [_contact_greeting(contact), ""]
    if attachment_ready:
        attachment_label = f" ({attachment_filename})" if attachment_filename else ""
        lines.append(f"Attached is Winship's invoice PDF{attachment_label} for {client_name}, covering {covered}.")
    else:
        lines.append(f"I have Winship's invoice for {client_name} covering {covered}.")
    if total:
        lines.append(f"The total due is {total}.")
    lines.append("Please let us know if anything else is needed for processing.")
    lines.extend(("", "Best,", "Clara Reid"))
    body = "\n".join(lines)
    if body_contains_backend_status_language(body):
        raise ValueError("Generated client-facing invoice body contains forbidden status language.")
    return body


def _general_target_blueprint(
    *,
    subject: str,
    body_template: str,
    line_items_present: bool,
    attachment_ready: bool,
    missing_prerequisites: tuple[str, ...],
) -> dict[str, Any]:
    gated_claims = (
        {
            "claim_ref": "general_client_invoice_pdf_attached",
            "claim": "Invoice PDF is attached.",
            "allowed": attachment_ready,
            "required_receipt": "invoice_attachment_confirmed_receipt",
        },
        {
            "claim_ref": "general_client_invoice_line_items",
            "claim": "Invoice line items, period, or dates are stated.",
            "allowed": line_items_present,
            "required_receipt": "invoice_line_items_or_period_confirmed_receipt",
        },
    )
    return {
        "status": TARGET_BLUEPRINT_NOT_SEND_READY if missing_prerequisites else FINAL_DRAFT_READY_FOR_APPROVAL,
        "purpose": "Target final client email blueprint with gated claims.",
        "subject_template": subject,
        "body_template": body_template,
        "unresolved_slots": tuple(missing_prerequisites),
        "gated_claims": gated_claims,
        "send_ready": False,
    }


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
    invoice_data: Mapping[str, Any] | None = None,
    contact: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    receipts = {str(item) for item in present_receipts}
    clara_receipt_present = "clara_email_draft_receipt" in receipts
    portal_status = portal_submission_status or "NOT_REQUIRED_BY_RECIPE"
    dates = tuple(str(item) for item in invoice_dates_covered if str(item).strip())
    general_invoice_data = None
    general_contact = None
    effective_recipient_package = recipient_package
    if client_ref not in {"capital_hilton", "live_arts_md"}:
        general_invoice_data = _general_invoice_data_from_package_args(
            client_display_name=client_display_name,
            attachment_ready=attachment_ready,
            invoice_period_label=invoice_period_label,
            invoice_dates_covered=dates,
            invoice_data=invoice_data,
        )
        general_contact = _general_contact_from_recipient_package(recipient_package, contact)
        effective_recipient_package = _general_recipient_package_with_contact(
            recipient_package,
            general_invoice_data,
            general_contact,
        )
    recipients_confirmed = effective_recipient_package.get("recipient_confirmation_status") == "CONFIRMED_BY_RECEIPT"
    missing = _missing_prerequisites(
        recipient_package=effective_recipient_package,
        attachment_ready=attachment_ready,
        invoice_period_label=invoice_period_label,
        invoice_dates_covered=dates,
        supplier_portal_required=supplier_portal_required,
        portal_submission_status=portal_status,
        clara_draft_receipt_present=clara_receipt_present,
    )
    subject = _safe_subject(client_display_name, invoice_period_label)
    if client_ref == "capital_hilton":
        body = _capital_hilton_body(
            first_contact_intro_required=first_contact_intro_required,
            attachment_ready=attachment_ready,
            invoice_period_label=invoice_period_label,
            invoice_dates_covered=dates,
            portal_submission_status=portal_status,
        )
        target_blueprint = _capital_hilton_target_blueprint(
            first_contact_intro_required=first_contact_intro_required,
            invoice_period_label=invoice_period_label,
            invoice_dates_covered=dates,
            portal_submission_status=portal_status,
            attachment_ready=attachment_ready,
            missing_prerequisites=missing,
            subject=subject,
        )
    elif client_ref == "live_arts_md":
        body = _live_arts_md_body(
            first_contact_intro_required=first_contact_intro_required,
            attachment_ready=attachment_ready,
            invoice_period_label=invoice_period_label,
            invoice_dates_covered=dates,
        )
        target_blueprint = _live_arts_md_target_blueprint(
            first_contact_intro_required=first_contact_intro_required,
            invoice_period_label=invoice_period_label,
            invoice_dates_covered=dates,
            attachment_ready=attachment_ready,
            missing_prerequisites=missing,
            subject=subject,
        )
    else:
        assert general_invoice_data is not None
        assert general_contact is not None
        body = build_general_client_invoice_body(general_invoice_data, general_contact)
        target_blueprint = _general_target_blueprint(
            subject=subject,
            body_template=body,
            line_items_present=bool(_line_items_from_invoice_data(general_invoice_data)),
            attachment_ready=attachment_ready,
            missing_prerequisites=missing,
        )
    send_ready = not missing
    draft_status = FINAL_DRAFT_READY_FOR_APPROVAL if send_ready else DRAFT_PREVIEW_NOT_SEND_READY
    if not recipients_confirmed or not attachment_ready:
        draft_status = DRAFT_BLOCKED_PENDING_PREREQUISITES
    if body_contains_backend_status_language(body):
        draft_status = DRAFT_PLACEHOLDER_FOR_OPERATOR_REVIEW
    target_blueprint = dict(target_blueprint)
    target_blueprint["send_ready"] = send_ready
    client_facing_ready = {
        "status": FINAL_DRAFT_READY_FOR_APPROVAL if send_ready else CLIENT_FACING_DRAFT_BLOCKED,
        "ready": send_ready,
        "subject": subject if send_ready else None,
        "body": body if send_ready else None,
        "blocked_by": () if send_ready else missing,
        "exact_email_ready_for_guardian_operator_approval": send_ready,
    }
    sent_email = {
        "status": SENT_EMAIL_NOT_SENT,
        "sent": False,
        "send_execution_receipt_ref": None,
    }
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
        "target_client_email_blueprint": target_blueprint,
        "client_facing_draft_ready_for_approval": client_facing_ready,
        "sent_email": sent_email,
        "to_recipients": tuple(effective_recipient_package.get("to_recipients", ())),
        "cc_recipients": tuple(effective_recipient_package.get("cc_recipients", ())),
        "recipient_confirmation_status": effective_recipient_package.get("recipient_confirmation_status", "CANDIDATE_UNCONFIRMED"),
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
