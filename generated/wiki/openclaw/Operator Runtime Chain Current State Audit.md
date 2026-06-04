# Operator Runtime Chain Current State Audit

Status: `OPERATOR_RUNTIME_CHAIN_CURRENT_STATE_AUDIT_READY`

Generated: `2026-06-04T16:11:12Z`

Mode: read-only current-state audit. This report does not design, implement, or fix architecture. It checks the proposed chain against the code, read models, and SQLite metadata that exist now.

## Current Actual Chain

OpenClaw currently has a bounded Mission Control request-file service, not one universal linear runtime chain.

The observed spine is:

1. Mission Control writes a supported request file to the approved inbox.
2. `openclaw_request_response_service.py` scans only the approved inbox, deduplicates, routes, and writes a processing heartbeat.
3. `openclaw_request_processor.py` classifies the request, calls `openclaw_request_router.py`, runs preflight, then dispatches a deterministic rail.
4. Supported rails include workflow-package requests, contextual system questions, workroom review decisions, workbook registration, local surface/artifact handoffs, and selected invoice/status paths.
5. The processor publishes Mac-readable response JSON plus machine-proof fields and Guardian output validation.

For workflow-package requests specifically:

1. `workflow_package_request_consumer.py` validates the envelope and authority boundary.
2. Contextual system questions short-circuit into `system_question_answer.py` with no package write.
3. Non-question operator instructions call `workflow_package_queue.create_package`.
4. The queue writes hash-only package inputs, privacy gate rows, intent classification, capability gates, no-op worker result rows, operator-review receipts, and closed business-action gates into `workflow_package_queue.sqlite`.

## Direct Answers

1. Where does LM1 currently exist?

   LM1 exists as LM-shaped contract/read-model logic in `lm_bounded_operator_orchestration.py`, backed by `generated/read_models/lm_bounded_operator_orchestration_latest.json`. Related deterministic substitutes are `deterministic_intent_interpreter.py` and `workflow_package_queue.classify_intent`. No live LM1 planner was found.

2. Is LM1 live, shadow, deterministic substitute, or contract-only?

   Contract-only plus deterministic substitute. The current read model reports `mode=contract_only_no_live_lm`, `model_invoked=false`, `external_provider_connected=false`, and `local_model_runtime_connected=false`.

3. Where does LM2 currently exist?

   LM2 is represented by `generated/read_models/openclaw_lm_child_package_gate.json`, `generated/system_knowledge/openclaw_lm_child_package_gate.sqlite`, `spawned_worker_package_lifecycle.py`, `worker_package_staging.py`, `workroom_review_packet_index.py`, and `workroom_review_decision_consumer.py`.

4. Is LM2 a real worker cage or just package staging/review packet lifecycle?

   It is package staging, child-package gating, no-spawn lifecycle, and review packet lifecycle. It is not a real worker cage in the audited path.

5. What currently creates packages?

   `workflow_package_queue.create_package` creates dry-run workflow packages through `workflow_package_request_consumer.consume_workflow_package_request`. `workflow_composer.py` creates plans only. Mac handoff packages and worker package stubs exist as metadata/staging artifacts, not execution.

6. Where are packages stored?

   Dry-run workflow packages are stored in `generated/system_knowledge/workflow_package_queue.sqlite` and summarized in `generated/read_models/workflow_package_queue_contract.json`. Package events are indexed in `package_event_index.sqlite` and `package_event_index.json`.

7. What validates package authority?

   The authority checks are split across `openclaw_request_router.py`, `workflow_package_request_consumer.py`, `workflow_package_queue.py`, `gate_decision_ledger.py`, `approval_request_queue.py`, `guardian_output_gate.py`, and `harness_provider_selection_registry.py`. All observed authority boundaries keep protected actions false.

8. What prevents false recursive truth?

   Truth must come from source refs, protected hashes, SQLite rows, receipts, gate/approval logs, evidence scoring, or operator-confirmed memory. LM-shaped output can choose or summarize, but it does not become truth by itself.

