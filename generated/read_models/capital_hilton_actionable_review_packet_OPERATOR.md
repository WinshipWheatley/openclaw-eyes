# Capital Hilton Actionable Review Packet v1

Status:
- Actionable for manual review: `true`.
- Ready for submission: `false`.
- Email sent: `false`.
- Portal submitted: `false`.
- Credentials accessed: `false`.
- Spreadsheet cells read: `false`.

## Invoice Facts
- Exact service date for tonight's gig: 2026-05-15 (operator said this was yesterday relative to May 16, 2026) (unverified_claim; needs confirmation)
- Exact service date for last Friday's gig: 2026-05-08 (unverified_claim; needs confirmation)
- Rate or amount per gig: $400 per gig (unverified_claim; needs confirmation)
- One invoice or two invoices: one invoice for 2026-05-15 and 2026-05-08; operator also wants 2026-05-22 upcoming gig and older gigs reviewed for inclusion if applicable (unverified_claim; needs confirmation)
- PO number(s) or explicit none: unknown; operator reports Coupa PO credit may exist and PO must be confirmed in Coupa later; no portal login authorized (unverified_claim; needs confirmation)
- Billing/remit details: mail check to operator home address provided in prompt; full street address redacted from committed artifacts (unverified_claim; needs confirmation)
- To/CC recipient decision: To: Annette Sunga (business email pending confirmation); CC: operator email, Chyna Hardin, Lawrence/Will Valcovic; no send authority (unverified_claim; needs confirmation)
- Supplier portal reference: Coupa supplier portal reference provided by operator; credential use/storage not authorized; credentials must remain tokenized in a later approved lane (unverified_claim; needs confirmation)
- Invoice attachment/output path: invoice must be created in Coupa against confirmed PO; existing Mac Documents/invoices spreadsheet is metadata-only source workbook; next invoice number should be one higher after workbook review; no spreadsheet cells read (unverified_claim; needs confirmation)

## Review Calculation
- Rate: $400 per gig
- Completed service dates in governed facts: 2026-05-08, 2026-05-15 (operator said this was yesterday relative to May 16, 2026)
- Candidate subtotal: $800 for the two completed governed service-date facts, before any older/upcoming gig review
- Final total claimed: `false`.

## Recipient Posture
- To: Annette Sunga (business email pending confirmation); CC: operator email, Chyna Hardin, Lawrence/Will Valcovic; no send authority
- Email send allowed: `false`.
- Contact evidence: Annette Sunga (needs_review)
- Contact evidence: Annette Sunga | Finance/AP contact | email=Annette.Sunga@hilton.com | allowed_use=to_candidate_pending_review (needs_review)
- Contact evidence: Chyna Hardin | Director of Finance | email=Chyna.Hardin@hilton.com | allowed_use=cc_candidate_pending_review (needs_review)
- Contact evidence: Lawrence / Will Valcovic | Hilton contact | email=lawrencevalcovic@hilton.com | allowed_use=cc_candidate_pending_review (needs_review)
- Contact evidence: winshiplive@gmail.com (needs_review)
- Contact evidence: Chyna Hardin, Director of Finance, Chyna.Hardin@hilton.com; Lawrence / Will Valcovic, lawrencevalcovic@hilton.com (needs_review)

## PO / Coupa Gate
- PO must be confirmed manually in Coupa before any final submission.
- OpenClaw may not log in, use credentials, upload, save, submit, or create a payable invoice.

## Exact Manual Steps
1. Confirm service dates and service list: 2026-05-08, 2026-05-15 (operator said this was yesterday relative to May 16, 2026). Do not include 2026-05-22 or older gigs unless operator confirms they belong on this invoice.
2. Confirm rate and review subtotal: $400 per gig; review subtotal candidate: $800 for the two completed governed service-date facts, before any older/upcoming gig review.
3. Manually open Coupa/Supplier Portal outside OpenClaw, using operator-controlled credentials only; confirm PO number and available PO credit.
4. Manually open the invoice workbook `Invoice Capitol Hilton 20260512 v2.xlsx` on the Mac if needed; confirm the current invoice number and set the next invoice number one higher. OpenClaw did not read cells.
5. Prepare the Coupa invoice manually only after PO, service dates, line items, amount, remit posture, and invoice number are confirmed.
6. Use recipient posture only as a draft/review list; do not send email from OpenClaw.
7. Return non-sensitive confirmation metadata to OpenClaw in a later lane if you want a receipt/read-model update.

## What Not To Do
- Do not send email or Gmail.
- Do not submit, save, upload, or create a payable invoice in Coupa from OpenClaw.
- Do not access, store, tokenize, or print credentials in this lane.
- Do not read spreadsheet cells or parse workbook formulas.
- Do not inspect bank data, private raw files, raw messages, or old HITL state.
- Do not treat parsed evidence as financial truth until operator confirmation.

## Remaining Blockers
- `po_coupa_confirmation_required` (blocks_final_submission): PO number is still unknown and must be confirmed manually in Coupa. Next: Operator confirms PO/available credit in Coupa without sharing credentials with OpenClaw.
- `recipient_confirmation_required` (blocks_email_send): Recipient posture is review-only and business email still needs operator confirmation. Next: Operator confirms To/CC list before any future email-send lane.
- `coupa_invoice_creation_manual_only` (blocks_openclaw_submission): Invoice must be created in Coupa against confirmed PO; OpenClaw has no portal/credential authority. Next: Operator manually prepares/reviews Coupa entry or approves a later bounded no-submit portal-review lane.
- `spreadsheet_invoice_number_manual_check` (blocks_final_invoice_number_claim): Invoice workbook is known only as metadata; OpenClaw did not read cells or formulas. Next: Operator manually opens the Mac invoice workbook and confirms next invoice number/formulas.

## Next Safe Lane
- Capital Hilton Manual Coupa PO Confirmation v0
