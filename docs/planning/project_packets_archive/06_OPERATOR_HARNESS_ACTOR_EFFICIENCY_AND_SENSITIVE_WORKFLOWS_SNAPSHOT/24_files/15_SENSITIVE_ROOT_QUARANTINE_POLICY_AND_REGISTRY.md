# Sensitive Root Quarantine Policy And Registry

Status type: FUTURE_LANE / BOUNDARY_GUARD

## Purpose

Define the future Sensitive Root Registry and Quarantine Intake policy as metadata-first, deny-content-access doctrine. This file protects sensitive legal, finance, music-law, and discovery zones from accidental LLM or agent access.

## Source Inputs

- `docs/planning/sensitive_roots/SENSITIVE_ROOT_REGISTRY_BREADCRUMB_20260507.md`
- Packet 05 `00_ACTIVE_HANDOFF.md`
- Packet 05 `15_30_BACKEND_SOURCE_SET_BRIDGE_AND_EXCLUSION_PLAN.md`
- Packet 05 `11_17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md`
- Packet 05 `19_backend_data_contract_semantic_contract_matrix_20260505.md`
- Packet 05 `00_ACTIVE_HANDOFF.md` built-state ledger for storage intelligence and authorization

## What It Governs

- Sensitive root as border checkpoint.
- Presence does not equal permission.
- Path does not equal content authorization.
- Local-only does not equal approved.
- Metadata-only awareness unless a future local-only approved lane exists.
- Strict quarantine for `Sensitive Discovery (no unauthorized approval)`.

## Repo Implementation Pointers

Future-only possible implementation would likely touch data contract/schema/repository/read-model tests only after exact authorization. Current proof pointers:

- `backend_data_contract.py`
- `backend_sqlite_schema.py`
- `backend_sqlite_repository.py`
- `backend_storage_intelligence.py`
- `tests/test_backend_storage_intelligence.py`
- `tests/test_backend_agent_context.py`

## Valid Future Lane Moves

- Static data contract planning for sensitive root metadata.
- SQLite table concept planning for registry fields.
- Pure read-model/risk helper planning.
- Operator Harness blocked/quarantine state display planning.

## Forbidden Drift

- No filesystem crawl.
- No content read.
- No private root traversal.
- No external LLM access.
- No OCR, summarization, automatic classification, movement, sync, permission changes, or ingestion.
- Do not inspect `/Users/hwinshipwheatley/Sensitive Folder For Review` or subfolders.

## Review Boundary

Review before any prompt mentions sensitive roots, legal/finance/music-law folders, quarantine, local-only actors, metadata scans, or content access.

## Why It Should Last 10-20 Moves

Sensitive-root boundaries must stay stable across many future lanes. This rail prevents curiosity, convenience, or path metadata from becoming access.
