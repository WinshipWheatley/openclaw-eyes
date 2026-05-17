# Active Machinery Block-Later Metadata Guardrail v0

Status:
- Metadata/read-model only: `true`.
- Runnable by agents: `false`.
- Runtime authority: `false`.
- Direct execution allowed: `false`.
- Destructive quarantine applied: `false`.
- Runtime changed: `false`.
- Files moved or deleted: `false`.
- Services disabled: `false`.

## Guardrail Records
Count: `5`.

### `builder_watcher.sh`
- Runnable by agents: `false`.
- Runtime authority: `false`.
- Direct execution allowed: `false`.
- Requires operator review: `true`.
- Requires governed replacement: `true`.
- Destructive quarantine applied: `false`.
- Static references: loop_supervisor.sh restarts builder_watcher.sh.
- Blocks/affects: module_cleanup, remote_builder.
- Must prove before action: Replace with Work Board / Operator Action handoff and prove bounded receipts; do not run as a watcher.

### `chief_watcher_brain.py`
- Runnable by agents: `false`.
- Runtime authority: `false`.
- Direct execution allowed: `false`.
- Requires operator review: `true`.
- Requires governed replacement: `true`.
- Destructive quarantine applied: `false`.
- Static references: systemd/user/chief-watcher-brain.service.in references chief_watcher_brain.py.
- Blocks/affects: cassandra_chief_utility, module_cleanup.
- Must prove before action: Replace with bounded Work Board / Operator Action workflow; do not run watcher/process behavior directly.

### `retry_send_demo_dashboard.sh`
- Runnable by agents: `false`.
- Runtime authority: `false`.
- Direct execution allowed: `false`.
- Requires operator review: `true`.
- Requires governed replacement: `true`.
- Destructive quarantine applied: `false`.
- Static references: retry_send_demo_dashboard.sh invokes send_demo_dashboard.py.
- Blocks/affects: module_cleanup, send_paths.
- Must prove before action: Keep as blocked unless replaced by a no-send proof fixture or explicitly approved bounded demo.

### `scripts/run_producer_listener.sh`
- Runnable by agents: `false`.
- Runtime authority: `false`.
- Direct execution allowed: `false`.
- Requires operator review: `true`.
- Requires governed replacement: `true`.
- Destructive quarantine applied: `false`.
- Static references: scripts/run_producer_listener.sh starts producer_listener.py.
- Blocks/affects: module_cleanup.
- Must prove before action: Do not run until Producer listener has a governed contract and operator-approved activation lane.

### `send_demo_dashboard.py`
- Runnable by agents: `false`.
- Runtime authority: `false`.
- Direct execution allowed: `false`.
- Requires operator review: `true`.
- Requires governed replacement: `true`.
- Destructive quarantine applied: `false`.
- Static references: retry_send_demo_dashboard.sh invokes send_demo_dashboard.py.
- Blocks/affects: module_cleanup, send_paths.
- Must prove before action: Replace with read-only dashboard proof or approved no-send review artifact.

## What Did Not Happen
- No high-risk files were edited or executed.
- No services or launchers were changed.
- No files were moved, deleted, renamed, or chmodded.
- No agents, sends, daemons, or runtime activation were enabled.
- Repo B was not executed.

## Next Safe Move
- Active Machinery Replace-with-Governed-Path Spec v0
