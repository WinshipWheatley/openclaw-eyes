"""Bridge check/payment evidence to the G2C books.

Records-only: no sends, no money movement, no bank access, no paid marking.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable, Mapping

from ar_expected_receivable_record import ExpectedReceivableRecord, create_expected_receivable
from ar_gig_record import create_gig_record
from ar_gig_to_cash_serialization import from_json
from ar_gig_to_cash_store import DEFAULT_DB_PATH, GigToCashStore
from ar_invoice_record import create_invoice_record


DEFAULT_REYNOLDS_COUNTERPARTY = "reynolds_tavern"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _db(db_path: str | Path | None) -> str:
    return str(db_path or DEFAULT_DB_PATH)


def _amount_from_evidence(evidence: Mapping[str, Any]) -> int:
    value = evidence.get("amount_minor_units")
    if isinstance(value, int) and value > 0:
        return value
    text = str(evidence.get("operator_note") or evidence.get("ocr_text") or "")
    match = re.search(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", text)
    if not match:
        return 0
    return int(round(float(match.group(1).replace(",", "")) * 100))


def seed_reynolds_receivable(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    amount_minor_units: int,
    gig_date_iso: str,
    due_date_iso: str,
    invoice_number: str | None = None,
) -> dict[str, str]:
    invoice_number = invoice_number or f"RT-{gig_date_iso}"
    now = _utc_now()
    with GigToCashStore(_db(db_path)) as store:
        gig = create_gig_record(
            counterparty_ref=DEFAULT_REYNOLDS_COUNTERPARTY,
            counterparty_name="Reynolds Tavern",
            billing_policy_ref="reynolds_tavern_standard_gig_fee",
            idempotency_key=f"seed:reynolds:gig:{gig_date_iso}",
            timezone="America/New_York",
            lifecycle_state="active",
            scheduled_start_iso=f"{gig_date_iso}T00:00:00",
            scheduled_end_iso=f"{gig_date_iso}T23:59:59",
        )
        store.append(gig)
        invoice = create_invoice_record(
            counterparty_ref=DEFAULT_REYNOLDS_COUNTERPARTY,
            billing_entity_ref="winship_live",
            lifecycle_state="approved",
            idempotency_key=f"seed:reynolds:invoice:{invoice_number}",
            source_ref=f"gig:{gig.gig_id}",
            invoice_number=invoice_number,
            issue_date_iso=gig_date_iso,
            due_date_iso=due_date_iso,
            currency_iso="USD",
            total_minor_units=amount_minor_units,
        )
        store.append(invoice)
        receivable = create_expected_receivable(
            invoice_id=invoice.invoice_id,
            invoice_version_id=invoice.invoice_version_id,
            counterparty_ref=DEFAULT_REYNOLDS_COUNTERPARTY,
            expected_minor_units=amount_minor_units,
            currency_iso="USD",
            due_date_iso=due_date_iso,
            recognized_utc_iso=now,
            idempotency_key=f"seed:reynolds:receivable:{invoice_number}",
            source_ref=f"gig:{gig.gig_id}",
        )
        store.append(receivable)
    return {
        "gig_id": gig.gig_id,
        "invoice_id": invoice.invoice_id,
        "receivable_id": receivable.receivable_id,
    }


def _current_open_receivables(db_path: str | Path) -> list[ExpectedReceivableRecord]:
    with sqlite3.connect(_db(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT canonical_json
            FROM expected_receivable_records
            WHERE lifecycle_state = 'open'
            ORDER BY ingestion_seq ASC
            """
        ).fetchall()
    candidates = [from_json(row[0]) for row in rows]
    out: list[ExpectedReceivableRecord] = []
    with GigToCashStore(_db(db_path)) as store:
        for record in candidates:
            if not isinstance(record, ExpectedReceivableRecord):
                continue
            current = store.get_current(ExpectedReceivableRecord, record.receivable_id)
            if current and current.lifecycle_state == "open":
                out.append(current)
    return out


def _gig_id_from_source_ref(source_ref: str) -> str:
    text = str(source_ref or "")
    if text.startswith("gig:gig:"):
        return text[len("gig:"):]
    if text.startswith("gig:"):
        return text[len("gig:"):]
    return text


