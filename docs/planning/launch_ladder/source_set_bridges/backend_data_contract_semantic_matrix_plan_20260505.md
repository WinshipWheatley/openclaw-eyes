# Backend Data Contract Semantic Matrix Plan

Generated/reviewed: 2026-05-05

## 1. Status / Non-Authority

This is a docs-only semantic contract matrix for backend/data-contract readiness planning.

It defines planning meanings that a future backend must eventually preserve. It does not design or create backend/API/schema files, SQL DDL, SQLite tables, fixtures, ingestion code, loaders, runtime services, app code, source-set generation, source-set regeneration, provider/model prompts, MCP context, Hermes runs, indexing, embeddings, extraction, chunking, private-root browsing, or commits.

This artifact is not implementation-readiness authority. It is a planning guard for deciding what meanings must be preserved before any separate implementation-readiness prompt can exist.

## 2. Source Basis

This matrix is based on:

- `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_first_planning_slice_decision_20260505.md`
- `docs/planning/launch_ladder/source_sets/04_BACKEND_DATA_CONTRACT_READINESS/MANIFEST.md`
- `docs/planning/launch_ladder/source_set_bridges/04_backend_data_contract_readiness_context_filter_freshness_bridge_20260505.md`
- `docs/planning/command_atlas/04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md`
- `docs/planning/launch_ladder/17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md`
- `docs/planning/launch_ladder/18_BACKEND_DATA_CONTRACT_SHAPE_PLAN.md`
- `docs/planning/launch_ladder/19_OPERATOR_WORLD_MODEL_BUILD_READINESS_ADDENDUM.md`
- `docs/planning/launch_ladder/30_BACKEND_SOURCE_SET_BRIDGE_AND_EXCLUSION_PLAN.md`
- `docs/planning/launch_ladder/24_OPERATOR_HARNESS_PLANNING_INDEX.md`
- `docs/INDEX.md`

No private roots, private data, providers/models, Claude, Claude Code, Hermes, MCPs, services, sync, indexing, embeddings, SQLite, extraction, chunking, source-set generation, backend implementation, runtime work, or app implementation are source inputs to this artifact.

## 3. Matrix Decision

The backend/data-contract readiness lane should first stabilize semantics, not storage.

The future backend must eventually represent records, relationships, evidence, freshness, provenance, authority, sensitivity, allowed sources, forbidden sources, confirmed/inferred/excluded/unknown states, and validation obligations without flattening them into a generic task ledger or database table plan.

The first safe contract artifact is therefore this Markdown semantic matrix. It names entities and rules in human-reviewable planning language only. It deliberately avoids JSON Schema, SQL DDL, SQLite, API routes, loaders, ingestion, fixtures, runtime services, app code, and source-set generation.

## 4. Core Semantic Entity Matrix

