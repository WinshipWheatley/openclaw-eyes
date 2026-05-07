# Backend Data Contract SQLite Implementation Readiness

Generated/reviewed: 2026-05-05

## 1. Status / Non-Authority

This is a docs-only SQLite implementation-readiness artifact for the backend data-contract substrate.

It prepares the first no-runtime SQLite schema-contract code slice. It does not authorize implementation by itself, and it does not implement SQLite, SQL DDL execution, migrations, persistence, database connections, file I/O, API routes, ingestion, extraction, indexing, embeddings, fixtures, runtime services, frontend/app behavior, provider/model calls, Hermes, MCPs, sync, source-set generation, private-root inspection, private-data inspection, commits, broad staging, or app behavior.

A later implementation prompt must be separate, exact-path allowlisted, context-filtered, and validated before any code changes begin.

## 2. Source Basis

This readiness artifact is based on:

- `backend_data_contract.py`
- `tests/test_backend_data_contract.py`
- `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_sqlite_plan_20260505.md`
- `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_storage_schema_plan_20260505.md`
- `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_semantic_contract_matrix_20260505.md`
- `docs/planning/launch_ladder/source_set_bridges/operator_north_star_machine_contract_20260505.md`
- `docs/planning/command_atlas/04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md`
- `launch_ladder_contract_check.py`
- `tests/test_launch_ladder_static_contract.py`
- `docs/testing/VALIDATION_MAP.md`

The source-set 04 bridge, context-filter doctrine, and doc 30 exclusion/classification-only handling remain binding. Docs 26/27/28/29 may provide exclusion, quarantine, source-category, owner-review, no-browsing, and private-root-excluded vocabulary only. They do not provide private-root content, backend input authority, ingestion authority, SQLite authority, provider/model context, MCP context, Hermes context, runtime authority, or cleanup/migration authority.

## 3. Readiness Decision

Decision: the next safe implementation step may be a separate no-runtime SQLite schema-contract code slice, but only after a future prompt explicitly authorizes it with exact paths.

That later slice should define pure-Python table-concept contract data and validation helpers for the first SQLite table concepts. It should not create a database, open a database connection, execute SQL DDL, create migration files, persist data, read or write files, call APIs, ingest, extract, index, embed, create fixtures, start runtime services, touch frontend/app behavior, invoke providers/models, invoke Hermes or MCPs, sync, inspect private roots, inspect private data, or perform app behavior.

The intended value of the next code slice is contract preservation, not storage behavior.

## 4. Exact Future Allowed Implementation Paths

Only a later, separate prompt may authorize code changes, and it should start with these exact paths:

- `backend_data_contract.py`
- `tests/test_backend_data_contract.py`
- `launch_ladder_contract_check.py` only if static enforcement must recognize the SQLite schema-contract slice
- `tests/test_launch_ladder_static_contract.py` only if checker coverage must follow
- `docs/testing/VALIDATION_MAP.md` only if validation discoverability changes

If the future prompt needs a new no-runtime SQLite schema-contract module or test file, it must name the exact new paths before work begins. Absent that explicit path allowance, no new implementation files are allowed.

## 5. Exact Forbidden Paths, Tools, And Behaviors

The future no-runtime SQLite schema-contract slice must not touch:

- Chief, Cassandra, Legal, polish-loop, runtime, secrets, credential, bridge, log, state, memory, config, or bin files;
- private-root or private-data paths;
- app/frontend files;
- API route files;
- migration directories or migration files;
- fixture directories or generated source-set folders;
- provider/model, Hermes, MCP, sync, runtime service, or service-control surfaces.

The future slice must not use or introduce:

- `sqlite3` imports or database connections;
- SQL DDL execution;
- migration runners or migration files;
- persistence helpers;
- file I/O helpers;
- API routes;
- ingestion, extraction, indexing, embeddings, chunking, source-set generation, or fixtures;
- runtime services, app behavior, frontend/app code, provider/model calls, Hermes, MCPs, sync, service control, or external calls;
- private-root/private-data inspection;
- broad scans, broad path access, broad staging, or `git add .`;
- auto-send, automated harassment, collection action, payment posting, bank action, legal advice, CPA action, relationship automation, or external communication.

## 6. First No-Runtime SQLite Schema-Contract Code Slice Scope

The first code slice should define table-concept contract surfaces only. It may describe table concept names, purposes, required conceptual fields, forbidden implementation behavior, and knowledge compiler layer relationships in pure Python.

It may add helper functions that list table concepts, normalize table concept names, check whether a table concept is known, return required conceptual fields, validate proposed conceptual fields, and return useful failure reasons.

It must remain no-runtime, no-persistence, no-file-I/O, no-DB-connection, no-SQL-DDL, and no-migrations. The helpers must be pure lookup and validation only.

## 7. First Table Concepts

