# Capital Hilton External Artifact Proof Capture

Status:
- Coupa invoice proof: `pending_not_recorded`.
- Excel companion invoice artifact: `pending_not_recorded`.
- Excel-vs-Coupa match proof: `pending_not_recorded`.
- Final send approval availability: `unavailable_missing_coupa_invoice_proof`.
- Raw sensitive artifacts stored in read-model: `false`.
- Coupa/browser/email/spreadsheet/credential/runtime authority added: `false`.

## Operator Proof Intake
- Command path: `scripts/export_capital_hilton_external_artifact_proof_capture.py --proof-input-json <path>`.
- Proof input supplied: `false`.
- Supplied proof count: `0`.
- Recorded real proof count: `0`.
- Intake accepts protected references and metadata only; raw artifact bodies are not allowed.

## Proof Records
- `coupa_payment_invoice_proof`: pending_not_recorded (operator supplied: `false`)
- `excel_companion_invoice_artifact`: pending_not_recorded (operator supplied: `false`)
- `excel_coupa_match_proof`: pending_not_recorded (operator supplied: `false`)

## Final Send Approval Prerequisites
- `coupa_invoice_proof_exists`: `false`
- `coupa_invoice_proof_references_expected_po_invoice_context`: `false`
- `excel_companion_invoice_artifact_exists`: `false`
- `excel_companion_invoice_verified_to_match_coupa`: `false`
- `cassandra_email_draft_exists`: `false`
- `attachment_reference_exists`: `false`
- `draft_identity_hash_reference_exists`: `false`
- `attachment_identity_hash_reference_exists`: `false`
- `no_unresolved_critical_blockers`: `false`
- `guardian_start_approval_recorded_or_required_upstream`: `true`

## Boundary
- Evidence only; no external action was taken.
- No raw Coupa PDFs, Excel files, credentials, bank details, portal passwords, token material, or check images are stored in normal read-models.
- Final send approval stays blocked until Coupa proof, Excel artifact, Excel-vs-Coupa match proof, draft identity, attachment identity, and blocker clearance exist.

Next safe lane: Capital Hilton Proof Capture Operator Surface v0
