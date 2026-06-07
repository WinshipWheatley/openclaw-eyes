# Local LM Harness Inventory Receipts

Status: LOCAL_LM_HARNESS_INVENTORY_RECEIPTS_READY
Ready for live local LM pilot: `false`

This inventory records local/model/harness candidates for a future proof-to-response pilot. It is not a runtime approval and does not invoke or connect any model.

## Candidates

- `local_llm_shadow_mode`: present `unknown`, live `false`, reason `shadow_mode_inventory_only_no_runtime_boundary_receipt`
- `future_local_open_model`: present `unknown`, live `false`, reason `future_model_not_selected_or_approved`
- `codex_desktop_operator_assist`: present `unknown`, live `false`, reason `codex_desktop_operator_assist_requires_explicit_gate_approval`
- `hermes_sidecar_candidate`: present `true`, live `false`, reason `hermes_sidecar_not_explicitly_registered_for_proof_to_response`
- `external_llm_blocked_by_default`: present `unknown`, live `false`, reason `external_provider_blocked_by_default`

## Receipts Required Before Live Pilot

- `proof_bundle_redaction_receipt`
- `model_invocation_boundary_receipt`
- `no_external_provider_receipt`
- `no_tool_authority_receipt`
- `no_memory_promotion_receipt`
- `verifier_pass_fail_receipt`
- `published_response_hash_receipt`
- `operator_approval_receipt`

## First Safe Pilot Scope

- `finance_capital_hilton_payment_watch`
- `business_development_capital_hilton_followup`
- `finance_live_arts_md_evidence`
- `build_informational_review`
- `self_heal_repair_explanation`

## Blocked By Default

- External LLM/provider calls
- Tool authority
- Browser, Gmail, Coupa, portal submit
- Ledger/workbook mutation, PDF export, paid marking
- Worker spawn and memory promotion to truth

## Decision

- Blockers: `['operator_approval_receipt_missing', 'proof_bundle_redaction_receipt_missing', 'model_invocation_boundary_receipt_missing', 'no_external_provider_receipt_missing', 'no_tool_authority_receipt_missing', 'verifier_pass_fail_receipt_missing']`
- Next safe action: Collect non-invocation boundary receipts and choose a local-only shadow harness candidate for explicit approval.
