# Active Machinery Quarantine Operator Review v0

Status:
- Review/read-model only: `true`.
- Runtime changed: `false`.
- Files moved or deleted: `false`.
- Services disabled: `false`.
- No blocking, wrapping, replacement, retirement, or caller switch happened.

## Summary
- High-risk live/script items: `14`.
- Block later: `5`.
- Replace with governed path: `4`.
- Wrap with Guardian: `3`.
- Retire later: `2`.
- Keep for now / current dependency: `0`.
- Needs operator decision: `9`.

## Block later
Count: `5`.

### `builder_watcher.sh`
- What it is: Shell launcher or watcher surface.
- Why it matters: Verified watcher/daemon signals on a builder surface; legacy watchdog-style build loops should not run outside a governed Operator Action packet.
- Current risk: `high`.
- Static references/dependencies: loop_supervisor.sh restarts builder_watcher.sh.
- Recommended future action: Keep warning-only now; later block activation or replace with governed path after operator approval.
- Prove before acting: Replace with Work Board / Operator Action handoff and prove bounded receipts; do not run as a watcher.
- Blocks/affects: remote_builder, module_cleanup.

### `chief_watcher_brain.py`
- What it is: Listener, watcher, or daemon-style surface.
- Why it matters: Verified watcher plus shell/process signals; this is too risky to run as active machinery without a replacement contract.
- Current risk: `high`.
- Static references/dependencies: systemd/user/chief-watcher-brain.service.in references chief_watcher_brain.py.
- Recommended future action: Keep warning-only now; later block activation or replace with governed path after operator approval.
- Prove before acting: Replace with bounded Work Board / Operator Action workflow; do not run watcher/process behavior directly.
- Blocks/affects: cassandra_chief_utility, module_cleanup.

### `retry_send_demo_dashboard.sh`
- What it is: Send/API-capable surface.
- Why it matters: Verified send-path signal on a shell demo/retry surface; demos must not become live send machinery.
- Current risk: `high`.
- Static references/dependencies: retry_send_demo_dashboard.sh invokes send_demo_dashboard.py.
- Recommended future action: Keep warning-only now; later block activation or replace with governed path after operator approval.
- Prove before acting: Keep as blocked unless replaced by a no-send proof fixture or explicitly approved bounded demo.
- Blocks/affects: send_paths, module_cleanup.

### `scripts/run_producer_listener.sh`
- What it is: Shell launcher or watcher surface.
- Why it matters: Verified launcher for listener machinery; shell launchers should not activate daemons outside governed runtime approval.
- Current risk: `high`.
- Static references/dependencies: scripts/run_producer_listener.sh starts producer_listener.py.
- Recommended future action: Keep warning-only now; later block activation or replace with governed path after operator approval.
- Prove before acting: Do not run until Producer listener has a governed contract and operator-approved activation lane.
- Blocks/affects: module_cleanup.

### `send_demo_dashboard.py`
- What it is: Send/API-capable surface.
- Why it matters: Verified send/API signal on a demo dashboard sender; demo send paths should remain blocked.
- Current risk: `high`.
- Static references/dependencies: retry_send_demo_dashboard.sh invokes send_demo_dashboard.py.
- Recommended future action: Keep warning-only now; later block activation or replace with governed path after operator approval.
- Prove before acting: Replace with read-only dashboard proof or approved no-send review artifact.
- Blocks/affects: send_paths, module_cleanup.

## Replace with governed path
Count: `4`.

### `cassandra_listener.py`
- What it is: Listener, watcher, or daemon-style surface.
- Why it matters: Verified listener signals on Cassandra intake; current direction is governed intake plus Work Board projection, not an ungated listener.
- Current risk: `high`.
- Static references/dependencies: systemd/user/cassandra-listener.service.in references cassandra_listener.py; start_cassandra_core.sh starts cassandra_listener.py and cassandra_watcher.py.
- Recommended future action: Design a governed replacement before any caller switch or service change.
- Prove before acting: Route through governed intake, Operator Action, and Guardian/HITL receipts before any live listener use.
- Blocks/affects: cassandra_chief_utility, send_paths, module_cleanup.

### `chief_guardian_listener.py`
- What it is: Listener, watcher, or daemon-style surface.
- Why it matters: Verified listener plus approval/HITL signals on legacy Guardian machinery; canonical direction is SQLite Operator Action / Guardian contract.
- Current risk: `high`.
- Static references/dependencies: systemd/user/chief-guardian-listener.service.in references chief_guardian_listener.py.
- Recommended future action: Design a governed replacement before any caller switch or service change.
- Prove before acting: Use SQLite-backed Operator Action/HITL surfaces; keep legacy listener compatibility-only until replacement proof exists.
- Blocks/affects: cassandra_chief_utility, send_paths, module_cleanup.

