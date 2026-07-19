# Fleet Wake/Notify v2b Implementation Plan

Mission: `WAKE-V2B-DESIGN-DELTA-AND-BUILD`
Design: `docs/superpowers/specs/2026-07-18-fleet-wake-notify-v1-design.md`

## Task 1: Codex exact-turn steering client

Files:

- Create `codex_app_server_control.py`
- Create `tests/test_codex_app_server_control.py`

Steps:

1. Write fake-peer tests for exact thread binding, exactly one `inProgress` turn, exact `expectedTurnId`, idle reporting, ambiguous-turn refusal, protocol errors, and prohibited interrupt source scan.
2. Run the focused test and confirm it fails because the module is absent.
3. Implement initialization, `thread/read`, and `turn/steer` only. Return typed delivery outcomes; never call interrupt or guess another thread.
4. Run the focused test to green and commit only these files.

## Task 2: Closed v2 WAKE contract and writer

Files:

- Create `fleet_coordination_contracts.py`
- Create `scripts/drop_fleet_wake.py`
- Create `tests/test_fleet_coordination_contracts.py`

Steps:

1. Write tests for normal/urgent validation, allowed urgent reasons, regular referenced file plus SHA, exact recipient filename, legacy classification, control-character rejection, and atomic mode-0600 output.
2. Run the focused test red.
3. Implement strict parsing and the writer. Make normal the default; require explicit priority and reason for urgent.
4. Run focused tests green and commit only these files.

## Task 3: Event dispatcher, coalescing, and Codex routing

Files:

- Create `fleet_coordination_watcher.py`
- Modify `codex_note_event_wake.py`
- Create `tests/test_fleet_coordination_watcher.py`
- Modify `tests/test_codex_note_event_wake.py`

Steps:

1. Write tests for finite OS-event dispatch, signature dedup, lane/recipient filtering, a 10-file five-second coalesce, per-minute cap, normal busy queuing, exact-thread urgent steering, idle urgent doorbell, and failed steer durability.
2. Run focused tests red.
3. Implement a one-shot dispatcher with injected clock/delivery adapters. Extend note-wake to accept a coalesced list and return busy without polling the model.
4. Run focused tests green and commit only the scoped files.

## Task 4: Registry, coverage, and watcher state

Files:

- Create `config/fleet_coordination.v2.json`
- Create `fleet_coordination_coverage.py`
- Create `tests/test_fleet_coordination_coverage.py`

Steps:

1. Write tests proving portable path resolution, all six seats, honest Gemini unsupported mid-turn, watcher-state liveness, urgent/coalesced/failure counts, and deterministic dual-output coverage.
2. Run focused tests red.
3. Implement the reviewed registry and deterministic read model. Treat CHECKIN as identity/status only, never a heartbeat.
4. Run focused tests green and commit only the scoped files.

## Task 5: Event monitor units and bootstrap runbook

Files:

- Create `systemd/user/openclaw-fleet-wake-v2b@.service.in`
- Create `systemd/user/openclaw-fleet-wake-v2b@.path.in`
- Create `docs/operations/FLEET_WAKE_NOTIFY_V2B.md`
- Create `tests/test_fleet_wake_v2b_deployment.py`

Steps:

1. Write tests proving event-based activation, no periodic timer/heartbeat, no interrupt/kill path, per-seat bootstrap, exact rollback, and no implicit live enable.
2. Run focused tests red.
3. Implement templates and documentation only; do not install, enable, restart, or steer a live task.
4. Run focused tests green and commit only the scoped files.

## Task 6: Verification and proof-back

1. Run all wake-v2b focused tests.
2. Run the relevant existing note-wake and app-server client regressions.
3. Run `git diff --check` over the wake-v2b commit range.
4. Write a result receipt to `Operator/from-codex/` with commit IDs, exact commands/counts, unresolved live-acceptance boundary, and artifact hashes.
5. Drop a normal-priority WAKE for Opus and update CHECKIN only if mission status changes.
