# OpenClaw Windows Read-Model Import Task v0

Purpose: finish the hands-free read-model mirror loop on PC/Windows by running the existing WSL import agent every five minutes.

## Task

- Task name: `OpenClawReadModelImport`
- Schedule: every 5 minutes
- Scope: current Windows user, logged-on-only by default
- Log path inside WSL: `/home/openclaw/.openclaw/logs/windows_task_read_model_import.log`
- Shared drop:
  - Windows: `E:\openclaw`
  - WSL: `/mnt/e/openclaw`

## Install

Run from Windows PowerShell, not from inside WSL:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-E\home\openclaw\scripts\windows_install_read_model_import_task.ps1"
```

If the backend distro is not `Ubuntu-E`, first run:

```powershell
wsl.exe -l -v
```

Then pass the correct distro:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\<DISTRO>\home\openclaw\scripts\windows_install_read_model_import_task.ps1" -PreferredDistro "<DISTRO>"
```

The installer:

1. Confirms `E:\openclaw` exists.
2. Confirms `wsl.exe` exists.
3. Detects the WSL distro, preferring `Ubuntu-E`.
4. Confirms `/home/openclaw` exists inside WSL.
5. Registers or replaces `OpenClawReadModelImport`.
6. Runs the task once.
7. Shows recent import log output.
8. Runs the read-model mirror doctor.

## Task Action

The scheduled task runs:

```text
wsl.exe -d Ubuntu-E -- bash -lc 'cd /home/openclaw && PYTHONDONTWRITEBYTECODE=1 python3 scripts/pc_read_model_import_agent.py --once --format operator >> .openclaw/logs/windows_task_read_model_import.log 2>&1'
```

The actual distro name may differ if `Ubuntu-E` is not present.

## Validate

From Windows PowerShell:

```powershell
Start-ScheduledTask -TaskName OpenClawReadModelImport
Start-Sleep -Seconds 12
wsl.exe -d Ubuntu-E -- bash -lc "tail -n 40 /home/openclaw/.openclaw/logs/windows_task_read_model_import.log"
wsl.exe -d Ubuntu-E -- bash -lc "cd /home/openclaw && PYTHONDONTWRITEBYTECODE=1 python3 scripts/manage_openclaw_local_services.py --doctor read_model_mirror --format operator"
```

The doctor should report:

- `missing_expected=0`
- `extra=0`
- `hash_mismatch=0`

## Uninstall

```powershell
Unregister-ScheduledTask -TaskName OpenClawReadModelImport -Confirm:$false
```

## Boundary

- Uses the existing WSL import agent only.
- No C-drive OpenClaw transfer folder.
- No Docker or Ollama.
- No SSH, SCP, rsync, or remote control.
- No package installs.
- No Mission Control changes.
- No runtime, tool, or agent activation.
- No file moves, deletes, or reorganization.
