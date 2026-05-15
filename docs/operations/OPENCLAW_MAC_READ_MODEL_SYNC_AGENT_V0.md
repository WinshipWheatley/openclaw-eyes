# OpenClaw Mac Read-Model Sync Agent v0

Purpose: let the Mac notice a local E-drive marker and run the existing safe
generated read-model mirror sync without opening Mission Control or creating a
remote-control path.

## Contract

- Shared drop on Mac: `/Volumes/openclaw_e`
- Request marker: `/Volumes/openclaw_e/shuttle/to_mac/read_model_sync_required.json`
- Completion marker: `/Volumes/openclaw_e/shuttle/from_mac/read_model_sync_completed.json`
- Heartbeat/status marker: `/Volumes/openclaw_e/shuttle/from_mac/read_model_sync_agent_status.json`
- Log file: `~/Library/Logs/OpenClaw/read_model_sync_agent.log`
- Backend clone: `~/Developer/OpenClawBackend/openclaw`

When the share is mounted and the request marker exists, run from the backend
clone:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_read_model_mirror.py --pull --format operator
```

The agent does not delete the request marker. Internally it invokes the sync
runner with the same Python interpreter that launched the agent and asks for JSON
output so it can write proof fields, while still printing an operator summary
from the agent itself.

On every mounted-share run it writes a heartbeat/status marker with:

- `status`: `synced`, `skipped_no_marker`, `share_missing`, or `error`
- `backend_head`
- `marker_seen`
- `manifest_written`
- `manifest_sha256`
- `copied_file_count`
- no-authority flags

When sync succeeds it writes a completion marker with:

- `generated_at`
- `backend_head`
- `manifest_path`
- `manifest_sha256`
- `copied_file_count`
- `source: mac_read_model_sync_agent`
- no-authority flags

If `/Volumes/openclaw_e` is not mounted, it logs `share_missing` and exits 0.
If the marker is absent, it logs `skipped_no_marker`, writes an idle heartbeat,
and exits 0.
If a successful completion marker is newer than the request marker, it logs
`marker_already_completed`, writes an `idle` heartbeat, and exits 0 instead of
pulling repeatedly on the same already-answered marker.

## Boundary

- Local Mac automation only.
- No Mission Control launch or source modification.
- No generated read-model contract changes.
- No package installation.
- No Docker or Ollama.
- No runtime, tool, or agent activation.
- No request marker deletion.
- No destructive file operations.

## Manual One-Shot Run

```bash
cd ~/Developer/OpenClawBackend/openclaw
PYTHONDONTWRITEBYTECODE=1 python3 scripts/mac_read_model_sync_agent.py
```

## Prepared LaunchAgent

The prepared plist is:

```text
launchd/com.openclaw.read-model-sync.plist
```

It runs once at login and then every 300 seconds. It is prepared in the repo but
is not installed or loaded by this lane. The plist uses the local Framework
Python path instead of Apple/Xcode `/usr/bin/python3`; the latter can run under a
minimal launchd PATH that is too old for the backend scripts and may not share
the same removable-volume access behavior.

Install and load manually:

```bash
mkdir -p ~/Library/LaunchAgents ~/Library/Logs/OpenClaw
cp ~/Developer/OpenClawBackend/openclaw/launchd/com.openclaw.read-model-sync.plist ~/Library/LaunchAgents/com.openclaw.read-model-sync.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.openclaw.read-model-sync.plist
launchctl enable gui/$(id -u)/com.openclaw.read-model-sync
launchctl kickstart -k gui/$(id -u)/com.openclaw.read-model-sync
```

Unload later:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.openclaw.read-model-sync.plist
```
