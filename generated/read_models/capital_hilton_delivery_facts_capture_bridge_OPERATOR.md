# Capital Hilton Delivery Facts Capture Bridge v0

## ELIWINSHIP Summary

OpenClaw already has the four Capital Hilton performance dates, $400/show, and a $1,600 subtotal in local captured state. This rail asks the remaining safe delivery questions: what is the PO/Coupa posture, who is the AP/email route, and what protected proof reference backs that up.

It does not log into Coupa or Gmail, read private bodies, send email, submit approval, or handle credentials.

## Current Captured State

- Dates: `2026-05-08, 2026-05-15, 2026-05-22, 2026-05-29`
- Rate: `$400/show`
- Subtotal: `$1,600`
- Artifact/readiness ref: `capital_hilton_invoice_artifact_candidate_markdown_preview_four_show`

## Capture Blocks

- PO/Coupa block: `NEEDS_DISCOVERY`
- AP/email route block: `AP_EMAIL_CANDIDATE_NEEDS_CONFIRMATION`
- Protected evidence: metadata references only, not raw protected content.

## Candidate AP Route

- `Annette.Sunga@hilton.com` - CANDIDATE_NEEDS_OPERATOR_CONFIRMATION
- `Chyna.Hardin@hilton.com` - CANDIDATE_NEEDS_OPERATOR_CONFIRMATION
- `lawrencevalcovic@hilton.com` - CANDIDATE_NEEDS_OPERATOR_CONFIRMATION

## Still Blocked

- Invoice artifact/readiness status: GENERATED_LOCAL_PREVIEW
- PO/Coupa/payment reference posture unresolved
- AP/email route candidates require operator confirmation
- Protected evidence references must be metadata-only and may require Guardian review
- Email send and Coupa submit remain external gates

## Writer Posture

No delivery-fact receipt/state write happened in this lane. The next backend lane should add a narrow writer for PO/Coupa posture and AP/email route capture requests.

## Authority

- Coupa/browser access: `false`
- Gmail/email send: `false`
- Credential handling: `false`
- Model/tool/runtime: `false`
- Raw body ingestion: `false`

## Next Safe Move

Render delivery-fact capture blocks; capture operator-confirmed facts later through a narrow writer.
