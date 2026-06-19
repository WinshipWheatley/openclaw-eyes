#!/usr/bin/env python3
"""Finite Phase-C worker runtime.

The control plane owns admission, leases, and acceptance. This module is the
small runtime bridge that turns one live lease into one bounded local builder
invocation, then reports candidate evidence or failure back to the ledger.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

try:  # pragma: no cover - package import
    from .control_plane import (
        LOOP_DIR,
        ControlPlaneLedger,
        TaskLease,
        iso_now,
    )
except ImportError:  # pragma: no cover - script import from polish_loop/
    from control_plane import (  # type: ignore
        LOOP_DIR,
        ControlPlaneLedger,
        TaskLease,
        iso_now,
    )


_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclasses.dataclass(frozen=True)
class WorkerRuntimeConfig:
    """Paths and limits for one finite local builder invocation."""

    python: str = sys.executable
    local_builder_path: Path = LOOP_DIR / "local_builder.py"
    loop_dir: Path = LOOP_DIR
    task_path: Path = LOOP_DIR / "task.md"
    pc_output_path: Path = LOOP_DIR / "current" / "pc_output.md"
    artifact_dir: Path = LOOP_DIR / "current"
    model: str = "gemma4:e4b"
    timeout_seconds: int = 3600
    subprocess_timeout_seconds: int | None = None
    extra_env: dict[str, str] = dataclasses.field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "WorkerRuntimeConfig":
        return cls(
            python=os.environ.get("PHASE_C_WORKER_PYTHON", sys.executable),
            local_builder_path=Path(
                os.environ.get("PHASE_C_LOCAL_BUILDER", str(LOOP_DIR / "local_builder.py"))
            ),
            loop_dir=Path(os.environ.get("PHASE_C_LOOP_DIR", str(LOOP_DIR))),
            task_path=Path(os.environ.get("PHASE_C_TASK_MD", str(LOOP_DIR / "task.md"))),
            pc_output_path=Path(
                os.environ.get("PHASE_C_PC_OUTPUT", str(LOOP_DIR / "current" / "pc_output.md"))
            ),
            artifact_dir=Path(
                os.environ.get("PHASE_C_ARTIFACT_DIR", str(LOOP_DIR / "current"))
            ),
            model=os.environ.get("PHASE_C_BUILDER_MODEL", "gemma4:e4b"),
            timeout_seconds=int(os.environ.get("PHASE_C_BUILDER_TIMEOUT", "3600")),
            subprocess_timeout_seconds=(
                int(os.environ["PHASE_C_WORKER_SUBPROCESS_TIMEOUT"])
                if os.environ.get("PHASE_C_WORKER_SUBPROCESS_TIMEOUT")
                else None
            ),
        )


@dataclasses.dataclass(frozen=True)
class WorkerRuntimeResult:
    task_id: str
    exit_code: int
    submitted_candidate: bool
    failure_recorded: bool
    artifact_path: Path
    pc_output_path: Path
    fingerprint: str | None = None


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _safe_id(value: str) -> str:
    return _SAFE_ID_RE.sub("_", value).strip("._") or "task"


def _tail(text: str, limit: int = 6000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _task_markdown(row: dict[str, Any], lease: TaskLease) -> str:
    payload = row.get("payload") or {}
    return "\n".join(
        [
            f"task_id: {lease.task_id}",
            f"task_type: {row.get('type')}",
            f"source: {row.get('source')}",
            "execution_mode: phase-c-worker-runtime",
            f"lease_owner: {lease.owner}",
            f"attempt: {lease.attempt_no}",
            "",
            "# Phase-C Worker Runtime Task",
            "",
            "The SQLite control-plane ledger is authoritative for this task.",
            "Use this materialized file only as the finite worker input for the live lease.",
            "",
            "Payload JSON:",
            json.dumps(payload, indent=2, sort_keys=True),
            "",
            "Runtime rules:",
            "- Produce candidate evidence in pc_output.md.",
            "- Do not claim or inspect another task.",
            "- Do not send external messages, spend money, restart production, or access Legal material.",
        ]
    )


def _write_artifact(
    artifact_path: Path,
    *,
    lease: TaskLease,
    command: list[str],
    exit_code: int,
    stdout: str,
    stderr: str,
    pc_output_path: Path,
    detail: dict[str, Any] | None = None,
) -> None:
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "task_id": lease.task_id,
                "owner": lease.owner,
                "attempt_no": lease.attempt_no,
                "finished_at": iso_now(),
                "command": command,
                "exit_code": exit_code,
                "pc_output_path": str(pc_output_path),
                "stdout_tail": _tail(stdout),
                "stderr_tail": _tail(stderr),
                "detail": detail or {},
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def run_local_builder_worker(
    ledger: ControlPlaneLedger,
    lease: TaskLease,
    *,
    config: WorkerRuntimeConfig | None = None,
    runner: Runner = subprocess.run,
) -> WorkerRuntimeResult:
    """Run exactly one local builder process for an already-held lease."""

    cfg = config or WorkerRuntimeConfig.from_env()
    row = ledger.get_task(lease.task_id)
    if row["status"] != "LEASED" or row["owner"] != lease.owner:
        raise RuntimeError(f"lease is not live for task {lease.task_id}")

    cfg.task_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.pc_output_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.artifact_dir.mkdir(parents=True, exist_ok=True)
    cfg.task_path.write_text(_task_markdown(row, lease), encoding="utf-8")
    cfg.pc_output_path.unlink(missing_ok=True)

    command = [
        cfg.python,
        str(cfg.local_builder_path),
        "--model",
        cfg.model,
        "--timeout",
        str(cfg.timeout_seconds),
    ]
    artifact_path = (
        cfg.artifact_dir
        / f"worker_runtime_{_safe_id(lease.task_id)}_attempt_{lease.attempt_no}.json"
    )
    env = os.environ.copy()
    env.update(cfg.extra_env)
    env.update(
        {
            "PHASE_C_LEDGER_DB": str(ledger.path),
            "PHASE_C_TASK_ID": lease.task_id,
            "PHASE_C_LEASE_OWNER": lease.owner,
            "PHASE_C_LEASE_NONCE": lease.lease_nonce,
            "PHASE_C_ATTEMPT_NO": str(lease.attempt_no),
            "PHASE_C_TASK_MD": str(cfg.task_path),
            "PHASE_C_PC_OUTPUT": str(cfg.pc_output_path),
        }
    )
    timeout = cfg.subprocess_timeout_seconds or max(cfg.timeout_seconds + 30, 30)

    try:
        completed = runner(
            command,
            cwd=str(cfg.loop_dir.parent),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        exit_code = int(completed.returncode)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except FileNotFoundError as exc:
        exit_code = 127
        stdout = ""
        stderr = str(exc)
        _write_artifact(
            artifact_path,
            lease=lease,
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            pc_output_path=cfg.pc_output_path,
            detail={"failed_to_start": True},
        )
        ledger.record_failed_to_start(
            lease.task_id,
            actor=lease.owner,
            detail={"reason": "local_builder_missing", "error": stderr},
        )
        return WorkerRuntimeResult(
            task_id=lease.task_id,
            exit_code=exit_code,
            submitted_candidate=False,
            failure_recorded=True,
            artifact_path=artifact_path,
            pc_output_path=cfg.pc_output_path,
            fingerprint="worker_runtime_failed_to_start",
        )
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + "\nworker runtime timed out"

    _write_artifact(
        artifact_path,
        lease=lease,
        command=command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        pc_output_path=cfg.pc_output_path,
    )

    if exit_code == 0 and cfg.pc_output_path.exists():
        ledger.submit_candidate_evidence(
            lease.task_id,
            owner=lease.owner,
            lease_nonce=lease.lease_nonce,
            evidence={
                "runner": "local_builder",
                "worker_runtime": "phase_c_pc1",
                "pc_output_path": str(cfg.pc_output_path),
                "runtime_artifact_path": str(artifact_path),
                "task_md_path": str(cfg.task_path),
                "exit_code": exit_code,
                "attempt_no": lease.attempt_no,
            },
        )
        return WorkerRuntimeResult(
            task_id=lease.task_id,
            exit_code=exit_code,
            submitted_candidate=True,
            failure_recorded=False,
            artifact_path=artifact_path,
            pc_output_path=cfg.pc_output_path,
        )

    fingerprint = (
        f"worker_runtime_exit_{exit_code}_"
        f"{'missing_output' if not cfg.pc_output_path.exists() else 'nonzero'}"
    )
    ledger.record_failure(
        lease.task_id,
        owner=lease.owner,
        lease_nonce=lease.lease_nonce,
        failure_fingerprint=fingerprint,
    )
    return WorkerRuntimeResult(
        task_id=lease.task_id,
        exit_code=exit_code,
        submitted_candidate=False,
        failure_recorded=True,
        artifact_path=artifact_path,
        pc_output_path=cfg.pc_output_path,
        fingerprint=fingerprint,
    )
