"""OpenClaw Work Board v0.

This module builds a local SQLite-backed work board from existing safe
OpenClaw metadata sources: routed intents, dropped intents, work packets,
operator actions, report bridge packages, and project capsules.

It is a control-plane/read-model layer only. It does not execute actions,
approve requests, activate agents, call models, call external APIs, or read
private/no-go raw content.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_work_packet import init_agent_work_packet_schema
from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger
from dropped_intent_registry import init_dropped_intent_schema
from intent_router import init_intent_router_schema
from operator_action import init_operator_action_schema
from project_capsule import init_project_capsule_schema
from report_bridge import init_report_bridge_schema


ROOT = Path(__file__).resolve().parent
WORK_BOARD_VERSION = "openclaw_work_board_v0"
READ_MODEL_VERSION = "work_board_read_model_v0"
DEFAULT_BOARD_ID = "openclaw_work_board_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "work_board.json"
OPERATOR_EXPORT_NAME = "work_board_OPERATOR.md"

BOARD_COLUMNS = {
    "captured_intent",
    "routed",
    "planned",
    "needs_review",
    "pending_approval",
    "approved",
    "in_progress",
    "blocked",
    "completed_with_receipt",
    "deferred",
    "rejected",
    "superseded",
}

SOURCE_KINDS = {
    "intent_record",
    "dropped_intent",
    "agent_work_packet",
    "operator_action",
    "report_bridge_package",
    "project_capsule",
    "manual_seed",
}

PRIORITY_HINTS = {"low", "normal", "high", "urgent", "unknown"}

NO_AUTHORITY_FLAGS = {
    "direct_execution_allowed": False,
    "arbitrary_shell_allowed": False,
    "auto_approval_allowed": False,
    "auto_execute_allowed": False,
    "agent_activation_allowed": False,
    "model_call_allowed": False,
    "tool_execution_allowed": False,
    "network_authority": False,
    "no_go_raw_access_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "client_deployment_allowed": False,
}

ALLOWED_TRANSITIONS = {
    "captured_intent": {"routed", "blocked", "superseded"},
    "routed": {"planned", "blocked", "superseded"},
    "planned": {"needs_review", "blocked", "superseded"},
    "needs_review": {"deferred", "rejected", "planned", "blocked", "superseded"},
    "pending_approval": {"approved", "blocked", "superseded"},
    "approved": {"in_progress", "blocked", "superseded"},
    "in_progress": {"completed_with_receipt", "blocked", "superseded"},
    "blocked": {"needs_review", "deferred", "rejected", "superseded"},
    "deferred": {"needs_review", "superseded"},
    "rejected": {"superseded"},
    "superseded": set(),
    "completed_with_receipt": {"superseded"},
}


@dataclass(frozen=True)
class WorkBoardBuildResult:
    run_id: str
    db_path: str
    board_id: str
    card_count: int
    counts_by_column: dict[str, int]


@dataclass(frozen=True)
class WorkBoardUpdateResult:
    card_id: str
    board_id: str
    previous_column: str
    board_column: str
    status: str
    updated: bool
    blocker_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS work_board_runs (
  run_id TEXT PRIMARY KEY,
  board_version TEXT NOT NULL,
  board_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  card_count INTEGER NOT NULL DEFAULT 0,
  direct_execution_allowed INTEGER NOT NULL DEFAULT 0,
  arbitrary_shell_allowed INTEGER NOT NULL DEFAULT 0,
  auto_approval_allowed INTEGER NOT NULL DEFAULT 0,
  auto_execute_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  no_go_raw_access_allowed INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  client_deployment_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS work_boards (
  board_id TEXT PRIMARY KEY,
  board_name TEXT NOT NULL,
  board_version TEXT NOT NULL,
  description TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  direct_execution_allowed INTEGER NOT NULL DEFAULT 0,
  auto_approval_allowed INTEGER NOT NULL DEFAULT 0,
  auto_execute_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS work_board_cards (
  card_id TEXT PRIMARY KEY,
  board_id TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_id TEXT NOT NULL,
  world_hint TEXT NOT NULL,
  agent_id TEXT,
  lane_id TEXT,
  intent_category TEXT,
  board_column TEXT NOT NULL,
  status TEXT NOT NULL,
  priority_hint TEXT NOT NULL,
  approval_required INTEGER NOT NULL DEFAULT 1,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  action_request_id TEXT,
  work_packet_id TEXT,
  receipt_id TEXT,
  blocker_reason TEXT,
  next_safe_move TEXT NOT NULL,
  evidence_basis TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  direct_execution_allowed INTEGER NOT NULL DEFAULT 0,
  arbitrary_shell_allowed INTEGER NOT NULL DEFAULT 0,
  auto_approval_allowed INTEGER NOT NULL DEFAULT 0,
  auto_execute_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  no_go_raw_access_allowed INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  client_deployment_allowed INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (board_id) REFERENCES work_boards(board_id) ON DELETE CASCADE,
  UNIQUE(board_id, source_kind, source_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS work_board_card_sources (
  card_source_id TEXT PRIMARY KEY,
  card_id TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_id TEXT NOT NULL,
  source_path TEXT,
  source_summary TEXT NOT NULL,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (card_id) REFERENCES work_board_cards(card_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS work_board_card_agents (
  card_agent_id TEXT PRIMARY KEY,
  card_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  lane_id TEXT,
  role TEXT NOT NULL,
  can_execute INTEGER NOT NULL DEFAULT 0,
  can_bypass_approval INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (card_id) REFERENCES work_board_cards(card_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS work_board_card_worlds (
  card_world_id TEXT PRIMARY KEY,
  card_id TEXT NOT NULL,
  world_hint TEXT NOT NULL,
  confidence TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (card_id) REFERENCES work_board_cards(card_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS work_board_card_dependencies (
  dependency_id TEXT PRIMARY KEY,
  card_id TEXT NOT NULL,
  dependency_kind TEXT NOT NULL,
  dependency_ref TEXT NOT NULL,
  dependency_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (card_id) REFERENCES work_board_cards(card_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS work_board_card_status_history (
  history_id TEXT PRIMARY KEY,
  card_id TEXT NOT NULL,
  previous_column TEXT,
  board_column TEXT NOT NULL,
  status TEXT NOT NULL,
  changed_by TEXT NOT NULL,
  change_reason TEXT NOT NULL,
  changed_at TEXT NOT NULL,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  approval_bypass_allowed INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (card_id) REFERENCES work_board_cards(card_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS work_board_card_blockers (
  blocker_id TEXT PRIMARY KEY,
  card_id TEXT NOT NULL,
  blocker_reason TEXT NOT NULL,
  blocker_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (card_id) REFERENCES work_board_cards(card_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS work_board_card_receipts (
  card_receipt_id TEXT PRIMARY KEY,
  card_id TEXT NOT NULL,
  receipt_kind TEXT NOT NULL,
  source_receipt_id TEXT,
  summary TEXT NOT NULL,
  created_at TEXT NOT NULL,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  auto_approval_allowed INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (card_id) REFERENCES work_board_cards(card_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS work_board_query_receipts (
  query_receipt_id TEXT PRIMARY KEY,
  board_id TEXT NOT NULL,
  report TEXT NOT NULL,
  card_count INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_work_board_cards_column ON work_board_cards(board_column)",
        "CREATE INDEX IF NOT EXISTS idx_work_board_cards_agent ON work_board_cards(agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_work_board_cards_world ON work_board_cards(world_hint)",
        "CREATE INDEX IF NOT EXISTS idx_work_board_cards_source ON work_board_cards(source_kind, source_id)",
    )


def init_work_board_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    parent = Path(path).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    init_intent_router_schema(path)
    init_dropped_intent_schema(path)
    init_agent_work_packet_schema(path)
    init_operator_action_schema(path)
    init_report_bridge_schema(path)
    init_project_capsule_schema(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def work_board_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_work_board_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'work_board%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _ensure_board(conn: sqlite3.Connection, *, board_id: str, now: str) -> None:
    conn.execute(
        """
