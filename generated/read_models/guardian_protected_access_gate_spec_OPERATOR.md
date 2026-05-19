# Guardian Protected Access Gate Spec v0

Status:
- Protected access allowed now: `false`.
- Guardian review required before future protected use: `true`.
- Security threshold required before live access/use: `true`.
- Raw protected content inspected/transmitted/stored: `false`.
- Approval, execution, browser, OAuth, credential, send, submit, and runtime authority: `false`.

## ELI5 Summary
- OpenClaw can know protected proof exists through a safe receipt/reference.
- The receipt is not the key and does not let agents open the protected proof.
- Guardian's gate decides whether a future use request is even eligible for later gated review.
- Nothing opens, sends, uploads, submits, or executes in this lane.
- This prepares the safety gate so later live workflows cannot skip proof, scope, Guardian review, or security-threshold controls.

## Access State Counts
- `ACCESS_NOT_REQUESTED`: 7
- `REFERENCE_MISSING`: 0
- `REFERENCE_RECORDED_ACCESS_BLOCKED`: 0
- `METADATA_INCOMPLETE`: 0
- `SECURITY_THRESHOLD_REQUIRED`: 0
- `GUARDIAN_REVIEW_REQUIRED`: 0
- `ACCESS_DENIED`: 0
- `ACCESS_READY_FOR_FUTURE_GATED_REVIEW`: 0
- `UNKNOWN_FAIL_CLOSED`: 2

## Gate Records
- `capital_hilton_coupa_payment_invoice_proof_access`: `ACCESS_NOT_REQUESTED`; allowed now: `false`.
- `capital_hilton_excel_companion_artifact_access`: `ACCESS_NOT_REQUESTED`; allowed now: `false`.
- `capital_hilton_pdf_invoice_attachment_access`: `ACCESS_NOT_REQUESTED`; allowed now: `false`.
- `cassandra_gmail_email_evidence_access`: `ACCESS_NOT_REQUESTED`; allowed now: `false`.
- `calendar_evidence_access`: `ACCESS_NOT_REQUESTED`; allowed now: `false`.
- `payment_sensitive_reference_access`: `ACCESS_NOT_REQUESTED`; allowed now: `false`.
- `client_credential_reference_access`: `ACCESS_NOT_REQUESTED`; allowed now: `false`.
- `browser_oauth_tool_bridge_reference_access`: `UNKNOWN_FAIL_CLOSED`; allowed now: `false`.
- `unknown_sensitive_surface_access`: `UNKNOWN_FAIL_CLOSED`; allowed now: `false`.

## Boundary
- Protected evidence receipts do not grant access.
- Unknown or unsupported protected access fails closed.
- Future use must pass exact scope, Guardian review, and security-threshold controls before live access exists.

Next safe lane: Capability Skill Registry Metadata Delta v0
