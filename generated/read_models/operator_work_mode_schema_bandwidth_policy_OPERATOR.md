# Operator Work Mode Schema / Bandwidth Policy v0

## ELIWINSHIP Summary

The helm feels overloaded when it shows the system's internal contracts as if they are Winship's job. Work Mode changes the default shape: show the few things that need Winship, say the next human move in plain language, and keep proof/details one level down.

Simple is not less powerful here. Simple means the system already did the sorting. The raw contracts, receipts, proof shelves, and generated read-models still exist, but they become substrate instead of the front door.

This prompt does not build UI or enable actions. It defines the read-model shape that a later app surface can use to render human solve paths.

## Bandwidth Defaults

- Helm default: `LOW_BANDWIDTH`.
- Low bandwidth: one next move, plain language, short choices, details hidden unless opened.
- Normal bandwidth: short explanation, why it matters, next step, choices, proof summary.
- High bandwidth: blockers, proof refs, receipt refs, authority gates, workflow relationship.
- Debug mode: contracts, generated read-models, raw fields, proof shelves, diagnostics. Never default.

## Work Modes

- `PROOF_WORK_MODE`: Help Winship decide what is true, missing, or needs a protected proof ref.
- `DECISION_WORK_MODE`: Help Winship choose the safe direction when a workflow needs judgment.
- `ARTIFACT_WORK_MODE`: Help Winship review or assemble an artifact path without creating protected output.
- `APPROVAL_WORK_MODE`: Help Winship review an approval packet before any action can happen.
- `REPAIR_DIAGNOSTIC_WORK_MODE`: Help Winship see what is actually broken before repair work starts.
- `TERRAIN_RECONCILIATION_WORK_MODE`: Help Winship sort current, stale, duplicate, overlapping, and source-gap terrain.
- `DRAFT_COMMUNICATION_WORK_MODE`: Help Winship review a communication before any send path exists.
- `AUTOMATION_CANDIDATE_WORK_MODE`: Help Winship see whether a repeated task might later be automated safely.
- `CREATIVE_PROJECT_WORK_MODE`: Help Winship resume creative or client work without losing context.
- `UNKNOWN_FAIL_CLOSED`: Keep unclear work from becoming a noisy or unsafe action.

## App-Wide Examples

- `capital_hilton_invoice_work_mode`: Pick what is true about the invoice. Purpose: make invoice proof path human-usable.
- `chief_terrain_reconciliation_work_mode`: Review what should stay current. Purpose: find current/stale/overlap/source gaps.
- `check_engine_diagnostic_work_mode`: Check what is actually broken. Purpose: show diagnostic evidence and next safe check.
- `security_delta_review_work_mode`: Decide if this needs security review. Purpose: classify whether new authority needs security delta/repass.
- `niles_struna_project_work_mode`: Pick up where you left off. Purpose: continue creative/client/software lane without losing context.
- `cassandra_clara_draft_work_mode`: Review the draft before anything sends. Purpose: draft review/send path later.

Capital Hilton is only the first major example. The same schema also covers terrain reconciliation, developer/system diagnostics, security review, creative/music work, communication drafts, client/project delivery, proof/reference work, and automation candidates.

## Human Translation

- Deterministic state decides truth, blockers, authority, and proof status.
- The LM may render plain language from a deterministic packet.
- The LM cannot decide authority, mark proof complete, approve an action, create hidden memory, or invent dynamic buttons.
- Output should become a read-model or preview packet before app display when possible.

## Helm Declutter

- Helm should show urgent decisions, blocked workflows needing human action, high-level health/authority state, and next safe move cards.
- Helm should hide raw machine contracts, long proof shelves, generated read-model details, completed/quieted steps, and duplicate proof rows.
- Proof stays one level down: inspectable, but not default visual noise.

## Stable Map / App Exposure

- Eventually expose active workflow sessions, current work mode, unresolved attention tickets, automation readiness, one next human move, bandwidth summaries, and proof summary refs.
- Keep raw screenshots, logs, transitional machine JSON, draft email payloads, raw protected content, and full contract internals out of the default surface.

## Still Blocked

- No live workflow execution, input persistence, automation execution, approval submission, invoice generation, email/Telegram send, browser/account/Coupa/Gmail/calendar access, credential handling, model/tool/agent/runtime/queue execution, ledger write, file cleanup, stable-map refresh, Mac UI implementation, or Mission Control Swift change.

## Prompt 2

- Prompt 2 should add the Operator Solve Path and Decision Node Contract. That is where explicit solve-path steps and decision nodes become deterministic packets. This prompt only defines the app-wide mode and bandwidth schema.

## Machine Proof Summary

- Bandwidth modes: `4`.
- Work mode types: `10`.
- Issue classifications: `11`.
- Work mode instances: `6`.
- All authority flags false: `true`.
- Machine contracts are not default app surface: `true`.
- Content hash: `sha256:b8431b7f8030db73d959dc4ab8091ecb7abe68346baf9a2956ac48e321bdf413`.
