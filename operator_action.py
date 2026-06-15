"""Operator Action Path v0 for helm-gated backend work.

This module records operator action requests, explicit approvals, allowlisted
backend command executions, and execution receipts in the existing Business Ops
ledger under a separated ``operator_action_*`` namespace.

It is deliberately not arbitrary shell, runtime activation, agent activation,
remote control, deployment, Docker/Ollama execution, or a hidden approval path.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import (
    DEFAULT_DB_PATH,
    init_business_ops_ledger,
    record_action_intent_gate_receipt,
    record_approval_log_entry,
    record_approval_request_record,
)


ROOT = Path(__file__).resolve().parent
OPERATOR_ACTION_VERSION = "operator_action_path_v0"
READ_MODEL_VERSION = "operator_actions_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "operator_actions.json"
OPERATOR_EXPORT_NAME = "operator_actions_OPERATOR.md"
COMMAND_TIMEOUT_SECONDS = 180
MAX_CAPTURE_CHARS = 20000

NO_AUTHORITY_FLAGS = {
    "arbitrary_shell_allowed": False,
    "runtime_activation_allowed": False,
    "agent_activation_allowed": False,
    "docker_allowed": False,
    "ollama_allowed": False,
    "network_allowed": False,
    "remote_control_allowed": False,
    "client_deployment_allowed": False,
    "file_delete_allowed": False,
    "file_move_allowed": False,
}

ALLOWED_SOURCE_KINDS = {
    "mission_control",
    "telegram",
    "cli",
    "report_bridge",
    "future_client_node",
    "unknown",
}

FORBIDDEN_COMMAND_TOKENS = {
    "bash",
    "sh",
    "zsh",
    "fish",
    "powershell",
    "cmd",
    "docker",
    "ollama",
    "ssh",
    "scp",
    "rsync",
    "apt",
    "apt-get",
    "npm",
    "pip",
    "pip3",
    "rm",
    "mv",
}


@dataclass(frozen=True)
class AllowedAction:
    action_type: str
    display_command: str
    command: tuple[str, ...]
    category: str
    description: str
    timeout_seconds: int = COMMAND_TIMEOUT_SECONDS


ALLOWED_ACTIONS: dict[str, AllowedAction] = {
    "export_context_selection_read_model": AllowedAction(
        action_type="export_context_selection_read_model",
        display_command=(
            "PYTHONDONTWRITEBYTECODE=1 python3 "
            "scripts/export_context_selection_read_model.py --format operator"
        ),
        command=(
            "python3",
            "scripts/export_context_selection_read_model.py",
            "--format",
            "operator",
        ),
        category="read_model_export",
        description="Refresh the bounded Context Selection generated read-model.",
    ),
    "export_report_bridge_read_model": AllowedAction(
        action_type="export_report_bridge_read_model",
        display_command=(
            "PYTHONDONTWRITEBYTECODE=1 python3 "
            "scripts/export_report_bridge_read_model.py --format operator"
        ),
        command=(
            "python3",
            "scripts/export_report_bridge_read_model.py",
            "--format",
            "operator",
        ),
        category="read_model_export",
        description="Refresh the bounded Report Bridge generated read-model.",
    ),
    "prepare_mac_read_model_shuttle": AllowedAction(
        action_type="prepare_mac_read_model_shuttle",
        display_command=(
            "PYTHONDONTWRITEBYTECODE=1 python3 "
            "scripts/prepare_mac_read_model_shuttle.py --format operator"
        ),
        command=(
            "python3",
            "scripts/prepare_mac_read_model_shuttle.py",
            "--format",
            "operator",
        ),
        category="read_model_shuttle",
        description="Prepare an E-drive Mac read-model shuttle package.",
    ),
    "query_generated_read_model_mirror": AllowedAction(
        action_type="query_generated_read_model_mirror",
        display_command=(
            "PYTHONDONTWRITEBYTECODE=1 python3 "
            "scripts/query_corpus_atlas.py --report generated-read-model-mirror --format operator"
        ),
        command=(
            "python3",
            "scripts/query_corpus_atlas.py",
            "--report",
            "generated-read-model-mirror",
            "--format",
            "operator",
        ),
        category="status_query",
        description="Query Mac generated-read-model mirror status.",
    ),
}


@dataclass(frozen=True)
class ActionRequestResult:
    action_id: str
    action_type: str
    status: str
    validation_status: str
    approval_required: bool
    request_receipt_id: str | None
    rejection_reason: str | None


@dataclass(frozen=True)
class ActionApprovalResult:
    action_id: str
    approval_id: str
    status: str
    approved_by: str
    approval_receipt_id: str


@dataclass(frozen=True)
class ActionExecutionResult:
    action_id: str
    execution_id: str
    action_type: str
    status: str
    exit_code: int
    duration_ms: int
    receipt_id: str
    stdout_text: str
    stderr_text: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(
        "\0".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _bool(value: bool) -> int:
    return 1 if value else 0


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _ledger_path(db_path: str | Path | None) -> Path:
    path = Path(db_path or DEFAULT_DB_PATH)
    if path.is_absolute():
        return path
    return ROOT / path


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _truncate(text: str | None, limit: int = MAX_CAPTURE_CHARS) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[truncated]\n"


def _validate_allowed_action(action: AllowedAction) -> None:
    if not action.command:
        raise ValueError(f"allowed action has empty command: {action.action_type}")
    if any(not isinstance(part, str) or not part for part in action.command):
        raise ValueError(f"allowed action command parts must be non-empty strings: {action.action_type}")
    if any(part in {"|", "&&", ";", ">", "<"} for part in action.command):
        raise ValueError(f"command composition is forbidden: {action.action_type}")
    first = action.command[0].lower()
    if first in FORBIDDEN_COMMAND_TOKENS:
        raise ValueError(f"forbidden command executable for action {action.action_type}: {first}")
    lowered = [part.lower() for part in action.command]
    for token in ("install", "clone", "run", "pull"):
        if token in lowered and any(name in lowered for name in ("docker", "ollama", "git", "pip", "npm", "apt")):
            raise ValueError(f"forbidden command token in action {action.action_type}: {token}")


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS operator_action_allowed_commands (
  action_type TEXT PRIMARY KEY,
  command_json TEXT NOT NULL,
  display_command TEXT NOT NULL,
  category TEXT NOT NULL,
  description TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  approval_required INTEGER NOT NULL DEFAULT 1,
  timeout_seconds INTEGER NOT NULL,
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
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS operator_action_requests (
  action_id TEXT PRIMARY KEY,
  action_type TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL,
  approval_required INTEGER NOT NULL DEFAULT 1,
  validation_status TEXT NOT NULL,
  validation_summary TEXT NOT NULL,
  request_receipt_id TEXT,
  approval_id TEXT,
  execution_id TEXT,
  source_kind TEXT NOT NULL DEFAULT 'cli',
  source_channel TEXT NOT NULL DEFAULT 'backend_cli',
  source_message_id TEXT,
  source_user_label TEXT,
  source_node_id TEXT,
  source_raw_text_present INTEGER NOT NULL DEFAULT 0,
  source_raw_text_stored INTEGER NOT NULL DEFAULT 0,
  runtime_activation_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  arbitrary_shell_allowed INTEGER NOT NULL DEFAULT 0,
  network_allowed INTEGER NOT NULL DEFAULT 0,
  docker_allowed INTEGER NOT NULL DEFAULT 0,
  ollama_allowed INTEGER NOT NULL DEFAULT 0,
  remote_control_allowed INTEGER NOT NULL DEFAULT 0,
  client_deployment_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS operator_action_approvals (
  approval_id TEXT PRIMARY KEY,
  action_id TEXT NOT NULL UNIQUE,
  approved_by TEXT NOT NULL,
  approval_note TEXT NOT NULL,
  approved_at TEXT NOT NULL,
  approval_status TEXT NOT NULL,
  approval_receipt_id TEXT NOT NULL,
  FOREIGN KEY (action_id) REFERENCES operator_action_requests(action_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS operator_action_executions (
  execution_id TEXT PRIMARY KEY,
  action_id TEXT NOT NULL UNIQUE,
  action_type TEXT NOT NULL,
  command_json TEXT NOT NULL,
  display_command TEXT NOT NULL,
  cwd TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT NOT NULL,
  exit_code INTEGER,
  duration_ms INTEGER,
  stdout_text TEXT NOT NULL DEFAULT '',
  stderr_text TEXT NOT NULL DEFAULT '',
  receipt_id TEXT,
  timeout_seconds INTEGER NOT NULL,
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
  FOREIGN KEY (action_id) REFERENCES operator_action_requests(action_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS operator_action_receipts (
  receipt_id TEXT PRIMARY KEY,
  action_id TEXT NOT NULL,
  execution_id TEXT,
  receipt_type TEXT NOT NULL,
  result TEXT NOT NULL,
  summary TEXT NOT NULL,
  stdout_excerpt TEXT NOT NULL DEFAULT '',
  stderr_excerpt TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
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
  FOREIGN KEY (action_id) REFERENCES operator_action_requests(action_id),
  FOREIGN KEY (execution_id) REFERENCES operator_action_executions(execution_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS operator_action_rejections (
  rejection_id TEXT PRIMARY KEY,
  action_id TEXT,
  action_type TEXT NOT NULL,
  rejection_reason TEXT NOT NULL,
  requested_by TEXT,
  created_at TEXT NOT NULL
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_operator_action_requests_status ON operator_action_requests(status)",
        "CREATE INDEX IF NOT EXISTS idx_operator_action_requests_type ON operator_action_requests(action_type)",
        "CREATE INDEX IF NOT EXISTS idx_operator_action_executions_status ON operator_action_executions(status)",
    )


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _run_migrations(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "operator_action_requests", "source_kind", "TEXT NOT NULL DEFAULT 'cli'")
    _ensure_column(conn, "operator_action_requests", "source_channel", "TEXT NOT NULL DEFAULT 'backend_cli'")
    _ensure_column(conn, "operator_action_requests", "source_message_id", "TEXT")
    _ensure_column(conn, "operator_action_requests", "source_user_label", "TEXT")
    _ensure_column(conn, "operator_action_requests", "source_node_id", "TEXT")
    _ensure_column(
        conn,
        "operator_action_requests",
        "source_raw_text_present",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(
        conn,
        "operator_action_requests",
        "source_raw_text_stored",
        "INTEGER NOT NULL DEFAULT 0",
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_operator_action_requests_source_kind ON operator_action_requests(source_kind)"
    )


def init_operator_action_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    parent = Path(path).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    for action in ALLOWED_ACTIONS.values():
        _validate_allowed_action(action)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for statement in _sql_statements():
            conn.execute(statement)
        _run_migrations(conn)
        _seed_allowed_commands(conn)
        conn.commit()
    finally:
        conn.close()
    return path


def operator_action_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_operator_action_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'operator_action_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _seed_allowed_commands(conn: sqlite3.Connection) -> None:
    now = utc_now()
    for action in ALLOWED_ACTIONS.values():
        conn.execute(
            """
