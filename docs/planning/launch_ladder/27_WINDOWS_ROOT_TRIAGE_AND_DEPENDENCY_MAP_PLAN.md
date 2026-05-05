# Windows Root Triage And Dependency Map Plan

Generated/reviewed: 2026-05-05

Source basis: `26_PC_WINDOWS_ROOTS_PRIVATE_DATA_BOUNDARY_BREADCRUMB.md`, `docs/planning/command_atlas/00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md`, `20_DEPLOYMENT_TOPOLOGY_NODE_PORTABILITY_AND_OS_AGNOSTICISM.md`, and `22_CROSS_PLATFORM_BRIDGE_CONTRACT_BREADCRUMB.md`. This plan uses path/name-level planning facts only. It does not inspect Windows root contents, private documents, secrets, services, users, permissions, provider/model state, runtime folders, or bridge payload contents.

## 1. Status / Non-Authority

This is a docs-only planning artifact for a future Windows root triage and active-dependency mapping pass.

It is not runtime truth, migration authority, cleanup authority, service authority, source-set authority, bridge authority, private-root authority, user-account authority, or permission to inspect private contents.

This document does not authorize commits, sync, file moves, deletes, renames, archival work, broad cleanup, permission changes, service changes, user changes, SSH changes, provider/model calls, MCP calls, Operator Harness ingestion, source-set generation, app implementation, private-data inspection, or broad content scanning.

## 2. Purpose

Define how a future audit should classify `C:\OpenClaw`, `C:\OpenClawShared`, `C:\OpenClawLegalPrivate`, `openclawssh`, and related WSL `/mnt/c` references before any cleanup, migration, bridge work, source-set generation, or Operator Harness build-prep.

The plan exists to prevent path-name authority laundering. Connected does not mean authorized. Mirrored does not mean canonical. Shared does not mean safe. Generated does not mean non-sensitive. Synced does not mean fresh.

## 3. Roots In Scope

In scope for a future metadata-only audit:

- `/home/openclaw`: canonical code/docs/planning repo in PC WSL Ubuntu-E.
- `C:\OpenClaw`: mixed active/runtime/business/legal residue; classify by subtree, not by root name.
- `C:\OpenClawShared`: active/mixed and sensitive because it contains `business\source_docs\finance_admin` with ledger/tax material; do not treat it as safe shared storage.
- `C:\OpenClawLegalPrivate`: likely active legal-private root; preserve until a legal-private root contract says otherwise.
- `openclawssh`: enabled SSH/service-account residue; do not delete, disable, rely on, or redesign around it until separately audited.
- WSL `/mnt/c/...` references to the Windows roots above.
- Mac private-root and bridge references only as dependency-map context, not as targets for Windows cleanup.

## 4. Why This Must Precede Cleanup

Windows-side OpenClaw roots are not cleanly separated yet. A future cleanup could break active dependencies, expose private material, erase rollback evidence, or migrate the wrong subtree if it treats root names as authority.

Runtime/log/state/bin/config folders are active-dependency candidates, not cleanup candidates. They must be mapped before any deletion, move, deduplication, archive, sync, source-set inclusion, or bridge redesign is proposed.

No broad moves from Mac or Windows should happen until an approved move manifest exists.

## 5. Metadata-Only Audit Method

The future audit should use path/name/reference metadata only.

Allowed methods:

- list explicit root names and top-level subtree names;
- record path strings, filenames, directory names, sizes, timestamps, and known references where safe;
- search the canonical repo for literal path/reference strings such as `C:\OpenClaw`, `C:\OpenClawShared`, `C:\OpenClawLegalPrivate`, `openclawssh`, and `/mnt/c/OpenClaw`;
- inspect scripts, configs, docs, and task definitions by explicit path when they are inside the canonical repo and not private data;
- classify references as candidates until a follow-up owner review confirms behavior.

Forbidden methods:

- opening tax, CPA, finance, legal, client, vault, reset proof, secret, or private document contents;
- traversing Windows roots broadly by content;
- running broad recursive scans over private roots;
- moving, deleting, renaming, archiving, syncing, or deduplicating files;
- changing permissions, users, SSH settings, services, launchers, tasks, or bridge behavior;
- adding private roots to source sets, agent browsing, Gemini/Codex context, Operator Harness ingestion, or provider/model context.

