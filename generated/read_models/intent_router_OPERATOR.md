# Intent Router Read-Model v0

What this is:
- A generated read-model over deterministic `intent_router_*` SQLite rows.
- It shows how operator text was routed to role-scoped agent lanes and what next safe move was proposed.

What this is not:
- It is not agent activation, LLM routing, Telegram wiring, model calling, tool execution, approval bypass, or runtime execution.

Summary:
- Total intents: 5.
- Routed: 4.
- Needs review: 1.
- Rejected: 0.
- By agent: cassandra=1, chief=2, guardian=1, niles=1.
- By category: communication_summary_request=1, file_context_request=1, markdown_reorg_request=1, read_model_refresh_request=1, safety_review_request=1.
- By source kind: cli=5.

Latest intent:
- Intent: `intent_live_chief_refresh_v0`.
- Status: `routed`.
- Route: `chief` / `system_orchestration`.
- Category: `read_model_refresh_request`.
- World: `operations`.
- Candidate action: `prepare_mac_read_model_shuttle`.
- Next safe move: Prepare a candidate Operator Action request for `prepare_mac_read_model_shuttle`; approval is still required before execution.

Authority boundary:
- agent_activation_allowed=false; direct_execution_allowed=false; approval_bypass_allowed=false.
- action_auto_create_allowed=false; action_auto_approve_allowed=false; action_auto_execute_allowed=false.
- no_go_raw_access_allowed=false; network_authority=false; tool_execution_allowed=false.
- model_execution_allowed=false; runtime_authority=false; client_deployment_allowed=false.
- file_move_allowed=false; file_delete_allowed=false.

Next safe move:
- Surface this read-model in Mission Control as route posture before adding any frontend request writer.
