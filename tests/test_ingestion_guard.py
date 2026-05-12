import pytest
import sqlite3
import os
import subprocess
from business_ops_ledger import init_business_ops_ledger, record_truth_registry_entry

DB_PATH = "test_ingestion_guard.sqlite"
TEST_FILE = "docs/operations/OPENCLAW_PACKET_TO_RECEIPT_MAPPING_V0.md"

@pytest.fixture(autouse=True)
def cleanup():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def run_ingest(source=TEST_FILE):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    cmd = ["python3", "scripts/ingest_canonical_docs.py", "--db", DB_PATH, "--source", source]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return result

def get_fact_truth_status():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT truth_status, verification_required FROM canonical_facts LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row

def test_guard_hash_current_allows_verified():
    init_business_ops_ledger(DB_PATH)
    # Setup registry with current hash and test_verified status
    record_truth_registry_entry(
        source_id="test_id",
        observed_path=TEST_FILE,
        origin_machine="pc",
        sync_role="source",
        sensitivity_class="operational_canonical",
        approval_status="approved",
        truth_status="test_verified",
        verification_required=0,
        canonical_eligible=1,
        doc_type="receipt_mapping",
        verification_evidence_id="ev_123",
        db_path=DB_PATH
    )
    # Manually update hash_status to current
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE truth_registry_entries SET hash_status = 'current' WHERE source_id = 'test_id'")
    conn.commit()
    conn.close()

    result = run_ingest()
    assert result.returncode == 0
    
    status, req = get_fact_truth_status()
    assert status == "test_verified"
    assert req == 0

def test_guard_hash_changed_forces_stale():
    init_business_ops_ledger(DB_PATH)
    # Setup registry with changed hash status
    record_truth_registry_entry(
        source_id="test_id",
        observed_path=TEST_FILE,
        origin_machine="pc",
        sync_role="source",
        sensitivity_class="operational_canonical",
        approval_status="approved",
        truth_status="test_verified",
        verification_required=0,
        canonical_eligible=1,
        doc_type="receipt_mapping",
        verification_evidence_id="ev_123",
        db_path=DB_PATH
    )
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE truth_registry_entries SET hash_status = 'changed' WHERE source_id = 'test_id'")
    conn.commit()
    conn.close()

    result = run_ingest()
    assert result.returncode == 0
    
    status, req = get_fact_truth_status()
    assert status == "stale_possible"
    assert req == 1

def test_guard_hash_not_recorded_downgrades_verified():
    init_business_ops_ledger(DB_PATH)
    # Setup registry with not_recorded hash (default)
    record_truth_registry_entry(
        source_id="test_id",
        observed_path=TEST_FILE,
        origin_machine="pc",
        sync_role="source",
        sensitivity_class="operational_canonical",
        approval_status="approved",
        truth_status="runtime_verified",
        verification_required=0,
        canonical_eligible=1,
        doc_type="receipt_mapping",
        verification_evidence_id="ev_123",
        db_path=DB_PATH
    )

    result = run_ingest()
    assert result.returncode == 0
    
    status, req = get_fact_truth_status()
    assert status == "stale_possible"
    assert req == 1

def test_guard_hash_not_recorded_preserves_doctrine_reference():
    init_business_ops_ledger(DB_PATH)
    # Setup registry with not_recorded hash and doctrine_reference
    record_truth_registry_entry(
        source_id="test_id",
        observed_path=TEST_FILE,
        origin_machine="pc",
        sync_role="source",
        sensitivity_class="operational_canonical",
        approval_status="approved",
        truth_status="doctrine_reference",
        verification_required=0,
        canonical_eligible=1,
        doc_type="receipt_mapping",
        db_path=DB_PATH
    )

    result = run_ingest()
    assert result.returncode == 0
    
    status, req = get_fact_truth_status()
    assert status == "doctrine_reference"
    assert req == 0

def test_guard_no_registry_entry_uses_fallback():
    init_business_ops_ledger(DB_PATH)
    # No registry entry at all

    result = run_ingest()
    assert result.returncode == 0
    
    status, req = get_fact_truth_status()
    assert status == "declared"
    assert req == 1

def test_ingestion_does_not_mutate_registry_hash():
    init_business_ops_ledger(DB_PATH)
    record_truth_registry_entry(
        source_id="test_id",
        observed_path=TEST_FILE,
        origin_machine="pc",
        sync_role="source",
        sensitivity_class="operational_canonical",
        approval_status="approved",
        truth_status="test_verified",
        verification_required=0,
        canonical_eligible=1,
        doc_type="receipt_mapping",
        verification_evidence_id="ev_123",
        db_path=DB_PATH
    )
    
    # Run ingest
    run_ingest()
    
    # Check registry entry - hash_status should still be not_recorded (default)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT hash_status FROM truth_registry_entries WHERE source_id = 'test_id'")
    row = cursor.fetchone()
    conn.close()
    assert row[0] is None or row[0] == "not_recorded"
