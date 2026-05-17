# Cassandra/Clara Fact Packet v0

Target workflow: `capital_hilton_invoice`
Packet kind: `capital_hilton_review_packet`
Usable Capital Hilton review packet: `true`
Governed facts found: `40`
Contact candidates found: `3`
Missing required facts: `0`

## Artifacts
- `missing_facts`: `generated/finance_packets/cassandra_clara_fact_packet_v0/CAPITAL_HILTON_MISSING_FACTS_PACKET.md`
- `contact_review`: `generated/finance_packets/cassandra_clara_fact_packet_v0/CAPITAL_HILTON_CONTACT_REVIEW.md`
- `draft_email`: `generated/finance_packets/cassandra_clara_fact_packet_v0/CAPITAL_HILTON_CLARA_DRAFT_EMAIL_REVIEW_ONLY.md`
- `portal_instructions`: `generated/finance_packets/cassandra_clara_fact_packet_v0/CAPITAL_HILTON_PORTAL_FILL_INSTRUCTIONS_REVIEW_ONLY.md`
- `receivable_review`: `generated/finance_packets/cassandra_clara_fact_packet_v0/CAPITAL_HILTON_RECEIVABLE_REVIEW.md`
- `manifest`: `generated/finance_packets/cassandra_clara_fact_packet_v0/MANIFEST.json`

## Missing Required Facts
- None.

## Invoice Facts Used
- `tonight_gig_date`: 2026-05-15 (operator said this was yesterday relative to May 16, 2026)
- `last_friday_gig_date`: 2026-05-08
- `rate_or_amount_per_gig`: $400 per gig
- `invoice_count_preference`: one invoice for 2026-05-15 and 2026-05-08; operator also wants 2026-05-22 upcoming gig and older gigs reviewed for inclusion if applicable
- `po_numbers`: unknown; operator reports Coupa PO credit may exist and PO must be confirmed in Coupa later; no portal login authorized
- `billing_remit_details`: mail check to operator home address provided in prompt; full street address redacted from committed artifacts
- `recipient_decision`: To: Annette Sunga (business email pending confirmation); CC: operator email, Chyna Hardin, Lawrence/Will Valcovic; no send authority
- `supplier_portal_reference`: Coupa supplier portal reference provided by operator; credential use/storage not authorized; credentials must remain tokenized in a later approved lane
- `invoice_attachment_output_path`: invoice must be created in Coupa against confirmed PO; existing Mac Documents/invoices spreadsheet is metadata-only source workbook; next invoice number should be one higher after workbook review; no spreadsheet cells read

## Boundaries
- No send authority.
- No runtime authority.
- No raw private files, logs, messages, spreadsheet cells, old HITL, or agent presence snapshots were read.
- Facts are parsed evidence, not truth, and need operator confirmation.

## Next Lane

Capital Hilton Invoice Review Packet Approval v0
