# Guardian Draft Approval Request Contract v0

Status:
- Workflow: `Capital Hilton companion invoice email`.
- Approval request available now: `false`.
- Current status: `blocked_unavailable_missing_prerequisites`.
- Approval request created: `false`.
- Approval receipt created: `false`.
- Guardian/Telegram notification sent: `false`.
- Gmail draft/email send/execution enabled: `false`.

## Draft Packet
- Draft packet: `cass_draft_review_c5e93dfda6dfa1c06686`.
- Draft status: `proposed_review_packet_not_gmail_draft`.
- Scope: one specific Cassandra draft plus one specific Excel companion invoice attachment.

## Required Proof
- `coupa_invoice_proof_exists`: missing - Coupa supplier-portal payment invoice proof exists.
- `coupa_invoice_proof_references_expected_po_invoice_context`: missing - Coupa proof references expected PO/invoice context.
- `excel_companion_invoice_artifact_exists`: missing - Excel companion invoice artifact/reference exists.
- `excel_companion_invoice_verified_to_match_coupa`: missing - Excel companion invoice is verified to reflect/match Coupa invoice.

## Required Draft / Attachment Identity
- `cassandra_email_draft_exists`: missing - Cassandra draft review packet has a specific draft record.
- `attachment_reference_exists`: missing - Excel companion invoice PDF attachment reference exists.
- `draft_identity_hash_reference_exists`: missing - Draft identity/hash/reference exists.
- `attachment_identity_hash_reference_exists`: missing - Attachment identity/hash/reference exists.

## Blockers
- `missing_coupa_invoice_proof`: missing coupa invoice proof
- `missing_coupa_expected_po_invoice_context_reference`: missing coupa expected po invoice context reference
- `missing_excel_companion_invoice`: missing excel companion invoice
- `missing_excel_match_proof`: missing excel match proof
- `missing_email_draft`: missing email draft
- `missing_attachment_reference`: missing attachment reference
- `missing_draft_identity_hash_reference`: missing draft identity hash reference
- `missing_attachment_identity_hash_reference`: missing attachment identity hash reference
- `unresolved_critical_blockers`: unresolved critical blockers

## Guardian Contract Boundary
- Start approval and final-send approval are distinct.
- Review packet, approval request, approval receipt, and execution remain distinct.
- Payload hash, TTL, idempotency, exact draft identity, and exact attachment identity are required.
- No generic approval, send, runtime, Coupa, browser, credential, spreadsheet, OAuth, or calendar authority is granted.

## Next Safe Move
- Record Coupa payment-invoice proof, Excel companion artifact reference, and Excel-Coupa match proof through governed metadata/protected-reference rails before any Guardian final-send approval request lane.
