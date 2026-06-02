# Cassandra Telegram Intake Contract

Status: `CASSANDRA_TELEGRAM_INTAKE_CONTRACT_READY`

This contract defines how future Telegram/Cassandra messages should enter OpenClaw without connecting Telegram live. It is a non-live schema and safety boundary only.

## Pipeline

1. Telegram/Cassandra message
2. Privacy/PII gate
3. Workflow Package Queue V0
4. Response receipt
5. Optional reply text
6. Business action gate

No business action is allowed without a later explicit gate.

## Required Receipt Fields

- `source_surface=telegram`
- `sender_ref` protected
- `chat_ref` protected
- `message_text_ref` or `protected_text_hash`
- `received_at`
- `workflow_package_id`
- `response_text`
- `no_send_business_action=true`
- `no_excel_by_default=true`
- `no_ledger=true`

Raw Telegram text should be stored only as a protected reference or hash unless a future privacy policy explicitly allows more.

## Supported Initial Examples

### St. Anne's work log

Input: `Mark that I'm at church running sound.`

- Workflow: `st_annes_work_log_event`
- Expected status: `OPERATOR_REVIEW_REQUIRED`
- Safe reply: recorded for operator review, not invoice-ready until confirmed
- Excel: no
- Email: no
- Ledger: no

### Capital Hilton proposal follow-up

Input: `Follow up on Capital Hilton proposal.`

- Workflow: `capital_hilton_proposal_followup`
- Expected status: `OPERATOR_REVIEW_REQUIRED`
- Safe reply: staged for operator review, no email sent
- Finance handoff: blocked until accepted

### St. Anne's invoice send request

Input: `Send St. Anne's invoice.`

- Workflow: `st_annes_monthly_invoice_rollup`
- Expected status: `PERMISSION_REQUIRED_OR_ARTIFACT_REQUIRED`
- Safe reply: blocked until an approved invoice artifact and explicit send gate exist
- Excel: not touched by Telegram intake
- Email: not sent
- Ledger: not touched

## Rules

- Telegram intake can record work-log events.
- Telegram intake cannot submit Coupa.
- Telegram intake cannot send email without an explicit send gate.
- Telegram intake cannot touch Excel directly.
- If permission, artifact, or provider authority is missing, the reply must name the specific blocker.

## Authority Boundary

- Telegram live connection: no
- Telegram credentials access: no
- Telegram send: no
- Gmail/email send: no
- Browser/Coupa submit: no
- Excel/workbook mutation: no
- PDF export: no
- Ledger posting: no
- Paid marking: no

## Source References

- Workflow Package Queue: `generated/read_models/workflow_package_queue_contract.json`
- Workflow Package Request Consumer: `generated/read_models/workflow_package_request_consumer_status.json`
- Automation Permission Registry: `generated/read_models/automation_permission_registry.json`
- St. Anne's Monthly Work Log Contract: `generated/read_models/st_annes_monthly_work_log_contract.json`
