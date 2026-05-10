import os
import pytest
import sys
from unittest.mock import patch, MagicMock
from scripts.generate_operator_status import generate_current_state, generate_next_actions

@pytest.fixture
def mock_snapshot():
    return {
        "timestamp": "2026-05-10T10:00:00",
        "where_are_we": {
            "git_head": "0de27a6f",
            "git_branch": "main",
            "git_status": "Clean"
        },
        "ledger_info": {
            "status": "active",
            "event_count": 2,
            "has_snapshot_receipt": True
        },
        "confirmed_current": [
            "Git HEAD: 0de27a6 feat(operator)",
            "Ledger Status: active (2 events)",
            "Active Handoff: context"
        ],
        "active_lane": "Hardening the spine.",
        "allowed_tools": "Reading files.",
        "forbidden_surfaces": "Secrets.",
        "north_star": "Lighter life.",
        "next_safe_move": "Next move.",
        "visible_road_horizon": {
            "visible_moves": ["Move 1", "Move 2"],
            "branch_after": "Proof",
            "unsafe_beyond": "Unsafe"
        }
    }

def test_generate_current_state(mock_snapshot):
    output = generate_current_state(mock_snapshot)
    assert "# GENERATED CURRENT STATE" in output
    # Volatile metadata should NOT be in the output string
    assert "2026-05-10T10:00:00" not in output
    assert "0de27a6f" not in output
    assert "Hardening the spine." in output
    assert "Lighter life." in output
    assert "Runtime Health" in output

def test_generate_next_actions(mock_snapshot):
    output = generate_next_actions(mock_snapshot)
    assert "# GENERATED NEXT ACTIONS" in output
    assert "Next move." in output
    assert "Move 1" in output
    assert "Move 2" in output
    assert "[DONE] Orientation Snapshot Receipt recorded to Ledger" in output
    assert "Unsafe" in output

def test_generate_next_actions_no_receipt(mock_snapshot):
    mock_snapshot["ledger_info"]["has_snapshot_receipt"] = False
    output = generate_next_actions(mock_snapshot)
    assert "[TODO] Record initial Orientation Snapshot Receipt" in output

@patch("scripts.generate_operator_status.get_orientation_snapshot")
@patch("scripts.generate_operator_status.open", new_callable=MagicMock)
@patch("argparse.ArgumentParser.parse_args")
def test_main_write(mock_args, mock_open, mock_get, mock_snapshot):
    from scripts.generate_operator_status import main
    mock_get.return_value = mock_snapshot
    mock_args.return_value = MagicMock(write=True, check=False)

    main()

    assert mock_open.call_count == 2
    mock_open.assert_any_call("Operator/GENERATED_CURRENT_STATE.md", "w")
    mock_open.assert_any_call("Operator/GENERATED_NEXT_ACTIONS.md", "w")

@patch("scripts.generate_operator_status.get_orientation_snapshot")
@patch("os.path.exists")
@patch("scripts.generate_operator_status.open", new_callable=MagicMock)
@patch("argparse.ArgumentParser.parse_args")
def test_main_check_ok(mock_args, mock_open, mock_exists, mock_get, mock_snapshot):
    from scripts.generate_operator_status import main, generate_current_state, generate_next_actions, DISCLAIMER
    mock_get.return_value = mock_snapshot
    mock_args.return_value = MagicMock(write=False, check=True)
    mock_exists.return_value = True

    curr_content = DISCLAIMER + "\n" + generate_current_state(mock_snapshot)
    next_content = DISCLAIMER + "\n" + generate_next_actions(mock_snapshot)

    # Mock reading the files
    mock_open.return_value.__enter__.return_value.read.side_effect = [curr_content, next_content]

    with patch("sys.exit") as mock_exit:
        main()
        mock_exit.assert_not_called()

@patch("scripts.generate_operator_status.get_orientation_snapshot")
@patch("os.path.exists")
@patch("scripts.generate_operator_status.open", new_callable=MagicMock)
@patch("argparse.ArgumentParser.parse_args")
def test_main_check_stale(mock_args, mock_open, mock_exists, mock_get, mock_snapshot):
    from scripts.generate_operator_status import main
    mock_get.return_value = mock_snapshot
    mock_args.return_value = MagicMock(write=False, check=True)
    mock_exists.return_value = True

    # Mock reading different content
    mock_open.return_value.__enter__.return_value.read.return_value = "stale content"

    with patch("sys.exit") as mock_exit:
        main()
        mock_exit.assert_called_with(1)