## 6. Dependency Categories

Classify each observed subtree or reference into one or more dependency categories:

- runtime/service dependency;
- script/config dependency;
- bridge/sync dependency;
- generated report/output dependency;
- legal-private workflow dependency;
- finance/CPA source dependency;
- music-law/publishing source dependency;
- stale/archive candidate;
- unknown/quarantine.

Multiple categories may apply. When categories conflict, use the most conservative label until an approved owner review resolves it.

## 7. Classification Labels

Use these labels in the future triage map:

- `canonical-repo`: code/docs/planning truth lives here.
- `active-dependency-candidate`: may be needed by runtime, scripts, services, logs, state, bin, config, bridge, or current workflows.
- `private-source-candidate`: may contain raw legal, finance, CPA, music-law, publishing, client, or personal source material.
- `generated-shared-candidate`: may contain generated reports, exports, bridge packets, or review outputs, but generated does not mean non-sensitive.
- `safe-reference-only`: may be cited as a boundary or path note but not browsed or ingested.
- `stale-archive-candidate`: may be old residue, but not movable until dependency and retention checks pass.
- `unknown-quarantine`: classification is not yet safe enough for cleanup, migration, source-set inclusion, or Harness display.
- `do-not-touch`: explicitly protected until a separate contract, audit, or approval exists.

## 8. Active-Dependency Map Shape

The future map should be a table or structured Markdown artifact with one row per root, subtree, or explicit reference.

Minimum columns:

- path or reference string;
- observed source of the reference;
- root owner or likely owner, if known;
- dependency categories;
- classification label;
- evidence basis;
- freshness basis;
- allowed next action;
- forbidden next action;
- private-data risk;
- bridge/source-set/Operator Harness exposure status;
- open question;
- required follow-up artifact.

The map should distinguish evidence of existence from evidence of active use. A path being visible, connected, mirrored, generated, or shared does not make it canonical, safe, fresh, or actionable.

## 9. Private-Data Handling Rules

Private roots and private-source candidates must be excluded from source sets, agent browsing, Gemini/Codex context, Operator Harness ingestion, provider/model context, and broad repo searches unless explicitly approved.

Treat legal, finance/CPA, tax, ledger, music-law/publishing, client, vault, reset proof, secret, and `.private` surfaces as private by default.

The audit may record that a private path exists or that a path name suggests a data class. It must not inspect private content to prove the classification in this phase.

## 10. Root-Specific Triage Rules

`/home/openclaw` remains the canonical code/docs/planning repo unless a later canonical document says otherwise.

`C:\OpenClaw` is mixed active/runtime/business/legal residue. Classify by subtree and known references. Do not treat it as canonical because it has the project name.

`C:\OpenClawShared` is active/mixed and sensitive because it contains `business\source_docs\finance_admin` with ledger/tax material. Do not treat it as safe shared storage, generated-only, or source-set eligible.

`C:\OpenClawLegalPrivate` is likely an active legal-private root. Preserve it until a legal-private root contract, owner review, and approved move manifest say otherwise.

`openclawssh` is an enabled SSH/service-account residue. Do not delete, disable, rely on, redesign around, or repurpose it until a separate account/access audit exists.

WSL `/mnt/c` references are bridge/path references, not authority. Translate them into the same Windows-root classification model before proposing any action.

## 11. What To Preserve

Preserve until mapped and approved:

- canonical repo state in `/home/openclaw`;
- runtime/log/state/bin/config dependency candidates;
- service/account/access facts involving `openclawssh` and Windows OpenSSH;
- bridge/sync scaffolding currently used for communication or mirroring;
- legal-private root structure and reset-proof/export evidence;
- generated reports and bridge packets needed for auditability;
- timestamps, sizes, path names, reference evidence, and rollback breadcrumbs.

## 12. What To Quarantine

Quarantine as non-browsable, non-ingestable planning surfaces:

