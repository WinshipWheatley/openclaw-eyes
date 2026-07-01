# Codex Backlog 044-093 — Done-vs-Open Audit

**By:** Master Orchestrator + 5 parallel Sonnet auditors (read-only, current HEAD)
**Date:** 2026-06-23
**Headline:** Of 50 tasks, **only 17 are genuine new builds.** 28 are already coded on branches
(needing a *land*, not a rebuild), 5 are already in HEAD, 4 are duplicates. Dispatching all 50 to
the local builder would have redone ~66% of the work.

| Disposition | Count | Meaning |
|---|---|---|
| **DONE_IN_HEAD** | 5 | already shipped — marked DEAD in ledger |
| **DUP** | 4 | covered by a canonical land branch — marked DEAD |
| **LAND_BRANCH** | 24 tasks / **19 branches** | code already written on a branch; needs cherry-pick + gate, NOT a rebuild |
| **OPEN** | 17 | genuine new build work |

Ledger now: 9 DEAD + 4 DONE (prior) + 41 PROPOSED (24 land + 17 open). **0 dispatchable** — the live cron stays idle until we deliberately promote.

---

## LAND track — 19 branches close 28 tasks (the big win: proven code, just gate it)

| Branch | Closes | Note |
|---|---|---|
| `codex/044-deterministic-operator-truth-query-intent` | 044, +dup 055/089/093 | truth-QUERY intent, zero-LLM ANSWER_READY |
| `codex/045-maestro-perspective-prompt` | 045, +dup 091 | inject `perspective_prompt('maestro')` |
| `codex/046-finance-intent-grounded-fallback` | 046 | finance-intent grounded fallback |
| `codex/047-question-relevant-maestro-packet` | 047 | trim packet to question-relevant facts |
| `codex/048-people-reference-query` | 048 | people-intent deterministic routing |
| `codex/049-guardian-negation-hedging-cues` | 049 | HEDGING_CUES + widened negation window |
| `codex/050-guardian-credential-leakage` | 050 | regex bearer/jwt/api-key leak detection |
| `codex/051-chief-approval-hold-edge-cases` | 051 | approval-hold phrase coverage |
| `codex/052-reality-bounce-send-after-deny` | 052 | regression test only |
| `codex/053-guardian-approval-boundary` | 053 | APPROVAL_EXECUTION_CLAIMS authority check |
| `codex/054-guardian-proof-backed-completion` | 054 | regression test only (impl already in HEAD) |
| `codex/057-severity-no-soften-guard` | 057 | severity-softening guard |
| `sonnet/061-cassandra-piper-tuning` | 061 | Piper fallback acoustic tuning |
| `sonnet/062-voice-render-observability` | 062 | voice synth timing/metrics |
| `sonnet/063-agent-voice-contracts` | 063 | voice delivery test contracts |
| `sonnet/064-niles-maillot-validation` | 064, 067 | Maillot X32 emulator + scene-validation harness |
| `sonnet/065-scene-corpus-producer-metadata` | 065 | producer-lane metadata extraction |
| `codex/pc-3-gate-isolation-atomic-token` | 074, 075, 082 | green-gate flock/isolation + --fast (= the "020" spec) |
| `codex/022-ar-receivables-packet` | 084, 085, 086 | **[BLOCKED]** AR receivables read-model (violates Gig-to-Cash architecture) |

**Recommended:** land these via cherry-pick into a batch branch → `green_gate.sh` → you deploy.
Far higher quality + cheaper than having the local gemma builder rebuild proven code. Landing
toward main is **your keyboard** (I prepare gated candidates; I never merge-to-master/deploy).

---

## BUILD track — 17 genuinely-open tasks (for the local loop or Codex)

P0 first. Each has a target + one-line goal from the audit; * = depends on a land first.

| # | Pri | Target | Goal |
|---|---|---|---|
| 073 | P0 | `openclaw_change_sentinel.py` + orchestrator lock | sentinel checks a lock before signalling launch (prevent dup orchestrator) |
| 066 | P0 | new `docs/niles_integration_readiness.md` | consolidated niles readiness/blockers/next-move doc |
| 076 | P1 | `scripts/green_gate.sh` REQUIRED_CLEAN_FIXTURES | expand gated fixtures to 8-12 high-signal read-models |
| 077 | P2 | `scripts/green_gate.sh` | emit wall-clock elapsed per gate phase |
| 078 | P1 | `scripts/green_gate.sh` | fail/warn on stale fixtures (age threshold) |
| 080 | P1 | `openclaw_hermes_gateway_policy.py` `_ROUTE_TARGET_RE` | add multi-word handoff verbs (escalate/give/hand over/…) |
| 081 | P1 | `tests/test_openclaw_hermes_gateway_policy.py` | test coverage for the (already-built) capability path |
| 083 | P2 | `agent_lane_registry.py` | telegram display-name + bot-username registry fields |
| 070 | P1 | `chief_cassandra_failure.py` `_queue_failure_task` | dedup repair packets on a normalized failure signature |
| 092 | P2 | `chief_cassandra_failure.py` / operator-truth | dedup operator-truth repair packets (overlaps 070) |
| 071 | P1 | `agent_presence.py` niles config | upgrade niles presence file-exists → process-probe |
| 072 | P1 | `sync_health.py` display status | distinguish "mac present, PC not imported" from generic stale (med conf) |
| 090 | P1 | `cassandra_listener.py` `_should_use_timeout_contract` | truth-probe queries skip the 60s heavy path (reuse 044 matcher) |
| 058 | P2 | TBD | terminology-context adapter framework (thin spec — scope first) |
| 068 | P1 | new `niles_process_registry.py` | first-class niles process schema (PID/service/start) |
| 087 | P1 | `ar_receivables_read_model.py` * | **[BLOCKED]** AR freshness/staleness signals (violates Gig-to-Cash architecture) |
| 088 | P1 | `tests/...ar_receivables...` * | **[BLOCKED]** AR test coverage + integration gate (violates Gig-to-Cash architecture) |

---

## Done/Dup marked DEAD (no work)
056, 079 (hermes 018a in HEAD) · 059, 060 (kokoro voice map + piper fallback) · 069 (polish-loop revival, this session) · 055, 089, 093 (dup of 044) · 091 (dup of 045).

---

## Land-readiness pre-check (merge-tree vs HEAD, non-destructive, 2026-06-23)
13 of 19 land branches cherry-pick **CLEAN**; 6 **CONFLICT** with this session's work.
- **CLEAN (12)** — fast first batch: `044, 045, 048, 049, 050, 051, 052, 053, 054, 057`, `sonnet/063`, `codex/pc-3-gate-isolation-atomic-token` (074/075/082). [Note: 084/085/086 blocked]
- **CONFLICT (6)** — need resolution: `046` (protected_generate.py), `047` (maestro_context_packet.py), `sonnet/061` + `sonnet/062` (voice files vs the merged kokoro work), `sonnet/064` + `sonnet/065` (niles x32/scene-corpus).

Suggested land sequencing: ship the clean 13 as batch-1 (gated candidate), resolve the 6 conflicts as batch-2 (Sonnet or manual).

## Recommended next moves
1. **LAND track first** — I prepare the 19 branches as a gated candidate batch (cherry-pick → green-gate), you review + deploy. This is most of the value and it's proven code.
2. **BUILD track** — promote the 15 open P0-first to `READY` for the live loop (or hand to Codex), enriching each payload from the targets above. Prove one end-to-end before releasing the rest.
3. [BLOCKED] Land 084 (codex/022) before promoting 087/088 (they extend it). Deferred to Gig-to-Cash Step 2.
