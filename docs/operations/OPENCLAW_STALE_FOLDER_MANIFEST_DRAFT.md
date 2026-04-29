# OpenClaw Stale Folder Manifest Draft

Status: metadata-only draft. No cleanup authorized.

## Safety Rule

No deletion or quarantine is authorized by this document. Cleanup requires:

metadata manifest -> user review -> quarantine -> delayed deletion.

This manifest is based on shallow metadata only: path existence, top-level names/counts, approximate size, mtimes, and repo reference searches. It does not prove that contents are non-sensitive.

## Manifest Table

| Path | exists | approx size | top-level count | newest mtime | repo references | classification | risk | recommendation | deletion safety |
|---|---:|---:|---:|---|---|---|---|---|---|
| `/mnt/c/OpenClaw/legal` | yes | 2.0G | 9 | 2026-04-07 10:04 | Yes: old Legal scripts/modules and this control doc | private/sensitive possible; likely stale/conflicting old Legal path; not proven inactive | high | create deeper metadata-only manifest after user approval; do not touch contents | never delete directly; not safe yet |
| `/mnt/c/OpenClaw/law_program` | yes | 352K | 17 | 2026-04-25 15:29 | Yes, only as cleanup/control concern in operations control doc | duplicate/noisy; possible stale Legal planning mirror | medium | compare metadata against repo planning tree; migrate selected non-sensitive docs only if user confirms | likely safe only after quarantine; not safe yet |
| `/mnt/c/OpenClawShared` root-level artifacts/screenshots only | yes | about 3.6M root files; 81M full tree not inspected | 20 root items; 15 root files | 2026-04-12 14:42 for root files; 2026-04-19 for `openclaw-vault` dir | Yes for subtrees; no exact references found for root screenshots, `auth_url.txt`, or `security-report-2026-04-12.html` | active shared root with noisy root-level artifacts/screenshots | medium/high | create root-artifact manifest only; leave active subtrees alone | likely safe only after quarantine for unreferenced root files; not safe yet |
| `/home/openclaw/mac_eyes/legacy` | yes | 116K | 20 | 2026-04-04 17:40 | Yes, only in operations control doc | stale/noisy Mac bridge legacy artifacts | medium | create deeper metadata-only manifest; migrate selected non-sensitive docs after review | likely safe only after quarantine; not safe yet |
| `/home/openclaw/OpenClaw/exports/inspection-*` | yes | 388K | 15 matching dirs | 2026-04-20 23:09 | Yes: `RUNBOOK.md`, `CURRENT_STATE.md`, `chief_listener.py`, `test_qwen_logic.py`, operations control doc | active output pattern; old proof/export instances are noisy historical artifacts | low/medium | manifest by timestamp and producing tool; keep newest/known referenced outputs until retention policy exists | likely safe only after quarantine; not safe yet |
| `/home/openclaw/openclaw_arko_review` | yes | 3.7M | 204 | 2026-04-12 21:27 | Yes, only in operations control doc | duplicate/noisy review tree; likely stale but not proven disposable | medium | create deeper metadata manifest and compare filename set against canonical repo root | not safe yet |
| `/home/openclaw/openclaw-builder` | yes | 1.1G | 16 | 2026-04-20 21:49 | Yes, only in operations control doc | unknown/experimental side tree; possible stale builder repo; possible active local work | medium/high | confirm active status and nested git identity; metadata-only manifest excluding prompt/session history | unknown; not safe yet |

## Path-Specific Notes

### `/mnt/c/OpenClaw/legal`

Checked: existence, top-level item count, approximate size, top-level mtimes/names, and repo reference search.

Intentionally not inspected: case contents, exports, archive contents, OneDrive contents, logs, client/matter documents, or any private Legal matter data.

Why it may be stale/noisy/active/sensitive: it is the old Legal path referenced by older Legal scripts and modules, while current Legal v0 control docs point private Legal data to `/mnt/c/OpenClawLegalPrivate`. Top-level names include `cases`, `export_staging`, `legal_archive`, and `OneDrive_2026-04-07`, so private/client/matter data is possible.

Recommended next safe action: create a deeper metadata-only manifest after user approval. Do not inspect or move contents without explicit Legal-boundary instructions.

### `/mnt/c/OpenClaw/law_program`

Checked: existence, top-level count, approximate size, top-level mtimes/names, repo reference search, and shallow comparison against `/home/openclaw/docs/planning/openclaw_legal/law_program`.

Intentionally not inspected: document contents.

Why it may be stale/noisy/active/sensitive: same top-level count exists in the repo planning tree, and several repo copies are newer. The Windows path is only referenced as a cleanup/control concern, not as an active code path found in this pass.

