"""Month-bounded receivables read model.

This module is read-only. It never sends, pays, posts, closes, or mutates a
ledger. It summarizes current Gig-to-Cash expected receivable records plus
explicit canonical month facts into one packet-safe source for money answers.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ar_gig_to_cash_serialization import from_json
from ar_gig_to_cash_store import DEFAULT_DB_PATH as DEFAULT_G2C_DB_PATH


SCHEMA_VERSION = "receivables_month_bounded_v1"
READ_MODEL_ID = "receivables_month_bounded"
READ_MODEL_FILENAME = "receivables_month_bounded.json"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_OUTPUT_PATH = DEFAULT_EXPORT_ROOT / READ_MODEL_FILENAME


class ReadModelWriteConflict(RuntimeError):
    """The output changed after the caller measured its expected version."""


DEFAULT_CANONICAL_RECEIVABLE_MONTH_FACTS: tuple[dict[str, Any], ...] = (
    {
        "client_ref": "live_arts_md",
        "client_display_name": "Live Arts MD",
        "month": "2026-06",
        "currency_iso": "USD",
        "invoiced_minor_units": 100000,
        "paid_minor_units": 100000,
        "open_minor_units": 0,
        "amount_evidence_minor_units": [90000, 10000, 100000, 0],
        "invoiced_derived": False,
        "needs_reconcile": False,
        "payment_status": "settled",
        "notes": [
            "Operator-confirmed 2026-07-17: $900 invoice 2026-1001 and $100 June rental invoice are paid; $1,000 issued, $1,000 paid, $0 open."
        ],
        "source_ref": "operator_graded_fact:live_arts_md:2026-07-17:telegram_msg_1781:zero_current_balance",
    },
    {
        "client_ref": "st_annes",
        "client_display_name": "St. Anne's",
        "month": "2026-04",
        "currency_iso": "USD",
        "invoiced_minor_units": 62500,
        "paid_minor_units": 62500,
        "open_minor_units": 0,
        "amount_evidence_minor_units": [62500],
        "needs_reconcile": False,
        "payment_status": "settled",
        "notes": ["April share of St. Anne's Apr+May $1,250 paid total; settled months do not resurface as owed."],
        "source_ref": "canonical_business_fact:st_annes:2026-04:apr_may_paid",
    },
    {
        "client_ref": "st_annes",
        "client_display_name": "St. Anne's",
        "month": "2026-05",
        "currency_iso": "USD",
        "invoiced_minor_units": 62500,
        "paid_minor_units": 62500,
        "open_minor_units": 0,
        "amount_evidence_minor_units": [62500],
        "needs_reconcile": False,
        "payment_status": "settled",
        "notes": ["May share of St. Anne's Apr+May $1,250 paid total; settled months do not resurface as owed."],
        "source_ref": "canonical_business_fact:st_annes:2026-05:apr_may_paid",
    },
    {
        "client_ref": "capital_hilton",
        "client_display_name": "Capital Hilton",
        "month": "2026-06",
        "currency_iso": "USD",
        "amount_known": False,
        "needs_reconcile": True,
        "payment_status": "open_amount_unknown",
        "notes": ["check_unverified: check expected per operator; amount not yet evidenced."],
        "source_ref": "canonical_business_fact:capital_hilton:2026-06:check_unverified",
    },
    {
        # Task 133 (operator correction 2026-07-07: "st annes is not settled... we are not
        # all paid up"): current St. Anne's work is owed but NOT YET INVOICED (draft held for
        # a copy fix), a third tier distinct from open-invoiced and settled. No amount claim
        # until the finalized invoice (134) evidences one -- 121's validator applies.
        "client_ref": "st_annes",
        "client_display_name": "St. Anne's",
        "month": "2026-07",
        "currency_iso": "USD",
        "amount_known": False,
        "needs_reconcile": False,
        "payment_status": "expected_uninvoiced",
        "notes": ["Current invoice ready to send once the copy is fixed; not yet invoiced, not settled."],
        "source_ref": "canonical_business_fact:st_annes_current_open:2026-07:expected_uninvoiced",
    },
)


_CLIENT_ALIAS_TO_REF = {
    "capital_hilton": "capital_hilton",
    "capitol_hilton": "capital_hilton",
    "hilton": "capital_hilton",
    "live_arts": "live_arts_md",
    "live_arts_md": "live_arts_md",
    "live_arts_maryland": "live_arts_md",
    "arts_alive_md": "live_arts_md",
    "st_anne": "st_annes",
    "st_annes": "st_annes",
    "st_anne_s": "st_annes",
    "st_annes_s": "st_annes",
    "saint_anne": "st_annes",
    "saint_annes": "st_annes",
}
_CLIENT_DISPLAY_NAMES = {
    "capital_hilton": "Capital Hilton",
    "live_arts_md": "Live Arts MD",
    "st_annes": "St. Anne's",
}
_VALID_STATUSES = {
    "cancelled",
    "expected_uninvoiced",
    "entered_for_payment_not_paid",
    "needs_reconcile",
    "open_amount_unknown",
    "open_not_paid",
    "settled",
    "unknown",
    "written_off",
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").casefold()).strip("_")


def _client_ref(value: Any) -> str:
    slug = _slug(value)
    return _CLIENT_ALIAS_TO_REF.get(slug, slug)


def _client_display(client_ref: str, explicit: Any = "") -> str:
    text = str(explicit or "").strip()
    if text:
        return text
    return _CLIENT_DISPLAY_NAMES.get(client_ref, client_ref.replace("_", " ").title())


def _month_from_date(value: Any) -> str:
    text = str(value or "").strip()
    match = re.match(r"^(\d{4}-\d{2})", text)
    return match.group(1) if match else ""


def _coerce_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if re.fullmatch(r"-?\d+", text):
            return int(text)
    return None


def _notes(value: Any) -> list[str]:
    if isinstance(value, str):
        clean = value.strip()
        return [clean] if clean else []
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


_AMOUNT_FIELDS = ("invoiced_minor_units", "paid_minor_units", "open_minor_units")
_DOLLAR_RE = re.compile(r"\$([0-9][0-9,]*(?:\.[0-9]{1,2})?)")
_SOURCE_TOKEN_AMOUNT_RE = re.compile(r"(?<![0-9])([0-9]{1,6})(?:_(?:open|paid|owed|due|invoiced|settled))")


def _minor_units_from_decimal_text(value: str) -> int | None:
    text = value.replace(",", "").strip()
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", text):
        return None
    whole, _, cents = text.partition(".")
    return int(whole) * 100 + int((cents + "00")[:2])


def _amount_evidence_minor_units(fact: Mapping[str, Any]) -> set[int]:
    amounts: set[int] = set()
    explicit = fact.get("amount_evidence_minor_units")
    if isinstance(explicit, Iterable) and not isinstance(explicit, (str, bytes, Mapping)):
        for value in explicit:
            coerced = _coerce_int(value)
            if coerced is not None:
                amounts.add(coerced)
    evidence_texts: list[str] = [
        str(fact.get("source_ref") or fact.get("source") or ""),
        str(fact.get("source_evidence") or fact.get("evidence") or ""),
    ]
    evidence_texts.extend(_notes(fact.get("notes") or fact.get("note")))
    for text in evidence_texts:
        for match in _DOLLAR_RE.finditer(text):
            parsed = _minor_units_from_decimal_text(match.group(1))
            if parsed is not None:
                amounts.add(parsed)
        for match in _SOURCE_TOKEN_AMOUNT_RE.finditer(text):
            amounts.add(int(match.group(1)) * 100)
    return amounts


def _validate_canonical_fact_amounts(fact: Mapping[str, Any]) -> list[str]:
    source_ref = _source_ref(fact, "canonical_business_fact")
    evidence_amounts = _amount_evidence_minor_units(fact)
    errors: list[str] = []
    paid = _coerce_int(fact.get("paid_minor_units"))
    open_amount = _coerce_int(fact.get("open_minor_units"))
    for field in _AMOUNT_FIELDS:
        value = _coerce_int(fact.get(field))
        if value is None or value == 0:
            continue
        if field == "invoiced_minor_units" and bool(fact.get("invoiced_derived")):
            if paid is not None and open_amount is not None and paid + open_amount == value:
                continue
        if value not in evidence_amounts:
            errors.append(f"{source_ref} {field}={value} has no matching amount in cited source evidence")
    return errors


def validate_canonical_receivable_month_facts(facts: Iterable[Mapping[str, Any]]) -> None:
    errors: list[str] = []
    for fact in facts:
        errors.extend(_validate_canonical_fact_amounts(fact))
    if errors:
        raise ValueError("unevidenced amount in receivables_month_bounded facts: " + "; ".join(errors))


def _source_ref(value: Mapping[str, Any], fallback: str) -> str:
    return str(value.get("source_ref") or value.get("source") or fallback).strip()


def _empty_bucket(client_ref: str, month: str, currency: str, display_name: str = "") -> dict[str, Any]:
    return {
        "client_ref": client_ref,
        "client_display_name": _client_display(client_ref, display_name),
        "month": month,
        "currency_iso": currency,
        "invoiced_minor_units": 0,
        "paid_minor_units": 0,
        "open_minor_units": 0,
        "amount_known": True,
        "amount_source_count": 0,
        "g2c_open_state_count": 0,
        "g2c_entered_for_payment_count": 0,
        "g2c_disputed_state_count": 0,
        "g2c_satisfied_state_count": 0,
        "g2c_written_off_state_count": 0,
        "g2c_cancelled_state_count": 0,
        "invoiced_derived": False,
        "needs_reconcile": False,
        "payment_status": "unknown",
        "settled_past_no_compound": False,
        "notes": [],
        "source_refs": [],
        "source_kinds": set(),
        "receivable_ids": [],
    }


def _bucket_for(
    buckets: dict[tuple[str, str, str], dict[str, Any]],
    *,
    client_ref: str,
    month: str,
    currency: str,
    display_name: str = "",
) -> dict[str, Any]:
    key = (client_ref, month, currency)
    if key not in buckets:
        buckets[key] = _empty_bucket(client_ref, month, currency, display_name)
    elif display_name and not buckets[key].get("client_display_name"):
        buckets[key]["client_display_name"] = _client_display(client_ref, display_name)
    return buckets[key]


def _append_unique(items: list[Any], value: Any) -> None:
    if value not in items:
        items.append(value)


def _iter_current_receivables(db_path: str | Path) -> list[Any]:
    path = Path(db_path)
    if not path.exists():
        return []
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT canonical_json
                FROM expected_receivable_records
                WHERE receivable_version_id NOT IN (
                    SELECT supersedes_receivable_version_id
                    FROM expected_receivable_records
                    WHERE supersedes_receivable_version_id IS NOT NULL
                )
                ORDER BY ingestion_seq ASC
                """
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []

    records: list[Any] = []
    for row in rows:
        try:
            records.append(from_json(row["canonical_json"]))
        except Exception:
            continue
    return records


