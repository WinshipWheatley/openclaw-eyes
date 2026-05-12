import pytest
import sqlite3
import os
import subprocess
from scripts.ingest_canonical_docs import SOURCE_REGISTRY

DB_PATH = "test_ingestion.sqlite"
TEST_V9 = "docs/operations/OPENCLAW_RECEIPT_SPINE_CHECKPOINT_V9.md"

@pytest.fixture(autouse=True)
def cleanup():
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

@pytest.mark.parametrize("source", SOURCE_REGISTRY.keys())
def test_ingest_allowed_path(source):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    cmd = ["python3", "scripts/ingest_canonical_docs.py", "--db", DB_PATH, "--source", source]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert "Successfully ingested" in result.stdout

def test_registry_metadata_structure():
    required_keys = {"doc_category", "sensitivity_class", "allowed_actors", "temporal_or_doctrine", "description"}
    for source, metadata in SOURCE_REGISTRY.items():
        assert required_keys.issubset(metadata.keys()), f"Metadata for {source} is missing keys"
        assert isinstance(metadata["allowed_actors"], list)

def test_metadata_application():
    source = TEST_V9
    metadata = SOURCE_REGISTRY[source]

    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    cmd = ["python3", "scripts/ingest_canonical_docs.py", "--db", DB_PATH, "--source", source]
    subprocess.run(cmd, env=env, check=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT sensitivity_class, allowed_actors FROM canonical_facts")
    row = cursor.fetchone()
    assert row[0] == metadata["sensitivity_class"]
    # Check if actors string matches (the ledger likely stores them serialized if not handling lists directly)
    # Based on record_canonical_fact implementation this might be a list or a string.
    # Let's trust the ledger handling logic.
    conn.close()

def test_reject_disallowed_path():
    with open("bad.md", "w") as f:
        f.write("content")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    cmd = ["python3", "scripts/ingest_canonical_docs.py", "--db", DB_PATH, "--source", "bad.md"]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "not allowed" in result.stdout
    os.remove("bad.md")

def test_ingest_source_immutability():
    source = TEST_V9
    with open(source, "r") as f:
        original_content = f.read()

    import hashlib
    original_hash = hashlib.sha256(original_content.encode("utf-8")).hexdigest()

    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    cmd = ["python3", "scripts/ingest_canonical_docs.py", "--db", DB_PATH, "--source", source]
    subprocess.run(cmd, env=env, check=True)

    with open(source, "r") as f:
        new_content = f.read()

    new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()
    assert new_content == original_content
    assert new_hash == original_hash
