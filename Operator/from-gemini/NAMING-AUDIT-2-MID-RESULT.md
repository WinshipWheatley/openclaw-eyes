# GEMINI AUDIT RESULT — Canonical Naming, Pass 2 of 3: MID LEVEL (Subsystems)

**Audit ID:** NAMING-AUDIT-2-MID
**Date:** 2026-06-30

## 1. SQLite Stores (Truth vs Derived)

| Store Name / Path | What it Drives | Clear or Confusing | Note |
|---|---|---|---|
| `.openclaw/business_ops/ledger.sqlite` | System catalog, repos, skills, and orchestrator state (Primary Truth). | **Confusing** | Historically `system_catalog.sqlite3`. Now it's `ledger.sqlite`, but read-models still export under the `system_catalog` name. |
| `polish_loop/control_plane.sqlite3` | Polish Loop factory execution, builder directives, and task closure. | **Confusing** | "Control plane" implies global orchestration/system-wide scope, but this is restricted entirely to the Polish Loop / Atelier isolated environment. |
| `state/gig_to_cash/gig_to_cash.sqlite3`| Expected gig and receivables. Drives Chief billing limits. | **Clear** | Does exactly what it says. |
| `generated/system_knowledge/*.sqlite` | Dozens of exported states (e.g., `openclaw_system_knowledge_registry.sqlite`). Drives fast packet generation. | **Confusing** | These are derived *read-models*, not authoritative stores. The `.sqlite` extension inside a `system_knowledge` directory mimics primary truth data, causing collision risk. |

## 2. Read Models

| Pattern / Location | What it Represents | Clear or Confusing | Note |
|---|---|---|---|
| `generated/read_models/*.json` | Flattened views of truth stores for LLM context injection (e.g., `operator_mission_priority_helm_declutter.json`, `sync_health.json`). | **Confusing** | The names are verbose and lack namespace prefixes indicating the owning subsystem/agent (e.g., `sync_health.json` is too generic). Having both JSON "read models" and SQLite "system knowledge" read-models fragments the concept. |

## 3. Packet Generators

| Generator Name | What it Drives | Clear or Confusing | Note |
|---|---|---|---|
| `maestro_context_packet.py` | The universal shared facts packet injected into **ALL** agents' contexts. | **Confusing (CRITICAL)** | Because it is named "maestro", injecting this into Niles or Guardian causes "Maestro persona bleed" where other agents think they are Maestro or refer to Maestro's specific rules. |
| `cassandra_clara_fact_packet.py` | Generates context/facts specifically for Cassandra (`openclaw-eyes` sidecar). | **Confusing** | Contains a double persona alias (Cassandra and Clara) in the filename itself. |
| `guardian_context_packet.py`, `hermes_context_packet.py` | Agent-specific context packets. | **Clear** | Appropriately scoped and named. |

## 4. Services (systemd)

| Unit Name | What it Runs | Clear or Confusing | Note |
|---|---|---|---|
| `niles-listener.service` | Niles listener. The description explicitly states "Producer / music-creative lane". | **Confusing** | The name is Niles, but the unit description and role invoke the "Producer" alias. |
| `chief-guardian-listener.service`| Guardian approval listener. | **Confusing** | Prefixing Guardian's service with `chief-` implies Chief owns/runs it, blurring the rigid boundary between the Chief and Guardian roles. |
| `openclaw-gateway.service` vs `hermes-gateway.service` | Both are active services running simultaneously. | **Confusing** | Overlapping generic "gateway" terms without clear domain boundaries in the name. |

---

## 5. Side-Benefit Capture

### Ledger Gaps (Observed on disk but out of sync with mental model)
- **Read-Model Proliferation**: Derived data is aggressively fragmenting into multiple formats (JSON vs SQLite dumps) and distinct output locations (`generated/read_models/` vs `generated/system_knowledge/`). The true `ledger.sqlite` is singular, but its shadows are exploding and adopting authoritative-sounding names.
- **Legacy `system_catalog.sqlite3`**: While the true file was archived to `.openclaw/archive/`, the name survives as a cultural artifact in documentation, filenames, and variable names, creating a phantom ledger.

### Recommended Naming CONVENTION (per category)
*(Recommendation only, no renames performed)*
- **Stores (Primary Truth):** `[Domain]Ledger.sqlite` (e.g., `BusinessOpsLedger.sqlite`, `PolishLoopLedger.sqlite`).
- **Read-Models (Derived):** `[Subsystem][Entity]ReadModel.[json/sqlite]` (e.g., `MaestroMissionPriorityReadModel.json`). Unify directory storage to a single `generated/read_models/`.
- **Packet Generators:** The globally shared packet MUST be renamed to `UniversalContextPacket.py` or `SharedFactsPacket.py` to kill Maestro persona bleed. Agent-specific packets remain `[Agent]ContextPacket.py`.
- **Services:** `openclaw-[agent]-[role].service` (e.g., `openclaw-niles-listener.service`, `openclaw-guardian-approval.service`).
