# Backend Source-Set Bridge And Exclusion Plan

Generated/reviewed: 2026-05-05

## 1. Status / Freshness

Status: docs-only bridge/exclusion planning artifact before `04_BACKEND_DATA_CONTRACT_READINESS` source-set generation.

This document does not create a source-set folder, backend/API/schema file, SQL DDL, SQLite database, fixture, ingestion script, extraction job, index, embedding, chunk, provider/model prompt, MCP context, Hermes run, sync process, runtime mutation, cleanup plan, migration plan, move manifest, app implementation, or Operator Harness ingestion surface.

Source basis:

- `docs/planning/launch_ladder/17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md`
- `docs/planning/launch_ladder/18_BACKEND_DATA_CONTRACT_SHAPE_PLAN.md`
- `docs/planning/launch_ladder/19_OPERATOR_WORLD_MODEL_BUILD_READINESS_ADDENDUM.md`
- `docs/planning/command_atlas/00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md`
- `docs/planning/launch_ladder/26_PC_WINDOWS_ROOTS_PRIVATE_DATA_BOUNDARY_BREADCRUMB.md`
- `docs/planning/launch_ladder/27_WINDOWS_ROOT_TRIAGE_AND_DEPENDENCY_MAP_PLAN.md`
- `docs/planning/launch_ladder/28_WINDOWS_ROOT_DEPENDENCY_MAP_TEMPLATE.md`
- `docs/planning/launch_ladder/29_WINDOWS_ROOT_DEPENDENCY_MAP.md`
- `docs/planning/launch_ladder/24_OPERATOR_HARNESS_PLANNING_INDEX.md`
- `docs/INDEX.md`

Stale when any of those inputs changes, when `04_BACKEND_DATA_CONTRACT_READINESS` source-set membership changes, when Windows/Mac private-root contracts are approved, when runtime/log/state/bin/config ownership is mapped, or when backend/schema/SQLite/ingestion work is explicitly authorized.

Refresh trigger: review this bridge before generating `04_BACKEND_DATA_CONTRACT_READINESS` or before any prompt tries to use Windows root dependency-map facts as backend/data-contract input.

## 2. Scope

This is bridge/exclusion planning only.

Its purpose is to define how Windows root dependency-map docs may inform backend source-set planning without turning private roots, runtime state, generated outputs, logs, config, or path metadata into backend input authority.

The bridge may carry exclusions, blocked states, unknown/quarantine labels, source-set warnings, and classification language. It must not carry private-root content.

## 3. Required Inputs Before Backend Source-Set Generation

Before generating `04_BACKEND_DATA_CONTRACT_READINESS`, the generation prompt must include or bridge these planning inputs:

- backend readiness plan: `17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md`;
- backend shape plan: `18_BACKEND_DATA_CONTRACT_SHAPE_PLAN.md`;
- world-model addendum: `19_OPERATOR_WORLD_MODEL_BUILD_READINESS_ADDENDUM.md`;
- Command Atlas system map: `docs/planning/command_atlas/00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md`;
- Windows private-data boundary: `26_PC_WINDOWS_ROOTS_PRIVATE_DATA_BOUNDARY_BREADCRUMB.md`;
- Windows root triage plan: `27_WINDOWS_ROOT_TRIAGE_AND_DEPENDENCY_MAP_PLAN.md`;
- Windows dependency-map template: `28_WINDOWS_ROOT_DEPENDENCY_MAP_TEMPLATE.md`;
- Windows dependency map: `29_WINDOWS_ROOT_DEPENDENCY_MAP.md`;
- this bridge/exclusion plan.

If the 24-file source-set budget cannot include the full Windows dependency-map stack, this bridge may summarize it as exclusion/classification guidance, provided the manifest names the withheld full docs and states that no private-root content was included.

## 4. Explicit Exclusions

The backend source-set generation prompt must exclude:

- Windows private roots;
- Mac private roots;
- `/home/openclaw/.private`;
- contents of `C:\OpenClaw`;
- contents of `C:\OpenClawShared`;
- contents of `C:\OpenClawLegalPrivate`;
- `C:\OpenClawShared\business\source_docs\finance_admin` and all finance/tax/CPA descendants;
- legal, finance, CPA, tax, ledger, music-law, publishing, client, vault, reset proof, secret, and `.private` contents;
- logs, state, memory, bin, config, runtime residue, runtime folders, bridge payloads, generated outputs, and shared vault contents unless represented only as blocked/excluded metadata labels;
- provider/model prompts and provider/model context;
- MCP invocations and MCP context;
- Hermes runs or Hermes session/runtime material;
- sync, migration, cleanup, move-manifest, or bridge-behavior work;
- indexing, embeddings, SQLite, FTS, extraction, chunking, ingestion, or database creation;
- Operator Harness ingestion, display authority, backend build-prep, app implementation, or schema implementation.

