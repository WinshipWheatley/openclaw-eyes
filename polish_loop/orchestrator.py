#!/usr/bin/env python3
"""
orchestrator.py — Central loop controller for the OpenClaw polish loop.

Sole writer of status.json. Planner and Builder write artifacts only.
Orchestrator reads artifacts and decides all state transitions.

Usage:
    python3 orchestrator.py           # continuous poll loop
    python3 orchestrator.py --once    # one cycle and exit
    python3 orchestrator.py --dry-run
    python3 orchestrator.py --reset-blocked --reason "..."
    python3 orchestrator.py --run-tests
"""

import argparse
import datetime
import json
import re
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants (configurable)
# ---------------------------------------------------------------------------

POLL_INTERVAL    = 30    # seconds between poll cycles
BUILDER_TIMEOUT  = 600   # 10 min — block if Builder dead and no output
PLANNER_TIMEOUT  = 600   # 10 min — block if Planner gone and no review
MAX_PASSES       = 3     # block if task needs a 4th pass

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

LOOP_DIR     = Path("/home/openclaw/polish_loop")
STATUS_FILE  = LOOP_DIR / "status.json"
CURRENT_DIR  = LOOP_DIR / "current"
PC_OUTPUT    = CURRENT_DIR / "pc_output.md"
MAC_REVIEW   = CURRENT_DIR / "mac_review.md"
CLOSEOUT     = CURRENT_DIR / "closeout.ok"
LOG_FILE     = Path("/mnt/c/OpenClaw/logs/orchestrator.log")

VALID_STATES = {"idle", "pc_turn", "mac_turn", "approved", "blocked", "parked"}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def log(tag: str, msg: str, dry_run: bool = False) -> None:
    ts   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = "[dry-run] " if dry_run else ""
    line  = f"[{ts}] [{tag}] {prefix}{msg}"
    print(line)
    if dry_run:
        return
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"[WARN] Could not write to orchestrator.log: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Status.json I/O — Orchestrator is the SOLE writer
# ---------------------------------------------------------------------------


def read_status() -> dict | None:
    """Return parsed status dict, or None if missing / unreadable / invalid state."""
    if not STATUS_FILE.exists():
        return None
    try:
        with open(STATUS_FILE) as f:
            d = json.load(f)
        if not isinstance(d, dict):
            return None
        if d.get("status") not in VALID_STATES:
            return None
        return d
    except Exception:
        return None


def _write_status_raw(updates: dict) -> None:
    """Low-level: merge updates into status.json atomically."""
    current: dict = {}
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE) as f:
                current = json.load(f)
            if not isinstance(current, dict):
                current = {}
        except Exception:
            current = {}

    current.update(updates)
    current["last_updated"] = datetime.datetime.now().isoformat()

    tmp = STATUS_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(current, f, indent=2)
    tmp.rename(STATUS_FILE)


def write_status(
    new_state: str,
    *,
    pass_num: int | None = None,
    approved: bool | None = None,
    reason: str | None = None,
    parked_from: str | None = None,
    parked_reason: str | None = None,
) -> None:
    """Write a state transition to status.json."""
    updates: dict = {"status": new_state}
    if pass_num is not None:
        updates["pass"] = pass_num
    if approved is not None:
        updates["approved"] = approved
    if reason is not None:
        updates["block_reason"] = reason
    elif new_state not in ("blocked", "parked"):
        # Clear stale block_reason when leaving blocked or parked
        updates["block_reason"] = None
    if parked_from is not None:
        updates["parked_from"] = parked_from
    elif new_state != "parked":
        updates["parked_from"] = None   # clear when leaving parked
    if parked_reason is not None:
        updates["parked_reason"] = parked_reason
    elif new_state != "parked":
        updates["parked_reason"] = None  # clear when leaving parked
    _write_status_raw(updates)


# ---------------------------------------------------------------------------
# Evidence validators
# ---------------------------------------------------------------------------


def pc_output_valid(expected_pass: int) -> tuple[bool, str]:
    """
    Returns (True, "ok") or (False, reason).
    reason values: "missing" | "empty" | "no_pass_line" | "stale" | "has_blocked"
    """
    if not PC_OUTPUT.exists():
        return False, "missing"
    try:
        content = PC_OUTPUT.read_text()
    except Exception as e:
        return False, f"unreadable: {e}"
    lines = content.splitlines()
    if not lines:
        return False, "empty"
    first = lines[0].strip()
    if not first.upper().startswith("PASS:"):
        return False, "no_pass_line"
    try:
        found = int(first.split(":", 1)[1].strip())
    except (ValueError, IndexError):
        return False, "no_pass_line"
    if found != expected_pass:
        return False, "stale"
    if re.search(r"^\s*STATUS:\s*BLOCKED\s*$", content, re.IGNORECASE | re.MULTILINE):
        return False, "has_blocked"
    return True, "ok"


