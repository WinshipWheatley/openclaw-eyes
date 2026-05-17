# Cassandra Governed Request -> Review Packet Proof

Status:
- Packet ready for operator review: `true`.
- Review only: `true`.
- Email sent: `false`.
- Portal submitted: `false`.
- Runtime execution triggered: `false`.
- Send authority added: `false`.

## Request
- Refresh the Capital Hilton invoice review packet from governed facts only. Include what is ready to invoice, what is blocked, and what I must confirm manually.

## Route
- Selected: `cassandra_clara_capital_hilton_review_packet`
- Input mode: command-level governed request proof; no Telegram send/reply.

## Governed Facts Used
- Completed service dates: 2026-05-08, 2026-05-15 (operator said this was yesterday relative to May 16, 2026)
- Rate: $400 per gig
- Review subtotal: $800 for the two completed governed service-date facts, before any older/upcoming gig review
- Invoice posture: one invoice for 2026-05-15 and 2026-05-08; operator also wants 2026-05-22 upcoming gig and older gigs reviewed for inclusion if applicable
- Facts remain parsed evidence, not truth; operator confirmation is still required.

## Manual Gates Still Blocked
- `po_coupa_confirmation_required`: PO number is still unknown and must be confirmed manually in Coupa. Next: Operator confirms PO/available credit in Coupa without sharing credentials with OpenClaw.
- `recipient_confirmation_required`: Recipient posture is review-only and business email still needs operator confirmation. Next: Operator confirms To/CC list before any future email-send lane.
- `coupa_invoice_creation_manual_only`: Invoice must be created in Coupa against confirmed PO; OpenClaw has no portal/credential authority. Next: Operator manually prepares/reviews Coupa entry or approves a later bounded no-submit portal-review lane.
- `spreadsheet_invoice_number_manual_check`: Invoice workbook is known only as metadata; OpenClaw did not read cells or formulas. Next: Operator manually opens the Mac invoice workbook and confirms next invoice number/formulas.

## Outputs
- Cassandra/Clara packet: `generated/read_models/cassandra_clara_fact_packet_OPERATOR.md`
- Capital Hilton actionable packet: `generated/read_models/capital_hilton_actionable_review_packet_OPERATOR.md`
- Artifact folder: `generated/finance_packets/cassandra_clara_fact_packet_v0`

## Boundaries
- No Telegram send.
- No Gmail/email send or reply.
- No Coupa or portal submit.
- No credentials accessed.
- No spreadsheet cells read.
- No runtime authority added.

Next recommended lane: Capital Hilton Manual Coupa PO Confirmation
