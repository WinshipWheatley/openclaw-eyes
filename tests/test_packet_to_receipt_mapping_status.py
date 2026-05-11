import os
from pathlib import Path
import pytest

MAPPING_DOC_PATH = Path("docs/operations/OPENCLAW_PACKET_TO_RECEIPT_MAPPING_V0.md")

def read_mapping_doc():
    if not MAPPING_DOC_PATH.exists():
        pytest.fail(f"Mapping document not found at {MAPPING_DOC_PATH}")
    return MAPPING_DOC_PATH.read_text(encoding="utf-8")

def get_lines_for_receipt(doc_content, receipt_name):
    lines = doc_content.splitlines()
    return [line for line in lines if receipt_name in line]

def test_mapping_doc_exists():
    assert MAPPING_DOC_PATH.exists()

def test_mapping_doc_conservative_guarantees():
    content = read_mapping_doc()
    
    # Phrase: "This document does not prove receipts are written."
    assert "This document does not prove receipts are written" in content
    
    # Guardrails against ingestion/runtime/schema changes
    assert "Do Not Build Yet" in content
    assert "Broad RAG ingestion" in content
    assert "Gmail body ingestion" in content
    assert "SQLite schema changes" in content

def test_receipt_status_consistencies():
    content = read_mapping_doc()
    
    # 1. action_intent_gate_receipt -> SQLITE_VERIFIED
    lines = get_lines_for_receipt(content, "action_intent_gate_receipt")
    assert any("SQLITE_VERIFIED" in line for line in lines), \
        "action_intent_gate_receipt must be marked SQLITE_VERIFIED in the mapping doc"

    # 2. approval_log_entry -> SQLITE_VERIFIED
    lines = get_lines_for_receipt(content, "approval_log_entry")
    assert any("SQLITE_VERIFIED" in line for line in lines), \
        "approval_log_entry must be marked SQLITE_VERIFIED in the mapping doc"

    # 3. approval_request_record -> NOT SQLITE_VERIFIED
    lines = get_lines_for_receipt(content, "approval_request_record")
    for line in lines:
        assert "SQLITE_VERIFIED" not in line, \
            f"approval_request_record must not be marked SQLITE_VERIFIED: {line}"

    # 4. outreach_email_draft_receipt -> NOT SQLITE_VERIFIED
    lines = get_lines_for_receipt(content, "outreach_email_draft_receipt")
    for line in lines:
        assert "SQLITE_VERIFIED" not in line, \
            f"outreach_email_draft_receipt must not be marked SQLITE_VERIFIED: {line}"

    # 5. pii_vault_record -> DECLARED_ONLY
    lines = get_lines_for_receipt(content, "pii_vault_record")
    assert any("DECLARED_ONLY" in line for line in lines), \
        "pii_vault_record must be marked DECLARED_ONLY in the mapping doc"

    # 6. email_triage_classification -> Notes include JSONL or not SQLite
    lines = get_lines_for_receipt(content, "email_triage_classification")
    relevant_lines = [line for line in lines if "|" in line] # focus on table rows
    assert any("JSONL" in line or "not SQLite" in line for line in relevant_lines), \
        "email_triage_classification must specify it is JSONL or not SQLite"

    # 7. orientation_snapshot_receipt -> SQLITE_VERIFIED
    lines = get_lines_for_receipt(content, "orientation_snapshot_receipt")
    assert any("SQLITE_VERIFIED" in line for line in lines), \
        "orientation_snapshot_receipt must be marked SQLITE_VERIFIED"

    # 8. test_proof_receipt -> SQLITE_VERIFIED
    lines = get_lines_for_receipt(content, "test_proof_receipt")
    assert any("SQLITE_VERIFIED" in line for line in lines), \
        "test_proof_receipt must be marked SQLITE_VERIFIED"
