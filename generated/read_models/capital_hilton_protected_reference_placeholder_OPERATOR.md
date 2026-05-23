# Capital Hilton Protected Reference Placeholder v0

## ELIWINSHIP Summary

A protected reference placeholder is a safe pointer. It lets Winship say where proof may live without exposing the raw file, copying it, uploading it, reading it, or treating the pointer as proof.

## Why This Helps

The system can remember that proof may be in a workbook, PDF, Coupa/PO reference, AP route, contract/rate source, performance proof source, tax/vendor/payment source, or future receipt shape. It keeps only metadata labels, source-card refs, receipt refs, hash placeholders, and redaction posture.

## What Is Safe Metadata

- Labels, roles, approximate source-location hints, source-card pointers, receipt pointers, hash placeholders, and redacted reference labels.
- These are still not proof until validated and promoted through the required receipts and Guardian review.

## What Stays Blocked

- Raw workbook, PDF, email, finance/private, Coupa portal, contract, tax, vendor, bank, check, remit, credential, session, account, browser, invoice, ledger, send, submit, approval, model, tool, agent, queue, and runtime material.

## Default Placeholders

- `excel_workbook_invoice_source_placeholder`: `EXCEL_WORKBOOK_REFERENCE`
- `coupa_po_payment_reference_placeholder`: `COUPA_REFERENCE_METADATA`
- `ap_route_metadata_placeholder`: `AP_EMAIL_ROUTE_METADATA`
- `rate_source_placeholder`: `CONTRACT_OR_RATE_SOURCE_REFERENCE`
- `performance_proof_reference_placeholder`: `PERFORMANCE_PROOF_REFERENCE`
- `tax_vendor_payment_handling_placeholder`: `TAX_VENDOR_PAYMENT_REFERENCE`
- `future_invoice_generation_receipt_placeholder`: `FUTURE_INVOICE_RECEIPT_REFERENCE`

## Guardian Review

Guardian can later review whether the metadata posture is safe to promote. Guardian cannot approve invoice generation, send/submit, Coupa/account access, browser access, email dispatch, raw body extraction, ledger writes, or runtime execution.

## Future Answer Workspace

Answer candidates may point to these placeholders. The placeholder remains non-proof until source-card, receipt, hash, redaction, and Guardian metadata requirements are satisfied. No upload or file picker is implemented here.
