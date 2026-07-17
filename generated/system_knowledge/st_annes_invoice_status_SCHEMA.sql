CREATE TABLE IF NOT EXISTS st_annes_invoice_status_receipt (
  receipt_sha256 TEXT PRIMARY KEY,
  generated_at TEXT NOT NULL,
  client_ref TEXT NOT NULL,
  invoice_period TEXT NOT NULL,
  invoice_status TEXT NOT NULL,
  source_receipt_path TEXT NOT NULL,
  source_pdf_path TEXT NOT NULL,
  source_pdf_sha256 TEXT NOT NULL,
  source_pdf_page_count INTEGER NOT NULL,
  openclaw_send_performed INTEGER NOT NULL CHECK(openclaw_send_performed IN (0, 1)),
  email_send_allowed INTEGER NOT NULL CHECK(email_send_allowed IN (0, 1)),
  ledger_posting_allowed INTEGER NOT NULL CHECK(ledger_posting_allowed IN (0, 1)),
  paid INTEGER NOT NULL CHECK(paid IN (0, 1)),
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS st_annes_invoice_send_history (
  gmail_message_id TEXT PRIMARY KEY,
  gmail_thread_id TEXT NOT NULL,
  sent_at_utc_iso TEXT NOT NULL,
  subject TEXT NOT NULL,
  attachment_filename TEXT NOT NULL,
  attachment_sha256 TEXT NOT NULL,
  disposition TEXT NOT NULL CHECK(disposition IN ('RECORDED', 'SUPERSEDED', 'OPERATIVE')),
  operative_receipt_sha256 TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