## 5. Permitted Use Of 26/27/28/29

The Windows root dependency-map stack may be used only to carry:

- classification labels;
- source-set exclusions;
- private-root boundary facts;
- unknown/quarantine labels;
- blocked-private-source labels;
- active-dependency-candidate warnings;
- owner-review requirements;
- no-browsing and no-ingestion constraints;
- source-registry-style field ideas as future metadata-contract vocabulary only.

Discovered does not mean read. Raw files are evidence, not truth. Search or retrieval finds candidates, not authority. Unknown and unclassified items stay quarantined.

## 6. Forbidden Use Of 26/27/28/29

The Windows root dependency-map stack must not be used to authorize:

- cleanup;
- migration;
- move manifests;
- file moves, deletes, renames, archive work, or deduplication;
- private-root browsing;
- source-set inclusion of Windows or Mac private roots;
- ingestion, extraction, indexing, embedding, chunking, SQLite, FTS, or database creation;
- backend build-prep or schema implementation;
- provider/model prompts or MCP context;
- Operator Harness ingestion or display of private/log/runtime content;
- authority transfer from path metadata to backend record truth.

Path strings, root names, mirrored surfaces, shared folder names, generated outputs, logs, vault labels, and config references are classification evidence only. They are not backend authority.

## 7. Backend Source-Set File-List Implication

`04_BACKEND_DATA_CONTRACT_READINESS` should include or bridge the Windows dependency-map stack without private-root content.

Acceptable patterns:

- include `30_BACKEND_SOURCE_SET_BRIDGE_AND_EXCLUSION_PLAN.md` as the compact bridge and list 26/27/28/29 as withheld/full-source references in the manifest;
- include 29 directly when source-set capacity allows, still as exclusion/classification guidance only;
- include a generated bridge summary that preserves blocked roots, unknown/quarantine, source-set exclusions, and forbidden actions, while withholding private-root content and runtime/log/state/config contents.

Unacceptable patterns:

- include raw Windows or Mac private-root paths as browsable content;
- include logs, runtime state, shared vault contents, finance/tax/legal material, generated outputs, or config contents as backend input authority;
- treat source-registry language as permission to inventory, extract, index, embed, or ingest files;
- treat dependency-map rows as proof of active runtime truth, safety, freshness, or backend record truth.

## 8. Validation Checklist Before `04_BACKEND_DATA_CONTRACT_READINESS`

Before generating the source set, confirm:

- `04_BACKEND_DATA_CONTRACT_READINESS` is still planning/readiness, not implementation.
- The manifest or prompt names included files, withheld surfaces, stale conditions, and source commit.
- 17, 18, 19, Command Atlas, and the Windows dependency-map stack are included or bridged.
- 26/27/28/29 are used only as exclusion/classification guidance.
- Windows and Mac private roots are excluded from source sets and agent browsing.
- `/home/openclaw/.private` is excluded.
- `C:\OpenClaw`, `C:\OpenClawShared`, and `C:\OpenClawLegalPrivate` contents are excluded.
- Logs, state, memory, bin, config, runtime residue, shared vault contents, generated outputs, and bridge payloads are excluded as content.
- No provider/model, MCP, Hermes, sync, indexing, embedding, SQLite, FTS, extraction, chunking, ingestion, runtime, cleanup, migration, or move-manifest work is authorized.
- Unknown/quarantine and blocked-private-source states remain restricted.
- The future backend/data-contract vocabulary preserves `discovered != read`, `classified != safe`, `compiled != accepted`, `visible != authorized`, and `freshness is target-scoped`.

## 9. Next Allowed Action

After this document is created, the next allowed action is to update `24_OPERATOR_HARNESS_PLANNING_INDEX.md` and `docs/INDEX.md` to reference it, then review and commit the docs-only planning stack with explicit paths if the operator asks.

Do not generate `04_BACKEND_DATA_CONTRACT_READINESS` from this document alone. Do not commit unless explicitly asked.

## 10. Final Boundary

This bridge is not backend input authority. It is a planning guard that prevents backend source-set generation from laundering private roots, runtime residue, generated outputs, logs, config references, or path metadata into authority.
