# OpenClaw Local Automation Services v0

Purpose: make proven local OpenClaw maintenance loops installable, visible, and stoppable without adding remote control or arbitrary scheduling.

## Scope

This v0 manages only the generated read-model mirror loop:

- Mac local half: `read_model_mirror_mac_sync`
  - Script: `scripts/mac_read_model_sync_agent.py`
  - Scheduler: macOS LaunchAgent, every 300 seconds when installed
  - Trigger: `/Volumes/openclaw_e/shuttle/to_mac/read_model_sync_required.json`
- PC/WSL local half: `read_model_mirror_pc_import`
  - Script: `scripts/pc_read_model_import_agent.py --once --format operator`
  - Scheduler: WSL user systemd timer when available, every 300 seconds
  - Input: `/mnt/e/openclaw/mac_generated_read_models_manifest.json`

The registry also names future local maintenance task classes, but they are not enabled as background services in v0.

## Commands

Build registry:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_local_automation_registry.py --format operator
```

Query registry:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/query_local_automation_registry.py --report summary --format operator
```

Status:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/manage_openclaw_local_services.py --status --format operator
```

Doctor:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/manage_openclaw_local_services.py --doctor read_model_mirror --format operator
```

Install/start the current machine's local half:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/manage_openclaw_local_services.py --install read_model_mirror --format operator
PYTHONDONTWRITEBYTECODE=1 python3 scripts/manage_openclaw_local_services.py --start read_model_mirror --format operator
```

Stop/uninstall:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/manage_openclaw_local_services.py --stop read_model_mirror --format operator
PYTHONDONTWRITEBYTECODE=1 python3 scripts/manage_openclaw_local_services.py --uninstall read_model_mirror --format operator
```

## Machine Behavior

On Mac, the manager installs or controls only:

```text
~/Library/LaunchAgents/com.openclaw.read-model-sync.plist
```

On PC/WSL, the manager installs or controls only:

```text
~/.config/systemd/user/openclaw-read-model-import.service
~/.config/systemd/user/openclaw-read-model-import.timer
```

If WSL user systemd is unavailable, installation is deferred and the one-shot command remains the safe fallback:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/pc_read_model_import_agent.py --once --format operator
```

## Shared Drop

- Mac: `/Volumes/openclaw_e`
- PC: `E:\openclaw`
- WSL: `/mnt/e/openclaw`

No C-drive transfer path is used.

## Stop/Disable Requirement

Every service installed by this lane has a documented stop and uninstall path. Uninstall removes only OpenClaw service files and leaves manifests, markers, logs, state, read-models, and ledger data in place.

## Boundary

- Local maintenance only.
- No arbitrary command execution.
- No remote control.
- No Mission Control changes.
- No generated read-model contract changes.
- No package installation.
- No Docker or Ollama execution.
- No runtime, tool, or agent activation.
- No broad filesystem watcher.
- No deletion, movement, or reorganization of user files.
