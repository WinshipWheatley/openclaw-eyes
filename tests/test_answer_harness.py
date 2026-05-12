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
        "f1", "doc1.md", "1. Overview", "commit1",
        "We are at the checkpoint v1.", "non_sensitive", ["OpenClaw"], DB_PATH
    )
    result = answer_operator_question(DB_PATH, "where are we?")
    assert result["status"] == "SUCCESS"
    assert result["intent_matched"] == "WHERE_ARE_WE"
    assert "We are at the checkpoint v1." in result["answer"]
    assert len(result["provenance"]) == 1
    assert result["provenance"][0]["fact_id"] == "f1"

def test_answer_is_from_fact_text():
    record_canonical_fact(
        "f2", "doc2.md", "2. Receipt Spine Status", "commit2",
        "Fact text content.", "non_sensitive", ["OpenClaw"], DB_PATH
    )
    result = answer_operator_question(DB_PATH, "what is built?")
    assert result["answer"] == "Fact text content."

def test_provenance_contains_required_fields():
    record_canonical_fact(
        "f3", "doc3.md", "3. Truth Boundary (Phase A Only)", "commit3",
        "Boundaries.", "non_sensitive", ["OpenClaw"], DB_PATH
    )
    result = answer_operator_question(DB_PATH, "what are the boundaries?")
    prov = result["provenance"][0]
    assert "fact_id" in prov
    assert "source_file" in prov
    assert "section_heading" in prov
    assert "source_commit" in prov
    assert "content_hash" in prov
