import os
import sqlite3
import pytest
import json
from scripts.truth_substrate_status import get_truth_substrate_status
from business_ops_ledger import init_business_ops_ledger, record_canonical_fact, record_truth_registry_entry

@pytest.fixture
def temp_db(tmp_path):
    db_path = str(tmp_path / "test_ledger.sqlite")
    init_business_ops_ledger(db_path)
    return db_path

def test_status_unavailable_missing_db():
    status = get_truth_substrate_status("/non/existent/path.sqlite")
    assert status["status"] == "unavailable"
    assert "Database missing" in status["reason"]

def test_status_unavailable_missing_tables(tmp_path):
    db_path = str(tmp_path / "empty.sqlite")
    conn = sqlite3.connect(db_path)
    conn.close()
    status = get_truth_substrate_status(db_path)
    assert status["status"] == "unavailable"
    assert "Missing tables" in status["reason"]

def test_status_metrics_empty_db(temp_db, monkeypatch):
    # Mock SOURCE_REGISTRY to be empty for this test
    monkeypatch.setattr("scripts.truth_substrate_status.SOURCE_REGISTRY", {})
    
    status = get_truth_substrate_status(temp_db)
    assert status["status"] == "available"
    assert status["metrics"]["facts"]["total"] == 0
    assert status["metrics"]["registry"]["total_sources"] == 0
    assert status["metrics"]["readiness"]["is_ready"] is True

def test_status_metrics_populated(temp_db, monkeypatch):
    # Setup facts
    record_canonical_fact(
        fact_id="f1", source_file="doc1.md", section_heading="H1", source_commit="sha1",
        fact_text="Fact 1", sensitivity_class="public_canonical", allowed_actors=["act1"],
        truth_status="doctrine_reference", verification_required=1, db_path=temp_db
    )
    record_canonical_fact(
        fact_id="f2", source_file="doc1.md", section_heading="H2", source_commit="sha1",
        fact_text="Fact 2", sensitivity_class="public_canonical", allowed_actors=["act1"],
        truth_status="historical_checkpoint", verification_required=0, db_path=temp_db
    )

    # Setup registry
    mock_registry = {"doc1.md": {}}
    monkeypatch.setattr("scripts.truth_substrate_status.SOURCE_REGISTRY", mock_registry)
    
    record_truth_registry_entry(
        source_id="s1", observed_path="doc1.md", origin_machine="pc", sync_role="source",
        sensitivity_class="public_canonical", approval_status="approved", truth_status="doctrine_reference",
        verification_required=False, canonical_eligible=True, hash_status="current", db_path=temp_db
    )

    status = get_truth_substrate_status(temp_db)
    assert status["status"] == "available"
    metrics = status["metrics"]
    assert metrics["facts"]["total"] == 2
    assert metrics["facts"]["by_truth_status"]["doctrine_reference"] == 1
    assert metrics["facts"]["by_truth_status"]["historical_checkpoint"] == 1
    assert metrics["facts"]["by_verification_required"][True] == 1
    assert metrics["facts"]["by_verification_required"][False] == 1
    
    assert metrics["registry"]["total_sources"] == 1
    assert metrics["registry"]["present_sources"] == 1
    assert metrics["registry"]["hash_status_counts"]["current"] == 1
    assert metrics["readiness"]["is_ready"] is True

def test_readiness_not_ready_hash_changed(temp_db, monkeypatch):
    mock_registry = {"doc1.md": {}}
    monkeypatch.setattr("scripts.truth_substrate_status.SOURCE_REGISTRY", mock_registry)
    
    record_truth_registry_entry(
        source_id="s1", observed_path="doc1.md", origin_machine="pc", sync_role="source",
        sensitivity_class="public_canonical", approval_status="approved", truth_status="doctrine_reference",
        verification_required=False, canonical_eligible=True, hash_status="changed", db_path=temp_db
    )

    status = get_truth_substrate_status(temp_db)
    assert status["metrics"]["readiness"]["is_ready"] is False
    assert status["metrics"]["readiness"]["result"] == "NOT_READY"

def test_readiness_not_ready_missing_row(temp_db, monkeypatch):
    mock_registry = {"doc1.md": {}}
    monkeypatch.setattr("scripts.truth_substrate_status.SOURCE_REGISTRY", mock_registry)
    
    # doc1.md is in registry but not in DB
    status = get_truth_substrate_status(temp_db)
    assert status["metrics"]["readiness"]["is_ready"] is False
    assert status["metrics"]["readiness"]["unsafe_count"] == 1

def test_readiness_not_ready_verified_not_current(temp_db, monkeypatch):
    mock_registry = {"doc1.md": {}}
    monkeypatch.setattr("scripts.truth_substrate_status.SOURCE_REGISTRY", mock_registry)
    
    record_truth_registry_entry(
        source_id="s1", observed_path="doc1.md", origin_machine="pc", sync_role="source",
        sensitivity_class="public_canonical", approval_status="approved", truth_status="test_verified",
        verification_required=False, canonical_eligible=True, hash_status="not_recorded",
        verification_source="test", db_path=temp_db
    )

    status = get_truth_substrate_status(temp_db)
    assert status["metrics"]["readiness"]["is_ready"] is False

def test_json_output_no_fact_text(temp_db, monkeypatch, capsys):
    record_canonical_fact(
        fact_id="f1", source_file="doc1.md", section_heading="H1", source_commit="sha1",
        fact_text="SECRET_FACT_TEXT", sensitivity_class="public_canonical", allowed_actors=["act1"],
        truth_status="doctrine_reference", verification_required=1, db_path=temp_db
    )
    
    from scripts.truth_substrate_status import main
    import sys
    
    test_args = ["scripts/truth_substrate_status.py", "--db", temp_db, "--json"]
    monkeypatch.setattr("sys.argv", test_args)
    monkeypatch.setattr("scripts.truth_substrate_status.SOURCE_REGISTRY", {})
    
    main()
    
    out, err = capsys.readouterr()
    assert "SECRET_FACT_TEXT" not in out
    data = json.loads(out)
    assert data["status"] == "available"

def test_no_mutation(temp_db, monkeypatch):
    # Verify DB state before
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM canonical_facts")
    count_before = cursor.fetchone()[0]
    conn.close()

    status = get_truth_substrate_status(temp_db)
    
    # Verify DB state after
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM canonical_facts")
    count_after = cursor.fetchone()[0]
    conn.close()
    
    assert count_before == count_after
