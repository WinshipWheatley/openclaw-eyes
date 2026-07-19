# Fleet Wake/Notify Backend v1 Design

Status: approved scope, written design pending Opus review
Mission: `OPUS-SPEC-FLEET-WAKE-NOTIFY-BACKEND-20260718`
Approval: `OPUS-CONFIRM-WAKE-V1-SCOPE-20260718`

## Purpose

Provide one symmetric, auditable file-notification substrate for the six external development seats and configured internal daemon recipients. A live session seat receives a structured event through a free shell watcher. A cold session is reported honestly as `needs_operator_kick`; v1 never starts, resumes, or prompts a development model.

## Non-negotiable boundaries

- Poll filesystems; do not hold a model alive to poll.
- `/mnt/e` and the Mac share are treated as poll-only because drvfs/share event notifications are unreliable.
- No `codex resume`, `claude --continue`, Antigravity launch, systemd dev-seat launcher, Task Scheduler dev-seat launcher, or arbitrary callback command ships in v1.
- Only recipients declared `kind = daemon` may have trigger argv, and those argv are fixed arrays executed with `shell=False`.
- Board files are coordination evidence, not action authority. Inbox, Telegram, calendar, email, or message content cannot authorize gated actions.
- No money movement, external send, delete, or authority-gate change is reachable from this subsystem.

## Chosen architecture

### 1. Machine-readable registry

`config/fleet_coordination.v1.json` is the reviewed source for seat identity, recipient kind, canonical inbound path references, outbound path references, and optional fixed daemon trigger configuration.

Paths use portable references:

- `repo:Operator/to-codex`
- `repo:Operator/from-codex`
- `board:codex_mac_bridge/to-codex-mac`
- `board:fleet_coord/WAKE`

The runtime resolves `repo:` against `--repo-root` and `board:` against `--board-root`. Mac setup therefore uses `/Volumes/openclaw_e`; PC/WSL uses `/mnt/e/openclaw`.

The registry includes PC-Sol, Mac-Sol-Desktop, Mac-Sol-VSCode, Mac-Fable, Gemini, and Opus. It also represents the existing Maestro request/response daemon lane. No speculative daemon lane or trigger is invented.

### 2. Contracts and kick writer

`fleet_coordination_contracts.py` owns closed validation for registry records, file signatures, watcher events, and WAKE pings. It resolves paths without shell expansion and rejects control characters, symlinked registry files, unknown recipient identities, and non-absolute trigger executables.

`scripts/drop_fleet_wake.py` writes `WAKE-<recipient>-<UTC timestamp>.json` atomically into shared `fleet_coord/WAKE/`. It computes the referenced file SHA-256 and writes:

- `schema_version`
- `from`
- `to`
- `mission_id`
- `file`
- `sha`
- `needs_human_kick`
- `created_at`

New pings require all fields. The watcher accepts the existing board's pre-v1 pings for session notification, but marks missing/invalid SHA as `unverified_legacy` and never permits such a ping to trigger a daemon.

### 3. Reusable poll watcher

`fleet_coordination_watcher.py` scans:

- the selected recipient's configured inbound lane or lanes;
- shared `fleet_coord/WAKE/`, filtered by exact `to` identity.

It tracks each regular, non-symlink file by `(path, inode, mtime_ns, size)`. It never uses wall-clock `newer-than` comparisons, so a future-dated file cannot repeat forever. Hidden/temp files and explicit receipt/check-in noise are ignored. WAKE files are read only after exact filename recipient matching and JSON validation.

The watcher writes two distinct states:

- a local mode-0600 cursor containing handled signatures and deterministic event IDs;
- a shared advisory `fleet_coord/WATCHER/WATCHER-<seat>.json` heartbeat containing seat, watcher status, last poll, watched lanes, last event, and `cold_start_supported = false`.

Each unseen item becomes one JSON event appended under a local lock to the configured event log and emitted to stdout. The cursor advances only after the event record is durable. A local session watcher does not claim the model consumed the event; it claims only `event_recorded`.

