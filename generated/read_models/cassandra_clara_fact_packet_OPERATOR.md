# Cassandra/Clara Fact Packet v0

Target workflow: `capital_hilton_invoice`
Packet kind: `capital_hilton_missing_facts_packet`
Usable Capital Hilton review packet: `false`
Governed facts found: `13`
Contact candidates found: `3`
Missing required facts: `9`

## Artifacts
- `missing_facts`: `generated/finance_packets/cassandra_clara_fact_packet_v0/CAPITAL_HILTON_MISSING_FACTS_PACKET.md`
- `contact_review`: `generated/finance_packets/cassandra_clara_fact_packet_v0/CAPITAL_HILTON_CONTACT_REVIEW.md`
- `draft_email`: `generated/finance_packets/cassandra_clara_fact_packet_v0/CAPITAL_HILTON_CLARA_DRAFT_EMAIL_REVIEW_ONLY.md`
- `receivable_review`: `generated/finance_packets/cassandra_clara_fact_packet_v0/CAPITAL_HILTON_RECEIVABLE_REVIEW.md`
- `manifest`: `generated/finance_packets/cassandra_clara_fact_packet_v0/MANIFEST.json`

## Missing Required Facts
- `tonight_gig_date`: Exact service date for tonight's gig
- `last_friday_gig_date`: Exact service date for last Friday's gig
- `rate_or_amount_per_gig`: Rate or amount per gig
- `invoice_count_preference`: One invoice or two invoices
- `po_numbers`: PO number(s) or explicit none
- `billing_remit_details`: Billing/remit details
- `recipient_decision`: To/CC recipient decision
- `supplier_portal_reference`: Supplier portal reference
- `invoice_attachment_output_path`: Invoice attachment/output path

## Boundaries
- No send authority.
- No runtime authority.
- No raw private files, logs, messages, spreadsheet cells, old HITL, or agent presence snapshots were read.
- Facts are parsed evidence, not truth, and need operator confirmation.

## Next Lane

Capital Hilton Governed Fact Intake v1
