import json
from pathlib import Path
import pytest

import invoice_review_action_request_handler
import live_arts_md_invoice_review_bundle
import openclaw_request_processor

@pytest.fixture
def temp_export(tmp_path):
    return tmp_path

def test_valid_mac_pdf_export_writes_receipt_and_updates_bundle(temp_export):
    raw_request = {
        "request_id": "test_req_1",
        "intended_use": "selected_invoice_pdf_export_completed_candidate",
        "client_ref": "live_arts_md",
        "workflow_ref": "live_arts_md_invoice_workflow",
        "invoice_id": "2026-1001",
        "exported_pdf_mac_path": "/Users/test/Desktop/invoice.pdf",
    }
    
    result = invoice_review_action_request_handler.process_selected_invoice_pdf_export_completed_candidate_result_request(
        raw_request,
        export_root=temp_export,
    )
    
    assert result["status"] == "GUIDED_RESULT_RECORDED"
    assert "pdf_export_candidate_receipt" in result["action_start_receipt"]["receipt_id"]
    
    # Check receipt was written
    receipt_path = temp_export / "selected_invoice_pdf_export_completed_candidate_receipt.json"
    assert receipt_path.exists()
    
    # Check bundle was written and updated
    bundle_path = temp_export / "live_arts_md_invoice_review_bundle.json"
    assert bundle_path.exists()
    bundle = json.loads(bundle_path.read_text())
    
    assert bundle["invoice_artifact"]["pdf_export_package"]["status"] == "PDF_EXPORT_COMPLETED_CANDIDATE"
    assert bundle["clara_email_draft"]["attachment_ready"] is False
    assert bundle["send_readiness"]["approval_ready"] is False
    assert bundle["payment_watch"]["ledger_posting_allowed"] is False
    assert bundle["invoice_artifact"]["artifact_review_status"] == "OPERATOR_REVIEW_REQUIRED"

def test_missing_pdf_path_is_rejected(temp_export):
    raw_request = {
        "request_id": "test_req_2",
        "intended_use": "selected_invoice_pdf_export_completed_candidate",
        "client_ref": "live_arts_md",
        "workflow_ref": "live_arts_md_invoice_workflow",
        "invoice_id": "2026-1001",
    }
    
    result = invoice_review_action_request_handler.process_selected_invoice_pdf_export_completed_candidate_result_request(
        raw_request,
        export_root=temp_export,
    )
    
    assert result["status"] == "BLOCKED_INVALID_RESULT"
    assert "MISSING_PDF_PATH" in result["action_start_receipt"]["validation_errors"]
    
def test_wrong_client_workflow_invoice_rejected(temp_export):
    raw_request = {
        "request_id": "test_req_3",
        "intended_use": "selected_invoice_pdf_export_completed_candidate",
        "client_ref": "wrong_client",
        "workflow_ref": "wrong_workflow",
        "invoice_id": "9999",
        "exported_pdf_mac_path": "/Users/test/Desktop/invoice.pdf",
    }
    
    result = invoice_review_action_request_handler.process_selected_invoice_pdf_export_completed_candidate_result_request(
        raw_request,
        export_root=temp_export,
    )
    
    assert result["status"] == "BLOCKED_INVALID_RESULT"
    errors = result["action_start_receipt"]["validation_errors"]
    assert "WRONG_CLIENT" in errors
    assert "WRONG_WORKFLOW" in errors
    assert "WRONG_INVOICE_ID" in errors

def test_explicit_route_matches(temp_export):
    raw_request = {
        "request_id": "test_req_4",
        "request_type": "LOCAL_SURFACE_RESULT",
        "intended_use": "selected_invoice_pdf_export_completed_candidate",
        "client_ref": "live_arts_md",
        "workflow_ref": "live_arts_md_invoice_workflow",
        "invoice_id": "2026-1001",
        "exported_pdf_mac_path": "/Users/test/Desktop/invoice.pdf",
    }
    
    req_path = temp_export / "test_req_4.json"
    req_path.write_text(json.dumps(raw_request))
    
    classification = openclaw_request_processor.RequestClassification(
        classification_id="test",
        source_request_filename="test_req_4.json",
        request_family="LOCAL_SURFACE_RESULT",
        selected_rail="selected_invoice_pdf_export_completed_candidate.live_arts_md",
        classification_reason="test",
        future_supported=False,
        next_safe_move="test",
    )
    
    route_decision = {
        "selected_handler_id": "selected_invoice_pdf_export_completed_candidate.live_arts_md"
    }
    
    response = openclaw_request_processor._process_selected_invoice_pdf_export_completed_result_request(
        req_path,
        raw_request,
        export_root=temp_export,
        generated_at=None,
        classification=classification,
        route_decision=route_decision
    )
    
    assert response.internal_status == "RESPONSE_READY"
    assert response.request_type == "LOCAL_SURFACE_RESULT"
    assert response.workflow_ref == "live_arts_md_invoice_workflow"
