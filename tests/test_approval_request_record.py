import os
import sqlite3
import json
import pytest
from business_ops_ledger import init_business_ops_ledger, record_approval_request_record

@pytest.fixture
def temp_db(tmp_path):
    db_path = str(tmp_path / "test_ledger.sqlite")
    init_business_ops_ledger(db_path)
    return db_path

def test_record_approval_request_record_success(temp_db):
    packet_id = "test_packet_123"
    packet_type = "guardian.approval_request_packet"
    approval_id = "app_abc_456"
    summary = "Requesting approval for album creation"
    agent = "Chief"

    success = record_approval_request_record(
        packet_id=packet_id,
        packet_type=packet_type,
        approval_id=approval_id,
        approval_request_summary=summary,
        requester_agent=agent,
        action_intent_ref="aig_789",
        risk_tier="Tier 2",
        db_path=temp_db
    )

    assert success is True

    # Verify SQLite event
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT event_type, actor, operator_visible_summary FROM events")
    event = cursor.fetchone()
    assert event[0] == "approval_request_record"
    assert event[1] == agent
    assert event[2] == summary

    # Verify SQLite packet
    cursor.execute("SELECT packet_id, intent_name, action_status, execution_authority, packet_json_safe FROM packets")
    packet = cursor.fetchone()
    assert packet[0] == packet_id
    assert packet[1] == packet_type
    assert packet[2] == "approval_request_recorded"
    assert packet[3] == 0  # No execution authority

    # Verify JSON content safety
    p_json = json.loads(packet[4])
    assert p_json["receipt_type"] == "approval_request_record"
    assert p_json["decision_status"] == "no_decision_recorded"
    assert p_json["decision_recorded"] is False
    assert p_json["execution_recorded"] is False
    assert p_json["no_execution_recorded"] is True
    assert p_json["approval_id"] == approval_id
    assert p_json["action_intent_ref"] == "aig_789"
    assert p_json["risk_tier"] == "Tier 2"

    conn.close()
