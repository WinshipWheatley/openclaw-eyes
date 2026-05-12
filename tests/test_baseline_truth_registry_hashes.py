import pytest
import os
import sqlite3
import sys
import hashlib
from unittest.mock import patch
from scripts.baseline_truth_registry_hashes import main as baseline_main
from business_ops_ledger import init_business_ops_ledger, record_truth_registry_entry, _query_truth_registry

@pytest.fixture
def temp_db(tmp_path):
    db_path = str(tmp_path / "test_ledger.sqlite")
    init_business_ops_ledger(db_path)
    return db_path

@pytest.fixture
def test_files(tmp_path):
    # Create test files
    os.makedirs(tmp_path / "test_docs", exist_ok=True)
    doc1_path = tmp_path / "test_docs/doc1.md"
    doc1_path.write_text("# Doc 1 Content")
    
    doc2_path = tmp_path / "test_docs/doc2.md"
    doc2_path.write_text("# Doc 2 Content")
    
    return {
        "doc1": str(doc1_path),
        "doc2": str(doc2_path)
    }

def test_baseline_requires_allow_hashing(temp_db, test_files, capsys):
    with patch("scripts.baseline_truth_registry_hashes.SOURCE_REGISTRY", {test_files["doc1"]: {}}):
        with patch("sys.argv", ["baseline", "--db", temp_db]):
            with pytest.raises(SystemExit) as exc:
                baseline_main()
            assert exc.value.code == 1
            captured = capsys.readouterr()
            assert "Error: --allow-hashing is required" in captured.out

def test_dry_run_lists_candidates(temp_db, test_files, capsys):
    # Setup registry entry
    record_truth_registry_entry(
        source_id="src1",
        observed_path=test_files["doc1"],
        origin_machine="pc",
        sync_role="source",
        sensitivity_class="public",
        approval_status="approved",
        truth_status="declared",
        verification_required=True,
        canonical_eligible=True,
        db_path=temp_db
    )
    
    with patch("scripts.baseline_truth_registry_hashes.SOURCE_REGISTRY", {test_files["doc1"]: {}}):
        with patch("sys.argv", ["baseline", "--db", temp_db, "--dry-run"]):
            baseline_main()
            captured = capsys.readouterr()
            assert "planned_candidate: Would check hash" in captured.out
            
            # Verify no hash written
            rows = _query_truth_registry("SELECT * FROM truth_registry_entries", (), temp_db)
            assert rows[0]["source_content_hash"] is None

def test_baseline_applied(temp_db, test_files, capsys):
    record_truth_registry_entry(
        source_id="src1",
        observed_path=test_files["doc1"],
        origin_machine="pc",
        sync_role="source",
        sensitivity_class="public",
        approval_status="approved",
        truth_status="test_verified",
        verification_required=False,
        canonical_eligible=True,
        verification_evidence_id="ev1",
        db_path=temp_db
    )
     
    with patch("scripts.baseline_truth_registry_hashes.SOURCE_REGISTRY", {test_files["doc1"]: {}}):
        with patch("sys.argv", ["baseline", "--db", temp_db, "--allow-hashing"]):
            baseline_main()
            captured = capsys.readouterr()
            assert "baseline_applied: Hash recorded" in captured.out
            
            # Verify hash written
            rows = _query_truth_registry("SELECT * FROM truth_registry_entries", (), temp_db)
            assert rows[0]["source_content_hash"] is not None
            assert rows[0]["hash_status"] == "current"
            assert rows[0]["truth_status"] == "test_verified" # Preserved
            assert rows[0]["verification_evidence_id"] == "ev1" # Preserved

