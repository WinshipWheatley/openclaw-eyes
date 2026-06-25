from dataclasses import dataclass
import uuid

VALID_RECEIVABLE_LIFECYCLE_STATES = frozenset([
    "pending",
    "partially_paid",
    "paid_in_full",
    "cancelled",
    "uncollectible"
])

@dataclass(frozen=True)
class ExpectedReceivableRecord:
    """
    Canonical ExpectedReceivableRecord representing pending inbound cash.
    Mapped to a logical invoice and counterparty.
    Strictly isolated from actual bank transactions and payment-matching logic.
    """
    receivable_id: str
    counterparty_ref: str
    invoice_id: str
    lifecycle_state: str
    idempotency_key: str
    source_ref: str
    expected_amount_minor_units: int
    currency_iso: str
    due_date_iso: str

    def __post_init__(self):
        if not self.receivable_id:
            raise ValueError("receivable_id is immutable and required")
        if not self.counterparty_ref:
            raise ValueError("counterparty_ref is required")
        if not self.invoice_id:
            raise ValueError("invoice_id is required")
        if not self.idempotency_key:
            raise ValueError("idempotency_key is required")
        if not self.source_ref:
            raise ValueError("source_ref is required")
        if not self.currency_iso:
            raise ValueError("currency_iso is required")
        if not self.due_date_iso:
            raise ValueError("due_date_iso is required")
            
        if self.lifecycle_state not in VALID_RECEIVABLE_LIFECYCLE_STATES:
            raise ValueError(f"Invalid lifecycle state: {self.lifecycle_state}")
            
        if not isinstance(self.expected_amount_minor_units, int):
            raise ValueError("expected_amount_minor_units must be an integer representing minor units (not floats)")
        if self.expected_amount_minor_units < 0:
            raise ValueError("expected_amount_minor_units cannot be negative")

def create_expected_receivable(
    counterparty_ref: str,
    invoice_id: str,
    idempotency_key: str,
    source_ref: str,
    expected_amount_minor_units: int,
    currency_iso: str,
    due_date_iso: str,
    lifecycle_state: str = "pending"
) -> ExpectedReceivableRecord:
    return ExpectedReceivableRecord(
        receivable_id=f"recv:{uuid.uuid4().hex}",
        counterparty_ref=counterparty_ref,
        invoice_id=invoice_id,
        lifecycle_state=lifecycle_state,
        idempotency_key=idempotency_key,
        source_ref=source_ref,
        expected_amount_minor_units=expected_amount_minor_units,
        currency_iso=currency_iso,
        due_date_iso=due_date_iso
    )
