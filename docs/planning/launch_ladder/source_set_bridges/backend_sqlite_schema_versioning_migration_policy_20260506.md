# Backend SQLite Schema Versioning Migration Policy

Generated/reviewed: 2026-05-06

## 1. Status / Non-Authority

This is a docs-only planning bridge for schema versioning and migration policy on the backend SQLite runtime path.

It does not implement a migration runner, create file-backed databases, create database files, add persistence, add ingestion, add extraction, add indexing, add FTS, add embeddings, add vectors, add RAG, add PageIndex behavior, call providers/models, invoke Hermes or MCPs, sync data, inspect private roots, add API routes, touch frontend/app behavior, stage files, or commit.

The current baseline is `5ebb706 test(backend): harden in-memory sqlite runtime proof`.

The current phase is a hardened in-memory SQLite runtime proof. `backend_sqlite_schema.py` remains the inert schema-definition authority, and `backend_sqlite_runtime.py` may apply those static schema strings only to an in-memory connection.

## 2. Source Basis

This policy is based on:

- `backend_data_contract.py`
- `backend_sqlite_schema.py`
- `backend_sqlite_runtime.py`
- `tests/test_backend_data_contract.py`
- `tests/test_backend_sqlite_schema.py`
- `tests/test_backend_sqlite_runtime.py`
- `docs/planning/launch_ladder/source_set_bridges/backend_sqlite_runtime_in_memory_readiness_plan_20260506.md`
- `docs/planning/project_packets/05_BACKEND_SQLITE_SCHEMA_ORCHESTRATION/00_ACTIVE_HANDOFF.md`
- `docs/planning/project_orchestration/24_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md`

## 3. Policy Decision

Schema versioning should use both:

- `SCHEMA_VERSION` metadata in `backend_sqlite_schema.py` as the code-level static schema identity; and
- a future static `schema_versions` table definition before any file-backed persistent database is authorized.

The current `SCHEMA_VERSION` constant is enough for the in-memory proof. It is not enough for file-backed persistence, because a persistent database must be able to record which schema created it and what policy governs future upgrades.

The `schema_versions` table should not be part of the seven semantic contract tables. It is schema-control metadata, not semantic knowledge. Keeping it separate protects the seven-table contract from accidental drift while still giving future runtime code a place to verify database shape before persistence is allowed.

## 4. Future Static Version Table Shape

If separately authorized, the smallest static version table should be named `schema_versions`.

Minimum fields:

- `schema_version_id` - stable primary key for the version row.
- `schema_version` - the exact code-level schema version string, matching `SCHEMA_VERSION`.
- `schema_name` - stable namespace such as `backend_sqlite`.
- `schema_applied_at` - timestamp text for when a runtime applied the schema.
- `schema_source_ref` - commit, receipt, or artifact reference for the static schema source.
- `migration_policy_ref` - planning or policy artifact governing upgrades.
- `is_current` - integer flag for the current active schema row.

This table should be represented as inert static schema metadata first. It must not introduce a migration runner, file-backed database, persistence, runtime file I/O, indexing, retrieval, app/API integration, provider/model calls, sync behavior, or private-root inspection.

## 5. Runtime Checks Required Before File-Backed DBs

Before any file-backed database is allowed, tests must prove:

- `backend_sqlite_runtime.py` is still the only backend SQLite lane importer of `sqlite3`;
- no DB files are created by the in-memory lane;
- in-memory schema creation succeeds;
- all seven semantic contract tables exist;
- the separate schema version metadata surface exists if that static table has been authorized;
- table columns and primary keys match `backend_sqlite_schema.py`;
- the runtime can read schema-version metadata from the database without writing application data;
- the runtime fails closed when an existing database has an unknown, missing, or mismatched schema version;
- no ingestion, extraction, indexing, FTS, embeddings, vectors, RAG, PageIndex, provider/model, Hermes, MCP, sync, private-root, API, frontend, app, Chief, Cassandra, Legal, or polish-loop runtime path is touched.

## 6. Migration Runner Behavior Still Forbidden

Until separately authorized, the runtime must not include:

- migration files;
- migration directories;
- migration runners;
- automatic upgrade/downgrade behavior;
- schema-altering runtime commands;
- data backfill behavior;
- data copy behavior;
- file-backed persistence;
- runtime file I/O;
- app/API integration.

A future migration runner must be planned as its own lane after schema version metadata exists and after file-backed persistence policy is approved.

## 7. Smallest Non-Sloppy Path

The smallest safe path from the current in-memory proof to eventual file-backed persistence is:

1. Keep the current `SCHEMA_VERSION` metadata as code-level identity.
2. Add a static/inert `schema_versions` table definition in a separate schema hardening slice.
3. Tighten static schema tests so the version table is clearly separate from the seven semantic contract tables.
4. Tighten runtime in-memory tests so runtime creation includes the version table only after the static table is authorized.
5. Add a docs-only file-backed persistence readiness plan.
6. Add tests that fail closed for missing, unknown, or mismatched schema versions.
7. Only then consider a separately authorized file-backed database proof.
8. Plan migrations before any migration runner exists.

Do not jump directly from the in-memory proof to file-backed DB creation.

## 8. Stop Conditions

Stop for operator review if a future prompt asks this lane to:

- create a file-backed DB;
- create database files;
- persist data;
- create migrations or a migration runner;
- alter schema at runtime;
- ingest or extract documents;
- index, add FTS, embed, add vectors, add RAG, or implement PageIndex;
- call providers/models;
- invoke Hermes, MCPs, or sync;
- inspect private roots or private data;
- add API routes;
- touch frontend/app behavior;
- edit Chief/Cassandra/Legal/polish-loop runtime files;
- broadly stage files or use `git add .`.

## 9. Recommended Next Prompt Type

Recommended next prompt type: static schema hardening, not runtime implementation.

The next bounded prompt should decide whether to add the separate inert `schema_versions` table to `backend_sqlite_schema.py` and update static/runtime tests to recognize it as schema-control metadata, not as an eighth semantic contract table.

## 10. Validation Commands For This Planning Bridge

```bash
cd /home/openclaw
git status -sb --untracked-files=all
git diff --check
git diff --cached --check
python3 launch_ladder_contract_check.py
pytest tests/test_launch_ladder_static_contract.py
pytest tests/test_backend_data_contract.py
pytest tests/test_backend_sqlite_schema.py
pytest tests/test_backend_sqlite_runtime.py
python3 -m py_compile backend_data_contract.py backend_sqlite_schema.py backend_sqlite_runtime.py launch_ladder_contract_check.py
git status -sb --untracked-files=all
```
