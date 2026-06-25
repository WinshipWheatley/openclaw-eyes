import sqlite3
import pytest
from pathlib import Path
from datetime import datetime, timezone
import json

from ar_counterparty_contact_operations import (
    _connect,
    ensure_schema,
    registry_register,
    materialization_run_start,
    materialization_add_evidence,
    materialization_run_fail,
    materialization_run_publish,
    materialization_set_current_read_model,
)

def _mem_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    ensure_schema(conn)
    return conn

def test_materialization_run_lifecycle_success():
    conn = _mem_db()
    
    # 1. Setup account and evidence
    now_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO ar_counterparty_accounts (account_id, account_label, status, created_at, updated_at, account_json) VALUES (?, ?, ?, ?, ?, ?)",
        ("acct_1", "Test Acct", "active", now_ts, now_ts, "{}")
    )
    conn.commit()
    
    ev = registry_register(
        conn=conn,
        evidence_id="ev_1",
        account_id="acct_1",
        source_system="test",
        source_event="test",
        source_locator="test",
        evidence_hash="1234",
        governed_artifact_path_str="/tmp/test",
        world="test",
        first_seen_timestamp=now_ts,
        ingestion_timestamp=now_ts,
        extractor_version="v1",
        schema_version="v1",
        source_reference="test",
    )
    
    # 2. Start run
    run_id = "run_1"
    materialization_run_start(
        conn, run_id, "gen_1", "v1", "v1", now_ts, now_ts
    )
    
    # Check status
    row = conn.execute("SELECT status FROM ar_materialization_runs WHERE run_id=?", (run_id,)).fetchone()
    assert row["status"] == "preparing"
    
    # 3. Add evidence
    materialization_add_evidence(conn, run_id, "ev_1", "used")
    
    # Check linkage
    row = conn.execute("SELECT inclusion_status FROM ar_materialization_run_evidence WHERE run_id=? AND evidence_id=?", (run_id, "ev_1")).fetchone()
    assert row["inclusion_status"] == "used"
    
    # 4. Publish run
    pub_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    materialization_run_publish(
        conn, run_id, pub_ts, "hash1", "/tmp/artifact.json", "hash2"
    )
    
    row = conn.execute("SELECT status FROM ar_materialization_runs WHERE run_id=?", (run_id,)).fetchone()
    assert row["status"] == "published"
    
    # 5. Set current read model
    materialization_set_current_read_model(conn, "test_domain", run_id, pub_ts)
    
    row = conn.execute("SELECT current_run_id FROM ar_published_read_models WHERE read_model_domain=?", ("test_domain",)).fetchone()
    assert row["current_run_id"] == run_id

def test_materialization_run_publish_fails_without_required_fields():
    conn = _mem_db()
    run_id = "run_invalid"
    now_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    
    materialization_run_start(
        conn, run_id, "gen_1", "v1", "v1", now_ts, now_ts
    )
    
    # Attempting to publish manually by missing fields should hit the trigger
    with pytest.raises(sqlite3.IntegrityError, match="run_completion_timestamp is required"):
        conn.execute("UPDATE ar_materialization_runs SET status='published' WHERE run_id=?", (run_id,))

def test_materialization_run_fail_status():
    conn = _mem_db()
    run_id = "run_fail"
    now_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    
    materialization_run_start(
        conn, run_id, "gen_1", "v1", "v1", now_ts, now_ts
    )
    
    materialization_run_fail(conn, run_id, now_ts, "ERR_1", "Oops")
    
    row = conn.execute("SELECT status, error_code FROM ar_materialization_runs WHERE run_id=?", (run_id,)).fetchone()
    assert row["status"] == "failed"
    assert row["error_code"] == "ERR_1"

def test_set_current_read_model_fails_if_run_not_published():
    conn = _mem_db()
    run_id = "run_unpub"
    now_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    
    materialization_run_start(
        conn, run_id, "gen_1", "v1", "v1", now_ts, now_ts
    )
    
    with pytest.raises(sqlite3.IntegrityError, match="Cannot publish a run that is not in published status"):
        materialization_set_current_read_model(conn, "domain_x", run_id, now_ts)
