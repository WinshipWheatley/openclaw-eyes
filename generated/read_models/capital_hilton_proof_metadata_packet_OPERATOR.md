# Capital Hilton Proof Metadata Packet v0

## ELI5 Summary

OpenClaw knows Capital Hilton is the first hard Finance steel thread, but it is not allowed to touch Coupa, Excel, email, accounts, credentials, or invoices. This packet only lists the candidate facts and the proof metadata needed before Cassandra, Guardian, or Finance World can safely do anything later.

## What We Know

- Capital Hilton is the finance steel-thread candidate.
- The lane is a Helm threshold lane aimed at Finance World.
- Cassandra is the review persona; Guardian gates protected proof; Operator remains final authority.
- Current authority is metadata/readback only.

## What We Partly Know

- Completed dates, rate, subtotal, and one-invoice posture appear as candidate facts when supported by existing review read-models.
- Coupa/PO and workbook references are known only as protected metadata needs, not accessible sources.
- Cassandra packet posture is review-only and not financial truth.

## What We Do Not Know

- PO/Coupa/payment reference
- approved AP recipient route
- whether workbook metadata is sufficient
- payment/status proof
- tax/vendor/payment handling
- final invoice packet shape

## Candidate Facts

- `completed_performance_dates`: `['2026-05-08', '2026-05-15 (operator said this was yesterday relative to May 16, 2026)']` -> `CANDIDATE_FACT_NOT_PROVEN`
- `service_performance_description`: `missing` -> `MISSING_PROOF`
- `rate`: `$400 per gig` -> `CANDIDATE_FACT_NOT_PROVEN`
- `subtotal`: `$800 for the two completed governed service-date facts, before any older/upcoming gig review` -> `CANDIDATE_FACT_NOT_PROVEN`
- `customer_client_identity`: `Capital Hilton` -> `METADATA_CONTEXT_NOT_FINAL_INVOICE_PROOF`
- `invoice_recipient_or_ap_route`: `True` -> `CANDIDATE_FACT_NOT_PROVEN`
- `po_coupa_reference`: `must_confirm_po_and_credit_in_coupa_before_final_submission` -> `CANDIDATE_FACT_NOT_PROVEN`
- `excel_workbook_reference`: `workbook metadata/reference mentioned; raw cells not read` -> `CANDIDATE_FACT_NOT_PROVEN`
- `payment_status_reference`: `missing` -> `MISSING_PROOF`
- `tax_vendor_payment_handling_assumptions`: `missing` -> `MISSING_PROOF`
- `invoice_shape_one_invoice_posture`: `one invoice for 2026-05-15 and 2026-05-08; operator also wants 2026-05-22 upcoming gig and older gigs reviewed for inclusion if applicable` -> `CANDIDATE_FACT_NOT_PROVEN`
- `final_invoice_packet_requirement`: `future final invoice packet required after security audit` -> `METADATA_CONTEXT_NOT_FINAL_INVOICE_PROOF`

## Missing Proof Checklist

- `performance_date_proof_metadata`
- `rate_proof_metadata`
- `subtotal_proof_metadata`
- `coupa_po_or_payment_reference_metadata`
- `excel_workbook_reference_metadata`
- `invoice_source_card_metadata`
- `ap_recipient_route_metadata`
- `guardian_protected_access_gate_metadata`
- `operator_confirmation_metadata`
- `future_invoice_generation_receipt_requirement`

## Protected Material Boundary

- Raw Coupa, Excel, Gmail/calendar, PDF, portal, account, and private finance bodies remain blocked.
- Credentials, tokens, cookies, browser sessions, and account access are blocked.
- Operator answers become memory candidates, not proof.

## Cassandra / Guardian / Finance World

- Cassandra may review metadata, packet posture, and missing proof labels only.
- Guardian must gate protected proof, redaction, quarantine, and access posture without self-authorizing.
- Finance World becomes actionable only after proof metadata, package receipts, model/tool/memory receipt posture, security audit, and operator final path are complete.

## Operator Memory Questions

- `memory_only_clarification`: Do you remember whether the Capital Hilton invoice should cover both 2026-05-08 and 2026-05-15 on one invoice?
- `proof_needed`: Do you remember whether $400/gig is the correct rate for both dates?
- `protected_proof_needed`: Is there a Coupa PO number or payment reference that should exist?
- `proof_needed`: Is the proof source likely Coupa, Excel, email, a PDF, a calendar entry, or a packet already in OpenClaw?
- `world_transition_needed`: Should the invoice go through Coupa only, email/AP contact, or another payment route?
- `security_gate_needed`: Is there any protected client material that must be represented only as metadata?
- `world_transition_needed`: What would convince you the invoice is ready to move from helm threshold lane into Finance World action?

## Next Safe Move

- Capture operator answers as Memory Candidate Receipts and then build protected proof metadata references; do not access Coupa, Excel, Gmail, browser, or accounts.

## Stable Map

- Summary included now: `false`
- Next stable-map refresh should include the Capital Hilton proof metadata summary.

## Boundary

- `coupa_access_allowed` = `False`
- `browser_oauth_allowed` = `False`
- `credential_handling_allowed` = `False`
- `gmail_calendar_access_allowed` = `False`
- `excel_raw_body_ingestion_allowed` = `False`
- `raw_finance_body_ingestion_allowed` = `False`
- `invoice_generation_allowed` = `False`
- `send_submit_approval_allowed` = `False`
- `account_access_allowed` = `False`
- `model_call_allowed` = `False`
- `model_api_execution_allowed` = `False`
- `model_router_runtime_allowed` = `False`
- `agent_activation_allowed` = `False`
- `tool_execution_allowed` = `False`
- `queue_execution_allowed` = `False`
- `runtime_dispatch_allowed` = `False`
- `planner_builder_execution_allowed` = `False`
- `hidden_memory_allowed` = `False`
- `external_retained_memory_allowed` = `False`
- `broad_filesystem_indexing_allowed` = `False`
- `broad_private_file_inspection_allowed` = `False`
- `repo_b_mutation_allowed` = `False`
- `repo_b_body_inspection_allowed` = `False`
- `mission_control_app_changes_included` = `False`
- `mac_sync_or_import_triggered` = `False`
- `network_operation_allowed` = `False`
- `pc_c_drive_artifact_write_allowed` = `False`
- `operator_final_authority` = `True`
