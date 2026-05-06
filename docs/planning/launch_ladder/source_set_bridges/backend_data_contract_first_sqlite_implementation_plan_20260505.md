# Backend Data Contract First SQLite Implementation Plan

Generated/reviewed: 2026-05-05

## 1. Status / Non-Authority

This is a planning-only first SQLite implementation path artifact for the backend data-contract substrate.

It plans the smallest future actual SQLite schema-definition slice. It does not authorize implementation by itself, and it does not implement SQLite, import or use `sqlite3`, execute SQL DDL, create migrations, create persistence, open database connections, perform file I/O runtime behavior, create API routes, ingest, extract, index, embed, create fixtures, start runtime services, touch frontend/app behavior, call providers/models, invoke Hermes, invoke MCPs, sync, generate source sets, inspect private roots, inspect private data, commit, broadly stage, or perform app behavior.

A future implementation prompt must be separate, exact-path bounded, context-filtered, validated, and explicitly authorized before any code changes begin.

## 2. Source Basis

This plan is based on:

- `backend_data_contract.py`
- `tests/test_backend_data_contract.py`
- `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_sqlite_implementation_readiness_20260505.md`
- `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_sqlite_plan_20260505.md`
- `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_storage_schema_plan_20260505.md`
- `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_semantic_contract_matrix_20260505.md`
- `docs/planning/launch_ladder/source_set_bridges/operator_north_star_machine_contract_20260505.md`
- `docs/planning/command_atlas/04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md`
- `docs/planning/launch_ladder/source_sets/04_BACKEND_DATA_CONTRACT_READINESS/MANIFEST.md`
- `docs/planning/launch_ladder/30_BACKEND_SOURCE_SET_BRIDGE_AND_EXCLUSION_PLAN.md`
- `launch_ladder_contract_check.py`
- `tests/test_launch_ladder_static_contract.py`
- `docs/testing/VALIDATION_MAP.md`

The source-set 04 bridge, context-filter doctrine, and doc 30 exclusion/classification-only handling remain binding. Docs 26/27/28/29 may contribute exclusion, quarantine, owner-review, no-browsing, no-ingestion, and private-root-excluded vocabulary only. They do not provide private-root content, backend input authority, ingestion authority, provider/model context, MCP context, Hermes context, runtime authority, SQLite authority, migration authority, or app authority.

## 3. Planning Decision

Smallest future SQLite implementation slice: create an inert SQLite schema-definition module and tests for the seven semantic table concepts.

The first actual implementation may define:

1. a Python schema-definition module containing table definitions, conceptual column metadata, table ordering, and optional SQL schema strings as inert constants;
2. tests proving the schema definitions preserve `backend_data_contract.py` table-concept requirements and forbidden behavior boundaries;
3. no runtime storage behavior.

The first actual implementation must not create a database file, execute SQL DDL, open a `sqlite3` connection, create migration files, run migrations, persist records, read or write runtime data files, create fixtures, call APIs, ingest, extract, index, embed, start services, touch frontend/app behavior, call providers/models, invoke Hermes or MCPs, sync, inspect private roots, inspect private data, or perform app behavior.

Decision: the first implementation may create a Python schema-definition module and may include SQL DDL strings as inert constants only. It must not create a migration file. It must not execute SQL DDL. It must not import `sqlite3`.

Boundary shorthand for the future implementation prompt: no `sqlite3`, no database connections, no SQL DDL execution, no migrations, no persistence, and no file I/O runtime behavior.

## 4. Exact Future Allowed Implementation Paths

Only a later, separate implementation prompt may authorize edits, and it should allow only these exact paths for the first actual SQLite schema-definition slice:

- `backend_sqlite_schema.py`
- `tests/test_backend_sqlite_schema.py`
- `launch_ladder_contract_check.py` only if static enforcement must recognize the new implementation slice
- `tests/test_launch_ladder_static_contract.py` only if checker coverage must follow that static enforcement
- `docs/testing/VALIDATION_MAP.md` only if validation discoverability changes

