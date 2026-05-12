import pytest
import sqlite3
import os
from business_ops_ledger import init_business_ops_ledger, record_truth_registry_entry

DB_PATH = "test_schema.sqlite"

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_business_ops_ledger(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_schema_fields_exist():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("PRAGMA table_info(truth_registry_entries)")
    columns = [row[1] for row in cursor.fetchall()]
    assert 'source_content_hash' in columns
    assert 'hash_algorithm' in columns
    assert 'hash_recorded_at' in columns
    assert 'hash_status' in columns
    assert 'verification_invalidated_at' in columns
    assert 'invalidation_reason' in columns
    conn.close()

def test_default_hash_status():
    record_truth_registry_entry(
        "s1", "path/1", "pc", "source", "public_canonical", "approved", "declared", True, True,
        db_path=DB_PATH
    )
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT hash_status FROM truth_registry_entries WHERE source_id = 's1'").fetchone()
    assert row[0] == 'not_recorded'
    conn.close()

def test_explicit_hash_metadata():
    record_truth_registry_entry(
        "s1", "path/1", "pc", "source", "public_canonical", "approved", "declared", True, True,
        source_content_hash="abc", hash_status="current", db_path=DB_PATH
    )
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT source_content_hash, hash_status FROM truth_registry_entries WHERE source_id = 's1'").fetchone()
    assert row[0] == 'abc'
    assert row[1] == 'current'
    conn.close()

def test_invalid_hash_status():
    result = record_truth_registry_entry(
        "s1", "path/1", "pc", "source", "public_canonical", "approved", "declared", True, True,
        hash_status="invalid", db_path=DB_PATH
    )
    assert result is False
