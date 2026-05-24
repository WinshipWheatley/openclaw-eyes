# Capital Hilton Performance Dates Capture Boundary v0

## ELIWINSHIP Summary

This is the first backend capture boundary for a workflow block. It says what would happen later if Winship chooses Use this draft for the Capital Hilton Performance Dates block.

It does not write the receipt yet. It does not change the real workflow state. It does not generate an invoice, create an email draft, send anything, or touch Coupa/Gmail/browser/Telegram.

## What It Validates

- Current OpenClaw dates: `2026-05-08, 2026-05-15`
- Draft input: `May 22 and May 29`
- Draft date set: `2026-05-08, 2026-05-15, 2026-05-22, 2026-05-29`
- Added dates: `2026-05-22, 2026-05-29`
- Validation status: `VALID_CAPTURE_CANDIDATE`

Adding May 22 and May 29 can become a valid capture candidate because the active session already has 2026 Capital Hilton dates. The year inference is still deterministic, not guessed from thin air.

## What Would Be Written Later

A future receipt/state writer would need to write an operator performance-date receipt and update the canonical workflow block. This contract only names that target.

## Downstream Effects

- Captured dates would update invoice packet inputs later.
- Subtotal preview would recalculate only after the rate is confirmed.
- Any email attachment would need a regenerated invoice later.
- Proof and PO/reference coverage may need to cover all four dates.
- Approval and send remain locked.

## Why This Matters

This is how Use this draft eventually becomes real without jumping to unsafe automation. The live draft stays reversible until an explicit capture boundary, then a future receipt-backed writer can commit it safely.

## Still Blocked

- receipt write
- canonical workflow state write
- capture execution
- invoice generation or preview render
- email draft or send
- approval submission
- browser/Coupa/Gmail/Telegram/account access
- credential handling
- model/tool/agent/runtime/queue execution
- file write or cleanup
- raw private body ingestion

## Authority

- Receipt write allowed: `false`
- State write allowed: `false`
- Capture execution allowed: `false`
- Invoice generation allowed: `false`
- Email send allowed: `false`