INSERT INTO work_boards (
  board_id, board_name, board_version, description, created_at, updated_at,
  direct_execution_allowed, auto_approval_allowed, auto_execute_allowed,
  agent_activation_allowed
) VALUES (?, 'OpenClaw Work Board', ?, ?, ?, ?, 0, 0, 0, 0)
ON CONFLICT(board_id) DO UPDATE SET
  board_version = excluded.board_version,
  description = excluded.description,
  updated_at = excluded.updated_at,
  direct_execution_allowed = 0,
  auto_approval_allowed = 0,
  auto_execute_allowed = 0,
  agent_activation_allowed = 0
""".strip(),
        (
            board_id,
            WORK_BOARD_VERSION,
            "Local review board over intents, work packets, actions, dropped intents, packages, and capsules.",
            now,
            now,
        ),
    )


def _insert_run(conn: sqlite3.Connection, *, run_id: str, board_id: str, now: str) -> None:
    conn.execute(
        """
INSERT INTO work_board_runs (
  run_id, board_version, board_id, created_at, completed_at, card_count,
  direct_execution_allowed, arbitrary_shell_allowed, auto_approval_allowed,
  auto_execute_allowed, agent_activation_allowed, model_call_allowed,
  tool_execution_allowed, network_authority, no_go_raw_access_allowed,
  file_move_allowed, file_delete_allowed, client_deployment_allowed, notes
) VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?)
ON CONFLICT(run_id) DO UPDATE SET
  completed_at = excluded.completed_at,
  direct_execution_allowed = 0,
  arbitrary_shell_allowed = 0,
  auto_approval_allowed = 0,
  auto_execute_allowed = 0,
  agent_activation_allowed = 0,
  model_call_allowed = 0,
  tool_execution_allowed = 0,
  network_authority = 0,
  no_go_raw_access_allowed = 0,
  file_move_allowed = 0,
  file_delete_allowed = 0,
  client_deployment_allowed = 0,
  notes = excluded.notes
""".strip(),
        (
            run_id,
            WORK_BOARD_VERSION,
            board_id,
            now,
            now,
            "Board build projects safe metadata only; no execution, approval, or agent activation.",
        ),
    )


def _make_card(
    *,
    board_id: str,
    source_kind: str,
    source_id: str,
    title: str,
    summary: str,
    world_hint: str,
    agent_id: str | None,
    lane_id: str | None,
    intent_category: str | None,
    board_column: str,
    status: str,
    priority_hint: str = "normal",
    approval_required: bool = True,
    action_request_id: str | None = None,
    work_packet_id: str | None = None,
    receipt_id: str | None = None,
    blocker_reason: str | None = None,
    next_safe_move: str = "Review this card and choose the next approved lane.",
    evidence_basis: str = "safe_metadata_projection",
    source_path: str | None = None,
) -> dict[str, Any]:
    if source_kind not in SOURCE_KINDS:
        raise ValueError(f"unsupported source_kind: {source_kind}")
    if board_column not in BOARD_COLUMNS:
        raise ValueError(f"unsupported board_column: {board_column}")
    if priority_hint not in PRIORITY_HINTS:
        raise ValueError(f"unsupported priority_hint: {priority_hint}")
    return {
        "card_id": _row_id("wbcard", board_id, source_kind, source_id),
        "board_id": board_id,
        "title": title[:180],
        "summary": summary[:900],
        "source_kind": source_kind,
        "source_id": source_id,
        "source_path": source_path,
        "world_hint": world_hint or "unknown",
        "agent_id": agent_id,
        "lane_id": lane_id,
        "intent_category": intent_category,
        "board_column": board_column,
        "status": status,
        "priority_hint": priority_hint,
        "approval_required": bool(approval_required),
        "action_request_id": action_request_id,
        "work_packet_id": work_packet_id,
        "receipt_id": receipt_id,
        "blocker_reason": blocker_reason,
        "next_safe_move": next_safe_move[:900],
        "evidence_basis": evidence_basis,
    }


def _intent_cards(conn: sqlite3.Connection, board_id: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, "intent_records"):
        return []
    rows = conn.execute(
        """
