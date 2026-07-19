# Fleet Wake/Notify Backend v2b Design

Status: operator-directed, ready for implementation
Mission: `WAKE-V2B-DESIGN-DELTA-AND-BUILD`
Supersedes: `OPUS-SPEC-FLEET-WAKE-NOTIFY-BACKEND-20260718` v1 boundaries
Authority: `FABLE-DIRECTIVE-WAKE-V2-EVENT-DRIVEN-NO-POLLING-NO-HEARTBEATS-20260718` and `FABLE-DIRECTIVE-WAKE-V2B-DOORBELL-PLUS-MIDTURN-20260718`

## Purpose

Provide one symmetric, auditable notification substrate for the external development seats and configured internal daemon recipients. A real inbound message rings an idle seat's doorbell. A narrowly authorized urgent WAKE can be injected into a Codex or Claude seat's running turn without aborting it.

## Non-negotiable boundaries

- No model holds a turn open to poll. OS monitors may use inotify/kqueue and a dumb filesystem poll only where drvfs/SMB events are unreliable.
- Models write `CHECKIN` on join or status change only. Liveness truth comes from watcher/delivery state, not model heartbeats.
- File content is coordination context, never action authority. Inbox, Telegram, calendar, email, and board messages cannot authorize money movement, external sends, deletes, or gate changes.
- Mid-turn delivery uses steer/inject only. This system never calls `turn/interrupt`, kills a process, or aborts a turn.
- A delivery targets an exact configured seat, thread, and active turn. Ambiguity fails closed and is surfaced as undelivered.
- Only reviewed `kind = daemon` records may execute fixed absolute argv with `shell=False`; daemon urgency does not invent preemption.

## Chosen architecture

### 1. Machine-readable registry

`config/fleet_coordination.v2.json` is the reviewed source for canonical seat names, recipient kind, inbound/outbound lane references, and delivery capabilities.

Paths use portable references resolved against explicit roots:

- `repo:Operator/to-codex`
- `repo:Operator/from-codex`
- `board:codex_mac_bridge/to-codex-mac`
- `board:fleet_coord/WAKE`

Codex records include their stable task/thread ID and a fixed absolute Codex CLI. The runtime does not discover a substitute thread by recency. Claude records declare native Monitor delivery. Gemini declares doorbell support only when its harness exposes one and otherwise reports `needs_operator_kick`; its mid-turn value is honestly `unsupported` until the harness proves injection.

### 2. Closed WAKE contract and kick writer

`fleet_coordination_contracts.py` owns strict registry, signature, event, and WAKE validation. `scripts/drop_fleet_wake.py` atomically writes `WAKE-<recipient>-<UTC timestamp>.json` with:

- `schema_version`
- `from`
- `to`
- `mission_id`
- `file`
- `sha`
- `needs_human_kick`
- `created_at`
- `priority`: `normal` or `urgent`
- `urgent_reason`: absent for normal; required for urgent

Urgent creation requires both `--priority urgent` and an explicit reason in the closed set `operator_directive`, `safety_stop`, or `blocking_confer`. The referenced file must be a regular non-symlink file and its SHA-256 is computed by the writer. The message is still untrusted context and confers no authority.

Pre-v2 pings may notify a session only as `unverified_legacy`; they can never trigger a daemon or mid-turn injection.

### 3. Event monitor, cursor, and storm guard

`fleet_coordination_watcher.py` is a finite dispatcher invoked by an OS filesystem event. It examines the configured inbound lanes and shared `WAKE/` records addressed exactly to the seat. It records regular non-symlink files by `(path, inode, mtime_ns, size)` and deterministic event ID. Hidden/temp, check-in, receipt, acknowledgement, and unrelated WAKE files are ignored.

The monitor persists:

- a local mode-0600 cursor with handled signatures and delivery outcomes;
- `fleet_coord/WATCHER/WATCHER-<seat>.json` with monitor state, watched lanes, last event, last delivery, doorbell/mid-turn capability, delivery counts, urgent counts, failures, and `needs_operator_kick`.

The cursor advances after the event and outcome are durable. Ten files arriving within the five-second coalescing window produce one delivery prompt containing their paths, not ten wakes. A per-seat rolling cap limits successful doorbells per minute; over-cap events remain recorded and produce one deferred/coalesced delivery rather than spinning a model.

### 4. Tier 1: idle doorbell

