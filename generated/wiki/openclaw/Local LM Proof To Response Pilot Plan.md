# Local LM Proof To Response Pilot Plan

Status: LOCAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY
Ready for operator approval: `true`
Ready for live invocation: `false`

This plan chooses the first local/approved proof-to-response pilot without invoking a model or connecting any runtime.

## First Pilot Lane

- `finance/capital_hilton`: Preferred first lane because it has low action risk, strong proof boundaries, no business execution, and a simple expected response.
- Expected response: Payment evidence is missing. Ledger stays untouched. Next: attach payment evidence.

## Allowed LM Input

- `world_ref`
- `thread_ref`
- `objective_ref`
- `redacted_known_facts`
- `proof_meter_labels`
- `receipt_refs`
- `gate_labels`
- `missing_input`
- `allowed_controls`
- `blocked_action_summaries`
- `human_safe_summaries`
- `agent_voice_mode`

## Candidate Sources

- `local_llm_shadow_mode`: allowed `false`, reason `blocked_until_operator_approval_and_live_boundary_receipts`
- `future_local_open_model`: allowed `false`, reason `future_model_not_selected_or_approved`
- `hermes_sidecar_candidate`: allowed `false`, reason `blocked_until_explicit_registration_and_receipts`
- `codex_desktop_operator_assist`: allowed `false`, reason `blocked_until_explicit_codex_desktop_assist_approval`
- `external_llm_blocked_by_default`: allowed `false`, reason `external_provider_blocked_by_default`

## Required Receipts

- `operator_approval_receipt`
- `model_harness_selected_receipt`
- `no_external_provider_receipt`
- `redacted_proof_bundle_receipt`
- `no_tool_authority_receipt`
- `verifier_pass_fail_receipt`
- `published_response_hash_receipt`

## Stop Conditions

- `model_claims_paid_sent_submitted`
- `model_asks_for_hidden_or_prohibited_context`
- `model_leaks_machine_contract_jargon`
- `model_proposes_protected_action`
- `verifier_fails`
- `proof_bundle_contains_forbidden_field`
- `external_provider_path_appears`

## Proof

- Verifier mandatory: `true`
- Unsafe true grants absent: `true`
