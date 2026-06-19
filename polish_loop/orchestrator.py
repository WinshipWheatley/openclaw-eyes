#!/usr/bin/env python3
"""
orchestrator.py — Central loop controller for the OpenClaw polish loop.

Phase-C default: one quiescent SQLite-ledger event and exit.
Legacy status.json handlers remain explicit under --legacy-once/--run-tests.

Usage:
    python3 orchestrator.py           # one Phase-C ledger event and exit
    python3 orchestrator.py --once    # same as default
    python3 orchestrator.py --legacy-once  # one legacy status.json cycle and exit
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

# Notification support
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) in sys.path:
    sys.path.remove(str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT))
try:
    import chief_notify as _chief_notify
    _NOTIFY_AVAILABLE = True
except ImportError:
    _NOTIFY_AVAILABLE = False

# PC-side review fallback — used when Mac planner cannot launch
try:
    from pc_review_fallback import run_review as _pc_review_run
    import pc_review_fallback as _pc_review_mod
    _PC_REVIEW_AVAILABLE = True
except ImportError:
    # Fallback: add script directory to path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from pc_review_fallback import run_review as _pc_review_run
        import pc_review_fallback as _pc_review_mod
        _PC_REVIEW_AVAILABLE = True
    except ImportError:
        _PC_REVIEW_AVAILABLE = False
        _pc_review_run = None  # type: ignore[assignment]
        _pc_review_mod = None  # type: ignore[assignment]

# Phase-C deterministic control plane. The legacy status.json handlers below
# remain for existing repair tooling/tests; the CLI entrypoint now defaults to
# one quiescent ledger event rather than a daemon poll.
try:
    from control_plane import (
        DEFAULT_LEDGER_PATH,
        ControlPlaneLedger,
        DispatchResult,
        TaskLease,
        run_control_plane_once,
    )
    _PHASE_C_AVAILABLE = True
except ImportError:
    DEFAULT_LEDGER_PATH = Path("/home/openclaw/polish_loop/control_plane.sqlite3")
    ControlPlaneLedger = None  # type: ignore[assignment]
    DispatchResult = None  # type: ignore[assignment]
    TaskLease = None  # type: ignore[assignment]
    run_control_plane_once = None  # type: ignore[assignment]
    _PHASE_C_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants (configurable)
# ---------------------------------------------------------------------------

POLL_INTERVAL    = 15    # seconds between poll cycles (faster state reaction)
BUILDER_TIMEOUT  = 600   # 10 min — block if Builder dead and no output
PLANNER_TIMEOUT  = 600   # 10 min — block if Planner gone and no review
MAX_PASSES       = 3     # block if task needs a 4th pass

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

LOOP_DIR     = Path("/home/openclaw/polish_loop")
AUDIT_LOCK   = LOOP_DIR / ".audit_lock"
STATUS_FILE  = LOOP_DIR / "status.json"
CURRENT_DIR  = LOOP_DIR / "current"
PC_OUTPUT    = CURRENT_DIR / "pc_output.md"
MAC_REVIEW   = CURRENT_DIR / "mac_review.md"
CLOSEOUT     = CURRENT_DIR / "closeout.ok"
TASK_MD      = LOOP_DIR / "task.md"
LOG_FILE     = Path("/mnt/c/OpenClaw/logs/orchestrator.log")
WATCHER_LOG  = Path("/home/openclaw/mac_eyes/sync/watcher.log")
BUILDER_LOG  = Path("/mnt/c/OpenClaw/logs/builder_watcher.out")
BUILDER_PID_FILE = LOOP_DIR / "builder.pid"
STAGING_ROOT = Path("/home/openclaw/staging")

VALID_STATES = {"idle", "pc_turn", "mac_turn", "approved", "blocked", "parked"}
WATCHER_TS_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")
WATCHER_RUNNER_FAILURE_TOKENS = (
    "no planner runner found",
    "command not found",
)
TASK_FRONTMATTER_FIELD_RE = re.compile(r"^(title|goal):\s*\S.*$", re.MULTILINE)
TASK_TITLE_RE = re.compile(r"^title:\s*(\S.*)$", re.MULTILINE)
MAC_REVIEW_HEADER_RE = re.compile(r"^#\s*Mac Review\s+[—-]\s*(.+?)\s+Pass\s+(\d+)\s*$", re.MULTILINE)

# Cassandra extension architecture lock:
# Future tool/capability additions must be implemented in cassandra_custom_tools.py,
# not by adding feature logic directly inside cassandra_brain.py.
_CASSANDRA_TOOL_ARCH_LOCK_MSG = (
    "cassandra tool/capability tasks must use cassandra_custom_tools.py; "
    "direct cassandra_brain.py feature additions are forbidden"
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def log(tag: str, msg: str, dry_run: bool = False) -> None:
    ts   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = "[dry-run] " if dry_run else ""
    line  = f"[{ts}] [{tag}] {prefix}{msg}"
    print(line)
    if dry_run or _TEST_SUPPRESS_FILE_LOGS:
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
        # Clear stale block_reason and notification flag when leaving blocked or parked
        updates["block_reason"] = None
        updates["blocked_notified"] = False
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
    reason values: "missing" | "empty" | "no_pass_line" | "stale" | "quality_gate".
    Returns (True, "blocked") for a syntactically valid terminal BLOCKED output.
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
    # Accept optional RUNNER: header
    runner_used = None
    first = lines[0].strip()
    if first.upper().startswith("RUNNER:"):
        runner_used = first.split(":", 1)[1].strip()
        if len(lines) < 2:
            return False, "no_pass_line"
        first = lines[1].strip()
    if not first.upper().startswith("PASS:"):
        return False, "no_pass_line"
    try:
        found = int(first.split(":", 1)[1].strip())
    except (ValueError, IndexError):
        return False, "no_pass_line"
    if found != expected_pass:
        return False, "stale"
    required_headers = ("CHANGES:", "REASONING:", "ROLLBACK PLAN:", "COST:", "TRUTH:", "HEADROOM:")
    upper = content.upper()
    for header in required_headers:
        if header not in upper:
            return False, "quality_gate"

    # Log runner used for evidence
    if runner_used:
        log("EVIDENCE", f"pc_output RUNNER: {runner_used}")

    if re.search(r"^\s*STATUS:\s*BLOCKED\s*$", content, re.IGNORECASE | re.MULTILINE):
        return True, "blocked"

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


def mac_review_identity() -> tuple[str, int] | None:
    """Return review header task/pass when mac_review.md declares them."""
    if not MAC_REVIEW.exists():
        return None
    try:
        content = MAC_REVIEW.read_text()
    except Exception:
        return None
    match = MAC_REVIEW_HEADER_RE.search(content)
    if not match:
        return None
    return match.group(1).strip(), int(match.group(2))


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


def active_task_identity(fallback: str = "?") -> str:
    """Return task.md title when available; otherwise keep the provided fallback."""
    task_md = TASK_MD
    if not task_md.exists():
        return fallback
    try:
        content = task_md.read_text()
    except Exception:
        return fallback
    match = TASK_TITLE_RE.search(content)
    if not match:
        return fallback
    title = match.group(1).strip()
    return title or fallback


def _active_task_frontmatter_value(key: str) -> str | None:
    task_md = TASK_MD
    if not task_md.exists():
        return None
    wanted = f"{key.lower()}:"
    try:
        for raw in task_md.read_text().splitlines():
            stripped = raw.strip()
            if stripped.lower().startswith(wanted):
                return stripped.split(":", 1)[1].strip()
    except Exception:
        return None
    return None


def _active_task_is_harness_backed_retest() -> bool:
    return (
        _active_task_frontmatter_value("execution_mode") == "harness-backed-retest"
        and _active_task_frontmatter_value("harness_mode") == "dry-run"
    )


def _chief_acceptance_verdict(status: dict) -> str:
    """Ask Chief to evaluate harness/review evidence. Returns APPROVE|REWORK|INSUFFICIENT_EVIDENCE."""
    try:
        from chief_acceptance_gate import evaluate_evidence
    except ImportError:
        return "INSUFFICIENT_EVIDENCE"
    pc_summary = ""
    if PC_OUTPUT.exists():
        try:
            pc_summary = PC_OUTPUT.read_text(errors="replace")[:500]
        except Exception:
            pass
    evidence = {
        "task_name": status.get("task_name", "?"),
        "pass_num": status.get("pass", 1),
        "pc_output_summary": pc_summary,
        "mac_review_verdict": "APPROVED",
        "harness_manifest": _latest_harness_manifest(status),
    }
    return evaluate_evidence(evidence)


def _latest_harness_manifest(status: dict) -> dict | None:
    """Best-effort lookup of the most recent harness run manifest for the active task."""
    flow = _active_task_frontmatter_value("harness_flow")
    if not flow:
        return None
    flow_dirs = {
        "morning_brief": "morning_brief_harness",
        "chief_end_of_day_review": "chief_eod_harness",
        "guardian_schema_retest": "guardian_schema_harness",
    }
    dir_name = flow_dirs.get(flow)
    if not dir_name:
        return None
    runs_dir = STAGING_ROOT / dir_name / "runs"
    if not runs_dir.exists():
        return None
    try:
        run_dirs = sorted(
            (d for d in runs_dir.iterdir() if d.is_dir()),
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
    except Exception:
        return None
    if not run_dirs:
        return None
    manifest_path = run_dirs[0] / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {
            "harness_name": m.get("harness_name"),
            "task_name": m.get("task_name"),
            "flow": m.get("flow", flow),
            "generated_at": m.get("generated_at"),
            "passed": m.get("passed"),
            "failed": m.get("failed"),
            "total_cases": m.get("total_cases"),
            "checks": m.get("checks") if isinstance(m.get("checks"), list) else [],
        }
    except Exception:
        return None


def queued_task_frontmatter_error(task_path: Path) -> str | None:
    """Return a brief validation error if a queued task is missing required frontmatter."""
    try:
        content = task_path.read_text()
    except Exception as exc:
        return f"unreadable task file ({exc})"

    found_fields = {match.group(1) for match in TASK_FRONTMATTER_FIELD_RE.finditer(content)}
    missing_fields = [field for field in ("title", "goal") if field not in found_fields]
    if missing_fields:
        return f"missing required frontmatter field(s): {', '.join(missing_fields)}"

    lower = content.lower()
    mentions_cassandra_feature_work = (
        "cassandra" in lower and any(k in lower for k in ("tool", "tools", "capability", "capabilities", "feature"))
    )
    attempts_direct_brain_edit = "cassandra_brain.py" in lower
    allows_custom_tools_path = "cassandra_custom_tools.py" in lower
    if mentions_cassandra_feature_work and attempts_direct_brain_edit and not allows_custom_tools_path:
        return _CASSANDRA_TOOL_ARCH_LOCK_MSG

    return None


def queued_task_autonomous_skip_reason(task_path: Path) -> str | None:
    """Return a brief reason when a queued task explicitly requires human-supervised execution."""
    try:
        content = task_path.read_text()
    except Exception:
        return None

    lower = content.lower()
    if "execution mode:" in lower and "human-supervised" in lower:
        return "human-supervised execution mode"
    if "assigned to:" in lower and "human-supervised" in lower:
        return "assigned to human-supervised work"
    if "not suitable for unattended autonomous execution" in lower:
        return "not suitable for unattended autonomous execution"
    return None


def audit_lock_active() -> bool:
    """True when queue-generation must be frozen for audit mode."""
    return AUDIT_LOCK.exists()


# ---------------------------------------------------------------------------
# Agent process detection
# ---------------------------------------------------------------------------

# Set to True/False in tests to override real process check.
_TEST_BUILDER_OVERRIDE: bool | None = None

# Set to True/False in tests to override _relaunch_builder() return value.
_TEST_RELAUNCH_OVERRIDE: bool | None = None

# Set to True in tests to keep idle-state queue promotion from touching live tasks.
_TEST_DISABLE_IDLE_AUTOLAUNCH: bool = False

# Set to True during self-tests to prevent synthetic transitions from polluting
# the live orchestrator operations log.
_TEST_SUPPRESS_FILE_LOGS: bool = False

# Override watcher log path during self-tests.
_TEST_WATCHER_LOG_OVERRIDE: Path | None = None

# Set to True during tests to disable the PC-side review fallback in handle_mac_turn.
_TEST_DISABLE_PC_REVIEW_FALLBACK: bool = False

# Set to True during tests to suppress self-heal task creation side effects.
_TEST_DISABLE_SELF_HEAL_TASKS: bool = False


def _pid_is_live(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/status") as f:
            state = ""
            for line in f:
                if line.startswith("State:"):
                    state = line
                    break
        if "T (stopped)" in state or "Z (zombie)" in state:
            log("WARN", f"Builder PID {pid} exists but is not runnable: {state.strip()}")
            return False
        return bool(state)
    except (OSError, IOError, ValueError):
        return False


def builder_running() -> bool:
    """True when the builder PID file points to a live runner process."""
    if _TEST_BUILDER_OVERRIDE is not None:
        return _TEST_BUILDER_OVERRIDE
    try:
        raw = BUILDER_PID_FILE.read_text(encoding="utf-8").strip()
        pid = int(raw)
    except (OSError, ValueError):
        return False
    return _pid_is_live(pid)


def _relaunch_builder() -> bool:
    """Signal builder_watcher to re-launch by toggling status through idle and back.

    builder_watcher detects pc_turn transitions (LAST_STATE != pc_turn → pc_turn)
    and launches the next runner.  A brief idle→pc_turn toggle triggers this.
    Returns True if the toggle was written successfully.
    """
    if _TEST_RELAUNCH_OVERRIDE is not None:
        return _TEST_RELAUNCH_OVERRIDE
    try:
        # Brief idle pulse so builder_watcher sees a fresh pc_turn transition
        _write_status_raw({"status": "idle"})
        import time
        time.sleep(0.5)
        _write_status_raw({"status": "pc_turn"})
        log("ACTION", "toggled idle→pc_turn to signal builder_watcher relaunch")
        return True
    except Exception as e:
        log("ERROR", f"Builder re-launch signal failed: {e}")
        return False


def _watcher_log_path() -> Path:
    """Return the watcher log path, allowing test overrides."""
    return _TEST_WATCHER_LOG_OVERRIDE or WATCHER_LOG


def _parse_watcher_timestamp(line: str) -> datetime.datetime | None:
    """Parse leading [YYYY-MM-DD HH:MM:SS] timestamps from watcher.log lines."""
    match = WATCHER_TS_RE.match(line)
    if not match:
        return None
    try:
        return datetime.datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def planner_runner_missing_since(status: dict) -> bool:
    """
    True when watcher.log recorded a Planner runner startup failure after the
    current mac_turn began. This lets the loop fail fast instead of waiting for
    the generic planner timeout.
    """
    watcher_log = _watcher_log_path()
    if not watcher_log.exists():
        return False

    since_raw = status.get("last_updated")
    try:
        since = datetime.datetime.fromisoformat(since_raw) if since_raw else None
    except Exception:
        since = None
    if since is not None and since.tzinfo is not None:
        since = since.astimezone().replace(tzinfo=None)
    if since is not None:
        since = since.replace(microsecond=0)

    try:
        lines = watcher_log.read_text(encoding="utf-8", errors="ignore").splitlines()[-300:]
    except Exception:
        return False

    # Track the most recent timestamp seen, so that lines without timestamps
    # (e.g. raw bash "command not found") inherit the timestamp of the
    # preceding line.
    last_seen_ts: datetime.datetime | None = None

    for line in lines:
        line_ts = _parse_watcher_timestamp(line)
        if line_ts is not None:
            last_seen_ts = line_ts

        lower = line.lower()
        if not any(token in lower for token in WATCHER_RUNNER_FAILURE_TOKENS):
            continue

        effective_ts = line_ts if line_ts is not None else last_seen_ts
        if since is not None:
            if effective_ts is None or effective_ts < since:
                continue
        return True

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
        archive_dir = LOOP_DIR / "archive"
        skip_names = {"env-001-install.md", "env-001-spec-tools.md"}

        # Build set of already-completed task names from archive
        completed_names: set[str] = set()
        if archive_dir.exists():
            for archived in archive_dir.glob("task_*"):
                # Archive format: task_{task_name}_{timestamp}.md
                parts = archived.stem.split("_", 1)
                if len(parts) > 1:
                    # Remove trailing _YYYYMMDDTHHMMSSz suffix
                    name_part = parts[1].rsplit("_", 1)[0]
                    completed_names.add(name_part)

        queued = sorted(queue_dir.glob("*.md"), key=lambda p: p.name) if queue_dir.exists() else []
        runnable = [
            p for p in queued
            if p.name not in skip_names and p.stem not in completed_names
        ]
        if not runnable:
            log("STATE", f"idle | task={task} | no task.md and no runnable queued task — waiting", dry_run)
            return

        for promote in runnable:
            validation_error = queued_task_frontmatter_error(promote)
            if validation_error:
                log("WARN", f"skipping queued task {promote.name}: {validation_error}", dry_run)
                continue
            autonomous_skip_reason = queued_task_autonomous_skip_reason(promote)
            if autonomous_skip_reason:
                log("WARN", f"skipping queued task {promote.name}: {autonomous_skip_reason}", dry_run)
                continue

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
            break
        else:
            log(
                "STATE",
                f"idle | task={task} | queued tasks invalid or skipped — waiting",
                dry_run,
            )
            return

    if task_md.exists():
        log("STATE", f"idle | task={task} | task.md present — transitioning to pc_turn", dry_run)
        log("TRANSITION", "idle → pc_turn", dry_run)
        if not dry_run:
            # Archive stale current/ artifacts before launching new Builder pass
            ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
            for artifact in (PC_OUTPUT, MAC_REVIEW, CLOSEOUT):
                if artifact.exists():
                    dst_name = f"{artifact.stem}_{task}_{ts}{artifact.suffix}"
                    dst = LOOP_DIR / "archive" / dst_name
                    artifact.rename(dst)
                    log("ACTION", f"archived {artifact.name} → archive/{dst_name}")
            write_status("pc_turn")
            _write_status_raw({"relaunch_attempted": False})
            # Builder launch is delegated to builder_watcher.sh (running as a
            # separate daemon).  It detects pc_turn transitions and handles
            # runner selection, fallback cascade, cost tracking, and output
            # validation.  Launching via run_polish_pass.sh here created a
            # dual-launch race and bypassed the smart runner pipeline.
            log("ACTION", "pc_turn set — builder_watcher will launch Builder")


def handle_pc_turn(status: dict, elapsed: float, dry_run: bool = False) -> None:
    task     = status.get("task_name", "?")
    pass_num = status.get("pass", 1)
    log("STATE", f"pc_turn | task={task} | pass={pass_num} | elapsed={elapsed:.0f}s", dry_run)
    archive_task = active_task_identity(task)

    # Check for valid output first
    if PC_OUTPUT.exists():
        valid, reason = pc_output_valid(pass_num)
        if valid:
            if reason == "blocked":
                log("EVIDENCE", f"pc_output terminal BLOCKED — PASS:{pass_num} matches", dry_run)
                log("TRANSITION", "pc_turn → blocked (reason: builder_reported_blocked)", dry_run)
                if not dry_run:
                    write_status("blocked", reason="builder_reported_blocked")
                return
            log("EVIDENCE", f"pc_output valid — PASS:{pass_num} matches", dry_run)
            log("TRANSITION", "pc_turn → mac_turn", dry_run)
            if not dry_run:
                write_status("mac_turn")
            return
        running_now = builder_running()
        if reason == "stale":
            found_pass = _read_output_pass()
            if running_now:
                log(
                    "STATE",
                    f"pc_turn | stale pc_output detected while Builder is still running "
                    f"(file PASS:{found_pass}, expected {pass_num}) — waiting",
                    dry_run,
                )
                return
            if not status.get("relaunch_attempted", False):
                log(
                    "ACTION",
                    f"pc_output stale (file PASS:{found_pass}, expected {pass_num}) and Builder is dead — "
                    "archiving stale output and re-launching once",
                    dry_run,
                )
                if not dry_run:
                    _archive_current_artifact(PC_OUTPUT, archive_task, "stale")
                    launched = _relaunch_builder()
                    if launched:
                        _write_status_raw({"relaunch_attempted": True})
                        return
                else:
                    return
            log("EVIDENCE", f"pc_output stale — file says PASS:{found_pass}, expected {pass_num}", dry_run)
            log("TRANSITION", "pc_turn → blocked (reason: stale_pc_output)", dry_run)
            if not dry_run:
                write_status("blocked", reason="stale_pc_output")
            return
        if reason == "quality_gate":
            if running_now:
                log(
                    "STATE",
                    "pc_output missing required sections while Builder is still running — waiting for final output",
                    dry_run,
                )
                return
            if not status.get("relaunch_attempted", False):
                log(
                    "ACTION",
                    "pc_output failed quality gate and Builder is dead — archiving invalid output and re-launching once",
                    dry_run,
                )
                if not dry_run:
                    _archive_current_artifact(PC_OUTPUT, archive_task, "quality_gate")
                    launched = _relaunch_builder()
                    if launched:
                        _write_status_raw({"relaunch_attempted": True})
                        return
                else:
                    return
            log("EVIDENCE", "pc_output failed quality gate (missing required narrative/reporting sections)", dry_run)
            log("TRANSITION", "pc_turn → blocked (reason: weak_pc_output_quality)", dry_run)
            if not dry_run:
                write_status("blocked", reason="weak_pc_output_quality")
            return
        # Other invalid (no_pass_line, unreadable) — fall through to timeout logic
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

    log("TRANSITION", "pc_turn → idle (self-heal skip after repeated builder failure)", dry_run)
    if not dry_run:
        recovery_task = _queue_manus_recovery_task(archive_task, "builder_timeout_after_retry")
        if recovery_task:
            log("ACTION", f"queued self-heal recovery task: {recovery_task}")
        _skip_failed_task_to_next(archive_task, pass_num, "builder_timeout")


def _read_output_pass() -> int | str:
    """Helper: read PASS number from pc_output.md first line, or '?' on failure."""
    try:
        lines = PC_OUTPUT.read_text().splitlines()
        if not lines:
            return "?"
        first = lines[0].strip()
        if first.upper().startswith("RUNNER:") and len(lines) > 1:
            first = lines[1].strip()
        if not first.upper().startswith("PASS:"):
            return "?"
        return int(first.split(":", 1)[1].strip())
    except Exception:
        return "?"


def _archive_current_artifact(path: Path, task: str, suffix: str) -> None:
    """Move a transient current/ artifact into archive/ with a reason suffix."""
    if not path.exists():
        return
    archive_dir = LOOP_DIR / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
    dst_name = f"{path.stem}_{task}_{suffix}_{ts}{path.suffix}"
    path.rename(archive_dir / dst_name)
    log("ACTION", f"archived {path.name} → archive/{dst_name}")


def _next_auto_gen_task_name() -> str:
    """Allocate next available auto-gen-XXX id across queue and archive."""
    queue_dir = LOOP_DIR / "tasks"
    archive_dir = LOOP_DIR / "archive"
    used: set[int] = set()

    def _collect(value: str) -> None:
        m = re.search(r"auto-gen-(\d{3})", value)
        if m:
            used.add(int(m.group(1)))

    if queue_dir.exists():
        for p in queue_dir.glob("auto-gen-*.md"):
            _collect(p.stem)
    if archive_dir.exists():
        for p in archive_dir.glob("task_auto-gen-*.md"):
            _collect(p.stem)

    i = 1
    while i in used:
        i += 1
    return f"auto-gen-{i:03d}"


def _latest_error_excerpt(max_lines: int = 6) -> str:
    """Extract recent error signatures to seed self-heal follow-up tasks."""
    hits: list[str] = []
    for path in (BUILDER_LOG, LOG_FILE):
        if not path.exists():
            continue
        try:
            tail = path.read_text(errors="replace").splitlines()[-300:]
        except Exception:
            continue
        for ln in tail:
            low = ln.lower()
            if any(tok in low for tok in ("error", "exception", "traceback", "failed", "timeout")):
                hits.append(ln.strip())
    if not hits:
        return "No explicit error signature captured; inspect latest builder timeout context."
    return " | ".join(hits[-max_lines:])[:1200]


def _queue_manus_recovery_task(failed_task: str, reason: str) -> str | None:
    """Queue a bounded Manus/doc-search recovery task and return task name."""
    if _TEST_DISABLE_SELF_HEAL_TASKS:
        return None
    # Guard: never self-heal a recovery task, or failures can recurse forever.
    if "manus-recovery" in failed_task or re.match(r"auto-gen-\d+", failed_task):
        log(
            "WARN",
            f"Skipping self-heal for '{failed_task}' because it is already a recovery task; cascading would create an infinite loop",
        )
        return None
    if audit_lock_active():
        log("STATE", "Audit lock active — refusing to queue recovery task")
        return None
    try:
        queue_dir = LOOP_DIR / "tasks"
        queue_dir.mkdir(parents=True, exist_ok=True)
        task_name = f"{_next_auto_gen_task_name()}-manus-recovery"
        excerpt = _latest_error_excerpt()
        body = (
            f"title: {task_name}\n"
            f"profile: standard\n"
            f"goal: Diagnose '{failed_task}' failure via Manus documentation research and queue a fix task.\n"
            f"scope:\n"
            f"- Research error signatures and root-cause paths for reason: {reason}.\n"
            f"- Produce one implementation-ready fix task with file scope and rollback.\n"
            f"- Include explicit verification commands for the proposed fix.\n"
            f"- Enforce PII Vault handling for all sensitive payload references.\n"
            f"- Never execute external payments; queue payment actions in Future Action for manual approval.\n"
            f"- Error excerpt: {excerpt}\n"
            f"success:\n"
            f"- Recovery fix task is queued and loop proceeds without hanging on this failure.\n"
            f"generated_by: orchestrator_self_heal\n"
            f"generated_at: {datetime.datetime.now().isoformat()}\n"
        )
        (queue_dir / f"{task_name}.md").write_text(body)
        return task_name
    except Exception as exc:
        log("WARN", f"Could not queue recovery task: {exc}")
        return None


def _skip_failed_task_to_next(task: str, pass_num: int, reason: str) -> None:
    """Archive current failed artifacts and return loop to idle for next queued task."""
    task = active_task_identity(task)
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
    archive_dir = LOOP_DIR / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    for artifact in (TASK_MD, PC_OUTPUT, MAC_REVIEW, CLOSEOUT):
        if artifact.exists():
            dst_name = f"{artifact.stem}_{task}_p{pass_num}_{reason}_{ts}{artifact.suffix}"
            artifact.rename(archive_dir / dst_name)
            log("ACTION", f"archived {artifact.name} → archive/{dst_name}")

    write_status("idle")
    _write_status_raw({"relaunch_attempted": False})


def handle_mac_turn(status: dict, elapsed: float, dry_run: bool = False) -> None:
    task     = status.get("task_name", "?")
    pass_num = status.get("pass", 1)
    log("STATE", f"mac_turn | task={task} | pass={pass_num} | elapsed={elapsed:.0f}s", dry_run)

    # --- Step 1: Ensure mac_review.md exists ---
    if not MAC_REVIEW.exists():
        planner_failed = planner_runner_missing_since(status)
        timed_out = elapsed >= PLANNER_TIMEOUT
        # If watcher.log has never been written, the Mac watcher has not started —
        # no human planner will appear. Use the PC-review fallback immediately rather
        # than waiting the full timeout window.
        watcher_absent = not _watcher_log_path().exists()

        def _attempt_pc_review_fallback(trigger_reason: str) -> bool:
            if not _PC_REVIEW_AVAILABLE or dry_run or _TEST_DISABLE_PC_REVIEW_FALLBACK:
                return False
            if not pc_output_valid(pass_num)[0]:
                log(
                    "EVIDENCE",
                    f"mac_turn | {trigger_reason} but pc_output is not reviewable yet — skipping PC-side review fallback",
                    dry_run,
                )
                return False
            log(
                "EVIDENCE",
                f"mac_turn | {trigger_reason} — attempting PC-side review fallback",
                dry_run,
            )
            rc = _pc_review_run(dry_run=False)
            if rc == 0 and MAC_REVIEW.exists():
                log("ACTION", "PC-side review fallback wrote mac_review.md — continuing with review", dry_run)
                return True
            log("EVIDENCE", f"PC-side review fallback did not produce mac_review.md (rc={rc})", dry_run)
            return False

        if planner_failed:
            # Only use the PC fallback when the watcher explicitly showed that
            # the Mac planner runner could not start for this mac_turn.
            if _attempt_pc_review_fallback("planner_runner_missing"):
                pass
            else:
                log("EVIDENCE", "mac_turn | watcher reported planner runner startup failure", dry_run)
                log("TRANSITION", "mac_turn → blocked (reason: planner_runner_missing)", dry_run)
                if not dry_run:
                    write_status("blocked", reason="planner_runner_missing")
                return
        elif watcher_absent:
            # Mac watcher log has never been written — no human planner will arrive.
            # Fire PC-review fallback immediately; fall through to timeout/block if it fails.
            if _attempt_pc_review_fallback("watcher_log_absent"):
                pass
            else:
                # Fallback unavailable or pc_output not reviewable yet — wait for timeout.
                log(
                    "STATE",
                    f"mac_turn | watcher absent, PC-review fallback unavailable — waiting ({elapsed:.0f}s / {PLANNER_TIMEOUT}s)",
                    dry_run,
                )
                if timed_out:
                    log("EVIDENCE", f"mac_turn | no mac_review.md after {elapsed:.0f}s", dry_run)
                    log("TRANSITION", "mac_turn → blocked (reason: planner_timeout_no_review)", dry_run)
                    if not dry_run:
                        write_status("blocked", reason="planner_timeout_no_review")
                return
        elif timed_out:
            if _attempt_pc_review_fallback("planner_timeout_no_review"):
                pass
            else:
                log("EVIDENCE", f"mac_turn | no mac_review.md after {elapsed:.0f}s", dry_run)
                log("TRANSITION", "mac_turn → blocked (reason: planner_timeout_no_review)", dry_run)
                if not dry_run:
                    write_status("blocked", reason="planner_timeout_no_review")
                return
        else:
            # Not yet timed out and planner hasn't explicitly failed
            log(
                "STATE",
                f"mac_turn | waiting for Planner review ({elapsed:.0f}s < {PLANNER_TIMEOUT}s)",
                dry_run,
            )
            return

    # --- Step 2: Process the review ---
    review_identity = mac_review_identity()
    if review_identity is not None:
        review_task, review_pass = review_identity
        accepted_tasks = {task, active_task_identity(task)}
        if review_pass != pass_num or review_task not in accepted_tasks:
            expected_tasks = ", ".join(sorted(accepted_tasks))
            log(
                "EVIDENCE",
                f"mac_review header mismatch — file task={review_task!r} pass={review_pass}, "
                f"expected task in {{{expected_tasks}}} and pass={pass_num}",
                dry_run,
            )
            log("TRANSITION", "mac_turn → blocked (reason: stale_mac_review)", dry_run)
            if not dry_run:
                write_status("blocked", reason="stale_mac_review")
            return

    approved = mac_review_says_approved()
    rework   = mac_review_says_rework()

    if approved and not rework:
        log("EVIDENCE", "mac_review: APPROVED", dry_run)

        # Chief acceptance gate — harness-backed retest tasks only
        if not dry_run and _active_task_is_harness_backed_retest():
            verdict = _chief_acceptance_verdict(status)
            if verdict == "REWORK":
                log("EVIDENCE", "chief acceptance gate: REWORK", dry_run)
                if pass_num >= MAX_PASSES:
                    log("TRANSITION", "mac_turn → blocked (reason: chief_rework_max_passes)", dry_run)
                    write_status("blocked", reason="chief_rework_max_passes")
                else:
                    log("TRANSITION", f"mac_turn → pc_turn (chief rework, pass {pass_num} → {pass_num + 1})", dry_run)
                    ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
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
            if verdict != "APPROVE":
                log("EVIDENCE", f"chief acceptance gate: {verdict}", dry_run)
                log("TRANSITION", "mac_turn → blocked (reason: chief_insufficient_evidence)", dry_run)
                write_status("blocked", reason="chief_insufficient_evidence")
                return
            log("EVIDENCE", "chief acceptance gate: APPROVE", dry_run)

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
                ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
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
    archive_task = active_task_identity(task)

    confirmed = closeout_confirmed(task, pass_num)
    if confirmed:
        log("EVIDENCE", f"closeout.ok confirmed — task={task} pass={pass_num}", dry_run)
    else:
        if CLOSEOUT.exists():
            log("STATE", "approved | waiting for valid matching closeout.ok", dry_run)
        else:
            log("STATE", "approved | waiting for closeout.ok", dry_run)
        return

    log("TRANSITION", "approved → idle", dry_run)
    if not dry_run:
        # Archive task.md before writing idle — prevents re-launch on next poll
        ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
        task_md = TASK_MD
        if task_md.exists():
            dst = LOOP_DIR / "archive" / f"task_{archive_task}_{ts}.md"
            task_md.rename(dst)
            log("ACTION", f"archived task.md → archive/task_{archive_task}_{ts}.md")
        # Archive current/ artifacts (pc_output, mac_review, closeout)
        for artifact in (PC_OUTPUT, MAC_REVIEW, CLOSEOUT):
            if artifact.exists():
                dst_name = f"{artifact.stem}_{archive_task}_{ts}{artifact.suffix}"
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

    if (
        reason in {"planner_timeout_no_review", "planner_runner_missing"}
        and _PC_REVIEW_AVAILABLE
        and not dry_run
        and not _TEST_DISABLE_PC_REVIEW_FALLBACK
        and not MAC_REVIEW.exists()
    ):
        pass_num = status.get("pass", 1)
        if pc_output_valid(pass_num)[0]:
            log("ACTION", f"blocked | attempting late PC-side review fallback for {reason}", dry_run)
            rc = _pc_review_run(dry_run=False)
            if rc == 0 and MAC_REVIEW.exists():
                log("TRANSITION", "blocked → mac_turn (late PC-side review fallback succeeded)", dry_run)
                write_status("mac_turn")
                return

    # Send one-shot Telegram notification to Winship — only on first entry into blocked
    if not dry_run and _NOTIFY_AVAILABLE and not status.get("blocked_notified", False):
        msg = (
            f"🚨 *Loop blocked* — human action required\n\n"
            f"*Task:* `{task}`\n"
            f"*Reason:* `{reason}`\n\n"
            f"To unblock, run:\n"
            f"`ssh openclaw \"python3 /home/openclaw/polish_loop/orchestrator.py --reset-blocked --reason 'fixed'\"`"
        )
        _chief_notify.send(msg)
        _write_status_raw({"blocked_notified": True})


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
    elif state in ("paused", "emergency_freeze", "stopped"):
        log("STATE", f"Loop is {state} — no action taken (use loop_control.sh resume)", dry_run)

    return read_status()


def phase_c_dispatch_local_builder(lease: "TaskLease") -> None:
    """Finite worker-runtime handoff for a claimed ledger lease.

    P0 owns the lease and durable state. The actual worker invocation is kept
    explicit and finite; no background poller is started here.
    """
    log("ACTION", f"phase-c dispatch | task={lease.task_id} | owner={lease.owner}")


def run_phase_c_once(
    *,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    owner: str = "orchestrator",
    dry_run: bool = False,
) -> "DispatchResult":
    if not _PHASE_C_AVAILABLE or ControlPlaneLedger is None or run_control_plane_once is None:
        raise RuntimeError("Phase-C control plane module is unavailable")
    if dry_run:
        ledger = ControlPlaneLedger(ledger_path)
        before = ledger.counts()
        result = run_control_plane_once(ledger, owner=owner, dispatch=None)
        after = ledger.counts()
        print(f"[dry-run] phase-c result={result} counts_before={before} counts_after={after}")
        return result
    ledger = ControlPlaneLedger(ledger_path)
    return run_control_plane_once(
        ledger,
        owner=owner,
        dispatch=phase_c_dispatch_local_builder,
    )


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


def cmd_reset_blocked(reason: str) -> None:
    """Reset blocked → idle (or mac_turn for planner-timeout). Human-controlled only, requires reason."""
    status = read_status()
    if status is None:
        print("ERROR: status.json missing or invalid", file=sys.stderr)
        sys.exit(1)
    if status["status"] != "blocked":
        print(f"ERROR: current state is {status['status']!r}, not 'blocked'", file=sys.stderr)
        sys.exit(1)

    block_reason = status.get("block_reason", "")
    # planner_timeout_no_review: valid builder output already exists — resume at mac_turn
    # to preserve the artifact rather than archiving it and relaunching builder.
    if block_reason == "planner_timeout_no_review" and PC_OUTPUT.exists():
        target_state = "mac_turn"
    else:
        target_state = "idle"

    _write_status_raw({
        "status": target_state,
        "block_reason": None,
        "reset_reason": reason,
        "reset_at": datetime.datetime.now().isoformat(),
    })
    log("RESET", f"blocked → {target_state} | reason: {reason}")
    print(f"Reset: blocked → {target_state} (reason: {reason})")


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
    _write_status_raw({"relaunch_attempted": False})
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

    global _TEST_DISABLE_IDLE_AUTOLAUNCH, _TEST_SUPPRESS_FILE_LOGS, _TEST_WATCHER_LOG_OVERRIDE
    global _TEST_DISABLE_PC_REVIEW_FALLBACK, _TEST_DISABLE_SELF_HEAL_TASKS
    global LOG_FILE

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
    live_log_file = LOG_FILE
    original_log_contents: str = live_log_file.read_text() if live_log_file.exists() else ""
    original_pc_log_file = _pc_review_mod.LOG_FILE if _pc_review_mod is not None else None

    original_artifacts: dict[Path, str | None] = {}
    for p in (PC_OUTPUT, MAC_REVIEW, CLOSEOUT):
        original_artifacts[p] = p.read_text() if p.exists() else None

    CURRENT_DIR.mkdir(parents=True, exist_ok=True)
    test_log_file = CURRENT_DIR / "test_orchestrator.log"
    test_log_file.unlink(missing_ok=True)

    def set_status(d: dict) -> None:
        STATUS_FILE.write_text(json.dumps(d, indent=2))

    def clear_status() -> None:
        if STATUS_FILE.exists():
            STATUS_FILE.unlink()

    def clear_artifacts() -> None:
        for p in (PC_OUTPUT, MAC_REVIEW, CLOSEOUT):
            if p.exists():
                p.unlink()

    test_watcher_log = CURRENT_DIR / "test_watcher.log"

    def clear_test_watcher_log() -> None:
        if test_watcher_log.exists():
            test_watcher_log.unlink()

    now     = datetime.datetime.now()
    now_iso = now.isoformat()
    old_iso = (now - datetime.timedelta(seconds=BUILDER_TIMEOUT + 60)).isoformat()
    watcher_now = now.strftime("%Y-%m-%d %H:%M:%S")
    watcher_old = (now - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

    def fresh_status(**kwargs) -> dict:
        base = {"pass": 1, "task_name": "test-orch", "last_updated": now_iso, "approved": False}
        base.update(kwargs)
        return base

    try:
        _TEST_DISABLE_IDLE_AUTOLAUNCH = True
        _TEST_SUPPRESS_FILE_LOGS = True
        _TEST_WATCHER_LOG_OVERRIDE = test_watcher_log
        _TEST_DISABLE_PC_REVIEW_FALLBACK = True
        _TEST_DISABLE_SELF_HEAL_TASKS = True
        LOG_FILE = test_log_file
        if _pc_review_mod is not None:
            _pc_review_mod._SUPPRESS_FILE_LOGS = True
            _pc_review_mod.LOG_FILE = test_log_file

        # 1. status.json missing → blocked, invalid_or_missing_status
        clear_status()
        clear_artifacts()
        clear_test_watcher_log()
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
        clear_test_watcher_log()
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
        clear_test_watcher_log()
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "pc_turn, elapsed < timeout, no output → still pc_turn (wait)",
            s is not None and s["status"] == "pc_turn",
            f"got {s}",
        )

        # 4. pc_turn, builder dead, elapsed > timeout → self-heal skip to idle
        #    Force builder_running() to return False so the test is independent
        #    of whether run_polish_pass.sh happens to be running on this machine.
        #    Force _relaunch_builder() to return False so one cycle reaches parked.
        global _TEST_BUILDER_OVERRIDE, _TEST_RELAUNCH_OVERRIDE
        _TEST_BUILDER_OVERRIDE = False
        _TEST_RELAUNCH_OVERRIDE = False
        set_status(fresh_status(status="pc_turn", last_updated=old_iso))
        clear_artifacts()
        clear_test_watcher_log()
        run_one_cycle(dry_run=False)
        _TEST_BUILDER_OVERRIDE = None
        _TEST_RELAUNCH_OVERRIDE = None
        s = read_status()
        check(
            "pc_turn, builder dead, elapsed > timeout → idle (self-heal skip)",
            s is not None and s["status"] == "idle",
            f"got {s}",
        )

        # 5. pc_turn, valid pc_output → mac_turn
        set_status(fresh_status(status="pc_turn", **{"pass": 2, "last_updated": now_iso}))
        clear_test_watcher_log()
        PC_OUTPUT.write_text(
            "RUNNER: claude\n"
            "PASS: 2\n"
            "STATUS: DONE\n\n"
            "CHANGES:\n"
            "- test\n\n"
            "REASONING:\n"
            "- test\n\n"
            "ROLLBACK PLAN:\n"
            "- revert test\n\n"
            "COST:\n"
            "- spend unavailable\n\n"
            "TRUTH:\n"
            "- verified: none\n\n"
            "HEADROOM:\n"
            "- unknown\n"
        )
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "pc_turn, valid pc_output → mac_turn",
            s is not None and s["status"] == "mac_turn",
            f"got {s}",
        )
        PC_OUTPUT.unlink(missing_ok=True)

        # 6. pc_turn, stale pc_output while Builder running → still pc_turn
        set_status(fresh_status(status="pc_turn", **{"pass": 3, "last_updated": now_iso}))
        clear_test_watcher_log()
        _TEST_BUILDER_OVERRIDE = True
        PC_OUTPUT.write_text("RUNNER: claude\nPASS: 2\nSTATUS: DONE\n")
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "pc_turn, stale pc_output while Builder running → still pc_turn",
            s is not None and s["status"] == "pc_turn",
            f"got {s}",
        )
        _TEST_BUILDER_OVERRIDE = None
        PC_OUTPUT.unlink(missing_ok=True)

        # 6b. pc_turn, stale pc_output with dead Builder → relaunch once, stay pc_turn
        set_status(fresh_status(status="pc_turn", **{"pass": 3, "last_updated": now_iso}))
        clear_test_watcher_log()
        _TEST_BUILDER_OVERRIDE = False
        _TEST_RELAUNCH_OVERRIDE = True
        PC_OUTPUT.write_text("PASS: 2\nSTATUS: DONE\n")
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "pc_turn, stale pc_output with dead Builder → relaunch once",
            s is not None and s["status"] == "pc_turn" and s.get("relaunch_attempted") is True and not PC_OUTPUT.exists(),
            f"got {s}",
        )
        _TEST_BUILDER_OVERRIDE = None
        _TEST_RELAUNCH_OVERRIDE = None

        # 6c. pc_turn, invalid quality-gate output while Builder running → still pc_turn
        set_status(fresh_status(status="pc_turn", **{"pass": 1, "last_updated": now_iso}))
        clear_test_watcher_log()
        _TEST_BUILDER_OVERRIDE = True
        PC_OUTPUT.write_text("RUNNER: claude\nPASS: 1\nSTATUS: DONE\n")
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "pc_turn, invalid quality-gate output while Builder running → still pc_turn",
            s is not None and s["status"] == "pc_turn",
            f"got {s}",
        )
        _TEST_BUILDER_OVERRIDE = None
        PC_OUTPUT.unlink(missing_ok=True)

        # 6d. pc_turn, invalid quality-gate output with dead Builder → relaunch once
        set_status(fresh_status(status="pc_turn", **{"pass": 1, "last_updated": now_iso}))
        clear_test_watcher_log()
        _TEST_BUILDER_OVERRIDE = False
        _TEST_RELAUNCH_OVERRIDE = True
        PC_OUTPUT.write_text("RUNNER: claude\nPASS: 1\nSTATUS: DONE\n")
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "pc_turn, invalid quality-gate output with dead Builder → relaunch once",
            s is not None and s["status"] == "pc_turn" and s.get("relaunch_attempted") is True and not PC_OUTPUT.exists(),
            f"got {s}",
        )
        _TEST_BUILDER_OVERRIDE = None
        _TEST_RELAUNCH_OVERRIDE = None

        # 7. mac_turn, no mac_review, elapsed < timeout → still mac_turn
        set_status(fresh_status(status="mac_turn", last_updated=now_iso))
        clear_artifacts()
        clear_test_watcher_log()
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "mac_turn, no mac_review, elapsed < timeout → still mac_turn (wait)",
            s is not None and s["status"] == "mac_turn",
            f"got {s}",
        )

        # 8. mac_turn, no mac_review, watcher runner failure → blocked immediately
        set_status(fresh_status(status="mac_turn", last_updated=now_iso))
        clear_artifacts()
        clear_test_watcher_log()
        test_watcher_log.write_text(
            f"[{watcher_now}] [watcher] ERROR: No planner runner found. "
            "Checked PATH and common install directories.\n"
        )
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "mac_turn, no mac_review, watcher runner failure → blocked (planner_runner_missing)",
            s is not None and s["status"] == "blocked"
            and s.get("block_reason") == "planner_runner_missing",
            f"got {s}",
        )

        # 9. mac_turn, stale watcher runner failure from earlier pass → still mac_turn
        set_status(fresh_status(status="mac_turn", last_updated=now_iso))
        clear_artifacts()
        clear_test_watcher_log()
        test_watcher_log.write_text(
            f"[{watcher_old}] [watcher] ERROR: No planner runner found. "
            "Checked PATH and common install directories.\n"
        )
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "mac_turn, stale watcher runner failure from earlier pass → still mac_turn",
            s is not None and s["status"] == "mac_turn",
            f"got {s}",
        )

        # 10. mac_turn, no mac_review, elapsed > timeout → blocked (planner_timeout_no_review)
        set_status(fresh_status(status="mac_turn", last_updated=old_iso))
        clear_artifacts()
        clear_test_watcher_log()
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "mac_turn, no mac_review, elapsed > timeout → blocked (planner_timeout_no_review)",
            s is not None and s["status"] == "blocked"
            and s.get("block_reason") == "planner_timeout_no_review",
            f"got {s}",
        )

        # 10a. PC review fallback: planner timeout + valid pc_output → approved
        _TEST_DISABLE_PC_REVIEW_FALLBACK = False
        set_status(fresh_status(status="mac_turn", last_updated=old_iso))
        clear_artifacts()
        clear_test_watcher_log()
        PC_OUTPUT.write_text(
            "RUNNER: codex\n"
            "PASS: 1\nSTATUS: DONE\n\n"
            "CHANGES:\n- /home/openclaw/polish_loop/orchestrator.py\n\n"
            "REASONING:\n- test reasoning\n\n"
            "ROLLBACK PLAN:\n- revert test\n\n"
            "COST:\n- spend unavailable\n\n"
            "TRUTH:\n- verified: none\n\n"
            "HEADROOM:\n- unknown\n"
        )
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "PC review fallback: planner_timeout_no_review + valid pc_output → approved",
            s is not None and s["status"] == "approved" and MAC_REVIEW.exists(),
            f"got {s}",
        )
        _TEST_DISABLE_PC_REVIEW_FALLBACK = True
        clear_artifacts()

        # 10b. PC review fallback: planner_runner_missing + valid pc_output → approved
        _TEST_DISABLE_PC_REVIEW_FALLBACK = False
        set_status(fresh_status(status="mac_turn", last_updated=now_iso))
        clear_artifacts()
        clear_test_watcher_log()
        test_watcher_log.write_text(
            f"[{watcher_now}] [watcher] ERROR: No planner runner found. "
            "Checked PATH and common install directories.\n"
        )
        PC_OUTPUT.write_text(
            "RUNNER: gemini\n"
            "PASS: 1\nSTATUS: DONE\n\n"
            "CHANGES:\n- test change\n\n"
            "REASONING:\n- test reasoning\n\n"
            "ROLLBACK PLAN:\n- revert test\n\n"
            "COST:\n- spend unavailable\n\n"
            "TRUTH:\n- verified: none\n\n"
            "HEADROOM:\n- unknown\n"
        )
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "PC review fallback: planner_runner_missing + valid pc_output → approved",
            s is not None and s["status"] == "approved" and MAC_REVIEW.exists(),
            f"got {s}",
        )
        _TEST_DISABLE_PC_REVIEW_FALLBACK = True
        clear_artifacts()

        # 10c. watcher_absent + valid pc_output + PC-review enabled → approved immediately (no timeout wait)
        _TEST_DISABLE_PC_REVIEW_FALLBACK = False
        set_status(fresh_status(status="mac_turn", last_updated=now_iso))  # NOT timed out
        clear_artifacts()
        clear_test_watcher_log()  # watcher log absent
        PC_OUTPUT.write_text(
            "RUNNER: codex\n"
            "PASS: 1\nSTATUS: DONE\n\n"
            "CHANGES:\n- /home/openclaw/polish_loop/orchestrator.py\n\n"
            "REASONING:\n- test reasoning\n\n"
            "ROLLBACK PLAN:\n- revert test\n\n"
            "COST:\n- spend unavailable\n\n"
            "TRUTH:\n- verified: none\n\n"
            "HEADROOM:\n- unknown\n"
        )
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "watcher absent + valid pc_output + PC-review enabled → approved immediately (no timeout wait)",
            s is not None and s["status"] == "approved" and MAC_REVIEW.exists(),
            f"got {s}",
        )
        _TEST_DISABLE_PC_REVIEW_FALLBACK = True
        clear_artifacts()

        # 10d. watcher_absent + PC-review disabled + no timeout → still mac_turn (wait)
        set_status(fresh_status(status="mac_turn", last_updated=now_iso))  # NOT timed out
        clear_artifacts()
        clear_test_watcher_log()  # watcher log absent
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "watcher absent + PC-review disabled + no timeout → still mac_turn (wait)",
            s is not None and s["status"] == "mac_turn",
            f"got {s}",
        )

        # 10e. watcher_absent + PC-review disabled + timeout → blocked (planner_timeout_no_review)
        set_status(fresh_status(status="mac_turn", last_updated=old_iso))  # timed out
        clear_artifacts()
        clear_test_watcher_log()  # watcher log absent
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "watcher absent + PC-review disabled + timeout → blocked (planner_timeout_no_review)",
            s is not None and s["status"] == "blocked"
            and s.get("block_reason") == "planner_timeout_no_review",
            f"got {s}",
        )

        # 11. mac_turn, ambiguous mac_review → blocked (ambiguous_mac_review)
        set_status(fresh_status(status="mac_turn", last_updated=now_iso))
        clear_test_watcher_log()
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

        # 12. mac_turn, NEEDS_REWORK, pass >= MAX_PASSES → blocked (max_passes_exceeded)
        set_status(fresh_status(status="mac_turn", **{"pass": MAX_PASSES, "last_updated": now_iso}))
        clear_test_watcher_log()
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

        # 13. approved, no closeout.ok → approved (wait for closeout)
        set_status(fresh_status(status="approved", approved=True, last_updated=now_iso))
        clear_artifacts()
        clear_test_watcher_log()
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "approved, no closeout.ok → approved (wait)",
            s is not None and s["status"] == "approved",
            f"got {s}",
        )

        # 14. --reset-blocked with reason → idle
        set_status(fresh_status(status="blocked", block_reason="test_block", last_updated=now_iso))
        cmd_reset_blocked("Builder auth expired — re-authed")
        s = read_status()
        check(
            "--reset-blocked with reason → idle",
            s is not None and s["status"] == "idle",
            f"got {s}",
        )

        # 14b. --reset-blocked planner_timeout_no_review + pc_output present → mac_turn (preserve artifact)
        set_status(fresh_status(status="blocked", block_reason="planner_timeout_no_review", last_updated=now_iso))
        PC_OUTPUT.write_text("# PASS:1\nsome output\n")
        cmd_reset_blocked("planner review missing — retrying")
        s = read_status()
        check(
            "--reset-blocked planner_timeout_no_review + pc_output → mac_turn (artifact preserved)",
            s is not None and s["status"] == "mac_turn" and PC_OUTPUT.exists(),
            f"got {s}, pc_output exists={PC_OUTPUT.exists()}",
        )
        PC_OUTPUT.unlink(missing_ok=True)

        # 14c. --reset-blocked planner_timeout_no_review but no pc_output → idle (fallback)
        set_status(fresh_status(status="blocked", block_reason="planner_timeout_no_review", last_updated=now_iso))
        cmd_reset_blocked("planner review missing — no artifact")
        s = read_status()
        check(
            "--reset-blocked planner_timeout_no_review + no pc_output → idle",
            s is not None and s["status"] == "idle",
            f"got {s}",
        )

        # 15. dry_run=True writes nothing
        set_status(fresh_status(status="mac_turn", last_updated=now_iso))
        clear_test_watcher_log()
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

        # 16. mac_turn, APPROVED → approved
        set_status(fresh_status(status="mac_turn", last_updated=now_iso))
        clear_test_watcher_log()
        MAC_REVIEW.write_text("Some analysis.\nAPPROVED\nNo issues.\n")
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "mac_turn, APPROVED → approved",
            s is not None and s["status"] == "approved",
            f"got {s}",
        )
        MAC_REVIEW.unlink(missing_ok=True)

        # 17. mac_turn, NEEDS_REWORK, pass < MAX_PASSES → pc_turn (pass incremented)
        set_status(fresh_status(status="mac_turn", **{"pass": 1, "last_updated": now_iso}))
        clear_test_watcher_log()
        MAC_REVIEW.write_text("NEEDS_REWORK\nFix these issues.\n")
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "mac_turn, NEEDS_REWORK, pass < MAX_PASSES → pc_turn (pass++)",
            s is not None and s["status"] == "pc_turn" and s.get("pass") == 2,
            f"got {s}",
        )
        MAC_REVIEW.unlink(missing_ok=True)

        # 18. approved + valid closeout.ok → idle
        set_status(fresh_status(status="approved", **{"pass": 1, "task_name": "test-orch", "approved": True}))
        clear_test_watcher_log()
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

        # 19. approved + malformed closeout.ok → approved (ERROR logged, waits)
        set_status(fresh_status(status="approved", **{"pass": 1, "task_name": "test-orch", "approved": True}))
        clear_test_watcher_log()
        CLOSEOUT.write_text("this is plain text, not json")
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "approved + malformed closeout.ok → approved (ERROR logged)",
            s is not None and s["status"] == "approved",
            f"got {s}",
        )
        CLOSEOUT.unlink(missing_ok=True)

        # 20. pc_turn, builder dead, elapsed > BUILDER_TIMEOUT → idle (self-heal skip)
        set_status(fresh_status(status="pc_turn", **{"pass": 1, "task_name": "test-orch", "last_updated": old_iso}))
        clear_test_watcher_log()
        _TEST_BUILDER_OVERRIDE = False
        _TEST_RELAUNCH_OVERRIDE = False
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "pc_turn, builder dead, elapsed > BUILDER_TIMEOUT → idle",
            s is not None and s["status"] == "idle",
            f"got {s}",
        )
        _TEST_BUILDER_OVERRIDE = None
        _TEST_RELAUNCH_OVERRIDE = None

        # 21. parked (pc_turn) + builder running → pc_turn
        set_status(fresh_status(status="parked", **{"pass": 1, "task_name": "test-orch", "parked_from": "pc_turn", "parked_reason": "builder_timeout"}))
        clear_test_watcher_log()
        _TEST_BUILDER_OVERRIDE = True
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "parked (pc_turn) + builder running → pc_turn",
            s is not None and s["status"] == "pc_turn",
            f"got {s}",
        )
        _TEST_BUILDER_OVERRIDE = None

        # 22. parked (mac_turn) → mac_turn (auto-resume, Planner is here)
        set_status(fresh_status(status="parked", **{"pass": 1, "task_name": "test-orch", "parked_from": "mac_turn", "parked_reason": "planner_timeout"}))
        clear_test_watcher_log()
        run_one_cycle(dry_run=False)
        s = read_status()
        check(
            "parked (mac_turn) → mac_turn (auto-resume)",
            s is not None and s["status"] == "mac_turn",
            f"got {s}",
        )

        # 23. cmd_resume from parked pc_turn resets relaunch_attempted guard
        set_status(fresh_status(status="parked", **{"pass": 1, "task_name": "test-orch", "parked_from": "pc_turn", "parked_reason": "builder_timeout", "relaunch_attempted": True}))
        clear_test_watcher_log()
        cmd_resume()
        s = read_status()
        check(
            "cmd_resume parked(pc_turn) resets relaunch_attempted",
            s is not None and s["status"] == "pc_turn" and s.get("relaunch_attempted") is False,
            f"got {s}",
        )

        # 24. builder_running() recognizes watcher-launched runner process patterns
        real_subprocess_run = subprocess.run
        seen_patterns: list[str] = []
        def fake_run(args, capture_output=False, text=False):
            pattern = args[-1] if args else ""
            seen_patterns.append(pattern)
            class R:
                def __init__(self, rc):
                    self.returncode = rc
            # Simulate watcher-launched Claude process present.
            if pattern == r"timeout [0-9]+ (codex|gemini|claude|aider)( .*)?":
                return R(0)
            return R(1)
        subprocess.run = fake_run
        try:
            detected = builder_running()
        finally:
            subprocess.run = real_subprocess_run
        check(
            "builder_running detects watcher-launched runner patterns",
            detected is True and r"timeout [0-9]+ (codex|gemini|claude|aider)( .*)?" in seen_patterns,
            f"detected={detected} patterns={seen_patterns}",
        )

        # 25. _queue_manus_recovery_task blocks recursive recovery-task cascades
        queue_dir = LOOP_DIR / "tasks"
        before_auto_gen = sorted(p.name for p in queue_dir.glob("auto-gen-*.md")) if queue_dir.exists() else []
        prior_self_heal_disable = _TEST_DISABLE_SELF_HEAL_TASKS
        real_audit_lock_active = audit_lock_active
        _TEST_DISABLE_SELF_HEAL_TASKS = False
        globals()["audit_lock_active"] = lambda: False
        try:
            plain_recovery_result = _queue_manus_recovery_task("manual-manus-recovery", "builder_timeout_after_retry")
            nested_result = _queue_manus_recovery_task("auto-gen-005-manus-recovery", "builder_timeout_after_retry")
            auto_gen_result = _queue_manus_recovery_task("auto-gen-005", "builder_timeout_after_retry")
        finally:
            _TEST_DISABLE_SELF_HEAL_TASKS = prior_self_heal_disable
            globals()["audit_lock_active"] = real_audit_lock_active
        after_auto_gen = sorted(p.name for p in queue_dir.glob("auto-gen-*.md")) if queue_dir.exists() else []
        check(
            "_queue_manus_recovery_task skips recursive recovery tasks",
            plain_recovery_result is None and nested_result is None and auto_gen_result is None and before_auto_gen == after_auto_gen,
            f"plain={plain_recovery_result!r} nested={nested_result!r} auto_gen={auto_gen_result!r} before={before_auto_gen} after={after_auto_gen}",
        )

        check(
            "run-tests isolates self-test log target from live orchestrator.log",
            LOG_FILE == test_log_file and live_log_file != test_log_file,
            f"LOG_FILE={LOG_FILE} live_log_file={live_log_file}",
        )

    finally:
        _TEST_SUPPRESS_FILE_LOGS = False
        _TEST_WATCHER_LOG_OVERRIDE = None
        _TEST_DISABLE_IDLE_AUTOLAUNCH = False
        _TEST_DISABLE_PC_REVIEW_FALLBACK = False
        _TEST_DISABLE_SELF_HEAL_TASKS = False
        LOG_FILE = live_log_file
        if _pc_review_mod is not None:
            _pc_review_mod._SUPPRESS_FILE_LOGS = False
            _pc_review_mod.LOG_FILE = original_pc_log_file
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
    parser.add_argument("--once",          action="store_true", help="Run one Phase-C ledger event then exit")
    parser.add_argument("--legacy-once",   action="store_true", help="Run one legacy status.json cycle then exit")
    parser.add_argument("--ledger",        type=Path, default=DEFAULT_LEDGER_PATH, help="Phase-C ledger path")
    parser.add_argument("--loop",          action="store_true", help="Deprecated; standing poll loops are disabled")
    args = parser.parse_args()

    if args.dry_run:
        if args.legacy_once:
            cmd_dry_run()
        else:
            run_phase_c_once(ledger_path=args.ledger, dry_run=True)
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

    if args.legacy_once:
        run_one_cycle()
        return

    if args.loop:
        print("ERROR: standing poll loops are disabled in Phase-C P0; use --once or an external event trigger", file=sys.stderr)
        sys.exit(2)

    result = run_phase_c_once(ledger_path=args.ledger)
    if result.dispatched:
        log("STATE", f"phase-c dispatched task={result.task_id}")


if __name__ == "__main__":
    main()
