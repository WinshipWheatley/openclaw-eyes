# PC Windows Roots Private Data Boundary Breadcrumb

Generated/reviewed: 2026-05-05

Source basis: operator-provided read-only Windows storage/account audit summary and the current PC WSL canonical planning context. No Windows file contents, private documents, secrets, services, permissions, users, or storage were modified by this breadcrumb.

## 1. Status / Non-Authority

This is a docs-only planning breadcrumb.

It records a path/name-level boundary conclusion from a read-only Windows/PC root audit. It is not runtime truth, migration authority, cleanup authority, service authority, user-account authority, or permission to inspect private contents.

This document does not authorize commits, sync, moves, deletes, renames, archive work, permission changes, service changes, user changes, bridge behavior changes, secret inspection, private-data inspection, or broad content scanning.

## 2. Purpose

Preserve the current root-map conclusion before the Launch Ladder planning stack is committed or future storage cleanup is planned.

The key finding is that the Windows-side OpenClaw roots are not cleanly separated yet. Some roots are canonical code/planning surfaces, some are likely private legal surfaces, and some are mixed legacy/shared/runtime/business surfaces that may contain raw finance and tax source material.

The immediate goal is to prevent future agents from treating a path name such as "shared", "exports", "vault", or "OpenClaw" as proof of safety or authority.

## 3. Confirmed Root Map

Confirmed account and access facts from the operator-provided audit:

- Windows current user: `desktop-hp\open claw`.
- WSL canonical repo user: `openclaw`.
- Windows local account `openclawssh` exists, is enabled, last logon `2026-04-09`, description: `No-space SSH account for VS Code Remote`.
- Windows OpenSSH Server `sshd` is running and listening on port `22`.

Confirmed Windows root facts:

- `/home/openclaw` is the canonical code/docs/planning repo in WSL Ubuntu-E.
- `C:\OpenClaw` exists, about 2.76 GB, with mixed folders including `billing`, `data\ledger`, `legal`, `logs`, `memory`, `state`, `exports`, `law_program`, and `OpenClaw_Watch_EXPORTS`.
- `C:\OpenClawLegalPrivate` exists with staging, vault, exports, and reset proof folders. It is likely the existing private legal root.
- `C:\OpenClawShared` exists, about 0.08 GB, with `openclaw-vault`, `logs`, `business`, and source finance material.
- `C:\OpenClawShared\business\source_docs\finance_admin\ledger` exists.
- `C:\OpenClawShared\business\source_docs\finance_admin\tax_docs\2017` through `2025` exist, including `2019` subfolders and `2025` 1099 docs.

## 4. Current Risk

`C:\OpenClawShared` is not merely generated or shared reports. It currently contains raw/source finance and tax material under `business\source_docs\finance_admin` and must be treated as sensitive until a separate cleanup and relocation plan is approved.

`C:\OpenClaw` is mixed legacy/runtime/business/legal residue. It should not be treated as canonical, safe, generated-only, or shareable without further path-level and content-owner audit.

`C:\OpenClawLegalPrivate` is likely the private legal root, but "likely" is not enough to authorize moves, sync, cleanup, or ingestion.

The enabled `openclawssh` Windows account and running OpenSSH Server are access-surface facts, not permission to rely on that account for future architecture or to remove it as residue.

## 5. Working Classification

Current working classification:

- `/home/openclaw`: canonical repo for OpenClaw code, docs, planning, and Git-tracked source of truth.
- `C:\OpenClawLegalPrivate`: likely legal-private Windows root; treat as sensitive and local/private until a separate legal-private root contract confirms boundaries.
- `C:\OpenClawShared`: mixed and sensitive because it contains `business\source_docs\finance_admin`; do not treat as generated-only, shareable, or safe for new raw source files.
- `C:\OpenClaw`: mixed legacy/runtime/business/legal residue; not canonical without further audit.
- `openclawssh`: enabled Windows SSH/service account or residue; do not delete, disable, repurpose, or rely on it until separately audited.

