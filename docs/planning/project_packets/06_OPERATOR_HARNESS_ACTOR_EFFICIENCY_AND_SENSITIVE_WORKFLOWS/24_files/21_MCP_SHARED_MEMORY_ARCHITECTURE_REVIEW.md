# MCP Shared Memory Architecture Review

Status type: FUTURE_LANE

## Purpose

Define a future architecture-review lane for MCP/shared memory ideas inspired by Open Brain / OB1-style shared context, without invoking MCPs or adding memory systems from Packet 06.

## Source Inputs

- Packet 05 `00_ACTIVE_HANDOFF.md`
- Packet 05 `07_04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md`
- Packet 05 `03_CORE_ARCHITECTURE_PRINCIPLES.md`
- CLI Receipt Layer breadcrumb

## What It Governs

- MCP/shared memory as review topic, not implementation authority.
- Single-source-of-truth requirements.
- Context provenance and context-filter receipt requirements.
- Agent shared-memory risks: stale authority, prompt injection, private leakage, and duplicate state.
- Relationship to existing SQLite/context substrate.

## Repo Implementation Pointers

- `backend_knowledge_packet.py`
- `backend_sqlite_repository.py`
- `backend_storage_intelligence.py`
- `tests/test_backend_agent_context.py`

## Valid Future Lane Moves

- Compare MCP/shared memory approaches against existing substrate.
- Draft a no-implementation architecture review.
- Define fail-closed requirements before any MCP connector or shared-memory layer.
- Identify when the answer should be "do not add a layer."

## Forbidden Drift

- No MCP invocation.
- No MCP context ingestion.
- No provider/model calls.
- No new shadow memory or duplicate ledger.
- No private-root exposure.
- No treating shared memory as accepted truth.

## Review Boundary

Review before any MCP, shared memory, external app connector, memory server, or context registry lane.

## Why It Should Last 10-20 Moves

Shared memory will remain tempting. This rail keeps review ahead of implementation and forces architecture discipline.
