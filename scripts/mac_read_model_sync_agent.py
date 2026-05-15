#!/usr/bin/env python3
"""Local macOS marker-triggered generated read-model sync agent."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]

AGENT_VERSION = "openclaw.mac_read_model_sync_agent.v0"
DEFAULT_SHARE_ROOT = Path("/Volumes/openclaw_e")
DEFAULT_LOG_PATH = Path("~/Library/Logs/OpenClaw/read_model_sync_agent.log")
DEFAULT_SYNC_SCRIPT = Path("scripts/sync_read_model_mirror.py")

Runner = Callable[
    [list[str], Path, dict[str, str], int],
    subprocess.CompletedProcess[str],
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def default_request_marker(share_root: str | Path = DEFAULT_SHARE_ROOT) -> Path:
    return Path(share_root) / "shuttle" / "to_mac" / "read_model_sync_required.json"


def default_completion_marker(share_root: str | Path = DEFAULT_SHARE_ROOT) -> Path:
    return Path(share_root) / "shuttle" / "from_mac" / "read_model_sync_completed.json"


def append_log(log_path: str | Path, event: str, **fields: Any) -> None:
    path = Path(log_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "agent_version": AGENT_VERSION,
        "event": event,
        "logged_at": utc_now(),
        **fields,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(stable_json(payload).strip() + "\n")


def build_sync_command(
    *,
    python_executable: str = "python3",
    sync_script: str | Path = DEFAULT_SYNC_SCRIPT,
    pull: bool = True,
    output_format: str = "operator",
) -> list[str]:
    command = [python_executable, Path(sync_script).as_posix()]
    if pull:
        command.append("--pull")
    command.extend(["--format", output_format])
    return command


def _base_status(
    *,
    status: str,
    share_root: Path,
    request_marker: Path,
    completion_marker: Path,
    repo_root: Path,
    command: list[str] | None = None,
    exit_code: int = 0,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "agent_version": AGENT_VERSION,
        "status": status,
        "generated_at": utc_now(),
        "share_root": share_root.as_posix(),
        "request_marker": request_marker.as_posix(),
        "completion_marker": completion_marker.as_posix(),
        "repo_root": repo_root.as_posix(),
        "command": command,
        "exit_code": exit_code,
        "request_marker_deleted": False,
        "runtime_authority": False,
        "remote_control_allowed": False,
        "agent_activation_allowed": False,
        "docker_allowed": False,
        "ollama_allowed": False,
        "mission_control_modified": False,
        "destructive_file_operations": False,
        **extra,
    }


def read_marker_payload(marker_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"marker_json_valid": False, "marker_parse_error": str(exc)}
    except OSError as exc:
        return {"marker_json_valid": False, "marker_read_error": str(exc)}
    if not isinstance(payload, dict):
        return {"marker_json_valid": False, "marker_payload_type": type(payload).__name__}
    return {"marker_json_valid": True, "marker_payload": payload}


def write_completion_marker(path: str | Path, payload: dict[str, Any]) -> None:
    marker = Path(path)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(stable_json(payload), encoding="utf-8")


def default_runner(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
    )


def _tail(value: str | bytes | None, limit: int = 4000) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value[-limit:]


def run_agent_once(
    *,
    share_root: str | Path = DEFAULT_SHARE_ROOT,
    request_marker: str | Path | None = None,
    completion_marker: str | Path | None = None,
    log_path: str | Path = DEFAULT_LOG_PATH,
    repo_root: str | Path = ROOT,
    sync_script: str | Path = DEFAULT_SYNC_SCRIPT,
    python_executable: str = "python3",
    pull: bool = True,
    output_format: str = "operator",
    timeout_seconds: int = 600,
    runner: Runner = default_runner,
) -> dict[str, Any]:
    share = Path(share_root)
    request = Path(request_marker) if request_marker else default_request_marker(share)
    completion = Path(completion_marker) if completion_marker else default_completion_marker(share)
    repo = Path(repo_root).expanduser().resolve()

    if not share.is_dir():
        status = _base_status(
            status="share_missing",
            share_root=share,
            request_marker=request,
            completion_marker=completion,
            repo_root=repo,
        )
        append_log(log_path, "share_missing", share_root=share.as_posix())
        return status

    if not request.is_file():
        status = _base_status(
            status="marker_missing",
            share_root=share,
            request_marker=request,
            completion_marker=completion,
            repo_root=repo,
        )
        append_log(log_path, "marker_missing", request_marker=request.as_posix())
        return status

    command = build_sync_command(
        python_executable=python_executable,
        sync_script=sync_script,
        pull=pull,
        output_format=output_format,
    )
    marker_payload = read_marker_payload(request)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    append_log(
        log_path,
        "sync_started",
        request_marker=request.as_posix(),
        command=command,
        repo_root=repo.as_posix(),
    )

    try:
        completed = runner(command, repo, env, timeout_seconds)
        sync_exit_code = completed.returncode
        status_name = "success" if sync_exit_code == 0 else "failure"
        status = _base_status(
            status=status_name,
            share_root=share,
            request_marker=request,
            completion_marker=completion,
            repo_root=repo,
            command=command,
            exit_code=sync_exit_code,
            sync_exit_code=sync_exit_code,
            sync_stdout_tail=_tail(completed.stdout),
            sync_stderr_tail=_tail(completed.stderr),
            **marker_payload,
        )
    except subprocess.TimeoutExpired as exc:
        sync_exit_code = 124
        status = _base_status(
            status="failure",
            share_root=share,
            request_marker=request,
            completion_marker=completion,
            repo_root=repo,
            command=command,
            exit_code=sync_exit_code,
            sync_exit_code=sync_exit_code,
            sync_stdout_tail=_tail(exc.stdout),
            sync_stderr_tail=_tail(exc.stderr),
            failure_reason="timeout",
            **marker_payload,
        )
    except OSError as exc:
        sync_exit_code = 1
        status = _base_status(
            status="failure",
            share_root=share,
            request_marker=request,
            completion_marker=completion,
            repo_root=repo,
            command=command,
            exit_code=sync_exit_code,
            sync_exit_code=sync_exit_code,
            failure_reason=type(exc).__name__,
            failure_detail=str(exc),
            **marker_payload,
        )

    try:
        write_completion_marker(completion, status)
    except OSError as exc:
        append_log(
            log_path,
            "completion_marker_write_failed",
            completion_marker=completion.as_posix(),
            error=str(exc),
        )
        status["completion_marker_written"] = False
        status["completion_marker_error"] = str(exc)
        return {**status, "exit_code": 1}

    status["completion_marker_written"] = True
    write_completion_marker(completion, status)
    append_log(
        log_path,
        "sync_completed" if status["status"] == "success" else "sync_failed",
        completion_marker=completion.as_posix(),
        sync_exit_code=sync_exit_code,
    )
    return status


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one local Mac read-model sync check from an E-drive marker."
    )
    parser.add_argument("--share-root", default=DEFAULT_SHARE_ROOT.as_posix())
    parser.add_argument("--request-marker")
    parser.add_argument("--completion-marker")
    parser.add_argument("--log-path", default=DEFAULT_LOG_PATH.as_posix())
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--sync-script", default=DEFAULT_SYNC_SCRIPT.as_posix())
    parser.add_argument("--python-executable", default="python3")
    parser.add_argument("--no-pull", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    status = run_agent_once(
        share_root=args.share_root,
        request_marker=args.request_marker,
        completion_marker=args.completion_marker,
        log_path=args.log_path,
        repo_root=args.repo_root,
        sync_script=args.sync_script,
        python_executable=args.python_executable,
        pull=not args.no_pull,
        output_format=args.format,
        timeout_seconds=args.timeout_seconds,
    )
    if args.format == "json":
        print(stable_json(status), end="")
    else:
        print(
            "\n".join(
                [
                    "Mac Read-Model Sync Agent v0",
                    "",
                    f"Status: {status['status']}",
                    f"Share: `{status['share_root']}`",
                    f"Request marker: `{status['request_marker']}`",
                    f"Completion marker: `{status['completion_marker']}`",
                    f"Exit code: {status['exit_code']}",
                ]
            )
        )
    return int(status["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
