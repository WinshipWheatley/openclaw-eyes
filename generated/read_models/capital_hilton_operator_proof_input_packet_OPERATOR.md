# Capital Hilton Operator Proof Input Packet

Status:
- Template only; no real proof was recorded.
- Intake command: `python3 scripts/export_capital_hilton_external_artifact_proof_capture.py --proof-input-json <path>`.
- Coupa proof: `pending_not_recorded`.
- Excel companion artifact: `pending_not_recorded`.
- Excel-vs-Coupa match proof: `pending_not_recorded`.
- Final send approval availability: `unavailable_missing_coupa_invoice_proof`.

## What To Provide Later
- `coupa_payment_invoice_proof` metadata/protected reference fields only.
- `excel_companion_invoice_artifact` metadata/protected reference fields only.
- `excel_coupa_match_proof` metadata/protected reference fields only.

## Safe Input Rules
- Provide metadata and protected/local-only artifact references only.
- Do not paste raw PDF contents, Excel file contents, portal screenshots, or copied private document bodies.
- Do not paste passwords, tokens, portal credentials, bank details, check images, or full home addresses.
- Keep raw files in protected/local-only storage outside normal generated read-models.
- Use null for unknown values.
- Use false only for explicit negative confirmations, not for unknowns.
- Proof must be operator-supplied or safely metadata-derived.
- Synthetic examples are examples only and must not be treated as real proof.

## Examples Included
- `empty_pending_template`: safe starting shape with null unknowns.
- `partial_coupa_proof_only_example`: example only, not recorded as proof.
- `full_synthetic_test_metadata_example`: synthetic/test example only, not real proof.

## Boundary
- No Coupa submit, browser automation, email send, spreadsheet write, credential access, runtime authority, send authority, or approval authority was added.
- No raw PDFs, Excel files, screenshots, passwords, tokens, bank details, home addresses, or check images are included.

Next safe lane: Capital Hilton Manual Proof Metadata Capture v0
