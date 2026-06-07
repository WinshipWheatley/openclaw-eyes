# Local LM Runtime Discovery

Status: LOCAL_LM_RUNTIME_DISCOVERY_READY
Ready for pilot: `false`
Recommended candidate: `local_llm_shadow_mode`

This is discovery only. It does not invoke a model, connect a runtime, start a service, call an endpoint, send a prompt, or expose a proof bundle.

## Candidates

- `ollama`: present `True`, running `True`, invocation `false`, pilot `false`
- `llama_cpp_or_llama_server`: present `False`, running `False`, invocation `false`, pilot `false`
- `lm_studio`: present `False`, running `False`, invocation `false`, pilot `false`
- `local_openai_compatible_server_configs`: present `True`, running `False`, invocation `false`, pilot `false`
- `hermes_sidecar`: present `True`, running `False`, invocation `false`, pilot `false`
- `local_llm_shadow_mode`: present `True`, running `unknown`, invocation `false`, pilot `false`
- `codex_desktop_operator_assist`: present `True`, running `True`, invocation `false`, pilot `false`
- `future_local_open_model`: present `True`, running `unknown`, invocation `false`, pilot `false`
- `external_llm_blocked_by_default`: present `unknown`, running `unknown`, invocation `false`, pilot `false`

## Missing Receipts

- `operator_approval_receipt`
- `model_harness_selected_receipt`
- `model_invocation_boundary_receipt`
- `no_external_provider_receipt`
- `no_tool_authority_receipt`
- `no_memory_promotion_receipt`
- `redacted_proof_bundle_receipt`
- `verifier_pass_fail_receipt`
- `published_response_hash_receipt`

## Boundary

- Runtime presence is not invocation approval.
- External providers remain blocked.
- Hermes remains blocked unless separately registered and receipted.
- No model can see proof bundles yet.
- Tool authority remains false.

## Next Safe Action

Collect missing receipts and operator approval before any local runtime sees a redacted proof bundle.
