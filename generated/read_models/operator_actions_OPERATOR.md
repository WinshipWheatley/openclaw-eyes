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
- Requests by source kind: cli=1, mission_control=1.
- Pending approval by source kind: mission_control=1.

Latest action:
- Action: `opact_inbox_sample_inbox_query_mirror_20260514_v0`.
- Type: `query_generated_read_model_mirror`.
- Status: `requested`.
- Requested by: `mission_control`.
- Source: `mission_control` / `mac_app`.

Last execution receipt:
- Receipt: `opreceipt_opact_demo_export_report_bridge_read_model_20260514_v0`.
- Result: `completed`.
- Exit code: `0`.
- Summary: Allowlisted operator action export_report_bridge_read_model completed with exit_code=0.

Allowed action types:
- `export_context_selection_read_model`: Refresh the bounded Context Selection generated read-model.
- `export_report_bridge_read_model`: Refresh the bounded Report Bridge generated read-model.
- `prepare_mac_read_model_shuttle`: Prepare an E-drive Mac read-model shuttle package.
- `query_generated_read_model_mirror`: Query Mac generated-read-model mirror status.

Source boundary:
- Mission Control, Telegram, CLI, Report Bridge, and future client nodes are source metadata only.
- Telegram-ready means metadata shape only; no Telegram API, polling, or sending is wired.
- Source message text does not become shell and raw source text is not stored by default.
- All source kinds still require explicit approval before execution.

Authority boundary:
- arbitrary_shell_allowed=false; runtime_activation_allowed=false; agent_activation_allowed=false.
- docker_allowed=false; ollama_allowed=false; network_allowed=false; remote_control_allowed=false.
- client_deployment_allowed=false; file_delete_allowed=false; file_move_allowed=false.

Next safe move:
- Surface this read-model in Mission Control as a request/review/result posture view before adding any app-side request writer.
