"""Reusable Clara invoice email draft package.

This module builds client-facing draft packages only. It does not create Gmail
drafts, send email, poll inboxes, read workbooks, generate invoice artifacts,
open browsers, access supplier portals, post ledgers, or mutate production
business state.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from agent_voice_profiles import (
    loop_closing_ask_for_workflow,
    render_loop_closing_ask,
    require_clara_copy_conformance,
    voice_copy_rules_for_speaker,
)


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

DEFAULT_CLARA_INVOICE_CLIENT_REGISTRY = {
    "capital_hilton": {
        "client_ref": "capital_hilton",
        "client_display_name": "Capital Hilton",
        "supplier_portal_required": True,
        "supplier_portal_provider": "COUPA",
        "recipients": (
            {"display_name": "Annette", "role": "finance_primary", "lane": "to"},
            {"display_name": "Chyna", "role": "finance_secondary", "lane": "cc"},
            {"display_name": "Will", "role": "relationship_contact", "lane": "cc"},
        ),
        "gated_claims": (
            {
                "claim_ref": "capital_hilton_excel_invoice_attached",
                "claim": "Excel invoice is attached for Annette's records.",
                "allowed_when": "attachment_ready",
                "required_receipt": "invoice_attachment_confirmed_receipt",
            },
            {
                "claim_ref": "capital_hilton_invoice_period_dates",
                "claim": "Invoice period or performance dates are stated.",
                "allowed_when": "invoice_period_or_dates",
                "required_receipt": "invoice_period_confirmed_receipt",
            },
            {
                "claim_ref": "capital_hilton_portal_submission",
                "claim": "Supplier portal invoice has been submitted.",
                "allowed_when": "portal_submitted",
                "required_receipt": "portal_invoice_submission_receipt",
                "supplier_portal_provider": "COUPA",
            },
        ),
    },
    "live_arts_md": {
        "client_ref": "live_arts_md",
        "client_display_name": "Live Arts MD",
        "recipients": (
            {"display_name": "Dane", "role": "primary_invoice_contact", "lane": "to"},
            {"display_name": "Draper", "role": "cc_candidate", "lane": "cc"},
            {"display_name": "Earnie", "role": "cc_candidate", "lane": "cc"},
            {
                "display_name": "Winship",
                "role": "operator_copy",
                "lane": "cc",
                "email": "winshiplive@gmail.com",
                "proof_ref": "operator_known_email:winshiplive@gmail.com",
            },
        ),
        "gated_claims": (
            {
                "claim_ref": "live_arts_md_invoice_attached",
                "claim": "Invoice is attached.",
                "allowed_when": "attachment_ready",
                "required_receipt": "invoice_attachment_confirmed_receipt",
            },
            {
                "claim_ref": "live_arts_md_invoice_period_or_work_type",
                "claim": "Invoice period or work type is stated.",
                "allowed_when": "invoice_period_or_dates",
                "required_receipt": "live_arts_md_invoice_candidate_selected_receipt",
            },
        ),
    },
    "st_annes": {
        "client_ref": "st_annes",
        "client_display_name": "St. Anne's",
        "recipients": (
            {
                "display_name": "Draper Carter",
                "role": "primary_invoice_contact",
                "lane": "to",
                "email": "draper.carter@gmail.com",
                "proof_ref": "operator_known_email:draper.carter@gmail.com",
            },
        ),
    },
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
    return _recipient_package_from_client_record(
        DEFAULT_CLARA_INVOICE_CLIENT_REGISTRY["capital_hilton"],
        {},
        confirmed=confirmed,
    )


def live_arts_md_recipient_package(*, confirmed: bool = False) -> dict[str, Any]:
    return _recipient_package_from_client_record(
        DEFAULT_CLARA_INVOICE_CLIENT_REGISTRY["live_arts_md"],
        {},
        confirmed=confirmed,
    )


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


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and _clean_text(value):
            return value
    return None


def _client_registry_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _clean_text(value).lower()).strip("_")


def _client_record_from_registry(
    *,
    client_ref: str,
    client_display_name: str,
    client_record: Mapping[str, Any] | None,
    client_registry: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, Any]:
    if client_record:
        return dict(client_record)

    registry: dict[str, Mapping[str, Any]] = dict(DEFAULT_CLARA_INVOICE_CLIENT_REGISTRY)
    if client_registry:
        registry.update({str(key): value for key, value in client_registry.items()})

    lookup_keys = {
        _client_registry_key(client_ref),
        _client_registry_key(client_display_name),
        str(client_ref),
        str(client_display_name),
    }
    for key, record in registry.items():
        record_keys = {
            _client_registry_key(key),
            _client_registry_key(record.get("client_ref")),
            _client_registry_key(record.get("client_display_name")),
        }
        record_keys.update(_client_registry_key(alias) for alias in record.get("aliases", ()))
        if lookup_keys & record_keys:
            return dict(record)
    return {}


def _record_recipients(record: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    recipients = record.get("recipients") or record.get("contacts") or record.get("client_specific_contacts") or ()
    if isinstance(recipients, Mapping):
        recipients = (recipients,)
    if not isinstance(recipients, (list, tuple)):
        return ()
    return tuple(item for item in recipients if isinstance(item, Mapping))


def _recipient_package_from_client_record(
    record: Mapping[str, Any],
    fallback_package: Mapping[str, Any],
    *,
    confirmed: bool = False,
) -> dict[str, Any]:
    raw_recipients = _record_recipients(record)
    if not raw_recipients:
        return dict(fallback_package)

    fallback_confirmed = fallback_package.get("recipient_confirmation_status") == "CONFIRMED_BY_RECEIPT"
    record_confirmed = record.get("recipient_confirmation_status") == "CONFIRMED_BY_RECEIPT"
    package_confirmed = confirmed or fallback_confirmed or record_confirmed
    recipients: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_recipients):
        name = _first_present(raw, "display_name", "name", "recipient_name", "label")
        if not name:
            continue
        role = _clean_text(_first_present(raw, "role", "contact_role")) or "primary_invoice_contact"
        lane = _clean_text(_first_present(raw, "lane", "recipient_lane", "delivery_lane")) or ("to" if index == 0 else "cc")
        email = _first_present(raw, "email", "email_address", "recipient_email", "to_email")
        proof_ref = _first_present(raw, "proof_ref", "receipt_ref", "source_ref")
        item_confirmed = package_confirmed or raw.get("confirmation_status") == "CONFIRMED_BY_RECEIPT" or raw.get("status") == "CONFIRMED_BY_RECEIPT"
        recipients.append(
            _recipient(
                _clean_text(name),
                role,
                "to" if lane not in {"to", "cc"} else lane,
                email=_clean_text(email) or None,
                confirmed=item_confirmed,
                proof_ref=_clean_text(proof_ref) or None,
            )
        )
    if not recipients:
        return dict(fallback_package)
    return _recipient_package(tuple(recipients))


def _contact_from_client_record(
    record: Mapping[str, Any],
    recipient_package: Mapping[str, Any],
    contact: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if contact:
        return dict(contact)
    draft_template = record.get("draft_template") if isinstance(record.get("draft_template"), Mapping) else {}
    greeting_name = _first_present(draft_template, "greeting_name", "recipient_name")
    if greeting_name:
        return {"name": greeting_name}
    recipients = tuple(recipient_package.get("to_recipients", ())) + tuple(recipient_package.get("cc_recipients", ()))
    for recipient in recipients:
        if not isinstance(recipient, Mapping):
            continue
        name = _first_present(recipient, "display_name", "name", "recipient_name", "label")
        email = _first_present(recipient, "email")
        if name or email:
            return {"name": name, "email": email}
    return {}


def _format_template(template: str, context: Mapping[str, Any]) -> str:
    class _SafeContext(dict):
        def __missing__(self, key):
            return ""

    safe_context = _SafeContext({key: "" if value is None else value for key, value in context.items()})
    return template.format_map(safe_context)


def _resolved_gated_claims(
    record: Mapping[str, Any],
    *,
    attachment_ready: bool,
    line_items_present: bool,
    invoice_period_label: str | None,
    invoice_dates_covered: tuple[str, ...],
    portal_submission_status: str | None,
) -> tuple[dict[str, Any], ...] | None:
    raw_claims = record.get("gated_claims")
    if not isinstance(raw_claims, (list, tuple)):
        draft_template = record.get("draft_template") if isinstance(record.get("draft_template"), Mapping) else {}
        raw_claims = draft_template.get("gated_claims")
    if not isinstance(raw_claims, (list, tuple)):
        return None

    claims: list[dict[str, Any]] = []
    for raw in raw_claims:
        if not isinstance(raw, Mapping):
            continue
        claim = dict(raw)
        allowed_when = claim.pop("allowed_when", None)
        if allowed_when == "attachment_ready":
            claim["allowed"] = attachment_ready
        elif allowed_when == "line_items_present":
            claim["allowed"] = line_items_present
        elif allowed_when == "invoice_period_or_dates":
            claim["allowed"] = bool(invoice_period_label or invoice_dates_covered)
        elif allowed_when == "portal_submitted":
            claim["allowed"] = portal_submission_status == "SUBMITTED_RECEIPT_CONFIRMED"
        else:
            claim["allowed"] = bool(claim.get("allowed", False))
        claims.append(claim)
    return tuple(claims)


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


def _supplier_portal_display_name(provider: str) -> str:
    if provider.upper() == "COUPA":
        return "Coupa"
    return provider


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


def _contact_role_is_intermediary(contact: Mapping[str, Any] | None) -> bool:
    role = _clean_text((contact or {}).get("role")).lower() if contact else ""
    return "intermediary" in role or "forward" in role


def _warm_closing_line(
    contact: Mapping[str, Any] | None,
    *,
    workflow_ref: str,
    client_ref: str,
) -> str:
    del contact
    closure = loop_closing_ask_for_workflow(workflow_ref, client_ref=client_ref)
    return render_loop_closing_ask(closure)


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
    supplier_portal_provider: str | None = None,
    portal_submission_status: str | None = None,
) -> dict[str, Any]:
    data = dict(invoice_data or {})
    data.setdefault("client_name", client_display_name)
    data.setdefault("attachment_ready", attachment_ready)
    data.setdefault("invoice_period_label", invoice_period_label)
    data.setdefault("invoice_dates_covered", invoice_dates_covered)
    data.setdefault("supplier_portal_provider", supplier_portal_provider)
    data.setdefault("portal_submission_status", portal_submission_status)
    if not _line_items_from_invoice_data(data):
        data.setdefault("coverage_label", _natural_join(invoice_dates_covered) if invoice_dates_covered else invoice_period_label)
        if invoice_dates_covered:
            label = invoice_period_label or "invoice work"
            data["line_items"] = tuple({"event": label, "date": date} for date in invoice_dates_covered)
        elif invoice_period_label:
            data["line_items"] = ({"event": invoice_period_label},)
    return data


def build_general_client_invoice_body(
    invoice_data: Mapping[str, Any],
    contact: Mapping[str, Any] | None,
    *,
    first_contact_intro_required: bool | None = None,
    client_ref: str = "",
    workflow_ref: str = "",
) -> str:
    """Build a reusable Clara invoice email body for clients without bespoke recipes."""
    client_name = _clean_text(
        _first_present(invoice_data, "client_name", "client_display_name", "client", "customer_name")
    ) or "your organization"
    line_items = _line_items_from_invoice_data(invoice_data)
    minor_units = _amounts_are_minor_units(line_items)
    covered = _natural_join(tuple(_format_line_item(item, minor_units=minor_units) for item in line_items))
    covered_has_amounts = any(item.get("amount") is not None for item in line_items)
    coverage_label = _clean_text(invoice_data.get("coverage_label"))
    coverage = coverage_label or (covered if line_items else _clean_text(invoice_data.get("invoice_period_label")) or covered)
    total = _invoice_total(invoice_data, line_items, minor_units=minor_units)
    attachment_filename = _clean_text(
        _first_present(invoice_data, "attachment_filename", "pdf_filename", "attachment_name", "invoice_pdf_filename")
    )
    attachment_ready = invoice_data.get("attachment_ready", True) is not False
    include_intro = (
        bool(first_contact_intro_required)
        if first_contact_intro_required is not None
        else invoice_data.get("first_contact_intro_required") is True
    )

    copy_rules = voice_copy_rules_for_speaker("clara")
    lines = [_contact_greeting(contact), ""]
    if include_intro:
        lines.extend((str(copy_rules["first_contact_intro"]), ""))
    if attachment_ready:
        attachment_label = f" ({attachment_filename})" if attachment_filename else ""
        if total:
            lines.append(
                f"Winship's invoice for {client_name} is attached{attachment_label}. "
                f"It covers {coverage}, coming to {total}."
            )
        else:
            lines.append(
                f"Winship's invoice for {client_name} is attached{attachment_label}. It covers {coverage}."
            )
    else:
        if total and coverage and not covered_has_amounts:
            lines.append(
                f"Winship's confirmed {client_name} invoice, covering {coverage} ({total}), "
                "is on its way to you."
            )
        elif coverage:
            lines.append(
                f"Winship's confirmed {client_name} invoice, covering {coverage}, "
                "is on its way to you."
            )
        elif total:
            lines.append(
                f"Winship's confirmed {client_name} invoice, totaling {total}, "
                "is on its way to you."
            )
        else:
            lines.append(f"Winship's confirmed {client_name} invoice is on its way to you.")
    portal_provider = _clean_text(invoice_data.get("supplier_portal_provider"))
    if portal_provider and invoice_data.get("portal_submission_status") == "SUBMITTED_RECEIPT_CONFIRMED":
        lines.append(
            f"The matching invoice has been submitted through the "
            f"{_supplier_portal_display_name(portal_provider)} supplier portal."
        )
    lines.extend((
        "",
        _warm_closing_line(
            contact,
            workflow_ref=workflow_ref,
            client_ref=client_ref,
        ),
        "",
        str(copy_rules["signoff"]),
    ))
    body = "\n".join(lines)
    if body_contains_backend_status_language(body):
        raise ValueError("Generated client-facing invoice body contains forbidden status language.")
    require_clara_copy_conformance(
        body,
        workflow_ref=workflow_ref,
        client_ref=client_ref,
    )
    return body


def _general_target_blueprint(
    *,
    subject: str,
    body_template: str,
    line_items_present: bool,
    attachment_ready: bool,
    missing_prerequisites: tuple[str, ...],
    gated_claims: tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Any]:
    resolved_claims = gated_claims or (
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
        "gated_claims": resolved_claims,
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
    client_record: Mapping[str, Any] | None = None,
    client_registry: Mapping[str, Mapping[str, Any]] | None = None,
    raw_operator_ask: str | None = None,
    model_compose: bool = False,
    copy_generator: Any = None,
    compose_attempts: int = 3,
    record_compose_telemetry: bool = False,
) -> dict[str, Any]:
    receipts = {str(item) for item in present_receipts}
    clara_receipt_present = "clara_email_draft_receipt" in receipts
    record = _client_record_from_registry(
        client_ref=client_ref,
        client_display_name=client_display_name,
        client_record=client_record,
        client_registry=client_registry,
    )
    record_display_name = _first_present(record, "client_display_name", "display_name", "name")
    if record_display_name:
        client_display_name = _clean_text(record_display_name)
    if record.get("supplier_portal_required") is True:
        supplier_portal_required = True
    supplier_portal_provider = supplier_portal_provider or _first_present(
        record,
        "supplier_portal_provider",
        "portal_provider",
    )
    portal_status = portal_submission_status or "NOT_REQUIRED_BY_RECIPE"
    dates = tuple(str(item) for item in invoice_dates_covered if str(item).strip())
    effective_recipient_package = _recipient_package_from_client_record(record, recipient_package)
    general_invoice_data = _general_invoice_data_from_package_args(
        client_display_name=client_display_name,
        attachment_ready=attachment_ready,
        invoice_period_label=invoice_period_label,
        invoice_dates_covered=dates,
        invoice_data=invoice_data,
        supplier_portal_provider=supplier_portal_provider,
        portal_submission_status=portal_status,
    )
    general_contact = _contact_from_client_record(record, effective_recipient_package, contact)
    effective_recipient_package = _general_recipient_package_with_contact(
        effective_recipient_package,
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
    body = build_general_client_invoice_body(
        general_invoice_data,
        general_contact,
        first_contact_intro_required=first_contact_intro_required,
        client_ref=client_ref,
        workflow_ref=workflow_ref,
    )
    compose_proof: dict[str, Any] | None = None
    if model_compose or copy_generator is not None:
        from clara_invoice_copy_composer import compose_invoice_copy

        closure = loop_closing_ask_for_workflow(workflow_ref, client_ref=client_ref)
        greeting = _contact_greeting(general_contact)
        copy_rules = voice_copy_rules_for_speaker("clara")
        required_body_atoms: list[str] = []
        exactly_once_body_atoms = [
            greeting,
            closure["ask_text"],
            closure["why_text"],
        ]
        for atom in tuple(general_invoice_data.get("model_required_body_atoms") or ()):
            if str(atom).strip():
                required_body_atoms.append(str(atom).strip())
        packet_facts = tuple(general_invoice_data.get("model_packet_facts") or ())
        packet_aid = {
            "packet_id": "clara-invoice-copy:" + _short_hash(client_ref, workflow_ref, subject, body),
            "facts": packet_facts,
            "privacy": {"package_minimized": True, "unresolved_sensitive_values": False},
            "authority": {
                "provider_draft_allowed": False,
                "email_send_allowed": False,
                "transaction_mutation_allowed": False,
            },
        }
        copy_contract = {
            "client_ref": client_ref,
            "workflow_ref": workflow_ref,
            "greeting": greeting,
            "canonical_signoff": str(copy_rules["signoff"]),
            "required_subject_atoms": tuple(general_invoice_data.get("model_required_subject_atoms") or ()),
            "required_body_atoms": tuple(required_body_atoms),
            "exactly_once_body_atoms": tuple(exactly_once_body_atoms),
            "required_any_body_atom_groups": tuple(
                tuple(str(atom) for atom in group)
                for group in general_invoice_data.get("model_required_any_body_atom_groups", ())
            ),
            "forbidden_claims": tuple(general_invoice_data.get("model_forbidden_claims") or ()),
            "copy_fact_citations": tuple(general_invoice_data.get("model_copy_fact_citations") or ()),
            "deterministic_fallback_subject_sha256": "sha256:" + hashlib.sha256(subject.encode("utf-8")).hexdigest(),
            "deterministic_fallback_body_sha256": "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest(),
        }
        try:
            compose_proof = compose_invoice_copy(
                str(raw_operator_ask or "Compose concise client-facing invoice copy."),
                packet_aid,
                copy_contract,
                generator_fn=copy_generator,
                attempts=compose_attempts,
            )
        except Exception as exc:
            rejected_proof = getattr(exc, "result", None)
            if record_compose_telemetry and isinstance(rejected_proof, Mapping):
                from clara_invoice_copy_composer import record_invoice_copy_taste_pass

                record_invoice_copy_taste_pass(rejected_proof)
            raise
        if record_compose_telemetry:
            from clara_invoice_copy_composer import record_invoice_copy_taste_pass

            record_invoice_copy_taste_pass(compose_proof)
        subject = str(compose_proof["subject"])
        body = str(compose_proof["body"])
    clara_conformance = require_clara_copy_conformance(
        body,
        workflow_ref=workflow_ref,
        client_ref=client_ref,
    )
    voice_conformance = clara_conformance["voice_conformance"]
    line_items_present = bool(_line_items_from_invoice_data(general_invoice_data))
    target_blueprint = _general_target_blueprint(
        subject=subject,
        body_template=body,
        line_items_present=line_items_present,
        attachment_ready=attachment_ready,
        missing_prerequisites=missing,
        gated_claims=_resolved_gated_claims(
            record,
            attachment_ready=attachment_ready,
            line_items_present=line_items_present,
            invoice_period_label=invoice_period_label,
            invoice_dates_covered=dates,
            portal_submission_status=portal_status,
        ),
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
        "voice_profile_ref": voice_conformance["voice_profile_ref"],
        "voice_conformance": voice_conformance,
        "loop_closing_ask_conformance": clara_conformance["loop_closing_ask"],
        "internal_identity": CASSANDRA_INTERNAL_IDENTITY,
        "external_identity": CLARA_EXTERNAL_IDENTITY,
        "draft_status": draft_status,
        "draft_only": True,
        "sent": False,
        "send_allowed": False,
        "subject": subject,
        "body": body,
        "model_compose_proof": compose_proof,
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
