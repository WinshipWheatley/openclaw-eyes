import pytest
import sqlite3
import os
from business_ops_ledger import (
    init_business_ops_ledger,
    record_approval_log_entry
)

@pytest.fixture
def clean_db(tmp_path):
    db_path = str(tmp_path / "ledger.sqlite")
    init_business_ops_ledger(db_path)
    return db_path

def test_record_approval_log_entry_safety(clean_db):
    """
    Verify that record_approval_log_entry writes correctly to SQLite 
    and adheres to the 'No Execution' truth boundary.
    """
    packet_id = "pkt_approval_123"
    packet_type = "chief.approval_decision_packet"
    verdict = "APPROVED"
    summary = "Approved outreach to Alice"
    approver = "Chief"

    success = record_approval_log_entry(
        packet_id=packet_id,
        packet_type=packet_type,
        approval_verdict=verdict,
        approval_summary=summary,
        approver_name=approver,
        db_path=clean_db
    )

    assert success is True

    # Verify event record
    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("SELECT event_type, actor, operator_visible_summary FROM events WHERE event_type = ?", ("approval_log_entry",))
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "approval_log_entry"
    assert row[1] == "Chief"
    assert row[2] == "APPROVED: Approved outreach to Alice"

    # Verify packet record (receipt)
    cursor.execute("SELECT packet_json_safe FROM packets WHERE packet_id = ?", (packet_id,))
    row = cursor.fetchone()
    assert row is not None
    import json
    payload = json.loads(row[0])
    
    assert payload["receipt_type"] == "approval_log_entry"
    assert payload["approval_verdict"] == verdict
    assert payload["approval_summary"] == summary
    assert payload["approver_name"] == approver
    assert payload["action_status"] == "approval_decision_recorded"
    
    # Boundary Check: No execution/mutation implied
    assert payload["execution_authority"] == 0
    assert payload["decision_record_only"] is True
    assert payload["execution_recorded"] is False
    assert payload["mutation_recorded"] is False
    assert payload["no_execution_recorded"] is True
    
    conn.close()

def test_record_approval_log_entry_with_request_id(clean_db):
    """Verify linking to a request_id works."""
    success = record_approval_log_entry(
        packet_id="pkt_456",
        packet_type="guardian.approval_decision_packet",
        approval_verdict="REJECTED",
        approval_summary="Risk too high",
        approver_name="Guardian",
        request_id="req_789",
        db_path=clean_db
    )
    assert success is True
    
    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("SELECT packet_json_safe FROM packets WHERE packet_id = ?", ("pkt_456",))
    payload = json.loads(cursor.fetchone()[0])
    assert payload["request_id"] == "req_789"
    conn.close()

import json
