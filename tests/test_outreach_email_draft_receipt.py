import os
import sqlite3
import pytest
from business_ops_ledger import init_business_ops_ledger, record_outreach_email_draft_receipt

TEST_DB_PATH = "tests/test_outreach_ledger.sqlite"

@pytest.fixture
def clean_db():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    init_business_ops_ledger(db_path=TEST_DB_PATH)
    yield TEST_DB_PATH
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

def test_record_outreach_email_draft_receipt(clean_db):
    packet_id = "pkt_123"
    draft_id = "dft_abc"
    thread_id = "thr_xyz"
    intent = "outreach_demo_v1"
    
    success = record_outreach_email_draft_receipt(
        packet_id=packet_id,
        draft_id=draft_id,
        thread_id=thread_id,
        target_intent=intent,
        db_path=clean_db
    )
    assert success is True
    
    # Verify events
    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("SELECT event_type, operator_visible_summary FROM events WHERE event_type = 'outreach_email_draft_receipt'")
    event = cursor.fetchone()
    assert event is not None
    assert event[0] == "outreach_email_draft_receipt"
    assert intent in event[1]
    
    # Verify packet record
    cursor.execute("SELECT packet_json_safe FROM packets WHERE packet_id = ?", (packet_id,))
    row = cursor.fetchone()
    assert row is not None
    import json
    data = json.loads(row[0])
    assert data["packet_type"] == "outreach_email_draft_receipt"
    assert data["draft_id"] == draft_id
    assert data["draft_only"] is True
    assert data["sent_recorded"] is False
    assert data["execution_authority"] == 0
    assert data["send_authority"] == 0
    conn.close()
