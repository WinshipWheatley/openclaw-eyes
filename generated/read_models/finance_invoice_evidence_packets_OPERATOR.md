# Finance Invoice Evidence Packets v0

## Counts
- Packets: 2
- Open packets: 2
- Blocked missing info: 1
- Ready for draft review: 0
- Missing items: 15
- High risk: 6

## Latest Packet
- Packet: `finance_capital_hilton_invoice_packet_v0`
- Title: Capital Hilton Invoice Evidence Packet v0
- Subject: Capital Hilton / Capitol Hilton
- Status: `blocked_missing_info`
- Next safe move: Answer the Capital Hilton missing-facts checklist; then review draft email and portal prompt without sending/submitting.

## Missing Items
- `finance_capital_hilton_invoice_packet_v0` blocks_invoice_draft: Amount or rate per gig is missing. -> Operator provides rate/amount per gig or approved evidence reference.
- `finpkt_505f7d07fc0dbd6d0d1f` blocks_invoice_draft: Amount, balance, deposit, or rate is missing. -> Provide the amount as an operator claim or approved evidence reference.
- `finance_capital_hilton_invoice_packet_v0` blocks_invoice_draft: Billing/remit details need confirmation. -> Operator confirms billing name, remit email, mailing/payment details, and any tax/remit fields.
- `finpkt_505f7d07fc0dbd6d0d1f` blocks_invoice_draft: Exact client/project/entity is not confirmed. -> Provide the client/project label or approve a safe metadata source that contains it.
- `finance_capital_hilton_invoice_packet_v0` blocks_invoice_draft: Exact date for last Friday's gig is not operator-confirmed for invoice use. -> Operator confirms the invoice date/service date for last Friday's gig.
- `finance_capital_hilton_invoice_packet_v0` blocks_invoice_draft: Exact date for tonight's gig is not operator-confirmed for invoice use. -> Operator confirms the invoice date/service date for tonight's gig.
- `finance_capital_hilton_invoice_packet_v0` blocks_invoice_draft: One invoice versus two invoices is undecided. -> Operator chooses one combined invoice or separate invoices per gig.
- `finance_capital_hilton_invoice_packet_v0` blocks_invoice_draft: PO number(s) are missing. -> Operator provides PO number(s), says none, or approves portal metadata lookup later.
- `finpkt_505f7d07fc0dbd6d0d1f` blocks_invoice_draft: Service date, invoice date, due date, or period is missing. -> Provide a date/period or approved evidence reference.
- `finance_capital_hilton_invoice_packet_v0` blocks_invoice_draft: Supplier portal reference is unresolved. -> Operator confirms whether SmartSpend/Coupa is required and provides portal reference if known.
- `finance_capital_hilton_invoice_packet_v0` blocks_send: Invoice attachment/output path is missing. -> Operator chooses or approves invoice attachment/output path in a later lane.
- `finance_capital_hilton_invoice_packet_v0` blocks_send: Recipient and CC decision is pending. -> Operator confirms To/CC list before any email draft is used.
- `finpkt_505f7d07fc0dbd6d0d1f` optional: Approved evidence reference is missing. -> Link an approved note, receipt reference, or sanitized metadata packet.
- `finpkt_505f7d07fc0dbd6d0d1f` optional: Mac invoice spreadsheet filename is not known. -> Mac Finance Spreadsheet Evidence Intake v0
- `finance_capital_hilton_invoice_packet_v0` optional: Mac invoice spreadsheet filename or metadata packet is not available. -> Mac Finance Spreadsheet Evidence Intake v0

