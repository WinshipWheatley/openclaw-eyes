import os
import sqlite3
import json
import pytest
from pathlib import Path
from business_ops_ledger import (
    init_business_ops_ledger,
    record_action_intent_gate_receipt
)

@pytest.fixture
def clean_db(tmp_path):
    db_path = str(tmp_path / "test_ledger.sqlite")
    init_business_ops_ledger(db_path)
    return db_path

def test_record_action_intent_gate_receipt_hardening(clean_db):
    packet_id = "test-packet-123"
    packet_type = "agent.action_intent_packet"
    gate_result = "PASS"
    evaluation_summary = "Test evaluation summary"
    
    success = record_action_intent_gate_receipt(
        packet_id=packet_id,
        packet_type=packet_type,
        gate_result=gate_result,
        evaluation_summary=evaluation_summary,
        db_path=clean_db,
        risk_tier="T1",
        approval_required=1
    )
    
    assert success is True
    
    # Verify in DB
    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    
    # Check event
    cursor.execute("SELECT event_type FROM events WHERE event_type = ?", ("action_intent_gate_receipt",))
    event = cursor.fetchone()
    assert event is not None
    
    # Check packet
    cursor.execute("""
        SELECT packet_id, execution_authority, approval_required, action_status, packet_json_safe 
        FROM packets WHERE packet_id = ?
    """, (packet_id,))
    packet = cursor.fetchone()
    assert packet is not None
    
    # 1. execution_authority == 0 (HARD MANDATE)
    assert packet[1] == 0
    
    # 2. approval_required is present
    assert packet[2] == 1
    
    # 3. action_status starts with gate_ and DOES NOT imply completion/success
    status = packet[3]
    assert status.startswith("gate_")
    assert "success" not in status.lower()
    assert "completed" not in status.lower()
    assert "executed" not in status.lower()
    assert "approved" not in status.lower()
    
    # 4. JSON payload must include guardrails
    payload = json.loads(packet[4])
    assert payload.get("no_execution_without_approval") is True
    assert payload.get("execution_authority") == 0
    assert payload.get("gate_result") == "PASS"
    
    conn.close()

def test_record_action_intent_gate_receipt_fail_case_hardening(clean_db):
    # Explicitly verify it records NO execution even on failure
    success = record_action_intent_gate_receipt(
        packet_id="p-999",
        packet_type="agent.action_intent_packet",
        gate_result="FAIL",
        evaluation_summary="Failed gate",
        db_path=clean_db
    )
    assert success is True
    
    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("SELECT execution_authority, action_status, packet_json_safe FROM packets WHERE packet_id = 'p-999'")
    row = cursor.fetchone()
    
    assert row[0] == 0
    assert row[1] == "gate_FAIL"
    
    payload = json.loads(row[2])
    assert payload.get("no_execution_without_approval") is True
    assert payload.get("gate_result") == "FAIL"
    
    conn.close()
