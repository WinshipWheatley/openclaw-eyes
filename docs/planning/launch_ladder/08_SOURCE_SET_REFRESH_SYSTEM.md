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

This slice does not create:

- `CHATGPT_PROJECT_INGEST_LAUNCH_LADDER/`
- generator scripts
- Mac sync scripts
- ChatGPT Project upload batches

## Future Output Shape

```text
CHATGPT_PROJECT_INGEST_LAUNCH_LADDER/
  1_CURRENT_PRODUCT_SPEC/
  2_MAC_IOS_APP_BUILD/
  3_BACKEND_AND_DATA_MODEL/
```

Each numbered folder should contain exactly 24 upload files total:

- 23 curated content files.
- 1 `MANIFEST.md`.

Do not use 24 content files plus a manifest. The manifest counts as one upload file.

## Required Future Manifest Fields

Every future `MANIFEST.md` must include:

- commit hash used as source basis
- generated time
- purpose
- included files
- withheld surfaces
- stale conditions
- refresh trigger
- upload instructions
- file count assertion: 23 content files + `MANIFEST.md` = 24 total upload files
- non-authority warning: generated copy is not canonical and does not authorize runtime/provider/service/private-data behavior

## Proposed Future Folder Purposes

| Folder | Purpose | Include bias | Withhold |
| --- | --- | --- | --- |
| `1_CURRENT_PRODUCT_SPEC` | Let ChatGPT review current product/spec shape. | Launch Ladder docs, runtime law, north star, modular ledger, control maps. | Runtime code unless explicitly needed, logs, secrets, private data, generated state. |
| `2_MAC_IOS_APP_BUILD` | Let Codex/ChatGPT help with read-only Mac/iOS app build planning. | App build brief, data contract docs, mock payload specs, routing/workspace docs. | Live services, private data, provider/model execution, credentials. |
| `3_BACKEND_AND_DATA_MODEL` | Let backend/data-model work consume schemas and freshness/evidence rules. | Evidence/freshness, routing, readiness record shapes, validation map. | Runtime mutation, live service checks, private data, broad logs. |

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
3. Do not upload parent README files unless the manifest says so.
4. Treat ChatGPT output as advisory until promoted in repo.
5. Refresh the source set if the repo has advanced or stale conditions are true.

## Do Not Do Yet

- Do not create generated ingest folders in this docs package.
- Do not create generator scripts in this docs package.
- Do not mirror private/runtime/log/vault/Legal/Gmail data.
- Do not let copied files become canonical.
