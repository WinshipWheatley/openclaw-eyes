# Approved Module Registry Read-Model v0

What this is:
- A generated read-model over local approved-module planning metadata.

What this is not:
- It is not runtime activation, deployment, external send, tool execution, model execution, or client data access.

Summary:
- Modules: 8.

Modules:
- `hermes_next_lane_advisory` status=`draft` authority=`read_only` client_safe=`true` core_only=`false`
- `guardian_hitl_gate` status=`draft` authority=`planning_only` client_safe=`true` core_only=`false`
- `planner_runner_registry` status=`blocked` authority=`future_gated` client_safe=`false` core_only=`true`
- `project_capsule_bundle_blueprint` status=`draft` authority=`planning_only` client_safe=`true` core_only=`false`
- `chief_intent_routing` status=`approved` authority=`planning_only` client_safe=`true` core_only=`false`
- `niles_album_matrix` status=`draft` authority=`planning_only` client_safe=`true` core_only=`false`
- `cassandra_clara_fact_intake` status=`draft` authority=`metadata_only` client_safe=`true` core_only=`false`
- `report_bridge_sanitized_summary` status=`approved` authority=`metadata_only` client_safe=`true` core_only=`false`

Boundary:
- `runtime_authority=false`; `deployment_allowed=false`; `send_allowed=false`.
- Client/project bundles may use these records only as local planning metadata.
