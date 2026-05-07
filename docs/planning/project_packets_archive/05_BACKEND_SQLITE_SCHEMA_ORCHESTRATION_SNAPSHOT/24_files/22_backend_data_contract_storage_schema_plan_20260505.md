# Backend Data Contract Storage Schema Plan

Generated/reviewed: 2026-05-05

## 1. Status / Non-Authority

This is a docs-only storage/schema planning artifact for the backend data contract spine.

It explains how the current pure-Python semantic contract may later map to SQLite/storage concepts. It does not implement SQLite, schema migrations, SQL DDL, persistence, API routes, ingestion, indexing, embeddings, extraction, chunking, source-set generation, runtime services, frontend/app code, provider/model calls, Hermes, MCPs, sync, private-root inspection, fixture generation, commits, or broad staging.

No private roots, private data, legal-private content, finance-private content, tax records, music-law-private content, secrets, credentials, provider/model prompts, MCP context, Hermes output, sync output, runtime state, logs, memory/state/config/bin contents, SQLite artifacts, embeddings, chunks, extraction output, indexing output, or generated runtime artifacts are source inputs to this plan.

## 2. Source Basis

This plan is based on:

- `backend_data_contract.py`
- `tests/test_backend_data_contract.py`
- `docs/planning/launch_ladder/source_set_bridges/operator_north_star_machine_contract_20260505.md`
- `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_semantic_contract_matrix_20260505.md`
- `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_implementation_readiness_checklist_20260505.md`
- `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_first_implementation_slice_readiness_20260505.md`
- `docs/planning/command_atlas/04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md`
- `docs/planning/launch_ladder/source_sets/04_BACKEND_DATA_CONTRACT_READINESS/MANIFEST.md`
- `docs/planning/launch_ladder/24_OPERATOR_HARNESS_PLANNING_INDEX.md`
- `docs/INDEX.md`
- `docs/testing/VALIDATION_MAP.md`

The Python module and tests are source basis only for the current semantic vocabulary and validator behavior. They do not authorize persistence or runtime behavior.

## 3. Bounce-Rule Classification

Classification result: Additive.

This plan is additive because it narrows how a future storage/schema prompt should preserve the already-approved semantic contract spine. It does not add a storage engine decision beyond the existing SQLite/storage planning lane, does not change entity families, does not authorize schema implementation, and does not weaken private-root, provider/model, Hermes, MCP, ingestion, indexing, runtime, app, or source-set-generation boundaries.

If a later storage/schema prompt treats this plan as permission to create tables, migrations, databases, APIs, ingestion, fixtures, or runtime services, that prompt is conflicting and must stop for explicit operator review.

## 4. Planning Decision

Recommended future storage shape: normalized semantic core.

Storage should be a ledger of semantic boundaries, not an engine of action.

The future storage layer should store semantic records, labels, evidence/provenance/freshness references, relationships, and operator promotions as separate concepts. It should not start with one wide domain table per life lane, and it should not flatten synthesis into truth.

The storage model should be boring underneath and expressive above it: a stable record envelope with explicit layer, family, state, labels, and authority boundaries, plus separate relationship and promotion records. Domain meaning should remain constrained by the Python contract validators until a separately authorized schema implementation mirrors those constraints.

## 5. Approaches Considered

| Approach | Benefits | Risks | Decision |
| --- | --- | --- | --- |
| One wide semantic records table | Simple first shape; easy to inspect. | Encourages label mixing, unclear provenance/freshness, and accidental synthesis-as-truth. | Do not choose as the main plan. |
| Normalized semantic core | Preserves layer/family/state separation, label bundles, evidence links, freshness, authority, sensitivity, relationships, and operator promotions. | Requires more careful constraints and validation tests later. | Recommended. |
| Domain-specific tables first | Familiar for invoices, payments, legal matters, music works, and projects. | Freezes business assumptions too early and risks private/source authority drift. | Defer until semantic core proves the contract. |

## 6. Future Storage Surfaces

These are conceptual storage surfaces only. They are not SQL DDL, column definitions, migrations, ORM models, fixture shapes, or implementation instructions.

