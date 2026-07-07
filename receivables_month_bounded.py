"""Month-bounded receivables read model.

This module is read-only. It never sends, pays, posts, closes, or mutates a
ledger. It summarizes current Gig-to-Cash expected receivable records plus
explicit canonical month facts into one packet-safe source for money answers.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
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


DEFAULT_CANONICAL_RECEIVABLE_MONTH_FACTS: tuple[dict[str, Any], ...] = (
    {
        "client_ref": "live_arts_md",
        "client_display_name": "Live Arts MD",
        "month": "2026-06",
        "currency_iso": "USD",
        "invoiced_minor_units": 199500,
        "paid_minor_units": 90000,
        "open_minor_units": 109500,
        "needs_reconcile": True,
        "payment_status": "needs_reconcile",
        "notes": ["$900 paid; $1,095 remains open pending operator reconciliation."],
        "source_ref": "canonical_business_fact:live_arts_md:2026-06:1095_open_900_paid",
    },
    {
        "client_ref": "st_annes",
        "client_display_name": "St. Anne's",
        "month": "2026-04",
        "currency_iso": "USD",
        "invoiced_minor_units": 62500,
        "paid_minor_units": 62500,
        "open_minor_units": 0,
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
        "invoiced_minor_units": 200000,
        "paid_minor_units": 0,
        "open_minor_units": 200000,
        "needs_reconcile": True,
        "payment_status": "open_not_paid",
        "notes": ["check_unverified: Coupa/check evidence is not payment proof; keep open until reconciliation."],
        "source_ref": "canonical_business_fact:capital_hilton:2026-06:check_unverified",
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
    "needs_reconcile",
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
    state = str(getattr(receivable, "lifecycle_state", "") or "open").strip().lower()
    bucket["invoiced_minor_units"] += amount
    if state == "satisfied":
        bucket["paid_minor_units"] += amount
        bucket["settled_past_no_compound"] = True
        if bucket["payment_status"] == "unknown":
            bucket["payment_status"] = "settled"
    elif state == "written_off":
        bucket["payment_status"] = "written_off"
        _append_unique(bucket["notes"], "written_off receivable excluded from open owed amount.")
    elif state == "cancelled":
        bucket["payment_status"] = "cancelled"
        _append_unique(bucket["notes"], "cancelled receivable excluded from open owed amount.")
    else:
        bucket["open_minor_units"] += amount
        if state == "disputed":
            bucket["needs_reconcile"] = True
            bucket["payment_status"] = "needs_reconcile"
        elif bucket["payment_status"] == "unknown":
            bucket["payment_status"] = "open_not_paid"
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
    for key in ("invoiced_minor_units", "paid_minor_units", "open_minor_units"):
        value = _coerce_int(fact.get(key))
        if value is not None:
            bucket[key] = value
    status = str(fact.get("payment_status") or fact.get("status") or "").strip().lower()
    if status in _VALID_STATUSES:
        bucket["payment_status"] = status
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
    bucket["source_kinds"].add("canonical_business_fact")
    _append_unique(bucket["source_refs"], _source_ref(fact, f"canonical_business_fact:{client_ref}:{month}"))


def _finalize_bucket(bucket: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(bucket)
    status = str(row.get("payment_status") or "unknown")
    invoiced = int(row.get("invoiced_minor_units") or 0)
    paid = int(row.get("paid_minor_units") or 0)
    open_amount = int(row.get("open_minor_units") or 0)
    if status == "settled":
        open_amount = 0
        paid = max(paid, invoiced)
        row["needs_reconcile"] = False
        row["settled_past_no_compound"] = True
    elif status == "unknown":
        if open_amount > 0:
            status = "needs_reconcile" if row.get("needs_reconcile") else "open_not_paid"
        elif invoiced > 0 and paid >= invoiced:
            status = "settled"
            row["settled_past_no_compound"] = True
        else:
            status = "unknown"
    row["payment_status"] = status
    row["invoiced_minor_units"] = invoiced
    row["paid_minor_units"] = paid
    row["open_minor_units"] = open_amount
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
    for row in rows:
        client_ref = str(row.get("client_ref") or "")
        open_by_client[client_ref] = open_by_client.get(client_ref, 0) + int(row.get("open_minor_units") or 0)
        paid_by_client[client_ref] = paid_by_client.get(client_ref, 0) + int(row.get("paid_minor_units") or 0)
        invoiced_by_client[client_ref] = invoiced_by_client.get(client_ref, 0) + int(row.get("invoiced_minor_units") or 0)
        if row.get("needs_reconcile"):
            needs_reconcile.append(f"{client_ref}:{row.get('month')}")
    return {
        "row_count": len(rows),
        "client_count": len({str(row.get("client_ref") or "") for row in rows}),
        "month_count": len({str(row.get("month") or "") for row in rows}),
        "open_minor_units_by_client": dict(sorted(open_by_client.items())),
        "paid_minor_units_by_client": dict(sorted(paid_by_client.items())),
        "invoiced_minor_units_by_client": dict(sorted(invoiced_by_client.items())),
        "needs_reconcile_keys": sorted(needs_reconcile),
    }


def build_receivables_month_bounded(
    *,
    g2c_db_path: str | Path = DEFAULT_G2C_DB_PATH,
    facts_path: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    buckets: dict[tuple[str, str, str], dict[str, Any]] = {}
    g2c_path = Path(g2c_db_path)
    g2c_records = _iter_current_receivables(g2c_path)
    for receivable in g2c_records:
        _merge_g2c_receivable(buckets, receivable)
    canonical_facts = load_canonical_receivable_month_facts(facts_path)
    for fact in canonical_facts:
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
) -> dict[str, Any]:
    payload = build_receivables_month_bounded(
        g2c_db_path=g2c_db_path,
        facts_path=facts_path,
        generated_at=generated_at,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export month-bounded receivables read model.")
    parser.add_argument("--g2c-db", default=DEFAULT_G2C_DB_PATH)
    parser.add_argument("--facts", default="")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--output", default="")
    parser.add_argument("--generated-at", default="")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    args = parser.parse_args(argv)

    output_path = Path(args.output) if args.output else Path(args.export_root) / READ_MODEL_FILENAME
    payload = export_receivables_month_bounded(
        g2c_db_path=args.g2c_db,
        facts_path=args.facts or None,
        output_path=output_path,
        generated_at=args.generated_at or None,
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
