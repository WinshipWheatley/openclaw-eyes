# Windows Root Dependency Map Template

Generated/reviewed: 2026-05-05

## 1. Status / Non-Authority

This is a metadata-only documentation template for a future Windows root active-dependency map.

It does not run an audit. It does not authorize cleanup, migration, content inspection, source-set inclusion, ingestion, sync, private-root browsing, bridge changes, runtime changes, service changes, permission changes, user changes, provider/model calls, or commits.

This template is not runtime truth, migration authority, cleanup authority, service authority, source-set authority, bridge authority, private-root authority, or permission to inspect private contents.

## 2. Purpose

Define the table shape, placeholder row style, evidence rules, and validation checklist for a future Windows root active-dependency map.

The future map should classify `C:\OpenClaw`, `C:\OpenClawShared`, `C:\OpenClawLegalPrivate`, `openclawssh`, and related WSL `/mnt/c` references before cleanup, migration, source-set generation, Operator Harness ingestion, bridge redesign, or backend build-prep.

The template exists to keep future work path/name/reference-based until explicit approval exists. Shared, vault, watch, mirror, exports, and logs are not proof of safety, freshness, or authority.

## 3. Source Basis

Source basis for this template:

- `docs/planning/launch_ladder/27_WINDOWS_ROOT_TRIAGE_AND_DEPENDENCY_MAP_PLAN.md`
- `docs/planning/launch_ladder/26_PC_WINDOWS_ROOTS_PRIVATE_DATA_BOUNDARY_BREADCRUMB.md`
- `docs/planning/command_atlas/00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md`
- `docs/planning/launch_ladder/24_OPERATOR_HARNESS_PLANNING_INDEX.md`

No Windows private roots, private file contents, services, users, permissions, runtime state, provider/model state, or sync flows were inspected for this template.

## 4. Roots Covered By This Template

This template covers future metadata-only rows for:

- `/home/openclaw`: canonical code/docs/planning repo.
- `C:\OpenClaw`: mixed active/runtime/business/legal residue; quarantine and classify by subtree.
- `C:\OpenClawShared`: mixed/sensitive because it contains raw finance/tax source material under `business\source_docs\finance_admin`.
- `C:\OpenClawLegalPrivate`: likely active legal-private root; do not casually migrate, merge, index, or browse.
- Future `C:\OpenClawFinancePrivate`: intended concept for raw finance/tax/CPA source material, but no move is authorized here.
- `openclawssh`: enabled SSH/service-account residue; do not delete, disable, rely on, or repurpose until separately audited.
- Related `/mnt/c/...` references to the Windows roots above.

Mac private roots may be mentioned only as exclusion/context notes. They are not audit targets for this template.

## 5. Classification Labels

Allowed classification labels:

- `active-runtime-candidate`
- `active-config-candidate`
- `active-bridge-candidate`
- `legal-private-candidate`
- `finance-private-candidate`
- `shared-generated-candidate`
- `private-source-candidate`
- `legacy-residue-candidate`
- `unknown-quarantine`
- `do-not-touch`

Use multiple labels when needed. If a row could fit both shared/generated and private-source labels, keep the more restrictive label until owner review and a contract prove otherwise.

## 6. Active-Dependency Map Structure

Use this Markdown table shape for the future map:

| Path / Reference | Observed Source | Likely Owner | Dependency Categories | Classification Label | Allowed Next Action | Forbidden Next Action | Private-Data Risk | Evidence Needed Before Reclassification | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `...` | path/name/reference metadata only | owner TBD | runtime/service, script/config, bridge/sync, generated output, legal-private, finance/CPA, music-law/publishing, stale/archive, or unknown | one or more labels from Section 5 | boundary note, owner question, or explicit follow-up artifact only | browse, ingest, sync, move, clean, source-set include, provider/model context, or private-root scan | low, medium, high, or unknown | owner review, dependency proof, freshness basis, contract, or move manifest | placeholder row only |

Every future row should distinguish evidence of existence from evidence of active use. A reachable path does not prove authority. A mirrored path does not prove canon. A synced path does not prove freshness.

## 7. Placeholder Example Rows

The rows below are illustrative placeholders only. They are not verified by this template and must not be treated as audit findings.

