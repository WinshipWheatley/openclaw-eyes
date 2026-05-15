# Capital Hilton Invoice Packet v0 - Summary

Purpose: prepare a reviewable evidence packet for Capital Hilton invoice work without sending anything or making financial truth claims.

Packet id: `finance_capital_hilton_invoice_packet_v0`
Internal agent: `cassandra`
External finance persona: `Clara Reid`

## Spreadsheet Metadata
- Selected candidate: `Invoice Capitol Hilton 20260512 v2.xlsx`
- Alternate candidate known: `Invoice Capitol Hilton 20260512.xlsx`
- Absolute path from Mac metadata: `/Users/hwinshipwheatley/Documents/invoices/Invoice Capitol Hilton 20260512 v2.xlsx`
- Sensitivity: `sensitive_metadata_only`
- Cell read allowed: `false`
- Workbook parsing allowed: `false`
- Copied/uploaded: `false`

## Contact Candidates
- Annette Sunga (Finance/AP contact), email=unknown, allowed_use=email_draft_recipient_candidate_needs_email_review, confidence=operator_supplied_candidate
- Chyna Hardin (Director of Finance), email=Chyna.Hardin@hilton.com, allowed_use=cc_candidate_pending_review, confidence=operator_supplied_candidate
- Lawrence / Will Valcovic (Hilton contact), email=lawrencevalcovic@hilton.com, allowed_use=cc_candidate_pending_review, confidence=operator_supplied_candidate

## Missing Facts Remaining
- blocks_invoice_draft: Amount or rate per gig is missing. -> Operator provides rate/amount per gig or approved evidence reference.
- blocks_invoice_draft: Billing/remit details need confirmation. -> Operator confirms billing name, remit email, mailing/payment details, and any tax/remit fields.
- blocks_invoice_draft: Exact date for last Friday's gig is not operator-confirmed for invoice use. -> Operator confirms the invoice date/service date for last Friday's gig.
- blocks_invoice_draft: Exact date for tonight's gig is not operator-confirmed for invoice use. -> Operator confirms the invoice date/service date for tonight's gig.
- blocks_invoice_draft: One invoice versus two invoices is undecided. -> Operator chooses one combined invoice or separate invoices per gig.
- blocks_invoice_draft: PO number(s) are missing. -> Operator provides PO number(s), says none, or approves portal metadata lookup later.
- blocks_invoice_draft: Supplier portal reference is unresolved. -> Operator confirms whether SmartSpend/Coupa is required and provides portal reference if known.
- blocks_send: Annette Sunga email is missing if Annette is selected as To recipient. -> Operator confirms Annette Sunga's email or chooses a different reviewed recipient.
- blocks_send: Invoice attachment/output path is missing. -> Operator chooses or approves invoice attachment/output path in a later lane.
- blocks_send: Recipient and CC decision is pending. -> Operator confirms To/CC list before any email draft is used.

## Boundaries
- No email send.
- No invoice send.
- No supplier portal login or submit.
- No bank access.
- No ledger write.
- No spreadsheet cell read.
- No financial truth claim.
