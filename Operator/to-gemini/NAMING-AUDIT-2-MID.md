# GEMINI AUDIT SPEC — Canonical Naming, Pass 2 of 3: MID LEVEL (subsystems)

Dispatched by: Opus (program orchestrator)
Date: 2026-06-30
Audit ID: NAMING-AUDIT-2-MID
Write result to: `Operator/from-gemini/NAMING-AUDIT-2-MID-RESULT.md`

## Role + hard rules
AGY-PC-Gemini, READ-ONLY (see `Operator/PROMPT-FOR-AGY-PC-GEMINI-WORKER.md`). MAP + RECOMMEND ONLY —
no renames/mutation, no secrets, no Legal Discovery. Separate OBSERVED from inference.

## Prereq
**Read `Operator/from-gemini/NAMING-AUDIT-1-HIGH-RESULT.md` FIRST** (the high-level map). Build on it;
don't repeat it. If it's missing, do pass 1's landscape briefly first, then proceed.

## Why (the operator's specific worry)
"SQLite is going to drive packet generators with all sorts of stuff that might confuse me, my local
agents, and CLIs." This pass maps the SUBSYSTEM names so we can see exactly where that confusion lives.

## Pass 2 scope — subsystem inventory + naming
1. **SQLite stores.** Inventory the real `.sqlite`/`.sqlite3` stores and what each DRIVES. Anchor on:
   the robust ledger `/home/openclaw/.openclaw/business_ops/ledger.sqlite` (and its `knowledge_*`
   folded tables); the live operational stores (event router, proof-to-response, governance registry,
   agentic-chain, system_catalog, system_knowledge_registry); `polish_loop` control_plane.sqlite3; the
   gig-to-cash store (`/home/openclaw/state/gig_to_cash/gig_to_cash.sqlite3`). For each: path, name,
   what it feeds, and whether its NAME makes its role obvious. Flag overlapping/confusing names
   (multiple "registry"/"catalog"/"knowledge"/"store" things).
2. **Read models.** `generated/read_models/*.json` — the naming pattern, what each represents, and
   where a name is cryptic or collides with another concept.
3. **Packet generators.** `*_context_packet.py` / `*_fact_packet.py` + `context_packet_builder_registry.py`
   + `context_source.py` (`build_ledger_context_packet`). How packet builders are named, how they map
   to agents/read-models/ledger, and where the SQLite→packet naming chain would confuse an
   agent or a CLI (the operator's core worry).
4. **Services.** The `systemd --user` units (listeners, workers, schedulers, kokoro-voice,
   hermes-gateway). Unit name → what it runs → the agent/subsystem it serves. Flag mismatches (e.g. a
   unit named for one thing that runs another, like producer_listener serving "niles").

## Output (in the result file)
- Per category (stores / read-models / packet-generators / services): a table of
  **name | what it is / drives | clear-or-confusing | note**.
- **Flagged confusions:** every place a name is cryptic, collides, or mismatches its role, with evidence.
- **Recommended naming CONVENTION per category** (a consistent scheme — prefixes, casing, the
  store→read-model→packet→agent chain) — as a recommendation only, no renames performed.
- Carry forward anything pass 3 (detailed: tables/columns/env/CLI/agent-ids) should zoom into.
