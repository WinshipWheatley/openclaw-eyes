from dataclasses import dataclass
from datetime import datetime
import uuid

VALID_INVOICE_LIFECYCLE_STATES = frozenset([
    "draft",
    "approved",
    "issued",
    "voided"
])

@dataclass(frozen=True)
class InvoiceRecord:
    """
    Canonical versioned InvoiceRecord representing a snapshot of an invoice.
    Isolated from payment status, bank data, Excel locations, and email delivery.
    """
    invoice_id: str
    invoice_version_id: str
    counterparty_ref: str
    billing_entity_ref: str
    lifecycle_state: str
    idempotency_key: str
    source_ref: str
    
    # Optional fields that become required in 'approved' or 'issued' states
    invoice_number: str | None = None
    issue_date_iso: str | None = None
    due_date_iso: str | None = None
    currency_iso: str | None = None
    total_minor_units: int | None = None
    
    # Backward pointer for versioning
    supersedes_invoice_version_id: str | None = None

    def __post_init__(self):
        if not self.invoice_id:
            raise ValueError("invoice_id is required")
        if not self.invoice_version_id:
            raise ValueError("invoice_version_id is required")
        if not self.counterparty_ref:
            raise ValueError("counterparty_ref is required")
        if not self.billing_entity_ref:
            raise ValueError("billing_entity_ref is required")
        if not self.idempotency_key:
            raise ValueError("idempotency_key is required")
        if not self.source_ref:
            raise ValueError("source_ref is required")
            
        if self.lifecycle_state not in VALID_INVOICE_LIFECYCLE_STATES:
            raise ValueError(f"Invalid lifecycle state: {self.lifecycle_state}")
            
        # Validate that total is strictly an integer if provided (not bool)
        if self.total_minor_units is not None and type(self.total_minor_units) is not int:
            raise ValueError("total_minor_units must be an integer representing minor units (not floats)")

        # Validate currency formatting
        if self.currency_iso is not None:
            if not isinstance(self.currency_iso, str) or len(self.currency_iso) != 3 or not self.currency_iso.isupper():
                raise ValueError("currency_iso must be exactly three uppercase letters")

        # Validate dates if provided
        issue_dt = None
        due_dt = None
        if self.issue_date_iso is not None:
            issue_dt = datetime.fromisoformat(self.issue_date_iso)
        if self.due_date_iso is not None:
            due_dt = datetime.fromisoformat(self.due_date_iso)
            
        if issue_dt and due_dt and due_dt < issue_dt:
            raise ValueError("due_date_iso cannot precede issue_date_iso")

        # Invariant: Approved or issued versions must have a number, dates, currency, and total
        if self.lifecycle_state in {"approved", "issued"}:
            if not self.invoice_number:
                raise ValueError(f"invoice_number is required for lifecycle state '{self.lifecycle_state}'")
            if not self.issue_date_iso:
                raise ValueError(f"issue_date_iso is required for lifecycle state '{self.lifecycle_state}'")
            if not self.due_date_iso:
                raise ValueError(f"due_date_iso is required for lifecycle state '{self.lifecycle_state}'")
            if not self.currency_iso:
                raise ValueError(f"currency_iso is required for lifecycle state '{self.lifecycle_state}'")
            if self.total_minor_units is None:
                raise ValueError(f"total_minor_units is required for lifecycle state '{self.lifecycle_state}'")

def create_invoice_record(
    counterparty_ref: str,
    billing_entity_ref: str,
    idempotency_key: str,
    source_ref: str,
    lifecycle_state: str = "draft",
    invoice_id: str | None = None,
    invoice_number: str | None = None,
    issue_date_iso: str | None = None,
    due_date_iso: str | None = None,
    currency_iso: str | None = None,
    total_minor_units: int | None = None,
    supersedes_invoice_version_id: str | None = None
) -> InvoiceRecord:
    # Generate logical invoice_id if not provided (e.g. for a new invoice series)
    if not invoice_id:
        invoice_id = f"inv:{uuid.uuid4().hex}"
        
    return InvoiceRecord(
        invoice_id=invoice_id,
        invoice_version_id=f"inv_ver:{uuid.uuid4().hex}",
        counterparty_ref=counterparty_ref,
        billing_entity_ref=billing_entity_ref,
        lifecycle_state=lifecycle_state,
        idempotency_key=idempotency_key,
        source_ref=source_ref,
        invoice_number=invoice_number,
        issue_date_iso=issue_date_iso,
        due_date_iso=due_date_iso,
        currency_iso=currency_iso,
        total_minor_units=total_minor_units,
        supersedes_invoice_version_id=supersedes_invoice_version_id
    )
