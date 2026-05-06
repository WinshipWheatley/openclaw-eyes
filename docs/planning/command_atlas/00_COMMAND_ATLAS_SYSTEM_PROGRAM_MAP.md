# Command Atlas / OpenClaw System Program Map

Generated/reviewed: 2026-05-05

Source basis: recent read-only systems-engineering signal alignment pass, `docs/planning/launch_ladder/24_OPERATOR_HARNESS_PLANNING_INDEX.md`, `docs/planning/launch_ladder/26_PC_WINDOWS_ROOTS_PRIVATE_DATA_BOUNDARY_BREADCRUMB.md`, current OpenClaw runtime law, and current core architecture principles. No private roots, Windows roots, services, users, runtime folders, models, providers, sync flows, or private data were inspected or modified for this artifact.

## 1. Status / Non-Authority

This is a docs-only planning artifact for the Command Atlas / OpenClaw System Program layer.

It records the current system-program alignment signal before Operator Harness implementation resumes. It is not runtime truth, migration authority, cleanup authority, service authority, user-account authority, bridge authority, model-routing authority, or permission to inspect private contents.

This document does not authorize commits, sync, file moves, deletes, renames, broad Windows cleanup, runtime-folder creation, permission changes, service changes, user changes, model/provider calls, app implementation, ingestion, bridge behavior changes, secret inspection, private-data inspection, or broad content scanning.

## 2. Purpose

The purpose of this artifact is to name the top layer clearly: Command Atlas / OpenClaw System Program.

The Operator Harness remains important, but it is a lane, cockpit, and operational view under the Atlas. It is not the entire OpenClaw system and should not pull every lane, root, private-data boundary, runtime dependency, and agentic workflow into its own implementation plan.

This map prevents the next implementation step from overfitting to the Harness screen while root boundaries, lane responsibilities, and active dependency candidates are still unsettled.

## 3. System Signal

The systems-engineering signal is that OpenClaw has outgrown a single-app framing.

Current planning now spans operator cockpit design, legal discovery, Chief/Cassandra/Guardian/Hermes lanes, bridge and deployment topology, local model benchmarking, private finance/legal/music-law roots, agentic build/test loops, validation discipline, source-set freshness, and Windows root triage.

The correct top layer is therefore not "Operator Harness app". The correct top layer is Command Atlas / OpenClaw System Program: a program map that keeps lane identity, authority boundaries, private-data domains, runtime dependencies, and deployment surfaces separate enough to reason about safely.

Core conclusion: do not resume Operator Harness implementation until the system program map and root/data-boundary triage are established.

## 4. Command Atlas Topology

Command Atlas is the top planning surface for OpenClaw system organization.

Its job is to keep these concerns distinct:

- lane identity and purpose;
- cockpit/view surfaces;
- canonical source locations;
- private roots and data classes;
- runtime, log, state, bin, and config dependency candidates;
- bridge and deployment topology;
- agentic planning, build, test, and validation loops;
- local model and Hardware Fit Analyzer experiment lanes;
- source-set freshness and taste-polish discipline.

`/home/openclaw` remains the canonical code/docs/planning repo. Windows and Mac private roots may be important operational surfaces, but they do not become canonical code or planning truth by path name, bridge visibility, sync status, or UI visibility.

## 5. Lane Inventory

Current Command Atlas lanes include:

- Operator Harness / Mission Control: the cockpit lane for operator-facing mission state, evidence, freshness, authority-scope display, and operational navigation.
- Legal discovery app: a legal-workflow lane with its own private-root implications and app-surface needs.
- Chief: the command, approval, routing, and executive synthesis lane, bounded by existing OpenClaw authority policy.
- Cassandra: the briefing, outreach, context, and relationship-intelligence lane, bounded by contact and data policies.
- External Communications / Relationship Judgment: the external-facing judgment lane for customer, client, venue, contractor, friend-of-system, outside-circle, and other relationship-sensitive interactions; it handles tone-reading, reputation, boundary, escalation, and promise-control doctrine without granting send or execution authority.
- Guardian: the safety, policy, and protective oversight lane.
- Hermes: the messaging, delivery, bridge, or transport-adjacent lane where applicable, without making transport equal authority.
- Future PI / local-private assistant lane: a privacy-sensitive personal-intelligence lane that may use local models only after separate fit, data, and routing approval.
- Agentic planner/build/test loop: the bounded execution lane for planning, implementation, validation, and release hygiene.
- Mac/PC bridge and deployment topology: the portability lane that separates stable contracts from machine-specific adapters.
- Private data roots: legal, finance/CPA, and music law/publishing roots, each with separate source/private/shared/generated boundaries.
- Local model benchmark / Hardware Fit Analyzer: the experiment lane for hardware fit, model/runtime feasibility, and local benchmark evidence only.
- Source-set / validation / taste-polish discipline: the lane that keeps source freshness, UI taste, validation gates, and planning inputs from drifting.
- Agentic build-loop / GitHub Action pattern without Claude: the planning lane for borrowing headless job packets, explicit tool allowlists, structured receipts, resumable state handles, and CI/PR feedback loops while keeping execution local-first, approval-gated, non-Claude, and explicit-authority-only.
- Windows root triage: the path/dependency classification lane for `C:\OpenClaw`, `C:\OpenClawShared`, `C:\OpenClawLegalPrivate`, `openclawssh`, and related residue.

