import os
import pytest
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
    assert "2026-05-10T10:00:00" in output
    assert "0de27a6f" in output
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

def test_generate_next_actions_no_ledger(mock_snapshot):
    mock_snapshot["confirmed_current"][1] = "Ledger Status: missing"
    output = generate_next_actions(mock_snapshot)
    assert "[TODO] Record initial Orientation Snapshot Receipt" in output

@patch("scripts.generate_operator_status.get_orientation_snapshot")
@patch("builtins.open", new_callable=MagicMock)
def test_main_smoke(mock_open, mock_get, mock_snapshot):
    from scripts.generate_operator_status import main
    mock_get.return_value = mock_snapshot
    
    main()
    
    assert mock_open.call_count == 2
    # Check if files were opened for writing
    mock_open.assert_any_call("Operator/GENERATED_CURRENT_STATE.md", "w")
    mock_open.assert_any_call("Operator/GENERATED_NEXT_ACTIONS.md", "w")
