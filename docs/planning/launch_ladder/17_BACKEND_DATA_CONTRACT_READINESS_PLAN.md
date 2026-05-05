# Backend Data Contract Readiness Plan

Status: docs/test-only planning artifact for the next source-set lane. This file does not create a source-set folder, implementation, SwiftUI/AppKit file, backend/API/schema file, SQL DDL, SQLite database, ingestion script, fixture, provider/model call, runtime mutation, approval mutation, private-data inspection, app name, audio asset, haptic behavior, notification behavior, or sound settings UI.

Freshness:

- Generated/reviewed: 2026-05-02
- Active source-set baseline: `03_MAC_APP_KNOWLEDGE_SUBSTRATE`
- Source commit from latest audited source set: `c5947e7fbdf8952824ddb60fb8b8203bdea28e95`
- Source basis: Mac App Knowledge Substrate source-set brief, Next Implementation Sequence, Launch Ladder Model, Evidence and Freshness, Security and Authority, Mission Control fixture contract, first-screen composition spec, knowledge-substrate planning package, validation map, and static Launch Ladder checker/test.
- Stale when: the `03_MAC_APP_KNOWLEDGE_SUBSTRATE` source set changes, the next source-set folder name changes, knowledge-substrate doctrine changes, backend/data-contract record topics change, validation expectations change, or implementation starts.
- Refresh trigger: update before generating `04_BACKEND_DATA_CONTRACT_READINESS` or before any backend/schema/SQLite/ingestion work is requested.

## 1. Recommended Next Source-Set Folder Name

Use:

```text
04_BACKEND_DATA_CONTRACT_READINESS
```

This is safer than:

```text
04_BACKEND_AND_DATA_MODEL
```

Reasoning to preserve: "Backend/data-model" sounds implementation-adjacent. "Backend/data-contract readiness" keeps the lane focused on records, contract boundaries, synthetic fixture intent, and validation expectations before actual backend/schema/SQLite work starts.

`04_BACKEND_DATA_CONTRACT_READINESS` is safer than `04_BACKEND_AND_DATA_MODEL` because it frames the next lane as contract-readiness planning, not backend implementation, schema selection, SQL DDL, SQLite database creation, ingestion, or fixture generation.

The folder name should tell future chats that the work is still readiness and planning. It should not invite schema creation, SQLite database creation, API work, ingestion, or fixture generation.

## 2. Why This Should Be The Next Source Set

`03_MAC_APP_KNOWLEDGE_SUBSTRATE` answered the app and knowledge direction well enough that the next bottleneck is data-contract readiness.

The Mac desktop Mission Control surface can only stay honest if later records and contracts are explicit about what exists, what is evidence, what is interpretation, what is blocked, what is unknown, what is fresh, what is stale, and what has been promoted by the operator. The next source set should define what records and contract boundaries must exist so the app can later render knowledge, evidence, freshness, blocked/unknown states, promotions, and packets without lying.

This is still planning. The useful next move is not backend implementation; it is deciding the contract vocabulary and validation posture that must exist before backend/schema/SQLite work starts.

## 3. What `03_MAC_APP_KNOWLEDGE_SUBSTRATE` Answered

The `03_MAC_APP_KNOWLEDGE_SUBSTRATE` source set answered these planning points:

- Mac desktop first.
- iOS companion later.
- The first surface is a read-only Mission Control surface.
- The product direction is a personal operator console.
- The surface is not a chatbot, SaaS admin panel, or agent theater.
- The knowledge substrate is compile-first.
- It is not vanilla RAG.
- SQLite is the future canonical local memory concept.
- Markdown is an export and handoff surface.
- HTML/rich fragments preserve source shape.
- FTS/search finds records.
- Compiled notes make knowledge useful.
- Raw files are evidence, not truth.
- Extracted text is parsed evidence, not truth.
- Rendered fragments preserve source shape, not authority.
- Artifact classifications are reviewed interpretations, not safety guarantees.
- Claims are evidence-backed and confidence-bounded.
- Compiled notes are interpretation, not truth.
- Operator promotions are explicit accept/reject/historical/sensitive/excluded decisions.
- Freshness must be target-scoped.
- Conversation packets must be sanitized and non-authorizing.
- Unknown defaults restricted.
- Sensitive content is local-only by default.
- Evidence/freshness must exist before UI or app state claims.
- Sound/haptics are quiet, optional, and non-authoritative.
- No app naming yet.

These answers are enough to plan the next source set, but not enough to implement storage, schema, ingestion, API, or app runtime behavior.

## 4. What Remains Unresolved Before Backend/Schema Work

The next readiness lane should resolve these questions before backend/schema work starts:

