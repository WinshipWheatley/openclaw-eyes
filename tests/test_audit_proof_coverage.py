import pytest
import os
import sqlite3
import json
import subprocess
from datetime import datetime

# Helper to run the script
def run_audit(args=None):
    cmd = ["python3", "scripts/audit_proof_coverage.py"]
    if args:
        cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result

def test_manifest_parsing_exists():
    """Verify the manifest file is where we expect it."""
    assert os.path.exists("docs/operations/OPENCLAW_EXPECTED_PROOF_MANIFEST_V0.md")

@pytest.fixture
def mock_ledger(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE events (
            event_id TEXT PRIMARY KEY,
            ts TEXT,
            event_type TEXT,
            actor TEXT,
            operator_visible_summary TEXT
        )
    """)
    conn.commit()
    yield db_path
    conn.close()

def test_audit_missing_proofs(mock_ledger, monkeypatch):
    # Empty ledger should result in MISSING status for all manifest labels
    monkeypatch.setenv("OPENCLAW_LEDGER_PATH", str(mock_ledger))
    
    # We need to ensure the script uses the environment variable or we pass it as an argument
    # For now, let's assume it supports --db
    result = run_audit(["--db", str(mock_ledger), "--json"])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    
    labels = [r["label"] for r in data["results"]]
    assert "generated_status_check" in labels
    assert all(r["status"] == "MISSING" for r in data["results"])
    assert all(r["signal"] == "MISSING" for r in data["results"])

def test_audit_failing_proof(mock_ledger):
    conn = sqlite3.connect(mock_ledger)
    cursor = conn.cursor()
    # Insert a failure
    cursor.execute("""
        INSERT INTO events (event_id, ts, event_type, actor, operator_visible_summary)
        VALUES (?, ?, ?, ?, ?)
    """, ("test_1", "2026-05-10T10:00:00", "test_proof_receipt", "test_actor", "FAIL generated_status_check exit=1 head=0f781b4 dirty=false"))
    conn.commit()
    conn.close()
    
    result = run_audit(["--db", str(mock_ledger), "--json"])
    data = json.loads(result.stdout)
    
    match = next(r for r in data["results"] if r["label"] == "generated_status_check")
    assert match["status"] == "FAIL"
    assert match["signal"] == "FAILING"

def test_audit_confirmed_proof(mock_ledger):
    # Get current head
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()[:8]
    
    conn = sqlite3.connect(mock_ledger)
    cursor = conn.cursor()
    # Insert a clean pass on current head
    cursor.execute("""
        INSERT INTO events (event_id, ts, event_type, actor, operator_visible_summary)
        VALUES (?, ?, ?, ?, ?)
    """, ("test_2", "2026-05-10T10:00:00", "test_proof_receipt", "test_actor", f"PASS generated_status_check exit=0 head={head} dirty=false"))
    conn.commit()
    conn.close()
    
    result = run_audit(["--db", str(mock_ledger), "--json"])
    data = json.loads(result.stdout)
    
    match = next(r for r in data["results"] if r["label"] == "generated_status_check")
    assert match["status"] == "PASS"
    assert match["relation"] == "MATCH"
    assert match["repo"] == "CLEAN"
    assert match["signal"] == "CONFIRMED"

def test_audit_drifted_proof(mock_ledger):
    conn = sqlite3.connect(mock_ledger)
    cursor = conn.cursor()
    # Insert a pass on an old head
    cursor.execute("""
        INSERT INTO events (event_id, ts, event_type, actor, operator_visible_summary)
        VALUES (?, ?, ?, ?, ?)
    """, ("test_3", "2026-05-10T10:00:00", "test_proof_receipt", "test_actor", "PASS generated_status_check exit=0 head=deadbeef dirty=false"))
    conn.commit()
    conn.close()
    
    result = run_audit(["--db", str(mock_ledger), "--json"])
    data = json.loads(result.stdout)
    
    match = next(r for r in data["results"] if r["label"] == "generated_status_check")
    assert match["status"] == "PASS"
    assert match["relation"] == "DRIFT"
    assert match["signal"] == "WEAK"

def test_audit_dirty_proof(mock_ledger):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()[:8]
    conn = sqlite3.connect(mock_ledger)
    cursor = conn.cursor()
    # Insert a dirty pass on current head
    cursor.execute("""
        INSERT INTO events (event_id, ts, event_type, actor, operator_visible_summary)
        VALUES (?, ?, ?, ?, ?)
    """, ("test_4", "2026-05-10T10:00:00", "test_proof_receipt", "test_actor", f"PASS generated_status_check exit=0 head={head} dirty=true"))
    conn.commit()
    conn.close()
    
    result = run_audit(["--db", str(mock_ledger), "--json"])
    data = json.loads(result.stdout)
    
    match = next(r for r in data["results"] if r["label"] == "generated_status_check")
    assert match["status"] == "PASS"
    assert match["repo"] == "DIRTY"
    assert match["signal"] == "WEAK"

def test_check_mode_failure(mock_ledger):
    # MISSING proof should cause --check to fail
    result = run_audit(["--db", str(mock_ledger), "--check"])
    assert result.returncode != 0

def test_check_mode_success(mock_ledger):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()[:8]
    
    # Insert all manifest proofs as CONFIRMED
    # We'll need the labels from the manifest. For v0 we know them.
    labels = [
        "generated_status_check",
        "ledger_inspector_summary",
        "orientation_snapshot_smoke",
        "cassandra_status_wiring_tests",
        "business_ops_ledger_tests"
    ]
    
    conn = sqlite3.connect(mock_ledger)
    cursor = conn.cursor()
    for i, label in enumerate(labels):
        cursor.execute("""
            INSERT INTO events (event_id, ts, event_type, actor, operator_visible_summary)
            VALUES (?, ?, ?, ?, ?)
        """, (f"ok_{i}", f"2026-05-10T10:00:{i:02d}", "test_proof_receipt", "test", f"PASS {label} exit=0 head={head} dirty=false"))
    conn.commit()
    conn.close()
    
    result = run_audit(["--db", str(mock_ledger), "--check"])
    assert result.returncode == 0
