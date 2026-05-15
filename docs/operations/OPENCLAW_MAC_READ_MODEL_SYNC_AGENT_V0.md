# OpenClaw Mac Read-Model Sync Agent v0

Purpose: let the Mac notice a local E-drive marker and run the existing safe
generated read-model mirror sync without opening Mission Control or creating a
remote-control path.

## Contract

- Shared drop on Mac: `/Volumes/openclaw_e`
- Request marker: `/Volumes/openclaw_e/shuttle/to_mac/read_model_sync_required.json`
- Completion marker: `/Volumes/openclaw_e/shuttle/from_mac/read_model_sync_completed.json`
- Log file: `~/Library/Logs/OpenClaw/read_model_sync_agent.log`
- Backend clone: `~/Developer/OpenClawBackend/openclaw`

When the share is mounted and the request marker exists, run from the backend
clone:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_read_model_mirror.py --pull --format operator
```

The agent does not delete the request marker. It writes a completion marker with
`status: success` or `status: failure`, the command, the sync exit code, and
short stdout/stderr tails.

If `/Volumes/openclaw_e` is not mounted, it logs `share_missing` and exits 0.
If the marker is absent, it logs `marker_missing` and exits 0.

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
is not installed or loaded by this lane.

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
