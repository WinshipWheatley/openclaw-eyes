import pytest
import sqlite3
import os
import subprocess
from scripts.inventory_scanner import scan_root

DB_PATH = "/tmp/test_report.sqlite"

@pytest.fixture(autouse=True)
def cleanup():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_generate_report_basic():
    scan_root("test_fixture_01", db_path=DB_PATH, confirm_real_root=False)
    
    result = subprocess.run(
        ["python3", "scripts/generate_inventory_report.py", "--db", DB_PATH, "--root-id", "test_fixture_01"],
        capture_output=True, text=True
    )
    
    assert "--- Inventory Report for test_fixture_01 ---" in result.stdout
    assert "Total Files: 4" in result.stdout
    assert ".txt: 2" in result.stdout
    assert "[BOUNDARY NOTE: Metadata only. No file contents read. No hashes computed.]" in result.stdout

def test_generate_report_empty():
    # Create empty DB
    from business_ops_ledger import init_business_ops_ledger
    init_business_ops_ledger(DB_PATH)
    
    result = subprocess.run(
        ["python3", "scripts/generate_inventory_report.py", "--db", DB_PATH, "--root-id", "nonexistent"],
        capture_output=True, text=True
    )
    
    assert "No records found." in result.stdout
