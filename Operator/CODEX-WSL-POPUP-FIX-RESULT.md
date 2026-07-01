# CODEX WSL Popup Fix Result

Date: 2026-07-01

## Status

PASS for the visible popup candidates.

I diagnosed Windows Scheduled Tasks that launch WSL/OpenClaw, then corrected the enabled visible candidate and the disabled-but-wrong startup tasks.

## Diagnosis

Installed WSL distros:

```text
Ubuntu-E  Running  WSL2
Ubuntu    Running  WSL2
```

Important finding: the popup risk was not simply "Ubuntu does not exist." It does exist, which is worse: wrong-distro tasks could quietly run against the wrong OpenClaw checkout/environment.

OpenClaw WSL tasks found:

- `OpenClaw-Sonnet-G2C005-20260625`: enabled, interactive, `Hidden=false`, targeted `-d Ubuntu`.
- `Start Album and Billing Brains`: disabled, interactive, `Hidden=false`, targeted `-d Ubuntu`.
- `Start Chief and Brains`: disabled, interactive, `Hidden=false`, targeted `-d Ubuntu`.
- `Start Watcher Brain`: disabled, interactive, `Hidden=false`, targeted `-d Ubuntu`.
- `start_openclaw_brains.sh`: disabled, interactive, `Hidden=false`, targeted `-d Ubuntu`.
- `Start-WSL-OpenClaw`: enabled/running, password logon, targeted `-d Ubuntu-E`.

Likely live focus-stealer: `OpenClaw-Sonnet-G2C005-20260625` because it was enabled, time-triggered, visible, interactive, and pointed at the wrong distro.

## Changes Applied

Changed `OpenClaw-Sonnet-G2C005-20260625`:

- `-d Ubuntu` -> `-d Ubuntu-E`
- `Hidden=false` -> `Hidden=true`

Also corrected disabled startup tasks so they do not regress if re-enabled:

- `Start Album and Billing Brains`: `-d Ubuntu-E`, `Hidden=true`
- `Start Chief and Brains`: `-d Ubuntu-E`, `Hidden=true`
- `Start Watcher Brain`: `-d Ubuntu-E`, `Hidden=true`
- `start_openclaw_brains.sh`: `-d Ubuntu-E`, `Hidden=true`

`Start-WSL-OpenClaw` was left unchanged after `Set-ScheduledTask` returned `0x8007052e` (stored password mismatch). It already targets `Ubuntu-E`, uses `Password` logon instead of interactive task popups, and is the running WSL keeper.

## Verification

Final observed task settings:

```text
OpenClaw-Sonnet-G2C005-20260625  Enabled=True   Hidden=True   Action=wsl.exe -d Ubuntu-E -u openclaw --exec bash -lc '/home/openclaw/Operator/scheduled/g2c005/run_sonnet_g2c005.sh'
Start Album and Billing Brains   Enabled=False  Hidden=True   Action=wsl.exe -d Ubuntu-E -- bash -lc "bash /home/openclaw/start_openclaw_brains.sh"
Start Chief and Brains           Enabled=False  Hidden=True   Action=wsl.exe -d Ubuntu-E -- bash -lc "bash /home/openclaw/start_chief_logged.sh"
Start Watcher Brain              Enabled=False  Hidden=True   Action=wsl.exe -d Ubuntu-E -- bash -lc "cd /home/openclaw && setsid -f python3 /home/openclaw/chief_watcher_brain.py </dev/null >/tmp/chief_watcher_brain.log 2>&1"
start_openclaw_brains.sh         Enabled=False  Hidden=True   Action=wsl.exe -d Ubuntu-E -- bash -lc "bash /home/openclaw/start_openclaw_brains.sh"
Start-WSL-OpenClaw               Enabled=True   Hidden=False  Action=wsl.exe -d Ubuntu-E -u root --exec /usr/bin/sleep infinity
```

## Residual Risk

If the visible popup persists, the next suspect is a non-Windows-Task trigger (Startup folder, registry Run key, third-party launcher, or a PowerShell wrapper under `E:\openclaw\windows_tasks`). The scheduled-task popup candidate is now fixed.
