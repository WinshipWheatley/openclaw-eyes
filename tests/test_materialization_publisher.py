import sqlite3
import pytest
import os
from pathlib import Path

from ar_counterparty_contact_operations import _connect, ensure_schema, stable_payload_hash
from materialization_publisher import publish_read_model, MaterializationError

def _mem_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    ensure_schema(conn)
    return conn

def test_publish_read_model_success(tmp_path):
    conn = _mem_db()
    
    # Needs valid evidence items to link
    conn.execute("INSERT INTO ar_counterparty_accounts (account_id, account_label, status, created_at, updated_at, account_json) VALUES ('acct_1', 'L', 'active', 't', 't', '{}')")
    conn.execute("INSERT INTO ar_evidence_registry (evidence_id, account_id, source_system, source_event, source_locator, evidence_hash, governed_artifact_path, world, governance_status, processing_status, availability, first_seen_timestamp, ingestion_timestamp, extractor_version, schema_version, source_reference) VALUES ('ev_1', 'acct_1', 'sys', 'ev', 'loc', 'hash', 'path', 'w', 'active', 'pending', 'available', 't', 't', 'v', 'v', 'ref')")
    conn.commit()

    def generator():
        return {"hello": "world", "nested": [1, 2, 3]}

    run_id = publish_read_model(
        conn=conn,
        governed_root=tmp_path,
        read_model_domain="test_domain",
        generator_id="test_gen",
        generator_version="1.0",
        schema_version="1.0",
        freshness_cutoff="2026-06-25T00:00:00Z",
        evidence_ids=["ev_1"],
        generator_fn=generator
    )

    # Validate db state
    row = conn.execute("SELECT status, stable_payload_hash FROM ar_materialization_runs WHERE run_id=?", (run_id,)).fetchone()
    assert row["status"] == "published"
    
    expected_hash = stable_payload_hash(generator())
    assert row["stable_payload_hash"] == expected_hash

    # Validate file state
    # object_path puts it in first two chars
    target_file = tmp_path / expected_hash[:2] / expected_hash[2:]
    assert target_file.exists()
    assert target_file.is_file()
    
    # Read the file and ensure it parses
    import json
    data = json.loads(target_file.read_text("utf-8"))
    assert data["hello"] == "world"

def test_publish_read_model_generator_failure(tmp_path):
    conn = _mem_db()
    
    def generator():
        raise ValueError("Oops, generator failed")

    with pytest.raises(MaterializationError, match="Generator failed: Oops, generator failed"):
        publish_read_model(
            conn=conn,
            governed_root=tmp_path,
            read_model_domain="test_domain",
            generator_id="test_gen",
            generator_version="1.0",
            schema_version="1.0",
            freshness_cutoff="2026-06-25T00:00:00Z",
            evidence_ids=[],
            generator_fn=generator
        )

    # Validate db state - run should be failed
    row = conn.execute("SELECT status, error_code FROM ar_materialization_runs").fetchone()
    assert row["status"] == "failed"
    assert row["error_code"] == "GENERATOR_ERROR"
