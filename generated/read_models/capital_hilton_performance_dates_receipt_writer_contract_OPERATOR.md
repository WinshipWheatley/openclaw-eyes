# Capital Hilton Performance Dates Receipt Writer Contract v0

## ELIWINSHIP Summary

This is the first Use this draft backend landing zone. It still does not write real state. It defines the exact receipt payload, state update target, and stale-preview record a future writer would use.

## What Would Be Captured Later

- Previous dates: `2026-05-08, 2026-05-15`
- New dates: `2026-05-08, 2026-05-15, 2026-05-22, 2026-05-29`
- Added dates: `2026-05-22, 2026-05-29`
- Receipt type: `OPERATOR_PERFORMANCE_DATES_ADDITION`
- Show count: `2` -> `4`

May 22 and May 29 would become a deterministic addition receipt. The receipt would say exactly what changed, where it came from, and which previews became stale.

## What Becomes Stale

- Invoice packet preview.
- Invoice packet artifact.
- Email draft attachment.
- Approval packet preview.
- Prior subtotal preview.
- Proof/PO coverage status.

Subtotal recalculates later after rate confirmation. Proof and send remain gated. No invoice or email is generated here.

## Why This Matters

OpenClaw can make local drafts meaningful without unsafe automation: draft first, explicit capture second, receipt-backed state later, execution gates last.

## Still Blocked

- live receipt write
- live workflow state write
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

- Live receipt write allowed: `false`
- Live state write allowed: `false`
- Invoice generation allowed: `false`
- Email send allowed: `false`
- Test-only writer harness used: `false`
