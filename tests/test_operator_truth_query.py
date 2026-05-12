import pytest
import sqlite3
import os
import json
import subprocess
from business_ops_ledger import init_business_ops_ledger, record_canonical_fact
from scripts.answer_harness import answer_operator_question

@pytest.fixture
def query_db(tmp_path):
    db_path = tmp_path / "query_test.sqlite"
    init_business_ops_ledger(str(db_path))
    
    # Add a verified fact
    record_canonical_fact(
        "f_v", "doc_v.md", "Status", "c1",
        "Verified fact text.", "non_sensitive", ["OpenClaw"], "cat1", "doc", "desc",
        "t_v", "doctrine_reference", 0, None, str(db_path)
    )
    
    # Add an uncertain fact
    record_canonical_fact(
        "f_u", "doc_u.md", "Status", "c2",
        "Uncertain fact text.", "non_sensitive", ["OpenClaw"], "cat2", "doc", "desc",
        "t_u", "doctrine_reference", 1, None, str(db_path)
    )

    return str(db_path)

def test_operator_truth_query_cli_success(query_db, monkeypatch):
    from scripts.truth_reconciliation_gateway import MODEL_ALLOWED_VERIFIED, MODEL_ALLOWED_UNCERTAIN
    
    # Mock gateway to return specific packets
    def mock_packet_mixed(db_path, fact_id, question, **kwargs):
        if fact_id == "f_v":
            return {
                "status": MODEL_ALLOWED_VERIFIED,
                "verified_facts": [{
                    "id": fact_id,
                    "text": "Verified fact text.",
                    "labels": "[REPO-SOURCE]",
                    "provenance": {
                        "fact_id": fact_id,
                        "source_file": "doc_v.md",
                        "truth_status": "doctrine_reference",
                        "verification_required": False
                    }
                }],
                "answer_boundary": "Boundary V",
                "runtime_authority": False
            }
        else:
            return {
                "status": MODEL_ALLOWED_UNCERTAIN,
                "uncertainty_status": "no_evidence",
                "confidence_band": "low",
                "uncertainty_reason": "missing",
                "fact_text": "Uncertain fact text.",
                "source_file": "doc_u.md",
                "content_hash": "h2",
                "truth_source_id": "t_u",
                "truth_status": "doctrine_reference",
                "verification_required": True,
                "answer_boundary": "Boundary U",
                "runtime_authority": False
            }

    monkeypatch.setattr("scripts.truth_reconciliation_gateway.build_llm_truth_packet", mock_packet_mixed)

    # Instead of subprocess, we'll test the main function directly by mocking sys.argv
    import scripts.operator_truth_query as query
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        monkeypatch.setattr("sys.argv", ["operator_truth_query.py", "where are we?", "--db", query_db])
        query.main()
    
    output = f.getvalue()
    assert "OPERATOR TRUTH QUERY: where are we?" in output
    assert "Status: SUCCESS" in output
    assert "Verified fact text." in output
    assert "Uncertain fact text." in output
    assert "Allowed Candidates:   1" in output
    assert "Uncertain Candidates: 1" in output
    assert "Runtime Authority: False" in output
    assert "Non-authorizing Statement" in output

def test_operator_truth_query_no_receipt_by_default(query_db, monkeypatch):
    import scripts.operator_truth_query as query
    monkeypatch.setattr("sys.argv", ["operator_truth_query.py", "where are we?", "--db", query_db])
    
    # Redirect stdout to suppress output during test
    import io
    from contextlib import redirect_stdout
    with redirect_stdout(io.StringIO()):
        query.main()
    
    conn = sqlite3.connect(query_db)
    count = conn.execute("SELECT count(*) FROM events WHERE event_type = 'truth_packet_decision_receipt'").fetchone()[0]
    conn.close()
    assert count == 0

def test_operator_truth_query_opt_in_receipt(query_db, monkeypatch):
    import scripts.operator_truth_query as query
    monkeypatch.setattr("sys.argv", ["operator_truth_query.py", "where are we?", "--db", query_db, "--record-receipt"])
    
    import io
    from contextlib import redirect_stdout
    with redirect_stdout(io.StringIO()):
        query.main()
    
    conn = sqlite3.connect(query_db)
    count = conn.execute("SELECT count(*) FROM events WHERE event_type = 'truth_packet_decision_receipt'").fetchone()[0]
    conn.close()
    assert count > 0

def test_operator_truth_query_blocked_hides_text(query_db, monkeypatch):
    # Add a fact that will be blocked
    record_canonical_fact(
        "f_blocked", "doc_b.md", "Status", "c3",
        "SECRET TEXT", "non_sensitive", ["OpenClaw"], "cat3", "doc", "desc",
        "t_b", "declared", 0, None, query_db
    )
    
    from scripts.truth_reconciliation_gateway import MODEL_BLOCKED
    
    def mock_packet_blocked(db_path, fact_id, question, **kwargs):
        if fact_id == "f_blocked":
            return {
                "status": MODEL_BLOCKED,
                "block_reason": "Hash mismatch.",
                "verified_facts": []
            }
        return {
            "status": "MODEL_BLOCKED",
            "block_reason": "Other block.",
            "verified_facts": []
        }

    monkeypatch.setattr("scripts.truth_reconciliation_gateway.build_llm_truth_packet", mock_packet_blocked)

    import scripts.operator_truth_query as query
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        monkeypatch.setattr("sys.argv", ["operator_truth_query.py", "where are we?", "--db", query_db])
        query.main()
    
    output = f.getvalue()
    assert "SECRET TEXT" not in output
    assert "Blocked Candidates:   3" in output # f_v, f_u, f_blocked all blocked by mock
    assert "Blocked Reasons: 3 fact(s) blocked." in output
    assert "Hash mismatch." in output
    assert "Other block." in output

def test_operator_truth_query_uncertain_is_qualified(query_db, monkeypatch):
    from scripts.truth_reconciliation_gateway import MODEL_ALLOWED_UNCERTAIN
    
    def mock_packet_uncertain(db_path, fact_id, question, **kwargs):
        return {
            "status": MODEL_ALLOWED_UNCERTAIN,
            "uncertainty_status": "no_evidence",
            "confidence_band": "provisional",
            "uncertainty_reason": "missing",
            "fact_text": "Provisional fact text.",
            "source_file": "doc.md",
            "content_hash": "h1",
            "truth_source_id": "t1",
            "truth_status": "declared",
            "verification_required": True,
            "answer_boundary": "Boundary U",
            "runtime_authority": False
        }

    monkeypatch.setattr("scripts.truth_reconciliation_gateway.build_llm_truth_packet", mock_packet_uncertain)

    import scripts.operator_truth_query as query
    import io
    from contextlib import redirect_stdout

    f = io.StringIO()
    with redirect_stdout(f):
        monkeypatch.setattr("sys.argv", ["operator_truth_query.py", "where are we?", "--db", query_db])
        query.main()
    
    output = f.getvalue()
    assert "Based on currently available evidence, this appears to be provisional" in output
    assert "Provisional fact text." in output
