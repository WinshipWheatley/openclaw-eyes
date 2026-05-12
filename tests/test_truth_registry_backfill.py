import pytest
import os
from scripts.backfill_truth_registry import backfill
from business_ops_ledger import init_business_ops_ledger, get_truth_registry_entry

DB_PATH = "/tmp/test_backfill.sqlite"

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_business_ops_ledger(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_backfill_dry_run():
    entries = backfill(DB_PATH, dry_run=True)
    assert len(entries) > 0
    assert get_truth_registry_entry(entries[0]["source_id"], db_path=DB_PATH) is None

def test_backfill_execution():
    entries = backfill(DB_PATH, dry_run=False)
    assert len(entries) > 0
    
    # Check one entry
    first = entries[0]
    entry = get_truth_registry_entry(first["source_id"], db_path=DB_PATH)
    assert entry is not None
    assert entry["approval_status"] == "approved"
    assert entry["truth_status"] in ["historical_checkpoint", "doctrine_reference"]
    assert entry["verification_required"] == 1

def test_idempotency():
    # Should work without error on second run due to REPLACE
    entries1 = backfill(DB_PATH, dry_run=False)
    entries2 = backfill(DB_PATH, dry_run=False)
    assert len(entries2) == len(entries1)
    
    # Check if entries exist
    assert get_truth_registry_entry(entries2[0]["source_id"], db_path=DB_PATH) is not None

def test_status_mapping():
    entries = backfill(DB_PATH, dry_run=True)
    for e in entries:
        assert e["truth_status"] != "runtime_verified"
        assert e["truth_status"] != "test_verified"
