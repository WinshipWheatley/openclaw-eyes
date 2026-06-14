# Operator Runtime Chain Current State Audit

Status: `OPERATOR_RUNTIME_CHAIN_CURRENT_STATE_AUDIT_READY`
Generated: `2026-06-05T00:44:20Z`

Mode: read-only current-state audit. This report tests the proposed chain against current code, read models, and SQLite metadata. It does not design or implement a new chain.

## Current Actual Chain

- OpenClaw currently has a bounded Mission Control request-file service.
- It classifies approved request files, routes them through deterministic local rails, writes heartbeat/response readbacks, and uses read models/SQLite receipts for selected rails.
- The LM and worker stages are mostly contract-only, LM-shaped selection, package staging, no-op worker receipts, and review packet lifecycle, not live model or worker execution.

## Stage Rows

### Mission Control request input
- currently_exists: `true`
- implementation_type: `deterministic`
- primary_files: `openclaw_request_response_service.py, openclaw_request_processor.py`
- input_shape: JSON request files in /mnt/e/openclaw/mission_control_capture_requests/inbox with request id/idempotency metadata, source surface, and typed payload fields.
- output_shape: Candidate selection, processing heartbeat, then response JSON in /mnt/e/openclaw/mission_control_responses/to_mac.
- SQLite involvement: None at file pickup; downstream handlers may write generated/system_knowledge SQLite.
- read_model involvement: `openclaw_request_response_service_status.json, openclaw_request_processor_status.json, openclaw_response_for_mac.json`
- receipt/proof output: Processing heartbeat, terminal Mac response JSON, service status processed-key evidence.
- authority boundary: Inbound authority is denied unless a deterministic handler explicitly permits a safe local action; protected actions stay false.
- known failure modes: filename family unsupported, malformed JSON, duplicate idempotency/scoped response, missing required fields
- confidence: `high`
- notes: Mission Control enters through bridge files, not a direct in-process app call.

### Request classification and router dispatch
- currently_exists: `true`
- implementation_type: `deterministic`
- primary_files: `openclaw_request_processor.py, openclaw_request_router.py, openclaw_request_response_service.py`
- input_shape: Request path plus JSON envelope; filename patterns and request_type/kind identify workflow package, workroom review, workbook registration, chat, file intake, and related families.
- output_shape: Selected request family/handler or blocked unsupported response.
- SQLite involvement: None in router dispatch.
- read_model involvement: `openclaw_request_router.json, openclaw_request_processor_status.json`
- receipt/proof output: Response detail fields include selected handler/classification and why_it_happened.
- authority boundary: Router/processor scan authority_boundary and performed-action flags, then block unsafe true grants.
- known failure modes: safe Mac envelope shape not aliased, handler not listed in service supported families, family-specific preflight mismatch
- confidence: `high`
- notes: The Workroom review repair showed that request_type aliases and filename families are operationally important.

### Context and lane enrichment
- currently_exists: `partial`
- implementation_type: `deterministic`
- primary_files: `workflow_package_request_consumer.py, system_question_answer.py, package_event_index.py, operator_next_decision.py`
- input_shape: Request fields such as current_world_ref, current_thread_ref, target_world_ref, target_thread_ref, source_surface, and local read-model refs.
- output_shape: Lane-biased operator_display, system-question answer, next-decision/action summary, or cross-lane route note.
- SQLite involvement: SQLite supplies metadata/proof in system_question_answer and package_event_index, but there is no universal context DB.
- read_model involvement: `package_event_index.json, operator_conversation_journal.json, operator_next_decision.json, system_question_answer_contract.json`
- receipt/proof output: Proof refs to read models/SQLite paths; raw conversation bodies are not primary operator text.
- authority boundary: Context identifies lane/thread only; it grants no send, ledger, workbook, worker, model, or provider authority.
- known failure modes: missing lane context, stale generated read model, context conflict handled narrowly by request family
- confidence: `medium-high`
- notes: The hypothesized single context layer is not a unified runtime component yet.

### Privacy and PII gate
- currently_exists: `partial`
- implementation_type: `deterministic`
- primary_files: `workflow_package_queue.py, workflow_package_request_consumer.py, openclaw_request_processor.py, gate1_privacy_request_readiness.py`
- input_shape: Source text, source_surface, request family, authority_boundary, and provider/model eligibility context.
- output_shape: privacy_gate_result rows, protected_text_hash package records, local_only answer policy, or blocked preflight.
- SQLite involvement: workflow_package_queue.sqlite stores privacy_gate_results and package_inputs with protected_text_hash/raw_text_stored=0.
- read_model involvement: `gate1_privacy_request_readiness.json, workflow_package_queue_contract.json, local_llm_intent_privacy_upgrade_plan.json`
- receipt/proof output: Package records include privacy impact/protected hash; system-question answers report local_only.
- authority boundary: Privacy handling does not authorize external providers, raw body disclosure, or model invocation.
- known failure modes: rule-based rather than live dynamic PII classifier, non-package rails rely on separate preflight/read-model policy
- confidence: `medium`
- notes: Privacy exists, but it is not yet a single mandatory first stage for every request family.

