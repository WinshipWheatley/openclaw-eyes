# OpenClaw Readiness Status Alias Registry

Status: READINESS_STATUS_ALIAS_REGISTRY_READY

Latest patch status: READINESS_STATUS_ALIAS_PATCH_READY

## Purpose
This registry keeps queue discipline strict without making agents block on equivalent readiness names. It is read-only guidance for precondition checks.

## Canonical aliases
- `WORKFLOW_PACKAGE_REQUEST_CONSUMER_READY`
  - `PC_WORKFLOW_PACKAGE_REQUEST_CONSUMER_READY`
  - `WORKFLOW_PACKAGE_RAIL_STATUS_READY`
  - Evidence: `generated/read_models/workflow_package_request_consumer_status.json`, commits `e9cd69f94db70416ff281bc02059ed658d8c9033` and `68e6ee06b571d03ff085fcfa033dd439d6eea061`.
- `PC_OPERATOR_DISPLAY_COPY_READY`
  - `PC_OPERATOR_COPY_LAYER_READY`
  - `PC_OPERATOR_DISPLAY_COPY_READY`
  - Evidence: commits `27dd37f5e0d69f345e78d7971b1ba9f739111e47` and `d2ba0e0a114993b1759e643f2469a5a4738bfade`.
- `SYSTEM_QUESTION_ANSWER_V0_READY`
  - `SYSTEM_QUESTION_ANSWER_V0_READY`
  - Evidence: `generated/read_models/system_question_answer_contract.json`.
- `AGENT_VOICE_ROUTING_V0_READY`
  - `AGENT_VOICE_ROUTING_V0_READY`
  - Evidence: `generated/read_models/agent_voice_routing_contract.json`.
- `MAC_HELM_COMPOSER_READY`
  - `MAC_HELM_COMPOSER_READY`
  - `HELM_COMPOSER_UI_READY`
  - Evidence: Mac commit `dd07f08`, plus Helm Composer contract evidence when present.
- `SYSTEM_QUESTION_ROUTE_READY`
  - `SYSTEM_QUESTION_ROUTE_READY`
  - `SYSTEM_QUESTION_E2E_READY`
  - `SYSTEM_QUESTION_ANSWER_ROUTE_READY`
  - Evidence: PC route commit `80d2b05d83429cd6137b07572e9a5ea7895843a3`, `generated/read_models/system_question_answer_contract.json`, and `generated/read_models/package_event_index.json`.
- `HELM_COMPOSER_CONTRACT_READY`
  - `HELM_COMPOSER_CONTRACT_READY`
  - Evidence: `generated/read_models/helm_composer_contract.json`, commit `32d5b4fd3fc19b65dedc053f7c2ee26bea780004`.
- `PACKAGE_EVENT_INDEX_READY`
  - `PACKAGE_EVENT_INDEX_READY`
  - Evidence: `generated/read_models/package_event_index.json`, commit `8763e37b39ec0184446d739c05c7480672d18214`.

## Boundary
This registry does not mark any new capability ready by itself. It does not send email, open Gmail, open Coupa, submit portal actions, mutate ledger state, mutate workbooks, export PDFs, mark paid, invoke LLMs, or grant business authority.

## Safe use
When a prompt requires a readiness token, resolve aliases through `generated/read_models/openclaw_readiness_status_alias_registry.json`, then still check the referenced evidence read model or commit before continuing.
