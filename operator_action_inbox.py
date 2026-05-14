"""Operator Action Inbox v0 for shared-drop request intake.

This module imports strict JSON request files from the E-drive shared drop into
the existing Operator Action Path. Import creates pending approval requests
only. It never approves, executes, shells out, moves files, deletes files, or
trusts user-supplied command strings.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from business_ops_ledger import DEFAULT_DB_PATH
from operator_action import (
    ALLOWED_ACTIONS,
    NO_AUTHORITY_FLAGS,
    init_operator_action_schema,
    request_operator_action,
    stable_json,
)


INBOX_SCHEMA_VERSION = "operator_action_request_v0"
DEFAULT_OPERATOR_ACTION_INBOX = Path("/mnt/e/openclaw/operator_actions/inbox")
DEFAULT_OPERATOR_ACTION_ARCHIVE = Path("/mnt/e/openclaw/operator_actions/archive")
DEFAULT_OPERATOR_ACTION_REJECTED = Path("/mnt/e/openclaw/operator_actions/rejected")

FORBIDDEN_REQUEST_KEYS = {
    "argv",
    "command",
    "command_args",
    "command_string",
    "execute",
    "shell",
    "shell_command",
}

ALLOWED_TOP_LEVEL_KEYS = {
    "schema_version",
    "request_id",
    "action_type",
    "requested_by",
    "reason",
    "created_at",
    "source",
    "authority",
}

ALLOWED_SOURCE_KEYS = {
    "node_id",
    "host_kind",
    "drop_path",
}

REQUIRED_AUTHORITY = {
    "approval_required": True,
    "auto_approve": False,
    "execute_immediately": False,
    **NO_AUTHORITY_FLAGS,
}


@dataclass(frozen=True)
class InboxImportItem:
    file_path: str
    request_file_hash: str | None
    action_id: str | None
    action_type: str | None
    status: str
    rejection_reason: str | None


@dataclass(frozen=True)
class InboxImportSummary:
    import_run_id: str
    imported_request_count: int
    rejected_request_count: int
    action_ids: tuple[str, ...]
    rejected_files: tuple[str, ...]
    items: tuple[InboxImportItem, ...]
    no_execution_occurred: bool
    approval_still_required: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(
        "\0".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS operator_action_inbox_imports (
  import_id TEXT PRIMARY KEY,
  import_run_id TEXT NOT NULL,
  request_file_path TEXT NOT NULL,
  request_file_hash TEXT,
  request_id TEXT,
  action_id TEXT,
  action_type TEXT,
  requested_by TEXT,
  source_node_id TEXT,
  source_host_kind TEXT,
  source_drop_path TEXT,
  status TEXT NOT NULL,
  rejection_reason TEXT,
  imported_at TEXT NOT NULL,
  approval_required INTEGER NOT NULL DEFAULT 1,
  auto_approve INTEGER NOT NULL DEFAULT 0,
  execute_immediately INTEGER NOT NULL DEFAULT 0,
  execution_started INTEGER NOT NULL DEFAULT 0,
  raw_request_body_stored INTEGER NOT NULL DEFAULT 0,
  runtime_activation_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  arbitrary_shell_allowed INTEGER NOT NULL DEFAULT 0,
  network_allowed INTEGER NOT NULL DEFAULT 0,
  docker_allowed INTEGER NOT NULL DEFAULT 0,
  ollama_allowed INTEGER NOT NULL DEFAULT 0,
  remote_control_allowed INTEGER NOT NULL DEFAULT 0,
  client_deployment_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS operator_action_inbox_rejections (
  rejection_id TEXT PRIMARY KEY,
  import_run_id TEXT NOT NULL,
  request_file_path TEXT NOT NULL,
  request_file_hash TEXT,
  action_type TEXT,
  rejection_reason TEXT NOT NULL,
  created_at TEXT NOT NULL
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_operator_action_inbox_imports_run ON operator_action_inbox_imports(import_run_id)",
        "CREATE INDEX IF NOT EXISTS idx_operator_action_inbox_imports_status ON operator_action_inbox_imports(status)",
        "CREATE INDEX IF NOT EXISTS idx_operator_action_inbox_imports_action ON operator_action_inbox_imports(action_id)",
    )


def init_operator_action_inbox_schema(db_path: str | Path | None = None) -> str:
    path = init_operator_action_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def operator_action_inbox_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_operator_action_inbox_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'operator_action_inbox_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _load_request_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("request file must contain a JSON object")
    return payload


def _require_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"request field is required: {key}")
    return value.strip()


def _optional_request_id(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("request_id")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("request_id must be a non-empty string or null")
    stripped = value.strip()
    if len(stripped) > 96 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for char in stripped):
        raise ValueError("request_id contains unsupported characters")
    return stripped


def _validate_iso_timestamp(value: str) -> None:
    normalized = value.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("created_at must be an ISO timestamp") from exc


def _contains_forbidden_keys(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_REQUEST_KEYS:
                return str(key)
            nested = _contains_forbidden_keys(child)
            if nested:
                return nested
    elif isinstance(value, list):
        for child in value:
            nested = _contains_forbidden_keys(child)
            if nested:
                return nested
    return None


def validate_action_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    forbidden_key = _contains_forbidden_keys(payload)
    if forbidden_key:
        raise ValueError(f"request contains forbidden command/control key: {forbidden_key}")

    unknown_top = sorted(set(payload) - ALLOWED_TOP_LEVEL_KEYS)
    if unknown_top:
        raise ValueError(f"request contains unsupported top-level field: {unknown_top[0]}")

    schema_version = _require_text(payload, "schema_version")
    if schema_version != INBOX_SCHEMA_VERSION:
        raise ValueError(f"unsupported request schema_version: {schema_version}")
    action_type = _require_text(payload, "action_type")
    if action_type not in ALLOWED_ACTIONS:
        raise ValueError(f"unknown allowlisted action_type: {action_type}")
    requested_by = _require_text(payload, "requested_by")
    reason = _require_text(payload, "reason")
    created_at = _require_text(payload, "created_at")
    _validate_iso_timestamp(created_at)
    request_id = _optional_request_id(payload)

    source = payload.get("source")
    if not isinstance(source, dict):
        raise ValueError("source must be an object")
    unknown_source = sorted(set(source) - ALLOWED_SOURCE_KEYS)
    if unknown_source:
        raise ValueError(f"source contains unsupported field: {unknown_source[0]}")
    source_node_id = _require_text(source, "node_id")
    source_host_kind = _require_text(source, "host_kind")
    source_drop_path = _require_text(source, "drop_path")

    authority = payload.get("authority")
    if not isinstance(authority, dict):
        raise ValueError("authority must be an object")
    for key, required in REQUIRED_AUTHORITY.items():
        if key not in authority:
            raise ValueError(f"authority flag is required: {key}")
        if authority[key] is not required:
            raise ValueError(f"authority flag has unsafe value: {key}")
    unknown_authority = sorted(set(authority) - set(REQUIRED_AUTHORITY))
    if unknown_authority:
        raise ValueError(f"authority contains unsupported field: {unknown_authority[0]}")

    return {
        "request_id": request_id,
        "action_type": action_type,
        "requested_by": requested_by,
        "reason": reason,
        "created_at": created_at,
        "source_node_id": source_node_id,
        "source_host_kind": source_host_kind,
        "source_drop_path": source_drop_path,
    }


def _action_id_for_request(validated: Mapping[str, Any], request_file_hash: str) -> str:
    request_id = validated.get("request_id")
    if request_id:
        return f"opact_inbox_{request_id}"
    return _row_id(
        "opact_inbox",
        validated["action_type"],
        validated["requested_by"],
        validated["reason"],
        request_file_hash,
    )


def _record_inbox_import(
    conn: sqlite3.Connection,
    *,
    import_run_id: str,
    file_path: Path,
    request_file_hash: str | None,
    status: str,
    action_id: str | None = None,
    action_type: str | None = None,
    requested_by: str | None = None,
    request_id: str | None = None,
    source_node_id: str | None = None,
    source_host_kind: str | None = None,
    source_drop_path: str | None = None,
    rejection_reason: str | None = None,
) -> None:
    now = utc_now()
    import_id = _row_id(
        "opain",
        import_run_id,
        file_path.as_posix(),
        request_file_hash or "no_hash",
        status,
    )
    conn.execute(
        """
