# Local LM Model Selection Review Packet

Status: LOCAL_LM_MODEL_SELECTION_REVIEW_READY
Packet status: pending_operator_review

This is selection review only. It does not invoke a model, connect a runtime, send a prompt, send a proof bundle, call a provider, read secrets, or grant authority.

## Recommendation

- Candidate: `model_candidate:sidecar:local_llm_shadow_mode`
- Harness: `local_llm_shadow_mode`
- Model: `None`
- Selected for review: `true`
- Invocation allowed: `false`
- Proof bundle allowed: `false`
- Required operator decision: `approve_model_selection_for_one_time_pilot`

## First Pilot Scope

- Lane: `finance/capital_hilton`
- Question: What should I do here?
- Scenario: `finance_capital_hilton_payment_watch`

## Expected Response

- Headline: Payment evidence needed
- Body: Coupa is processing. I can't mark this paid until payment evidence is attached. The ledger stays untouched.
- Next step: Attach payment evidence.

## Candidates Considered

- `model_candidate:sidecar:local_llm_shadow_mode`: Selected for review because it is local/sidecar, already aligned with the shadow pilot path, requires no external provider or API key, and can draft from redacted proof only after explicit approval. Invocation `false`, proof `false`.
- `model_candidate:local_runtime:ollama`: Rejected for invocation now because runtime presence does not prove model boundary, approval, or proof-bundle receipts. Invocation `false`, proof `false`.
- `model_candidate:sidecar:hermes_sidecar`: Rejected for invocation now because Hermes needs explicit proof-to-response registration and receipts. Invocation `false`, proof `false`.
- `model_candidate:operator_assist:codex_desktop_operator_assist`: Rejected for this pilot because operator-assist harnesses require separate scope and proof-bundle approval. Invocation `false`, proof `false`.
- `model_candidate:external_provider:openai`: Rejected external_provider candidate because external providers remain blocked for private finance/client proof. Invocation `false`, proof `false`.
- `model_candidate:external_provider:anthropic`: Rejected external_provider candidate because external providers remain blocked for private finance/client proof. Invocation `false`, proof `false`.
- `model_candidate:external_provider:google`: Rejected external_provider candidate because external providers remain blocked for private finance/client proof. Invocation `false`, proof `false`.
- `model_candidate:external_provider:mistral`: Rejected external_provider candidate because external providers remain blocked for private finance/client proof. Invocation `false`, proof `false`.
- `model_candidate:external_provider:groq`: Rejected external_provider candidate because external providers remain blocked for private finance/client proof. Invocation `false`, proof `false`.
- `model_candidate:external_provider:together`: Rejected external_provider candidate because external providers remain blocked for private finance/client proof. Invocation `false`, proof `false`.
- `model_candidate:external_provider:openrouter`: Rejected external_provider candidate because external providers remain blocked for private finance/client proof. Invocation `false`, proof `false`.
- `model_candidate:external_provider:nvidia_nim`: Rejected external_provider candidate because external providers remain blocked for private finance/client proof. Invocation `false`, proof `false`.

## Required Receipts Before Invocation

- `operator_approval_receipt`
- `model_invocation_boundary_receipt`
- `verifier_pass_fail_receipt`
- `published_response_hash_receipt`

## Stop Conditions

- `model_invocation_attempted_without_operator_approval`
- `runtime_connection_attempted_without_model_boundary_receipt`
- `external_provider_path_appears`
- `proof_bundle_contains_forbidden_field`
- `raw_financial_private_proof_requested_or_exposed`
- `operator_device_session_verification_material_requested_or_exposed`
- `model_claims_paid_sent_submitted_or_executed_without_receipt`
- `model_requests_tool_memory_or_business_authority`
- `verifier_fails`

## Decision Options

- `approve_model_selection_for_one_time_pilot`
- `request_more_detail`
- `choose_different_candidate`
- `reject_for_now`