These are table concepts only. They are not SQL DDL, column definitions, ORM models, migration instructions, database files, or persistence behavior.

| Table concept | Purpose |
| --- | --- |
| `semantic_records` | Central envelope for record identity, entity family, knowledge layer, contract state, validator decision, and accepted-knowledge derivation inputs. |
| `semantic_labels` | Separate labels for provenance, freshness, confidence, sensitivity, authority, and review status. |
| `semantic_relationships` | Directional semantic links, responsibility links, contradiction links, provenance links, freshness links, and authority/sensitivity links. |
| `provenance_refs` | Source-basis, source-set, manifest, bridge, packet, and receipt references without authority laundering. |
| `validation_receipts` | Static validation evidence as receipt-shaped metadata, not runtime authority or approval. |
| `operator_promotions` | Scope-bound operator write-back/capture decisions that support accepted-knowledge derivation. |
| `context_filter_receipts` | Pass, warn, block, or needs-review outcomes for context packages before execution influence. |

## 8. Required Conceptual Fields

The later code slice should preserve these conceptual fields at minimum:

| Table concept | Required conceptual fields |
| --- | --- |
| `semantic_records` | `record_id`, `entity_family`, `knowledge_layer`, `contract_state`, `validator_decision`, `synthesis_not_truth`, `accepted_knowledge_derived`, `provenance_refs`, `freshness_refs`, `confidence_label`, `sensitivity_label`, `authority_label`, `review_status_label` |
| `semantic_labels` | `label_id`, `target_record_id`, `label_name`, `label_value`, `label_basis`, `review_status` |
| `semantic_relationships` | `relationship_id`, `from_record_id`, `to_record_id`, `relationship_kind`, `relationship_state`, `provenance_refs`, `freshness_refs`, `authority_label`, `sensitivity_label` |
| `provenance_refs` | `provenance_ref_id`, `target_record_id`, `source_basis`, `source_set_ref`, `manifest_ref`, `bridge_ref`, `packet_ref`, `receipt_ref` |
| `validation_receipts` | `receipt_id`, `validated_target`, `validator_name`, `validation_result`, `failure_reasons`, `checked_at`, `source_basis` |
| `operator_promotions` | `promotion_id`, `target_record_id`, `operator_decision`, `receipt_ref`, `promotion_scope`, `promoted_by_operator`, `complete_label_set` |
| `context_filter_receipts` | `context_filter_receipt_id`, `context_package_ref`, `filter_scope`, `checked_inputs`, `withheld_surfaces`, `filter_outcome`, `finding_summary`, `review_route` |

The future implementation may choose different Python names only if tests prove the same conceptual fields remain present and the mapping to `backend_data_contract.py` is explicit.

## 9. Knowledge Compiler Separation

The future table-concept contract must preserve the knowledge compiler layers:

- raw;
- compiled/wiki;
- relationship;
- synthesis;
- write-back/capture.

The table-concept layer must preserve the loop:

```text
raw reality -> compiled/wiki pages -> relationships -> synthesis -> write-back/capture -> recompile
```

Storage concepts must not turn this into a truth ladder. Raw is evidence or opaque withheld existence, not truth. Compiled/wiki is interpretation, not accepted truth. Relationship is directional semantic linkage, not graph truth. Synthesis is draft, inferred, interpretive, contradictory, stale, sensitive/local-only, blocked, or needs review until captured. Write-back/capture is eligible for accepted knowledge only when labels, receipt, and operator promotion are complete.

## 10. Synthesis-Not-Truth Boundary

Synthesis must not become truth by table placement.

A future `semantic_records` table concept may include synthesis records only when they preserve knowledge layer, state, provenance, freshness, confidence, sensitivity, authority, review status, and `synthesis_not_truth` semantics. A synthesis record must not become accepted knowledge because it appears in a table, has relationships, was validated, was compiled, was indexed, or is visible to an operator surface.

Accepted knowledge may be derived only when all of these are true:

1. the target is in the write-back/capture layer;
2. the state is confirmed with receipt;
3. provenance, freshness, confidence, sensitivity, authority, and review status labels are complete;
4. an `operator_promotions` concept binds the target, scope, receipt, decision, and operator authority;
5. no excluded, private-root-excluded, blocked, unknown, stale, or needs-review boundary prevents acceptance.

If a future code slice defines an accepted-knowledge view or helper, it must be derived from those fields and tests must prove synthesis cannot be accepted knowledge by table placement alone.

## 11. Boundary Separation

The future table-concept contract must keep these boundaries separate:

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
| Review status | Review status remains distinct from approval and promotion. |

Approval, validation, context filtering, provenance, labels, and promotion must not collapse into one merged receipt or one boolean field.

## 12. Receivables / Accountability Steel Thread

The future table-concept contract may support receivables/accountability as semantic accountability records and relationships only.

