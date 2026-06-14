import os
import sqlite3
import pytest
from business_ops_ledger import (
    init_business_ops_ledger,
    append_event,
    append_packet_receipt,
    append_capability_decision,
    append_retrieval_receipt,
    append_side_effect,
    append_operator_explanation,
    get_last_event_summary,
    get_packet_summary,
)

TEST_DB_PATH = "tests/test_ledger.sqlite"

@pytest.fixture
def clean_db():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    init_business_ops_ledger(TEST_DB_PATH)
    yield TEST_DB_PATH
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

def test_ledger_initialization(clean_db):
    assert os.path.exists(clean_db)
    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()

    # Check if all tables exist
    tables = [
        "events", "packets", "capability_decisions",
        "retrieval_receipts", "side_effects", "operator_explanations"
    ]
    for table in tables:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        assert cursor.fetchone() is not None
    conn.close()

def test_append_event(clean_db):
    success = append_event(
        event_id="evt_123",
        event_type="operator_query",
        actor="chief",
        operator_visible_summary="Test event",
        db_path=clean_db
    )
    assert success

    summary = get_last_event_summary(db_path=clean_db)
    assert summary == "Test event"

def test_append_packet_receipt(clean_db):
    packet = {
        "packet_id": "pkt_456",
        "intent_name": "monitored_email_conversation",
        "request_category": "email",
        "actor_name": "chief",
        "execution_authority": False,
        "approval_required": True,
        "action_status": "draft_only"
    }

    success = append_packet_receipt(packet, event_id="evt_123", db_path=clean_db)
    assert success

    summary = get_packet_summary("pkt_456", db_path=clean_db)
    assert summary["intent_name"] == "monitored_email_conversation"
    assert summary["approval_required"] is True
    assert summary["action_status"] == "draft_only"

def test_sensitive_data_default_false(clean_db):
    append_event("evt_789", "test", "actor", db_path=clean_db)

    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("SELECT raw_sensitive_data_stored FROM events WHERE event_id='evt_789'")
    val = cursor.fetchone()[0]
    assert val == 0
    conn.close()

def test_retrieval_receipt_blocked(clean_db):
    success = append_retrieval_receipt(
        packet_id="pkt_456",
        source="gmail",
        attempted=True,
        blocked=True,
        reason="policy_violation",
        db_path=clean_db
    )
    assert success

    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("SELECT blocked, reason FROM retrieval_receipts WHERE packet_id='pkt_456'")
    row = cursor.fetchone()
    assert row[0] == 1
    assert row[1] == "policy_violation"
    conn.close()

def test_side_effect_replay_safe_default(clean_db):
    side_effect_id = append_side_effect("pkt_456", "email_draft", "pending", db_path=clean_db)

    assert side_effect_id == "side_effect:1"

    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("SELECT replay_safe FROM side_effects WHERE packet_id='pkt_456'")
    val = cursor.fetchone()[0]
    assert val == 0
    conn.close()

def test_fail_open_on_bad_path():
    # Attempt to write to a path that should fail (e.g. a directory that doesn't exist)
    success = append_event("evt_fail", "test", "actor", db_path="/nonexistent/path/ledger.sqlite")
    # Should return False but not crash
    assert success is False
