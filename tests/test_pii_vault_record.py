import sqlite3
import pytest
import os
import json
from business_ops_ledger import init_business_ops_ledger, record_pii_vault_receipt

TEST_DB_PATH = ".openclaw/business_ops/test_pii_vault_ledger.sqlite"

@pytest.fixture
def clean_db():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    init_business_ops_ledger(db_path=TEST_DB_PATH)
    yield TEST_DB_PATH
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

def test_record_pii_vault_receipt_success(clean_db):
    packet_id = "p-123"
    token_mapping_id = "vault_map_456"
    target_intent = "anonymizing customer email"

    success = record_pii_vault_receipt(
        packet_id=packet_id,
        token_mapping_id=token_mapping_id,
        target_intent=target_intent,
        db_path=clean_db
    )
    assert success is True

    # Check Events Table
    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("SELECT event_type, operator_visible_summary FROM events")
    event_row = cursor.fetchone()
    assert event_row is not None
    event_type, summary = event_row
    assert event_type == "pii_vault_record"
    assert "Vault reference recorded for: anonymizing customer email" in summary
    assert "(Redacted Metadata Only)" in summary

    # Check Packets Table
    cursor.execute("SELECT packet_id, execution_authority, action_status, packet_json_safe FROM packets")
    packet_row = cursor.fetchone()
    conn.close()

    assert packet_row is not None
    db_packet_id, exec_auth, action_status, packet_json_safe = packet_row
    assert db_packet_id == packet_id
    assert exec_auth == 0
    assert action_status == "redacted_metadata_recorded"

    data = json.loads(packet_json_safe)
    assert data["packet_type"] == "pii_vault_record"
    assert data["token_mapping_id"] == token_mapping_id
    assert data["redacted_metadata_only"] is True
    assert data["raw_pii_stored"] is False
    assert data["vault_write_verified"] is False
    assert data["external_model_access_granted"] is False
    assert data["sensitive_content_access"] == 0
    assert data["execution_authority"] == 0

def test_record_pii_vault_receipt_rejects_unsafe_keys(clean_db):
    unsafe_keys = [
        "raw_text", "pii_text", "email_body", "message_body",
        "prompt_body", "sensitive_content", "unredacted_text",
        "original_text", "recipient_email", "phone_number",
        "ssn", "address"
    ]

    for key in unsafe_keys:
        kwargs = {key: "some value"}
        with pytest.raises(ValueError, match=f"Unsafe key '{key}' is strictly forbidden"):
            record_pii_vault_receipt(
                packet_id="p-999",
                token_mapping_id="vault_map_789",
                target_intent="test failure",
                db_path=clean_db,
                **kwargs
            )
