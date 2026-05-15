# Report Bridge Read-Model v0

What this is:
- A generated read-model over `report_bridge_*` SQLite rows.
- It exposes sanitized node/client/project report-package posture without querying raw SQLite directly.

What this is not:
- Report Bridge is sanitized package intake, not remote control or deployment.
- It is not runtime activation, agent activation, tool execution, model execution, network access, or truth promotion.

Summary:
- Latest run: `None`.
- Packages: 0 total, 0 accepted, 0 rejected.
- Nodes seen: 0.
- Projects seen: 0.
- Package kinds: none.
- Node kinds: none.
- Projects: none.
- Clients: none.
- Inbox: `/mnt/e/openclaw/node_uplink/inbox`.

Latest imported package:
- None.

Latest rejection:
- None.

Authority boundary:
- runtime_authority=false; deployment_authority=false; remote_management_allowed=false.
- agent_activation_allowed=false; tool_execution_allowed=false; model_execution_allowed=false.
- container_execution_allowed=false; network_authority=false; truth_promotion_allowed=false.
- client_data_access=false.

Next safe move:
- Use this read-model to inspect package posture; any real client data, deployment, remote management, runtime, agent, tool, model, network, or truth-promotion work needs a separate scoped lane.
