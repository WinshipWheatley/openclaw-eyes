# Capital Hilton Coupa Execution Path Contract

Status:
- End-to-end Hilton workflow modeled: `true`.
- Execution enabled now: `false`.
- Coupa submit enabled: `false`.
- Email send enabled: `false`.
- Spreadsheet write enabled: `false`.
- Runtime authority added: `false`.

## Scope
- Base workflow: A normal client invoice may use a single operator invoice artifact as payment-generating unless a client-specific portal, PO, or payment rule requires an overlay.
- Hilton overlay: `hilton_coupa_supplier_portal`.
- Overlay scope: Capital Hilton / Hilton only.
- This two-invoice/two-approval/Coupa portal process is not generalized to all clients.
- Future client-specific complexity should be added as overlays/adapters using the same gates, proof, and protected-evidence substrate.

## Phases
- `requested_from_operator_channel`: future_supported_intake_shape_modeled (Cassandra)
- `governed_intent_routed`: modeled_not_executing (workflow_router)
- `guardian_start_approval_required`: required_before_workflow_start (Guardian)
- `start_approval_recorded`: not_recorded_for_execution (Guardian)
- `facts_verified`: pending_evidence_review (workflow_router)
- `credential_access_required`: future_blocked (protected_secret_pii_broker)
- `local_browser_execution_required`: future_blocked (local_mac_execution_agent)
- `coupa_invoice_creation_pending`: blocked (local_mac_execution_agent)
- `coupa_invoice_proof_capture_pending`: blocked (local_mac_execution_agent)
- `excel_companion_invoice_update_pending`: blocked (local_mac_execution_agent)
- `invoice_match_verification_required`: required_before_send_approval (workflow_router)
- `outward_email_draft_pending`: draft_only_future (Cassandra)
- `guardian_send_approval_required`: blocked_until_artifact_proofs_exist (Guardian)
- `outward_email_send_blocked_until_gate`: blocked (Clara/Cassandra)
- `expected_payment_tracking_pending`: future_pending (money_ledger)
- `money_ledger_payment_verification_pending`: required_for_paid_status (money_ledger)

## Required Gates
- `operator_intent_gate`: Cassandra/governed intake must capture a bounded operator intent.
- `guardian_start_approval_gate`: Guardian must approve starting this Capital Hilton workflow.
- `invoice_fact_readiness_gate`: Required facts, PO posture, and manual confirmations must be reviewed.
- `credential_pii_access_gate`: Protected values must be inserted only through a future local broker.
- `browser_automation_scope_gate`: Browser automation must be scoped to the approved Coupa task.
- `coupa_submit_gate`: Coupa submit is separate from browser navigation and must be explicitly gated.
- `coupa_invoice_proof_capture_gate`: Coupa invoice proof/download must be captured as protected evidence.
- `excel_write_generation_gate`: Excel companion generation/write must be explicitly gated.
- `coupa_vs_excel_invoice_match_gate`: Excel companion invoice must reflect/match the Coupa payment invoice.
- `email_draft_gate`: Cassandra may only produce a draft record, not send.
- `guardian_send_approval_gate`: Guardian must approve the specific draft and attachment.
- `email_send_gate`: Email send remains blocked until specific Guardian send approval.
- `payment_verification_gate`: Paid status requires money-ledger verification.

## Guardian Approvals
- `start_workflow_approval`: Authorize beginning the Capital Hilton invoice workflow after governed operator intent. General send authority: `false`.
- `send_email_with_invoice_approval`: Authorize only Cassandra's specific drafted email and specified Excel invoice attachment. General send authority: `false`.

## Send Approval Blockers
- Coupa invoice proof must exist in SQLite/read-model evidence.
- Excel companion invoice must be verified to reflect/match the Coupa invoice.
- Approval can only cover one specific draft email and attachment.

## Protected Data
- Protected broker is modeled for a future lane, but inactive now.
- Raw secrets, remit PII, bank data, token material, and check/deposit images are not stored in normal read-models.

## Not Enabled
- No Coupa automation, Coupa submit, email send, spreadsheet write, credential insertion, Telegram command execution, or runtime authority.

Next safe lane: Capital Hilton Coupa Start Approval Packet Spec v0
