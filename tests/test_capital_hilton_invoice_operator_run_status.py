import json
import sqlite3
from pathlib import Path

import pytest

import capital_hilton_invoice_operator_run_status as operator_run


FIXED_NOW = "2026-06-01T22:30:00+00:00"


def _write_fixture(input_dir: Path, *, timestamp: str = "20260601T221600Z", unsafe: str = "") -> dict[str, str]:
    input_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir = input_dir / "2026-06-01"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / "Invoice_Capital_Hilton_2026-06-01.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfixture capital hilton pdf\n")
    pdf_sha = operator_run.sha256_file(pdf_path)
    report_path = input_dir / f"capital_hilton_invoice_operator_run_report_{timestamp}.md"
    full_report_path = input_dir / "capital_hilton_invoice_operator_run_full_automation_report_20260601T222036Z.md"
    receipt_path = input_dir / f"capital_hilton_invoice_operator_run_receipt_{timestamp}.json"
    report_path.write_text("# Capital Hilton Invoice Operator Run\n\nCAPITAL_HILTON_INVOICE_SUBMITTED_AND_EMAIL_SENT\n", encoding="utf-8")
    full_report_path.write_text(
        "\n".join(
            [
                "# Capital Hilton Invoice Operator Run - Full Automation Report",
                "Direct Excel/AppleScript PDF export appeared to return success but did not create a PDF.",
                "The Excel helper had OPEN_WORKBOOK permission and timeout fragility.",
                "The macOS/Excel print-to-PDF UI flow was the path that worked.",
                "Validation checked existence, size, SHA256, page count, invoice text, total, May 29 completed, and June 5 scheduled.",
                "openpyxl was missing in the default python3 environment.",
                "Remit-To is a business decision gate.",
                "After Remit-To save, Coupa cleared the invoice number field.",
                "Browser helpers hit a virtual clipboard error.",
                "Hilton Coupa disallows special characters in Invoice #.",
                "Gmail draft with attachment was recreated to add CC.",
                "## Automation Backlog",
                "- Preserve this learning in SQLite.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    full_report_sha = operator_run.sha256_file(full_report_path)
    receipt_payload = {
        "status": "CAPITAL_HILTON_INVOICE_SUBMITTED_AND_EMAIL_SENT",
        "workflow_ref": "capital_hilton_invoice_operator_run",
        "client_ref": "capital_hilton",
        "generated_at": "2026-06-01T22:16:00Z",
        "full_automation_report_path": str(full_report_path),
        "pc_full_automation_report_path": str(full_report_path),
        "may_29_corrected": True,
        "cell_changed": "May 2026!C25",
        "cell_before": "Friday, May 29, 2026 (scheduled)",
        "cell_after": "Friday, May 29, 2026 (completed)",
        "june_5_future_gig_preserved": True,
        "future_gig_cell": "May 2026!C26",
        "future_gig_value": "Friday, June 5, 2026 (scheduled)",
        "pdf_exported": True,
        "pdf_page_count": 1,
        "pc_bridge_pdf_path": str(pdf_path),
        "pdf_sha256": pdf_sha,
        "invoice_total": "$2,000.00",
        "workbook_invoice_number": "2026-1006",
        "coupa_invoice_number": "2026 1006",
        "invoice_number_note": "Coupa rejected special characters; workbook/PDF retains 2026-1006 while submitted Coupa invoice uses 2026 1006.",
        "coupa_submission_recorded": True,
        "coupa_submitted": True,
        "coupa_status_observed": "Processing",
        "coupa_po_number": "DCASH00983536",
        "coupa_customer": "Hilton | Smart Spend",
        "coupa_internal_invoice_id": "1697749",
        "coupa_confirmation_ref": "WINSHIP LIVE invoice #2026 1006 is processing",
        "remit_to_selected": "WINSHIP LIVE / 21401 / 1009 Smithville St / Annapolis, MD 21401 / United States",
        "remit_to_choice": "mailing_check_address",
        "bank_remit_to_selected": False,
        "email_to_annette_recorded": True,
        "email_to_annette_sent": True,
        "email_send_performed": True,
        "email_to": ["Annette.Sunga@hilton.com"],
        "email_cc": ["winshiplive@gmail.com"],
        "email_subject": "Capital Hilton Invoice",
        "email_body": "raw email body should not be copied into the read model",
        "sent_gmail_message_id": "19e853f053e7fae1",
        "sent_gmail_thread_id": "19e853cfea99a645",
        "operator_assisted": True,
        "autonomous_openclaw_coupa_submit": False,
        "autonomous_openclaw_email_send": False,
        "ledger_mutation_performed": False,
        "ledger_posting_allowed": False,
        "paid": False,
        "paid_marking_performed": False,
        "payment_received_recorded": False,
        "automation_notes": [
            "Use Coupa Create Invoice from PO, not uploaded-invoice route.",
            "Address picker may clear the invoice number; re-verify fields after Remit-To save.",
            "Hilton Coupa does not allow special characters in Invoice #; submitted Coupa invoice used 2026 1006.",
            "Gmail draft with attachment was recreated to add CC because attachment drafts were not editable via connector.",
        ],
    }
    if unsafe == "paid":
        receipt_payload["paid"] = True
    if unsafe == "ledger":
        receipt_payload["ledger_mutation_performed"] = True
    if unsafe == "autonomous_email":
        receipt_payload["autonomous_openclaw_email_send"] = True
    receipt_path.write_text(json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "receipt_path": str(receipt_path),
        "run_report_path": str(report_path),
        "full_automation_report_path": str(full_report_path),
        "full_automation_report_sha": full_report_sha,
        "pdf_path": str(pdf_path),
        "pdf_sha": pdf_sha,
    }


def test_build_read_model_records_operator_run_without_openclaw_authority(tmp_path):
    fixture = _write_fixture(tmp_path)

    payload = operator_run.build_read_model(input_dir=tmp_path, generated_at=FIXED_NOW)

    assert payload["schema_version"] == operator_run.SCHEMA_VERSION
    assert payload["status"] == operator_run.RECORDED_STATUS
    assert payload["client_ref"] == "capital_hilton"
    assert payload["may_29_corrected"] is True
    assert payload["pdf_exported"] is True
    assert payload["pdf_sha256"] == fixture["pdf_sha"]
    assert payload["artifact_refs"]["full_automation_report"]["sha256"] == fixture["full_automation_report_sha"]
    assert payload["artifact_refs"]["full_automation_report"]["kind"] == "operator_run_full_automation_report"
    assert payload["full_automation_report_recorded"] is True
    assert payload["invoice_number_portal_normalized"] is True
    assert payload["invoice_number_normalization_reason"] == "Hilton Coupa disallows special characters"
    assert payload["automation_report_summary"]["excel_direct_export_success_without_pdf_recorded"] is True
    assert payload["automation_report_summary"]["excel_helper_open_workbook_fragility_recorded"] is True
    assert payload["automation_report_summary"]["print_to_pdf_ui_worked"] is True
    assert payload["automation_report_summary"]["openpyxl_missing_recorded"] is True
    assert payload["automation_report_summary"]["browser_virtual_clipboard_issue_recorded"] is True
    assert payload["automation_report_summary"]["gmail_replacement_draft_recorded"] is True
    assert payload["automation_report_summary"]["automation_backlog_recorded"] is True
    assert payload["coupa_submission_recorded"] is True
    assert payload["coupa_submission_status"] == "processing"
    assert payload["email_to_annette_recorded"] is True
    assert payload["email_to_annette_sent"] is True
    assert payload["autonomous_openclaw_coupa_submit"] is False
    assert payload["autonomous_openclaw_email_send"] is False
    assert payload["ledger_mutation_performed"] is False
    assert payload["paid"] is False
    assert all(value is False for value in payload["authority_boundary"].values())
    assert payload["proof_refs"]["collapsed_by_default"] is True
    assert payload["proof_refs"]["full_automation_report_ref"] == fixture["full_automation_report_path"]
    payload_text = json.dumps(payload)
    assert "email_body" not in payload_text
    assert "raw email body should not be copied" not in payload_text


def test_find_latest_source_pair_uses_newest_receipt_timestamp(tmp_path):
    _write_fixture(tmp_path, timestamp="20260601T220647Z")
    newest = _write_fixture(tmp_path, timestamp="20260601T221600Z")

    pair = operator_run.find_latest_source_pair(tmp_path)

    assert str(pair.receipt_path) == newest["receipt_path"]
    assert str(pair.run_report_path) == newest["run_report_path"]
    assert pair.timestamp == "20260601T221600Z"


@pytest.mark.parametrize("unsafe", ["paid", "ledger", "autonomous_email"])
def test_build_read_model_rejects_unsafe_terminal_or_authority_state(tmp_path, unsafe):
    _write_fixture(tmp_path, unsafe=unsafe)

    with pytest.raises(ValueError):
        operator_run.build_read_model(input_dir=tmp_path, generated_at=FIXED_NOW)


def test_export_writes_local_and_bridge_read_models(tmp_path):
    _write_fixture(tmp_path / "input")

    result = operator_run.export_read_model(
        input_dir=tmp_path / "input",
        export_root=tmp_path / "local",
        bridge_export_root=tmp_path / "bridge",
        sqlite_path=tmp_path / "system_knowledge" / "capital_hilton_invoice_operator_run_status.sqlite",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result.read_model_path).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result.bridge_read_model_path).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["status"] == operator_run.RECORDED_STATUS
    assert local["machine_proof"]["ledger_mutation_performed_false"] is True
    assert local["machine_proof"]["paid_false"] is True
    assert Path(result.sqlite_path).exists()

    conn = sqlite3.connect(result.sqlite_path)
    try:
        row = conn.execute(
            "SELECT source_receipt_status, coupa_status_observed, invoice_number_portal_normalized, "
            "ledger_mutation_performed, paid, authority_flags_all_false "
            "FROM capital_hilton_invoice_operator_run_status"
        ).fetchone()
        learning_keys = {
            value
            for (value,) in conn.execute(
                "SELECT learning_key FROM capital_hilton_invoice_operator_run_learning"
            ).fetchall()
        }
    finally:
        conn.close()

    assert row == ("CAPITAL_HILTON_INVOICE_SUBMITTED_AND_EMAIL_SENT", "Processing", 1, 0, 0, 1)
    assert "print_to_pdf_ui_worked" in learning_keys
    assert "browser_virtual_clipboard_issue_recorded" in learning_keys
