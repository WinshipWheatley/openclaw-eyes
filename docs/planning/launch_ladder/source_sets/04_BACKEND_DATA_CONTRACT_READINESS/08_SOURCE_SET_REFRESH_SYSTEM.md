# Source-Set Refresh System

Status: docs-only future source-set workflow. This file does not create generated folders or scripts.

Freshness:

- Generated/reviewed: 2026-05-02
- Source commit at creation: `e06b7ae`
- Package commit: `TBD_AFTER_COMMIT`
- Source basis: existing audit/build mirror and ingest scripts, MCP profiles, modular readiness ledger, validation map, Launch Ladder docs.
- Stale when: source files change, file counts change, upload rules change, generated folders are created/refreshed, or ChatGPT Project limits change.
- Refresh trigger: update before implementing any generator or producing `CHATGPT_PROJECT_INGEST_LAUNCH_LADDER/`.

## Purpose

The future source-set refresh system should generate bounded ChatGPT Project upload folders for Launch Ladder work. Generated folders are derived and non-canonical. Repo docs remain canonical.

For Operator Harness, this is now a Source-Set Ladder: a slower-moving ChatGPT Project context progression that sits beside the Launch Ladder work model. Source-set folders are not Launch Ladder steps. They are staged context packets that should squeeze a specific type of planning or build value before the chat moves to the next folder.

This slice does not create:

- `CHATGPT_PROJECT_INGEST_LAUNCH_LADDER/`
- generator scripts
- Mac sync scripts
- ChatGPT Project upload batches

## Current Operator Harness Output Shape

```text
~/OpenClaw_Watch/operator_harness_readiness/
  CHAT_STAY_UP_TO_DATE.md
  CHATGPT_PROJECT_INGEST_OPERATOR_HARNESS/
    01_CURRENT_PRODUCT_SPEC/
    02_MAC_IOS_APP_BUILD/
    03_MAC_APP_KNOWLEDGE_SUBSTRATE/
```

Each numbered folder should contain exactly 24 upload files total:

- 23 curated content files.
- 1 `MANIFEST.md`.

Do not use 24 content files plus a manifest. The manifest counts as one upload file.

`CHAT_STAY_UP_TO_DATE.md` is the adjacent delta bridge. It is outside `CHATGPT_PROJECT_INGEST_OPERATOR_HARNESS/*`, and it is not counted in the 24 files. The 24-file folder is the baseline; the bridge is the small delta layer.

## Source-Set Ladder Model

The current Source-Set Ladder is:

```text
01_CURRENT_PRODUCT_SPEC -> 02_MAC_IOS_APP_BUILD -> 03_MAC_APP_KNOWLEDGE_SUBSTRATE -> 04_BACKEND_DATA_CONTRACT_READINESS -> future 05/etc.
```

Folder movement should be deliberate:

- When folder 01 is exhausted, move to folder 02. Exhausted means the chat has extracted stable product requirements, authority boundaries, evidence/freshness rules, route-compression semantics, and current unresolved questions are app-facing rather than product/spec-facing.
- When folder 02 is exhausted, move to folder 03. Exhausted means app view states, read-only client behavior, taste/atmosphere posture, quiet feedback posture, and knowledge-substrate direction are clear enough that the next useful work is a combined app/knowledge planning pass.
- By folder 03, the system should already propose what folder 04 should contain. Folder 04 should not be created automatically; its purpose should be justified by evidence from folders 01 through 03.

`03_MAC_APP_KNOWLEDGE_SUBSTRATE` is still a planning source set. It combines Mac desktop Mission Control planning with the Compiled Knowledge Substrate package before backend/data-model or Mac UI implementation starts. The likely next source set after it is a backend/data-model packet, but only after the 03 planning pass decides which schema style, synthetic fixtures, operator-promotion contracts, and evidence/freshness boundaries are stable.

Every folder should preserve North Star, route, evidence, freshness, withheld surfaces, and next-folder estimate. The source-set folder name is context position, not launch authorization.

## Delta Bridge Rule

`CHAT_STAY_UP_TO_DATE.md` may be uploaded alongside the active source-set folder when a chat needs small repo deltas without replacing all 24 files.

