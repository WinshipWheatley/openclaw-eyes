import pytest
import os
import subprocess
import json
from business_ops_ledger import init_business_ops_ledger, record_truth_registry_entry

DB_PATH = "/tmp/test_query_truth.sqlite"

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_business_ops_ledger(DB_PATH)
    record_truth_registry_entry("s1", "a.md", "pc", "source", "public", "approved", "declared", True, True, doc_type="test", db_path=DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_query_filters():
    # truth_status
    res = subprocess.run(["python3", "scripts/query_truth_registry.py", "--db", DB_PATH, "--truth-status", "declared"], capture_output=True, text=True)
    assert len(json.loads(res.stdout)) == 1
    
    # doc_type
    res = subprocess.run(["python3", "scripts/query_truth_registry.py", "--db", DB_PATH, "--doc-type", "test"], capture_output=True, text=True)
    assert len(json.loads(res.stdout)) == 1

    # requires-verification
    res = subprocess.run(["python3", "scripts/query_truth_registry.py", "--db", DB_PATH, "--requires-verification"], capture_output=True, text=True)
    assert len(json.loads(res.stdout)) == 1

def test_no_filter_fails():
    res = subprocess.run(["python3", "scripts/query_truth_registry.py", "--db", DB_PATH], capture_output=True, text=True)
    assert res.returncode != 0
