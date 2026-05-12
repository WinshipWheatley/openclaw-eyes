import pytest
import sqlite3
import os
from scripts.resync_canonical_fact_truth import resync_canonical_facts
from business_ops_ledger import init_business_ops_ledger, record_truth_registry_entry, record_canonical_fact

DB_PATH = "test_resync.sqlite"

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_business_ops_ledger(DB_PATH)
    
    # Registry Entry
    record_truth_registry_entry(
        "s1", "path/1", "pc", "source", "public_canonical", "approved", "declared", True, True, 
        db_path=DB_PATH
    )
    
    # Canonical Fact (old status: declared)
    record_canonical_fact(
        "f1", "doc1.md", "h1", "commit1",
        "Fact text.", "public_canonical", ["OpenClaw"], "cat1", "doctrine", "desc",
        "s1", "declared", 1, None, db_path=DB_PATH
    )
    
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_dry_run_no_change():
    resync_canonical_facts(DB_PATH, dry_run=True)
    conn = sqlite3.connect(DB_PATH)
    fact = conn.execute("SELECT truth_status FROM canonical_facts WHERE fact_id = 'f1'").fetchone()
    assert fact[0] == "declared"
    conn.close()

def test_resync_success():
    # Update registry to test_verified
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE truth_registry_entries SET truth_status = 'test_verified', verification_evidence_id = 'ev1' WHERE source_id = 's1'")
    conn.commit()
    conn.close()
    
    resync_canonical_facts(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT truth_status, verification_required FROM canonical_facts WHERE fact_id = 'f1'").fetchone()
    assert row[0] == "test_verified"
    assert row[1] == 1
    conn.close()

def test_source_filter():
    resync_canonical_facts(DB_PATH, source="nonexistent.md")
    conn = sqlite3.connect(DB_PATH)
    status = conn.execute("SELECT truth_status FROM canonical_facts WHERE fact_id = 'f1'").fetchone()[0]
    assert status == "declared"
    conn.close()