### LM planner / intent-to-machine-contract layer
- currently_exists: `partial`
- implementation_type: `lm_shaped_contract`
- primary_files: `lm_bounded_operator_orchestration.py, workflow_composer.py, deterministic_intent_interpreter.py, system_question_answer.py, machine_intent_candidate_validator.py`
- input_shape: Local read models, deterministic action payloads, lane context, and example prompts/questions.
- output_shape: LM-shaped contract read models, deterministic candidate choices, local-only system answers, and plan-only workflow composer outputs.
- SQLite involvement: No live model runtime SQLite in the current chain; shadow/readiness SQLite exists as test-harness state only.
- read_model involvement: `lm_bounded_operator_orchestration_latest.json, workflow_composer_latest.json, deterministic_intent_interpreter.json, live_lm_readiness_gate.json`
- receipt/proof output: Read models explicitly state contract_only_no_live_lm, model_invoked=false, provider_connected=false.
- authority boundary: model_invocation_allowed=false, external_provider_connect_allowed=false, local_model_runtime_allowed=false, worker_spawn_allowed=false.
- known failure modes: LM-shaped copy can look like live reasoning, candidate plans can become stale if treated as canonical truth
- confidence: `high`
- notes: LM-shaped does not mean a live LM is running.

### Deterministic package compiler
- currently_exists: `true`
- implementation_type: `deterministic`
- primary_files: `workflow_package_request_consumer.py, workflow_package_queue.py`
- input_shape: WORKFLOW_PACKAGE_REQUEST_V0 envelope with source text, source surface, target/current lane refs, requested workflow, and false authority flags.
- output_shape: Package object with package_id, workflow_ref, privacy/capability/business gates, no-op worker assignment/result, and operator-review receipt.
- SQLite involvement: Writes workflow_package_queue.sqlite packages, package_inputs, privacy_gate_results, intent_classification_results, capability_gate_results, worker_assignments, worker_results, operator_review_receipts, and business_action_gate_results.
- read_model involvement: `workflow_package_queue_contract.json, workflow_package_request_consumer_status.json`
- receipt/proof output: Consumer receipt/operator_display and normalized package/gate rows.
- authority boundary: Unsafe true grants block; business_action_gate is closed by default.
- known failure modes: unsupported workflow_ref, capability gate block, dry-run package misread as worker execution
- confidence: `high`
- notes: This is the strongest real match for the hypothesized compiler/package registry stage.

### SQLite/package registry truth
- currently_exists: `true`
- implementation_type: `deterministic`
- primary_files: `workflow_package_queue.py, package_event_index.py, sqlite_governance_registry.py`
- input_shape: Package records, request/response refs, journal refs, source read models, and generated receipt refs.
- output_shape: SQLite package/gate rows plus compact package_event_index rows and read model.
- SQLite involvement: workflow_package_queue.sqlite is package truth; package_event_index.sqlite indexes refs; gate_decision_ledger.sqlite and approval_request_queue.sqlite are governance truth, not package truth.
- read_model involvement: `package_event_index.json, sqlite_governance_registry.json, backend_queue_recovery_status.json`
- receipt/proof output: Rows and refs/hashes/summaries; raw prompt bodies are not dumped.
- authority boundary: Indexing does not create business action, sent, paid, or ledger truth.
- known failure modes: duplicate package concepts across DBs, summary mistaken for source truth, dirty SQLite from live service activity
- confidence: `high`
- notes: The business ledger is deliberately excluded from package truth.

### Capability and authority gates
- currently_exists: `true`
- implementation_type: `deterministic`
- primary_files: `openclaw_request_processor.py, openclaw_request_router.py, workflow_package_request_consumer.py, workflow_package_queue.py, gate_decision_ledger.py, approval_request_queue.py, operator_action_payloads.py`
- input_shape: Requested action, request family, authority_boundary, performed flags, workflow_ref, target lane, and gate refs.
- output_shape: Blocked/allowed/approval_required decision records, pending approval rows, disabled action payloads, and Guardian/Chief display responses.
- SQLite involvement: workflow_package_queue.sqlite stores capability/business gates; gate_decision_ledger.sqlite stores decisions; approval_request_queue.sqlite stores pending approvals.
- read_model involvement: `gate_decision_ledger.json, approval_request_queue.json, operator_action_payloads.json, automation_permission_registry.json`
- receipt/proof output: Gate rows, approval rows, response blockers, disabled_reason fields.
- authority boundary: Protected actions remain false: email, Coupa, ledger, workbook mutation, PDF export, paid, submit, push, worker spawn, external provider, live model.
- known failure modes: approval queue mistaken for executor, enabled UI action mistaken for authority
- confidence: `high`
- notes: Action payload exists does not mean action authority exists.