INSERT INTO operator_action_allowed_commands (
  action_type, command_json, display_command, category, description, enabled,
  approval_required, timeout_seconds, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?, ?)
ON CONFLICT(action_type) DO UPDATE SET
  command_json = excluded.command_json,
  display_command = excluded.display_command,
  category = excluded.category,
  description = excluded.description,
  enabled = 1,
  approval_required = 1,
  timeout_seconds = excluded.timeout_seconds,
  updated_at = excluded.updated_at,
  runtime_activation_allowed = 0,
  agent_activation_allowed = 0,
  arbitrary_shell_allowed = 0,
  network_allowed = 0,
  docker_allowed = 0,
  ollama_allowed = 0,
  remote_control_allowed = 0,
  client_deployment_allowed = 0,
  file_delete_allowed = 0,
  file_move_allowed = 0
""".strip(),
            (
                action.action_type,
                stable_json(list(action.command)),
                action.display_command,
                action.category,
                action.description,
                action.timeout_seconds,
                now,
                now,
            ),
        )


def _get_request(conn: sqlite3.Connection, action_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM operator_action_requests WHERE action_id = ?",
        (action_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown operator action id: {action_id}")
    return row


def _insert_receipt(
    conn: sqlite3.Connection,
    *,
    receipt_id: str,
    action_id: str,
    receipt_type: str,
    result: str,
    summary: str,
    execution_id: str | None = None,
    stdout_excerpt: str = "",
    stderr_excerpt: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
INSERT INTO operator_action_receipts (
  receipt_id, action_id, execution_id, receipt_type, result, summary,
  stdout_excerpt, stderr_excerpt, payload_json, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(receipt_id) DO UPDATE SET
  result = excluded.result,
  summary = excluded.summary,
  stdout_excerpt = excluded.stdout_excerpt,
  stderr_excerpt = excluded.stderr_excerpt,
  payload_json = excluded.payload_json,
  created_at = excluded.created_at
""".strip(),
        (
            receipt_id,
            action_id,
            execution_id,
            receipt_type,
            result,
            summary,
            stdout_excerpt,
            stderr_excerpt,
            stable_json(payload or {}),
            utc_now(),
        ),
    )


