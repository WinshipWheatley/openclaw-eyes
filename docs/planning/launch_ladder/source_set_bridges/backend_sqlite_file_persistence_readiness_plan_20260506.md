# Backend SQLite File Persistence Readiness Plan

Generated/reviewed: 2026-05-06

## 1. Status / Non-Authority

This is a docs-only planning bridge for a later, separately authorized file-backed SQLite persistence proof.

It does not implement file-backed SQLite, create database files, add persistence, edit runtime code, edit tests, create migrations or a migration runner, add ingestion, add extraction, add indexing, add FTS, add embeddings, add vectors, add RAG, add PageIndex behavior, call providers/models, invoke Hermes or MCPs, sync data, inspect private roots, add API routes, touch frontend/app behavior, stage files, or commit.

The current baseline is `02f0b61 docs(project): add faster workflow checkpoint rule`.

The runtime code baseline includes `f6a4030 feat(backend): add in-memory schema version checks`.

Current built state:

- `backend_sqlite_schema.py` defines seven semantic contract tables plus separate schema-control metadata.
- `SCHEMA_VERSION` exists as the code-level schema identity.
- `schema_versions` exists as a separate physical schema-control table, not as an eighth semantic contract table.
- `backend_sqlite_runtime.py` can create an in-memory SQLite connection only.
- In-memory runtime creation applies all physical schema definitions.
- In-memory schema version recording/checking exists and is explicit, not automatic.
- No file-backed SQLite persistence exists yet.

## 2. Source Basis

This plan is based on:

- `backend_sqlite_schema.py`
- `backend_sqlite_runtime.py`
- `tests/test_backend_sqlite_schema.py`
- `tests/test_backend_sqlite_runtime.py`
- `docs/planning/launch_ladder/source_set_bridges/backend_sqlite_schema_versioning_migration_policy_20260506.md`
- `docs/planning/launch_ladder/source_set_bridges/backend_sqlite_runtime_in_memory_readiness_plan_20260506.md`
- `docs/planning/project_orchestration/01_PROJECT_CHAT_OPERATOR_EXPERIENCE_CONTRACT.md`
- `docs/planning/project_orchestration/24_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md`

Terminal truth from `/home/openclaw` wins over this planning bridge if a later commit changes the built state.

## 3. File Path Policy

The first file-backed implementation may accept an explicit operator/test-provided path only.

Required path rules:

- accept an explicit `Path` object;
- use no default production path;
- use no private-root paths;
- perform no home-directory scanning;
- perform no environment-variable path magic;
- perform no auto-discovery;
- perform no app integration;
- perform no Mac mirror inference;
- require tests to use pytest `tmp_path`;
- keep every database file created by tests under the active test `tmp_path`.

The first slice should require the parent directory to already exist. It should not create parent directories. That keeps the proof narrow and makes accidental path expansion obvious.

The helper should reject directory paths. It should also reject paths whose parent does not exist.

## 4. Allowed First File-Backed Helper

If separately authorized later, the smallest acceptable helper shape is:

```python
create_file_backed_connection(db_path: Path) -> sqlite3.Connection
```

Required behavior for that future helper:

- require `db_path` to be an explicit `Path`;
- reject directory paths;
- reject a missing parent directory;
- create or open only the exact supplied database file;
- apply `sqlite_physical_schema_sql_definitions()`;
- record the current `SCHEMA_VERSION`;
- verify the recorded schema version matches before returning;
- return the connection;
- close the connection on schema-application or version-check failure.

The helper must not accept a string path, default path, environment-derived path, root directory, private-root path, or app-managed location in the first file-backed slice.

The helper must not add ingestion, repository/data-access layers, retrieval, app integration, API routes, schema migrations, or migration runner behavior.

## 5. Required Tests Before Commit

A later file-backed implementation commit must include tests proving:

- the database is created only under pytest `tmp_path`;
- directory paths are refused;
- missing parent paths are refused;
- all physical tables are created, including the seven semantic tables and `schema_versions`;
- the schema version is recorded;
- the schema version check passes for a newly created database;
- an existing database with missing schema version fails closed;
- an existing database with wrong schema version fails closed;
- no extra files appear outside the expected database location;
- if SQLite creates journal or WAL files, they are limited to the same `tmp_path` and match the expected database filename stem;
- existing in-memory behavior still passes unchanged;
- `backend_sqlite_runtime.py` remains the only backend SQLite lane importer of `sqlite3`;
- forbidden surfaces remain absent from the runtime module.

The first test pass must not rely on private directories, operator home paths, repository root writes, Mac mirror paths, environment variables, or hidden existing database state.

## 6. Migration Boundary

The first file-backed slice must not include a migration runner.

If the supplied database already exists and has a missing, unknown, ambiguous, or mismatched schema version, the first slice should fail closed. It should not attempt to repair, migrate, overwrite, backfill, copy, or delete the database.

Migration policy remains a future separate lane. A future migration runner must be planned after the file-backed proof can fail closed cleanly and after the operator explicitly authorizes migration behavior.

## 7. Hard Forbids

The later file-backed proof must not include:

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

It also must not include:

- default production database paths;
- home-directory scanning;
- environment-variable path magic;
- auto-discovery;
- automatic parent-directory creation in the first slice;
- migrations or migration runners;
- schema repair;
- data backfill;
- repository/data-access layers.

## 8. Next Implementation Prompt Outline

The later implementation prompt should be exact-path bounded.

Allowed files:

- `backend_sqlite_runtime.py`
- `tests/test_backend_sqlite_runtime.py`
- `docs/testing/VALIDATION_MAP.md` only if validation-map discoverability truly needs updating

Forbidden files and surfaces:

- `24_files/`
- `backend_sqlite_schema.py`, unless a concrete blocker is found and reported before editing
- app/API/agent/provider/Hermes/MCP/sync surfaces
- private-root/private-data surfaces
- frontend/app behavior
- Chief/Cassandra/Legal/polish-loop runtime files
- unrelated docs

Validation for the later implementation prompt:

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

## 9. Stop Conditions

Stop for operator/ChatGPT review if the later implementation prompt or working diff introduces:

- a default database path;
- app-owned storage;
- environment-based path selection;
- broad filesystem discovery;
- private-root access;
- automatic parent-directory creation;
- migration runner behavior;
- schema repair behavior;
- ingestion, extraction, indexing, retrieval, FTS, embeddings, vectors, RAG, or PageIndex;
- provider/model calls;
- Hermes, MCPs, sync, API routes, or frontend/app behavior;
- unexpected files outside `backend_sqlite_runtime.py`, `tests/test_backend_sqlite_runtime.py`, and an explicitly justified validation-map update.

## 10. Success Criteria

This planning bridge is successful when the next implementation prompt can safely add one file-backed SQLite proof without expanding into app behavior, retrieval, migrations, ingestion, or private-data authority.

The next implementation should feel boring: explicit path in, physical schema applied, schema version recorded and checked, connection returned, fail closed on mismatch, no wider system touched.
