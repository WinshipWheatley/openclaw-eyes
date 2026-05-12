import pytest
import sqlite3
import os
from scripts.generate_canonical_fact_truth_report import run_report
from io import StringIO
import sys

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE canonical_facts (
            id INTEGER PRIMARY KEY,
            source_file TEXT,
            section_heading TEXT,
            fact_text TEXT,
            truth_source_id TEXT,
            truth_status TEXT,
            verification_required INTEGER,
            verification_evidence_id TEXT
        )
    """)
    conn.execute("""
        INSERT INTO canonical_facts VALUES 
        (1, 'file1.md', 'h1', 'text1', 'ts1', 'declared', 1, NULL),
        (2, 'file1.md', 'h1', 'text2', 'ts1', 'declared', 1, NULL),
        (3, 'file2.md', 'h2', 'text3', 'ts2', 'test_verified', 0, 'ev1')
    """)
    conn.commit()
    conn.close()
    return str(db_path)

def test_report_logic(temp_db, capsys):
    # Capture output
    run_report(temp_db)
    captured = capsys.readouterr()
    
    assert "Total facts: 3" in captured.out
    assert "declared: 2" in captured.out
    assert "test_verified: 1" in captured.out
    assert "Boundary note: Truth status describes verification posture, not runtime authority." in captured.out

def test_report_filters(temp_db, capsys):
    # Filter by status
    run_report(temp_db, truth_status='declared')
    captured = capsys.readouterr()
    assert "Total facts: 2" in captured.out
    
    # Filter by source
    run_report(temp_db, source='file2.md')
    captured = capsys.readouterr()
    assert "Total facts: 1" in captured.out
    
    # Filter by verification
    run_report(temp_db, verification_required=True)
    captured = capsys.readouterr()
    assert "Total facts: 2" in captured.out

def test_report_empty_db(tmp_path, capsys):
    db_path = tmp_path / "empty.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE canonical_facts (id INTEGER PRIMARY KEY, source_file TEXT, section_heading TEXT, fact_text TEXT, truth_source_id TEXT, truth_status TEXT, verification_required INTEGER, verification_evidence_id TEXT)")
    conn.commit()
    conn.close()
    
    run_report(str(db_path))
    captured = capsys.readouterr()
    assert "No canonical facts found matching the criteria." in captured.out