| Future conceptual table | Contract concepts mapped | Required boundary |
| --- | --- | --- |
| `semantic_records` | Record identity, entity family, knowledge layer, contract state, target reference, record summary, validator decision. | Stores semantic meaning only; no raw private content, provider output, runtime truth, or action authority. |
| `record_labels` | Provenance, freshness, confidence, sensitivity, authority, and review status labels. | Labels must remain explicit and complete before write-back/capture acceptance. |
| `record_evidence_refs` | Evidence reference, evidence status, missing-evidence reason, opaque blocked-source reference. | Evidence refs do not imply truth, ingestion, extraction, browsing, or provider safety. |
| `record_provenance_refs` | Source basis, source-set reference, manifest reference, bridge reference, packet reference, receipt reference. | Provenance does not create authority by visibility, packaging, mirroring, or indexing. |
| `record_freshness_claims` | Freshness target, freshness basis, reviewed-at label, stale condition. | Freshness is target-scoped only; never whole-system health or sync success. |
| `record_authority_bounds` | Authority scope, allowed use, forbidden implication, approval route, external-action boundary. | Storage visibility does not authorize sending, financial action, legal/CPA action, runtime mutation, or provider/model calls. |
| `record_sensitivity_bounds` | Sensitivity class, local-only reason, withheld surface, private-root-excluded boundary. | Private category names may be stored as boundary labels only, never as content summaries. |
| `semantic_relationships` | Directional links among records, entity responsibility links, provenance links, contradiction links, freshness links, source-set links. | Relationship existence does not mean relationship truth, cleanup authority, private-root access, or cross-context blending. |
| `operator_promotions` | Operator promotion, rejection, historical marking, sensitivity marking, exclusion, receipt/scope reference. | Accepted knowledge must be derived from bounded promotion, not inferred from a record being present. |
| `context_filter_receipts` | Pass, warn, block, or needs-review outcome for a context package. | Advisory unless paired with separate approval; block/needs-review halts execution influence. |
| `storage_validation_receipts` | Static validation results for schema readiness and contract-preservation checks. | Validation receipts are evidence of checks, not runtime/service/provider authority. |

## 7. Contract Concept Mapping

| Contract concept | Future storage representation | Must preserve |
| --- | --- | --- |
| `KnowledgeLayer` | Explicit layer value on each semantic record. | Raw, compiled/wiki, relationship, synthesis, and write-back/capture stay distinct. |
| `EntityFamily` | Explicit family value on each semantic record. | Unknown and excluded families remain fail-closed. |
| `ContractState` | Explicit state value on each semantic record. | Unknown-style and excluded-style states cannot confirm truth accidentally. |
| `ContractLabel` | Separate label records or label fields with completeness checks. | Write-back/capture requires provenance, freshness, confidence, sensitivity, authority, and review status. |
| `ContractDecision` | Stored validator decision or validation receipt when useful later. | Decision cannot override the validator or become action authority. |
| Implementation-forbidden concepts | Forbidden-use checks before storage acceptance. | Storage may not launder API, SQLite, provider/model, ingestion, runtime, private-root, harassment, auto-send, or collection-action authority. |
| `promoted_by_operator` | Promotion record with target, scope, receipt, decision basis, and timestamp when later authorized. | Promotion is bounded; it is not global truth, external safety, or execution approval. |

## 8. Knowledge Layer Representation

The future schema must represent the knowledge compiler layers as layer semantics, not as a truth ladder.

| Layer | Future storage meaning | Must not imply |
| --- | --- | --- |
| Raw layer | Approved evidence, missing evidence, or opaque withheld existence. | Truth, public safety, provider readiness, ingestion, extraction, or private browsing. |
| Compiled/wiki layer | Durable notes, summaries, briefs, and pages with source basis and labels. | Accepted truth, external sharing, app display authority, or schema authority. |
| Relationship layer | Directional links, tags, responsibility edges, provenance edges, freshness edges, contradiction edges, and authority/sensitivity edges. | Graph database truth, cleanup authority, private-root exposure, or cross-context blending. |
| Synthesis layer | Draft, inferred, interpretive, contradictory, stale, sensitive/local-only, blocked, or needs-review judgment. | Automatic truth, operator approval, provider safety, action readiness, hidden execution, or taste override. |
| Write-back/capture layer | Labeled captured insight with operator promotion and receipt/scope basis. | Silent promotion, global truth, external action authority, or runtime implementation. |

