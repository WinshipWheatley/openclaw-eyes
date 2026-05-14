# OpenClaw Module Registry v0

Module Registry v0 records reusable OpenClaw capabilities for planning and project-capsule selection.

Current modules:
- `corpus_atlas`
- `evidence_kettle`
- `tool_inventory`
- `tool_intake`
- `context_selection`
- `read_model_shuttle`
- `mac_mirror_atlas`
- `project_capsule`
- `mission_control_read_only_helm`

Commands:
- `python3 scripts/build_module_registry.py --format operator`
- `python3 scripts/query_module_registry.py --report summary --format operator`
- `python3 scripts/query_module_registry.py --report dependencies --format operator`
- `python3 scripts/query_module_registry.py --report client-capsule --format operator`
- `python3 scripts/update_project_capsule_modules.py --ensure-demo --format operator`

Boundary:
- Registry rows are planning metadata only.
- Selecting a module for a capsule does not activate it.
- No runtime, deployment, tool, network, model, or agent authority is granted.