SELECT intent_id, intent_text_preview, routed_agent_id, routed_lane_id,
       world_hint, intent_category, status, next_safe_move, approval_required,
       rejection_reason, created_at
FROM intent_records
ORDER BY created_at DESC, intent_id DESC
LIMIT 100
""".strip()
    ).fetchall()
    cards = []
    for row in rows:
        if row["status"] == "routed":
            column = "routed"
        elif row["status"] == "needs_operator_review":
            column = "needs_review"
        else:
            column = "rejected"
        cards.append(
            _make_card(
                board_id=board_id,
                source_kind="intent_record",
                source_id=row["intent_id"],
                title=f"Intent: {row['intent_text_preview']}",
                summary=row["next_safe_move"],
                world_hint=row["world_hint"],
                agent_id=row["routed_agent_id"],
                lane_id=row["routed_lane_id"],
                intent_category=row["intent_category"],
                board_column=column,
                status=row["status"],
                approval_required=bool(row["approval_required"]),
                blocker_reason=row["rejection_reason"],
                next_safe_move=row["next_safe_move"],
                evidence_basis="intent_router_record",
            )
        )
    return cards


def _dropped_intent_column(status: str) -> str:
    return {
        "unresolved": "needs_review",
        "unknown_review": "needs_review",
        "deferred": "deferred",
        "rejected": "rejected",
        "superseded": "superseded",
        "built": "completed_with_receipt",
    }.get(status, "needs_review")


def _dropped_intent_cards(conn: sqlite3.Connection, board_id: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, "dropped_intents"):
        return []
    rows = conn.execute(
        """
SELECT dropped_intent_id, title, short_summary, world_hint, agent_hint,
       lane_hint, intent_category, current_status, status_confidence,
       evidence_basis, suggested_next_question, suggested_next_lane,
       approval_required, created_at
FROM dropped_intents
ORDER BY
  CASE current_status
    WHEN 'unresolved' THEN 0
    WHEN 'unknown_review' THEN 1
    WHEN 'deferred' THEN 2
    ELSE 3
  END,
  updated_at DESC,
  dropped_intent_id
LIMIT 80
""".strip()
    ).fetchall()
    cards = []
    for row in rows:
        next_safe = f"{row['suggested_next_question']} Suggested lane: {row['suggested_next_lane']}."
        cards.append(
            _make_card(
                board_id=board_id,
                source_kind="dropped_intent",
                source_id=row["dropped_intent_id"],
                title=row["title"],
                summary=row["short_summary"],
                world_hint=row["world_hint"],
                agent_id=row["agent_hint"],
                lane_id=row["lane_hint"],
                intent_category=row["intent_category"],
                board_column=_dropped_intent_column(row["current_status"]),
                status=row["current_status"],
                priority_hint="high" if row["current_status"] in {"unresolved", "unknown_review"} else "normal",
                approval_required=bool(row["approval_required"]),
                next_safe_move=next_safe,
                evidence_basis=f"dropped_intent_registry:{row['evidence_basis']}",
            )
        )
    return cards


def _agent_work_packet_cards(conn: sqlite3.Connection, board_id: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, "agent_work_packets"):
        return []
    rows = conn.execute(
        """
SELECT packet_id, source_intent_id, routed_agent_id, routed_lane_id,
       world_hint, intent_category, goal, status, approval_required,
       execution_allowed, action_created, candidate_action_type, created_at
FROM agent_work_packets
ORDER BY created_at DESC, packet_id DESC
LIMIT 80
""".strip()
    ).fetchall()
    cards = []
    for row in rows:
        blocker = None
        column = "planned"
        if row["execution_allowed"] or row["action_created"]:
            column = "blocked"
            blocker = "Work packet claims execution/action creation authority; review required."
        cards.append(
            _make_card(
                board_id=board_id,
                source_kind="agent_work_packet",
                source_id=row["packet_id"],
                title=f"Work packet: {row['goal']}",
                summary=f"Draft packet for {row['routed_agent_id']}/{row['routed_lane_id']}.",
                world_hint=row["world_hint"],
                agent_id=row["routed_agent_id"],
                lane_id=row["routed_lane_id"],
                intent_category=row["intent_category"],
                board_column=column,
                status=row["status"],
                approval_required=bool(row["approval_required"]),
                work_packet_id=row["packet_id"],
                blocker_reason=blocker,
                next_safe_move="Review the planning packet; approval is required before any real action.",
                evidence_basis="agent_work_packet_record",
            )
        )
    return cards


def _latest_action_receipts(conn: sqlite3.Connection) -> dict[str, str]:
    if not _table_exists(conn, "operator_action_receipts"):
        return {}
    rows = conn.execute(
        """