INSERT INTO operator_action_inbox_imports (
  import_id, import_run_id, request_file_path, request_file_hash, request_id,
  action_id, action_type, requested_by, source_node_id, source_host_kind,
  source_drop_path, status, rejection_reason, imported_at, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(import_id) DO UPDATE SET
  action_id = excluded.action_id,
  action_type = excluded.action_type,
  requested_by = excluded.requested_by,
  status = excluded.status,
  rejection_reason = excluded.rejection_reason,
  imported_at = excluded.imported_at,
  notes = excluded.notes
""".strip(),
        (
            import_id,
            import_run_id,
            file_path.as_posix(),
            request_file_hash,
            request_id,
            action_id,
            action_type,
            requested_by,
            source_node_id,
            source_host_kind,
            source_drop_path,
            status,
            rejection_reason,
            now,
            "Inbox import records request provenance only; no execution occurred.",
        ),
    )
    if status == "rejected":
        conn.execute(
            """
INSERT INTO operator_action_inbox_rejections (
  rejection_id, import_run_id, request_file_path, request_file_hash,
  action_type, rejection_reason, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(rejection_id) DO NOTHING
""".strip(),
            (
                _row_id(
                    "opainrej",
                    import_run_id,
                    file_path.as_posix(),
                    request_file_hash or "no_hash",
                    rejection_reason or "unknown",
                ),
                import_run_id,
                file_path.as_posix(),
                request_file_hash,
                action_type,
                rejection_reason or "unknown rejection",
                now,
            ),
        )


def import_operator_action_request_file(
    *,
    file_path: str | Path,
    db_path: str | Path | None = None,
    import_run_id: str | None = None,
) -> InboxImportItem:
    path = Path(file_path)
    if not path.is_file():
        raise ValueError(f"operator action request file not found: {path}")

    db = init_operator_action_inbox_schema(db_path)
    resolved_run_id = import_run_id or _row_id("opainrun", path.as_posix(), utc_now())
    request_file_hash: str | None = None
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            request_file_hash = _sha256_file(path)
            payload = _load_request_json(path)
            validated = validate_action_request_payload(payload)
            action_id = _action_id_for_request(validated, request_file_hash)
            result = request_operator_action(
                action_id=action_id,
                action_type=validated["action_type"],
                requested_by=validated["requested_by"],
                reason=validated["reason"],
                db_path=db,
            )
            _record_inbox_import(
                conn,
                import_run_id=resolved_run_id,
                file_path=path,
                request_file_hash=request_file_hash,
                status="imported",
                action_id=result.action_id,
                action_type=validated["action_type"],
                requested_by=validated["requested_by"],
                request_id=validated.get("request_id"),
                source_node_id=validated["source_node_id"],
                source_host_kind=validated["source_host_kind"],
                source_drop_path=validated["source_drop_path"],
            )
            conn.commit()
            return InboxImportItem(
                file_path=path.as_posix(),
                request_file_hash=request_file_hash,
                action_id=result.action_id,
                action_type=validated["action_type"],
                status="imported",
                rejection_reason=None,
            )
        except Exception as exc:
            action_type = None
            try:
                payload = _load_request_json(path)
                if isinstance(payload.get("action_type"), str):
                    action_type = payload["action_type"].strip()
            except Exception:
                action_type = None
            _record_inbox_import(
                conn,
                import_run_id=resolved_run_id,
                file_path=path,
                request_file_hash=request_file_hash,
                status="rejected",
                action_type=action_type,
                rejection_reason=str(exc),
            )
            conn.commit()
            return InboxImportItem(
                file_path=path.as_posix(),
                request_file_hash=request_file_hash,
                action_id=None,
                action_type=action_type,
                status="rejected",
                rejection_reason=str(exc),
            )
    finally:
        conn.close()


def _request_files_from_inbox(inbox: str | Path) -> tuple[Path, ...]:
    inbox_path = Path(inbox)
    if not inbox_path.is_dir():
        raise ValueError(f"operator action inbox not found: {inbox_path}")
    return tuple(sorted(path for path in inbox_path.iterdir() if path.is_file() and path.suffix == ".json"))


def import_operator_action_requests(
    *,
    file_path: str | Path | None = None,
    inbox: str | Path = DEFAULT_OPERATOR_ACTION_INBOX,
    db_path: str | Path | None = None,
    import_run_id: str | None = None,
) -> InboxImportSummary:
    if file_path is None:
        files = _request_files_from_inbox(inbox)
    else:
        files = (Path(file_path),)
    run_id = import_run_id or _row_id(
        "opainrun",
        ",".join(path.as_posix() for path in files) or Path(inbox).as_posix(),
        utc_now(),
    )
    items = tuple(
        import_operator_action_request_file(
            file_path=path,
            db_path=db_path,
            import_run_id=run_id,
        )
        for path in files
    )
    action_ids = tuple(item.action_id for item in items if item.status == "imported" and item.action_id)
    rejected = tuple(item.file_path for item in items if item.status == "rejected")
    return InboxImportSummary(
        import_run_id=run_id,
        imported_request_count=len(action_ids),
        rejected_request_count=len(rejected),
        action_ids=action_ids,
        rejected_files=rejected,
        items=items,
        no_execution_occurred=True,
        approval_still_required=True,
    )


def build_operator_action_inbox_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
    import_run_id: str | None = None,
) -> dict[str, Any]:
    db = init_operator_action_inbox_schema(db_path)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        imports = conn.execute(
            """
SELECT *
FROM operator_action_inbox_imports
ORDER BY imported_at DESC, import_id DESC
""".strip()
        ).fetchall()
        rejections = conn.execute(
            """
SELECT *
FROM operator_action_inbox_rejections
ORDER BY created_at DESC, rejection_id DESC
""".strip()
        ).fetchall()
        if import_run_id:
            imports = [row for row in imports if row["import_run_id"] == import_run_id]
            rejections = [row for row in rejections if row["import_run_id"] == import_run_id]
        imported_count = sum(1 for row in imports if row["status"] == "imported")
        rejected_count = sum(1 for row in imports if row["status"] == "rejected")
        if report == "summary":
            items = imports[:10]
        elif report == "imports":
            items = imports
        elif report == "rejections":
            items = rejections
        else:
            raise ValueError(f"unknown operator action inbox report: {report}")
        return {
            "status": "ok",
            "report": report,
            "db_path": db,
            "default_inbox": DEFAULT_OPERATOR_ACTION_INBOX.as_posix(),
            "default_archive": DEFAULT_OPERATOR_ACTION_ARCHIVE.as_posix(),
            "default_rejected": DEFAULT_OPERATOR_ACTION_REJECTED.as_posix(),
            "counts": {
                "imports": len(imports),
                "imported": imported_count,
                "rejected": rejected_count,
                "rejection_rows": len(rejections),
            },
            "items": [dict(row) for row in items],
            "no_execution_occurred": True,
            "approval_still_required": True,
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def format_inbox_import_summary(summary: InboxImportSummary) -> str:
    lines = [
        "Operator Action Inbox v0 Import",
        "",
        f"Run: `{summary.import_run_id}`",
        f"Imported requests: {summary.imported_request_count}",
        f"Rejected requests: {summary.rejected_request_count}",
        f"No execution occurred: `{str(summary.no_execution_occurred).lower()}`",
        f"Approval still required: `{str(summary.approval_still_required).lower()}`",
        "",
        "Items:",
    ]
    if not summary.items:
        lines.append("- none")
    for item in summary.items:
        if item.status == "imported":
            lines.append(f"- imported `{item.file_path}` -> `{item.action_id}`")
        else:
            lines.append(f"- rejected `{item.file_path}`: {item.rejection_reason}")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Inbox import creates pending approval requests only.",
            "- No approval, execution, arbitrary shell, runtime, agent, Docker/Ollama, network, remote-control, deployment, file-delete, or file-move authority.",
        ]
    )
    return "\n".join(lines)


def format_operator_action_inbox_report(payload: dict[str, Any]) -> str:
    lines = [
        f"Operator Action Inbox v0 - {payload['report']}",
        "",
        f"Imports: {payload['counts']['imports']}",
        f"Imported: {payload['counts']['imported']}",
        f"Rejected: {payload['counts']['rejected']}",
        f"Default inbox: `{payload['default_inbox']}`",
        "",
        "Items:",
    ]
    if not payload["items"]:
        lines.append("- none")
    for item in payload["items"]:
        if "rejection_reason" in item and item.get("status") == "rejected":
            lines.append(f"- rejected `{item['request_file_path']}`: {item['rejection_reason']}")
        elif "action_id" in item:
            lines.append(f"- {item['status']} `{item['request_file_path']}` -> `{item.get('action_id') or 'none'}`")
        else:
            lines.append(f"- rejected `{item['request_file_path']}`: {item['rejection_reason']}")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Inbox rows are import provenance only.",
            "- Import does not approve or execute actions.",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "DEFAULT_OPERATOR_ACTION_ARCHIVE",
    "DEFAULT_OPERATOR_ACTION_INBOX",
    "DEFAULT_OPERATOR_ACTION_REJECTED",
    "INBOX_SCHEMA_VERSION",
    "InboxImportItem",
    "InboxImportSummary",
    "build_operator_action_inbox_report",
    "format_inbox_import_summary",
    "format_operator_action_inbox_report",
    "import_operator_action_request_file",
    "import_operator_action_requests",
    "init_operator_action_inbox_schema",
    "operator_action_inbox_table_names",
    "stable_json",
    "validate_action_request_payload",
]
