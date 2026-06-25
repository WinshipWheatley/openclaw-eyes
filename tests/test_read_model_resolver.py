import sqlite3
import pytest
import json
from pathlib import Path
from ar_counterparty_contact_operations import ensure_schema
from capital_hilton_orchestrator import orchestrate_capital_hilton_read_model
from read_model_resolver import resolve_current_read_model, ResolverError, TamperError

def _mem_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    ensure_schema(conn)
    return conn

def test_resolve_current_read_model(tmp_path):
    db_path = tmp_path / "ar.sqlite"
    receipt_path = tmp_path / "fake_receipt.json"
    receipt_path.write_text("{}")
    
    now_ts = "2026-06-25T00:00:00+00:00"
    
    from ar_counterparty_contact_operations import seed_capital_hilton_annette_fixture, _connect
    seed_capital_hilton_annette_fixture(
        sqlite_path=db_path,
        metadata_receipt_path=receipt_path,
        generated_at=now_ts,
    )
    
    with _connect(db_path) as conn:
        conn.execute("INSERT INTO ar_evidence_registry (evidence_id, account_id, source_system, source_event, source_locator, evidence_hash, governed_artifact_path, world, governance_status, processing_status, availability, first_seen_timestamp, ingestion_timestamp, extractor_version, schema_version, source_reference) VALUES ('ev_test', 'capital_hilton', 'sys', 'ev', 'loc', 'hash', 'path', 'w', 'active', 'pending', 'available', 't', 't', 'v', 'v', 'ref')")
        conn.commit()
        
        run_id = orchestrate_capital_hilton_read_model(
            conn=conn,
            governed_root=tmp_path,
            freshness_cutoff=now_ts,
            evidence_ids=["ev_test"]
        )
        
        # Test successful resolve
        path, payload = resolve_current_read_model(conn, tmp_path, "capital_hilton_ar_context")
        assert path.exists()
        assert payload["schema_version"] == "AR_CAPITAL_HILTON_READ_MODEL_V0"
        
        # Test tamper error (change file content)
        path.chmod(0o644)
        path.write_text("{\"tampered\": true}")
        with pytest.raises(TamperError, match="Tamper detected"):
            resolve_current_read_model(conn, tmp_path, "capital_hilton_ar_context")
            
        # Test missing active read model
        conn.execute("DELETE FROM ar_published_read_models WHERE read_model_domain = 'capital_hilton_ar_context'")
        with pytest.raises(ResolverError, match="No active read model"):
            resolve_current_read_model(conn, tmp_path, "capital_hilton_ar_context")
