# Core Architecture Principles

Status type: OPERATING_DOCTRINE

## Purpose

Carry the permanent OpenClaw architecture guardrails into Packet 07 so prompt discipline, receipt surfaces, sensitive policy, and gated activation work stay simple, inspectable, and source-bound.

## Source Inputs

- Packet 06 `03_CORE_ARCHITECTURE_PRINCIPLES.md`
- Packet 06 final `00_ACTIVE_HANDOFF.md`
- `OPENCLAW_RUNTIME.md`
- `USER.md`
- `CORE_ARCHITECTURE_PRINCIPLES.md`

## What It Governs

- One source of truth per concern.
- Minimal infrastructure before new orchestration.
- Explicit review before new dependencies, services, CLIs, MCP surfaces, memory layers, runtime gates, or billing/legal machinery.
- Separation of doctrine, tooling, runtime, storage, and authority.
- Gated activation as future work, not ambient permission.

## Repo Implementation Pointers

- `backend_data_contract.py`
- `backend_sqlite_schema.py`
- `backend_sqlite_repository.py`
- `backend_knowledge_packet.py`
- `backend_storage_intelligence.py`
- `scripts/openclaw_receipts.py`
- `openclaw_sensitive_policy.py`

## Valid Future Lane Moves

- Compare architecture approaches before adding a new control layer.
- Prefer deterministic receipts and static contracts before runtime integration.
- Keep shared memory and MCP work in review until authority is explicit.
- Keep billing, legal, and sensitive-root surfaces metadata-only until later approved lanes.

## Forbidden Drift

- No shadow memory systems.
- No duplicate ledgers that drift from SQLite, packets, or handoffs.
- No hidden control planes.
- No runtime activation from documentation.
- No receipt summary becoming a writer or approval engine.

## Review Boundary

Review before proposing new architecture, dependencies, services, launchers, MCP servers, memory layers, runtime integration, billing machinery, or legal processors.

## Why It Should Last 10-20 Moves

Packet 07 contains several high-authority temptations. This rail keeps future work grounded in simple architecture and explicit gates.