def _resolve_g2c_payment_status(bucket: dict[str, Any]) -> None:
    """Resolve mixed G2C lifecycle states without record-order dependence."""
    disputed = int(bucket.get("g2c_disputed_state_count") or 0)
    plain_open = int(bucket.get("g2c_open_state_count") or 0)
    entered = int(bucket.get("g2c_entered_for_payment_count") or 0)
    satisfied = int(bucket.get("g2c_satisfied_state_count") or 0)
    written_off = int(bucket.get("g2c_written_off_state_count") or 0)
    cancelled = int(bucket.get("g2c_cancelled_state_count") or 0)
    terminal_conflict = bool(satisfied and (written_off or cancelled)) or bool(
        written_off and cancelled
    )
    if disputed or terminal_conflict:
        status = "needs_reconcile"
        bucket["needs_reconcile"] = True
    elif plain_open:
        status = "open_not_paid"
    elif entered:
        status = "entered_for_payment_not_paid"
    elif satisfied:
        status = "settled"
    elif written_off:
        status = "written_off"
    elif cancelled:
        status = "cancelled"
    else:
        status = "unknown"
    bucket["payment_status"] = status
    bucket["settled_past_no_compound"] = status == "settled"


def _merge_g2c_receivable(buckets: dict[tuple[str, str, str], dict[str, Any]], receivable: Any) -> None:
    month = _month_from_date(getattr(receivable, "due_date_iso", ""))
    if not month:
        return
    client_ref = _client_ref(getattr(receivable, "counterparty_ref", ""))
    currency = str(getattr(receivable, "currency_iso", "") or "USD").upper()
    amount = int(getattr(receivable, "expected_minor_units", 0) or 0)
    if amount <= 0:
        return
    bucket = _bucket_for(buckets, client_ref=client_ref, month=month, currency=currency)
    bucket["amount_known"] = True
    bucket["amount_source_count"] = int(bucket.get("amount_source_count") or 0) + 1
    state = str(getattr(receivable, "lifecycle_state", "") or "open").strip().lower()
    bucket["invoiced_minor_units"] += amount
    if state == "entered_for_payment":
        bucket["g2c_entered_for_payment_count"] = (
            int(bucket.get("g2c_entered_for_payment_count") or 0) + 1
        )
        bucket["open_minor_units"] += amount
        _append_unique(
            bucket["notes"],
            "Payer confirmed the invoice was entered for payment; funds have not been received.",
        )
    elif state == "satisfied":
        bucket["g2c_satisfied_state_count"] = (
            int(bucket.get("g2c_satisfied_state_count") or 0) + 1
        )
        bucket["paid_minor_units"] += amount
    elif state == "written_off":
        bucket["g2c_written_off_state_count"] = (
            int(bucket.get("g2c_written_off_state_count") or 0) + 1
        )
        _append_unique(bucket["notes"], "written_off receivable excluded from open owed amount.")
    elif state == "cancelled":
        bucket["g2c_cancelled_state_count"] = (
            int(bucket.get("g2c_cancelled_state_count") or 0) + 1
        )
        _append_unique(bucket["notes"], "cancelled receivable excluded from open owed amount.")
    else:
        bucket["open_minor_units"] += amount
        if state == "disputed":
            bucket["g2c_disputed_state_count"] = (
                int(bucket.get("g2c_disputed_state_count") or 0) + 1
            )
        else:
            bucket["g2c_open_state_count"] = (
                int(bucket.get("g2c_open_state_count") or 0) + 1
            )
    _resolve_g2c_payment_status(bucket)
    bucket["source_kinds"].add("g2c_expected_receivable")
    _append_unique(bucket["source_refs"], str(getattr(receivable, "source_ref", "") or "g2c:expected_receivable"))
    _append_unique(bucket["receivable_ids"], str(getattr(receivable, "receivable_id", "") or ""))