Accepted knowledge should be a derived condition only: valid write-back/capture layer, confirmed-with-receipt state, complete required labels, and operator promotion within scope. A future schema may expose an accepted-knowledge view only if it is derived from those fields and cannot be manually set as a shortcut.

## 9. Label And Promotion Field Mapping

| Label or gate | Future stored field meaning | Required guard |
| --- | --- | --- |
| Provenance | Source basis, source-set reference, manifest reference, bridge reference, packet or receipt reference. | No source laundering; visibility is not authority. |
| Freshness | Named target, reviewed-at basis, stale condition, freshness source. | No global freshness or sync-health implication. |
| Confidence | Confidence label and basis for the exact record. | No unsupported certainty or truth promotion. |
| Sensitivity | Sensitivity class, withheld surface, local-only reason, private-root-excluded marker. | No content summaries for private categories. |
| Authority | Allowed use, forbidden implication, approval route, external-action requirement. | No hidden sending, payment, legal/CPA, provider/model, runtime, or service authority. |
| Review status | Draft, needs review, reviewed, blocked, rejected, historical, or promoted status when later authorized. | Review status does not equal approval unless a bounded receipt says so. |
| Operator promotion | Receipt, target, scope, operator decision, promotion state, promotion timestamp. | Promotion is scope-bound and cannot generalize to future actions. |

## 10. Entity Family Representation

The first future schema should represent entity families as explicit semantic family values on `semantic_records`, with family-specific constraints enforced by the Python contract or an equivalent schema-layer validator later.

| Family group | Entity families | Storage posture |
| --- | --- | --- |
| Parties and responsibility | person, organization, client | Represent identity and responsibility roles without assuming payment, legal, or contact authority. |
| Receivables/accountability | job, invoice, payment, follow-up action, approval | Represent obligations, responsibility, evidence, follow-up drafts, and bounded approvals without auto-send, harassment, collection action, bank access, posting, or final financial truth. |
| Work and projects | project, blocker, system artifact | Represent operator-life burden, system planning, blockers, evidence, and review routes without runtime mutation or service authority. |
| Creative and professional lanes | music work, legal matter, tax matter | Represent boundary-labeled planning records and review needs without private-root inspection, legal advice, CPA action, provider/model use, or private content summaries. |
| Knowledge compiler substrate | source material, compiled page, relationship, synthesis | Represent source basis, compiled pages, links, and interpretations while preserving raw/compiled/wiki/relationship/synthesis/write-back separation. |

Unknown families must remain restricted. Excluded families such as private data, private roots, secrets, credentials, provider prompts, runtime logs, bank accounts, legal private content, and tax private content must not become accepted records through storage visibility.

## 11. Receivables And Accountability Steel Thread

The future storage shape should support the original receivables proof path by representing:

- who is involved in work;
- who is responsible for payment, approval, escalation, legal/accounting action, or decision authority;
- which job, invoice, payment, client, organization, or follow-up action a record concerns;
- what evidence supports or fails to support the obligation;
- what is stale, blocked, contradictory, unknown, or needs review;
- what follow-up text is merely draft-only;
- what operator promotion or approval receipt exists, if any, and for what exact scope.

It must not authorize harassment, automated sending, external sending, collection action, bank access, payment posting, final financial truth, legal advice, CPA action, private-root inspection, provider/model calls, or relationship automation.

The useful storage primitive is accountability, not chasing. Records should make responsibility, evidence, freshness, authority, and next review points visible without creating an outbound-action machine.

## 12. What Must Stay Out Of Storage For Now

No storage exists in this slice. A future storage/schema implementation must continue to exclude the following unless a later operator prompt explicitly authorizes a narrower, reviewed exception:

