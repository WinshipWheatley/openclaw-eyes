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
    # Use real schema columns
    conn.execute("""
        CREATE TABLE canonical_facts (
            fact_id TEXT PRIMARY KEY,
            source_file TEXT NOT NULL,
            section_heading TEXT NOT NULL,
            source_commit TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            fact_text TEXT NOT NULL,
            sensitivity_class TEXT NOT NULL,
            allowed_actors TEXT NOT NULL,
            doc_category TEXT,
            temporal_or_doctrine TEXT,
            source_description TEXT,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            truth_source_id TEXT,
            truth_status TEXT,
            verification_required INTEGER DEFAULT 1,
            verification_evidence_id TEXT
        )
    """)
    conn.execute("""
        INSERT INTO canonical_facts (
            fact_id, source_file, section_heading, source_commit, content_hash,
            fact_text, sensitivity_class, allowed_actors, truth_source_id,
            truth_status, verification_required, verification_evidence_id
        ) VALUES
        ('f1', 'file1.md', 'h1', 'c1', 'h1', 'text1', 'sens1', 'act1', 'ts1', 'declared', 1, NULL),
        ('f2', 'file1.md', 'h1', 'c1', 'h1', 'text2', 'sens1', 'act1', 'ts1', 'declared', 1, NULL),
        ('f3', 'file2.md', 'h2', 'c2', 'h2', 'text3', 'sens2', 'act2', 'ts2', 'test_verified', 0, 'ev1')
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
    # Check listing format
    assert "- ID: f1 | Source: file1.md | Section: h1 | Status: declared" in captured.out
    assert "Boundary note: Truth status describes verification posture, not runtime authority." in captured.out
    # Ensure fact_text is NOT printed
    assert "text1" not in captured.out

def test_report_filters(temp_db, capsys):
    # Filter by status
    run_report(temp_db, truth_status='declared')
    captured = capsys.readouterr()
    assert "Total facts: 2" in captured.out

    # Filter by source (exact match)
    run_report(temp_db, source='file2.md')
    captured = capsys.readouterr()
    assert "Total facts: 1" in captured.out
    assert "Source: file2.md" in captured.out

    # Filter by source (no match)
    run_report(temp_db, source='missing.md')
    captured = capsys.readouterr()
    assert "No canonical facts found matching the criteria." in captured.out

    # Filter by verification (requires=1)
    run_report(temp_db, verification_required=1)
    captured = capsys.readouterr()
    assert "Total facts: 2" in captured.out

def test_report_empty_db(tmp_path, capsys):
    db_path = tmp_path / "empty.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE canonical_facts (fact_id TEXT PRIMARY KEY, source_file TEXT, section_heading TEXT, fact_text TEXT, truth_status TEXT, verification_required INTEGER)")
    conn.commit()
    conn.close()

    run_report(str(db_path))
    captured = capsys.readouterr()
    assert "No canonical facts found matching the criteria." in captured.out
