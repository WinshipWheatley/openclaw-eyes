INSERT OR REPLACE INTO st_annes_invoice_status_receipt (receipt_sha256, generated_at, client_ref, invoice_period, invoice_status, source_receipt_path, source_pdf_path, source_pdf_sha256, source_pdf_page_count, openclaw_send_performed, email_send_allowed, ledger_posting_allowed, paid, payload_json) VALUES ('ed090053514715831f6f7ee882bdd7b3f99ba086c66b19daaf4004f3d756ef90', '2026-07-17T15:02:00+00:00', 'st_annes', '2026-06', 'SENT', '/mnt/e/openclaw/artifacts/invoice_workbooks/st-annes/2026-06/st_annes_external_agent_corrected_send_receipt_20260717T134714Z.json', '/Users/hwinshipwheatley/Documents/Invoices/openclaw_invoice_workspace/clients/st-annes/invoices/2026/2026-06_st-annes/invoice_final_20260717.pdf', '1f2ebb6b77e7ddfe095b8a449d5c3eaf12ea61f74730b0a901fe800b3c81140e', 1, 0, 0, 0, 0, '{
  "amount": 875,
  "artifact_kind": "operator_provided_pdf_invoice",
  "authoritative_source": {
    "attachment_metadata_confirmed": true,
    "gmail_sent_readback_confirmed": true,
    "path": "/mnt/e/openclaw/codex_mac_bridge/from-codex-mac-desktop/ST-ANNES-INVOICE-FINAL-CORRECTION-SENT-20260717.md",
    "sha256": "ccb626fe40bcb46ebc1714907ae9ed3718cbd32a72cfa8e908ff1e57b891a88a"
  },
  "authority_boundary": {
    "browser_access_allowed": false,
    "coupa_allowed": false,
    "email_send_allowed": false,
    "finance_invoice_allowed": false,
    "gmail_allowed": false,
    "ledger_posting_allowed": false,
    "openclaw_send_allowed": false,
    "paid": false,
    "portal_submit_allowed": false,
    "workbook_mutation_allowed": false
  },
  "bcc": [],
  "browser_or_coupa_submit_performed": false,
  "cc": [
    "winshiplive@gmail.com"
  ],
  "client_display_name": "St. Anne''s",
  "client_ref": "st_annes",
  "content_hash": "sha256:1f7eb40559a5df73dff7d403e0457e5e7d7acf209e5ff9e7b94a71e8b9f09426",
  "downstream": {
    "check_received": {
      "state": "pending",
      "status": "UNKNOWN"
    },
    "draper_forwarded_to_glenn": {
      "state": "pending",
      "status": "UNKNOWN"
    },
    "glenn_acknowledged": {
      "state": "pending",
      "status": "UNKNOWN"
    },
    "invoice_paid": {
      "state": "pending",
      "status": "UNKNOWN"
    }
  },
  "email_send_allowed": false,
  "email_send_performed_by_openclaw": false,
  "generated_at": "2026-07-17T15:02:00+00:00",
  "gmail_message_id": "19f7054d2e151aa4",
  "gmail_thread_id": "19f7053211a51f52",
  "invoice_amount_summary": {
    "may_service_subtotal_observed": false,
    "prior_balance_observed": false,
    "total_outstanding_observed": false
  },
  "invoice_number": "3",
  "invoice_period": "2026-06",
  "invoice_ref": "ST-ANNES-2026-06-INVOICE-3",
  "invoice_status": "SENT",
  "ledger_mutation_performed": false,
  "ledger_posting_allowed": false,
  "line_item_checks": {
    "draft_absent_from_sent_pdf": true,
    "each_service_125": true,
    "invoice_number_3_unchanged": true,
    "sent_date_2026_07_17_displayed": true,
    "seven_services_present": true,
    "total_due_875": true
  },
  "line_items_verified": true,
  "loop_closure": {
    "expected_evidence": "reply_or_note_from_glenn",
    "gmail_thread_id": "19f7053211a51f52",
    "milestone_ref": "glenn_acknowledged",
    "watch_scope": "gmail_thread_plus_any_glenn_reply"
  },
  "machine_proof": {
    "artifact_metadata_receipt_verified": true,
    "attachment_sha256_receipt_consistent": true,
    "business_authority_flags_false": true,
    "email_send_allowed_false": true,
    "external_agent_send_provenance": true,
    "ledger_mutation_performed": false,
    "ledger_posting_allowed_false": true,
    "local_pdf_inspected": false,
    "manual_send_out_of_band_recorded": true,
    "openclaw_send_performed": false,
    "operator_authorized_fact": true,
    "paid_false": true,
    "pdf_exists": false,
    "pdf_page_count_is_one": true,
    "pdf_sha256_matches_receipt": false,
    "reconciliation_record_only": true,
    "source_pdf_sha256_matches_receipt": true
  },
  "manual_send_out_of_band_known": true,
  "month": "2026-06",
  "next_safe_move": "Await observed Glenn reply or note evidence. Keep forward, acknowledgment, check, and paid milestones pending; do not send or mark paid.",
  "openclaw_send_performed": false,
  "operator_authorized": true,
  "paid": false,
  "payment_status": "NOT_MARKED_PAID",
  "pdf_export_performed_by_openclaw": false,
  "read_model_id": "st_annes_invoice_status",
  "recipient": "draper.carter@gmail.com",
  "safety_flags": {
    "browser_access_allowed": false,
    "coupa_allowed": false,
    "email_send_allowed": false,
    "finance_invoice_allowed": false,
    "gmail_allowed": false,
    "ledger_posting_allowed": false,
    "openclaw_send_allowed": false,
    "paid": false,
    "portal_submit_allowed": false,
    "workbook_mutation_allowed": false
  },
  "schema_version": "st_annes_invoice_status_v1",
  "send_disposition": "OPERATIVE",
  "send_history": [
    {
      "attachment_filename": "invoice_format_fixed_20260716.pdf",
      "attachment_sha256": "a32fa83cde025d237531a3360108f6f9c4e3afa87e8f857fe05912c3d994ee1b",
      "disposition": "SUPERSEDED",
      "gmail_message_id": "19f6e50b5dc44aa6",
      "reason": "The finalized corrected invoice supersedes the earlier draft-labeled attachment; the earlier send remains historical evidence.",
      "sent_at_utc_iso": "2026-07-17T04:23:30+00:00",
      "subject": "St. Anne''s Invoice — June 2026 Services"
    },
    {
      "attachment_filename": "invoice_final_20260717.pdf",
      "attachment_sha256": "1f2ebb6b77e7ddfe095b8a449d5c3eaf12ea61f74730b0a901fe800b3c81140e",
      "disposition": "OPERATIVE",
      "gmail_message_id": "19f7054d2e151aa4",
      "gmail_thread_id": "19f7053211a51f52",
      "sent_at_utc_iso": "2026-07-17T13:47:14+00:00",
      "subject": "Corrected: St. Anne''s Invoice — June 2026 Services"
    }
  ],
  "send_provenance": "external_agent_send",
  "sent_at_utc_iso": "2026-07-17T13:47:14+00:00",
  "sent_by_openclaw": false,
  "service_count": 7,
  "source_pdf_file_size_bytes": 107683,
  "source_pdf_local_available": false,
  "source_pdf_page_count": 1,
  "source_pdf_path": "/Users/hwinshipwheatley/Documents/Invoices/openclaw_invoice_workspace/clients/st-annes/invoices/2026/2026-06_st-annes/invoice_final_20260717.pdf",
  "source_pdf_sha256": "1f2ebb6b77e7ddfe095b8a449d5c3eaf12ea61f74730b0a901fe800b3c81140e",
  "source_receipt_generated_at": "2026-07-17T14:56:17+00:00",
  "source_receipt_path": "/mnt/e/openclaw/artifacts/invoice_workbooks/st-annes/2026-06/st_annes_external_agent_corrected_send_receipt_20260717T134714Z.json",
  "source_receipt_sha256": "ed090053514715831f6f7ee882bdd7b3f99ba086c66b19daaf4004f3d756ef90",
  "source_receipt_status": "SENT",
  "source_workbook_mutated_by_openclaw": false,
  "status_as_of_utc_iso": "2026-07-17T13:47:14+00:00",
  "subject": "Corrected: St. Anne''s Invoice — June 2026 Services",
  "supersedes": {
    "attachment_filename": "invoice_format_fixed_20260716.pdf",
    "attachment_sha256": "a32fa83cde025d237531a3360108f6f9c4e3afa87e8f857fe05912c3d994ee1b",
    "disposition": "SUPERSEDED",
    "gmail_message_id": "19f6e50b5dc44aa6",
    "reason": "The finalized corrected invoice supersedes the earlier draft-labeled attachment; the earlier send remains historical evidence.",
    "sent_at_utc_iso": "2026-07-17T04:23:30+00:00",
    "subject": "St. Anne''s Invoice — June 2026 Services"
  },
  "to": [
    "draper.carter@gmail.com"
  ],
  "validation": {
    "artifact_validation_mode": "authoritative_sent_readback",
    "attachment_sha256_receipt_consistent": true,
    "corrected_send": true,
    "expected_page_count": 1,
    "external_agent_send": true,
    "field_checks_ok": true,
    "local_artifact_available": false,
    "observed_page_count": 1,
    "page_count_ok": true,
    "pdf_exists": false,
    "pdf_path": "/Users/hwinshipwheatley/Documents/Invoices/openclaw_invoice_workspace/clients/st-annes/invoices/2026/2026-06_st-annes/invoice_final_20260717.pdf",
    "pdf_sha256_matches_receipt": false,
    "receipt_path": "/mnt/e/openclaw/artifacts/invoice_workbooks/st-annes/2026-06/st_annes_external_agent_corrected_send_receipt_20260717T134714Z.json",
    "receipt_source_sha256_matches_pdf": true,
    "receipt_status_ok": true
  },
  "workbook_finalization": {
    "backup_path": "/Users/hwinshipwheatley/Documents/Invoices/openclaw_invoice_workspace/clients/st-annes/invoices/2026/2026-06_st-annes/invoice.backup-before-final-20260717T091039-0400.xlsx",
    "backup_sha256": "626f89587d7fa8976dc7f99d55fd2f622c7433b7eac3c175dcb4fecab2165ea1",
    "changed_cells": [
      "June 2026!G2",
      "June 2026!G4"
    ],
    "final_sha256": "a986c19c50542efb9890085c656590cccff1f0233513420c5eb64178c27e411e",
    "path": "/Users/hwinshipwheatley/Documents/Invoices/openclaw_invoice_workspace/clients/st-annes/invoices/2026/2026-06_st-annes/invoice.xlsx",
    "semantic_diff_passed": true
  },
  "workflow_ref": "st_annes_invoice_workflow"
}
');
INSERT OR REPLACE INTO st_annes_invoice_send_history (gmail_message_id, gmail_thread_id, sent_at_utc_iso, subject, attachment_filename, attachment_sha256, disposition, operative_receipt_sha256, payload_json) VALUES ('19f6e50b5dc44aa6', '', '2026-07-17T04:23:30+00:00', 'St. Anne''s Invoice — June 2026 Services', 'invoice_format_fixed_20260716.pdf', 'a32fa83cde025d237531a3360108f6f9c4e3afa87e8f857fe05912c3d994ee1b', 'SUPERSEDED', 'ed090053514715831f6f7ee882bdd7b3f99ba086c66b19daaf4004f3d756ef90', '{
  "attachment_filename": "invoice_format_fixed_20260716.pdf",
  "attachment_sha256": "a32fa83cde025d237531a3360108f6f9c4e3afa87e8f857fe05912c3d994ee1b",
  "disposition": "SUPERSEDED",
  "gmail_message_id": "19f6e50b5dc44aa6",
  "reason": "The finalized corrected invoice supersedes the earlier draft-labeled attachment; the earlier send remains historical evidence.",
  "sent_at_utc_iso": "2026-07-17T04:23:30+00:00",
  "subject": "St. Anne''s Invoice — June 2026 Services"
}
');
INSERT OR REPLACE INTO st_annes_invoice_send_history (gmail_message_id, gmail_thread_id, sent_at_utc_iso, subject, attachment_filename, attachment_sha256, disposition, operative_receipt_sha256, payload_json) VALUES ('19f7054d2e151aa4', '19f7053211a51f52', '2026-07-17T13:47:14+00:00', 'Corrected: St. Anne''s Invoice — June 2026 Services', 'invoice_final_20260717.pdf', '1f2ebb6b77e7ddfe095b8a449d5c3eaf12ea61f74730b0a901fe800b3c81140e', 'OPERATIVE', 'ed090053514715831f6f7ee882bdd7b3f99ba086c66b19daaf4004f3d756ef90', '{
  "attachment_filename": "invoice_final_20260717.pdf",
  "attachment_sha256": "1f2ebb6b77e7ddfe095b8a449d5c3eaf12ea61f74730b0a901fe800b3c81140e",
  "disposition": "OPERATIVE",
  "gmail_message_id": "19f7054d2e151aa4",
  "gmail_thread_id": "19f7053211a51f52",
  "sent_at_utc_iso": "2026-07-17T13:47:14+00:00",
  "subject": "Corrected: St. Anne''s Invoice — June 2026 Services"
}
');
