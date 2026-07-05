"""Auto-fire invoicing scheduler.

This module decides whether a client invoice should be finalized, sent, or
prepared for operator verification. It does not send by itself: callers inject a
sender adapter, and SEND_HOLD/proof policy is checked before any send adapter is
called.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _period_before(day: date) -> str:
    year = day.year
    month = day.month - 1
    if month == 0:
        year -= 1
        month = 12
    return f"{year:04d}-{month:02d}"


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _policy(model: Mapping[str, Any]) -> dict[str, Any]:
    raw = model.get("send_policy") if isinstance(model.get("send_policy"), Mapping) else {}
    return dict(raw)


def _policy_due(today: date, policy: Mapping[str, Any]) -> bool:
    cadence = _clean(policy.get("cadence")).lower() or "monthly"
    if cadence != "monthly":
        return False
    trigger = _clean(policy.get("trigger")).lower() or "first_of_month"
    if trigger == "first_of_month":
        return today.day == 1
    if trigger in {"day_of_month", "monthly_day"}:
        try:
            return today.day == int(policy.get("day"))
        except (TypeError, ValueError):
            return False
    try:
        return today.day == int(trigger)
    except ValueError:
        return False


def _invoice_ready(invoice: Mapping[str, Any] | None) -> bool:
    if not invoice:
        return False
    if invoice.get("invoice_ready") is True:
        return True
    return bool(invoice.get("line_items"))


def _load_invoice(invoice_store: Any, client_slug: str, period: str) -> dict[str, Any] | None:
    if hasattr(invoice_store, "load_invoice"):
        invoice = invoice_store.load_invoice(client_slug, period)
    elif hasattr(invoice_store, "load_current_invoice"):
        invoice = invoice_store.load_current_invoice(client_slug, period)
    else:
        invoice = None
    return dict(invoice) if isinstance(invoice, Mapping) else None


def _finalize_invoice(invoice_store: Any, client_slug: str, period: str, invoice: dict[str, Any]) -> dict[str, Any]:
    if hasattr(invoice_store, "finalize_invoice"):
        finalized = invoice_store.finalize_invoice(client_slug, period, invoice)
        return dict(finalized) if isinstance(finalized, Mapping) else dict(invoice)
    finalized = dict(invoice)
    finalized["finalized"] = True
    return finalized


class AutoFireStateStore:
    """Small state store for tests/dev; records last sent period by client."""

    def __init__(self) -> None:
        self._last_sent_period: dict[str, str] = {}
        self._receipts: dict[tuple[str, str], str] = {}

    def last_sent_period(self, client_slug: str) -> str | None:
        return self._last_sent_period.get(client_slug)

    def record_sent(self, client_slug: str, period: str, *, receipt_ref: str = "") -> None:
        self._last_sent_period[client_slug] = period
        self._receipts[(client_slug, period)] = receipt_ref


class SQLiteAutoFireStateStore:
    """Explicit-path SQLite dedup store; no default production location is chosen here."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS invoice_auto_fire_state (
                    client_slug        TEXT PRIMARY KEY,
                    last_sent_period   TEXT NOT NULL,
                    send_receipt_ref   TEXT NOT NULL,
                    updated_at_utc_iso TEXT NOT NULL
                )
                """
            )
        finally:
            conn.close()

    def last_sent_period(self, client_slug: str) -> str | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT last_sent_period FROM invoice_auto_fire_state WHERE client_slug = ?",
                (client_slug,),
            ).fetchone()
            return row["last_sent_period"] if row else None
        finally:
            conn.close()

    def record_sent(self, client_slug: str, period: str, *, receipt_ref: str = "") -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO invoice_auto_fire_state
                    (client_slug, last_sent_period, send_receipt_ref, updated_at_utc_iso)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(client_slug) DO UPDATE SET
                    last_sent_period = excluded.last_sent_period,
                    send_receipt_ref = excluded.send_receipt_ref,
                    updated_at_utc_iso = excluded.updated_at_utc_iso
                """,
                (client_slug, period, receipt_ref, _utc_now_iso()),
            )
        finally:
            conn.close()


