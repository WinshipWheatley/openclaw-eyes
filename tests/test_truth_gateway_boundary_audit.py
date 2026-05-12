import pytest
import sqlite3
import os
import hashlib
from scripts.truth_reconciliation_gateway import (
    build_llm_truth_packet,
    MODEL_ALLOWED_VERIFIED,
    MODEL_ALLOWED_UNCERTAIN,
    MODEL_BLOCKED
)
from scripts.answer_harness import answer_operator_question

def calculate_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

@pytest.fixture
def audit_env(tmp_path, monkeypatch):
    db_path = tmp_path / "audit_ledger.sqlite"
    source_file = tmp_path / "audit_source.md"
    source_content = b"Audit source content"
    source_file.write_bytes(source_content)
    source_hash = calculate_sha256(source_content)

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE canonical_facts (
            fact_id TEXT PRIMARY KEY,
            source_file TEXT,
            section_heading TEXT,
            source_commit TEXT,
            content_hash TEXT,
            truth_source_id TEXT,
            truth_status TEXT,
            verification_required INTEGER,
            verification_evidence_id TEXT,
            fact_text TEXT,
            sensitivity_class TEXT,
            allowed_actors TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE truth_registry_entries (
            source_id TEXT PRIMARY KEY,
            observed_path TEXT,
            source_content_hash TEXT,
            hash_status TEXT,
            truth_status TEXT,
            verification_required INTEGER,
            verification_invalidated_at TEXT,
            invalidation_reason TEXT
        )
    """)

    # Fact 1: Verified (No verification required)
    conn.execute("""
        INSERT INTO canonical_facts (fact_id, source_file, section_heading, source_commit, content_hash, truth_status, verification_required, fact_text, sensitivity_class, allowed_actors, truth_source_id)
        VALUES ('f_verified', ?, 'Status', 'c1', 'h1', 'doctrine_reference', 0, 'verified fact text', 'non_sensitive', '["OpenClaw"]', 's1')
    """, (str(source_file),))

    # Fact 2: Uncertain (Verification required, no evidence)
    conn.execute("""
        INSERT INTO canonical_facts (fact_id, source_file, section_heading, source_commit, content_hash, truth_status, verification_required, fact_text, sensitivity_class, allowed_actors, truth_source_id)
        VALUES ('f_uncertain', ?, 'Status', 'c1', 'h1', 'doctrine_reference', 1, 'uncertain fact text', 'non_sensitive', '["OpenClaw"]', 's1')
    """, (str(source_file),))

    conn.execute("""
        INSERT INTO truth_registry_entries (source_id, observed_path, source_content_hash, hash_status, truth_status, verification_required)
        VALUES ('s1', ?, ?, 'current', 'doctrine_reference', 0)
    """, (str(source_file), source_hash))

    conn.commit()
    conn.close()

    monkeypatch.setattr("scripts.truth_reconciliation_gateway.SOURCE_REGISTRY", {str(source_file): {}})

    return {
        "db_path": str(db_path),
        "source_file": source_file,
        "source_hash": source_hash
    }

def test_boundary_audit_verified_vs_uncertain_constants():
    """Guarantee 1: MODEL_ALLOWED_UNCERTAIN must not be treated as MODEL_ALLOWED_VERIFIED."""
    assert MODEL_ALLOWED_VERIFIED != MODEL_ALLOWED_UNCERTAIN
    assert MODEL_ALLOWED_VERIFIED == "MODEL_ALLOWED_VERIFIED"
    assert MODEL_ALLOWED_UNCERTAIN == "MODEL_ALLOWED_UNCERTAIN"

def test_boundary_audit_uncertain_is_qualified(audit_env):
    """Guarantee 2: MODEL_ALLOWED_UNCERTAIN answers must remain qualified/provisional."""
    result = answer_operator_question(audit_env["db_path"], "where are we?")
    # Fact 'f_uncertain' comes after 'f_verified' in some contexts, but here we expect both to be processed
    # Actually answer_harness combines them. 
    # Let's test them individually to be precise.
    
    # We'll mock build_llm_truth_packet to isolate
    import scripts.truth_reconciliation_gateway as gateway
    
    # 1. Test Uncertain Path
    packet_uncertain = gateway.build_llm_truth_packet(audit_env["db_path"], "f_uncertain")
    assert packet_uncertain["status"] == MODEL_ALLOWED_UNCERTAIN
    
    # Harness check
    # We need to ensure f_verified doesn't drown it out or we test f_uncertain alone
    # Let's delete f_verified for this test
    conn = sqlite3.connect(audit_env["db_path"])
    conn.execute("DELETE FROM canonical_facts WHERE fact_id = 'f_verified'")
    conn.commit()
    conn.close()
    
    result = answer_operator_question(audit_env["db_path"], "where are we?")
    assert result["status"] == "SUCCESS"
    assert "Based on currently available evidence, this appears to be provisional" in result["answer"]
    assert "uncertain fact text" in result["answer"]

def test_boundary_audit_blocked_hides_text(audit_env):
    """Guarantee 3: MODEL_BLOCKED must never expose fact_text."""
    # Cause a block (e.g. non-existent file)
    os.remove(audit_env["source_file"])
    
    packet = build_llm_truth_packet(audit_env["db_path"], "f_verified")
    assert packet["status"] == MODEL_BLOCKED
    assert "fact_text" not in packet
    assert "verified_facts" in packet and packet["verified_facts"] == []
    
    # Harness check
    result = answer_operator_question(audit_env["db_path"], "where are we?")
    assert result["status"] == MODEL_BLOCKED
    assert "verified fact text" not in result["answer"]
    assert "Audit source content" not in result["answer"]

def test_boundary_audit_hash_mismatch_is_blocked_not_uncertain(audit_env):
    """Guarantee 4: Source hash mismatch must remain MODEL_BLOCKED, not MODEL_ALLOWED_UNCERTAIN."""
    # Modify file to cause mismatch
    audit_env["source_file"].write_bytes(b"TAMPERED")
    
    # Even though f_uncertain is "uncertain", the hash mismatch should BLOCK it entirely
    packet = build_llm_truth_packet(audit_env["db_path"], "f_uncertain")
    assert packet["status"] == MODEL_BLOCKED
    assert packet["status"] != MODEL_ALLOWED_UNCERTAIN
    assert "fact_text" not in packet

def test_boundary_audit_runtime_authority_is_false(audit_env):
    """Guarantee 5: Truth packet posture must not imply runtime authority."""
    packet_v = build_llm_truth_packet(audit_env["db_path"], "f_verified")
    assert packet_v["runtime_authority"] is False
    
    packet_u = build_llm_truth_packet(audit_env["db_path"], "f_uncertain")
    assert packet_u["runtime_authority"] is False
    
    result = answer_operator_question(audit_env["db_path"], "where are we?")
    assert result["runtime_authority"] is False

def test_boundary_audit_status_boundary_note():
    """Guarantee 6: Operator/generated status must preserve the boundary note."""
    from scripts.truth_substrate_status import get_truth_substrate_status
    status = get_truth_substrate_status(".openclaw/business_ops/ledger.sqlite")
    if status["status"] == "available":
        assert "MODEL_BLOCKED takes precedence over candidate status if hash mismatch exists." in status["metrics"]["gateway_posture"]["note"]
    
    # Check orientation_snapshot (indirectly via capture or just checking script content)
    with open("scripts/orientation_snapshot.py", "r") as f:
        content = f.read()
        assert "Truth status describes candidate verification posture, not live runtime health, agent authority, or terminal gateway decisions." in content

    with open("scripts/generate_operator_status.py", "r") as f:
        content = f.read()
        assert "Truth status describes candidate verification posture, not live runtime health, agent authority, or terminal gateway decisions." in content
