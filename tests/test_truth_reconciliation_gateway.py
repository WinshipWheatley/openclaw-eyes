import pytest
import sqlite3
import os
import hashlib
from scripts.truth_reconciliation_gateway import check_fact_source_integrity

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
            truth_source_id TEXT,
            truth_status TEXT,
            verification_required INTEGER,
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
        INSERT INTO canonical_facts (fact_id, source_file, truth_source_id, truth_status, verification_required, fact_text)
        VALUES ('f1', ?, 's1', 'doctrine_reference', 1, 'fact text content')
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
