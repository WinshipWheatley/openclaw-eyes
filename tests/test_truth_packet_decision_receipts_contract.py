import os

def test_truth_packet_decision_receipts_doc_contract():
    """Verify the truth packet decision receipts documentation contains required contract terms."""
    doc_path = "docs/operations/OPENCLAW_TRUTH_PACKET_DECISION_RECEIPTS_V0.md"
    assert os.path.exists(doc_path), f"Missing documentation file: {doc_path}"
    
    with open(doc_path, "r") as f:
        content = f.read()
    
    # Required Type
    assert "truth_packet_decision_receipt" in content
    
    # Required Packet Statuses
    assert "MODEL_ALLOWED_VERIFIED" in content
    assert "MODEL_ALLOWED_UNCERTAIN" in content
    assert "MODEL_BLOCKED" in content
    
    # Safety Fields
    assert "fact_text_crossed_model_boundary" in content
    assert "fact_text_redacted_in_receipt" in content
    assert "runtime_authority" in content
    assert "false" in content.lower() # Verify it is set to false
    
    # Integrity Guarantees
    assert "source hash mismatch" in content.lower()
    assert "MODEL_BLOCKED" in content
    
    # Forbidden Actions
    assert "no truth upgrades" in content.lower()
    assert "no mechanical changes" in content.lower()
    assert "fact_text" in content
    assert "receipts must NEVER store" in content
