# LM2 Room Backed Worker Pilot Operator Approval

Status: `LM2_ROOM_BACKED_WORKER_PILOT_OPERATOR_APPROVAL_READY`

Operator decision recorded: `approve_one_time_room_backed_lm2_worker_pilot`.

This approval is for one future room-backed LM2 worker attempt only. This record does not invoke a model, connect Ollama, spawn a worker, send a prompt, send a proof bundle, open business systems, mutate records, export PDFs, mark paid, submit, or push.

## Approved Scope

- Worker class: `lm2_bounded_worker`
- Runtime: `ollama`
- Model: `qwen3:8b-q4_K_M`
- Lane: `finance/capital_hilton`
- Objective: `payment_watch_response`
- Question: What should I do here?
- Package type: room-backed worker package
- Mode: `proof_to_response_only`
- Attempt limit: one future attempt only
- Verifier: required
- Fallback: required

## Not Authorized

- `repeated_invocations`
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
- `external_provider`
- `file_system_mutation`
- `shell_commands`
- `push_merge`
- `raw_finance_private_proof`
- `operator_device_session_secrets`

## Required Before Future Attempt

- `operator_approval_receipt`
- `room_backed_package_receipt`
- `project_room_readiness_receipt`
- `worker_package_boundary_receipt`
- `model_invocation_boundary_receipt`
- `redacted_proof_bundle_receipt`
- `no_external_provider_receipt`
- `no_tool_authority_receipt`

## Source Refs

- `generated/read_models/lm2_room_backed_worker_pilot_approval_packet.json`
- `generated/read_models/lm2_room_backed_worker_pilot_boundary.json`
- `generated/read_models/project_room_sourceset_contract.json`
- `generated/read_models/project_room_package_compiler_integration.json`
- `generated/read_models/proof_bundle_freshness_trace_status.json`
- `generated/read_models/proof_bundle_builder_redaction_status.json`
- `generated/read_models/proof_to_response_schema_adapter_status.json`
- `generated/read_models/local_model_selection_for_proof_response.json`
