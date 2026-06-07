# Proof Bundle Builder Redaction Integration

Status: PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY

This status proves the proof bundle builder and LM shadow pilot path use redacted LM-visible inputs.

## Allowed LM Input Fields

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

## Scenario Bundles

- `finance_capital_hilton_payment_watch`: `financial_sensitive/local_only`, voice `diagnostic`, errors `[]`
- `finance_live_arts_payment_evidence`: `financial_sensitive/local_only`, voice `diagnostic`, errors `[]`
- `business_development_capital_hilton_followup`: `internal_operator_safe`, voice `operations`, errors `[]`
- `music_niles_controller_mapping`: `creative_internal_safe`, voice `creative`, errors `[]`
- `self_heal_missing_proof_for_payment`: `internal_operator_safe`, voice `diagnostic`, errors `[]`
- `unknown_context`: `internal_operator_safe`, voice `brief`, errors `[]`

## Proof

- Redacted bundles valid: `true`
- Shadow pilot uses redacted bundles: `true`
- Unsafe true grants absent: `true`
