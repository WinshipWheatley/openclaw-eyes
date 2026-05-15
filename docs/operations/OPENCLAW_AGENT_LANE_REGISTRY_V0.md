# OpenClaw Agent Lane Registry v0

Purpose: define role-scoped OpenClaw agent lanes for future intent routing without
activating agents or granting hidden authority.

This registry lives in the Business Ops ledger under `agent_lane_*` tables. It
does not replace Operator Action Path, Operator Intent Inbox, Context Selection,
Report Bridge, File Event Queue, or the existing receipt spine. It gives those
systems a durable map of which role should receive which type of work.

## Existing surface reconciliation

- `capability_registry.py` exists as older Cassandra/Chief capability context.
- It is partial and runtime-adjacent, not the current SQLite authority surface.
- `backend_data_contract.py` has inert conceptual `agent_context_profile` and
  actor-profile schema surfaces.
- Agent Lane Registry v0 is the active metadata registry for current substrate
  routing posture. It keeps the old role knowledge as context, not authority.

## Agents

- `chief`: system orchestration, work planning, routing, and Codex work packets.
- `cassandra`: operator communications, summaries, briefings, and draft messages.
- `guardian`: safety, security, no-go boundaries, and risk cautions.
- `niles`: music/art production planning and creative file metadata proposals.
- `hermes`: advisory synthesis, comparisons, and non-canonical memos.
- `report_bridge`: sanitized report-package intake and rejection/import posture.

Aliases:

- `producer` and `creative_file_resolver` route to `niles` for v0.
- `node_uplink` routes to `report_bridge`.

## Source kinds

Supported source kinds are metadata/request surfaces only:

- `mission_control`
- `telegram`
- `cli`
- `report_bridge`
- `future_client_node`

Telegram is represented for future metadata routing only. No Telegram API,
polling, sending, message-body storage, or execution behavior is wired.

## Authority boundary

All v0 lanes have:

- `agent_activation_allowed=false`
- `direct_execution_allowed=false`
- `approval_bypass_allowed=false`
- `no_go_raw_access_allowed=false`
- `network_authority=false`
- `tool_execution_allowed=false`
- `model_execution_allowed=false`
- `runtime_authority=false`
- `client_deployment_allowed=false`

No source can bypass approval. Message text cannot become shell. Role assignment
does not promote evidence to truth.

## Tables

- `agent_lane_registry_runs`
- `agent_lanes`
- `agent_lane_worlds`
- `agent_lane_allowed_inputs`
- `agent_lane_blocked_inputs`
- `agent_lane_allowed_outputs`
- `agent_lane_blocked_outputs`
- `agent_lane_action_policies`
- `agent_lane_receipt_requirements`
- `agent_lane_source_kinds`
- `agent_lane_aliases`
- `agent_lane_routing_hints`

## Commands

Build and export the read-model:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_agent_lane_registry.py --format operator
```

Query:

```bash
python3 scripts/query_agent_lane_registry.py --report summary --format operator
python3 scripts/query_agent_lane_registry.py --report agents --format operator
python3 scripts/query_agent_lane_registry.py --agent chief --format operator
python3 scripts/query_agent_lane_registry.py --agent niles --format operator
python3 scripts/query_agent_lane_registry.py --report world --world music_art --format operator
python3 scripts/query_agent_lane_registry.py --report source-kind --source-kind telegram --format operator
python3 scripts/query_agent_lane_registry.py --report approval-required --format operator
```

## Generated read-model

- `generated/read_models/agent_lanes.json`
- `generated/read_models/agent_lanes_OPERATOR.md`

These files are inspection surfaces for Mission Control, agents, and operator
workflows. They do not activate agents or create execution authority.

## Next safe extension

Use `agent_lanes.json` as routing context for Operator Intent Inbox and future
Mission Control request drafting. Any real action still enters Operator Action
Path and requires explicit approval before bounded execution.
