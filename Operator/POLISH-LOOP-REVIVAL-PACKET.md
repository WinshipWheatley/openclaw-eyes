# Polish-Loop Revival Packet

**Prepared by:** Master Orchestrator (PC backend)
**Date:** 2026-06-23
**Status:** APPLIED + PROVEN (commit `edeb14a0`). The reversible corrections are done; the
orchestrator is healthy and the queue is clean. **The only step left is your single cron paste**
(the harness blocks me from installing crons). Nothing was started; no daemon, no prod dispatch
(the live `--once` proof no-ops on the drained ledger).

The polish-loop revival is the gate for the big plan: **Chief → polish-loop → the Codex
backlog**. This packet is everything you need to flip it on with confidence in one keystroke,
plus the corrections you must apply first (the old restart path is broken).

---

## TL;DR — what I found

1. **The orchestrator is not broken — nothing is triggering it.** The code is healthy: a
   `--dry-run` exits 0 with a clean `DispatchResult(dispatched=False, reason='dry_run_no_dispatch')`,
   reading the ledger correctly. The process is just dead (stale PID `732508`, nothing running).
2. **The documented restart path is broken.** `loop_supervisor.sh` launches
   `orchestrator.py --loop`, but **`--loop` is deprecated and disabled** — it prints
   `ERROR: standing poll loops are disabled for Phase-C/PC4` and exits 2. The supervisor would
   log `RESTART FAILED` every 60s forever. The architecture moved to **event-triggered `--once`**.
3. **The ledger is fully drained** — 4 tasks, all `DONE`, 0 attempts, no WAL lock.
4. **The "ledger contention" is dual-source staleness.** Legacy `status.json` claims
   `task-028d…` is `READY`/dispatchable, but the authoritative Phase-C ledger says it's `DONE`.
   The Phase-C path reads the ledger (ignores `status.json`), so this is cosmetic for dispatch but
   misleading for humans/dashboards. Reconcile it (below).
5. **`tasks/*.md` is a dead-drop** — nothing auto-ingests it. The 4 files there are orphaned
   emitted specs, not live work.

---

## Supervised single-task proof (both green)

| Proof | Command | Result |
|---|---|---|
| Orchestrator code healthy | `python3 polish_loop/orchestrator.py --dry-run` | `dispatched=False` clean, **EXIT 0**, counts `{tasks:4, attempts:0, events:4}` |
| Revival-target chain healthy | the stress-wire task's own verification battery (11 test files) | **247 passed in 41.28s, EXIT 0** |

The second battery is the `00-chief-agent-stress-polish-loop-wire` task's verification command —
it exercises exactly the chain the loop repairs (Cassandra status/payment wiring, Chief↔Cassandra
failure routing, Chief LLM router, acceptance gate, agent voice routing, Telegram intake, PC review
fallback). It was recorded green at 239; it's now green at 247 (grew with this session's work).

---

## Orphaned-task triage (all 4 → archive; none is open work)

| File | Date | Disposition | Why |
|---|---|---|---|
| `00-chief-agent-stress-polish-loop-wire-…Z.md` | 06-19 | **Archive as DONE/verified** | Already verified; its battery is green (247 passed). Keep its verification command as the loop's smoke battery. |
| `chief-cassandra-failure-20260602T221225.md` | 06-02 | **Archive (superseded)** | 3-week-old auto-emitted failure investigation; Cassandra path rebuilt since. |
| `chief-cassandra-failure-20260610T205623.md` | 06-10 | **Archive (superseded)** | Hilton send-authority investigation; send path is SEND_HOLD-gated, no open action. |
| `chief-cassandra-failure-20260618T210019.md` | 06-18 | **Archive (resolved)** | The exact query ("where are we?") now works — stress battery confirms it answers clean. |

These were auto-emitted by Chief's failure path and never ingested (dead-drop). Archiving them is
safe housekeeping. **Say the word and I'll move them to `polish_loop/archive/` and commit.**

---

## Corrections — status

### 1. Reconcile `status.json` to ledger truth — ✅ DONE (commit `edeb14a0`)
The file claimed `task-028d…` was `READY`; it's now honest: `phase_c_status=DONE`,
`dispatchable=false` (matches the drained ledger).

