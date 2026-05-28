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


def test_regenerate_or_link_artifact_blocks_until_invoice_record_selected(tmp_path):
    result = _process(tmp_path, "regenerate_or_link_invoice_artifact")

    assert result.status == "BLOCKED_NEEDS_INVOICE_RECORD_SELECTION"
    assert result.action_receipt["completion_receipt_written"] is False
    assert result.headline == "Invoice artifact needs linkage"
    assert "invoice page/period" in result.body
    assert state_machine.AUTHORITY_BOUNDARY["invoice_generation_performed"] is False
    assert state_machine.AUTHORITY_BOUNDARY["pdf_export_performed"] is False


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
