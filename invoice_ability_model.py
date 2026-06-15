"""System invoice ability model builder.

This module implements the facts-to-invoice-model part of the universal invoice
ability. It does not render PDFs, mutate workbooks, send email, call Square,
write ledgers, restart services, or alter SEND_HOLD.
"""

from __future__ import annotations

import json
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping


SCHEMA_VERSION = "system_invoice_ability_model_v1"
SUPPORTED_ARCHETYPES = {
    "simple_gig",
    "monthly_multiline",
    "rental_equipment",
    "hourly_services",
    "reconciliation",
}
IMPLEMENTED_ARCHETYPES = {"simple_gig", "monthly_multiline"}
MONEY_QUANT = Decimal("0.01")


COMMON_FIELD_MAP = {
    "header": {
        "invoice_title": "G2",
        "invoice_number": "G3",
        "invoice_date": "G4",
        "event_or_job": "G5",
        "venue_address_line1": "G6",
        "venue_city_state": "G7",
    },
    "issuer": {
        "business_identity_display": ("C3", "B9"),
        "business_address_line1": "B10",
        "business_city_state_zip": "B11",
        "business_phone": "B12",
        "business_email": "B13",
    },
    "terms": {
        "payment_terms": "G14",
        "currency": "model.currency",
    },
    "line_items": {
        "line_item_number": "B row",
        "line_item_description": "C row",
        "line_item_quantity": "D row",
        "line_item_unit_price": "E row",
        "line_item_discount": "F row",
        "line_item_amount": "G row",
    },
    "payment_instructions": {
        "payment_method_check": "B30",
        "payment_method_electronic": ("B31", "B32"),
        "client_facing_review_required": True,
    },
    "status": {
        "send_authorization": "never inferred from invoice status, receipt status, or PDF existence",
    },
    "internal_notes": {
        "client_facing_default": "excluded",
        "include_only_when_render_policy_allows": True,
    },
}


TEMPLATE_PROFILES: dict[str, dict[str, Any]] = {
    "simple_gig": {
        "profile_id": "reynolds_st_annes_simple_gig_v1",
        "archetype": "simple_gig",
        "template_source_ref": "Invoice St. Anne's Running.xlsx",
        "selected_sheet_name": "April 2026",
        "selection_reason": "Simple venue-style direct subtotal/total invoice for one-off performance work.",
        "printable_strategy": "one-sheet direct invoice page",
        "formula_dependency_strategy": "no cross-sheet dependency expected for selected page",
        "line_item_mode": "range_based_direct_amounts",
        "line_table_name": None,
        "line_item_rows": "B16:G21",
        "supports_negative_credit_lines": False,
        "contains_receipt_status": False,
        "contains_internal_reconciliation_notes": False,
        "field_map_overrides": {
            "bill_to": {
                "bill_to_name": "G9",
                "bill_to_address_line1": "G10",
                "bill_to_city_state": "G11",
                "bill_to_contact_name_role": "G12",
                "bill_to_contact_email": "G13",
                "bill_to_phone": None,
            },
            "totals": {
                "subtotal": "G24",
                "tax_rate": "G25",
                "sales_tax": "G26",
                "deposit_received": "G27",
                "total_due": "G28",
            },
        },
    },
    "monthly_multiline": {
        "profile_id": "capital_hilton_monthly_multiline_v1",
        "archetype": "monthly_multiline",
        "template_source_ref": "Invoice Capital Hilton Running.xlsx",
        "selected_sheet_name": "Invoice",
        "selection_reason": "Repeating line table with multiple service rows and possible negative credit rows.",
        "printable_strategy": "one-sheet table invoice page",
        "formula_dependency_strategy": "selected validation sheet has no cross-sheet dependency in the render page",
        "line_item_mode": "table_based_formula_amounts",
        "line_table_name": "SimpleInvoice",
        "line_item_rows": "B16:G22",
        "supports_negative_credit_lines": True,
        "contains_receipt_status": False,
        "contains_internal_reconciliation_notes": False,
        "field_map_overrides": {
            "bill_to": {
                "bill_to_name": "G9",
                "bill_to_address_line1": "G10",
                "bill_to_city_state": "G11",
                "bill_to_contact_name_role": None,
                "bill_to_contact_email": None,
                "bill_to_phone": "G12",
            },
            "totals": {
                "subtotal": "G24",
                "tax_rate": "G25",
                "sales_tax": "G26",
                "deposit_received": "G27",
                "total_due": "G28",
            },
        },
    },
}


