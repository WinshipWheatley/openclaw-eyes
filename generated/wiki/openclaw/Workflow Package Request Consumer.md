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

- St. Anne's church sound instruction: `cassandra` / `operator_intake` / "St. Anne's work log captured"
- Capital Hilton proposal follow-up: `cassandra` / `operator_calm` / "Capital Hilton proposal follow-up staged"
- Capital Hilton invoice submit request: `chief` / `diagnostic` / "Capital Hilton invoice needs operator assist"

The Capital Hilton invoice submit package remains blocked because the operator-assist provider and final Submit gate are not explicitly staged. No Coupa action occurred.

## Operator Display Layer

Workflow package responses keep machine fields in proof/details, but Mission Control can render `operator_display` for primary copy.

- Plain human language first
- No raw workflow refs in primary visible copy
- No all-caps machine statuses in primary visible copy
- Proof/details collapsed by default
- Blocked responses explain the missing gate in one sentence

## Voice Routing

Package responses include deterministic voice fields:

- `speaker_ref`
- `voice_mode`
- `audience`

External client-facing draft copy should use `clara`; internal agent names are not for client-visible copy.

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
