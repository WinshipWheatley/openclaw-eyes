# Active Machinery Quarantine Decision Packet v0

Status:
- Decision/read-model only: `true`.
- Implementation authorized: `false`.
- Runtime changed: `false`.
- Files moved or deleted: `false`.
- Services disabled: `false`.

## Counts
- Block later: `5`.
- Replace with governed path: `4`.
- Wrap with Guardian: `3`.
- Retire later: `2`.
- Keep for now / current dependency: `0`.
- Needs operator decision overlay: `9`.

## Decision Buckets
### Block later
Count: `5`.

- `builder_watcher.sh`
  - Why: Verified watcher/daemon signals on a builder surface; legacy watchdog-style build loops should not run outside a governed Operator Action packet.
  - Static references: loop_supervisor.sh restarts builder_watcher.sh.
  - Prove first: Replace with Work Board / Operator Action handoff and prove bounded receipts; do not run as a watcher.
  - Blocks/affects: module_cleanup, remote_builder.
  - Implementation authorized now: `false`.
- `chief_watcher_brain.py`
  - Why: Verified watcher plus shell/process signals; this is too risky to run as active machinery without a replacement contract.
  - Static references: systemd/user/chief-watcher-brain.service.in references chief_watcher_brain.py.
  - Prove first: Replace with bounded Work Board / Operator Action workflow; do not run watcher/process behavior directly.
  - Blocks/affects: cassandra_chief_utility, module_cleanup.
  - Implementation authorized now: `false`.
- `retry_send_demo_dashboard.sh`
  - Why: Verified send-path signal on a shell demo/retry surface; demos must not become live send machinery.
  - Static references: retry_send_demo_dashboard.sh invokes send_demo_dashboard.py.
  - Prove first: Keep as blocked unless replaced by a no-send proof fixture or explicitly approved bounded demo.
  - Blocks/affects: module_cleanup, send_paths.
  - Implementation authorized now: `false`.
- `scripts/run_producer_listener.sh`
  - Why: Verified launcher for listener machinery; shell launchers should not activate daemons outside governed runtime approval.
  - Static references: scripts/run_producer_listener.sh starts producer_listener.py.
  - Prove first: Do not run until Producer listener has a governed contract and operator-approved activation lane.
  - Blocks/affects: module_cleanup.
  - Implementation authorized now: `false`.
- `send_demo_dashboard.py`
  - Why: Verified send/API signal on a demo dashboard sender; demo send paths should remain blocked.
  - Static references: retry_send_demo_dashboard.sh invokes send_demo_dashboard.py.
  - Prove first: Replace with read-only dashboard proof or approved no-send review artifact.
  - Blocks/affects: module_cleanup, send_paths.
  - Implementation authorized now: `false`.

### Replace with governed path
Count: `4`.

- `cassandra_listener.py`
  - Why: Verified listener signals on Cassandra intake; current direction is governed intake plus Work Board projection, not an ungated listener.
  - Static references: systemd/user/cassandra-listener.service.in references cassandra_listener.py; start_cassandra_core.sh starts cassandra_listener.py and cassandra_watcher.py.
  - Prove first: Route through governed intake, Operator Action, and Guardian/HITL receipts before any live listener use.
  - Blocks/affects: cassandra_chief_utility, module_cleanup, send_paths.
  - Implementation authorized now: `false`.
- `chief_guardian_listener.py`
  - Why: Verified listener plus approval/HITL signals on legacy Guardian machinery; canonical direction is SQLite Operator Action / Guardian contract.
  - Static references: systemd/user/chief-guardian-listener.service.in references chief_guardian_listener.py.
  - Prove first: Use SQLite-backed Operator Action/HITL surfaces; keep legacy listener compatibility-only until replacement proof exists.
  - Blocks/affects: cassandra_chief_utility, module_cleanup, send_paths.
  - Implementation authorized now: `false`.
- `chief_listener.py`
  - Why: Verified central listener signals; current Chief direction is deterministic control-plane over governed intake, not autonomous listener authority.
  - Static references: systemd/user/chief-listener.service.in references chief_listener.py; start_chief_logged.sh starts chief_listener.py.
  - Prove first: Prove caller scope, HITL boundary, and receipt path before live listener activation.
  - Blocks/affects: cassandra_chief_utility, module_cleanup, send_paths.
  - Implementation authorized now: `false`.
