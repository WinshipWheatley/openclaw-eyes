# LM2 Structured Output Retry Operator Approval

Status: `LM2_STRUCTURED_OUTPUT_RETRY_OPERATOR_APPROVAL_READY`

Operator decision recorded: `approve_one_time_room_backed_lm2_structured_output_retry`.

This approval is for one future room-backed LM2 retry attempt only, using structured-output enforcement. This record does not invoke a model, connect Ollama, spawn a worker, send a prompt, send a proof bundle, open business systems, mutate records, export PDFs, mark paid, submit, or push.

## Approved Scope

- Worker class: `lm2_bounded_worker`
- Runtime: `ollama`
- Model: `qwen3:8b-q4_K_M`
- Lane: `finance/capital_hilton`
- Objective: `payment_watch_response`
- Question: What should I do here?
- Package type: room-backed worker package
- Mode: `proof_to_response_only`
- Structured output: required
- Schema adapter: required
- Verifier: required
- Fallback: required
- Attempt limit: one future retry attempt only

## Not Authorized

- `repeated_invocations`
- `external_provider`
- `tool_use`
- `browser_gmail_coupa`
- `email_send`
- `send`
- `submit`
- `ledger_mutation`
- `workbook_mutation`
- `pdf_export`
- `paid_marking`
- `memory_promotion`
- `worker_spawning_beyond_this_one_future_attempt`
- `file_system_mutation`
- `shell_commands`
- `push_merge`
- `raw_finance_private_proof`
- `operator_device_session_secrets`
- `stale_source_as_current_truth`

## Required Before Future Retry

- `operator_approval_receipt`
- `structured_output_boundary_receipt`
- `room_backed_package_receipt`
- `project_room_readiness_receipt`
- `model_invocation_boundary_receipt`
- `redacted_proof_bundle_receipt`
- `no_external_provider_receipt`
- `no_tool_authority_receipt`

## Required After Future Retry

- `worker_started_receipt`
- `model_invocation_attempt_receipt`
- `raw_draft_captured_receipt`
- `schema_adapter_pass_fail_receipt`
- `worker_stopped_receipt`
- `verifier_pass_fail_receipt`
- `published_response_hash_receipt_or_fallback_receipt`
- `no_business_action_receipt`

## Source Refs

- `generated/read_models/lm2_structured_output_retry_approval_packet.json`
- `generated/read_models/lm2_room_backed_worker_pilot_postmortem.json`
- `generated/read_models/lm2_room_backed_worker_one_time_pilot.json`
- `generated/read_models/project_room_package_compiler_integration.json`
- `generated/read_models/proof_to_response_schema_adapter_status.json`
- `generated/read_models/proof_bundle_freshness_trace_status.json`
- `generated/read_models/proof_bundle_builder_redaction_status.json`
