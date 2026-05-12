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

def test_answer_harness_refused():
    result = answer_operator_question(DB_PATH, "unknown question")
    assert result["status"] == "REFUSED"

def test_answer_harness_not_enough_context():
    result = answer_operator_question(DB_PATH, "where are we?")
    assert result["status"] == "NOT_ENOUGH_CONTEXT"

def test_valid_intent_gateway_success(monkeypatch):
    # Insert a dummy fact
    record_canonical_fact(
        "f1", "doc1.md", "Status", "commit1",
        "Raw fact text.", "non_sensitive", ["OpenClaw"], "cat1", "doc", "desc",
        "t1", "declared", 1, None, DB_PATH
    )

    from scripts.truth_reconciliation_gateway import MODEL_ALLOWED_VERIFIED

    # Mock gateway to simulate PASS
    def mock_packet(db_path, fact_id, question, allow_reconciliation=False):
        return {
            "status": MODEL_ALLOWED_VERIFIED,
            "state": MODEL_ALLOWED_VERIFIED,
            "verified_facts": [{
                "id": fact_id,
                "text": "Verified fact text from gateway.",
                "labels": "[REPO-SOURCE] [HASH-CURRENT] [DECLARED] [VERIFY_REQUIRED]",
                "provenance": {
                    "fact_id": fact_id,
                    "source_file": "doc1.md",
                    "source_commit": "commit1",
                    "content_hash": "h1",
                    "truth_source_id": "t1",
                    "truth_status": "declared",
                    "verification_required": True,
                    "verification_evidence_id": None
                }
            }],
            "answer_boundary": "Only answer from verified_facts.",
            "runtime_authority": False,
            "transitions": ["CANDIDATE_SURFACED", "CHECK_RUNNING", "NO_DIFF_FOUND", "PACKET_READY", MODEL_ALLOWED_VERIFIED]
        }

    monkeypatch.setattr("scripts.truth_reconciliation_gateway.build_llm_truth_packet", mock_packet)

    result = answer_operator_question(DB_PATH, "where are we?")
    assert result["status"] == "SUCCESS"
    assert "Verified fact text from gateway." in result["answer"]
    assert "Raw fact text." not in result["answer"]
    assert result["provenance"][0]["labels"] == "[REPO-SOURCE] [HASH-CURRENT] [DECLARED] [VERIFY_REQUIRED]"
    assert result["answer_boundary"] == "Only answer from verified_facts."
    assert result["runtime_authority"] is False
    assert result["truth_summary"]["gateway_transitions"][-1] == MODEL_ALLOWED_VERIFIED

def test_valid_intent_gateway_blocked(monkeypatch):
    # Insert a dummy fact
    record_canonical_fact(
        "f2", "doc2.md", "Mapping Table", "commit2",
        "Raw fact text.", "non_sensitive", ["OpenClaw"], "cat2", "doc", "desc",
        "t2", "declared", 1, None, DB_PATH
    )

    # Mock gateway to simulate BLOCK
    def mock_packet_blocked(db_path, fact_id, question, allow_reconciliation=False):
        return {
            "status": "MODEL_BLOCKED",
            "state": "MODEL_BLOCKED",
            "block_reason": "Hash mismatch detected.",
            "transitions": ["CANDIDATE_SURFACED", "CHECK_RUNNING", "DIFF_FOUND", "MODEL_BLOCKED"],
            "verified_facts": []
        }

    monkeypatch.setattr("scripts.truth_reconciliation_gateway.build_llm_truth_packet", mock_packet_blocked)

    result = answer_operator_question(DB_PATH, "what is built?")
    assert result["status"] == "MODEL_BLOCKED"
    assert "Hash mismatch detected." in result["answer"]
    assert "Raw fact text." not in result["answer"]
    assert result["truth_summary"]["blocked"] is True
    assert len(result["provenance"]) == 0

