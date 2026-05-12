import pytest
import sqlite3
import os
import hashlib
import json
from scripts.truth_reconciliation_gateway import (
    build_llm_truth_packet,
    MODEL_ALLOWED_VERIFIED,
    MODEL_ALLOWED_UNCERTAIN,
    MODEL_BLOCKED
)
from business_ops_ledger import init_business_ops_ledger

def calculate_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

@pytest.fixture
def test_env(tmp_path, monkeypatch):
    db_path = tmp_path / "ledger.sqlite"
    receipt_db_path = tmp_path / "receipts.sqlite"
    source_file = tmp_path / "source.md"
    source_content = b"Some source content"
    source_file.write_bytes(source_content)
    source_hash = calculate_sha256(source_content)

    # Init both DBs
    init_business_ops_ledger(str(db_path))
    init_business_ops_ledger(str(receipt_db_path))

    conn = sqlite3.connect(db_path)
    # canonical_facts and truth_registry_entries are already created by init_business_ops_ledger
    
    # Valid setup
    conn.execute("""
        INSERT INTO canonical_facts (fact_id, source_file, section_heading, source_commit, content_hash, truth_source_id, truth_status, verification_required, fact_text, sensitivity_class, allowed_actors)
        VALUES ('f1', ?, 'Status', 'c1', 'h1', 's1', 'doctrine_reference', 0, 'fact text content', 'public_canonical', '["all"]')
    """, (str(source_file),))

    conn.execute("""
        INSERT INTO truth_registry_entries (source_id, observed_path, source_content_hash, hash_status, truth_status, verification_required, sensitivity_class, approval_status, origin_machine, sync_role, canonical_eligible)
        VALUES ('s1', ?, ?, 'current', 'doctrine_reference', 0, 'public_canonical', 'approved', 'pc', 'source', 1)
    """, (str(source_file), source_hash))

    conn.commit()
    conn.close()

    monkeypatch.setattr("scripts.truth_reconciliation_gateway.SOURCE_REGISTRY", {str(source_file): {}})

    return {
        "db_path": str(db_path),
        "receipt_db_path": str(receipt_db_path),
        "source_file": source_file,
        "source_hash": source_hash,
        "fact_id": "f1",
        "source_id": "s1"
    }

def test_build_packet_no_receipt_by_default(test_env):
    # build_llm_truth_packet default is record_receipt=False
    build_llm_truth_packet(test_env["db_path"], test_env["fact_id"])

    conn = sqlite3.connect(test_env["db_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM events WHERE event_type = 'truth_packet_decision_receipt'")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 0

def test_build_packet_verified_records_receipt(test_env):
    # record_receipt=True
    build_llm_truth_packet(
        test_env["db_path"], 
        test_env["fact_id"], 
        question="How many?",
        record_receipt=True, 
        receipt_db_path=test_env["receipt_db_path"]
    )

    conn = sqlite3.connect(test_env["receipt_db_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT packet_json_safe FROM packets")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) > 0
    # Filter for the right receipt type
    payload = None
    for row in rows:
        p = json.loads(row[0])
        if p.get("receipt_type") == "truth_packet_decision_receipt":
            payload = p
            break
    
    assert payload is not None
    assert payload["packet_status"] == MODEL_ALLOWED_VERIFIED
    assert payload["fact_id"] == "f1"
    assert payload["question"] == "How many?"
    assert payload["fact_text_crossed_model_boundary"] is True
    assert "fact_text" not in payload
    assert payload["fact_text_redacted_in_receipt"] is True
    assert payload["external_model_access_granted"] is False

def test_build_packet_uncertain_records_receipt(test_env):
    # Set verification_required=1 and no evidence to make it uncertain
    conn = sqlite3.connect(test_env["db_path"])
    conn.execute("UPDATE canonical_facts SET verification_required = 1 WHERE fact_id = 'f1'")
    conn.commit()
    conn.close()

    build_llm_truth_packet(
        test_env["db_path"], 
        test_env["fact_id"], 
        record_receipt=True, 
        receipt_db_path=test_env["receipt_db_path"]
    )

    conn = sqlite3.connect(test_env["receipt_db_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT packet_json_safe FROM packets")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) > 0
    payload = None
    for row in rows:
        p = json.loads(row[0])
        if p.get("receipt_type") == "truth_packet_decision_receipt":
            payload = p
            break
    
    assert payload is not None
    assert payload["packet_status"] == MODEL_ALLOWED_UNCERTAIN
    assert payload["uncertainty_status"] == "verification_required_no_evidence"
    assert payload["confidence_band"] == "medium_provisional"
    assert payload["fact_text_crossed_model_boundary"] is True
    assert "fact_text" not in payload
    assert payload["external_model_access_granted"] is False

def test_build_packet_blocked_records_receipt(test_env):
    # Cause a mismatch
    test_env["source_file"].write_bytes(b"Mismatch")

    build_llm_truth_packet(
        test_env["db_path"], 
        test_env["fact_id"], 
        record_receipt=True, 
        receipt_db_path=test_env["receipt_db_path"]
    )

    conn = sqlite3.connect(test_env["receipt_db_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT packet_json_safe FROM packets")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) > 0
    payload = None
    for row in rows:
        p = json.loads(row[0])
        if p.get("receipt_type") == "truth_packet_decision_receipt":
            payload = p
            break
    
    assert payload is not None
    assert payload["packet_status"] == MODEL_BLOCKED
    assert payload["block_reason"] is not None
    assert payload["fact_text_crossed_model_boundary"] is False
    assert "fact_text" not in payload
    assert payload["external_model_access_granted"] is False

def test_repaired_uncertain_receipt_uses_refreshed_hash_status(test_env):
    conn = sqlite3.connect(test_env["db_path"])
    conn.execute("UPDATE truth_registry_entries SET hash_status = 'changed' WHERE source_id = 's1'")
    conn.execute("UPDATE canonical_facts SET verification_required = 1 WHERE fact_id = 'f1'")
    conn.commit()
    conn.close()

    packet = build_llm_truth_packet(
        test_env["db_path"],
        test_env["fact_id"],
        allow_reconciliation=True,
        record_receipt=True,
        receipt_db_path=test_env["receipt_db_path"]
    )

    assert packet["status"] == MODEL_ALLOWED_UNCERTAIN
    assert packet["source_content_hash_status"] == "current"

    conn = sqlite3.connect(test_env["receipt_db_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT packet_json_safe FROM packets")
    rows = cursor.fetchall()
    conn.close()

    payload = None
    for row in rows:
        p = json.loads(row[0])
        if p.get("receipt_type") == "truth_packet_decision_receipt":
            payload = p
            break

    assert payload is not None
    assert payload["packet_status"] == MODEL_ALLOWED_UNCERTAIN
    assert payload["source_content_hash_status"] == "current"
    assert payload["external_model_access_granted"] is False
    assert "fact_text" not in payload

def test_receipt_logging_does_not_change_status(test_env):
    # record_receipt=False
    res_no = build_llm_truth_packet(test_env["db_path"], test_env["fact_id"], record_receipt=False)
    
    # record_receipt=True
    res_yes = build_llm_truth_packet(
        test_env["db_path"], 
        test_env["fact_id"], 
        record_receipt=True, 
        receipt_db_path=test_env["receipt_db_path"]
    )

    # Status and core content should be identical
    assert res_no["status"] == res_yes["status"]
    assert res_no["transitions"] == res_yes["transitions"]
    if "verified_facts" in res_no:
        assert res_no["verified_facts"][0]["text"] == res_yes["verified_facts"][0]["text"]
