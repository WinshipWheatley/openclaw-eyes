# Validation Map And Test Boundaries

Status type: OPERATING_DOCTRINE / BOUNDARY_GUARD

## Purpose

Preserve the difference between docs/source-set renewal, static receipts, focused tests, runtime checks, and forbidden live authority surfaces.

## Source Inputs

- Packet 06 `07_VALIDATION_MAP_AND_TEST_BOUNDARIES.md`
- Packet 06 final `00_ACTIVE_HANDOFF.md`
- Packet 06 receipt validation receipts
- `OPENCLAW_RUNTIME.md`
- `scripts/openclaw_receipts.py`
- `tests/test_openclaw_receipts.py`

## What It Governs

- Safe validation for docs renewal.
- Static checks for receipt and policy work.
- Focused tests for bounded implementation lanes.
- Why live runtime services, provider/model calls, invoice actions, MCP writes, private-root access, and legal content reads are not validation shortcuts.

## Repo Implementation Pointers

- `scripts/openclaw_receipts.py`
- `openclaw_sensitive_policy.py`
- `tests/test_openclaw_receipts.py`
- `tests/test_backend_agent_context.py`
- `tests/test_chief_listener_lifecycle.py`
- `tests/test_service_inventory_audit.py`
- `tests/test_legacy_launch_script_safety.py`

## Valid Future Lane Moves

- Docs renewal may run exact path checks, `git diff --check`, and changed-file receipts.
- Implementation lanes may run focused tests for touched code only.
- Static policy lanes may add no-content/no-echo tests.
- Runtime activation reviews may use static tests and notes without service launch.

## Forbidden Drift

- Do not run broad expensive suites as theater.
- Do not start services as proof.
- Do not call providers/models or MCPs as proof.
- Do not treat stale receipts as current truth.
- Do not let passing checks grant runtime, billing, legal, private-data, external-action, or hidden-memory authority.

## Review Boundary

Review before claiming a lane is complete, widening tests, or treating receipts as inputs for future agents.

## Why It Should Last 10-20 Moves

Validation boundaries cut across all Packet 07 work. This rail should prevent both under-validation and authority overreach.
