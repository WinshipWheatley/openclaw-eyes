import pytest
from ar_expected_receivable_record import ExpectedReceivableRecord, create_expected_receivable

def test_expected_receivable_initialization_success():
    recv = create_expected_receivable(
        invoice_id="inv:1",
        invoice_version_id="inv_ver:1",
        counterparty_ref="cpt:1",
        expected_minor_units=200000,
        currency_iso="USD",
        due_date_iso="2026-07-25",
        recognized_utc_iso="2026-06-25T10:00:00+00:00",
        idempotency_key="idemp:1",
        source_ref="src:1"
    )
    assert recv.receivable_id.startswith("recv:")
    assert recv.receivable_version_id.startswith("recv_ver:")
    assert recv.invoice_version_id == "inv_ver:1"
    assert recv.lifecycle_state == "open"
    assert recv.expected_minor_units == 200000
    assert recv.currency_iso == "USD"

def test_invalid_lifecycle_state():
    with pytest.raises(ValueError, match="Invalid lifecycle state"):
        create_expected_receivable(
            invoice_id="inv:1",
            invoice_version_id="inv_ver:1",
            counterparty_ref="cpt:1",
            expected_minor_units=200000,
            currency_iso="USD",
            due_date_iso="2026-07-25",
            recognized_utc_iso="2026-06-25T10:00:00+00:00",
            idempotency_key="idemp:1",
            source_ref="src:1",
            lifecycle_state="unknown"
        )

def test_terminal_state_requires_resolution_ref():
    with pytest.raises(ValueError, match="resolution_ref is required for terminal state 'satisfied'"):
        create_expected_receivable(
            invoice_id="inv:1",
            invoice_version_id="inv_ver:1",
            counterparty_ref="cpt:1",
            expected_minor_units=200000,
            currency_iso="USD",
            due_date_iso="2026-07-25",
            recognized_utc_iso="2026-06-25T10:00:00+00:00",
            idempotency_key="idemp:1",
            source_ref="src:1",
            lifecycle_state="satisfied"
        )

def test_amount_must_be_strictly_positive_integer():
    with pytest.raises(ValueError, match="expected_minor_units must be an integer \\(not floats or booleans\\)"):
        create_expected_receivable(
            invoice_id="inv:1",
            invoice_version_id="inv_ver:1",
            counterparty_ref="cpt:1",
            expected_minor_units=True, # bool
            currency_iso="USD",
            due_date_iso="2026-07-25",
            recognized_utc_iso="2026-06-25T10:00:00+00:00",
            idempotency_key="idemp:1",
            source_ref="src:1"
        )

    with pytest.raises(ValueError, match="expected_minor_units must be positive"):
        create_expected_receivable(
            invoice_id="inv:1",
            invoice_version_id="inv_ver:1",
            counterparty_ref="cpt:1",
            expected_minor_units=-500, # negative
            currency_iso="USD",
            due_date_iso="2026-07-25",
            recognized_utc_iso="2026-06-25T10:00:00+00:00",
            idempotency_key="idemp:1",
            source_ref="src:1"
        )
        
def test_currency_must_be_three_uppercase_letters():
    with pytest.raises(ValueError, match="currency_iso must be exactly three uppercase letters"):
        create_expected_receivable(
            invoice_id="inv:1",
            invoice_version_id="inv_ver:1",
            counterparty_ref="cpt:1",
            expected_minor_units=200000,
            currency_iso="usd",
            due_date_iso="2026-07-25",
            recognized_utc_iso="2026-06-25T10:00:00+00:00",
            idempotency_key="idemp:1",
            source_ref="src:1"
        )

def test_recognized_utc_iso_must_be_timezone_aware():
    with pytest.raises(ValueError, match="recognized_utc_iso must be timezone-aware"):
        create_expected_receivable(
            invoice_id="inv:1",
            invoice_version_id="inv_ver:1",
            counterparty_ref="cpt:1",
            expected_minor_units=200000,
            currency_iso="USD",
            due_date_iso="2026-07-25",
            recognized_utc_iso="2026-06-25T10:00:00", # missing timezone
            idempotency_key="idemp:1",
            source_ref="src:1"
        )

def test_immutability():
    recv = create_expected_receivable(
        invoice_id="inv:1",
        invoice_version_id="inv_ver:1",
        counterparty_ref="cpt:1",
        expected_minor_units=200000,
        currency_iso="USD",
        due_date_iso="2026-07-25",
        recognized_utc_iso="2026-06-25T10:00:00+00:00",
        idempotency_key="idemp:1",
        source_ref="src:1"
    )
    with pytest.raises(Exception):
        recv.lifecycle_state = "satisfied"