def test_baseline_rerun_same_content(temp_db, test_files, capsys):
    # First baseline
    record_truth_registry_entry(
        source_id="src1",
        observed_path=test_files["doc1"],
        origin_machine="pc",
        sync_role="source",
        sensitivity_class="public",
        approval_status="approved",
        truth_status="declared",
        verification_required=True,
        canonical_eligible=True,
        db_path=temp_db
    )
    
    with patch("scripts.baseline_truth_registry_hashes.SOURCE_REGISTRY", {test_files["doc1"]: {}}):
        with patch("sys.argv", ["baseline", "--db", temp_db, "--allow-hashing"]):
            baseline_main()
            capsys.readouterr()
            
            # Second run
            with patch("sys.argv", ["baseline", "--db", temp_db, "--allow-hashing"]):
                baseline_main()
                captured = capsys.readouterr()
                assert "current: Hash matches baseline" in captured.out

def test_baseline_detects_changed_but_no_invalidate(temp_db, test_files, capsys):
    # First baseline
    record_truth_registry_entry(
        source_id="src1",
        observed_path=test_files["doc1"],
        origin_machine="pc",
        sync_role="source",
        sensitivity_class="public",
        approval_status="approved",
        truth_status="test_verified",
        verification_required=False,
        canonical_eligible=True,
        verification_evidence_id="ev1",
        db_path=temp_db
    )
    
    with patch("scripts.baseline_truth_registry_hashes.SOURCE_REGISTRY", {test_files["doc1"]: {}}):
        with patch("sys.argv", ["baseline", "--db", temp_db, "--allow-hashing"]):
            baseline_main()
            capsys.readouterr()
            
            # Change file
            with open(test_files["doc1"], "w") as f:
                f.write("# Changed Content")
            
            # Second run
            with patch("sys.argv", ["baseline", "--db", temp_db, "--allow-hashing"]):
                baseline_main()
                captured = capsys.readouterr()
                assert "changed_detected_not_applied" in captured.out
                
                # Verify no status change
                rows = _query_truth_registry("SELECT * FROM truth_registry_entries", (), temp_db)
                assert rows[0]["truth_status"] == "test_verified"
                assert rows[0]["hash_status"] == "current" # Still says current in DB because we didn't update it

def test_baseline_source_limit(temp_db, test_files, capsys):
    record_truth_registry_entry(source_id="src1", observed_path=test_files["doc1"], origin_machine="pc", sync_role="source", sensitivity_class="public", approval_status="approved", truth_status="declared", verification_required=True, canonical_eligible=True, db_path=temp_db)
    record_truth_registry_entry(source_id="src2", observed_path=test_files["doc2"], origin_machine="pc", sync_role="source", sensitivity_class="public", approval_status="approved", truth_status="declared", verification_required=True, canonical_eligible=True, db_path=temp_db)
    
    mock_registry = {test_files["doc1"]: {}, test_files["doc2"]: {}}
    with patch("scripts.baseline_truth_registry_hashes.SOURCE_REGISTRY", mock_registry):
        # Target only doc1
        with patch("sys.argv", ["baseline", "--db", temp_db, "--allow-hashing", "--source", test_files["doc1"]]):
            baseline_main()
            captured = capsys.readouterr()
            assert "doc1" in captured.out
            assert "doc2" not in captured.out

def test_baseline_reject_non_registry(temp_db, test_files, capsys):
    with patch("scripts.baseline_truth_registry_hashes.SOURCE_REGISTRY", {test_files["doc1"]: {}}):
        with patch("sys.argv", ["baseline", "--db", temp_db, "--allow-hashing", "--source", "fake.md"]):
            with pytest.raises(SystemExit) as exc:
                baseline_main()
            assert exc.value.code == 1
            captured = capsys.readouterr()
            assert "is not in SOURCE_REGISTRY" in captured.out

def test_baseline_missing_registry_row(temp_db, test_files, capsys):
    # No registry entry in DB
    with patch("scripts.baseline_truth_registry_hashes.SOURCE_REGISTRY", {test_files["doc1"]: {}}):
        with patch("sys.argv", ["baseline", "--db", temp_db, "--allow-hashing"]):
            baseline_main()
            captured = capsys.readouterr()
            assert "missing: No truth_registry_entries row found" in captured.out
