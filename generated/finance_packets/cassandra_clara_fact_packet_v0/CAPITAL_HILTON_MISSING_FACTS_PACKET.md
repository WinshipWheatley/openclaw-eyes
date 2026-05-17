# Capital Hilton Missing-Facts Packet

This packet was built from governed Repo A SQLite/read-model facts only.

Usable review packet: `true`
Packet kind: `capital_hilton_review_packet`

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
- No raw notes, logs, messages, spreadsheet cells, old HITL, or agent presence snapshots were read.
- All facts remain parsed evidence, not truth, until operator confirmation.