def mac_review_says_approved() -> bool:
    """True if mac_review.md contains 'APPROVED' on its own line (no NEEDS_REWORK)."""
    if not MAC_REVIEW.exists():
        return False
    for line in MAC_REVIEW.read_text().splitlines():
        stripped = line.strip().upper()
        if stripped == "APPROVED":
            return True
    return False


def mac_review_says_rework() -> bool:
    """True if mac_review.md contains 'NEEDS_REWORK' on its own line."""
    if not MAC_REVIEW.exists():
        return False
    for line in MAC_REVIEW.read_text().splitlines():
        stripped = line.strip().upper()
        if stripped == "NEEDS_REWORK":
            return True
    return False


def closeout_confirmed(task_name: str, pass_num: int) -> bool:
    """True if closeout.ok exists with matching task_name and pass."""
    if not CLOSEOUT.exists():
        return False
    text = ""
    try:
        text = CLOSEOUT.read_text().strip()
        d = json.loads(text)
        return d.get("task_name") == task_name and d.get("pass") == pass_num
    except Exception as e:
        log(
            "ERROR",
            f"closeout.ok is not valid JSON — Planner must rewrite it. "
            f'Expected: {{"task_name": "{task_name}", "pass": {pass_num}}}. '
            f"Parse error: {e!r}. Content: {text[:200]!r}",
        )
        return False


# ---------------------------------------------------------------------------
# Agent process detection
# ---------------------------------------------------------------------------

# Set to True/False in tests to override real process check.
_TEST_BUILDER_OVERRIDE: bool | None = None

# Set to True/False in tests to override _relaunch_builder() return value.
_TEST_RELAUNCH_OVERRIDE: bool | None = None

# Test hook: when True, suppress idle auto-promotion/auto-start side effects.
_TEST_DISABLE_IDLE_AUTOSTART: bool = False

# Set to True in tests to keep idle-state queue promotion from touching live tasks.
_TEST_DISABLE_IDLE_AUTOLAUNCH: bool = False


