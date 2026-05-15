# Project Capsule Read-Model v0

What this is:
- A generated read-model over `project_capsule_*` SQLite planning rows.
- It exposes synthetic project-capsule posture without querying raw SQLite directly.

What this is not:
- It is not deployment, runtime activation, client-data access, tool execution, agent activation, or truth promotion.

Summary:
- Latest run: `pcaprun_53ec84733997a10c1423`.
- Capsule count: 1.
- Demo capsule: `demo_project_capsule_v0` - Demo Client Operations Helper.
- Worlds: `build`, `communications`, `operations`.
- Tool candidates: `copier`, `datasette`, `pocketbase`, `sqlite_utils`.
- Next safe move: Export the project capsule read-model, then generate the synthetic demo template.

Authority boundary:
- runtime_authority=false; deployment_authority=false; client_data_access=false.
- agent_activation_allowed=false; tool_execution_allowed=false; network_authority=false.
- approval_status=not_approved.

Next safe move:
- Use this read-model for inspection and prompt grounding only; real-client, deployment, runtime, tool, or agent work needs a separate scoped lane.