| Path / Reference | Observed Source | Likely Owner | Dependency Categories | Classification Label | Allowed Next Action | Forbidden Next Action | Private-Data Risk | Evidence Needed Before Reclassification | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `C:\OpenClawShared\business\source_docs\finance_admin\tax_docs\YYYY\...` | Illustrative placeholder from boundary docs; not verified by this template | finance owner TBD | finance/CPA source dependency | `finance-private-candidate`, `private-source-candidate`, `do-not-touch` | keep as boundary note; prepare owner question | inspect contents, browse, ingest, sync, move, clean, source-set include, provider/model context | high | finance-private root contract, owner review, approved move manifest, retention plan | illustrative only |
| `C:\OpenClawLegalPrivate\vault\...` | Illustrative placeholder from boundary docs; not verified by this template | legal owner TBD | legal-private workflow dependency | `legal-private-candidate`, `private-source-candidate`, `do-not-touch` | keep as boundary note; prepare legal-private contract question | inspect contents, index, browse, merge, migrate, sync, source-set include | high | legal-private root contract, owner review, approved move manifest, rollback plan | illustrative only |
| `C:\OpenClaw\logs\...` | Illustrative placeholder from boundary docs; not verified by this template | runtime owner TBD | runtime/service dependency, generated report/output dependency, unknown/quarantine | `active-runtime-candidate`, `shared-generated-candidate`, `unknown-quarantine` | map references by path/name only; ask whether logs are active dependency candidates | delete, clean, archive, sync, expose in Harness, treat as non-sensitive | unknown | runtime/log/state/bin/config dependency map, retention rule, owner review | illustrative only |

## 8. Validation Checklist Before Actual Audit

Before a real audit starts, confirm:

- the audit scope is metadata-only;
- the exact roots and reference strings are listed before any command is run;
- private-content browsing is forbidden;
- broad Windows root traversal is forbidden;
- source-set inclusion is forbidden;
- Operator Harness ingestion is forbidden;
- provider/model context inclusion is forbidden;
- cleanup, move, delete, rename, sync, archive, deduplication, service, user, permission, SSH, runtime, and bridge changes are forbidden;
- every row has an allowed next action and a forbidden next action;
- every row has a private-data risk value;
- every reclassification requires evidence and owner review.

## 9. Forbidden Audit Behaviors

Do not:

- inspect private file contents;
- traverse Windows private roots broadly;
- run broad root scans;
- add private roots to source sets, agent browsing, Gemini/Codex context, provider/model context, or Operator Harness ingestion;
- move, delete, rename, clean, archive, deduplicate, or sync files;
- change permissions, services, users, SSH settings, launchers, tasks, or runtime state;
- rely on, delete, disable, repurpose, or redesign around `openclawssh`;
- treat `C:\OpenClawShared` as safe shared storage;
- treat `C:\OpenClaw` as canonical;
- treat shared, vault, watch, mirror, exports, or logs as proof of safety, freshness, or authority.

## 10. Allowed Evidence Types

Allowed evidence types for a future map:

- explicit path strings;
- explicit directory names and filenames;
- top-level metadata such as size and timestamp when explicitly approved;
- repo-local references in docs, scripts, configs, and task definitions by exact path;
- git status or ignore status for repo-local files;
- owner-supplied summaries;
- existing planning-doc boundary notes;
- approved dependency-map summaries.

Allowed evidence is not authority by itself. It is only a basis for classification questions and follow-up artifacts.

## 11. Source-Set Exclusion Rule

No Windows or Mac private roots should enter source sets, agent browsing, Gemini/Codex context, provider/model context, Operator Harness ingestion, or backend/data-contract source-set generation unless explicitly approved by a later private-root contract and source-set bridge.

`C:\OpenClawShared`, `C:\OpenClawLegalPrivate`, candidate `C:\OpenClawFinancePrivate`, Mac `OpenClawFinancePrivate`, Mac `OpenClawLegalPrivate`, and Mac `OpenClawMusicLawPrivate` are excluded by default.

`/home/openclaw` remains the canonical code/docs/planning repo. That does not make any mounted Windows path canonical, fresh, safe, or actionable.

## 12. Next Safe Action

After this template is committed, the next safe action is a read-only review of the template itself against `27_WINDOWS_ROOT_TRIAGE_AND_DEPENDENCY_MAP_PLAN.md` to confirm that every required column, classification label, private-data exclusion, and forbidden audit behavior is present.

Do not run the actual Windows root audit until the operator explicitly approves a metadata-only audit command set with exact paths, exclusions, and no private-content traversal.
