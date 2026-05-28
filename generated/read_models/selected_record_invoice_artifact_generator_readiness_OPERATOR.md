# Selected-Record Invoice Artifact Generator Readiness

Ready: `false`
Safe to generate now: `false`

OpenClaw needs source workbook linkage and generation authority before creating the selected invoice artifact.

## Missing Inputs

- `source_workbook_ref`
- `source_workbook_pc_or_mac_path`
- `source_workbook_reference_confirmed_receipt`
- `selected_record_invoice_artifact_generation_authority_receipt`
- `approved_generation_inputs`

## Existing Generator Audit

- `invoice_artifact_builder`: selected-record-safe=`false`; Does not accept source_workbook_ref, invoice_period_label, invoice_record_label, selected-record receipt, or generation authority receipt.
- `capital_hilton_invoice_artifact_generator`: selected-record-safe=`false`; Preview rail is not a current Excel/PDF invoice artifact generator and does not bind a selected workbook page/record.
