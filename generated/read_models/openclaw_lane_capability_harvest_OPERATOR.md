# OpenClaw Lane Capability Harvest

- Readiness: `READY_FOR_PLANNING_NOT_EXECUTION`
- Confidence: `HIGH`
- Hermes recommendation: `finish_invoice_steel_thread_sequence`
- Chief build task: `chief_build_task:finish_invoice_steel_thread_sequence`

## What Live Arts Taught OpenClaw

Live Arts status: `ACTIVE_STEEL_THREAD`.
Harvested capabilities: Simple invoice rail, Invoice candidate selection and collapse, Selected invoice summary state, Event Bridge Prepare PDF action, Scoped PDF artifact package, Manual send proof receipt, Read-only payment watch, No-authority invoice boundary, Mac/PC bridge scoped response.

## What Capital Hilton Should Reuse

Capital Hilton status: `PARTIAL`.
Reuse: `[
  "capability:simple_invoice_rail",
  "capability:event_bridge_prepare_pdf_action",
  "capability:authority_boundary",
  "capability:manual_send_proof"
]`.
Add only the complex extensions: supplier portal proof, Coupa/PO posture, multi-invoice review, and approval gates.

## What St. Anne's Should Reuse

St. Anne's status: `PARTIAL`.
Reuse: `[
  "capability:simple_invoice_rail",
  "capability:event_bridge_prepare_pdf_action",
  "capability:invoice_candidate_selection",
  "capability:pdf_artifact_package",
  "capability:payment_watch"
]`.
Do not inherit Coupa, supplier portal, or PO blockers.

## After The Three Invoice Lanes

If Live Arts, Capital Hilton, and St. Anne's are all proven, the next adjacent lane should be payment proof intake.

## Hermes Next

Hermes should keep the build order on Live Arts -> Capital Hilton -> St. Anne's until those lanes prove the reusable invoice rail.

## Chief Next

chief_build_task:finish_invoice_steel_thread_sequence

## Do Not Work Now

- generic Telegram polish before object rails are stable
- ledger posting before proof and approval gates are proven
- remote Mac or cloud relay before the local bridge/helper path is stable
- generic AI chat upgrades without a bounded business object

## Boundary

This registry is planning/read-model only. It performs no service start, LM call, Chief launch, email/Gmail/browser/Coupa access, workbook cell read, PDF export, ledger mutation, production mutation, or push.