- `producer_listener.py`
  - Why: Verified listener/scheduler/send signals on Producer/Niles-adjacent machinery; not ready as autonomous runtime.
  - Static references: scripts/run_producer_listener.sh starts producer_listener.py.
  - Prove first: Define Producer/Niles module boundary and route actions through Guardian/HITL before activation.
  - Blocks/affects: module_cleanup, send_paths.
  - Implementation authorized now: `false`.

### Wrap with Guardian
Count: `3`.

- `chief_email_brain.py`
  - Why: Verified send/API signals on an email capability; external communication must remain draft/review-only until explicitly approved.
  - Static references: no static reference captured.
  - Prove first: Require immutable approved packet, no-send default, and Guardian receipt before any external send behavior.
  - Blocks/affects: cassandra_chief_utility, module_cleanup, send_paths.
  - Implementation authorized now: `false`.
- `chief_guardian_sender.py`
  - Why: Verified send/API plus Guardian signals; any notification/sender path needs explicit approval boundaries.
  - Static references: Guardian/HITL surfaces reference chief_guardian_sender.py.
  - Prove first: Allow only approved notification packets and receipts; no raw or freeform send authority.
  - Blocks/affects: cassandra_chief_utility, module_cleanup, send_paths.
  - Implementation authorized now: `false`.
- `chief_sender.py`
  - Why: Verified send/API signals on a sender surface; external sends require Guardian/operator approval.
  - Static references: Chief brain files reference chief_sender.py.
  - Prove first: Require approved immutable packet, recipient binding, no raw command text, and receipt proof.
  - Blocks/affects: cassandra_chief_utility, module_cleanup, send_paths.
  - Implementation authorized now: `false`.

### Retire later
Count: `2`.

- `cassandra_watcher.py`
  - Why: Verified watcher/listener signals on a Cassandra surface; likely superseded by governed intake and read-model flows.
  - Static references: systemd/user/cassandra-watcher.service.in references cassandra_watcher.py; start_cassandra_core.sh starts cassandra_listener.py and cassandra_watcher.py.
  - Prove first: Prove it is still needed; otherwise retire after equivalent governed path is confirmed.
  - Blocks/affects: cassandra_chief_utility, module_cleanup, send_paths.
  - Implementation authorized now: `false`.
- `chief_brainstorm_watcher.py`
  - Why: Verified watcher/state-mutator signals on a Chief brainstorming surface; not on the current canonical authority path.
  - Static references: no static reference captured.
  - Prove first: Keep disabled until an operator-approved use case proves it should become a governed Work Board source.
  - Blocks/affects: cassandra_chief_utility, module_cleanup.
  - Implementation authorized now: `false`.

### Keep for now / current dependency
Count: `0`.

No items in this bucket.

### Needs Operator Decision
Count: `9`.
These are approval gates, not runtime instructions. They overlap with the primary buckets above.

- `cassandra_listener.py` remains gated before any action.
- `cassandra_watcher.py` remains gated before any action.
- `chief_brainstorm_watcher.py` remains gated before any action.
- `chief_email_brain.py` remains gated before any action.
- `chief_guardian_listener.py` remains gated before any action.
- `chief_guardian_sender.py` remains gated before any action.
- `chief_listener.py` remains gated before any action.
- `chief_sender.py` remains gated before any action.
- `producer_listener.py` remains gated before any action.

## First Safe Future Implementation Lane
- Active Machinery Block-Later Metadata Guardrail v0
- Scope: metadata guardrail/read-model only for block_later surfaces; no service disable, file move/delete, launcher edit, caller switch, send enablement, or runtime activation

## What Is Not Authorized
- No service disable.
- No file move, delete, rename, or chmod.
- No launcher or systemd template edit.
- No caller switch.
- No agent, send, daemon, or runtime activation.
- No Repo B execution.

## Next Safe Move
- Active Machinery Block-Later Metadata Guardrail v0