def _validate_action_source(
    *,
    source_kind: str,
    source_channel: str,
    source_message_id: str | None,
    source_user_label: str | None,
    source_node_id: str | None,
    source_raw_text_present: bool,
    source_raw_text_stored: bool,
) -> dict[str, Any]:
    source_kind = source_kind.strip()
    source_channel = source_channel.strip()
    if source_kind not in ALLOWED_SOURCE_KINDS:
        raise ValueError(f"unsupported source_kind: {source_kind}")
    if not source_channel:
        raise ValueError("source_channel is required")
    if source_raw_text_stored:
        raise ValueError("source_raw_text_stored must be false")
    return {
        "source_kind": source_kind,
        "source_channel": source_channel,
        "source_message_id": source_message_id.strip() if isinstance(source_message_id, str) and source_message_id.strip() else None,
        "source_user_label": source_user_label.strip() if isinstance(source_user_label, str) and source_user_label.strip() else None,
        "source_node_id": source_node_id.strip() if isinstance(source_node_id, str) and source_node_id.strip() else None,
        "source_raw_text_present": bool(source_raw_text_present),
        "source_raw_text_stored": False,
    }


def request_operator_action(
    *,
    action_type: str,
    requested_by: str,
    reason: str,
    action_id: str | None = None,
    source_kind: str = "cli",
    source_channel: str = "backend_cli",
    source_message_id: str | None = None,
    source_user_label: str | None = None,
    source_node_id: str | None = None,
    source_raw_text_present: bool = False,
    source_raw_text_stored: bool = False,
    db_path: str | Path | None = None,
) -> ActionRequestResult:
    action_type = action_type.strip()
    requested_by = requested_by.strip()
    reason = reason.strip()
    if not action_type:
        raise ValueError("action_type is required")
    if not requested_by:
        raise ValueError("requested_by is required")
    if not reason:
        raise ValueError("reason is required")
    source = _validate_action_source(
        source_kind=source_kind,
        source_channel=source_channel,
        source_message_id=source_message_id,
        source_user_label=source_user_label,
        source_node_id=source_node_id,
        source_raw_text_present=source_raw_text_present,
        source_raw_text_stored=source_raw_text_stored,
    )

    path = init_operator_action_schema(db_path)
    now = utc_now()
    resolved_action_id = action_id or _row_id("opact", action_type, requested_by, reason, now)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        allowed = ALLOWED_ACTIONS.get(action_type)
        if allowed is None:
            summary = f"Rejected unknown operator action type: {action_type}"
            conn.execute(
                """
INSERT INTO operator_action_requests (
  action_id, action_type, requested_by, reason, created_at, updated_at,
  status, approval_required, validation_status, validation_summary,
  source_kind, source_channel, source_message_id, source_user_label,
  source_node_id, source_raw_text_present, source_raw_text_stored
) VALUES (?, ?, ?, ?, ?, ?, 'rejected', 1, 'rejected', ?, ?, ?, ?, ?, ?, ?, 0)
ON CONFLICT(action_id) DO UPDATE SET
  status = 'rejected',
  validation_status = 'rejected',
  validation_summary = excluded.validation_summary,
  updated_at = excluded.updated_at,
  source_kind = excluded.source_kind,
  source_channel = excluded.source_channel,
  source_message_id = excluded.source_message_id,
  source_user_label = excluded.source_user_label,
  source_node_id = excluded.source_node_id,
  source_raw_text_present = excluded.source_raw_text_present,
  source_raw_text_stored = 0
""".strip(),
                (
                    resolved_action_id,
                    action_type,
                    requested_by,
                    reason,
                    now,
                    now,
                    summary,
                    source["source_kind"],
                    source["source_channel"],
                    source["source_message_id"],
                    source["source_user_label"],
                    source["source_node_id"],
                    _bool(source["source_raw_text_present"]),
                ),
            )
            conn.execute(
                """
INSERT INTO operator_action_rejections (
  rejection_id, action_id, action_type, rejection_reason, requested_by, created_at
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(rejection_id) DO NOTHING
""".strip(),
                (
                    _row_id("oprej", resolved_action_id, action_type, summary),
                    resolved_action_id,
                    action_type,
                    summary,
                    requested_by,
                    now,
                ),
            )
            conn.commit()
            gate_receipt_id = f"opact_gate_{resolved_action_id}"
            record_action_intent_gate_receipt(
                packet_id=gate_receipt_id,
                packet_type="operator_action.request",
                gate_result="FAIL",
                evaluation_summary=summary,
                actor=requested_by,
                db_path=path,
                approval_required=1,
                action_type=action_type,
                action_id=resolved_action_id,
            )
            _insert_receipt(
                conn,
                receipt_id=gate_receipt_id,
                action_id=resolved_action_id,
                receipt_type="request_validation",
                result="rejected",
                summary=summary,
                payload={
                    "action_type": action_type,
                    "approval_required": True,
                    "allowed": False,
                    "source": source,
                    **NO_AUTHORITY_FLAGS,
                },
            )
            conn.commit()
            return ActionRequestResult(
                action_id=resolved_action_id,
                action_type=action_type,
                status="rejected",
                validation_status="rejected",
                approval_required=True,
                request_receipt_id=gate_receipt_id,
                rejection_reason=summary,
            )

        validation_summary = f"Action type is allowlisted and requires explicit approval: {action_type}"
        request_receipt_id = f"opact_approval_request_{resolved_action_id}"
        gate_receipt_id = f"opact_gate_{resolved_action_id}"
        approval_id = f"opapproval_{resolved_action_id}"
        conn.execute(
            """
INSERT INTO operator_action_requests (
  action_id, action_type, requested_by, reason, created_at, updated_at,
  status, approval_required, validation_status, validation_summary,
  request_receipt_id, approval_id, source_kind, source_channel,
  source_message_id, source_user_label, source_node_id,
  source_raw_text_present, source_raw_text_stored
) VALUES (?, ?, ?, ?, ?, ?, 'requested', 1, 'allowlisted', ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
ON CONFLICT(action_id) DO UPDATE SET
  action_type = excluded.action_type,
  requested_by = excluded.requested_by,
  reason = excluded.reason,
  updated_at = excluded.updated_at,
  status = CASE
    WHEN operator_action_requests.status IN ('approved', 'completed', 'failed', 'running') THEN operator_action_requests.status
    ELSE excluded.status
  END,
  approval_required = 1,
  validation_status = excluded.validation_status,
  validation_summary = excluded.validation_summary,
  request_receipt_id = excluded.request_receipt_id,
  approval_id = excluded.approval_id,
  source_kind = excluded.source_kind,
  source_channel = excluded.source_channel,
  source_message_id = excluded.source_message_id,
  source_user_label = excluded.source_user_label,
  source_node_id = excluded.source_node_id,
  source_raw_text_present = excluded.source_raw_text_present,
  source_raw_text_stored = 0
""".strip(),
            (
                resolved_action_id,
                action_type,
                requested_by,
                reason,
                now,
                now,
                validation_summary,
                request_receipt_id,
                approval_id,
                source["source_kind"],
                source["source_channel"],
                source["source_message_id"],
                source["source_user_label"],
                source["source_node_id"],
                _bool(source["source_raw_text_present"]),
            ),
        )
        conn.commit()
        record_action_intent_gate_receipt(
            packet_id=gate_receipt_id,
            packet_type="operator_action.request",
            gate_result="PASS",
            evaluation_summary=validation_summary,
            actor=requested_by,
            db_path=path,
            approval_required=1,
            action_type=action_type,
            action_id=resolved_action_id,
            command=allowed.display_command,
        )
        record_approval_request_record(
            packet_id=request_receipt_id,
            packet_type="operator_action.approval_request",
            approval_id=approval_id,
            approval_request_summary=f"Approval required for {action_type}: {reason}",
            requester_agent=requested_by,
            action_intent_ref=gate_receipt_id,
            risk_tier="bounded_backend_command",
            db_path=path,
            action_id=resolved_action_id,
            no_auto_approval=True,
            command=allowed.display_command,
        )
        _insert_receipt(
            conn,
            receipt_id=request_receipt_id,
            action_id=resolved_action_id,
            receipt_type="approval_request",
            result="requested",
            summary=f"Approval requested for {action_type}.",
            payload={
                "action_id": resolved_action_id,
                "action_type": action_type,
                "approval_required": True,
                "auto_approved": False,
                "source": source,
                "command": list(allowed.command),
                "display_command": allowed.display_command,
                **NO_AUTHORITY_FLAGS,
            },
        )
        conn.commit()
        return ActionRequestResult(
            action_id=resolved_action_id,
            action_type=action_type,
            status="requested",
            validation_status="allowlisted",
            approval_required=True,
            request_receipt_id=request_receipt_id,
            rejection_reason=None,
        )
    finally:
        conn.close()


