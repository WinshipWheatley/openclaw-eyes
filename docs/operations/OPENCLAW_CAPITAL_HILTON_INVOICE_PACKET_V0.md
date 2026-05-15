# OpenClaw Capital Hilton Invoice Packet v0

Capital Hilton Invoice Packet v0 is a governed finance packet for preparing the operator to invoice two Capital Hilton / Capitol Hilton gigs. It is review-only: it prepares missing facts, draft context, portal-fill instructions, and receivable tracking posture without sending, submitting, logging into portals, accessing banks, writing ledgers, or reading spreadsheet cells.

## What It Creates

- Finance packet id: `finance_capital_hilton_invoice_packet_v0`
- Draft email artifact for operator review only
- Codex Desktop Mac/Safari portal-fill prompt with no-submit boundaries
- Receivable tracking proposal with `status=pending_invoice_approval`
- Metadata-only Work Board cards for missing facts, portal prompt review, and receivable tracking
- Finance evidence packet read-model output through `finance_invoice_evidence_packets`

## Known Operator Context

- Client/location: Capital Hilton / Capitol Hilton
- Finance/AP contact likely: Annette Sunga
- Possible contacts: Chyna Hardin and Lawrence / Will Valcovic
- Supplier portal context: SmartSpend / Coupa related
- Remit email context: `winshiplive@gmail.com`
- Gigs: tonight's gig and last Friday's gig

All of this remains operator-supplied context or needs-review context. No final financial truth is claimed.

## Missing Required Facts

- Exact date for tonight's gig
- Exact date for last Friday's gig
- Amount/rate per gig
- Whether this should be one invoice or two
- PO number(s)
- Billing/remit details
- Recipient/CC decision
- Supplier portal reference
- Invoice attachment/output path

## Mac Spreadsheet Posture

The operator reports a likely spreadsheet under `~/Documents/invoices/`. This lane does not access the Mac folder, copy the spreadsheet, parse workbook cells, or claim facts from it.

The next safe lane is `Mac Finance Spreadsheet Evidence Intake v0`, which should begin with Mac-side metadata only and require operator approval before any sheet names, rows, cells, or workbook content are inspected.

## Command

```bash
python3 scripts/build_capital_hilton_invoice_packet.py --format operator
```

## Generated Artifacts

Default folder:

```text
generated/finance_packets/capital_hilton_invoice_packet_v0/
```

Files:

- `CAPITAL_HILTON_DRAFT_EMAIL_REVIEW_ONLY.md`
- `CAPITAL_HILTON_PORTAL_FILL_PROMPT_NO_SUBMIT.md`
- `CAPITAL_HILTON_RECEIVABLE_TRACKING_PROPOSAL.md`
- `CAPITAL_HILTON_PACKET_SUMMARY.md`
- `MANIFEST.json`

## Authority Boundary

- `email_send_allowed=false`
- `invoice_send_allowed=false`
- `supplier_portal_login_allowed=false`
- `browser_automation_allowed=false`
- `bank_access_allowed=false`
- `ledger_write_allowed=false`
- `external_api_allowed=false`
- `spreadsheet_cell_read_allowed=false`
- `financial_truth_claimed=false`
- `operator_approval_required=true`
