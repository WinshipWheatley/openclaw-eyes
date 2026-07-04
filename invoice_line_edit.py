"""Deterministic invoice line-item edits for the invoice cockpit.

This module edits only the cockpit's in-memory invoice data. It does not write
to source workbooks, send email, update ledgers, or infer paid status.
"""

from __future__ import annotations

import copy
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


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


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _infer_year(invoice_data: dict[str, Any]) -> int:
    for item in invoice_data.get("line_items") or []:
        date = str((item or {}).get("service_date") or "")
        if re.match(r"\d{4}-\d{2}-\d{2}", date):
            return int(date[:4])
    for key in ("service_date", "issue_date"):
        date = str(invoice_data.get(key) or "")
        if re.match(r"\d{4}-\d{2}-\d{2}", date):
            return int(date[:4])
    return datetime.now().year


def _extract_date(text: str, invoice_data: dict[str, Any]) -> str | None:
    iso = re.search(r"\b(20[0-9]{2}-[0-9]{1,2}-[0-9]{1,2})\b", text)
    if iso:
        dt = datetime.fromisoformat(iso.group(1))
        return dt.strftime("%Y-%m-%d")
    month_names = "|".join(sorted(MONTHS, key=len, reverse=True))
    m = re.search(
        rf"\b({month_names})\.?\s+([0-9]{{1,2}})(?:st|nd|rd|th)?(?:,\s*(20[0-9]{{2}}))?\b",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    month = MONTHS[m.group(1).lower().rstrip(".")]
    day = int(m.group(2))
    year = int(m.group(3)) if m.group(3) else _infer_year(invoice_data)
    return datetime(year, month, day).strftime("%Y-%m-%d")


def _amounts_are_minor_units(invoice_data: dict[str, Any]) -> bool:
    units = str(invoice_data.get("amount_units") or "").lower()
    if units in {"cent", "cents", "minor", "minor_unit", "minor_units"}:
        return True
    if units in {"dollar", "dollars", "major", "major_units"}:
        return False
    items = list(invoice_data.get("line_items") or [])
    amounts = [item.get("amount") for item in items if isinstance(item, dict)]
    return bool(amounts) and all(
        isinstance(amount, int) and not isinstance(amount, bool) and abs(amount) >= 1000
        for amount in amounts
    )


def _money_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().replace("$", "").replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _extract_money(text: str) -> Decimal | None:
    match = re.search(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", text)
    if not match:
        match = re.search(r"\b(?:at|for|to)\s+([0-9][0-9,]*(?:\.[0-9]{1,2})?)\b", text, re.IGNORECASE)
    return _money_decimal(match.group(1)) if match else None


def _coerce_amount(amount: Decimal, *, minor_units: bool) -> int | float:
    if minor_units:
        return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    as_float = float(amount)
    return int(as_float) if as_float.is_integer() else as_float


def _line_amount_as_total(value: Any, *, minor_units: bool) -> int | float:
    amount = _money_decimal(value)
    if amount is None:
        return 0
    if minor_units:
        return int(amount)
    as_float = float(amount)
    return int(as_float) if as_float.is_integer() else as_float


def _strip_articles(text: str) -> str:
    text = _clean(text)
    text = re.sub(r"^(?:a|an|the)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+(?:line|item)$", "", text, flags=re.IGNORECASE)
    return _clean(text)


def _find_line_index(items: list[dict[str, Any]], *, target_date: str | None = None, target_text: str = "") -> int | None:
    if target_date:
        for index, item in enumerate(items):
            if str(item.get("service_date") or "") == target_date:
                return index
    normalized_target = _norm(_strip_articles(target_text))
    if normalized_target:
        for index, item in enumerate(items):
            desc = _norm(item.get("description"))
            if normalized_target and (normalized_target in desc or desc in normalized_target):
                return index
    return 0 if len(items) == 1 and not target_date and not normalized_target else None


def _metadata(status: str, *, operation: str = "none", note: str = "", changed: bool = False) -> dict[str, Any]:
    return {
        "status": status,
        "operation": operation,
        "changed": changed,
        "note": note,
    }


def _with_unparsed(invoice_data: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(invoice_data)
    result["invoice_edit"] = _metadata(
        "unparsed",
        note="Couldn't parse that invoice edit. Please name the line, date, and amount.",
    )
    return result


def _recalculate(invoice_data: dict[str, Any], *, minor_units: bool) -> dict[str, Any]:
    items = [dict(item) for item in invoice_data.get("line_items") or [] if isinstance(item, dict)]
    total = sum(_line_amount_as_total(item.get("amount"), minor_units=minor_units) for item in items)
    deposit_paid = _line_amount_as_total(invoice_data.get("deposit_paid", 0), minor_units=minor_units)
    invoice_data["line_items"] = items
    invoice_data["amount_total"] = total
    invoice_data["balance_due"] = max(total - deposit_paid, 0)
    if items:
        invoice_data["project_desc"] = "; ".join(_clean(item.get("description")) for item in items)
        invoice_data["service_date"] = str(items[0].get("service_date") or invoice_data.get("service_date") or "")
    return invoice_data


def _apply_add(invoice_data: dict[str, Any], instruction: str, *, minor_units: bool) -> dict[str, Any] | None:
    date = _extract_date(instruction, invoice_data)
    amount = _extract_money(instruction)
    if not date or amount is None:
        return None
    before_date = instruction.split(date, 1)[0]
    desc = re.sub(r"^.*?\badd\b", "", before_date, flags=re.IGNORECASE)
    desc = re.sub(r"\b(?:on|for)\s*$", "", desc, flags=re.IGNORECASE)
    desc = _strip_articles(desc)
    if not desc:
        return None
    result = copy.deepcopy(invoice_data)
    items = [dict(item) for item in result.get("line_items") or [] if isinstance(item, dict)]
    items.append(
        {
            "description": desc,
            "service_date": date,
            "amount": _coerce_amount(amount, minor_units=minor_units),
        }
    )
    result["line_items"] = items
    result = _recalculate(result, minor_units=minor_units)
    result["invoice_edit"] = _metadata("applied", operation="add", changed=True)
    return result


def _apply_remove(invoice_data: dict[str, Any], instruction: str, *, minor_units: bool) -> dict[str, Any] | None:
    result = copy.deepcopy(invoice_data)
    items = [dict(item) for item in result.get("line_items") or [] if isinstance(item, dict)]
    if not items:
        return None
    date = _extract_date(instruction, invoice_data)
    target_text = re.sub(r"^.*?\bremove\b", "", instruction, flags=re.IGNORECASE)
    index = _find_line_index(items, target_date=date, target_text=target_text)
    if index is None:
        return None
    del items[index]
    result["line_items"] = items
    result = _recalculate(result, minor_units=minor_units)
    result["invoice_edit"] = _metadata("applied", operation="remove", changed=True)
    return result


def _change_target_text(instruction: str) -> str:
    target = re.sub(r"^.*?\bchange\b", "", instruction, flags=re.IGNORECASE)
    target = re.split(r"\b(?:to|amount to|price to|date to|description to)\b|\$", target, maxsplit=1, flags=re.IGNORECASE)[0]
    return _strip_articles(target)


def _apply_change(invoice_data: dict[str, Any], instruction: str, *, minor_units: bool) -> dict[str, Any] | None:
    result = copy.deepcopy(invoice_data)
    items = [dict(item) for item in result.get("line_items") or [] if isinstance(item, dict)]
    if not items:
        return None
    target_date = _extract_date(instruction, invoice_data)
    target_text = _change_target_text(instruction)
    index = _find_line_index(items, target_date=target_date, target_text=target_text)
    if index is None:
        return None
    amount = _extract_money(instruction)
    if amount is not None:
        items[index]["amount"] = _coerce_amount(amount, minor_units=minor_units)
    elif re.search(r"\bdate\s+to\b", instruction, re.IGNORECASE):
        new_date = _extract_date(instruction.split("date", 1)[-1], invoice_data)
        if not new_date:
            return None
        items[index]["service_date"] = new_date
    elif re.search(r"\bdescription\s+to\b", instruction, re.IGNORECASE):
        new_desc = re.split(r"\bdescription\s+to\b", instruction, flags=re.IGNORECASE, maxsplit=1)[-1]
        new_desc = _strip_articles(new_desc)
        if not new_desc:
            return None
        items[index]["description"] = new_desc
    else:
        return None
    result["line_items"] = items
    result = _recalculate(result, minor_units=minor_units)
    result["invoice_edit"] = _metadata("applied", operation="change", changed=True)
    return result


def apply_invoice_edit(invoice_data: dict[str, Any], instruction: str) -> dict[str, Any]:
    """Return edited invoice data, or unchanged invoice facts with an honest parse note."""
    source = copy.deepcopy(invoice_data or {})
    text = _clean(instruction)
    if not text:
        return _with_unparsed(source)
    minor_units = _amounts_are_minor_units(source)
    lowered = text.lower()
    if re.search(r"\badd\b", lowered):
        return _apply_add(source, text, minor_units=minor_units) or _with_unparsed(source)
    if re.search(r"\bremove\b", lowered):
        return _apply_remove(source, text, minor_units=minor_units) or _with_unparsed(source)
    if re.search(r"\b(change|update|make)\b", lowered):
        return _apply_change(source, text, minor_units=minor_units) or _with_unparsed(source)
    return _with_unparsed(source)


__all__ = ["apply_invoice_edit"]
