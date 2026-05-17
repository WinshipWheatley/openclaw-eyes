# Capital Hilton Two-Invoice Workflow

Status:
- Base invoice workflow preserved: `true`.
- Hilton Coupa overlay modeled: `true`.
- Coupa payment invoice modeled: `true`.
- Excel companion invoice modeled: `true`.
- Ready for submission: `false`.
- Email sent: `false`.
- Coupa submitted: `false`.
- Spreadsheet write triggered: `false`.

## Base vs Hilton Overlay
- Base workflow: A client-agnostic invoice workflow may use one operator invoice artifact as the payment-generating invoice unless a client-specific portal/PO rule overrides it.
- Hilton overlay: For Hilton/Capital Hilton, the Coupa Supplier Portal invoice created from the Hilton PO is the payment-generating invoice. The Excel/generated invoice is a companion/reference invoice.

## Invoice Artifacts
- Coupa payment invoice: `not_created_by_openclaw_proof_not_captured`; payment-generating for Hilton.
- Excel companion invoice: `screenshot_confirmed_companion_context_only`; not payment-generating for Hilton.
- Excel invoice number evidence: `2026-1005`; total due context: `800.00 USD`.

## PO Budget Context
- PO: `DCASH00983536`; status: `Issued - Pending Manual`.
- Total: `4000.00 USD`; invoiced-to-date: `2000.00 USD`; apparent remaining: `2000.00 USD`.
- Budget context is screenshot evidence, not final accounting truth.

## Protected Evidence Slots
- `coupa_invoice_pdf_or_download`: protected_local_or_operator_approved_artifact_reference_only
- `excel_companion_invoice_file_or_pdf`: protected_local_file_reference_only
- `check_image_or_deposit_proof`: protected_local_only_no_normal_repo_storage
- `money_ledger_payment_confirmation`: money_ledger_reference_only_no_bank_details

## Boundary
- No Coupa submit, invoice creation, email send, spreadsheet write, browser automation, secret storage, or runtime authority.
- Payment-ready requires Coupa invoice proof; paid requires money-ledger confirmation.

Next safe lane: Capital Hilton Coupa Payment Invoice Proof Capture v0