The future prompt should read `backend_data_contract.py` and `tests/test_backend_data_contract.py` as source contract inputs, but it should not edit them in the first actual SQLite implementation slice. If the future prompt needs to change `backend_data_contract.py`, it must stop and become a no-runtime contract-hardening prompt instead.

No migration path is allowed in the first implementation slice. No database file path is allowed in the first implementation slice.

## 5. Exact Forbidden Paths, Tools, And Behaviors

The future implementation prompt must not touch:

- Chief, Cassandra, Legal, polish-loop, runtime, secrets, credential, bridge, log, state, memory, config, or bin files;
- private-root or private-data paths;
- app/frontend files;
- API route files;
- migration directories or migration files;
- fixture directories or generated source-set folders;
- provider/model, Hermes, MCP, sync, runtime service, or service-control surfaces.

The future implementation prompt must not use or introduce:

- `sqlite3` imports;
- SQLite runtime behavior;
- database connections;
- SQL DDL execution;
- migration files or migration runners;
- persistence helpers;
- file I/O runtime behavior;
- API routes;
- ingestion, extraction, indexing, embeddings, chunking, source-set generation, or fixtures;
- runtime services, app behavior, frontend/app behavior, provider/model calls, Hermes, MCPs, sync, service control, or external calls;
- private-root/private-data inspection;
- broad scans, broad path access, broad staging, or `git add .`;
- auto-send, automated harassment, automated sending, external sending, collection action, payment posting, bank action, legal advice, CPA action, relationship automation, or external communication.

## 6. Table-Creation Boundaries

The first schema-definition module may describe these table concepts only:

| Table concept | First implementation boundary |
| --- | --- |
| `semantic_records` | May define an inert table definition for record identity, entity family, knowledge layer, contract state, validator decision, synthesis-not-truth flag, accepted-knowledge derivation inputs, and label/provenance references. It must not store raw private content or directly imply accepted truth. |
| `semantic_labels` | May define an inert table definition for target-scoped labels. Labels must keep provenance, freshness, confidence, sensitivity, authority, and review status explicit. |
| `semantic_relationships` | May define an inert table definition for directional links. Relationship presence must not imply relationship truth, action authority, cleanup authority, or private-root access. |
| `provenance_refs` | May define an inert table definition for source basis, source-set, manifest, bridge, packet, and receipt references. Visibility must not create authority. |
| `validation_receipts` | May define an inert table definition for static validation evidence. Validation receipt boundaries must remain separate from approval, promotion, and runtime authority. |
| `operator_promotions` | May define an inert table definition for scope-bound operator write-back/capture decisions. Promotion must remain separate from records, labels, and validation receipts. |
| `context_filter_receipts` | May define an inert table definition for pass, warn, block, or needs-review context-filter outcomes. Context-filter receipt boundaries must remain separate from execution approval. |

The first implementation must not add domain tables for invoices, payments, legal matters, tax matters, music works, projects, travel, ordinary-life admin, clients, bank accounts, provider outputs, runtime logs, source files, chunks, embeddings, indexes, prompts, Hermes packets, MCP payloads, sync state, fixtures, or app state.

## 7. Migration Posture

Allowed in the first future implementation:

- a Python schema-definition module;
- inert table-definition objects or dataclasses;
- inert SQL schema strings as constants, if tests prove they are never executed;
- schema ordering metadata;
- validation helpers that compare schema definitions against `backend_data_contract.py`.

Forbidden in the first future implementation:

- migration files;
- migration directories;
- migration runners;
- schema application helpers;
- SQLite database files;
- `sqlite3` connections;
- SQL DDL execution;
- persistence functions;
- file I/O runtime behavior.

If a future prompt asks for migration files, database creation, connection helpers, persistence, or SQL execution, it must stop for another planning/static pass.

## 8. Future Test Requirements

A future first actual SQLite implementation must add tests proving:

