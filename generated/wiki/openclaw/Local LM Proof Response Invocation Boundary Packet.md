# Local LM Proof Response Invocation Boundary Packet

Status: LOCAL_LM_PROOF_RESPONSE_INVOCATION_BOUNDARY_PACKET_READY
Packet status: pending_operator_review

This is review-only. It does not invoke a model, contact Ollama, send a prompt, send a proof bundle, grant authority, or create an execution path.

## Selected Model

- Runtime: `ollama`
- Model ref: `local_model:ollama:qwen3_8b-q4_k_m`
- Model name: `qwen3:8b-q4_K_M`
- Invocation allowed: `false`
- Proof bundle allowed: `false`

## Pilot Boundary

- Lane: `finance/capital_hilton`
- Question: What should I do here?
- Expected response: Payment evidence is missing. Coupa is processing. The ledger stays untouched. Next: attach payment evidence.
- Candidate source mode: `future_live_local_lm_pending_approval`

## Runtime Contact Method

- Recommended method: `ollama_cli_one_shot_stdin_after_operator_approval`
- Command template, not executed: `ollama run qwen3:8b-q4_K_M`
- Contact allowed now: `false`
- Reason: Recommended for the first pilot because it is local-only, names the exact model, keeps the first invocation surface small, and avoids expanding to an HTTP endpoint until a later approval explicitly chooses that path.

## Allowed Input

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
- `freshness_state`
- `confidence_class`
- `decision_trace_summary`

## Forbidden Input

- `raw_bank_or_account_details`
- `credentials_or_tokens`
- `operator_device_session_verification_secrets`
- `raw_prompt_dumps`
- `raw_artifact_or_ocr_text`
- `full_workbook_contents`
- `source_workbook_bodies`
- `raw_email_bodies`
- `raw_ledger_rows`
- `hidden_machine_contracts`
- `incoming_authority_granted_fields`

## Stop Conditions

- `proof_bundle_contains_forbidden_field`
- `context_freshness_is_stale_superseded_or_unknown`
- `runtime_or_model_mismatch`
- `model_asks_for_hidden_context`
- `model_claims_paid_sent_submitted_or_executed`
- `model_promises_protected_action`
- `model_includes_machine_contract_jargon`
- `verifier_fails`
- `external_provider_path_appears`
- `tool_call_attempt_appears`

## Operator Decision Options

- `approve_one_time_local_lm_invocation_for_finance_payment_watch`
- `request_more_detail`
- `choose_different_model`
- `reject_for_now`
