# Codex packet — ONE robust knowledge ledger (consolidate the SQLite catalog sprawl) 2026-06-29

**Owner:** Codex (build/migration). **Reviewer:** Opus + operator. **Branch:** `codex/stress-fixes`.
**Repo:** /home/openclaw. **HIGH-CARE migration — read all hard constraints before touching data.**

## The finding (audit done by Opus)
A scan of every SQLite DB (722 total; 41 are tool-cache noise = Gemini/Codex/Copilot, ignore) shows:
**THE ROBUST STORE ALREADY EXISTS** = `/home/openclaw/.openclaw/business_ops/ledger.sqlite`
(678MB, **272 tables**, written live today). It already holds the deep multi-repo knowledge:
`corpus_paths` (59,073), `corpus_path_labels` (587,472), `corpus_sensitivity_labels` (59,073),
`corpus_world_bindings`, `file_inventory` (3,326), `canonical_facts` (104, FTS), `corpus_atlas_runs`
(262), `repo_b_*` + `legacy_repo_intake_*` repo intakes, `agent_runtime_components` (48), agent lanes,
presence, telegram intake, receipts (`retrieval_receipts`, `side_effects`, `operator_explanations`,
`verification_evidence`).

The problem is SPRAWL AROUND it — separate, shallower, partly-stale satellites that duplicate slices
of the ledger instead of writing into it:
- `/home/openclaw/system_catalog.sqlite3` — 3 tables (scans/repos/skills), 134 repos (122 worktrees),
  1 skill. Shallow REPO-level index that does NOT write to the ledger. **Redundant** with the ledger's
  corpus_*/file_inventory/repo intake tables.
- `/home/openclaw/generated/system_knowledge/openclaw_system_knowledge_registry.sqlite` — 24
  system_components, 9 capabilities, agent_roles, authority_boundaries (the SEMANTIC layer), 2 wks stale.
- `/home/openclaw/generated/system_knowledge/{operator_controller_event_router,proof_to_response_runtime,
  sqlite_governance_registry,agentic_chain_inspector}.sqlite` — per-subsystem knowledge stores.
- `/mnt/e/openclaw/generated/read_models/openclaw_filesystem_atlas.sqlite` — another atlas.
- NOISE: `ledger.sqlite.bak.fin` (666MB backup), dozens of `.openclaw/tmp/pytest-*/ledger.sqlite`
  test copies, the 803MB tool caches.

Operator directive: "the multi-repo knowledge needs to be written into the robust system I built, and
there really just needs to be ONE — the real robust one." That one = `ledger.sqlite`.

## Goal
ONE robust knowledge store (the ledger) is the single source of truth for system/multi-repo knowledge.
Satellites either WRITE INTO the ledger or are retired (after their unique data is verified present).
Consumers (Hermes grounding, Map Room, agent context) read the ledger. Operational queues that are a
DIFFERENT concern (polish-loop control_plane build queue, finance/G2C append-only store) stay separate
— this is about KNOWLEDGE/CATALOG stores, not every sqlite.

