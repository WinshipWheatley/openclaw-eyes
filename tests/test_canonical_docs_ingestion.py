import pytest
import sqlite3
import os
import subprocess
from scripts.ingest_canonical_docs import ALLOWED_SOURCES

DB_PATH = "test_ingestion.sqlite"
TEST_V9 = "docs/operations/OPENCLAW_RECEIPT_SPINE_CHECKPOINT_V9.md"
TEST_V2 = "docs/operations/OPENCLAW_KNOWLEDGE_INGESTION_CHECKPOINT_V2.md"
TEST_MAPPING = "docs/operations/OPENCLAW_PACKET_TO_RECEIPT_MAPPING_V0.md"

@pytest.fixture(autouse=True)
def cleanup():
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

@pytest.mark.parametrize("source", ALLOWED_SOURCES)
def test_ingest_allowed_path(source):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    cmd = ["python3", "scripts/ingest_canonical_docs.py", "--db", DB_PATH, "--source", source]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert "Successfully ingested" in result.stdout

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

def test_reject_directory():
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    cmd = ["python3", "scripts/ingest_canonical_docs.py", "--db", DB_PATH, "--source", "docs/operations"]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "not allowed" in result.stdout

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
