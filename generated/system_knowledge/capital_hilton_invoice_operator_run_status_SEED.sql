INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_status (receipt_sha256, generated_at, client_ref, workflow_ref, source_receipt_status, coupa_status_observed, workbook_invoice_number, coupa_invoice_number, invoice_number_portal_normalized, full_automation_report_path, full_automation_report_sha256, run_report_path, pdf_path, pdf_sha256, email_status, ledger_mutation_performed, paid, authority_flags_all_false, payload_json) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', '2026-06-14T04:38:20+00:00', 'capital_hilton', 'capital_hilton_invoice_operator_run', 'CAPITAL_HILTON_INVOICE_SUBMITTED_AND_EMAIL_SENT', 'Processing', '2026-1006', '2026 1006', 1, '/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_full_automation_report_20260601T222036Z.md', '36ac70d82bd158016a4f005c1b999917c91f0bb43987dd07ececb4fb96c39b52', '/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_report_20260601T221600Z.md', '/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/2026-06-01/Invoice_Capital_Hilton_2026-06-01.pdf', '9e3ee65b771cb9efeec640880bf9234bbdd738419a2a420b7fcfb8bc7cda65f4', 'sent_operator_assisted', 0, 0, 1, '{
  "artifact_refs": {
    "full_automation_report": {
      "kind": "operator_run_full_automation_report",
      "path": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_full_automation_report_20260601T222036Z.md",
      "present": true,
      "sha256": "36ac70d82bd158016a4f005c1b999917c91f0bb43987dd07ececb4fb96c39b52"
    },
    "pdf": {
      "kind": "operator_run_invoice_pdf",
      "page_count": 1,
      "path": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/2026-06-01/Invoice_Capital_Hilton_2026-06-01.pdf",
      "present": true,
      "sha256": "9e3ee65b771cb9efeec640880bf9234bbdd738419a2a420b7fcfb8bc7cda65f4"
    },
    "receipt": {
      "kind": "operator_run_receipt",
      "path": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_receipt_20260601T221600Z.json",
      "sha256": "a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040"
    },
    "run_report": {
      "kind": "operator_run_report",
      "path": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_report_20260601T221600Z.md",
      "sha256": "2be9054870be304773a03b7e75c42bdc09311a35abde436c979d6e01e7aa570f"
    }
  },
  "authority_boundary": {
    "browser_access_allowed": false,
    "coupa_allowed": false,
    "coupa_submit_allowed": false,
    "email_send_allowed": false,
    "gmail_allowed": false,
    "invoice_creation_allowed": false,
    "ledger_posting_allowed": false,
    "paid_marking_allowed": false,
    "portal_submit_allowed": false
  },
  "automation_notes": [
    "Use Coupa Create Invoice from PO, not uploaded-invoice route.",
    "Select Hilton | Smart Spend if Coupa first shows an empty or advanced-only orders view.",
    "Use PO DCASH00983536 for this Capital Hilton invoice.",
    "Address picker may clear the invoice number; re-verify fields after Remit-To save.",
    "Remit-To is a gated business decision. This run selected the mailing/check address, not Bank of America.",
    "Hilton Coupa does not allow special characters in Invoice #; submitted Coupa invoice used 2026 1006.",
    "Workbook/PDF invoice number remains 2026-1006.",
    "Final Coupa action after warnings is labeled Send Invoice.",
    "Successful submit returned status Processing, not Approved.",
    "Gmail draft with attachment was recreated to add CC because attachment drafts were not editable via connector.",
    "The sent email was the newer reviewed draft with CC and attachment; older draft without CC may remain unsent.",
    "Do not mark paid and do not mutate ledger from this receipt."
  ],
  "automation_report_summary": {
    "artifact_validation_checks_recorded": true,
    "automation_backlog_recorded": true,
    "browser_virtual_clipboard_issue_recorded": true,
    "coupa_field_reset_after_remit_to_recorded": true,
    "coupa_po_route_recorded": true,
    "excel_direct_export_success_without_pdf_recorded": true,
    "excel_helper_open_workbook_fragility_recorded": true,
    "full_automation_report_recorded": true,
    "gmail_replacement_draft_recorded": true,
    "invoice_number_normalization_reason": "Hilton Coupa disallows special characters",
    "invoice_number_portal_normalized": true,
    "openpyxl_missing_recorded": true,
    "print_to_pdf_ui_worked": true,
    "remit_to_business_gate_recorded": true,
    "workbook_baseline_and_cell_mutation_recorded": true
  },
  "autonomous_openclaw_coupa_submit": false,
  "autonomous_openclaw_email_send": false,
  "bank_remit_to_selected": false,
  "cell_after": "Friday, May 29, 2026 (completed)",
  "cell_before": "Friday, May 29, 2026 (scheduled)",
  "client_display_name": "Capital Hilton",
  "client_ref": "capital_hilton",
  "content_hash": "sha256:3f42596cf5c835afd09550eac862c31aa8fa749e28e204430bc4d967f84b410a",
  "corrected_cell": "May 2026!C25",
  "coupa_confirmation_ref": "WINSHIP LIVE (GLOBL-0000897564) invoice #2026 1006 is processing",
  "coupa_customer": "Hilton | Smart Spend",
  "coupa_internal_invoice_id": "1697749",
  "coupa_invoice_number": "2026 1006",
  "coupa_po_number": "DCASH00983536",
  "coupa_status_observed": "Processing",
  "coupa_submission_recorded": true,
  "coupa_submission_status": "processing",
  "coupa_submitted": true,
  "email_cc": [
    "winshiplive@gmail.com"
  ],
  "email_status": "sent_operator_assisted",
  "email_subject": "Capital Hilton Invoice",
  "email_to": [
    "Annette.Sunga@hilton.com"
  ],
  "email_to_annette_recorded": true,
  "email_to_annette_sent": true,
  "full_automation_report_recorded": true,
  "future_gig_cell": "May 2026!C26",
  "future_gig_preserved": true,
  "future_gig_value": "Friday, June 5, 2026 (scheduled)",
  "generated_at": "2026-06-14T04:38:20+00:00",
  "invoice_number_normalization_reason": "Hilton Coupa disallows special characters",
  "invoice_number_note": "Coupa rejected special characters; workbook/PDF retains 2026-1006 while submitted Coupa invoice uses 2026 1006.",
  "invoice_number_portal_normalized": true,
  "invoice_total": "$2,000.00",
  "ledger_mutation_performed": false,
  "ledger_posting_allowed": false,
  "machine_proof": {
    "authority_flags_all_false": true,
    "automation_report_compact_summary_recorded": true,
    "autonomous_openclaw_coupa_submit_false": true,
    "autonomous_openclaw_email_send_false": true,
    "coupa_submission_recorded": true,
    "email_to_annette_recorded": true,
    "full_automation_report_found": true,
    "invoice_number_portal_normalized": true,
    "ledger_mutation_performed_false": true,
    "may_29_corrected": true,
    "paid_false": true,
    "pdf_exists": true,
    "pdf_exported": true,
    "pdf_sha256_matches_receipt": true,
    "raw_message_body_excluded": true,
    "receipt_parsed": true,
    "run_report_found": true
  },
  "may_29_corrected": true,
  "next_safe_action": "Operator may review recorded submission/email evidence; OpenClaw is not authorized to submit, send, post ledger, or mark paid from this read model.",
  "operator_assisted": true,
  "paid": false,
  "paid_marking_performed": false,
  "payment_received_recorded": false,
  "pdf_exported": true,
  "pdf_page_count": 1,
  "pdf_sha256": "9e3ee65b771cb9efeec640880bf9234bbdd738419a2a420b7fcfb8bc7cda65f4",
  "proof_refs": {
    "collapsed_by_default": true,
    "full_automation_report_ref": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_full_automation_report_20260601T222036Z.md",
    "pdf_ref": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/2026-06-01/Invoice_Capital_Hilton_2026-06-01.pdf",
    "receipt_ref": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_receipt_20260601T221600Z.json",
    "run_report_ref": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_report_20260601T221600Z.md"
  },
  "read_model_id": "capital_hilton_invoice_operator_run_status",
  "remit_to_choice": "mailing_check_address",
  "remit_to_selected": "WINSHIP LIVE / 21401 / 1009 Smithville St / Annapolis, MD 21401 / United States",
  "schema_version": "capital_hilton_invoice_operator_run_status_v1",
  "sent_gmail_message_id": "19e853f053e7fae1",
  "sent_gmail_thread_id": "19e853cfea99a645",
  "source_path_normalization": {
    "bridge_pdf_path": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/2026-06-01/Invoice_Capital_Hilton_2026-06-01.pdf",
    "full_automation_report_path": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_full_automation_report_20260601T222036Z.md",
    "pc_bridge_pdf_path": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/2026-06-01/Invoice_Capital_Hilton_2026-06-01.pdf",
    "pc_full_automation_report_path": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_full_automation_report_20260601T222036Z.md",
    "run_report_path": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_report_20260601T221600Z.md"
  },
  "source_receipt_status": "CAPITAL_HILTON_INVOICE_SUBMITTED_AND_EMAIL_SENT",
  "status": "CAPITAL_HILTON_OPERATOR_RUN_RECORDED",
  "validation": {
    "full_automation_report_path": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_full_automation_report_20260601T222036Z.md",
    "full_automation_report_present": true,
    "full_automation_report_sha256": "36ac70d82bd158016a4f005c1b999917c91f0bb43987dd07ececb4fb96c39b52",
    "pdf_page_count": 1,
    "pdf_path": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/2026-06-01/Invoice_Capital_Hilton_2026-06-01.pdf",
    "pdf_present": true,
    "pdf_sha256": "9e3ee65b771cb9efeec640880bf9234bbdd738419a2a420b7fcfb8bc7cda65f4",
    "receipt_path": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_receipt_20260601T221600Z.json",
    "receipt_sha256": "a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040",
    "run_report_path": "/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_report_20260601T221600Z.md",
    "run_report_sha256": "2be9054870be304773a03b7e75c42bdc09311a35abde436c979d6e01e7aa570f",
    "source_files_validated": true,
    "source_pdf_sha256": "9e3ee65b771cb9efeec640880bf9234bbdd738419a2a420b7fcfb8bc7cda65f4",
    "source_status": "CAPITAL_HILTON_INVOICE_SUBMITTED_AND_EMAIL_SENT"
  },
  "workbook_invoice_number": "2026-1006",
  "workflow_ref": "capital_hilton_invoice_operator_run",
  "world": "invoice_operations"
}
');
INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (receipt_sha256, learning_key, learning_value) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', 'full_automation_report_recorded', 'True');
INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (receipt_sha256, learning_key, learning_value) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', 'workbook_baseline_and_cell_mutation_recorded', 'True');
INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (receipt_sha256, learning_key, learning_value) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', 'excel_direct_export_success_without_pdf_recorded', 'True');
INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (receipt_sha256, learning_key, learning_value) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', 'excel_helper_open_workbook_fragility_recorded', 'True');
INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (receipt_sha256, learning_key, learning_value) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', 'print_to_pdf_ui_worked', 'True');
INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (receipt_sha256, learning_key, learning_value) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', 'artifact_validation_checks_recorded', 'True');
INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (receipt_sha256, learning_key, learning_value) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', 'openpyxl_missing_recorded', 'True');
INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (receipt_sha256, learning_key, learning_value) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', 'coupa_po_route_recorded', 'True');
INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (receipt_sha256, learning_key, learning_value) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', 'remit_to_business_gate_recorded', 'True');
INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (receipt_sha256, learning_key, learning_value) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', 'coupa_field_reset_after_remit_to_recorded', 'True');
INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (receipt_sha256, learning_key, learning_value) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', 'browser_virtual_clipboard_issue_recorded', 'True');
INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (receipt_sha256, learning_key, learning_value) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', 'invoice_number_portal_normalized', 'True');
INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (receipt_sha256, learning_key, learning_value) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', 'invoice_number_normalization_reason', 'Hilton Coupa disallows special characters');
INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (receipt_sha256, learning_key, learning_value) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', 'gmail_replacement_draft_recorded', 'True');
INSERT OR REPLACE INTO capital_hilton_invoice_operator_run_learning (receipt_sha256, learning_key, learning_value) VALUES ('a6edefabc2fdc3f7ea5ae9c8c5e5a49c7bccdb29d31468dbaa667b3a04520040', 'automation_backlog_recorded', 'True');