This classification is conservative and path/name-based. It is meant to prevent accidental authority expansion.

## 6. Open Questions

Questions that need a separate approved audit:

- Which `C:\OpenClaw` folders are runtime state, generated exports, legacy residue, business source material, or legal-private material?
- Which data in `C:\OpenClawShared` should be relocated into finance-private or legal-private roots?
- Which `C:\OpenClawShared` folders are safe generated/shared outputs after raw source data is removed?
- Is `openclawssh` still required for VS Code Remote, bridge operations, or historical access only?
- Which processes, scripts, shortcuts, tasks, or services still reference `C:\OpenClaw`, `C:\OpenClawShared`, or `openclawssh`?
- Which roots are backed up, mirrored, synced, or exposed to Mac/watch surfaces?
- What is the approved retention and rollback plan for any future relocation?

Do not answer these questions by opening private contents from this breadcrumb.

## 7. Near-Term Handling Rules

Until a move manifest and private-root contract exist:

- do not add additional raw finance, tax, CPA, legal-private, client, or source business files to `C:\OpenClawShared`;
- do not treat `C:\OpenClawShared` as safe shared storage;
- do not use `C:\OpenClaw` as canonical repo state;
- do not sync raw finance/tax/private source material from Windows to Mac or from Mac to Windows;
- do not run broad content scans over these roots;
- do not move or clean folders based on path name alone;
- do not change permissions or ownership;
- do not delete, disable, or rely on `openclawssh` until a separate account/access audit says so;
- do not bridge private Windows source roots into Operator Harness or Launch Ladder source sets.

Planning docs may reference these roots as risk surfaces. Implementation work must wait for explicit authority.

## 8. Recommended Future Private Roots

Future Windows root doctrine should separate raw/private source material from generated/shared report surfaces.

Recommended target concepts:

- `C:\OpenClawFinancePrivate\tax_docs\YYYY\...`
- `C:\OpenClawFinancePrivate\ledger\...`
- `C:\OpenClawFinancePrivate\cpa_exchange\...`
- `C:\OpenClawMusicLawPrivate\...`
- `C:\OpenClawLegalPrivate\...`
- `C:\OpenClawShared\openclaw-vault\...` for generated/shared vault or report surfaces only after cleanup.

The future model should make source roots, generated outputs, shared reports, legal-private data, finance-private data, music-law-private data, logs, exports, reset proofs, and bridge packets explicit.

No broad moves from Mac or Windows should happen until a move manifest is approved.

## 9. What This Does Not Authorize

This breadcrumb does not authorize:

- moving, deleting, renaming, archiving, or cleaning files;
- editing `.gitignore` beyond the exact allowlist required for this document;
- changing permissions or ownership;
- disabling, deleting, modifying, or relying on `openclawssh`;
- editing OpenSSH Server or other services;
- syncing Windows roots to Mac or Mac roots to Windows;
- inspecting tax, CPA, finance, legal, client, vault, reset proof, secret, or private document contents;
- adding `C:\OpenClawShared` to a source set;
- treating `C:\OpenClawShared` as safe shared storage;
- treating `C:\OpenClaw` as canonical;
- committing changes.

It is only a boundary marker for future planning.

## 10. Next Safe Actions

Recommended next safe actions:

1. Commit planning-stack docs only with explicit paths after the operator confirms no unintended private paths are staged.
2. Create a separate docs-only move-manifest planning task for Windows roots, with no content inspection in the first pass.
3. Create a Windows private-root contract that distinguishes finance-private, music-law-private, legal-private, generated/shared reports, logs, exports, and bridge packets.
4. Audit references to `C:\OpenClaw`, `C:\OpenClawShared`, `C:\OpenClawLegalPrivate`, and `openclawssh` by script/config path only before any migration work.
5. Keep `C:\OpenClawShared` from receiving new raw finance/tax/private source files while cleanup planning is pending.

Exact next safe action: before commit, run `git status -sb --untracked-files=all` and stage only the intended planning docs and exact `.gitignore` allowlist changes by path. Do not use `git add .` for this stack.