# GEMINI AUDIT SPEC — Canonical Naming, Pass 3 of 3: DETAIL LEVEL + rename plan

Dispatched by: Opus (program orchestrator)
Date: 2026-06-30
Audit ID: NAMING-AUDIT-3-DETAIL
Write result to: `Operator/from-gemini/NAMING-AUDIT-3-DETAIL-RESULT.md`

## Role + hard rules
AGY-PC-Gemini, READ-ONLY (see `Operator/PROMPT-FOR-AGY-PC-GEMINI-WORKER.md`). MAP + RECOMMEND ONLY —
**do NOT perform any rename or mutation.** No secrets, no Legal Discovery. Separate OBSERVED from inference.

## Prereq
**Read `Operator/from-gemini/NAMING-AUDIT-2-MID-RESULT.md` FIRST** (and the HIGH result). Build on them.

## Ground truth + side-benefit (applies to ALL 3 naming passes)
- **Ground truth is the REAL repos — filesystem + git — NOT the SQLite ledger/system_catalog.** Verify
  granular names against the actual source files/schema; flag where the ledger/catalog's names diverge
  from what's on disk.
- **Side-benefit capture (separate section):** (a) **Ledger gaps** — real granular items (tables,
  scripts, env vars, agent-ids) the ledger/system_catalog does NOT track but should; (b) finalize the
  **detailed repo/component map** (path → component → purpose → proposed canonical name) so it can be
  ingested into the ledger WITH the adopted naming standard — i.e. after we converge naming, the
  ledger gets both the new conventions AND this fuller map.

## Pass 3 scope — the granular names agents + CLIs actually trip on
1. **Ledger schema names.** Representative `knowledge_*` + operational TABLE names and notable COLUMN
   names in the ledger + the packet-driving stores. Flag inconsistent prefixes/casing/abbreviations.
2. **Agent-facing identifiers (high payoff — these confuse agents directly).** From
   `operator_universal_intake.py` (AGENT_LANE_REGISTRY_V0, AGENT_EXECUTION_MODE_REGISTRY_V0,
   SUPPORTED_SURFACES, AGENT_LANE_ALIASES, WATCH_DESK_LANES, SUPPORTED_ACTION_TYPES) and
   `agent_lane_registry.py` / `operator_skill_registry.py`: the agent IDs, lane names, surface names,
   action_types, skill_ids. Flag drift like `watch desk` vs `watch_desk` vs `watchdesk`, `niles` vs
   `producer`, `cassandra_ar`/`cassandra_finance`/`cassandra_business` for one owner, mixed
   separators/casing for the same concept.
3. **Env vars + CLI/script names.** Notable env var names (e.g. the `OPENCLAW_*` family, the
   front-door-profile vars set in the openclaw-request-response.service unit) and script/CLI entry
   names — flag where the name doesn't match what it controls/does.
4. **Cross-file concept drift.** Where the SAME concept is named differently across files (the kind of
   thing that makes a CLI or an agent reference the wrong name).

## Output (in the result file)
- **Detailed inconsistency list:** name | where | the drift | who it confuses (operator / agent / CLI).
- **PRIORITIZED rename recommendations** — for each, tag the RISK:
  - `cosmetic-safe` — a local rename with no ingest/packet impact.
  - `BREAKS-INGEST-OR-PACKETS` — names that flow into the ledger ingest paths or packet generation;
    renaming these requires running BOTH ledger ingest paths + verifying the LIVE ledger (high risk).
    **Recommend only — flag loudly, do not rename.**
- A proposed **canonical naming standard** (the single scheme to converge on) so future builds stop
  adding drift.
- Order recommendations by confusion-reduced ÷ risk, so the operator can pick the surgical wins first
  (prune, don't pile — we will NOT rename everything, only what genuinely confuses).
