#!/usr/bin/env python3
"""Local PC/WSL generated read-model mirror import agent."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from corpus_atlas import stable_json
from generated_read_model_files import VOLATILE_SELF_REPORT_READ_MODEL_FILES
from read_model_shuttle import (
    DEFAULT_IMPORT_MANIFEST_PATH,
    DEFAULT_RETURNED_MANIFEST_PATH,
)
from scripts.import_latest_mac_read_model_mirror import import_latest_mac_read_model_mirror
from sync_health import refresh_sync_health_from_manifest


AGENT_VERSION = "openclaw.pc_read_model_import_agent.v0"
DEFAULT_COMPLETION_MARKER_PATH = (
    Path("/mnt/e/openclaw") / "shuttle" / "from_mac" / "read_model_sync_completed.json"
)
DEFAULT_STATE_PATH = ROOT / ".openclaw" / "state" / "read_model_import_agent_state.json"
DEFAULT_LOG_PATH = ROOT / ".openclaw" / "logs" / "read_model_import_agent.log"
DEFAULT_REQUEST_MARKER_PATH = Path("/mnt/e/openclaw") / "shuttle" / "to_mac" / "read_model_sync_required.json"
FINAL_MAC_MIRROR_LIFECYCLE_STATE = "health_exported_waiting_for_mac_mirror"
SELF_REPORT_FILES = frozenset(VOLATILE_SELF_REPORT_READ_MODEL_FILES)

Importer = Callable[..., dict[str, Any]]
SyncHealthRefresher = Callable[..., dict[str, Any]]

NO_AUTHORITY_FLAGS = {
    "remote_control_allowed": False,
    "runtime_authority": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "model_execution_allowed": False,
    "container_execution_allowed": False,
    "docker_allowed": False,
    "ollama_allowed": False,
    "network_authority": False,
    "mission_control_modified": False,
    "generated_contracts_modified": False,
    "file_delete_allowed": False,
    "file_move_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_log(log_path: str | Path, event: str, **fields: Any) -> None:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "agent_version": AGENT_VERSION,
        "event": event,
        "logged_at": utc_now(),
        **fields,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def load_state(state_path: str | Path) -> dict[str, Any]:
    path = Path(state_path)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"state_read_error": True}
    return payload if isinstance(payload, dict) else {"state_read_error": True}


def write_state(state_path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _read_json_object(path: str | Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _manifest_hashes_by_path(path: str | Path) -> dict[str, str]:
    payload = _read_json_object(path) or {}
    records = payload.get("path_records") or []
    hashes: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        relative_path = record.get("relative_path")
        content_hash = record.get("content_hash")
        if isinstance(relative_path, str) and isinstance(content_hash, str):
            hashes[relative_path] = content_hash
    return hashes


def manifest_change_is_self_report_only(*, previous_manifest: str | Path, current_manifest: str | Path) -> bool:
    previous = Path(previous_manifest)
    current = Path(current_manifest)
    if not previous.is_file() or not current.is_file():
        return False
    previous_hashes = _manifest_hashes_by_path(previous)
    current_hashes = _manifest_hashes_by_path(current)
    if not previous_hashes or not current_hashes:
        return False
    non_self_paths = (set(previous_hashes) | set(current_hashes)) - SELF_REPORT_FILES
    if any(previous_hashes.get(path) != current_hashes.get(path) for path in non_self_paths):
        return False
    return any(previous_hashes.get(path) != current_hashes.get(path) for path in SELF_REPORT_FILES)


def _marker_pending(request_marker: Path, completion_marker: Path) -> bool:
    if not request_marker.is_file():
        return False
    if not completion_marker.is_file():
        return True
    try:
        return request_marker.stat().st_mtime > completion_marker.stat().st_mtime
    except OSError:
        return True


def write_final_mac_mirror_marker_if_needed(
    *,
    sync_health_refresh: dict[str, Any],
    request_marker_path: str | Path = DEFAULT_REQUEST_MARKER_PATH,
    completion_marker_path: str | Path = DEFAULT_COMPLETION_MARKER_PATH,
) -> dict[str, Any]:
    request_marker = Path(request_marker_path)
    completion_marker = Path(completion_marker_path)
    lifecycle = sync_health_refresh.get("sync_lifecycle_state")
    if lifecycle != FINAL_MAC_MIRROR_LIFECYCLE_STATE:
        return {
            "final_mac_mirror_marker_needed": False,
            "final_mac_mirror_marker_written": False,
            "reason": "sync health lifecycle does not need a final Mac mirror leg",
            "sync_lifecycle_state": lifecycle,
        }
    if _marker_pending(request_marker, completion_marker):
        return {
            "final_mac_mirror_marker_needed": True,
            "final_mac_mirror_marker_written": False,
            "reason": "existing request marker is still pending Mac completion",
            "request_marker_path": request_marker.as_posix(),
            "sync_lifecycle_state": lifecycle,
        }
    import datetime as _datetime

    request_marker.parent.mkdir(parents=True, exist_ok=True)
    marker = {
        "schema_version": "read_model_sync_required_v0",
        "generated_at": _datetime.datetime.now(_datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "reason": "PC sync health/read-model export is refreshed; mirror generated read-models back to Mac through the normal sync agent.",
        "requested_by": "pc_read_model_import_agent",
        "next_expected_responder": "mac_read_model_sync_agent",
        "sync_lifecycle_state": lifecycle,
        "operator_action_required": False,
        "missing_expected_files": [],
        "hash_mismatch_files": [],
        "manual_fallback_mac_command": "cd ~/Developer/OpenClawBackend/openclaw\nPYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_read_model_mirror.py --pull --format operator",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    request_marker.write_text(stable_json(marker), encoding="utf-8")
    return {
        "final_mac_mirror_marker_needed": True,
        "final_mac_mirror_marker_written": True,
        "reason": marker["reason"],
        "request_marker_path": request_marker.as_posix(),
        "sync_lifecycle_state": lifecycle,
    }


def _completion_marker_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "completion_marker_present": False,
        }
    stat = path.stat()
    return {
        "completion_marker_present": True,
        "completion_marker_size_bytes": stat.st_size,
        "completion_marker_mtime": stat.st_mtime,
        "completion_marker_sha256": sha256_file(path),
    }


def _base_status(
    *,
    status: str,
    manifest_path: Path,
    completion_marker_path: Path,
    state_path: Path,
    log_path: Path,
    exit_code: int = 0,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "agent_version": AGENT_VERSION,
        "status": status,
        "generated_at": utc_now(),
        "manifest_path": manifest_path.as_posix(),
        "completion_marker_path": completion_marker_path.as_posix(),
        "state_path": state_path.as_posix(),
        "log_path": log_path.as_posix(),
        "exit_code": exit_code,
        "manifest_deleted": False,
        "completion_marker_deleted": False,
        "manifest_moved": False,
        **NO_AUTHORITY_FLAGS,
        **extra,
    }


def run_import_agent_once(
    *,
    manifest_path: str | Path = DEFAULT_RETURNED_MANIFEST_PATH,
    completion_marker_path: str | Path = DEFAULT_COMPLETION_MARKER_PATH,
    state_path: str | Path = DEFAULT_STATE_PATH,
    log_path: str | Path = DEFAULT_LOG_PATH,
    db_path: str | Path = DEFAULT_DB_PATH,
    import_manifest_path: str | Path = DEFAULT_IMPORT_MANIFEST_PATH,
    importer: Importer = import_latest_mac_read_model_mirror,
    sync_health_refresher: SyncHealthRefresher = refresh_sync_health_from_manifest,
    request_marker_path: str | Path = DEFAULT_REQUEST_MARKER_PATH,
) -> dict[str, Any]:
    manifest = Path(manifest_path)
    completion_marker = Path(completion_marker_path)
    state_file = Path(state_path)
    log_file = Path(log_path)

    if not manifest.is_file():
        status = _base_status(
            status="manifest_missing",
            manifest_path=manifest,
            completion_marker_path=completion_marker,
            state_path=state_file,
            log_path=log_file,
            message=f"Mac generated-read-model manifest is missing: {manifest}",
            **_completion_marker_summary(completion_marker),
        )
        write_state(state_file, status)
        append_log(log_file, "manifest_missing", manifest_path=manifest.as_posix())
        return status

    manifest_hash = sha256_file(manifest)
    manifest_stat = manifest.stat()
    previous_state = load_state(state_file)
    if previous_state.get("last_successful_manifest_sha256") == manifest_hash:
        refreshed_at = utc_now()
        status = _base_status(
            status="skipped_unchanged",
            manifest_path=manifest,
            completion_marker_path=completion_marker,
            state_path=state_file,
            log_path=log_file,
            generated_at=refreshed_at,
            manifest_sha256=manifest_hash,
            manifest_size_bytes=manifest_stat.st_size,
            manifest_mtime=manifest_stat.st_mtime,
            last_imported_at=previous_state.get("last_imported_at"),
            message="Manifest hash matches the last successful import; import skipped.",
            **_completion_marker_summary(completion_marker),
        )
        try:
            sync_health_refresh = sync_health_refresher(
                db_path=db_path,
                manifest_path=manifest,
                pc_import_state_path=state_file,
                mac_completion_path=completion_marker,
                pc_task_log_path=log_file,
            )
        except Exception as exc:
            failure = _base_status(
                status="sync_health_refresh_failed",
                manifest_path=manifest,
                completion_marker_path=completion_marker,
                state_path=state_file,
                log_path=log_file,
                exit_code=1,
                manifest_sha256=manifest_hash,
                manifest_size_bytes=manifest_stat.st_size,
                manifest_mtime=manifest_stat.st_mtime,
                failure_reason=type(exc).__name__,
                failure_detail=str(exc),
                **_completion_marker_summary(completion_marker),
            )
            write_state(
                state_file,
                {
                    **previous_state,
                    "agent_version": AGENT_VERSION,
                    "status": failure["status"],
                    "updated_at": failure["generated_at"],
                    "last_seen_manifest_sha256": manifest_hash,
                    "last_seen_manifest_path": manifest.as_posix(),
                    "last_failure_at": failure["generated_at"],
                    "last_failure_reason": failure["failure_reason"],
                    "last_failure_detail": failure["failure_detail"],
                    **NO_AUTHORITY_FLAGS,
                },
            )
            append_log(
                log_file,
                "sync_health_refresh_failed",
                manifest_sha256=manifest_hash,
                failure_reason=failure["failure_reason"],
            )
            return failure
        status["sync_health_refresh"] = sync_health_refresh
        final_mac_mirror_request = write_final_mac_mirror_marker_if_needed(
            sync_health_refresh=sync_health_refresh,
            request_marker_path=request_marker_path,
            completion_marker_path=completion_marker,
        )
        status["final_mac_mirror_request"] = final_mac_mirror_request
        write_state(
            state_file,
            {
                **previous_state,
                "agent_version": AGENT_VERSION,
                "status": status["status"],
                "updated_at": status["generated_at"],
                "last_seen_manifest_sha256": manifest_hash,
                "last_seen_manifest_path": manifest.as_posix(),
                "last_skip_reason": "unchanged_manifest_hash",
                "last_sync_health_refreshed_at": refreshed_at,
                "last_sync_health_refresh": sync_health_refresh,
                "last_final_mac_mirror_request": final_mac_mirror_request,
                **NO_AUTHORITY_FLAGS,
            },
        )
        append_log(
            log_file,
            "skipped_unchanged",
            manifest_sha256=manifest_hash,
            sync_health_refreshed=True,
            final_mac_mirror_marker_written=final_mac_mirror_request.get("final_mac_mirror_marker_written"),
        )
        return status

    self_report_only_manifest_change = manifest_change_is_self_report_only(
        previous_manifest=import_manifest_path,
        current_manifest=manifest,
    )

    append_log(log_file, "import_started", manifest_path=manifest.as_posix(), manifest_sha256=manifest_hash)
    try:
        import_result = importer(
            manifest=manifest,
            db_path=db_path,
            import_manifest_path=import_manifest_path,
        )
    except Exception as exc:
        status = _base_status(
            status="failure",
            manifest_path=manifest,
            completion_marker_path=completion_marker,
            state_path=state_file,
            log_path=log_file,
            exit_code=1,
            manifest_sha256=manifest_hash,
            manifest_size_bytes=manifest_stat.st_size,
            manifest_mtime=manifest_stat.st_mtime,
            failure_reason=type(exc).__name__,
            failure_detail=str(exc),
            **_completion_marker_summary(completion_marker),
        )
        write_state(
            state_file,
            {
                **previous_state,
                "agent_version": AGENT_VERSION,
                "status": status["status"],
                "updated_at": status["generated_at"],
                "last_seen_manifest_sha256": manifest_hash,
                "last_seen_manifest_path": manifest.as_posix(),
                "last_failure_at": status["generated_at"],
                "last_failure_reason": status["failure_reason"],
                "last_failure_detail": status["failure_detail"],
                **NO_AUTHORITY_FLAGS,
            },
        )
        append_log(
            log_file,
            "import_failed",
            manifest_sha256=manifest_hash,
            failure_reason=status["failure_reason"],
        )
        return status

    refreshed_at = utc_now()
    status = _base_status(
        status="success",
        manifest_path=manifest,
        completion_marker_path=completion_marker,
        state_path=state_file,
        log_path=log_file,
        generated_at=refreshed_at,
        manifest_sha256=manifest_hash,
        manifest_size_bytes=manifest_stat.st_size,
        manifest_mtime=manifest_stat.st_mtime,
        import_run_id=import_result.get("import_run_id"),
        root_id=import_result.get("root_id"),
        path_count=import_result.get("path_count"),
        mirror_counts=(
            import_result.get("generated_read_model_mirror", {}).get("counts", {})
            if isinstance(import_result.get("generated_read_model_mirror"), dict)
            else {}
        ),
        **_completion_marker_summary(completion_marker),
    )
    success_state = {
        "agent_version": AGENT_VERSION,
        "status": status["status"],
        "updated_at": status["generated_at"],
        "last_seen_manifest_sha256": manifest_hash,
        "last_seen_manifest_path": manifest.as_posix(),
        "last_successful_manifest_sha256": manifest_hash,
        "last_successful_manifest_path": manifest.as_posix(),
        "last_imported_at": status["generated_at"],
        "last_import_run_id": status.get("import_run_id"),
        "last_root_id": status.get("root_id"),
        "last_path_count": status.get("path_count"),
        "last_mirror_counts": status.get("mirror_counts"),
        **NO_AUTHORITY_FLAGS,
    }
    write_state(state_file, success_state)
    if self_report_only_manifest_change:
        status["sync_health_refresh_skipped"] = True
        status["sync_health_refresh_skip_reason"] = "manifest changed only for volatile sync_health self-report files"
        write_state(
            state_file,
            {
                **success_state,
                "last_sync_health_refresh_skipped_at": status["generated_at"],
                "last_sync_health_refresh_skip_reason": status["sync_health_refresh_skip_reason"],
            },
        )
        append_log(
            log_file,
            "sync_health_refresh_skipped",
            manifest_sha256=manifest_hash,
            reason=status["sync_health_refresh_skip_reason"],
        )
        return status
    try:
        sync_health_refresh = sync_health_refresher(
            db_path=db_path,
            manifest_path=manifest,
            pc_import_state_path=state_file,
            mac_completion_path=completion_marker,
            pc_task_log_path=log_file,
        )
    except Exception as exc:
        failure = _base_status(
            status="sync_health_refresh_failed",
            manifest_path=manifest,
            completion_marker_path=completion_marker,
            state_path=state_file,
            log_path=log_file,
            exit_code=1,
            manifest_sha256=manifest_hash,
            manifest_size_bytes=manifest_stat.st_size,
            manifest_mtime=manifest_stat.st_mtime,
            import_run_id=import_result.get("import_run_id"),
            root_id=import_result.get("root_id"),
            path_count=import_result.get("path_count"),
            failure_reason=type(exc).__name__,
            failure_detail=str(exc),
            **_completion_marker_summary(completion_marker),
        )
        write_state(
            state_file,
            {
                **success_state,
                "status": failure["status"],
                "updated_at": failure["generated_at"],
                "last_failure_at": failure["generated_at"],
                "last_failure_reason": failure["failure_reason"],
                "last_failure_detail": failure["failure_detail"],
            },
        )
        append_log(
            log_file,
            "sync_health_refresh_failed",
            manifest_sha256=manifest_hash,
            failure_reason=failure["failure_reason"],
            import_run_id=status.get("import_run_id"),
        )
        return failure
    status["sync_health_refresh"] = sync_health_refresh
    final_mac_mirror_request = write_final_mac_mirror_marker_if_needed(
        sync_health_refresh=sync_health_refresh,
        request_marker_path=request_marker_path,
        completion_marker_path=completion_marker,
    )
    status["final_mac_mirror_request"] = final_mac_mirror_request
    write_state(
        state_file,
        {
            **success_state,
            "last_sync_health_refreshed_at": refreshed_at,
            "last_sync_health_refresh": sync_health_refresh,
            "last_final_mac_mirror_request": final_mac_mirror_request,
        },
    )
    append_log(
        log_file,
        "import_succeeded",
        manifest_sha256=manifest_hash,
        import_run_id=status.get("import_run_id"),
        sync_health_refreshed=True,
        final_mac_mirror_marker_written=final_mac_mirror_request.get("final_mac_mirror_marker_written"),
    )
    return status


def run_import_agent_loop(
    *,
    interval_seconds: int,
    stop_after: int | None = None,
    **kwargs: Any,
) -> int:
    iterations = 0
    while True:
        status = run_import_agent_once(**kwargs)
        iterations += 1
        if stop_after is not None and iterations >= stop_after:
            return int(status.get("exit_code", 0))
        time.sleep(interval_seconds)


def format_agent_report(payload: dict[str, Any]) -> str:
    lines = [
        "PC Read-Model Import Agent v0",
        "",
        f"Status: `{payload['status']}`",
        f"Manifest: `{payload['manifest_path']}`",
        f"Completion marker: `{payload['completion_marker_path']}`",
        f"State: `{payload['state_path']}`",
        f"Log: `{payload['log_path']}`",
        f"Exit code: {payload['exit_code']}",
    ]
    if payload.get("manifest_sha256"):
        lines.append(f"Manifest sha256: `{payload['manifest_sha256']}`")
    if payload.get("import_run_id"):
        lines.append(f"Import run: `{payload['import_run_id']}`")
    if payload.get("path_count") is not None:
        lines.append(f"Imported path count: {payload['path_count']}")
    if payload.get("mirror_counts"):
        counts = payload["mirror_counts"]
        lines.extend(
            [
                "Mirror counts:",
                f"- missing_expected={counts.get('missing_expected', 0)}",
                f"- extra={counts.get('extra', 0)}",
                f"- hash_mismatch={counts.get('hash_mismatch', 0)}",
            ]
        )
    if payload.get("message"):
        lines.append(f"Message: {payload['message']}")
    if payload.get("failure_reason"):
        lines.extend(
            [
                f"Failure: `{payload['failure_reason']}`",
                f"Detail: {payload.get('failure_detail', '')}",
            ]
        )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Local PC/WSL import watcher only; it does not delete manifests, move files, change Mission Control, modify generated contracts, or activate runtime/tools/agents.",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import the Mac generated-read-model manifest when it changes."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run one import check. This is the default.")
    mode.add_argument("--loop", action="store_true", help="Poll continuously.")
    parser.add_argument("--interval", type=int, default=300, help="Loop interval in seconds.")
    parser.add_argument("--manifest", default=DEFAULT_RETURNED_MANIFEST_PATH.as_posix())
    parser.add_argument("--completion-marker", default=DEFAULT_COMPLETION_MARKER_PATH.as_posix())
    parser.add_argument("--state-path", default=DEFAULT_STATE_PATH.as_posix())
    parser.add_argument("--log-path", default=DEFAULT_LOG_PATH.as_posix())
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--import-manifest-path", default=DEFAULT_IMPORT_MANIFEST_PATH.as_posix())
    parser.add_argument("--request-marker", default=DEFAULT_REQUEST_MARKER_PATH.as_posix())
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    kwargs = {
        "manifest_path": args.manifest,
        "completion_marker_path": args.completion_marker,
        "state_path": args.state_path,
        "log_path": args.log_path,
        "db_path": args.db,
        "import_manifest_path": args.import_manifest_path,
        "request_marker_path": args.request_marker,
    }
    if args.loop:
        return run_import_agent_loop(interval_seconds=args.interval, **kwargs)

    payload = run_import_agent_once(**kwargs)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_agent_report(payload))
    return int(payload.get("exit_code", 0))


if __name__ == "__main__":
    raise SystemExit(main())
