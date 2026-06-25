import pytest
from ar_work_session_record import WorkSessionRecord, create_work_session

def test_work_session_initialization_success():
    session = create_work_session(
        gig_id="gig:123",
        worker_ref="operator:winship",
        idempotency_key="cmd_start_01",
        source_ref="event:456",
        start_utc_iso="2026-06-25T10:00:00+00:00",
        iana_timezone="America/New_York",
        lifecycle_state="active"
    )
    assert session.work_session_id.startswith("ws:")
    assert session.gig_id == "gig:123"
    assert session.worker_ref == "operator:winship"
    assert session.iana_timezone == "America/New_York"
    assert session.start_utc_iso == "2026-06-25T10:00:00+00:00"
    assert session.end_utc_iso is None
    assert session.lifecycle_state == "active"

def test_active_session_cannot_have_end_time():
    with pytest.raises(ValueError, match="Active sessions cannot have an end time"):
        create_work_session(
            gig_id="gig:123",
            worker_ref="op:w",
            idempotency_key="id_1",
            source_ref="src_1",
            start_utc_iso="2026-06-25T10:00:00+00:00",
            lifecycle_state="active",
            end_utc_iso="2026-06-25T11:00:00+00:00"
        )

def test_completed_session_must_have_end_time():
    with pytest.raises(ValueError, match="Completed sessions require an end time"):
        create_work_session(
            gig_id="gig:123",
            worker_ref="op:w",
            idempotency_key="id_1",
            source_ref="src_1",
            start_utc_iso="2026-06-25T10:00:00+00:00",
            lifecycle_state="completed",
            end_utc_iso=None
        )

def test_end_time_cannot_precede_start_time():
    with pytest.raises(ValueError, match="End time cannot precede start time"):
        create_work_session(
            gig_id="gig:123",
            worker_ref="op:w",
            idempotency_key="id_1",
            source_ref="src_1",
            start_utc_iso="2026-06-25T12:00:00+00:00",
            lifecycle_state="completed",
            end_utc_iso="2026-06-25T10:00:00+00:00"
        )

def test_work_session_missing_provenance():
    with pytest.raises(ValueError, match="idempotency_key is required"):
        WorkSessionRecord(
            work_session_id="ws:1",
            gig_id="gig:1",
            worker_ref="w:1",
            iana_timezone="UTC",
            idempotency_key="",
            source_ref="src:1",
            lifecycle_state="active",
            start_utc_iso="2026-06-25T10:00:00+00:00"
        )
        
    with pytest.raises(ValueError, match="source_ref is required for provenance"):
        WorkSessionRecord(
            work_session_id="ws:1",
            gig_id="gig:1",
            worker_ref="w:1",
            iana_timezone="UTC",
            idempotency_key="id_1",
            source_ref="",
            lifecycle_state="active",
            start_utc_iso="2026-06-25T10:00:00+00:00"
        )

def test_work_session_immutability():
    session = create_work_session(
        gig_id="gig:123",
        worker_ref="operator:winship",
        idempotency_key="cmd_start_01",
        source_ref="event:456",
        start_utc_iso="2026-06-25T10:00:00+00:00",
    )
    with pytest.raises(Exception): # frozen instance
        session.end_utc_iso = "2026-06-25T11:00:00+00:00"
