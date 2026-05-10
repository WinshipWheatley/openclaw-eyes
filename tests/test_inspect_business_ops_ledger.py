import os
import sqlite3
import pytest
import subprocess
import json
from business_ops_ledger import init_business_ops_ledger, append_event

TEST_DB_PATH = "tests/test_inspect_ledger.sqlite"

@pytest.fixture
def clean_db():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    init_business_ops_ledger(TEST_DB_PATH)
    # Add some dummy data
    append_event("evt_1", "type_a", "actor_1", operator_visible_summary="Summary A", db_path=TEST_DB_PATH)
    append_event("evt_2", "type_b", "actor_2", operator_visible_summary="Summary B", db_path=TEST_DB_PATH)
    append_event("evt_3", "type_a", "actor_1", operator_visible_summary="Summary C", db_path=TEST_DB_PATH)
    yield TEST_DB_PATH
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

def test_cli_summary(clean_db):
    result = subprocess.run(
        ["python3", "scripts/inspect_business_ops_ledger.py", "--db", clean_db, "--summary"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "events" in result.stdout
    assert "type_a" in result.stdout
    assert "type_b" in result.stdout

def test_cli_json_summary(clean_db):
    result = subprocess.run(
        ["python3", "scripts/inspect_business_ops_ledger.py", "--db", clean_db, "--summary", "--json"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "summary" in data
    assert data["summary"]["tables"]["events"] == 3
    assert data["summary"]["event_types"]["type_a"] == 2

def test_cli_latest(clean_db):
    result = subprocess.run(
        ["python3", "scripts/inspect_business_ops_ledger.py", "--db", clean_db, "--latest", "2"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    # Should see 2 events
    assert "evt_3" in result.stdout
    assert "evt_2" in result.stdout
    assert "evt_1" not in result.stdout

def test_cli_event_type_filter(clean_db):
    result = subprocess.run(
        ["python3", "scripts/inspect_business_ops_ledger.py", "--db", clean_db, "--latest", "10", "--event-type", "type_b"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "type_b" in result.stdout
    assert "type_a" not in result.stdout

def test_cli_read_only_guarantee(clean_db):
    # Verify no new events are added by running inspection
    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM events")
    count_before = cursor.fetchone()[0]
    conn.close()

    subprocess.run(
        ["python3", "scripts/inspect_business_ops_ledger.py", "--db", clean_db, "--summary"],
        capture_output=True, text=True
    )

    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM events")
    count_after = cursor.fetchone()[0]
    conn.close()

    assert count_before == count_after