RENDER_DEPENDENCY = {
    "status": "RENDER_DEPENDENCY_NOT_IMPLEMENTED",
    "pdf_rendered": False,
    "workbook_written": False,
    "renderer_required": True,
    "renderer_options": (
        "headless_libreoffice",
        "purpose_built_templating_renderer",
    ),
    "not_using_mac_excel": True,
    "reason": (
        "A2 implements facts -> structured invoice model and field map only. "
        "PDF render/hash/page-count registration remains a separate dependency."
    ),
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _get(mapping: Mapping[str, Any], *path: str) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _require(mapping: Mapping[str, Any], paths: tuple[tuple[str, ...], ...]) -> None:
    missing = []
    for path in paths:
        value = _get(mapping, *path)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(".".join(path))
    if missing:
        raise ValueError(f"invoice facts missing required field(s): {', '.join(missing)}")


def _decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def _money(value: Any) -> str:
    return str(_decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))


def _field_map_for_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    field_map = deepcopy(COMMON_FIELD_MAP)
    for section, overrides in profile["field_map_overrides"].items():
        field_map.setdefault(section, {})
        field_map[section].update(overrides)
    return field_map


def validate_invoice_facts(facts: Mapping[str, Any]) -> None:
    """Validate the minimum SYSTEM HANDOFF invoice facts shape."""

    required_paths = (
        ("invoice_request_id",),
        ("source_type",),
        ("business_identity", "display_name"),
        ("business_identity", "legal_or_payable_name"),
        ("business_identity", "address_line1"),
        ("business_identity", "city_state_zip"),
        ("business_identity", "phone"),
        ("business_identity", "email"),
        ("client", "name"),
        ("client", "billing_address_line1"),
        ("client", "billing_city_state_zip"),
        ("job", "archetype"),
        ("job", "title"),
        ("invoice", "invoice_number"),
        ("invoice", "invoice_date"),
        ("invoice", "payment_terms"),
        ("invoice", "currency"),
    )
    _require(facts, required_paths)
    archetype = str(_get(facts, "job", "archetype"))
    if archetype not in SUPPORTED_ARCHETYPES:
        raise ValueError(f"unsupported invoice archetype: {archetype}")
    if archetype not in IMPLEMENTED_ARCHETYPES:
        raise ValueError(f"invoice archetype not implemented in A2 first version: {archetype}")
    if str(_get(facts, "invoice", "currency")) != "USD":
        raise ValueError("A2 first version supports USD invoices only")
    line_items = facts.get("line_items")
    if not isinstance(line_items, list) or not line_items:
        raise ValueError("invoice facts require at least one line item")
    for index, item in enumerate(line_items, start=1):
        if not isinstance(item, Mapping):
            raise ValueError(f"line_items[{index}] must be an object")
        _require(
            item,
            (
                ("item_number",),
                ("description",),
                ("quantity",),
                ("unit_price",),
                ("line_type",),
            ),
        )


def select_template_profile(facts: Mapping[str, Any]) -> dict[str, Any]:
    """Select the deterministic template profile for supported archetypes."""

    validate_invoice_facts(facts)
    archetype = str(_get(facts, "job", "archetype"))
    profile = deepcopy(TEMPLATE_PROFILES[archetype])
    profile["field_map"] = _field_map_for_profile(profile)
    return profile


def _line_amount(item: Mapping[str, Any]) -> Decimal:
    quantity = _decimal(item.get("quantity"))
    unit_price = _decimal(item.get("unit_price"))
    discount = _decimal(item.get("discount"))
    amount = quantity * unit_price - discount
    if str(item.get("line_type") or "").lower() == "credit" and amount > 0:
        amount = -amount
    return amount


def _build_line_items(line_items: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], Decimal]:
    built: list[dict[str, Any]] = []
    subtotal = Decimal("0")
    running_total = Decimal("0")
    for item in line_items:
        amount = _line_amount(item)
        subtotal += amount
        running_total += amount
        built.append(
            {
                "item_number": int(item["item_number"]),
                "description": str(item["description"]),
                "period_start": item.get("period_start"),
                "period_end": item.get("period_end"),
                "quantity": _money(item.get("quantity")),
                "unit": item.get("unit"),
                "unit_price": _money(item.get("unit_price")),
                "discount": _money(item.get("discount")),
                "line_type": str(item.get("line_type")),
                "equipment_name": item.get("equipment_name"),
                "line_amount": _money(amount),
                "running_total_after_line": _money(running_total),
            }
        )
    return built, subtotal


def _render_policy(facts: Mapping[str, Any]) -> dict[str, bool]:
    policy = facts.get("render_policy") if isinstance(facts.get("render_policy"), Mapping) else {}
    return {
        "client_facing": bool(policy.get("client_facing", True)),
        "include_payment_instructions": bool(policy.get("include_payment_instructions", True)),
        "include_internal_reconciliation_notes": bool(
            policy.get("include_internal_reconciliation_notes", False)
        ),
        "requires_visual_review": bool(policy.get("requires_visual_review", True)),
        "send_ready": False,
    }


