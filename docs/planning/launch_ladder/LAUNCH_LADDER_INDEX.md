# OpenClaw Launch Ladder Index

Status: docs-only planning/spec index. This package does not authorize runtime, service, installer, launcher, scheduler, provider/model, Gmail, Telegram, Hermes runtime, `.mcp.json`, secret, vault, private-log, LegalPrivate, Gmail body, CPA, Music Law, Publishing, private matter, or installed-unit changes.

Freshness:

- Generated/reviewed: 2026-05-02
- Source commit at creation: `e06b7ae`
- Package commit: `TBD_AFTER_COMMIT`
- Source basis: runtime law, north-star note, modular readiness ledger, operational control maps, Hermes advisory contract, validation map, existing audit/build source-set scripts, and `.gitignore` allowlist model.
- Stale when: any source-basis file changes, any route gains or loses authority, any validation map entry changes, any generated source set is refreshed, or the package is committed under a different hash without updating freshness.
- Refresh trigger: rerun a docs-only Launch Ladder review before using this package to drive app/backend/source-set implementation.

## Purpose

This folder is the operator-facing Launch Ladder planning/spec package for OpenClaw. It translates existing canonical control sources into a console-oriented map of runtime shape, module readiness, goals, launch routes, evidence, freshness, workspaces, authority, productization profiles, and next implementation order.

The upstream readiness source is `docs/planning/OPENCLAW_MODULAR_READINESS_LEDGER.md`. This package must not drift into a second module-readiness truth table. It should reference the ledger, then add launch and routing semantics around it.

The long-range product horizon is the Multi-OpenClaw Command Atlas: a zoomable operator map across Winship's personal OpenClaw builds and future client/company OpenClaw deployments. This v1 Launch Ladder package is a small first proof of that atlas, not the whole atlas. It proves the first operator-facing unit of work, freshness model, evidence model, and authority boundary before any app, generated source set, runtime mutation, service control, private data access, or provider/model call exists.

The atlas should eventually let the operator move from all builds and deployments to one build, departments, agents/systems/subsystems/modules, launch goals, Launch Ladders, steps, evidence artifacts, and exact docs/code/prompts/validation. At every level it should answer: what is this, what can it do, what is its North Star, what is its readiness, what is blocked, what evidence proves this, and what is the next safe Launch Ladder.

## Canonical Files

| File | Role |
| --- | --- |
| `00_NORTH_STAR.md` | Stable product and operator north star for the Launch Ladder console. |
| `01_RUNTIME_MAP.md` | Static map of agents, systems, subsystems, and module surfaces. |
| `02_CAPABILITY_AUTHORITY_AND_READINESS.md` | Capability, authority, and readiness view derived from the modular ledger. |
| `03_GOAL_HORIZONS.md` | Short, medium, and long horizon planning without promoting plans into authority. |
| `04_LAUNCH_LADDER_MODEL.md` | Launch Ladder stages, route compression, compact buttons, parallel bundles, and view modes. |
| `05_EVIDENCE_AND_FRESHNESS.md` | Evidence model, freshness fields, stale conditions, and repo-side operator trail shape. |
| `06_ROUTING_AND_WORKSPACES.md` | Exact routing map across PC/WSL, Mac, Codex Desktop, ChatGPT Projects, Gemini/Hermes advisory, and future clients. |
| `07_SECURITY_AND_AUTHORITY.md` | Security and authority rules for launch routing and console behavior. |
| `08_SOURCE_SET_REFRESH_SYSTEM.md` | Future ChatGPT Project source-set workflow and 24-file discipline. |
| `09_MAC_IOS_APP_BUILD_BRIEF.md` | Read-only first macOS/iOS app build brief and data-contract needs. |
| `10_PRODUCTIZATION_PROFILES.md` | Personal OpenClaw and future client/company deployment profiles. |
| `11_NEXT_IMPLEMENTATION_SEQUENCE.md` | Smallest safe sequence after this docs package. |
| `CHAT_STAY_UP_TO_DATE.md` | Adjacent ChatGPT Project delta bridge template; not part of any 24-file source-set folder. |

## Non-Authority Rule

This package can name a route, status, source set, or next slice. It cannot make that route authorized. Launch-ready is a proof and preparedness state; launch-authorized requires the applicable human, Chief, Guardian, broker, or lane approval path.

In the future atlas, the map remains a window, router, and evidence browser. Repo docs, tests, runtime checks, commits, approval receipts, and generated artifacts are sources. The operator remains authority.

## Source Trail

Key current source evidence includes:

- `OPENCLAW_RUNTIME.md` and `USER.md` for operator control and workflow expectations.
- `CORE_ARCHITECTURE_PRINCIPLES.md` for single-source, minimal-infrastructure, and audit-before-adding rules.
- `docs/planning/OPENCLAW_PERSONAL_AI_SUBSTRATE_NORTH_STAR.md` for the governed substrate direction.
- `docs/planning/OPENCLAW_MODULAR_READINESS_LEDGER.md` for module readiness, authority, data boundaries, and productization posture.
- `docs/operations/OPENCLAW_INTENT_AND_CONTROL_MAP.md` for pending decisions, action authority conflicts, and progressive discovery.
- `docs/operations/OPENCLAW_MODEL_FALLBACK_POLICY.md` for no silent external fallback and benchmark limits.
- `docs/operations/MCP_PROGRESSIVE_DISCOVERY_PROFILES.md` for default docs-only exposure and unlock gates.
- `docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md` for static service/process ownership and forbidden controls.
- `docs/operations/HERMES_ADVISORY_PACKET_CONTRACT.md` and `docs/planning/HERMES_FIRST_ADVISORY_TRIAL_PLAN.md` for non-canonical advisory boundaries.
- `docs/testing/VALIDATION_MAP.md` for proof selection.
- `mac_eyes/Launchers/sync_openclaw_audit_build_to_mac.sh` and `mac_eyes/Launchers/refresh_openclaw_audit_build_ingest.sh` for existing source-set/mirror discipline.
