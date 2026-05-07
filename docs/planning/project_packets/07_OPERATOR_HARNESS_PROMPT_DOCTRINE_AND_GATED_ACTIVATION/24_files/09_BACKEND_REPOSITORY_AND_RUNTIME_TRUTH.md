# Backend Repository And Runtime Truth

Status type: BUILT_TRUTH

## Purpose

Preserve file-backed SQLite runtime and semantic repository substrate as built truth while keeping live runtime activation gated.

## Source Inputs

- Packet 06 `09_BACKEND_REPOSITORY_AND_RUNTIME_TRUTH.md`
- Packet 06 `20_RUNTIME_INTEGRATION_AND_RECOVERY_ARCHITECTURE.md`
- Packet 06 `22_RUNTIME_AUTHORITY_AND_LEGACY_GATING.md`
- Packet 06 final `00_ACTIVE_HANDOFF.md`

## What It Governs

- Repository helpers and caller-owned SQLite connection posture.
- File-backed persistence as built substrate.
- Separation between repository/runtime substrate and live service launch.
- Future read models that rely on repository truth without starting services.

## Repo Implementation Pointers

- `backend_sqlite_runtime.py`
- `backend_sqlite_repository.py`
- `tests/test_backend_sqlite_runtime.py`
- `tests/test_backend_sqlite_repository.py`

## Valid Future Lane Moves

- Plan read-only queries and read-model assemblies.
- Use repository proof pointers in activation readiness reviews.
- Define static recovery/readiness receipts without service launch.

## Forbidden Drift

- Do not run live runtime services.
- Do not treat repository helpers as external-action authority.
- Do not add migrations, service runners, file crawlers, polling, or sync from this rail.
- Do not inspect private roots to prove repository behavior.

## Review Boundary

Review when future lanes need persistence proof, runtime architecture review, or repository-derived receipts.

## Why It Should Last 10-20 Moves

Repository truth is stable enough to anchor Packet 07 while live runtime activation remains gated.
