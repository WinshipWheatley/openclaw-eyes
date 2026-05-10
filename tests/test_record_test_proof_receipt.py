import os
import sqlite3
import json
import subprocess
import pytest
import uuid
from pathlib import Path

# Import ledger functions to verify state
from business_ops_ledger import init_business_ops_ledger

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
RECORDER_SCRIPT = SCRIPTS_DIR / "record_test_proof_receipt.py"

@pytest.fixture
def temp_ledger(tmp_path):
    db_path = tmp_path / "test_ledger.sqlite"
    init_business_ops_ledger(str(db_path))
    return str(db_path)

def test_successful_command_records_receipt(temp_ledger):
    label = "test_pass"
    # Run a simple echo command
    res = subprocess.run([
        "python3", str(RECORDER_SCRIPT),
        "--label", label,
        "--db", temp_ledger,
        "--", "echo", "hello world"
    ], capture_output=True, text=True)

    assert res.returncode == 0

    # Verify ledger
    conn = sqlite3.connect(temp_ledger)
    cursor = conn.cursor()

    # Check events table
    cursor.execute("SELECT event_type, actor, operator_visible_summary FROM events")
    rows = cursor.fetchall()
    assert len(rows) == 1
    etype, actor, summary_json = rows[0]
    assert etype == "test_proof_receipt"
    assert actor == "test_proof_recorder_v0"

    receipt = json.loads(summary_json)
    assert receipt["command_label"] == label
    assert receipt["status"] == "pass"
    assert receipt["exit_code"] == 0
    assert "hello world" in receipt["output_tail"]

    # Check operator_explanations table
    cursor.execute("SELECT summary FROM operator_explanations")
    rows = cursor.fetchall()
    assert len(rows) == 1
    assert "test_pass pass" in rows[0][0]

    conn.close()

def test_failing_command_records_receipt(temp_ledger):
    label = "test_fail"
    # Run a command that fails
    res = subprocess.run([
        "python3", str(RECORDER_SCRIPT),
        "--label", label,
        "--db", temp_ledger,
        "--", "ls", "/nonexistent_path_openclaw_test"
    ], capture_output=True, text=True)

    assert res.returncode != 0

    # Verify ledger
    conn = sqlite3.connect(temp_ledger)
    cursor = conn.cursor()

    cursor.execute("SELECT operator_visible_summary FROM events")
    rows = cursor.fetchall()
    assert len(rows) == 1
    receipt = json.loads(rows[0][0])
    assert receipt["status"] == "fail"
    assert receipt["exit_code"] != 0
    assert "/nonexistent_path_openclaw_test" in receipt["output_tail"]

    conn.close()

def test_output_is_hashed_and_tail_is_bounded(temp_ledger):
    label = "test_bounds"
    # Use zero-padded numbers to avoid substring matches (e.g., line_01 vs line_11)
    cmd = "for i in {01..20}; do echo line_$i; done"
    res = subprocess.run([
        "python3", str(RECORDER_SCRIPT),
        "--label", label,
        "--db", temp_ledger,
        "--", "bash", "-c", cmd
    ], capture_output=True, text=True)

    assert res.returncode == 0

    conn = sqlite3.connect(temp_ledger)
    cursor = conn.cursor()
    cursor.execute("SELECT operator_visible_summary FROM events")
    receipt = json.loads(cursor.fetchone()[0])

    # Check hash exists
    assert len(receipt["output_hash"]) == 64

    # Check tail is bounded (last 10 lines)
    tail_lines = receipt["output_tail"].splitlines()
    assert len(tail_lines) <= 10
    assert "line_20" in tail_lines[-1]
    assert "line_01" not in receipt["output_tail"]

    conn.close()

def test_redaction_of_secrets(temp_ledger):
    label = "test_redact"
    # Command with a secret-like pattern
    cmd_str = "echo API_KEY=sk-test1234567890"
    res = subprocess.run([
        "python3", str(RECORDER_SCRIPT),
        "--label", label,
        "--db", temp_ledger,
        "--", "bash", "-c", cmd_str
    ], capture_output=True, text=True)

    assert res.returncode == 0

    conn = sqlite3.connect(temp_ledger)
    cursor = conn.cursor()
    cursor.execute("SELECT operator_visible_summary FROM events")
    receipt = json.loads(cursor.fetchone()[0])

    # Check redaction in tail
    assert "sk-test1234567890" not in receipt["output_tail"]
    assert "[REDACTED]" in receipt["output_tail"]
    assert receipt["redaction_marker"] is True

    # Check redaction in command_string
    assert "sk-test1234567890" not in receipt["command_string"]
    assert "[REDACTED]" in receipt["command_string"]

    conn.close()

def test_no_packets_row_is_written(temp_ledger):
    label = "test_no_packets"
    subprocess.run([
        "python3", str(RECORDER_SCRIPT),
        "--label", label,
        "--db", temp_ledger,
        "--", "echo", "hi"
    ], capture_output=True, text=True)

    conn = sqlite3.connect(temp_ledger)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM packets")
    assert cursor.fetchone()[0] == 0
    conn.close()

def test_missing_command_fails(temp_ledger):
    res = subprocess.run([
        "python3", str(RECORDER_SCRIPT),
        "--label", "test_missing"
    ], capture_output=True, text=True)

    assert res.returncode != 0
    assert "No command provided" in res.stderr

    # Ledger should be empty
    conn = sqlite3.connect(temp_ledger)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM events")
    assert cursor.fetchone()[0] == 0
    conn.close()
