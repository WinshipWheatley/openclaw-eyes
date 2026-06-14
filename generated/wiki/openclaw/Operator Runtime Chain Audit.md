# Operator Runtime Chain Audit

Status: `OPERATOR_RUNTIME_CHAIN_AUDIT_READY`

Generated: `2026-06-04T15:39:23Z`

This is a read-only audit of the OpenClaw operator runtime chain:

`chat goal -> privacy gate -> LM planner -> package compiler -> SQLite registry -> authority gate -> LM2/worker cage -> receipt -> operator review -> business-action gate -> dynamic app card`

No runtime state was intentionally mutated beyond the requested generated audit artifacts.

## Direct Answers

1. Where does LM1 currently exist?

LM1 currently exists as contract-only and deterministic substitute layers: `workflow_composer.py`, `lm_bounded_operator_orchestration.py`, `workflow_package_queue.py` deterministic `classify_intent`, `deterministic_intent_interpreter.py`, and `local_llm_intent_privacy_upgrade_plan.json`.

2. Is LM1 live, shadow, deterministic substitute, or contract-only?

LM1 is not live. It is deterministic substitute plus contract-only planning. `lm_bounded_operator_orchestration_latest.json` reports `mode=contract_only_no_live_lm`. The local LLM privacy plan is `planning_only`, and `local_llm_intent_shadow_harness.json` is absent.

3. Where does LM2 currently exist?

LM2 currently exists in `spawned_worker_package_lifecycle.py`, `worker_package_staging.py`, `openclaw_lm_child_package_gate.json` / `.sqlite`, `agent_handoff_event_consumer.py`, and `workroom_review_packet_index.py` as lifecycle, policy, staging, and review packet infrastructure.

4. Is LM2 a real worker cage or just package staging/review packet lifecycle?

It is not a live worker cage yet. It is package staging, disabled child-spawn policy, lifecycle definitions, example receipts, and review packet indexing.

5. What currently creates packages?

`workflow_package_queue.create_package` creates dry-run packages. `workflow_package_request_consumer.consume_workflow_package_request` validates Mission Control envelopes and calls it. `workflow_composer` creates plans only.

6. Where are packages stored?

Packages are stored in `generated/system_knowledge/workflow_package_queue.sqlite` and indexed in `generated/system_knowledge/package_event_index.sqlite`.

7. What validates package authority?

Request preflight/router false-authority checks, workflow package envelope validation, package privacy/capability/business-action gates, gate decision ledger, approval request queue, operator action payload authority boundaries, LM-bounded deterministic validation, review-decision unsafe scans, and Guardian output gate.

8. What prevents false recursive truth?

Truth is anchored to source refs, protected hashes, SQLite rows, receipts, approval logs, evidence confidence classes, and operator-confirmed memory. LM-shaped output can recommend or summarize only.

9. What does the app currently render that should instead be generated dynamically?

The app receives mixed `visible_cards`, `operator_display`, `layered_response_fields`, `spoken_response_packet`, `visual_event_package`, and `action_payloads`. Workflow-specific status cards, diagnostic cards, lane-specific copy, review controls, and proof disclosure should be generated from one backend card schema.

10. What generic dynamic card schema does the backend need?

`openclaw_dynamic_operator_card_v0`: `card_id`, source refs, current/target lane refs, speaker/voice fields, headline, status, tone, summary, next action, facts, allowed/blocked actions, action payload ids, authority boundary, gates, proof refs, receipts, review controls, machine details, and render hints.

11. What can the app eventually strip away?

Per-workflow hardcoded cards, lane-specific status text, diagnostic/package queue special cases, duplicated authority warnings, direct protected-action mapping, proof disclosure logic, and bespoke button payload builders.

12. What is the next safest implementation sequence?

Publish the generic card contract, map current outputs into it, render it generically on Mac, bind buttons to action payload ids and operator decision receipts, enforce WIP/approval gates before staging, then add LM1 shadow mode. Only after those proofs exist should a real LM2 cage be built.

## Stage Summary

| Stage | Exists | Current posture | Main gap |
| --- | --- | --- | --- |
| Chat/input envelope | yes | live deterministic processor | no single generic card schema |
| Current context envelope | yes | deterministic lane metadata | context fields are rail-specific |
| Dynamic PII/privacy gate | yes | hash-only deterministic gate | no live dynamic classifier |
| LM1 planner | yes | deterministic substitute / contract-only | no live LM1 runtime |
| Package compiler | yes | dry-run deterministic compiler | input is not typed Composer output |
| SQLite/package registry | yes | real local package/event DBs | fragmented DB ownership remains |
| Capability/provider gate | yes | deterministic registry/gate | provider gate not shared everywhere |
| Approval/gate ledger | yes | local non-executing ledgers | not bound to every package/action |
| LM2/worker cage | partial | contract/stub lifecycle | no live worker cage |
| Worker result receipt | partial | noop/contract receipts | no real unified receipt ingestion |
| Review packet index | yes | read-model review queue | no dedicated review decision DB here |
| Operator decision | yes | local receipt rails | decision schemas remain rail-specific |
| Business-action gate | yes | closed deterministic gates | no executor gate |
| Dynamic card/answer | partial | deterministic response builder | ad hoc card shapes |
| Memory promotion | yes | candidate-only gate | promotion decisions need full receipt flow |

## SQLite Proof

- `workflow_package_queue.sqlite`: package queue tables with 68 rows in each normalized package table.
- `package_event_index.sqlite`: 32 package/request/response/journal events.
- `gate_decision_ledger.sqlite`: 10 gate decisions.
- `approval_request_queue.sqlite`: 7 approval requests.
- `operator_conversation_journal.sqlite`: 32 journal entries.
- `openclaw_lm_child_package_gate.sqlite`: child-package policy, package, decision, and receipt tables.
- `st_annes_monthly_work_log.sqlite`: St. Anne's staged work log and review action tables.
- `capital_hilton_invoice_operator_run_status.sqlite`: Capital Hilton operator-assisted status receipt.

## Next Safe Sequence

1. Publish `openclaw_dynamic_operator_card_v0` as a read-model contract only.
2. Map existing `operator_display`, `layered_response_fields`, proof refs, and action payloads into that card shape.
3. Keep old `visible_cards` temporarily for compatibility.
4. Make Mission Control render backend cards generically.
5. Bind buttons to `operator_action_payloads` and record `operator_decision_receipt_v0`.
6. Enforce Workroom WIP limits before new staging.
7. Route Composer/LM1 output into a typed package compiler input.
8. Add local LM1 shadow mode after privacy receipts exist.
9. Add worker result receipt validation.
10. Build real LM2 cage only after sandbox, receipt, WIP, and approval gates are enforced.

## Boundary

- No email, Gmail, browser, Coupa, ledger, workbook, PDF, submit, mark-paid, worker, child-agent, external-LLM, merge, push, or business action occurred.
- LM output is not truth. Truth must come from source files, read models, SQLite rows, receipts, hashes, approval logs, or operator-confirmed memory.