def approve_operator_action(
    *,
    action_id: str,
    approved_by: str,
    approval_note: str,
    db_path: str | Path | None = None,
) -> ActionApprovalResult:
    approved_by = approved_by.strip()
    approval_note = approval_note.strip()
    if not approved_by:
        raise ValueError("approved_by is required")
    if not approval_note:
        raise ValueError("approval_note is required")
    path = init_operator_action_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        request = _get_request(conn, action_id)
        if request["status"] == "rejected":
            raise ValueError(f"cannot approve rejected action: {action_id}")
        if request["validation_status"] != "allowlisted":
            raise ValueError(f"cannot approve non-allowlisted action: {action_id}")
        if request["status"] in {"running", "completed"}:
            raise ValueError(f"cannot approve already executed action: {action_id}")

        approval_id = request["approval_id"] or f"opapproval_{action_id}"
        approval_receipt_id = f"opact_approval_{action_id}"
        now = utc_now()
        conn.execute(
            """
INSERT INTO operator_action_approvals (
  approval_id, action_id, approved_by, approval_note, approved_at,
  approval_status, approval_receipt_id
) VALUES (?, ?, ?, ?, ?, 'approved', ?)
ON CONFLICT(action_id) DO UPDATE SET
  approved_by = excluded.approved_by,
  approval_note = excluded.approval_note,
  approved_at = excluded.approved_at,
  approval_status = 'approved',
  approval_receipt_id = excluded.approval_receipt_id
""".strip(),
            (
                approval_id,
                action_id,
                approved_by,
                approval_note,
                now,
                approval_receipt_id,
            ),
        )
        conn.execute(
            """
UPDATE operator_action_requests
SET status = 'approved', updated_at = ?, approval_id = ?
WHERE action_id = ?
""".strip(),
            (now, approval_id, action_id),
        )
        conn.commit()
        record_approval_log_entry(
            packet_id=approval_receipt_id,
            packet_type="operator_action.approval_decision",
            approval_verdict="APPROVED",
            approval_summary=approval_note,
            approver_name=approved_by,
            request_id=request["request_receipt_id"],
            db_path=path,
            action_id=action_id,
            action_type=request["action_type"],
            execution_not_started=True,
        )
        _insert_receipt(
            conn,
            receipt_id=approval_receipt_id,
            action_id=action_id,
            receipt_type="approval_decision",
            result="approved",
            summary=f"Action {action_id} approved for bounded execution.",
            payload={
                "action_id": action_id,
                "action_type": request["action_type"],
                "approved_by": approved_by,
                "approval_note": approval_note,
                "execution_started": False,
                **NO_AUTHORITY_FLAGS,
            },
        )
        conn.commit()
        return ActionApprovalResult(
            action_id=action_id,
            approval_id=approval_id,
            status="approved",
            approved_by=approved_by,
            approval_receipt_id=approval_receipt_id,
        )
    finally:
        conn.close()


