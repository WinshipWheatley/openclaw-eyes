# Capital Hilton Portal Fill Instructions - Review Only, No Submit

Purpose: prepare what the operator must review before any Coupa/Supplier portal work. This file does not authorize a browser session, credential use, upload, save, or submit.

Known governed facts:
- Service date 1: tonight_gig_date has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:e4843b5c9fd0); operator confirmation required
- Service date 2: last_friday_gig_date has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:d0c045745ed6); operator confirmation required
- Rate/amount per gig: rate_or_amount_per_gig has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:06ae3c61778f); operator confirmation required
- Invoice grouping: invoice_count_preference has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:62b213bacc10); operator confirmation required
- PO reference: po_numbers has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:f7b0bbc2f9ec); operator confirmation required
- Billing/remit: billing_remit_details has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:041800d2eafb); operator confirmation required
- Recipient/CC posture: recipient_cc_decision has imported structured evidence in finance_invoice_packet_facts (sha256:4e606352be02); operator confirmation required
- Supplier portal reference: supplier_portal_reference has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:ac571565822e); operator confirmation required
- Invoice output/attachment posture: invoice_attachment_output_path has imported structured evidence in capital_hilton_invoice_fact_updates (sha256:64c764c0bb9b); operator confirmation required

Stop rules:
- Do not log in to Coupa or any supplier portal.
- Do not use or store credentials.
- Do not read spreadsheet cells or parse workbook formulas.
- Do not upload, save, submit, email, or create a payable invoice.
- Stop if the PO number or invoice amount cannot be confirmed by approved evidence/operator review.

Next safe move: operator reviews these facts, confirms missing/unknown portal details, then approves a separate bounded portal-review lane if needed.
