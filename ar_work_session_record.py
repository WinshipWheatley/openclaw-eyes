from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

VALID_WORK_SESSION_LIFECYCLE_STATES = frozenset([
    "active",
    "paused",
    "completed",
    "cancelled"
])

@dataclass(frozen=True)
class WorkSessionRecord:
    """
    Canonical WorkSessionRecord representing a slice of tracked work.
    Isolated from billing rates, invoice materialization, and spreadsheet locations.
    """
    work_session_id: str
    gig_id: str
    worker_ref: str
    iana_timezone: str
    idempotency_key: str
    source_ref: str
    lifecycle_state: str
    
    # Canonical UTC timestamps
    start_utc_iso: str
    end_utc_iso: str | None = None
    
    # Optional correction pointer
    superseded_by_session_id: str | None = None

    def __post_init__(self):
        if not self.work_session_id:
            raise ValueError("work_session_id is immutable and required")
        if not self.gig_id:
            raise ValueError("gig_id is immutable and required")
        if not self.worker_ref:
            raise ValueError("worker_ref is required")
        if not self.iana_timezone:
            raise ValueError("IANA timezone is required")
        if not self.idempotency_key:
            raise ValueError("idempotency_key is required")
        if not self.source_ref:
            raise ValueError("source_ref is required for provenance")
        if self.lifecycle_state not in VALID_WORK_SESSION_LIFECYCLE_STATES:
            raise ValueError(f"Invalid lifecycle state: {self.lifecycle_state}")
            
        if not self.start_utc_iso:
            raise ValueError("start_utc_iso is required")

        # Invariant: Active sessions cannot have an end time
        if self.lifecycle_state == "active" and self.end_utc_iso is not None:
            raise ValueError("Active sessions cannot have an end time")

        # Invariant: Completed sessions require an end time
        if self.lifecycle_state == "completed" and self.end_utc_iso is None:
            raise ValueError("Completed sessions require an end time")

        if self.end_utc_iso:
            try:
                start_dt = datetime.fromisoformat(self.start_utc_iso)
                end_dt = datetime.fromisoformat(self.end_utc_iso)
                
                # Invariant: End time cannot precede start time
                if start_dt > end_dt:
                    raise ValueError("End time cannot precede start time")
            except ValueError as e:
                if "End time cannot precede start time" in str(e):
                    raise
                raise ValueError(f"Invalid timestamp formats: {e}")

def create_work_session(
    gig_id: str,
    worker_ref: str,
    idempotency_key: str,
    source_ref: str,
    start_utc_iso: str,
    iana_timezone: str = "UTC",
    lifecycle_state: str = "active",
    end_utc_iso: str | None = None,
    superseded_by_session_id: str | None = None
) -> WorkSessionRecord:
    return WorkSessionRecord(
        work_session_id=f"ws:{uuid.uuid4().hex}",
        gig_id=gig_id,
        worker_ref=worker_ref,
        iana_timezone=iana_timezone,
        idempotency_key=idempotency_key,
        source_ref=source_ref,
        lifecycle_state=lifecycle_state,
        start_utc_iso=start_utc_iso,
        end_utc_iso=end_utc_iso,
        superseded_by_session_id=superseded_by_session_id
    )
