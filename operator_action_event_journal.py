"""Durable journal for operator UI action events.

This records meaningful Mission Control button clicks and local-surface results
without granting authority or completing workflow blockers. Action-specific
receipts still decide whether invoice steps progress.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "operator_action_event_journal_v0"
READ_MODEL_ID = "operator_action_event_journal"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
DEFAULT_DB_PATH = Path(".openclaw/operator_events/operator_action_events.sqlite")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

ACTION_CATEGORIES = {
    "LOCAL_INSPECTION",
    "GOVERNED_REQUEST",
    "UNSUPPORTED_PENDING",
    "BLOCKED",
    "DISABLED",
}

EVENT_STATUSES = {
    "RECEIVED",
    "HANDLED",
    "BLOCKED",
    "PENDING_NOT_WIRED",
    "DISABLED",
    "SUPERSEDED",
}

PENDING_STATUSES = {"PENDING_NOT_WIRED", "DISABLED", "BLOCKED", "RECEIVED"}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_store(db_path: Path = DEFAULT_DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS operator_action_events (
              event_id TEXT PRIMARY KEY,
              source_request_id TEXT NOT NULL,
              client_ref TEXT,
              workflow_ref TEXT,
              bundle_id TEXT,
              action_ref TEXT,
              intended_use TEXT,
              label_clicked TEXT,
              action_category TEXT NOT NULL,
              emitted_backend_request INTEGER NOT NULL CHECK (emitted_backend_request IN (0,1)),
              handled INTEGER NOT NULL CHECK (handled IN (0,1)),
              handler_ref TEXT,
              status TEXT NOT NULL,
              operator_visible_summary TEXT NOT NULL,
              no_external_action INTEGER NOT NULL CHECK (no_external_action IN (0,1)),
              physical_deletion_allowed INTEGER NOT NULL CHECK (physical_deletion_allowed IN (0,1)),
              proof_refs_json TEXT NOT NULL,
              expected_next_safe_move TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


def _event_id(
    *,
    source_request_id: str,
    action_ref: str,
    intended_use: str,
    label_clicked: str,
) -> str:
    return f"operator_action_event:{_short_hash(source_request_id, action_ref, intended_use, label_clicked)}"


def record_operator_action_event(
    *,
    source_request_id: str,
    client_ref: str | None,
    workflow_ref: str | None,
    bundle_id: str | None,
    action_ref: str | None,
    intended_use: str | None,
    label_clicked: str | None,
    action_category: str,
    emitted_backend_request: bool,
    handled: bool,
    handler_ref: str | None,
    status: str,
    operator_visible_summary: str,
    no_external_action: bool,
    physical_deletion_allowed: bool = False,
    proof_refs: Sequence[str] | None = None,
    expected_next_safe_move: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if action_category not in ACTION_CATEGORIES:
        raise ValueError(f"unsupported action_category: {action_category}")
    if status not in EVENT_STATUSES:
        raise ValueError(f"unsupported event status: {status}")
    source = source_request_id or "unknown_operator_action"
    action = action_ref or intended_use or "unknown_action"
    intended = intended_use or action
    label = label_clicked or action
    timestamp = generated_at or _now()
    event = {
        "event_id": _event_id(
            source_request_id=source,
            action_ref=action,
            intended_use=intended,
            label_clicked=label,
        ),
        "source_request_id": source,
        "client_ref": client_ref or "",
        "workflow_ref": workflow_ref or "",
        "bundle_id": bundle_id or "",
        "action_ref": action,
        "intended_use": intended,
        "label_clicked": label,
        "action_category": action_category,
        "emitted_backend_request": bool(emitted_backend_request),
        "handled": bool(handled),
        "handler_ref": handler_ref or "",
        "status": status,
        "operator_visible_summary": operator_visible_summary,
        "no_external_action": bool(no_external_action),
        "physical_deletion_allowed": bool(physical_deletion_allowed),
        "proof_refs": _as_tuple(proof_refs),
        "expected_next_safe_move": expected_next_safe_move or "",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    init_store(db_path)
    with _connect(db_path) as conn:
        existing = conn.execute(
            "SELECT created_at FROM operator_action_events WHERE event_id = ?",
            (event["event_id"],),
        ).fetchone()
        created_at = str(existing["created_at"]) if existing else event["created_at"]
        event["created_at"] = created_at
        conn.execute(
            """
            INSERT INTO operator_action_events (
              event_id, source_request_id, client_ref, workflow_ref, bundle_id,
              action_ref, intended_use, label_clicked, action_category,
              emitted_backend_request, handled, handler_ref, status,
              operator_visible_summary, no_external_action,
              physical_deletion_allowed, proof_refs_json,
              expected_next_safe_move, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
              action_category=excluded.action_category,
              emitted_backend_request=excluded.emitted_backend_request,
              handled=excluded.handled,
              handler_ref=excluded.handler_ref,
              status=excluded.status,
              operator_visible_summary=excluded.operator_visible_summary,
              no_external_action=excluded.no_external_action,
              physical_deletion_allowed=excluded.physical_deletion_allowed,
              proof_refs_json=excluded.proof_refs_json,
              expected_next_safe_move=excluded.expected_next_safe_move,
              updated_at=excluded.updated_at
            """,
            (
                event["event_id"],
                event["source_request_id"],
                event["client_ref"],
                event["workflow_ref"],
                event["bundle_id"],
                event["action_ref"],
                event["intended_use"],
                event["label_clicked"],
                event["action_category"],
                1 if event["emitted_backend_request"] else 0,
                1 if event["handled"] else 0,
                event["handler_ref"],
                event["status"],
                event["operator_visible_summary"],
                1 if event["no_external_action"] else 0,
                1 if event["physical_deletion_allowed"] else 0,
                stable_json(event["proof_refs"]),
                event["expected_next_safe_move"],
                event["created_at"],
                event["updated_at"],
            ),
        )
    return event


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    event = dict(row)
    event["emitted_backend_request"] = bool(event["emitted_backend_request"])
    event["handled"] = bool(event["handled"])
    event["no_external_action"] = bool(event["no_external_action"])
    event["physical_deletion_allowed"] = bool(event["physical_deletion_allowed"])
    event["proof_refs"] = tuple(json.loads(str(event.pop("proof_refs_json") or "[]")))
    return event


def list_events(db_path: Path = DEFAULT_DB_PATH, *, limit: int = 50) -> tuple[dict[str, Any], ...]:
    init_store(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM operator_action_events
            ORDER BY updated_at DESC, created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return tuple(_row_to_event(row) for row in rows)


def build_read_model(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    generated_at: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    events = list_events(db_path, limit=limit)
    pending = tuple(event for event in events if event["status"] in PENDING_STATUSES and not event["handled"])
    blocked_or_disabled = tuple(event for event in events if event["status"] in {"BLOCKED", "DISABLED"})
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "store_path": db_path.as_posix(),
        "event_count_returned": len(events),
        "pending_operator_intents": pending,
        "blocked_or_disabled_events": blocked_or_disabled,
        "events": events,
        "authority_boundary": {
            "external_actions_executed": False,
            "physical_deletion_performed": False,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "invoice_generation_performed": False,
            "email_send_performed": False,
            "supplier_portal_submit_performed": False,
            "ledger_posting_performed": False,
            "production_business_mutation_performed": False,
        },
    }


def write_exports(
    payload: Mapping[str, Any],
    export_root: Path = DEFAULT_EXPORT_ROOT,
) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    pending = payload.get("pending_operator_intents") or ()
    events = payload.get("events") or ()
    lines = [
        "# Operator Action Event Journal",
        "",
        f"- Events returned: {len(events)}",
        f"- Pending/not-wired intents: {len(pending)}",
        "- No external action, file deletion, workbook read, send, submit, ledger, or production mutation is authorized here.",
    ]
    if pending:
        lines.extend(["", "## Pending Intents"])
        for event in pending:
            lines.append(f"- {event['label_clicked']}: {event['operator_visible_summary']}")
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def export_read_model(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    limit: int = 50,
) -> tuple[dict[str, Any], Path, Path]:
    payload = build_read_model(db_path=db_path, generated_at=generated_at, limit=limit)
    json_path, operator_path = write_exports(payload, export_root=export_root)
    return payload, json_path, operator_path

