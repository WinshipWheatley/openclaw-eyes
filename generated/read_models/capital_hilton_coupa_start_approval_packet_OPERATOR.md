# Capital Hilton Coupa Start Approval Packet

Status:
- Start approval packet modeled: `true`.
- Packet executable now: `false`.
- Guardian message sent: `false`.
- Coupa/browser/email/spreadsheet/credential/runtime authority added: `false`.

## Approval Scope
- Approval type: `start_workflow_approval`.
- Workflow: `capital_hilton_coupa_supplier_portal_invoice`.
- Scope: Capital Hilton / Hilton only.

Authorizes:
- begin governed workflow preparation
- verify current Capital Hilton facts/read-models
- prepare readiness packets for later explicitly gated steps

Does not authorize:
- Coupa submit
- browser automation
- credential/PII access
- Excel or spreadsheet write
- email send
- payment status change
- Guardian send approval
- final external communication
- general runtime authority

## Downstream Gates Still Required
- `credential_pii_access_gate`: Protected local mechanism must approve scoped credential/remit PII insertion.
- `browser_automation_scope_gate`: Mac-local browser automation must be scoped and separately approved.
- `coupa_submit_gate`: Coupa submit is a separate gate from browser navigation.
- `coupa_invoice_proof_capture_gate`: Coupa invoice proof/download must be captured as protected evidence.
- `excel_companion_invoice_generation_match_gate`: Excel companion artifact must be generated/updated and matched to Coupa proof.
- `guardian_send_approval_gate`: Guardian send approval must bind one specific draft email and attachment.
- `money_ledger_payment_verification_gate`: Paid status requires money-ledger payment verification.

## Later Send Approval Compatibility
- Existing Cassandra draft + Guardian approval machinery was inspected statically.
- Later send approval should reuse or detangle existing draft/Guardian patterns rather than rebuild them.
- Start approval remains separate from send approval.

## Boundary
- No Guardian/Telegram/Gmail/email message was sent.
- No Coupa browser automation or submit was enabled.
- No spreadsheet write, credential/PII access, raw secret storage, runtime authority, or send authority was added.

Next safe lane: Capital Hilton Coupa Start Approval Operator Surface v0
