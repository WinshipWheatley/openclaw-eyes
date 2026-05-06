# Backend Data Contract SQLite Plan

Generated/reviewed: 2026-05-05

## 1. Status / Non-Authority

This is a docs-only SQLite planning artifact for the backend data-contract substrate.

It narrows the safest future SQLite/storage path after the no-runtime schema-contract layer in `backend_data_contract.py`. It does not implement SQLite, SQL DDL, migrations, persistence, database connections, file I/O, API routes, ingestion, indexing, embeddings, extraction, fixtures, runtime services, frontend/app code, provider/model calls, Hermes, MCPs, sync, source-set generation, private-root inspection, private-data inspection, commits, broad staging, or app behavior.

This artifact is not implementation authority. A future implementation prompt must be separate, exact-path allowlisted, context-filtered, and validated before any code changes begin.

## 2. Source Basis

This plan is based on:

- `backend_data_contract.py`
- `tests/test_backend_data_contract.py`
- `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_storage_schema_plan_20260505.md`
- `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_semantic_contract_matrix_20260505.md`
- `docs/planning/launch_ladder/source_set_bridges/operator_north_star_machine_contract_20260505.md`
- `docs/planning/command_atlas/04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md`
- `docs/planning/launch_ladder/source_sets/04_BACKEND_DATA_CONTRACT_READINESS/MANIFEST.md`
- `docs/planning/launch_ladder/24_OPERATOR_HARNESS_PLANNING_INDEX.md`
- `docs/INDEX.md`
- `docs/testing/VALIDATION_MAP.md`
- `launch_ladder_contract_check.py`
- `tests/test_launch_ladder_static_contract.py`

The source-set 04 bridge, context-filter doctrine, and doc 30 exclusion/classification-only handling remain binding. Docs 26/27/28/29 may provide exclusion, quarantine, source-category, owner-review, no-browsing, and private-root-excluded vocabulary only. They do not provide private-root content, backend input authority, ingestion authority, SQLite authority, provider/model context, MCP context, Hermes context, runtime authority, or cleanup/migration authority.

## 3. Planning Decision

Smallest future SQLite implementation slice: define a narrow, local SQLite schema-contract substrate for semantic records, labels, relationships, provenance references, validation receipts, operator promotions, and context-filter receipts, with tests that prove the planned stored shape preserves the Python contract semantics.

That future slice must be schema-only at first:

1. no database file creation;
2. no migration runner;
3. no connection-opening helper;
4. no file I/O;
5. no ingestion, extraction, indexing, embedding, API, runtime, provider/model, Hermes, MCP, sync, app, or fixture behavior;
6. no private-root/private-data inspection;
7. no domain-specific invoice, legal, tax, music, or life-admin tables.

The first implementation should produce inspectable schema-contract code and tests only. Actual persistence, database creation, migration execution, connection use, and runtime integration remain future-only until a later implementation-readiness gate explicitly authorizes them.

## 4. First Table Mapping

These are future SQLite table concepts only. They are not SQL DDL and not implementation instructions.

| Schema-contract surface | First SQLite table concept | Reason it belongs in the first slice |
| --- | --- | --- |
| `semantic_record` | `semantic_records` | Central envelope for record identity, entity family, knowledge layer, contract state, validator decision, and accepted-knowledge derivation inputs. |
| `semantic_label` | `semantic_labels` | Keeps provenance, freshness, confidence, sensitivity, authority, and review status explicit instead of embedded in prose. |
| `semantic_relationship` | `semantic_relationships` | Preserves directional links, contradictions, responsibility links, provenance links, and freshness links without treating graph presence as truth. |
| `provenance_ref` | `provenance_refs` | Records approved source basis, source-set, manifest, bridge, packet, and receipt references without laundering authority. |
| `validation_receipt` | `validation_receipts` | Stores static validation evidence as receipt-shaped metadata, not runtime authority. |
| `operator_promotion` | `operator_promotions` | Keeps accepted-knowledge promotion separate from records and labels, with target, scope, receipt, and operator decision. |
| `context_filter_receipt` | `context_filter_receipts` | Keeps pass/warn/block/needs-review context-filter outcomes separate from approval and execution authority. |

## 5. Future-Only Surfaces

