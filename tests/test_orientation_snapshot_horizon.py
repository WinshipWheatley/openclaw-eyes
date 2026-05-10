import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from scripts.orientation_snapshot import get_horizon, get_orientation_snapshot
from business_ops_ledger import init_business_ops_ledger, append_event

TEST_DB_PATH = "tests/test_horizon.sqlite"

@pytest.fixture
def clean_db():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    init_business_ops_ledger(TEST_DB_PATH)
    yield TEST_DB_PATH
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

def test_get_horizon_no_receipt():
    ledger_info = {"has_snapshot_receipt": False}
    horizon = get_horizon(ledger_info)
    
    moves = horizon["visible_moves"]
    assert "Optionally record snapshot summaries to SQLite Ledger" in moves
    
    from scripts.orientation_snapshot import get_next_safe_move
    next_move = get_next_safe_move(ledger_info)
    assert "record snapshot summaries to SQLite Ledger" in next_move

def test_get_horizon_with_receipt():
    ledger_info = {"has_snapshot_receipt": True}
    horizon = get_horizon(ledger_info)
    
    moves = horizon["visible_moves"]
    assert "Optionally record snapshot summaries to SQLite Ledger" not in moves
    
    from scripts.orientation_snapshot import get_next_safe_move
    next_move = get_next_safe_move(ledger_info)
    assert "record snapshot summaries to SQLite Ledger" not in next_move
    assert "prototyping generated CURRENT_STATE / NEXT_ACTIONS read-model" in next_move

@patch("scripts.orientation_snapshot.run_git_command")
@patch("os.path.exists")
@patch("scripts.orientation_snapshot.LEDGER_DB_PATH", TEST_DB_PATH)
def test_get_orientation_snapshot_horizon_integration(mock_exists, mock_git, clean_db):
    # 1. Test without receipt
    mock_git.return_value = "main"
    mock_exists.side_effect = lambda path: path == TEST_DB_PATH
    
    snapshot = get_orientation_snapshot()
    assert "Optionally record snapshot summaries to SQLite Ledger" in snapshot["visible_road_horizon"]["visible_moves"]
    
    # 2. Add receipt to DB
    append_event(
        event_id="os_123",
        event_type="orientation_snapshot_receipt",
        actor="test",
        db_path=TEST_DB_PATH
    )
    
    snapshot = get_orientation_snapshot()
    assert "Optionally record snapshot summaries to SQLite Ledger" not in snapshot["visible_road_horizon"]["visible_moves"]

def test_horizon_does_not_claim_runtime_health():
    ledger_info = {"has_snapshot_receipt": True}
    horizon = get_horizon(ledger_info)
    # Check that visible moves don't mention "live runtime health" or similar claims
    for move in horizon["visible_moves"]:
        assert "live" not in move.lower()
        assert "health" not in move.lower()