Bridge-only upload is enough when:

- the numbered folder still has exactly 23 content files plus `MANIFEST.md`;
- the manifest source commit remains the correct baseline for the chat;
- changes since upload are small docs/test clarifications or current-focus notes;
- withheld surfaces, folder purpose, file membership, and authority boundaries are unchanged.

A full 24-file refresh is needed when:

- any included source file changed in a way that affects the folder purpose;
- folder membership, withheld surfaces, upload rules, or source-set ladder position changed;
- the chat is moving from folder 01 to 02, from 02 to 03, or to a future folder;
- the bridge would need to explain too much and would become a substitute source set.

## Required Future Manifest Fields

Every future `MANIFEST.md` must include:

- commit hash used as source basis
- generated time
- purpose
- included files
- withheld surfaces
- stale conditions
- refresh trigger
- source-set ladder position
- next likely source-set folder
- upload instructions
- file count assertion: 23 content files + `MANIFEST.md` = 24 total upload files
- non-authority warning: generated copy is not canonical and does not authorize runtime/provider/service/private-data behavior

## Proposed Future Folder Purposes

| Folder | Purpose | Include bias | Withhold |
| --- | --- | --- | --- |
| `1_CURRENT_PRODUCT_SPEC` | Let ChatGPT review current product/spec shape. | Launch Ladder docs, runtime law, north star, modular ledger, control maps. | Runtime code unless explicitly needed, logs, secrets, private data, generated state. |
| `2_MAC_IOS_APP_BUILD` | Let Codex/ChatGPT help with read-only Mac/iOS app build planning. | App build brief, data contract docs, mock payload specs, routing/workspace docs. | Live services, private data, provider/model execution, credentials. |
| `3_MAC_APP_KNOWLEDGE_SUBSTRATE` | Let ChatGPT plan the Mac desktop Mission Control surface and SQLite-backed Compiled Knowledge Substrate together before implementation. | Mission Control fixture contract, first-screen composition, taste/atmosphere, quiet feedback, knowledge-substrate docs, authority/evidence boundaries, validation map. | UI implementation, backend/schema files, SQLite DBs, ingestion, real business files, runtime mutation, provider/model calls, private data, app naming. |
| Future backend/data-model source set | Let backend/data-model work consume schemas and freshness/evidence rules after 03 planning is exhausted. | Evidence/freshness, routing, readiness record shapes, operator promotions, SQLite schema contracts, validation map. | Runtime mutation, live service checks, private data, broad logs, provider/model calls. |

## Source-Set Freshness Rules

A generated source set is stale if:

- Any included source file changes after generation.
- Any withheld-surface rule changes.
- The source commit differs from current repo head and the manifest does not explain why.
- The folder has anything other than 24 upload files total.
- The manifest is missing upload instructions or stale conditions.
- A route consumes the source set after the modular ledger, service freeze, model policy, MCP profile, or Launch Ladder docs changed.

## Future Generator Requirements

A later generator script should:

- Use explicit manifests only.
- Refuse missing source files.
- Refuse broad roots.
- Refuse secrets, logs, vaults, LegalPrivate, Gmail bodies, private matter data, `.mcp.json` edits, and runtime state.
- Write deterministic `MANIFEST.md` files.
- Verify 24 files total per upload folder.
- Print stale/withheld-surface warnings.
- Avoid deletes outside the generated Launch Ladder ingest root.

## Upload Instructions For Future Manifests

Each future manifest should tell the operator:

1. Upload one numbered folder at a time.
2. Include all 24 files in that folder.
3. Optionally upload adjacent `CHAT_STAY_UP_TO_DATE.md` with the numbered folder when bridge-only delta conditions are true.
4. Do not count `CHAT_STAY_UP_TO_DATE.md` inside the 24 files.
5. Do not upload parent README files unless the manifest says so.
6. Treat ChatGPT output as advisory until promoted in repo.
7. Refresh the full 24-file source set if the repo has advanced materially or stale conditions are true.

## Do Not Do Yet

- Do not create generated ingest folders in this docs package.
- Do not create generator scripts in this docs package.
- Do not mirror private/runtime/log/vault/Legal/Gmail data.
- Do not let copied files become canonical.
