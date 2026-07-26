# Cassandra/Clara Fact Packet v0

Target workflow: `capital_hilton_invoice`
Packet kind: `capital_hilton_review_packet`
Usable Capital Hilton review packet: `true`
Governed facts found: `40`
Contact candidates found: `4`
Receivable/payment posture rows: `10`
Missing required facts: `0`
Source policy: `imported_cassandra_chief_memory_sqlite_only`

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
- `tonight_gig_date`: tonight_gig_date has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:e4843b5c9fd0); operator confirmation required
- `last_friday_gig_date`: last_friday_gig_date has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:d0c045745ed6); operator confirmation required
- `rate_or_amount_per_gig`: rate_or_amount_per_gig has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:06ae3c61778f); operator confirmation required
- `invoice_count_preference`: invoice_count_preference has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:62b213bacc10); operator confirmation required
- `po_numbers`: po_numbers has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:f7b0bbc2f9ec); operator confirmation required
- `billing_remit_details`: billing_remit_details has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:041800d2eafb); operator confirmation required
- `recipient_decision`: recipient_decision has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:4e606352be02); operator confirmation required
- `supplier_portal_reference`: supplier_portal_reference has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:ac571565822e); operator confirmation required
- `invoice_attachment_output_path`: invoice_attachment_output_path has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:64c764c0bb9b); operator confirmation required

## Facts Needing Operator Confirmation
- `tonight_gig_date`: Exact service date for tonight's gig
- `last_friday_gig_date`: Exact service date for last Friday's gig
- `rate_or_amount_per_gig`: Rate or amount per gig
- `invoice_count_preference`: One invoice or two invoices
- `po_numbers`: PO number(s) or explicit none
- `billing_remit_details`: Billing/remit details
- `recipient_decision`: To/CC recipient decision
- `supplier_portal_reference`: Supplier portal reference
- `invoice_attachment_output_path`: Invoice attachment/output path

## Contact / Recipient Posture
- `ccmem_ent_d37554eb4750da5db7b5`: business_contact:sha256:101e8459b3b / finance_ap_contact; email_permission_rows=1; no_send=true
- `ccmem_ent_717a5a0b2e5324400a81`: business_contact:sha256:61f129360f8 / director_of_finance; email_permission_rows=1; no_send=true
- `ccmem_ent_fe0efbbcd5c92b17e77d`: business_contact:sha256:e0717bc385e / hilton_contact; email_permission_rows=1; no_send=true
- `ccmem_ent_8c759b658eb4756428cb`: organization:capital_hilton_capitol_hilton / organization_candidate; email_permission_rows=0; no_send=true

## Invoice / Receivable Posture
- `receivable_packet_status:invoice_prep` from `finance_invoice_packets`; parsed_evidence_not_truth / needs_operator_confirmation
- `receivable_packet_status:invoice_prep` from `finance_invoice_packets`; parsed_evidence_not_truth / needs_operator_confirmation
- `receivable_payment_tracking_metadata` from `finance_state_json`; parsed_evidence_not_truth / needs_operator_confirmation
- `receivable_payment_tracking_metadata` from `finance_state_json`; parsed_evidence_not_truth / needs_operator_confirmation
- `receivable_payment_tracking_metadata` from `finance_state_json`; parsed_evidence_not_truth / needs_operator_confirmation
- `receivable_payment_tracking_metadata` from `finance_state_json`; parsed_evidence_not_truth / needs_operator_confirmation
- `receivable_payment_tracking_metadata` from `finance_state_json`; parsed_evidence_not_truth / needs_operator_confirmation
- `receivable_payment_tracking_metadata` from `finance_state_json`; parsed_evidence_not_truth / needs_operator_confirmation
- `receivable_payment_tracking_metadata` from `finance_state_json`; parsed_evidence_not_truth / needs_operator_confirmation
- `receivable_payment_tracking_metadata` from `finance_state_json`; parsed_evidence_not_truth / needs_operator_confirmation

## Boundaries
- No send authority.
- No runtime authority.
- No raw private files, logs, messages, spreadsheet cells, old HITL, or agent presence snapshots were read.
- Facts are parsed evidence, not truth, and need operator confirmation.

## Next Lane

Capital Hilton Invoice Review Packet Approval v0
