"""OpenClaw sleep/suspend resilience monitor.

The monitor is intentionally narrow:
- detect likely host sleep/resume gaps from wall-clock deltas,
- keep the host awake only while recent fleet work is visible,
- optionally run the existing allowlisted service keeper after a resume gap,
- write local read-model receipts.

It does not deploy, restart active services, call models, read secrets, or send
externally.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent
DEFAULT_ORCH_ROOT = Path(os.environ.get("OPENCLAW_ORCH_ROOT", "/mnt/e/openclaw/orchestration"))
DEFAULT_READ_MODEL_ROOT = ROOT / "generated/read_models"

JSON_EXPORT_NAME = "openclaw_sleep_resilience_status.json"
OPERATOR_EXPORT_NAME = "openclaw_sleep_resilience_status_OPERATOR.md"
STATE_EXPORT_NAME = "openclaw_sleep_resilience_state.json"
SCHEMA_VERSION = "openclaw_sleep_resilience_status_v0"

DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_ACTIVE_WINDOW_SECONDS = 15 * 60
DEFAULT_RESUME_GAP_SECONDS = 10 * 60

RECENT_ACTIVITY_PREFIXES = (
    "LANE-",
    "CLAIMED-",
    "POOL-",
    "PC-SUBORCH",
    "MASTER-",
    "FROM-",
)
SELF_PREFIX = "OPENCLAW-SLEEP-RESILIENCE"

NO_AUTHORITY_FLAGS = {
    "local_read_model_only": True,
    "external_send_attempted": False,
    "secrets_read": False,
    "lm_called": False,
    "browser_accessed": False,
    "email_accessed": False,
    "gmail_accessed": False,
    "ledger_mutated": False,
    "business_workflow_state_mutated": False,
    "queue_files_processed_directly": False,
    "service_restart_attempted": False,
    "arbitrary_service_start_attempted": False,
    "allowlisted_service_keeper_only": True,
}


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


CommandRunner = Callable[[list[str]], CommandResult]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _run_command(args: list[str], *, timeout_seconds: int = 20) -> CommandResult:
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        return CommandResult(127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return CommandResult(124, stdout, stderr or "command timed out")
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def detect_resume_gap(
    *,
    previous_wall_utc: datetime | None,
    now_utc: datetime,
    interval_seconds: int,
    resume_gap_seconds: int,
) -> tuple[bool, int | None]:
    if previous_wall_utc is None:
        return False, None
    delta_seconds = int((now_utc - previous_wall_utc).total_seconds())
    threshold = max(resume_gap_seconds, interval_seconds * 2)
    return delta_seconds > threshold, delta_seconds


def load_state(state_path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(state_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def recent_fleet_activity(
    orch_root: str | Path,
    *,
    now_utc: datetime,
    active_window_seconds: int,
    limit: int = 20,
) -> list[dict[str, Any]]:
    to_claude = Path(orch_root) / "inbox/to-claude"
    if not to_claude.is_dir():
        return []
    cutoff = now_utc.timestamp() - active_window_seconds
    rows: list[dict[str, Any]] = []
    for path in to_claude.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if name.startswith(SELF_PREFIX):
            continue
        if not name.startswith(RECENT_ACTIVITY_PREFIXES):
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            continue
        rows.append(
            {
                "name": name,
                "path": path.as_posix(),
                "mtime_utc": datetime.fromtimestamp(mtime, timezone.utc)
                .replace(microsecond=0)
                .isoformat(),
            }
        )
    rows.sort(key=lambda row: row["mtime_utc"], reverse=True)
    return rows[:limit]


def windows_awake_command(*, active: bool, hold_seconds: int = 75) -> list[str]:
    flag = "0x80000001" if active else "0x80000000"
    sleep_clause = (
        f"; Start-Sleep -Seconds {max(1, hold_seconds)}; "
        "[OpenClaw.Kernel32]::SetThreadExecutionState(0x80000000) | Out-Null"
        if active
        else ""
    )
    command = (
        "Add-Type -Namespace OpenClaw -Name Kernel32 -MemberDefinition "
        "'[System.Runtime.InteropServices.DllImport(\"kernel32.dll\")] "
        "public static extern uint SetThreadExecutionState(uint esFlags);'; "
        f"[OpenClaw.Kernel32]::SetThreadExecutionState({flag}) | Out-Null"
        f"{sleep_clause}"
    )
    return [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        command,
    ]


def set_host_awake(
    *,
    active: bool,
    hold_seconds: int = 75,
    runner: CommandRunner | None = None,
) -> dict[str, Any]:
    if runner is None and shutil.which("powershell.exe") is None:
        return {
            "adapter": "windows_set_thread_execution_state",
            "requested_state": "ACTIVE" if active else "CLEARED",
            "status": "UNAVAILABLE",
            "error": "powershell.exe unavailable; host sleep inhibition not applied.",
        }
    command = windows_awake_command(active=active, hold_seconds=hold_seconds)
    if runner is None and active:
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except OSError as exc:
            return {
                "adapter": "windows_set_thread_execution_state",
                "requested_state": "ACTIVE",
                "status": "FAILED",
                "returncode": 1,
                "error": str(exc),
            }
        return {
            "adapter": "windows_set_thread_execution_state",
            "requested_state": "ACTIVE",
            "status": "APPLIED",
            "returncode": 0,
            "holder_pid": process.pid,
            "hold_seconds": hold_seconds,
            "error": "",
        }
    result = (runner or _run_command)(command)
    return {
        "adapter": "windows_set_thread_execution_state",
        "requested_state": "ACTIVE" if active else "CLEARED",
        "status": "APPLIED" if result.returncode == 0 else "FAILED",
        "returncode": result.returncode,
        "hold_seconds": hold_seconds if active else 0,
        "error": result.stderr.strip(),
    }


def run_service_keeper(
    *,
    runner: CommandRunner | None = None,
) -> dict[str, Any]:
    command = [
        sys.executable,
        (ROOT / "scripts/openclaw_service_keeper.py").as_posix(),
        "--format",
        "json",
    ]
    result = (runner or _run_command)(command)
    parsed: dict[str, Any] = {}
    if result.stdout.strip():
        try:
            maybe = json.loads(result.stdout)
            if isinstance(maybe, dict):
                parsed = maybe
        except json.JSONDecodeError:
            parsed = {}
    return {
        "command": "scripts/openclaw_service_keeper.py --format json",
        "status": "RAN" if result.returncode == 0 else "FAILED",
        "returncode": result.returncode,
        "run_status": parsed.get("run_status", ""),
        "action_count": parsed.get("action_count", 0),
        "error": result.stderr.strip(),
    }


def build_sleep_resilience_status(
    *,
    now_utc: datetime,
    previous_state: dict[str, Any],
    recent_activity: list[dict[str, Any]],
    inhibitor_result: dict[str, Any] | None,
    service_keeper_result: dict[str, Any] | None,
    interval_seconds: int,
    active_window_seconds: int,
    resume_gap_seconds: int,
) -> dict[str, Any]:
    previous_wall = parse_iso_datetime(str(previous_state.get("last_wall_utc", "")))
    resume_detected, wall_gap_seconds = detect_resume_gap(
        previous_wall_utc=previous_wall,
        now_utc=now_utc,
        interval_seconds=interval_seconds,
        resume_gap_seconds=resume_gap_seconds,
    )
    active_work_visible = bool(recent_activity)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": now_utc.replace(microsecond=0).isoformat(),
        "purpose": "Keep the PC awake during active OpenClaw fleet work and detect resume gaps.",
        "interval_seconds": interval_seconds,
        "active_window_seconds": active_window_seconds,
        "resume_gap_seconds": resume_gap_seconds,
        "active_work_visible": active_work_visible,
        "recent_activity_count": len(recent_activity),
        "recent_activity": recent_activity,
        "previous_wall_utc": previous_state.get("last_wall_utc", ""),
        "wall_gap_seconds": wall_gap_seconds,
        "resume_gap_detected": resume_detected,
        "host_awake": inhibitor_result
        or {
            "adapter": "not_requested",
            "requested_state": "SKIPPED",
            "status": "SKIPPED",
            "error": "",
        },
        "resume_recovery": service_keeper_result
        or {
            "command": "",
            "status": "SKIPPED",
            "returncode": 0,
            "run_status": "",
            "action_count": 0,
            "error": "",
        },
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def render_operator_summary(payload: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Sleep Resilience",
        "",
        f"- Active work visible: {payload['active_work_visible']}",
        f"- Resume gap detected: {payload['resume_gap_detected']}",
        f"- Wall gap seconds: {payload['wall_gap_seconds']}",
        f"- Host awake status: {payload['host_awake']['status']}",
        f"- Resume recovery status: {payload['resume_recovery']['status']}",
        "",
        "## Recent Activity",
    ]
    if not payload["recent_activity"]:
        lines.append("- none")
    for row in payload["recent_activity"][:10]:
        lines.append(f"- {row['mtime_utc']} {row['name']}")
    return "\n".join(lines) + "\n"


def write_sleep_resilience_status(
    payload: dict[str, Any],
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
) -> tuple[Path, Path, Path]:
    root = Path(read_model_root)
    if not root.is_absolute():
        root = ROOT / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    state_path = root / STATE_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(render_operator_summary(payload), encoding="utf-8")
    state_path.write_text(
        stable_json({"last_wall_utc": payload["generated_at"]}),
        encoding="utf-8",
    )
    return json_path, operator_path, state_path


def run_once(
    *,
    orch_root: str | Path = DEFAULT_ORCH_ROOT,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    active_window_seconds: int = DEFAULT_ACTIVE_WINDOW_SECONDS,
    resume_gap_seconds: int = DEFAULT_RESUME_GAP_SECONDS,
    apply_host_awake: bool = False,
    run_service_keeper_on_resume: bool = False,
    now_utc: datetime | None = None,
    runner: CommandRunner | None = None,
) -> dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    root = Path(read_model_root)
    if not root.is_absolute():
        root = ROOT / root
    previous_state = load_state(root / STATE_EXPORT_NAME)
    activity = recent_fleet_activity(
        orch_root,
        now_utc=now,
        active_window_seconds=active_window_seconds,
    )
    resume_detected, _gap = detect_resume_gap(
        previous_wall_utc=parse_iso_datetime(str(previous_state.get("last_wall_utc", ""))),
        now_utc=now,
        interval_seconds=interval_seconds,
        resume_gap_seconds=resume_gap_seconds,
    )
    inhibitor = (
        set_host_awake(
            active=bool(activity),
            hold_seconds=interval_seconds + 15,
            runner=runner,
        )
        if apply_host_awake
        else None
    )
    keeper = (
        run_service_keeper(runner=runner)
        if resume_detected and run_service_keeper_on_resume
        else None
    )
    payload = build_sleep_resilience_status(
        now_utc=now,
        previous_state=previous_state,
        recent_activity=activity,
        inhibitor_result=inhibitor,
        service_keeper_result=keeper,
        interval_seconds=interval_seconds,
        active_window_seconds=active_window_seconds,
        resume_gap_seconds=resume_gap_seconds,
    )
    write_sleep_resilience_status(payload, read_model_root=root)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orch-root", default=str(DEFAULT_ORCH_ROOT))
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--active-window-seconds", type=int, default=DEFAULT_ACTIVE_WINDOW_SECONDS)
    parser.add_argument("--resume-gap-seconds", type=int, default=DEFAULT_RESUME_GAP_SECONDS)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--apply-host-awake", action="store_true")
    parser.add_argument("--run-service-keeper-on-resume", action="store_true")
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    args = parser.parse_args(argv)

    while True:
        payload = run_once(
            orch_root=args.orch_root,
            read_model_root=args.read_model_root,
            interval_seconds=args.interval_seconds,
            active_window_seconds=args.active_window_seconds,
            resume_gap_seconds=args.resume_gap_seconds,
            apply_host_awake=args.apply_host_awake,
            run_service_keeper_on_resume=args.run_service_keeper_on_resume,
        )
        if args.format == "json":
            print(stable_json(payload), end="", flush=True)
        elif args.format == "operator":
            print(render_operator_summary(payload), end="", flush=True)
        else:
            print(
                "OpenClaw sleep resilience: "
                f"active={payload['active_work_visible']} "
                f"resume_gap={payload['resume_gap_detected']} "
                f"awake={payload['host_awake']['status']} "
                f"recovery={payload['resume_recovery']['status']}",
                flush=True,
            )
        if not args.loop:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
