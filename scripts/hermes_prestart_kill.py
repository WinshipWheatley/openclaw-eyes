#!/usr/bin/env python3
"""
hermes_prestart_kill.py - ExecStartPre helper for hermes-gateway.service.

Reads gateway.pid (JSON {"pid": N, ...}), reads /proc/N/cmdline, confirms it
contains 'run_openclaw_hermes_gateway.py', sends SIGTERM then (after 1 s)
SIGKILL if still alive, and removes the stale pid file. This clears the
orphan/stale-PID condition BEFORE the new gateway tries to claim the pid file,
which is what caused the 3723-restart crash loop on 2026-06-29.

Safety invariant: this script will NEVER kill any process whose cmdline does
NOT contain the exact marker string 'run_openclaw_hermes_gateway.py'. It targets
the PID stored in the JSON file only - it never calls pgrep/pkill. PID 413
('openclaw-gateway', a different native service) and the hermes_fleet_loop are
therefore unreachable by this script.
"""
import json
import os
import signal
import sys
import time

PID_FILE = "/home/openclaw/sidecars/hermes_home/gateway.pid"
TARGET_MARKER = "run_openclaw_hermes_gateway.py"
TAG = "hermes-prestart"


def _log(msg):
    print(f"{TAG}: {msg}", file=sys.stderr, flush=True)


def _safe_remove(path):
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        _log(f"could not remove {path}: {exc}")


def main():
    if not os.path.exists(PID_FILE):
        _log("no pid file found, nothing to do")
        return

    # Parse the pid file - JSON produced by run_openclaw_hermes_gateway.py.
    try:
        with open(PID_FILE) as f:
            data = json.load(f)
        pid = int(data["pid"])
    except Exception as exc:  # noqa: BLE001 - any parse failure means the file is junk.
        _log(f"could not parse pid file: {exc} - removing it")
        _safe_remove(PID_FILE)
        return

    if pid <= 1:
        _log(f"suspicious PID {pid} in pid file, skipping kill")
        _safe_remove(PID_FILE)
        return

    cmdline_path = f"/proc/{pid}/cmdline"
    if not os.path.exists(cmdline_path):
        _log(f"PID {pid} not alive (no /proc entry), removing stale pid file")
        _safe_remove(PID_FILE)
        return

    try:
        with open(cmdline_path, "rb") as f:
            raw = f.read()
        cmdline = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
    except OSError as exc:
        _log(f"could not read /proc/{pid}/cmdline: {exc} - removing pid file, NOT killing")
        _safe_remove(PID_FILE)
        return

    if TARGET_MARKER not in cmdline:
        # cmdline mismatch - NOT the gateway (e.g. the kernel recycled the PID).
        # Remove the stale pid file but NEVER signal a foreign process.
        _log(
            f"PID {pid} cmdline does NOT contain {TARGET_MARKER!r} "
            f"(first 120 chars: {cmdline[:120]!r}) - NOT killing, removing pid file only"
        )
        _safe_remove(PID_FILE)
        return

    # Confirmed the target - safe to kill.
    _log(f"stale gateway confirmed at PID {pid} (cmdline matches), sending SIGTERM")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _log(f"PID {pid} already gone (race), removing pid file")
        _safe_remove(PID_FILE)
        return
    except PermissionError as exc:
        _log(f"SIGTERM to PID {pid} denied: {exc} - leaving pid file for manual cleanup")
        return

    time.sleep(1.0)

    try:
        os.kill(pid, 0)  # ProcessLookupError if it exited
        _log(f"PID {pid} survived SIGTERM after 1 s, sending SIGKILL")
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        time.sleep(0.5)
    except ProcessLookupError:
        _log(f"PID {pid} exited cleanly after SIGTERM")

    _safe_remove(PID_FILE)
    _log("stale gateway cleared, pid file removed - ExecStart may now proceed")


if __name__ == "__main__":
    main()
