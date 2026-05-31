# Live Arts MD Invoice Automation

Status: PARTIAL

## Short human summary
Live Arts MD has selected-invoice and manual-send metadata, but source evidence keeps proof, attachment readiness, payment watch, and ledger state gated.

## Confirmed facts
- Selected invoice candidate: 2026-1001 / Speaker Rental / $900 / sheet June 2026 Speaker Rental / selection OPERATOR_CONFIRMED.
- Selected invoice state: sent=false, paid=false, submitted=false, ledger_posted=false, receipt_status=UNPAID.
- Manual send metadata exists for invoice 2026-1001 at 2026-05-28T14:32:00-04:00; proof_status=MANUAL_SEND_PROOF_PENDING; file_backed_proof=false; receipt_received=false.
- Payment watch: READINESS_ONLY_NOT_ACTIVE; ledger_match_status=NOT_ATTEMPTED; bank read performed=false.
- PDF export package status: PDF_EXPORT_PACKAGE_READY_FOR_MAC; request_payload_ready=true; execution_venue=MAC_LOCAL; required_capability=MAC_EXCEL_PDF_EXPORT.
- PDF output refs: Mac=scoped_live_arts_md_export/June_2026_Speaker_Rental/2026-1001.pdf; PC=/mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md/2026-1001/Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental.pdf; source workbook=/Users/hwinshipwheatle...
- Invoice artifact: review_status=NOT_READY; attachment_ready=false; trusted selected artifact present=false.

## Known unknowns
- Manual send proof missing field: proof screenshot/ref
- Blocker: Prepare invoice PDF
- Blocker: Confirm the Live Arts MD recipient/contact.
- Blocker: Guardian approval request is required before send approval.
- Blocker: Approval/send remains disabled until receipts exist.

## Tension / contradiction signals
- Workflow readiness conflicts with attachment or approval: live_arts_md_bundle says ready but attachment_ready or approval_ready is false/missing.
- PDF export package missing required fields: live_arts_md_bundle.developer_end_to_end_card is PDF export ready but missing: invoice_id, selected_sheet_label, output_bridge_path.
- Artifact placeholder is not selected-invoice proof: /mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md_invoice_2026-1001.pdf is marked INVALID_PLACEHOLDER and not trusted as selected invoice artifact.
- Artifact placeholder is not selected-invoice proof: /Users/hwinshipwheatley/Desktop/Live_Arts_MD_Speaker_Rental_Invoice_September_May_2026.pdf is marked NOT_TRUSTED_EXISTING_MULTI_PAGE_PDF and not trusted as selected invoice artifact.

## Next useful actions
- Capture sent-email screenshot or sent-mail proof for invoice 2026-1001.
- Confirm recipient/contact evidence before claiming send readiness.
- Use the Mac Excel PDF edge path only as a scoped export package with operator review after export.
- Keep payment watch readiness-only until send/manual proof exists.

## What not to do
- Do not claim OpenClaw sent the invoice.
- Do not claim file-backed manual-send proof exists while file_backed_proof=false.
- Do not claim PDF export completed just because a Mac package is ready.
- Do not mark paid, submitted, ledger-posted, or attachment-ready without receipts.
- Do not add Coupa/PO blockers to Live Arts unless a source read-model says the client requires them.

## Source refs / input read-model refs
- generated/read_models/live_arts_md_invoice_review_bundle.json (live_arts_md_invoice_review_bundle)
- generated/read_models/hermes_mission_sentinel.json (hermes_mission_sentinel)
- generated/read_models/hermes_chief_build_handoff.json (hermes_chief_build_handoff)

Last generated timestamp: 2026-05-31T03:40:20+00:00

Generated understanding view. Registry/read-models/receipts remain source of truth.
