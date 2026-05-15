#!/usr/bin/env python3
"""Local macOS marker-triggered generated read-model sync agent."""

from __future__ import annotations

import argparse
import hashlib
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


def default_status_marker(share_root: str | Path = DEFAULT_SHARE_ROOT) -> Path:
    return Path(share_root) / "shuttle" / "from_mac" / "read_model_sync_agent_status.json"


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_head(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "remote_control_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "model_execution_allowed": False,
    "network_authority": False,
    "docker_allowed": False,
    "ollama_allowed": False,
    "file_delete_allowed": False,
    "file_move_allowed": False,
    "destructive_file_operations": False,
}


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
        "mission_control_modified": False,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
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


def read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def marker_already_completed(request_marker: Path, completion_marker: Path) -> bool:
    if not completion_marker.is_file():
        return False
    completion = read_json_object(completion_marker)
    if not completion or completion.get("status") != "synced":
        return False
    try:
        return completion_marker.stat().st_mtime >= request_marker.stat().st_mtime
    except OSError:
        return False


def write_json_marker(path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    marker = Path(path)
    marker.parent.mkdir(parents=True, exist_ok=True)
    data = stable_json(payload)
    try:
        marker.write_text(data, encoding="utf-8")
        return {"marker_path": marker.as_posix(), "write_method": "direct"}
    except OSError as direct_error:
        temp = marker.with_name(f".{marker.name}.tmp.{os.getpid()}")
        temp.write_text(data, encoding="utf-8")
        temp.replace(marker)
        return {
            "marker_path": marker.as_posix(),
            "write_method": "replace_after_direct_failed",
            "direct_write_error": str(direct_error),
        }


def parse_sync_report(stdout: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def sync_report_proof(sync_report: dict[str, Any] | None, manifest_path: Path) -> dict[str, Any]:
    mac_sync = (sync_report or {}).get("mac_sync") or {}
    observed_manifest = Path(mac_sync.get("pc_drop_manifest_path") or manifest_path)
    manifest_written = observed_manifest.is_file()
    manifest_sha = mac_sync.get("manifest_sha256")
    if manifest_written and not manifest_sha:
        manifest_sha = sha256_file(observed_manifest)
    return {
        "manifest_path": observed_manifest.as_posix(),
        "manifest_written": manifest_written,
        "manifest_sha256": manifest_sha,
        "copied_file_count": mac_sync.get("copied_count"),
        "git_pull": mac_sync.get("git_pull"),
        "sync_report_status": (sync_report or {}).get("status"),
    }


def heartbeat_payload(
    *,
    status: str,
    repo_root: Path,
    marker_seen: bool,
    manifest_written: bool = False,
    manifest_sha256: str | None = None,
    copied_file_count: int | None = None,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "agent_version": AGENT_VERSION,
        "generated_at": utc_now(),
        "status": status,
        "backend_head": repo_head(repo_root),
        "marker_seen": marker_seen,
        "manifest_written": manifest_written,
        "manifest_sha256": manifest_sha256,
        "copied_file_count": copied_file_count,
        "error": error,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    if extra:
        payload.update(extra)
    return payload


def completion_payload(
    *,
    backend_head: str | None,
    manifest_path: str,
    manifest_sha256: str | None,
    copied_file_count: int | None,
    status: str = "synced",
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "agent_version": AGENT_VERSION,
        "generated_at": utc_now(),
        "status": status,
        "backend_head": backend_head,
        "manifest_path": manifest_path,
        "manifest_sha256": manifest_sha256,
        "copied_file_count": copied_file_count,
        "error": error,
        "source": "mac_read_model_sync_agent",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


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
    status_marker: str | Path | None = None,
    manifest_path: str | Path | None = None,
    log_path: str | Path = DEFAULT_LOG_PATH,
    repo_root: str | Path = ROOT,
    sync_script: str | Path = DEFAULT_SYNC_SCRIPT,
    python_executable: str = sys.executable,
    pull: bool = True,
    sync_output_format: str = "json",
    timeout_seconds: int = 600,
    runner: Runner = default_runner,
) -> dict[str, Any]:
    share = Path(share_root)
    request = Path(request_marker) if request_marker else default_request_marker(share)
    completion = Path(completion_marker) if completion_marker else default_completion_marker(share)
    status_path = Path(status_marker) if status_marker else default_status_marker(share)
    manifest = Path(manifest_path) if manifest_path else share / "mac_generated_read_models_manifest.json"
    repo = Path(repo_root).expanduser().resolve()

    if not share.is_dir():
        heartbeat = heartbeat_payload(
            status="share_missing",
            repo_root=repo,
            marker_seen=False,
            error=f"share root is not mounted: {share}",
        )
        status = _base_status(
            status="share_missing",
            share_root=share,
            request_marker=request,
            completion_marker=completion,
            repo_root=repo,
            status_marker=status_path.as_posix(),
            marker_seen=False,
            manifest_written=False,
            heartbeat=heartbeat,
        )
        append_log(log_path, "share_missing", share_root=share.as_posix())
        return status

    if not request.is_file():
        heartbeat = heartbeat_payload(
            status="skipped_no_marker",
            repo_root=repo,
            marker_seen=False,
        )
        heartbeat_result = write_json_marker(status_path, heartbeat)
        status = _base_status(
            status="skipped_no_marker",
            share_root=share,
            request_marker=request,
            completion_marker=completion,
            repo_root=repo,
            status_marker=status_path.as_posix(),
            marker_seen=False,
            manifest_written=False,
            heartbeat=heartbeat,
            heartbeat_written=True,
            heartbeat_write=heartbeat_result,
        )
        append_log(log_path, "skipped_no_marker", request_marker=request.as_posix())
        return status

    marker_payload = read_marker_payload(request)
    if marker_already_completed(request, completion):
        manifest_written = manifest.is_file()
        manifest_sha = sha256_file(manifest) if manifest_written else None
        heartbeat = heartbeat_payload(
            status="idle",
            repo_root=repo,
            marker_seen=True,
            manifest_written=manifest_written,
            manifest_sha256=manifest_sha,
            extra={
                "request_marker": request.as_posix(),
                "completion_marker": completion.as_posix(),
                "manifest_path": manifest.as_posix(),
                "reason": "request marker already has a newer synced completion marker",
            },
        )
        heartbeat_result = write_json_marker(status_path, heartbeat)
        append_log(
            log_path,
            "marker_already_completed",
            request_marker=request.as_posix(),
            completion_marker=completion.as_posix(),
            manifest_written=manifest_written,
            **marker_payload,
        )
        return _base_status(
            status="idle",
            share_root=share,
            request_marker=request,
            completion_marker=completion,
            repo_root=repo,
            status_marker=status_path.as_posix(),
            marker_seen=True,
            manifest_written=manifest_written,
            manifest_sha256=manifest_sha,
            heartbeat=heartbeat,
            heartbeat_written=True,
            heartbeat_write=heartbeat_result,
            **marker_payload,
        )

    command = build_sync_command(
        python_executable=python_executable,
        sync_script=sync_script,
        pull=pull,
        output_format=sync_output_format,
    )
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    append_log(log_path, "marker_detected", request_marker=request.as_posix(), **marker_payload)
    append_log(log_path, "sync_started", request_marker=request.as_posix(), command=command, repo_root=repo.as_posix())
    if pull:
        append_log(log_path, "git_pull_requested", behavior="sync runner will run git pull origin main")

    try:
        completed = runner(command, repo, env, timeout_seconds)
        sync_exit_code = completed.returncode
        sync_report = parse_sync_report(completed.stdout)
        proof = sync_report_proof(sync_report, manifest)
        status_name = "synced" if sync_exit_code == 0 else "error"
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
            failure_reason="sync_exit_code_nonzero" if sync_exit_code != 0 else None,
            failure_detail=_tail(completed.stderr, 1000) if sync_exit_code != 0 else None,
            status_marker=status_path.as_posix(),
            marker_seen=True,
            sync_report=sync_report,
            **proof,
            **marker_payload,
        )
        append_log(log_path, "sync_finished", sync_exit_code=sync_exit_code, status=status_name)
        if proof.get("git_pull"):
            append_log(log_path, "git_pull_finished", git_pull=proof["git_pull"])
        append_log(
            log_path,
            "manifest_observed",
            manifest_path=proof["manifest_path"],
            manifest_written=proof["manifest_written"],
            manifest_sha256=proof["manifest_sha256"],
            copied_file_count=proof["copied_file_count"],
        )
    except subprocess.TimeoutExpired as exc:
        sync_exit_code = 124
        status = _base_status(
            status="error",
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
            status_marker=status_path.as_posix(),
            marker_seen=True,
            manifest_written=False,
            manifest_path=manifest.as_posix(),
            **marker_payload,
        )
    except OSError as exc:
        sync_exit_code = 1
        status = _base_status(
            status="error",
            share_root=share,
            request_marker=request,
            completion_marker=completion,
            repo_root=repo,
            command=command,
            exit_code=sync_exit_code,
            sync_exit_code=sync_exit_code,
            failure_reason=type(exc).__name__,
            failure_detail=str(exc),
            status_marker=status_path.as_posix(),
            marker_seen=True,
            manifest_written=False,
            manifest_path=manifest.as_posix(),
            **marker_payload,
        )

    heartbeat = heartbeat_payload(
        status=status["status"],
        repo_root=repo,
        marker_seen=True,
        manifest_written=bool(status.get("manifest_written")),
        manifest_sha256=status.get("manifest_sha256"),
        copied_file_count=status.get("copied_file_count"),
        error=status.get("failure_detail") or status.get("failure_reason"),
        extra={
            "request_marker": request.as_posix(),
            "completion_marker": completion.as_posix(),
            "manifest_path": status.get("manifest_path"),
        },
    )
    try:
        heartbeat_result = write_json_marker(status_path, heartbeat)
        status["heartbeat_written"] = True
        status["heartbeat_write"] = heartbeat_result
        append_log(log_path, "heartbeat_written", **heartbeat_result)
    except OSError as exc:
        append_log(log_path, "heartbeat_write_failed", status_marker=status_path.as_posix(), error=str(exc))
        status["heartbeat_written"] = False
        status["heartbeat_error"] = str(exc)
        return {**status, "exit_code": 1}

    completion_record = completion_payload(
        backend_head=heartbeat["backend_head"],
        manifest_path=status.get("manifest_path") or manifest.as_posix(),
        manifest_sha256=status.get("manifest_sha256"),
        copied_file_count=status.get("copied_file_count"),
        status=status["status"],
        error=status.get("failure_detail") or status.get("failure_reason"),
    )
    try:
        completion_result = write_json_marker(completion, completion_record)
    except OSError as exc:
        append_log(log_path, "completion_marker_write_failed", completion_marker=completion.as_posix(), error=str(exc))
        status["completion_marker_written"] = False
        status["completion_marker_error"] = str(exc)
        status["exit_code"] = 1
        return status

    status["completion_marker_written"] = True
    status["completion_marker_write"] = completion_result
    append_log(log_path, "completion_marker_written", **completion_result)
    append_log(log_path, "sync_completed" if status["status"] == "synced" else "sync_failed", completion_marker=completion.as_posix(), sync_exit_code=sync_exit_code)
    return status


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one local Mac read-model sync check from an E-drive marker."
    )
    parser.add_argument("--share-root", default=DEFAULT_SHARE_ROOT.as_posix())
    parser.add_argument("--request-marker")
    parser.add_argument("--completion-marker")
    parser.add_argument("--status-marker")
    parser.add_argument("--manifest-path")
    parser.add_argument("--log-path", default=DEFAULT_LOG_PATH.as_posix())
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--sync-script", default=DEFAULT_SYNC_SCRIPT.as_posix())
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--no-pull", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    parser.add_argument("--sync-output-format", choices=("operator", "json"), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    status = run_agent_once(
        share_root=args.share_root,
        request_marker=args.request_marker,
        completion_marker=args.completion_marker,
        status_marker=args.status_marker,
        manifest_path=args.manifest_path,
        log_path=args.log_path,
        repo_root=args.repo_root,
        sync_script=args.sync_script,
        python_executable=args.python_executable,
        pull=not args.no_pull,
        sync_output_format=args.sync_output_format,
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
                    f"Status marker: `{status.get('status_marker')}`",
                    f"Manifest written: {str(status.get('manifest_written', False)).lower()}",
                    f"Exit code: {status['exit_code']}",
                ]
            )
        )
    return int(status["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
