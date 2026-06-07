# Local LM Pilot Harness Selection Packet

Status: LOCAL_LM_PILOT_HARNESS_SELECTION_PACKET_READY
Packet status: pending_operator_review

This is review-only. It does not invoke a model, connect a runtime, start a service, or grant authority.

## Selection

- Harness: `local_llm_shadow_mode`
- Model/runtime: `not_selected_pending_operator_review`
- Local only: `true`
- External provider used: `false`
- Runtime present: `unknown`
- Invocation allowed: `false`

## Proof Input

- Proof bundle: `redacted_proof_bundle:finance_capital_hilton_payment_watch`
- Redaction policy: `generated/read_models/proof_bundle_redaction_policy.json`
- Verifier: `proof_to_response_verifier.py#proof_to_response_verifier_v0`
- Allowed inputs: `['world_ref', 'thread_ref', 'objective_ref', 'redacted_known_facts', 'proof_meter_labels', 'receipt_refs', 'gate_labels', 'missing_input', 'allowed_controls', 'blocked_action_summaries', 'human_safe_summaries', 'agent_voice_mode']`

## No Access

- Tool access: `false`
- Memory write access: `false`
- Business action authority: `false`
- Browser/Gmail/Coupa/ledger/workbook/PDF/paid marking: blocked

## Missing Receipts

- `proof_bundle_redaction_receipt`
- `model_invocation_boundary_receipt`
- `no_external_provider_receipt`
- `no_tool_authority_receipt`
- `no_memory_promotion_receipt`
- `verifier_pass_fail_receipt`
- `published_response_hash_receipt`
- `operator_approval_receipt`

## Plain Status

No suitable live local runtime is confirmed present yet; `local_llm_shadow_mode` is a review candidate only until receipts and explicit approval exist.

## Operator Decision Options

- `select_local_llm_shadow_mode_for_one_time_pilot_review`: Records the harness/model candidate for review only; it does not allow invocation.
- `request_more_detail`: Ask for more harness, runtime, redaction, or receipt detail before selection.
- `reject_for_now`: Keep local/live LM invocation blocked.

## Answers

- Which harness would be used? `local_llm_shadow_mode`
- Is it local only? `true`
- Is any external provider involved? `false`
- What model/runtime would be called? `not_selected_pending_operator_review`
- Is that runtime currently installed/present? `unknown`
- What proof bundle would be sent? `redacted_proof_bundle:finance_capital_hilton_payment_watch`
- What redaction policy applies? `generated/read_models/proof_bundle_redaction_policy.json`
- What tool access does the model have? `none`
- What memory write access does the model have? `none`
