# St. Anne's Monthly Work Log

Status: `ST_ANNES_MONTHLY_WORK_LOG_CONTRACT_READY`

This contract defines the future St. Anne's monthly work-log lane for Telegram/Cassandra or Mission Control intake. It is record-only intake until an operator reviews the month-end rollup and separately approves workbook, PDF, and send actions.

## Business Rule

- Client: `st_annes`
- Default rate: `$125` per event
- Month-end invoice should include all recorded St. Anne's events for the month
- Manual/operator confirmation is required before workbook write or send

## Work Log Event

Required event fields:

- `event_id`
- `client_ref=st_annes`
- `service_date`
- `service_time` optional
- `service_label`
- `description`
- `default_rate=125`
- `amount=125`
- `source=telegram|mission_control|manual`
- `operator_confirmed`
- `pii_privacy_status`
- `included_in_invoice_period`
- `invoice_ref` optional

Example Telegram message:

`Mark that I'm at church running sound.`

Expected result: record a St. Anne's work-log event with the current date/time, service label, default `$125` amount, `source=telegram`, and no workbook/email/ledger action.

## Month Rollup

The month rollup gathers all St. Anne's work-log events for the invoice period and computes `expected_total`. It does not write Excel by itself.

Month-end gates:

- Operator review required
- Workbook write requires staged patch approval
- PDF requires artifact approval
- Send requires explicit send approval
- Ledger mutation is not part of this lane
- Paid marking is not part of this lane

## May 2026 Fixture

Recorded events:

- May 10: Adult Forum, `$125`
- May 16: Wedding, `$125`
- May 25: Funeral, `$125`
- May 31, 10:00 AM: Church Service, `$125`

Expected total: `$500`

May 2026 invoice state:

- `invoice_status=MANUAL_SEND_OUT_OF_BAND_RECORDED`
- OpenClaw send performed: no
- Ledger posting allowed: no
- Paid: no
- Source read model: `/mnt/e/openclaw/generated/read_models/st_annes_invoice_status.json`

## Authority Boundary

- Telegram live connection allowed: no
- Telegram send allowed: no
- Workbook write allowed: no
- PDF export allowed: no
- Email send allowed: no
- Ledger posting allowed: no
- Paid marking allowed: no
- Browser/Gmail/Coupa allowed: no