These surfaces must remain future-only after the first SQLite schema slice:

- domain tables for invoices, payments, legal matters, tax matters, music works, projects, travel, ordinary-life admin, or clients;
- raw-content, extracted-text, rendered-fragment, chunk, embedding, full-text index, search, or file-source tables;
- provider/model prompt or output tables;
- Hermes, MCP, sync, runtime, service, app-state, log, or bridge-payload tables;
- migration-runner tables, job queues, ingestion ledgers, indexing ledgers, extraction ledgers, API state, or fixture tables;
- private-root path/content tables beyond opaque boundary class references explicitly allowed by a later prompt.

The first SQLite path should prove semantic separation before storing domain substance.

## 6. Normalized Representation Rules

Represent as normalized tables:

- semantic records;
- semantic labels;
- semantic relationships;
- provenance references;
- validation receipts;
- operator promotions;
- context-filter receipts.

Represent as labels, receipts, or edges rather than copied fields:

- provenance, freshness, confidence, sensitivity, authority, and review status;
- accepted-knowledge derivation;
- operator promotion, rejection, historical marking, sensitivity marking, and exclusion;
- validation outcomes and failure reasons;
- context-filter pass, warn, block, needs-review, withheld surfaces, and review routes;
- responsibility, contradiction, freshness, authority, sensitivity, and source-set relationships.

Do not represent synthesis as truth by table placement. Do not represent operator promotion as a boolean on `semantic_records` alone. Do not represent approval, validation, context filtering, and promotion as one merged receipt.

## 7. Knowledge Compiler Separation

Every future `semantic_records` row concept must carry a knowledge layer:

- raw;
- compiled/wiki;
- relationship;
- synthesis;
- write-back/capture.

Storage must preserve the loop:

```text
raw reality -> compiled/wiki pages -> relationships -> synthesis -> write-back/capture -> recompile
```

The SQLite layer must not turn this into a truth ladder. Raw is evidence or opaque withheld existence, not truth. Compiled/wiki is interpretation, not accepted truth. Relationship is a directional semantic link, not graph truth. Synthesis is draft/inferred/interpretive until captured. Write-back/capture is eligible for accepted knowledge only when labels, receipt, and operator promotion are complete.

## 8. Synthesis-Not-Truth Rule

Synthesis must remain stored as synthesis.

A future schema may make synthesis searchable or linkable only as a labeled semantic record with its own provenance, freshness, confidence, sensitivity, authority, review status, and state. It must not become accepted knowledge because it appears in a table, has relationships, was validated, was compiled, was indexed, or is visible to an operator surface.

Accepted knowledge may be derived only when all of these are true:

1. the target is in the write-back/capture layer;
2. the state is confirmed with receipt;
3. provenance, freshness, confidence, sensitivity, authority, and review status labels are complete;
4. an `operator_promotion` record binds the target, scope, receipt, decision, and operator authority;
5. no excluded, private-root-excluded, blocked, unknown, stale, or needs-review boundary prevents acceptance.

If a future schema wants an accepted-knowledge view, that view must be derived from those fields. It must not be manually set as stored truth.

## 9. Boundary Representation

The future SQLite schema should represent boundaries as separate semantic facts:

| Boundary | Representation posture |
| --- | --- |
| Provenance | `provenance_refs` with source basis, source-set ref, manifest ref, bridge ref, packet ref, and receipt ref. Visibility is not authority. |
| Freshness | label or receipt target with reviewed-at basis, stale condition, and exact target. No whole-system freshness. |
| Confidence | label with value and basis for the exact record. No unsupported certainty. |
| Sensitivity | label or boundary record for sensitivity class, withheld surface, local-only reason, and private-root-excluded marker. No content summaries for private categories. |
| Authority | label or boundary record for allowed use, forbidden implication, approval route, and external-action boundary. No hidden execution. |
| Review status | label for draft, needs review, reviewed, blocked, rejected, historical, or promoted status. Review status is not approval. |
| Validation receipt | separate receipt for static checks, target, validator, result, failure reasons, and source basis. It does not approve implementation or runtime work. |
| Operator promotion | separate promotion record with target, scope, operator decision, receipt reference, and complete-label assertion. It is not global truth. |
| Context-filter receipt | separate receipt for context package, checked inputs, withheld surfaces, outcome, finding summary, and review route. It is not execution approval. |