### 2. Fix the restart mechanism — ⏳ YOUR ONE PASTE (harness blocks agent cron-install)
`--loop` is dead; the event-triggered model wants a short-lived `--once` per tick. I built the
full combined crontab (your 3 existing jobs + the new tick) at **`/tmp/polish_loop_crontab.txt`**.
Install it with a single line in this session:
```bash
! crontab /tmp/polish_loop_crontab.txt
```
The new line it adds:
```cron
*/5 * * * * /usr/bin/flock -n /tmp/polish_orch.lock ./chief_env/bin/python polish_loop/orchestrator.py --once >> /mnt/c/OpenClaw/logs/orchestrator_once.out 2>&1
```
- `flock -n` keeps overlapping ticks from piling up (a dispatched task holds a 900s lease;
  `claim_next_ready` won't double-claim either).
- Each tick claims **one** READY task, dispatches it to the local builder, exits. Empty ledger →
  no-op. Safe, bounded revival.

### 3. Remove the orchestrator from `loop_supervisor.sh` — ✅ DONE (commit `edeb14a0`)
`check_orchestrator` + its main-loop call removed; `check_duplicates` now counts only the
deprecated `--loop` daemon so transient `--once` ticks are never miscounted/killed. Other watches
(builder_watcher, dashboard_gen, ceo_briefing, mac_watcher) left intact. `bash -n` passes.

---

## After revival: the big-plan ingest — MAPPED ✅ (one discrepancy to resolve)

To run **Chief → polish-loop → the Codex backlog**, the backlog tasks must be **ingested into the
control_plane ledger** as `READY` rows. Both unknowns are now mapped:

- **Backlog source:** `generated/read_models/chief_build_backlog.json` (live: **7** `backlog_items`)
  + AGY's `Operator/from-gemini/PLAN-GOTCHAS-AND-CODEX-BACKLOG-AUDIT-RESULT.md`. ("MASTER-WORK-QUEUE.md"
  was a misremember — the real queue is the Chief build backlog.)
- **Enqueue API:** `ControlPlaneLedger.admit_task(source=…, task_type=…, requested_status="READY",
  payload=…, acceptance_ref=…)`. **Safety gate:** only sources in
  `READY_SOURCES = {human_intent, detector, approved_followup}` admit directly to dispatchable
  `READY` (everything else is downgraded to `PROPOSED`/`agent_suggestion`); detectors can't emit
  send/payment/money work; heartbeat payloads are rejected. So an operator-approved ingest uses
  `source="human_intent"`. State machine: `PROPOSED→READY→LEASED→VERIFYING→DONE`.

**One discrepancy to resolve before ingest:** the live `chief_build_backlog.json` has **7** items,
but the audit referenced ~**50** Codex tasks (Batch 044–093). Reconcile which list is authoritative
(and de-dupe against the 4 already-DONE ledger tasks) before loading. That's the next phase — say
the word and I'll build the ingest (read source → `admit_task` per item → verify counts) for your go.

---

## UPDATE 2026-06-23 — execution side still needs starting (found during backlog dispatch)
The cron revival got the **dispatch** side live (orchestrator `--once` claims tasks + writes fix
directives). But the **execution** side is down: `phase_c_dispatch_local_builder` only writes a
directive — a separate **builder-watcher** (kept alive by `loop_supervisor.sh`) runs the actual
local_builder build. Neither `loop_supervisor` nor any builder-watcher/worker process is running.
ollama is up with `gemma4:e4b/26b/31b` available (builder default `gemma4:e4b` is present — no model
drift). So a promoted task would dispatch but never build (→ churn to BLOCKED).
**To actually build the backlog:** start the execution daemon (operator's hand):
```bash
setsid nohup bash loop_supervisor.sh >> /mnt/c/OpenClaw/logs/supervisor.out 2>&1 &
```
(loop_supervisor keeps builder_watcher + dashboard alive; the orchestrator is cron-driven, no longer
supervised here.) Alternatively, prove one build with a single bounded manual run before starting the
daemon. Promotes are HELD until the execution side is confirmed running.

## The one move to go live (after corrections 1–3)
```bash
# smoke it once by hand first (claims at most one task, then exits):
cd /home/openclaw && ./chief_env/bin/python polish_loop/orchestrator.py --once
# then let the cron tick drive it.
```
Prod dispatch and the daemon are **your hand** — I prepped, proved, and staged; I did not start it.
