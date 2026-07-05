"""Gig capture flow for operator-owned calendar and invoice data.

This module turns messages like "Dane asked me to do X on Y" into a bounded
calendar event plus a current-month invoice line item. It performs no sends,
payments, ledger posts, Gmail drafts, or workbook writes.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Mapping

import interpreter_lm
from contacts_registry import ContactsRegistry
from fleet_temporal_anchor import temporal_anchor_text
from invoice_line_edit import apply_invoice_edit


DEFAULT_CLIENT_MODELS: dict[str, dict[str, Any]] = {
    "live-arts-md": {"display_name": "Live Arts MD", "rate": 500},
    "st-annes": {"display_name": "St. Anne's", "rate": 125},
    "capital-hilton": {"display_name": "Capital Hilton", "rate": 400},
}

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

WEEKDAYS = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "weds": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


@dataclass(frozen=True)
class CapturedGigIntent:
    contact_hint: str
    description: str
    date_text: str
    message_amount: Decimal | None = None


class MemoryInvoiceStore:
    """Tiny test/dev invoice store; production wiring can inject a real store."""

    def __init__(self, invoices: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        self.invoices = {key: copy.deepcopy(dict(value)) for key, value in (invoices or {}).items()}
        self.saved: list[tuple[str, dict[str, Any]]] = []

    def load_current_invoice(self, client_slug: str, service_date: str) -> dict[str, Any]:
        if client_slug in self.invoices:
            return copy.deepcopy(self.invoices[client_slug])
        return {
            "client_name": _client_display_name(client_slug, DEFAULT_CLIENT_MODELS),
            "issue_date": service_date[:7] + "-01",
            "deposit_paid": 0,
            "amount_total": 0,
            "balance_due": 0,
            "line_items": [],
            "amount_units": "dollars",
        }

    def save_current_invoice(self, client_slug: str, invoice_data: dict[str, Any]) -> None:
        saved = copy.deepcopy(invoice_data)
        self.invoices[client_slug] = saved
        self.saved.append((client_slug, saved))


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _money_decimal(value: str) -> Decimal | None:
    text = str(value or "").strip().replace("$", "").replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def _public_money(value: Decimal | int | float) -> int | float:
    amount = Decimal(str(value))
    as_float = float(amount)
    return int(as_float) if as_float.is_integer() else as_float


def _extract_message_amount(message: str) -> Decimal | None:
    match = re.search(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", message)
    return _money_decimal(match.group(1)) if match else None


def interpret_capture_gig(message: str) -> CapturedGigIntent:
    """Deterministic fallback for the narrow capture phrase."""
    text = _clean(message)
    match = re.match(
        r"(?P<who>[A-Za-z][A-Za-z.' -]{0,80}?)\s+asked\s+me\s+to\s+do\s+(?P<body>.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError("Could not parse gig capture phrase.")
    who = _clean(match.group("who"))
    body = _clean(match.group("body"))
    date_match = re.search(
        r"\bon\s+(?P<date>(?:20\d{2}-\d{1,2}-\d{1,2})|(?:[A-Za-z]+\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*20\d{2})?)|today|tomorrow|yesterday)\b",
        body,
        flags=re.IGNORECASE,
    )
    if not date_match:
        raise ValueError("Could not parse gig date.")
    description = _clean(body[: date_match.start()])
    description = re.sub(r"\s+for\s+\$\s*[0-9][0-9,]*(?:\.[0-9]{1,2})?\s*$", "", description)
    if not description:
        raise ValueError("Could not parse gig description.")
    return CapturedGigIntent(
        contact_hint=who,
        description=description,
        date_text=_clean(date_match.group("date")),
        message_amount=_extract_message_amount(text),
    )


def _intent_from_interpreter_result(raw: Any, message: str) -> CapturedGigIntent | None:
    if isinstance(raw, CapturedGigIntent):
        return raw
    if isinstance(raw, interpreter_lm.InterpretResult):
        if not raw.is_high_confidence_capture_gig():
            return None
        return CapturedGigIntent(
            contact_hint=raw.contact,
            description=raw.description,
            date_text=raw.date,
            message_amount=_extract_message_amount(message),
        )
    if not isinstance(raw, Mapping):
        return None
    data = dict(raw)
    if {"contact_hint", "description", "date_text"} <= set(data):
        return CapturedGigIntent(
            contact_hint=str(data.get("contact_hint") or ""),
            description=str(data.get("description") or ""),
            date_text=str(data.get("date_text") or ""),
            message_amount=data.get("message_amount") or _extract_message_amount(message),
        )
    intent_label = str(data.get("intent") or "").strip().lower().replace("-", "_").replace(" ", "_")
    intent = (
        interpreter_lm.CAPTURE_GIG_INTENT
        if intent_label in {interpreter_lm.CAPTURE_GIG_INTENT, "gig_capture", "add_gig", "calendar_gig"}
        else intent_label
    )
    result = interpreter_lm.InterpretResult(
        route=str(data.get("route") or interpreter_lm.ROUTE_WORKFLOW).upper(),
        confidence=float(data.get("confidence") or 0.0),
        reason=str(data.get("reason") or ""),
        intent=intent,
        contact=str(data.get("contact") or data.get("contact_hint") or data.get("who") or ""),
        description=str(data.get("description") or data.get("gig_description") or data.get("service") or ""),
        date=str(data.get("date") or data.get("date_text") or data.get("service_date") or data.get("when") or ""),
    )
    if not result.is_high_confidence_capture_gig():
        return None
    return CapturedGigIntent(
        contact_hint=result.contact,
        description=result.description,
        date_text=result.date,
        message_amount=_extract_message_amount(message),
    )


def _interpret_capture_gig_primary(
    message: str,
    *,
    interpreter: Callable[[str], Any] | None = None,
) -> CapturedGigIntent:
    lm_interpreter = interpreter
    if lm_interpreter is None and interpreter_lm._interpreter_enabled():
        lm_interpreter = interpreter_lm.interpret_operator_message
    if lm_interpreter is not None:
        try:
            intent = _intent_from_interpreter_result(lm_interpreter(message), message)
            if intent is not None:
                return intent
        except Exception:
            pass
    return interpret_capture_gig(message)


def _resolve_date(date_text: str, *, now: datetime | None = None) -> str:
    anchor = (now or datetime.now()).date()
    text = _clean(date_text).lower().replace("nxt", "next").rstrip(".")
    if text == "today":
        return anchor.isoformat()
    if text == "tomorrow":
        return (anchor + timedelta(days=1)).isoformat()
    if text == "yesterday":
        return (anchor - timedelta(days=1)).isoformat()
    weekday_names = "|".join(sorted(WEEKDAYS, key=len, reverse=True))
    weekday = re.search(rf"\b(?:next|this)\s+({weekday_names})\b", text, flags=re.IGNORECASE)
    if weekday:
        target = WEEKDAYS[weekday.group(1).lower()]
        delta = (target - anchor.weekday()) % 7
        if delta == 0 or text.startswith("next "):
            delta = delta or 7
        return (anchor + timedelta(days=delta)).isoformat()
    iso = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    if iso:
        return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3))).isoformat()
    month_names = "|".join(sorted(MONTHS, key=len, reverse=True))
    match = re.search(
        rf"\b({month_names})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,\s*(20\d{{2}}))?\b",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        day_only = re.search(r"\b(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b", text)
        if day_only:
            day = int(day_only.group(1))
            year = anchor.year
            month = anchor.month
            resolved = date(year, month, day)
            if resolved < anchor:
                if month == 12:
                    resolved = date(year + 1, 1, day)
                else:
                    resolved = date(year, month + 1, day)
            return resolved.isoformat()
        raise ValueError("Could not resolve gig date.")
    month = MONTHS[match.group(1).lower().rstrip(".")]
    day = int(match.group(2))
    year = int(match.group(3)) if match.group(3) else anchor.year
    resolved = date(year, month, day)
    if match.group(3) is None and resolved < anchor:
        resolved = date(year + 1, month, day)
    return resolved.isoformat()


def _client_display_name(client_slug: str, client_models: Mapping[str, Mapping[str, Any]]) -> str:
    model = client_models.get(client_slug) or {}
    return _clean(model.get("display_name")) or " ".join(part.capitalize() for part in client_slug.split("-"))


def _client_rate(client_slug: str, client_models: Mapping[str, Mapping[str, Any]]) -> Decimal | None:
    model = client_models.get(client_slug) or {}
    value = model.get("rate", model.get("default_rate", model.get("invoice_rate")))
    return _money_decimal(str(value)) if value is not None else None


def _calendar_events_on(calendar_router: Any, service_date: str) -> list[dict[str, Any]]:
    if calendar_router is None:
        return []
    if hasattr(calendar_router, "events_on"):
        return [dict(item) for item in calendar_router.events_on(service_date)]
    if hasattr(calendar_router, "find_conflicts"):
        return [dict(item) for item in calendar_router.find_conflicts(service_date)]
    if hasattr(calendar_router, "check_date"):
        result = calendar_router.check_date(service_date)
        if isinstance(result, Mapping):
            return [dict(item) for item in result.get("events", result.get("conflicts", ())) or ()]
    return []


def _calendar_add_event(calendar_router: Any, event: dict[str, Any]) -> dict[str, Any]:
    if calendar_router is None:
        return {"ok": False, "error": "calendar_router_missing"}
    if hasattr(calendar_router, "add_event"):
        result = calendar_router.add_event(event)
    elif hasattr(calendar_router, "create_event"):
        result = calendar_router.create_event(event)
    else:
        return {"ok": False, "error": "calendar_add_event_unavailable"}
    return dict(result) if isinstance(result, Mapping) else {"ok": bool(result), "event": event}


def _save_invoice(invoice_store: Any, client_slug: str, service_date: str, invoice_data: dict[str, Any]) -> None:
    if hasattr(invoice_store, "save_current_invoice"):
        invoice_store.save_current_invoice(client_slug, invoice_data)
    elif hasattr(invoice_store, "save"):
        invoice_store.save(client_slug, service_date, invoice_data)


def _load_invoice(invoice_store: Any, client_slug: str, service_date: str, client_name: str) -> dict[str, Any]:
    if hasattr(invoice_store, "load_current_invoice"):
        return dict(invoice_store.load_current_invoice(client_slug, service_date))
    if hasattr(invoice_store, "load"):
        return dict(invoice_store.load(client_slug, service_date))
    return {
        "client_name": client_name,
        "issue_date": service_date[:7] + "-01",
        "deposit_paid": 0,
        "amount_total": 0,
        "balance_due": 0,
        "line_items": [],
        "amount_units": "dollars",
    }


def _authority_boundary() -> dict[str, bool]:
    return {
        "email_send_performed": False,
        "gmail_draft_created": False,
        "payment_performed": False,
        "ledger_posting_performed": False,
        "external_send_performed": False,
    }


def capture_gig(
    message: str,
    *,
    contacts_registry: ContactsRegistry | None = None,
    calendar_router: Any = None,
    invoice_store: Any = None,
    client_models: Mapping[str, Mapping[str, Any]] | None = None,
    interpreter: Callable[[str], CapturedGigIntent | Mapping[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    registry = contacts_registry or ContactsRegistry()
    models = client_models or DEFAULT_CLIENT_MODELS
    invoice_store = invoice_store or MemoryInvoiceStore()
    try:
        intent = _interpret_capture_gig_primary(message, interpreter=interpreter)
        service_date = _resolve_date(intent.date_text, now=now)
    except Exception as exc:
        return {
            "status": "needs_clarify",
            "reason": str(exc),
            "authority_boundary": _authority_boundary(),
        }

    contact = registry.get_contact(intent.contact_hint)
    if contact is None:
        return {
            "status": "needs_contact_clarify",
            "contact_hint": intent.contact_hint,
            "authority_boundary": _authority_boundary(),
        }
    client_options = tuple(contact.get("connected_client") or ())
    if len(client_options) != 1:
        return {
            "status": "needs_client_clarify",
            "contact": contact,
            "client_options": client_options,
            "parsed": {
                "description": intent.description,
                "service_date": service_date,
            },
            "authority_boundary": _authority_boundary(),
        }
    client_slug = client_options[0]
    client_name = _client_display_name(client_slug, models)
    rate = _client_rate(client_slug, models)
    if rate is None:
        return {
            "status": "needs_rate_config",
            "client_slug": client_slug,
            "contact": contact,
            "authority_boundary": _authority_boundary(),
        }

    event = {
        "title": f"{client_name} - {intent.description}",
        "date": service_date,
        "client_slug": client_slug,
        "description": intent.description,
        "source": "gig_capture",
    }
    if calendar_router is None:
        return {
            "status": "calendar_router_missing",
            "client_slug": client_slug,
            "service_date": service_date,
            "description": intent.description,
            "authority_boundary": _authority_boundary(),
        }
    conflicts = _calendar_events_on(calendar_router, service_date)
    if conflicts:
        calendar_result = {
            "status": "conflict",
            "existing_event": conflicts[0],
            "events": tuple(conflicts),
        }
    else:
        add_result = _calendar_add_event(calendar_router, event)
        calendar_result = {
            "status": "event_added" if add_result.get("ok") else "event_add_failed",
            "event": add_result.get("event") or event,
            "error": add_result.get("error"),
        }
        if calendar_result["status"] != "event_added":
            return {
                "status": "calendar_event_failed",
                "client_slug": client_slug,
                "service_date": service_date,
                "calendar": calendar_result,
                "authority_boundary": _authority_boundary(),
            }

    invoice_data = _load_invoice(invoice_store, client_slug, service_date, client_name)
    instruction = f"add {intent.description} on {service_date} at ${_public_money(rate)}"
    edited_invoice = apply_invoice_edit(invoice_data, instruction)
    edit_meta = edited_invoice.get("invoice_edit") if isinstance(edited_invoice, dict) else {}
    if not isinstance(edit_meta, Mapping) or edit_meta.get("status") != "applied":
        return {
            "status": "invoice_line_failed",
            "client_slug": client_slug,
            "calendar": calendar_result,
            "invoice_edit": edit_meta,
            "authority_boundary": _authority_boundary(),
        }
    _save_invoice(invoice_store, client_slug, service_date, edited_invoice)
    line_item = edited_invoice["line_items"][-1]
    calendar_phrase = "Calendar conflict surfaced" if calendar_result["status"] == "conflict" else "Calendar event added"
    confirmation = (
        f"{calendar_phrase} for {service_date}; invoice line added for "
        f"{client_name}: {intent.description} at ${_public_money(rate):g}."
    )
    ignored_message_amount = None
    if intent.message_amount is not None and intent.message_amount != rate:
        ignored_message_amount = _public_money(intent.message_amount)
    return {
        "status": "captured",
        "contact": contact,
        "client_slug": client_slug,
        "service_date": service_date,
        "description": intent.description,
        "rate": {
            "source": "client_model",
            "amount": _public_money(rate),
            "ignored_message_amount": ignored_message_amount,
        },
        "calendar": calendar_result,
        "invoice": {
            "status": "line_added",
            "line_item": line_item,
            "invoice_data": edited_invoice,
        },
        "temporal_anchor": temporal_anchor_text(now=now),
        "confirmation": confirmation,
        "authority_boundary": _authority_boundary(),
    }


__all__ = [
    "CapturedGigIntent",
    "MemoryInvoiceStore",
    "capture_gig",
    "interpret_capture_gig",
]
