import sqlite3
import pytest
from pathlib import Path
from ar_counterparty_contact_operations import seed_capital_hilton_annette_fixture, ensure_schema
from capital_hilton_orchestrator import orchestrate_capital_hilton_read_model

def _mem_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    ensure_schema(conn)
    return conn

def test_orchestrate_capital_hilton_read_model(tmp_path):
    db_path = tmp_path / "ar.sqlite"
    receipt_path = tmp_path / "fake_receipt.json"
    receipt_path.write_text("{}")
    
    # Needs evidence to link
    now_ts = "2026-06-25T00:00:00+00:00"
    
    # Seed capital hilton data
    from ar_counterparty_contact_operations import seed_capital_hilton_annette_fixture, _connect
    seed_capital_hilton_annette_fixture(
        sqlite_path=db_path,
        metadata_receipt_path=receipt_path,
        generated_at=now_ts,
    )
    
    with _connect(db_path) as conn:
        # Just create a fake evidence entry so we can link it
        conn.execute("INSERT INTO ar_evidence_registry (evidence_id, account_id, source_system, source_event, source_locator, evidence_hash, governed_artifact_path, world, governance_status, processing_status, availability, first_seen_timestamp, ingestion_timestamp, extractor_version, schema_version, source_reference) VALUES ('ev_test', 'capital_hilton', 'sys', 'ev', 'loc', 'hash', 'path', 'w', 'active', 'pending', 'available', 't', 't', 'v', 'v', 'ref')")
        conn.commit()
        
        run_id = orchestrate_capital_hilton_read_model(
            conn=conn,
            governed_root=tmp_path,
            freshness_cutoff=now_ts,
            evidence_ids=["ev_test"]
        )
        
        # Verify
        row = conn.execute("SELECT status, stable_payload_hash FROM ar_materialization_runs WHERE run_id=?", (run_id,)).fetchone()
        assert row["status"] == "published"
        
        # Verify linkage
        link = conn.execute("SELECT inclusion_status FROM ar_materialization_run_evidence WHERE run_id=?", (run_id,)).fetchone()
        assert link["inclusion_status"] == "used"

