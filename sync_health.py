"""Sync Health v0 for OpenClaw read-model mirror trust.

This module records and exports a bounded health snapshot for the Mac/PC
generated read-model mirror. It reads manifest/marker/state/log metadata only.
It does not run sync, control another machine, delete files, move files, or
modify Mission Control.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger
from generated_read_model_files import (
    VOLATILE_SELF_REPORT_READ_MODEL_FILES,
    canonical_generated_read_model_records,
)


ROOT = Path(__file__).resolve().parent
SYNC_HEALTH_VERSION = "sync_health_v0"
READ_MODEL_VERSION = "sync_health_read_model_v0"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "sync_health.json"
OPERATOR_EXPORT_NAME = "sync_health_OPERATOR.md"
SELF_EXPORT_FILES = frozenset(VOLATILE_SELF_REPORT_READ_MODEL_FILES)
OPERATOR_INTERRUPT_POLICY = (
    "routine sync lifecycle states stay in proof/detail; only unresolved "
    "actionable failures should interrupt the operator"
)
ROUTINE_SYNC_LIFECYCLE_STATES = frozenset(
    {
        "trusted_current",
        "sync_requested_waiting_for_mac",
        "mac_synced_waiting_for_pc_import",
        "pc_imported_waiting_for_health_export",
        "health_exported_waiting_for_mac_mirror",
    }
)
ACTIONABLE_SYNC_LIFECYCLE_STATES = frozenset({"actionable_sync_failure"})

DEFAULT_PC_SHARE_ROOT = Path("/mnt/e/openclaw")
DEFAULT_MANIFEST_PATH = DEFAULT_PC_SHARE_ROOT / "mac_generated_read_models_manifest.json"
DEFAULT_REQUEST_MARKER_PATH = DEFAULT_PC_SHARE_ROOT / "shuttle" / "to_mac" / "read_model_sync_required.json"
DEFAULT_APP_REQUEST_MARKER_PATH = "/Volumes/openclaw_e/shuttle/to_mac/read_model_sync_required.json"
DEFAULT_MAC_STATUS_PATH = DEFAULT_PC_SHARE_ROOT / "shuttle" / "from_mac" / "read_model_sync_agent_status.json"
DEFAULT_MAC_COMPLETION_PATH = DEFAULT_PC_SHARE_ROOT / "shuttle" / "from_mac" / "read_model_sync_completed.json"
DEFAULT_PC_IMPORT_STATE_PATH = ROOT / ".openclaw" / "state" / "read_model_import_agent_state.json"
DEFAULT_PC_TASK_LOG_PATH = ROOT / ".openclaw" / "logs" / "windows_task_read_model_import.log"
DEFAULT_WINDOWS_TASK_LOG_PATH = DEFAULT_PC_SHARE_ROOT / "windows_tasks" / "logs" / "OpenClawReadModelImport.log"

NO_AUTHORITY_FLAGS = {
    "app_direct_execution_allowed": False,
    "arbitrary_command_allowed": False,
    "remote_control_allowed": False,
    "ssh_scp_rsync_allowed": False,
    "docker_ollama_allowed": False,
    "runtime_activation_allowed": False,
    "agent_activation_allowed": False,
    "file_delete_allowed": False,
    "file_move_allowed": False,
}


@dataclass(frozen=True)
class SyncHealthBuildResult:
    run_id: str
    snapshot_id: str
    trust_status: str
    mirror_status: str
    recommended_fix_kind: str
    sync_lifecycle_state: str
    operator_action_required: bool
    db_path: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _display_path(path: str | Path, *, repo_root: str | Path = ROOT) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS sync_health_runs (
  run_id TEXT PRIMARY KEY,
  sync_health_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  trust_status TEXT NOT NULL,
  mirror_status TEXT NOT NULL,
  recommended_fix_kind TEXT NOT NULL,
  app_direct_execution_allowed INTEGER NOT NULL DEFAULT 0,
  arbitrary_command_allowed INTEGER NOT NULL DEFAULT 0,
  remote_control_allowed INTEGER NOT NULL DEFAULT 0,
  ssh_scp_rsync_allowed INTEGER NOT NULL DEFAULT 0,
  docker_ollama_allowed INTEGER NOT NULL DEFAULT 0,
  runtime_activation_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS sync_health_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  trust_status TEXT NOT NULL,
  mirror_status TEXT NOT NULL,
  canonical_expected INTEGER NOT NULL DEFAULT 0,
  observed INTEGER NOT NULL DEFAULT 0,
  missing_expected INTEGER NOT NULL DEFAULT 0,
  extra INTEGER NOT NULL DEFAULT 0,
  hash_mismatch INTEGER NOT NULL DEFAULT 0,
  matched_hash INTEGER NOT NULL DEFAULT 0,
  stale_files_json TEXT NOT NULL,
  missing_files_json TEXT NOT NULL,
  extra_files_json TEXT NOT NULL,
  mac_heartbeat_status TEXT,
  mac_heartbeat_time TEXT,
  mac_marker_seen INTEGER NOT NULL DEFAULT 0,
  mac_manifest_written INTEGER NOT NULL DEFAULT 0,
  mac_completion_status TEXT,
  mac_completion_time TEXT,
  pc_import_status TEXT,
  pc_import_time TEXT,
  pc_manifest_hash TEXT,
  windows_task_log_present INTEGER NOT NULL DEFAULT 0,
  pc_scheduler_known INTEGER NOT NULL DEFAULT 0,
  display_status TEXT NOT NULL DEFAULT 'unknown_review',
  sync_lifecycle_state TEXT NOT NULL DEFAULT 'unknown_review',
  operator_action_required INTEGER NOT NULL DEFAULT 0,
  operator_interrupt_policy TEXT NOT NULL DEFAULT 'actionable_failures_only',
  next_expected_actor TEXT NOT NULL DEFAULT 'operator_review',
  next_safe_move TEXT NOT NULL,
  recommended_fix_kind TEXT NOT NULL,
  can_request_fix_from_app INTEGER NOT NULL DEFAULT 0,
  request_marker_path TEXT NOT NULL,
  app_request_marker_path TEXT NOT NULL,
  no_authority_json TEXT NOT NULL,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (run_id) REFERENCES sync_health_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS sync_health_sources (
  source_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_path TEXT NOT NULL,
  present INTEGER NOT NULL DEFAULT 0,
  observed_at TEXT NOT NULL,
  source_status TEXT,
  source_time TEXT,
  source_hash TEXT,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (run_id) REFERENCES sync_health_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS sync_health_recommendations (
  recommendation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  recommended_fix_kind TEXT NOT NULL,
  next_safe_move TEXT NOT NULL,
  next_expected_actor TEXT NOT NULL DEFAULT 'operator_review',
  can_request_fix_from_app INTEGER NOT NULL DEFAULT 0,
  request_marker_path TEXT NOT NULL,
  app_request_marker_path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES sync_health_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS sync_health_receipts (
  receipt_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  receipt_kind TEXT NOT NULL,
  summary TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES sync_health_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_sync_health_snapshots_generated ON sync_health_snapshots(generated_at)",
        "CREATE INDEX IF NOT EXISTS idx_sync_health_snapshots_trust ON sync_health_snapshots(trust_status)",
    )


def _ensure_sync_health_columns(conn: sqlite3.Connection) -> None:
    table_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(sync_health_snapshots)").fetchall()
    }
    if "display_status" not in table_columns:
        conn.execute("ALTER TABLE sync_health_snapshots ADD COLUMN display_status TEXT NOT NULL DEFAULT 'unknown_review'")
    if "next_expected_actor" not in table_columns:
        conn.execute("ALTER TABLE sync_health_snapshots ADD COLUMN next_expected_actor TEXT NOT NULL DEFAULT 'operator_review'")
    if "sync_lifecycle_state" not in table_columns:
        conn.execute("ALTER TABLE sync_health_snapshots ADD COLUMN sync_lifecycle_state TEXT NOT NULL DEFAULT 'unknown_review'")
    if "operator_action_required" not in table_columns:
        conn.execute("ALTER TABLE sync_health_snapshots ADD COLUMN operator_action_required INTEGER NOT NULL DEFAULT 0")
    if "operator_interrupt_policy" not in table_columns:
        conn.execute("ALTER TABLE sync_health_snapshots ADD COLUMN operator_interrupt_policy TEXT NOT NULL DEFAULT 'actionable_failures_only'")

    recommendation_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(sync_health_recommendations)").fetchall()
    }
    if "next_expected_actor" not in recommendation_columns:
        conn.execute("ALTER TABLE sync_health_recommendations ADD COLUMN next_expected_actor TEXT NOT NULL DEFAULT 'operator_review'")


def init_sync_health_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    parent = Path(path).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        _ensure_sync_health_columns(conn)
        conn.commit()
    finally:
        conn.close()
    return path


def sync_health_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_sync_health_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'sync_health%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _read_json_object(path: str | Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _mtime_iso(path: str | Path) -> str | None:
    try:
        return datetime.fromtimestamp(Path(path).stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat()
    except OSError:
        return None


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _json_list(values: list[str]) -> str:
    return stable_json(values)


def compare_manifest_to_backend(
    *,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: str | Path = ROOT,
) -> dict[str, Any]:
    manifest = Path(manifest_path)
    records = canonical_generated_read_model_records(
        source_root=read_model_root,
        repo_root=repo_root,
        include_hash=True,
    )
    expected_records = {item["relative_path"]: item for item in records}
    expected = set(expected_records)
    if not manifest.is_file():
        return {
            "manifest_present": False,
            "manifest_path": manifest.as_posix(),
            "manifest_sha256": None,
            "counts": {
                "canonical_expected": len(expected),
                "observed": 0,
                "missing_expected": len(expected),
                "extra": 0,
                "hash_mismatch": 0,
                "matched_hash": 0,
            },
            "missing_expected_files": sorted(expected),
            "extra_files": [],
            "hash_mismatch_files": [],
        }
    payload = _read_json_object(manifest) or {}
    path_records = payload.get("path_records") or []
    observed_records = {
        record.get("relative_path"): record
        for record in path_records
        if isinstance(record, dict) and isinstance(record.get("relative_path"), str)
    }
    observed = set(observed_records)
    matched: list[str] = []
    mismatched: list[str] = []
    for relative_path in sorted(expected & observed):
        expected_hash = expected_records[relative_path].get("sha256")
        observed_hash = observed_records[relative_path].get("content_hash")
        if relative_path in SELF_EXPORT_FILES and observed_hash:
            matched.append(relative_path)
        elif expected_hash and observed_hash and expected_hash == observed_hash:
            matched.append(relative_path)
        elif expected_hash and observed_hash and expected_hash != observed_hash:
            mismatched.append(relative_path)
    return {
        "manifest_present": True,
        "manifest_path": manifest.as_posix(),
        "manifest_sha256": sha256_file(manifest),
        "counts": {
            "canonical_expected": len(expected),
            "observed": len(observed),
            "missing_expected": len(expected - observed),
            "extra": len(observed - expected),
            "hash_mismatch": len(mismatched),
            "matched_hash": len(matched),
        },
        "missing_expected_files": sorted(expected - observed),
        "extra_files": sorted(observed - expected),
        "hash_mismatch_files": mismatched,
    }


def _status_marker(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path) or {}
    return {
        "present": path.is_file(),
        "status": payload.get("status") if isinstance(payload.get("status"), str) else None,
        "time": payload.get("generated_at") if isinstance(payload.get("generated_at"), str) else _mtime_iso(path),
        "marker_seen": bool(payload.get("marker_seen")) if payload else False,
        "manifest_written": bool(payload.get("manifest_written")) if payload else False,
        "hash": sha256_file(path) if path.is_file() else None,
    }


def _completion_marker(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path) or {}
    return {
        "present": path.is_file(),
        "status": payload.get("status") if isinstance(payload.get("status"), str) else None,
        "time": payload.get("generated_at") if isinstance(payload.get("generated_at"), str) else _mtime_iso(path),
        "manifest_written": bool(payload.get("manifest_sha256") or payload.get("manifest_path")) if payload else False,
        "hash": sha256_file(path) if path.is_file() else None,
    }


def _pc_import_state(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path) or {}
    return {
        "present": path.is_file(),
        "status": payload.get("status") if isinstance(payload.get("status"), str) else None,
        "time": (
            payload.get("last_imported_at")
            if isinstance(payload.get("last_imported_at"), str)
            else payload.get("updated_at")
            if isinstance(payload.get("updated_at"), str)
            else _mtime_iso(path)
        ),
        "manifest_hash": (
            payload.get("last_successful_manifest_sha256")
            if isinstance(payload.get("last_successful_manifest_sha256"), str)
            else None
        ),
        "hash": sha256_file(path) if path.is_file() else None,
    }


def _request_marker_state(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path) or {}
    return {
        "present": path.is_file(),
        "status": payload.get("status") if isinstance(payload.get("status"), str) else None,
        "time": payload.get("generated_at") if isinstance(payload.get("generated_at"), str) else _mtime_iso(path),
        "next_expected_responder": (
            payload.get("next_expected_responder")
            if isinstance(payload.get("next_expected_responder"), str)
            else None
        ),
        "hash": sha256_file(path) if path.is_file() else None,
    }


def _self_report_state(read_model_root: str | Path, manifest_path: str | Path) -> dict[str, Any]:
    root = Path(read_model_root)
    manifest_time = _parse_time(_mtime_iso(manifest_path))
    present_files: list[str] = []
    newer_files: list[str] = []
    for relative_path in sorted(SELF_EXPORT_FILES):
        path = root / relative_path
        if not path.is_file():
            continue
        present_files.append(relative_path)
        file_time = _parse_time(_mtime_iso(path))
        if manifest_time and file_time and file_time > manifest_time:
            newer_files.append(relative_path)
    return {
        "present": bool(present_files),
        "present_files": present_files,
        "newer_than_manifest": bool(newer_files),
        "newer_files": newer_files,
    }


def _classification(
    *,
    trust_status: str,
    mirror_status: str,
    display_status: str,
    recommended_fix_kind: str,
    next_safe_move: str,
    next_expected_actor: str,
    can_request_fix_from_app: bool,
    sync_lifecycle_state: str,
    operator_action_required: bool | None = None,
) -> dict[str, Any]:
    if operator_action_required is None:
        operator_action_required = sync_lifecycle_state in ACTIONABLE_SYNC_LIFECYCLE_STATES
    return {
        "trust_status": trust_status,
        "mirror_status": mirror_status,
        "display_status": display_status,
        "recommended_fix_kind": recommended_fix_kind,
        "next_safe_move": next_safe_move,
        "next_expected_actor": next_expected_actor,
        "can_request_fix_from_app": can_request_fix_from_app,
        "sync_lifecycle_state": sync_lifecycle_state,
        "operator_action_required": operator_action_required,
        "operator_interrupt_policy": OPERATOR_INTERRUPT_POLICY,
    }


def classify_sync_health(
    *,
    manifest_health: dict[str, Any],
    mac_status: dict[str, Any],
    mac_completion: dict[str, Any],
    pc_state: dict[str, Any],
    request_marker: dict[str, Any],
    self_report: dict[str, Any],
    windows_task_log_present: bool,
) -> dict[str, Any]:
    counts = manifest_health["counts"]
    missing = int(counts.get("missing_expected") or 0)
    extra = int(counts.get("extra") or 0)
    mismatched = int(counts.get("hash_mismatch") or 0)
    if not manifest_health.get("manifest_present"):
        return _classification(
            trust_status="unknown_review",
            mirror_status="unknown",
            display_status="manifest_missing",
            recommended_fix_kind="inspect_automation",
            next_safe_move="Mac manifest is missing; inspect the Mac sync service and shared E-drive mount.",
            next_expected_actor="operator_review",
            can_request_fix_from_app=False,
            sync_lifecycle_state="actionable_sync_failure",
        )
    if missing > 0 or mismatched > 0:
        request_time = _parse_time(request_marker.get("time"))
        completion_time = _parse_time(mac_completion.get("time"))
        if request_marker.get("present") and not (request_time and completion_time and completion_time > request_time):
            return _classification(
                trust_status="stale_needs_mac_sync",
                mirror_status="needs_mac_sync",
                display_status="sync_requested_waiting_for_mac",
                recommended_fix_kind="wait_for_mac_sync",
                next_safe_move="Mac sync has already been requested; waiting for the normal Mac sync agent cycle.",
                next_expected_actor="mac_sync_agent",
                can_request_fix_from_app=False,
                sync_lifecycle_state="sync_requested_waiting_for_mac",
                operator_action_required=False,
            )
        return _classification(
            trust_status="stale_needs_mac_sync",
            mirror_status="needs_mac_sync",
            display_status="needs_mac_sync",
            recommended_fix_kind="request_mac_sync",
            next_safe_move="Request Mac sync through the shared marker and let the Mac LaunchAgent refresh the mirror.",
            next_expected_actor="mac_sync_agent",
            can_request_fix_from_app=True,
            sync_lifecycle_state="actionable_sync_failure",
        )
    if extra > 0:
        return _classification(
            trust_status="mismatch",
            mirror_status="error",
            display_status="manual_review",
            recommended_fix_kind="manual_review",
            next_safe_move="Review extra Mac mirror files before treating the mirror as trusted.",
            next_expected_actor="operator_review",
            can_request_fix_from_app=False,
            sync_lifecycle_state="actionable_sync_failure",
        )
    manifest_hash = manifest_health.get("manifest_sha256")
    completion_time = _parse_time(mac_completion.get("time"))
    import_time = _parse_time(pc_state.get("time"))
    state_hash = pc_state.get("manifest_hash")
    if pc_state.get("present") and manifest_hash and state_hash and state_hash != manifest_hash:
        return _classification(
            trust_status="stale_needs_pc_import",
            mirror_status="needs_pc_import",
            display_status="waiting_for_pc_import",
            recommended_fix_kind="wait_for_pc_import",
            next_safe_move="Mac sync appears complete. Waiting for PC import task.",
            next_expected_actor="pc_import_task",
            can_request_fix_from_app=False,
            sync_lifecycle_state="mac_synced_waiting_for_pc_import",
            operator_action_required=False,
        )
    if completion_time and import_time and completion_time > import_time:
        return _classification(
            trust_status="stale_needs_pc_import",
            mirror_status="needs_pc_import",
            display_status="waiting_for_pc_import",
            recommended_fix_kind="wait_for_pc_import",
            next_safe_move="Mac sync appears complete. Waiting for PC import task.",
            next_expected_actor="pc_import_task",
            can_request_fix_from_app=False,
            sync_lifecycle_state="mac_synced_waiting_for_pc_import",
            operator_action_required=False,
        )
    proof_present = bool(
        (mac_status.get("present") or mac_completion.get("present"))
        and (pc_state.get("present") or windows_task_log_present)
    )
    if proof_present:
        if self_report.get("newer_than_manifest"):
            return _classification(
                trust_status="trusted",
                mirror_status="ok",
                display_status="current",
                recommended_fix_kind="none",
                next_safe_move="Sync health is current on PC and waiting for the normal Mac mirror cycle to pick up the latest health read-model.",
                next_expected_actor="mac_sync_agent",
                can_request_fix_from_app=False,
                sync_lifecycle_state="health_exported_waiting_for_mac_mirror",
                operator_action_required=False,
            )
        return _classification(
            trust_status="trusted",
            mirror_status="ok",
            display_status="current",
            recommended_fix_kind="none",
            next_safe_move="No sync repair is needed.",
            next_expected_actor="none",
            can_request_fix_from_app=False,
            sync_lifecycle_state="trusted_current",
            operator_action_required=False,
        )
    return _classification(
        trust_status="degraded",
        mirror_status="ok",
        display_status="degraded",
        recommended_fix_kind="inspect_automation",
        next_safe_move="Mirror content matches, but automation proof files are missing or incomplete.",
        next_expected_actor="operator_review",
        can_request_fix_from_app=False,
        sync_lifecycle_state="actionable_sync_failure",
    )

def _source_rows(
    *,
    run_id: str,
    generated_at: str,
    manifest_path: Path,
    mac_status_path: Path,
    mac_completion_path: Path,
    pc_state_path: Path,
    pc_task_log_path: Path,
    windows_task_log_path: Path,
    request_marker_path: Path,
    read_model_root_path: Path,
    mac_status: dict[str, Any],
    mac_completion: dict[str, Any],
    pc_state: dict[str, Any],
    request_marker: dict[str, Any],
    self_report: dict[str, Any],
) -> list[dict[str, Any]]:
    observed = [
        ("mac_manifest", manifest_path, manifest_path.is_file(), None, _mtime_iso(manifest_path), sha256_file(manifest_path) if manifest_path.is_file() else None),
        ("mac_heartbeat", mac_status_path, mac_status["present"], mac_status.get("status"), mac_status.get("time"), mac_status.get("hash")),
        ("mac_completion", mac_completion_path, mac_completion["present"], mac_completion.get("status"), mac_completion.get("time"), mac_completion.get("hash")),
        ("pc_import_state", pc_state_path, pc_state["present"], pc_state.get("status"), pc_state.get("time"), pc_state.get("hash")),
        ("read_model_sync_request_marker", request_marker_path, request_marker["present"], request_marker.get("status"), request_marker.get("time"), request_marker.get("hash")),
        ("sync_health_self_report", read_model_root_path, self_report["present"], "newer_than_manifest" if self_report.get("newer_than_manifest") else "not_newer", None, None),
        ("pc_task_log", pc_task_log_path, pc_task_log_path.is_file(), "present" if pc_task_log_path.is_file() else None, _mtime_iso(pc_task_log_path), None),
        ("windows_task_log", windows_task_log_path, windows_task_log_path.is_file(), "present" if windows_task_log_path.is_file() else None, _mtime_iso(windows_task_log_path), None),
    ]
    return [
        {
            "source_id": _row_id("synchealthsrc", run_id, source_kind, source_path.as_posix()),
            "run_id": run_id,
            "source_kind": source_kind,
            "source_path": source_path.as_posix(),
            "present": present,
            "observed_at": generated_at,
            "source_status": status,
            "source_time": source_time,
            "source_hash": source_hash,
        }
        for source_kind, source_path, present, status, source_time, source_hash in observed
    ]


def build_sync_health_snapshot(
    *,
    db_path: str | Path | None = None,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: str | Path = ROOT,
    mac_status_path: str | Path = DEFAULT_MAC_STATUS_PATH,
    mac_completion_path: str | Path = DEFAULT_MAC_COMPLETION_PATH,
    pc_import_state_path: str | Path = DEFAULT_PC_IMPORT_STATE_PATH,
    pc_task_log_path: str | Path = DEFAULT_PC_TASK_LOG_PATH,
    windows_task_log_path: str | Path = DEFAULT_WINDOWS_TASK_LOG_PATH,
    request_marker_path: str | Path = DEFAULT_REQUEST_MARKER_PATH,
    app_request_marker_path: str = DEFAULT_APP_REQUEST_MARKER_PATH,
    run_id: str | None = None,
) -> SyncHealthBuildResult:
    path = init_sync_health_schema(db_path)
    generated_at = utc_now()
    resolved_run_id = run_id or _row_id("synchealthrun", generated_at)
    snapshot_id = _row_id("synchealthsnap", resolved_run_id, generated_at)

    manifest = Path(manifest_path)
    mac_status_file = Path(mac_status_path)
    mac_completion_file = Path(mac_completion_path)
    pc_state_file = Path(pc_import_state_path)
    pc_log_file = Path(pc_task_log_path)
    windows_log_file = Path(windows_task_log_path)
    request_marker = Path(request_marker_path)

    manifest_health = compare_manifest_to_backend(
        manifest_path=manifest,
        read_model_root=read_model_root,
        repo_root=repo_root,
    )
    mac_status = _status_marker(mac_status_file)
    mac_completion = _completion_marker(mac_completion_file)
    pc_state = _pc_import_state(pc_state_file)
    request_marker_state = _request_marker_state(request_marker)
    self_report = _self_report_state(read_model_root, manifest)
    windows_log_present = windows_log_file.is_file()
    pc_scheduler_known = bool(windows_log_present or pc_log_file.is_file() or pc_state["present"])
    classification = classify_sync_health(
        manifest_health=manifest_health,
        mac_status=mac_status,
        mac_completion=mac_completion,
        pc_state=pc_state,
        request_marker=request_marker_state,
        self_report=self_report,
        windows_task_log_present=windows_log_present,
    )
    counts = manifest_health["counts"]
    missing_files = list(manifest_health["missing_expected_files"])
    hash_mismatch_files = list(manifest_health["hash_mismatch_files"])
    stale_files = sorted(set(missing_files) | set(hash_mismatch_files))
    extra_files = list(manifest_health["extra_files"])

    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
INSERT INTO sync_health_runs (
  run_id, sync_health_version, created_at, completed_at,
  trust_status, mirror_status, recommended_fix_kind,
  app_direct_execution_allowed, arbitrary_command_allowed, remote_control_allowed,
  ssh_scp_rsync_allowed, docker_ollama_allowed, runtime_activation_allowed,
  agent_activation_allowed, file_delete_allowed, file_move_allowed
) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0)
ON CONFLICT(run_id) DO UPDATE SET
  completed_at = excluded.completed_at,
  trust_status = excluded.trust_status,
  mirror_status = excluded.mirror_status,
  recommended_fix_kind = excluded.recommended_fix_kind
""".strip(),
            (
                resolved_run_id,
                SYNC_HEALTH_VERSION,
                generated_at,
                generated_at,
                classification["trust_status"],
                classification["mirror_status"],
                classification["recommended_fix_kind"],
            ),
        )
        conn.execute("DELETE FROM sync_health_sources WHERE run_id = ?", (resolved_run_id,))
        conn.execute("DELETE FROM sync_health_recommendations WHERE run_id = ?", (resolved_run_id,))
        conn.execute("DELETE FROM sync_health_receipts WHERE run_id = ?", (resolved_run_id,))
        conn.execute(
            """
INSERT OR REPLACE INTO sync_health_snapshots (
  snapshot_id, run_id, generated_at, trust_status, mirror_status,
  canonical_expected, observed, missing_expected, extra, hash_mismatch,
  matched_hash, stale_files_json, missing_files_json, extra_files_json,
  mac_heartbeat_status, mac_heartbeat_time, mac_marker_seen,
  mac_manifest_written, mac_completion_status, mac_completion_time,
  pc_import_status, pc_import_time, pc_manifest_hash,
  windows_task_log_present, pc_scheduler_known, display_status,
  sync_lifecycle_state, operator_action_required, operator_interrupt_policy,
  next_expected_actor, next_safe_move, recommended_fix_kind,
  can_request_fix_from_app, request_marker_path,
  app_request_marker_path, no_authority_json, raw_body_stored
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
""".strip(),
            (
                snapshot_id,
                resolved_run_id,
                generated_at,
                classification["trust_status"],
                classification["mirror_status"],
                int(counts.get("canonical_expected") or 0),
                int(counts.get("observed") or 0),
                int(counts.get("missing_expected") or 0),
                int(counts.get("extra") or 0),
                int(counts.get("hash_mismatch") or 0),
                int(counts.get("matched_hash") or 0),
                _json_list(stale_files),
                _json_list(missing_files),
                _json_list(extra_files),
                mac_status.get("status"),
                mac_status.get("time"),
                1 if mac_status.get("marker_seen") else 0,
                1 if (mac_status.get("manifest_written") or mac_completion.get("manifest_written")) else 0,
                mac_completion.get("status"),
                mac_completion.get("time"),
                pc_state.get("status"),
                pc_state.get("time"),
                pc_state.get("manifest_hash"),
                1 if windows_log_present else 0,
                1 if pc_scheduler_known else 0,
                classification["display_status"],
                classification["sync_lifecycle_state"],
                1 if classification["operator_action_required"] else 0,
                classification["operator_interrupt_policy"],
                classification["next_expected_actor"],
                classification["next_safe_move"],
                classification["recommended_fix_kind"],
                1
                if (
                    classification["recommended_fix_kind"] == "request_mac_sync"
                    and classification["can_request_fix_from_app"]
                    and request_marker.as_posix().startswith("/mnt/e/openclaw/")
                )
                else 0,
                request_marker.as_posix(),
                app_request_marker_path,
                stable_json(NO_AUTHORITY_FLAGS),
            ),
        )
        for source in _source_rows(
            run_id=resolved_run_id,
            generated_at=generated_at,
            manifest_path=manifest,
            mac_status_path=mac_status_file,
            mac_completion_path=mac_completion_file,
            pc_state_path=pc_state_file,
            pc_task_log_path=pc_log_file,
            windows_task_log_path=windows_log_file,
            request_marker_path=request_marker,
            read_model_root_path=Path(read_model_root),
            mac_status=mac_status,
            mac_completion=mac_completion,
            pc_state=pc_state,
            request_marker=request_marker_state,
            self_report=self_report,
        ):
            conn.execute(
                """
INSERT INTO sync_health_sources (
  source_id, run_id, source_kind, source_path, present, observed_at,
  source_status, source_time, source_hash, raw_body_stored
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
""".strip(),
                (
                    source["source_id"],
                    source["run_id"],
                    source["source_kind"],
                    source["source_path"],
                    1 if source["present"] else 0,
                    source["observed_at"],
                    source["source_status"],
                    source["source_time"],
                    source["source_hash"],
                ),
            )
        conn.execute(
            """
INSERT INTO sync_health_recommendations (
  recommendation_id, run_id, snapshot_id, recommended_fix_kind,
  next_safe_move, next_expected_actor, can_request_fix_from_app, request_marker_path,
  app_request_marker_path, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
            (
                _row_id("synchealthrec", resolved_run_id, classification["recommended_fix_kind"]),
                resolved_run_id,
                snapshot_id,
                classification["recommended_fix_kind"],
                classification["next_safe_move"],
                classification["next_expected_actor"],
                1 if classification["recommended_fix_kind"] == "request_mac_sync" and classification["can_request_fix_from_app"] else 0,
                request_marker.as_posix(),
                app_request_marker_path,
                generated_at,
            ),
        )
        receipt_payload = {
            "run_id": resolved_run_id,
            "snapshot_id": snapshot_id,
            "trust_status": classification["trust_status"],
            "mirror_status": classification["mirror_status"],
            "recommended_fix_kind": classification["recommended_fix_kind"],
            "sync_lifecycle_state": classification["sync_lifecycle_state"],
            "operator_action_required": classification["operator_action_required"],
            "counts": counts,
            "stale_files": stale_files,
            **NO_AUTHORITY_FLAGS,
        }
        conn.execute(
            """
INSERT INTO sync_health_receipts (
  receipt_id, run_id, snapshot_id, receipt_kind, summary, payload_json, created_at
) VALUES (?, ?, ?, 'sync_health_snapshot', ?, ?, ?)
""".strip(),
            (
                _row_id("synchealthreceipt", resolved_run_id, snapshot_id),
                resolved_run_id,
                snapshot_id,
                f"Recorded sync health snapshot: {classification['trust_status']}.",
                stable_json(receipt_payload),
                generated_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return SyncHealthBuildResult(
        run_id=resolved_run_id,
        snapshot_id=snapshot_id,
        trust_status=classification["trust_status"],
        mirror_status=classification["mirror_status"],
        recommended_fix_kind=classification["recommended_fix_kind"],
        sync_lifecycle_state=classification["sync_lifecycle_state"],
        operator_action_required=classification["operator_action_required"],
        db_path=path,
    )


def _latest_snapshot(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
SELECT *
FROM sync_health_snapshots
ORDER BY generated_at DESC, snapshot_id DESC
LIMIT 1
""".strip()
    ).fetchone()


