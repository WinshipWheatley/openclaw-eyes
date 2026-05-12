import pytest
import os
import sqlite3
import json
from scripts.answer_harness import answer_operator_question
from business_ops_ledger import init_business_ops_ledger, record_canonical_fact

DB_PATH = "test_answer_harness.sqlite"

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_business_ops_ledger(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_valid_intent_success():
    # Insert a dummy fact
    record_canonical_fact(
        "f1", "doc1.md", "Status", "commit1",
        "We are at the checkpoint v1.", "non_sensitive", ["OpenClaw"], "cat1", "doc", "desc",
        "t1", "declared", 1, None, DB_PATH
    )
    result = answer_operator_question(DB_PATH, "where are we?")
    assert result["status"] == "SUCCESS"
    assert result["intent_matched"] == "WHERE_ARE_WE"
    assert "We are at the checkpoint v1." in result["answer"]
    assert len(result["provenance"]) == 1
    assert result["provenance"][0]["fact_id"] == "f1"
    # New truth checks
    assert "truth_source_id" in result["provenance"][0]
    assert result["provenance"][0]["truth_status"] == "declared"
    assert "truth_summary" in result
    assert result["truth_summary"]["verification_required_count"] == 1

def test_answer_is_from_fact_text():
    record_canonical_fact(
        "f2", "doc2.md", "Mapping Table", "commit2",
        "Fact text content.", "non_sensitive", ["OpenClaw"], "cat2", "doc", "desc",
        "t2", "test_verified", 0, "ev2", DB_PATH
    )
    result = answer_operator_question(DB_PATH, "what is built?")
    assert result["answer"] == "Fact text content."
    assert result["provenance"][0]["truth_status"] == "test_verified"
    assert result["provenance"][0]["verification_required"] is False
    assert result["truth_summary"]["has_test_verified"] is True

def test_provenance_contains_required_fields():
    record_canonical_fact(
        "f3", "doc3.md", "Terrain vs Declaration", "commit3",
        "Boundaries.", "non_sensitive", ["OpenClaw"], "cat3", "doc", "desc",
        "t3", "declared", 1, None, DB_PATH
    )
    result = answer_operator_question(DB_PATH, "what are the boundaries?")
    prov = result["provenance"][0]
    assert "fact_id" in prov
    assert "source_file" in prov
    assert "section_heading" in prov
    assert "source_commit" in prov
    assert "content_hash" in prov
    assert "truth_source_id" in prov
