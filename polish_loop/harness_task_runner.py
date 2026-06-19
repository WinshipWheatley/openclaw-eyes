#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import time
from datetime import datetime
from pathlib import Path

HARNESS_TIMEOUT_SECONDS = 300
APPROVED_DRY_RUN_HARNESSES: dict[str, dict[str, object]] = {
    "morning_brief": {
        "script": "/home/openclaw/morning_brief_harness.py",
        "required_args": ("--fixture",),
    },
    "local_model_benchmark": {
        "script": "/home/openclaw/openclaw_local_model_benchmark.py",
        "required_args": (),
    },
}


def _parse_frontmatter(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("# "):
            break
        if line.startswith("- "):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip().lower().replace(" ", "_")] = value.strip()
    return meta


def _qualifying_meta(task_path: Path) -> tuple[dict[str, str], str | None]:
    if not task_path.exists():
        return {}, "task file missing"
    meta = _parse_frontmatter(task_path.read_text(encoding="utf-8"))
    if meta.get("execution_mode") != "harness-backed-retest" and meta.get("harness_flow") is None:
        return meta, None
    if meta.get("execution_mode") != "harness-backed-retest":
        return meta, "missing or unsupported execution_mode"
    if meta.get("harness_mode") != "dry-run":
        return meta, "missing or unsupported harness_mode"
    harness_flow = meta.get("harness_flow", "")
    approved = APPROVED_DRY_RUN_HARNESSES.get(harness_flow)
    if not approved:
        return meta, "missing or unsupported harness_flow"
    entrypoint = meta.get("harness_entrypoint", "")
    if not entrypoint:
        return meta, "missing harness_entrypoint"
    try:
        argv = shlex.split(entrypoint)
    except ValueError:
        return meta, "malformed harness_entrypoint"
    if len(argv) < 2:
        return meta, "incomplete harness_entrypoint"
    if argv[0] != "python3" or argv[1] != str(approved["script"]):
        return meta, "unsupported harness_entrypoint"
    for required_arg in approved.get("required_args", ()):
        if required_arg not in argv:
            return meta, f"harness_entrypoint missing {required_arg}"
    return meta, "qualified"


def _write_pc_output(pc_output: Path, *, status: str, pass_num: int, changes: list[str], reasoning: list[str], rollback: list[str], truth: list[str], headroom: list[str], cost: list[str]) -> None:
    lines = [
        "RUNNER: harness",
        f"PASS: {pass_num}",
        f"STATUS: {status}",
        "",
        "CHANGES:",
        *[f"- {item}" for item in changes],
        "",
        "REASONING:",
        *[f"- {item}" for item in reasoning],
        "",
        "ROLLBACK PLAN:",
        *[f"- {item}" for item in rollback],
        "",
        "COST:",
        *[f"- {item}" for item in cost],
        "",
        "TRUTH:",
        *[f"- {item}" for item in truth],
        "",
        "HEADROOM:",
        *[f"- {item}" for item in headroom],
        "",
    ]
    pc_output.write_text("\n".join(lines), encoding="utf-8")


def _artifact_payload(meta: dict[str, str], *, result: str, started_at: str, finished_at: str, duration_ms: int, exit_code: int, stdout_path: Path, stderr_path: Path, detail: str) -> dict[str, object]:
    return {
        "result": result,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "harness_flow": meta.get("harness_flow"),
        "harness_entrypoint": meta.get("harness_entrypoint"),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "detail": detail,
    }


def _claim_ledger_task(db_path: str | None, task_id: str | None, owner: str, lease_seconds: int):
    if not db_path and not task_id:
        return None
    if not db_path or not task_id:
        raise SystemExit("--ledger-db and --ledger-task-id must be supplied together")
    try:
        from control_plane import ControlPlaneLedger
    except ImportError as exc:
        raise SystemExit(f"Phase-C ledger unavailable: {exc}") from exc
    ledger = ControlPlaneLedger(db_path)
    lease = ledger.claim_task(task_id, owner=owner, lease_seconds=lease_seconds)
    if lease is None:
        raise SystemExit(f"Phase-C ledger claim refused for task={task_id}")
    return ledger, lease


