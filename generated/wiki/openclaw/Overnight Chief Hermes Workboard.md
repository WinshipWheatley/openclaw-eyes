# Overnight Chief Hermes Workboard

Status: READY_FOR_OPERATOR_REVIEW

Mode: planning_only

This workboard is a planning surface. Hermes recommends the lane sequence, Chief packages bounded next tasks, and Guardian marks anything that needs explicit approval. It does not execute provider actions or mutate business state.

## Hermes Recommendation

Sequence operator review and hygiene first, client follow-up watches next, then hardening work.

1. Confirm/discard St. Anne's work-log events
2. Build St. Anne's month-end rollup path from confirmed real events
3. Track Capital Hilton proposal response
4. Track Capital Hilton Coupa Processing / payment follow-up
5. Excel permission persistence hardening
6. Prepare Telegram/Cassandra dry-run inbox
7. Add TTS sanitizer for speaker profiles

## Chief Packets

### St. Anne's Work-Log Review Surface

Goal: prepare confirm/discard guidance for staged St. Anne's work-log events without treating smoke as billable truth.

Current state: the church-sound smoke event is `SMOKE_OR_TEST_EVENT` and `NOT_INCLUDED_SMOKE_EVENT`.

Allowed planning actions:

- Inspect local St. Anne's work-log read models.
- Summarize staged, confirmed, and smoke-excluded event states.
- Read the St. Anne's work-log hygiene read model.
- Prepare a no-action review checklist.

Blocked actions:

- Include smoke/test events in invoice rollup.
- Mutate Excel.
- Create invoice.
- Export PDF.
- Send email.
- Mutate ledger.
- Mark paid.

Next safe move: show that the current church-sound event is smoke/test-only and ask for separate real-world confirmation before any rollup eligibility.

### St. Anne's Month-End Rollup Prerequisites

Goal: package St. Anne's month-end rollup prerequisites from confirmed real events only, without touching the workbook.

Next safe move: create a rollup readiness checklist that has zero eligible events until real operator business confirmation exists.

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

Goal: plan a Telegram/Cassandra dry-run inbox into the workflow package queue without connecting Telegram.

Next safe move: create or refine local-only tests for Telegram-shaped envelopes.

### TTS Voice Profile Sanitizer Usage

Goal: plan how operator_display fields and conversation-journal summaries feed TTS-safe text by speaker profile.

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
- St. Anne's smoke/test event invoice inclusion.
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
- `st_annes_work_log_events.json`
- `st_annes_work_log_hygiene.json`
- `operator_assist_provider_registry.json`
- `business_development_proposal_lane_registry.json`
- `capital_hilton_coupa_workflow_harvest.json`
- `agent_voice_profiles.json`
- `agent_voice_routing_contract.json`
- `operator_conversation_journal.json`