SELECT action_id, receipt_id, created_at
FROM operator_action_receipts
ORDER BY created_at DESC, receipt_id DESC
""".strip()
    ).fetchall()
    receipts: dict[str, str] = {}
    for row in rows:
        receipts.setdefault(row["action_id"], row["receipt_id"])
    return receipts


def _operator_action_column(status: str) -> str:
    return {
        "requested": "pending_approval",
        "approved": "approved",
        "running": "in_progress",
        "completed": "completed_with_receipt",
        "failed": "blocked",
        "rejected": "rejected",
    }.get(status, "needs_review")


def _operator_action_cards(conn: sqlite3.Connection, board_id: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, "operator_action_requests"):
        return []
    receipts = _latest_action_receipts(conn)
    rows = conn.execute(
        """
SELECT action_id, action_type, requested_by, reason, status,
       approval_required, validation_status, source_kind, source_channel,
       created_at, updated_at
FROM operator_action_requests
ORDER BY created_at DESC, action_id DESC
LIMIT 100
""".strip()
    ).fetchall()
    cards = []
    for row in rows:
        receipt_id = receipts.get(row["action_id"])
        column = _operator_action_column(row["status"])
        blocker = None
        if row["status"] == "failed":
            blocker = "Operator action failed; inspect execution receipt before retry."
        cards.append(
            _make_card(
                board_id=board_id,
                source_kind="operator_action",
                source_id=row["action_id"],
                title=f"Operator action: {row['action_type']}",
                summary=row["reason"],
                world_hint="operations",
                agent_id="chief",
                lane_id="system_orchestration",
                intent_category="operator_action",
                board_column=column,
                status=row["status"],
                priority_hint="high" if row["status"] == "requested" else "normal",
                approval_required=bool(row["approval_required"]),
                action_request_id=row["action_id"],
                receipt_id=receipt_id,
                blocker_reason=blocker,
                next_safe_move="Review approval/execution receipts; do not execute from the board.",
                evidence_basis=f"operator_action:{row['validation_status']}:{row['source_kind']}/{row['source_channel']}",
            )
        )
    return cards


def _report_bridge_cards(conn: sqlite3.Connection, board_id: str) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    if _table_exists(conn, "report_bridge_packages"):
        rows = conn.execute(
            """
SELECT package_id, package_kind, node_id, node_kind, project_id,
       client_id, imported_file_count, rejected_file_count, status,
       notes, imported_at
FROM report_bridge_packages
ORDER BY imported_at DESC, package_id
LIMIT 40
""".strip()
        ).fetchall()
        for row in rows:
            cards.append(
                _make_card(
                    board_id=board_id,
                    source_kind="report_bridge_package",
                    source_id=row["package_id"],
                    title=f"Report package: {row['package_id']}",
                    summary=f"{row['package_kind']} from {row['node_id']} ({row['imported_file_count']} files).",
                    world_hint="operations",
                    agent_id="report_bridge",
                    lane_id="node_report_intake",
                    intent_category="report_bridge_request",
                    board_column="completed_with_receipt",
                    status=row["status"],
                    approval_required=False,
                    next_safe_move="Inspect sanitized package summary; no remote control or truth promotion.",
                    evidence_basis="report_bridge_import_metadata",
                )
            )
    if _table_exists(conn, "report_bridge_rejections"):
        rows = conn.execute(
            """
SELECT rejection_id, package_id, package_path, rejection_type,
       rejection_reason, created_at
FROM report_bridge_rejections
ORDER BY created_at DESC, rejection_id
LIMIT 40
""".strip()
        ).fetchall()
        for row in rows:
            source_id = row["package_id"] or row["rejection_id"]
            cards.append(
                _make_card(
                    board_id=board_id,
                    source_kind="report_bridge_package",
                    source_id=f"rejected:{source_id}",
                    title=f"Rejected report package: {source_id}",
                    summary=row["rejection_reason"],
                    world_hint="operations",
                    agent_id="report_bridge",
                    lane_id="node_report_intake",
                    intent_category="report_bridge_request",
                    board_column="rejected",
                    status=row["rejection_type"],
                    blocker_reason=row["rejection_reason"],
                    next_safe_move="Review rejection reason; do not import raw/private package content.",
                    evidence_basis="report_bridge_rejection_metadata",
                    source_path=row["package_path"],
                )
            )
    return cards


def _project_capsule_cards(conn: sqlite3.Connection, board_id: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, "project_capsules"):
        return []
    rows = conn.execute(
        """
SELECT project_id, client_id, project_name, project_goal, owner_scope,
       status, approval_status, runtime_authority, deployment_authority,
       client_data_access, created_at
FROM project_capsules
ORDER BY created_at DESC, project_id
LIMIT 20
""".strip()
    ).fetchall()
    cards = []
    for row in rows:
        column = "planned" if row["status"] == "draft" else "deferred"
        blocker = None
        if row["runtime_authority"] or row["deployment_authority"] or row["client_data_access"]:
            column = "blocked"
            blocker = "Project capsule claims runtime/deployment/client-data authority."
        cards.append(
            _make_card(
                board_id=board_id,
                source_kind="project_capsule",
                source_id=row["project_id"],
                title=f"Project capsule: {row['project_name']}",
                summary=row["project_goal"],
                world_hint="business_development",
                agent_id="chief",
                lane_id="system_orchestration",
                intent_category="project_capsule_request",
                board_column=column,
                status=row["status"],
                approval_required=row["approval_status"] != "approved",
                blocker_reason=blocker,
                next_safe_move="Use capsule as planning context only; no deployment or client-data authority.",
                evidence_basis=f"project_capsule:{row['owner_scope']}:{row['approval_status']}",
            )
        )
    return cards


def _source_cards(conn: sqlite3.Connection, board_id: str) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    cards.extend(_intent_cards(conn, board_id))
    cards.extend(_dropped_intent_cards(conn, board_id))
    cards.extend(_agent_work_packet_cards(conn, board_id))
    cards.extend(_operator_action_cards(conn, board_id))
    cards.extend(_report_bridge_cards(conn, board_id))
    cards.extend(_project_capsule_cards(conn, board_id))
    return cards


def _replace_card_children(conn: sqlite3.Connection, *, card_id: str) -> None:
    for table in (
        "work_board_card_sources",
        "work_board_card_agents",
        "work_board_card_worlds",
        "work_board_card_dependencies",
        "work_board_card_blockers",
        "work_board_card_receipts",
    ):
        conn.execute(f"DELETE FROM {table} WHERE card_id = ?", (card_id,))


def _upsert_card(conn: sqlite3.Connection, *, card: dict[str, Any], run_id: str, now: str) -> None:
    existing = conn.execute(
        "SELECT board_column, status, created_at FROM work_board_cards WHERE card_id = ?",
        (card["card_id"],),
    ).fetchone()
    created_at = existing["created_at"] if existing else now
    previous_column = existing["board_column"] if existing else None
    conn.execute(
        """
