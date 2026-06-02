# Workflow Package Queue

Status: `WORKFLOW_PACKAGE_QUEUE_V0_READY`

This is the first durable package queue/status machine for turning human-style instructions from Mission Control, Telegram, Cassandra, manual entry, or Codex into gated workflow packages.

V0 uses dry-run/no-op workers only. It does not connect Telegram live, send email, open Gmail/browser/Coupa, mutate ledgers, mutate workbooks, export PDFs, mark paid, or submit anything.

## Pipeline

1. `human_instruction`
2. `privacy_pii_gate`
3. `intent_classification`
4. `workflow_package_record`
5. `sqlite_package_registry`
6. `capability_provider_gate`
7. `worker_assignment`
8. `result_receipt`
9. `operator_review_gate`
10. `business_action_gate`

## Supported Package Types

- `st_annes_work_log_event`
- `st_annes_monthly_invoice_rollup`
- `capital_hilton_invoice_operator_assist`
- `capital_hilton_proposal_followup`
- `diagnostic_package_gate_smoke`

## Fixture Results

- `st_annes_work_log_event`: status `OPERATOR_REVIEW_REQUIRED`, capability gate `ALLOW_DRY_RUN`
- `st_annes_monthly_invoice_rollup`: status `PERMISSION_REQUIRED`, capability gate `PERMISSION_REQUIRED`
- `capital_hilton_proposal_followup`: status `OPERATOR_REVIEW_REQUIRED`, capability gate `ALLOW_DRY_RUN`
- `capital_hilton_invoice_operator_assist`: status `PROVIDER_GATE_REQUIRED`, capability gate `PROVIDER_GATE_REQUIRED`
- `diagnostic_package_gate_smoke`: status `PACKAGE_STAGED`, capability gate `ALLOW_DRY_RUN`

## Operator Display Layer

Package responses include `operator_display` for Mission Control cards while retaining machine fields in proof/details.

- `speaker_ref`
- `voice_profile_ref`
- `voice_mode`
- `audience`
- `routing_reason`
- `headline`
- `subheadline`
- `status_label`
- `tone`
- `plain_summary`
- `next_safe_action`
- `why_it_matters`
- `primary_fact`
- `secondary_facts`
- `proof_caption`
- `show_machine_details_by_default`

Example display headlines:

- St. Anne's work log captured: Needs confirmation - Review and confirm the event.
- St. Anne's invoice is not ready to send: Missing prerequisite - Resolve the missing gate, then review the package again.
- Capital Hilton proposal follow-up staged: Needs review - Review the follow-up plan.
- Capital Hilton invoice needs operator assist: Provider gate required - Stage an operator-assist packet when you are ready.
- Workflow package staged: Needs review - Review the staged package.

## Authority Boundary

- Email send allowed: no
- Ledger posting allowed: no
- Browser/Gmail/Coupa/portal allowed: no
- Workbook source mutation allowed: no
- Paid marking allowed: no
- Sent state granted: no

## Notes

- Telegram intake records work-log/package intent only in V0.
- St. Anne's invoice send is blocked without permission/artifact gates.
- Capital Hilton Coupa submission is blocked without an explicitly staged operator-assist provider and Submit gate.
- Capital Hilton proposal follow-up is Business Development only and creates no invoice.
