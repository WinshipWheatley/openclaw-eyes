# Capital Hilton Coupa Workflow Harvest

Status: `CAPITAL_HILTON_COUPA_WORKFLOW_HARVEST_READY`

This harvest converts the June 1, 2026 Capital Hilton operator-assisted invoice run into a reusable automation contract. It is not a live Coupa task and it does not authorize browser, Coupa, Gmail, ledger, paid, submit, or send actions.

## Source Evidence

- Operator receipt: `/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_receipt_20260601T221600Z.json`
- Operator report: `/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_report_20260601T221600Z.md`
- Full automation report: `/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_full_automation_report_20260601T222036Z.md`
- Final PDF: `/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/2026-06-01/Invoice_Capital_Hilton_2026-06-01.pdf`

## Reusable Workflow Contract

- `workflow_ref`: `capital_hilton_coupa_invoice_submission`
- `provider_mode`: `operator_assisted_browser`
- Correct route: PO-based invoice creation, not uploaded-invoice route.
- PO observed: `DCASH00983536`
- Workbook/PDF invoice number: `2026-1006`
- Coupa invoice number: `2026 1006`
- Coupa status after submission: `Processing`
- Remit-To selected: mailing/check address for Winship.

## Required Inputs

- Corrected invoice PDF with artifact validation.
- PO number.
- Invoice number normalized for Coupa.
- Remit-To selection.
- Final Coupa submit approval.
- Post-submit email approval.

## Gates

- Login/MFA gate.
- Remit-To selection gate.
- Invoice number normalization gate.
- Final Coupa submit gate.
- Gmail draft review gate.
- Final email send gate.

## Blocked By Default

- Autonomous Coupa submit.
- Autonomous email send.
- Ledger post.
- Paid marking.

## What Can Be Automated

- Validate the corrected PDF by path, page count, hash, and text facts.
- Navigate after operator login and customer context confirmation.
- Locate PO `DCASH00983536` and start Create Invoice from PO.
- Verify prefilled supplier, customer, PO line, quantity, price, total, date, and currency.
- Calculate and classify warnings before presenting a submit packet.
- Create or replace a Gmail draft with attachment proof for review.

## What Requires Operator Confirmation

- Login/MFA and correct account/customer context.
- Remit-To selection.
- Invoice number normalization when Coupa rejects special characters.
- Final Coupa Send Invoice action.
- Final Gmail send after draft and attachment review.

## What Failed Today

- Excel/AppleScript export said success but produced no PDF.
- Excel helper had `OPEN_WORKBOOK` and permission fragility.
- Print-to-PDF UI was the path that actually worked.
- `openpyxl` was missing in the default Python environment.
- Browser text helpers hit a virtual clipboard issue.
- Gmail draft with attachment needed replacement because attachment drafts were not editable in place.

## What To Test Next

- Deterministic workbook reader and patcher path independent of ad hoc Python packages.
- Receipt-driven Excel open/export/close with file-exists, text, and hash validation.
- Stable local working-copy roots for client workbook permissions.
- Coupa PO invoice state machine with customer select, PO locate, remit-to gate, field recheck, calculate, warning classify, final submit gate, and processing receipt.
- Customer-specific invoice number normalization rules.
- Gmail draft replacement and stale-draft warning behavior.

## Safety Boundary

- Ledger mutation: no.
- Paid marking: no.
- Payment receipt recording: no.
- Autonomous OpenClaw Coupa submit: no.
- Autonomous OpenClaw email send: no.
- This harvest is reusable system knowledge only.
