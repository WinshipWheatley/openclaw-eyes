# Core Architecture Principles

Status type: OPERATING_DOCTRINE

## Purpose

Carry the permanent architecture guardrails into Packet 06 so future operator-harness, receipt-layer, sensitive-root, runtime, MCP, and billing-bridge work stays simple, inspectable, and source-bound.

## Source Inputs

- `CORE_ARCHITECTURE_PRINCIPLES.md`
- `OPENCLAW_RUNTIME.md`
- Packet 05 `08_CORE_ARCHITECTURE_PRINCIPLES.md`
- Packet 05 `00_ACTIVE_HANDOFF.md`
- CLI Receipt Layer breadcrumb
- Sensitive Root Registry breadcrumb

## What It Governs

- Single source of truth per concern.
- Minimal infrastructure before new orchestration layers.
- Audit before adding dependencies, services, plugins, CLIs, MCP surfaces, or storage layers.
- Categorical clarity between application logic, tooling, runtime, governance, and documentation.
- Future-proof simplicity for new engineers and future agents.

## Repo Implementation Pointers

- `backend_data_contract.py`
- `backend_sqlite_schema.py`
- `backend_sqlite_repository.py`
- `backend_knowledge_packet.py`
- `backend_storage_intelligence.py`

These modules are proof that built substrate already exists; they are not permission to add new layers casually.

## Valid Future Lane Moves

- Compare three architecture approaches before adding a new control layer.
- Prefer deterministic receipts over repeated LLM discovery.
- Keep CLI receipt tooling read-only until write authority is explicitly selected.
- Treat MCP/shared memory review as architecture review before implementation.

## Forbidden Drift

- No shadow memory systems.
- No duplicate ledgers that can drift from SQLite or handoff truth.
- No hidden control planes.
- No heavyweight orchestration stack when a small script, table, or read model is sufficient.
- No treating receipt summaries as canonical writers.

## Review Boundary

Review this file before proposing new dependencies, services, plugins, CLIs, MCP servers, runtime integration, billing machinery, or storage authority.

## Why It Should Last 10-20 Moves

Packet 06 contains several tempting tool-building lanes. This file keeps them honest across many moves by requiring audit, simplicity, and single-source authority every time.
