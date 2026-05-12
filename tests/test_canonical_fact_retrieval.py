import pytest
import sqlite3
import os
from business_ops_ledger import (
    init_business_ops_ledger,
    record_canonical_fact,
    get_canonical_facts_by_source,
    get_canonical_facts_by_heading
)

DB_PATH = "test_retrieval.sqlite"

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_business_ops_ledger(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_retrieval_functions():
    # Insert facts
    record_canonical_fact(
        "f1", "doc1.md", "Header1", "commit1",
        "Fact text 1", "public_canonical", ["agent1"], "cat1", "doc1", "desc1", DB_PATH
    )
    record_canonical_fact(
        "f2", "doc2.md", "Header2", "commit2",
        "Fact text 2", "public_canonical", ["agent2"], "cat2", "doc2", "desc2", DB_PATH
    )

    # Test source retrieval
    facts = get_canonical_facts_by_source("doc1.md", DB_PATH)
    assert len(facts) == 1
    assert facts[0]["fact_id"] == "f1"
    assert facts[0]["allowed_actors"] == ["agent1"]
    assert facts[0]["doc_category"] == "cat1"

    # Test heading retrieval
    facts = get_canonical_facts_by_heading("Header2", DB_PATH)
    assert len(facts) == 1
    assert facts[0]["fact_id"] == "f2"
    assert facts[0]["doc_category"] == "cat2"

    # Test empty result
    facts = get_canonical_facts_by_source("none.md", DB_PATH)
    assert len(facts) == 0

def test_read_only_mode():
    record_canonical_fact(
        "f3", "doc3.md", "Header3", "commit3",
        "Fact text 3", "public_canonical", ["agent3"], "cat3", "doc3", "desc3", DB_PATH
    )
    facts = get_canonical_facts_by_source("doc3.md", DB_PATH)
    assert len(facts) == 1
