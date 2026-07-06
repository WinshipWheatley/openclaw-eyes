"""Paid-through settlement over the append-only Gig-to-Cash receivable store."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from ar_expected_receivable_record import ExpectedReceivableRecord, create_expected_receivable
from ar_gig_to_cash_store import GigToCashStore
from temporal_recurrence_registry import PaidUpState, client_ref_slug, paid_up_state


@dataclass(frozen=True)
class MarkPaidUpResult:
    client_ref: str
    paid_through: date
    settled_receivable_ids: tuple[str, ...]
    skipped_receivable_ids: tuple[str, ...]
    state: PaidUpState


class ClientPaidThroughStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE IF NOT EXISTS client_paid_through_versions ("
            "seq INTEGER PRIMARY KEY AUTOINCREMENT,"
            "client_ref TEXT NOT NULL,"
            "paid_through TEXT NOT NULL,"
            "source_ref TEXT NOT NULL,"
            "recorded_utc TEXT NOT NULL,"
            "UNIQUE(client_ref, paid_through, source_ref)"
            ")"
        )
        return conn

    def get_paid_through(self, client_ref: str) -> date | None:
        slug = client_ref_slug(client_ref)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT paid_through FROM client_paid_through_versions "
                "WHERE client_ref = ? ORDER BY paid_through DESC, seq DESC LIMIT 1",
                (slug,),
            ).fetchone()
        return date.fromisoformat(row["paid_through"]) if row else None

    def set_paid_through(self, client_ref: str, paid_through: date, *, source_ref: str) -> date:
        slug = client_ref_slug(client_ref)
        current = self.get_paid_through(slug)
        if current is not None and current >= paid_through:
            return current
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO client_paid_through_versions "
                "(client_ref, paid_through, source_ref, recorded_utc) VALUES (?, ?, ?, ?)",
                (
                    slug,
                    paid_through.isoformat(),
                    source_ref,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return paid_through


def _store_conn(store: GigToCashStore) -> sqlite3.Connection:
    conn = getattr(store, "_conn", None)
    if conn is None:
        raise ValueError("GigToCashStore must be open")
    return conn


def _date_from_iso(value: str) -> date:
    return datetime.fromisoformat(str(value)).date()


def _current_receivables_for_client(store: GigToCashStore, client_ref: str) -> tuple[ExpectedReceivableRecord, ...]:
    conn = _store_conn(store)
    rows = conn.execute(
        """
        SELECT receivable_id
        FROM expected_receivable_records
        WHERE receivable_id NOT IN (
            SELECT supersedes_receivable_version_id
            FROM expected_receivable_records
            WHERE supersedes_receivable_version_id IS NOT NULL
        )
        ORDER BY ingestion_seq ASC
        """
    ).fetchall()
    receivables: list[ExpectedReceivableRecord] = []
    slug = client_ref_slug(client_ref)
    for row in rows:
        current = store.get_current(ExpectedReceivableRecord, row["receivable_id"])
        if current is not None and client_ref_slug(current.counterparty_ref) == slug:
            receivables.append(current)
    return tuple(receivables)


def mark_paid_up(
    store: GigToCashStore,
    client_ref: str,
    *,
    as_of: date,
    paid_through_store: ClientPaidThroughStore,
    source_ref: str = "operator_paid_up",
) -> MarkPaidUpResult:
    slug = client_ref_slug(client_ref)
    settled: list[str] = []
    skipped: list[str] = []
    resolution_ref = f"paid_up:{slug}:{as_of.isoformat()}"

    for receivable in _current_receivables_for_client(store, slug):
        if receivable.lifecycle_state != "open":
            skipped.append(receivable.receivable_id)
            continue
        if _date_from_iso(receivable.due_date_iso) > as_of:
            skipped.append(receivable.receivable_id)
            continue
        replacement = create_expected_receivable(
            receivable_id=receivable.receivable_id,
            invoice_id=receivable.invoice_id,
            invoice_version_id=receivable.invoice_version_id,
            counterparty_ref=receivable.counterparty_ref,
            lifecycle_state="satisfied",
            expected_minor_units=receivable.expected_minor_units,
            currency_iso=receivable.currency_iso,
            due_date_iso=receivable.due_date_iso,
            recognized_utc_iso=receivable.recognized_utc_iso,
            idempotency_key=f"{resolution_ref}:{receivable.receivable_id}",
            source_ref=source_ref,
            supersedes_receivable_version_id=receivable.receivable_version_id,
            resolution_ref=resolution_ref,
        )
        result = store.supersede(receivable.receivable_id, replacement)
        if result.created:
            settled.append(receivable.receivable_id)

    paid_through_store.set_paid_through(slug, as_of, source_ref=source_ref)
    state = paid_up_state(slug, paid_through=as_of, now=as_of)
    return MarkPaidUpResult(
        client_ref=slug,
        paid_through=as_of,
        settled_receivable_ids=tuple(settled),
        skipped_receivable_ids=tuple(skipped),
        state=state,
    )


def paid_up_state_for_client(
    client_ref: str,
    *,
    now: date,
    paid_through_store: ClientPaidThroughStore,
) -> PaidUpState:
    paid_through = paid_through_store.get_paid_through(client_ref)
    return paid_up_state(client_ref, paid_through=paid_through, now=now)


__all__ = [
    "ClientPaidThroughStore",
    "MarkPaidUpResult",
    "mark_paid_up",
    "paid_up_state_for_client",
]
