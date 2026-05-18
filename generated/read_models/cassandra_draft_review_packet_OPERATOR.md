# Cassandra Draft Review Packet v0

Status:
- Workflow: `Capital Hilton companion invoice email`.
- Draft status: `proposed_review_packet_not_gmail_draft`.
- Final send gate: `unavailable_missing_coupa_invoice_proof`.
- Gmail draft created: `false`.
- Email sent: `false`.
- Live account accessed: `false`.

## Operator Meaning
- Cassandra can prepare a review-only companion invoice email packet for Capital Hilton.
- This packet is not a Gmail draft, not a send, and not an approval receipt.

## Draft Preview
- Subject: Review only: Capital Hilton companion invoice (unavailable_missing_coupa_invoice_proof)
- Body summary: Review-only companion invoice email packet. Final send remains blocked until governed proof and specific draft/attachment approval requirements are satisfied.
- Recipients are role labels only; no raw private contact expansion happened.

## Required Proof Before Final Send
- Coupa supplier-portal payment invoice proof: present_now=`false`; status=`pending_not_recorded`.
- Excel companion invoice protected artifact/reference: present_now=`false`; status=`pending_not_recorded`.
- Excel companion invoice matches Coupa/payment invoice proof: present_now=`false`; status=`pending_not_recorded`.

## Blockers
- Missing governed Coupa supplier-portal payment invoice proof. (`missing_coupa_payment_invoice_proof`).
- Missing governed Excel companion invoice protected artifact/reference. (`missing_excel_companion_invoice_artifact`).
- Missing governed Excel companion invoice matches Coupa/payment invoice proof. (`missing_excel_coupa_match_proof`).
- missing email draft (`missing_email_draft`).
- missing attachment reference (`missing_attachment_reference`).
- missing draft identity hash reference (`missing_draft_identity_hash_reference`).
- missing attachment identity hash reference (`missing_attachment_identity_hash_reference`).
- unresolved critical blockers (`unresolved_critical_blockers`).

## Authority Boundary
- No Gmail draft creation, email send, live Gmail read, OAuth, browser automation, PDF attachment, spreadsheet mutation, or runtime authority was added.
- Future approval must be specific to one draft, one attachment, and one workflow scope.

## Next Safe Move
- Review the packet only; record Coupa proof and Excel match proof through governed evidence rails before any final-send approval lane.
