# GEMINI AUDIT RESULT — Canonical Naming, Pass 1 of 3: HIGH LEVEL

**Audit ID:** NAMING-AUDIT-1-HIGH
**Date:** 2026-06-30

## 1. Repo + Worktree Enumeration (Definitive Ground Truth)

| Path | Repo Identity | Purpose | Status |
|---|---|---|---|
| `/home/openclaw` | `openclaw` | Main orchestration and systems codebase | **LIVE** |
| `/home/openclaw/sidecars/hermes` | `openclaw-hermes` | Hermes self-healing sidecar agent | **Vendored / Live** |
| `/home/openclaw/sidecars/gbrain_upstream` | `gbrain_upstream` | Upstream components / legacy brain | Vendored |
| `/home/openclaw/openclaw-builder` | `openclaw-builder` | Builder execution environment | Vendored |
| `/home/openclaw/.nemoclaw/source` | `nemoclaw` | Internal framework component | Vendored |
| `/home/openclaw/generated/external_sources/openclaw-eyes` | `openclaw-eyes` | External corpus/knowledge map | Vendored |
| `/home/openclaw/.openclaw/agents/*` | `chief`, `health-sentinel`, `strategy-sentinel`, `timeline-sentinel` | Dedicated state repos for agents | **Live State** |
| `/home/openclaw/worktrees/*` | `openclaw` clones | ~120 isolated worktrees for features | Throwaway / Isolated |
| `/home/openclaw/.claude/worktrees/*` | `openclaw` clones | Agent-driven worktrees | Throwaway / Isolated |

## 2. Branch Reality

| Branch | Role | One-Line Summary |
|---|---|---|
| `codex/stress-fixes` | **LIVE (Production)** | The true active integration branch running the live services. |
| `main` | **RELEASE (Stale)** | ~325 commits behind live. |
| `promote/main-*` | **Staged** | Batches grouped for upcoming promotion PRs to `main`. |
| `codex/*` | **Feature / Fix** | Human-driven or legacy feature branches (often abandoned/merged). |
| `agy-codex/*` / `agy-sonnet/*` | **Agent Feature** | Agent-driven isolated work branches. |

**Mental-Model Trap:** The operator expects `main` to be the live branch, but it is heavily stale. Any automated edits or queries targeting `main` will miss ~3 weeks of production reality. `codex/stress-fixes` is the de facto `main`.

## 3. Top Systems + Canonical Names

| Canonical Name | Aliases Seen | Purpose |
|---|---|---|
| **Agents Fleet** | Maestro (Sara), Cassandra (Clara Reid), Chief, Guardian, Niles (Producer), Hermes | The 6 core autonomous operators with specific scopes and boundaries. |
| **Business Ops Ledger** | `ledger.sqlite`, previously `system_catalog.sqlite3` | The central SQLite registry of knowledge, skills, and operations. |
| **Polish Loop** | Factory, Atelier, Control Plane (`control_plane.sqlite3`) | The closed-loop executor for generating and building code/tasks. |
| **Generated Read-Models** | `system_knowledge/*.sqlite`, JSON dumps | Flattened, queryable exports of ledger state for agents. |
| **Context Packets** | `maestro_context_packet.py` | The standardized prompt injected into all agent contexts. |
| **Operator Intake** | `operator_universal_intake.py`, frontdoor | The unified receipt boundary for incoming operator directives. |

## 4. Ranked Confusions (Macro Naming Traps)

1. **`main` vs `codex/stress-fixes` (CRITICAL)**: The biggest trap. Operations targeting `main` operate on an obsolete system state.
2. **`system_catalog.sqlite3` vs `ledger.sqlite` (HIGH)**: The central catalog migrated to `.openclaw/business_ops/ledger.sqlite`, but `.sqlite3` legacy mentions still litter docs and scripts.
3. **Polish Loop vs Atelier vs Control Plane (HIGH)**: The directory is `polish_loop`, the DB is `control_plane.sqlite3`, and documentation often refers to "Atelier" or "factory". This tripartite naming confuses CLI tool matching.
4. **Agent Persona Bleed (MED)**: Niles is often referred to as "Producer" and Cassandra as "Clara Reid", confusing routing semantics.

## 5. Side-Benefit Capture

### Ledger Gaps (Observed on disk but not universally cataloged)
- **Active Ledger Location:** `.openclaw/business_ops/ledger.sqlite` is the true live ledger, leaving `system_catalog.sqlite3` in `archive/` as a historical artifact.
- **Proliferation of `*.sqlite` files:** Dozens of specialized sqlite files exist in `.openclaw/memory/`, `.openclaw/test_harness/`, and `generated/system_knowledge/` that may not be formally inventoried in the root ledger.

### Component Map (High Level)
- `/home/openclaw` → Orchestrator Core → `openclaw_orchestrator`
- `/home/openclaw/polish_loop` → Sub-executor Factory → `openclaw_atelier`
- `/home/openclaw/.openclaw/business_ops` → Production State → `openclaw_business_ledger`
- `/home/openclaw/sidecars/hermes` → Self-healing Supervisor → `openclaw_hermes`
