# LM2 Live Worker Pilot Boundary Packet

Status: LM2_LIVE_WORKER_PILOT_BOUNDARY_READY
Packet status: pending_operator_review

This is review-only. It does not spawn a worker, invoke a model, send a prompt, send a proof bundle, or grant authority.

## Pilot Scope

- Worker class: `lm2_bounded_worker`
- Runtime: `ollama`
- Model: `qwen3:8b-q4_K_M`
- Lane: `finance/capital_hilton`
- Objective: `payment_watch_response`
- Question: What should I do here?
- Mode: `proof_to_response_only`

## Authority

- Invocation allowed: `false`
- Worker spawn allowed: `false`
- Proof bundle allowed: `false`

## Allowed Worker Input

- `redacted_freshness_gated_proof_bundle`
- `agent_voice_mode`
- `required_json_response_schema`
- `expected_response_example`
- `stop_conditions`
- `verifier_requirements`

## Forbidden Worker Input

- `raw_financial_proof`
- `bank_or_account_details`
- `credentials_or_tokens`
- `operator_device_session_verification_secrets`
- `raw_prompt_dumps`
- `raw_ocr_or_artifact_text`
- `workbook_bodies`
- `email_bodies`
- `ledger_bodies`
- `hidden_machine_contracts`
- `authority_granted_fields`

## Worker Capabilities

Allowed:
- `read_provided_redacted_proof_bundle`
- `draft_one_json_proof_to_response_candidate`
- `return_candidate_to_verifier`
- `stop`

Forbidden:
- `tool_use`
- `browser_gmail_coupa`
- `email_send`
- `submit`
- `ledger_mutation`
- `workbook_mutation`
- `pdf_export`
- `paid_marking`
- `memory_promotion`
- `worker_spawning`
- `external_provider`
- `file_system_mutation`
- `shell_commands`
- `repeated_invocations`

## Stop Conditions

- `proof_bundle_contains_forbidden_field`
- `context_freshness_stale_superseded_or_unknown`
- `model_returns_non_json`
- `model_claims_paid_sent_submitted_or_executed`
- `model_promises_protected_action`
- `model_asks_for_hidden_private_context`
- `model_attempts_tool_use`
- `model_exceeds_one_attempt`
- `verifier_fails`

## Operator Decision Options

- `approve_one_time_lm2_worker_pilot`
- `request_more_detail`
- `reject_for_now`
