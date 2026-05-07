# Backend Data Contract And Schema Truth

Status type: BUILT_TRUTH

## Purpose

Preserve the backend data contract and SQLite schema substrate as built truth that Packet 07 can rely on without re-opening implementation.

## Source Inputs

- Packet 06 `08_BACKEND_DATA_CONTRACT_AND_SCHEMA_TRUTH.md`
- Packet 06 final `00_ACTIVE_HANDOFF.md`
- Packet 05 backend SQLite source-set archive

## What It Governs

- Data contract truth as semantic vocabulary.
- SQLite schema truth as built substrate.
- Raw, compiled/wiki, relationship, synthesis, and write-back/capture separation.
- Synthesis-not-truth and operator-promotion boundaries.

## Repo Implementation Pointers

- `backend_data_contract.py`
- `backend_sqlite_schema.py`
- `tests/test_backend_data_contract.py`
- `tests/test_backend_sqlite_schema.py`

## Valid Future Lane Moves

- Reference schema and data contract as proof pointers for read-model, receipt, policy, and gated activation planning.
- Add schema only through later exact implementation authority.
- Use semantic families without broad implementation preload.

## Forbidden Drift

- Do not re-plan built substrate as unbuilt.
- Do not treat schema visibility as persistence, runtime, billing, legal, or private-data authority.
- Do not flatten synthesis into truth.
- Do not add domain tables from this rail alone.

## Review Boundary

Review when future work needs backend built-truth claims or new schema authority.

## Why It Should Last 10-20 Moves

The data contract remains foundational and stable enough to support Packet 07 without repeated rediscovery.
