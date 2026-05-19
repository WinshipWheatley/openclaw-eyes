# Protected Access Broker Concept Delta v0

Status:
- Preconditions satisfied: `true`.
- Current posture: metadata/protected-reference readiness only.
- Live credential/OAuth/browser/account access: `blocked`.
- Agents receive direct credentials: `false`.

## ELI5 Summary
- What protected access means: OpenClaw may remember that a sensitive thing exists and what proof is needed, but it does not get the secret, raw document, account, or browser power yet.
- What OpenClaw can safely track now: Metadata, protected reference IDs, hashes, dates, amounts, PO references, match status, blockers, and approval requirements.
- What must stay out of normal read-models: Passwords, tokens, OAuth secrets, bank/remit details, home address, check images, raw PDFs, raw Excel files, and private message bodies.
- What remains blocked until security threshold: Credential use, OAuth, Gmail/calendar/Coupa access, browser automation, spreadsheet mutation, sends, submits, and agent-held secrets.
- Why this protects before real workflows: It lets the system plan and prove readiness without handing dangerous material to agents or pretending live authority exists.

## Protected Access Surfaces
- `capital_hilton_coupa_payment_invoice_proof`: PROTECTED_REFERENCE_ALLOWED (live_coupa_access_blocked)
- `capital_hilton_excel_pdf_invoice_artifacts`: PROTECTED_REFERENCE_ALLOWED (spreadsheet_or_attachment_generation_blocked)
- `gmail_email_send_or_draft`: LIVE_ACCESS_BLOCKED (gmail_draft_send_access_blocked)
- `calendar_access`: LIVE_ACCESS_BLOCKED (calendar_live_access_blocked)
- `bank_remit_home_address_check_images`: NORMAL_READ_MODEL_FORBIDDEN (raw_finance_private_data_blocked)
- `client_company_credentials`: NORMAL_READ_MODEL_FORBIDDEN (credential_access_blocked)
- `browser_automation`: REQUIRES_SECURITY_THRESHOLD (browser_automation_blocked)
- `oauth_tool_bridges`: UNSAFE_OR_BLOCKED (oauth_tool_bridge_blocked)
- `unknown_sensitive_surface`: UNKNOWN_FAIL_CLOSED (blocked_fail_closed)

## Safe Metadata / Protected References
- `protected_artifact_reference`
- `protected_reference_id`
- `protected_reference_path_token`
- `artifact_identity_or_hash`
- `proof_type`
- `proof_status`
- `source_system_label`
- `captured_at`
- `date_captured`
- `invoice_number`
- `portal_invoice_reference`
- `po_reference`
- `amount`
- `service_dates`
- `operator_confirmation_status`
- `match_status`
- `mismatch_reasons`
- `redaction_status`
- `protection_status`

## Never Store Raw In Normal Read-Models
- raw passwords
- raw OAuth client secrets or refresh tokens
- raw bot/API tokens
- portal usernames paired with secrets
- bank account or routing details
- remit details
- home address
- check images or deposit images
- raw PDF bodies
- raw Excel workbook bodies
- raw Gmail/calendar bodies
- private legal/client documents
- client/company credentials

## Future Broker Must Prove
- local-only protected storage or handoff mechanism
- operator-approved exact task scope
- Guardian gate for sensitive/live access
- field-level minimization and redaction
- no raw secret/PII leakage into normal read-model tests
- scoped access receipt without revealing sensitive values
- revocation/abort behavior
- tamper/hard-stop controls before Stage 4 execution

## Boundaries
- No credentials, OAuth, Gmail/calendar/Coupa/browser access, sends, submits, approval receipts, execution, Repo B execution, Mission Control changes, or client deployment were added.
- Protected references are not permission to open protected artifacts.
- Unknown sensitive access fails closed.

Next safe lane: Protected Evidence Reference Receipt v0