## Risks
- `finpkt_505f7d07fc0dbd6d0d1f` missing_amount (high): Provide the amount as an operator claim or approved evidence reference.
- `finance_capital_hilton_invoice_packet_v0` missing_amount (high): Operator must provide amount/rate per gig or approved evidence before any invoice draft context can be considered.
- `finpkt_505f7d07fc0dbd6d0d1f` send_not_allowed (high): Keep all invoice/email outputs as draft context only until a later explicit approval path exists.
- `finance_capital_hilton_invoice_packet_v0` send_not_allowed (high): Draft email is review-only; no send or external communication is authorized.
- `finpkt_505f7d07fc0dbd6d0d1f` unclear_client (high): Provide the client/project label or approve a safe metadata source that contains it.
- `finance_capital_hilton_invoice_packet_v0` unsupported_claim (high): Treat all Capital Hilton facts as operator claims until dates, amount, PO, recipient, and portal reference are confirmed.
- `finance_capital_hilton_invoice_packet_v0` bank_data_needed (medium): Payment tracking later requires approved bank/ledger evidence; this lane performs no bank access.
- `finpkt_505f7d07fc0dbd6d0d1f` missing_date (medium): Provide a date/period or approved evidence reference.
- `finance_capital_hilton_invoice_packet_v0` missing_date (medium): Operator must confirm exact service dates for tonight's gig and last Friday's gig.
- `finance_capital_hilton_invoice_packet_v0` sensitive_data_needed (medium): Invoice details and spreadsheet data remain sensitive metadata only until approved evidence intake.
- `finpkt_505f7d07fc0dbd6d0d1f` spreadsheet_needs_review (medium): Treat ~/Documents/invoices/ as sensitive metadata only; use a future Mac-side intake lane for filename metadata.
- `finance_capital_hilton_invoice_packet_v0` spreadsheet_needs_review (medium): Treat ~/Documents/invoices/ as sensitive metadata only; next safe lane is Mac Finance Spreadsheet Evidence Intake v0.

## Latest Packet Outputs
- `bounded_context_packet` send_allowed=False invoice_creation_allowed=False: Finance packet context for Chief/Cassandra
- `capital_hilton_draft_email_review_only` send_allowed=False invoice_creation_allowed=False: Draft email body for operator review only (`generated/finance_packets/capital_hilton_invoice_packet_v0/CAPITAL_HILTON_DRAFT_EMAIL_REVIEW_ONLY.md`)
- `capital_hilton_packet_summary` send_allowed=False invoice_creation_allowed=False: Capital Hilton packet summary and missing facts (`generated/finance_packets/capital_hilton_invoice_packet_v0/CAPITAL_HILTON_PACKET_SUMMARY.md`)
- `capital_hilton_portal_fill_instruction_prompt` send_allowed=False invoice_creation_allowed=False: Codex Desktop portal-fill instruction prompt, no submit (`generated/finance_packets/capital_hilton_invoice_packet_v0/CAPITAL_HILTON_PORTAL_FILL_PROMPT_NO_SUBMIT.md`)
- `capital_hilton_receivable_tracking_proposal` send_allowed=False invoice_creation_allowed=False: Receivable tracking proposal pending invoice approval (`generated/finance_packets/capital_hilton_invoice_packet_v0/CAPITAL_HILTON_RECEIVABLE_TRACKING_PROPOSAL.md`)

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
- `wbcard_595e855c32c9485f3127` needs_review: Capital Hilton invoice packet needs facts
- `wbcard_3391f8c6db1e59c51c6b` needs_review: Capital Hilton portal-fill prompt pending approval
- `wbcard_4ff0b10d3febb4356859` planned: Capital Hilton receivable tracking pending invoice send
- `wbcard_6a5098ba58d539d4390b` needs_review: Finance Invoice Evidence Packet Builder
- `wbcard_95706de4a863fcb25686` needs_review: Finance Invoice Evidence Packet Builder
- `wbcard_033ee3e3f51f17787a24` needs_review: Mac spreadsheet evidence intake needed
- `wbcard_56753122b32749dcb9f4` needs_review: Mac spreadsheet evidence intake needed
- `wbcard_c3fa812491a9deebb2ac` needs_review: Review missing finance evidence
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
