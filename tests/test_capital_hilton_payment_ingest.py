from __future__ import annotations

import sqlite3
from pathlib import Path

from ar_expected_receivable_record import ExpectedReceivableRecord, create_expected_receivable
from ar_gig_to_cash_store import GigToCashStore
from ar_invoice_record import create_invoice_record

import capital_hilton_payment_ingest as ingest


FIXED_NOW = "2026-07-04T13:00:00+00:00"


def _seed_capital_hilton_open_receivable(db_path: Path) -> ExpectedReceivableRecord:
    invoice = create_invoice_record(
        invoice_id="inv:capital_hilton:2026-06",
        invoice_number="CH-2026-06",
        counterparty_ref="capital_hilton",
        billing_entity_ref="winship",
        lifecycle_state="issued",
        issue_date_iso="2026-06-25",
        due_date_iso="2026-07-01",
        currency_iso="USD",
        total_minor_units=200000,
        idempotency_key="invoice:capital_hilton:2026-06",
        source_ref="test:capital_hilton_invoice",
    )
    receivable = create_expected_receivable(
        receivable_id="recv:capital_hilton:2026-06",
        invoice_id=invoice.invoice_id,
        invoice_version_id=invoice.invoice_version_id,
        counterparty_ref="capital_hilton",
        expected_minor_units=200000,
        currency_iso="USD",
        due_date_iso="2026-07-01",
        recognized_utc_iso="2026-06-25T12:00:00+00:00",
        idempotency_key="receivable:capital_hilton:2026-06:open",
        source_ref="test:capital_hilton_receivable",
    )
    with GigToCashStore(str(db_path)) as store:
        store.append(invoice)
        store.append(receivable)
    return receivable


def _evidence_text(*, amount: str = "$2,000.00", check_number: str = "3000014313") -> str:
    return f"""# PAYMENT EVIDENCE - Capital Hilton receivable PAID

## Check facts
- Payer: HILTON - Center of Excellence
- Payee: WINSHIP LIVE
- Amount: {amount} (Two Thousand and 00/100)
- Date: 06/25/2026
- Check #: {check_number}
- Bank: Wells Fargo Bank, N.A.
- Image on file: /home/openclaw/state/telegram_image_intake/maestro/716/telegram_image.jpg

## Reconciliation
- Matches the tracked Capital Hilton receivable ($2,000 invoice, Coupa-submitted).
"""


def _write_evidence(path: Path, *, amount: str = "$2,000.00", check_number: str = "3000014313") -> Path:
    path.write_text(_evidence_text(amount=amount, check_number=check_number), encoding="utf-8")
    return path


def _payment_rows(db_path: Path) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT payment_evidence_id, receivable_id, canonical_json FROM payment_evidence_records"
        ).fetchall()
    finally:
        conn.close()


def test_capital_hilton_payment_matches_open_receivable_and_emits_gated_proposal(tmp_path: Path) -> None:
    db_path = tmp_path / "g2c.sqlite3"
    evidence_path = _write_evidence(tmp_path / "capital-hilton-payment.md")
    original = _seed_capital_hilton_open_receivable(db_path)

    result = ingest.ingest_capital_hilton_payment(
        evidence_path=evidence_path,
        db_path=str(db_path),
        requested_at_utc=FIXED_NOW,
    )

    assert result["status"] == ingest.PAYMENT_RECORDED_CLOSE_PROPOSAL_READY
    assert result["payment_evidence_record"]["check_number"] == "3000014313"
    assert result["payment_evidence_record"]["amount_minor_units"] == 200000
    assert result["append_result"]["created"] is True
    proposal = result["close_proposal"]
    assert proposal["schema_version"] == "g2c_receivable_close_proposal_v0"
    assert proposal["status"] == ingest.PROPOSAL_REQUIRES_OPERATOR_APPROVAL
    assert proposal["matched_receivable"]["receivable_id"] == original.receivable_id
    assert proposal["payment_evidence"]["resolution_ref"] == "payment_evidence:check:3000014313"
    assert proposal["approval_request"]["route_back"]["function"] == "apply_approved_receivable_close"
    assert proposal["authority_boundary"]["money_movement_performed"] is False
    assert proposal["authority_boundary"]["store_close_performed"] is False

    with GigToCashStore(str(db_path)) as store:
        current = store.get_current(ExpectedReceivableRecord, original.receivable_id)
        history = store.list_history(ExpectedReceivableRecord, original.receivable_id)
    assert current == original
    assert len(history) == 1
    assert len(_payment_rows(db_path)) == 1


def test_amount_or_check_mismatch_is_flagged_without_proposal_or_receivable_close(tmp_path: Path) -> None:
    db_path = tmp_path / "g2c.sqlite3"
    evidence_path = _write_evidence(
        tmp_path / "capital-hilton-payment-mismatch.md",
        amount="$1,999.00",
        check_number="9999999999",
    )
    original = _seed_capital_hilton_open_receivable(db_path)

    result = ingest.ingest_capital_hilton_payment(
        evidence_path=evidence_path,
        db_path=str(db_path),
        requested_at_utc=FIXED_NOW,
    )

    assert result["status"] == ingest.NO_MATCH_FLAGGED
    assert result["close_proposal"] is None
    assert "amount_mismatch" in result["flags"]
    assert "check_mismatch" in result["flags"]
    assert result["authority_boundary"]["money_movement_performed"] is False
    assert result["authority_boundary"]["store_close_performed"] is False

    with GigToCashStore(str(db_path)) as store:
        current = store.get_current(ExpectedReceivableRecord, original.receivable_id)
        history = store.list_history(ExpectedReceivableRecord, original.receivable_id)
    assert current == original
    assert len(history) == 1
    assert _payment_rows(db_path) == []
