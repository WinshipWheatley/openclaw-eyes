# Local LM Proof Response Operator Approval

Status: LOCAL_LM_PROOF_RESPONSE_OPERATOR_APPROVAL_READY

This records the operator decision `approve_one_time_local_lm_invocation_for_finance_payment_watch`.

It does not invoke a model, contact Ollama, send a prompt, send a proof bundle, spawn a worker, or grant business authority.

## Scope

- Attempt limit: one future invocation attempt only
- Lane: `finance/capital_hilton`
- Question: What should I do here?
- Runtime: `ollama`
- Model: `qwen3:8b-q4_K_M`
- Boundary packet: `local_lm_invocation_boundary:finance_capital_hilton:qwen3_8b_q4_k_m:v0`
- Input: redacted, freshness-gated proof bundle only
- Output: draft proof-to-response text only
- Verifier: mandatory
- Fallback: mandatory if verifier fails

## Not Authorized

- Model tool use
- Browser, Gmail, or Coupa access
- Email send or submit
- Ledger, workbook, PDF, or paid mutation
- Worker spawn
- Memory promotion
- External provider use
- Future repeated invocations

## Runtime Requirements

- Build a redacted proof bundle.
- Require current or traceable candidate freshness context.
- Run the deterministic verifier before publishing text.
- Publish a safe fallback if verification fails.
- Record verifier and response hash receipts after the attempt.

## Source Refs

- `generated/read_models/local_lm_proof_response_invocation_boundary_packet.json`
- `generated/read_models/local_model_selection_for_proof_response.json`
- `generated/read_models/proof_bundle_freshness_trace_status.json`
- `generated/read_models/proof_bundle_builder_redaction_status.json`
- `generated/read_models/local_lm_proof_response_preflight_receipts.json`