def build_system_invoice_model(facts: Mapping[str, Any]) -> dict[str, Any]:
    """Build the structured invoice model consumed by render/send rails."""

    profile = select_template_profile(facts)
    line_items, subtotal = _build_line_items(list(facts["line_items"]))
    invoice = facts["invoice"]
    tax_rate = _decimal(invoice.get("tax_rate"))
    sales_tax = subtotal * tax_rate
    deposit_received = _decimal(invoice.get("deposit_received"))
    prior_balance = _decimal(invoice.get("prior_balance"))
    payments_or_credits = _decimal(invoice.get("payments_or_credits"))
    total_due = prior_balance + subtotal + sales_tax - deposit_received - payments_or_credits
    render_policy = _render_policy(facts)

    return {
        "schema_version": SCHEMA_VERSION,
        "invoice_request_id": facts["invoice_request_id"],
        "source_type": facts["source_type"],
        "template_profile": profile,
        "field_bindings": {
            "header": {
                "invoice_title": "Invoice",
                "invoice_number": invoice["invoice_number"],
                "invoice_date": invoice["invoice_date"],
                "event_or_job": facts["job"]["title"],
                "venue_address_line1": facts["job"].get("venue_address_line1"),
                "venue_city_state": facts["job"].get("venue_city_state"),
            },
            "issuer": {
                "business_identity_display": facts["business_identity"]["display_name"],
                "legal_or_payable_name": facts["business_identity"]["legal_or_payable_name"],
                "business_address_line1": facts["business_identity"]["address_line1"],
                "business_city_state_zip": facts["business_identity"]["city_state_zip"],
                "business_phone": facts["business_identity"]["phone"],
                "business_email": facts["business_identity"]["email"],
            },
            "bill_to": {
                "bill_to_name": facts["client"]["name"],
                "bill_to_address_line1": facts["client"]["billing_address_line1"],
                "bill_to_city_state": facts["client"]["billing_city_state_zip"],
                "bill_to_contact_name_role": _contact_name_role(facts["client"]),
                "bill_to_contact_email": facts["client"].get("contact_email"),
                "bill_to_phone": facts["client"].get("phone"),
            },
            "terms": {
                "payment_terms": invoice["payment_terms"],
                "currency": invoice["currency"],
            },
            "line_items": line_items,
            "totals": {
                "prior_balance": _money(prior_balance),
                "payments_or_credits": _money(payments_or_credits),
                "current_charges": _money(subtotal),
                "subtotal": _money(subtotal),
                "tax_rate": _money(tax_rate),
                "sales_tax": _money(sales_tax),
                "deposit_received": _money(deposit_received),
                "total_due": _money(total_due),
                "balance_due": _money(total_due),
            },
            "payment_instructions": {
                "include_in_client_facing_output": render_policy["include_payment_instructions"],
                "requires_review": True,
            },
            "status": {
                "review_status": "SUPERVISOR_VERIFY_REQUIRED",
                "send_ready": False,
            },
            "internal_notes": {
                "included_in_client_facing_output": render_policy[
                    "include_internal_reconciliation_notes"
                ],
                "notes": facts["job"].get("notes") if not render_policy["client_facing"] else None,
            },
        },
        "render_policy": render_policy,
        "render_dependency": dict(RENDER_DEPENDENCY),
        "artifact_registration": {
            "working_workbook_path": None,
            "working_pdf_path": None,
            "artifact_pdf_path": None,
            "workbook_sha256": None,
            "pdf_sha256": None,
            "page_count": 0,
            "render_mode": None,
            "review_status": "SUPERVISOR_VERIFY_REQUIRED",
            "send_ready": False,
        },
        "safety": {
            "email_send_performed": False,
            "square_send_performed": False,
            "workbook_written": False,
            "pdf_rendered": False,
            "ledger_payment_posted": False,
            "send_hold_modified": False,
        },
    }


def _contact_name_role(client: Mapping[str, Any]) -> str | None:
    name = str(client.get("contact_name") or "").strip()
    role = str(client.get("contact_role") or "").strip()
    if name and role:
        return f"{name}, {role}"
    return name or role or None


__all__ = [
    "IMPLEMENTED_ARCHETYPES",
    "RENDER_DEPENDENCY",
    "SCHEMA_VERSION",
    "SUPPORTED_ARCHETYPES",
    "TEMPLATE_PROFILES",
    "build_system_invoice_model",
    "select_template_profile",
    "stable_json",
    "validate_invoice_facts",
]
