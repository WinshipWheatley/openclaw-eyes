"""Capital Hilton payment evidence ingest.

Reads the captured check evidence, records a local append-only payment evidence
fact in the Gig-to-Cash SQLite file, and emits a gated receivable-close
proposal. It never marks a receivable paid, moves money, posts a ledger entry,
accesses a bank, sends email, or touches broker/listener code.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, NamedTuple

from ar_expected_receivable_record import ExpectedReceivableRecord
from ar_gig_to_cash_serialization import from_json
from ar_gig_to_cash_store import DEFAULT_DB_PATH


DEFAULT_EVIDENCE_PATH = Path("/home/openclaw/Operator/finance-evidence/capital-hilton-payment-20260702.md")
EXPECTED_COUNTERPARTY_REF = "capital_hilton"
EXPECTED_CHECK_NUMBER = "3000014313"

SCHEMA_VERSION = "capital_hilton_payment_ingest_v0"
PAYMENT_EVIDENCE_SCHEMA_VERSION = "capital_hilton_payment_evidence_record_v0"
PAYMENT_RECORDED_CLOSE_PROPOSAL_READY = "PAYMENT_RECORDED_CLOSE_PROPOSAL_READY"
PROPOSAL_REQUIRES_OPERATOR_APPROVAL = "PROPOSAL_REQUIRES_OPERATOR_APPROVAL"
NO_MATCH_FLAGGED = "NO_MATCH_FLAGGED"
ACTION_TYPE_RECEIVABLE_CLOSE = "g2c_receivable_close"

AUTHORITY_BOUNDARY_PROPOSAL = {
    "money_movement_performed": False,
    "bank_access_performed": False,
    "send_performed": False,
    "email_send_performed": False,
    "ledger_posting_performed": False,
    "store_close_performed": False,
}

_PAYMENT_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS payment_evidence_records (
    ingestion_seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    ingested_utc           TEXT    NOT NULL,
    payment_evidence_id    TEXT    NOT NULL,
    receivable_id          TEXT    NOT NULL,
    receivable_version_id  TEXT    NOT NULL,
    idempotency_key        TEXT    NOT NULL UNIQUE,
    canonical_json         TEXT    NOT NULL,
    content_sha256         TEXT    NOT NULL
)
"""


class AppendResult(NamedTuple):
    ingestion_seq: int
    idempotency_key: str
    content_sha256: str
    created: bool


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_aware_iso(value: str) -> datetime:
    text = str(value or "").replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _expires_at(requested_at_utc: str) -> str:
    return (_parse_aware_iso(requested_at_utc) + timedelta(hours=24)).isoformat(timespec="seconds")


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _short_hash(payload: Any, length: int = 20) -> str:
    return _sha256(_stable_json(payload))[:length]


