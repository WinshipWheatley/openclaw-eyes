import pytest
import sqlite3
import os
import json
from business_ops_ledger import init_business_ops_ledger, append_truth_packet_decision_receipt
from scripts.truth_substrate_status import get_truth_substrate_status
from scripts.generate_operator_status import get_recent_proof_receipts

@pytest.fixture
def temp_ledger(tmp_path):
    db_path = str(tmp_path / "visibility_test.sqlite")
    init_business_ops_ledger(db_path)
    return db_path

def test_truth_substrate_status_reads_receipts(temp_ledger):
    # Record some receipts
    append_truth_packet_decision_receipt(
        packet_status="MODEL_ALLOWED_VERIFIED",
        fact_id="f1",
        fact_text_crossed_model_boundary=True,
        db_path=temp_ledger
    )
    append_truth_packet_decision_receipt(
        packet_status="MODEL_BLOCKED",
        fact_id="f2",
        block_reason="mismatch",
        db_path=temp_ledger
    )

    status = get_truth_substrate_status(temp_ledger)
    assert status["status"] == "available"
    
    dr = status["metrics"]["decision_receipts"]
    assert dr["total"] == 2
    assert dr["by_status"]["MODEL_ALLOWED_VERIFIED"] == 1
    assert dr["by_status"]["MODEL_BLOCKED"] == 1
    
    latest = dr["latest"]
    assert latest["packet_status"] == "MODEL_BLOCKED"
    assert latest["fact_text_crossed_model_boundary"] == 0 # SQLite boolean
    assert latest["fact_text_redacted_in_receipt"] == 1
    assert latest["runtime_authority"] == 0

def test_recent_proof_receipts_includes_truth_decisions(temp_ledger):
    append_truth_packet_decision_receipt(
        packet_status="MODEL_ALLOWED_VERIFIED",
        fact_id="f-verified",
        fact_text_crossed_model_boundary=True,
        db_path=temp_ledger
    )
    
    results = get_recent_proof_receipts(limit=5, db_path=temp_ledger)
    proofs = results["list"]
    
    assert len(proofs) == 1
    assert "[TRUTH_DECISION]" in proofs[0]
    assert "MODEL_ALLOWED_VERIFIED" in proofs[0]
    assert "(Audit Only)" in proofs[0]

def test_visibility_does_not_expose_fact_text(temp_ledger):
    # 1. Record a safe receipt
    append_truth_packet_decision_receipt(
        packet_status="MODEL_ALLOWED_VERIFIED",
        fact_id="safe-fact",
        db_path=temp_ledger
    )

    # 2. Attempt unsafe receipt (must fail)
    with pytest.raises(ValueError):
        append_truth_packet_decision_receipt(
            packet_status="MODEL_BLOCKED",
            fact_id="secret-fact",
            fact_text="THIS IS SECRET", 
            db_path=temp_ledger
        )
    
    status = get_truth_substrate_status(temp_ledger)
    dr = status["metrics"]["decision_receipts"]
    assert dr["total"] == 1 # Only the safe one
    
    latest = dr["latest"]
    assert latest["fact_id"] == "safe-fact"
    
    # Check that the actual secret content is NOT present anywhere
    assert "THIS IS SECRET" not in str(status)
    assert "fact_text" not in latest
    
    results = get_recent_proof_receipts(limit=5, db_path=temp_ledger)
    assert "THIS IS SECRET" not in str(results)

