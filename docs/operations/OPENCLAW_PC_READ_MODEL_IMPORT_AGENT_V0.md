# OpenClaw PC Read-Model Import Agent v0

Purpose: let PC/WSL notice when the Mac drops a refreshed generated-read-model
manifest on the E-drive share, then run the existing safe mirror import path
without a manual PC-side command.

## Contract

- Manifest watched by PC/WSL: `/mnt/e/openclaw/mac_generated_read_models_manifest.json`
- Optional Mac completion marker: `/mnt/e/openclaw/shuttle/from_mac/read_model_sync_completed.json`
- Local state file: `.openclaw/state/read_model_import_agent_state.json`
- Local log file: `.openclaw/logs/read_model_import_agent.log`
- Import helper used: `scripts/import_latest_mac_read_model_mirror.py`

The agent hashes the returned Mac manifest. If the hash matches the last
successful import, it records `skipped_unchanged` and does not import again. If
the hash is new, it imports through the existing Mac mirror path and records the
manifest hash, import time, import run id, path count, and mirror counts.

It does not delete, move, rename, or rewrite the source manifest or Mac
completion marker.

## Commands

One-shot mode is the default:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/pc_read_model_import_agent.py --once --format operator
```

Optional loop mode:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/pc_read_model_import_agent.py --loop --interval 300 --format operator
```

Loop mode is intended for a future local scheduler or manually supervised
terminal session. This lane does not install or load a service.

## Statuses

- `manifest_missing`: the E-drive manifest is not present yet.
- `skipped_unchanged`: the manifest hash matches the last successful import.
- `success`: a changed manifest was imported successfully.
- `failure`: import was attempted and failed; state/logs capture the failure.

## Service Recommendation

Keep this as a manual one-shot until the Mac sync agent and PC import behavior
are stable for several cycles. A later lane can add an explicit WSL user
systemd unit, Windows Task Scheduler entry, or cron-style wrapper if the
operator wants unattended local polling.

No service is installed or loaded by v0.

## Boundary

- Local PC/WSL automation only.
- No remote control path.
- No Mission Control changes.
- No generated read-model contract changes.
- No package installation.
- No Docker or Ollama execution.
- No runtime, tool, or agent activation.
- No destructive file operations.
- No C-drive transfer defaults.
