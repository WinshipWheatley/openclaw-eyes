# PC4 Harden Watchdog

The Phase-C orchestrator is finite and event-driven, but every `run_phase_c_once()`
call touches `polish_loop/heartbeat-<role>`. MASTER can detect a silent stopped
runner by checking that file's mtime against the expected launcher cadence.

For unattended operation, wrap the finite tick in systemd or an equivalent host
scheduler. The wrapper should call the process periodically, enforce
`OPENCLAW_TEST_MODE=1` and `OPENCLAW_SEND_HOLD=1` for PC4 hardening runs, and alert
when the heartbeat mtime stops advancing. Do not replace the deterministic ledger
with a shell poll loop.
