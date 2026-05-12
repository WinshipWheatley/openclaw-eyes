
import pytest
import sqlite3
import os
import subprocess
from scripts.ingest_canonical_docs import ALLOWED_SOURCE

DB_PATH = "test_ingestion.sqlite"

@pytest.fixture(autouse=True)
def cleanup():
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def test_ingest_allowed_path():
    # Create mock file
    with open(ALLOWED_SOURCE, "w") as f:
        f.write("# Title\n## Header\nFact content.")

    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    cmd = ["python3", "scripts/ingest_canonical_docs.py", "--db", DB_PATH, "--source", ALLOWED_SOURCE]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert "Successfully ingested" in result.stdout

    # Verify in DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM canonical_facts")
    rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0][1] == ALLOWED_SOURCE
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
    # Setup: ensure source file exists and record original content
    original_content = "# Title\n## Header\nFact content."
    with open(ALLOWED_SOURCE, "w") as f:
        f.write(original_content)

    import hashlib
    original_hash = hashlib.sha256(original_content.encode("utf-8")).hexdigest()

    # Execution
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    cmd = ["python3", "scripts/ingest_canonical_docs.py", "--db", DB_PATH, "--source", ALLOWED_SOURCE]
    subprocess.run(cmd, env=env, check=True)

    # Verification
    with open(ALLOWED_SOURCE, "r") as f:
        new_content = f.read()

    new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()
    assert new_content == original_content
    assert new_hash == original_hash