It may represent:

- who is involved in work;
- who is responsible for payment, approval, escalation, legal/accounting action, or decision authority;
- what job, invoice, payment, client, organization, approval, or follow-up action the record concerns;
- what evidence, provenance, freshness, confidence, sensitivity, authority, and review labels apply;
- what is unknown, blocked, stale, contradictory, excluded, or needs review;
- what operator promotion or approval receipt exists for a precise scope.

It must not authorize automated harassment, automated sending, external sending, collection action, bank access, payment posting, final financial truth, legal advice, CPA action, private-root inspection, provider/model use, runtime action, or relationship automation.

The useful primitive is accountability, not chasing.

## 13. Required Tests For Later Code Slice

A later no-runtime SQLite schema-contract implementation must add or update tests proving:

- every first table concept exists: `semantic_records`, `semantic_labels`, `semantic_relationships`, `provenance_refs`, `validation_receipts`, `operator_promotions`, and `context_filter_receipts`;
- table concept names normalize correctly;
- each table concept exposes required conceptual fields;
- missing conceptual fields fail closed with useful reasons;
- forbidden implementation behavior remains attached to every table concept;
- forbidden terms such as SQLite implementation, SQL DDL execution, migration, persistence, database connection, file I/O, API route, ingestion, extraction, indexing, embedding, fixture, runtime service, provider/model call, Hermes, MCP, sync, source-set generation, and private-root inspection are not authorized;
- raw, compiled/wiki, relationship, synthesis, and write-back/capture layers remain separate;
- synthesis does not become accepted knowledge by table placement alone;
- operator promotion, validation receipt, provenance ref, and context-filter receipt remain separate concepts;
- provenance, freshness, confidence, sensitivity, authority, review status, validation receipt, and promotion boundaries are represented explicitly;
- receivables/accountability remains evidence-backed and non-outbound;
- helpers perform pure lookup and validation only, with no file I/O, database connections, API calls, provider/model calls, runtime behavior, Hermes, MCPs, sync, ingestion, extraction, indexing, embeddings, or fixtures.

## 14. Required Validation Before/After Later Code Slice

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

After a future no-runtime SQLite schema-contract implementation:

```bash
cd /home/openclaw
git status -sb --untracked-files=all
git diff --check
git diff --cached --check
python3 launch_ladder_contract_check.py
pytest tests/test_launch_ladder_static_contract.py
pytest tests/test_backend_data_contract.py
python3 -m py_compile backend_data_contract.py launch_ladder_contract_check.py
git status -sb --untracked-files=all
git diff --check
git diff --cached --check
```

If a later prompt authorizes a new Python module or test file, the py-compile and pytest commands must include that exact file or its exact test target.

## 15. Stop Conditions

Stop for another planning/static pass if any of these are true:

- the future prompt does not name exact allowed implementation paths;
- the future prompt asks for SQLite database creation, SQL DDL execution, migrations, persistence, database connections, file I/O, API routes, ingestion, extraction, indexing, embeddings, fixtures, runtime services, frontend/app behavior, provider/model calls, Hermes, MCPs, sync, source-set generation, private-root inspection, private-data inspection, or app behavior;
- the future prompt adds domain-specific invoice, payment, legal, tax, music, client, travel, or ordinary-life admin tables before the semantic core contract is proven;
- the future prompt weakens raw/compiled/wiki/relationship/synthesis/write-back separation;
- synthesis can become accepted truth by table placement, validation, indexing, visibility, or relationship presence;
- operator promotion, validation receipt, provenance ref, context-filter receipt, sensitivity, authority, freshness, confidence, or review status boundaries are merged or optional;
- receivables/accountability is framed as outbound action machinery;
- source-set 04 bridge, context-filter doctrine, doc 30 exclusion/classification-only handling, or private-root/private-data exclusions are omitted;
- static checks, tests, syntax checks, Markdown checks, final-byte checks, or editor diagnostics are not named.

## 16. Taste Pass Notes

Taste pass 1 grouped the artifact around future-agent decision flow: non-authority, paths, scope, table concepts, boundaries, tests, validation, and stop conditions.

Taste pass 2 tightened wording so table concepts remain conceptual and do not read like SQL DDL, ORM, migration, persistence, or runtime instructions.

Taste pass 3 was not used.

## 17. Next Safe Action

Next safe action: run a read-only proof pass or proceed to a separately authorized no-runtime SQLite schema-contract implementation prompt that names exact paths, restates forbidden behavior, and requires the validation commands above.

Do not proceed to SQLite database creation, SQL DDL execution, migrations, persistence, database connections, file I/O, APIs, ingestion, extraction, indexing, embeddings, fixtures, runtime services, frontend/app behavior, provider/model calls, Hermes, MCPs, sync, source-set generation, private-root/private-data inspection, or app behavior from this artifact.