- `backend_sqlite_schema.py` exists and exposes exactly the seven first table concepts;
- every table concept maps to the matching `backend_data_contract.py` SQLite table concept;
- every required conceptual field from `backend_data_contract.py` is represented;
- `semantic_records`, `semantic_labels`, `semantic_relationships`, `provenance_refs`, `validation_receipts`, `operator_promotions`, and `context_filter_receipts` remain distinct;
- SQL DDL strings, if present, are inert constants only and no helper executes them;
- no `sqlite3`, database connection, persistence, file I/O runtime behavior, migration, API, ingestion, extraction, indexing, embedding, fixture, provider/model, Hermes, MCP, sync, source-set generation, private-root inspection, private-data inspection, runtime service, frontend/app behavior, or app behavior is introduced;
- raw, compiled/wiki, relationship, synthesis, and write-back/capture remain separate;
- synthesis cannot become accepted truth by table placement;
- operator promotion, validation receipt, provenance ref, context-filter receipt, sensitivity, authority, freshness, confidence, review status, and validation-receipt boundaries remain explicit and separate;
- receivables/accountability support remains semantic and non-outbound;
- helper functions are pure lookup/validation and do not perform runtime behavior.

## 9. Knowledge Compiler Separation

The future schema-definition module must preserve the knowledge compiler loop:

```text
raw reality -> compiled/wiki pages -> relationships -> synthesis -> write-back/capture -> recompile
```

Every `semantic_records` definition must preserve an explicit knowledge-layer field for:

- raw;
- compiled/wiki;
- relationship;
- synthesis;
- write-back/capture.

Storage placement is not a truth ladder. Raw is evidence or opaque withheld existence, not truth. Compiled/wiki is interpretation, not accepted truth. Relationship is directional semantic linkage, not graph truth. Synthesis is draft, inferred, interpretive, contradictory, stale, sensitive/local-only, blocked, or needs review until captured. Write-back/capture is eligible for accepted knowledge only when labels, receipt, and operator promotion are complete.

## 10. Synthesis-Not-Truth Boundary

Synthesis must not become truth by table placement.

A future `semantic_records` schema definition may include synthesis rows only when it preserves knowledge layer, state, provenance, freshness, confidence, sensitivity, authority, review status, validation receipt, and `synthesis_not_truth` semantics.

A synthesis record must not become accepted knowledge because it appears in a table, has relationships, has SQL DDL, was validated, was compiled, was indexed, or is visible to an operator surface.

Accepted knowledge may be derived only when all of these are true:

1. the target is in the write-back/capture layer;
2. the state is confirmed with receipt;
3. provenance, freshness, confidence, sensitivity, authority, and review status labels are complete;
4. an `operator_promotions` table concept binds the target, scope, receipt, decision, and operator authority;
5. no excluded, private-root-excluded, blocked, unknown, stale, or needs-review boundary prevents acceptance.

The first implementation must not define an accepted-knowledge storage shortcut, manually stored truth flag, or auto-promoted truth view.

## 11. Boundary Separation

The future schema-definition module must keep these boundaries separate:

| Boundary | Required separation |
| --- | --- |
| Operator promotion | `operator_promotions` remains separate from `semantic_records`, `semantic_labels`, and `validation_receipts`. Promotion is scope-bound and not global truth. |
| Validation receipt | `validation_receipts` records static validation evidence only. It does not approve implementation, runtime work, or accepted truth. |
| Provenance ref | `provenance_refs` records source basis and bridge/manifest/packet/receipt references. Visibility is not authority. |
| Context-filter receipt | `context_filter_receipts` records pass/warn/block/needs-review outcomes. It is not execution approval. |
| Sensitivity | Sensitivity remains an explicit label or boundary with withheld surfaces and private-root-excluded markers. No private content summaries. |
| Authority | Authority remains an explicit label or boundary with allowed use, forbidden implication, approval route, and external-action boundary. No hidden execution. |
| Freshness | Freshness remains target-scoped with reviewed-at basis and stale condition. No whole-system freshness. |
| Confidence | Confidence remains a label with value and basis for the exact record. No unsupported certainty. |
| Review status | Review status remains distinct from approval, validation, and promotion. |
| Validation-receipt boundary | Validation receipt references may support review, but they do not become operator promotion, persistence authority, runtime authority, or accepted truth. |

