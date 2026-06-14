# Invoice Delivery Completion Proof Aggregator

## Summary
OpenClaw can now aggregate final invoice delivery proof refs and decide whether INVOICE_SENT or INVOICE_SENT_AND_RECORDED may be displayed. Missing receipts block completion.

## Capital Hilton
- Not complete: COMPLETION_BLOCKED_NO_RECEIPTS - OpenClaw cannot mark the Capital Hilton invoice as sent yet. The final proof receipts are missing: EMAIL_SEND_RECEIPT, EMAIL_ATTACHMENT_PROOF, GMAIL_PROVIDER_MESSAGE_REF, COUPA_SUBMIT_RECEIPT, COUPA_CONFIRMATION_PROOF, INVOICE_ARTIFACT_SAVED_RECEIPT, INVOICE_ARTIFACT_HASH_PROOF, GUARDIAN_APPROVAL_RECEIPT, OPERATOR_APPROVAL_RECEIPT, PAYMENT_TRACKING_UPDATE_RECEIPT, LOCAL_RECORD_SAVED_RECEIPT. Nothing new was sent, submitted, or recorded by this check.
- Email-only: COMPLETION_BLOCKED_MISSING_COUPA_PROOF - OpenClaw cannot claim INVOICE_SENT_AND_RECORDED because Coupa submit/confirmation proof is missing.
- Coupa-only: COMPLETION_BLOCKED_MISSING_EMAIL_PROOF - OpenClaw cannot claim INVOICE_SENT because email send and attachment proof refs are missing.
- Fully complete fixture: COMPLETION_CONFIRMED - INVOICE SENT AND RECORDED. Proofs show: Email sent to Annette with Winship-branded invoice attachment. Coupa invoice submitted/confirmed from PO if required. Invoice artifact saved with date. Guardian/operator approval receipts present. Payment tracking updated if required.
- False claim: COMPLETION_BLOCKED_MISSING_EMAIL_PROOF - Invoice sent, INVOICE_SENT, COUPA_INVOICE_SUBMITTED, INVOICE_SENT_AND_RECORDED

## Blockers
- COMPLETION_CLAIM_WITHOUT_EMAIL_RECEIPT: Email completion claim lacks receipt proof.
- COMPLETION_CLAIM_WITHOUT_COUPA_RECEIPT: Coupa completion claim lacks receipt proof.
- COMPLETION_CLAIM_WITHOUT_ARTIFACT_HASH: Artifact hash proof is missing.
- COMPLETION_CLAIM_WITHOUT_APPROVAL: Approval proof is missing.
- COMPLETION_CLAIM_WITHOUT_LOCAL_RECORD: Local record proof is missing.
- STALE_PROOF: Stale proof blocks completion.
- RAW_PROVIDER_ID_EXPOSED: Raw provider id exposure is blocked.
- RAW_PRIVATE_BODY_EXPOSED: Raw private body exposure is blocked.
- EXTERNAL_ACTION_ATTEMPTED: External action is blocked.
- UNKNOWN_FAIL_CLOSED: Unknown completion state fails closed.

## Boundary
No completion write, no email send, no Mail/Gmail send, no Coupa access/submit, no browser, no payment tracking write, no visual artifact spawn, no external action, no workflow run, no agent dispatch, no credential handling, no raw-body ingestion.
