"""Open AR aging: every open row in the ONE money source gets a due date, days past due,
a bucket, and one next action.

Read-only. Reads generated/read_models/receivables_month_bounded.json (the single money
source, doctrine in money_truth.py) plus an operator-maintained terms file. Never sends,
never posts, never marks paid. The read model id deliberately avoids the tokens the
morning brief scans for money (receivable, invoice, finance, billing, payment) so the
brief does not double-count rows; the brief carries one explicit aging line instead.
"""

from __future__ import annotations

import calendar
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "open_ar_aging_v0"
READ_MODEL_ID = "open_ar_aging"
DEFAULT_MONEY_SOURCE_PATH = Path("generated/read_models/receivables_month_bounded.json")
DEFAULT_TERMS_PATH = Path("config/receivable_terms.v1.json")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
UNKNOWN_AMOUNT_STATUSES = frozenset({"open_amount_unknown", "amount_unknown", "unknown_amount", "expected_uninvoiced"})
FOLLOW_UP_AFTER_DAYS = 7
BUCKETS = ("not_due", "current", "30", "60", "90_plus")
NEXT_ACTIONS = ("request_or_confirm_po", "reconcile_amount", "follow_up_draft", "watch", "wait")

AUTHORITY_BOUNDARY = {
    "send_performed": False,
    "email_send_performed": False,
    "money_movement_performed": False,
    "ledger_mutation_performed": False,
    "ledger_posting_performed": False,
    "paid_marking_performed": False,
    "bank_access_performed": False,
    "browser_access_performed": False,
    "telegram_send_performed": False,
    "external_model_called": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_terms(path: str | Path = DEFAULT_TERMS_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    default_days = int(payload.get("default_terms_days", 30))
    clients = payload.get("clients") if isinstance(payload.get("clients"), Mapping) else {}
    normalized: dict[str, dict[str, Any]] = {}
    for ref, cfg in clients.items():
        cfg = cfg if isinstance(cfg, Mapping) else {}
        normalized[str(ref)] = {
            "terms_days": int(cfg.get("terms_days", default_days)),
            "purchase_order_required": bool(cfg.get("purchase_order_required", False)),
        }
    return {"default_terms_days": default_days, "clients": normalized}


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _month_end(month: str) -> date:
    year, mon = (int(part) for part in month.split("-")[:2])
    return date(year, mon, calendar.monthrange(year, mon)[1])


def _add_days(day: date, days: int) -> date:
    return date.fromordinal(day.toordinal() + days)


def _is_open(row: Mapping[str, Any]) -> bool:
    status = str(row.get("payment_status") or "").strip().lower()
    if status == "settled" or bool(row.get("settled_past_no_compound")):
        return False
    open_units = row.get("open_minor_units")
    if isinstance(open_units, int) and not isinstance(open_units, bool) and open_units > 0:
        return True
    if status in UNKNOWN_AMOUNT_STATUSES:
        return True
    return bool(row.get("needs_reconcile"))


def _bucket(days_past_due: int) -> str:
    if days_past_due <= 0:
        return "not_due"
    if days_past_due < 30:
        return "current"
    if days_past_due < 60:
        return "30"
    if days_past_due < 90:
        return "60"
    return "90_plus"


def _next_action(*, amount_known: bool, needs_reconcile: bool, po_required: bool, days_past_due: int) -> str:
    if po_required and (not amount_known or needs_reconcile):
        return "request_or_confirm_po"
    if not amount_known:
        return "reconcile_amount"
    if days_past_due >= FOLLOW_UP_AFTER_DAYS:
        return "follow_up_draft"
    if days_past_due > 0:
        return "watch"
    return "wait"


def _priority(bucket: str, action: str) -> int:
    if bucket == "90_plus" or action == "request_or_confirm_po":
        return 1
    if bucket in {"30", "60"} or action in {"follow_up_draft", "reconcile_amount"}:
        return 2
    return 3


def build_open_ar_aging(
    *,
    money_source_path: str | Path = DEFAULT_MONEY_SOURCE_PATH,
    terms_path: str | Path = DEFAULT_TERMS_PATH,
    today: date | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    today_value = today or date.today()
    terms = load_terms(terms_path)
    source_path = Path(money_source_path)
    source = _load_json(source_path)
    source_rows = [row for row in (source or {}).get("rows", ()) if isinstance(row, Mapping)] if isinstance(source, Mapping) else []
    source_generated_at = str((source or {}).get("generated_at") or "") if isinstance(source, Mapping) else ""

    rows: list[dict[str, Any]] = []
    for row in source_rows:
        if not _is_open(row):
            continue
        client_ref = str(row.get("client_ref") or "").strip()
        month = str(row.get("month") or "").strip()
        if not client_ref or not month:
            continue
        client_terms = terms["clients"].get(client_ref, {"terms_days": terms["default_terms_days"], "purchase_order_required": False})
        try:
            due = _add_days(_month_end(month), int(client_terms["terms_days"]))
        except (ValueError, TypeError):
            continue
        days_past_due = max(0, (today_value - due).days)
        amount_known = bool(row.get("amount_known")) and isinstance(row.get("open_minor_units"), int)
        needs_reconcile = bool(row.get("needs_reconcile"))
        action = _next_action(
            amount_known=amount_known,
            needs_reconcile=needs_reconcile,
            po_required=bool(client_terms["purchase_order_required"]),
            days_past_due=days_past_due,
        )
        bucket = _bucket(days_past_due)
        rows.append(
            {
                "client_ref": client_ref,
                "client_display_name": str(row.get("client_display_name") or client_ref),
                "month": month,
                "currency_iso": str(row.get("currency_iso") or "USD"),
                "amount_known": amount_known,
                "open_minor_units": row.get("open_minor_units") if amount_known else None,
                "payment_status": str(row.get("payment_status") or ""),
                "needs_reconcile": needs_reconcile,
                "terms_days": int(client_terms["terms_days"]),
                "purchase_order_required": bool(client_terms["purchase_order_required"]),
                "due_date_iso": due.isoformat(),
                "days_past_due": days_past_due,
                "bucket": bucket,
                "next_action": action,
                "attention_priority": _priority(bucket, action),
                "source_refs": list(row.get("source_refs") or []),
            }
        )
    rows.sort(key=lambda r: (r["attention_priority"], -r["days_past_due"], r["client_ref"], r["month"]))

    by_bucket = {bucket: 0 for bucket in BUCKETS}
    by_action = {action: 0 for action in NEXT_ACTIONS}
    for row in rows:
        by_bucket[row["bucket"]] += 1
        by_action[row["next_action"]] += 1
    known_total = sum(int(r["open_minor_units"]) for r in rows if r["amount_known"])
    summary = {
        "open_row_count": len(rows),
        "open_minor_units_total_known": known_total,
        "unknown_amount_row_count": sum(1 for r in rows if not r["amount_known"]),
        "rows_by_bucket": by_bucket,
        "rows_by_next_action": by_action,
        "oldest_days_past_due": max((r["days_past_due"] for r in rows), default=0),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or _utc_now(),
        "today": today_value.isoformat(),
        "money_source_path": source_path.as_posix(),
        "money_source_present": source is not None,
        "money_source_generated_at": source_generated_at,
        "terms_path": Path(terms_path).as_posix(),
        "rows": rows,
        "summary": summary,
        "source_refs": [f"money_source:{source_path.as_posix()}", f"terms:{Path(terms_path).as_posix()}"],
        "doctrine": {
            "money_answers_source": "receivables_month_bounded rows only; this model adds time, never amounts.",
            "unknown_amounts": "Rows without amount_known carry no amount here either.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {"read_only": True, "rows_evaluated": len(source_rows), "rows_open": len(rows)},
    }


_ACTION_WORDS = {
    "request_or_confirm_po": "request or confirm PO",
    "reconcile_amount": "reconcile amount",
    "follow_up_draft": "follow-up draft",
    "watch": "watch",
    "wait": "not due",
}


def _dollars(minor_units: int, currency: str) -> str:
    prefix = "$" if currency.upper() == "USD" else f"{currency.upper()} "
    whole, cents = divmod(int(minor_units), 100)
    return f"{prefix}{whole:,}" if cents == 0 else f"{prefix}{whole:,}.{cents:02d}"


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    lines = ["# Open AR Aging", "", f"As of {payload.get('today')}; money source {payload.get('money_source_generated_at') or 'missing'}.", ""]
    rows = payload.get("rows") or []
    if not rows:
        lines.append("Nothing open. Every row in the money source is settled or not yet due.")
    for row in rows:
        month = datetime.strptime(row["month"], "%Y-%m").strftime("%b %Y")
        amount = _dollars(row["open_minor_units"], row["currency_iso"]) if row["amount_known"] else "amount unknown"
        past_due = f"{row['days_past_due']} days past due" if row["days_past_due"] > 0 else f"due {row['due_date_iso']}"
        lines.append(f"- {row['client_display_name']} · {month} · {amount} · {past_due} · {_ACTION_WORDS[row['next_action']]}")
    summary = payload.get("summary") or {}
    actions = {k: v for k, v in (summary.get("rows_by_next_action") or {}).items() if v}
    lines.append("")
    lines.append("Next actions: " + (", ".join(f"{_ACTION_WORDS[k]} ({v})" for k, v in actions.items()) if actions else "none") + ".")
    lines.append("Boundary: read-only; no sends, no ledger writes, no amounts beyond the money source.")
    return "\n".join(lines) + "\n"


def export_open_ar_aging(
    *,
    money_source_path: str | Path = DEFAULT_MONEY_SOURCE_PATH,
    terms_path: str | Path = DEFAULT_TERMS_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    today: date | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_open_ar_aging(money_source_path=money_source_path, terms_path=terms_path, today=today, generated_at=generated_at)
    root = Path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"{READ_MODEL_ID}.json"
    operator_path = root / f"{READ_MODEL_ID}_OPERATOR.md"
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return {
        "json_path": str(json_path),
        "operator_path": str(operator_path),
        "open_row_count": payload["summary"]["open_row_count"],
        "oldest_days_past_due": payload["summary"]["oldest_days_past_due"],
        "next_actions": payload["summary"]["rows_by_next_action"],
    }
