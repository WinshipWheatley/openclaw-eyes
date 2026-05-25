# Coupa Supplier Portal Package Compiler

## Summary
OpenClaw can now assemble a Coupa supplier portal payment-rail package from PO/reference, invoice value, artifact, protected secret, Guardian approval, portal gate, and proof refs. Nothing is opened, logged into, submitted, or paid.

## Capital Hilton Missing PO
- Status: NOT_READY_MISSING_PO
- Message: OpenClaw has assembled the Coupa payment-rail package shape for Capital Hilton. Nothing has been opened or submitted. The package still needs the Coupa PO/reference, required proof, and Guardian/operator approval before any future Coupa/browser adapter can act.
- PO/reference: No Coupa PO/reference ref
- Invoice values: VALUES_CONFIRMED; dates/rate/subtotal refs present
- Artifact: invoice_artifact_ref:capital_hilton_pdf_2026-05-25, invoice_artifact_ref:capital_hilton_xlsx_2026-05-25
- Next: Provide, attach, or confirm the Coupa PO/reference, or tell OpenClaw to keep discovery open.

## Complete Except Approval
- Status: NOT_READY_MISSING_APPROVAL
- Message: The Coupa package has PO/value/artifact posture, but the Guardian approval packet is missing.
- Approval: READY_FOR_GUARDIAN_REVIEW
- Next: Create an Action Covenant and Guardian approval request for SUBMIT_COUPA.

## Blocked
- PO_REFERENCE_MISSING: Coupa PO/reference is missing.
- PO_REFERENCE_UNCONFIRMED: Coupa PO/reference must be confirmed before future submit.
- INVOICE_VALUES_MISSING: Invoice values are missing.
- VALUE_MISMATCH: Invoice value mismatch blocks Coupa package readiness.
- ARTIFACT_REF_MISSING: Invoice artifact ref is missing.
- ARTIFACT_HASH_MISSING: Artifact hash/fingerprint is missing.
- SECRET_REF_MISSING: Protected credential ref is missing.
- APPROVAL_MISSING: Guardian/operator approval is missing.
- BROWSER_GATE_MISSING: Browser gate is missing.
- SUBMIT_GATE_MISSING: Submit gate is missing.
- RAW_PO_EXPOSED: Raw PO/reference exposure is blocked.
- RAW_CREDENTIAL_INCLUDED: Credential exposure is blocked.
- COUPA_ACCESS_ATTEMPTED: Coupa access is blocked.
- COUPA_SUBMIT_ATTEMPTED: Coupa submit is blocked.
- BROWSER_ATTEMPTED: Browser access is blocked.
- EXTERNAL_ACTION_ATTEMPTED: External action is blocked.
- UNKNOWN_FAIL_CLOSED: Unknown Coupa package state fails closed.

## Boundary
No Coupa access, no Coupa submit, no browser, no portal login, no secret reveal, no payment action, no approval execution, no workflow run, no agent dispatch, no external action, no credential handling, no raw-body ingestion.