### LM2 / child LM / worker cage
- currently_exists: `partial`
- implementation_type: `contract_only`
- primary_files: `worker_package_staging.py, spawned_worker_package_lifecycle.py, openclaw_lm_child_package_gate.py, agent_handoff_event_consumer.py`
- input_shape: Handoff event, worker_ref, package stub fields, lifecycle state, and review packet refs.
- output_shape: Worker package stubs, lifecycle contracts, example review packet entries, handoff receipts/activity posts.
- SQLite involvement: openclaw_lm_child_package_gate.sqlite stores policy/contract/receipt-shaped rows, not live worker execution truth.
- read_model involvement: `worker_package_staging_status.json, spawned_worker_package_lifecycle.json, openclaw_lm_child_package_gate.json, agent_handoff_event_status.json`
- receipt/proof output: Staging/status receipts require result_receipt_required=true; staging itself is not worker output.
- authority boundary: worker_spawn_allowed=false, child_agent_run_allowed=false, external_llm_allowed=false, git_push_allowed=false.
- known failure modes: package staged misread as worker executed, speaker authority accidentally inferred for worker, example review packet mistaken for live result
- confidence: `high`
- notes: Package staged does not mean worker executed.

### Receipts and proof output
- currently_exists: `true`
- implementation_type: `deterministic`
- primary_files: `openclaw_request_processor.py, openclaw_request_response_service.py, workflow_package_request_consumer.py, workroom_review_decision_consumer.py, agent_handoff_event_consumer.py, package_event_index.py`
- input_shape: Handler receipt/result object, readback files, package refs, decision refs, and source request refs.
- output_shape: Bridge response JSON, local read-model updates, package_event_index rows, and collapsed proof refs.
- SQLite involvement: Receipts may be stored/indexed in workflow_package_queue.sqlite, package_event_index.sqlite, and governance SQLite files.
- read_model involvement: `workroom_review_decision_status.json, package_event_index.json, openclaw_request_response_service_status.json`
- receipt/proof output: Response files under /mnt/e/openclaw/mission_control_responses/to_mac plus generated read models.
- authority boundary: Receipts prove local deterministic handler output only; no protected business execution is implied without executor receipt.
- known failure modes: summary replaces receipt in UI, latest response mirror overwritten by later request, stale read model persists
- confidence: `high`
- notes: Receipts are stronger evidence than generated narrative text.

### Operator review
- currently_exists: `partial`
- implementation_type: `deterministic`
- primary_files: `workroom_review_packet_index.py, workroom_review_decision_consumer.py, operator_action_payloads.py, approval_request_queue.py, operator_next_decision.py`
- input_shape: Review packet id, action payload, decision_action approve/request_rework/mark_informational, and pending approval records.
- output_shape: Decision receipt/status, actionability/next-decision surfaces when regenerated, compact workroom activity posts.
- SQLite involvement: Approval requests are SQLite-backed; Workroom review decisions are generated read-model receipts.
- read_model involvement: `workroom_review_packet_index.json, workroom_review_decision_status.json, operator_action_payloads.json, operator_next_decision.json`
- receipt/proof output: Workroom review decision receipts with no_merge/no_push/no_business_action true.
- authority boundary: Review records a decision only; merge, push, send, ledger, workbook, PDF, Coupa, paid remain false.
- known failure modes: packet still visible until lifecycle refresh, approval-for-record misread as merge/push authority
- confidence: `high`
- notes: The exact Mac mark_review_packet_informational request now has response proof and status history.

### Business-action gate
- currently_exists: `true`
- implementation_type: `deterministic`
- primary_files: `workflow_package_queue.py, gate_decision_ledger.py, approval_request_queue.py, operator_action_payloads.py, automation_permission_registry.py`
- input_shape: Protected action request or package with possible business effect.
- output_shape: Closed gate, blocked gate, approval_required item, or disabled action payload.
- SQLite involvement: workflow_package_queue.sqlite business_action_gate_results, gate_decision_ledger.sqlite, approval_request_queue.sqlite.
- read_model involvement: `gate_decision_ledger.json, approval_request_queue.json, automation_permission_registry.json`
- receipt/proof output: Gate rows and approval request rows record decisions only.
- authority boundary: No send/submit/ledger/workbook/PDF/paid authority is granted by read models or approval queues.
- known failure modes: approval existence mistaken for execution, payment proof intake enabled before evidence
- confidence: `high`
- notes: The current gate system is conservative and should be preserved.