9. What does the app currently render that should instead be generated dynamically?

   Based on backend payloads, the app currently has to interpret ad hoc fields such as `visible_cards`, `operator_display`, `response_kind`, `primary_status`, `primary_blocker`, `next_action`, proof refs, status tones, and action payloads. These should converge into one backend-generated dynamic card packet.

10. What generic dynamic card schema does the backend need?

    A generic card packet should include card id, request id, world/thread/workflow/client refs, semantic status, truth status, headline, summary, bullets, next safe action, proof refs, receipt refs, gate state, allowed/blocked actions, action payloads, authority boundary, detail disclosure, freshness, confidence, accessibility text, render hints, and content/proof hashes.

11. What can the app eventually strip away?

    Hardcoded client/status card copy, response-kind layout mapping, duplicated action enablement policy, proof disclosure heuristics, and special-case wording for Capital Hilton and St. Anne's.

12. What is the next safest implementation sequence?

    Freeze current deterministic behavior first. Add a backend `dynamic_card_packet` beside existing fields. Populate it for system-question, workflow-package, workroom-review, and workbook-registration rails. Migrate Mac rendering with fallback. Standardize receipts. Keep live LM, worker, and business-action execution blocked until separate gates are test-backed.

## Stage Audit

| Stage | Current State | Evidence | Boundary |
| --- | --- | --- | --- |
| Chat/input envelope | Partial, file-envelope based. | `openclaw_request_response_service.py`, `openclaw_request_processor.py` | Approved inbox only; no broad watch or live execution. |
| Current context envelope | Partial. Context is honored for workflow-package/system-question rails. | `workflow_package_request_consumer.py`, `system_question_answer.py`, `finance_thread_index.json` | Lane metadata identifies context only; it grants no authority. |
| Dynamic PII/privacy gate | Partial. Package queue stores hash-only inputs and privacy rows. | `workflow_package_queue.py`, `workflow_package_queue.sqlite` | Raw text is not stored in package inputs; no provider share. |
| LM1 planner | Contract-only/deterministic substitute. | `lm_bounded_operator_orchestration_latest.json`, `workflow_composer_latest.json` | No model invocation or provider connection. |
| Deterministic package compiler | Exists for workflow-package rail. | `workflow_package_queue.py` | Dry-run/no-op packages only. |
| SQLite/package registry | Exists. | `workflow_package_queue.sqlite`, `package_event_index.sqlite` | Registry writes are proof/status, not execution. |
| Capability/provider gate | Partial. | `capability_gate_results`, `harness_provider_selection_registry.json` | Provider choice does not grant authority. |
| Approval/Gate Decision Ledger | Partial. | `gate_decision_ledger.sqlite`, `approval_request_queue.sqlite` | Approval records do not execute actions. |
| LM2/child-worker cage | Contract-only. | `openclaw_lm_child_package_gate.json`, `spawned_worker_package_lifecycle.json` | No worker spawn or child-agent run. |
| Worker result receipt | Partial. | `worker_results` rows, review receipts | No live worker result receipt found. |
| Review packet index | Exists as read model. | `workroom_review_packet_index.json` | No merge, push, worker spawn, or business action. |
| Operator decision | Partial. | `workroom_review_decision_status.json`, `operator_action_payloads.json` | Review controls only; no executor authority. |
| Business-action gate | Partial/closed. | `business_action_gate_results`, `guardian_output_gate.json` | Send, Coupa, ledger, workbook, PDF, submit, paid, push remain closed. |
| Dynamic operator card/answer | Partial. | response payloads, `operator_card_render_packet_contract.json`, `local_surface_request_contract.json` | Cards render/stage only; no action authority. |
| Memory distillation/promotion | Partial governance layer. | `memory_promotion_gate.json`, `evidence_confidence_scoring.json` | No automatic truth promotion. |

