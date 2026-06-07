# Model Catalog Inventory

Status: MODEL_CATALOG_INVENTORY_READY

This is catalog/discovery only. It does not invoke models, connect runtimes, call provider APIs, read secrets, send prompts, or expose proof bundles.

## Summary

- Total candidates: `22`
- Local candidates: `10`
- External catalog candidates: `8`
- Invocation allowed: `0`
- Proof bundle allowed: `0`
- Recommended next decision: `select_model_for_review`

## Policy

- Local models are preferred for private finance/client proof.
- External providers are blocked by default for private proof.
- External provider catalog entries are metadata only.
- Configured provider does not imply approval.
- Powerful model does not imply authority.
- Provider choice does not grant tool access.
- Inventory does not approve proof exposure.

## Candidates

- `model_candidate:local_runtime:ollama` (local_runtime_installed): Ollama present `True`, configured `True`, running `True`, invocation `false`, proof `false`
- `model_candidate:local_runtime:llama_cpp_or_llama_server` (local_runtime_installed): llama.cpp / llama-server present `False`, configured `unknown`, running `False`, invocation `false`, proof `false`
- `model_candidate:local_runtime:lm_studio` (local_runtime_installed): LM Studio present `False`, configured `unknown`, running `False`, invocation `false`, proof `false`
- `model_candidate:local_runtime:local_openai_compatible_server_configs` (local_runtime_installed): Local OpenAI-compatible server present `True`, configured `True`, running `False`, invocation `false`, proof `false`
- `model_candidate:local_runtime:future_local_open_model` (local_runtime_installed): Future local open model present `True`, configured `True`, running `unknown`, invocation `false`, proof `false`
- `model_candidate:sidecar:hermes_sidecar` (local_sidecar_harness): Hermes sidecar candidate present `True`, configured `True`, running `False`, invocation `false`, proof `false`
- `model_candidate:sidecar:local_llm_shadow_mode` (local_sidecar_harness): local_llm_shadow_mode present `True`, configured `True`, running `unknown`, invocation `false`, proof `false`
- `model_candidate:operator_assist:codex_desktop_operator_assist` (operator_assist_harness): Codex Desktop operator assist present `True`, configured `True`, running `True`, invocation `false`, proof `false`
- `model_candidate:operator_assist:mac_codex` (operator_assist_harness): Mac Codex present `unknown`, configured `True`, running `unknown`, invocation `false`, proof `false`
- `model_candidate:operator_assist:pc_codex` (operator_assist_harness): PC Codex present `unknown`, configured `True`, running `unknown`, invocation `false`, proof `false`
- `model_candidate:external_provider:openai` (external_provider_catalog): OpenAI present `unknown`, configured `True`, running `unknown`, invocation `false`, proof `false`
- `model_candidate:external_provider:anthropic` (external_provider_catalog): Anthropic present `unknown`, configured `True`, running `unknown`, invocation `false`, proof `false`
- `model_candidate:external_provider:google` (external_provider_catalog): Google present `unknown`, configured `True`, running `unknown`, invocation `false`, proof `false`
- `model_candidate:external_provider:mistral` (external_provider_catalog): Mistral present `unknown`, configured `unknown`, running `unknown`, invocation `false`, proof `false`
- `model_candidate:external_provider:groq` (external_provider_catalog): Groq present `unknown`, configured `unknown`, running `unknown`, invocation `false`, proof `false`
- `model_candidate:external_provider:together` (external_provider_catalog): Together present `unknown`, configured `unknown`, running `unknown`, invocation `false`, proof `false`
- `model_candidate:external_provider:openrouter` (external_provider_catalog): OpenRouter present `unknown`, configured `unknown`, running `unknown`, invocation `false`, proof `false`
- `model_candidate:external_provider:nvidia_nim` (external_provider_catalog): NVIDIA NIM present `unknown`, configured `True`, running `unknown`, invocation `false`, proof `false`
- `model_candidate:blocked_future:unregistered_provider` (blocked_unknown_or_future): Unregistered provider present `unknown`, configured `False`, running `unknown`, invocation `false`, proof `false`
- `model_candidate:blocked_future:unverified_model` (blocked_unknown_or_future): Unverified model present `unknown`, configured `False`, running `unknown`, invocation `false`, proof `false`
- `model_candidate:blocked_future:missing_privacy_policy` (blocked_unknown_or_future): Missing privacy policy present `unknown`, configured `False`, running `unknown`, invocation `false`, proof `false`
- `model_candidate:blocked_future:missing_receipt_path` (blocked_unknown_or_future): Missing receipt path present `unknown`, configured `False`, running `unknown`, invocation `false`, proof `false`