def _snapshot_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "snapshot_id": row["snapshot_id"],
        "run_id": row["run_id"],
        "generated_at": row["generated_at"],
        "trust_status": row["trust_status"],
        "mirror_status": row["mirror_status"],
        "canonical_expected": row["canonical_expected"],
        "observed": row["observed"],
        "missing_expected": row["missing_expected"],
        "extra": row["extra"],
        "hash_mismatch": row["hash_mismatch"],
        "matched_hash": row["matched_hash"],
        "stale_files": json.loads(row["stale_files_json"]),
        "missing_files": json.loads(row["missing_files_json"]),
        "extra_files": json.loads(row["extra_files_json"]),
        "mac_heartbeat_status": row["mac_heartbeat_status"],
        "mac_heartbeat_time": row["mac_heartbeat_time"],
        "mac_marker_seen": bool(row["mac_marker_seen"]),
        "mac_manifest_written": bool(row["mac_manifest_written"]),
        "mac_completion_status": row["mac_completion_status"],
        "mac_completion_time": row["mac_completion_time"],
        "pc_import_status": row["pc_import_status"],
        "pc_import_time": row["pc_import_time"],
        "pc_manifest_hash": row["pc_manifest_hash"],
        "windows_task_log_present": bool(row["windows_task_log_present"]),
        "pc_scheduler_known": bool(row["pc_scheduler_known"]),
        "display_status": row["display_status"],
        "sync_lifecycle_state": row["sync_lifecycle_state"],
        "operator_action_required": bool(row["operator_action_required"]),
        "operator_interrupt_policy": row["operator_interrupt_policy"],
        "next_expected_actor": row["next_expected_actor"],
        "next_safe_move": row["next_safe_move"],
        "recommended_fix_kind": row["recommended_fix_kind"],
        "can_request_fix_from_app": bool(row["can_request_fix_from_app"]),
        "request_marker_path": row["request_marker_path"],
        "app_request_marker_path": row["app_request_marker_path"],
        "no_authority_flags": json.loads(row["no_authority_json"]),
    }


