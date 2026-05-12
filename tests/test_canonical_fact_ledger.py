
import pytest
import sqlite3
import os
from business_ops_ledger import init_business_ops_ledger, record_canonical_fact

DB_PATH = "test_ledger.sqlite"

@pytest.fixture(autouse=True)
def setup_db():
    init_business_ops_ledger(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_record_canonical_fact_success():
    assert record_canonical_fact(
        fact_id="f1",
        source_file="doc.md",
        section_heading="Overview",
        source_commit="abc123",
        fact_text="This is a test fact.",
        sensitivity_class="public_canonical",
        allowed_actors=["admin"],
        doc_category="test",
        temporal_or_doctrine="test",
        source_description="test",
        db_path=DB_PATH
    )

def test_rejects_empty_fact_text():
    with pytest.raises(ValueError, match="fact_text cannot be empty"):
        record_canonical_fact("f2", "doc.md", "Overview", "abc", "", "public_canonical", [], None, None, None, DB_PATH)

def test_rejects_missing_provenance():
    with pytest.raises(ValueError, match="Missing mandatory provenance fields"):
        record_canonical_fact("f3", "", "Overview", "abc", "fact", "public_canonical", [], None, None, None, DB_PATH)

def test_rejects_unsafe_sensitivity():
    with pytest.raises(ValueError, match="Invalid sensitivity_class"):
        record_canonical_fact("f4", "d.md", "O", "a", "fact", "SUPER_SECRET", [], None, None, None, DB_PATH)

def test_rejects_pii():
    with pytest.raises(ValueError, match="PII detected in fact_text"):
        record_canonical_fact("f5", "d.md", "O", "a", "Contact me at bob@example.com", "public_canonical", [], None, None, None, DB_PATH)
    with pytest.raises(ValueError, match="PII detected in fact_text"):
        record_canonical_fact("f6", "d.md", "O", "a", "My SSN is 123-45-6789", "public_canonical", [], None, None, None, DB_PATH)
    with pytest.raises(ValueError, match="PII detected in fact_text"):
        record_canonical_fact("f7", "d.md", "O", "a", "Call 555-555-5555", "public_canonical", [], None, None, None, DB_PATH)

def test_data_integrity():
    record_canonical_fact(
        fact_id="f8",
        source_file="doc.md",
        section_heading="Overview",
        source_commit="abc123",
        fact_text="Stable fact content.",
        sensitivity_class="non_sensitive",
        allowed_actors=["user"],
        doc_category="cat",
        temporal_or_doctrine="doc",
        source_description="desc",
        db_path=DB_PATH
    )
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT content_hash, sensitivity_class, doc_category FROM canonical_facts WHERE fact_id = 'f8'")
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    import hashlib
    expected_hash = hashlib.sha256("Stable fact content.".encode("utf-8")).hexdigest()
    assert row[0] == expected_hash
    assert row[1] == "non_sensitive"
    assert row[2] == "cat"