def _finish_ledger_task(ledger_claim, *, pc_output: Path, ok: bool, fingerprint: str) -> None:
    if ledger_claim is None:
        return
    ledger, lease = ledger_claim
    if ok and pc_output.exists():
        ledger.submit_candidate_evidence(
            lease.task_id,
            owner=lease.owner,
            lease_nonce=lease.lease_nonce,
            evidence={
                "runner": "harness_task_runner",
                "pc_output_path": str(pc_output),
            },
        )
    else:
        ledger.record_failure(
            lease.task_id,
            owner=lease.owner,
            lease_nonce=lease.lease_nonce,
            failure_fingerprint=fingerprint,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute the narrow harness-backed retest lane.")
    parser.add_argument("--task-file", type=Path, required=True)
    parser.add_argument("--pc-output", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--stdout-file", type=Path, required=True)
    parser.add_argument("--stderr-file", type=Path, required=True)
    parser.add_argument("--pass-num", type=int, required=True)
    parser.add_argument("--ledger-db")
    parser.add_argument("--ledger-task-id")
    parser.add_argument("--lease-owner", default="harness_task_runner")
    parser.add_argument("--lease-seconds", type=int, default=600)
    args = parser.parse_args()
    ledger_claim = _claim_ledger_task(
        args.ledger_db,
        args.ledger_task_id,
        args.lease_owner,
        args.lease_seconds,
    )

    meta, qualification = _qualifying_meta(args.task_file)
    if qualification is None:
        _finish_ledger_task(
            ledger_claim,
            pc_output=args.pc_output,
            ok=False,
            fingerprint="harness_not_qualified",
        )
        return 1

    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.stdout_file.parent.mkdir(parents=True, exist_ok=True)
    args.stderr_file.parent.mkdir(parents=True, exist_ok=True)

    started = datetime.now()
    t0 = time.monotonic()

    if qualification != "qualified":
        args.stdout_file.write_text("", encoding="utf-8")
        args.stderr_file.write_text(qualification, encoding="utf-8")
        finished = datetime.now()
        duration_ms = int((time.monotonic() - t0) * 1000)
        _write_pc_output(
            args.pc_output,
            status="BLOCKED",
            pass_num=args.pass_num,
            changes=["No live builder runner was launched."],
            reasoning=[f"Harness-backed retest failed closed: {qualification}."],
            rollback=["Fix the task harness metadata or demote the task back to advisory review."],
            cost=["No live builder spend was incurred."],
            truth=[
                "Verified: this task claimed the harness-backed retest lane.",
                f"Verified: execution stopped before live runner launch because {qualification}.",
            ],
            headroom=["Unknown: harness metadata was invalid, so no harness run occurred."],
        )
        args.artifact.write_text(
            json.dumps(
                _artifact_payload(
                    meta,
                    result="fail_closed",
                    started_at=started.isoformat(timespec="seconds"),
                    finished_at=finished.isoformat(timespec="seconds"),
                    duration_ms=duration_ms,
                    exit_code=0,
                    stdout_path=args.stdout_file,
                    stderr_path=args.stderr_file,
                    detail=qualification,
                ),
                indent=2,
            ),
            encoding="utf-8",
        )
        _finish_ledger_task(
            ledger_claim,
            pc_output=args.pc_output,
            ok=False,
            fingerprint=f"harness_fail_closed_{qualification}",
        )
        return 0

    # Clear any stale builder output so this lane can only succeed with fresh harness-owned evidence.
    args.pc_output.parent.mkdir(parents=True, exist_ok=True)
    args.pc_output.unlink(missing_ok=True)

    argv = shlex.split(meta["harness_entrypoint"])
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=HARNESS_TIMEOUT_SECONDS, check=False)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + "\nHarness timed out."
        exit_code = 124

    args.stdout_file.write_text(stdout, encoding="utf-8")
    args.stderr_file.write_text(stderr, encoding="utf-8")

    finished = datetime.now()
    duration_ms = int((time.monotonic() - t0) * 1000)
    run_dir = stdout.strip().splitlines()[-1].strip() if stdout.strip() else ""

    if exit_code == 0 and run_dir:
        args.artifact.write_text(
            json.dumps(
                _artifact_payload(
                    meta,
                    result="success",
                    started_at=started.isoformat(timespec="seconds"),
                    finished_at=finished.isoformat(timespec="seconds"),
                    duration_ms=duration_ms,
                    exit_code=exit_code,
                    stdout_path=args.stdout_file,
                    stderr_path=args.stderr_file,
                    detail=run_dir,
                ),
                indent=2,
            ),
            encoding="utf-8",
        )
        _write_pc_output(
            args.pc_output,
            status="DONE",
            pass_num=args.pass_num,
            changes=[
                "Executed the declared dry-run harness entrypoint instead of a live builder runner.",
                f"Harness run directory: {run_dir}",
                f"Harness execution artifact: {args.artifact}",
            ],
            reasoning=["This task qualified for the narrow auto-safe harness-backed retest lane and completed through the declared harness path."],
            rollback=["Archive the harness artifacts and re-run through the normal builder path only after review if needed."],
            cost=["Only local dry-run harness work was executed."],
            truth=[
                "Verified: no ordinary live builder runner was launched for this task.",
                f"Verified: harness flow {meta.get('harness_flow')} completed with exit code 0.",
                f"Verified: stdout artifact at {args.stdout_file}.",
                f"Verified: stderr artifact at {args.stderr_file}.",
            ],
            headroom=["Unknown: harness replay does not currently emit provider headroom."],
        )
        _finish_ledger_task(
            ledger_claim,
            pc_output=args.pc_output,
            ok=True,
            fingerprint="harness_success",
        )
    else:
        _write_pc_output(
            args.pc_output,
            status="BLOCKED",
            pass_num=args.pass_num,
            changes=["No live builder runner was launched."],
            reasoning=["Harness-backed retest ran the declared dry-run entrypoint and failed closed."],
            rollback=["Inspect the captured harness stdout/stderr artifacts before any retry or live-run promotion."],
            cost=["Only local dry-run harness work was attempted."],
            truth=[
                "Verified: no ordinary live builder runner was launched for this task.",
                f"Verified: harness execution ended with exit code {exit_code}.",
            ],
            headroom=["Unknown: harness execution did not produce a promotable result."],
        )
        result = "fail_closed"
        detail = f"exit_code={exit_code}"
        args.artifact.write_text(
            json.dumps(
                _artifact_payload(
                    meta,
                    result=result,
                    started_at=started.isoformat(timespec="seconds"),
                    finished_at=finished.isoformat(timespec="seconds"),
                    duration_ms=duration_ms,
                    exit_code=exit_code,
                    stdout_path=args.stdout_file,
                    stderr_path=args.stderr_file,
                    detail=detail,
                ),
                indent=2,
            ),
            encoding="utf-8",
        )
        _finish_ledger_task(
            ledger_claim,
            pc_output=args.pc_output,
            ok=False,
            fingerprint=f"harness_exit_{exit_code}",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
