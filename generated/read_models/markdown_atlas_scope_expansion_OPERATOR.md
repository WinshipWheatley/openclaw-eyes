# Markdown Atlas Scope Expansion v0

## ELIWINSHIP Summary

This report maps what the Markdown Atlas already knows and how to expand it safely. It is metadata-only: paths, filenames, counts, roots, and existing ledger facts. It does not read Markdown bodies, scan private folders, reorganize files, create vectors, or ask an AI to judge old notes yet.

## Current Coverage

- SQLite ledger present: `true`
- Ledger path: `/home/openclaw/.openclaw/business_ops/ledger.sqlite`
- Corpus roots: `7`
- Corpus paths: `43762`
- Corpus path labels: `434362`
- Markdown Atlas runs: `3`
- Markdown documents: `598`
- Markdown classifications: `2990`
- Markdown links: `1794`
- Reorg candidates: `598`
- Supersession rows: `9`
- Evidence sources/items: `12` / `206`

## Root Scope

- `REQUIRES_OPERATOR_APPROVAL` `not_scanned://client/project_root`: Ask operator whether this root belongs in the Markdown universe before any metadata run.
- `REQUIRES_OPERATOR_APPROVAL` `not_scanned://client/runtime_root`: Ask operator whether this root belongs in the Markdown universe before any metadata run.
- `REQUIRES_OPERATOR_APPROVAL` `not_imported://github/legacy_openclaw`: Ask operator whether this root belongs in the Markdown universe before any metadata run.
- `CURRENTLY_COVERED` `/Users/hwinshipwheatley/openclaw_generated_read_models`: Re-run metadata-only Atlas on existing registered roots if a refresh is needed.
- `CURRENTLY_COVERED` `/Users/hwinshipwheatley/Developer/OpenClawMissionControl/OpenClaw Mission Controle`: Re-run metadata-only Atlas on existing registered roots if a refresh is needed.
- `REQUIRES_OPERATOR_APPROVAL` `unknown_until_operator_manifest://mac/openclaw_mirror`: Ask operator whether this root belongs in the Markdown universe before any metadata run.
- `CURRENTLY_COVERED` `/home/openclaw`: Re-run metadata-only Atlas on existing registered roots if a refresh is needed.
- `CANDIDATE_METADATA_ONLY` `/mnt/e/openclaw`: Ask operator whether this exact root should be added to the corpus root allowlist.
- `BLOCKED_PRIVATE` `operator_home_wide`: Require explicit narrow subfolder approval before metadata indexing.
- `REQUIRES_OPERATOR_APPROVAL` `mac_desktop_documents_downloads`: Ask operator whether these surfaces are included or excluded.
- `BLOCKED_C_DRIVE` `windows_c_drive_mount`: Do not scan; require a separate explicit approval path if ever reconsidered.
- `BLOCKED_SYSTEM` `system_roots_wide`: Keep blocked.

## Markdown Universe Gaps

- `repo_a_known_markdown`: Refresh metadata-only Atlas on existing registered roots.
- `repo_b_reference_markdown`: Require explicit Repo B root approval and reference-only policy.
- `mac_app_markdown`: Keep Mac-side body access blocked; use manifest/root receipts only.
- `handoff_markdown`: Classify by path metadata first; do not treat as current doctrine.
- `old_prompt_markdown`: Label as history/candidate doctrine/residue before semantic review.
- `doctrine_markdown`: Use current runtime law and receipts as promotion gates.
- `generated_operator_markdown`: Exclude from human-authored Markdown analysis unless specifically requested.
- `personal_notes_unknown`: Ask operator for explicit narrow roots and sensitivity boundaries.
- `external_drive_unknown`: Ask operator for exact root allowlist before metadata indexing.
- `desktop_downloads_unknown`: Ask whether these areas are included or excluded.

## Recommended Next Expansion

- Recommendation: `RUN_METADATA_ONLY_ON_EXISTING_REGISTERED_ROOTS`
- Include registered root ids: `mac_generated_read_models, mac_mission_control_app, pc_wsl_home_openclaw`
- Keep body ingestion, private broad roots, vectors, and semantic review blocked.
- Ask for explicit root approval before adding new roots.

## Future AI Judgment Policy

- Later, after metadata classification, AI may summarize selected allowlisted docs and recommend canonical/stale/residue labels.
- AI may recommend source-card promotion, stable-map summaries, or archive/reorg candidates without moving files.
- Blocked now: broad body summarization, truth promotion from old notes, file moves/deletes, vector memory from all docs, and private-note use without approval.

## Operator Questions

- Which roots should be considered part of Winship's Markdown universe?
- Are Mac Desktop, Documents, and Downloads included or excluded?
- Are external drives included or excluded?
- Is Repo B Markdown reference-only?
- Should old prompts be preserved as history, candidate doctrine, or residue?
- Which Markdown folders are sensitive/private?
- Should generated read-model/operator Markdown be excluded from human-authored Markdown analysis?

## Boundary

- No broad raw Markdown body ingestion.
- No private root approval by default.
- No file moves, deletes, renames, vector indexing, model calls, network, Git sync, Mac sync/import, or Mission Control app mutation.
