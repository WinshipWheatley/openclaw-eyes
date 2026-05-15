# OpenClaw Windows Read-Model Import Task v0

Purpose: finish the hands-free read-model mirror loop on PC/Windows by running the existing WSL import agent every minute.

## Task

- Task name: `OpenClawReadModelImport`
- Schedule: every 1 minute
- Scope: current Windows user, logged-on-only by default
- Wrapper path: `E:\openclaw\windows_tasks\OpenClawReadModelImport.ps1`
- Windows-side log path: `E:\openclaw\windows_tasks\logs\OpenClawReadModelImport.log`
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
5. Writes or updates `E:\openclaw\windows_tasks\OpenClawReadModelImport.ps1`.
6. Registers or replaces `OpenClawReadModelImport`.
7. Runs the task once.
8. Shows task status, Windows-side log tail, and WSL-side log tail.
9. Runs the read-model mirror doctor.

The default interval is 1 minute. The import agent hashes the manifest and skips unchanged imports, so this keeps the PC side responsive without repeatedly re-importing the same manifest.

## Task Action

The scheduled task runs the Windows-side wrapper:

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "E:\openclaw\windows_tasks\OpenClawReadModelImport.ps1"
```

The wrapper then runs WSL with the selected distro:

```text
wsl.exe -d Ubuntu-E -- bash -lc 'mkdir -p /home/openclaw/.openclaw/logs && cd /home/openclaw && PYTHONDONTWRITEBYTECODE=1 python3 scripts/pc_read_model_import_agent.py --once --format operator'
```

The actual distro name may differ if `Ubuntu-E` is not present. The wrapper captures output in the Windows-side log and appends the WSL command output to `/home/openclaw/.openclaw/logs/windows_task_read_model_import.log`.

## Validate

From Windows PowerShell:

```powershell
Start-ScheduledTask -TaskName OpenClawReadModelImport
Start-Sleep -Seconds 12
Get-ScheduledTaskInfo -TaskName OpenClawReadModelImport
Get-Content -LiteralPath "E:\openclaw\windows_tasks\logs\OpenClawReadModelImport.log" -Tail 60
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
