import pytest
from ar_invoice_record import InvoiceRecord, create_invoice_record

def test_invoice_record_initialization_draft():
    invoice = create_invoice_record(
        counterparty_ref="cpt:1",
        billing_entity_ref="entity:1",
        idempotency_key="idemp:1",
        source_ref="src:1"
    )
    assert invoice.invoice_id.startswith("inv:")
    assert invoice.invoice_version_id.startswith("inv_ver:")
    assert invoice.lifecycle_state == "draft"
    assert invoice.invoice_number is None

def test_invoice_record_initialization_issued():
    invoice = create_invoice_record(
        counterparty_ref="cpt:1",
        billing_entity_ref="entity:1",
        idempotency_key="idemp:1",
        source_ref="src:1",
        lifecycle_state="issued",
        invoice_number="INV-001",
        issue_date_iso="2026-06-25",
        due_date_iso="2026-07-25",
        currency_iso="USD",
        total_minor_units=150000
    )
    assert invoice.lifecycle_state == "issued"
    assert invoice.invoice_number == "INV-001"
    assert invoice.total_minor_units == 150000

def test_invoice_issued_requires_fields():
    with pytest.raises(ValueError, match="invoice_number is required for lifecycle state 'issued'"):
        create_invoice_record(
            counterparty_ref="cpt:1",
            billing_entity_ref="entity:1",
            idempotency_key="idemp:1",
            source_ref="src:1",
            lifecycle_state="issued",
            invoice_number=None,
            issue_date_iso="2026-06-25",
            due_date_iso="2026-07-25",
            currency_iso="USD",
            total_minor_units=150000
        )
        
    with pytest.raises(ValueError, match="total_minor_units is required for lifecycle state 'approved'"):
        create_invoice_record(
            counterparty_ref="cpt:1",
            billing_entity_ref="entity:1",
            idempotency_key="idemp:1",
            source_ref="src:1",
            lifecycle_state="approved",
            invoice_number="INV-001",
            issue_date_iso="2026-06-25",
            due_date_iso="2026-07-25",
            currency_iso="USD",
            total_minor_units=None
        )

def test_total_minor_units_must_be_integer():
    with pytest.raises(ValueError, match="total_minor_units must be an integer representing minor units \\(not floats\\)"):
        create_invoice_record(
            counterparty_ref="cpt:1",
            billing_entity_ref="entity:1",
            idempotency_key="idemp:1",
            source_ref="src:1",
            lifecycle_state="draft",
            total_minor_units=150.00 # float
        )

def test_invoice_versioning_pointer():
    invoice_v1 = create_invoice_record(
        counterparty_ref="cpt:1",
        billing_entity_ref="entity:1",
        idempotency_key="idemp:1",
        source_ref="src:1",
        lifecycle_state="draft"
    )
    
    invoice_v2 = create_invoice_record(
        invoice_id=invoice_v1.invoice_id,
        counterparty_ref="cpt:1",
        billing_entity_ref="entity:1",
        idempotency_key="idemp:2",
        source_ref="src:2",
        lifecycle_state="issued",
        invoice_number="INV-001",
        issue_date_iso="2026-06-25",
        due_date_iso="2026-07-25",
        currency_iso="USD",
        total_minor_units=150000,
        supersedes_invoice_version_id=invoice_v1.invoice_version_id
    )
    
    assert invoice_v2.invoice_id == invoice_v1.invoice_id
    assert invoice_v2.invoice_version_id != invoice_v1.invoice_version_id
    assert invoice_v2.supersedes_invoice_version_id == invoice_v1.invoice_version_id

def test_invoice_immutability():
    invoice = create_invoice_record(
        counterparty_ref="cpt:1",
        billing_entity_ref="entity:1",
        idempotency_key="idemp:1",
        source_ref="src:1",
        lifecycle_state="draft"
    )
    with pytest.raises(Exception):
        invoice.lifecycle_state = "approved"
