import pytest
import sqlite3
import os
import hashlib
from scripts.truth_reconciliation_gateway import (
    check_fact_source_integrity,
    build_llm_truth_packet,
    MODEL_ALLOWED,
    MODEL_BLOCKED,
    CANDIDATE_SURFACED,
    CHECK_RUNNING,
    NO_DIFF_FOUND,
    DIFF_FOUND,
    PACKET_READY
)

def calculate_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

@pytest.fixture
def test_env(tmp_path, monkeypatch):
    db_path = tmp_path / "ledger.sqlite"
    source_file = tmp_path / "source.md"
    source_content = b"Some source content"
    source_file.write_bytes(source_content)
    source_hash = calculate_sha256(source_content)

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE canonical_facts (
            fact_id TEXT PRIMARY KEY,
            source_file TEXT,
            source_commit TEXT,
            content_hash TEXT,
            truth_source_id TEXT,
            truth_status TEXT,
            verification_required INTEGER,
            verification_evidence_id TEXT,
            fact_text TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE truth_registry_entries (
            source_id TEXT PRIMARY KEY,
            observed_path TEXT,
            source_content_hash TEXT,
            hash_status TEXT
        )
    """)

    # Valid setup
    conn.execute("""
        INSERT INTO canonical_facts (fact_id, source_file, source_commit, content_hash, truth_source_id, truth_status, verification_required, fact_text)
        VALUES ('f1', ?, 'c1', 'h1', 's1', 'doctrine_reference', 1, 'fact text content')
    """, (str(source_file),))

    conn.execute("""
        INSERT INTO truth_registry_entries (source_id, observed_path, source_content_hash, hash_status)
        VALUES ('s1', ?, ?, 'current')
    """, (str(source_file), source_hash))

    conn.commit()
    conn.close()

    monkeypatch.setattr("scripts.truth_reconciliation_gateway.SOURCE_REGISTRY", {str(source_file): {}})

    return {
        "db_path": str(db_path),
        "source_file": source_file,
        "source_hash": source_hash,
        "fact_id": "f1",
        "source_id": "s1"
    }

def test_check_integrity_pass(test_env):
    result = check_fact_source_integrity(test_env["db_path"], test_env["fact_id"])
    assert result["status"] == "PASS"
    assert result["state"] == "NO_DIFF_FOUND"
    assert result["disk_content_hash"] == test_env["source_hash"]
    assert "fact_text" not in result

def test_check_integrity_fact_missing(test_env):
    result = check_fact_source_integrity(test_env["db_path"], "non_existent")
    assert result["status"] == "BLOCK"
    assert "Fact not found" in result["block_reason"]

def test_check_integrity_registry_missing(test_env):
    conn = sqlite3.connect(test_env["db_path"])
    conn.execute("DELETE FROM truth_registry_entries WHERE source_id = 's1'")
    conn.commit()
    conn.close()

    result = check_fact_source_integrity(test_env["db_path"], test_env["fact_id"])
    assert result["status"] == "BLOCK"
    assert "Registry entry missing" in result["block_reason"]

def test_check_integrity_source_not_in_registry(test_env, monkeypatch):
    monkeypatch.setattr("scripts.truth_reconciliation_gateway.SOURCE_REGISTRY", {})
    result = check_fact_source_integrity(test_env["db_path"], test_env["fact_id"])
    assert result["status"] == "BLOCK"
    assert "Source file not in SOURCE_REGISTRY" in result["block_reason"]

def test_check_integrity_alignment_mismatch(test_env):
    conn = sqlite3.connect(test_env["db_path"])
    conn.execute("UPDATE truth_registry_entries SET observed_path = 'wrong.md' WHERE source_id = 's1'")
    conn.commit()
    conn.close()

    result = check_fact_source_integrity(test_env["db_path"], test_env["fact_id"])
    assert result["status"] == "BLOCK"
    assert "Alignment mismatch" in result["block_reason"]

def test_check_integrity_hash_status_changed(test_env):
    conn = sqlite3.connect(test_env["db_path"])
    conn.execute("UPDATE truth_registry_entries SET hash_status = 'changed' WHERE source_id = 's1'")
    conn.commit()
    conn.close()

    result = check_fact_source_integrity(test_env["db_path"], test_env["fact_id"])
    assert result["status"] == "BLOCK"
    assert result["state"] == "DIFF_FOUND"
    assert "Registry hash_status is 'changed'" in result["block_reason"]

def test_check_integrity_missing_recorded_hash(test_env):
    conn = sqlite3.connect(test_env["db_path"])
    conn.execute("UPDATE truth_registry_entries SET source_content_hash = NULL WHERE source_id = 's1'")
    conn.commit()
    conn.close()

    result = check_fact_source_integrity(test_env["db_path"], test_env["fact_id"])
    assert result["status"] == "BLOCK"
    assert "Registry source_content_hash is missing" in result["block_reason"]

def test_check_integrity_disk_hash_mismatch(test_env):
    test_env["source_file"].write_bytes(b"Modified content")

    result = check_fact_source_integrity(test_env["db_path"], test_env["fact_id"])
    assert result["status"] == "BLOCK"
    assert result["state"] == "DIFF_FOUND"
    assert "Disk hash mismatch" in result["block_reason"]

def test_check_integrity_file_missing(test_env):
    os.remove(test_env["source_file"])

    result = check_fact_source_integrity(test_env["db_path"], test_env["fact_id"])
    assert result["status"] == "BLOCK"
    assert result["state"] == "DIFF_FOUND"
    assert "Source file missing from disk" in result["block_reason"]

def test_build_packet_pass(test_env):
    result = build_llm_truth_packet(test_env["db_path"], test_env["fact_id"], question="What is built?")
    assert result["status"] == MODEL_ALLOWED
    assert result["state"] == MODEL_ALLOWED
    assert result["question"] == "What is built?"
    assert result["substrate_status"] == "READY"
    assert len(result["verified_facts"]) == 1

    fact = result["verified_facts"][0]
    assert fact["id"] == "f1"
    assert fact["text"] == "fact text content"
    assert "[REPO-SOURCE]" in fact["labels"]
    assert "[HASH-CURRENT]" in fact["labels"]
    assert "[DOCTRINE_REFERENCE]" in fact["labels"]
    assert "[VERIFY_REQUIRED]" in fact["labels"]

    assert fact["provenance"]["fact_id"] == "f1"
    assert fact["provenance"]["truth_status"] == "doctrine_reference"

    assert result["runtime_authority"] is False
    assert "Answer only from verified_facts" in result["answer_boundary"]

    expected_transitions = [CANDIDATE_SURFACED, CHECK_RUNNING, NO_DIFF_FOUND, PACKET_READY, MODEL_ALLOWED]
    assert result["transitions"] == expected_transitions

def test_build_packet_blocked_by_hash_diff(test_env):
    test_env["source_file"].write_bytes(b"Modified content")

    result = build_llm_truth_packet(test_env["db_path"], test_env["fact_id"])
    assert result["status"] == MODEL_BLOCKED
    assert result["state"] == MODEL_BLOCKED
    assert result["verified_facts"] == []
    assert "Disk hash mismatch" in result["block_reason"]

    assert DIFF_FOUND in result["transitions"]
    assert MODEL_BLOCKED in result["transitions"]

def test_build_packet_blocked_by_missing_fact(test_env):
    result = build_llm_truth_packet(test_env["db_path"], "missing_fact")
    assert result["status"] == MODEL_BLOCKED
    assert "Fact not found" in result["block_reason"]
    assert result["verified_facts"] == []

def test_build_packet_no_mutation(test_env):
    conn = sqlite3.connect(test_env["db_path"])
    before = conn.execute("SELECT * FROM canonical_facts").fetchall()
    conn.close()

    build_llm_truth_packet(test_env["db_path"], test_env["fact_id"])

    conn = sqlite3.connect(test_env["db_path"])
    after = conn.execute("SELECT * FROM canonical_facts").fetchall()
    conn.close()

    assert before == after

def test_check_integrity_read_only(test_env):
    # Ensure DB is not mutated
    conn = sqlite3.connect(test_env["db_path"])
    before = conn.execute("SELECT * FROM truth_registry_entries").fetchall()
    conn.close()

    check_fact_source_integrity(test_env["db_path"], test_env["fact_id"])

    conn = sqlite3.connect(test_env["db_path"])
    after = conn.execute("SELECT * FROM truth_registry_entries").fetchall()
    conn.close()

    assert before == after
