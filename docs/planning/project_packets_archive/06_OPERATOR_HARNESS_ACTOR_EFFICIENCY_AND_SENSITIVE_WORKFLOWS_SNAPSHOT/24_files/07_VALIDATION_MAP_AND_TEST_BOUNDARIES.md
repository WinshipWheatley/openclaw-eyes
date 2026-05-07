# Validation Map And Test Boundaries

Status type: OPERATING_DOCTRINE / BOUNDARY_GUARD

## Purpose

Preserve the difference between docs/source-set checks, static validation, backend tests, runtime checks, and forbidden live services.

Packet 06 generation and most future planning lanes are docs-only unless a later prompt explicitly authorizes implementation.

## Source Inputs

- Packet 05 `10_VALIDATION_MAP.md`
- Packet 05 `00_ACTIVE_HANDOFF.md`
- Packet 05 `README.md`
- CLI Receipt Layer breadcrumb
- `OPENCLAW_RUNTIME.md`

## What It Governs

- Which checks may run for docs/source-set work.
- Which backend tests belong to implementation lanes only.
- How validation receipts should be recorded in the active handoff.
- Why no live runtime services, model/provider calls, invoice tools, or private-root scans are validation shortcuts.

## Repo Implementation Pointers

- `launch_ladder_contract_check.py`
- `tests/test_launch_ladder_static_contract.py`
- `tests/test_backend_data_contract.py`
- `tests/test_backend_sqlite_schema.py`
- `tests/test_backend_sqlite_runtime.py`
- `tests/test_backend_sqlite_repository.py`
- `tests/test_backend_knowledge_packet.py`
- `tests/test_backend_storage_intelligence.py`
- `tests/test_backend_performance_repository.py`
- `tests/test_backend_performance_intelligence.py`
- `tests/test_backend_agent_context.py`

## Valid Future Lane Moves

- Docs-only lanes may run `git status`, `git diff --check`, `git diff --stat`, `git diff --name-only`, and exact path `find` checks.
- Implementation lanes may name exact pytest and py_compile targets only after implementation authority exists.
- CLI receipt planning may define future validation receipt shapes without implementing them.

## Forbidden Drift

- Do not run backend tests for a docs-only packet unless explicitly requested.
- Do not run live services as proof.
- Do not call providers/models as validation.
- Do not treat stale receipts as current truth.
- Do not let a passing check grant runtime, billing, private-data, or external-action authority.

## Review Boundary

Review before claiming a lane is done, before widening validation, or before using receipts as inputs to future agents.

## Why It Should Last 10-20 Moves

Validation boundaries are cross-cutting. This file should stop future lanes from either under-validating or overreaching into runtime.