def match_check_to_receivable(
    evidence_record: Mapping[str, Any],
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    vendor = str(evidence_record.get("claimed_client_ref") or "").strip().lower()
    amount = _amount_from_evidence(evidence_record)
    currency = str(evidence_record.get("currency_iso") or "USD").strip().upper()
    for receivable in _current_open_receivables(db_path):
        if vendor and receivable.counterparty_ref.lower() != vendor:
            continue
        if receivable.currency_iso != currency:
            continue
        return {
            "matched": True,
            "receivable_id": receivable.receivable_id,
            "invoice_id": receivable.invoice_id,
            "gig_id": _gig_id_from_source_ref(receivable.source_ref),
            "counterparty_ref": receivable.counterparty_ref,
            "expected_minor_units": receivable.expected_minor_units,
            "check_minor_units": amount,
            "currency_iso": currency,
            "due_date_iso": receivable.due_date_iso,
            "amount_matches": amount == receivable.expected_minor_units,
        }
    return {"matched": False, "amount_matches": False, "check_minor_units": amount, "currency_iso": currency}


def build_deposit_question_card(match: Mapping[str, Any]) -> dict[str, Any]:
    dollars = int(match.get("expected_minor_units") or 0) / 100
    vendor = str(match.get("counterparty_ref") or "the gig")
    summary = (
        f"{vendor} check matches the ${dollars:,.2f} receivable due {match.get('due_date_iso')}. "
        "Did you deposit it? Also confirm whether this gig has already been played or this is an advance/deposit."
    )
    return {
        "card_type": "CHECK_RECEIVABLE_MATCH",
        "headline": f"{vendor} check matches receivable",
        "summary": summary,
        "receivable_id": str(match.get("receivable_id") or ""),
        "gig_id": str(match.get("gig_id") or ""),
        "authority_boundary": {
            "money_movement_performed": False,
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
        },
    }


def _ensure_link_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gig_evidence_link (
            artifact_ref TEXT NOT NULL PRIMARY KEY,
            gig_id TEXT NOT NULL,
            receivable_id TEXT NOT NULL,
            vendor TEXT NOT NULL
        )
        """
    )


def _insert_link(db_path: str | Path, *, artifact_ref: str, gig_id: str, receivable_id: str, vendor: str) -> None:
    with sqlite3.connect(_db(db_path)) as conn:
        _ensure_link_table(conn)
        conn.execute(
            """
            INSERT OR IGNORE INTO gig_evidence_link (artifact_ref, gig_id, receivable_id, vendor)
            VALUES (?, ?, ?, ?)
            """,
            (artifact_ref, gig_id, receivable_id, vendor),
        )


def list_gig_evidence_links(*, db_path: str | Path = DEFAULT_DB_PATH) -> list[dict[str, str]]:
    with sqlite3.connect(_db(db_path)) as conn:
        _ensure_link_table(conn)
        rows = conn.execute(
            "SELECT artifact_ref, gig_id, receivable_id, vendor FROM gig_evidence_link ORDER BY artifact_ref"
        ).fetchall()
    return [
        {
            "artifact_ref": row[0],
            "gig_id": row[1],
            "receivable_id": row[2],
            "vendor": row[3],
        }
        for row in rows
    ]


def confirm_deposit(
    match: Mapping[str, Any],
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    artifact_ref: str,
    duplicate_fn: Callable[[float], Mapping[str, Any] | None] | None = None,
    log_fn: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    if not match.get("matched"):
        return {"receivable_satisfied": False, "income_logged": False, "reason": "no_match"}
    receivable_id = str(match["receivable_id"])
    amount_minor = int(match["expected_minor_units"])
    amount = amount_minor / 100
    vendor = str(match.get("counterparty_ref") or "")
    with GigToCashStore(_db(db_path)) as store:
        current = store.get_current(ExpectedReceivableRecord, receivable_id)
        if current is None:
            return {"receivable_satisfied": False, "income_logged": False, "reason": "missing_receivable"}
        receivable_satisfied = False
        if current.lifecycle_state != "satisfied":
            new_record = create_expected_receivable(
                invoice_id=current.invoice_id,
                invoice_version_id=current.invoice_version_id,
                counterparty_ref=current.counterparty_ref,
                expected_minor_units=current.expected_minor_units,
                currency_iso=current.currency_iso,
                due_date_iso=current.due_date_iso,
                recognized_utc_iso=_utc_now(),
                idempotency_key=f"deposit_confirm:{artifact_ref}:{receivable_id}",
                source_ref=current.source_ref,
                lifecycle_state="satisfied",
                receivable_id=current.receivable_id,
                supersedes_receivable_version_id=current.receivable_version_id,
                resolution_ref=artifact_ref,
            )
            store.supersede(receivable_id, new_record)
            receivable_satisfied = True

    if duplicate_fn is None or log_fn is None:
        import chief_cpa_brain

        duplicate_fn = duplicate_fn or chief_cpa_brain.find_duplicate_today
        log_fn = log_fn or chief_cpa_brain.log_entry
    duplicate = duplicate_fn(amount)
    income_logged = False
    income_entry = duplicate
    if duplicate is None:
        income_entry = log_fn(
            amount=amount,
            description=f"{vendor} gig {match.get('due_date_iso')} artifact={artifact_ref} gig={match.get('gig_id')} receivable={receivable_id}",
            category="schedule_c_gross",
            entry_type="income",
            payer=vendor,
        )
        income_logged = True
    _insert_link(
        db_path,
        artifact_ref=artifact_ref,
        gig_id=str(match.get("gig_id") or ""),
        receivable_id=receivable_id,
        vendor=vendor,
    )
    return {
        "receivable_satisfied": receivable_satisfied,
        "income_logged": income_logged,
        "income_entry": dict(income_entry or {}),
        "paid_marking_performed": False,
        "money_movement_performed": False,
    }


__all__ = [
    "build_deposit_question_card",
    "confirm_deposit",
    "list_gig_evidence_links",
    "match_check_to_receivable",
    "seed_reynolds_receivable",
]
