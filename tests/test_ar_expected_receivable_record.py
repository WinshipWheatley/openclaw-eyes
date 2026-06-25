import pytest
from ar_expected_receivable_record import ExpectedReceivableRecord, create_expected_receivable

def test_expected_receivable_initialization_success():
    recv = create_expected_receivable(
        counterparty_ref="cpt:1",
        invoice_id="inv:1",
        idempotency_key="idemp:1",
        source_ref="src:1",
        expected_amount_minor_units=200000,
        currency_iso="USD",
        due_date_iso="2026-07-25"
    )
    assert recv.receivable_id.startswith("recv:")
    assert recv.counterparty_ref == "cpt:1"
    assert recv.invoice_id == "inv:1"
    assert recv.lifecycle_state == "pending"
    assert recv.expected_amount_minor_units == 200000
    assert recv.currency_iso == "USD"
    assert recv.due_date_iso == "2026-07-25"

def test_invalid_lifecycle_state():
    with pytest.raises(ValueError, match="Invalid lifecycle state: unknown"):
        create_expected_receivable(
            counterparty_ref="cpt:1",
            invoice_id="inv:1",
            idempotency_key="idemp:1",
            source_ref="src:1",
            expected_amount_minor_units=200000,
            currency_iso="USD",
            due_date_iso="2026-07-25",
            lifecycle_state="unknown"
        )

def test_amount_must_be_positive_integer():
    with pytest.raises(ValueError, match="expected_amount_minor_units must be an integer"):
        create_expected_receivable(
            counterparty_ref="cpt:1",
            invoice_id="inv:1",
            idempotency_key="idemp:1",
            source_ref="src:1",
            expected_amount_minor_units=2000.00, # float
            currency_iso="USD",
            due_date_iso="2026-07-25"
        )

    with pytest.raises(ValueError, match="expected_amount_minor_units cannot be negative"):
        create_expected_receivable(
            counterparty_ref="cpt:1",
            invoice_id="inv:1",
            idempotency_key="idemp:1",
            source_ref="src:1",
            expected_amount_minor_units=-500,
            currency_iso="USD",
            due_date_iso="2026-07-25"
        )

def test_missing_required_fields():
    with pytest.raises(ValueError, match="counterparty_ref is required"):
        ExpectedReceivableRecord(
            receivable_id="recv:1",
            counterparty_ref="",
            invoice_id="inv:1",
            lifecycle_state="pending",
            idempotency_key="idemp:1",
            source_ref="src:1",
            expected_amount_minor_units=200000,
            currency_iso="USD",
            due_date_iso="2026-07-25"
        )
        
    with pytest.raises(ValueError, match="due_date_iso is required"):
        ExpectedReceivableRecord(
            receivable_id="recv:1",
            counterparty_ref="cpt:1",
            invoice_id="inv:1",
            lifecycle_state="pending",
            idempotency_key="idemp:1",
            source_ref="src:1",
            expected_amount_minor_units=200000,
            currency_iso="USD",
            due_date_iso=""
        )

def test_immutability():
    recv = create_expected_receivable(
        counterparty_ref="cpt:1",
        invoice_id="inv:1",
        idempotency_key="idemp:1",
        source_ref="src:1",
        expected_amount_minor_units=200000,
        currency_iso="USD",
        due_date_iso="2026-07-25"
    )
    with pytest.raises(Exception):
        recv.lifecycle_state = "paid_in_full"
