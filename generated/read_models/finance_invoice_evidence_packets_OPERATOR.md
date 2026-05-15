# Finance Invoice Evidence Packets v0

## Counts
- Packets: 1
- Open packets: 1
- Blocked missing info: 0
- Ready for draft review: 0
- Missing items: 5
- High risk: 3

## Latest Packet
- Packet: `finpkt_505f7d07fc0dbd6d0d1f`
- Title: Finance Invoice Evidence Packet v0 Demo
- Subject: Manual Review
- Status: `needs_operator_facts`
- Next safe move: Provide one real receivable/invoice target with safe operator facts; do not use private raw files yet.

## Missing Items
- `finpkt_505f7d07fc0dbd6d0d1f` blocks_invoice_draft: Amount, balance, deposit, or rate is missing. -> Provide the amount as an operator claim or approved evidence reference.
- `finpkt_505f7d07fc0dbd6d0d1f` blocks_invoice_draft: Exact client/project/entity is not confirmed. -> Provide the client/project label or approve a safe metadata source that contains it.
- `finpkt_505f7d07fc0dbd6d0d1f` blocks_invoice_draft: Service date, invoice date, due date, or period is missing. -> Provide a date/period or approved evidence reference.
- `finpkt_505f7d07fc0dbd6d0d1f` optional: Approved evidence reference is missing. -> Link an approved note, receipt reference, or sanitized metadata packet.
- `finpkt_505f7d07fc0dbd6d0d1f` optional: Mac invoice spreadsheet filename is not known. -> Mac Finance Spreadsheet Evidence Intake v0

## Risks
- `finpkt_505f7d07fc0dbd6d0d1f` missing_amount (high): Provide the amount as an operator claim or approved evidence reference.
- `finpkt_505f7d07fc0dbd6d0d1f` send_not_allowed (high): Keep all invoice/email outputs as draft context only until a later explicit approval path exists.
- `finpkt_505f7d07fc0dbd6d0d1f` unclear_client (high): Provide the client/project label or approve a safe metadata source that contains it.
- `finpkt_505f7d07fc0dbd6d0d1f` missing_date (medium): Provide a date/period or approved evidence reference.
- `finpkt_505f7d07fc0dbd6d0d1f` spreadsheet_needs_review (medium): Treat ~/Documents/invoices/ as sensitive metadata only; use a future Mac-side intake lane for filename metadata.

## Mac Spreadsheet Candidate
- Candidate known: `true`
- Folder known: `true`
- Folder: `~/Documents/invoices/`
- Exact path known: `false`
- Metadata available: `false`
- Ingestion allowed: `false`
- Cell read allowed: `false`
- Next safe move: Mac Finance Spreadsheet Evidence Intake v0

## Work Board Linkage
- `wbcard_95706de4a863fcb25686` needs_review: Finance Invoice Evidence Packet Builder
- `wbcard_56753122b32749dcb9f4` needs_review: Mac spreadsheet evidence intake needed
- `wbcard_ab0fb6f1aecdbb537d49` needs_review: Review missing finance evidence

## Authority Boundary
- `invoice_send_allowed`: `false`.
- `email_send_allowed`: `false`.
- `bank_access_allowed`: `false`.
- `ledger_write_allowed`: `false`.
- `tax_filing_allowed`: `false`.
- `external_api_allowed`: `false`.
- `raw_sensitive_body_ingest_allowed`: `false`.
- `spreadsheet_cell_read_allowed`: `false`.
- `workbook_parsing_allowed`: `false`.
- `financial_truth_claimed`: `false`.
- `operator_approval_required`: `true`.
