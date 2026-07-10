# OpenClaw boot integrity

Task 150 covers the one observed restart failure class: WSL can reach a half-boot in which systemd is PID 1 but
`/run/dbus/system_bus_socket` is absent. Unit enablement was verified healthy after a clean restart; do not interpret
`systemctl --user is-enabled` failures while D-Bus is absent as disabled units.

## Linux-side assertions

`scripts/openclaw_boot_enable.sh` is verify-only. It checks linger, every service/worker/watcher and timer that was
enabled on the verified clean boot, the stack target, the boot assertion unit, and Ollama enablement. It prints a
suggested enable command only for an observed drift. It never runs that command.

Render `systemd/user/openclaw-boot-assert.service.in` through the normal OpenClaw unit installer and enable it during
the operator-owned deploy. The one-shot applies one shared three-minute retry budget to D-Bus, `/mnt/e`, Ollama, the ten services, and
the timers. The ten operator-facing services remain the report denominator; the six enabled auxiliary workers and
watchers plus the six operational timers must also be healthy before the report can be green. It may start a contract
unit only when that unit is enabled but inactive, using a non-blocking start so the deadline remains bounded. It does not restart an active unit. `getty@tty1.service` is
explicitly ignored because WSL has no tty1 and that failure is benign.

The result is written atomically to `/mnt/c/OpenClaw/logs/openclaw_boot_integrity.marker`. A green boot reports once:

```text
Fleet up after restart: 10/10 services, ollama warm, timers armed.
```

Duplicate named poller processes, growing Telegram `getUpdates` conflict counts, and a running stale distro named
exactly `Ubuntu` are warnings only. No detector in this task kills a process or changes distro state.

## Windows Task Scheduler hook (operator keyboard)

This step cannot be installed or tested from the current WSL-hosted Codex shell. The operator performs it in Windows:

1. Open Task Scheduler and choose **Create Task**.
2. Name it `OpenClaw Boot Integrity` and select **Run only when user is logged on**.
3. Add the trigger **At log on** for the operator account.
4. Add an action **Start a program** with program `C:\Windows\System32\cmd.exe` and arguments
   `/d /c ""\\wsl.localhost\Ubuntu-E\home\openclaw\scripts\windows\openclaw_boot_check.bat""`.
5. Save the task, then use **Run** once and inspect
   `C:\OpenClaw\logs\openclaw_boot_integrity.marker`.

The batch hook observes `wsl.exe -l --running -q` from Windows so it can warn if the stale distro named `Ubuntu` is
running, then invokes only Ubuntu-E as user `openclaw`. It never changes distro state.

If the marker says system D-Bus is missing, the remedy belongs at the operator keyboard: run `wsl --shutdown` once
from PowerShell, then reopen Ubuntu-E. Never automate that remedy from the detector.

## Acceptance owned by the operator

On the next real PC restart, open Ubuntu-E without manually starting services. Confirm the ten services are active,
the three timers are armed, `curl -s http://localhost:11434/api/ps` succeeds, and the single Maestro boot report
arrives. This is the only way to mark the Windows hook and no-human-action restart path LIVE-VERIFIED.
