# Agent Capability View v0

Evidence:
- Agents: `7`.
- Lane capability records: `212`.
- Legacy capability claims included as context only: `23`.
- Lane registry controls authority; legacy connected claims do not activate integrations.

Agents:
- `cassandra` / `operator_comms`: outputs `6`, approvals `5`, legacy claims `13`.
- `chief` / `system_orchestration`: outputs `5`, approvals `6`, legacy claims `10`.
- `guardian` / `safety_security`: outputs `4`, approvals `3`, legacy claims `0`.
- `hermes` / `advisory_synthesis`: outputs `4`, approvals `3`, legacy claims `0`.
- `niles` / `music_art_production`: outputs `4`, approvals `4`, legacy claims `0`.
- `report_bridge` / `node_report_intake`: outputs `3`, approvals `3`, legacy claims `0`.
- `watch_desk` / `watch_desk_projection`: outputs `3`, approvals `3`, legacy claims `0`.

Boundary:
- Context/readback only. No agent activation, direct execution, runtime dispatch, approval bypass, external send, network, tool, model, credential, no-go raw access, client deployment, stable-map update, or truth promotion authority.
- Legacy `capability_registry.py` connected flags are historical/contextual claims that require receipt and lane verification.

Blocked:
- Treating this view as an execution router or integration proof remains blocked.
- Any write/send/tool/model/runtime action still requires the normal approval and receipt path.

Next safe move:
- Let Mission Control and operator-intent surfaces use this as a capability readback context, then route work packets through existing approval gates.