Approval, validation, context filtering, provenance, labels, and promotion must not collapse into one merged receipt or one boolean field.

## 12. Receivables / Accountability Steel Thread

The future SQLite schema-definition slice may support receivables/accountability as semantic accountability records, labels, and relationships only.

It may represent:

- who is involved in work;
- who is responsible for payment, approval, escalation, legal/accounting action, or decision authority;
- what job, invoice, payment, client, organization, approval, or follow-up action the record concerns;
- what evidence, provenance, freshness, confidence, sensitivity, authority, and review labels apply;
- what is unknown, blocked, stale, contradictory, excluded, or needs review;
- what operator promotion or approval receipt exists for a precise scope.

It must not authorize automated harassment, automated sending, external sending, runtime action, private-root inspection, provider/model use, collection action, bank access, bank/payment posting, final financial truth, legal advice, CPA action, app behavior, or relationship automation.

The useful primitive remains accountability, not chasing.

## 13. Required Stop Conditions

Stop for another planning/static pass if any of these are true:

- the future prompt does not name exact allowed implementation paths;
- the future prompt asks to edit `backend_data_contract.py` instead of only reading it as source contract input;
- the future prompt asks for `sqlite3`, SQLite runtime behavior, database connections, SQL DDL execution, migration files, migration runners, persistence, database files, or file I/O runtime behavior;
- the future prompt asks for API routes, ingestion, extraction, indexing, embeddings, fixtures, runtime services, frontend/app behavior, provider/model calls, Hermes, MCPs, sync, source-set generation, private-root inspection, private-data inspection, or app behavior;
- the future prompt adds domain-specific invoice, payment, legal, tax, music, client, travel, ordinary-life admin, bank, ledger, prompt, provider-output, runtime, source-file, chunk, embedding, index, fixture, or app-state tables;
- the future prompt weakens raw/compiled/wiki/relationship/synthesis/write-back separation;
- synthesis can become accepted truth by table placement, SQL DDL, validation, indexing, visibility, or relationship presence;
- operator promotion, validation receipt, provenance ref, context-filter receipt, sensitivity, authority, freshness, confidence, review status, or validation-receipt boundaries are merged or optional;
- receivables/accountability is framed as outbound action machinery;
- source-set 04 bridge, context-filter doctrine, doc 30 exclusion/classification-only handling, or private-root/private-data exclusions are omitted;
- validation commands, static gate updates, syntax checks, whitespace checks, final status checks, or editor diagnostics are not named.

## 14. Exact Validation Commands For Later Implementation

Before a future implementation prompt begins:

```bash
cd /home/openclaw
pwd
git status -sb --untracked-files=all
git log --oneline -8
git diff --check
git diff --cached --check
python3 launch_ladder_contract_check.py
pytest tests/test_launch_ladder_static_contract.py
pytest tests/test_backend_data_contract.py
python3 -m py_compile backend_data_contract.py launch_ladder_contract_check.py
```

After a future first actual SQLite schema-definition implementation:

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
git diff --check
git diff --cached --check
```

Run editor diagnostics on every touched file. If a future prompt authorizes additional exact files, validation must include those exact files or tests.

## 15. Taste Pass Notes

Taste pass 1 grouped the artifact around future-agent execution flow: non-authority, exact paths, table boundaries, migration posture, tests, semantic boundaries, stop conditions, and validation.

Taste pass 2 tightened wording so the first future implementation is actual SQLite schema definition while remaining inert and non-runtime.

Taste pass 3 was not used.

## 16. Next Safe Action

Next safe action: a read-only proof pass against this plan and its static gate, or a separately authorized first actual SQLite schema-definition implementation prompt that names exact paths and restates all forbidden behavior.

Do not proceed to SQLite runtime behavior, `sqlite3` usage, SQL DDL execution, migrations, persistence, DB connections, file I/O runtime behavior, API routes, ingestion, extraction, indexing, embeddings, fixtures, runtime services, frontend/app behavior, provider/model calls, Hermes, MCPs, sync, source-set generation, private-root/private-data inspection, or app behavior from this artifact.
