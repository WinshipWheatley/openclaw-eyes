#!/usr/bin/env python3
"""Deterministic one-tick fleet autoscaler for OpenClaw build workers.

This script intentionally does not run an infinite loop. Supervisors can invoke
it on a timer; each tick observes queue/gate state, optionally spawns one
exit-on-complete worker, writes telemetry, and exits.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence


DEFAULT_WORKSPACE = Path("/mnt/e/openclaw/orchestration")
DEFAULT_REPO_ROOT = Path("/home/openclaw")
DEFAULT_TELEMETRY_PATH = Path("generated/read_models/fleet_telemetry.json")
BUILD_TASK_RE = re.compile(r"^\d{3,4}-BUILD-.+\.md$")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _task_key(path: Path) -> str:
    return path.name.split("-", 1)[0].lower()


def _claim_texts(inbox_dir: Path) -> list[str]:
    texts: list[str] = []
    for path in sorted(inbox_dir.glob("*CLAIM*.md")):
        texts.append(path.name.lower())
        try:
            texts.append(path.read_text(encoding="utf-8").lower())
        except OSError:
            pass
    return texts


def claim_exists(task_path: Path, inbox_dir: Path) -> bool:
    key = _task_key(task_path)
    slug = task_path.stem.lower()
    for text in _claim_texts(inbox_dir):
        if key and key in text:
            return True
        if slug and slug in text:
            return True
    return False


def pending_build_tasks(to_pc_dir: Path, inbox_dir: Path) -> list[Path]:
    if not to_pc_dir.exists():
        return []
    tasks = []
    for path in sorted(to_pc_dir.glob("*.md")):
        if not BUILD_TASK_RE.match(path.name):
            continue
        if claim_exists(path, inbox_dir):
            continue
        tasks.append(path)
    return tasks


def _process_lines(pattern: str) -> list[str]:
    completed = subprocess.run(["pgrep", "-af", pattern], text=True, capture_output=True, check=False)
    if completed.returncode not in {0, 1}:
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def gate_running(process_lines: Sequence[str] | None = None) -> bool:
    lines = list(process_lines) if process_lines is not None else _process_lines("green_gate.sh|pytest -q -rA")
    current_pid = str(os.getpid())
    for line in lines:
        if current_pid in line:
            continue
        if "green_gate.sh" in line or "pytest -q -rA" in line:
            return True
    return False


def active_worker_lines(process_lines: Sequence[str] | None = None) -> list[str]:
    lines = list(process_lines) if process_lines is not None else _process_lines("OPENCLAW_AUTOSCALER_WORKER|EXIT_ON_COMPLETE=1|openclaw_run.py")
    return [line for line in lines if "openclaw_fleet_autoscaler.py" not in line]


def _default_worker_command(repo_root: Path) -> list[str]:
    configured = os.environ.get("OPENCLAW_AUTOSCALER_WORKER_COMMAND", "").strip()
    if configured:
        return shlex.split(configured)
    return [sys.executable, str(repo_root / "scripts" / "openclaw_run.py"), "status"]


def _spawn_env(base_env: Mapping[str, str], task_path: Path) -> dict[str, str]:
    env = dict(base_env)
    env.update(
        {
            "EXIT_ON_COMPLETE": "1",
            "OPENCLAW_AUTOSCALER_WORKER": "1",
            "OPENCLAW_SEND_HOLD": "1",
            "OPENCLAW_TEST_MODE": "1",
            "OPENCLAW_DIRECTIVE_PATH": task_path.as_posix(),
        }
    )
    return env


def spawn_worker(
    task_path: Path,
    *,
    repo_root: Path,
    popen: Callable[..., Any] = subprocess.Popen,
    base_env: Mapping[str, str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    command = _default_worker_command(repo_root)
    env = _spawn_env(base_env or os.environ, task_path)
    if dry_run:
        return {"spawned": False, "dry_run": True, "pid": None, "command": command, "env": env}
    proc = popen(
        command,
        cwd=str(repo_root),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {"spawned": True, "dry_run": False, "pid": int(getattr(proc, "pid", 0) or 0), "command": command, "env": env}


def write_telemetry(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(dict(payload)), encoding="utf-8")


def tick(
    *,
    workspace: Path = DEFAULT_WORKSPACE,
    repo_root: Path = DEFAULT_REPO_ROOT,
    telemetry_path: Path | None = None,
    process_lines: Sequence[str] | None = None,
    popen: Callable[..., Any] = subprocess.Popen,
    dry_run: bool = False,
    max_workers: int = 1,
) -> dict[str, Any]:
    loop_dir = workspace / "loop"
    to_pc_dir = loop_dir / "to-pc"
    inbox_dir = workspace / "inbox" / "to-claude"
    tasks = pending_build_tasks(to_pc_dir, inbox_dir)
    workers = active_worker_lines(process_lines)
    gate_busy = gate_running(process_lines)
    capacity_available = len(workers) < max_workers
    spawn_result: dict[str, Any] | None = None

    if tasks and not gate_busy and capacity_available:
        spawn_result = spawn_worker(tasks[0], repo_root=repo_root, popen=popen, dry_run=dry_run)

    telemetry = {
        "schema_version": "fleet_telemetry_v0",
        "generated_at": _utc_now(),
        "workspace": workspace.as_posix(),
        "repo_root": repo_root.as_posix(),
        "queued_task_count": len(tasks),
        "queued_tasks": [path.name for path in tasks],
        "gate_running": gate_busy,
        "gate_available": not gate_busy,
        "active_worker_count": len(workers),
        "active_worker_lines": list(workers)[:8],
        "max_workers": max_workers,
        "spawned": bool(spawn_result and spawn_result.get("spawned")),
        "dry_run": bool(spawn_result and spawn_result.get("dry_run")),
        "spawned_task": tasks[0].name if spawn_result and tasks else "",
        "spawned_pid": spawn_result.get("pid") if spawn_result else None,
        "exit_on_complete_enforced": bool(spawn_result and spawn_result.get("env", {}).get("EXIT_ON_COMPLETE") == "1"),
        "send_hold_enforced": bool(spawn_result and spawn_result.get("env", {}).get("OPENCLAW_SEND_HOLD") == "1"),
        "test_mode_enforced": bool(spawn_result and spawn_result.get("env", {}).get("OPENCLAW_TEST_MODE") == "1"),
    }
    target = telemetry_path or repo_root / DEFAULT_TELEMETRY_PATH
    write_telemetry(target, telemetry)
    return telemetry


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one deterministic OpenClaw fleet autoscaler tick.")
    parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--telemetry-path", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-workers", type=int, default=1)
    args = parser.parse_args(list(argv) if argv is not None else None)

    telemetry_path = Path(args.telemetry_path) if args.telemetry_path else None
    payload = tick(
        workspace=Path(args.workspace),
        repo_root=Path(args.repo_root),
        telemetry_path=telemetry_path,
        dry_run=bool(args.dry_run),
        max_workers=max(1, int(args.max_workers)),
    )
    print(stable_json(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