def _iter_fact_rows(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    rows: list[Mapping[str, Any]] = []
    for key in ("receivable_month_facts", "month_facts", "rows", "facts"):
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, Mapping))
    return rows


def load_canonical_receivable_month_facts(facts_path: str | Path | None = None) -> list[Mapping[str, Any]]:
    if facts_path is None:
        return [dict(row) for row in DEFAULT_CANONICAL_RECEIVABLE_MONTH_FACTS]
    path = Path(facts_path)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return _iter_fact_rows(payload)


def _merge_canonical_fact(
    buckets: dict[tuple[str, str, str], dict[str, Any]],
    fact: Mapping[str, Any],
) -> None:
    client_ref = _client_ref(fact.get("client_ref") or fact.get("client") or fact.get("client_display_name"))
    month = str(fact.get("month") or _month_from_date(fact.get("due_date_iso") or fact.get("as_of") or "")).strip()
    if not client_ref or not month:
        return
    currency = str(fact.get("currency_iso") or "USD").upper()
    bucket = _bucket_for(
        buckets,
        client_ref=client_ref,
        month=month,
        currency=currency,
        display_name=str(fact.get("client_display_name") or fact.get("display_name") or ""),
    )
    fact_amounts: dict[str, int] = {}
    for key in ("invoiced_minor_units", "paid_minor_units", "open_minor_units"):
        value = _coerce_int(fact.get(key))
        if value is not None:
            fact_amounts[key] = value
            bucket[key] = value
    if fact_amounts:
        bucket["amount_known"] = True
        bucket["amount_source_count"] = int(bucket.get("amount_source_count") or 0) + 1
    elif fact.get("amount_known") is False and int(bucket.get("amount_source_count") or 0) == 0:
        bucket["amount_known"] = False
    status = str(fact.get("payment_status") or fact.get("status") or "").strip().lower()
    if status == "open_amount_unknown" and bucket.get("amount_known"):
        status = "open_not_paid" if int(bucket.get("open_minor_units") or 0) > 0 else "needs_reconcile"
    if status in _VALID_STATUSES:
        bucket["payment_status"] = status
    if "invoiced_derived" in fact:
        bucket["invoiced_derived"] = bool(fact.get("invoiced_derived"))
    if "needs_reconcile" in fact:
        bucket["needs_reconcile"] = bool(fact.get("needs_reconcile"))
    if bucket["payment_status"] == "needs_reconcile":
        bucket["needs_reconcile"] = True
    if bucket["payment_status"] == "settled":
        bucket["open_minor_units"] = 0
        if bucket["paid_minor_units"] < bucket["invoiced_minor_units"]:
            bucket["paid_minor_units"] = bucket["invoiced_minor_units"]
        bucket["needs_reconcile"] = False
        bucket["settled_past_no_compound"] = True
    for note in _notes(fact.get("notes") or fact.get("note")):
        _append_unique(bucket["notes"], note)
    source_ref = _source_ref(fact, f"canonical_business_fact:{client_ref}:{month}")
    source_kind = "operator_graded_fact" if source_ref.startswith("operator_graded_fact:") else "canonical_business_fact"
    bucket["source_kinds"].add(source_kind)
    _append_unique(bucket["source_refs"], source_ref)