| Semantic entity | Planning purpose | Evidence / freshness / provenance | Authority / sensitivity boundary | Confirmed / inferred / excluded / unknown handling | Forbidden implication | Validation before implementation-readiness |
| --- | --- | --- | --- | --- | --- | --- |
| Source file record | Represents a discovered source artifact as an entity. | Evidence is path/name/hash/timestamp only when approved; freshness is discovery-target scoped; provenance must name source set, manifest, bridge, or approved source basis. | Display-only by default; private-root-excluded or local-only when sensitive; never proof of safe content. | Confirmed means existence is in an approved source basis; inferred means candidate only; excluded means withheld by boundary; unknown remains quarantined. | Discovered does not mean read, safe, ingested, indexed, or authorized. | Require explicit source basis, withheld-surface statement, and no private-root browsing authority. |
| Extracted text record | Represents parsed text as evidence candidate. | Evidence is extraction source and extraction freshness when separately authorized later; provenance must preserve source artifact and extraction method. | Local-only for sensitive material; blocked when source category is private or unknown. | Confirmed only after approved extraction exists; inferred from planning docs only as future need; excluded if extraction is prohibited; unknown cannot feed claims. | Extracted does not mean true, complete, safe, or accepted. | Block implementation-readiness until extraction authority, private-boundary handling, and context-filter checks are separately approved. |
| Rendered fragment record | Represents a visual/rich preview or preserved source shape. | Evidence is source or extracted-text reference; freshness belongs to the rendered target, not the whole source. | Display-only; must hide or sanitize sensitive content; Chart Room-style evidence surface only. | Confirmed only when render source is approved; inferred as future display need; excluded for private roots; unknown cannot be previewed. | Rendered does not mean authoritative, complete, or safe for app display. | Require forbidden-private-preview rule and evidence/freshness basis before implementation-readiness. |
| Artifact classification record | Represents reviewed sensitivity or category label. | Evidence is reviewer/source basis and label freshness; provenance must state classification source and target. | Classification is not safety; unknown defaults restricted; local-only and private-root-excluded remain possible outcomes. | Confirmed when reviewed in approved planning/source basis; inferred labels are warnings only; excluded labels preserve blocked reason; unknown stays restricted. | Classified does not mean safe, public, ingested, or provider-safe. | Require label vocabulary, reviewer/provenance expectation, and no downgrade from unknown to safe by display. |
| Claim record | Represents a bounded proposition about an entity. | Evidence is one or more approved evidence refs; freshness is claim-target scoped; provenance names source basis and confidence basis. | Display-only until operator promotion; sensitive claims remain local-only or blocked. | Confirmed means evidence-backed and current for target; inferred means hypothesis; excluded means unsupported/private; unknown means no claim. | A claim does not equal truth or permission to act. | Require evidence ref, confidence language, freshness target, and no unsupported assertion rule. |
| Contradiction record | Represents conflict between claims, sources, or freshness states. | Evidence is conflicting claim/source refs; freshness belongs to the contradiction review. | Review-only; does not authorize resolution, mutation, sending, or deletion. | Confirmed when conflict is evidence-backed; inferred when suspected; excluded if conflict source is private; unknown if insufficient evidence. | Contradiction display does not resolve the contradiction. | Require unresolved-state handling and explicit operator-review route. |
| Compiled note record | Represents synthesized interpretation from evidence and claims. | Evidence is claim/source refs; freshness is note review target; provenance records compiler/source basis. | Display-only until operator promotion; local-only when sensitive; not external-model-safe by default. | Confirmed only as compiled interpretation; inferred notes are drafts; excluded if source is blocked; unknown cannot be summarized as knowledge. | Compiled does not mean accepted, true, provider-safe, or action-ready. | Require source refs, interpretation label, and operator-promotion separation. |
| Freshness record | Represents recency of a specific target. | Evidence is review timestamp/source basis for one named target; provenance must say what freshness applies to. | Display-only; cannot broaden authority beyond target. | Confirmed for target only; inferred freshness is invalid; excluded targets remain stale/blocked; unknown freshness blocks stronger claims. | Freshness is not whole-system health or permission to execute. | Require target-scoped wording and stale-condition checks. |
| Operator promotion record | Represents explicit operator acceptance, rejection, historical marking, sensitivity marking, or exclusion. | Evidence is operator decision receipt and target/scope; freshness is decision-target scoped. | Approval is scope-bound; promotion does not grant general authority or runtime action. | Confirmed only with receipt; inferred promotion is invalid; excluded remains excluded; unknown requires review. | Promoted does not mean globally true, public, runnable, or provider-safe. | Require receipt semantics, target scope, and non-generalization rule. |
| Conversation packet record | Represents sanitized conversation or handoff context. | Evidence is sanitized source refs and packet provenance; freshness is packet-generation scoped. | Non-authorizing by default; local-only if sensitive; external-model use requires separate approval. | Confirmed as sanitized packet only; inferred packets are drafts; excluded if private leakage risk; unknown cannot be shared. | Packetized does not mean complete context or external-model safety. | Require sanitizer/context-filter review and no hidden execution instructions. |
| Blocked sensitive source record | Represents existence of withheld sensitive content without exposing it. | Evidence is opaque source reference and block reason; freshness is boundary-review scoped. | Blocked, local-only, private-root-excluded, or review-required. | Confirmed blocked existence only; inferred block warnings stay restricted; excluded content remains absent; unknown stays quarantined. | Proving blocked existence does not authorize browsing or summarizing content. | Require opaque references and no private-content leakage. |
| Unknown or unclassified artifact record | Represents candidate material lacking safe classification or evidence. | Evidence may be candidate path/name only if approved; freshness is unknown-target scoped. | Restricted by default; no claims, promotions, packets, or display beyond unknown boundary. | Confirmed unknown means known lack of classification; inferred unknown remains candidate; excluded stays withheld; unknown cannot soften into safe. | Unknown does not mean low risk or okay to inspect. | Require quarantine/default-restricted rule. |
| Audit or substrate event record | Represents event evidence about planning, validation, review, or substrate state. | Evidence is receipt/check/result source; freshness is event-target scoped; provenance names command or review basis only when allowed. | Evidence-only; cannot become runtime control authority. | Confirmed event records are receipts; inferred events are invalid; excluded logs/private runtime state remain unread; unknown events do not prove absence. | Event visibility does not authorize log reading, service mutation, or runtime action. | Require allowed evidence surfaces and no private log/runtime dependency. |
| Launch Packet / Approval Receipt linkage record | Represents relation between proposed work and approval evidence. | Evidence is packet id/scope and receipt id/scope in planning language; freshness is approval-target scoped. | Approval-required; receipt binds one packet/action/scope only. | Confirmed only with explicit receipt; inferred approval is invalid; excluded actions stay blocked; unknown approval blocks implementation. | Approval receipt does not prove execution or success. | Require packet/receipt/scope separation before implementation-readiness. |
| Context provenance record | Represents source sets, manifests, freshness docs, bridges, prompts, handoffs, and receipts as engineered inputs. | Evidence is named source path, commit/timestamp when relevant, stale conditions, included inputs, and withheld surfaces. | Context-visible does not mean authorized; stale context routes to review. | Confirmed provenance names approved context; inferred provenance is insufficient; excluded context cannot be laundered; unknown provenance blocks use. | Packaged context does not become authority by being visible, synced, mirrored, indexed, or included. | Require source basis, stale conditions, withheld surfaces, and context-filter pass/warn/block receipt. |
| Context-filter receipt record | Represents pass, warn, block, or needs-review outcome for a context package. | Evidence is filter scope, checked inputs, findings, outcome, reviewer path, and timestamp when applicable. | Advisory unless tied to separate approval; block/needs-review halts execution influence. | Confirmed receipt states outcome; inferred pass is invalid; excluded inputs stay excluded; unknown findings route to review. | Filter output does not approve implementation, providers, Hermes, MCPs, private browsing, or runtime work. | Require receipt language before any agent/build-loop packet or implementation-readiness prompt. |