- Contract format: Markdown table contracts vs JSON Schema vs SQL DDL vs staged progression.
- Which conceptual records become first-class contract objects.
- Which synthetic fixture topics become actual JSON fixtures later.
- Where backend/data-contract docs should live.
- Whether operator promotions belong inside the knowledge substrate contract, broader Launch Ladder authority contract, or both.
- How conversation packets are sanitized without accidentally authorizing provider/model use.
- How blocked/unknown/sensitive records are represented to the app without exposing private content.
- Freshness scoping: source, extraction, rendered fragment, classification, claim, compiled note, packet, promotion, or all.
- Whether Knowledge Atlas remains app-facing language only or becomes backend aggregate contract language.
- How audit events/substrate events relate to Launch Packets, Approval Receipts, and evidence/freshness receipts.

If these are skipped, backend/schema/SQLite work could harden the wrong product shape.

## 5. World-Model / Mode-Authority Readiness

Backend/data-contract readiness must now absorb `19_OPERATOR_WORLD_MODEL_BUILD_READINESS_ADDENDUM.md` before backend/schema/SQLite/UI implementation begins. This file remains the readiness plan, `18_BACKEND_DATA_CONTRACT_SHAPE_PLAN.md` remains the shape-plan companion, and `19_OPERATOR_WORLD_MODEL_BUILD_READINESS_ADDENDUM.md` is the world-model addendum that updates the readiness assumptions for Operator Harness places and modes.

Operator Harness places such as Bridge / Captain's View, Helm, Chart Room, Engine Room, Cargo Hold, Radio Room, Treasury / Purser's Office, Studio Bay, and Ports are not decorative UI metaphors. They imply authority scopes, allowed surfaces, context boundaries, evidence obligations, and action limits.

Readiness must preserve these rules:

- UI-visible does not mean actionable.
- Mirrored does not mean canonical.
- Synced does not mean fresh.
- Displaying a thing in Harness does not grant Chief/Cassandra/Hermes/PI permission to act on it.
- Records should eventually know where they may be surfaced and what authority, freshness, and evidence basis is required before display.

This is conceptual readiness only. Do not define schema, SQL, APIs, migrations, ingestion code, SwiftUI/AppKit code, fixtures, or runtime behavior in this readiness plan.

### Before Source-Set Generation

Before generating the next backend/data-contract source set, confirm that `17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md`, `18_BACKEND_DATA_CONTRACT_SHAPE_PLAN.md`, `19_OPERATOR_WORLD_MODEL_BUILD_READINESS_ADDENDUM.md`, `docs/planning/command_atlas/00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md`, and `docs/planning/launch_ladder/26_PC_WINDOWS_ROOTS_PRIVATE_DATA_BOUNDARY_BREADCRUMB.md` are included or bridged so future implementation does not build from stale backend-only assumptions.

## 6. Minimum File List The Next Source Set Should Include

The next source-set generation should stay 24-file-oriented: exactly 23 content files plus `MANIFEST.md` when it is actually generated.

Candidate minimum set:

| File | Purpose in `04_BACKEND_DATA_CONTRACT_READINESS` |
| --- | --- |
| `MANIFEST.md` | Upload authority, source commit, generated timestamp, purpose, included files, withheld surfaces, stale conditions, and 23 content plus manifest count. |
| `17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md` | Defines the next source-set purpose, boundaries, record topics, and validation expectations. |
| `16_MAC_APP_KNOWLEDGE_SUBSTRATE_SOURCE_SET_BRIEF.md` | Carries the 03 conclusions that justify the next lane. |
| `11_NEXT_IMPLEMENTATION_SEQUENCE.md` | Shows the planned sequence and keeps implementation deferred. |
| `04_LAUNCH_LADDER_MODEL.md` | Preserves Launch Ladder, Launch Packet, Approval Receipt, and authority separation. |
| `05_EVIDENCE_AND_FRESHNESS.md` | Preserves evidence/freshness target scoping and manifest authority. |
| `06_ROUTING_AND_WORKSPACES.md` | Preserves routing, Workspace Launch Profile, and navigation-only boundaries. |
| `07_SECURITY_AND_AUTHORITY.md` | Preserves withheld surfaces, authority classes, and no-provider/no-runtime boundaries. |
| `08_SOURCE_SET_REFRESH_SYSTEM.md` | Preserves source-set ladder, manifest, bridge, and refresh rules. |
| `09_MAC_IOS_APP_BUILD_BRIEF.md` | Preserves app-facing record needs and read-only Mission Control posture. |
| `12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md` | Preserves fixture state meanings and app display boundaries. |
| `13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md` | Preserves the first-screen evidence/freshness and knowledge-context posture. |
| `KNOWLEDGE_SUBSTRATE_README.md` | Preserves package purpose and hard boundaries. |
| `KNOWLEDGE_SUBSTRATE_INDEX.md` | Preserves package navigation and current posture. |
| `KNOWLEDGE_SUBSTRATE_01_NORTH_STAR.md` | Preserves local-first knowledge substrate doctrine. |
| `KNOWLEDGE_SUBSTRATE_02_SQLITE_LAYER_MODEL.md` | Preserves conceptual layers without becoming schema/DDL. |
| `KNOWLEDGE_SUBSTRATE_03_SAFETY_AND_SENSITIVITY_LEVELS.md` | Preserves local-only restricted defaults. |
| `KNOWLEDGE_SUBSTRATE_04_APP_CARDS_AND_UI_STATES.md` | Preserves record-state language for the future app. |
| `KNOWLEDGE_SUBSTRATE_05_FIXTURE_PLAN.md` | Preserves synthetic fixture intent without creating fixtures. |
| `KNOWLEDGE_SUBSTRATE_06_STATIC_VALIDATION_EXPECTATIONS.md` | Preserves static checks and implementation blockers. |
| `VALIDATION_MAP.md` | Points future agents to the correct static validation. |
| `launch_ladder_contract_check.py` | Provides static contract checks. |
| `test_launch_ladder_static_contract.py` | Provides pytest coverage for the static contract. |