### Dynamic app cards and answers
- currently_exists: `partial`
- implementation_type: `deterministic`
- primary_files: `openclaw_request_processor.py, operator_action_payloads.py, system_question_answer.py, operator_controller_protocol.py`
- input_shape: Handler result, operator_display, visible_cards, layered_response_fields, spoken_response_packet, visual_event_package, and action payloads.
- output_shape: Bridge response JSON and read models consumed by Mac/Helm surfaces.
- SQLite involvement: Indirect only through read models and system-question SQLite metadata.
- read_model involvement: `operator_action_payloads.json, operator_controller_protocol.json, operator_next_decision.json, system_question_answer_contract.json, openclaw_response_for_mac.json`
- receipt/proof output: Response files include display/card fields and proof refs collapsed by default.
- authority boundary: UI card/action visibility is not backend action authority.
- known failure modes: Mac hardcodes some lane card logic, mixed response shapes, stale action card noise
- confidence: `medium`
- notes: Backend payloads are dynamic fragments; operator_controller_protocol is additive protocol evidence, not a runtime executor.

### Memory/evidence/canonical truth controls
- currently_exists: `partial`
- implementation_type: `deterministic`
- primary_files: `evidence_confidence_scoring.py, operator_memory_distillation.py, memory_promotion_gate.py, canonical_state_map.py`
- input_shape: Receipts, artifact refs, generated summaries, memory candidates, and canonical state entries.
- output_shape: Confidence labels, memory candidates, promotion gate records, and canonical truth map.
- SQLite involvement: No single memory SQLite truth store in this audited path; journal/package/artifact SQLite can supply proof refs.
- read_model involvement: `evidence_confidence_scoring.json, operator_memory_distillation.json, memory_promotion_gate.json, canonical_state_map.json`
- receipt/proof output: Proof refs attached to facts/memories; promotion_status remains candidate unless approved.
- authority boundary: Memory cannot promote itself into canonical business truth; generated summaries cannot override receipts.
- known failure modes: candidate memory treated as canonical, generated summary treated as stronger than receipt
- confidence: `medium-high`
- notes: Memory exists does not mean canonical truth.

## Differences From Hypothesis
- The current runtime is not a single linear universal chain; it is a request-family router with separate deterministic rails.
- The privacy gate exists as hash-only package-queue privacy rows, not a universal dynamic PII gate before every rail.
- LM1 is not live; it is contract-only/deterministic selection over existing action payloads.
- The package compiler exists for the workflow-package rail, not every request family.
- SQLite package truth exists, but only selected rails have SQLite-backed canonical rows.
- Capability/provider gate exists as dry-run gate rows and registry read models, not a live provider executor.
- LM2/worker cage is not live; it is child-package gate contracts, package stubs, and review lifecycle.
- Worker receipts are no-op/offline/rail-specific, not live worker cage receipts.
- Business-action gates are closed by default; no live executor was found.
- Dynamic cards are partial and fragmented; a generic card packet is still needed.

## False Recursive Truth Audit
- Rule: LM output is never truth by itself.
- Remaining risk: Ad hoc response/card fields may make generated summaries look like app truth if not paired with explicit proof refs.
- Remaining risk: Approval records can be mistaken for execution proof unless card copy separates approval, execution, and receipt.
- Remaining risk: LM-shaped recommendation copy can sound authoritative unless safe_to_execute and provider_choice_grants_authority stay visible.

## Safest Next Sequence
- Step 1: Freeze existing request-response, workflow-package, system-question, workroom-review, and workbook-registration behavior with focused regression tests.
- Step 2: Add backend dynamic_card_packet as an additive field beside existing visible_cards/operator_display fields.
- Step 3: Populate dynamic_card_packet for system-question, workflow-package, workroom-review, and workbook-registration rails first.
- Step 4: Add bridge equality and Mac-render smoke tests that compare old card content to new card packets.
- Step 5: Only after dynamic cards are stable, define a universal receipt envelope shared by package, approval, review, and future worker rails.
- Step 6: Keep live LM/worker/business-action activation blocked until privacy, authority, sandbox, receipt, review, and rollback gates are test-backed.

## Authority Boundary

All protected authority flags remain false. This audit did not mutate runtime code, service state, business state, ledger, workbook, email, browser/Coupa/Gmail, workers, model runtimes, or git remote state.

Status: `OPERATOR_RUNTIME_CHAIN_CURRENT_STATE_AUDIT_READY`
