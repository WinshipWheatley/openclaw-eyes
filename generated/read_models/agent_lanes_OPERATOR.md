# Agent Lanes Read-Model v0

What this is:
- A generated read-model over role-scoped `agent_lane_*` SQLite rows.
- It defines planning lanes, routing hints, source metadata posture, approvals, and receipts.

What this is not:
- It is not agent activation, runtime execution, Telegram wiring, model calling, tool execution, approval bypass, no-go raw access, or client deployment.

Summary:
- Agents: 6.
- Lanes: 6.
- Worlds: build=2, business_development=2, communications=2, cross_world=5, music_art=1, operations=5, research=1, security=2.

Agents:
- `cassandra` -> `operator_comms`; authority=`advisory_only`; worlds=communications, cross_world, operations.
- `chief` -> `system_orchestration`; authority=`request_only`; worlds=build, business_development, communications, cross_world, operations, security.
- `guardian` -> `safety_security`; authority=`advisory_only`; worlds=cross_world, operations, security.
- `hermes` -> `advisory_synthesis`; authority=`advisory_only`; worlds=build, cross_world, operations, research.
- `niles` -> `music_art_production`; authority=`advisory_only`; worlds=music_art.
- `report_bridge` -> `node_report_intake`; authority=`request_only`; worlds=business_development, cross_world, operations.

Source posture:
- Mission Control, Telegram, CLI, Report Bridge, and future client nodes are source metadata/request channels only.
- Telegram is represented for future metadata routing only; no Telegram API, polling, or sending is wired.
- All sources still require approval gates before any bounded execution path.

Authority boundary:
- agent_activation_allowed=false; direct_execution_allowed=false; approval_bypass_allowed=false.
- no_go_raw_access_allowed=false; network_authority=false; tool_execution_allowed=false.
- model_execution_allowed=false; runtime_authority=false; client_deployment_allowed=false.

Next safe move:
- Use this read-model as routing context for Operator Intent Inbox and future Mission Control request drafting; do not activate agents from it.
