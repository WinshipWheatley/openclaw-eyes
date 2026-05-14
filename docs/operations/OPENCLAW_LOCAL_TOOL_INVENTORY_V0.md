# OpenClaw Local Tool Inventory v0

Local Tool Inventory v0 records observed metadata about tools already installed in the PC/WSL OpenClaw environment.

It writes a separated `tool_inventory_*` namespace into `.openclaw/business_ops/ledger.sqlite`.

## Boundary

- No packages are installed, upgraded, removed, or cloned.
- No network APIs are called.
- No servers, daemons, containers, models, agents, or runtime activation paths are started.
- Version/path probes are bounded, allowlisted, and metadata-only.
- Installed does not mean approved.
- Detected does not mean integrated.
- Available does not mean authorized.

## Tables

- `tool_inventory_runs`
- `tool_observations`
- `tool_observation_labels`
- `tool_install_locations`
- `tool_version_observations`
- `tool_runtime_boundaries`
- `tool_future_candidates`

## Commands

```bash
python3 scripts/build_tool_inventory.py --format operator
python3 scripts/query_tool_inventory.py --report summary --format operator
python3 scripts/query_tool_inventory.py --report detected --format operator
python3 scripts/query_tool_inventory.py --report category --category local_llm --format operator
python3 scripts/query_tool_inventory.py --report category --category sqlite --format operator
python3 scripts/query_tool_inventory.py --report high-risk --format operator
python3 scripts/query_tool_inventory.py --report future-candidates --format operator
python3 scripts/query_tool_inventory.py --report not-detected --format operator
```

## Future Use

This inventory is metadata for later review. Future Evidence Kettle, sandboxing, deployment, sync, local model, or client capsule work must make separate bounded decisions before using any observed tool.