INSERT INTO work_board_cards (
  card_id, board_id, title, summary, source_kind, source_id, world_hint,
  agent_id, lane_id, intent_category, board_column, status, priority_hint,
  approval_required, execution_allowed, action_request_id, work_packet_id,
  receipt_id, blocker_reason, next_safe_move, evidence_basis, created_at,
  updated_at, raw_body_stored, direct_execution_allowed, arbitrary_shell_allowed,
  auto_approval_allowed, auto_execute_allowed, agent_activation_allowed,
  model_call_allowed, tool_execution_allowed, network_authority,
  no_go_raw_access_allowed, file_move_allowed, file_delete_allowed,
  client_deployment_allowed
) VALUES (
  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
)
ON CONFLICT(card_id) DO UPDATE SET
  title = excluded.title,
  summary = excluded.summary,
  world_hint = excluded.world_hint,
  agent_id = excluded.agent_id,
  lane_id = excluded.lane_id,
  intent_category = excluded.intent_category,
  board_column = excluded.board_column,
  status = excluded.status,
  priority_hint = excluded.priority_hint,
  approval_required = excluded.approval_required,
  execution_allowed = 0,
  action_request_id = excluded.action_request_id,
  work_packet_id = excluded.work_packet_id,
  receipt_id = excluded.receipt_id,
  blocker_reason = excluded.blocker_reason,
  next_safe_move = excluded.next_safe_move,
  evidence_basis = excluded.evidence_basis,
  updated_at = excluded.updated_at,
  raw_body_stored = 0,
  direct_execution_allowed = 0,
  arbitrary_shell_allowed = 0,
  auto_approval_allowed = 0,
  auto_execute_allowed = 0,
  agent_activation_allowed = 0,
  model_call_allowed = 0,
  tool_execution_allowed = 0,
  network_authority = 0,
  no_go_raw_access_allowed = 0,
  file_move_allowed = 0,
  file_delete_allowed = 0,
  client_deployment_allowed = 0
""".strip(),
        (
            card["card_id"],
            card["board_id"],
            card["title"],
            card["summary"],
            card["source_kind"],
            card["source_id"],
            card["world_hint"],
            card["agent_id"],
            card["lane_id"],
            card["intent_category"],
            card["board_column"],
            card["status"],
            card["priority_hint"],
            1 if card["approval_required"] else 0,
            card["action_request_id"],
            card["work_packet_id"],
            card["receipt_id"],
            card["blocker_reason"],
            card["next_safe_move"],
            card["evidence_basis"],
            created_at,
            now,
        ),
    )
    _replace_card_children(conn, card_id=card["card_id"])
    conn.execute(
        """
INSERT INTO work_board_card_sources (
  card_source_id, card_id, source_kind, source_id, source_path,
  source_summary, raw_body_stored, created_at
) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
""".strip(),
        (
            _row_id("wbsrc", card["card_id"], card["source_kind"], card["source_id"]),
            card["card_id"],
            card["source_kind"],
            card["source_id"],
            card.get("source_path"),
            card["summary"],
            now,
        ),
    )
    if card["agent_id"]:
        conn.execute(
            """
INSERT INTO work_board_card_agents (
  card_agent_id, card_id, agent_id, lane_id, role,
  can_execute, can_bypass_approval, created_at
) VALUES (?, ?, ?, ?, 'assigned_lane', 0, 0, ?)
""".strip(),
            (_row_id("wbagent", card["card_id"], card["agent_id"]), card["card_id"], card["agent_id"], card["lane_id"], now),
        )
    conn.execute(
        """
INSERT INTO work_board_card_worlds (
  card_world_id, card_id, world_hint, confidence, created_at
) VALUES (?, ?, ?, 'metadata_hint', ?)
""".strip(),
        (_row_id("wbworld", card["card_id"], card["world_hint"]), card["card_id"], card["world_hint"], now),
    )
    if card["approval_required"]:
        conn.execute(
            """
INSERT INTO work_board_card_dependencies (
  dependency_id, card_id, dependency_kind, dependency_ref,
  dependency_status, created_at
) VALUES (?, ?, 'approval_gate', 'operator_approval', 'required_before_action', ?)
""".strip(),
            (_row_id("wbdep", card["card_id"], "approval_gate"), card["card_id"], now),
        )
    if card["blocker_reason"]:
        conn.execute(
            """
INSERT INTO work_board_card_blockers (
  blocker_id, card_id, blocker_reason, blocker_status, created_at
) VALUES (?, ?, ?, 'open', ?)
""".strip(),
            (_row_id("wbblock", card["card_id"], card["blocker_reason"]), card["card_id"], card["blocker_reason"], now),
        )
    if card["receipt_id"]:
        conn.execute(
            """