def _money_minor_units(text: str) -> int | None:
    cleaned = str(text or "").replace("$", "").replace(",", "").strip()
    if not cleaned:
        return None
    try:
        amount = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _normalized_counterparty(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def parse_payment_evidence(text: str, *, source_ref: str) -> dict[str, Any]:
    amount_match = re.search(r"Amount:\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", text, re.IGNORECASE)
    check_match = re.search(r"Check\s*#:\s*([0-9]{4,12})", text, re.IGNORECASE)
    date_match = re.search(r"Date:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})", text, re.IGNORECASE)
    bank_match = re.search(r"Bank:\s*([^\n]+)", text, re.IGNORECASE)
    payer_match = re.search(r"Payer:\s*([^\n]+)", text, re.IGNORECASE)
    image_match = re.search(r"Image on file:\s*([^\n]+)", text, re.IGNORECASE)
    amount_text = amount_match.group(1) if amount_match else ""
    check_number = check_match.group(1) if check_match else ""
    return {
        "schema_version": PAYMENT_EVIDENCE_SCHEMA_VERSION,
        "source_ref": source_ref,
        "counterparty_ref": EXPECTED_COUNTERPARTY_REF,
        "client_name": "Capital Hilton",
        "payer": payer_match.group(1).strip() if payer_match else "HILTON",
        "amount_minor_units": _money_minor_units(amount_text),
        "currency_iso": "USD",
        "check_number": check_number,
        "payment_date": date_match.group(1).strip() if date_match else "",
        "bank": bank_match.group(1).strip() if bank_match else "",
        "image_ref": image_match.group(1).strip() if image_match else "",
        "resolution_ref": f"payment_evidence:check:{check_number}" if check_number else "payment_evidence:unlabeled",
    }


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_payment_schema(conn: sqlite3.Connection) -> None:
    conn.execute(_PAYMENT_TABLE_DDL)
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_payment_evidence_receivable
        ON payment_evidence_records (receivable_id, receivable_version_id)
        """
    )


def _open_current_receivables(conn: sqlite3.Connection) -> tuple[ExpectedReceivableRecord, ...]:
    rows = conn.execute(
        """
        SELECT canonical_json, content_sha256
        FROM expected_receivable_records
        WHERE lifecycle_state IN ('open', 'disputed')
          AND receivable_version_id NOT IN (
              SELECT supersedes_receivable_version_id
              FROM expected_receivable_records
              WHERE supersedes_receivable_version_id IS NOT NULL
          )
        ORDER BY ingestion_seq ASC
        """
    ).fetchall()
    records: list[ExpectedReceivableRecord] = []
    for row in rows:
        if _sha256(row["canonical_json"]) != row["content_sha256"]:
            continue
        record = from_json(row["canonical_json"])
        if isinstance(record, ExpectedReceivableRecord):
            records.append(record)
    return tuple(records)


def _match_receivable(
    payment: Mapping[str, Any],
    receivables: tuple[ExpectedReceivableRecord, ...],
) -> tuple[ExpectedReceivableRecord | None, tuple[str, ...]]:
    flags: list[str] = []
    check_number = str(payment.get("check_number") or "")
    if check_number != EXPECTED_CHECK_NUMBER:
        flags.append("check_mismatch")

    candidates = [
        receivable
        for receivable in receivables
        if _normalized_counterparty(receivable.counterparty_ref) == _normalized_counterparty(EXPECTED_COUNTERPARTY_REF)
    ]
    if not candidates:
        return None, tuple(flags + ["counterparty_mismatch"])

    amount = payment.get("amount_minor_units")
    amount_matches = [
        receivable
        for receivable in candidates
        if amount is not None and receivable.expected_minor_units == amount
    ]
    if not amount_matches:
        return None, tuple(flags + ["amount_mismatch"])
    if flags:
        return None, tuple(flags)
    if len(amount_matches) > 1:
        return None, ("ambiguous_receivable_match",)
    return amount_matches[0], ()


def _receivable_summary(receivable: ExpectedReceivableRecord) -> dict[str, Any]:
    return {
        "receivable_id": receivable.receivable_id,
        "receivable_version_id": receivable.receivable_version_id,
        "invoice_id": receivable.invoice_id,
        "invoice_version_id": receivable.invoice_version_id,
        "counterparty_ref": receivable.counterparty_ref,
        "lifecycle_state": receivable.lifecycle_state,
        "expected_minor_units": receivable.expected_minor_units,
        "currency_iso": receivable.currency_iso,
        "due_date_iso": receivable.due_date_iso,
        "source_ref": receivable.source_ref,
    }


def _payment_evidence_id(payment: Mapping[str, Any], receivable: ExpectedReceivableRecord) -> str:
    return "payment_evidence:capital_hilton:" + _short_hash(
        {
            "source_ref": payment.get("source_ref"),
            "check_number": payment.get("check_number"),
            "amount_minor_units": payment.get("amount_minor_units"),
            "receivable_version_id": receivable.receivable_version_id,
        },
        length=24,
    )


def _payment_record(payment: Mapping[str, Any], receivable: ExpectedReceivableRecord) -> dict[str, Any]:
    record = dict(payment)
    record["payment_evidence_id"] = _payment_evidence_id(payment, receivable)
    record["receivable_id"] = receivable.receivable_id
    record["receivable_version_id"] = receivable.receivable_version_id
    record["invoice_id"] = receivable.invoice_id
    record["invoice_version_id"] = receivable.invoice_version_id
    return record


def _canonical_payment_record(record: Mapping[str, Any]) -> str:
    return _stable_json(
        {
            "schema_version": PAYMENT_EVIDENCE_SCHEMA_VERSION,
            "record_type": "PaymentEvidenceRecord",
            "payload": dict(record),
        }
    )


def _append_payment_evidence(
    conn: sqlite3.Connection,
    record: Mapping[str, Any],
) -> AppendResult:
    canonical = _canonical_payment_record(record)
    sha = _sha256(canonical)
    idempotency_key = f"capital_hilton_payment:{sha}"
    existing = conn.execute(
        """
        SELECT ingestion_seq, content_sha256
        FROM payment_evidence_records
        WHERE idempotency_key = ?
        """,
        (idempotency_key,),
    ).fetchone()
    if existing:
        return AppendResult(
            ingestion_seq=existing["ingestion_seq"],
            idempotency_key=idempotency_key,
            content_sha256=sha,
            created=False,
        )
    conn.execute(
        """
        INSERT INTO payment_evidence_records
            (ingested_utc, payment_evidence_id, receivable_id, receivable_version_id,
             idempotency_key, canonical_json, content_sha256)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _utc_now_iso(),
            record["payment_evidence_id"],
            record["receivable_id"],
            record["receivable_version_id"],
            idempotency_key,
            canonical,
            sha,
        ),
    )
    seq = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return AppendResult(
        ingestion_seq=seq,
        idempotency_key=idempotency_key,
        content_sha256=sha,
        created=True,
    )


