# Capital Hilton Protected Proof Intake v0

## ELIWINSHIP Summary

Capital Hilton has ten proof gaps. This packet turns them into concrete questions Winship can answer or point toward, while keeping the answer separate from proof. A text answer can help the system know where to look; it does not prove the invoice facts by itself.

## Candidate Facts

- Target world: `Finance`
- Current phase: `HELM_THRESHOLD_LANE`
- Lane destiny: `MOVE_TO_WORLD_ACTION`
- Missing proof count: `10`
- Protected proof required: `true`
- Candidate dates: `2026-05-08, 2026-05-15`
- Candidate rate: `$400 per gig`
- Candidate subtotal: `$800`
- Candidate one-invoice posture: `true`
- Candidate facts proven: `false`

## What Winship Can Provide Or Point To

- `performance_date_2026_05_08_proof`: Can we point to protected proof that the May 8, 2026 Capital Hilton performance happened?
- `performance_date_2026_05_15_proof`: Can we point to protected proof that the May 15, 2026 Capital Hilton performance happened?
- `rate_400_per_gig_proof`: Can we point to proof that the agreed rate was $400 per gig?
- `subtotal_800_proof`: Can deterministic math prove 2 gigs x $400 = $800 from accepted source facts?
- `one_invoice_posture_proof`: Should these two dates be billed together on one invoice, and what proof supports that?
- `coupa_po_payment_reference_metadata`: Is there a Coupa, PO, payment, or reference number that needs to appear on the invoice packet?
- `excel_workbook_or_invoice_source_reference`: Is there an Excel workbook, invoice template, or source artifact that should be referenced without ingesting the raw body?
- `ap_recipient_route_metadata`: What is the approved AP route or recipient path, without sending anything yet?
- `tax_vendor_handling_metadata`: Are there tax, vendor, W-9, entity, or payment-handling details that affect the invoice packet?
- `future_invoice_generation_receipt_requirement`: What receipt would prove a future invoice was generated correctly, if invoice generation is ever approved later?

## Answers Versus Proof

- Text answers become Memory Candidate Receipts.
- Screenshot, file, source-card, protected-reference, or receipt answers can point toward proof.
- Protected references still need Guardian review before promotion.
- Nothing here generates an invoice or accesses Coupa, browser, email, Excel, accounts, credentials, ledgers, or send/submit/approval paths.

## What Quiets Items

- `performance_date_2026_05_08_proof`: Quiet only after protected proof metadata or a valid rejected/obsolete receipt is linked.
- `performance_date_2026_05_15_proof`: Quiet only after protected proof metadata or a valid rejected/obsolete receipt is linked.
- `rate_400_per_gig_proof`: Quiet only after rate proof metadata is linked or the candidate rate is rejected with a receipt.
- `subtotal_800_proof`: Quiet after a deterministic math receipt links accepted date and rate proof.
- `one_invoice_posture_proof`: Quiet after one-invoice posture is source-backed, parked with reason, or rejected with receipt.
- `coupa_po_payment_reference_metadata`: Quiet after protected metadata identifies the reference or a receipt states none is required.
- `excel_workbook_or_invoice_source_reference`: Quiet after source artifact metadata is linked or the artifact is rejected as irrelevant with a receipt.
- `ap_recipient_route_metadata`: Quiet after the AP route is protected-metadata linked, parked for discovery, or rejected with reason.
- `tax_vendor_handling_metadata`: Quiet after protected metadata resolves relevance or a rejection/obsolete receipt is linked.
- `future_invoice_generation_receipt_requirement`: Quiet only as a future receipt requirement; it does not authorize invoice generation.

## Shared Fix Path

- `protected_finance_proof_metadata_intake`
- Solving one protected finance proof metadata intake can update Capital Hilton, Cassandra, Finance World, Guardian, and Package Preview posture after receipts/gates exist.

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

## Next Safest Move

- Capture answers as memory candidates, then link actual source-card/protected evidence/receipt metadata through Guardian-gated proof intake.