## Important Current Examples

### Finance / Capital Hilton: "What should I do here?"

The request enters as `WORKFLOW_PACKAGE_REQUEST`, but the consumer detects a contextual system question. It calls `system_question_answer.answer_system_question` with `current_world_ref=finance` and `current_thread_ref=capital_hilton`.

Observed answer:

- Headline: `Stay on payment watch`
- Summary: `Coupa is processing. Wait for payment evidence before anything touches the ledger.`
- Next safe action: `Watch for payment proof.`
- No package is recorded.
- No diagnostic workflow package queue route is used.
- No Coupa/browser/ledger action occurs.

### LM-Bounded Capital Hilton Payment Watch

`lm_bounded_operator_orchestration_latest.json` selects `capital_hilton.payment.open_finance` from existing deterministic action payloads. It keeps `safe_to_execute_now=false`, `model_invoked=false`, and `provider_choice_grants_authority=false`.

### Workroom Review Decision

The Workroom review consumer records review decisions only. Allowed controls are review outcomes such as approve-for-record, request-rework, or mark-informational. Merge, push, worker spawn, and business actions remain closed.

### Workbook Registration

The workbook registration rail records metadata-only workbook references. It does not open the workbook, read cells, mutate workbooks, export PDFs, send email, open Coupa, or post ledger entries.

## Differences From The Hypothesis

- The runtime is not one universal linear chain yet.
- The privacy gate is package-queue-specific, not universal.
- LM1 is not live.
- LM2 is not live.
- Package compiler and SQLite package truth exist for the workflow-package rail.
- Business-action gates are closed; no live business-action executor was found.
- Dynamic cards are partial and fragmented, not a single generic backend packet.

## False Recursive Truth

Rule: LM output is never truth by itself.

Accepted truth sources:

- Source file
- Generated read model
- SQLite row
- Receipt
- Hash
- Approval log
- Operator-confirmed memory

Current guards:

- `workflow_package_queue.py` stores protected text hashes and `raw_text_stored=0`.
- `lm_bounded_operator_orchestration.py` can only choose existing deterministic action payloads.
- `system_question_answer.py` reads local read models and SQLite metadata only.
- `evidence_confidence_scoring.py` ranks receipts/hashes/source rows above generated summaries.
- `memory_promotion_gate.py` keeps candidate memory separate from truth promotion.
- `guardian_output_gate.py` validates outgoing response payloads.

Remaining risks:

- Generated summaries can look like truth if proof refs are hidden.
- Approval can be mistaken for execution proof.
- LM-shaped copy can sound authoritative unless `safe_to_execute=false` remains visible.

## What Not To Break

- Approved-inbox bounded pickup and duplicate skipping.
- Fail-closed authority-boundary checks.
- Contextual system-question short-circuiting.
- Hash-only package inputs.
- Closed capability/business-action gates.
- Review-packet separation between worker output and speaker authority.
- Provider selection rule that harness choice does not grant authority.

## Missing Pieces

- Universal runtime envelope across all request families.
- Live LM1 planner.
- Real LM2 worker cage.
- Generic backend card packet.
- Universal receipt envelope.
- Positive business-action executor gate.
- Approval-to-execution bridge.

## Safest Next Sequence

1. Preserve current deterministic rails and tests.
2. Emit a generic backend `dynamic_card_packet` beside existing response fields.
3. Populate that packet for system-question, workflow-package, workroom-review, and workbook-registration rails.
4. Add bridge equality and render parity tests.
5. Standardize receipt envelopes.
6. Keep live LM/worker/business-action activation blocked until privacy, authority, sandbox, receipt, review, and rollback gates are test-backed.

## Validation Boundary

This audit performed no email, Gmail, browser, Coupa, ledger, workbook, PDF, submit, mark-paid, worker, child-agent, service restart, git push, external LLM, or local model runtime action.
