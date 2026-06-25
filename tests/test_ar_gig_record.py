import pytest
from ar_gig_record import GigRecord, create_gig_record, VALID_GIG_LIFECYCLE_STATES

def test_gig_record_initialization_success():
    gig = create_gig_record(
        counterparty_ref="capital_hilton",
        counterparty_name="Capital Hilton",
        billing_policy_ref="policy:standard_hourly",
        idempotency_key="request_12345"
    )
    assert gig.gig_id.startswith("gig:")
    assert gig.counterparty_ref == "capital_hilton"
    assert gig.counterparty_name == "Capital Hilton"
    assert gig.lifecycle_state == "proposed"
    assert gig.timezone == "UTC"
    assert gig.billing_policy_ref == "policy:standard_hourly"
    assert gig.idempotency_key == "request_12345"
    assert gig.scheduled_start_iso is None
    assert gig.scheduled_end_iso is None

def test_gig_record_invalid_lifecycle_state():
    with pytest.raises(ValueError, match="Invalid lifecycle state: unknown_state"):
        create_gig_record(
            counterparty_ref="capital_hilton",
            counterparty_name="Capital Hilton",
            billing_policy_ref="policy:standard_hourly",
            idempotency_key="request_12345",
            lifecycle_state="unknown_state"
        )

def test_gig_record_missing_required_fields():
    with pytest.raises(ValueError, match="counterparty reference and canonical name are required"):
        GigRecord(
            gig_id="gig:123",
            counterparty_ref="",
            counterparty_name="Capital Hilton",
            lifecycle_state="proposed",
            timezone="UTC",
            billing_policy_ref="policy:standard_hourly",
            idempotency_key="req_123"
        )
        
    with pytest.raises(ValueError, match="Explicit timezone is required"):
        GigRecord(
            gig_id="gig:123",
            counterparty_ref="cpt",
            counterparty_name="Capital Hilton",
            lifecycle_state="proposed",
            timezone="",
            billing_policy_ref="policy",
            idempotency_key="req_123"
        )

def test_gig_record_idempotency_key_required():
    with pytest.raises(ValueError, match="Idempotency key is required to prevent duplicates"):
        GigRecord(
            gig_id="gig:123",
            counterparty_ref="capital_hilton",
            counterparty_name="Capital Hilton",
            lifecycle_state="proposed",
            timezone="UTC",
            billing_policy_ref="policy:standard_hourly",
            idempotency_key=""
        )

def test_gig_record_scheduled_window_validation():
    # Valid window
    gig = create_gig_record(
        counterparty_ref="capital_hilton",
        counterparty_name="Capital Hilton",
        billing_policy_ref="policy",
        idempotency_key="req_123",
        scheduled_start_iso="2026-06-25T10:00:00+00:00",
        scheduled_end_iso="2026-06-25T12:00:00+00:00"
    )
    assert gig.scheduled_start_iso is not None
    
    # Invalid window (start > end)
    with pytest.raises(ValueError, match="Scheduled start must be before or equal to scheduled end"):
        create_gig_record(
            counterparty_ref="capital_hilton",
            counterparty_name="Capital Hilton",
            billing_policy_ref="policy",
            idempotency_key="req_123",
            scheduled_start_iso="2026-06-25T14:00:00+00:00",
            scheduled_end_iso="2026-06-25T12:00:00+00:00"
        )

def test_gig_record_immutability():
    gig = create_gig_record(
        counterparty_ref="capital_hilton",
        counterparty_name="Capital Hilton",
        billing_policy_ref="policy:standard_hourly",
        idempotency_key="request_12345"
    )
    with pytest.raises(Exception): # FrozenInstanceError or AttributeError
        gig.lifecycle_state = "active"
