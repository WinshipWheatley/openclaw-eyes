import os
import json
from pathlib import Path
import sqlite3
import pytest

from ar_counterparty_contact_operations import seed_capital_hilton_annette_fixture, _connect
from capital_hilton_orchestrator import orchestrate_capital_hilton_read_model
from read_model_resolver import resolve_current_read_model
from maestro_context_packet import build_maestro_context_packet
from agent_lane_registry import seed_agent_lane_registry

def test_t016_synthetic_e2e(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_FEATURE_CAPITAL_HILTON_AR", "1")
    
    db_path = tmp_path / "ar.sqlite"
    governed_root = tmp_path
    now_ts = "2026-06-25T00:00:00+00:00"
    receipt_path = tmp_path / "fake_receipt.json"
    receipt_path.write_text("{}")
    
    # 1. Initialize Agent Lane Registry to verify T015 audit requirement
    registry_db = tmp_path / "agent_registry.sqlite"
    seed_agent_lane_registry(db_path=registry_db)
    with _connect(registry_db) as conn:
        row = conn.execute("SELECT telegram_bot_username, telegram_display_name FROM agent_lanes WHERE agent_id = 'cassandra'").fetchone()
        assert row is not None
        assert row["telegram_bot_username"] == "@openclaw_cassandra_bot"
        assert row["telegram_display_name"] == "Clara Reid"
        
    # 2. Seed Evidence
    seed_capital_hilton_annette_fixture(
        sqlite_path=db_path,
        metadata_receipt_path=receipt_path,
        generated_at=now_ts,
    )
    with _connect(db_path) as conn:
        conn.execute("INSERT INTO ar_evidence_registry (evidence_id, account_id, source_system, source_event, source_locator, evidence_hash, governed_artifact_path, world, governance_status, processing_status, availability, first_seen_timestamp, ingestion_timestamp, extractor_version, schema_version, source_reference) VALUES ('ev_test', 'capital_hilton', 'sys', 'ev', 'loc', 'hash', 'path', 'w', 'active', 'pending', 'available', 't', 't', 'v', 'v', 'ref')")
        conn.commit()

        # 3. Orchestrate Read Model Publication
        run_id = orchestrate_capital_hilton_read_model(
            conn=conn,
            governed_root=governed_root,
            freshness_cutoff=now_ts,
            evidence_ids=["ev_test"]
        )
        
        # 4. Resolve the Published Read Model
        model_path, payload = resolve_current_read_model(conn, governed_root, "capital_hilton_ar_context")

    # 5. Verify Context Packet Deterministic Response (T014)
    packet = build_maestro_context_packet(
        question="What is the capital hilton invoice status?",
        read_model_root=governed_root,
        require_real_truth=False
    )
    
    assert packet["status"] == "ANSWER_READY"
    assert "deterministic_response" in packet
    assert "Capital Hilton" in packet["deterministic_response"]
    
    traceability = packet.get("traceability", {})
    assert traceability.get("renderer_bypassed") is True
    assert traceability.get("materialization_run_id") == run_id

    # NEGATIVE PATH 1: Feature Flag OFF
    monkeypatch.delenv("OPENCLAW_FEATURE_CAPITAL_HILTON_AR", raising=False)
    packet_off = build_maestro_context_packet(
        question="What is the capital hilton invoice status?",
        read_model_root=governed_root,
        require_real_truth=False
    )
    assert packet_off["status"] == "READY"
    assert "deterministic_response" not in packet_off
    monkeypatch.setenv("OPENCLAW_FEATURE_CAPITAL_HILTON_AR", "1")
    
    # NEGATIVE PATH 2: Tampered Artifact
    model_path.chmod(0o644)
    model_path.write_text("{\"tampered\": true}")
    packet_tampered = build_maestro_context_packet(
        question="What is the capital hilton invoice status?",
        read_model_root=governed_root,
        require_real_truth=False
    )
    assert packet_tampered["status"] == "READY"
    assert "deterministic_response" not in packet_tampered

    # NEGATIVE PATH 3: Missing active read model pointer
    conn.execute("DELETE FROM ar_published_read_models WHERE read_model_domain = 'capital_hilton_ar_context'")
    conn.commit()
    packet_missing = build_maestro_context_packet(
        question="What is the capital hilton invoice status?",
        read_model_root=governed_root,
        require_real_truth=False
    )
    assert packet_missing["status"] == "READY"
    assert "deterministic_response" not in packet_missing
