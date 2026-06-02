# Overnight Chief Hermes Workboard

Status: READY_FOR_OPERATOR_REVIEW

Mode: planning_only

This workboard is a planning surface. Hermes recommends the lane sequence, Chief packages bounded next tasks, and Guardian marks anything that needs explicit approval. It does not execute provider actions or mutate business state.

## Hermes Recommendation

Sequence record-only lanes first, operator-assist follow-ups next, then hardening work.

1. St. Anne's work-log confirmation path
2. St. Anne's month-end rollup readiness
3. Capital Hilton proposal follow-up timing
4. Capital Hilton Coupa payment watch
5. Excel permission persistence hardening
6. Telegram/Cassandra non-live adapter
7. TTS sanitizer and voice profile usage

## Chief Packets

### St. Anne's Work-Log Review Surface

Goal: prepare the next operator review surface for staged St. Anne's work-log events.

Allowed planning actions:

- Inspect local St. Anne's work-log read models.
- Summarize staged and confirmed event states.
- Prepare a no-action review checklist.

Blocked actions:

- Mutate Excel.
- Create invoice.
- Export PDF.
- Send email.
- Mutate ledger.
- Mark paid.

Next safe move: show staged events with confirm/discard/edit actions gated by operator review.

### St. Anne's Month-End Rollup Prerequisites

Goal: package St. Anne's month-end rollup prerequisites without touching the workbook.

Next safe move: create a rollup readiness checklist that stops before workbook mutation.

### Capital Hilton Proposal Follow-Up Plan

Goal: prepare a Capital Hilton proposal follow-up plan that stays in Business Development.

Next safe move: stage a follow-up packet that waits for explicit email approval.

### Capital Hilton Coupa Payment Watch

Goal: package a Coupa Processing/payment-watch checklist.

Next safe move: record that Coupa status is Processing and payment remains unclaimed.

### Excel Permission Hardening Plan

Goal: plan Excel permission persistence hardening for workbook/PDF automation.

Next safe move: draft a permission-hardening test matrix with no workbook writes.

### Telegram/Cassandra Non-Live Adapter

Goal: plan Telegram-shaped envelopes into the workflow package queue without connecting Telegram.

Next safe move: create or refine local-only tests for Telegram-shaped envelopes.

### TTS Voice Profile Sanitizer Usage

Goal: plan how operator_display fields feed TTS-safe text by speaker profile.

Next safe move: keep TTS as local text preparation until a separate approval creates a live provider gate.

## Guardian Gates

Explicit approval is required for:

- Email send.
- Coupa submit.
- Ledger posting.
- Paid marking.
- Excel workbook mutation.
- PDF export.
- Live provider access.
- Old agent loop launch.
- Git push.

## Do Not Run While Sleeping

- Email or Gmail send.
- Coupa or browser portal actions.
- Telegram or TTS live connection.
- Excel GUI open/write or workbook mutation.
- PDF export.
- Ledger post or paid marking.
- Invoice creation.
- Proposal acceptance marking.
- Service restart.
- `loop_control.sh` or `start_chief.sh`.
- Chief/Cassandra/Guardian loops.
- Git push.

## Source Read Models

- `client_work_closeout_2026_06_01.json`
- `invoice_steel_thread_harvest_registry.json`
- `workflow_package_request_consumer_status.json`
- `automation_permission_registry.json`
- `st_annes_monthly_work_log_contract.json`
- `operator_assist_provider_registry.json`
- `business_development_proposal_lane_registry.json`
- `capital_hilton_coupa_workflow_harvest.json`
- `agent_voice_profiles.json`
- `agent_voice_routing_contract.json`