## 6. Operator Harness Position

Operator Harness is a lane and cockpit under Command Atlas.

It should surface the mission-control view of relevant lanes, not absorb the whole system into one app boundary. Its first implementation should wait until the Atlas can answer which lane owns which data, which roots are private or mixed, which paths are active dependency candidates, and which signals are safe to display.

The Harness may eventually show legal, finance, model-fit, agentic-loop, bridge, and deployment signals, but display does not create authority. UI-visible does not mean actionable. Synced does not mean fresh. Mirrored does not mean canonical. Connected does not mean authorized.

## 7. Private Data / Root Boundary Posture

Current conservative posture:

- `/home/openclaw` is the canonical WSL code/docs/planning repo.
- `C:\OpenClaw` is mixed active/runtime/business/legal residue and must be quarantined by subtree before any cleanup or migration plan treats it as safe.
- `C:\OpenClawShared` is active/mixed and contains raw finance/tax source material under `business\source_docs\finance_admin`; it is sensitive until cleaned and contractually separated.
- `C:\OpenClawLegalPrivate` is likely an active legal-private root; do not casually migrate, merge, deduplicate, or replace it.
- Mac private roots now exist and use distinct roles: `OpenClawFinancePrivate`, `OpenClawLegalPrivate`, and `OpenClawMusicLawPrivate`.
- `openclawssh` is an enabled Windows SSH/service-account residue; do not delete, disable, repurpose, or rely on it until a separate account/access audit says so.

The boundary problem is not solved by naming a root "shared", "private", "vault", "exports", or "OpenClaw". Path names are clues, not authority.

## 8. Known Signal Distortions

Known distortions that can mislead future work:

- Treating Operator Harness as the whole system instead of one cockpit lane.
- Treating `C:\OpenClawShared` as safe because it says "Shared" while it contains raw finance/tax source material.
- Treating `C:\OpenClaw` as canonical because it has the project name while `/home/openclaw` is the canonical repo.
- Treating `C:\OpenClawLegalPrivate` as migration-ready because it looks organized while it may already be an active private legal root.
- Treating runtime, log, state, bin, and config folders as cleanup candidates before dependency mapping.
- Treating Mac private roots as mirror or staging surfaces without documenting their distinct legal, finance, and music-law roles.
- Treating an enabled SSH account as either approved infrastructure or disposable residue without a separate audit.
- Treating Cassandra voice styling as sufficient external-communication judgment without separate risk, evidence, escalation, reputation, and promise-control checks.
- Treating a Claude Code SDK / GitHub Action pattern as permission to install Claude tooling, create workflow automation, run cloud agents, or let CI become hidden execution authority.
- Treating local model benchmark planning as production PI routing authority.
- Treating bridge visibility, mirrored files, or UI display as proof of freshness, canon, or authority.

## 9. Current Blockers Before Harness Work

Operator Harness implementation should remain paused until these blockers are resolved or explicitly bounded:

1. Command Atlas ownership map exists for lanes, cockpit surfaces, private roots, runtime dependencies, and validation gates.
2. Windows root triage separates active dependency candidates from stale residue by subtree.
3. `C:\OpenClawShared` finance/tax source material is treated as sensitive and excluded from Harness source sets.
4. `C:\OpenClawLegalPrivate` has a legal-private root contract before any migration or merge proposal.
5. Mac private root roles are documented as separate finance, legal, and music-law/publishing domains.
6. `openclawssh` is audited as an account/access surface before future reliance or removal.
7. Runtime/log/state/bin/config references are mapped before any cleanup recommendation.
8. The Operator Harness read model is scoped to safe planning/demo fixtures or approved public/generated signals.

## 10. Corrected Follow-Up Sequence

The corrected sequence is:

