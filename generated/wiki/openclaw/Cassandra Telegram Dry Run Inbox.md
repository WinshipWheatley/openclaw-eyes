# Cassandra Telegram Dry Run Inbox

Status: `CASSANDRA_TELEGRAM_DRYRUN_INBOX_READY`

This is a non-live inbox for simulated Telegram/Cassandra messages. It turns local JSON dry-run messages into Workflow Package Queue entries and response receipts.

It does not connect Telegram, read Telegram credentials, send replies, send email, open Gmail/browser/Coupa, touch Excel, export PDFs, mutate ledgers, mark paid, or submit anything.

## Paths

- Inbox: `/mnt/e/openclaw/cassandra_telegram_dryrun_inbox`
- Response receipts: `/mnt/e/openclaw/cassandra_telegram_dryrun_inbox/responses`
- Package queue SQLite: `/home/openclaw/generated/system_knowledge/workflow_package_queue.sqlite`

## Supported Examples

- `telegram_dryrun_fixture_st_annes_work_log` -> `st_annes_work_log_event` / `OPERATOR_REVIEW_REQUIRED`
- `telegram_dryrun_fixture_capital_hilton_proposal` -> `capital_hilton_proposal_followup` / `OPERATOR_REVIEW_REQUIRED`
- `telegram_dryrun_fixture_st_annes_invoice_send` -> `st_annes_monthly_invoice_rollup` / `PERMISSION_REQUIRED`

## Boundary

- Telegram live connection: no
- Telegram reply send: no
- Email/browser/Gmail/Coupa/portal: no
- Excel/workbook/PDF: no
- Ledger/paid/sent mutation: no

## Last Processed Statuses

- `telegram_dryrun_fixture_capital_hilton_proposal`: `capital_hilton_proposal_followup` / `OPERATOR_REVIEW_REQUIRED`
- `telegram_dryrun_fixture_st_annes_invoice_send`: `st_annes_monthly_invoice_rollup` / `PERMISSION_REQUIRED`
- `telegram_dryrun_fixture_st_annes_work_log`: `st_annes_work_log_event` / `OPERATOR_REVIEW_REQUIRED`