INSERT INTO work_board_card_receipts (
  card_receipt_id, card_id, receipt_kind, source_receipt_id,
  summary, created_at, execution_allowed, auto_approval_allowed
) VALUES (?, ?, 'source_receipt_link', ?, ?, ?, 0, 0)
""".strip(),
            (
                _row_id("wbreceipt", card["card_id"], card["receipt_id"]),
                card["card_id"],
                card["receipt_id"],
                "Linked source receipt; board did not execute anything.",
                now,
            ),
        )
    history_id = _row_id("wbhist", card["card_id"], card["board_column"], card["status"])
    conn.execute(
        """
INSERT OR IGNORE INTO work_board_card_status_history (
  history_id, card_id, previous_column, board_column, status,
  changed_by, change_reason, changed_at, execution_allowed,
  approval_bypass_allowed
) VALUES (?, ?, ?, ?, ?, 'work_board_builder', ?, ?, 0, 0)
""".strip(),
        (
            history_id,
            card["card_id"],
            previous_column,
            card["board_column"],
            card["status"],
            f"Projected from {card['source_kind']}:{card['source_id']} during {run_id}.",
            now,
        ),
    )


def build_work_board(
    *,
    db_path: str | Path | None = None,
    board_id: str = DEFAULT_BOARD_ID,
    run_id: str | None = None,
) -> WorkBoardBuildResult:
    path = init_work_board_schema(db_path)
    now = utc_now()
    resolved_run_id = run_id or _row_id("wbrun", board_id, now)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        _ensure_board(conn, board_id=board_id, now=now)
        _insert_run(conn, run_id=resolved_run_id, board_id=board_id, now=now)
        cards = _source_cards(conn, board_id)
        for card in cards:
            _upsert_card(conn, card=card, run_id=resolved_run_id, now=now)
        counts = Counter(card["board_column"] for card in cards)
        conn.execute(
            "UPDATE work_board_runs SET card_count = ?, completed_at = ? WHERE run_id = ?",
            (len(cards), now, resolved_run_id),
        )
        conn.commit()
        return WorkBoardBuildResult(
            run_id=resolved_run_id,
            db_path=path,
            board_id=board_id,
            card_count=len(cards),
            counts_by_column=dict(sorted(counts.items())),
        )
    finally:
        conn.close()


REPORT_SECTIONS = {
    "summary",
    "cards",
    "needs-review",
    "pending-approval",
    "blocked",
    "completed",
}


def _card_summary(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {
        "card_id": row["card_id"],
        "board_id": row["board_id"],
        "title": row["title"],
        "summary": row["summary"],
        "source_kind": row["source_kind"],
        "source_id": row["source_id"],
        "world_hint": row["world_hint"],
        "agent_id": row["agent_id"],
        "lane_id": row["lane_id"],
        "intent_category": row["intent_category"],
        "board_column": row["board_column"],
        "status": row["status"],
        "priority_hint": row["priority_hint"],
        "approval_required": bool(row["approval_required"]),
        "execution_allowed": bool(row["execution_allowed"]),
        "action_request_id": row["action_request_id"],
        "work_packet_id": row["work_packet_id"],
        "receipt_id": row["receipt_id"],
        "blocker_reason": row["blocker_reason"],
        "next_safe_move": row["next_safe_move"],
        "updated_at": row["updated_at"],
    }


def build_work_board_report(
    *,
    db_path: str | Path | None = None,
    board_id: str = DEFAULT_BOARD_ID,
    report: str = "summary",
    agent: str | None = None,
    world: str | None = None,
    column: str | None = None,
) -> dict[str, Any]:
    if report not in REPORT_SECTIONS:
        raise ValueError(f"unknown work board report: {report}")
    if column and column not in BOARD_COLUMNS:
        raise ValueError(f"unsupported board column: {column}")
    path = init_work_board_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        clauses = ["board_id = ?"]
        params: list[Any] = [board_id]
        report_column_map = {
            "needs-review": "needs_review",
            "pending-approval": "pending_approval",
            "blocked": "blocked",
            "completed": "completed_with_receipt",
        }
        resolved_column = column or report_column_map.get(report)
        if resolved_column:
            clauses.append("board_column = ?")
            params.append(resolved_column)
        if agent:
            clauses.append("agent_id = ?")
            params.append(agent)
        if world:
            clauses.append("world_hint = ?")
            params.append(world)
        where = " AND ".join(clauses)
        rows = conn.execute(
            f"""
SELECT *
FROM work_board_cards
WHERE {where}
ORDER BY
  CASE priority_hint WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 WHEN 'low' THEN 3 ELSE 4 END,
  updated_at DESC,
  card_id
LIMIT 200
""".strip(),
            tuple(params),
        ).fetchall()
        all_rows = conn.execute(
            "SELECT * FROM work_board_cards WHERE board_id = ?",
            (board_id,),
        ).fetchall()
        column_counts = Counter(row["board_column"] for row in all_rows)
        agent_counts = Counter((row["agent_id"] or "unassigned") for row in all_rows)
        world_counts = Counter(row["world_hint"] for row in all_rows)
        latest_cards = sorted(all_rows, key=lambda row: (row["updated_at"], row["card_id"]), reverse=True)[:10]
        conn.execute(
            """
