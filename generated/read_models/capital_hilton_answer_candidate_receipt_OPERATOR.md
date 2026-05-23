# Capital Hilton Answer Candidate Receipt v0

## ELIWINSHIP Summary

An answer candidate is a safe receipt for what Winship says or points to while resolving a Capital Hilton proof question. It can clarify memory, reject a candidate, park an item, or point toward a source card, protected reference, or receipt. It does not prove the invoice facts by itself.

## Why Answers Clarify But Do Not Prove

- Text, yes/no, and structured-form answers become memory candidates unless linked to proof refs.
- Source-card, protected-reference, and receipt answers point toward proof but still need validation.
- Protected references need Guardian review before promotion.
- Text answers do not quiet proof because memory is not source proof.

## Default Answer Candidates

- `performance_date_2026_05_08_proof`: `UNANSWERED`
- `performance_date_2026_05_15_proof`: `UNANSWERED`
- `rate_400_per_gig_proof`: `UNANSWERED`
- `subtotal_800_proof`: `UNANSWERED`
- `one_invoice_posture_proof`: `UNANSWERED`
- `coupa_po_payment_reference_metadata`: `UNANSWERED`
- `excel_workbook_or_invoice_source_reference`: `UNANSWERED`
- `ap_recipient_route_metadata`: `UNANSWERED`
- `tax_vendor_handling_metadata`: `UNANSWERED`
- `future_invoice_generation_receipt_requirement`: `UNANSWERED`

## Parked, Rejected, Or Unknown Answers

- Parked items stay visible as parked, not completed.
- Rejected candidates can quiet only with a reason and receipt policy.
- Unknown states fail closed and keep the proof item proof-needed.

## Still Blocked

- Coupa access
- browser/OAuth/account access
- credential/token/cookie/API key handling
- Gmail/calendar/email account access
- raw Excel body ingestion
- raw PDF body ingestion
- raw email body ingestion
- raw finance/private body ingestion
- invoice generation
- ledger write
- email dispatch
- send/submit/approval
- live model call
- agent activation
- tool execution
- queue/autonomy
- proof satisfaction by operator answer alone
- automatic quieting
- protected reference promotion without Guardian gate

## Next Backend Batch Lane

- Prompt 2 will define protected proof reference placeholders. It still will not access protected files or raw finance bodies.
