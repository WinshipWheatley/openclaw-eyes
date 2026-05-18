# Capital Hilton Send Approval Gate

Status:
- Send approval packet modeled: `true`.
- Current availability: `unavailable_missing_coupa_invoice_proof`.
- Proof evidence rail: `blocked_waiting_for_governed_proof`.
- Packet executable now: `false`.
- Guardian message sent: `false`.
- Email/Coupa/browser/spreadsheet/credential/runtime authority added: `false`.

## Approval Target
- Approval type: `send_email_with_invoice_approval`.
- Workflow: `capital_hilton_coupa_supplier_portal_invoice`.
- Target action: send one specific drafted email with one specific Excel companion invoice PDF attachment.
- Scope: exact draft plus exact attachment only; no general email authority.

## Required Before Send Approval Can Be Requested
- `coupa_invoice_proof_exists`: missing - Coupa supplier-portal invoice proof exists in SQLite/read-model evidence.
- `coupa_invoice_proof_references_expected_po_invoice_context`: missing - Coupa proof references the expected PO and invoice context.
- `excel_companion_invoice_artifact_exists`: missing - Excel companion invoice artifact exists.
- `excel_companion_invoice_verified_to_match_coupa`: missing - Excel companion invoice is verified to reflect/match Coupa invoice.
- `cassandra_email_draft_exists`: missing - Cassandra outward email draft exists as a draft record.
- `attachment_reference_exists`: missing - Excel PDF attachment reference exists.
- `draft_identity_hash_reference_exists`: missing - Draft identity/hash/reference exists.
- `attachment_identity_hash_reference_exists`: missing - Attachment identity/hash/reference exists.
- `no_unresolved_critical_blockers`: missing - No unresolved critical blockers remain.
- `guardian_start_approval_recorded_or_required_upstream`: present - Guardian start approval is recorded or modeled as required upstream.

## Proof Evidence Rail
- Coupa supplier-portal payment invoice proof: `pending_not_recorded`; final-send unlock proof: `true`.
- Excel companion invoice match proof: `pending_not_recorded`; final-send unlock proof: `true`.

## If Later Approved, It Would Authorize
- send the specific Cassandra-drafted email
- include the specific Excel-generated PDF invoice attachment
- record a send receipt afterward in a future execution lane

## Still Blocked
- Coupa submit
- browser automation
- credential/PII access
- spreadsheet writes
- new invoice creation
- payment status change
- general email authority
- general runtime authority
- future sends

## Reuse / Detangle
- Existing Cassandra draft + Guardian approval machinery was inspected statically.
- Later implementation should reuse or detangle existing machinery rather than rebuild it.
- This lane did not activate draft, Guardian transport, or send paths.

## Future Checklist
- `protected_coupa_invoice_proof`: protected evidence for Coupa invoice proof
- `excel_companion_artifact`: Excel companion invoice artifact and protected/reference path
- `excel_match_proof`: Coupa-vs-Excel match proof
- `cassandra_draft_record`: Cassandra draft record with stable identity
- `attachment_reference`: Excel PDF attachment reference with stable identity
- `guardian_send_approval_delivery`: Guardian send approval request delivery path
- `operator_approval_receipt`: explicit operator approval receipt
- `stage_4_send_controls`: Operator Sovereignty Stage 4 controls before real send authority

## Boundary
- No Guardian/Telegram/Gmail/email message was sent.
- No email draft, PDF attachment, Coupa submit, browser automation, spreadsheet write, credential/PII access, or runtime authority was added.
- Real send remains blocked until future Stage 4 controls and exact operator approval receipts exist.

Next safe lane: Capital Hilton Send Approval Operator Surface v0
