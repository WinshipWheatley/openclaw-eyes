import pytest
import sqlite3
import os
import json
import subprocess
from business_ops_ledger import init_business_ops_ledger, record_file_inventory_entry

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "inventory.sqlite"
    init_business_ops_ledger(str(db_path))
    
    # Add dummy data
    record_file_inventory_entry(
        "id1", "root1", None, "/abs/path/1", "rel/path/1", "file1.txt", 
        ".txt", "text", 100, "2026-05-11", None, "low", "eligible_metadata_only", None, 
        db_path=str(db_path)
    )
    record_file_inventory_entry(
        "id2", "root2", None, "/abs/path/2", "rel/path/2", "file2.json", 
        ".json", "data", 200, "2026-05-11", None, "low", "eligible_metadata_only", None, 
        db_path=str(db_path)
    )
    return str(db_path)

def test_cli_requires_db():
    result = subprocess.run(["python3", "scripts/query_file_inventory.py", "--root-id", "root1"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "the following arguments are required: --db" in result.stderr

def test_cli_requires_filter():
    result = subprocess.run(["python3", "scripts/query_file_inventory.py", "--db", "nonexistent.db"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "one of the arguments --root-id --extension --file-name is required" in result.stderr

def test_query_by_root_id(temp_db):
    result = subprocess.run(["python3", "scripts/query_file_inventory.py", "--db", temp_db, "--root-id", "root1"], capture_output=True, text=True)
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["file_name"] == "file1.txt"

def test_query_by_extension(temp_db):
    result = subprocess.run(["python3", "scripts/query_file_inventory.py", "--db", temp_db, "--extension", ".json"], capture_output=True, text=True)
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["file_name"] == "file2.json"

def test_query_by_name(temp_db):
    result = subprocess.run(["python3", "scripts/query_file_inventory.py", "--db", temp_db, "--file-name", "file1.txt"], capture_output=True, text=True)
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["file_name"] == "file1.txt"

def test_missing_db_fails(tmp_path):
    db_path = str(tmp_path / "missing.db")
    result = subprocess.run(["python3", "scripts/query_file_inventory.py", "--db", db_path, "--root-id", "root1"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "Error: Database not found" in result.stderr