def builder_running() -> bool:
    """True if run_polish_pass.sh is currently executing (the Builder agent)."""
    if _TEST_BUILDER_OVERRIDE is not None:
        return _TEST_BUILDER_OVERRIDE
    try:
        result = subprocess.run(
            ["pgrep", "-f", "run_polish_pass.sh"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def _relaunch_builder() -> bool:
    """Attempt to re-launch the Builder via run_polish_pass.sh. Returns True if process started."""
    if _TEST_RELAUNCH_OVERRIDE is not None:
        return _TEST_RELAUNCH_OVERRIDE
    try:
        subprocess.Popen(
            ["bash", str(LOOP_DIR / "run_polish_pass.sh")],
            stdout=open(LOG_FILE.parent / "polish_relaunch.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        return True
    except Exception as e:
        log("ERROR", f"Builder re-launch failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Elapsed time helper
# ---------------------------------------------------------------------------


def compute_elapsed(status: dict) -> float:
    """Seconds since last_updated in status.json."""
    last = status.get("last_updated")
    if not last:
        return 0.0
    try:
        then = datetime.datetime.fromisoformat(last)
        return (datetime.datetime.now() - then).total_seconds()
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# State handlers
# ---------------------------------------------------------------------------


def handle_idle(status: dict, dry_run: bool = False) -> None:
    task = status.get("task_name", "?")
    task_md = LOOP_DIR / "task.md"
    if _TEST_DISABLE_IDLE_AUTOLAUNCH:
        log("STATE", f"idle | task={task} | test mode — autolaunch disabled", dry_run)
        return
    if not task_md.exists():
        queue_dir = LOOP_DIR / "tasks"
        skip_names = {"env-001-install.md", "env-001-spec-tools.md"}
        queued = sorted(queue_dir.glob("*.md"), key=lambda p: p.name) if queue_dir.exists() else []
        runnable = [p for p in queued if p.name not in skip_names]
        if not runnable:
            log("STATE", f"idle | task={task} | no task.md and no runnable queued task — waiting", dry_run)
            return

        promote = runnable[0]
        promoted_name = promote.stem
        log("ACTION", f"promoting queued task {promote.name} → task.md", dry_run)
        if not dry_run:
            task_md.write_text(promote.read_text())
            promote.unlink()
            _write_status_raw({
                "task_name": promoted_name,
                "pass": 1,
                "approved": False,
                "block_reason": None,
                "parked_from": None,
                "parked_reason": None,
                "relaunch_attempted": False,
            })
            status = read_status() or status
            task = status.get("task_name", promoted_name)

    if task_md.exists():
        log("STATE", f"idle | task={task} | task.md present — transitioning to pc_turn", dry_run)
        log("TRANSITION", "idle → pc_turn", dry_run)
        if not dry_run:
            # Archive stale current/ artifacts before launching new Builder pass
            ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
            for artifact in (PC_OUTPUT, MAC_REVIEW, CLOSEOUT):
                if artifact.exists():
                    dst_name = f"{artifact.stem}_{task}_{ts}{artifact.suffix}"
                    dst = LOOP_DIR / "archive" / dst_name
                    artifact.rename(dst)
                    log("ACTION", f"archived {artifact.name} → archive/{dst_name}")
            write_status("pc_turn")
            _write_status_raw({"relaunch_attempted": False})
            subprocess.Popen(["bash", "/home/openclaw/polish_loop/run_polish_pass.sh"])
            log("ACTION", "launched Builder via run_polish_pass.sh")


def handle_pc_turn(status: dict, elapsed: float, dry_run: bool = False) -> None:
    task     = status.get("task_name", "?")
    pass_num = status.get("pass", 1)
    log("STATE", f"pc_turn | task={task} | pass={pass_num} | elapsed={elapsed:.0f}s", dry_run)

    # Check for valid output first
    if PC_OUTPUT.exists():
        valid, reason = pc_output_valid(pass_num)
        if valid:
            log("EVIDENCE", f"pc_output valid — PASS:{pass_num} matches", dry_run)
            log("TRANSITION", "pc_turn → mac_turn", dry_run)
            if not dry_run:
                write_status("mac_turn")
            return
        if reason == "stale":
            # Output exists with wrong pass number — explicit stale signal
            log("EVIDENCE", f"pc_output stale — file says PASS:{_read_output_pass()}, expected {pass_num}", dry_run)
            log("TRANSITION", "pc_turn → blocked (reason: stale_pc_output)", dry_run)
            if not dry_run:
                write_status("blocked", reason="stale_pc_output")
            return
        # Other invalid (no_pass_line, has_blocked, unreadable) — fall through to timeout logic
        log("STATE", f"pc_turn | pc_output invalid ({reason}) — checking agent status", dry_run)

    # Three-stage timeout check
    running = builder_running()
    if running:
        log("STATE", f"pc_turn | builder running — waiting", dry_run)
        return
    if elapsed < BUILDER_TIMEOUT:
        log("STATE", f"pc_turn | builder not running, elapsed {elapsed:.0f}s < {BUILDER_TIMEOUT}s — waiting", dry_run)
        return
    log("STATE", f"pc_turn | builder dead, elapsed {elapsed:.0f}s >= {BUILDER_TIMEOUT}s", dry_run)

    # Check if we already attempted a re-launch this pass
    relaunch_attempted = status.get("relaunch_attempted", False)

    if not relaunch_attempted:
        log("ACTION", "Attempting Builder re-launch before parking", dry_run)
        if not dry_run:
            launched = _relaunch_builder()
            if launched:
                log("ACTION", "Builder re-launched — resetting timeout, staying in pc_turn", dry_run)
                _write_status_raw({"relaunch_attempted": True})
                return
            else:
                log("ACTION", "Builder re-launch failed — parking", dry_run)
        else:
            return  # dry-run: would attempt re-launch

    log("TRANSITION", "pc_turn → parked (parked_from=pc_turn, reason=builder_timeout)", dry_run)
    if not dry_run:
        write_status("parked", parked_from="pc_turn", parked_reason="builder_timeout")


def _read_output_pass() -> int | str:
    """Helper: read PASS number from pc_output.md first line, or '?' on failure."""
    try:
        first = PC_OUTPUT.read_text().splitlines()[0]
        return int(first.split(":", 1)[1].strip())
    except Exception:
        return "?"


def handle_mac_turn(status: dict, elapsed: float, dry_run: bool = False) -> None:
    task     = status.get("task_name", "?")
    pass_num = status.get("pass", 1)
    log("STATE", f"mac_turn | task={task} | pass={pass_num} | elapsed={elapsed:.0f}s", dry_run)

    if not MAC_REVIEW.exists():
        if elapsed < PLANNER_TIMEOUT:
            log(
                "STATE",
                f"mac_turn | waiting for Planner review ({elapsed:.0f}s < {PLANNER_TIMEOUT}s)",
                dry_run,
            )
            return
        log("EVIDENCE", f"mac_turn | no mac_review.md after {elapsed:.0f}s", dry_run)
        log("TRANSITION", "mac_turn → blocked (reason: planner_timeout_no_review)", dry_run)
        if not dry_run:
            write_status("blocked", reason="planner_timeout_no_review")
        return

    approved = mac_review_says_approved()
    rework   = mac_review_says_rework()

    if approved and not rework:
        log("EVIDENCE", "mac_review: APPROVED", dry_run)
        log("TRANSITION", "mac_turn → approved", dry_run)
        if not dry_run:
            write_status("approved", approved=True)
        return

    if rework and not approved:
        if pass_num >= MAX_PASSES:
            log("EVIDENCE", f"mac_review: NEEDS_REWORK but pass {pass_num} >= MAX_PASSES {MAX_PASSES}", dry_run)
            log("TRANSITION", "mac_turn → blocked (reason: max_passes_exceeded)", dry_run)
            if not dry_run:
                write_status("blocked", reason="max_passes_exceeded")
        else:
            log("EVIDENCE", f"mac_review: NEEDS_REWORK — next pass {pass_num + 1}", dry_run)
            log("TRANSITION", f"mac_turn → pc_turn (pass {pass_num} → {pass_num + 1})", dry_run)
            if not dry_run:
                # Archive stale artifacts before next pass — mirrors handle_idle archiving
                ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
                task_name = status.get("task_name", "?")
                archive_dir = LOOP_DIR / "archive"
                archive_dir.mkdir(parents=True, exist_ok=True)
                for artifact in (PC_OUTPUT, MAC_REVIEW, CLOSEOUT):
                    if artifact.exists():
                        dst_name = f"{artifact.stem}_{task_name}_p{pass_num}_{ts}{artifact.suffix}"
                        dst = archive_dir / dst_name
                        artifact.rename(dst)
                        log("ACTION", f"archived {artifact.name} → archive/{dst_name}")
                write_status("pc_turn", pass_num=pass_num + 1)
        return

    # Ambiguous: neither APPROVED nor NEEDS_REWORK alone (or both together)
    log("EVIDENCE", "mac_review exists but ambiguous (neither APPROVED nor NEEDS_REWORK)", dry_run)
    log("TRANSITION", "mac_turn → blocked (reason: ambiguous_mac_review)", dry_run)
    if not dry_run:
        write_status("blocked", reason="ambiguous_mac_review")


def handle_approved(status: dict, dry_run: bool = False) -> None:
    task     = status.get("task_name", "?")
    pass_num = status.get("pass", 1)
    log("STATE", f"approved | task={task} | pass={pass_num}", dry_run)

    confirmed = closeout_confirmed(task, pass_num)
    if confirmed:
        log("EVIDENCE", f"closeout.ok confirmed — task={task} pass={pass_num}", dry_run)
    elif CLOSEOUT.exists():
        log("STATE", "approved | auto-closing despite unconfirmed closeout.ok", dry_run)
    else:
        log("STATE", "approved | auto-closing without closeout.ok", dry_run)

    log("TRANSITION", "approved → idle", dry_run)
    if not dry_run:
        # Archive task.md before writing idle — prevents re-launch on next poll
        ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        task_md = LOOP_DIR / "task.md"
        if task_md.exists():
            dst = LOOP_DIR / "archive" / f"task_{task}_{ts}.md"
            task_md.rename(dst)
            log("ACTION", f"archived task.md → archive/task_{task}_{ts}.md")
        # Archive current/ artifacts (pc_output, mac_review, closeout)
        for artifact in (PC_OUTPUT, MAC_REVIEW, CLOSEOUT):
            if artifact.exists():
                dst_name = f"{artifact.stem}_{task}_{ts}{artifact.suffix}"
                dst = LOOP_DIR / "archive" / dst_name
                artifact.rename(dst)
                log("ACTION", f"archived {artifact.name} → archive/{dst_name}")
        write_status("idle")
        refreshed = read_status()
        if refreshed is not None:
            handle_idle(refreshed, dry_run=False)


def handle_blocked(status: dict, dry_run: bool = False) -> None:
    reason = status.get("block_reason", "unknown")
    task   = status.get("task_name", "?")
    log("STATE", f"blocked | task={task} | reason={reason} — waiting for --reset-blocked", dry_run)


def handle_parked(status: dict, dry_run: bool = False) -> None:
    task        = status.get("task_name", "?")
    parked_from = status.get("parked_from", "")
    reason      = status.get("parked_reason", "unknown")
    log("STATE", f"parked | task={task} | from={parked_from} | reason={reason}", dry_run)

    if parked_from == "pc_turn":
        if builder_running():
            log("TRANSITION", "parked → pc_turn (Builder restarted)", dry_run)
            if not dry_run:
                write_status("pc_turn")
                _write_status_raw({"relaunch_attempted": False})
        else:
            log("STATE", "parked | waiting for Builder to restart", dry_run)
    elif parked_from == "mac_turn":
        # Planner is present (this code is running) — auto-resume immediately
        log("TRANSITION", "parked → mac_turn (Planner session active)", dry_run)
        if not dry_run:
            write_status("mac_turn")
    else:
        log("STATE", f"parked | unknown parked_from={parked_from!r} — use --resume to recover", dry_run)


# ---------------------------------------------------------------------------
# Main poll cycle
# ---------------------------------------------------------------------------


def run_one_cycle(dry_run: bool = False) -> dict | None:
    """Run one evaluation cycle. Returns status after handling."""
    status = read_status()

    if status is None:
        log("STATE", "status.json missing or invalid", dry_run)
        log("TRANSITION", "? → blocked (reason: invalid_or_missing_status)", dry_run)
        if not dry_run:
            # Write minimal blocked record (can't rely on existing content)
            now = datetime.datetime.now().isoformat()
            blocked = {
                "status": "blocked",
                "block_reason": "invalid_or_missing_status",
                "last_updated": now,
            }
            # Preserve task_name/pass if the file exists but has bad state
            if STATUS_FILE.exists():
                try:
                    raw = json.loads(STATUS_FILE.read_text())
                    if isinstance(raw, dict):
                        for k in ("task_name", "pass"):
                            if k in raw:
                                blocked[k] = raw[k]
                except Exception:
                    pass
            tmp = STATUS_FILE.with_suffix(".tmp")
            with open(tmp, "w") as f:
                json.dump(blocked, f, indent=2)
            tmp.rename(STATUS_FILE)
        return None

    state   = status["status"]
    elapsed = compute_elapsed(status)

    if state == "idle":
        handle_idle(status, dry_run)
    elif state == "pc_turn":
        handle_pc_turn(status, elapsed, dry_run)
    elif state == "mac_turn":
        handle_mac_turn(status, elapsed, dry_run)
    elif state == "approved":
        handle_approved(status, dry_run)
    elif state == "blocked":
        handle_blocked(status, dry_run)
    elif state == "parked":
        handle_parked(status, dry_run)

    return read_status()


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


def cmd_reset_blocked(reason: str) -> None:
    """Reset blocked → idle. Human-controlled only, requires reason."""
    status = read_status()
    if status is None:
        print("ERROR: status.json missing or invalid", file=sys.stderr)
        sys.exit(1)
    if status["status"] != "blocked":
        print(f"ERROR: current state is {status['status']!r}, not 'blocked'", file=sys.stderr)
        sys.exit(1)

    _write_status_raw({
        "status": "idle",
        "block_reason": None,
        "reset_reason": reason,
        "reset_at": datetime.datetime.now().isoformat(),
    })
    log("RESET", f"blocked → idle | reason: {reason}")
    print(f"Reset: blocked → idle (reason: {reason})")


def cmd_resume() -> None:
    """Manually resume from parked state → parked_from state."""
    status = read_status()
    if status is None:
        print("ERROR: cannot read status.json", file=sys.stderr)
        sys.exit(1)
    if status.get("status") != "parked":
        current = status.get("status", "?")
        print(f"ERROR: current state is {current!r}, not 'parked'", file=sys.stderr)
        sys.exit(1)
    parked_from = status.get("parked_from", "")
    if parked_from not in ("pc_turn", "mac_turn"):
        print(f"ERROR: unknown parked_from={parked_from!r} — cannot determine resume target", file=sys.stderr)
        sys.exit(1)
    write_status(parked_from)
    print(f"[resume] parked → {parked_from}")


def cmd_dry_run() -> None:
    """Print state machine evaluation, exit 0, write nothing."""
    print("[dry-run] Orchestrator dry run — no writes to status.json")
    status = read_status()
    if status is None:
        print("[dry-run] status.json: MISSING or INVALID")
        print("[dry-run] Would transition: ? → blocked (reason: invalid_or_missing_status)")
        sys.exit(0)
    state    = status["status"]
    pass_num = status.get("pass", 1)
    task     = status.get("task_name", "?")
    elapsed  = compute_elapsed(status)
    print(f"[dry-run] Current state: {state} | task={task} | pass={pass_num} | elapsed={elapsed:.0f}s")
    run_one_cycle(dry_run=True)
    print("[dry-run] Complete — no writes performed")
    sys.exit(0)


def cmd_run_tests() -> None:
    """Run the orchestrator test matrix against live files."""
    import copy

    global _TEST_DISABLE_IDLE_AUTOLAUNCH

    results:  list[str] = []
    failures: list[str] = []

    def check(label: str, condition: bool, note: str = "") -> None:
        if condition:
            results.append(f"  [PASS] {label}")
        else:
            msg = f"  [FAIL] {label}"
            if note:
                msg += f" — {note}"
            results.append(msg)
            failures.append(label)

    # ---- Save and restore real status.json --------------------------------
    original_status: str | None = None
    if STATUS_FILE.exists():
        original_status = STATUS_FILE.read_text()

    original_artifacts: dict[Path, str | None] = {}
    for p in (PC_OUTPUT, MAC_REVIEW, CLOSEOUT):
        original_artifacts[p] = p.read_text() if p.exists() else None

    CURRENT_DIR.mkdir(parents=True, exist_ok=True)

    def set_status(d: dict) -> None:
        STATUS_FILE.write_text(json.dumps(d, indent=2))

    def clear_status() -> None:
        if STATUS_FILE.exists():
            STATUS_FILE.unlink()

    def clear_artifacts() -> None:
        for p in (PC_OUTPUT, MAC_REVIEW, CLOSEOUT):
            if p.exists():
                p.unlink()

    now     = datetime.datetime.now()
    now_iso = now.isoformat()
    old_iso = (now - datetime.timedelta(seconds=BUILDER_TIMEOUT + 60)).isoformat()

    def fresh_status(**kwargs) -> dict:
        base = {"pass": 1, "task_name": "test-orch", "last_updated": now_iso, "approved": False}
        base.update(kwargs)
        return base

    try:
        _TEST_DISABLE_IDLE_AUTOLAUNCH = True

        # 1. status.json missing → blocked, invalid_or_missing_status
        clear_status()
        clear_artifacts()
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "status.json missing → blocked (invalid_or_missing_status)",
            s is not None and s["status"] == "blocked"
            and s.get("block_reason") == "invalid_or_missing_status",
            f"got {s}",
        )

        # 2. unknown status → blocked, invalid_or_missing_status
        set_status(fresh_status(status="unicorn"))
        clear_artifacts()
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "status = unknown string → blocked (invalid_or_missing_status)",
            s is not None and s["status"] == "blocked"
            and s.get("block_reason") == "invalid_or_missing_status",
            f"got {s}",
        )

        # 3. pc_turn, builder not running, elapsed < timeout → still pc_turn
        set_status(fresh_status(status="pc_turn", last_updated=now_iso))
        clear_artifacts()
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "pc_turn, elapsed < timeout, no output → still pc_turn (wait)",
            s is not None and s["status"] == "pc_turn",
            f"got {s}",
        )

        # 4. pc_turn, builder dead, elapsed > timeout → parked (builder_timeout)
        #    Force builder_running() to return False so the test is independent
        #    of whether run_polish_pass.sh happens to be running on this machine.
        #    Force _relaunch_builder() to return False so one cycle reaches parked.
        global _TEST_BUILDER_OVERRIDE, _TEST_RELAUNCH_OVERRIDE
        _TEST_BUILDER_OVERRIDE = False
        _TEST_RELAUNCH_OVERRIDE = False
        set_status(fresh_status(status="pc_turn", last_updated=old_iso))
        clear_artifacts()
        run_one_cycle(dry_run=False)
        _TEST_BUILDER_OVERRIDE = None
        _TEST_RELAUNCH_OVERRIDE = None
        s = read_status()
        check(
            "pc_turn, builder dead, elapsed > timeout → parked (builder_timeout)",
            s is not None and s["status"] == "parked"
            and s.get("parked_from") == "pc_turn",
            f"got {s}",
        )

        # 5. pc_turn, valid pc_output → mac_turn
        set_status(fresh_status(status="pc_turn", **{"pass": 2, "last_updated": now_iso}))
        PC_OUTPUT.write_text("PASS: 2\nSTATUS: DONE\n\nCHANGES:\ntest\n")
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "pc_turn, valid pc_output → mac_turn",
            s is not None and s["status"] == "mac_turn",
            f"got {s}",
        )
        PC_OUTPUT.unlink(missing_ok=True)

        # 6. pc_turn, pc_output PASS mismatch → blocked (stale_pc_output)
        set_status(fresh_status(status="pc_turn", **{"pass": 3, "last_updated": now_iso}))
        PC_OUTPUT.write_text("PASS: 2\nSTATUS: DONE\n")
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "pc_turn, pc_output PASS mismatch → blocked (stale_pc_output)",
            s is not None and s["status"] == "blocked"
            and s.get("block_reason") == "stale_pc_output",
            f"got {s}",
        )
        PC_OUTPUT.unlink(missing_ok=True)

        # 7. mac_turn, no mac_review, elapsed < timeout → still mac_turn
        set_status(fresh_status(status="mac_turn", last_updated=now_iso))
        clear_artifacts()
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "mac_turn, no mac_review, elapsed < timeout → still mac_turn (wait)",
            s is not None and s["status"] == "mac_turn",
            f"got {s}",
        )

        # 8. mac_turn, no mac_review, elapsed > timeout → blocked (planner_timeout_no_review)
        set_status(fresh_status(status="mac_turn", last_updated=old_iso))
        clear_artifacts()
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "mac_turn, no mac_review, elapsed > timeout → blocked (planner_timeout_no_review)",
            s is not None and s["status"] == "blocked"
            and s.get("block_reason") == "planner_timeout_no_review",
            f"got {s}",
        )

        # 9. mac_turn, ambiguous mac_review → blocked (ambiguous_mac_review)
        set_status(fresh_status(status="mac_turn", last_updated=now_iso))
        MAC_REVIEW.write_text("This review says nothing definitive.\n")
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "mac_turn, ambiguous mac_review → blocked (ambiguous_mac_review)",
            s is not None and s["status"] == "blocked"
            and s.get("block_reason") == "ambiguous_mac_review",
            f"got {s}",
        )
        MAC_REVIEW.unlink(missing_ok=True)

        # 10. mac_turn, NEEDS_REWORK, pass >= MAX_PASSES → blocked (max_passes_exceeded)
        set_status(fresh_status(status="mac_turn", **{"pass": MAX_PASSES, "last_updated": now_iso}))
        MAC_REVIEW.write_text("NEEDS_REWORK\nSome issues found.\n")
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            f"mac_turn, NEEDS_REWORK, pass={MAX_PASSES} >= MAX_PASSES → blocked (max_passes_exceeded)",
            s is not None and s["status"] == "blocked"
            and s.get("block_reason") == "max_passes_exceeded",
            f"got {s}",
        )
        MAC_REVIEW.unlink(missing_ok=True)

        # 11. approved, no closeout.ok → idle (auto-close)
        set_status(fresh_status(status="approved", approved=True, last_updated=now_iso))
        clear_artifacts()
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "approved, no closeout.ok → idle (auto-close)",
            s is not None and s["status"] == "idle",
            f"got {s}",
        )

        # 12. --reset-blocked with reason → idle
        set_status(fresh_status(status="blocked", block_reason="test_block", last_updated=now_iso))
        cmd_reset_blocked("Builder auth expired — re-authed")
        s = read_status()
        check(
            "--reset-blocked with reason → idle",
            s is not None and s["status"] == "idle",
            f"got {s}",
        )

        # 13. dry_run=True writes nothing
        set_status(fresh_status(status="mac_turn", last_updated=now_iso))
        MAC_REVIEW.write_text("APPROVED\n")
        before = STATUS_FILE.read_text()
        run_one_cycle(dry_run=True)
        after = STATUS_FILE.read_text()
        check(
            "--dry-run (run_one_cycle dry_run=True) writes nothing",
            before == after,
            "status.json changed during dry run",
        )
        MAC_REVIEW.unlink(missing_ok=True)

        # 14. mac_turn, APPROVED → approved
        set_status(fresh_status(status="mac_turn", last_updated=now_iso))
        MAC_REVIEW.write_text("Some analysis.\nAPPROVED\nNo issues.\n")
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "mac_turn, APPROVED → approved",
            s is not None and s["status"] == "approved",
            f"got {s}",
        )
        MAC_REVIEW.unlink(missing_ok=True)

        # 15. mac_turn, NEEDS_REWORK, pass < MAX_PASSES → pc_turn (pass incremented)
        set_status(fresh_status(status="mac_turn", **{"pass": 1, "last_updated": now_iso}))
        MAC_REVIEW.write_text("NEEDS_REWORK\nFix these issues.\n")
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "mac_turn, NEEDS_REWORK, pass < MAX_PASSES → pc_turn (pass++)",
            s is not None and s["status"] == "pc_turn" and s.get("pass") == 2,
            f"got {s}",
        )
        MAC_REVIEW.unlink(missing_ok=True)

        # 16. approved + valid closeout.ok → idle
        set_status(fresh_status(status="approved", **{"pass": 1, "task_name": "test-orch", "approved": True}))
        closeout_payload = {
            "task_name": "test-orch",
            "pass": 1,
            "confirmed_at": now_iso,
        }
        CLOSEOUT.write_text(json.dumps(closeout_payload))
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "approved + valid closeout.ok → idle",
            s is not None and s["status"] == "idle",
            f"got {s}",
        )
        CLOSEOUT.unlink(missing_ok=True)

        # 17. approved + malformed closeout.ok → idle (ERROR logged, not stuck-silent)
        set_status(fresh_status(status="approved", **{"pass": 1, "task_name": "test-orch", "approved": True}))
        CLOSEOUT.write_text("this is plain text, not json")
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "approved + malformed closeout.ok → idle (ERROR logged)",
            s is not None and s["status"] == "idle",
            f"got {s}",
        )
        CLOSEOUT.unlink(missing_ok=True)

        # 16. pc_turn, builder dead, elapsed > BUILDER_TIMEOUT → parked
        set_status(fresh_status(status="pc_turn", **{"pass": 1, "task_name": "test-orch", "last_updated": old_iso}))
        _TEST_BUILDER_OVERRIDE = False
        _TEST_RELAUNCH_OVERRIDE = False
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "pc_turn, builder dead, elapsed > BUILDER_TIMEOUT → parked",
            s is not None and s["status"] == "parked" and s.get("parked_from") == "pc_turn",
            f"got {s}",
        )
        _TEST_BUILDER_OVERRIDE = None
        _TEST_RELAUNCH_OVERRIDE = None

        # 17. parked (pc_turn) + builder running → pc_turn
        set_status(fresh_status(status="parked", **{"pass": 1, "task_name": "test-orch", "parked_from": "pc_turn", "parked_reason": "builder_timeout"}))
        _TEST_BUILDER_OVERRIDE = True
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "parked (pc_turn) + builder running → pc_turn",
            s is not None and s["status"] == "pc_turn",
            f"got {s}",
        )
        _TEST_BUILDER_OVERRIDE = None

        # 18. parked (mac_turn) → mac_turn (auto-resume, Planner is here)
        set_status(fresh_status(status="parked", **{"pass": 1, "task_name": "test-orch", "parked_from": "mac_turn", "parked_reason": "planner_timeout"}))
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "parked (mac_turn) → mac_turn (auto-resume)",
            s is not None and s["status"] == "mac_turn",
            f"got {s}",
        )

    finally:
        _TEST_DISABLE_IDLE_AUTOLAUNCH = False
        # Restore original state
        if original_status is not None:
            STATUS_FILE.write_text(original_status)
        elif STATUS_FILE.exists():
            STATUS_FILE.unlink()
        for p, content in original_artifacts.items():
            if content is not None:
                p.write_text(content)
            elif p.exists():
                p.unlink()

    # Print results  (count is dynamic — len(results) reflects actual run)
    total = len(results)
    print(f"\nOrchestrator Test Matrix — {total} checks")
    for r in results:
        print(r)
    if failures:
        print(f"\nFAILED: {len(failures)} / {total}")
        sys.exit(1)
    else:
        print(f"\nAll {total} tests passed.")
        sys.exit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenClaw Polish Loop Orchestrator")
    parser.add_argument("--dry-run",       action="store_true", help="Print eval, exit 0, write nothing")
    parser.add_argument("--reset-blocked", action="store_true", help="Reset blocked → idle (requires --reason)")
    parser.add_argument("--reason",        type=str,            help="Reason string for --reset-blocked")
    parser.add_argument("--resume",        action="store_true", help="Resume from parked state → parked_from state")
    parser.add_argument("--run-tests",     action="store_true", help="Run orchestrator test matrix")
    parser.add_argument("--once",          action="store_true", help="Run one poll cycle then exit")
    parser.add_argument("--loop",          action="store_true", help="Continuous poll loop (default)")
    args = parser.parse_args()

    if args.dry_run:
        cmd_dry_run()
        return

    if args.reset_blocked:
        if not args.reason:
            print("ERROR: --reset-blocked requires --reason", file=sys.stderr)
            sys.exit(1)
        cmd_reset_blocked(args.reason)
        return

    if args.resume:
        cmd_resume()
        sys.exit(0)

    if args.run_tests:
        cmd_run_tests()
        return

    if args.once:
        run_one_cycle()
        return

    # Default / --loop: continuous poll
    log("INIT", (
        f"Orchestrator starting — poll={POLL_INTERVAL}s "
        f"builder_timeout={BUILDER_TIMEOUT}s "
        f"planner_timeout={PLANNER_TIMEOUT}s "
        f"max_passes={MAX_PASSES}"
    ))
    while True:
        run_one_cycle()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
