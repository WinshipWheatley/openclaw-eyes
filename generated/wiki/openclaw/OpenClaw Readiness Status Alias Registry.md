# OpenClaw Readiness Status Alias Registry

Status: READINESS_STATUS_ALIAS_REGISTRY_READY

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

## Boundary
This registry does not mark any new capability ready by itself. It does not send email, open Gmail, open Coupa, submit portal actions, mutate ledger state, mutate workbooks, export PDFs, mark paid, invoke LLMs, or grant business authority.

## Safe use
When a prompt requires a readiness token, resolve aliases through `generated/read_models/openclaw_readiness_status_alias_registry.json`, then still check the referenced evidence read model or commit before continuing.
