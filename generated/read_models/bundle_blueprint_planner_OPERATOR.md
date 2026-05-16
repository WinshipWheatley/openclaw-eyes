# Bundle Blueprint Planner Read-Model v0

What this is:
- A generated read-model over deterministic local bundle-planning examples.

What this is not:
- It is not GitHub packaging, deployment, runtime activation, external integration, or client data transfer.

Summary:
- Example manifests: 5.
- Selected modules: cassandra_clara_fact_intake=3, guardian_hitl_gate=2, hermes_next_lane_advisory=1, niles_album_matrix=1, project_capsule_bundle_blueprint=2, report_bridge_sanitized_summary=2.
- Blocked modules: planner_runner_registry=1.

Boundary:
- `github_packaging_allowed=false`; `deployment_allowed=false`; `runtime_authority=false`.
- Private/client data stays local; Core receives sanitized status/proof only.
