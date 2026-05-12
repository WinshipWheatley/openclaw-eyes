import pytest
import sqlite3
import os
from scripts.attach_verification_evidence import attach_evidence
from business_ops_ledger import init_business_ops_ledger, record_truth_registry_entry, get_truth_registry_entry

DB_PATH = "test_attach_evidence.sqlite"

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_business_ops_ledger(DB_PATH)
    record_truth_registry_entry(
        "s1", "path/1", "pc", "source", "public_canonical", "approved", "declared", True, True, 
        db_path=DB_PATH
    )
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_attach_evidence_no_status_change():
    success = attach_evidence(DB_PATH, "s1", "manual_review", "ref1", "summary1")
    assert success
    entry = get_truth_registry_entry("s1", DB_PATH)
    assert entry["truth_status"] == "declared"

def test_upgrade_test_verified():
    success = attach_evidence(DB_PATH, "s1", "test_proof", "ref2", "summary2", target_truth_status="test_verified")
    assert success
    entry = get_truth_registry_entry("s1", DB_PATH)
    assert entry["truth_status"] == "test_verified"

def test_upgrade_runtime_verified():
    success = attach_evidence(DB_PATH, "s1", "runtime_receipt", "ref3", "summary3", target_truth_status="runtime_verified")
    assert success
    entry = get_truth_registry_entry("s1", DB_PATH)
    assert entry["truth_status"] == "runtime_verified"

def test_invalid_upgrade_manual_to_runtime():
    success = attach_evidence(DB_PATH, "s1", "manual_review", "ref4", "summary4", target_truth_status="runtime_verified")
    assert not success

def test_missing_source_id():
    success = attach_evidence(DB_PATH, "s999", "test_proof", "ref5", "summary5")
    assert not success
