from __future__ import annotations

from datetime import date
from pathlib import Path

from ar_expected_receivable_record import ExpectedReceivableRecord, create_expected_receivable
from ar_gig_to_cash_store import GigToCashStore
from ar_invoice_record import create_invoice_record
from receivable_temporal_scoping import (
    ClientPaidThroughStore,
    mark_paid_up,
    paid_up_state_for_client,
)


def _append_invoice_and_receivable(
    store: GigToCashStore,
    *,
    client_ref: str,
    invoice_id: str,
    receivable_id: str,
    due_date: str,
    amount: int = 12500,
) -> ExpectedReceivableRecord:
    invoice = create_invoice_record(
        invoice_id=invoice_id,
        counterparty_ref=client_ref,
        billing_entity_ref="winship_live",
        lifecycle_state="issued",
        invoice_number=invoice_id.replace("inv:", "INV-").upper(),
        issue_date_iso=due_date,
        due_date_iso=due_date,
        currency_iso="USD",
        total_minor_units=amount,
        idempotency_key=f"invoice:{invoice_id}",
        source_ref="test",
    )
    store.append(invoice)
    receivable = create_expected_receivable(
        receivable_id=receivable_id,
        invoice_id=invoice.invoice_id,
        invoice_version_id=invoice.invoice_version_id,
        counterparty_ref=client_ref,
        expected_minor_units=amount,
        currency_iso="USD",
        due_date_iso=due_date,
        recognized_utc_iso=f"{due_date}T00:00:00+00:00",
        idempotency_key=f"receivable:{receivable_id}:open",
        source_ref="test",
    )
    store.append(receivable)
    return receivable


def test_mark_paid_up_settles_due_receivables_idempotently_without_compounding(tmp_path: Path) -> None:
    paid_store = ClientPaidThroughStore(tmp_path / "paid_through.sqlite")
    with GigToCashStore(str(tmp_path / "ar.sqlite")) as store:
        _append_invoice_and_receivable(
            store,
            client_ref="st_annes",
            invoice_id="inv:st-annes-june",
            receivable_id="recv:st-annes-june",
            due_date="2026-06-15",
        )
        _append_invoice_and_receivable(
            store,
            client_ref="st_annes",
            invoice_id="inv:st-annes-july",
            receivable_id="recv:st-annes-july",
            due_date="2026-07-15",
        )

        first = mark_paid_up(store, "st_annes", as_of=date(2026, 6, 15), paid_through_store=paid_store)
        second = mark_paid_up(store, "st_annes", as_of=date(2026, 6, 15), paid_through_store=paid_store)

        june = store.get_current(ExpectedReceivableRecord, "recv:st-annes-june")
        july = store.get_current(ExpectedReceivableRecord, "recv:st-annes-july")

        assert first.settled_receivable_ids == ("recv:st-annes-june",)
        assert second.settled_receivable_ids == ()
        assert june.lifecycle_state == "satisfied"
        assert june.resolution_ref == "paid_up:st_annes:2026-06-15"
        assert july.lifecycle_state == "open"
        assert len(store.list_history(ExpectedReceivableRecord, "recv:st-annes-june")) == 2
        assert paid_store.get_paid_through("st_annes") == date(2026, 6, 15)


def test_paid_up_state_uses_paid_through_and_recurrence_without_assuming_forever(tmp_path: Path) -> None:
    paid_store = ClientPaidThroughStore(tmp_path / "paid_through.sqlite")
    paid_store.set_paid_through("st_annes", date(2026, 6, 15), source_ref="test")

    assert paid_up_state_for_client("st_annes", now=date(2026, 6, 30), paid_through_store=paid_store).status == "paid_up_through"
    assert paid_up_state_for_client("st_annes", now=date(2026, 7, 1), paid_through_store=paid_store).status == "invoice_due"
    assert paid_up_state_for_client("live_arts_md", now=date(2026, 9, 1), paid_through_store=paid_store).status == "unknown_scope"