def _prepare(
    *,
    sender: Any,
    client_slug: str,
    period: str,
    invoice: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    if hasattr(sender, "prepare_for_operator_verify"):
        result = sender.prepare_for_operator_verify(
            client_slug=client_slug,
            period=period,
            invoice=invoice,
            reason=reason,
        )
    else:
        result = {"ok": False, "error": "prepare_for_operator_verify_unavailable"}
    return dict(result) if isinstance(result, Mapping) else {"ok": bool(result)}


def _send(
    *,
    sender: Any,
    client_slug: str,
    period: str,
    invoice: dict[str, Any],
    channel: str,
) -> dict[str, Any]:
    if not hasattr(sender, "send_invoice"):
        return {"ok": False, "error": "send_invoice_unavailable"}
    result = sender.send_invoice(
        client_slug=client_slug,
        period=period,
        invoice=invoice,
        channel=channel,
    )
    return dict(result) if isinstance(result, Mapping) else {"ok": bool(result)}


def _process_client(
    *,
    client_slug: str,
    period: str,
    model: Mapping[str, Any],
    invoice_store: Any,
    sender: Any,
    state_store: Any,
    send_hold_active: bool,
    source: str,
) -> dict[str, Any]:
    if state_store.last_sent_period(client_slug) == period:
        return {"client_slug": client_slug, "period": period, "status": "already_sent", "source": source}
    invoice = _load_invoice(invoice_store, client_slug, period)
    if not _invoice_ready(invoice):
        return {"client_slug": client_slug, "period": period, "status": "invoice_not_ready", "source": source}
    finalized = _finalize_invoice(invoice_store, client_slug, period, invoice)
    policy = _policy(model)
    channel = _clean(policy.get("channel")) or "email"
    if send_hold_active:
        prepared = _prepare(
            sender=sender,
            client_slug=client_slug,
            period=period,
            invoice=finalized,
            reason="send_hold_active",
        )
        return {
            "client_slug": client_slug,
            "period": period,
            "status": "send_hold_blocked",
            "reason": "send_hold_active",
            "prepared": prepared,
            "source": source,
        }
    if policy.get("proven") is not True:
        prepared = _prepare(
            sender=sender,
            client_slug=client_slug,
            period=period,
            invoice=finalized,
            reason="send_policy_unproven",
        )
        return {
            "client_slug": client_slug,
            "period": period,
            "status": "prepared_for_operator_verify",
            "reason": "send_policy_unproven",
            "prepared": prepared,
            "source": source,
        }
    sent = _send(
        sender=sender,
        client_slug=client_slug,
        period=period,
        invoice=finalized,
        channel=channel,
    )
    if not sent.get("ok"):
        return {
            "client_slug": client_slug,
            "period": period,
            "status": "send_failed",
            "send_result": sent,
            "source": source,
        }
    receipt = _clean(sent.get("send_receipt") or sent.get("receipt_ref"))
    state_store.record_sent(client_slug, period, receipt_ref=receipt)
    return {
        "client_slug": client_slug,
        "period": period,
        "status": "sent",
        "send_result": sent,
        "source": source,
    }


def run_auto_fire(
    *,
    today: date,
    client_models: Mapping[str, Mapping[str, Any]],
    invoice_store: Any,
    sender: Any,
    state_store: Any,
    send_hold_active: bool,
) -> dict[str, Any]:
    period = _period_before(today)
    due_clients = [
        (client_slug, model)
        for client_slug, model in client_models.items()
        if _policy_due(today, _policy(model))
    ]
    if not due_clients:
        return {"status": "not_trigger_day", "period": period, "actions": []}
    actions = [
        _process_client(
            client_slug=client_slug,
            period=period,
            model=model,
            invoice_store=invoice_store,
            sender=sender,
            state_store=state_store,
            send_hold_active=send_hold_active,
            source="auto_fire",
        )
        for client_slug, model in due_clients
    ]
    return {"status": "checked", "period": period, "actions": actions}


def send_invoice_now(
    client_slug: str,
    *,
    period: str,
    client_models: Mapping[str, Mapping[str, Any]],
    invoice_store: Any,
    sender: Any,
    state_store: Any,
    send_hold_active: bool,
) -> dict[str, Any]:
    model = client_models.get(client_slug)
    if not isinstance(model, Mapping):
        return {"client_slug": client_slug, "period": period, "status": "unknown_client"}
    return _process_client(
        client_slug=client_slug,
        period=period,
        model=model,
        invoice_store=invoice_store,
        sender=sender,
        state_store=state_store,
        send_hold_active=send_hold_active,
        source="on_demand",
    )


__all__ = [
    "AutoFireStateStore",
    "SQLiteAutoFireStateStore",
    "run_auto_fire",
    "send_invoice_now",
]