INSERT OR REPLACE INTO work_board_query_receipts (
  query_receipt_id, board_id, report, card_count,
  raw_body_stored, execution_allowed, created_at
) VALUES (?, ?, ?, ?, 0, 0, ?)
""".strip(),
            (_row_id("wbquery", board_id, report, agent or "", world or "", column or "", utc_now()), board_id, report, len(rows), utc_now()),
        )
        conn.commit()
        return {
            "status": "ok",
            "report": report,
            "db_path": str(path),
            "board_id": board_id,
            "card_count": len(all_rows),
            "filtered_card_count": len(rows),
            "counts_by_column": dict(sorted(column_counts.items())),
            "counts_by_agent": dict(sorted(agent_counts.items())),
            "counts_by_world": dict(sorted(world_counts.items())),
            "needs_review_count": column_counts.get("needs_review", 0),
            "pending_approval_count": column_counts.get("pending_approval", 0),
            "blocked_count": column_counts.get("blocked", 0),
            "completed_with_receipt_count": column_counts.get("completed_with_receipt", 0),
            "cards": [_card_summary(row) for row in rows],
            "latest_cards": [_card_summary(row) for row in latest_cards],
            "top_next_safe_moves": [
                row["next_safe_move"] for row in all_rows if row["board_column"] in {"needs_review", "pending_approval", "blocked"}
            ][:10],
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def _counts_line(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def format_work_board_report(payload: dict[str, Any]) -> str:
    lines = [
        f"OpenClaw Work Board v0 - {payload['report']}",
        "",
        f"Cards: {payload['card_count']}",
        f"Filtered cards: {payload['filtered_card_count']}",
        f"By column: {_counts_line(payload['counts_by_column'])}",
        f"By agent: {_counts_line(payload['counts_by_agent'])}",
        f"By world: {_counts_line(payload['counts_by_world'])}",
        f"Needs review: {payload['needs_review_count']}",
        f"Pending approval: {payload['pending_approval_count']}",
        f"Blocked: {payload['blocked_count']}",
        f"Completed with receipt: {payload['completed_with_receipt_count']}",
        "",
        "Cards:",
    ]
    for item in payload.get("cards") or []:
        lines.append(
            f"- `{item['card_id']}` {item['board_column']} {item['source_kind']}:{item['source_id']} "
            f"agent={item['agent_id'] or 'unassigned'} title={item['title']}"
        )
    if not payload.get("cards"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Board cards are metadata only; no execution, approvals, agent activation, model calls, or file operations.",
        ]
    )
    return "\n".join(lines)


def _has_action_receipt(conn: sqlite3.Connection, action_id: str | None) -> bool:
    if not action_id:
        return False
    row = conn.execute(
        "SELECT 1 FROM operator_action_receipts WHERE action_id = ? LIMIT 1",
        (action_id,),
    ).fetchone()
    return row is not None


def _has_action_execution(conn: sqlite3.Connection, action_id: str | None) -> bool:
    if not action_id:
        return False
    row = conn.execute(
        "SELECT 1 FROM operator_action_executions WHERE action_id = ? LIMIT 1",
        (action_id,),
    ).fetchone()
    return row is not None


def _has_action_approval(conn: sqlite3.Connection, action_id: str | None) -> bool:
    if not action_id:
        return False
    row = conn.execute(
        "SELECT 1 FROM operator_action_approvals WHERE action_id = ? AND approval_status = 'approved' LIMIT 1",
        (action_id,),
    ).fetchone()
    return row is not None


def _validate_transition(
    conn: sqlite3.Connection,
    *,
    row: sqlite3.Row,
    target_column: str,
    metadata_only: bool,
) -> None:
    current = row["board_column"]
    if target_column == current:
        return
    if target_column not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"unsupported board transition: {current} -> {target_column}")
    action_id = row["action_request_id"]
    if target_column == "approved" and not (metadata_only or _has_action_approval(conn, action_id)):
        raise ValueError("approved transition requires linked approval or explicit metadata-only update")
    if target_column == "in_progress" and not _has_action_execution(conn, action_id):
        raise ValueError("in_progress transition requires linked execution metadata")
    if target_column == "completed_with_receipt" and not (row["receipt_id"] or _has_action_receipt(conn, action_id)):
        raise ValueError("completed_with_receipt transition requires a linked receipt")


def update_work_board_card(
    *,
    db_path: str | Path | None = None,
    card_id: str,
    board_column: str | None = None,
    status: str | None = None,
    blocker_reason: str | None = None,
    changed_by: str = "operator",
    change_reason: str = "metadata_only_update",
    metadata_only: bool = False,
) -> WorkBoardUpdateResult:
    if not card_id:
        raise ValueError("card_id is required")
    if board_column and board_column not in BOARD_COLUMNS:
        raise ValueError(f"unsupported board_column: {board_column}")
    path = init_work_board_schema(db_path)
    now = utc_now()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM work_board_cards WHERE card_id = ?", (card_id,)).fetchone()
        if not row:
            raise ValueError(f"unknown work board card: {card_id}")
        previous_column = row["board_column"]
        target_column = board_column or ("blocked" if blocker_reason else previous_column)
        if blocker_reason:
            target_column = "blocked"
            status = status or "blocked"
        _validate_transition(conn, row=row, target_column=target_column, metadata_only=metadata_only)
        target_status = status or target_column
        conn.execute(
            """
UPDATE work_board_cards
SET board_column = ?, status = ?, blocker_reason = COALESCE(?, blocker_reason),
    updated_at = ?, execution_allowed = 0, direct_execution_allowed = 0,
    arbitrary_shell_allowed = 0, auto_approval_allowed = 0,
    auto_execute_allowed = 0, agent_activation_allowed = 0,
    model_call_allowed = 0, tool_execution_allowed = 0,
    network_authority = 0, no_go_raw_access_allowed = 0,
    file_move_allowed = 0, file_delete_allowed = 0,
    client_deployment_allowed = 0
