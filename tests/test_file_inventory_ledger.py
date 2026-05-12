import pytest
import sqlite3
import os
from business_ops_ledger import init_business_ops_ledger, record_file_inventory_entry

DB_PATH = "/tmp/test_file_inventory.sqlite"

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_business_ops_ledger(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_ledger_initialization():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='file_inventory'")
    assert cursor.fetchone() is not None
    conn.close()

def test_record_file_inventory_entry():
    success = record_file_inventory_entry(
        file_id="f1",
        root_id="r1",
        drive_label="D",
        absolute_path="/mnt/d/file.txt",
        relative_path="file.txt",
        file_name="file.txt",
        extension="txt",
        file_type_guess="text",
        size_bytes=100,
        modified_at="2026-05-11",
        content_hash="abc",
        sensitivity_guess="public",
        ingest_eligibility="eligible_metadata_only",
        exclusion_reason=None,
        db_path=DB_PATH
    )
    assert success is True

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM file_inventory WHERE file_id = 'f1'")
    row = cursor.fetchone()
    conn.close()
    assert row is not None
    assert row[1] == "r1"
    assert row[8] == 100

def test_size_bytes_enforcement():
    with pytest.raises(ValueError, match="size_bytes cannot be negative"):
        record_file_inventory_entry(
            "f2", "r1", None, "/path", "rel", "f", None, None, -1, "t", None, None, "unknown", None, DB_PATH
        )

def test_ingest_eligibility_enforcement():
    with pytest.raises(ValueError, match="Invalid ingest_eligibility"):
        record_file_inventory_entry(
            "f3", "r1", None, "/path", "rel", "f", None, None, 10, "t", None, None, "invalid", None, DB_PATH
        )
