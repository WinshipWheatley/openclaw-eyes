import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from scripts.orientation_snapshot import get_orientation_snapshot, record_receipt
from business_ops_ledger import init_business_ops_ledger

TEST_DB_PATH = "tests/test_snapshot_receipt.sqlite"

@pytest.fixture
def clean_db():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    init_business_ops_ledger(TEST_DB_PATH)
    yield TEST_DB_PATH
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

@patch("scripts.orientation_snapshot.run_git_command")
@patch("os.path.exists")
def test_record_receipt_writes_to_ledger(mock_exists, mock_git, clean_db):
    # Setup mocks for snapshot generation
    mock_git.side_effect = lambda args: {
        "rev-parse --abbrev-ref HEAD": "test-branch",
        "rev-parse HEAD": "abcdef123456",
        "log -1 --oneline": "abcdef1 test commit",
        "status -s": ""
    }.get(" ".join(args), "")

    mock_exists.return_value = False # Documents don't exist in this mock

    snapshot = get_orientation_snapshot()
    
    # Record receipt
    success = record_receipt(snapshot, db_path=clean_db)
    assert success is True

    # Verify ledger entry
    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("SELECT event_type, actor, operator_visible_summary FROM events")
    row = cursor.fetchone()
    conn.close()

    assert row[0] == "orientation_snapshot"
    assert row[1] == "orientation_snapshot_v0"
    assert "branch:test-branch" in row[2]
    assert "head:abcdef12" in row[2]
    assert "status:Clean" in row[2]

def test_default_snapshot_does_not_record_receipt(clean_db):
    # We'll check that the events table is empty initially
    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM events")
    count_before = cursor.fetchone()[0]
    conn.close()
    assert count_before == 0

    # Running main without --record should NOT record anything
    # We'll mock get_orientation_snapshot to avoid git calls
    with patch("scripts.orientation_snapshot.get_orientation_snapshot") as mock_get:
        mock_get.return_value = {
            "where_are_we": {"git_branch": "main", "git_head": "123", "git_status": "Clean"},
            "active_lane": "test"
        }
        from scripts.orientation_snapshot import main
        with patch("sys.argv", ["scripts/orientation_snapshot.py"]):
            with patch("scripts.orientation_snapshot.render_markdown"):
                main()

    # Verify ledger entry is still empty
    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM events")
    count_after = cursor.fetchone()[0]
    conn.close()
    assert count_after == 0
