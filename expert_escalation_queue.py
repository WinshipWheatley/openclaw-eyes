from __future__ import annotations

"""Local queue primitives for checked external expert escalation packets."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from expert_escalation_packet import check_expert_escalation_packet


DEFAULT_EXPERT_QUEUE_ROOT = Path("/mnt/c/OpenClaw/logs/expert_escalations")
QUEUE_DIR_NAMES = ("pending", "running", "done", "failed", "results")
PACKET_STATE_DIR_NAMES = ("pending", "running", "done", "failed")

_PACKET_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_RESULT_TEXT_LIMITS = {
    "summary": 2000,
    "stdout_excerpt": 4000,
    "stderr_excerpt": 4000,
}
_MAX_ARTIFACT_PATHS = 25
_MAX_ARTIFACT_PATH_LENGTH = 300


class ExpertEscalationQueueError(ValueError):
    """Raised when an expert escalation queue operation is rejected."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _queue_root(root: str | Path | None) -> Path:
    return Path(root) if root is not None else DEFAULT_EXPERT_QUEUE_ROOT


def _queue_dirs(root: str | Path | None) -> dict[str, Path]:
    queue_root = _queue_root(root)
    return {name: queue_root / name for name in QUEUE_DIR_NAMES}


def _safe_packet_id(packet_id: object) -> str:
    normalized = str(packet_id or "").strip()
    if not normalized:
        raise ExpertEscalationQueueError("missing_packet_id")
    if ".." in normalized or "/" in normalized or "\\" in normalized:
        raise ExpertEscalationQueueError("unsafe_packet_id")
    if not _PACKET_ID_PATTERN.fullmatch(normalized):
        raise ExpertEscalationQueueError("unsafe_packet_id")
    return normalized


def _packet_path(root: str | Path | None, state: str, packet_id: str) -> Path:
    if state not in PACKET_STATE_DIR_NAMES:
        raise ExpertEscalationQueueError(f"invalid_packet_state:{state}")
    return _queue_dirs(root)[state] / f"{packet_id}.json"


def _result_path(root: str | Path | None, packet_id: str, status: str) -> Path:
    if status not in {"done", "failed"}:
        raise ExpertEscalationQueueError(f"invalid_result_status:{status}")
    return _queue_dirs(root)["results"] / f"{packet_id}.{status}.json"


def _existing_packet_paths(root: str | Path | None, packet_id: str) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for state in PACKET_STATE_DIR_NAMES:
        path = _packet_path(root, state, packet_id)
        if path.exists():
            paths[state] = path
    return paths


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(str(path))

    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        if path.exists():
            raise FileExistsError(str(path))
        tmp_path.replace(path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def _read_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ExpertEscalationQueueError("json_file_must_contain_object")
    return data


def _require_only_state(root: str | Path | None, packet_id: str, state: str) -> Path:
    existing = _existing_packet_paths(root, packet_id)
    if state not in existing:
        raise FileNotFoundError(str(_packet_path(root, state, packet_id)))
    unexpected = sorted(name for name in existing if name != state)
    if unexpected:
        raise ExpertEscalationQueueError("packet_exists_in_multiple_states:" + ",".join(unexpected))
    return existing[state]


def _move_packet_state(root: str | Path | None, packet_id: str, source_state: str, target_state: str) -> Path:
    ensure_expert_queue_dirs(root)
    source_path = _require_only_state(root, packet_id, source_state)
    target_path = _packet_path(root, target_state, packet_id)
    if target_path.exists():
        raise FileExistsError(str(target_path))
    source_path.replace(target_path)
    return target_path


def _bounded_text(value: object, limit: int) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:limit]


