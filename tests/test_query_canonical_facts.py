import pytest
import sqlite3
import os
import json
import subprocess
from business_ops_ledger import init_business_ops_ledger, record_canonical_fact

DB_PATH = "test_query.sqlite"

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_business_ops_ledger(DB_PATH)
    record_canonical_fact(
        "f1", "doc1.md", "Header1", "commit1", 
        "Fact text 1", "public_canonical", ["agent1"], "cat1", "doc1", "desc1", None, "declared", 1, None, DB_PATH
    )
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def run_query(args):
    cmd = ["python3", "scripts/query_canonical_facts.py", "--db", DB_PATH] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result

def test_cli_requires_db():
    result = subprocess.run(["python3", "scripts/query_canonical_facts.py", "--source", "doc1.md"], capture_output=True, text=True)
    assert result.returncode != 0

def test_query_by_source():
    result = run_query(["--source", "doc1.md"])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["source_file"] == "doc1.md"
    assert "fact_text" in data[0]

def test_query_by_heading():
    result = run_query(["--heading", "Header1"])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["section_heading"] == "Header1"

def test_no_filter_fails():
    result = run_query([])
    assert result.returncode != 0
    data = json.loads(result.stdout)
    assert "error" in data

def test_missing_db_fails():
    cmd = ["python3", "scripts/query_canonical_facts.py", "--db", "nonexistent.sqlite", "--source", "doc1.md"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    data = json.loads(result.stdout)
    assert "error" in data
