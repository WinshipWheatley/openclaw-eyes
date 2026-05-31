# Capital Hilton Invoice Workflow

Status: BLOCKED

## Short human summary
Capital Hilton remains a complex, proof-gated invoice workflow: Coupa/supplier portal proof, selected invoice/page evidence, artifact linkage, recipients, and approvals are not complete.

## Confirmed facts
- Bundle id: invoice_review_bundle:capital_hilton:v0; client_ref=capital_hilton.
- Approval ready: False; disabled reasons: ['Coupa proof missing', 'Invoice record/page not selected', 'Generated artifact not linked', 'Recipients unconfirmed', 'Attachment not ready'].
- Supplier portal proof: provider=COUPA; required=True; status=MISSING.
- Excel invoice artifact: Capital Hilton Excel invoice candidate; attachment_ready=False; proof_status=GENERATION_AUTHORITY_REQUIRED; linkage_status=GENERATION_AUTHORITY_REQUIRED.
- Artifact refs: Mac=/Volumes/openclaw_e/generated/invoice_artifacts/capital_hilton_invoice_artifact_v0/WINSHIP_CAPITAL_HILTON_INVOICE_2026-05-25.xlsx; PC=/mnt/e/openclaw/generated/invoice_artifacts/capital_hilton_invoice_artifact_v0/WINSHIP_CAPITAL_HILTON_IN...
- Invoice selection: active_workbook_state=BLOCKED_NEEDS_INVOICE_RECORD_SELECTION; operator_approval=None; portal execution=None.

## Known unknowns
- Blocker: Generation/export authority is required before creating the selected invoice artifact.
- Blocker: Coupa submission proof is still required.
- Blocker: Which invoice page/period should OpenClaw prepare for Capital Hilton?
- Blocker: OpenClaw needs the current invoice page/period before it can attach the Excel invoice.
- Blocker: Generated invoice artifact needs proof linking it to the selected invoice record.
- Blocker: Recipient list needs confirmation.
- Blocker: Send is blocked until approval and send execution receipts exist.

## Tension / contradiction signals
- Workflow readiness conflicts with attachment or approval: live_arts_md_bundle says ready but attachment_ready or approval_ready is false/missing.
- PDF export package missing required fields: live_arts_md_bundle.developer_end_to_end_card is PDF export ready but missing: invoice_id, selected_sheet_label, output_bridge_path.
- Artifact placeholder is not selected-invoice proof: /mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md_invoice_2026-1001.pdf is marked INVALID_PLACEHOLDER and not trusted as selected invoice artifact.
- Artifact placeholder is not selected-invoice proof: /Users/hwinshipwheatley/Desktop/Live_Arts_MD_Speaker_Rental_Invoice_September_May_2026.pdf is marked NOT_TRUSTED_EXISTING_MULTI_PAGE_PDF and not trusted as selected invoice artifact.

## Next useful actions
- Select or confirm the current invoice page/period before treating the artifact as current.
- Capture supplier portal/Coupa proof as proof intake only; no portal submission authority is granted here.
- Link or regenerate artifact evidence only through metadata/proof receipts.
- Keep approval blocked until prerequisite receipts exist.

## What not to do
- Do not claim Coupa submitted or supplier portal proof exists while proof status is missing/requested.
- Do not treat the candidate Excel artifact as attachment-ready without linkage receipts.
- Do not send email or mark approval based on draft text.
- Do not read workbook cells or mutate the workbook from this wiki layer.

## Source refs / input read-model refs
- generated/read_models/invoice_review_bundle.json (invoice_review_bundle)

Last generated timestamp: 2026-05-31T04:32:51+00:00

Generated understanding view. Registry/read-models/receipts remain source of truth.
