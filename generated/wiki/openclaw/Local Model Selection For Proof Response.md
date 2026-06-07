# Local Model Selection For Proof Response

Status: LOCAL_MODEL_SELECTION_FOR_PROOF_RESPONSE_READY
Packet status: pending_operator_review

This is review-only. It does not invoke a model, send a prompt, send a proof bundle, connect an external provider, start or stop services, read secrets, or grant authority.

## Recommendation

- Model: `qwen3:8b-q4_K_M`
- Model ref: `local_model:ollama:qwen3_8b-q4_k_m`
- Runtime: `ollama`
- Ready for invocation: `false`
- Proof bundle allowed: `false`
- Required operator decision: `approve_model_selection_for_one_time_pilot`

## First Pilot Lane

- Lane: `finance/capital_hilton`
- Question: What should I do here?

## Candidates

- `mistral-nemo:12b-instruct-2407-q2_K`: selected `false`; invocation `false`; proof `false`. Rejected for first review because qwen3:8b-q4_K_M is a better balance for the initial proof-to-response lane.
- `qwen3:8b-q4_K_M`: selected `true`; invocation `false`; proof `false`. Selected for review because qwen3:8b-q4_K_M is installed locally, modestly sized, likely capable enough for concise proof-to-response drafting, and avoids external providers or tool authority.
- `qwen3:4b`: selected `false`; invocation `false`; proof `false`. Rejected for first review because a slightly stronger installed local model is available for concise drafting.
- `qwen3.6:latest`: selected `false`; invocation `false`; proof `false`. Rejected for first review because qwen3:8b-q4_K_M is a better balance for the initial proof-to-response lane.
- `magistral:latest`: selected `false`; invocation `false`; proof `false`. Rejected for first review because qwen3:8b-q4_K_M is a better balance for the initial proof-to-response lane.
- `mistral-small:latest`: selected `false`; invocation `false`; proof `false`. Rejected for first review because qwen3:8b-q4_K_M is a better balance for the initial proof-to-response lane.
- `nemotron-3-nano:4b`: selected `false`; invocation `false`; proof `false`. Rejected for first review because a slightly stronger installed local model is available for concise drafting.
- `nemotron-3-nano:30b`: selected `false`; invocation `false`; proof `false`. Rejected for first review because it has a larger operational footprint than needed for the simple Finance / Capital Hilton lane.
- `gemma4:31b`: selected `false`; invocation `false`; proof `false`. Rejected for first review because it has a larger operational footprint than needed for the simple Finance / Capital Hilton lane.
- `gemma4:26b`: selected `false`; invocation `false`; proof `false`. Rejected for first review because it has a larger operational footprint than needed for the simple Finance / Capital Hilton lane.
- `gemma4:e4b`: selected `false`; invocation `false`; proof `false`. Rejected for first review because qwen3:8b-q4_K_M is a better balance for the initial proof-to-response lane.

## Decision Options

- `approve_model_selection_for_one_time_pilot`
- `choose_different_model`
- `request_more_detail`
- `reject_for_now`
