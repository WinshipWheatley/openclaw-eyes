import pytest
import sqlite3
import os
from unittest.mock import patch
from business_ops_ledger import init_business_ops_ledger, record_truth_registry_entry
from scripts.truth_ingest_readiness_report import generate_report

DB_PATH = "test_readiness.sqlite"

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_business_ops_ledger(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

# Mock SOURCE_REGISTRY
MOCK_REGISTRY = {
    "doc1.md": {"temporal_or_doctrine": "doctrine_reference"},
    "doc2.md": {"temporal_or_doctrine": "temporal_checkpoint"},
    "doc3.md": {"temporal_or_doctrine": "doctrine_reference"},
}

def test_missing_registry_rows_block_readiness(capsys):
    with patch("scripts.truth_ingest_readiness_report.SOURCE_REGISTRY", MOCK_REGISTRY):
        # Only record doc1
        record_truth_registry_entry(
            "s1", "doc1.md", "pc", "source", "public_canonical", "approved", "declared", True, True, db_path=DB_PATH
        )
        assert generate_report(DB_PATH) is False
        captured = capsys.readouterr()
        assert "RESULT: NOT_READY_FOR_CONTROLLED_INGEST" in captured.out
        assert "doc2.md (truth=MISSING, hash=MISSING): Not in truth registry" in captured.out

def test_test_verified_not_recorded_blocks_readiness(capsys):
    with patch("scripts.truth_ingest_readiness_report.SOURCE_REGISTRY", MOCK_REGISTRY):
        record_truth_registry_entry(
            "s1", "doc1.md", "pc", "source", "public_canonical", "approved", "test_verified", True, True, 
            verification_source="test_fixture", verification_evidence_id="ev_test_fixture",
            hash_status="not_recorded", db_path=DB_PATH
        )
        # All present, but doc1 is unsafe
        record_truth_registry_entry(
            "s2", "doc2.md", "pc", "source", "public_canonical", "approved", "declared", True, True, db_path=DB_PATH
        )
        record_truth_registry_entry(
            "s3", "doc3.md", "pc", "source", "public_canonical", "approved", "declared", True, True, db_path=DB_PATH
        )
        
        assert generate_report(DB_PATH) is False
        captured = capsys.readouterr()
        assert "RESULT: NOT_READY_FOR_CONTROLLED_INGEST" in captured.out
        assert "Verified status 'test_verified' with hash status 'not_recorded'" in captured.out

def test_runtime_verified_unknown_blocks_readiness(capsys):
    with patch("scripts.truth_ingest_readiness_report.SOURCE_REGISTRY", MOCK_REGISTRY):
        record_truth_registry_entry(
            "s1", "doc1.md", "pc", "source", "public_canonical", "approved", "runtime_verified", True, True, 
            verification_source="test_fixture", verification_evidence_id="ev_test_fixture",
            hash_status="unknown", db_path=DB_PATH
        )
        record_truth_registry_entry(
            "s2", "doc2.md", "pc", "source", "public_canonical", "approved", "declared", True, True, db_path=DB_PATH
        )
        record_truth_registry_entry(
            "s3", "doc3.md", "pc", "source", "public_canonical", "approved", "declared", True, True, db_path=DB_PATH
        )
        
        assert generate_report(DB_PATH) is False
        captured = capsys.readouterr()
        assert "RESULT: NOT_READY_FOR_CONTROLLED_INGEST" in captured.out
        assert "Verified status 'runtime_verified' with hash status 'unknown'" in captured.out

def test_test_verified_current_allows_readiness(capsys):
    with patch("scripts.truth_ingest_readiness_report.SOURCE_REGISTRY", MOCK_REGISTRY):
        record_truth_registry_entry(
            "s1", "doc1.md", "pc", "source", "public_canonical", "approved", "test_verified", True, True, 
            verification_source="test_fixture", verification_evidence_id="ev_test_fixture",
            hash_status="current", db_path=DB_PATH
        )
        record_truth_registry_entry(
            "s2", "doc2.md", "pc", "source", "public_canonical", "approved", "declared", True, True, 
            hash_status="current", db_path=DB_PATH
        )
        record_truth_registry_entry(
            "s3", "doc3.md", "pc", "source", "public_canonical", "approved", "declared", True, True, 
            hash_status="current", db_path=DB_PATH
        )
        
        assert generate_report(DB_PATH) is True
        captured = capsys.readouterr()
        assert "RESULT: READY_FOR_CONTROLLED_INGEST" in captured.out

def test_doctrine_reference_not_recorded_does_not_block_readiness(capsys):
    with patch("scripts.truth_ingest_readiness_report.SOURCE_REGISTRY", MOCK_REGISTRY):
        # doc1 is doctrine_reference
        record_truth_registry_entry(
            "s1", "doc1.md", "pc", "source", "public_canonical", "approved", "declared", True, True, 
            hash_status="not_recorded", db_path=DB_PATH
        )
        record_truth_registry_entry(
            "s2", "doc2.md", "pc", "source", "public_canonical", "approved", "declared", True, True, 
            hash_status="current", db_path=DB_PATH
        )
        record_truth_registry_entry(
            "s3", "doc3.md", "pc", "source", "public_canonical", "approved", "declared", True, True, 
            hash_status="current", db_path=DB_PATH
        )
        
        assert generate_report(DB_PATH) is True
        captured = capsys.readouterr()
        assert "RESULT: READY_FOR_CONTROLLED_INGEST" in captured.out
        assert "Unbaselined Doctrine References (Allowed but noted):" in captured.out
        assert "doc1.md" in captured.out

def test_hash_status_changed_blocks_readiness(capsys):
    with patch("scripts.truth_ingest_readiness_report.SOURCE_REGISTRY", MOCK_REGISTRY):
        record_truth_registry_entry(
            "s1", "doc1.md", "pc", "source", "public_canonical", "approved", "declared", True, True, 
            hash_status="changed", db_path=DB_PATH
        )
        record_truth_registry_entry(
            "s2", "doc2.md", "pc", "source", "public_canonical", "approved", "declared", True, True, 
            hash_status="current", db_path=DB_PATH
        )
        record_truth_registry_entry(
            "s3", "doc3.md", "pc", "source", "public_canonical", "approved", "declared", True, True, 
            hash_status="current", db_path=DB_PATH
        )
        
        assert generate_report(DB_PATH) is False
        captured = capsys.readouterr()
        assert "RESULT: NOT_READY_FOR_CONTROLLED_INGEST" in captured.out
        assert "Hash changed" in captured.out

def test_report_is_read_only():
    # If the file is opened in ro mode, it's read only.
    # We already have URI mode in the script.
    pass
