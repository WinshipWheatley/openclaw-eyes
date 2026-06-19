# PHASE-C-P0-RECON

Branch/worktree: `codex/phase-c-p0-control-plane` at `/home/openclaw/worktrees/phase-c-p0-control-plane`

## Existing Polish Loop Surface

- `polish_loop/orchestrator.py`: existing conductor around `status.json`, `task.md`, `current/pc_output.md`, `current/mac_review.md`, archive discipline, pass caps, quality checks, and runner handoff. It still exposes a default standing poll loop and writes non-transactional JSON state.
- `polish_loop/local_builder.py`: present in the live checkout as an ignored/untracked runtime asset; thin Ollama worker wrapper with bounded tool calls and `pc_output.md` submission. It is not tracked in this branch yet and must be brought under P0 as the worker-runtime surface.
- `polish_loop/harness_task_runner.py`: present in the live checkout as an ignored/untracked runtime asset; dry-run harness lane that writes evidence artifacts and `pc_output.md`. It is not tracked in this branch yet and must gain ledger claim/submit integration.
- `polish_loop/builder_output_validator.py`: tracked format/quota validator for builder output. It validates structure only; it does not decide durable completion.
- `polish_loop/status.json`: tracked stale runtime state; non-transactional and not suitable as the authority.

## Target Components

| Component | Existing state | Tag | P0 action |
|---|---|---:|---|
| Ledger | `status.json` is a single JSON file with ad hoc atomic rename, no audit tables, no WAL, no task payload schema. | ADD | Add `polish_loop/control_plane.py` SQLite-WAL ledger with `tasks`, `attempts`, and `events`; migrate control-plane authority away from `status.json`. |
| Leases | Builder liveness is inferred from processes and artifact files; no CAS claim, owner, nonce, expiry, or duplicate rejection. | ADD | Add atomic `claim_ready_task` / `heartbeat_lease` / `release` with owner+nonce+version checks. |
| State machine | Old states are `idle`, `pc_turn`, `mac_turn`, `approved`, `blocked`, `parked`; pass cap exists but not the P0 states or transition guards. | EXTEND | Add strict `PROPOSED -> READY -> LEASED -> VERIFYING -> DONE` plus `BLOCKED`/`DEAD`; reject invalid or duplicate transitions in transactions. |
| Allowlist | Frontmatter validation and autonomous skips exist, but any queue markdown can be promoted by idle loop. Agent-created work can become runnable. | FIX | Add source allowlist; only `human_intent`, `detector`, and `approved_followup` can create READY tasks. Builder/auditor/orch create TTL-bound PROPOSED only. |
| Budgets + breaker | `MAX_PASSES`, timeouts, and one relaunch guard exist; self-heal task creation can still continue outside a durable budget record. | EXTEND | Persist per-task attempts, max attempts, budget cap/spend, failure fingerprints, and terminal reasons; block respawn after exhaustion. |
| Two-phase acceptance | `pc_output_valid`, Mac review, and optional Chief gate exist; model text can still drive `approved`, and acceptance is not immutable against workspace edits. | FIX | Move completion into validator-backed candidate evidence plus clean-state `scripts/green_gate.sh`; DONE only from code-owned acceptance ref and gate result outside builder workspace. |

## Six Invariants

| Invariant | Existing state | Tag | P0 action |
|---|---|---:|---|
| 1. Empty queue causes zero model calls / dispatches / writes | `--once` can inspect without launching; default loop polls and logs, idle promotion scans markdown; no durable proof counters. | FIX | Event/quiescent `run_control_plane_once` returns no-op with zero writes when no eligible ledger row exists; no default standing loop. |
| 2. Crash+restart recovers; duplicate/invalid transitions rejected | JSON state survives simple restarts but has no transaction log, leases, duplicate claim rejection, or transition table. | ADD | SQLite-WAL plus CAS leases and strict transition API; attempts/events survive process death. |
| 3. Builder cannot make PROPOSED dispatchable | No source/role distinction in queue promotion; builder-authored markdown could become runnable if it passes frontmatter. | FIX | Ledger source allowlist rejects builder/auditor/orch READY creation and PROPOSED->READY promotion. |
| 4. No respawn past budget; terminal/quiescent on exhaustion | `MAX_PASSES` and `relaunch_attempted` partially cap retries; self-heal queueing can create follow-on work and status can return idle. | EXTEND | Durable max attempts and budget breaker transition to `BLOCKED`/`DEAD`; exhausted tasks are non-dispatchable. |
| 5. Builder workspace cannot edit acceptance test to cause DONE | Current acceptance reads mutable repo files/artifacts and model-written `pc_output.md`; no immutable acceptance reference. | FIX | Store immutable acceptance hash/ref when task is admitted; validator compares against ledger ref and runs clean-room gate from repo root, not builder workspace. |
| 6. No prose heartbeat row/packet whose only content is alive/nothing-to-do | Runtime has `orchestrator_heartbeat.json` in live checkout and idle prose logs; no ledger row guard. | FIX | Reject heartbeat/alive/nothing-to-do payload-only tasks and provide no heartbeat row type. |

## Reconciliation Result

No PHASE-C-P0-RECON-BLOCKER: `polish_loop` provides the choreography and worker surfaces but not the deterministic P0 core. Build should harden/extend it in place, import the existing runtime worker files into the branch, and avoid a greenfield orchestrator.