## HARD CONSTRAINTS (non-destructive — do not lose data)
1. **Back up the ledger first** (copy `ledger.sqlite` to a dated archive) before ANY write to it.
2. **Additive then retire** — fold a satellite's UNIQUE data into the ledger, VERIFY it's queryable
   there, and only THEN retire the satellite (move to an archive dir, don't `rm`). Never delete a
   satellite before its data is confirmed in the ledger.
3. The ledger is **written live** (today's mtime) by existing ingest paths — do NOT break them. Reuse
   the existing ledger writers/schema; check `reference_canonical_ledger_ingest_paths` doctrine
   (`scripts/populate_real_ledger.py` + `scripts/ingest_canonical_docs.py`, both `--confirm`-gated) and
   the corpus-atlas ingest that already populates `corpus_*`. Prod-state writes are operator-gated — do
   NOT self-`--confirm`; propose the commands for the operator.
4. TDD any new ingest/reconciliation code.

## Tasks (in order)
1. **Reconcile, don't blind-merge.** For each satellite (system_catalog, knowledge_registry, the 4
   system_knowledge/*.sqlite, filesystem_atlas): diff its tables against the ledger. Report what is
   (a) already in the ledger (retire the satellite copy), (b) UNIQUE and worth folding in (write a
   ledger table + an ingest), (c) genuinely a separate operational concern (leave). Output the
   reconciliation as a table in the results file BEFORE migrating.
2. **Make multi-repo knowledge land in the ledger.** The `system_catalog` scan (134 repos, worktree-
   deduped to ~12 real) should be an ingest that writes a ledger table (or reconciles into the existing
   corpus_roots/repo intake tables), NOT a separate file. Worktree-dedup so a "what repos exist" query
   returns ~12, not 134.
3. **Refresh** the corpus/scan so the ledger's multi-repo knowledge is current; confirm freshness.
4. **Repoint EVERY packet generator at the ledger — this is the operator's core requirement.** Not
   just Hermes: the ledger is the single robust source, and *anything that builds a context/packet*
   must generate from it so every packet across the fleet carries the same robustness. Concretely:
   - **Agent brain packets** — `maestro_context_packet.py` (the per-agent context packet for
     Maestro/Cassandra/Chief/Niles/Guardian). NOTE: a `DEFAULT_SYSTEM_CATALOG_PATH` pointing at the
     shallow `system_catalog.sqlite3` was just added here — **repoint it at the LEDGER**, not the
     satellite, so agent packets draw from the robust store. Keep the existing budgeter/cap discipline
     (small, source-tagged, capped facts) — robustness of SOURCE, not packet bloat.
   - **Polish-loop build packets** — the context the builder receives (`polish_loop/` packet/context
     assembly, e.g. pc_context.md / worker_packet). Generate the builder's "what exists / where things
     live" context from the ledger so builds reason over the real system.
   - **Dankifier** (`packet_dankness_*`) — the packet-quality loop should ground/enrich against the
     ledger.
   - **Hermes grounding** — replace the hand-curated `sidecars/hermes_home/OPENCLAW_INVENTORY.md` (Opus
     stopgap) with a GENERATED inventory built FROM the ledger (a small exporter), so it stays current.
   Build a SINGLE shared ledger-backed packet-source helper that all of these call (DRY) rather than
   each re-implementing a query. Keep PII/legal exclusions intact (the ledger has sensitivity labels —
   `corpus_sensitivity_labels` — honor them; never surface legal/vault/secret bodies into a packet).
5. **Governance:** there is already a `sqlite_governance_registry.sqlite` — use/extend it to record the
   "one knowledge ledger" policy so new knowledge writes go to the ledger, not new sqlite files.
6. **Cleanup (separate, low-risk, operator-approved):** archive `ledger.sqlite.bak.fin`; delete the
   `.openclaw/tmp/pytest-*/ledger.sqlite` test copies; leave the tool caches (operator's call).

## THE "AUTOMATIC" GUARANTEE (operator's explicit condition — how we KNOW robustness reaches every packet)
"Automatic" is FALSE today and must be MADE true by construction + enforced by a test. Current state
(audited): five agent-context builders, three different sources, only ONE on the ledger:
- `cassandra_clara_fact_packet.py` → **already reads `business_ops_ledger`** — THE REFERENCE PATTERN, copy it.
- `maestro_context_packet.py` → flat read_models + the SHALLOW `system_catalog.sqlite3` + truth store (repoint).
- `cassandra_context_packet.py` → flat read_models JSON only (repoint).
- `hermes_context_packet.py` → flat read_models JSON only (repoint).
- `backend_knowledge_packet.py` → read-model kinds (repoint/confirm).
- polish-loop builder context assembly (confirm + repoint).

Make it real + provable:
1. **Build ONE shared `context_source` module** (ledger-backed; Clara's packet shows the pattern).
   It returns robust, source-tagged, capped, sensitivity-filtered facts FROM the ledger. (Clarify first
   whether the live read-models are PROJECTIONS of the ledger or independent — if projections, the
   source may read them; if independent, read the ledger directly. Either way the source-of-truth is
   the ledger and provenance must say so.)
2. **Refactor all the builders above to pull their facts from `context_source`** (DRY — they stop
   re-querying read_models/system_catalog themselves).
3. **THE GUARANTEE = a contract test** (`tests/test_context_packet_ledger_contract.py`): it discovers
   every `*_context_packet.py` / `*_fact_packet.py` builder in the repo, builds a packet from each, and
   asserts every fact carries LEDGER provenance (source_ref resolves to the ledger or a ledger
   projection). It MUST FAIL if (a) any current builder bypasses the ledger, or (b) a NEW builder is
   added that isn't ledger-sourced. This is what makes "every packet is robust" enforceable rather than
   hoped-for — drift turns the build red. Register the builder set so "complete enumeration" is a tested
   invariant, not a comment.

## Acceptance
- A single query against `ledger.sqlite` answers "what repos/components/capabilities/files does OpenClaw
  have" (the multi-repo knowledge), worktree-deduped and fresh.
- Each retired satellite's unique data is verifiably present in the ledger first; satellites archived,
  not deleted.
- Hermes's OPENCLAW_INVENTORY.md is generated from the ledger.
- Reconciliation table + before/after sizes/counts in `Operator/CODEX-ONE-KNOWLEDGE-LEDGER-RESULTS.md`.
- No existing ledger ingest path broken; prod-state writes proposed for the operator, not self-confirmed.