## 5. Card And State Concept Matrix

| Card / state concept | Meaning for future Operator Harness planning | Evidence / freshness requirement | Must not imply |
| --- | --- | --- | --- |
| Ready | Preconditions are met for review or planning display. | Target-specific evidence and freshness exist. | Execution, implementation, or approval. |
| Blocked | Data, action, source, or route is intentionally withheld. | Block reason and boundary source are named. | Panic, deletion, cleanup, browsing, or override. |
| Stale | A specific freshness target failed or is outdated. | Stale target and stale basis are named. | Whole-system failure or permission to regenerate broadly. |
| Unknown | Classification, evidence, or authority is missing. | Unknown reason is named when available. | Low risk, safe default, or permission to inspect. |
| Sensitive / local-only | Content or context must remain local and bounded. | Sensitivity source and boundary are named. | Provider/model safety, public sharing, or app preview. |
| Evidence available | Approved references exist for review. | Evidence refs and freshness target are named. | Truth, authority, or completeness. |
| Approval / promotion available | Operator decision can be requested or has a bounded receipt. | Packet/receipt target and scope are named. | Execution, success, or global permission. |
| Contradiction present | Evidence or claims conflict and need review. | Conflicting refs are named without private leakage. | Automatic resolution or stronger claim. |
| Packet prepared | A bounded context package exists. | Provenance, allowed use, forbidden use, and stale conditions are named. | External-model safety, execution authority, or complete context. |
| Context filter blocked | Context package failed a safety/provenance/authority check. | Block condition and checked scope are named. | Permission to broaden tools or silently patch prompts. |
| Needs review | Human/operator/Guardian review is required before influence. | Review reason and scope are named. | Approval, execution, or safe fallback. |

## 6. Allowed And Forbidden Source Categories

| Category | Allowed planning use | Forbidden use | Default state |
| --- | --- | --- | --- |
| Tracked repo planning docs | Semantic planning, provenance, source-basis references. | Runtime authority, implementation authority, hidden commands. | Allowed for docs-only planning. |
| Source-set manifests and freshness docs | Context provenance, stale conditions, included/withheld surfaces. | Boilerplate, source laundering, authority inflation. | Required provenance. |
| Source-set bridge/addendum docs | Narrow freshness, exclusion, and doctrine bridges. | Source-set regeneration or private-root content transfer. | Allowed as bounded bridge context. |
| Knowledge Substrate planning docs | Compile-first doctrine and evidence/freshness semantics. | Ingestion, indexing, embeddings, SQLite, extraction, chunking. | Planning-only. |
| 26/27/28/29 through 30 | Exclusion/classification vocabulary only. | Private-root content, cleanup, migration, ingestion, backend build-prep. | Exclusion-only. |
| Windows or Mac private roots | None in this slice. | Browsing, summaries, extraction, source-set inclusion, provider/model context. | Excluded. |
| Logs/runtime/state/config/bin/memory | None in this slice unless already represented as blocked/excluded metadata in approved docs. | Reading contents, runtime truth, service authority, backend authority. | Excluded. |
| Provider/model prompts and outputs | None in this slice. | Context source, implementation driver, hidden authority. | Excluded. |
| Hermes/MCP/sync/runtime artifacts | None in this slice. | Invocation, output ingestion, authority evidence, service activation. | Excluded. |
| Generated safe fixtures | Future planning topic only. | Fixture creation in this slice. | Not created. |

