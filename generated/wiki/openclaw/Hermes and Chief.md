# Hermes and Chief

Status: PARTIAL

## Short human summary
Hermes and Chief read-models currently describe deterministic mission focus, purpose-bound gravity, build handoff, and deferred workflow work without production authority.

## Confirmed facts
- Hermes mission status: READINESS_SENTINEL_NO_EXECUTION; automation_ready_status=NOT_SEND_READY; urgent_goal=Send the Live Arts MD invoice today before the 4:00 PM cutoff, or manually send it..
- Mission critical path: Choose invoice candidate -> BLOCKING (live_arts_md_invoice_candidate_selected_receipt).
- Mission critical path: Get invoice artifact/attachment right -> BLOCKING (invoice_attachment_confirmed_receipt).
- Mission critical path: Confirm recipients -> BLOCKING (recipient_confirmation_receipt).
- Mission critical path: Finalize Clara email package -> BLOCKED_BY_ARTIFACT_AND_RECIPIENTS (clara_email_draft_receipt).
- Mission critical path: Send path decision -> DEADLINE_DECISION (manual_send_receipt_or_email_send_receipt).
- Chief handoff status: DEVELOPER_BUILD_HANDOFF_NO_PRODUCTION_AUTHORITY; handoff_ref=hermes_chief_build_handoff:2fe563699bfa8454.
- Chief task CRITICAL: Build/verify Live Arts invoice candidate selection path -> BOTH.
- Chief task CRITICAL: Build/verify manual artifact attach/link rail -> BOTH.
- Chief task CRITICAL: Build/verify recipient confirmation rail -> BOTH.
- Chief task HIGH: Build/verify Clara send-ready draft transition -> PC.
- Chief task CRITICAL: Build/verify manual-send proof capture fallback -> BOTH.
- Chief task MEDIUM: Build/verify payment watch readiness after send proof -> PC.
- Purpose-bound charter rows: 6.
- Hermes gravity controller: DETERMINISTIC_NON_EXECUTING_PURPOSE_BOUND_GRAVITY_CONTROLLER; charter_count=6.
- Deferred Chief dynamic workflow: DEFERRED_WAITING_FOR_CODEX_5_5_CAPACITY; preferred_model=GPT-5.5 Codex.

## Known unknowns
- Hermes blocker: invoice candidate not selected
- Hermes blocker: invoice artifact/attachment not ready
- Hermes blocker: recipient details unconfirmed
- Hermes blocker: approval/send readiness disabled
- Chief build gap: invoice candidate selection result path
- Chief build gap: manual artifact attach/link rail
- Chief build gap: recipient confirmation rail
- Chief build gap: Clara exact draft readiness transition
- Chief build gap: manual-send proof capture
- Deferred missing proof: Live Arts MD manual send receipt

## Tension / contradiction signals
- none

## Next useful actions
- Use registry/wiki context to avoid duplicate work before Chief picks tasks.
- Keep Chief build work receipt/test focused and separated from production execution.
- Route unsafe or unclear work back to Hermes/Guardian/operator review.

## What not to do
- Do not start live agents from the wiki.
- Do not let Chief handoff tasks imply email, Coupa, ledger, runtime, or workbook authority.
- Do not duplicate a deferred workflow build if a registry/read-model already owns it.

## Source refs / input read-model refs
- generated/read_models/hermes_mission_sentinel.json (hermes_mission_sentinel)
- generated/read_models/hermes_chief_build_handoff.json (hermes_chief_build_handoff)
- generated/read_models/purpose_bound_automation_charter.json (purpose_bound_automation_charter)
- generated/read_models/hermes_gravity_controller.json (hermes_gravity_controller)
- generated/read_models/chief_dynamic_workflow_deferred_build.json (chief_dynamic_workflow_deferred_build)

Last generated timestamp: 2026-05-31T04:09:25+00:00

Generated understanding view. Registry/read-models/receipts remain source of truth.