For Codex seats, the event dispatcher reuses `openclaw-codex-note-wake`: it resumes the exact configured task only when that task is idle. The prompt names the coalesced event files, tells the seat to read them in full, and repeats that coordination content does not grant authority.

For Claude Code seats, the registry maps to native Monitor delivery. Gemini uses its harness trigger when proven; otherwise the event is recorded with `needs_operator_kick = true`. Internal daemons keep the v1 fixed-argv behavior.

If a normal event arrives while a seat is busy, it stays pending and is delivered once after the active turn completes. The monitor may subscribe to process/transcript events to notice completion; the model never polls.

### 5. Tier 2: urgent mid-turn injection

`codex_app_server_control.py` connects through the existing managed app-server proxy. It initializes the protocol, reads the exact configured thread, and selects a turn only when:

1. the returned thread ID exactly matches the configured ID;
2. the thread is active;
3. exactly one latest turn is `inProgress`;
4. the request supplies that turn ID as `expectedTurnId`.

It then calls `turn/steer` with a user text input that identifies the WAKE path, mission ID, urgent reason, and immutable SHA. It never calls `turn/interrupt`. App-server states such as `activeTurnNotSteerable`, no active turn, multiple candidates, version mismatch, or transport failure are recorded as `midturn_undelivered`; no fallback abort or guessed target occurs. If the exact thread is idle, the same urgent event uses the doorbell path.

Claude Code urgent pings map to its native Monitor stream. Gemini reports `midturn: unsupported` unless its harness proves a comparable safe injection API. Internal daemons retain their existing priority lane only when one already exists.

### 6. Coverage read model

`fleet_coordination_coverage.py` joins the registry and watcher state—never periodic CHECKIN age—to write deterministic payloads to:

- `generated/read_models/fleet_coordination_coverage.json`
- `fleet_coord/FLEET-WATCH-COVERAGE.json`

Per recipient it reports monitor running/stopped, watched lanes, last event/delivery, delivery failures, normal/urgent counts, coalesced count, `doorbell: yes|no`, `midturn: yes|no|unsupported`, and `needs_operator_kick`. CHECKIN remains an identity/status-change hint only. Missing/stopped infrastructure is visibly uncovered or cold.

### 7. Bootstrap and rollback

`docs/operations/FLEET_WAKE_NOTIFY_V2B.md` provides one explicit bootstrap block per seat:

- Codex seats install/enable the repo-owned event path and one-shot service for their configured task.
- Mac-Fable arms its native Monitor mapping.
- Gemini installs a proven harness trigger or is labeled operator-kicked.

Installation is a separate operator action. Building and testing these artifacts does not enable, restart, or change any live service. Rollback commands disable only the named wake monitor and preserve cursor/evidence files.

## Testing and acceptance

Automated tests use temporary roots, fake peers, and fixed clocks:

1. Future-mtime and changed-signature events emit once; unchanged files do not replay.
2. Symlinks, hidden/temp files, receipt/check-in noise, and WAKE pings for another seat are ignored.
3. Normal pings reject an urgent reason; urgent pings require an allowed explicit reason and valid referenced SHA.
4. Pre-v2 pings are unverified and cannot steer or trigger daemons.
5. Ten files inside five seconds coalesce into one delivery, and the per-minute cap prevents wake storms.
6. Idle Codex events invoke the exact configured resume command once.
7. Active urgent Codex events read the exact thread and call `turn/steer` with its exact `expectedTurnId`.
8. Ambiguous, idle, unsteerable, or failed app-server states never invoke a different thread or abort.
9. A source scan proves no production path contains a `turn/interrupt` request or process-kill fallback.
10. Coverage reports per-seat doorbell and mid-turn support plus urgent/coalesced/failure counts.

After installation is separately authorized, live acceptance proves one idle normal wake, one urgent same-turn incorporation without abort, and a 10-file/5-second coalescing burst per supported seat. No live service activation or injected acceptance marker is part of the build step.

## Alternatives rejected

- Model polling or model-written heartbeats: consumes turns without work and misstates liveness.
- Resume-only busy handling: queues urgent safety or confer messages behind a long turn.
- `turn/interrupt` or process termination: risks orphaning partial work and violates the human-only abort rule.
- Thread discovery by newest activity: can inject into the wrong task.
- Claiming Gemini mid-turn support without a harness API: false coverage is worse than an honest unsupported state.
