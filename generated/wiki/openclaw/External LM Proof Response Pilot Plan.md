# External LM Proof Response Pilot Plan

Status: EXTERNAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY

This is planning only. It does not invoke an external model, call APIs, read secrets, browse, send prompts, or send proof bundles.

## Purpose

- Compare external LLM response quality against local and shadow response quality.
- Test agent voice, concision, helpfulness, and verifier compatibility.
- Do not test business execution.
- Do not send private proof.

## First Safe Scope

- Scope: `synthetic_finance_capital_hilton_payment_watch`
- Synthetic allowed now: `false`
- Private proof allowed: `false`
- Expected next step: Attach payment evidence

## Synthetic Facts

- payment evidence missing
- payment processor says processing
- ledger untouched
- paid=false
- next safe action: attach payment evidence

## Blocked Data

- `real_private_finance_proof`
- `client_payment_documents`
- `actual_bank_screenshots`
- `raw_email_coupa_gmail_browser_content`
- `workbook_bodies`
- `ledger_rows`
- `credentials_or_tokens`
- `any_unredacted_proof_bundle`

## Candidate External Provider Classes

- `external_llm_blocked_by_default`: invocation `false`, synthetic `false`, private proof `false`
- `model_candidate:external_provider:openai`: invocation `false`, synthetic `false`, private proof `false`
- `model_candidate:external_provider:anthropic`: invocation `false`, synthetic `false`, private proof `false`
- `model_candidate:external_provider:google`: invocation `false`, synthetic `false`, private proof `false`
- `model_candidate:external_provider:mistral`: invocation `false`, synthetic `false`, private proof `false`
- `model_candidate:external_provider:groq`: invocation `false`, synthetic `false`, private proof `false`
- `model_candidate:external_provider:together`: invocation `false`, synthetic `false`, private proof `false`
- `model_candidate:external_provider:openrouter`: invocation `false`, synthetic `false`, private proof `false`
- `model_candidate:external_provider:nvidia_nim`: invocation `false`, synthetic `false`, private proof `false`
- `manual_paste_test_with_synthetic_bundle`: invocation `false`, synthetic `false`, private proof `false`
- `approved_api_test_future_gated`: invocation `false`, synthetic `false`, private proof `false`

## Verifier Requirements

- `proof_to_response_verifier`
- `no_unsupported_paid_sent_submitted_executed_claims`
- `no_authority_grant`
- `no_protected_action_promise`
- `no_machine_contract_jargon`
- `concise_response`
- `allowed_controls_only`

## Operator Decision Options

- `approve_synthetic_external_llm_quality_test`
- `approve_manual_external_llm_test_with_synthetic_bundle`
- `request_more_detail`
- `reject_for_now`

## Proof

- Private proof blocked: `true`
- Verifier mandatory: `true`
- Unsafe true grants absent: `true`
