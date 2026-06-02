CREATE TABLE IF NOT EXISTS capital_hilton_invoice_operator_run_status (
  receipt_sha256 TEXT PRIMARY KEY,
  generated_at TEXT NOT NULL,
  client_ref TEXT NOT NULL,
  workflow_ref TEXT NOT NULL,
  source_receipt_status TEXT NOT NULL,
  coupa_status_observed TEXT NOT NULL,
  workbook_invoice_number TEXT NOT NULL,
  coupa_invoice_number TEXT NOT NULL,
  invoice_number_portal_normalized INTEGER NOT NULL CHECK(invoice_number_portal_normalized IN (0, 1)),
  full_automation_report_path TEXT NOT NULL,
  full_automation_report_sha256 TEXT NOT NULL,
  run_report_path TEXT NOT NULL,
  pdf_path TEXT NOT NULL,
  pdf_sha256 TEXT NOT NULL,
  email_status TEXT NOT NULL,
  ledger_mutation_performed INTEGER NOT NULL CHECK(ledger_mutation_performed IN (0, 1)),
  paid INTEGER NOT NULL CHECK(paid IN (0, 1)),
  authority_flags_all_false INTEGER NOT NULL CHECK(authority_flags_all_false IN (0, 1)),
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS capital_hilton_invoice_operator_run_learning (
  receipt_sha256 TEXT NOT NULL,
  learning_key TEXT NOT NULL,
  learning_value TEXT NOT NULL,
  PRIMARY KEY (receipt_sha256, learning_key),
  FOREIGN KEY (receipt_sha256)
    REFERENCES capital_hilton_invoice_operator_run_status(receipt_sha256)
    ON DELETE CASCADE
);
