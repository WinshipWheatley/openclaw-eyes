# Launch Ladder North Star

Status: docs-only planning/spec. This file does not authorize runtime or private-data changes.

Freshness:

- Generated/reviewed: 2026-05-02
- Source commit at creation: `e06b7ae`
- Package commit: `TBD_AFTER_COMMIT`
- Source basis: `OPENCLAW_RUNTIME.md`, `USER.md`, `CORE_ARCHITECTURE_PRINCIPLES.md`, `docs/planning/OPENCLAW_PERSONAL_AI_SUBSTRATE_NORTH_STAR.md`, `docs/planning/OPENCLAW_MODULAR_READINESS_LEDGER.md`.
- Stale when: the personal substrate north star, modular readiness ledger, runtime law, or operator authority model changes.
- Refresh trigger: update before app/backend/source-set generation or any launch route that claims readiness.

## Purpose

Launch Ladder is the operator-facing control-console model for OpenClaw. It should let Winship see what exists, what it can do, what it may do, what is proven, what is planned, what is stale, and exactly which route can move a recommendation toward launch without blurring authority.

The stable product direction is one governed substrate with many clients. VS Code, PC/WSL, Mac, Codex Desktop, ChatGPT Projects, Gemini/Hermes advisory, and future macOS/iOS/other clients should be windows into the same evidence and authority model, not separate control planes.

The long-range product horizon is the Multi-OpenClaw Command Atlas: a zoomable operator map across Winship's personal OpenClaw builds and future client/company OpenClaw deployments. The atlas should let the operator manage, build, debug, harden, polish, and extend many OpenClaw-style systems while preserving operator authority and reducing mental load.

This v1 Launch Ladder spec is a small first proof of that atlas. It defines the first safe unit of operator-facing work, not the full world map, app, backend, source-set generator, or multi-deployment registry.

## Atlas Zoom Levels

The future atlas should support these zoom levels:

| Zoom level | Operator meaning |
| --- | --- |
| All builds / deployments | World view across Winship's personal OpenClaw builds and future client/company deployments. |
| One build / deployment | Continent view for one system, client, workspace, or deployment boundary. |
| Departments | Country/state/county view for functional areas, product lanes, teams, or operational domains. |
| Agents / systems / subsystems / modules | System map for Chief, Cassandra, Guardian, Hermes, brokers, source-set workflow, Legal/local discovery, and future customer modules. |
| Launch goals | Outcome-level view of what the operator is trying to make true. |
| Launch Ladders | Operator-facing unit of work that replaces vague lanes. |
| Steps | Exact bounded actions inside one Launch Ladder. |
| Evidence artifacts | Proof objects such as docs, tests, commits, approvals, source sets, checks, and generated artifacts. |
| Docs/code/prompts/validation | Street-level repo evidence and execution-proof references. |

Every level should answer:

- What is this?
- What can it do?
- What is its North Star?
- What is its readiness?
- What is blocked?
- What evidence proves this?
- What is the next safe Launch Ladder?

## Atlas Authority Boundary

The atlas is not authority. Repo docs, tests, runtime checks, approval receipts, commits, and generated artifacts are sources. Dashboard, console, app, and atlas views are windows, routers, and evidence browsers. The operator remains authority, and Launch-ready remains separate from launch-authorized.

## North Star Commitments

- The repo remains the canonical source for this package.
- The modular readiness ledger remains the module-readiness source.
- Derived source sets, mirrors, app views, advisory memos, and generated folders are non-canonical until promoted by an explicit human or existing control path.
- The North Star remains visible and stable even when a compact route defers work.
- Deferred work is preserved, not discarded. A compressed route must name what it defers, where that deferred work lives, and when it must return.
- Launch-ready is not launch-authorized.

## Proposed Console Sections

1. Runtime: agents, systems, subsystems, and modules.
2. Capacity/Ability: what each module can currently do for Winship.
3. North Star horizons: one hour to end of day, one to two weeks, and one to six months.
4. Launch Ladder: staged path from recommendation to launch-ready and launch-authorized.
5. Evidence/Proof: every claim cites docs, tests, commits, artifacts, or checks.
6. Freshness/Staleness: every map, route, source set, and status names timestamp, commit, source basis, stale conditions, and refresh trigger.
7. Routing/Workspaces: exact tool, machine, workspace, source set, output path, validation, and stop condition.
8. Security/Authority: what each module may do, may not do, and what requires approval.
9. Productization/Deployment Profiles: personal OpenClaw plus future client/company deployments.
10. Multi-OpenClaw Command Atlas: long-range zoomable map across personal and future client/company builds.

## Console Design Bias

The console should be quiet, dense, and operator-focused. It should show readiness, route choices, evidence, freshness, and authority without becoming a service controller in the first version.

Near-term console output can be Markdown or JSON artifacts. A macOS/iOS app can come later, but its first version should read artifacts and source sets only.

## Evidence Anchors

- The personal substrate north star states that OpenClaw is a local-first owned substrate, not a cloud LLM product with files attached.
- The runtime law requires inspect -> plan -> act -> verify and preserves human control for destructive, external, credential-bearing, or scope-expanding actions.
- The modular readiness ledger distinguishes landed, static, dry-run, bounded, planned, and aspirational module states.
- The MCP profile document requires bounded first packets and withheld-surface reveal artifacts before broad access.

## Do Not Do Yet

- Do not build service control into the first console.
- Do not make the console a canonical memory or approval system.
- Do not make app routes imply provider/model access.
- Do not hide deferred work when using route compression.
- Do not treat the v1 Launch Ladder proof as the full Multi-OpenClaw Command Atlas.
- Do not create generated ingest folders, app code, runtime mutations, service controls, private-data routes, or provider/model calls from this package.
- Do not claim broad autonomy, unified memory, trusted local model quality, or live service health from this package.
