import pytest
import sqlite3
import os
from scripts.truth_substrate_status import get_truth_substrate_status

@pytest.fixture
def status_db(tmp_path):
    db_path = tmp_path / "status_test.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE canonical_facts (
            fact_id TEXT PRIMARY KEY,
            truth_source_id TEXT,
            verification_required INTEGER,
            verification_evidence_id TEXT,
            truth_status TEXT,
            source_file TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE truth_registry_entries (
            source_id TEXT PRIMARY KEY,
            observed_path TEXT,
            source_content_hash TEXT,
            hash_status TEXT,
            truth_status TEXT,
            verification_required INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE verification_evidence (
            evidence_id TEXT PRIMARY KEY,
            source_id TEXT,
            evidence_type TEXT
        )
    """)
    conn.execute("CREATE TABLE packets (event_id TEXT, packet_json_safe TEXT)")
    conn.execute("CREATE TABLE events (event_id TEXT, event_type TEXT, ts TEXT)")
    
    # 1. Verified: verification_required=0
    conn.execute("""
        INSERT INTO canonical_facts (fact_id, truth_source_id, verification_required, truth_status)
        VALUES ('f1', 's1', 0, 'doctrine_reference')
    """)
    
    # 2. Verified: verification_required=1 with valid evidence
    conn.execute("""
        INSERT INTO canonical_facts (fact_id, truth_source_id, verification_required, verification_evidence_id, truth_status)
        VALUES ('f2', 's2', 1, 'ev2', 'manual_review')
    """)
    conn.execute("""
        INSERT INTO verification_evidence (evidence_id, source_id, evidence_type)
        VALUES ('ev2', 's2', 'manual')
    """)
    
    # 3. Uncertain: verification_required=1 with NO evidence
    conn.execute("""
        INSERT INTO canonical_facts (fact_id, truth_source_id, verification_required, truth_status)
        VALUES ('f3', 's3', 1, 'historical')
    """)
    
    # 4. Uncertain: verification_required=1 with NON-EXISTENT evidence_id
    conn.execute("""
        INSERT INTO canonical_facts (fact_id, truth_source_id, verification_required, verification_evidence_id, truth_status)
        VALUES ('f4', 's4', 1, 'ev_missing', 'historical')
    """)
    
    # 5. Uncertain: verification_required=1 with MISMATCHED source_id in evidence
    conn.execute("""
        INSERT INTO canonical_facts (fact_id, truth_source_id, verification_required, verification_evidence_id, truth_status)
        VALUES ('f5', 's5', 1, 'ev_mismatch', 'historical')
    """)
    conn.execute("""
        INSERT INTO verification_evidence (evidence_id, source_id, evidence_type)
        VALUES ('ev_mismatch', 's_wrong', 'manual')
    """)
    
    conn.commit()
    conn.close()
    return str(db_path)

def test_truth_substrate_status_alignment(status_db):
    status = get_truth_substrate_status(status_db)
    assert status["status"] == "available"
    
    gp = status["metrics"]["gateway_posture"]
    # Verified should be f1 and f2 = 2
    assert gp["verified_candidate_facts"] == 2
    # Uncertain should be f3, f4, f5 = 3
    assert gp["uncertain_candidate_facts"] == 3

def test_truth_substrate_status_blocked_source_precedence(status_db):
    # Add a blocked source in registry
    conn = sqlite3.connect(status_db)
    conn.execute("""
        INSERT INTO truth_registry_entries (source_id, hash_status)
        VALUES ('s_blocked', 'changed')
    """)
    conn.commit()
    conn.close()
    
    status = get_truth_substrate_status(status_db)
    gp = status["metrics"]["gateway_posture"]
    assert gp["blocked_sources_count"] == 1
    assert "MODEL_BLOCKED takes precedence" in gp["note"]
