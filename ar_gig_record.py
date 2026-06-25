from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid

VALID_GIG_LIFECYCLE_STATES = frozenset([
    "proposed",
    "active",
    "completed",
    "cancelled",
    "on_hold"
])

@dataclass(frozen=True)
class GigRecord:
    """
    Canonical GigRecord representing a contracted engagement.
    Strictly isolated from work sessions, invoices, and payment matching.
    """
    gig_id: str
    counterparty_ref: str
    counterparty_name: str
    lifecycle_state: str
    timezone: str
    billing_policy_ref: str
    idempotency_key: str
    
    # Optional scheduled window
    scheduled_start_iso: str | None = None
    scheduled_end_iso: str | None = None

    def __post_init__(self):
        if not self.gig_id:
            raise ValueError("gig_id is immutable and required")
        if not self.counterparty_ref or not self.counterparty_name:
            raise ValueError("counterparty reference and canonical name are required")
        if self.lifecycle_state not in VALID_GIG_LIFECYCLE_STATES:
            raise ValueError(f"Invalid lifecycle state: {self.lifecycle_state}")
        if not self.timezone:
            raise ValueError("Explicit timezone is required")
        if not self.idempotency_key:
            raise ValueError("Idempotency key is required to prevent duplicates")
            
        if self.scheduled_start_iso and self.scheduled_end_iso:
            try:
                start_dt = datetime.fromisoformat(self.scheduled_start_iso)
                end_dt = datetime.fromisoformat(self.scheduled_end_iso)
                if start_dt > end_dt:
                    raise ValueError("Scheduled start must be before or equal to scheduled end")
            except ValueError as e:
                raise ValueError(f"Invalid scheduled window: {e}")

def create_gig_record(
    counterparty_ref: str,
    counterparty_name: str,
    billing_policy_ref: str,
    idempotency_key: str,
    timezone: str = "UTC",
    lifecycle_state: str = "proposed",
    scheduled_start_iso: str | None = None,
    scheduled_end_iso: str | None = None,
) -> GigRecord:
    return GigRecord(
        gig_id=f"gig:{uuid.uuid4().hex}",
        counterparty_ref=counterparty_ref,
        counterparty_name=counterparty_name,
        lifecycle_state=lifecycle_state,
        timezone=timezone,
        billing_policy_ref=billing_policy_ref,
        idempotency_key=idempotency_key,
        scheduled_start_iso=scheduled_start_iso,
        scheduled_end_iso=scheduled_end_iso
    )