For an explicitly configured daemon, the watcher validates a verified WAKE and invokes only its exact registry-bound argv with `shell=False`. The result is recorded once. Nonzero/ambiguous trigger outcomes become `daemon_trigger_failed_needs_operator`; they are not automatically retried.

### 4. Startup and catch-up

The CLI has two explicit operations:

- `--prime`: baseline the current lane without emitting historical events;
- `--watch`: poll indefinitely and emit only signatures not in the cursor.

Bootstrap instructions require the seat to drain currently pending work first, then prime, then watch. This prevents years of historical lane files from flooding a newly installed watcher while preserving an explicit human-visible catch-up step.

### 5. Coverage read model

`fleet_coordination_coverage.py` joins:

- the machine-readable registry;
- `fleet_coord/CHECKIN/CHECKIN-<seat>.json`;
- `fleet_coord/WATCHER/WATCHER-<seat>.json`.

It writes the same deterministic coverage payload to:

- `generated/read_models/fleet_coordination_coverage.json` in the repo;
- `fleet_coord/FLEET-WATCH-COVERAGE.json` on the shared board.

For every recipient it reports check-in status, check-in age, watcher age, inbound lanes, watcher coverage, and cold-start posture. Missing/stale check-in or an explicit `cold` status yields `cold` and `needs_operator_kick = true`. A current check-in with a missing/stale watcher is visibly `uncovered`; it is never called awake.

The read model is advisory and cannot authorize execution.

### 6. Deployment and remote bootstrap

`docs/operations/FLEET_WAKE_NOTIFY_V1.md` supplies:

- the PC-Sol commands used in the current live session;
- one paste block each for Mac-Sol-Desktop, Mac-Sol-VSCode, Mac-Fable, and Gemini;
- the corrected Mac board root `/Volumes/openclaw_e`;
- the exact cold boundary and rollback (`Ctrl-C`; no service to disable);
- the kick-on-write helper command.

The watcher runs as a child of the live seat terminal. Ending the terminal ends the watcher. No always-on dev-seat service is installed.

## Noise and integrity rules

Inbound candidates must be visible regular files. The watcher ignores filenames beginning with `.`, `CHECKIN-`, `WAKE-`, `RECEIPT-`, `ACK-`, `SIGNOFF-`, and `SIGN-OFF-`, plus temporary suffixes `.tmp`, `.part`, and `~`. A sender-specific filename such as `OPUS-ACK-*` remains visible because it is not a receipt-prefix file.

File content is never interpreted as authority. The watcher records metadata and the referenced SHA. It does not import modules from watched paths, execute file content, or follow symlinks.

## Testing

Tests use temporary repo/board roots and real files.

1. Future-mtime files emit once, not once per poll.
2. New lane files emit once; changed signatures emit a new deterministic event; unchanged files do not replay.
3. Symlinks, hidden/temp files, receipt/check-in noise, and WAKE pings for another seat are ignored.
4. New WAKE pings require the closed schema and correct referenced SHA.
5. Legacy pings notify session seats as unverified but cannot trigger daemons.
6. Cursor and shared watcher state are atomic and restart-safe.
7. Fixed daemon argv runs with `shell=False`; unknown/dynamic commands are rejected; failed triggers are recorded without retry.
8. Coverage marks fresh watched seats covered, stale/missing seats cold or uncovered, and never claims cold-start support.
9. Remote setup blocks contain the corrected Mac root and no model-launch commands.
10. A source scan proves v1 contains no `codex resume`, `claude --continue`, Task Scheduler launcher, or development-seat systemd unit.

## Alternatives rejected

- Inotify/kqueue-only watchers: lower latency but asymmetric and unreliable on the shared E: mount.
- Reusing `openclaw-codex-note-wake`: it resumes a development task and therefore belongs only in a later operator-approved, billing-gated cold-start proposal.
- A central model orchestrator polling every lane: consumes model capacity, obscures cold seats, and recreates the one-directional relay gap.