WHERE card_id = ?
""".strip(),
            (target_column, target_status, blocker_reason, now, card_id),
        )
        if blocker_reason:
            conn.execute(
                """
INSERT INTO work_board_card_blockers (
  blocker_id, card_id, blocker_reason, blocker_status, created_at
) VALUES (?, ?, ?, 'open', ?)
ON CONFLICT(blocker_id) DO UPDATE SET blocker_reason = excluded.blocker_reason
""".strip(),
                (_row_id("wbblock", card_id, blocker_reason), card_id, blocker_reason, now),
            )
        conn.execute(
            """
INSERT INTO work_board_card_status_history (
  history_id, card_id, previous_column, board_column, status,
  changed_by, change_reason, changed_at, execution_allowed,
  approval_bypass_allowed
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
""".strip(),
            (
                _row_id("wbhist", card_id, target_column, target_status, now, changed_by),
                card_id,
                previous_column,
                target_column,
                target_status,
                changed_by,
                change_reason,
                now,
            ),
        )
        conn.commit()
        return WorkBoardUpdateResult(
            card_id=card_id,
            board_id=row["board_id"],
            previous_column=previous_column,
            board_column=target_column,
            status=target_status,
            updated=target_column != previous_column or bool(status),
            blocker_added=bool(blocker_reason),
        )
    finally:
        conn.close()


def build_work_board_read_model(
    *,
    db_path: str | Path | None = None,
    board_id: str = DEFAULT_BOARD_ID,
) -> dict[str, Any]:
    report = build_work_board_report(db_path=db_path, board_id=board_id, report="summary")
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "mode": "local_work_board_control_plane_metadata_only",
        "generated_at": utc_now(),
        "source_ledger_path": _display_path(report["db_path"]),
        "source_ledger_namespace": "work_board_*",
        "board_count": 1,
        "board_id": board_id,
        "card_count": report["card_count"],
        "counts_by_column": report["counts_by_column"],
        "counts_by_agent": report["counts_by_agent"],
        "counts_by_world": report["counts_by_world"],
        "needs_review_count": report["needs_review_count"],
        "pending_approval_count": report["pending_approval_count"],
        "blocked_count": report["blocked_count"],
        "completed_with_receipt_count": report["completed_with_receipt_count"],
        "latest_cards": report["latest_cards"],
        "top_next_safe_moves": report["top_next_safe_moves"],
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_work_board_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Work Board Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over local `work_board_*` control-plane cards.",
        "",
        "What this is not:",
        "- It is not execution, approval, agent activation, model calling, external API access, or file operations.",
        "",
        "Summary:",
        f"- Boards: {read_model['board_count']}.",
        f"- Cards: {read_model['card_count']}.",
        f"- By column: {_counts_line(read_model['counts_by_column'])}.",
        f"- By agent: {_counts_line(read_model['counts_by_agent'])}.",
        f"- Needs review: {read_model['needs_review_count']}.",
        f"- Pending approval: {read_model['pending_approval_count']}.",
        f"- Blocked: {read_model['blocked_count']}.",
        f"- Completed with receipt: {read_model['completed_with_receipt_count']}.",
        "",
        "Latest cards:",
    ]
    for card in read_model.get("latest_cards") or []:
        lines.append(
            f"- `{card['card_id']}` {card['board_column']} {card['source_kind']}:{card['source_id']} - {card['title']}"
        )
    if not read_model.get("latest_cards"):
        lines.append("- None.")
    lines.extend(["", "Top next safe moves:"])
    for move in read_model.get("top_next_safe_moves") or []:
        lines.append(f"- {move}")
    if not read_model.get("top_next_safe_moves"):
        lines.append("- None.")
    lines.extend(["", "Authority boundary:"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`.")
    return "\n".join(lines) + "\n"


def export_work_board_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    board_id: str = DEFAULT_BOARD_ID,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_work_board_read_model(db_path=db_path, board_id=board_id)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_work_board_read_model(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "board_id": board_id,
        "card_count": read_model["card_count"],
        "counts_by_column": read_model["counts_by_column"],
        **NO_AUTHORITY_FLAGS,
    }


def format_build_result(result: WorkBoardBuildResult) -> str:
    return "\n".join(
        [
            "OpenClaw Work Board v0",
            "",
            f"Board: `{result.board_id}`",
            f"Run: `{result.run_id}`",
            f"Cards: {result.card_count}",
            f"By column: {_counts_line(result.counts_by_column)}",
            "",
            "Boundary:",
            "- Board build projected safe metadata only; no action was created, approved, or executed.",
        ]
    )


def format_update_result(result: WorkBoardUpdateResult) -> str:
    return "\n".join(
        [
            "OpenClaw Work Board Card Update v0",
            "",
            f"Card: `{result.card_id}`",
            f"Board: `{result.board_id}`",
            f"Column: `{result.previous_column}` -> `{result.board_column}`",
            f"Status: `{result.status}`",
            f"Updated: `{str(result.updated).lower()}`",
            f"Blocker added: `{str(result.blocker_added).lower()}`",
            "",
            "Boundary:",
            "- Metadata-only update; no execution, approval, action creation, or file operation occurred.",
        ]
    )


__all__ = [
    "BOARD_COLUMNS",
    "DEFAULT_BOARD_ID",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_VERSION",
    "REPORT_SECTIONS",
    "WORK_BOARD_VERSION",
    "WorkBoardBuildResult",
    "WorkBoardUpdateResult",
    "build_work_board",
    "build_work_board_read_model",
    "build_work_board_report",
    "export_work_board_read_model",
    "format_build_result",
    "format_update_result",
    "format_work_board_read_model",
    "format_work_board_report",
    "init_work_board_schema",
    "stable_json",
    "update_work_board_card",
    "work_board_table_names",
]