def test_integration_ish_success(tmp_path, monkeypatch):
    # Real-ish integration: setup DB and a dummy file on disk
    db_path = str(tmp_path / "integration.sqlite")
    init_business_ops_ledger(db_path)

    source_file = tmp_path / "doc3.md"
    source_content = b"Content of doc3"
    source_file.write_bytes(source_content)
    import hashlib
    source_hash = hashlib.sha256(source_content).hexdigest()

    # Insert into truth registry
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT INTO truth_registry_entries (
            source_id, observed_path, source_content_hash, hash_status, truth_status,
            origin_machine, sync_role, sensitivity_class, approval_status,
            verification_required, canonical_eligible
        )
        VALUES ('t3', ?, ?, 'current', 'doctrine_reference', 'pc', 'source', 'operational_canonical', 'approved', 1, 1)
    """, (str(source_file), source_hash))
    conn.commit()
    conn.close()

    # Insert fact
    record_canonical_fact(
        "f3", str(source_file), "Terrain vs Declaration", "commit3",
        "Fact 3 text.", "non_sensitive", ["OpenClaw"], "cat3", "doc", "desc",
        "t3", "doctrine_reference", 1, None, db_path
    )

    # Mock SOURCE_REGISTRY to include our temp file
    monkeypatch.setattr("scripts.truth_reconciliation_gateway.SOURCE_REGISTRY", {str(source_file): {}})

    # Now call answer_harness (it should use the real build_llm_truth_packet logic)
    result = answer_operator_question(db_path, "what are the boundaries?")
    assert result["status"] == "SUCCESS"
    assert "Fact 3 text." in result["answer"]
    assert "[HASH-CURRENT]" in result["provenance"][0]["labels"]

def test_answer_harness_allow_reconciliation_integration(tmp_path, monkeypatch):
    db_path = str(tmp_path / "reconciliation.sqlite")
    init_business_ops_ledger(db_path)

    source_file = tmp_path / "doc4.md"
    source_content = b"Content of doc4"
    source_file.write_bytes(source_content)
    import hashlib
    source_hash = hashlib.sha256(source_content).hexdigest()

    # Insert into truth registry with 'changed' status
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT INTO truth_registry_entries (
            source_id, observed_path, source_content_hash, hash_status, truth_status,
            origin_machine, sync_role, sensitivity_class, approval_status,
            verification_required, canonical_eligible
        )
        VALUES ('t4', ?, ?, 'changed', 'doctrine_reference', 'pc', 'source', 'operational_canonical', 'approved', 1, 1)
    """, (str(source_file), source_hash))
    conn.commit()
    conn.close()

    # Insert fact
    record_canonical_fact(
        "f4", str(source_file), "Status", "commit4",
        "Fact 4 text.", "non_sensitive", ["OpenClaw"], "cat4", "doc", "desc",
        "t4", "doctrine_reference", 1, None, db_path
    )

    monkeypatch.setattr("scripts.truth_reconciliation_gateway.SOURCE_REGISTRY", {str(source_file): {}})

    # Default (no reconciliation) should fail
    result = answer_operator_question(db_path, "where are we?")
    assert result["status"] == "MODEL_BLOCKED"

    # With reconciliation allowed, it should pass
    result = answer_operator_question(db_path, "where are we?", allow_reconciliation=True)
    assert result["status"] == "SUCCESS"
    assert "RECONCILIATION_APPLIED" in result["truth_summary"]["gateway_transitions"]

    # Verify DB was repaired
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT hash_status FROM truth_registry_entries WHERE source_id = 't4'").fetchone()
    conn.close()
    assert row[0] == 'current'

def test_uncertain_packet_handling(monkeypatch):
    # record_canonical_fact is already done by fixtures or manually in previous tests?
    # Actually setup_db is autouse=True and it clears the DB.
    # I'll use record_canonical_fact here.
    from business_ops_ledger import record_canonical_fact
    record_canonical_fact(
        "fu1", "u1.md", "Status", "c1",
        "Uncertain fact text.", "non_sensitive", ["OpenClaw"], "cat1", "doc", "desc",
        "tu1", "declared", 1, None, DB_PATH
    )

    from scripts.truth_reconciliation_gateway import MODEL_ALLOWED_UNCERTAIN

    def mock_packet_uncertain(db_path, fact_id, question, allow_reconciliation=False):
        return {
            "status": MODEL_ALLOWED_UNCERTAIN,
            "uncertainty_status": "verification_required_no_evidence",
            "confidence_band": "medium_provisional",
            "uncertainty_reason": "source_integrity_passed_but_verification_evidence_missing",
            "fact_text": "Uncertain fact text from gateway.",
            "source_file": "u1.md",
            "source_commit": "c1",
            "content_hash": "h1",
            "source_content_hash_status": "current",
            "truth_source_id": "tu1",
            "truth_status": "declared",
            "verification_required": True,
            "verification_evidence_id": None,
            "answer_boundary": "Qualified language required (e.g., 'records indicate', 'provisionally'). Forbid hard-truth phrasing.",
            "runtime_authority": False,
            "transitions": ["CANDIDATE_SURFACED", "CHECK_RUNNING", "NO_DIFF_FOUND", "PACKET_READY", MODEL_ALLOWED_UNCERTAIN]
        }

    monkeypatch.setattr("scripts.truth_reconciliation_gateway.build_llm_truth_packet", mock_packet_uncertain)

    result = answer_operator_question(DB_PATH, "where are we?")
    assert result["status"] == "SUCCESS"
    assert "Based on currently available evidence, this appears to be provisional" in result["answer"]
    assert "Uncertain fact text from gateway." in result["answer"]
    assert result["truth_summary"]["has_uncertain_facts"] is True
    assert result["runtime_authority"] is False
    assert "Qualified language required" in result["answer_boundary"]
