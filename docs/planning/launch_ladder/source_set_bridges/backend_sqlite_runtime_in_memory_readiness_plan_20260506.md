# Backend SQLite Runtime In-Memory Readiness Plan

Generated/reviewed: 2026-05-06

## 1. Status / Non-Authority

This is a docs-only planning bridge for the next possible runtime SQLite lane.

It does not authorize runtime implementation by itself. It does not implement runtime SQLite, import `sqlite3`, execute SQL, create database files, persist data, create migrations, add ingestion, add retrieval, touch app behavior, stage files, or commit.

The current baseline is `f7367d6 test(backend): tighten inert sqlite schema invariants`.

The current phase is a code-level static schema contract. `backend_sqlite_schema.py` defines inert schema metadata and SQL definition strings; `tests/test_backend_sqlite_schema.py` has 12 passing tests that enforce the static schema shape.

## 2. Source Basis

This plan is based on:

- `backend_data_contract.py`
- `backend_sqlite_schema.py`
- `tests/test_backend_data_contract.py`
- `tests/test_backend_sqlite_schema.py`
- `docs/planning/project_packets/05_BACKEND_SQLITE_SCHEMA_ORCHESTRATION/00_ACTIVE_HANDOFF.md`
- `docs/planning/launch_ladder/source_set_bridges/sqlite_schema_definition_repo_truth_20260506.md`
- `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_first_sqlite_implementation_plan_20260505.md`
- `docs/planning/launch_ladder/source_set_bridges/backend_retrieval_strategy_breadcrumb_20260506.md`

## 3. Recommended Next Runtime Proof If Separately Authorized

The smallest safe runtime proof should:

- create `backend_sqlite_runtime.py`;
- create `tests/test_backend_sqlite_runtime.py`;
- import `sqlite3` only inside `backend_sqlite_runtime.py`;
- use in-memory SQLite only;
- apply the existing inert schema strings from `backend_sqlite_schema.py` to an in-memory connection;
- verify all seven tables exist;
- verify columns and primary keys match `backend_sqlite_schema.py`;
- avoid DB files;
- avoid persistence;
- avoid migrations and migration runners;
- avoid app, API, or agent integration.

The future runtime implementation prompt must be separate, exact-path bounded, and explicit that this is an in-memory proof only.

## 4. Required Tests / Gates Before Any Persistent DB

Before any file-backed persistent database is allowed, tests and gates must prove:

- the runtime module is the only `sqlite3` importer;
- no DB files are created;
- in-memory schema creation succeeds;
- all seven tables exist;
- columns and primary keys match the static schema;
- no ingestion, indexing, retrieval, provider/model, or app paths are touched;
- a schema version or migration policy exists before file-backed persistence.

## 5. Migration / Versioning Recommendation

Do not jump straight to a file-backed DB.

The first runtime proof should be in-memory only.

Plan a schema version table or version metadata before persistent database creation. `backend_sqlite_schema.py` already has `SCHEMA_VERSION`, but persistence needs an explicit policy for how runtime code records, checks, and upgrades schema state.

Migration policy should be planned before DB files exist. The smallest non-sloppy sequence is:

1. docs-only runtime readiness bridge;
2. separately authorized in-memory runtime proof;
3. schema version table or version metadata decision;
4. migration policy;
5. file-backed database creation only after the above gates pass.

## 6. Hard Forbids For The First Runtime Lane

The first runtime lane must not include:

- file-backed DB;
- persistence;
- migrations or migration runners;
- ingestion or extraction;
- indexing, FTS, embeddings, vectors, RAG, or PageIndex;
- provider/model calls;
- Hermes, MCPs, or sync;
- private-root/private-data inspection;
- API routes;
- frontend/app behavior;
- Chief/Cassandra/Legal/polish-loop runtime edits;
- broad staging;
- `git add .`.

## 7. Runtime Boundary Notes

If later authorized, `backend_sqlite_runtime.py` may become the only place where `sqlite3` is imported.

`backend_sqlite_schema.py` should remain inert schema definition authority. Runtime code should consume the existing schema definitions; it should not fork the schema text, invent new tables, add domain-specific tables, or add retrieval/indexing behavior.

Tests should verify the runtime proof against `backend_sqlite_schema.py`, not against duplicated expectations.

## 8. Stop Conditions

Stop for another planning/static pass if a future prompt asks for:

- database files;
- persistence;
- migrations or migration runners;
- schema changes not already planned;
- ingestion, extraction, indexing, FTS, embeddings, vectors, RAG, or PageIndex;
- provider/model calls;
- Hermes, MCPs, or sync;
- private-root/private-data inspection;
- app, frontend, or API integration;
- Chief/Cassandra/Legal/polish-loop runtime edits;
- broad staging or `git add .`.

## 9. Validation Commands For This Planning Bridge

```bash
cd /home/openclaw
git status -sb --untracked-files=all
git diff --check
git diff --cached --check
python3 launch_ladder_contract_check.py
pytest tests/test_launch_ladder_static_contract.py
pytest tests/test_backend_data_contract.py
pytest tests/test_backend_sqlite_schema.py
python3 -m py_compile backend_data_contract.py backend_sqlite_schema.py launch_ladder_contract_check.py
git status -sb --untracked-files=all
```
