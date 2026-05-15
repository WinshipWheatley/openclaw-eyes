# OpenClaw Finance Invoice Evidence Packet v0

Finance Invoice Evidence Packet v0 is the first practical Finance World workflow after Repo B finance reconciliation.

It helps the operator turn scattered invoice or receivable thoughts into a reviewable packet:

```text
operator facts + approved evidence + missing info + risks + Work Board card + next safe move
```

It does not create, send, or finalize invoices. It does not send emails, access banks, write ledgers, parse workbooks, read spreadsheet cells, file taxes, or claim financial truth.

## Purpose

The workflow is designed to reduce operator burden. Instead of the operator manually remembering what invoice facts are needed, where evidence might live, and what is still unsafe, OpenClaw records:

- what facts were supplied
- whether each fact is an operator claim or evidence-backed
- what evidence links exist
- what is missing
- what risks block draft review
- what next safe move will make the packet more useful

## Packet Status

Packets use these statuses:

- `draft`
- `needs_operator_facts`
- `evidence_ready`
- `blocked_missing_info`
- `ready_for_draft_review`
- `completed_packet`

The default demo packet is synthetic and uses `needs_operator_facts`. It is safe for testing the workflow, not for financial action.

## Facts

Facts are stored as bounded metadata:

- `operator_supplied`
- `approved_evidence_reference`
- `calculated_from_approved_evidence`
- `unknown_review`

Truth status is explicit:

- `unverified_claim`
- `operator_confirmed`
- `evidence_backed`
- `needs_review`

OpenClaw does not claim an amount, balance, date, or payment status is true unless it is operator-provided or backed by approved evidence. A fact marked evidence-backed without a source reference is downgraded to `needs_review` and risked as `unsupported_claim`.

## Evidence Links

Evidence links are metadata-only references. Allowed source kinds include:

- `markdown_evidence`
- `approved_file_metadata`
- `receipt_reference`
- `operator_note`
- `report_bridge_metadata`
- `mac_local_spreadsheet_candidate`
- `unknown_review`

Allowed use can be:

- `cite_in_packet`
- `summarize_only`
- `metadata_only`
- `metadata_only_pending_review`
- `blocked`

Raw sensitive bodies are not ingested in this lane.

## Mac Spreadsheet Candidate

The operator reported a likely relevant spreadsheet under:

`~/Documents/invoices/`

This lane records that as a high-value evidence candidate only:

- `spreadsheet_candidate_known=true`
- `spreadsheet_folder_known=true`
- `spreadsheet_folder=~/Documents/invoices/`
- `spreadsheet_path_known=false` unless the operator provides an exact filename
- `spreadsheet_ingestion_allowed=false`
- `spreadsheet_cell_read_allowed=false`
- `workbook_parsing_allowed=false`
- `sensitivity_status=sensitive_metadata_only`
- `ingestion_policy=needs_operator_review`
- `allowed_use=metadata_only_pending_review`

The next safe lane is:

`Mac Finance Spreadsheet Evidence Intake v0`

That future lane should run locally on the Mac, identify workbook metadata first, and still avoid cell extraction until separately approved.

## Work Board Linkage

If enabled, the builder creates metadata-only Work Board cards:

- Finance Invoice Evidence Packet Builder
- Review missing finance evidence
- Prepare invoice draft context / packet review
- Mac spreadsheet evidence intake needed

These cards never create operator actions, approve work, send messages, access banks, write ledgers, or parse spreadsheet cells.

## Commands

Build a demo packet:

```bash
python3 scripts/build_finance_invoice_evidence_packet.py \
  --title "Finance Invoice Evidence Packet v0 Demo" \
  --subject "Manual Review" \
  --workflow-kind invoice_prep \
  --format operator
```

Build with safe operator facts:

```bash
python3 scripts/build_finance_invoice_evidence_packet.py \
  --title "Receivable review" \
  --subject "Client or project label" \
  --workflow-kind receivables_review \
  --fact service_date="May 2026" \
  --amount balance=100 \
  --format operator
```

Query:

```bash
python3 scripts/query_finance_invoice_evidence_packets.py --report summary --format operator
python3 scripts/query_finance_invoice_evidence_packets.py --report packets --format operator
python3 scripts/query_finance_invoice_evidence_packets.py --report missing --format operator
python3 scripts/query_finance_invoice_evidence_packets.py --report risks --format operator
python3 scripts/query_finance_invoice_evidence_packets.py --report spreadsheet --format operator
python3 scripts/query_finance_invoice_evidence_packets.py --packet-id <packet_id> --format operator
```

Export read-model:

```bash
python3 scripts/export_finance_invoice_evidence_packets_read_model.py --format operator
```

Generated read-models:

- `generated/read_models/finance_invoice_evidence_packets.json`
- `generated/read_models/finance_invoice_evidence_packets_OPERATOR.md`

## Future Mac-Side Lane

`Mac Finance Spreadsheet Evidence Intake v0` should:

- run locally on Mac
- inspect `~/Documents/invoices/` metadata first
- identify exact workbook filename, modified time, and file size
- optionally collect sheet names only if approved
- avoid row/cell extraction until a later explicit approval
- produce a sanitized metadata packet for Repo A
- preserve `sensitive_metadata_only` by default

This lane does not implement that Mac-side intake.

## Authority Boundary

- `invoice_send_allowed=false`
- `email_send_allowed=false`
- `bank_access_allowed=false`
- `ledger_write_allowed=false`
- `tax_filing_allowed=false`
- `external_api_allowed=false`
- `raw_sensitive_body_ingest_allowed=false`
- `spreadsheet_cell_read_allowed=false`
- `workbook_parsing_allowed=false`
- `financial_truth_claimed=false`
- `operator_approval_required=true`

## How This Makes the Operator Freer

The useful outcome is not a new finance app to manage. It is a small structure that can hold one real invoice/receivable thread, show what is missing, protect sensitive boundaries, and tell the operator the next safe step.

The recommended next lane is `Mac Finance Spreadsheet Evidence Intake v0`, because the likely spreadsheet lives on the Mac and should be handled there as metadata-first, approval-gated evidence.
