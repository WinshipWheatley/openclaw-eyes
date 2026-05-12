import pytest
import sqlite3
import os
from scripts.backfill_truth_registry import backfill
from business_ops_ledger import init_business_ops_ledger

DB_PATH = "test_backfill.sqlite"

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_business_ops_ledger(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_backfill_idempotency():
    # First run
    stats1 = backfill(DB_PATH)
    assert stats1["inserted"] > 0
    assert stats1["skipped"] == 0
    
    # Second run
    stats2 = backfill(DB_PATH)
    assert stats2["inserted"] == 0
    assert stats2["skipped"] == stats1["inserted"]

def test_backfill_preserves_status():
    # Fill initially
    backfill(DB_PATH)
    
    # Manually upgrade one entry
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE truth_registry_entries SET truth_status = 'test_verified', verification_evidence_id = 'ev1' LIMIT 1")
    conn.commit()
    conn.close()
    
    # Rerun backfill
    backfill(DB_PATH)
    
    # Check preservation
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT truth_status, verification_evidence_id FROM truth_registry_entries WHERE truth_status = 'test_verified'").fetchone()
    assert row[0] == 'test_verified'
    assert row[1] == 'ev1'
    conn.close()
