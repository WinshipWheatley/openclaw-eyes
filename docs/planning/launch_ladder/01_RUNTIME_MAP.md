# Runtime Map

Status: docs-only static map. This file does not inspect or claim live runtime state.

Freshness:

- Generated/reviewed: 2026-05-02
- Source commit at creation: `e06b7ae`
- Package commit: `TBD_AFTER_COMMIT`
- Source basis: modular readiness ledger, intent/control map, service-management freeze, MCP profile doc, model fallback policy, Hermes advisory contract.
- Stale when: service ownership docs, module readiness, MCP profiles, model policy, or Hermes advisory boundary changes.
- Refresh trigger: rerun before creating backend data models, app fixtures, or source-set generator specs.

## Runtime Shape

| Layer | Surfaces | Current claim | Evidence |
| --- | --- | --- | --- |
| Runtime law | `OPENCLAW_RUNTIME.md`, `USER.md`, `CORE_ARCHITECTURE_PRINCIPLES.md` | Canonical behavior and architecture guardrails. | Runtime law and architecture principles. |
| Readiness/control docs | Modular readiness ledger, intent/control map, service freeze, model fallback policy, MCP profiles. | Static control maps and policy contracts, not live-state proof. | `docs/planning/OPENCLAW_MODULAR_READINESS_LEDGER.md`, `docs/operations/*`. |
| Agents/modules | Chief, Cassandra, Guardian, Hermes, Google broker, Legal/local discovery, expert escalation, dashboard/reporting, source-set workflow. | Mixed readiness; see modular ledger for status and authority. | Modular ledger and validation map. |
| Service/process surfaces | systemd-owned units, legacy/manual processes, deprecated/frozen controls. | Static service-freeze closure only; no live inspection in this package. | `docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md`. |
| External/advisory surfaces | ChatGPT Projects, Codex Desktop, Gemini, Hermes advisory, expert escalation. | Proposal/advisory only unless separately approved and sanitized. | Model fallback policy, Hermes advisory packet contract, expert lane contracts. |
| Future clients | macOS/iOS app, other operator clients. | Planned read-only clients first. | This Launch Ladder package and north-star note. |

## Module Map

Use the modular readiness ledger as the source for purpose, status, authority, data allowed, proof, dependencies, next safe slice, and portability notes.

This runtime map adds console grouping:

- Control core: runtime law, architecture principles, validation map, service-control SE kernel.
- Operator assistants: Cassandra, Chief, Guardian.
- Advisory consultants: Hermes advisory, expert escalation, external review packets.
- Data/integration brokers: Google/Gmail/Calendar broker, MCP progressive discovery, local model privacy boundary.
- Product lanes: Legal/local discovery, future company advisory assistant, creative/business assistant.
- Reporting/source-set lanes: dashboard/operator reporting, ChatGPT Project ingest workflow, Mac mirror workflow.

## Atlas Runtime Scope

In the long-range Multi-OpenClaw Command Atlas, the runtime map becomes one zoom layer in a larger multi-deployment map. It must support personal OpenClaw and future client/company deployments without merging their data, authority, readiness, or evidence.

The atlas should preserve these separations:

| Scope | Meaning | Required answer |
| --- | --- | --- |
| All builds / deployments | Cross-deployment world view. | Which builds exist, what each is for, and which ones are ready, stale, blocked, frozen, or active. |
| One build / deployment | One OpenClaw-style system. | Its North Star, modules, boundaries, readiness, blockers, evidence, and next safe Launch Ladder. |
| Departments | Functional areas inside a deployment. | What the department can do, what is blocked, and which Launch Ladders move it. |
| Agents / systems / subsystems / modules | Concrete components. | Capability, authority, readiness, evidence, stale conditions, and withheld surfaces. |
| Launch goals through evidence | Work execution view. | Launch goal, ladder, step, evidence artifact, docs/code/prompts/validation, and next safe action. |

This scope is still docs/spec only in v1. No live runtime inspection, service control, private-data access, provider/model call, generated ingest folder, or app code is created here.

## Static Service View

The service freeze names systemd-owned services and legacy/manual-owned processes, but explicitly says it does not prove live service state, select new owners, run audits, reconcile installed state, or authorize service operations.

For the Launch Ladder console, service status should start as:

| Field | First value |
| --- | --- |
| `service_source` | `docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md` |
| `service_truth_level` | `static_contract` |
| `live_state_checked` | `false` |
| `mutation_allowed` | `false` |
| `next_safe_slice` | read-only live-state verification plan, not execution |

## Runtime Map Unknowns

- Live service health is unknown from this package.
- Installed local model availability after 2026-04-28 is unknown unless checked in a separate approved lane.
- Hermes runtime state is intentionally withheld.
- Gmail bodies, private logs, vaults, Legal/private matter data, and installed units are intentionally withheld.

## Do Not Do Yet

- Do not run `systemctl`, installers, launchers, service audits, model/provider calls, Hermes runtime, Gmail/Telegram actions, logs, vaults, or private-data checks from this map.
- Do not use this map to infer installed service health.
- Do not let future app clients become alternate runtime owners.
