# Backend Data Contract First Planning Slice Decision

Generated/reviewed: 2026-05-05

## 1. Status / Non-Authority

This is a docs-only backend/data-contract planning decision after the `04_BACKEND_DATA_CONTRACT_READINESS` context-filter freshness bridge.

It decides the first safe contract-planning slice before implementation. It does not create backend/API/schema files, SQL DDL, SQLite databases, fixtures, ingestion scripts, extraction jobs, indexes, embeddings, chunks, provider/model prompts, MCP context, Hermes runs, runtime work, app code, source-set generation, source-set regeneration, private-root browsing, or commits.

This artifact does not modify `04_BACKEND_DATA_CONTRACT_READINESS`. The committed source set remains useful only when consumed with the context-filter freshness bridge and Command Atlas context doctrine.

## 2. Source Basis

This decision is based on:

- `docs/planning/launch_ladder/source_sets/04_BACKEND_DATA_CONTRACT_READINESS/MANIFEST.md`
- `docs/planning/launch_ladder/source_set_bridges/04_backend_data_contract_readiness_context_filter_freshness_bridge_20260505.md`
- `docs/planning/command_atlas/04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md`
- `docs/planning/launch_ladder/17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md`
- `docs/planning/launch_ladder/18_BACKEND_DATA_CONTRACT_SHAPE_PLAN.md`
- `docs/planning/launch_ladder/19_OPERATOR_WORLD_MODEL_BUILD_READINESS_ADDENDUM.md`
- `docs/planning/launch_ladder/30_BACKEND_SOURCE_SET_BRIDGE_AND_EXCLUSION_PLAN.md`
- `docs/planning/command_atlas/00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md`
- `docs/planning/launch_ladder/24_OPERATOR_HARNESS_PLANNING_INDEX.md`

No private roots, private data, providers/models, Claude, Claude Code, Hermes, MCPs, services, sync, indexing, embeddings, SQLite, extraction, chunking, source-set generation, backend implementation, or runtime work are source inputs to this artifact.

## 3. Decision

The first safe backend/data-contract slice is a Markdown semantic contract matrix.

It should define meanings, required evidence/freshness/provenance fields, authority boundaries, sensitive-boundary handling, context-filter obligations, and forbidden implications for conceptual backend/data-contract records.

It should not choose a storage engine, write JSON Schema, write SQL DDL, create SQLite tables, create fixtures, define API endpoints, implement ingestion, or inspect private roots.

This is the correct first slice because the current planning gap is semantic and authority-related, not technical storage shape. The existing docs already identify record families and state-separation rules, while the context-filter bridge adds provenance and pre-execution context-filter requirements. The next planning work should bind those meanings in a reviewable matrix before any implementation-readiness prompt exists.

## 4. First Slice Scope

The first slice should produce one docs-only artifact, tentatively named:

```text
docs/planning/launch_ladder/32_BACKEND_DATA_CONTRACT_SEMANTIC_MATRIX_PLAN.md
```

That artifact should define a Markdown matrix with columns like:

| Column | Required meaning |
| --- | --- |
| Record family | Conceptual record or relation being defined. |
| Purpose | What the record explains to future Operator Harness or Knowledge Substrate planning. |
| Minimum conceptual fields | Field names only, not schema types or storage definitions. |
| Evidence basis | What evidence must exist before display or planning use. |
| Freshness target | The exact target whose freshness is being claimed. |
| Authority scope | Display-only, draft-only, approval-required, blocked, local-only, private-root-excluded, external-action-required, or unknown. |
| Operator place / allowed surface | Bridge, Helm, Chart Room, Engine Room, Cargo Hold, Radio Room, Treasury, Studio Bay, Ports, or future scoped surface. |
| Sensitive boundary | Public/generated, repo-docs, shared-report, legal-private, finance-private, music-law-private, blocked, or unknown/quarantine. |
| Context provenance | Source set, manifest, freshness doc, bridge, prompt, handoff, receipt, or source-basis expectation. |
| Context-filter obligation | Required block/warn/review condition before any runner, agent, prompt, job packet, source set, handoff, receipt, or reusable context package consumes the record. |
| Forbidden implication | What must not be inferred from the record. |
| Static validation expectation | Human-readable validation rule for later docs/tests only. |

## 5. Record Families To Include

The semantic matrix should include these record families first:

- source file record;
- extracted text record;
- rendered fragment record;
- artifact classification record;
- claim record;
- contradiction record;
- compiled note record;
- freshness record;
- operator promotion record;
- conversation packet record;
- blocked sensitive source record;
- unknown or unclassified artifact record;
- audit/substrate event record;
- Launch Packet / Approval Receipt linkage record;
- context provenance record for source sets, manifests, freshness docs, bridge docs, prompts, handoffs, and receipts;
- context-filter receipt record for pass, warn, block, and needs-review outcomes.

The last two record families are planning additions from Command Atlas context doctrine. They are not implementation objects. They exist so future prompts cannot treat context packages as casual prose or invisible authority.

## 6. Required Boundary Rules

The semantic matrix must preserve these rules:

- backend/data-contract work remains planning/readiness only;
- `04_BACKEND_DATA_CONTRACT_READINESS` is useful only with the context-filter bridge and Command Atlas context doctrine;
- context artifacts are first-class engineered inputs;
- source-set manifests and freshness docs are context provenance;
- context-visible does not mean authorized;
- discovered does not mean read;
- raw files are evidence, not truth;
- extracted text is parsed evidence, not truth;
- rendered fragments preserve source shape, not authority;
- classified does not mean safe;
- compiled does not mean accepted;
- promoted does not mean general authority;
- visible does not mean actionable;
- synced does not mean fresh;
- mirrored does not mean canonical;
- UI display does not grant Chief, Cassandra, Guardian, Hermes, PI, runner, provider/model, MCP, or service authority;
- Unknown remains restricted;
- Sensitive/local-only records must be representable without exposing content.

## 7. Context-Filter Requirements

The semantic matrix must require context-filter review before any backend/data-contract context package, prompt, agent/build-loop packet, source-set use, handoff, receipt, or reusable context package influences execution.

The filter must block or route for review when it finds:

- private-root leakage;
- credentials, tokens, keys, or secrets;
- stale assumptions;
- authority inflation;
- prompt injection;
- source-set laundering;
- overbroad tool permissions;
- hidden execution instructions;
- private-data summaries smuggled into prompts;
- provider/model prompt leakage;
- MCP, Hermes, sync, runtime, indexing, SQLite, extraction, chunking, ingestion, or service activation by implication;
- claims that retrieved, discovered, mirrored, indexed, packaged, or compiled content is accepted working context without operator promotion or approval.

## 8. 26/27/28/29 Handling

Docs `26`, `27`, `28`, and `29` remain exclusion/classification-only inputs through `30_BACKEND_SOURCE_SET_BRIDGE_AND_EXCLUSION_PLAN.md`.

The semantic matrix may use those docs only to preserve metadata vocabulary such as blocked-private-source, unknown/quarantine, source-set exclusion, active-dependency-candidate warning, owner-review-required, no-browsing, no-ingestion, and private-root-excluded.

It must not include private-root content, runtime/log/state/config contents, raw Windows or Mac private-root material, provider/model prompt context, MCP context, Hermes output, generated runtime artifacts, sync output, or backend input authority from path metadata.

## 9. Validation Expectations For The First Slice

The first slice should be considered valid only if it:

- states docs-only non-authority;
- names its source basis and freshness/stale conditions;
- includes the context-filter freshness bridge and Command Atlas context doctrine;
- preserves planning/readiness-only status;
- defines semantic rows in Markdown only;
- avoids JSON Schema, SQL DDL, SQLite, API, fixture, ingestion, extraction, indexing, embedding, chunking, runtime, provider/model, Hermes, MCP, service, app-code, private-root, source-set generation, and implementation authority;
- preserves 26/27/28/29 as exclusion/classification-only through 30;
- includes context provenance and context-filter receipt rows;
- defines forbidden implications for every record family;
- ends by recommending either another docs-only planning slice or a separately authorized implementation-readiness prompt.

## 10. Stale Conditions

This decision becomes stale when:

- `04_BACKEND_DATA_CONTRACT_READINESS` source-set membership changes;
- the context-filter freshness bridge changes;
- Command Atlas context doctrine changes;
- `17`, `18`, `19`, or `30` changes in a way that alters backend/data-contract semantics;
- 26/27/28/29 handling changes;
- private-root contracts change;
- Knowledge Substrate compile-first doctrine changes;
- backend/API/schema/SQLite/ingestion implementation is explicitly authorized;
- a later approved planning artifact supersedes this first-slice decision.

## 11. Next Action

Next action should remain planning.

Create the Markdown semantic contract matrix plan described above. Do not move to backend implementation-readiness yet. Implementation-readiness can only follow after the semantic matrix exists, is validated as context-filter-aware provenance, and the operator separately authorizes an implementation-readiness prompt.