def _artifact_paths(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        candidates: Sequence[object] = [value]
    elif isinstance(value, Sequence):
        candidates = value
    else:
        candidates = [value]

    paths: list[str] = []
    for raw_path in candidates[:_MAX_ARTIFACT_PATHS]:
        path = str(raw_path or "").strip()
        if not path:
            continue
        if ".." in path or path.startswith(("/", "~")) or "\\" in path:
            raise ExpertEscalationQueueError("unsafe_artifact_path")
        paths.append(path[:_MAX_ARTIFACT_PATH_LENGTH])
    return paths


def _result_mapping(value: Mapping[str, Any] | str | object, *, failed: bool) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if failed:
        return {"summary": str(value or ""), "stderr_excerpt": str(value or "")}
    return {"summary": str(value or "")}


def _result_record(
    *,
    packet_id: str,
    packet: Mapping[str, Any],
    status: str,
    result: Mapping[str, Any] | str | object,
    completed_at: str | None,
) -> dict[str, Any]:
    result_data = _result_mapping(result, failed=status == "failed")
    return {
        "packet_id": packet_id,
        "status": status,
        "created_at": str(result_data.get("created_at") or packet.get("created_at") or _utc_now()),
        "completed_at": str(result_data.get("completed_at") or completed_at or _utc_now()),
        "summary": _bounded_text(result_data.get("summary"), _RESULT_TEXT_LIMITS["summary"]),
        "artifact_paths": _artifact_paths(result_data.get("artifact_paths")),
        "stdout_excerpt": _bounded_text(result_data.get("stdout_excerpt"), _RESULT_TEXT_LIMITS["stdout_excerpt"]),
        "stderr_excerpt": _bounded_text(result_data.get("stderr_excerpt"), _RESULT_TEXT_LIMITS["stderr_excerpt"]),
    }


def ensure_expert_queue_dirs(root: str | Path | None = None) -> dict[str, Path]:
    dirs = _queue_dirs(root)
    _queue_root(root).mkdir(parents=True, exist_ok=True)
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def enqueue_expert_packet(
    packet: Mapping[str, Any],
    root: str | Path | None = None,
    *,
    created_at: str | None = None,
) -> Path:
    del created_at
    result = check_expert_escalation_packet(packet)
    if not result.passed:
        raise ExpertEscalationQueueError("unsafe_expert_packet:" + ",".join(result.violations))

    packet_id = _safe_packet_id(packet.get("packet_id"))
    ensure_expert_queue_dirs(root)
    existing = _existing_packet_paths(root, packet_id)
    if existing:
        raise FileExistsError(str(next(iter(existing.values()))))

    pending_path = _packet_path(root, "pending", packet_id)
    _atomic_write_json(pending_path, dict(packet))
    return pending_path


def list_pending_expert_packets(root: str | Path | None = None) -> list[Path]:
    dirs = ensure_expert_queue_dirs(root)
    return sorted(dirs["pending"].glob("*.json"), key=lambda path: path.name)


def load_expert_packet(path: str | Path) -> dict[str, Any]:
    return _read_json_object(Path(path))


def mark_expert_packet_running(packet_id: str, root: str | Path | None = None) -> Path:
    safe_packet_id = _safe_packet_id(packet_id)
    return _move_packet_state(root, safe_packet_id, "pending", "running")


def mark_expert_packet_done(
    packet_id: str,
    root: str | Path | None,
    result: Mapping[str, Any] | str | object,
    *,
    completed_at: str | None = None,
) -> Path:
    safe_packet_id = _safe_packet_id(packet_id)
    result_path = _result_path(root, safe_packet_id, "done")
    if result_path.exists():
        raise FileExistsError(str(result_path))

    running_path = _require_only_state(root, safe_packet_id, "running")
    packet = load_expert_packet(running_path)
    record = _result_record(
        packet_id=safe_packet_id,
        packet=packet,
        status="done",
        result=result,
        completed_at=completed_at,
    )
    done_path = _move_packet_state(root, safe_packet_id, "running", "done")
    _atomic_write_json(result_path, record)
    return done_path


def mark_expert_packet_failed(
    packet_id: str,
    root: str | Path | None,
    error: Mapping[str, Any] | str | object,
    *,
    completed_at: str | None = None,
) -> Path:
    safe_packet_id = _safe_packet_id(packet_id)
    result_path = _result_path(root, safe_packet_id, "failed")
    if result_path.exists():
        raise FileExistsError(str(result_path))

    running_path = _require_only_state(root, safe_packet_id, "running")
    packet = load_expert_packet(running_path)
    record = _result_record(
        packet_id=safe_packet_id,
        packet=packet,
        status="failed",
        result=error,
        completed_at=completed_at,
    )
    failed_path = _move_packet_state(root, safe_packet_id, "running", "failed")
    _atomic_write_json(result_path, record)
    return failed_path