## 7. Relationship Rules

Relationships are planning semantics only. They are not schema, table, API, or storage definitions.

| Relationship | Planning meaning | Boundary |
| --- | --- | --- |
| source file -> extracted text | Parsed text depends on approved source and approved extraction. | No extraction authority in this artifact. |
| source file or extracted text -> rendered fragment | Preview depends on source shape or parsed text. | No private preview or renderer implementation. |
| evidence -> claim | Claim needs explicit evidence refs. | Evidence does not make the claim true by itself. |
| claim -> contradiction | Contradiction compares claims/evidence. | Contradiction does not resolve itself. |
| claim/evidence -> compiled note | Note synthesizes interpretation. | Compilation does not mean acceptance. |
| target -> freshness | Freshness applies to one named target. | No global freshness implication. |
| target -> operator promotion | Promotion binds target and scope. | No general authority transfer. |
| records -> conversation packet | Packet uses sanitized approved records only. | No external-model safety by packetization. |
| blocked source -> opaque reference | Blocked existence can be represented without content. | No browsing or summary leakage. |
| unknown artifact -> review queue | Unknown routes to review/quarantine. | Unknown cannot feed claims or packets. |
| context package -> context-filter receipt | Context must be checked before influencing execution. | Receipt does not authorize implementation. |
| Launch Packet -> Approval Receipt | Receipt can bind one proposed action/scope. | Approval does not prove execution or success. |

## 8. Confirmed / Inferred / Excluded / Unknown Rules

- Confirmed means supported by an approved source basis for a named target and scope.
- Inferred means a hypothesis or planning implication, not accepted truth.
- Excluded means withheld by boundary, sensitivity, stale condition, or missing authority.
- Unknown means insufficient classification, evidence, freshness, or authority; it remains restricted.
- Confirmed does not mean actionable unless a separate action authority exists.
- Inferred cannot flow into claims, packets, promotions, or implementation-readiness as fact.
- Excluded cannot be laundered through summaries, manifests, bridge docs, prompts, or context packages.
- Unknown cannot be softened into safe, public, low-risk, or provider/model-safe.

## 9. Context-Filter Gates Before Implementation-Readiness

Before any backend/data-contract implementation-readiness prompt is allowed, a future planning or validation artifact must show that the intended context package blocks or routes for review on:

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

## 10. Validation Checklist

A future implementation-readiness prompt remains blocked until a separate review confirms:

- this semantic matrix or its successor is current;
- the `04_BACKEND_DATA_CONTRACT_READINESS` source set is consumed with the context-filter freshness bridge and Command Atlas context doctrine;
- source-set manifests and freshness docs are treated as context provenance;
- 26/27/28/29 remain exclusion/classification-only through 30;
- private roots, private data, logs, runtime state, config, provider/model prompts, MCP context, Hermes output, sync output, generated runtime artifacts, indexing, embeddings, SQLite, extraction, chunking, ingestion, and app implementation are still excluded;
- record families preserve evidence/freshness/provenance/authority/sensitivity separation;
- unknown, blocked, sensitive, and local-only states remain restricted;
- conversation packets remain sanitized and non-authorizing;
- context-filter receipt requirements are explicit;
- any next prompt is explicit about allowed paths, forbidden tools, stale conditions, and validation receipts.

## 11. Stale Conditions

This matrix becomes stale when:

- the first planning slice decision changes;
- the context-filter freshness bridge changes;
- Command Atlas context doctrine changes;
- `04_BACKEND_DATA_CONTRACT_READINESS` source-set membership changes;
- `17`, `18`, `19`, or `30` changes in a way that alters record semantics or source boundaries;
- 26/27/28/29 handling changes;
- private-root contracts change;
- Knowledge Substrate compile-first doctrine changes;
- backend/API/schema/SQLite/ingestion implementation is explicitly authorized;
- a later approved semantic matrix or implementation-readiness artifact supersedes this plan.

## 12. Next Action

The next step should remain planning.

The safest next artifact is a docs-only implementation-readiness checklist that maps this semantic matrix to exact preconditions for a future backend/data-contract implementation prompt. That checklist should still not implement backend/API/schema/SQLite/ingestion/fixtures/runtime/app code, run providers/models, invoke Hermes or MCPs, inspect private roots, generate source sets, or authorize runtime work.