def _finalize_bucket(bucket: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(bucket)
    status = str(row.get("payment_status") or "unknown")
    amount_known = bool(row.get("amount_known", True))
    invoiced = int(row.get("invoiced_minor_units") or 0)
    paid = int(row.get("paid_minor_units") or 0)
    open_amount = int(row.get("open_minor_units") or 0)
    if not amount_known:
        # Task 133: expected_uninvoiced is a DELIBERATE third tier (owed, not yet invoiced),
        # not the same as "we don't know the open amount of an invoiced item" -- don't let it
        # get swallowed into open_amount_unknown, and it isn't "needing reconcile" either
        # (that's an invoiced-and-unpaid concept; this is pre-invoice).
        if status != "expected_uninvoiced":
            status = "open_amount_unknown"
            row["needs_reconcile"] = True
            if not row.get("notes"):
                row["notes"] = ["check expected per operator; amount not yet evidenced."]
        invoiced_value: int | None = None
        paid_value: int | None = None
        open_value: int | None = None
    else:
        invoiced_value = invoiced
        paid_value = paid
        open_value = open_amount
    if status == "settled":
        open_amount = 0
        paid = max(paid, invoiced)
        row["needs_reconcile"] = False
        row["settled_past_no_compound"] = True
        open_value = open_amount
        paid_value = paid
    elif status == "unknown":
        if open_amount > 0:
            status = "needs_reconcile" if row.get("needs_reconcile") else "open_not_paid"
        elif invoiced > 0 and paid >= invoiced:
            status = "settled"
            row["settled_past_no_compound"] = True
        else:
            status = "unknown"
    if status in ("open_amount_unknown", "expected_uninvoiced"):
        amount_known = False
        invoiced_value = None
        paid_value = None
        open_value = None
    row["payment_status"] = status
    row["amount_known"] = amount_known
    row["invoiced_minor_units"] = invoiced_value
    row["paid_minor_units"] = paid_value
    row["open_minor_units"] = open_value
    row["invoiced_derived"] = bool(row.get("invoiced_derived"))
    row.pop("amount_source_count", None)
    row.pop("g2c_open_state_count", None)
    row.pop("g2c_entered_for_payment_count", None)
    row.pop("g2c_disputed_state_count", None)
    row.pop("g2c_satisfied_state_count", None)
    row.pop("g2c_written_off_state_count", None)
    row.pop("g2c_cancelled_state_count", None)
    row["source_kinds"] = sorted(str(item) for item in row.get("source_kinds", set()) if str(item))
    row["source_refs"] = sorted(dict.fromkeys(str(item) for item in row.get("source_refs", []) if str(item)))
    row["notes"] = list(dict.fromkeys(str(item) for item in row.get("notes", []) if str(item)))
    row["receivable_ids"] = sorted(dict.fromkeys(str(item) for item in row.get("receivable_ids", []) if str(item)))
    row["current_truth"] = True
    row["structured_fact"] = True
    return row


def _summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    open_by_client: dict[str, int] = {}
    paid_by_client: dict[str, int] = {}
    invoiced_by_client: dict[str, int] = {}
    needs_reconcile: list[str] = []
    unknown_amounts: list[str] = []
    for row in rows:
        client_ref = str(row.get("client_ref") or "")
        amount_known = row.get("amount_known") is not False
        if amount_known:
            open_by_client[client_ref] = open_by_client.get(client_ref, 0) + int(row.get("open_minor_units") or 0)
            paid_by_client[client_ref] = paid_by_client.get(client_ref, 0) + int(row.get("paid_minor_units") or 0)
            invoiced_by_client[client_ref] = invoiced_by_client.get(client_ref, 0) + int(row.get("invoiced_minor_units") or 0)
        if row.get("needs_reconcile"):
            needs_reconcile.append(f"{client_ref}:{row.get('month')}")
        if not amount_known:
            unknown_amounts.append(f"{client_ref}:{row.get('month')}")
    return {
        "row_count": len(rows),
        "client_count": len({str(row.get("client_ref") or "") for row in rows}),
        "month_count": len({str(row.get("month") or "") for row in rows}),
        "open_minor_units_by_client": dict(sorted(open_by_client.items())),
        "paid_minor_units_by_client": dict(sorted(paid_by_client.items())),
        "invoiced_minor_units_by_client": dict(sorted(invoiced_by_client.items())),
        "needs_reconcile_keys": sorted(needs_reconcile),
        "unknown_amount_keys": sorted(unknown_amounts),
    }


def _recurrence_rule_derived_facts(
    buckets: Mapping[tuple[str, str, str], Mapping[str, Any]],
    *,
    rule_db_path: str | Path,
    today: Any = None,
) -> list[dict[str, Any]]:
    """Task 136a: the expected-uninvoiced tier consumes operator-stated recurrence rules.
    No rule = no derivation -- never guess schedules. When a rule's scheduled day has passed
    for the current month AND no send evidence already covers that client-month (no G2C/
    canonical row already exists for it), derive an expected_uninvoiced fact citing the rule
    as the source. Hand-landed facts (a manually-entered canonical fact) become
    CORROBORATION once they exist, not the source of truth -- this only fills a gap, it
    never overrides an existing bucket."""
    if not Path(rule_db_path).exists():
        # No rule has ever been stated -- skip entirely, zero behavior change, zero
        # connection overhead.
        return []
    from recurrence_rule_store import RecurrenceRuleStore

    current = today or datetime.now(timezone.utc).date()
    month_key = f"{current.year:04d}-{current.month:02d}"
    derived: list[dict[str, Any]] = []
    with RecurrenceRuleStore(rule_db_path) as store:
        for rule in store.active_rules(event_type="invoice_send"):
            if rule.schedule_kind != "monthly_day":
                continue
            if current.day < rule.schedule_day:
                continue  # scheduled day hasn't arrived yet this month
            if any(key[0] == rule.client_ref and key[1] == month_key for key in buckets):
                continue  # send evidence (G2C or a hand-landed canonical fact) already covers this period
            derived.append(
                {
                    "client_ref": rule.client_ref,
                    "client_display_name": _CLIENT_DISPLAY_NAMES.get(rule.client_ref, ""),
                    "month": month_key,
                    "currency_iso": "USD",
                    "amount_known": False,
                    "needs_reconcile": False,
                    "payment_status": "expected_uninvoiced",
                    "notes": [
                        f"Derived from recurrence rule: invoice_send monthly on day "
                        f"{rule.schedule_day} ({rule.rule_version_id})."
                    ],
                    "source_ref": f"recurrence_rule:{rule.rule_version_id}",
                }
            )
    return derived


def build_receivables_month_bounded(
    *,
    g2c_db_path: str | Path = DEFAULT_G2C_DB_PATH,
    facts_path: str | Path | None = None,
    generated_at: str | None = None,
    recurrence_rule_db_path: str | Path | None = None,
) -> dict[str, Any]:
    buckets: dict[tuple[str, str, str], dict[str, Any]] = {}
    g2c_path = Path(g2c_db_path)
    g2c_records = _iter_current_receivables(g2c_path)
    for receivable in g2c_records:
        _merge_g2c_receivable(buckets, receivable)
    canonical_facts = load_canonical_receivable_month_facts(facts_path)
    validate_canonical_receivable_month_facts(canonical_facts)
    for fact in canonical_facts:
        _merge_canonical_fact(buckets, fact)
    from recurrence_rule_store import DEFAULT_DB_PATH as DEFAULT_RULE_DB_PATH

    derivation_today = None
    if generated_at:
        try:
            derivation_today = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).date()
        except ValueError:
            derivation_today = None
    rule_derived_facts = _recurrence_rule_derived_facts(
        buckets,
        rule_db_path=recurrence_rule_db_path or DEFAULT_RULE_DB_PATH,
        today=derivation_today,
    )
    for fact in rule_derived_facts:
        _merge_canonical_fact(buckets, fact)
    rows = [
        _finalize_bucket(bucket)
        for _key, bucket in sorted(buckets.items(), key=lambda item: item[0])
    ]
    source_refs = [source for row in rows for source in row["source_refs"]]
    if g2c_path.exists():
        source_refs.append(f"gig_to_cash:{g2c_path.as_posix()}")
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or _utc_now(),
        "source_refs": sorted(dict.fromkeys(source_refs)),
        "source_status": {
            "g2c_db_path": g2c_path.as_posix(),
            "g2c_db_present": g2c_path.exists(),
            "g2c_current_receivable_count": len(g2c_records),
            "canonical_month_fact_count": len(canonical_facts),
            "facts_path": str(facts_path or ""),
            "recurrence_rule_derived_fact_count": len(rule_derived_facts),
        },
        "rows": rows,
        "summary": _summary(rows),
        "authority_boundary": {
            "send_performed": False,
            "email_send_performed": False,
            "money_movement_performed": False,
            "ledger_mutation_performed": False,
            "ledger_posting_performed": False,
            "paid_marking_performed": False,
            "bank_access_performed": False,
            "browser_access_performed": False,
        },
        "doctrine": {
            "money_answers_source": "receivables_month_bounded rows only; do not infer totals from narrative.",
            "settle_past_no_compound": "Rows with payment_status=settled force open_minor_units=0 and do not resurface as owed.",
        },
    }


