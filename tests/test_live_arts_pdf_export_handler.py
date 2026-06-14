import json
import hashlib
from datetime import datetime
from pathlib import Path
import pytest

import invoice_review_action_request_handler
import live_arts_md_invoice_review_bundle
import openclaw_request_processor
import selected_invoice_pdf_export_operator_assistance_annotation as assistance_annotation

@pytest.fixture
def temp_export(tmp_path):
    return tmp_path


def _live_bundle(payload):
    return payload.get("live_arts_md_bundle", payload)


def _failed_export_request(**overrides):
    request = {
        "request_id": "test_failed_pdf_export",
        "request_type": "INVOICE_REVIEW_ACTION_RESULT",
        "type": "INVOICE_REVIEW_ACTION_RESULT",
        "kind": "INVOICE_REVIEW_ACTION_RESULT",
        "intended_use": "selected_invoice_pdf_export_completed_candidate",
        "action_kind": "selected_invoice_pdf_export_completed_candidate",
        "client_ref": "live_arts_md",
        "workflow_ref": "live_arts_md_invoice_workflow",
        "invoice_id": "2026-1001",
        "export_attempted": True,
        "export_success": False,
        "failure_code": "EXCEL_APPLESCRIPT_FAILED",
        "failure_message": "Microsoft Excel got an error: The object you are trying to access does not exist",
        "failed_stage": "apple_script_export",
        "artifact_filename": Path("Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental.pdf"),
    }
    request.update(overrides)
    return request


ACTIVE_CANDIDATE_SHA256 = "c4eac79c7b04bb7d3b8650fbf891a72c66c3cc376287a13a12b09ec56ef21bf3"


