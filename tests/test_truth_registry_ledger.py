import pytest
import sqlite3
import os
from business_ops_ledger import (
    init_business_ops_ledger, 
    record_truth_registry_entry, 
    record_verification_evidence,
    get_truth_registry_entry,
    get_truth_registry_entries_by_status,
    get_verification_evidence_for_source
)

DB_PATH = "/tmp/test_truth_registry.sqlite"

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_business_ops_ledger(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_truth_registry_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='truth_registry_entries'")
    assert cursor.fetchone() is not None
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='verification_evidence'")
    assert cursor.fetchone() is not None
    conn.close()

def test_valid_entries():
    # Declared entry
    assert record_truth_registry_entry(
        "s1", "path/a", "pc", "source", "public_canonical", 
        "candidate", "declared", True, False, db_path=DB_PATH
    )
    # Doctrine reference
    assert record_truth_registry_entry(
        "s2", "path/b", "pc", "source", "operational_canonical", 
        "approved", "doctrine_reference", False, True, db_path=DB_PATH
    )
    # Historical Checkpoint
    assert record_truth_registry_entry(
        "s3", "path/c", "pc", "source", "non_sensitive", 
        "approved", "historical_checkpoint", False, False, source_commit="abc123", db_path=DB_PATH
    )

def test_invalid_status_logic():
    # runtime_verified without evidence
    with pytest.raises(ValueError, match="requires verification_evidence_id"):
        record_truth_registry_entry(
            "s_fail", "path/fail", "pc", "source", "public_canonical", 
            "candidate", "runtime_verified", True, True, db_path=DB_PATH
        )
    # test_verified without evidence
    with pytest.raises(ValueError, match="requires verification_evidence_id"):
        record_truth_registry_entry(
            "s_fail2", "path/fail2", "pc", "source", "public_canonical", 
            "candidate", "test_verified", True, True, db_path=DB_PATH
        )

def test_verification_evidence():
    record_truth_registry_entry(
        "s4", "path/d", "pc", "source", "public_canonical", 
        "candidate", "runtime_verified", True, True, verification_source="test_log", db_path=DB_PATH
    )
    assert record_verification_evidence("ev1", "s4", "test_proof", "ref1", "summary", db_path=DB_PATH)
    
    evidence = get_verification_evidence_for_source("s4", db_path=DB_PATH)
    assert len(evidence) == 1
    assert evidence[0]["evidence_id"] == "ev1"

def test_get_by_status():
    record_truth_registry_entry(
        "s_stat1", "path/s1", "pc", "source", "public_canonical", 
        "approved", "declared", False, False, db_path=DB_PATH
    )
    entries = get_truth_registry_entries_by_status("declared", db_path=DB_PATH)
    assert len(entries) >= 1
    assert entries[0]["source_id"] == "s_stat1"
