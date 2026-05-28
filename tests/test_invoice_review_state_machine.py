import json
import sqlite3
from pathlib import Path

import invoice_review_bundle
import invoice_review_state_machine as state_machine


FIXED_NOW = "2026-05-27T19:30:00+00:00"


def _request(action_kind: str, request_id: str | None = None) -> dict:
    bundle = invoice_review_bundle.build_capital_hilton_bundle(generated_at=FIXED_NOW)
    actions = {}
    for action in bundle["correction_actions"]:
        actions[action["action_kind"]] = action
    for step in bundle["review_proof_timeline"]:
        if step["primary_action"]:
            actions[step["primary_action"]["action_kind"]] = step["primary_action"]
            compatibility = step["primary_action"]["hidden_request_payload"].get("compatibility_action_kind")
            if compatibility:
                actions[str(compatibility)] = step["primary_action"]
        for action in step["secondary_actions"]:
            actions[action["action_kind"]] = action
    hidden = dict(actions[action_kind]["hidden_request_payload"])
    hidden["action_kind"] = action_kind
    hidden["request_kind"] = action_kind
    return {
        "request_id": request_id or f"invoice_review_state_{action_kind}",
        "request_type": "INVOICE_REVIEW_ACTION_REQUEST",
        "kind": "INVOICE_REVIEW_ACTION_REQUEST",
        "workflow_ref": invoice_review_bundle.CAPITAL_HILTON_WORKFLOW_REF,
        "client_ref": "capital_hilton",
        "action_kind": action_kind,
        "intended_use": action_kind,
        "hidden_request_payload": hidden,
    }


def _paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    return (
        tmp_path / "state.sqlite",
        tmp_path / "generated" / "read_models",
        tmp_path / "bridge" / "generated" / "read_models",
    )


def _process(tmp_path: Path, action_kind: str):
    db_path, export_root, bridge_root = _paths(tmp_path)
    return state_machine.process_action(
        _request(action_kind),
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_root,
        generated_at=FIXED_NOW,
    )


def _selection_result_request(**overrides):
    request = {
        "request_id": "invoice_record_selection_result_valid",
        "request_type": "LOCAL_SURFACE_RESULT",
        "kind": "LOCAL_SURFACE_RESULT",
        "type": "LOCAL_SURFACE_RESULT",
        "intended_use": "confirm_invoice_record_selection",
        "client_ref": "capital_hilton",
        "workflow_ref": invoice_review_bundle.CAPITAL_HILTON_WORKFLOW_REF,
        "source_action_ref": "start_invoice_record_selection",
        "operator_provided": True,
        "operator_confirmed": True,
        "invoice_period_label": "May 2026",
        "invoice_page_label": "Capital Hilton May invoice page",
        "generated_candidate_disposition": "wrong_page",
        "operator_notes": "Use the May page.",
        "no_workbook_body_read": True,
        "no_cell_read": True,
        "no_ocr": True,
        "no_external_action": True,
        "no_generation_export": True,
    }
    request.update(overrides)
    return request


def _process_selection_result(tmp_path: Path, **overrides):
    db_path, export_root, bridge_root = _paths(tmp_path)
    return state_machine.process_invoice_record_selection_result(
        _selection_result_request(**overrides),
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_root,
        generated_at=FIXED_NOW,
    )