def _approval_request(
    *,
    proposal_id: str,
    payment: Mapping[str, Any],
    receivable: ExpectedReceivableRecord,
    requested_at_utc: str,
) -> dict[str, Any]:
    return {
        "schema_version": "OPERATOR_ACTION_APPROVAL_REQUEST_V0",
        "action_type": ACTION_TYPE_RECEIVABLE_CLOSE,
        "owner_agent": "cassandra",
        "owner_objective_id": proposal_id,
        "request_id": f"operator_action:{proposal_id}",
        "summary": f"Mark Capital Hilton receivable {receivable.receivable_id} paid/deposited from check evidence.",
        "payload": {
            "proposal_id": proposal_id,
            "payment_evidence": dict(payment),
            "matched_receivable": _receivable_summary(receivable),
            "authority_boundary": dict(AUTHORITY_BOUNDARY_PROPOSAL),
        },
        "risk_warning": (
            "Approval would append a satisfied receivable fact through the gated close workflow. "
            "This ingest only records payment evidence and proposes the action; it does not move money."
        ),
        "expires_at": _expires_at(requested_at_utc),
        "route_back": {
            "module": "gig_receivable_close",
            "function": "apply_approved_receivable_close",
            "proposal_id": proposal_id,
        },
        "authority_refs": ("OPENCLAW_RUNTIME.md#gig-to-cash-local-fact-recording",),
        "risk_tier": "high",
    }


def _close_proposal(
    *,
    payment: Mapping[str, Any],
    receivable: ExpectedReceivableRecord,
    requested_at_utc: str,
) -> dict[str, Any]:
    proposal_id = "g2c_receivable_close:" + _short_hash(
        {
            "payment_evidence_id": payment.get("payment_evidence_id"),
            "receivable_id": receivable.receivable_id,
            "receivable_version_id": receivable.receivable_version_id,
        }
    )
    return {
        "schema_version": "g2c_receivable_close_proposal_v0",
        "status": PROPOSAL_REQUIRES_OPERATOR_APPROVAL,
        "proposal_id": proposal_id,
        "flags": (),
        "payment_evidence": dict(payment),
        "matched_receivable": _receivable_summary(receivable),
        "approval_request": _approval_request(
            proposal_id=proposal_id,
            payment=payment,
            receivable=receivable,
            requested_at_utc=requested_at_utc,
        ),
        "authority_boundary": dict(AUTHORITY_BOUNDARY_PROPOSAL),
    }


def _append_result_payload(result: AppendResult) -> dict[str, Any]:
    return {
        "ingestion_seq": result.ingestion_seq,
        "idempotency_key": result.idempotency_key,
        "content_sha256": result.content_sha256,
        "created": result.created,
    }


def ingest_capital_hilton_payment(
    *,
    evidence_path: str | Path = DEFAULT_EVIDENCE_PATH,
    db_path: str = DEFAULT_DB_PATH,
    requested_at_utc: str | None = None,
) -> dict[str, Any]:
    evidence_path = Path(evidence_path)
    requested_at = requested_at_utc or _utc_now_iso()
    text = evidence_path.read_text(encoding="utf-8")
    payment = parse_payment_evidence(text, source_ref=str(evidence_path))

    conn = _connect(db_path)
    try:
        _ensure_payment_schema(conn)
        receivables = _open_current_receivables(conn)
        matched, flags = _match_receivable(payment, receivables)
        if matched is None:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": NO_MATCH_FLAGGED,
                "flags": flags or ("no_open_receivable_match",),
                "payment_evidence_record": payment,
                "append_result": None,
                "close_proposal": None,
                "authority_boundary": dict(AUTHORITY_BOUNDARY_PROPOSAL),
            }

        conn.execute("BEGIN IMMEDIATE")
        try:
            record = _payment_record(payment, matched)
            append_result = _append_payment_evidence(conn, record)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()

    proposal = _close_proposal(payment=record, receivable=matched, requested_at_utc=requested_at)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": PAYMENT_RECORDED_CLOSE_PROPOSAL_READY,
        "flags": (),
        "payment_evidence_record": record,
        "append_result": _append_result_payload(append_result),
        "close_proposal": proposal,
        "authority_boundary": dict(AUTHORITY_BOUNDARY_PROPOSAL),
    }


__all__ = [
    "ACTION_TYPE_RECEIVABLE_CLOSE",
    "AUTHORITY_BOUNDARY_PROPOSAL",
    "DEFAULT_EVIDENCE_PATH",
    "EXPECTED_CHECK_NUMBER",
    "EXPECTED_COUNTERPARTY_REF",
    "NO_MATCH_FLAGGED",
    "PAYMENT_RECORDED_CLOSE_PROPOSAL_READY",
    "PROPOSAL_REQUIRES_OPERATOR_APPROVAL",
    "ingest_capital_hilton_payment",
    "parse_payment_evidence",
]