- `C:\OpenClawShared` as a whole until raw finance/tax source material is separated;
- `C:\OpenClawShared\business\source_docs\finance_admin` and all ledger/tax/CPA descendants;
- `C:\OpenClawLegalPrivate` until a legal-private root contract exists;
- candidate finance-private, legal-private, music-law-private, client, vault, reset proof, and secret surfaces;
- unknown `/mnt/c` references that point into OpenClaw Windows roots;
- stale/archive candidates before retention and dependency checks.

Quarantine means do not browse content, ingest, sync, include in source sets, clean, move, or expose to Operator Harness.

## 13. What To Migrate Later

Later migration candidates may include:

- generated/shared reports after raw private material is separated;
- finance-private source material into a future finance-private root contract;
- music-law/publishing source material into a future music-law-private root contract;
- stale/archive residue after dependency and retention checks;
- runtime/log/state/config homes only after an approved runtime dependency map exists;
- bridge packets only after the cross-platform bridge contract and adapter plan exist.

Migration requires an approved move manifest, rollback plan, owner review, data-class classification, and no-private-content browsing in the planning phase.

## 14. What Not To Touch

Do not touch:

- `C:\OpenClaw` as a whole;
- `C:\OpenClawShared` as a whole;
- `C:\OpenClawLegalPrivate` as a whole;
- `C:\OpenClawShared\business\source_docs\finance_admin` or any finance/tax/CPA source material;
- Mac `OpenClawFinancePrivate`, `OpenClawLegalPrivate`, or `OpenClawMusicLawPrivate` roots;
- runtime, log, state, bin, config, memory, exports, reset proof, bridge, vault, or generated-report folders before dependency mapping;
- `openclawssh`, Windows OpenSSH Server, SSH keys, service settings, user profiles, or permissions;
- `.private` contents, secrets, private legal/client files, tax files, CPA files, finance ledgers, or live vault contents.

## 15. Acceptance Criteria Before Any Move/Cleanup

Before any move, cleanup, migration, deduplication, archive, source-set inclusion, bridge change, or Operator Harness build-prep, all of these must exist:

- active-dependency map for all relevant Windows roots and `/mnt/c` references;
- root-specific classification labels for each subtree in scope;
- private-data exclusions confirmed for source sets and agent browsing;
- owner review for legal-private, finance-private, music-law-private, and shared/generated candidates;
- separate `openclawssh` account/access audit;
- runtime/log/state/bin/config dependency map;
- bridge/sync dependency map tied to the future bridge contract;
- approved move manifest with rollback plan;
- explicit operator approval for the bounded next action.

## 16. Follow-Up Artifacts

Recommended follow-up artifacts:

1. Windows root active-dependency map, path/name/reference metadata only.
2. `openclawssh` account/access audit, no credential inspection.
3. Windows private-root contract for legal, finance/CPA, and music-law/publishing roots.
4. Generated/shared report contract for safe output surfaces after raw private material is separated.
5. Runtime/log/state/bin/config dependency map.
6. Cross-platform bridge contract and current-adapter inventory.
7. Move manifest template with rollback and retention sections.
8. Source-set exclusion bridge for private Windows and Mac roots.

## 17. What This Does Not Authorize

This plan does not authorize:

- inspecting private file contents;
- traversing private roots broadly;
- moving, deleting, renaming, archiving, cleaning, deduplicating, or syncing files;
- changing permissions, services, users, SSH settings, launchers, tasks, or bridge behavior;
- relying on, disabling, deleting, or redesigning around `openclawssh`;
- adding Windows or Mac private roots to source sets, agent browsing, Gemini/Codex context, provider/model context, or Operator Harness ingestion;
- treating `C:\OpenClawShared` as safe shared storage;
- treating `C:\OpenClaw` as canonical;
- treating generated/shared paths as non-sensitive without contract review;
- committing changes.

## 18. Next Safe Action

Create a docs-only active-dependency map template for the Windows roots using explicit path/name/reference metadata only. The template should include the map columns above, sample rows with placeholders only, and a validation checklist that forbids content inspection, moves, sync, service changes, provider/model calls, and source-set inclusion.

Do not run the audit, browse private roots, or propose cleanup until the template and approval boundaries are accepted.
