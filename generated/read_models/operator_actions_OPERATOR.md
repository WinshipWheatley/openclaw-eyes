# Operator Actions Read-Model v0

What this is:
- A generated read-model over helm-gated `operator_action_*` SQLite rows.
- It exposes requested, approved, executed, failed, rejected, and receipted bounded backend actions.

What this is not:
- It is not arbitrary shell, hidden authority, runtime activation, agent activation, remote control, client deployment, Docker/Ollama, or truth promotion.

Summary:
- Requests: 2.
- Pending approval: 1.
- Approved decisions: 1.
- Completed: 1; failed: 0; rejected: 0.
- Receipts: 4.

Latest action:
- Action: `opact_inbox_sample_inbox_query_mirror_20260514_v0`.
- Type: `query_generated_read_model_mirror`.
- Status: `requested`.
- Requested by: `mission_control`.

Last execution receipt:
- Receipt: `opact_approval_request_opact_inbox_sample_inbox_query_mirror_20260514_v0`.
- Result: `requested`.
- Exit code: `0`.
- Summary: Approval requested for query_generated_read_model_mirror.

Allowed action types:
- `export_context_selection_read_model`: Refresh the bounded Context Selection generated read-model.
- `export_report_bridge_read_model`: Refresh the bounded Report Bridge generated read-model.
- `prepare_mac_read_model_shuttle`: Prepare an E-drive Mac read-model shuttle package.
- `query_generated_read_model_mirror`: Query Mac generated-read-model mirror status.

Authority boundary:
- arbitrary_shell_allowed=false; runtime_activation_allowed=false; agent_activation_allowed=false.
- docker_allowed=false; ollama_allowed=false; network_allowed=false; remote_control_allowed=false.
- client_deployment_allowed=false; file_delete_allowed=false; file_move_allowed=false.

Next safe move:
- Surface this read-model in Mission Control as a request/review/result posture view before adding any app-side request writer.
