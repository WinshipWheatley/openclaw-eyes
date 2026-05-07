# CLI Receipt Layer And Low-Context Interface

Status type: FUTURE_LANE

## Purpose

Define a future lane for deterministic, read-only CLI receipts that make facts cheap and let LLMs spend tokens on judgment, drafting, and bounded patching instead of repeated discovery.

## Source Inputs

- `docs/planning/agent_efficiency/CLI_RECEIPT_LAYER_LOW_CONTEXT_BREADCRUMB_20260507.md`
- Packet 05 `00_ACTIVE_HANDOFF.md`
- Packet 05 `07_04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md`
- Packet 05 `10_VALIDATION_MAP.md`
- Packet 05 `01_01_PROJECT_CHAT_OPERATOR_EXPERIENCE_CONTRACT.md`
- `CORE_ARCHITECTURE_PRINCIPLES.md`
- `.gitignore`

## What It Governs

- Future receipt command shapes.
- Read-only deterministic repo/state summaries.
- Compact Markdown or JSON-ish receipt output.
- Receipt freshness, staleness, and authority limits.
- Relationship to context substrate and actor policies.

## Repo Implementation Pointers

Future-only candidates may include a new exact CLI file only after approval. Current proof pointers:

- `launch_ladder_contract_check.py`
- `tests/test_launch_ladder_static_contract.py`
- backend tests named in File 07

## Valid Future Lane Moves

- Plan `openclaw repo-check`.
- Plan `openclaw docs-only-guard --allowed <path>`.
- Plan `openclaw source-set-status <packet>`.
- Plan `openclaw changed-files-receipt`.
- Plan `openclaw no-private-root-check`.
- Plan tests that prove no private traversal and no mutation.

## Forbidden Drift

- No implementation from this rail alone.
- No write-capable CLI.
- No private-root access.
- No network or model/provider calls.
- No stale receipt treated as current truth.
- No hidden authority that bypasses handoffs.

## Review Boundary

Review before implementing any CLI, adding command names, wrapping tests, reading filesystem metadata, or surfacing receipts to agents.

## Why It Should Last 10-20 Moves

The receipt idea can support many future lanes. This file keeps the concept small, read-only, and authority-aware until an explicit implementation slice exists.