- raw private file contents;
- private-root paths beyond approved opaque boundary labels;
- secrets, credentials, provider keys, tokens, and config values;
- runtime logs, runtime state, service state, memory/state/config/bin contents, bridge payloads, and sync output;
- provider/model prompts and outputs;
- Hermes, MCP, or external-agent context;
- embeddings, indexes, chunks, extraction output, ingestion output, and source-set generation output;
- bank records, ledger contents, tax records, CPA materials, legal-private materials, music-law-private materials, publishing-private materials, client-private content, and finance-private content;
- outbound message bodies intended for sending without separate approval;
- automated sending instructions, harassment patterns, collection-action instructions, payment posting instructions, legal advice, or CPA action instructions;
- API credentials, runtime execution commands, migration runners, app-state claims, or service-control handles.

Blocked or private material may be represented only as opaque existence, boundary class, missing-evidence reason, or review route when separately authorized by planning doctrine.

## 13. Validation Gates Before Schema Implementation

A future schema implementation prompt remains blocked unless all of these gates pass:

1. A separate operator prompt explicitly authorizes schema/storage implementation and names exact edit paths.
2. The prompt carries this plan, the semantic contract matrix, the implementation-readiness checklist, the first implementation slice readiness decision, the source-set 04 manifest, and the source-set 04 context-filter freshness bridge.
3. Command Atlas Context Development Lifecycle / Context Filter doctrine is included or explicitly bridged.
4. A context-filter receipt for the exact prompt is pass, or warn with explicit operator acceptance.
5. The prompt states whether SQLite, SQL DDL, migration files, tests, fixtures, and database creation are allowed; absent explicit authorization, all remain forbidden.
6. Allowed paths and forbidden paths are exact; broad scans and `git add .` remain forbidden.
7. The future schema maps every record to layer, family, state, labels, provenance, freshness, confidence, sensitivity, authority, review status, and promotion gates without flattening synthesis into truth.
8. Unknown, excluded, blocked, sensitive/local-only, private-root-excluded, and owner-review-required states remain representable without content exposure.
9. Receivables/accountability records preserve role separation and forbid automated sending, harassment, collection action, payment posting, legal/CPA action, private-root inspection, and provider/model use.
10. Future tests prove accepted knowledge is derived only from valid write-back/capture plus confirmed receipt, complete labels, and operator promotion.
11. No runtime service, API route, ingestion job, extractor, indexer, embedding process, provider/model call, Hermes/MCP invocation, sync action, app code, or fixture generation is introduced unless separately and explicitly authorized.
12. Whitespace, final-byte, static checker, pytest, syntax, and editor-diagnostic receipts are named before edits begin.

## 14. Smallest Future Schema Implementation Slice

The smallest future schema implementation slice should be a no-runtime schema-contract slice, not a persistence system.

Recommended future slice, only if separately authorized:

1. Define a storage/schema contract artifact for the central semantic record envelope and required label/promotion constraints.
2. Add tests that compare the schema contract against `backend_data_contract.py` enums and validator behavior.
3. Do not create a database, migration runner, API route, ingestion path, fixture set, runtime service, app surface, provider/model call, private-root scan, or sync process.

The first actual storage table implementation, if authorized after that, should include only the minimal semantic record envelope plus label/promotion constraints needed to preserve `is_entity_record_accepted_knowledge()`. Domain-specific invoice/payment/legal/music tables should wait until the semantic core proves that synthesis, promotion, sensitivity, and authority cannot be flattened.

## 15. Stale Conditions

This plan becomes stale when:

- `backend_data_contract.py` changes entity families, layers, labels, states, decisions, forbidden concepts, or accepted-knowledge semantics;
- `tests/test_backend_data_contract.py` changes validation coverage for write-back/capture, entity families, receivables/accountability, or no-provider/no-private-root boundaries;
- the semantic contract matrix or implementation-readiness checklist changes;
- the first implementation slice readiness decision changes;
- the source-set 04 manifest or context-filter freshness bridge changes;
- Command Atlas Context Development Lifecycle / Context Filter doctrine changes;
- docs 26/27/28/29/30 handling changes;
- private-root contracts change;
- a later approved storage/schema plan supersedes this one;
- a future operator prompt explicitly authorizes schema/storage implementation and names a narrower implementation packet.

## 16. Next Safe Action

The next safe action is a read-only proof pass or one more planning pass that checks whether this storage/schema plan, the pure-Python contract spine, and the existing validation map give enough context for a future no-runtime schema-contract implementation prompt.

Schema implementation should not begin from this artifact alone.