def export_receivables_month_bounded(
    *,
    g2c_db_path: str | Path = DEFAULT_G2C_DB_PATH,
    facts_path: str | Path | None = None,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    generated_at: str | None = None,
    recurrence_rule_db_path: str | Path | None = None,
    expected_output_sha256: str | None = None,
) -> dict[str, Any]:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    # Every exporter, including the ordinary CLI path, takes the same stable
    # sidecar lock *before* reading sources.  The lock therefore survives output
    # inode replacement and prevents a waiting exporter from publishing a
    # payload it built before another exporter completed.
    with lock_path.open("a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        if expected_output_sha256 is not None:
            if not path.exists():
                raise ReadModelWriteConflict("receivables_read_model_missing")
            observed = hashlib.sha256(path.read_bytes()).hexdigest()
            if observed != expected_output_sha256:
                raise ReadModelWriteConflict("receivables_read_model_changed")
        payload = build_receivables_month_bounded(
            g2c_db_path=g2c_db_path,
            facts_path=facts_path,
            generated_at=generated_at,
            recurrence_rule_db_path=recurrence_rule_db_path,
        )
        encoded = stable_json(payload).encode("utf-8")
        temporary = path.with_name(
            f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        with temporary.open("xb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export month-bounded receivables read model.")
    parser.add_argument("--g2c-db", default=DEFAULT_G2C_DB_PATH)
    parser.add_argument("--facts", default="")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--output", default="")
    parser.add_argument("--generated-at", default="")
    parser.add_argument("--recurrence-rule-db", default="")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    args = parser.parse_args(argv)

    output_path = Path(args.output) if args.output else Path(args.export_root) / READ_MODEL_FILENAME
    payload = export_receivables_month_bounded(
        g2c_db_path=args.g2c_db,
        facts_path=args.facts or None,
        output_path=output_path,
        generated_at=args.generated_at or None,
        recurrence_rule_db_path=args.recurrence_rule_db or None,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        summary = payload["summary"]
        print(
            "Receivables month bounded: "
            f"{summary['row_count']} rows, "
            f"needs_reconcile={len(summary['needs_reconcile_keys'])}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
