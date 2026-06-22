# Control Plane Cutover Plan

**Status:** BRANCH-ONLY. This plan documents what a live cutover requires.
**Branch:** `codex/control-plane-worker-integration`
**Author:** Change 3 of 5 (ChatGPT-audited redesign)
**Date:** 2026-06-22

---

## What Has Been Proved (On This Branch)

`tests/test_control_plane_worker_integration.py` demonstrates end-to-end against
an **isolated temp ledger** (never touching the real `control_plane.sqlite3`):

1. `admit_task()` inserts a READY + dispatchable row.
2. `claim_next_ready()` atomically transitions the task to LEASED and returns a `TaskLease`.
3. `_task_markdown(row, lease)` materializes a task file from the live lease.
4. `run_local_builder_worker()` (with a fake `runner=` callable, no subprocess) writes
   the task markdown, drives the worker, and calls `submit_candidate_evidence()` on success
   or `record_failure()` on failure.
5. `decide_acceptance()` (with a stub `gate_runner=`) transitions VERIFYING → DONE or BLOCKED.
6. The raw SQLite file is confirmed populated: `tasks`, `attempts`, and `events` tables are
   all written (not mocked).

All 10 new tests pass. All 11 existing pc4 tests remain green. (21/21 total.)

---

## The Gap: Why `control_plane.sqlite3` Is Never Written In Production

`ControlPlaneLedger` and `run_local_builder_worker()` are fully built and tested.
The missing link is **the caller that calls `admit_task()`** in the live workflow.

Currently, no live code path calls `admit_task()` on the real ledger. The machinery
exists; no live task source feeds it.

---

## Which Live Callers Must Call `admit_task()` For Full Cutover

### Primary: `polish_loop/pc4_heal_emitter.py` → `emit_heal_task()`

This is the **only existing production admit path**. It calls `ledger.admit_task()` via
`admit_task_kwargs_for_payload()`. It is called by:

- `tests/test_pc4_hardening.py` and `tests/test_pc4_self_healing.py` — correctly, on
  temp ledgers.
- `self_heal_repair_doctrine.py` — contains the `to_admit_task_kwargs()` helper but
  **nothing calls it at runtime**.

**Cutover step A:** The Gemini verification sentry (`active_machinery_gemini_verification.py`)
or the check-engine inspector (`chief_check_engine_diagnostic_package.py`) — whichever
runs the claim-auditing loop — must import `emit_heal_task` from `pc4_heal_emitter` and
call it against the **real** `ControlPlaneLedger(DEFAULT_LEDGER_PATH)` when a failing
audit finding is detected.

### Secondary: `polish_loop/orchestrator.py` → `run_control_plane_once()`

`orchestrator.py` already calls `run_control_plane_once(ledger, ...)` which calls
`claim_next_ready()`. This half is wired. The missing half is tasks being in the
ledger for it to claim.

Once Step A is in place, the orchestrator will find tasks and dispatch them via
`phase_c_dispatch_local_builder()`.

### If Human-Intent Tasks Are Needed

For operator-originated tasks (e.g., Maestro Telegram or operator keyboard input),
the intake bridge (`operator_universal_intake.py` or `cassandra_listener.py`) must call:

```python
ledger.admit_task(
    source="human_intent",
    task_type="agent_heal",
    requested_status="READY",
    payload=validated_payload,
    acceptance_ref=make_acceptance_ref(acceptance_file, green_gate_path),
)
```

This is the same API exercised in the integration tests.

---

## Exact Cutover Steps (Operator Must Review Each)

**Step 1 — Wire the detector path (minimum viable cutover)**

In `polish_loop/pc4_heal_emitter.py`, the `emit_heal_task()` function already exists
and calls `ledger.admit_task()` correctly. The wiring gap is: the runtime audit loop
must pass the **real** `ControlPlaneLedger(DEFAULT_LEDGER_PATH)` instead of a temp
ledger or `None`.

Specifically, wherever `check_agent_claim()` returns a failing `AuditFinding`, call:

```python
from polish_loop.control_plane import ControlPlaneLedger, DEFAULT_LEDGER_PATH
from polish_loop.pc4_heal_emitter import emit_heal_task

ledger = ControlPlaneLedger(DEFAULT_LEDGER_PATH)
emit_heal_task(
    ledger,
    finding,
    request_text=request_text,
    answer_text=answer_text,
    repro_prompts=(request_text,),
    acceptance_path=Path("tests/test_pc4_self_healing.py"),
)
```

**Step 2 — Confirm `orchestrator.py` poll loop is running**

`orchestrator.py` already calls `run_control_plane_once(ledger, ...)` in its main loop.
Confirm the orchestrator service is active and pointing at `DEFAULT_LEDGER_PATH`.

**Step 3 — First live smoke test (one task)**

Before full fleet cutover, manually call `emit_heal_task()` against the real ledger
with a known-good payload (e.g., a synthetic failing claim against a known truth value)
and watch the orchestrator pick it up. Verify the task reaches DONE or BLOCKED with
the correct terminal reason.

**Step 4 — Monitor for collision artifacts**

The real ledger lives at `/home/openclaw/polish_loop/control_plane.sqlite3`. SQLite
WAL mode is already configured (`PRAGMA journal_mode=WAL`), but concurrent writes from
multiple orchestrator cycles or multiple detectors could produce busy-timeout errors.
The ledger uses `busy_timeout=5000 ms` — increase if needed.

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Detector emits tasks faster than orchestrator claims them | Medium | Deduplication is built in: `emit_heal_task` re-uses deterministic task IDs for `agent_heal` type; duplicate active tasks are silently deduped by `TASK_DEDUPED` event. |
| Real `local_builder.py` doesn't exist at the configured path | High initially | `run_local_builder_worker()` already handles `FileNotFoundError` → `record_failed_to_start()` → BLOCKED, no crash. |
| Acceptance ref hash mismatch after a deploy | Medium | `decide_acceptance()` rejects tampered refs; task goes BLOCKED with `acceptance_ref_hash_mismatch` reason. Re-emit a new task with a fresh acceptance ref. |
| SQLite readonly collision (see memory: feedback_read_actual_error) | Known | This is the `/tmp`-sqlite collision artifact: always verify the actual error before declaring a regression. The real ledger at `/home/openclaw/polish_loop/` is not `/tmp`, so this should not apply, but watch for it. |
| `status.json` compatibility view not updating | Low | `render_status_view()` is called on every successful `_tx()` commit. If the orchestrator loop reads a stale `status.json`, it is because no task was committed, not a bug. |
| Orchestrator dispatching to a worker without a real `local_builder.py` | High initially | Use `config.subprocess_timeout_seconds` to limit blast radius. The failure path is tested and terminalized cleanly. |

---

## What Is NOT Required For Cutover

- No schema migration: `_ensure_schema()` is idempotent; running against an existing
  ledger is safe.
- No service restart: the orchestrator loop polls continuously. Admitting a task to
  the ledger is picked up on the next poll cycle.
- No changes to the real `control_plane.py` or `worker_runtime.py`: both are
  production-ready as of this branch.
- No merge to master: this branch exists for operator review only.

---

## Rollback

If a live cutover produces undesirable behavior:

1. Stop admitting tasks: remove/comment the `emit_heal_task()` call in the detector.
2. The orchestrator will drain any in-flight LEASED tasks (they will timeout via
   `recover_expired_leases()` and be returned to READY, then eventually BLOCKED on
   max_attempts exhaustion).
3. No data is lost: the ledger retains full event history.
4. The real `status.json` will revert to `"status": "idle"` once all tasks are terminal.
