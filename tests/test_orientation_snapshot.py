import os
import json
import pytest
from unittest.mock import patch, MagicMock
from scripts.orientation_snapshot import get_orientation_snapshot, parse_markdown_section

# --- Tests for parse_markdown_section ---

def test_parse_markdown_section():
    content = """
# Section 1
Content 1
# Section 2
Content 2
## Sub Section
Sub Content
# Section 3
1. **Question 1**
   Answer 1
2. **Question 2**
   Answer 2
"""
    assert parse_markdown_section(content, "Section 1") == "Content 1"
    # Now it should include Sub Section because it's level 2 and we are at level 1
    assert parse_markdown_section(content, "Section 2") == "Content 2\n## Sub Section\nSub Content"
    assert parse_markdown_section(content, "Question 1") == "Answer 1"
    assert parse_markdown_section(content, "Question 2") == "Answer 2"
    assert parse_markdown_section(content, "Non-existent") == ""


# --- Tests for get_orientation_snapshot ---

@patch("scripts.orientation_snapshot.run_git_command")
@patch("os.path.exists")
@patch("sqlite3.connect")
@patch("scripts.orientation_snapshot.get_truth_substrate_status")
def test_get_orientation_snapshot_basic(mock_truth, mock_connect, mock_exists, mock_git):
    # Setup mocks
    mock_git.side_effect = lambda args: {
        "rev-parse --abbrev-ref HEAD": "main",
        "rev-parse HEAD": "1234567890abcdef",
        "log -1 --oneline": "1234567 initial commit",
        "status -s": ""
    }.get(" ".join(args), "")

    mock_exists.side_effect = lambda path: {
        "Operator/05_ORIENTATION_CONTRACT.md": False,
        "docs/operations/OPENCLAW_CURRENT_RUNTIME_MAP.md": False,
        ".openclaw/business_ops/ledger.sqlite": False,
        "docs/planning/project_packets/07_OPERATOR_HARNESS_PROMPT_DOCTRINE_AND_GATED_ACTIVATION/00_ACTIVE_HANDOFF.md": False
    }.get(path, False)

    mock_truth.return_value = {"status": "available", "metrics": {"facts": {"total": 0, "by_truth_status": {}}, "registry": {"total_sources": 0, "present_sources": 0}, "readiness": {"result": "READY"}}}

    snapshot = get_orientation_snapshot()

    assert snapshot["where_are_we"]["git_branch"] == "main"
    assert snapshot["where_are_we"]["git_head"] == "12345678"
    assert snapshot["where_are_we"]["git_status"] == "Clean"
    assert snapshot["active_lane"] == ""
    assert "Ledger Status: missing" in snapshot["confirmed_current"][0]
    assert snapshot["truth_substrate"]["status"] == "available"


@patch("scripts.orientation_snapshot.run_git_command")
@patch("os.path.exists")
@patch("sqlite3.connect")
@patch("builtins.open", new_callable=MagicMock)
@patch("scripts.orientation_snapshot.get_truth_substrate_status")
def test_get_orientation_snapshot_with_docs(mock_truth, mock_open, mock_connect, mock_exists, mock_git):
    # Setup mocks
    mock_git.return_value = ""
    mock_exists.return_value = True

    contract_content = """
# What lane is active?
Hardening the spine.
# What is the North Star?
Lighter life.
"""
    mock_open.return_value.__enter__.return_value.read.return_value = contract_content
    mock_open.return_value.__enter__.return_value.readlines.return_value = ["# Handoff\n", "The train is moving.\n"]

    # Mock sqlite
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [("events",), ("packets",)]
    mock_cursor.fetchone.return_value = (42,)

    mock_truth.return_value = {"status": "available", "metrics": {"facts": {"total": 10, "by_truth_status": {"doctrine_reference": 10}}, "registry": {"total_sources": 1, "present_sources": 1}, "readiness": {"result": "READY"}}}

    snapshot = get_orientation_snapshot()

    assert snapshot["active_lane"] == "Hardening the spine."
    assert snapshot["north_star"] == "Lighter life."
    assert snapshot["confirmed_current"][0] == "Ledger Status: active"
    assert "Active Handoff: The train is moving." in snapshot["confirmed_current"][1]
    assert snapshot["truth_substrate"]["metrics"]["facts"]["total"] == 10


def test_render_markdown_truth_summary(capsys):
    from scripts.orientation_snapshot import render_markdown
    snapshot = {
        "timestamp": "2026-05-12T12:00:00",
        "where_are_we": {"cwd": "/home/openclaw", "git_branch": "main", "git_head": "f016273", "git_status": "Clean"},
        "active_lane": "Hardening the spine.",
        "confirmed_current": ["Ledger Status: active"],
        "historical_context": "None",
        "blocked_or_unknown": "None",
        "allowed_tools": "None",
        "forbidden_surfaces": "None",
        "truth_substrate": {
            "status": "available",
            "metrics": {
                "facts": {"total": 83, "by_truth_status": {"doctrine_reference": 71, "historical_checkpoint": 12}},
                "registry": {"total_sources": 9, "present_sources": 9},
                "readiness": {"result": "READY"}
            }
        },
        "next_safe_move": "None",
        "visible_road_horizon": {"visible_moves": [], "branch_after": "None", "unsafe_beyond": "None"},
        "north_star": "None",
        "manifesto_posture": "None"
    }
    render_markdown(snapshot)
    captured = capsys.readouterr()
    assert "## 4. Truth Substrate Status" in captured.out
    assert "**Facts**: 83 (71 doctrine, 12 historical)" in captured.out
    assert "READY" in captured.out
    assert "Truth substrate status is read-only" in captured.out
    assert "SECRET_FACT_TEXT" not in captured.out


def test_render_markdown_truth_unavailable(capsys):
    from scripts.orientation_snapshot import render_markdown
    snapshot = {
        "timestamp": "2026-05-12T12:00:00",
        "where_are_we": {"cwd": "/home/openclaw", "git_branch": "main", "git_head": "f016273", "git_status": "Clean"},
        "active_lane": "Hardening the spine.",
        "confirmed_current": ["Ledger Status: active"],
        "historical_context": "None",
        "blocked_or_unknown": "None",
        "allowed_tools": "None",
        "forbidden_surfaces": "None",
        "truth_substrate": {"status": "unavailable", "reason": "Database missing"},
        "next_safe_move": "None",
        "visible_road_horizon": {"visible_moves": [], "branch_after": "None", "unsafe_beyond": "None"},
        "north_star": "None",
        "manifesto_posture": "None"
    }
    render_markdown(snapshot)
    captured = capsys.readouterr()
    assert "UNAVAILABLE (Database missing)" in captured.out


def test_json_mode_smoke(capsys):
    from scripts.orientation_snapshot import main
    with patch("sys.argv", ["scripts/orientation_snapshot.py", "--json"]):
        with patch("scripts.orientation_snapshot.get_orientation_snapshot") as mock_get:
            mock_get.return_value = {"test": "data"}
            main()
            captured = capsys.readouterr()
            data = json.loads(captured.out)
            assert data["test"] == "data"
