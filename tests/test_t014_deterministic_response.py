import os
import sqlite3
import pytest
from pathlib import Path
from ar_counterparty_contact_operations import ensure_schema
from capital_hilton_orchestrator import orchestrate_capital_hilton_read_model
from maestro_context_packet import build_maestro_context_packet

def test_t014_deterministic_response(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_FEATURE_CAPITAL_HILTON_AR", "1")
    
    # 1. Setup DB and run materialization
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
        
        orchestrate_capital_hilton_read_model(
            conn=conn,
            governed_root=tmp_path,
            freshness_cutoff=now_ts,
            evidence_ids=["ev_test"]
        )

    # 2. Test context packet generation
    packet = build_maestro_context_packet(
        question="capital hilton status",
        read_model_root=tmp_path,
        require_real_truth=False
    )
    
    assert packet["status"] == "ANSWER_READY"
    assert "deterministic_response" in packet
    assert "Capital Hilton" in packet["deterministic_response"]