1. Keep `/home/openclaw` as canonical code/docs/planning truth.
2. Use Command Atlas as the top layer and Operator Harness as one cockpit lane under it.
3. Create path/dependency triage maps for Windows roots before cleanup.
4. Map runtime, log, state, bin, and config references as active-dependency candidates before move planning.
5. Create private-root contracts for legal, finance/CPA, and music law/publishing.
6. Create a separate `openclawssh` account/access audit before relying on or removing the account.
7. Define safe generated/shared surfaces only after raw/source private material is separated.
8. Resume Operator Harness implementation only against approved fixtures, safe generated reports, or explicitly authorized source sets.

Do not execute broad Windows root cleanup yet. First create triage and dependency maps.

## 11. Do-Not-Touch / Do-Not-Move-Yet List

Do not touch or move yet:

- `C:\OpenClaw` as a whole.
- `C:\OpenClawShared` as a whole.
- `C:\OpenClawLegalPrivate` as a whole.
- `C:\OpenClawShared\business\source_docs\finance_admin` or any finance/tax/CPA source material.
- Mac `OpenClawFinancePrivate`, `OpenClawLegalPrivate`, or `OpenClawMusicLawPrivate` roots.
- Runtime, log, state, bin, config, memory, exports, reset proof, bridge, vault, and generated-report folders before dependency mapping.
- `openclawssh`, Windows OpenSSH Server, SSH keys, service settings, user profiles, or permissions.
- `.private` contents, secrets, private legal/client files, tax files, CPA files, finance ledgers, or live vault contents.

These are active-dependency or private-data candidates until proven otherwise.

## 12. Future Folder Structure Candidate

A future structure may separate concerns like this, pending triage and explicit approval:

- `/home/openclaw`: canonical repo, docs, planning, tracked source, and safe fixtures.
- Windows `C:\OpenClawRuntime`: candidate runtime/log/state/config home only if dependency mapping proves the need.
- Windows `C:\OpenClawFinancePrivate`: candidate raw finance, tax, CPA, ledger, and CPA-exchange private root.
- Windows `C:\OpenClawLegalPrivate`: legal-private root, likely preserving the current active root after contract review.
- Windows `C:\OpenClawMusicLawPrivate`: candidate music-law and publishing private root if Windows-side parity is needed.
- Windows `C:\OpenClawShared`: generated/shared reports only after raw private material is removed and a generated/shared contract exists.
- Mac `OpenClawFinancePrivate`: Mac finance-private root.
- Mac `OpenClawLegalPrivate`: Mac legal-private root.
- Mac `OpenClawMusicLawPrivate`: Mac music-law/publishing private root.

This is a candidate target vocabulary, not a move manifest. Existing runtime/log/state/bin/config paths must be treated as active-dependency candidates until mapped.

## 13. Final Calibration Gate

Before any systems-engineering run-through, cleanup, build activation, Harness implementation, root migration, service activation, or agentic build loop, the operator must confirm that Command Atlas remains the top layer, Operator Harness remains a lane/view under it, root/data-boundary triage is current, active-dependency mapping is current, private roots are excluded from source sets and agent browsing unless explicitly approved, and the next action is bounded, reversible, and accepted.

## 14. What This Does Not Authorize

This artifact does not authorize:

- Operator Harness implementation work;
- app, backend, schema, fixture, ingestion, provider, model, bridge, service, launcher, or sync changes;
- broad Windows root cleanup;
- creating runtime folders;
- moving, deleting, renaming, merging, deduplicating, archiving, or cleaning files;
- changing users, services, permissions, SSH settings, or credentials;
- relying on or disabling `openclawssh`;
- inspecting private roots or `.private` contents;
- adding private Windows or Mac roots to source sets;
- treating `C:\OpenClawShared` as safe shared storage;
- treating `C:\OpenClaw` as canonical;
- treating local model benchmark docs as production routing authority;
- sending external communications or automating relationship decisions;
- installing Claude Code, Claude GitHub Actions, SDKs, runners, dependencies, or GitHub Actions workflows;
- allowing GitHub issues, PRs, comments, checks, or CI to become hidden execution authority;
- committing changes.

It only records the current system-program map and the corrected sequencing boundary.

## 15. Next Safe Action

Exact next safe action: create a docs-only Windows root triage and dependency-map plan that classifies subtrees by path/name and known references only, without inspecting private contents or moving anything.

That plan should distinguish active runtime/config/log/state/bin candidates, private source roots, generated/shared report candidates, legal-private roots, finance/CPA roots, music-law/publishing roots, bridge/sync surfaces, and stale residue before Operator Harness implementation resumes.
