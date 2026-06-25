from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

VALID_RECEIVABLE_LIFECYCLE_STATES = frozenset([
    "open",
    "disputed",
    "satisfied",
    "written_off",
    "cancelled"
])

@dataclass(frozen=True)
class ExpectedReceivableRecord:
    """
    Canonical versioned ExpectedReceivableRecord representing a snapshot of pending inbound cash.
    """
    receivable_id: str
    receivable_version_id: str
    invoice_id: str
    invoice_version_id: str
    counterparty_ref: str
    lifecycle_state: str
    expected_minor_units: int
    currency_iso: str
    due_date_iso: str
    recognized_utc_iso: str
    idempotency_key: str
    source_ref: str
    
    # Optional fields
    supersedes_receivable_version_id: str | None = None
    resolution_ref: str | None = None

    def __post_init__(self):
        # 1. Check required fields
        if not self.receivable_id:
            raise ValueError("receivable_id is required")
        if not self.receivable_version_id:
            raise ValueError("receivable_version_id is required")
        if not self.invoice_id:
            raise ValueError("invoice_id is required")
        if not self.invoice_version_id:
            raise ValueError("invoice_version_id is required")
        if not self.counterparty_ref:
            raise ValueError("counterparty_ref is required")
        if not self.idempotency_key:
            raise ValueError("idempotency_key is required")
        if not self.source_ref:
            raise ValueError("source_ref is required")
            
        # 2. Lifecycle states
        if self.lifecycle_state not in VALID_RECEIVABLE_LIFECYCLE_STATES:
            raise ValueError(f"Invalid lifecycle state: {self.lifecycle_state}")
            
        if self.lifecycle_state in {"satisfied", "written_off", "cancelled"}:
            if not self.resolution_ref:
                raise ValueError(f"resolution_ref is required for terminal state '{self.lifecycle_state}'")

        # 3. Numeric constraints
        if type(self.expected_minor_units) is not int:
            raise ValueError("expected_minor_units must be an integer (not floats or booleans)")
        if self.expected_minor_units <= 0:
            raise ValueError("expected_minor_units must be positive")

        # 4. Currency
        if not self.currency_iso or not isinstance(self.currency_iso, str) or len(self.currency_iso) != 3 or not self.currency_iso.isupper():
            raise ValueError("currency_iso must be exactly three uppercase letters")

        # 5. Dates
        if not self.due_date_iso:
            raise ValueError("due_date_iso is required")
        if not self.recognized_utc_iso:
            raise ValueError("recognized_utc_iso is required")
            
        datetime.fromisoformat(self.due_date_iso)
        
        recognized_dt = datetime.fromisoformat(self.recognized_utc_iso)
        if recognized_dt.tzinfo is None or recognized_dt.tzinfo.utcoffset(recognized_dt) is None:
            raise ValueError("recognized_utc_iso must be timezone-aware")

def create_expected_receivable(
    invoice_id: str,
    invoice_version_id: str,
    counterparty_ref: str,
    expected_minor_units: int,
    currency_iso: str,
    due_date_iso: str,
    recognized_utc_iso: str,
    idempotency_key: str,
    source_ref: str,
    lifecycle_state: str = "open",
    receivable_id: str | None = None,
    supersedes_receivable_version_id: str | None = None,
    resolution_ref: str | None = None
) -> ExpectedReceivableRecord:
    if not receivable_id:
        receivable_id = f"recv:{uuid.uuid4().hex}"
        
    return ExpectedReceivableRecord(
        receivable_id=receivable_id,
        receivable_version_id=f"recv_ver:{uuid.uuid4().hex}",
        invoice_id=invoice_id,
        invoice_version_id=invoice_version_id,
        counterparty_ref=counterparty_ref,
        lifecycle_state=lifecycle_state,
        expected_minor_units=expected_minor_units,
        currency_iso=currency_iso,
        due_date_iso=due_date_iso,
        recognized_utc_iso=recognized_utc_iso,
        idempotency_key=idempotency_key,
        source_ref=source_ref,
        supersedes_receivable_version_id=supersedes_receivable_version_id,
        resolution_ref=resolution_ref
    )