REPORT_SECTIONS = {"summary", "proof"}


def build_sync_health_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
) -> dict[str, Any]:
    if report not in REPORT_SECTIONS:
        raise ValueError(f"unknown sync health report: {report}")
    path = init_sync_health_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        snapshot = _snapshot_dict(_latest_snapshot(conn))
        sources = []
        if report == "proof" and snapshot:
            sources = [
                dict(row)
                for row in conn.execute(
                    """
SELECT source_kind, source_path, present, source_status, source_time, source_hash
FROM sync_health_sources
WHERE run_id = ?
ORDER BY source_kind
""".strip(),
                    (snapshot["run_id"],),
                ).fetchall()
            ]
        return {
            "status": "ok" if snapshot else "empty",
            "report": report,
            "db_path": str(path),
            "latest_snapshot": snapshot,
            "sources": sources,
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def build_sync_health_read_model(db_path: str | Path | None = None) -> dict[str, Any]:
    report = build_sync_health_report(db_path=db_path, report="proof")
    snapshot = report["latest_snapshot"] or {}
    return {
        "schema_version": READ_MODEL_VERSION,
        "generated_at": utc_now(),
        "source_ledger_path": str(db_path or DEFAULT_DB_PATH),
        "trust_status": snapshot.get("trust_status", "unknown_review"),
        "mirror_status": snapshot.get("mirror_status", "unknown"),
        "display_status": snapshot.get("display_status", "unknown_review"),
        "sync_lifecycle_state": snapshot.get("sync_lifecycle_state", "unknown_review"),
        "operator_action_required": snapshot.get("operator_action_required", False),
        "operator_interrupt_policy": snapshot.get("operator_interrupt_policy", OPERATOR_INTERRUPT_POLICY),
        "next_expected_actor": snapshot.get("next_expected_actor", "operator_review"),
        "canonical_expected": snapshot.get("canonical_expected", 0),
        "observed": snapshot.get("observed", 0),
        "missing_expected": snapshot.get("missing_expected", 0),
        "extra": snapshot.get("extra", 0),
        "hash_mismatch": snapshot.get("hash_mismatch", 0),
        "matched_hash": snapshot.get("matched_hash", 0),
        "stale_files": snapshot.get("stale_files", []),
        "missing_files": snapshot.get("missing_files", []),
        "extra_files": snapshot.get("extra_files", []),
        "last_mac_heartbeat": {
            "status": snapshot.get("mac_heartbeat_status"),
            "time": snapshot.get("mac_heartbeat_time"),
            "marker_seen": snapshot.get("mac_marker_seen", False),
            "manifest_written": snapshot.get("mac_manifest_written", False),
        },
        "last_mac_completion": {
            "status": snapshot.get("mac_completion_status"),
            "time": snapshot.get("mac_completion_time"),
        },
        "last_pc_import": {
            "status": snapshot.get("pc_import_status"),
            "time": snapshot.get("pc_import_time"),
            "manifest_hash": snapshot.get("pc_manifest_hash"),
            "windows_task_log_present": snapshot.get("windows_task_log_present", False),
            "pc_scheduler_known": snapshot.get("pc_scheduler_known", False),
        },
        "recommended_fix": {
            "kind": snapshot.get("recommended_fix_kind", "manual_review"),
            "display_status": snapshot.get("display_status", "unknown_review"),
            "next_expected_actor": snapshot.get("next_expected_actor", "operator_review"),
            "sync_lifecycle_state": snapshot.get("sync_lifecycle_state", "unknown_review"),
            "operator_action_required": snapshot.get("operator_action_required", False),
            "next_safe_move": snapshot.get("next_safe_move", "Build sync health before relying on this read-model."),
            "can_request_fix_from_app": snapshot.get("can_request_fix_from_app", False),
            "request_marker_path": snapshot.get("request_marker_path", DEFAULT_REQUEST_MARKER_PATH.as_posix()),
            "app_request_marker_path": snapshot.get("app_request_marker_path", DEFAULT_APP_REQUEST_MARKER_PATH),
        },
        "proof_sources": report["sources"],
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def _operator_markdown(payload: dict[str, Any]) -> str:
    recommended = payload["recommended_fix"]
    lines = [
        "# OpenClaw Sync Health",
        "",
        f"Trust status: `{payload['trust_status']}`",
        f"Mirror status: `{payload['mirror_status']}`",
        f"Display status: `{payload['display_status']}`",
        f"Lifecycle state: `{payload['sync_lifecycle_state']}`",
        f"Operator action required: `{str(payload['operator_action_required']).lower()}`",
        f"Next expected actor: `{payload['next_expected_actor']}`",
        "",
        "Mirror counts:",
        f"- canonical_expected={payload['canonical_expected']}",
        f"- observed={payload['observed']}",
        f"- missing_expected={payload['missing_expected']}",
        f"- extra={payload['extra']}",
        f"- hash_mismatch={payload['hash_mismatch']}",
        f"- matched_hash={payload['matched_hash']}",
        "",
        "Recommended fix:",
        f"- kind: `{recommended['kind']}`",
        f"- display status: `{recommended['display_status']}`",
        f"- next expected actor: `{recommended['next_expected_actor']}`",
        f"- lifecycle state: `{recommended['sync_lifecycle_state']}`",
        f"- operator action required: `{str(recommended['operator_action_required']).lower()}`",
        f"- next: {recommended['next_safe_move']}",
        f"- app can request bounded Mac sync marker: `{str(recommended['can_request_fix_from_app']).lower()}`",
        "",
        "Proof:",
        f"- Mac heartbeat: `{payload['last_mac_heartbeat']['status']}` at `{payload['last_mac_heartbeat']['time']}`",
        f"- Mac completion: `{payload['last_mac_completion']['status']}` at `{payload['last_mac_completion']['time']}`",
        f"- PC import: `{payload['last_pc_import']['status']}` at `{payload['last_pc_import']['time']}`",
        f"- Windows task log present: `{str(payload['last_pc_import']['windows_task_log_present']).lower()}`",
    ]
    if payload["stale_files"]:
        lines.extend(["", "Stale files:"])
        lines.extend(f"- `{item}`" for item in payload["stale_files"])
    if payload["extra_files"]:
        lines.extend(["", "Extra files:"])
        lines.extend(f"- `{item}`" for item in payload["extra_files"])
    lines.extend(
        [
            "",
            "No-authority posture:",
        ]
    )
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Sync Health is a read-model and ledger snapshot only.",
            "- It does not remote-control Mac or Windows, run arbitrary commands, modify Mission Control, or broaden sync authority.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def export_sync_health_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    repo_root: str | Path = ROOT,
) -> dict[str, Any]:
    payload = build_sync_health_read_model(db_path=db_path)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(_operator_markdown(payload), encoding="utf-8")
    return {
        "json_path": _display_path(json_path, repo_root=repo_root),
        "operator_path": _display_path(operator_path, repo_root=repo_root),
        "trust_status": payload["trust_status"],
        "mirror_status": payload["mirror_status"],
        "display_status": payload["display_status"],
        "sync_lifecycle_state": payload["sync_lifecycle_state"],
        "operator_action_required": payload["operator_action_required"],
        "next_expected_actor": payload["next_expected_actor"],
        "recommended_fix_kind": payload["recommended_fix"]["kind"],
        "missing_expected": payload["missing_expected"],
        "extra": payload["extra"],
        "hash_mismatch": payload["hash_mismatch"],
    }


def refresh_sync_health_from_manifest(
    *,
    db_path: str | Path | None = None,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: str | Path = ROOT,
    mac_status_path: str | Path = DEFAULT_MAC_STATUS_PATH,
    mac_completion_path: str | Path = DEFAULT_MAC_COMPLETION_PATH,
    pc_import_state_path: str | Path = DEFAULT_PC_IMPORT_STATE_PATH,
    pc_task_log_path: str | Path = DEFAULT_PC_TASK_LOG_PATH,
    windows_task_log_path: str | Path = DEFAULT_WINDOWS_TASK_LOG_PATH,
    request_marker_path: str | Path = DEFAULT_REQUEST_MARKER_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    """Record and export sync health from the latest mirror manifest.

    This is the durable PC-side bridge between a successful manifest import and
    the operator-facing read-model files Mission Control consumes. It reads
    metadata/proof files only and writes the sync_health read-model outputs.
    """

    build = build_sync_health_snapshot(
        db_path=db_path,
        manifest_path=manifest_path,
        read_model_root=read_model_root,
        repo_root=repo_root,
        mac_status_path=mac_status_path,
        mac_completion_path=mac_completion_path,
        pc_import_state_path=pc_import_state_path,
        pc_task_log_path=pc_task_log_path,
        windows_task_log_path=windows_task_log_path,
        request_marker_path=request_marker_path,
    )
    export = export_sync_health_read_model(
        db_path=db_path,
        export_root=export_root,
        repo_root=repo_root,
    )
    payload = build_sync_health_read_model(db_path=db_path)
    return {
        "sync_health_refreshed": True,
        "run_id": build.run_id,
        "snapshot_id": build.snapshot_id,
        "json_path": export["json_path"],
        "operator_path": export["operator_path"],
        "trust_status": payload["trust_status"],
        "mirror_status": payload["mirror_status"],
        "display_status": payload["display_status"],
        "sync_lifecycle_state": payload["sync_lifecycle_state"],
        "operator_action_required": payload["operator_action_required"],
        "canonical_expected": payload["canonical_expected"],
        "observed": payload["observed"],
        "missing_expected": payload["missing_expected"],
        "extra": payload["extra"],
        "hash_mismatch": payload["hash_mismatch"],
        "matched_hash": payload["matched_hash"],
        **NO_AUTHORITY_FLAGS,
    }


def format_sync_health_report(payload: dict[str, Any]) -> str:
    snapshot = payload.get("latest_snapshot")
    lines = ["OpenClaw Sync Health v0", ""]
    if not snapshot:
        lines.extend(["Status: `empty`", "No sync health snapshot has been built yet."])
    else:
        lines.extend(
            [
                f"Trust status: `{snapshot['trust_status']}`",
                f"Mirror status: `{snapshot['mirror_status']}`",
                f"Display status: `{snapshot['display_status']}`",
                f"Lifecycle state: `{snapshot['sync_lifecycle_state']}`",
                f"Operator action required: `{str(snapshot['operator_action_required']).lower()}`",
                f"Next expected actor: `{snapshot['next_expected_actor']}`",
                "",
                "Mirror counts:",
                f"- canonical_expected={snapshot['canonical_expected']}",
                f"- observed={snapshot['observed']}",
                f"- missing_expected={snapshot['missing_expected']}",
                f"- extra={snapshot['extra']}",
                f"- hash_mismatch={snapshot['hash_mismatch']}",
                f"- matched_hash={snapshot['matched_hash']}",
                "",
                f"Recommended fix: `{snapshot['recommended_fix_kind']}`",
                f"Next safe move: {snapshot['next_safe_move']}",
                f"App request changes repair path: `{str(snapshot['can_request_fix_from_app']).lower()}`",
            ]
        )
        if payload.get("report") == "proof":
            lines.extend(["", "Proof sources:"])
            for source in payload.get("sources", []):
                lines.append(
                    f"- {source['source_kind']}: present={bool(source['present'])} "
                    f"status={source['source_status']} time={source['source_time']}"
                )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Read-model only; no arbitrary command, remote control, SSH/SCP/rsync, Docker/Ollama, runtime, agent, deletion, or move authority.",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "NO_AUTHORITY_FLAGS",
    "build_sync_health_read_model",
    "build_sync_health_report",
    "build_sync_health_snapshot",
    "classify_sync_health",
    "compare_manifest_to_backend",
    "export_sync_health_read_model",
    "format_sync_health_report",
    "init_sync_health_schema",
    "refresh_sync_health_from_manifest",
    "sync_health_table_names",
]