def _execute_allowed_command(action: AllowedAction) -> subprocess.CompletedProcess[str]:
    _validate_allowed_action(action)
    return subprocess.run(
        list(action.command),
        cwd=ROOT,
        env={"PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=action.timeout_seconds,
        shell=False,
    )


def execute_operator_action(
    *,
    action_id: str,
    db_path: str | Path | None = None,
) -> ActionExecutionResult:
    path = init_operator_action_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        request = _get_request(conn, action_id)
        if request["status"] != "approved":
            raise ValueError(f"operator action must be approved before execution: {action_id}")
        approval = conn.execute(
            "SELECT * FROM operator_action_approvals WHERE action_id = ? AND approval_status = 'approved'",
            (action_id,),
        ).fetchone()
        if approval is None:
            raise ValueError(f"operator action has no explicit approval row: {action_id}")
        action = ALLOWED_ACTIONS.get(request["action_type"])
        if action is None:
            raise ValueError(f"operator action is no longer allowlisted: {request['action_type']}")

        execution_id = f"opexec_{action_id}"
        receipt_id = f"opreceipt_{action_id}"
        started_at = utc_now()
        conn.execute(
            """
INSERT INTO operator_action_executions (
  execution_id, action_id, action_type, command_json, display_command, cwd,
  started_at, status, timeout_seconds
) VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?)
ON CONFLICT(action_id) DO UPDATE SET
  command_json = excluded.command_json,
  display_command = excluded.display_command,
  cwd = excluded.cwd,
  started_at = excluded.started_at,
  status = 'running',
  timeout_seconds = excluded.timeout_seconds
""".strip(),
            (
                execution_id,
                action_id,
                action.action_type,
                stable_json(list(action.command)),
                action.display_command,
                ROOT.as_posix(),
                started_at,
                action.timeout_seconds,
            ),
        )
        conn.execute(
            "UPDATE operator_action_requests SET status = 'running', updated_at = ? WHERE action_id = ?",
            (started_at, action_id),
        )
        conn.commit()

        start = time.monotonic()
        try:
            completed = _execute_allowed_command(action)
            exit_code = int(completed.returncode)
            stdout_text = _truncate(completed.stdout)
            stderr_text = _truncate(completed.stderr)
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout_text = _truncate(exc.stdout if isinstance(exc.stdout, str) else "")
            stderr_text = _truncate(
                (exc.stderr if isinstance(exc.stderr, str) else "")
                + f"\nCommand timed out after {action.timeout_seconds} seconds."
            )
        duration_ms = int((time.monotonic() - start) * 1000)
        status = "completed" if exit_code == 0 else "failed"
        completed_at = utc_now()

        conn.execute(
            """
UPDATE operator_action_executions
SET completed_at = ?, status = ?, exit_code = ?, duration_ms = ?,
    stdout_text = ?, stderr_text = ?, receipt_id = ?
WHERE action_id = ?
""".strip(),
            (
                completed_at,
                status,
                exit_code,
                duration_ms,
                stdout_text,
                stderr_text,
                receipt_id,
                action_id,
            ),
        )
        conn.execute(
            """
UPDATE operator_action_requests
SET status = ?, updated_at = ?, execution_id = ?
WHERE action_id = ?
""".strip(),
            (status, completed_at, execution_id, action_id),
        )
        _insert_receipt(
            conn,
            receipt_id=receipt_id,
            action_id=action_id,
            execution_id=execution_id,
            receipt_type="execution_receipt",
            result=status,
            summary=(
                f"Allowlisted operator action {action.action_type} "
                f"{status} with exit_code={exit_code}."
            ),
            stdout_excerpt=stdout_text[:2000],
            stderr_excerpt=stderr_text[:2000],
            payload={
                "action_id": action_id,
                "action_type": action.action_type,
                "execution_id": execution_id,
                "command": list(action.command),
                "display_command": action.display_command,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
                "status": status,
                "approval_id": approval["approval_id"],
                "arbitrary_shell_used": False,
                "shell_true": False,
                **NO_AUTHORITY_FLAGS,
            },
        )
        conn.commit()
        return ActionExecutionResult(
            action_id=action_id,
            execution_id=execution_id,
            action_type=action.action_type,
            status=status,
            exit_code=exit_code,
            duration_ms=duration_ms,
            receipt_id=receipt_id,
            stdout_text=stdout_text,
            stderr_text=stderr_text,
        )
    finally:
        conn.close()


def _turnstile_result_status(
    *,
    ok: bool,
    side_effect_status: str,
    detail: str,
    meta: dict[str, Any] | None,
) -> str:
    if ok:
        return "completed"
    text = f"{side_effect_status} {detail}".lower()
    meta = meta or {}
    if bool(meta.get("send_hold_active")) or "send_hold" in text or "blocked" in text:
        return "blocked"
    if "refused" in text or "refus" in text:
        return "refused"
    return "failed"


def record_executor_turnstile_action(
    *,
    packet_id: str,
    surface: str,
    ok: bool,
    side_effect_status: str,
    detail: str = "",
    side_effect_id: str | None = None,
    db_path: str | Path | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    """Record one idempotent operator-action receipt for a compose executor outcome."""

    packet_id = (packet_id or "").strip()
    surface = (surface or "").strip()
    if not packet_id:
        raise ValueError("packet_id is required")
    if not surface:
        raise ValueError("surface is required")

    path = init_operator_action_schema(db_path)
    action_id = _row_id("opact_turnstile", packet_id, surface)
    receipt_id = f"opreceipt_turnstile_{action_id}"
    now = utc_now()
    status = _turnstile_result_status(
        ok=ok,
        side_effect_status=side_effect_status,
        detail=detail,
        meta=meta,
    )
    summary = f"Compose executor {surface} recorded as {status} for packet {packet_id}."
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
INSERT INTO operator_action_requests (
  action_id, action_type, requested_by, reason, created_at, updated_at,
  status, approval_required, validation_status, validation_summary,
  request_receipt_id, source_kind, source_channel, source_raw_text_present,
  source_raw_text_stored
) VALUES (?, ?, 'chief_compose', ?, ?, ?, ?, 1, 'turnstile_recorded', ?, ?,
          'mission_control', 'chief_compose.execute_packet', 0, 0)
ON CONFLICT(action_id) DO UPDATE SET
  updated_at = excluded.updated_at,
  status = excluded.status,
  validation_status = excluded.validation_status,
  validation_summary = excluded.validation_summary,
  request_receipt_id = excluded.request_receipt_id,
  source_kind = excluded.source_kind,
  source_channel = excluded.source_channel,
  source_raw_text_present = 0,
  source_raw_text_stored = 0
""".strip(),
            (
                action_id,
                surface,
                f"Auto-record compose executor outcome for packet {packet_id}.",
                now,
                now,
                status,
                summary,
                receipt_id,
            ),
        )
        _insert_receipt(
            conn,
            receipt_id=receipt_id,
            action_id=action_id,
            receipt_type="executor_turnstile_receipt",
            result=status,
            summary=summary,
            payload={
                "packet_id": packet_id,
                "surface": surface,
                "ok": bool(ok),
                "side_effect_status": side_effect_status,
                "side_effect_id": side_effect_id,
                "detail": detail,
                "compose_executor_path": True,
                "external_action_authority_changed": False,
                **NO_AUTHORITY_FLAGS,
                "receipt_meta": meta or {},
            },
        )
        conn.commit()
    finally:
        conn.close()
    return receipt_id


def _all_rows(conn: sqlite3.Connection, table: str, order_by: str) -> list[dict[str, Any]]:
    rows = conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
    return [dict(row) for row in rows]


def build_operator_action_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
    action_id: str | None = None,
) -> dict[str, Any]:
    path = init_operator_action_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        requests = _all_rows(conn, "operator_action_requests", "created_at DESC, action_id DESC")
        approvals = _all_rows(conn, "operator_action_approvals", "approved_at DESC, approval_id DESC")
        executions = _all_rows(conn, "operator_action_executions", "started_at DESC, execution_id DESC")
        receipts = _all_rows(conn, "operator_action_receipts", "created_at DESC, receipt_id DESC")
        rejections = _all_rows(conn, "operator_action_rejections", "created_at DESC, rejection_id DESC")
        allowed = _all_rows(conn, "operator_action_allowed_commands", "action_type")

        if action_id:
            requests = [row for row in requests if row["action_id"] == action_id]
            approvals = [row for row in approvals if row["action_id"] == action_id]
            executions = [row for row in executions if row["action_id"] == action_id]
            receipts = [row for row in receipts if row["action_id"] == action_id]
            rejections = [row for row in rejections if row["action_id"] == action_id]

        status_counts = Counter(row["status"] for row in requests)
        execution_counts = Counter(row["status"] for row in executions)
        counts = {
            "requests": len(requests),
            "pending_approval": status_counts.get("requested", 0),
            "approved": len(approvals),
            "completed": status_counts.get("completed", 0),
            "failed": status_counts.get("failed", 0),
            "rejected": status_counts.get("rejected", 0),
            "running": status_counts.get("running", 0),
            "executions": len(executions),
            "receipts": len(receipts),
            "rejections": len(rejections),
            "allowed_actions": len(allowed),
            "request_status": dict(sorted(status_counts.items())),
            "execution_status": dict(sorted(execution_counts.items())),
            "action_types": dict(sorted(Counter(row["action_type"] for row in requests).items())),
        }
        if report == "summary":
            items = requests[:10]
        elif report == "pending":
            items = [row for row in requests if row["status"] == "requested"]
        elif report == "requests":
            items = requests
        elif report == "approvals":
            items = approvals
        elif report == "executions":
            items = executions
        elif report == "receipts":
            items = receipts
        elif report == "rejections":
            items = rejections
        elif report == "allowed":
            items = allowed
        elif report == "latest":
            items = requests[:1]
        else:
            raise ValueError(f"unknown operator action report: {report}")
        return {
            "status": "ok",
            "report": report,
            "db_path": str(path),
            "counts": counts,
            "items": items,
            "latest_action": requests[0] if requests else None,
            "latest_execution": executions[0] if executions else None,
            "latest_receipt": receipts[0] if receipts else None,
            "allowed_action_types": sorted(ALLOWED_ACTIONS),
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def _count_rows(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _latest_row(conn: sqlite3.Connection, table: str, order_by: str) -> dict[str, Any] | None:
    row = conn.execute(f"SELECT * FROM {table} ORDER BY {order_by} LIMIT 1").fetchone()
    return dict(row) if row else None


def build_operator_actions_read_model(
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    path = init_operator_action_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        requests = _all_rows(conn, "operator_action_requests", "created_at DESC, action_id DESC")
        approvals = _all_rows(conn, "operator_action_approvals", "approved_at DESC, approval_id DESC")
        executions = _all_rows(conn, "operator_action_executions", "started_at DESC, execution_id DESC")
        receipts = _all_rows(conn, "operator_action_receipts", "created_at DESC, receipt_id DESC")
        rejections = _all_rows(conn, "operator_action_rejections", "created_at DESC, rejection_id DESC")
        status_counts = Counter(row["status"] for row in requests)
        source_counts = Counter(row.get("source_kind") or "unknown" for row in requests)
        pending_by_source = Counter(
            row.get("source_kind") or "unknown"
            for row in requests
            if row["status"] == "requested"
        )
        latest = requests[0] if requests else None
        latest_execution = executions[0] if executions else None
        execution_receipts = [
            receipt for receipt in receipts if receipt.get("receipt_type") == "execution_receipt"
        ]
        latest_receipt = execution_receipts[0] if execution_receipts else None
        latest_time = (
            latest_receipt["created_at"]
            if latest_receipt
            else latest["created_at"]
            if latest
            else "not_available_no_operator_actions"
        )
        return {
            "schema_version": READ_MODEL_VERSION,
            "read_model_version": READ_MODEL_VERSION,
            "mode": "helm_gated_operator_action_posture_only",
            "generated_at": latest_time,
            "source_ledger_path": _display_path(path),
            "source_ledger_namespace": "operator_action_*",
            "request_count": len(requests),
            "pending_approval_count": status_counts.get("requested", 0),
            "approved_count": len(approvals),
            "completed_count": status_counts.get("completed", 0),
            "failed_count": status_counts.get("failed", 0),
            "rejected_count": status_counts.get("rejected", 0),
            "execution_count": len(executions),
            "receipt_count": len(receipts),
            "latest_action": _safe_action_summary(latest),
            "last_execution_receipt_summary": _safe_receipt_summary(latest_receipt, latest_execution),
            "request_count_by_source_kind": dict(sorted(source_counts.items())),
            "pending_approval_by_source_kind": dict(sorted(pending_by_source.items())),
            "latest_request_source": _safe_source_summary(latest),
            "source_channel_posture": {
                "mission_control_ready": True,
                "telegram_ready_metadata_only": True,
                "telegram_api_wired": False,
                "telegram_polling": False,
                "telegram_sending": False,
                "cli_ready": True,
                "report_bridge_ready": True,
                "future_client_node_ready": True,
                "source_raw_text_stored_by_default": False,
                "message_text_becomes_shell": False,
                "all_sources_require_approval": True,
            },
            "allowed_action_types": [
                {
                    "action_type": action.action_type,
                    "category": action.category,
                    "description": action.description,
                    "display_command": action.display_command,
                    "approval_required": True,
                }
                for action in ALLOWED_ACTIONS.values()
            ],
            "request_status_counts": dict(sorted(status_counts.items())),
            "execution_status_counts": dict(
                sorted(Counter(row["status"] for row in executions).items())
            ),
            "rejection_count": len(rejections),
            "authority_flags": dict(NO_AUTHORITY_FLAGS),
            **NO_AUTHORITY_FLAGS,
            "helm_flow": [
                "orient",
                "request",
                "review",
                "approve",
                "execute_bounded_work",
                "receipt",
                "updated_helm_state",
            ],
            "claims_not_made": [
                "arbitrary_shell",
                "hidden_approval",
                "auto_execution",
                "runtime_activation",
                "agent_activation",
                "tool_or_model_execution",
                "remote_control",
                "client_deployment",
                "truth_promotion",
            ],
        }
    finally:
        conn.close()


def _safe_action_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "action_id": row["action_id"],
        "action_type": row["action_type"],
        "requested_by": row["requested_by"],
        "reason": row["reason"],
        "status": row["status"],
        "approval_required": bool(row["approval_required"]),
        "validation_status": row["validation_status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "source_kind": row.get("source_kind") or "unknown",
        "source_channel": row.get("source_channel") or "unknown",
        "source_message_id": row.get("source_message_id"),
        "source_user_label": row.get("source_user_label"),
        "source_node_id": row.get("source_node_id"),
        "source_raw_text_present": bool(row.get("source_raw_text_present", 0)),
        "source_raw_text_stored": bool(row.get("source_raw_text_stored", 0)),
    }


def _safe_source_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "source_kind": row.get("source_kind") or "unknown",
        "source_channel": row.get("source_channel") or "unknown",
        "source_message_id": row.get("source_message_id"),
        "source_user_label": row.get("source_user_label"),
        "source_node_id": row.get("source_node_id"),
        "source_raw_text_present": bool(row.get("source_raw_text_present", 0)),
        "source_raw_text_stored": bool(row.get("source_raw_text_stored", 0)),
    }


def _safe_receipt_summary(
    receipt: dict[str, Any] | None,
    execution: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if receipt is None:
        return None
    return {
        "receipt_id": receipt["receipt_id"],
        "action_id": receipt["action_id"],
        "execution_id": receipt["execution_id"],
        "receipt_type": receipt["receipt_type"],
        "result": receipt["result"],
        "summary": receipt["summary"],
        "created_at": receipt["created_at"],
        "exit_code": execution["exit_code"] if execution else None,
        "duration_ms": execution["duration_ms"] if execution else None,
    }


def format_operator_action_report(payload: dict[str, Any]) -> str:
    lines = [
        f"Operator Action Path v0 - {payload['report']}",
        "",
        f"Requests: {payload['counts']['requests']}",
        f"Pending approval: {payload['counts']['pending_approval']}",
        f"Approved decisions: {payload['counts']['approved']}",
        f"Completed: {payload['counts']['completed']}",
        f"Failed: {payload['counts']['failed']}",
        f"Rejected: {payload['counts']['rejected']}",
        f"Executions: {payload['counts']['executions']}",
        f"Receipts: {payload['counts']['receipts']}",
        "",
        "Items:",
    ]
    for item in payload.get("items") or []:
        if "display_command" in item and "action_id" not in item:
            lines.append(f"- {item['action_type']}: {item['display_command']}")
        elif "rejection_reason" in item:
            lines.append(f"- rejected {item['action_type']}: {item['rejection_reason']}")
        elif "receipt_type" in item:
            lines.append(f"- {item['receipt_type']} {item['receipt_id']}: {item['result']}")
        elif "execution_id" in item and "exit_code" in item:
            lines.append(
                f"- {item['execution_id']} for {item['action_type']}: {item['status']} exit={item['exit_code']}"
            )
        elif "approval_id" in item and "approved_by" in item:
            lines.append(f"- {item['approval_id']} for {item['action_id']}: {item['approval_status']}")
        else:
            lines.append(f"- {item['action_id']} {item['action_type']}: {item['status']}")
    if not payload.get("items"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Requests do not auto-approve or auto-execute.",
            "- Execution uses hardcoded allowlisted command arrays only.",
            "- No arbitrary shell, runtime activation, agent activation, Docker/Ollama, network, remote control, client deployment, file deletion, or file move authority.",
        ]
    )
    return "\n".join(lines)


def _counts_line(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def format_operator_actions_read_model(read_model: dict[str, Any]) -> str:
    latest = read_model.get("latest_action")
    receipt = read_model.get("last_execution_receipt_summary")
    lines = [
        "# Operator Actions Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over helm-gated `operator_action_*` SQLite rows.",
        "- It exposes requested, approved, executed, failed, rejected, and receipted bounded backend actions.",
        "",
        "What this is not:",
        "- It is not arbitrary shell, hidden authority, runtime activation, agent activation, remote control, client deployment, Docker/Ollama, or truth promotion.",
        "",
        "Summary:",
        f"- Requests: {read_model['request_count']}.",
        f"- Pending approval: {read_model['pending_approval_count']}.",
        f"- Approved decisions: {read_model['approved_count']}.",
        f"- Completed: {read_model['completed_count']}; failed: {read_model['failed_count']}; rejected: {read_model['rejected_count']}.",
        f"- Receipts: {read_model['receipt_count']}.",
        f"- Requests by source kind: {_counts_line(read_model['request_count_by_source_kind'])}.",
        f"- Pending approval by source kind: {_counts_line(read_model['pending_approval_by_source_kind'])}.",
        "",
        "Latest action:",
    ]
    if latest:
        lines.extend(
            [
                f"- Action: `{latest['action_id']}`.",
                f"- Type: `{latest['action_type']}`.",
                f"- Status: `{latest['status']}`.",
                f"- Requested by: `{latest['requested_by']}`.",
                f"- Source: `{latest['source_kind']}` / `{latest['source_channel']}`.",
            ]
        )
    else:
        lines.append("- None.")
    lines.append("")
    lines.append("Last execution receipt:")
    if receipt:
        lines.extend(
            [
                f"- Receipt: `{receipt['receipt_id']}`.",
                f"- Result: `{receipt['result']}`.",
                f"- Exit code: `{receipt['exit_code']}`.",
                f"- Summary: {receipt['summary']}",
            ]
        )
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "Allowed action types:",
        ]
    )
    for action in read_model["allowed_action_types"]:
        lines.append(f"- `{action['action_type']}`: {action['description']}")
    lines.extend(
        [
            "",
            "Source boundary:",
            "- Mission Control, Telegram, CLI, Report Bridge, and future client nodes are source metadata only.",
            "- Telegram-ready means metadata shape only; no Telegram API, polling, or sending is wired.",
            "- Source message text does not become shell and raw source text is not stored by default.",
            "- All source kinds still require explicit approval before execution.",
            "",
            "Authority boundary:",
            "- arbitrary_shell_allowed=false; runtime_activation_allowed=false; agent_activation_allowed=false.",
            "- docker_allowed=false; ollama_allowed=false; network_allowed=false; remote_control_allowed=false.",
            "- client_deployment_allowed=false; file_delete_allowed=false; file_move_allowed=false.",
            "",
            "Next safe move:",
            "- Surface this read-model in Mission Control as a request/review/result posture view before adding any app-side request writer.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_operator_actions_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_operator_actions_read_model(db_path=db_path)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_operator_actions_read_model(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "request_count": read_model["request_count"],
        "pending_approval_count": read_model["pending_approval_count"],
        "completed_count": read_model["completed_count"],
        "failed_count": read_model["failed_count"],
        "rejected_count": read_model["rejected_count"],
        **NO_AUTHORITY_FLAGS,
    }


def format_request_result(result: ActionRequestResult) -> str:
    lines = [
        "Operator Action Request v0",
        "",
        f"Action: `{result.action_id}`",
        f"Type: `{result.action_type}`",
        f"Status: `{result.status}`",
        f"Validation: `{result.validation_status}`",
        f"Approval required: `{str(result.approval_required).lower()}`",
    ]
    if result.rejection_reason:
        lines.append(f"Rejection: {result.rejection_reason}")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Request creation does not approve or execute the action.",
        ]
    )
    return "\n".join(lines)


def format_approval_result(result: ActionApprovalResult) -> str:
    return "\n".join(
        [
            "Operator Action Approval v0",
            "",
            f"Action: `{result.action_id}`",
            f"Approval: `{result.approval_id}`",
            f"Status: `{result.status}`",
            f"Approved by: `{result.approved_by}`",
            f"Receipt: `{result.approval_receipt_id}`",
            "",
            "Boundary:",
            "- Approval records an explicit decision only; execution requires a separate command.",
        ]
    )


def format_execution_result(result: ActionExecutionResult) -> str:
    return "\n".join(
        [
            "Operator Action Execution v0",
            "",
            f"Action: `{result.action_id}`",
            f"Execution: `{result.execution_id}`",
            f"Type: `{result.action_type}`",
            f"Status: `{result.status}`",
            f"Exit code: `{result.exit_code}`",
            f"Duration ms: `{result.duration_ms}`",
            f"Receipt: `{result.receipt_id}`",
            "",
            "Boundary:",
            "- Executed one hardcoded allowlisted command array after explicit approval.",
            "- No arbitrary shell, runtime, agent, Docker/Ollama, network, remote-control, deployment, file-delete, or file-move authority.",
        ]
    )


def format_export_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Operator Actions Read-Model Export v0",
            "",
            f"Exported: `{summary['json_path']}`",
            f"Operator: `{summary['operator_path']}`",
            f"Requests: {summary['request_count']}",
            f"Pending approval: {summary['pending_approval_count']}",
            f"Completed: {summary['completed_count']}; failed: {summary['failed_count']}; rejected: {summary['rejected_count']}",
            "",
            "Boundary:",
            "- Export reads `operator_action_*` rows and writes generated read-model files only.",
        ]
    )


__all__ = [
    "ALLOWED_ACTIONS",
    "ALLOWED_SOURCE_KINDS",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "ActionApprovalResult",
    "ActionExecutionResult",
    "ActionRequestResult",
    "approve_operator_action",
    "build_operator_action_report",
    "build_operator_actions_read_model",
    "execute_operator_action",
    "export_operator_actions_read_model",
    "format_approval_result",
    "format_execution_result",
    "format_export_summary",
    "format_operator_action_report",
    "format_request_result",
    "init_operator_action_schema",
    "operator_action_table_names",
    "record_executor_turnstile_action",
    "request_operator_action",
    "stable_json",
]
