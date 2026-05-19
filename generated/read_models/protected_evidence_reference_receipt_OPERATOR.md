# Protected Evidence Reference Receipt v0

Status:
- Receipt contract only; no real sensitive proof was recorded.
- Raw artifact/content storage: `false`.
- Access, approval, execution, browser, credential, OAuth, send, submit, and runtime authority: `false`.

## ELI5 Summary
- OpenClaw can record a safe reference saying protected proof exists for a workflow.
- The receipt stores IDs, hashes, dates, labels, and status, not passwords, raw PDFs, raw spreadsheets, bank details, or private bodies.
- The receipt is not a key; agents still cannot open the protected artifact.
- The receipt does not approve sends, browser actions, portal submits, spreadsheet writes, or runtime work.
- Guardian and security-threshold controls are still required before any sensitive artifact is opened or used.
- Future workflows can cite protected proof references without copying secrets or raw private content into normal read-models.

## Receipt Status Counts
- `REFERENCE_MISSING`: 7
- `REFERENCE_RECORDED`: 0
- `METADATA_INCOMPLETE`: 0
- `METADATA_VALID`: 0
- `METADATA_INVALID`: 0
- `RAW_CONTENT_REJECTED`: 0
- `PROTECTED_ACCESS_REQUIRED`: 0
- `UNKNOWN_FAIL_CLOSED`: 1

## Receipt Types
- `coupa_payment_invoice_proof_reference`: `REFERENCE_MISSING`; raw access granted: `false`.
- `excel_companion_artifact_reference`: `REFERENCE_MISSING`; raw access granted: `false`.
- `pdf_invoice_artifact_reference`: `REFERENCE_MISSING`; raw access granted: `false`.
- `gmail_email_evidence_reference`: `REFERENCE_MISSING`; raw access granted: `false`.
- `calendar_evidence_reference`: `REFERENCE_MISSING`; raw access granted: `false`.
- `bank_remit_home_check_image_sensitive_reference`: `REFERENCE_MISSING`; raw access granted: `false`.
- `client_credential_reference`: `REFERENCE_MISSING`; raw access granted: `false`.
- `unknown_sensitive_surface_reference`: `UNKNOWN_FAIL_CLOSED`; raw access granted: `false`.

## Forbidden Raw Content Fields
- `raw_pdf_body`
- `raw_pdf_contents`
- `pdf_body`
- `pdf_contents`
- `raw_excel_body`
- `raw_excel_contents`
- `excel_body`
- `excel_contents`
- `raw_document_body`
- `raw_private_document`
- `raw_artifact_contents`
- `artifact_body`
- `raw_email_body`
- `raw_gmail_body`
- `raw_calendar_body`
- `portal_username`
- `portal_password`
- `password`
- `token`
- `oauth_token`
- `refresh_token`
- `api_key`
- `secret`
- `credential`
- `credentials`
- `bank_details`
- `bank_account`
- `routing_number`
- `remit_details`
- `home_address`
- `check_image`
- `check_image_bytes`
- `browser_session_cookie`

## Boundary
- A protected reference receipt is not proof that the underlying artifact is true.
- A protected reference receipt is not permission to open the artifact.
- Guardian/security-threshold gates remain required before access or use.

Next safe lane: Guardian Protected Access Gate Spec v0
