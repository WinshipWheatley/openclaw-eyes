# Workflow Package Request Consumer

Status: `WORKFLOW_PACKAGE_RAIL_STATUS_READY`

The PC request-response rail now consumes Mission Control generic operator instruction envelopes with `request_type=WORKFLOW_PACKAGE_REQUEST_V0` and routes them into Workflow Package Queue V0.

## Current Route

`Mission Control chat -> bridge inbox request -> PC request-response service -> workflow_package_request_consumer -> workflow_package_queue -> scoped Mac response`

This is a dry-run package queue rail only. It does not connect Telegram live, send email, open Gmail/browser/Coupa, mutate ledgers, mutate workbooks, export PDFs, mark paid, submit anything, or grant external authority.

## Supported Package Types

- `st_annes_work_log_event`
- `st_annes_monthly_invoice_rollup`
- `capital_hilton_invoice_operator_assist`
- `capital_hilton_proposal_followup`
- `diagnostic_package_gate_smoke`

## Smoke Results

- St. Anne's church sound instruction: `st_annes_work_log_event`, `OPERATOR_REVIEW_REQUIRED`
- Capital Hilton proposal follow-up: `capital_hilton_proposal_followup`, `OPERATOR_REVIEW_REQUIRED`
- Capital Hilton invoice submit request: `capital_hilton_invoice_operator_assist`, `PROVIDER_GATE_REQUIRED`

The Capital Hilton invoice submit package remains blocked because the operator-assist provider and final Submit gate are not explicitly staged. No Coupa action occurred.

## Boundary

- Email send allowed: no
- Ledger posting allowed: no
- Browser/Gmail/Coupa allowed: no
- Portal submit allowed: no
- Workbook mutation allowed: no
- PDF export allowed: no
- Paid/sent state grant: no

## Next Mac Step

Run `actual_chat_ui_response_smoke` from Mission Control so the Mac app proves the chat UI observes and renders these scoped package responses.