## 10. Receivables / Accountability Steel Thread

The SQLite substrate should support the receivables/accountability proof path by storing semantic accountability records and relationships, not outbound action machinery.

It may later represent:

- who is involved in work;
- who is responsible for payment, approval, escalation, legal/accounting action, or decision authority;
- what job, invoice, payment, client, organization, approval, or follow-up action the record concerns;
- what evidence, provenance, freshness, confidence, sensitivity, authority, and review labels apply;
- what is unknown, blocked, stale, contradictory, excluded, or needs review;
- what operator promotion or approval receipt exists for a precise scope.

It must not authorize automated harassment, automated sending, external sending, collection action, bank access, payment posting, final financial truth, legal advice, CPA action, private-root inspection, provider/model calls, runtime action, or relationship automation.

## 11. Allowed Future Implementation Paths

Only a later, separate prompt may authorize implementation, and it should start with these exact paths:

- `backend_data_contract.py`
- `tests/test_backend_data_contract.py`
- `launch_ladder_contract_check.py` only if static enforcement must recognize the SQLite planning or schema-contract slice
- `tests/test_launch_ladder_static_contract.py` only if checker coverage must follow
- `docs/testing/VALIDATION_MAP.md` only if validation discoverability changes

If the future prompt needs a new SQLite schema-contract module or test file, it must name the exact new paths before work begins. Absent that explicit path allowance, no new implementation files are allowed.

## 12. Forbidden Paths, Tools, And Behaviors

The following remain forbidden for the first SQLite path unless a later prompt explicitly narrows and authorizes them:

- SQLite database file creation;
- SQL DDL execution;
- migration files or migration runners;
- persistence helpers;
- database connections;
- file I/O helpers;
- API routes;
- ingestion, extraction, indexing, embeddings, chunking, source-set generation, or fixtures;
- runtime services, app behavior, frontend/app code, provider/model calls, Hermes, MCPs, sync, service control, or external calls;
- private-root/private-data inspection;
- Chief, Cassandra, Legal, polish-loop, runtime, secrets, credential, bridge, log, state, memory, config, or bin files;
- broad scans, broad path access, broad staging, or `git add .`;
- auto-send, collection action, payment posting, legal advice, CPA action, relationship automation, or external communication.

## 13. Required Validation Before/After Implementation

Before a future SQLite implementation prompt begins:

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

After a future SQLite schema-contract implementation:

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

Tests must prove:

- every required schema-contract surface maps to the expected first table concept;
- future-only surfaces remain future-only;
- raw, compiled/wiki, relationship, synthesis, and write-back/capture layers remain separate;
- synthesis does not become accepted knowledge by storage placement alone;
- operator promotion, validation receipt, provenance ref, and context-filter receipt remain distinct;
- provenance, freshness, confidence, sensitivity, authority, review status, validation receipt, and promotion boundaries are represented explicitly;
- receivables/accountability remains evidence-backed and non-outbound;
- forbidden implementation terms remain blocked.

## 14. Stale Conditions

This plan becomes stale when:

- `backend_data_contract.py` changes layers, states, labels, entity families, forbidden concepts, schema-contract surfaces, or accepted-knowledge semantics;
- `tests/test_backend_data_contract.py` changes coverage for schema surfaces, forbidden behavior, write-back/capture, entity families, or receivables/accountability;
- `backend_data_contract_storage_schema_plan_20260505.md` changes;
- `backend_data_contract_semantic_contract_matrix_20260505.md` changes;
- `operator_north_star_machine_contract_20260505.md` changes;
- Command Atlas context-filter doctrine changes;
- source-set 04 membership, freshness bridge, or doc 30 exclusion/classification handling changes;
- a later operator prompt explicitly authorizes SQLite implementation-readiness or implementation with a narrower plan.

## 15. Next Safe Action

Next move: add a fail-closed static gate for this SQLite plan before implementation-readiness.

Do not proceed directly to SQLite implementation from this planning artifact. The safe sequence is:

1. static gate for this plan;
2. read-only proof pass;
3. SQLite implementation-readiness prompt;
4. only then a separately authorized, exact-path, no-runtime SQLite schema-contract implementation slice.