This candidate is 22 content files plus `MANIFEST.md`, leaving one content slot available if the generated 04 package must be exactly 23 content files. After absorbing the world-model / mode-authority addendum, the first candidate for that open slot is `19_OPERATOR_WORLD_MODEL_BUILD_READINESS_ADDENDUM.md`, unless a later bridge includes it with Command Atlas and the PC root boundary doc. If later generation tries to include both `14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md` and `15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md`, those are lower-priority for 04 because 03 already preserved taste, sound, and app feel. Keep 04 focused on backend/data-contract readiness.

This is source-set planning, not source-set generation. Do not create `04_BACKEND_DATA_CONTRACT_READINESS` in this slice.

## 7. Synthetic Fixture/Data-Contract Topics To Cover Later

Later readiness work should cover these synthetic fixture and data-contract topics:

- source file record.
- extracted text record.
- rendered fragment record.
- artifact classification record.
- claim record.
- contradiction record.
- compiled note record.
- freshness record.
- operator promotion record.
- conversation packet record.
- blocked sensitive source record.
- unknown/unclassified artifact record.
- audit/substrate event record.
- Launch Packet / Approval Receipt linkage record, if needed for app evidence boundaries.

These are topics for later contracts and synthetic fixtures. This slice does not create fixture files.

## 8. Static Validation Expectations To Require Later

Future static validation for `04_BACKEND_DATA_CONTRACT_READINESS` should require:

- Exact 24-file source set.
- Manifest commit/timestamps/purpose/stale conditions.
- No backend/schema/SQLite implementation claims.
- No ingestion/scanning/provider/private/runtime authorization.
- Record-state separation.
- Raw/extracted/rendered/classified/claim/compiled/promoted/freshness/packet/audit separation.
- Unknown restricted.
- Sensitive local-only.
- Conversation packets not implying external-model safety.
- Promotions target/scope limits.
- Freshness target-scoping, not whole-system health.
- Workspace Launch Profiles navigation-only.
- Launch Packets separate from Approval Receipts.
- UI/app claims needing evidence/freshness proof.
- Future fixtures synthetic only.
- No app naming.
- No audio/haptic/notification implementation.

The current docs/test slice should validate that this plan exists, contains the required sections, names the required record topics, repeats the boundaries, recommends `04_BACKEND_DATA_CONTRACT_READINESS` next, and does not authorize implementation or source-set generation.

## 9. Boundaries That Remain In Force

Hard prohibitions for this planning slice:

- Do not implement anything.
- Do not create source-set folder 04 yet.
- Do not create SwiftUI/AppKit files.
- Do not create backend/API/schema files.
- Do not create SQL DDL.
- Do not create a SQLite DB.
- Do not create ingestion scripts.
- Do not create fixtures yet.
- Do not scan old business files.
- Do not inspect private data, vaults, logs, LegalPrivate, secrets, Gmail, cloud drives, or runtime state.
- Do not call providers/models.
- Do not mutate runtime, services, approvals, Guardian, Hermes, Telegram, or Gmail.
- Do not create audio assets, haptics, notifications, sound behavior, or sound settings UI.
- Do not name the app or invent product names, codenames, mascots, slogans, logos, or brand identity.

These boundaries remain in force for the plan and for any later generation prompt unless the operator explicitly authorizes a narrower next slice.

## 10. Recommended Next Move

After this artifact is committed, the next move should be source-set generation for:

```text
04_BACKEND_DATA_CONTRACT_READINESS
```

That future 04 source set should still be readiness/planning, not backend implementation. It should carry the exact source-set file list, manifest rules, withheld surfaces, stale conditions, and validation expectations needed to decide data contracts before backend/schema/SQLite/ingestion work starts.

Do not generate the 04 source set in this slice.