Recommended next safe action: run a deeper metadata-only comparison of filenames, sizes, mtimes, and hashes if approved. Migrate selected non-sensitive docs only after user confirms canonical status.

### `/mnt/c/OpenClawShared` root-level artifacts/screenshots only

Checked: root-level names, file counts, sizes, mtimes, and repo references for exact root artifact names. Subtree references were noted only to distinguish active areas.

Intentionally not inspected: screenshot contents, `openclaw-vault` contents, business data, album data, logs, handoff contents, or any private/operator material.

Why it may be stale/noisy/active/sensitive: the root contains unreferenced screenshots and artifacts such as `auth_url.txt` and `security-report-2026-04-12.html`, while subtrees such as `album`, `business`, `OpenClaw-Handoff`, and `openclaw-vault` are heavily referenced and likely active.

Recommended next safe action: create a root-file-only artifact manifest. Do not touch active subtrees.

### `/home/openclaw/mac_eyes/legacy`

Checked: existence, top-level count, approximate size, top-level mtimes/names, and repo reference search.

Intentionally not inspected: operator notes, state file contents, layout contents, or any Mac private vault contents.

Why it may be stale/noisy/active/sensitive: filenames indicate legacy Mac bridge notes, layouts, state files, and archived operator-facing docs. It is only referenced by the operations control map.

Recommended next safe action: create a deeper metadata-only manifest and user-review any docs before migration or quarantine.

### `/home/openclaw/OpenClaw/exports/inspection-*`

Checked: matching directory list, count, approximate size, mtimes, and repo reference search.

Intentionally not inspected: inspection output contents.

Why it may be stale/noisy/active/sensitive: `chief_listener.py`, `RUNBOOK.md`, and `CURRENT_STATE.md` describe `inspection-*` as an output pattern, so the pattern is active. Individual dated outputs are historical proof/export instances and may be noisy.

Recommended next safe action: create a retention manifest by timestamp and producing tool. Keep latest and referenced inspection outputs until a retention policy is approved.

### `/home/openclaw/openclaw_arko_review`

Checked: existence, top-level count, approximate size, top-level mtimes/names, and repo reference search.

Intentionally not inspected: file contents, `.claude` contents, reports, tests, or duplicated runtime module contents.

Why it may be stale/noisy/active/sensitive: it contains a large duplicate-looking review tree with many runtime module names, docs, scripts, tests, and a `.claude` directory. It is only referenced by the operations control map, but it may contain unique review material.

Recommended next safe action: create a deeper metadata manifest and compare the filename set against the canonical repo root. Do not quarantine until unique artifacts are identified.

### `/home/openclaw/openclaw-builder`

Checked: existence, top-level count, approximate size, top-level mtimes/names, and repo reference search.

Intentionally not inspected: nested `.git` details, `.venv` contents, logs, Aider chat/input histories, prompt histories, or tests.

Why it may be stale/noisy/active/sensitive: it is a large side tree with nested `.git`, `.venv`, Aider history files, logs, tests, and architecture files. Recent mtime on `tests` means active use is possible. Aider histories may contain prompt/operator-sensitive data.

Recommended next safe action: confirm whether this nested builder repo is active, then create metadata-only manifest excluding prompt/session history.

## Explicit Do-Not-Touch List

The following paths are excluded from cleanup action by this draft:

- `/mnt/c/OpenClaw/logs`
- `/mnt/c/OpenClawShared/openclaw-vault`
- `/mnt/c/OpenClawLegalPrivate`
- `/home/openclaw/sidecars/hermes_home`
- `/home/openclaw/.chief.env`
- `/home/openclaw/.google-secrets`
- `/home/openclaw/.pii_vault.enc`

## Recommended Next Pass

Run a deeper metadata-only comparison pass for:

- `/mnt/c/OpenClaw/law_program` vs `/home/openclaw/docs/planning/openclaw_legal/law_program`
- `/home/openclaw/openclaw_arko_review` vs canonical repo root
- `/home/openclaw/openclaw-builder` status and nested git identity
- root-level `/mnt/c/OpenClawShared` artifacts

The next pass should still avoid private contents, secrets, `.env` files, tokens, Gmail bodies, client/matter documents, private Legal matter contents, Hermes sessions, PII vault contents, and Aider prompt histories.

## Verification Limits

This manifest does not prove contents are non-sensitive.

This manifest does not prove any path is safe to delete.

This manifest does not authorize cleanup, quarantine, migration, deletion, or renaming.

This manifest does not determine canonical ownership for duplicated docs or side trees.

This manifest does not inspect private Legal matter data, operator vault contents, secrets, Hermes sessions, PII vault contents, or Aider prompt histories.