def _seed_active_pdf_candidate_review(export_root: Path, *, sha256: str = ACTIVE_CANDIDATE_SHA256, page_count: int = 1) -> None:
    export_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "read_model_id": "live_arts_md_invoice_review_bundle",
        "live_arts_md_bundle": {
            "invoice_artifact": {
                "artifact_candidate_review": {
                    "status": "OPERATOR_REVIEW_REQUIRED",
                    "artifact_review_status": "OPERATOR_REVIEW_REQUIRED",
                    "candidate_valid_for_operator_review": True,
                    "candidate_ref": "pdf_export_candidate_receipt:95913871095d32dd",
                    "client_ref": "live_arts_md",
                    "workflow_ref": "live_arts_md_invoice_workflow",
                    "invoice_id": "2026-1001",
                    "selected_invoice_id": "2026-1001",
                    "selected_sheet_label": "June 2026 Speaker Rental",
                    "selected_invoice_amount": 900,
                    "pdf_bridge_path": (
                        "/mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md/2026-1001/"
                        "Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental_scope_corrected_live_arts_md_2.pdf"
                    ),
                    "pdf_mac_path": (
                        "/Volumes/openclaw_e/artifacts/invoice_workbooks/live_arts_md/2026-1001/"
                        "Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental_scope_corrected_live_arts_md_2.pdf"
                    ),
                    "sha256": sha256,
                    "page_count": page_count,
                    "observed_page_count": page_count,
                    "expected_page_count": 1,
                    "attachment_ready": False,
                    "approval_ready": False,
                    "ledger_posting_allowed": False,
                    "sent": False,
                    "paid": False,
                }
            }
        },
    }
    (export_root / live_arts_md_invoice_review_bundle.JSON_EXPORT_NAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _pdf_candidate_decision_request(**overrides):
    request = {
        "request_id": "live_arts_md_pdf_candidate_decision_fixture",
        "request_type": "INVOICE_REVIEW_ACTION_RESULT",
        "type": "INVOICE_REVIEW_ACTION_RESULT",
        "kind": "INVOICE_REVIEW_ACTION_RESULT",
        "intended_use": "selected_invoice_pdf_candidate_review_decision",
        "action_kind": "approve_pdf_candidate",
        "client_ref": "live_arts_md",
        "workflow_ref": "live_arts_md_invoice_workflow",
        "world_ref": "finance",
        "invoice_id": "2026-1001",
        "candidate_ref": "pdf_export_candidate_receipt:95913871095d32dd",
        "candidate_sha256": ACTIVE_CANDIDATE_SHA256,
        "observed_page_count": 1,
        "expected_page_count": 1,
        "operator_visual_review": True,
        "email_send_allowed": False,
        "ledger_posting_allowed": False,
        "browser_access_allowed": False,
        "portal_access_allowed": False,
        "attachment_ready": False,
        "approval_ready": False,
        "sent": False,
        "paid": False,
        "authority_boundary": dict(invoice_review_action_request_handler.AUTHORITY_BOUNDARY),
    }
    request.update(overrides)
    return request


def _process_pdf_candidate_decision(export_root: Path, request: dict) -> dict:
    return invoice_review_action_request_handler.process_action_request(
        request,
        export_root=export_root,
        bridge_export_root=None,
        db_path=export_root.parent / "invoice_review_state.sqlite",
        event_db_path=export_root.parent / "operator_action_events.sqlite",
        event_export_root=export_root,
    )


def _write_pdf(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n% Live Arts MD test approved artifact\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_completed_pdf_export_candidate(export_root: Path, *, pdf_path: Path, sha256: str) -> None:
    receipt = {
        "receipt_id": "pdf_export_candidate_receipt:95913871095d32dd",
        "receipt_type": "selected_invoice_pdf_export_completed_candidate_receipt",
        "receipt_name": "selected_invoice_pdf_export_completed_candidate_receipt",
        "client_ref": "live_arts_md",
        "workflow_ref": "live_arts_md_invoice_workflow",
        "invoice_id": "2026-1001",
        "exported_pdf_mac_path": (
            "/Volumes/openclaw_e/artifacts/invoice_workbooks/live_arts_md/2026-1001/"
            "Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental_scope_corrected_live_arts_md_2.pdf"
        ),
        "output_bridge_path": pdf_path.as_posix(),
        "pdf_bridge_path": pdf_path.as_posix(),
        "artifact_filename": pdf_path.name,
        "file_size_bytes": pdf_path.stat().st_size,
        "sha256": sha256,
        "export_attempted": True,
        "export_success": True,
        "result_status": "PDF_EXPORT_COMPLETED_CANDIDATE",
        "artifact_review_status": "OPERATOR_REVIEW_REQUIRED",
        "page_count": 1,
        "expected_page_count": 1,
        "failed_candidate_sha256": "fc2b9d9448307ddbcaff7d087b05c8b8e1af5c547caf6103dfc3b14162b84640",
        "failed_candidate_artifact_review_status": "SCOPE_MISMATCH_REJECTED",
        "failed_candidate_reason_code": "WRONG_EXPORT_SCOPE_WORKBOOK_INSTEAD_OF_SELECTED_INVOICE_PAGE",
        "observed_failed_candidate_page_count": 7,
        "final_candidate_parent_ref": "live_arts_md_2026_1001_failed_7_page_candidate",
        "attachment_ready": False,
        "approval_ready": False,
        "email_send_allowed": False,
        "ledger_posting_allowed": False,
        "sent": False,
        "paid": False,
        "validation_errors": [],
    }
    annotation = assistance_annotation.build_annotation(
        candidate_receipt_payload=receipt,
        candidate_receipt_path="generated/read_models/selected_invoice_pdf_export_completed_candidate_receipt.json",
        export_root=export_root,
        bridge_export_root=None,
        generated_at="2026-05-28T15:00:00+00:00",
    )
    (export_root / "selected_invoice_pdf_export_completed_candidate_receipt.json").write_text(
        live_arts_md_invoice_review_bundle.stable_json(receipt),
        encoding="utf-8",
    )
    (export_root / "selected_invoice_pdf_export_operator_assistance_annotation.json").write_text(
        assistance_annotation.stable_json(annotation),
        encoding="utf-8",
    )


def test_approve_pdf_candidate_with_false_authority_fields_is_decision_only(temp_export):
    _seed_active_pdf_candidate_review(temp_export)

    result = _process_pdf_candidate_decision(temp_export, _pdf_candidate_decision_request())
    receipt = result["action_start_receipt"]

    assert result["status"] == "GUIDED_RESULT_RECORDED"
    assert receipt["receipt_name"] == "selected_invoice_pdf_candidate_review_decision_receipt"
    assert receipt["decision_status"] == "APPROVED_FOR_DRAFT_ATTACHMENT_PACKAGE"
    assert receipt["operator_decision_only"] is True
    assert receipt["candidate_sha256"] == ACTIVE_CANDIDATE_SHA256
    assert receipt["observed_page_count"] == receipt["expected_page_count"] == 1
    assert receipt["attachment_ready"] is False
    assert receipt["approval_ready"] is False
    assert receipt["ledger_posting_allowed"] is False
    assert receipt["sent"] is False
    assert receipt["paid"] is False
    assert result["machine_proof"]["email_send_performed"] is False
    assert result["machine_proof"]["ledger_posting_performed"] is False
    assert result["machine_proof"]["browser_access_performed"] is False
    assert (temp_export / "selected_invoice_pdf_candidate_review_decision_receipt.json").exists()


def test_approve_pdf_candidate_refreshes_bundle_to_approved_artifact_when_export_receipt_exists(temp_export):
    pdf_path = temp_export / "artifacts" / "Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental_scope_corrected_live_arts_md_2.pdf"
    sha256 = _write_pdf(pdf_path)
    _seed_active_pdf_candidate_review(temp_export, sha256=sha256)
    _seed_completed_pdf_export_candidate(temp_export, pdf_path=pdf_path, sha256=sha256)

    result = _process_pdf_candidate_decision(
        temp_export,
        _pdf_candidate_decision_request(candidate_sha256=sha256),
    )
    bundle_payload = json.loads((temp_export / "live_arts_md_invoice_review_bundle.json").read_text(encoding="utf-8"))
    artifact = bundle_payload["live_arts_md_bundle"]["invoice_artifact"]

    assert result["status"] == "GUIDED_RESULT_RECORDED"
    assert result["state_machine_progress"]["source_bundle_path"].endswith("live_arts_md_invoice_review_bundle.json")
    assert artifact["status"] == "PDF_ARTIFACT_OPERATOR_APPROVED"
    assert artifact["artifact_review_status"] == "APPROVED_FOR_DRAFT_ATTACHMENT_PACKAGE"
    assert "artifact_candidate_review" not in artifact
    assert artifact["approved_pdf_artifact"]["sha256"] == sha256
    assert artifact["approved_pdf_artifact"]["source_candidate_ref"] == "pdf_export_candidate_receipt:95913871095d32dd"
    assert artifact["draft_attachment_package_eligible"] is True
    assert artifact["attachment_ready"] is False
    assert artifact["sent"] is False
    assert artifact["paid"] is False
    assert artifact["email_send_allowed"] is False
    assert artifact["ledger_posting_allowed"] is False


def test_approve_pdf_candidate_with_authority_fields_absent_is_decision_only(temp_export):
    _seed_active_pdf_candidate_review(temp_export)
    request = _pdf_candidate_decision_request()
    for key in (
        "email_send_allowed",
        "ledger_posting_allowed",
        "browser_access_allowed",
        "portal_access_allowed",
        "attachment_ready",
        "approval_ready",
        "sent",
        "paid",
        "authority_boundary",
    ):
        request.pop(key, None)

    result = _process_pdf_candidate_decision(temp_export, request)

    assert result["status"] == "GUIDED_RESULT_RECORDED"
    assert result["action_start_receipt"]["decision_status"] == "APPROVED_FOR_DRAFT_ATTACHMENT_PACKAGE"
    assert result["action_start_receipt"]["email_send_performed"] is False


@pytest.mark.parametrize(
    "field",
    ("email_send_allowed", "ledger_posting_allowed", "browser_access_allowed", "portal_access_allowed"),
)
def test_approve_pdf_candidate_blocks_true_external_authority_grants(temp_export, field):
    _seed_active_pdf_candidate_review(temp_export)
    request = _pdf_candidate_decision_request(**{field: True})

    result = _process_pdf_candidate_decision(temp_export, request)

    assert result["status"] == "BLOCKED_EXTERNAL_AUTHORITY"
    assert result["action_start_receipt"]["completion_receipt_written"] is False
    assert not (temp_export / "selected_invoice_pdf_candidate_review_decision_receipt.json").exists()


@pytest.mark.parametrize("field", ("sent", "paid"))
def test_approve_pdf_candidate_blocks_sent_or_paid_claims(temp_export, field):
    _seed_active_pdf_candidate_review(temp_export)

    result = _process_pdf_candidate_decision(temp_export, _pdf_candidate_decision_request(**{field: True}))

    assert result["status"] == "BLOCKED_EXTERNAL_AUTHORITY"
    assert result["machine_proof"]["email_send_performed"] is False
    assert result["machine_proof"]["ledger_posting_performed"] is False


def test_approve_pdf_candidate_rejects_candidate_sha_mismatch(temp_export):
    _seed_active_pdf_candidate_review(temp_export)

    result = _process_pdf_candidate_decision(
        temp_export,
        _pdf_candidate_decision_request(candidate_sha256="0" * 64),
    )

    assert result["status"] == "BLOCKED_PREREQUISITES"
    assert "CANDIDATE_SHA_MISMATCH" in result["action_start_receipt"]["validation_errors"]
    assert result["action_start_receipt"]["attachment_ready"] is False


def test_approve_pdf_candidate_rejects_page_count_mismatch(temp_export):
    _seed_active_pdf_candidate_review(temp_export)

    result = _process_pdf_candidate_decision(
        temp_export,
        _pdf_candidate_decision_request(observed_page_count=7),
    )

    assert result["status"] == "BLOCKED_PREREQUISITES"
    assert "CANDIDATE_PAGE_COUNT_MISMATCH" in result["action_start_receipt"]["validation_errors"]
    assert "PDF_CANDIDATE_PAGE_COUNT_MISMATCH" in result["action_start_receipt"]["validation_errors"]


def test_reject_pdf_candidate_accepts_unknown_desired_page_without_external_action(temp_export):
    _seed_active_pdf_candidate_review(temp_export)
    request = _pdf_candidate_decision_request(
        action_kind="reject_pdf_candidate",
        observed_page_count=1,
        expected_page_count=1,
        reason_code="OPERATOR_REJECTED_AFTER_VISUAL_REVIEW",
        desired_page_known=False,
    )

    result = _process_pdf_candidate_decision(temp_export, request)
    receipt = result["action_start_receipt"]

    assert result["status"] == "GUIDED_RESULT_RECORDED"
    assert receipt["decision_status"] == "REJECTED_BY_OPERATOR"
    assert receipt["attachment_ready"] is False
    assert receipt["approval_ready"] is False
    assert receipt["ledger_posting_allowed"] is False
    assert receipt["sent"] is False
    assert receipt["paid"] is False


def test_failed_helper_receipt_with_path_values_serializes_cleanly(temp_export):
    raw_request = _failed_export_request()

    result = invoice_review_action_request_handler.process_selected_invoice_pdf_export_completed_candidate_result_request(
        raw_request,
        export_root=temp_export,
        bridge_export_root=None,
    )

    receipt_path = temp_export / "selected_invoice_pdf_export_completed_candidate_receipt.json"
    response_json = invoice_review_action_request_handler.stable_json(
        {
            "result": result,
            "path": Path("/tmp/openclaw/pathlike"),
            "created_at": datetime(2026, 5, 31, 12, 0, 0),
            "set_value": {"b", "a"},
            "tuple_value": (Path("/tmp/openclaw/tuple-path"),),
        }
    )
    parsed = json.loads(response_json)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert parsed["path"] == "/tmp/openclaw/pathlike"
    assert parsed["tuple_value"] == ["/tmp/openclaw/tuple-path"]
    assert receipt["artifact_filename"] == "Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental.pdf"
    assert receipt["failure_code"] == "EXCEL_APPLESCRIPT_FAILED"


def test_failed_helper_receipt_records_structured_failure_without_attachment_ready(temp_export):
    result = invoice_review_action_request_handler.process_selected_invoice_pdf_export_completed_candidate_result_request(
        _failed_export_request(),
        export_root=temp_export,
        bridge_export_root=None,
    )
    bundle_payload = json.loads((temp_export / "live_arts_md_invoice_review_bundle.json").read_text(encoding="utf-8"))
    bundle = _live_bundle(bundle_payload)
    local_result = result["local_surface_result"]

    assert result["status"] == "GUIDED_FAILURE_RECORDED"
    assert bundle_payload["read_model_id"] == "live_arts_md_invoice_review_bundle"
    assert result["headline"] == "PDF Export Failed"
    assert result["action_start_receipt"]["failure_code"] == "EXCEL_APPLESCRIPT_FAILED"
    assert result["action_start_receipt"]["failure_message"].startswith("Microsoft Excel got an error")
    assert local_result["artifact_review_status"] == "EXPORT_FAILED"
    assert local_result["attachment_ready"] is False
    assert local_result["approval_ready"] is False
    assert local_result["ledger_posting_allowed"] is False
    assert local_result["sent"] is False
    assert local_result["paid"] is False
    assert local_result["final"] is False
    assert bundle["invoice_artifact"]["artifact_review_status"] == "EXPORT_FAILED"
    package = bundle["invoice_artifact"]["pdf_export_package"]
    assert package["status"] == "EXPORT_FAILED"
    assert package["invoice_id"] == "2026-1001"
    assert package["selected_sheet_label"] == "June 2026 Speaker Rental"
    assert package["selected_page_label"] == "page 1"
    assert package["selected_print_areas"] == [
        "June 2026 Speaker Rental!G2:G5",
        "June 2026 Speaker Rental!F40:G43",
        "June 2026 Speaker Rental!B49:G53",
    ]
    assert package["output_pdf_mac_path"] == (
        "/Volumes/openclaw_e/artifacts/invoice_workbooks/live_arts_md/2026-1001/"
        "Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental.pdf"
    )
    assert "/selected-invoice/" not in package["output_pdf_mac_path"]
    assert bundle["clara_email_draft"]["attachment_ready"] is False
    assert bundle["approval_footer"]["approval_ready"] is False
    assert bundle["payment_watch"]["ledger_posting_allowed"] is False
    assert result["machine_proof"]["email_send_performed"] is False
    assert result["machine_proof"]["gmail_access_performed"] is False
    assert result["machine_proof"]["browser_access_performed"] is False
    assert result["machine_proof"]["coupa_browser_automation_performed"] is False
    assert result["machine_proof"]["ledger_posting_performed"] is False

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
        bridge_export_root=None,
    )

    assert result["status"] == "GUIDED_RESULT_RECORDED"
    assert "pdf_export_candidate_receipt" in result["action_start_receipt"]["receipt_id"]

    # Check receipt was written
    receipt_path = temp_export / "selected_invoice_pdf_export_completed_candidate_receipt.json"
    assert receipt_path.exists()

    # Check bundle was written and updated
    bundle_path = temp_export / "live_arts_md_invoice_review_bundle.json"
    assert bundle_path.exists()
    bundle_payload = json.loads(bundle_path.read_text())
    bundle = _live_bundle(bundle_payload)

    assert bundle_payload["read_model_id"] == "live_arts_md_invoice_review_bundle"
    assert bundle["invoice_artifact"]["pdf_export_package"]["status"] == "PDF_EXPORT_COMPLETED_CANDIDATE"
    assert bundle["clara_email_draft"]["attachment_ready"] is False
    assert bundle["send_readiness"]["approval_ready"] is False
    assert bundle["payment_watch"]["ledger_posting_allowed"] is False
    assert bundle["invoice_artifact"]["artifact_review_status"] == "OPERATOR_REVIEW_REQUIRED"


def test_corrected_mac_pdf_export_receipt_preserves_scope_and_failed_candidate_lineage(temp_export):
    raw_request = {
        "request_id": "test_corrected_pdf_export",
        "request_type": "INVOICE_REVIEW_ACTION_RESULT",
        "intended_use": "selected_invoice_pdf_export_completed_candidate",
        "action_kind": "selected_invoice_pdf_export_completed_candidate",
        "client_ref": "live_arts_md",
        "workflow_ref": "live_arts_md_invoice_workflow",
        "invoice_id": "2026-1001",
        "export_attempted": True,
        "export_success": True,
        "exported_pdf_mac_path": (
            "/Volumes/openclaw_e/artifacts/invoice_workbooks/live_arts_md/2026-1001/"
            "Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental_scope_corrected_live_arts_md_2.pdf"
        ),
        "artifact_filename": "Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental_scope_corrected_live_arts_md_2.pdf",
        "file_size_bytes": 109494,
        "sha256": "c4eac79c7b04bb7d3b8650fbf891a72c66c3cc376287a13a12b09ec56ef21bf3",
        "page_count": 1,
        "expected_output_page_count": 1,
        "selected_sheet_label": "June 2026 Speaker Rental",
        "selected_page_label": "fresh selected worksheet export",
        "selected_invoice_amount": 900,
        "operator_assisted": True,
        "fully_unattended": False,
        "failed_candidate_sha256": "fc2b9d9448307ddbcaff7d087b05c8b8e1af5c547caf6103dfc3b14162b84640",
        "observed_failed_candidate_page_count": 7,
        "final_candidate_parent_ref": "live_arts_md_2026_1001_failed_7_page_candidate",
        "scope_correction_applied": True,
    }

    result = invoice_review_action_request_handler.process_selected_invoice_pdf_export_completed_candidate_result_request(
        raw_request,
        export_root=temp_export,
        bridge_export_root=None,
    )
    receipt = json.loads(
        (temp_export / "selected_invoice_pdf_export_completed_candidate_receipt.json").read_text(encoding="utf-8")
    )

    assert result["status"] == "GUIDED_RESULT_RECORDED"
    assert receipt["pdf_bridge_path"] == (
        "/mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md/2026-1001/"
        "Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental_scope_corrected_live_arts_md_2.pdf"
    )
    assert receipt["page_count"] == 1
    assert receipt["expected_page_count"] == 1
    assert receipt["operator_assisted"] is True
    assert receipt["fully_unattended"] is False
    assert receipt["failed_candidate_sha256"] == "fc2b9d9448307ddbcaff7d087b05c8b8e1af5c547caf6103dfc3b14162b84640"
    assert receipt["failed_candidate_artifact_review_status"] == "SCOPE_MISMATCH_REJECTED"
    assert receipt["failed_candidate_reason_code"] == "WRONG_EXPORT_SCOPE_WORKBOOK_INSTEAD_OF_SELECTED_INVOICE_PAGE"
    assert receipt["attachment_ready"] is False
    assert receipt["approval_ready"] is False
    assert receipt["ledger_posting_allowed"] is False

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
        bridge_export_root=None,
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
        bridge_export_root=None,
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
    assert all(isinstance(item, str) for item in response.readback_files)
