import pytest
import sqlite3
import os
from scripts.inventory_scanner import scan_root

DB_PATH = "/tmp/test_inventory_persist.sqlite"

@pytest.fixture(autouse=True)
def cleanup():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_unknown_root_rejected():
    with pytest.raises(ValueError, match="Unknown root_id"):
        scan_root("nonexistent")

def test_dry_run_scans_correctly():
    results = scan_root("test_fixture_01", dry_run=True)
    paths = [r["relative_path"] for r in results]
    assert "notes/readme.txt" in paths
    assert "docs/song_notes.md" in paths
    assert "data/example.json" in paths
    assert "nested/deeper/file.txt" in paths

def test_db_persistence():
    scan_root("test_fixture_01", db_path=DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM file_inventory")
    count = cursor.fetchone()[0]
    assert count > 0

    cursor.execute("SELECT file_name, ingest_eligibility FROM file_inventory WHERE file_name = 'readme.txt'")
    row = cursor.fetchone()
    assert row is not None
    assert row[1] == "eligible_metadata_only"
    conn.close()

def test_dry_run_does_not_write():
    scan_root("test_fixture_01", dry_run=True, db_path=DB_PATH)
    assert not os.path.exists(DB_PATH)