### `chief_listener.py`
- What it is: Listener, watcher, or daemon-style surface.
- Why it matters: Verified central listener signals; current Chief direction is deterministic control-plane over governed intake, not autonomous listener authority.
- Current risk: `high`.
- Static references/dependencies: systemd/user/chief-listener.service.in references chief_listener.py; start_chief_logged.sh starts chief_listener.py.
- Recommended future action: Design a governed replacement before any caller switch or service change.
- Prove before acting: Prove caller scope, HITL boundary, and receipt path before live listener activation.
- Blocks/affects: cassandra_chief_utility, send_paths, module_cleanup.

### `producer_listener.py`
- What it is: Listener, watcher, or daemon-style surface.
- Why it matters: Verified listener/scheduler/send signals on Producer/Niles-adjacent machinery; not ready as autonomous runtime.
- Current risk: `high`.
- Static references/dependencies: scripts/run_producer_listener.sh starts producer_listener.py.
- Recommended future action: Design a governed replacement before any caller switch or service change.
- Prove before acting: Define Producer/Niles module boundary and route actions through Guardian/HITL before activation.
- Blocks/affects: send_paths, module_cleanup.

## Wrap with Guardian
Count: `3`.

### `chief_email_brain.py`
- What it is: Send/API-capable surface.
- Why it matters: Verified send/API signals on an email capability; external communication must remain draft/review-only until explicitly approved.
- Current risk: `high`.
- Static references/dependencies: no static reference captured in the warning packet.
- Recommended future action: Keep no-send now; require immutable Guardian/Operator Action packet and receipt proof before runtime use.
- Prove before acting: Require immutable approved packet, no-send default, and Guardian receipt before any external send behavior.
- Blocks/affects: cassandra_chief_utility, send_paths, module_cleanup.

### `chief_guardian_sender.py`
- What it is: Send/API-capable surface.
- Why it matters: Verified send/API plus Guardian signals; any notification/sender path needs explicit approval boundaries.
- Current risk: `high`.
- Static references/dependencies: Guardian/HITL surfaces reference chief_guardian_sender.py.
- Recommended future action: Keep no-send now; require immutable Guardian/Operator Action packet and receipt proof before runtime use.
- Prove before acting: Allow only approved notification packets and receipts; no raw or freeform send authority.
- Blocks/affects: cassandra_chief_utility, send_paths, module_cleanup.

### `chief_sender.py`
- What it is: Send/API-capable surface.
- Why it matters: Verified send/API signals on a sender surface; external sends require Guardian/operator approval.
- Current risk: `high`.
- Static references/dependencies: Chief brain files reference chief_sender.py.
- Recommended future action: Keep no-send now; require immutable Guardian/Operator Action packet and receipt proof before runtime use.
- Prove before acting: Require approved immutable packet, recipient binding, no raw command text, and receipt proof.
- Blocks/affects: cassandra_chief_utility, send_paths, module_cleanup.

## Retire later
Count: `2`.

### `cassandra_watcher.py`
- What it is: Listener, watcher, or daemon-style surface.
- Why it matters: Verified watcher/listener signals on a Cassandra surface; likely superseded by governed intake and read-model flows.
- Current risk: `high`.
- Static references/dependencies: systemd/user/cassandra-watcher.service.in references cassandra_watcher.py; start_cassandra_core.sh starts cassandra_listener.py and cassandra_watcher.py.
- Recommended future action: Prove no active dependency or governed equivalent before retirement.
- Prove before acting: Prove it is still needed; otherwise retire after equivalent governed path is confirmed.
- Blocks/affects: cassandra_chief_utility, send_paths, module_cleanup.

### `chief_brainstorm_watcher.py`
- What it is: Listener, watcher, or daemon-style surface.
- Why it matters: Verified watcher/state-mutator signals on a Chief brainstorming surface; not on the current canonical authority path.
- Current risk: `high`.
- Static references/dependencies: no static reference captured in the warning packet.
- Recommended future action: Prove no active dependency or governed equivalent before retirement.
- Prove before acting: Keep disabled until an operator-approved use case proves it should become a governed Work Board source.
- Blocks/affects: cassandra_chief_utility, module_cleanup.

## Keep for now / current dependency
Count: `0`.

No high-risk live/script item is recommended to stay as-is. Physically leave all files untouched until a separate approved lane acts.

## Needs operator decision
Count: `9`.

### `cassandra_listener.py`
- What it is: Listener, watcher, or daemon-style surface.
- Why it matters: Verified listener signals on Cassandra intake; current direction is governed intake plus Work Board projection, not an ungated listener.
- Current risk: `high`.
- Static references/dependencies: systemd/user/cassandra-listener.service.in references cassandra_listener.py; start_cassandra_core.sh starts cassandra_listener.py and cassandra_watcher.py.
- Recommended future action: Design a governed replacement before any caller switch or service change.
- Prove before acting: Route through governed intake, Operator Action, and Guardian/HITL receipts before any live listener use.
- Blocks/affects: cassandra_chief_utility, send_paths, module_cleanup.

