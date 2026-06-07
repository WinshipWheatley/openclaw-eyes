# Local Model List Inventory

Status: LOCAL_MODEL_LIST_INVENTORY_READY

This is read-only local model inventory. It does not invoke a model, send a prompt, send a proof bundle, call an external provider, read secrets, or grant authority.

## Summary

- Models found: `11`
- Model invocation performed: `false`
- Prompt sent: `false`
- Proof bundle sent: `false`
- External provider used: `false`
- Secrets read: `false`
- Recommended next decision: `select_one_local_model_for_pilot_review`

## Models

- `mistral-nemo:12b-instruct-2407-q2_K` (ollama): 4.8 GB; parameters 12b; invocation `false`, proof bundle `false`
- `qwen3:8b-q4_K_M` (ollama): 5.2 GB; parameters 8b; invocation `false`, proof bundle `false`
- `qwen3:4b` (ollama): 2.5 GB; parameters 4b; invocation `false`, proof bundle `false`
- `qwen3.6:latest` (ollama): 23 GB; invocation `false`, proof bundle `false`
- `magistral:latest` (ollama): 14 GB; invocation `false`, proof bundle `false`
- `mistral-small:latest` (ollama): 14 GB; invocation `false`, proof bundle `false`
- `nemotron-3-nano:4b` (ollama): 2.8 GB; parameters 4b; invocation `false`, proof bundle `false`
- `nemotron-3-nano:30b` (ollama): 24 GB; parameters 30b; invocation `false`, proof bundle `false`
- `gemma4:31b` (ollama): 19 GB; parameters 31b; invocation `false`, proof bundle `false`
- `gemma4:26b` (ollama): 17 GB; parameters 26b; invocation `false`, proof bundle `false`
- `gemma4:e4b` (ollama): 9.6 GB; invocation `false`, proof bundle `false`

## Rules

- Listing models is not approval to invoke.
- Presence is not proof-bundle permission.
- No discovered model is selected for the pilot.
- External providers remain blocked.
