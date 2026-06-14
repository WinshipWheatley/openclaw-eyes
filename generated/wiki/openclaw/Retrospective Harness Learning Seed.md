# Retrospective Harness Learning Seed

Status: RETROSPECTIVE_HARNESS_LEARNING_SEED_READY

This is a review-only learning seed. It records failure classes, decision traces, and candidate harness updates without invoking models or changing runtime behavior.

## Trajectory Sources

- `controller_events`: Verified controller gestures, selected card/action refs, world/thread context, and route outcomes.
- `proof_to_response_attempts`: Candidate response attempts, adapter results, verifier results, and published fallback decisions.
- `verifier_failures`: Deterministic rejection reasons from proof-to-response verifier and schema adapter.
- `fallback_receipts`: Receipts proving a safe fallback was published when a draft was blocked.
- `workroom_review_decisions`: Review decisions such as informational, request rework, approve, or deny.
- `operator_session_timeline`: Scene-level timeline events across worlds, lanes, cards, receipts, evidence, and review decisions.
- `self_heal_repair_records`: Repair packages, blockers, validation results, and manual operator steps.
- `stale_context_blocks`: Context freshness decisions that blocked stale, superseded, generated-only, or untraceable truth.
- `local_external_lm_synthetic_test_outcomes`: Synthetic local/external LM quality trials, postmortems, verifier outcomes, and fact-ID alignment checks.

## Failure Classes

- `stale_context`: A response or card relied on historical, superseded, unresolved, or untraceable context as if it were current.
- `non_json_model_output`: A model response failed the required JSON/schema shape before factual verification could run.
- `unsupported_claim`: A draft claimed paid, sent, submitted, executed, or another fact not supported by current proof.
- `wrong_lane_response`: A response was safe in isolation but scoped to the wrong world, thread, card, gate, or objective.
- `missing_proof`: The requested outcome needs evidence, receipt, or approval that is absent.
- `overbroad_context`: Too much raw, private, or unrelated context entered a prompt, composer, or proof bundle.
- `protected_action_attempt`: A route or draft tried to execute or promise a protected action without the required gate.
- `tool_not_allowed`: A path needed or attempted a tool/runtime/resource outside the current authority boundary.
- `premature_completion`: A task, response, or card marked work complete before proof, receipt, or validation supported completion.
- `repeated_work_without_new_proof`: The system retried the same path without new evidence, changed context, or a new validation result.
- `card_or_ui_dominance_over_text`: A card, UI control, or machine contract became the primary operator response instead of concise proof-grounded text.
- `context_scope_leak`: A local path, stale lane, unrelated proof detail, or raw context crossed into a response or composer outside its allowed scope.

## Required Examples

- `local_qwen_non_json_failure` (non_json_model_output): The saved draft did not satisfy the required JSON response shape, so schema adaptation/verifier publication failed before factual truth checks could pass.
- `finance_payment_watch_wrong_coupa_gate_routing` (wrong_lane_response): The gate response was safe but scoped too narrowly to protected Coupa submit detail rather than the payment-watch lane.
- `evidence_picker_file_path_leak_into_composer` (context_scope_leak): The composer needed a protected artifact ref or redacted summary, not a raw path that could expose private machine context.
- `stale_build_review_packet_ready_for_review` (stale_context): Lifecycle and freshness state were not treated as the primary context gate for the card/response.
- `proof_to_response_wrong_lane_linger` (wrong_lane_response): The latest read model lacked sufficient request-scoped freshness and context fields, so stale lane state could linger.
- `external_synthetic_fact_id_mismatch` (unsupported_claim): The verifier found the cited fact ID did not match the proof-bundle fact IDs, so the claim could not be grounded.
- `remote_desktop_trace_log_leak_self_heal` (tool_not_allowed): Raw trace logs are noisy and can leak resource, path, or session details if treated as operator-facing memory.

## Context Maintenance

- `stale_context_should_be_demoted`: Stale or unknown context becomes Needs verification or historical support, not current truth.
- `superseded_receipts_excluded`: Superseded receipts stay available in trace but cannot enter LM bundles as current truth.
- `summaries_cannot_override_receipts`: Generated summaries are explanations only; receipts, hashes, and source rows define truth.
- `old_tool_output_logs_compacted`: Old tool output/logs should be compacted to high-signal blocker, validation, and receipt summaries.
- `high_signal_lessons_preserved`: Preserve failure class, proof, operator decision, receipt, validation, and recurrence signal.
- `raw_history_hidden_unless_requested`: Raw prompts, logs, file paths, private proof, and trace dumps remain hidden unless explicitly requested and allowed.

## Candidate Updates

- `retrospective_update:01:local_qwen_non_json_failure` -> proof_to_response_schema_adapter: Add JSON-only prompt/schema adapter fixture checks before any approved local model retry. (review required: true, auto apply: false)
- `retrospective_update:02:finance_payment_watch_wrong_coupa_gate_routing` -> operator_controller_event_router: Prefer lane-level payment-watch intent when selected context is current-focus/payment-watch; keep Coupa gate detail scoped to gate controls. (review required: true, auto apply: false)
- `retrospective_update:03:evidence_picker_file_path_leak_into_composer` -> proof_bundle_builder: Normalize composer-visible evidence references to artifact refs and redacted summaries. (review required: true, auto apply: false)
- `retrospective_update:04:stale_build_review_packet_ready_for_review` -> dynamic_card_lifecycle_policy: Gate Build review visibility on lifecycle/freshness state and latest review decision receipt. (review required: true, auto apply: false)
- `retrospective_update:05:proof_to_response_wrong_lane_linger` -> proof_to_response_runtime: Require request-scoped proof_to_response in every controller response and mark latest stale if context mismatches. (review required: true, auto apply: false)
- `retrospective_update:06:external_synthetic_fact_id_mismatch` -> proof_to_response_verifier: Add fact-ID alignment checks between synthetic response claims and proof-bundle facts before publication. (review required: true, auto apply: false)
- `retrospective_update:07:remote_desktop_trace_log_leak_self_heal` -> self_heal_repair_doctrine: Summarize trace logs into blocker/proof/validation receipts and keep raw trace material behind developer proof. (review required: true, auto apply: false)

## Selection Policy

- Full RHO enabled: `false`
- Candidates are selected by difficulty, recurrence, diversity, operator friction, and safety relevance.
- Candidate updates require review and cannot auto-apply.
