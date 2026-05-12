import pytest
import os
import sqlite3
import hashlib
from unittest.mock import patch
from scripts.check_truth_registry_hashes import main, compute_sha256

# Helper to create a test DB
def create_test_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE truth_registry_entries (
            source_id TEXT PRIMARY KEY,
            observed_path TEXT UNIQUE,
            doc_type TEXT,
            truth_status TEXT,
            verification_required INTEGER DEFAULT 1,
            verification_evidence_id TEXT,
            verification_source TEXT,
            approval_status TEXT,
            source_content_hash TEXT,
            hash_algorithm TEXT,
            hash_recorded_at TEXT,
            hash_status TEXT DEFAULT 'not_recorded',
            verification_invalidated_at TEXT,
            invalidation_reason TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_hash(content):
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.sha256(content).hexdigest()

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_ledger.sqlite"
    create_test_db(str(db_path))
    return str(db_path)

@pytest.fixture
def mock_registry(tmp_path):
    # Create some dummy files
    f1 = tmp_path / "doc1.md"
    f1.write_text("content 1")
    
    f2 = tmp_path / "doc2.md"
    f2.write_text("content 2")
    
    registry = {
        str(f1): {"doc_category": "cat1"},
        str(f2): {"doc_category": "cat2"}
    }
    return registry, f1, f2

def test_check_fails_without_allow_hashing(temp_db, capsys):
    with patch("sys.argv", ["scripts/check_truth_registry_hashes.py", "--db", temp_db]):
        with pytest.raises(SystemExit) as e:
            main()
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "Error: --allow-hashing is required" in captured.err

def test_check_missing_baseline(temp_db, mock_registry, capsys):
    registry, f1, f2 = mock_registry
    conn = sqlite3.connect(temp_db)
    conn.execute("INSERT INTO truth_registry_entries (source_id, observed_path, hash_status) VALUES (?, ?, ?)", 
                 ("id1", str(f1), "not_recorded"))
    conn.commit()
    conn.close()
    
    with patch("sys.argv", ["scripts/check_truth_registry_hashes.py", "--db", temp_db, "--allow-hashing", "--source", str(f1)]):
        with patch("scripts.check_truth_registry_hashes.SOURCE_REGISTRY", registry):
            main()
    
    captured = capsys.readouterr()
    assert "no_baseline" in captured.out

def test_check_matching_hash(temp_db, mock_registry, capsys):
    registry, f1, f2 = mock_registry
    h1 = get_hash("content 1")
    
    conn = sqlite3.connect(temp_db)
    conn.execute("""
        INSERT INTO truth_registry_entries 
        (source_id, observed_path, source_content_hash, hash_status, truth_status) 
        VALUES (?, ?, ?, ?, ?)
    """, ("id1", str(f1), h1, "current", "test_verified"))
    conn.commit()
    conn.close()
    
    with patch("sys.argv", ["scripts/check_truth_registry_hashes.py", "--db", temp_db, "--allow-hashing", "--source", str(f1)]):
        with patch("scripts.check_truth_registry_hashes.SOURCE_REGISTRY", registry):
            main()
    
    captured = capsys.readouterr()
    assert "current: Hash matches baseline" in captured.out
    
    # Verify truth_status preserved
    conn = sqlite3.connect(temp_db)
    row = conn.execute("SELECT truth_status FROM truth_registry_entries WHERE source_id='id1'").fetchone()
    assert row[0] == "test_verified"
    conn.close()

def test_check_mismatch_without_apply(temp_db, mock_registry, capsys):
    registry, f1, f2 = mock_registry
    old_h = get_hash("old content")
    
    conn = sqlite3.connect(temp_db)
    conn.execute("""
        INSERT INTO truth_registry_entries 
        (source_id, observed_path, source_content_hash, hash_status, truth_status) 
        VALUES (?, ?, ?, ?, ?)
    """, ("id1", str(f1), old_h, "current", "test_verified"))
    conn.commit()
    conn.close()
    
    with patch("sys.argv", ["scripts/check_truth_registry_hashes.py", "--db", temp_db, "--allow-hashing", "--source", str(f1)]):
        with patch("scripts.check_truth_registry_hashes.SOURCE_REGISTRY", registry):
            main()
    
    captured = capsys.readouterr()
    assert "would_invalidate" in captured.out
    
    # Verify nothing changed
    conn = sqlite3.connect(temp_db)
    row = conn.execute("SELECT hash_status, truth_status FROM truth_registry_entries WHERE source_id='id1'").fetchone()
    assert row[0] == "current"
    assert row[1] == "test_verified"
    conn.close()

def test_check_mismatch_with_apply_test_verified(temp_db, mock_registry, capsys):
    registry, f1, f2 = mock_registry
    old_h = get_hash("old content")
    
    conn = sqlite3.connect(temp_db)
    conn.execute("""
        INSERT INTO truth_registry_entries 
        (source_id, observed_path, source_content_hash, hash_status, truth_status, verification_evidence_id) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("id1", str(f1), old_h, "current", "test_verified", "ev123"))
    conn.commit()
    conn.close()
    
    with patch("sys.argv", ["scripts/check_truth_registry_hashes.py", "--db", temp_db, "--allow-hashing", "--source", str(f1), "--apply"]):
        with patch("scripts.check_truth_registry_hashes.SOURCE_REGISTRY", registry):
            main()
    
    captured = capsys.readouterr()
    assert "invalidated" in captured.out
    assert "downgraded to stale_possible" in captured.out
    
    conn = sqlite3.connect(temp_db)
    row = conn.execute("SELECT hash_status, truth_status, verification_invalidated_at, invalidation_reason, verification_required, verification_evidence_id FROM truth_registry_entries WHERE source_id='id1'").fetchone()
    assert row[0] == "changed"
    assert row[1] == "stale_possible"
    assert row[2] is not None # invalidated_at
    assert "content hash mismatch" in row[3]
    assert row[4] == 1 # verification_required
    assert row[5] == "ev123" # preserved evidence ID
    conn.close()

def test_check_mismatch_with_apply_doctrine_reference(temp_db, mock_registry, capsys):
    registry, f1, f2 = mock_registry
    old_h = get_hash("old content")
    
    conn = sqlite3.connect(temp_db)
    conn.execute("""
        INSERT INTO truth_registry_entries 
        (source_id, observed_path, source_content_hash, hash_status, truth_status) 
        VALUES (?, ?, ?, ?, ?)
    """, ("id1", str(f1), old_h, "current", "doctrine_reference"))
    conn.commit()
    conn.close()
    
    with patch("sys.argv", ["scripts/check_truth_registry_hashes.py", "--db", temp_db, "--allow-hashing", "--source", str(f1), "--apply"]):
        with patch("scripts.check_truth_registry_hashes.SOURCE_REGISTRY", registry):
            main()
    
    captured = capsys.readouterr()
    assert "invalidated" in captured.out
    
    conn = sqlite3.connect(temp_db)
    row = conn.execute("SELECT hash_status, truth_status FROM truth_registry_entries WHERE source_id='id1'").fetchone()
    assert row[0] == "changed"
    assert row[1] == "doctrine_reference" # preserved
    conn.close()

def test_check_non_registry_source(temp_db, capsys):
    with patch("sys.argv", ["scripts/check_truth_registry_hashes.py", "--db", temp_db, "--allow-hashing", "--source", "/tmp/not_in_registry.md"]):
        with pytest.raises(SystemExit) as e:
            main()
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "is not in SOURCE_REGISTRY" in captured.err

def test_check_no_canonical_fact_modification(temp_db, mock_registry, tmp_path):
    # Setup a dummy canonical_facts table
    conn = sqlite3.connect(temp_db)
    conn.execute("CREATE TABLE canonical_facts (fact_id TEXT PRIMARY KEY, fact_text TEXT)")
    conn.execute("INSERT INTO canonical_facts VALUES ('f1', 'original fact text')")
    
    registry, f1, f2 = mock_registry
    old_h = get_hash("old content")
    conn.execute("""
        INSERT INTO truth_registry_entries 
        (source_id, observed_path, source_content_hash, hash_status, truth_status) 
        VALUES (?, ?, ?, ?, ?)
    """, ("id1", str(f1), old_h, "current", "test_verified"))
    conn.commit()
    conn.close()
    
    with patch("sys.argv", ["scripts/check_truth_registry_hashes.py", "--db", temp_db, "--allow-hashing", "--source", str(f1), "--apply"]):
        with patch("scripts.check_truth_registry_hashes.SOURCE_REGISTRY", registry):
            main()
    
    conn = sqlite3.connect(temp_db)
    row = conn.execute("SELECT fact_text FROM canonical_facts WHERE fact_id='f1'").fetchone()
    assert row[0] == "original fact text"
    conn.close()
