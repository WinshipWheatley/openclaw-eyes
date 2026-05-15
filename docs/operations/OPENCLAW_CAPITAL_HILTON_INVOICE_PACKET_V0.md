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

The Mac metadata-first lane can attach spreadsheet metadata from:

```text
/mnt/e/openclaw/shuttle/from_mac/finance_invoice_spreadsheet_metadata.json
```

Current selected candidate, when ingested:

```text
Invoice Capitol Hilton 20260512 v2.xlsx
```

The alternate candidate is:

```text
Invoice Capitol Hilton 20260512.xlsx
```

This remains `sensitive_metadata_only`. OpenClaw may store filename, path, size, and timestamps from the Mac metadata packet, but it must not read cells, parse sheets, copy, upload, or infer dates/amounts/PO numbers from the workbook.

The next safe lane is `Mac Finance Spreadsheet Evidence Intake v0`, which should begin with Mac-side metadata only and require operator approval before any sheet names, rows, cells, or workbook content are inspected.

## Cassandra / Clara Reid Fact Intake

Internal agent name: `cassandra`.

External finance/AP persona: `Clara Reid`.

External-facing draft email artifacts must not mention Cassandra and should sign:

```text
Best,
Clara Reid
```

If live Cassandra/Telegram intake is blocked, use the governed CLI fallback. It stores facts in SQLite packet tables and can also store a bounded synthetic Cassandra intake record when requested. It does not send Telegram messages.

```bash
python3 scripts/ingest_finance_spreadsheet_metadata.py --format operator

python3 scripts/ingest_capital_hilton_invoice_facts.py \
  --spreadsheet-selection "Invoice Capitol Hilton 20260512 v2.xlsx" \
  --format operator
```

Later, when the operator supplies concrete facts:

```bash
python3 scripts/ingest_capital_hilton_invoice_facts.py \
  --source-kind telegram_cassandra \
  --tonight-gig-date "YYYY-MM-DD" \
  --last-friday-gig-date "YYYY-MM-DD" \
  --rate-or-amount-per-gig "..." \
  --invoice-count-preference "one combined invoice|two invoices" \
  --po-numbers "..." \
  --recipient-decision "..." \
  --supplier-portal-reference "..." \
  --format operator
```

This is governed intake only. It does not create an executable action, approve anything, send email, or submit a portal form.

## Contact Candidates

The packet can store these as contact candidates only:

- Annette Sunga, Finance/AP contact, email unknown, needs review.
- Chyna Hardin, Director of Finance, `Chyna.Hardin@hilton.com`, CC candidate pending review.
- Lawrence / Will Valcovic, `lawrencevalcovic@hilton.com`, CC candidate pending review.

Annette’s email remains a missing item if she is selected as the To recipient.

## Command

```bash
python3 scripts/build_capital_hilton_invoice_packet.py --format operator
```

Metadata/fact intake commands:

```bash
python3 scripts/ingest_finance_spreadsheet_metadata.py --format operator
python3 scripts/ingest_capital_hilton_invoice_facts.py --report --format operator
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
