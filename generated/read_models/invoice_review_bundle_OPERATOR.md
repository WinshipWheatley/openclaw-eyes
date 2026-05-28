# Invoice Review Bundle

Review the Capital Hilton invoice package.
Nothing has been sent.
OpenClaw needs the current invoice page/period before it can attach the Excel invoice.

Approval card:
- Question: Review the Capital Hilton invoice package?
- Buttons: APPROVE, DO_NOT_APPROVE, EXPLAIN, EDIT_DRAFT, HOLD
- Excel invoice candidate: Capital Hilton Excel invoice candidate
- Preview: Excel candidate available for inspection. Inline PDF/image preview is not available yet.
- Attachment readiness: false
- Clara draft subject: Capital Hilton invoice package for review
- Approval footer: Approval is disabled until invoice selection, Coupa proof, recipients, and attachment proof are ready.

Blockers:
- Select the Capital Hilton invoice page/period from the confirmed workbook.
- Coupa submission proof is still required.
- Which invoice page/period should OpenClaw prepare for Capital Hilton?
- OpenClaw needs the current invoice page/period before it can attach the Excel invoice.
- Generated invoice artifact needs proof linking it to the selected invoice record.
- Recipient list needs confirmation.
- Send is blocked until approval and send execution receipts exist.

Guided fix paths:
- Select the Capital Hilton invoice page/period from the confirmed workbook. -> Select invoice page
- Coupa submission proof is still required. -> Start Coupa proof step
- Which invoice page/period should OpenClaw prepare for Capital Hilton? -> Select invoice page
- OpenClaw needs the current invoice page/period before it can attach the Excel invoice. -> Select invoice page
- Generated invoice artifact needs proof linking it to the selected invoice record. -> Regenerate or link invoice
- Recipient list needs confirmation. -> Review recipients
- Send is blocked until approval and send execution receipts exist. -> Prepare send approval

Proof is available behind disclosure. No email, Coupa, browser, ledger, or production action is enabled.
