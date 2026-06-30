# GEMINI AUDIT SPEC — Canonical Naming, Pass 1 of 3: HIGH LEVEL (the landscape)

Dispatched by: Opus (program orchestrator)
Date: 2026-06-30
Audit ID: NAMING-AUDIT-1-HIGH
Write result to: `Operator/from-gemini/NAMING-AUDIT-1-HIGH-RESULT.md`

## Role + hard rules
You are AGY-PC-Gemini, READ-ONLY (see `Operator/PROMPT-FOR-AGY-PC-GEMINI-WORKER.md`).
**MAP + RECOMMEND ONLY — do NOT rename, move, edit, or mutate anything.** No secrets / .chief.env /
tokens, no Legal Discovery, no deep private-media scans. Separate OBSERVED facts from inference.

## Why
The operator is hitting naming confusion: he thought there were ~4 repos (there are more), "main"
turned out not to be the live branch, and the SQLite ledger now drives packet generators with names
that risk confusing him, his local agents, and CLIs. We want ONE canonical naming picture, built in
3 passes (this is HIGH level; mid + detail follow). Renames are a LATER, surgical, operator-gated
effort — this map informs WHAT is worth renaming, not a rename itself.

## Ground truth + side-benefit (applies to ALL 3 naming passes)
- **Ground truth is the REAL repos — filesystem + git — NOT the SQLite ledger/system_catalog.** The
  ledger is a DERIVED inventory and may be stale or incomplete. Use the actual files/dirs/git as the
  source of truth; treat the ledger/catalog as a CLAIM to VERIFY, not the answer. Wherever the
  ledger/system_catalog disagrees with what's actually on disk, FLAG the divergence explicitly.
- **Side-benefit capture (record as you dig, in a separate section of your result):**
  (a) **Ledger gaps** — anything real on the filesystem/repos that the ledger / system_catalog does
      NOT know about (files, components, stores, scripts that "should be known"). List them so we can
      feed them back into the ledger after naming.
  (b) **Detailed repo/component map** — build toward a reusable map (path → component → purpose →
      proposed canonical name) that can later be ingested into the ledger WITH the new naming
      conventions. (High level here; pass 3 makes it detailed.)

## Pass 1 scope — the macro landscape only (don't go into tables/columns/functions yet)
1. **Repos + worktrees — definitive enumeration.** How many real git repos/worktrees exist on this
   box and what each is. Use `git worktree list`, `git -C <path> rev-parse --show-toplevel`, and look
   under `/home/openclaw` (main repo), `/home/openclaw/sidecars/hermes` (its OWN repo + .venv),
   `/home/openclaw/worktrees/`, `agy-codex/*`, `/home/openclaw/.gemini/`, and any nested `.git`. For
   each: path, its repo identity, purpose, and is-it-live-or-vendored-or-throwaway.
2. **Branch reality — resolve "main isn't main".** Map the key branches: `main` (release, currently
   ~325 commits behind), `codex/stress-fixes` (the LIVE integration branch the running services use),
   `promote/main-*` (staged promotions), the `codex/*` and `agy-codex/*` families. State plainly:
   which branch is "the live one", which is "release", and the mental-model trap to document.
3. **Top systems/components + canonical names.** The macro pieces and what they're called: the fleet
   (6 agents — maestro, cassandra/Clara Reid, chief, guardian, niles, hermes), the robust SQLite
   ledger, the polish-loop / factory ("Atelier"?), the read-model system, the context-packet system,
   the control plane, the self-healing/Hermes loops, the operator-intake system. Flag where ONE thing
   has MULTIPLE names or aliases (e.g. factory vs Atelier, Graphify/graphiffy, any Maestro/Sara slip,
   producer/niles).

## Output (in the result file)
- **Repo/worktree table:** path | identity | purpose | live/vendored/throwaway.
- **Branch table:** branch | role (live/release/staged/feature) | one-line.
- **Top-entity glossary:** canonical name | aliases seen | one-line purpose.
- **Ranked confusions:** the macro naming traps, ordered by how much each would confuse the operator
  / a local agent / a CLI — with the observed evidence for each.
- Keep it HIGH level; do not recommend specific renames yet (that's pass 3). Note anything that
  surprised you for the operator to know.
