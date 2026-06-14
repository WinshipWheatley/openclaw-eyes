# Invoice Delivery Run Package Assembler

## Summary
OpenClaw can now assemble the Capital Hilton invoice delivery run package shape across delivery facts, invoice artifact refs, email package refs, Coupa package refs, Guardian/covenant refs, proof plans, execution gates, and future completion receipts. It does not execute.

## Capital Hilton Not Ready
- Status: NOT_READY_MISSING_ARTIFACT
- Message: OpenClaw has assembled the Capital Hilton invoice delivery run package shape. It is not ready to execute yet. The workflow still needs confirmed Coupa PO/reference; final invoice artifact/hash; confirmed recipient/contact route; email delivery package; Coupa supplier portal package; Guardian approval; exact operator approval; send/submit receipts. Nothing has been sent, submitted, opened, approved, or recorded as complete.
- Missing: confirmed Coupa PO/reference; final invoice artifact/hash; confirmed recipient/contact route; email delivery package; Coupa supplier portal package; Guardian approval; exact operator approval; send/submit receipts
- Next: Generate, attach, and hash the Winship-branded invoice PDF/XLSX before package review.

## Review Package
- Status: RUN_PACKAGE_READY_FOR_REVIEW
- Message: OpenClaw has assembled the Capital Hilton invoice delivery run package for review. It still has no execution authority. Nothing has been sent, submitted, opened, approved, or recorded as complete.
- Next: Review the package and collect missing approval/proof/adapter receipts; execution remains locked.

## Completion Target
- Label: INVOICE_SENT_AND_RECORDED
- Completion allowed: false
- Missing receipts: email send receipt, future, Coupa submit/confirmation receipt, future if Coupa required, attachment proof receipt, operator approval receipt, payment tracking update receipt, future

## Blocked
- DELIVERY_FACTS_MISSING: Delivery facts are missing.
- INVOICE_ARTIFACT_MISSING: Invoice artifact is missing.
- EMAIL_PACKAGE_MISSING: Email package is missing.
- COUPA_PACKAGE_MISSING: Coupa package is missing.
- APPROVAL_MISSING: Approval is missing.
- ACTION_COVENANT_MISSING: Action Covenant is missing.
- SECRET_REF_MISSING: Protected secret ref is missing.
- PROOF_MISSING: Proof is missing.
- EXECUTION_ADAPTER_MISSING: Execution adapter is missing.
- EMAIL_SEND_ATTEMPTED: Email send is blocked.
- COUPA_SUBMIT_ATTEMPTED: Coupa submit is blocked.
- BROWSER_ATTEMPTED: Browser access is blocked.
- COMPLETION_CLAIM_WITHOUT_RECEIPTS: Completion claim is blocked without receipts.
- EXTERNAL_ACTION_ATTEMPTED: External action is blocked.
- UNKNOWN_FAIL_CLOSED: Unknown run package state fails closed.

## Boundary
No run package execution, no workflow run, no email send, no Mail/Gmail send, no Coupa access/submit, no browser, no secret reveal, no approval execution, no payment tracking write, no external action, no credential handling, no raw-body ingestion.
