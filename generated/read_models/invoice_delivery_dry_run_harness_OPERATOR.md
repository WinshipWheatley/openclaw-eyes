# Invoice Delivery Dry-Run Harness

## Summary
OpenClaw can now dry-run the Capital Hilton invoice delivery package and report ready steps, blocked steps, missing proofs, missing approvals, missing adapters, and next fixes without executing.

## Capital Hilton Current Dry-Run
- Status: DRY_RUN_BLOCKED_MISSING_INPUTS
- Message: OpenClaw ran a dry-run of the Capital Hilton invoice delivery package. Nothing was sent, submitted, opened, approved, or changed. The workflow is not executable yet because final invoice artifact/hash, confirmed recipient/contact route, email delivery package, confirmed Coupa PO/reference, Coupa supplier portal package, protected secret ref if future Coupa login required, INVOICE_ARTIFACT_HASH, RECIPIENT_CONFIRMATION, PO_REFERENCE_CONFIRMATION, GUARDIAN_APPROVAL, OPERATOR_APPROVAL, EMAIL_SEND_RECEIPT, COUPA_SUBMIT_RECEIPT, PAYMENT_TRACKING_RECEIPT, Guardian approval, Action Covenant, EMAIL_SEND_ADAPTER, COUPA_BROWSER_ADAPTER, COUPA_SUBMIT_ADAPTER, PAYMENT_TRACKING_ADAPTER. Next safe move: Fill the missing component inputs, then rerun the dry-run.
- Ready: 1 ready step(s): Validate Capital Hilton dates/rate basis
- Blocked: 9 blocked step(s): Verify invoice artifact/hash, Verify email package, Verify Coupa package, Verify Guardian approval, Verify action covenant, Verify protected secret refs, Verify email send adapter, Verify Coupa adapter, Verify final completion readback
- Missing: final invoice artifact/hash, confirmed recipient/contact route, email delivery package, confirmed Coupa PO/reference, Coupa supplier portal package, protected secret ref if future Coupa login required, INVOICE_ARTIFACT_HASH, RECIPIENT_CONFIRMATION, PO_REFERENCE_CONFIRMATION, GUARDIAN_APPROVAL, OPERATOR_APPROVAL, EMAIL_SEND_RECEIPT, COUPA_SUBMIT_RECEIPT, PAYMENT_TRACKING_RECEIPT, Guardian approval, Action Covenant, EMAIL_SEND_ADAPTER, COUPA_BROWSER_ADAPTER, COUPA_SUBMIT_ADAPTER, PAYMENT_TRACKING_ADAPTER
- Next: Fill the missing component inputs, then rerun the dry-run.

## Review Package Dry-Run
- Status: DRY_RUN_BLOCKED_MISSING_APPROVAL
- Message: OpenClaw ran a dry-run of the Capital Hilton invoice delivery package. Nothing was sent, submitted, opened, approved, or changed. The workflow is not executable yet because GUARDIAN_APPROVAL, OPERATOR_APPROVAL, EMAIL_SEND_RECEIPT, COUPA_SUBMIT_RECEIPT, PAYMENT_TRACKING_RECEIPT, Guardian approval, exact operator approval receipt, EMAIL_SEND_ADAPTER, COUPA_BROWSER_ADAPTER, COUPA_SUBMIT_ADAPTER, PAYMENT_TRACKING_ADAPTER. Next safe move: Create Guardian packet and future exact operator approval receipt before any execution adapter.
- Next: Create Guardian packet and future exact operator approval receipt before any execution adapter.

## Blocked
- RUN_PACKAGE_MISSING: Run package is missing.
- DELIVERY_FACTS_MISSING: Delivery facts are missing.
- INVOICE_ARTIFACT_MISSING: Invoice artifact/hash is missing.
- EMAIL_PACKAGE_MISSING: Email package is missing.
- COUPA_PACKAGE_MISSING: Coupa package is missing.
- APPROVAL_MISSING: Approval proof is missing.
- ACTION_COVENANT_MISSING: Action covenant is missing.
- SECRET_REF_MISSING: Protected secret ref is missing.
- SEND_ADAPTER_MISSING: Email send adapter is missing.
- COUPA_ADAPTER_MISSING: Coupa adapter is missing.
- PROOF_MISSING: Proof is missing.
- EXTERNAL_ACTION_ATTEMPTED: External action is blocked.
- COMPLETION_CLAIM_ATTEMPTED: Completion claim is blocked.
- UNKNOWN_FAIL_CLOSED: Unknown dry-run state fails closed.

## Boundary
No dry-run external action, no run package execution, no workflow run, no email send, no Mail/Gmail send, no Coupa access/submit, no browser, no secret reveal, no approval execution, no payment tracking write, no external action, no credential handling, no raw-body ingestion.
