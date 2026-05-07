# Backend Repository And Runtime Truth

Status type: BUILT_TRUTH

## Purpose

Preserve the file-backed SQLite runtime and semantic repository substrate as built truth, while keeping runtime service integration outside Packet 06 docs-only generation.

## Source Inputs

- Packet 05 `00_ACTIVE_HANDOFF.md`
- Packet 05 `03_sqlite_schema_definition_repo_truth_20260506.md`
- Packet 05 `22_backend_data_contract_storage_schema_plan_20260505.md`
- Packet 05 `23_backend_data_contract_sqlite_plan_20260505.md`
- Packet 05 `24_backend_data_contract_sqlite_implementation_readiness_20260505.md`

## What It Governs

- Repository helpers and caller-owned SQLite connection posture.
- File-backed persistence as built substrate, not speculative planning.
- The difference between repository/runtime substrate and live service integration.
- Future read models that rely on repository truth without starting services.

## Repo Implementation Pointers

- `backend_sqlite_runtime.py`
- `backend_sqlite_repository.py`
- `tests/test_backend_sqlite_runtime.py`
- `tests/test_backend_sqlite_repository.py`

## Valid Future Lane Moves

- Plan read-only query/read-model assembly.
- Plan CLI receipts that summarize repository state through deterministic read-only checks after a separate implementation prompt.
- Review runtime integration architecture without starting services.

## Forbidden Drift

- Do not run live runtime services from this packet.
- Do not treat repository helpers as external-action authority.
- Do not add migrations, service runners, polling, file crawlers, or sync from this rail.
- Do not inspect private roots to prove repository behavior.

## Review Boundary

Review when future lanes need persistence proof, runtime architecture review, or repository-derived receipts.

## Why It Should Last 10-20 Moves

Repository/runtime built truth is stable enough to anchor multiple read-model and receipt lanes while keeping live runtime work gated.
