# LM2 Room Backed Worker Pilot Boundary

Status: LM2_ROOM_BACKED_WORKER_PILOT_BOUNDARY_READY

This is boundary/read-model work only. It requires a room-backed worker package before any future LM2 pilot and does not invoke LM2, connect Ollama, spawn a worker, send a prompt, or send a proof bundle.

## Pilot Scope

- Worker class: `lm2_bounded_worker`
- Runtime: `ollama`
- Model: `qwen3:8b-q4_K_M`
- Lane: `finance/capital_hilton`
- Objective: `payment_watch_response`
- Question: What should I do here?
- Mode: `proof_to_response_only`

## Required Package Refs

- `project_room_id`: `finance_capital_hilton_payment_watch`
- `source_inventory_ref`: `source_inventory:finance_capital_hilton_payment_watch`
- `conflict_log_ref`: `conflict_log:finance_capital_hilton_payment_watch`
- `missing_context_ref`: `missing_context:finance_payment_evidence`
- `duplicate_report_ref`: `version_family:finance_payment_watch`
- `decision_trace_ref`: `decision_trace:finance_capital_hilton_payment_watch`
- `freshness_gate_ref`: `freshness_gate:receipt_current_or_needs_verification`
- `compaction_policy_ref`: `generated/read_models/context_compaction_preview_policy.json`
- `redacted_proof_bundle_ref`: `generated/read_models/proof_bundle_freshness_trace_status.json#finance_capital_hilton_payment_watch_redacted`
- `authority_boundary_ref`: `lm2_room_backed_worker_pilot_boundary:authority_boundary:v1`
- `receipt_requirement_ref`: `lm2_room_backed_worker_pilot_boundary:receipt_requirements:v1`

## Allowed Worker Input

- `redacted_freshness_gated_proof_bundle`
- `current_lane_summary`
- `source_inventory_summary`
- `missing_context_summary`
- `decision_trace_summary`
- `proof_meter_labels`
- `allowed_controls`
- `blocked_action_summaries`
- `required_json_response_schema`
- `one_valid_json_example`
- `stop_conditions`

## Forbidden Worker Input

- `raw_messy_folder_dump`
- `full_logs_or_artifacts_by_default`
- `raw_financial_proof`
- `bank_or_account_details`
- `credentials_or_tokens`
- `operator_device_session_verification_secrets`
- `raw_prompt_dumps`
- `raw_ocr_or_artifact_text`
- `workbook_email_or_ledger_bodies`
- `hidden_machine_contracts`
- `authority_granted_fields`
- `stale_source_as_current_truth`
- `duplicate_versions_as_equal_evidence`
- `missing_context_as_permission_to_invent`

## Stop Conditions

- `project_room_not_ready`
- `source_inventory_missing`
- `unresolved_critical_conflict`
- `missing_context_blocks_supported_claim`
- `freshness_stale_superseded_or_unknown`
- `proof_bundle_contains_forbidden_field`
- `model_returns_non_json`
- `model_claims_paid_sent_submitted_or_executed`
- `model_promises_protected_action`
- `model_asks_for_hidden_private_context`
- `model_attempts_tool_use`
- `model_exceeds_one_attempt`
- `verifier_fails`

## Rules

- invocation_allowed=false
- worker_spawn_allowed=false
- proof_bundle_allowed=false
- room_backed_package_required=true
- project_room_ready_required=true
- this packet is not approval
- this packet does not run LM2
