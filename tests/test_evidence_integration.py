import sqlite3
from pathlib import Path

import pytest

from ar_counterparty_contact_operations import ensure_schema
from evidence_integration import import_and_register_evidence
from evidence_importer import import_evidence

@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON;")
    
    # We need to create the dependency tables too
    ensure_schema(c)
    
    # Insert a dummy account for foreign key satisfaction
    c.execute(
        "INSERT INTO ar_counterparty_accounts (account_id, account_label, status, created_at, updated_at, account_json) VALUES (?, ?, ?, ?, ?, ?)",
        ("acc-123", "Acme", "active", "2026", "2026", "{}")
    )
    c.commit()
    return c

@pytest.fixture
def workspace(tmp_path):
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()
    return source_dir, target_dir

def test_integration_success_quarantined_default(conn, workspace):
    source_dir, target_dir = workspace
    src = source_dir / "test.txt"
    src.write_bytes(b"content A")
    
    row = import_and_register_evidence(
        conn=conn,
        source_path=src,
        governed_root=target_dir,
        account_id="acc-123",
        source_system="gmail",
        source_event="sync_1",
        source_locator="msg_1",
        world="real"
    )
    
    assert row["governance_status"] == "quarantined"
    assert row["processing_status"] == "pending"
    import hashlib
    expected_hash = hashlib.sha256(b"content A").hexdigest()
    assert row["evidence_hash"] == expected_hash
    assert Path(row["governed_artifact_path"]).exists()

def test_identical_source_occurrence_idempotent(conn, workspace):
    source_dir, target_dir = workspace
    src = source_dir / "test.txt"
    src.write_bytes(b"content A")
    
    row1 = import_and_register_evidence(
        conn=conn,
        source_path=src,
        governed_root=target_dir,
        account_id="acc-123",
        source_system="gmail",
        source_event="sync_1",
        source_locator="msg_1",
        world="real"
    )
    
    row2 = import_and_register_evidence(
        conn=conn,
        source_path=src,
        governed_root=target_dir,
        account_id="acc-123",
        source_system="gmail",
        source_event="sync_1",
        source_locator="msg_1",
        world="real"
    )
    
    assert row1["evidence_id"] == row2["evidence_id"]
    
    # ensure only one row in db
    count = conn.execute("SELECT COUNT(*) FROM ar_evidence_registry").fetchone()[0]
    assert count == 1

def test_separate_provenance_different_events(conn, workspace):
    source_dir, target_dir = workspace
    src = source_dir / "test.txt"
    src.write_bytes(b"content A")
    
    row1 = import_and_register_evidence(
        conn=conn,
        source_path=src,
        governed_root=target_dir,
        account_id="acc-123",
        source_system="gmail",
        source_event="sync_1",
        source_locator="msg_1",
        world="real"
    )
    
    row2 = import_and_register_evidence(
        conn=conn,
        source_path=src,
        governed_root=target_dir,
        account_id="acc-123",
        source_system="gmail",
        source_event="sync_2",
        source_locator="msg_1",
        world="real"
    )
    
    assert row1["evidence_id"] != row2["evidence_id"]
    assert row1["evidence_hash"] == row2["evidence_hash"]
    
    count = conn.execute("SELECT COUNT(*) FROM ar_evidence_registry").fetchone()[0]
    assert count == 2

def test_supersession_for_changed_content(conn, workspace):
    source_dir, target_dir = workspace
    src = source_dir / "test.txt"
    
    # 1. First ingest
    src.write_bytes(b"content V1")
    row1 = import_and_register_evidence(
        conn=conn,
        source_path=src,
        governed_root=target_dir,
        account_id="acc-123",
        source_system="drive",
        source_event="sync_1",
        source_locator="file_xyz",
        world="real"
    )
    assert row1["supersedes_evidence_id"] is None
    
    # Must activate row1 to be superseded
    conn.execute("UPDATE ar_evidence_registry SET governance_status='active' WHERE evidence_id=?", (row1["evidence_id"],))
    conn.commit()
    
    # 2. Changed content
    src.write_bytes(b"content V2")
    row2 = import_and_register_evidence(
        conn=conn,
        source_path=src,
        governed_root=target_dir,
        account_id="acc-123",
        source_system="drive",
        source_event="sync_2",
        source_locator="file_xyz",
        world="real"
    )
    
    assert row2["evidence_id"] != row1["evidence_id"]
    assert row2["supersedes_evidence_id"] == row1["evidence_id"]

def test_orphaned_content_intact_on_db_failure(conn, workspace):
    source_dir, target_dir = workspace
    src = source_dir / "test.txt"
    src.write_bytes(b"content X")
    
    # Force a DB failure by using a missing account_id (foreign key violation)
    with pytest.raises(sqlite3.IntegrityError):
        import_and_register_evidence(
            conn=conn,
            source_path=src,
            governed_root=target_dir,
            account_id="MISSING_ACCOUNT",
            source_system="drive",
            source_event="sync",
            source_locator="file",
            world="real"
        )
        
    # DB failed, but content object was written and remains intact
    found_files = list(target_dir.rglob("*"))
    # Filter only files (no directories)
    files = [f for f in found_files if f.is_file()]
    assert len(files) == 1
    assert files[0].read_bytes() == b"content X"
