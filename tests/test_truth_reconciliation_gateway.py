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
    RECONCILIATION_ALLOWED,
    RECONCILIATION_BLOCKED,
    RECONCILIATION_APPLIED,
    RECALLED_AFTER_RECONCILIATION,
    RECHECK_RUNNING,
    RECHECK_PASSED,
    RECHECK_FAILED,
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
            section_heading TEXT,
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
            hash_status TEXT,
            truth_status TEXT,
            verification_required INTEGER,
            verification_invalidated_at TEXT,
            invalidation_reason TEXT
        )
    """)

    # Valid setup
    conn.execute("""
        INSERT INTO canonical_facts (fact_id, source_file, section_heading, source_commit, content_hash, truth_source_id, truth_status, verification_required, fact_text)
        VALUES ('f1', ?, 'Status', 'c1', 'h1', 's1', 'doctrine_reference', 1, 'fact text content')
    """, (str(source_file),))

    conn.execute("""
        INSERT INTO truth_registry_entries (source_id, observed_path, source_content_hash, hash_status, truth_status, verification_required)
        VALUES ('s1', ?, ?, 'current', 'doctrine_reference', 1)
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
    assert result["repairable"] is True

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
    assert result["repairable"] is False

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

def test_build_packet_no_mutation_by_default(test_env):
    conn = sqlite3.connect(test_env["db_path"])
    conn.execute("UPDATE truth_registry_entries SET hash_status = 'changed' WHERE source_id = 's1'")
    conn.commit()
    conn.close()

    build_llm_truth_packet(test_env["db_path"], test_env["fact_id"])

    conn = sqlite3.connect(test_env["db_path"])
    row = conn.execute("SELECT hash_status FROM truth_registry_entries WHERE source_id = 's1'").fetchone()
    conn.close()
    assert row[0] == 'changed'

def test_v1_mechanical_repair_success(test_env):
    # Set status to changed
    conn = sqlite3.connect(test_env["db_path"])
    conn.execute("UPDATE truth_registry_entries SET hash_status = 'changed' WHERE source_id = 's1'")
    conn.commit()
    conn.close()

    # Build packet with reconciliation allowed
    result = build_llm_truth_packet(test_env["db_path"], test_env["fact_id"], allow_reconciliation=True)

    assert result["status"] == MODEL_ALLOWED
    assert RECONCILIATION_APPLIED in result["transitions"]
    assert RECALLED_AFTER_RECONCILIATION in result["transitions"]
    assert RECHECK_PASSED in result["transitions"]

    # Verify DB was actually updated
    conn = sqlite3.connect(test_env["db_path"])
    row = conn.execute("SELECT hash_status FROM truth_registry_entries WHERE source_id = 's1'").fetchone()
    conn.close()
    assert row[0] == 'current'

def test_v1_mechanical_repair_refused_on_hash_mismatch(test_env):
    # Set status to changed AND change file
    conn = sqlite3.connect(test_env["db_path"])
    conn.execute("UPDATE truth_registry_entries SET hash_status = 'changed' WHERE source_id = 's1'")
    conn.commit()
    conn.close()
    test_env["source_file"].write_bytes(b"Mismatch")

    # Build packet with reconciliation allowed
    result = build_llm_truth_packet(test_env["db_path"], test_env["fact_id"], allow_reconciliation=True)

    assert result["status"] == MODEL_BLOCKED
    # It should have attempted mismatch invalidation instead of repair
    assert RECONCILIATION_APPLIED in result["transitions"]
    assert "Hash mismatch detected" in result["block_reason"]

    # Verify DB was invalidated
    conn = sqlite3.connect(test_env["db_path"])
    row = conn.execute("SELECT hash_status, invalidation_reason FROM truth_registry_entries WHERE source_id = 's1'").fetchone()
    conn.close()
    assert row[0] == 'changed'
    assert row[1] == 'JIT hash mismatch detected'

def test_v1_mechanical_repair_refused_when_not_allowed(test_env):
    conn = sqlite3.connect(test_env["db_path"])
    conn.execute("UPDATE truth_registry_entries SET hash_status = 'changed' WHERE source_id = 's1'")
    conn.commit()
    conn.close()

    # allow_reconciliation=False (default)
    result = build_llm_truth_packet(test_env["db_path"], test_env["fact_id"], allow_reconciliation=False)

    assert result["status"] == MODEL_BLOCKED
    assert RECONCILIATION_BLOCKED in result["transitions"]

def test_v1_mismatch_invalidation_success(test_env):
    # Setup a high-confidence status in BOTH tables
    conn = sqlite3.connect(test_env["db_path"])
    conn.execute("UPDATE truth_registry_entries SET truth_status = 'test_verified' WHERE source_id = 's1'")
    conn.execute("UPDATE canonical_facts SET truth_status = 'test_verified' WHERE truth_source_id = 's1'")
    conn.commit()
    conn.close()

    # Change file
    test_env["source_file"].write_bytes(b"Dirty content")

    # Build packet with reconciliation allowed
    result = build_llm_truth_packet(test_env["db_path"], test_env["fact_id"], allow_reconciliation=True)

    assert result["status"] == MODEL_BLOCKED
    assert RECONCILIATION_APPLIED in result["transitions"]
    assert "Hash mismatch detected" in result["block_reason"]

    # Verify DB updates in registry
    conn = sqlite3.connect(test_env["db_path"])
    row = conn.execute("""
        SELECT hash_status, truth_status, verification_required, verification_invalidated_at, invalidation_reason, source_content_hash
        FROM truth_registry_entries WHERE source_id = 's1'
    """).fetchone()

    assert row[0] == 'changed'
    assert row[1] == 'stale_possible'  # Downgraded
    assert row[2] == 1  # verification_required set
    assert row[3] is not None  # verification_invalidated_at set
    assert row[4] == 'JIT hash mismatch detected'
    assert row[5] == test_env["source_hash"]  # source_content_hash NOT replaced

    # Verify DB updates in canonical_facts
    row_f = conn.execute("SELECT truth_status, verification_required FROM canonical_facts WHERE fact_id = 'f1'").fetchone()
    assert row_f[0] == 'stale_possible'
    assert row_f[1] == 1

    conn.close()

def test_v1_mismatch_invalidation_no_downgrade_for_doctrine(test_env):
    # doctrine_reference should not downgrade to stale_possible
    conn = sqlite3.connect(test_env["db_path"])
    conn.execute("UPDATE truth_registry_entries SET truth_status = 'doctrine_reference' WHERE source_id = 's1'")
    conn.execute("UPDATE canonical_facts SET truth_status = 'doctrine_reference' WHERE truth_source_id = 's1'")
    conn.commit()
    conn.close()

    test_env["source_file"].write_bytes(b"Dirty content")

    result = build_llm_truth_packet(test_env["db_path"], test_env["fact_id"], allow_reconciliation=True)

    conn = sqlite3.connect(test_env["db_path"])
    row = conn.execute("SELECT truth_status FROM truth_registry_entries WHERE source_id = 's1'").fetchone()
    conn.close()
    assert row[0] == 'doctrine_reference'

def test_v1_mismatch_no_exposure_of_fact_text(test_env):
    test_env["source_file"].write_bytes(b"Dirty content")

    result = build_llm_truth_packet(test_env["db_path"], test_env["fact_id"], allow_reconciliation=True)

    assert result["status"] == MODEL_BLOCKED
    assert result["verified_facts"] == []
    # Fact text must not be in the top level either (it shouldn't be anyway)
    assert "text" not in str(result) or "fact text content" not in str(result)