def test_confirm_source_workbook_writes_completion_receipt_and_refreshes_bundle(tmp_path):
    db_path, export_root, bridge_root = _paths(tmp_path)

    result = state_machine.process_action(
        _request("confirm_source_workbook_reference"),
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_root,
        generated_at=FIXED_NOW,
    )
    receipt = state_machine.read_receipt(db_path, result.action_receipt["receipt_id"])
    source_bundle = json.loads((export_root / invoice_review_bundle.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    bridge_bundle = json.loads((bridge_root / invoice_review_bundle.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    active = next(step for step in source_bundle["capital_hilton_bundle"]["review_proof_timeline"] if step["title"] == "Active workbook")

    assert receipt["receipt_name"] == "active_workbook_confirmed_receipt"
    assert receipt["completion_receipt_written"] == 1
    assert result.state_snapshot["source_workbook_status"] == "CONFIRMED"
    assert active["status"] == "COMPLETE"
    assert source_bundle["capital_hilton_bundle"]["invoice_selection"]["active_workbook_state"] == "ACTIVE_WORKBOOK_CONFIRMED"
    assert bridge_bundle["capital_hilton_bundle"]["bundle_id"] == invoice_review_bundle.CAPITAL_HILTON_BUNDLE_ID
    assert result.bridge_mirror_written is True


def test_replace_source_workbook_requests_replacement_without_deletion(tmp_path):
    result = _process(tmp_path, "replace_source_workbook_reference")

    assert result.status == "REQUESTED"
    assert "No file will be deleted" in result.body
    assert result.action_receipt["receipt_event"] == "source_workbook_replacement_requested"
    assert result.action_receipt["completion_receipt_written"] is False
    assert result.state_snapshot["source_workbook_status"] == "REPLACEMENT_REQUESTED"
    assert state_machine.AUTHORITY_BOUNDARY["file_deletion_performed"] is False


def test_start_invoice_record_selection_writes_action_start_and_requests_operator_selection(tmp_path):
    db_path, export_root, _ = _paths(tmp_path)
    result = _process(tmp_path, "start_invoice_record_selection")
    source_bundle = json.loads((export_root / invoice_review_bundle.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    invoice_step = next(step for step in source_bundle["capital_hilton_bundle"]["review_proof_timeline"] if step["title"] == "Invoice page/period")

    assert result.action_receipt["receipt_name"] == "invoice_record_selection_started_receipt"
    assert result.action_receipt["receipt_event"] == "invoice_record_selection_started"
    assert result.action_receipt["completion_receipt_written"] is False
    assert result.state_snapshot["invoice_record_selection_status"] == "NEEDS_OPERATOR_SELECTION"
    assert invoice_step["status"] == "IN_PROGRESS"
    assert "invoice_record_selected_receipt" not in state_machine.receipt_names(db_path)
    assert source_bundle["capital_hilton_bundle"]["excel_invoice_artifact"]["proof_status"] == "GENERATED_INVOICE_ARTIFACT_CANDIDATE"
    assert source_bundle["capital_hilton_bundle"]["excel_invoice_artifact"]["attachment_ready"] is False
    assert source_bundle["capital_hilton_bundle"]["approval_footer"]["approval_ready"] is False


def test_regenerate_or_link_artifact_blocks_until_invoice_record_selected(tmp_path):
    result = _process(tmp_path, "regenerate_or_link_invoice_artifact")

    assert result.status == "BLOCKED_NEEDS_INVOICE_RECORD_SELECTION"
    assert result.action_receipt["completion_receipt_written"] is False
    assert result.headline == "Invoice artifact needs selection receipt"
    assert "selection receipt" in result.body
    assert state_machine.AUTHORITY_BOUNDARY["invoice_generation_performed"] is False
    assert state_machine.AUTHORITY_BOUNDARY["pdf_export_performed"] is False


def test_regenerate_or_link_artifact_requires_operator_selection_receipt(tmp_path):
    db_path, export_root, bridge_root = _paths(tmp_path)
    state_machine.init_store(db_path)
    state = state_machine.load_state(db_path, generated_at=FIXED_NOW)
    state["invoice_record_selection_status"] = "OPERATOR_CONFIRMED"
    state["invoice_period_status"] = "OPERATOR_CONFIRMED"
    state["invoice_period_label"] = "May 2026"
    state["invoice_record_label"] = "May tab / page 2"
    with state_machine._connect(db_path) as conn:
        state_machine._upsert_state(conn, state)

    result = state_machine.process_action(
        _request("regenerate_or_link_invoice_artifact"),
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_root,
        generated_at=FIXED_NOW,
    )

    assert result.status == "BLOCKED_NEEDS_INVOICE_RECORD_SELECTION"
    assert "selection receipt" in result.body


def test_regenerate_or_link_artifact_after_selection_returns_generator_not_wired_without_output(tmp_path):
    db_path, export_root, bridge_root = _paths(tmp_path)
    selection = state_machine.process_invoice_record_selection_result(
        _selection_result_request(),
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_root,
        generated_at=FIXED_NOW,
    )
    result = state_machine.process_action(
        _request("regenerate_or_link_invoice_artifact"),
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_root,
        generated_at=FIXED_NOW,
    )
    source_bundle = json.loads((export_root / invoice_review_bundle.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    bridge_bundle = json.loads((bridge_root / invoice_review_bundle.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    capital = source_bundle["capital_hilton_bundle"]

    assert selection.action_receipt["receipt_name"] == "invoice_record_selection_operator_confirmed_receipt"
    assert result.status == "GENERATOR_NOT_WIRED"
    assert result.action_receipt["receipt_name"] == "invoice_artifact_generator_not_wired_receipt"
    assert result.action_receipt["receipt_event"] == "invoice_artifact_generator_not_wired"
    assert result.action_receipt["completion_receipt_written"] is False
    assert result.action_receipt["artifact_metadata"]["metadata_status"] == "GENERATED_ARTIFACT_METADATA_VALID"
    assert result.action_receipt["generator_audit"]["existing_generator_found"] is True
    assert "invoice_artifact_builder" in result.action_receipt["generator_audit"]["generator_refs"]
    assert result.action_receipt["generator_audit"]["generator_status"] == "GENERATOR_NOT_WIRED"
    assert result.action_receipt["generator_audit"]["artifact_created"] is False
    assert result.action_receipt["generator_audit"]["artifact_linked"] is False
    assert result.action_receipt["artifact_metadata"]["workbook_business_cells_read"] is False
    assert result.action_receipt["artifact_metadata"]["generation_or_export_performed"] is False
    assert result.state_snapshot["generated_artifact_status"] == "ARTIFACT_GENERATOR_NOT_WIRED"
    assert result.state_snapshot["generated_artifact_generator_status"] == "GENERATOR_NOT_WIRED"
    assert capital["invoice_selection"]["invoice_record_state"] == "INVOICE_RECORD_OPERATOR_CONFIRMED"
    assert capital["excel_invoice_artifact"]["proof_status"] == "ARTIFACT_GENERATOR_NOT_WIRED"
    assert capital["excel_invoice_artifact"]["linkage_status"] == "NEEDS_REGENERATION_OR_LINK"
    assert capital["excel_invoice_artifact"]["attachment_ready"] is False
    assert capital["approval_footer"]["approval_ready"] is False
    assert bridge_bundle["capital_hilton_bundle"]["excel_invoice_artifact"]["linkage_status"] == "NEEDS_REGENERATION_OR_LINK"
    assert state_machine.AUTHORITY_BOUNDARY["spreadsheet_cell_read_performed"] is False
    assert state_machine.AUTHORITY_BOUNDARY["invoice_generation_performed"] is False
    assert state_machine.AUTHORITY_BOUNDARY["pdf_export_performed"] is False


def test_regenerate_or_link_artifact_marks_invalid_candidate_not_attach_ready(tmp_path, monkeypatch):
    bad_artifact = tmp_path / "bad.xlsx"
    bad_artifact.write_text("not an xlsx package", encoding="utf-8")
    monkeypatch.setattr(invoice_review_bundle, "CAPITAL_HILTON_EXCEL_PATH", bad_artifact)
    db_path, export_root, bridge_root = _paths(tmp_path)
    state_machine.process_invoice_record_selection_result(
        _selection_result_request(),
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_root,
        generated_at=FIXED_NOW,
    )

    result = state_machine.process_action(
        _request("regenerate_or_link_invoice_artifact"),
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_root,
        generated_at=FIXED_NOW,
    )
    source_bundle = json.loads((export_root / invoice_review_bundle.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert result.status == "GENERATED_ARTIFACT_INVALID"
    assert result.action_receipt["receipt_name"] == "generated_invoice_artifact_invalid_receipt"
    assert result.action_receipt["artifact_metadata"]["metadata_status"] == "GENERATED_ARTIFACT_INVALID"
    assert source_bundle["capital_hilton_bundle"]["excel_invoice_artifact"]["linkage_status"] == "INVALID_METADATA"
    assert source_bundle["capital_hilton_bundle"]["excel_invoice_artifact"]["attachment_ready"] is False
    assert source_bundle["capital_hilton_bundle"]["approval_footer"]["approval_ready"] is False


def test_supplier_portal_proof_action_writes_intake_receipt_without_submission(tmp_path):
    result = _process(tmp_path, "request_supplier_portal_submission_proof")

    assert result.action_receipt["receipt_name"] == "supplier_portal_proof_intake_requested_receipt"
    assert result.action_receipt["receipt_event"] == "supplier_portal_proof_intake_requested"
    assert result.state_snapshot["supplier_portal_provider"] == "COUPA"
    assert result.state_snapshot["supplier_portal_proof_status"] == "PROOF_REQUESTED"
    assert result.state_snapshot["coupa_proof_status"] == "PROOF_REQUESTED"
    assert "Nothing will be submitted" in result.body
    assert state_machine.AUTHORITY_BOUNDARY["coupa_submission_performed"] is False
    assert state_machine.AUTHORITY_BOUNDARY["coupa_browser_automation_performed"] is False


def test_coupa_proof_action_remains_compatibility_alias(tmp_path):
    result = _process(tmp_path, "request_coupa_submission_proof")

    assert result.action_receipt["receipt_name"] == "coupa_proof_intake_requested_receipt"
    assert result.action_receipt["receipt_event"] == "coupa_proof_intake_requested"
    assert result.state_snapshot["supplier_portal_proof_status"] == "PROOF_REQUESTED"


def test_recipient_review_starts_without_inventing_emails(tmp_path):
    result = _process(tmp_path, "review_and_confirm_recipients")

    assert result.action_receipt["receipt_name"] == "recipient_review_started_receipt"
    assert result.action_receipt["receipt_event"] == "recipient_review_started"
    assert result.state_snapshot["recipient_confirmation_status"] == "REVIEW_REQUESTED_EMAILS_MISSING"
    assert result.state_snapshot["recipient_review_status"] == "NEEDS_CONTACT_CONFIRMATION"
    assert "Annette, Chyna, and Will" in result.body
    assert "@" not in result.body
    assert result.action_receipt["completion_receipt_written"] is False


def test_approval_and_send_and_payment_watch_stay_blocked_with_missing_prerequisites(tmp_path):
    approval = _process(tmp_path, "show_approval_prerequisites")
    send = _process(tmp_path, "prepare_send_approval_request")
    payment = _process(tmp_path, "setup_payment_watch_after_submission")

    assert "Coupa proof missing" in approval.body
    assert send.status == "BLOCKED_PREREQUISITES"
    assert "No send approval, email send, or Coupa submission happened" in send.body
    assert payment.status == "BLOCKED_PREREQUISITES"
    assert "No ledger or payment state changed" in payment.body


def test_sqlite_state_and_receipt_tables_are_queryable(tmp_path):
    db_path, export_root, bridge_root = _paths(tmp_path)
    result = state_machine.process_action(
        _request("request_supplier_portal_submission_proof"),
        db_path=db_path,
        export_root=export_root,
        bridge_export_root=bridge_root,
        generated_at=FIXED_NOW,
    )
    with sqlite3.connect(db_path) as conn:
        receipt_count = conn.execute("SELECT count(*) FROM invoice_review_receipts").fetchone()[0]
        state_row = conn.execute("SELECT coupa_proof_status FROM invoice_review_states").fetchone()

    assert receipt_count == 1
    assert state_row[0] == "PROOF_REQUESTED"
    receipt = state_machine.read_receipt(db_path, result.action_receipt["receipt_id"])
    assert receipt is not None
    assert receipt["receipt_event"] == "supplier_portal_proof_intake_requested"


def test_disabled_or_not_wired_action_returns_clean_blocked_response(tmp_path):
    result = _process(tmp_path, "edit_clara_draft_request")

    assert result.status == "BLOCKED_NOT_WIRED"
    assert result.action_receipt["completion_receipt_written"] is False
    assert "not wired yet" in result.body


def test_invoice_record_selection_result_writes_receipt_and_refreshes_bundle(tmp_path):
    db_path, export_root, bridge_root = _paths(tmp_path)
    result = _process_selection_result(tmp_path)
    source_bundle = json.loads((export_root / invoice_review_bundle.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    bridge_bundle = json.loads((bridge_root / invoice_review_bundle.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    receipt = state_machine.read_receipt(db_path, result.action_receipt["receipt_id"])

    assert result.status == "REQUESTED"
    assert result.action_receipt["receipt_name"] == "invoice_record_selection_operator_confirmed_receipt"
    assert result.action_receipt["receipt_event"] == "invoice_record_selection_operator_confirmed"
    assert result.action_receipt["completion_receipt_written"] is False
    assert receipt["receipt_event"] == "invoice_record_selection_operator_confirmed"
    assert result.state_snapshot["invoice_record_selection_status"] == "OPERATOR_CONFIRMED"
    assert result.state_snapshot["invoice_period_status"] == "OPERATOR_CONFIRMED"
    assert result.state_snapshot["invoice_period_label"] == "May 2026"
    assert result.state_snapshot["invoice_record_label"] == "Capital Hilton May invoice page"
    capital = source_bundle["capital_hilton_bundle"]
    assert capital["invoice_selection"]["invoice_record_state"] == "INVOICE_RECORD_OPERATOR_CONFIRMED"
    assert capital["invoice_selection"]["invoice_period_state"] == "INVOICE_PERIOD_OPERATOR_CONFIRMED"
    assert capital["excel_invoice_artifact"]["linkage_status"] == "NEEDS_REGENERATION_OR_LINK"
    assert capital["excel_invoice_artifact"]["attachment_ready"] is False
    assert capital["approval_footer"]["approval_ready"] is False
    assert bridge_bundle["capital_hilton_bundle"]["invoice_selection"]["operator_confirmed_selection"] is True


def test_invoice_record_selection_result_rejects_missing_required_fields(tmp_path):
    missing_period = _process_selection_result(tmp_path, invoice_period_label="")
    missing_record = _process_selection_result(tmp_path, invoice_page_label="", invoice_record_label="", sheet_label="")

    assert missing_period.status == "BLOCKED_INVALID_SELECTION_RESULT"
    assert "INVOICE_PERIOD_LABEL_REQUIRED" in missing_period.action_receipt["validation_errors"]
    assert missing_record.status == "BLOCKED_INVALID_SELECTION_RESULT"
    assert "INVOICE_RECORD_OR_PAGE_LABEL_REQUIRED" in missing_record.action_receipt["validation_errors"]


def test_invoice_record_selection_result_rejects_unsafe_flags_and_scope(tmp_path):
    unsafe = _process_selection_result(tmp_path, no_cell_read=False)
    wrong_scope = _process_selection_result(tmp_path, client_ref="st_annes")

    assert unsafe.status == "BLOCKED_INVALID_SELECTION_RESULT"
    assert "NO_CELL_READ_REQUIRED" in unsafe.action_receipt["validation_errors"]
    assert wrong_scope.status == "BLOCKED_INVALID_SELECTION_RESULT"
    assert "WRONG_CLIENT" in wrong_scope.action_receipt["validation_errors"]
    assert state_machine.AUTHORITY_BOUNDARY["workbook_body_read_performed"] is False
    assert state_machine.AUTHORITY_BOUNDARY["spreadsheet_cell_read_performed"] is False