### `cassandra_watcher.py`
- What it is: Listener, watcher, or daemon-style surface.
- Why it matters: Verified watcher/listener signals on a Cassandra surface; likely superseded by governed intake and read-model flows.
- Current risk: `high`.
- Static references/dependencies: systemd/user/cassandra-watcher.service.in references cassandra_watcher.py; start_cassandra_core.sh starts cassandra_listener.py and cassandra_watcher.py.
- Recommended future action: Prove no active dependency or governed equivalent before retirement.
- Prove before acting: Prove it is still needed; otherwise retire after equivalent governed path is confirmed.
- Blocks/affects: cassandra_chief_utility, send_paths, module_cleanup.

### `chief_brainstorm_watcher.py`
- What it is: Listener, watcher, or daemon-style surface.
- Why it matters: Verified watcher/state-mutator signals on a Chief brainstorming surface; not on the current canonical authority path.
- Current risk: `high`.
- Static references/dependencies: no static reference captured in the warning packet.
- Recommended future action: Prove no active dependency or governed equivalent before retirement.
- Prove before acting: Keep disabled until an operator-approved use case proves it should become a governed Work Board source.
- Blocks/affects: cassandra_chief_utility, module_cleanup.

### `chief_email_brain.py`
- What it is: Send/API-capable surface.
- Why it matters: Verified send/API signals on an email capability; external communication must remain draft/review-only until explicitly approved.
- Current risk: `high`.
- Static references/dependencies: no static reference captured in the warning packet.
- Recommended future action: Keep no-send now; require immutable Guardian/Operator Action packet and receipt proof before runtime use.
- Prove before acting: Require immutable approved packet, no-send default, and Guardian receipt before any external send behavior.
- Blocks/affects: cassandra_chief_utility, send_paths, module_cleanup.

### `chief_guardian_listener.py`
- What it is: Listener, watcher, or daemon-style surface.
- Why it matters: Verified listener plus approval/HITL signals on legacy Guardian machinery; canonical direction is SQLite Operator Action / Guardian contract.
- Current risk: `high`.
- Static references/dependencies: systemd/user/chief-guardian-listener.service.in references chief_guardian_listener.py.
- Recommended future action: Design a governed replacement before any caller switch or service change.
- Prove before acting: Use SQLite-backed Operator Action/HITL surfaces; keep legacy listener compatibility-only until replacement proof exists.
- Blocks/affects: cassandra_chief_utility, send_paths, module_cleanup.

### `chief_guardian_sender.py`
- What it is: Send/API-capable surface.
- Why it matters: Verified send/API plus Guardian signals; any notification/sender path needs explicit approval boundaries.
- Current risk: `high`.
- Static references/dependencies: Guardian/HITL surfaces reference chief_guardian_sender.py.
- Recommended future action: Keep no-send now; require immutable Guardian/Operator Action packet and receipt proof before runtime use.
- Prove before acting: Allow only approved notification packets and receipts; no raw or freeform send authority.
- Blocks/affects: cassandra_chief_utility, send_paths, module_cleanup.

### `chief_listener.py`
- What it is: Listener, watcher, or daemon-style surface.
- Why it matters: Verified central listener signals; current Chief direction is deterministic control-plane over governed intake, not autonomous listener authority.
- Current risk: `high`.
- Static references/dependencies: systemd/user/chief-listener.service.in references chief_listener.py; start_chief_logged.sh starts chief_listener.py.
- Recommended future action: Design a governed replacement before any caller switch or service change.
- Prove before acting: Prove caller scope, HITL boundary, and receipt path before live listener activation.
- Blocks/affects: cassandra_chief_utility, send_paths, module_cleanup.

### `chief_sender.py`
- What it is: Send/API-capable surface.
- Why it matters: Verified send/API signals on a sender surface; external sends require Guardian/operator approval.
- Current risk: `high`.
- Static references/dependencies: Chief brain files reference chief_sender.py.
- Recommended future action: Keep no-send now; require immutable Guardian/Operator Action packet and receipt proof before runtime use.
- Prove before acting: Require approved immutable packet, recipient binding, no raw command text, and receipt proof.
- Blocks/affects: cassandra_chief_utility, send_paths, module_cleanup.

### `producer_listener.py`
- What it is: Listener, watcher, or daemon-style surface.
- Why it matters: Verified listener/scheduler/send signals on Producer/Niles-adjacent machinery; not ready as autonomous runtime.
- Current risk: `high`.
- Static references/dependencies: scripts/run_producer_listener.sh starts producer_listener.py.
- Recommended future action: Design a governed replacement before any caller switch or service change.
- Prove before acting: Define Producer/Niles module boundary and route actions through Guardian/HITL before activation.
- Blocks/affects: send_paths, module_cleanup.

## Operator Decisions Needed
- Approve which block_later surfaces should become denylisted, replaced, or left as warning-only.
- Approve replacement lanes for Cassandra/Chief/Guardian listener surfaces before caller or service changes.
- Approve Guardian-wrapped send-path design before any send-capable surface is allowed to run.
- Approve retirement only after static dependencies and rollback are proven.

## What Did Not Happen
- No high-risk scripts were executed.
- Repo B was not run.
- Runtime behavior did not change.
- Services, files, launchers, and permissions were left untouched.
- Agents, sends, and daemons were not enabled.

## Next Safe Move
- Active Machinery Quarantine Decision Packet v0
