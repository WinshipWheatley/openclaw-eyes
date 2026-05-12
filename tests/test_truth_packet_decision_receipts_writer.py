import pytest
import os
import sqlite3
import json
from business_ops_ledger import init_business_ops_ledger, append_truth_packet_decision_receipt

@pytest.fixture
def temp_ledger(tmp_path):
    db_path = str(tmp_path / "test_ledger.sqlite")
    init_business_ops_ledger(db_path)
    return db_path

def test_append_truth_packet_decision_receipt_basic(temp_ledger):
    success = append_truth_packet_decision_receipt(
        packet_status="MODEL_ALLOWED_VERIFIED",
        fact_id="fact-123",
        fact_text_crossed_model_boundary=True,
        db_path=temp_ledger
    )
    assert success is True

    # Verify content
    conn = sqlite3.connect(temp_ledger)
    cursor = conn.cursor()
    cursor.execute("SELECT packet_json_safe FROM packets")
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    payload = json.loads(row[0])
    assert payload["packet_status"] == "MODEL_ALLOWED_VERIFIED"
    assert payload["fact_id"] == "fact-123"
    assert payload["fact_text_crossed_model_boundary"] is True
    assert payload["fact_text_redacted_in_receipt"] is True
    assert payload["runtime_authority"] is False
    assert payload["execution_authority"] == 0
    assert payload["external_model_access_granted"] is False

def test_blocked_receipt_forces_boundary_false(temp_ledger):
    # Try to force it to true for a blocked packet
    success = append_truth_packet_decision_receipt(
        packet_status="MODEL_BLOCKED",
        fact_id="fact-blocked",
        fact_text_crossed_model_boundary=True,
        db_path=temp_ledger
    )
    assert success is True

    conn = sqlite3.connect(temp_ledger)
    cursor = conn.cursor()
    cursor.execute("SELECT packet_json_safe FROM packets")
    row = cursor.fetchone()
    conn.close()

    payload = json.loads(row[0])
    assert payload["packet_status"] == "MODEL_BLOCKED"
    # Safety rule: MODEL_BLOCKED must force fact_text_crossed_model_boundary=false.
    assert payload["fact_text_crossed_model_boundary"] is False

def test_redacts_fact_text_even_if_passed(temp_ledger):
    # Now raises ValueError instead of just popping
    with pytest.raises(ValueError) as excinfo:
        append_truth_packet_decision_receipt(
            packet_status="MODEL_ALLOWED_VERIFIED",
            fact_id="fact-123",
            fact_text="THIS SHOULD BE REDACTED",
            db_path=temp_ledger
        )
    assert "strictly forbidden" in str(excinfo.value)


def test_uncertain_status_can_be_true(temp_ledger):
    success = append_truth_packet_decision_receipt(
        packet_status="MODEL_ALLOWED_UNCERTAIN",
        fact_id="fact-uncertain",
        fact_text_crossed_model_boundary=True,
        db_path=temp_ledger
    )
    assert success is True

    conn = sqlite3.connect(temp_ledger)
    cursor = conn.cursor()
    cursor.execute("SELECT packet_json_safe FROM packets")
    row = cursor.fetchone()
    conn.close()

    payload = json.loads(row[0])
    assert payload["packet_status"] == "MODEL_ALLOWED_UNCERTAIN"
    assert payload["fact_text_crossed_model_boundary"] is True

def test_external_model_access_granted_true_is_rejected(temp_ledger):
    with pytest.raises(ValueError) as excinfo:
        append_truth_packet_decision_receipt(
            packet_status="MODEL_ALLOWED_VERIFIED",
            fact_id="fact-123",
            external_model_access_granted=True,
            db_path=temp_ledger
        )
    assert "external_model_access_granted" in str(excinfo.value)

    conn = sqlite3.connect(temp_ledger)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM packets")
    count = cursor.fetchone()[0]
    conn.close()

    assert count == 0


def test_external_model_access_granted_defaults_false(temp_ledger):
    success = append_truth_packet_decision_receipt(
        packet_status="MODEL_ALLOWED_VERIFIED",
        fact_id="fact-123",
        db_path=temp_ledger
    )
    assert success is True

    conn = sqlite3.connect(temp_ledger)
    cursor = conn.cursor()
    cursor.execute("SELECT packet_json_safe FROM packets")
    row = cursor.fetchone()
    conn.close()

    payload = json.loads(row[0])
    assert payload["external_model_access_granted"] is False

def test_rejects_unsafe_overrides(temp_ledger):
    unsafe_attempts = [
        {"runtime_authority": True},
        {"execution_authority": 1},
        {"fact_text": "Sensitive Info"},
        {"fact_text_redacted_in_receipt": False},
        {"sensitive_content_access": 1},
        {"vault_write_verified": True}
    ]
    
    for attempt in unsafe_attempts:
        with pytest.raises(ValueError) as excinfo:
            append_truth_packet_decision_receipt(
                packet_status="MODEL_ALLOWED_VERIFIED",
                fact_id="fact-123",
                db_path=temp_ledger,
                **attempt
            )
        assert "strictly forbidden" in str(excinfo.value)
