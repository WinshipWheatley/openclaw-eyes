"""Telegram Agent Intake v0 for OpenClaw.

This module provides governed storage for Telegram-facing operator updates. It
does not call Telegram APIs, send messages, start listeners, inspect secrets, or
execute commands. It stores bounded metadata in SQLite, links operator-authored
updates to Intent Router records, and exports a read-model for readiness.
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

from agent_presence import init_agent_presence_schema
from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger
from intent_router import init_intent_router_schema, route_operator_intent
from operator_action_inbox import init_operator_action_inbox_schema
from work_board import DEFAULT_BOARD_ID, init_work_board_schema


ROOT = Path(__file__).resolve().parent
TELEGRAM_INTAKE_VERSION = "telegram_agent_intake_v0"
READ_MODEL_VERSION = "telegram_agent_intake_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "telegram_agent_intake.json"
OPERATOR_EXPORT_NAME = "telegram_agent_intake_OPERATOR.md"

CORE_AGENTS = ("chief", "cassandra", "guardian", "niles", "hermes")

AGENT_METADATA = {
    "chief": {
        "display_name": "Chief",
        "outward_name": "Chief",
        "lane_id": "system_orchestration",
        "source_channel": "chief_listener",
        "telegram_surface": "chief_listener.py",
        "service_surface": "systemd/user/chief-listener.service.in",
        "listener_hook_status": "governed_hook_added",
        "notes": "Chief listener can record operator text through governed intake, but runtime presence is separate.",
    },
    "cassandra": {
        "display_name": "Cassandra",
        "outward_name": "Clara Reid",
        "lane_id": "operator_comms",
        "source_channel": "cassandra_listener",
        "telegram_surface": "cassandra_listener.py",
        "service_surface": "systemd/user/cassandra-listener.service.in",
        "listener_hook_status": "governed_hook_added",
        "notes": "Internal agent is Cassandra; outward-facing identity is Clara Reid.",
    },
    "guardian": {
        "display_name": "Guardian",
        "outward_name": "Guardian",
        "lane_id": "safety_security",
        "source_channel": "guardian_listener",
        "telegram_surface": "chief_guardian_listener.py",
        "service_surface": "systemd/user/chief-guardian-listener.service.in",
        "listener_hook_status": "governed_hook_added",
        "notes": "Guardian Telegram surface is approval/safety oriented, not a general execution lane.",
    },
    "niles": {
        "display_name": "Niles",
        "outward_name": "Niles Mercer",
        "lane_id": "music_art_production",
        "source_channel": "niles_producer_listener",
        "telegram_surface": "producer_listener.py",
        "service_surface": "scripts/run_producer_listener.sh",
        "listener_hook_status": "governed_hook_added",
        "notes": "Producer is treated as a Niles alias until a later lane separates authority.",
    },
    "hermes": {
        "display_name": "Hermes",
        "outward_name": "Hermes",
        "lane_id": "advisory_synthesis",
        "source_channel": "hermes_gateway",
        "telegram_surface": None,
        "service_surface": "systemd/user/hermes-gateway.service.in",
        "listener_hook_status": "no_telegram_listener_found",
        "notes": "Hermes gateway exists, but no current repo Telegram listener file was found.",
    },
}

NO_AUTHORITY_FLAGS = {
    "telegram_send_allowed": False,
    "command_execution_allowed": False,
    "action_auto_execute_allowed": False,
    "approval_bypass_allowed": False,
    "raw_payload_storage_allowed": False,
    "token_exposure_allowed": False,
    "external_api_send_allowed": False,
    "agent_activation_allowed": False,
    "runtime_activation_allowed": False,
    "arbitrary_shell_allowed": False,
}

REPORT_SECTIONS = {"summary", "agents", "latest", "blockers", "dry-run", "cassandra-live"}


@dataclass(frozen=True)
class TelegramIntakeResult:
    update_record_id: str
    run_id: str
    db_path: str
    agent_target: str
    source_channel: str
    routed_to_intent_inbox: bool
    intent_record_id: str | None
    route_status: str | None
    routed_agent_id: str | None
    routed_lane_id: str | None
    work_board_card_id: str | None
    raw_payload_stored: bool
    message_text_stored: bool
    telegram_send_allowed: bool
    command_execution_allowed: bool


@dataclass(frozen=True)
class TelegramIntakeCheckResult:
    run_id: str
    db_path: str
    governed_storage_available: bool
    dry_run_update_id: str
    dry_run_intent_id: str | None
    dry_run_status: str | None
    agent_count: int
    receive_ready_count: int
    blocker_count: int
    telegram_send_allowed: bool


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


def _message_hash(text: str) -> str:
    return hashlib.sha256(("telegram-agent-intake-v0:" + text).encode("utf-8")).hexdigest()


def _excerpt(text: str, limit: int = 180) -> str:
    clean = " ".join((text or "").replace("\x00", " ").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS telegram_agent_intake_runs (
  run_id TEXT PRIMARY KEY,
  intake_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  update_count INTEGER NOT NULL DEFAULT 0,
  routed_count INTEGER NOT NULL DEFAULT 0,
  dry_run_proof_count INTEGER NOT NULL DEFAULT 0,
  governed_storage_available INTEGER NOT NULL DEFAULT 1,
  telegram_send_allowed INTEGER NOT NULL DEFAULT 0,
  command_execution_allowed INTEGER NOT NULL DEFAULT 0,
  action_auto_execute_allowed INTEGER NOT NULL DEFAULT 0,
  approval_bypass_allowed INTEGER NOT NULL DEFAULT 0,
  raw_payload_storage_allowed INTEGER NOT NULL DEFAULT 0,
  token_exposure_allowed INTEGER NOT NULL DEFAULT 0,
  external_api_send_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS telegram_agent_update_records (
  update_record_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'telegram',
  source_channel TEXT NOT NULL,
  source_message_id TEXT,
  source_message_id_stored INTEGER NOT NULL DEFAULT 1,
  agent_target TEXT NOT NULL,
  operator_message INTEGER NOT NULL DEFAULT 0,
  message_text_stored INTEGER NOT NULL DEFAULT 0,
  message_text_hash TEXT NOT NULL,
  message_text_excerpt TEXT,
  raw_payload_stored INTEGER NOT NULL DEFAULT 0,
  chat_id_stored INTEGER NOT NULL DEFAULT 0,
  chat_id_redacted INTEGER NOT NULL DEFAULT 1,
  received_at TEXT NOT NULL,
  routed_to_intent_inbox INTEGER NOT NULL DEFAULT 0,
  intent_record_id TEXT,
  work_board_card_id TEXT,
  blocked_reason TEXT,
  created_at TEXT NOT NULL,
  telegram_send_allowed INTEGER NOT NULL DEFAULT 0,
  command_execution_allowed INTEGER NOT NULL DEFAULT 0,
  action_auto_execute_allowed INTEGER NOT NULL DEFAULT 0,
  approval_bypass_allowed INTEGER NOT NULL DEFAULT 0,
  raw_payload_storage_allowed INTEGER NOT NULL DEFAULT 0,
  token_exposure_allowed INTEGER NOT NULL DEFAULT 0,
  external_api_send_allowed INTEGER NOT NULL DEFAULT 0
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS telegram_agent_intent_links (
  link_id TEXT PRIMARY KEY,
  update_record_id TEXT NOT NULL,
  intent_record_id TEXT NOT NULL,
  link_kind TEXT NOT NULL,
  created_at TEXT NOT NULL,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (update_record_id) REFERENCES telegram_agent_update_records(update_record_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS telegram_agent_route_results (
  route_result_id TEXT PRIMARY KEY,
  update_record_id TEXT NOT NULL,
  intent_record_id TEXT,
  routed_agent_id TEXT,
  routed_lane_id TEXT,
  intent_category TEXT,
  status TEXT NOT NULL,
  confidence REAL,
  next_safe_move TEXT NOT NULL,
  created_at TEXT NOT NULL,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  approval_bypass_allowed INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (update_record_id) REFERENCES telegram_agent_update_records(update_record_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS telegram_agent_storage_receipts (
  receipt_id TEXT PRIMARY KEY,
  update_record_id TEXT NOT NULL,
  intent_record_id TEXT,
  summary TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  raw_payload_stored INTEGER NOT NULL DEFAULT 0,
  message_text_stored INTEGER NOT NULL DEFAULT 0,
  command_execution_allowed INTEGER NOT NULL DEFAULT 0,
  telegram_send_allowed INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (update_record_id) REFERENCES telegram_agent_update_records(update_record_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS telegram_agent_blockers (
  blocker_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  blocker_kind TEXT NOT NULL,
  blocker_reason TEXT NOT NULL,
  next_safe_move TEXT NOT NULL,
  created_at TEXT NOT NULL,
  resolved INTEGER NOT NULL DEFAULT 0
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_telegram_agent_updates_run ON telegram_agent_update_records(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_telegram_agent_updates_agent ON telegram_agent_update_records(agent_target)",
        "CREATE INDEX IF NOT EXISTS idx_telegram_agent_routes_status ON telegram_agent_route_results(status)",
    )


def init_telegram_agent_intake_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    init_business_ops_ledger(path)
    init_operator_action_inbox_schema(path)
    init_intent_router_schema(path)
    init_agent_presence_schema(path)
    init_work_board_schema(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def telegram_agent_intake_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_telegram_agent_intake_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name FROM sqlite_master
WHERE type = 'table' AND name LIKE 'telegram_agent_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _insert_run(conn: sqlite3.Connection, *, run_id: str, now: str) -> None:
    conn.execute(
        """
INSERT INTO telegram_agent_intake_runs (
  run_id, intake_version, created_at, notes
) VALUES (?, ?, ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
  intake_version = excluded.intake_version,
  telegram_send_allowed = 0,
  command_execution_allowed = 0,
  action_auto_execute_allowed = 0,
  approval_bypass_allowed = 0,
  raw_payload_storage_allowed = 0,
  token_exposure_allowed = 0,
  external_api_send_allowed = 0,
  notes = excluded.notes
""".strip(),
        (
            run_id,
            TELEGRAM_INTAKE_VERSION,
            now,
            "Governed Telegram intake metadata only; no Telegram send, command execution, approval bypass, or raw payload storage.",
        ),
    )


def _agent_from_text_or_channel(text: str, source_channel: str, agent_target: str | None) -> str:
    if agent_target and agent_target in AGENT_METADATA:
        return agent_target
    lowered = f"{source_channel} {text}".lower()
    if "clara" in lowered or "cassandra" in lowered:
        return "cassandra"
    if "guardian" in lowered:
        return "guardian"
    if "niles" in lowered or "producer" in lowered:
        return "niles"
    if "hermes" in lowered:
        return "hermes"
    if "chief" in lowered:
        return "chief"
    if "cassandra" in source_channel:
        return "cassandra"
    if "guardian" in source_channel:
        return "guardian"
    if "producer" in source_channel or "niles" in source_channel:
        return "niles"
    if "hermes" in source_channel:
        return "hermes"
    if "chief" in source_channel:
        return "chief"
    return "unknown"


def _route_text(text: str, agent_target: str) -> str:
    lowered = text.lower()
    explicit_tokens = ("chief", "cassandra", "clara", "guardian", "niles", "producer", "hermes", "report bridge")
    if any(token in lowered for token in explicit_tokens):
        return text
    prefix = {
        "chief": "Chief",
        "cassandra": "Cassandra",
        "guardian": "Guardian",
        "niles": "Niles",
        "hermes": "Hermes",
    }.get(agent_target)
    if prefix:
        return f"{prefix}, {text}"
    return text


def _insert_or_update_work_board_card(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    title: str,
    summary: str,
    agent_id: str,
    lane_id: str,
    board_column: str,
    status: str,
    next_safe_move: str,
    now: str,
) -> str:
    board_id = DEFAULT_BOARD_ID
    card_id = _row_id("wbcard", board_id, "manual_seed", source_id)
    conn.execute(
        """
INSERT INTO work_boards (
  board_id, board_name, board_version, description, created_at, updated_at,
  direct_execution_allowed, auto_approval_allowed, auto_execute_allowed,
  agent_activation_allowed
) VALUES (?, 'OpenClaw Work Board', 'openclaw_work_board_v0', ?, ?, ?, 0, 0, 0, 0)
ON CONFLICT(board_id) DO UPDATE SET updated_at = excluded.updated_at
""".strip(),
        (board_id, "Local review board over OpenClaw control-plane metadata, including Telegram intake readiness.", now, now),
    )
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
) VALUES (?, ?, ?, ?, 'manual_seed', ?, 'operations', ?, ?, 'telegram_agent_intake',
  ?, ?, 'high', 1, 0, NULL, NULL, NULL, NULL, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
ON CONFLICT(board_id, source_kind, source_id) DO UPDATE SET
  title = excluded.title,
  summary = excluded.summary,
  agent_id = excluded.agent_id,
  lane_id = excluded.lane_id,
  board_column = excluded.board_column,
  status = excluded.status,
  approval_required = 1,
  execution_allowed = 0,
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
            card_id,
            board_id,
            title,
            summary,
            source_id,
            agent_id,
            lane_id,
            board_column,
            status,
            next_safe_move,
            "telegram_agent_intake_readiness",
            now,
            now,
        ),
    )
    conn.execute(
        """
INSERT OR REPLACE INTO work_board_card_sources (
  card_source_id, card_id, source_kind, source_id, source_path,
  source_summary, raw_body_stored, created_at
) VALUES (?, ?, 'manual_seed', ?, NULL, ?, 0, ?)
""".strip(),
        (_row_id("wbsrc", card_id, source_id), card_id, source_id, summary, now),
    )
    return card_id


def record_telegram_update(
    *,
    text: str,
    source_channel: str,
    agent_target: str | None = None,
    source_message_id: str | None = None,
    source_user_label: str | None = "operator",
    operator_message: bool = True,
    received_at: str | None = None,
    route_intent: bool = True,
    create_work_board_card: bool = False,
    db_path: str | Path | None = None,
    run_id: str | None = None,
) -> TelegramIntakeResult:
    if not text or not text.strip():
        raise ValueError("telegram message text is required")
    if not source_channel or not source_channel.strip():
        raise ValueError("source_channel is required")

    path = init_telegram_agent_intake_schema(db_path)
    now = utc_now()
    resolved_received_at = received_at or now
    resolved_agent = _agent_from_text_or_channel(text, source_channel, agent_target)
    msg_hash = _message_hash(text)
    resolved_run_id = run_id or _row_id("tgintakerun", source_channel, resolved_agent, msg_hash, now)
    update_record_id = _row_id("tgupdate", source_channel, source_message_id or "", resolved_agent, msg_hash, resolved_received_at)
    intent_id: str | None = None
    route_status: str | None = None
    routed_agent_id: str | None = None
    routed_lane_id: str | None = None
    route_category: str | None = None
    route_confidence: float | None = None
    next_safe_move = "Message stored as governed Telegram intake metadata; no execution or external send is authorized."
    blocked_reason: str | None = None
    work_board_card_id: str | None = None

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        _insert_run(conn, run_id=resolved_run_id, now=now)
        conn.execute(
            """
INSERT INTO telegram_agent_update_records (
  update_record_id, run_id, source, source_channel, source_message_id,
  source_message_id_stored, agent_target, operator_message,
  message_text_stored, message_text_hash, message_text_excerpt,
  raw_payload_stored, chat_id_stored, chat_id_redacted, received_at,
  routed_to_intent_inbox, intent_record_id, work_board_card_id,
  blocked_reason, created_at, telegram_send_allowed, command_execution_allowed,
  action_auto_execute_allowed, approval_bypass_allowed,
  raw_payload_storage_allowed, token_exposure_allowed, external_api_send_allowed
) VALUES (?, ?, 'telegram', ?, ?, 1, ?, ?, 0, ?, ?, 0, 0, 1, ?, 0, NULL, NULL, NULL, ?, 0, 0, 0, 0, 0, 0, 0)
ON CONFLICT(update_record_id) DO UPDATE SET
  run_id = excluded.run_id,
  source_channel = excluded.source_channel,
  source_message_id = excluded.source_message_id,
  agent_target = excluded.agent_target,
  operator_message = excluded.operator_message,
  message_text_stored = 0,
  message_text_hash = excluded.message_text_hash,
  message_text_excerpt = excluded.message_text_excerpt,
  raw_payload_stored = 0,
  chat_id_stored = 0,
  chat_id_redacted = 1,
  received_at = excluded.received_at,
  telegram_send_allowed = 0,
  command_execution_allowed = 0,
  action_auto_execute_allowed = 0,
  approval_bypass_allowed = 0,
  raw_payload_storage_allowed = 0,
  token_exposure_allowed = 0,
  external_api_send_allowed = 0
""".strip(),
            (
                update_record_id,
                resolved_run_id,
                source_channel.strip(),
                source_message_id,
                resolved_agent,
                1 if operator_message else 0,
                msg_hash,
                _excerpt(text),
                resolved_received_at,
                now,
            ),
        )
        conn.commit()
        if route_intent and operator_message:
            try:
                route_result = route_operator_intent(
                    text=_route_text(text, resolved_agent),
                    source_kind="telegram",
                    source_channel=source_channel.strip(),
                    source_message_id=source_message_id,
                    source_user_label=source_user_label or "operator",
                    requested_by="operator",
                    db_path=path,
                    intent_id=_row_id("intent", "telegram", source_channel, update_record_id),
                    run_id=_row_id("irun", "telegram", source_channel, update_record_id),
                )
                intent_id = route_result.intent_id
                route_status = route_result.status
                routed_agent_id = route_result.routed_agent_id
                routed_lane_id = route_result.routed_lane_id
                route_category = route_result.intent_category
                route_confidence = route_result.confidence
                next_safe_move = route_result.next_safe_move
                conn.execute(
                    """
INSERT OR REPLACE INTO telegram_agent_intent_links (
  link_id, update_record_id, intent_record_id, link_kind, created_at,
  execution_allowed
) VALUES (?, ?, ?, 'telegram_update_to_intent_record', ?, 0)
""".strip(),
                    (_row_id("tgintentlink", update_record_id, intent_id), update_record_id, intent_id, now),
                )
                conn.execute(
                    """
INSERT OR REPLACE INTO telegram_agent_route_results (
  route_result_id, update_record_id, intent_record_id, routed_agent_id,
  routed_lane_id, intent_category, status, confidence, next_safe_move,
  created_at, execution_allowed, approval_bypass_allowed
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
""".strip(),
                    (
                        _row_id("tgroute", update_record_id, intent_id),
                        update_record_id,
                        intent_id,
                        routed_agent_id,
                        routed_lane_id,
                        route_category,
                        route_status,
                        route_confidence,
                        next_safe_move,
                        now,
                    ),
                )
            except Exception as exc:
                blocked_reason = f"intent_route_failed:{exc.__class__.__name__}"
                route_status = "blocked"
                next_safe_move = "Telegram update was stored, but deterministic routing failed; inspect intake blocker."
                conn.execute(
                    """
INSERT OR REPLACE INTO telegram_agent_route_results (
  route_result_id, update_record_id, intent_record_id, routed_agent_id,
  routed_lane_id, intent_category, status, confidence, next_safe_move,
  created_at, execution_allowed, approval_bypass_allowed
) VALUES (?, ?, NULL, ?, NULL, NULL, 'blocked', NULL, ?, ?, 0, 0)
""".strip(),
                    (_row_id("tgroute", update_record_id, "blocked"), update_record_id, resolved_agent, next_safe_move, now),
                )
        elif not operator_message:
            blocked_reason = "non_operator_message_metadata_only"
        else:
            blocked_reason = "route_intent_disabled"

        if create_work_board_card:
            metadata = AGENT_METADATA.get(resolved_agent, AGENT_METADATA["chief"])
            work_board_card_id = _insert_or_update_work_board_card(
                conn,
                source_id=f"telegram_agent_intake:{update_record_id}",
                title=f"Telegram intake proof for {metadata['display_name']}",
                summary="Synthetic or listener-provided Telegram update was stored in governed SQLite metadata and linked to Intent Router when safe.",
                agent_id=resolved_agent if resolved_agent in AGENT_METADATA else "chief",
                lane_id=metadata["lane_id"],
                board_column="routed" if route_status == "routed" else "needs_review",
                status=route_status or "metadata_stored",
                next_safe_move=next_safe_move,
                now=now,
            )

        conn.execute(
            """
UPDATE telegram_agent_update_records
SET routed_to_intent_inbox = ?,
    intent_record_id = ?,
    work_board_card_id = ?,
    blocked_reason = ?
WHERE update_record_id = ?
""".strip(),
            (1 if intent_id else 0, intent_id, work_board_card_id, blocked_reason, update_record_id),
        )
        receipt_payload = {
            "update_record_id": update_record_id,
            "intent_record_id": intent_id,
            "agent_target": resolved_agent,
            "source_channel": source_channel,
            "message_text_hash": msg_hash,
            "raw_payload_stored": False,
            "message_text_stored": False,
            "chat_id_stored": False,
            **NO_AUTHORITY_FLAGS,
        }
        conn.execute(
            """
INSERT OR REPLACE INTO telegram_agent_storage_receipts (
  receipt_id, update_record_id, intent_record_id, summary, payload_json,
  created_at, raw_payload_stored, message_text_stored,
  command_execution_allowed, telegram_send_allowed
) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 0)
""".strip(),
            (
                _row_id("tgreceipt", update_record_id),
                update_record_id,
                intent_id,
                "Telegram update stored in governed SQLite metadata; no send, execution, token exposure, or raw payload storage.",
                stable_json(receipt_payload),
                now,
            ),
        )
        counts = conn.execute(
            "SELECT COUNT(*) AS total, SUM(routed_to_intent_inbox) AS routed FROM telegram_agent_update_records WHERE run_id = ?",
            (resolved_run_id,),
        ).fetchone()
        conn.execute(
            """
UPDATE telegram_agent_intake_runs
SET completed_at = ?, update_count = ?, routed_count = ?,
    dry_run_proof_count = CASE WHEN ? LIKE 'synthetic_%' THEN 1 ELSE dry_run_proof_count END,
    governed_storage_available = 1,
    telegram_send_allowed = 0,
    command_execution_allowed = 0,
    action_auto_execute_allowed = 0,
    approval_bypass_allowed = 0,
    raw_payload_storage_allowed = 0,
    token_exposure_allowed = 0,
    external_api_send_allowed = 0
WHERE run_id = ?
""".strip(),
            (utc_now(), int(counts["total"] or 0), int(counts["routed"] or 0), source_channel, resolved_run_id),
        )
        conn.commit()
        return TelegramIntakeResult(
            update_record_id=update_record_id,
            run_id=resolved_run_id,
            db_path=path,
            agent_target=resolved_agent,
            source_channel=source_channel,
            routed_to_intent_inbox=bool(intent_id),
            intent_record_id=intent_id,
            route_status=route_status,
            routed_agent_id=routed_agent_id,
            routed_lane_id=routed_lane_id,
            work_board_card_id=work_board_card_id,
            raw_payload_stored=False,
            message_text_stored=False,
            telegram_send_allowed=False,
            command_execution_allowed=False,
        )
    finally:
        conn.close()


def record_telegram_listener_update_safe(
    *,
    text: str,
    source_channel: str,
    agent_target: str,
    source_message_id: str | None = None,
    source_user_label: str | None = "operator",
    operator_message: bool = True,
    route_intent: bool = True,
    db_path: str | Path | None = None,
) -> str | None:
    """Best-effort governed intake hook for live listeners.

    This helper deliberately catches all failures so legacy listener behavior is
    not changed by storage errors. It never prints message text, chat IDs, token
    values, or raw payloads.
    """

    try:
        result = record_telegram_update(
            text=text,
            source_channel=source_channel,
            agent_target=agent_target,
            source_message_id=source_message_id,
            source_user_label=source_user_label,
            operator_message=operator_message,
            route_intent=route_intent,
            create_work_board_card=False,
            db_path=db_path,
        )
        return result.update_record_id
    except Exception as exc:
        print(f"[telegram_agent_intake] governed intake failed: {exc.__class__.__name__}", flush=True)
        return None


def record_cassandra_listener_text_update(
    *,
    text: str,
    source_message_id: str | None = None,
    source_user_label: str | None = "operator",
    operator_message: bool = True,
    route_intent: bool = True,
    db_path: str | Path | None = None,
) -> str | None:
    """Record Cassandra live-listener text as governed intake metadata only.

    This wrapper is Cassandra-specific so live receive proof can be queried
    without granting reply, action, or Telegram-send authority.
    """

    return record_telegram_listener_update_safe(
        text=text,
        source_channel=AGENT_METADATA["cassandra"]["source_channel"],
        agent_target="cassandra",
        source_message_id=source_message_id,
        source_user_label=source_user_label,
        operator_message=operator_message,
        route_intent=route_intent,
        db_path=db_path,
    )


def _latest_presence_by_agent(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    if not _table_exists(conn, "agent_presence_agents"):
        return {}
    rows = _dict_rows(
        conn,
        """
SELECT *
FROM agent_presence_agents
ORDER BY created_at DESC
""".strip(),
    )
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        result.setdefault(row["agent_id"], row)
    return result


def _agent_posture_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    presence = _latest_presence_by_agent(conn)
    rows: list[dict[str, Any]] = []
    for agent_id in CORE_AGENTS:
        metadata = AGENT_METADATA[agent_id]
        agent_presence = presence.get(agent_id, {})
        actual_state = agent_presence.get("actual_state", "unknown")
        desired_state = agent_presence.get("desired_state", "unknown_review")
        telegram_surface_found = bool(metadata.get("telegram_surface"))
        governed_hook_available = metadata.get("listener_hook_status") == "governed_hook_added"
        receive_allowed = bool(actual_state == "online" and telegram_surface_found and governed_hook_available)
        if not telegram_surface_found:
            blocker = "telegram_listener_not_found"
            next_safe_move = f"Create or approve a Telegram listener surface for {metadata['display_name']} before expecting live receive."
        elif not governed_hook_available:
            blocker = "governed_listener_hook_missing"
            next_safe_move = f"Wire {metadata['display_name']} listener to telegram_agent_intake before relying on it."
        elif actual_state != "online":
            blocker = f"presence_{actual_state}"
            next_safe_move = f"Use agent presence/recovery policy to resolve {metadata['display_name']} state; do not bypass recovery gates."
        else:
            blocker = "none"
            next_safe_move = "Live listener appears online and governed storage hook is available; send remains blocked."
        rows.append(
            {
                "agent_id": agent_id,
                "display_name": metadata["display_name"],
                "outward_name": metadata["outward_name"],
                "lane_id": metadata["lane_id"],
                "desired_state": desired_state,
                "actual_state": actual_state,
                "telegram_surface_found": telegram_surface_found,
                "telegram_surface": metadata.get("telegram_surface"),
                "service_surface": metadata.get("service_surface"),
                "governed_listener_hook_available": governed_hook_available,
                "telegram_receive_allowed": receive_allowed,
                "telegram_send_allowed": False,
                "blocker": blocker,
                "next_safe_move": next_safe_move,
                "notes": metadata["notes"],
            }
        )
    return rows


def _upsert_blockers_and_cards(conn: sqlite3.Connection, *, run_id: str, agent_rows: list[dict[str, Any]], now: str) -> int:
    blocker_count = 0
    _insert_or_update_work_board_card(
        conn,
        source_id="telegram_agent_intake:readiness",
        title="Telegram agent intake readiness",
        summary="Governed Telegram intake storage is available in SQLite; live receive depends on each agent presence state.",
        agent_id="chief",
        lane_id="system_orchestration",
        board_column="planned",
        status="governed_storage_available",
        next_safe_move="Wire live listeners through governed intake and keep send authority blocked until explicitly approved.",
        now=now,
    )
    for row in agent_rows:
        if row["blocker"] == "none":
            continue
        blocker_count += 1
        conn.execute(
            """
INSERT OR REPLACE INTO telegram_agent_blockers (
  blocker_id, run_id, agent_id, blocker_kind, blocker_reason,
  next_safe_move, created_at, resolved
) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
""".strip(),
            (
                _row_id("tgblocker", row["agent_id"], row["blocker"]),
                run_id,
                row["agent_id"],
                row["blocker"],
                row["next_safe_move"],
                row["next_safe_move"],
                now,
            ),
        )
        if row["agent_id"] in {"cassandra", "chief", "niles", "hermes"}:
            _insert_or_update_work_board_card(
                conn,
                source_id=f"telegram_agent_intake:{row['agent_id']}:blocker",
                title=f"{row['outward_name']} Telegram readiness blocked",
                summary=f"{row['display_name']} desired={row['desired_state']} actual={row['actual_state']} blocker={row['blocker']}.",
                agent_id=row["agent_id"],
                lane_id=row["lane_id"],
                board_column="needs_review",
                status=row["blocker"],
                next_safe_move=row["next_safe_move"],
                now=now,
            )
    return blocker_count


def check_telegram_agent_intake(
    *,
    db_path: str | Path | None = None,
    run_id: str | None = None,
    create_dry_run_proof: bool = True,
) -> TelegramIntakeCheckResult:
    path = init_telegram_agent_intake_schema(db_path)
    now = utc_now()
    resolved_run_id = run_id or _row_id("tgcheck", now)
    dry_run: TelegramIntakeResult | None = None
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        _insert_run(conn, run_id=resolved_run_id, now=now)
        agent_rows = _agent_posture_rows(conn)
        blocker_count = _upsert_blockers_and_cards(conn, run_id=resolved_run_id, agent_rows=agent_rows, now=now)
        conn.commit()
    finally:
        conn.close()
    if create_dry_run_proof:
        dry_run = record_telegram_update(
            text="Chief, status check from gig.",
            source_channel="synthetic_dry_run",
            agent_target="chief",
            source_message_id="synthetic_local_proof",
            source_user_label="operator",
            operator_message=True,
            route_intent=True,
            create_work_board_card=True,
            db_path=path,
            run_id=resolved_run_id,
        )
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        agent_rows = _agent_posture_rows(conn)
        receive_ready_count = sum(1 for row in agent_rows if row["telegram_receive_allowed"])
        update_count = conn.execute(
            "SELECT COUNT(*) AS count FROM telegram_agent_update_records WHERE run_id = ?",
            (resolved_run_id,),
        ).fetchone()["count"]
        routed_count = conn.execute(
            "SELECT COUNT(*) AS count FROM telegram_agent_update_records WHERE run_id = ? AND routed_to_intent_inbox = 1",
            (resolved_run_id,),
        ).fetchone()["count"]
        conn.execute(
            """
UPDATE telegram_agent_intake_runs
SET completed_at = ?, update_count = ?, routed_count = ?,
    dry_run_proof_count = ?, governed_storage_available = 1,
    telegram_send_allowed = 0, command_execution_allowed = 0,
    action_auto_execute_allowed = 0, approval_bypass_allowed = 0,
    raw_payload_storage_allowed = 0, token_exposure_allowed = 0,
    external_api_send_allowed = 0
WHERE run_id = ?
""".strip(),
            (utc_now(), update_count, routed_count, 1 if dry_run else 0, resolved_run_id),
        )
        conn.commit()
    finally:
        conn.close()
    return TelegramIntakeCheckResult(
        run_id=resolved_run_id,
        db_path=path,
        governed_storage_available=True,
        dry_run_update_id=dry_run.update_record_id if dry_run else "",
        dry_run_intent_id=dry_run.intent_record_id if dry_run else None,
        dry_run_status=dry_run.route_status if dry_run else None,
        agent_count=len(CORE_AGENTS),
        receive_ready_count=receive_ready_count,
        blocker_count=blocker_count,
        telegram_send_allowed=False,
    )


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT run_id FROM telegram_agent_intake_runs ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    return row["run_id"] if row else None


def build_telegram_agent_intake_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
) -> dict[str, Any]:
    if report not in REPORT_SECTIONS:
        raise ValueError(f"unknown telegram intake report: {report}")
    path = init_telegram_agent_intake_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        run_id = _latest_run_id(conn)
        update_rows = _dict_rows(conn, "SELECT * FROM telegram_agent_update_records ORDER BY created_at DESC LIMIT 100")
        route_rows = _dict_rows(conn, "SELECT * FROM telegram_agent_route_results ORDER BY created_at DESC LIMIT 100")
        blockers = _dict_rows(conn, "SELECT * FROM telegram_agent_blockers WHERE resolved = 0 ORDER BY agent_id")
        agents = _agent_posture_rows(conn)
        counts = {
            "update_count": len(update_rows),
            "routed_count": sum(1 for row in update_rows if row["routed_to_intent_inbox"]),
            "raw_payload_stored_count": sum(1 for row in update_rows if row["raw_payload_stored"]),
            "message_text_stored_count": sum(1 for row in update_rows if row["message_text_stored"]),
            "agents": len(agents),
            "receive_ready_count": sum(1 for row in agents if row["telegram_receive_allowed"]),
            "blocked_agent_count": sum(1 for row in agents if row["blocker"] != "none"),
            "by_agent_target": dict(sorted(Counter(row["agent_target"] for row in update_rows).items())),
            "by_route_status": dict(sorted(Counter(row["status"] for row in route_rows).items())),
        }
        cassandra_rows = [
            row
            for row in update_rows
            if row["agent_target"] == "cassandra" or "cassandra" in row["source_channel"]
        ]
        cassandra_live_rows = [
            row
            for row in cassandra_rows
            if row["source_channel"] == AGENT_METADATA["cassandra"]["source_channel"]
        ]
        cassandra_synthetic_rows = [
            row
            for row in cassandra_rows
            if row["source_channel"].startswith("synthetic_cassandra")
        ]
        counts.update(
            {
                "cassandra_live_listener_count": len(cassandra_live_rows),
                "cassandra_live_operator_count": sum(1 for row in cassandra_live_rows if row["operator_message"]),
                "cassandra_synthetic_count": len(cassandra_synthetic_rows),
                "cassandra_metadata_only_count": sum(
                    1
                    for row in cassandra_live_rows
                    if not row["operator_message"] or not row["routed_to_intent_inbox"]
                ),
                "cassandra_no_live_receive_proof": len(cassandra_live_rows) == 0,
                "cassandra_old_ad_hoc_log_count": 0,
            }
        )
        if report == "agents":
            rows = agents
        elif report == "blockers":
            rows = blockers
        elif report == "latest":
            rows = update_rows[:10]
        elif report == "dry-run":
            rows = [row for row in update_rows if row["source_channel"] == "synthetic_dry_run"][:10]
        elif report == "cassandra-live":
            rows = cassandra_rows[:20]
        else:
            rows = update_rows[:12]
        return {
            "status": "ok",
            "report": report,
            "run_id": run_id,
            "counts": counts,
            "rows": rows,
            "agents": agents,
            "blockers": blockers,
            "no_authority_flags": NO_AUTHORITY_FLAGS,
        }
    finally:
        conn.close()


def format_telegram_intake_check_result(result: TelegramIntakeCheckResult) -> str:
    return "\n".join(
        [
            "Telegram Agent Intake Readiness v0",
            "",
            f"Run: `{result.run_id}`",
            f"Governed storage available: `{str(result.governed_storage_available).lower()}`",
            f"Dry-run update: `{result.dry_run_update_id}`",
            f"Dry-run intent: `{result.dry_run_intent_id or 'none'}`",
            f"Dry-run route status: `{result.dry_run_status or 'none'}`",
            f"Agents represented: {result.agent_count}",
            f"Receive-ready agents: {result.receive_ready_count}",
            f"Blockers: {result.blocker_count}",
            f"Telegram send allowed: `{str(result.telegram_send_allowed).lower()}`",
            "",
            "Boundary:",
            "- Check stores governed metadata and routes a synthetic local proof only; it does not call Telegram, send messages, start agents, read secrets, or execute commands.",
        ]
    )


def _counts_line(counts: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) if counts else "none"


def format_telegram_agent_intake_report(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    lines = [
        f"Telegram Agent Intake v0 - {payload['report']}",
        "",
        f"Updates: {counts['update_count']}",
        f"Routed: {counts['routed_count']}",
        f"Raw payload stored: {counts['raw_payload_stored_count']}",
        f"Full message text stored: {counts['message_text_stored_count']}",
        f"Agents: {counts['agents']}",
        f"Receive-ready agents: {counts['receive_ready_count']}",
        f"Blocked agents: {counts['blocked_agent_count']}",
        f"By agent target: {_counts_line(counts['by_agent_target'])}",
        f"By route status: {_counts_line(counts['by_route_status'])}",
    ]
    if payload["report"] == "cassandra-live":
        proof = "not_proven" if counts["cassandra_no_live_receive_proof"] else "proven"
        lines.extend(
            [
                f"Cassandra live listener records: {counts['cassandra_live_listener_count']}",
                f"Cassandra live operator records: {counts['cassandra_live_operator_count']}",
                f"Cassandra synthetic records: {counts['cassandra_synthetic_count']}",
                f"Cassandra metadata-only live records: {counts['cassandra_metadata_only_count']}",
                f"Old/ad hoc Cassandra log records: {counts['cassandra_old_ad_hoc_log_count']} (not governed proof)",
                f"Live receive proof: `{proof}`",
                "Reply/send allowed: `false`",
            ]
        )
    lines.extend(["", "Rows:"])
    for row in payload.get("rows") or []:
        if payload["report"] == "agents":
            lines.append(
                f"- `{row['agent_id']}` outward={row['outward_name']} desired={row['desired_state']} actual={row['actual_state']} receive={str(row['telegram_receive_allowed']).lower()} blocker={row['blocker']}"
            )
        elif payload["report"] == "blockers":
            lines.append(f"- `{row['agent_id']}` {row['blocker_kind']}: {row['next_safe_move']}")
        elif payload["report"] == "cassandra-live":
            if row["source_channel"] == AGENT_METADATA["cassandra"]["source_channel"]:
                kind = "live_listener"
            elif row["source_channel"].startswith("synthetic_cassandra"):
                kind = "synthetic"
            else:
                kind = "other"
            lines.append(
                f"- `{row['update_record_id']}` kind={kind} channel={row['source_channel']} operator={str(bool(row['operator_message'])).lower()} routed={str(bool(row['routed_to_intent_inbox'])).lower()} intent={row['intent_record_id'] or 'none'}"
            )
        else:
            lines.append(
                f"- `{row['update_record_id']}` target={row['agent_target']} channel={row['source_channel']} routed={str(bool(row['routed_to_intent_inbox'])).lower()} intent={row['intent_record_id'] or 'none'}"
            )
    if not payload.get("rows"):
        lines.append("- none")
    lines.extend(["", "Agents:"])
    for row in payload.get("agents") or []:
        lines.append(
            f"- `{row['agent_id']}` / {row['outward_name']}: actual={row['actual_state']}, receive={str(row['telegram_receive_allowed']).lower()}, send=false, next={row['next_safe_move']}"
        )
    lines.extend(["", "Authority boundary:"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`.")
    return "\n".join(lines)


def build_telegram_agent_intake_read_model(db_path: str | Path | None = None) -> dict[str, Any]:
    report = build_telegram_agent_intake_report(db_path=db_path, report="summary")
    latest = build_telegram_agent_intake_report(db_path=db_path, report="latest")
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "generated_at": utc_now(),
        "intake_status": "governed_storage_available" if report["counts"]["update_count"] >= 0 else "unknown_review",
        "governed_storage_available": True,
        "storage_tables": [
            "telegram_agent_update_records",
            "telegram_agent_intent_links",
            "telegram_agent_route_results",
            "telegram_agent_storage_receipts",
            "intent_records",
            "work_board_cards",
        ],
        "counts": report["counts"],
        "agents": report["agents"],
        "latest_updates": latest["rows"],
        "blockers": report["blockers"],
        "dry_run_route_proof": build_telegram_agent_intake_report(db_path=db_path, report="dry-run")["rows"],
        "next_safe_moves": [
            "Wire or restart only agents whose presence/recovery policy explicitly allows it.",
            "Keep Cassandra/Clara outbound Telegram send blocked until an approved status-only send path exists.",
            "Use governed intake records and Intent Router records as canonical storage for Telegram operator updates.",
        ],
        "no_authority_flags": NO_AUTHORITY_FLAGS,
    }


def _operator_markdown(read_model: dict[str, Any]) -> str:
    counts = read_model["counts"]
    lines = [
        "# Telegram Agent Intake v0",
        "",
        "## Summary",
        f"- Intake status: `{read_model['intake_status']}`",
        f"- Governed storage available: `{str(read_model['governed_storage_available']).lower()}`",
        f"- Updates: {counts['update_count']}",
        f"- Routed: {counts['routed_count']}",
        f"- Receive-ready agents: {counts['receive_ready_count']}",
        f"- Blocked agents: {counts['blocked_agent_count']}",
        f"- Raw payload stored: {counts['raw_payload_stored_count']}",
        f"- Full message text stored: {counts['message_text_stored_count']}",
        "",
        "## Agents",
    ]
    for row in read_model.get("agents") or []:
        lines.append(
            f"- `{row['agent_id']}` / {row['outward_name']}: desired={row['desired_state']}, actual={row['actual_state']}, receive={str(row['telegram_receive_allowed']).lower()}, send=false, blocker={row['blocker']}"
        )
    lines.extend(["", "## Dry-Run Proof"])
    for row in read_model.get("dry_run_route_proof") or []:
        lines.append(
            f"- `{row['update_record_id']}` channel={row['source_channel']} target={row['agent_target']} intent={row['intent_record_id'] or 'none'} routed={str(bool(row['routed_to_intent_inbox'])).lower()}"
        )
    if not read_model.get("dry_run_route_proof"):
        lines.append("- None.")
    lines.extend(["", "## Blockers"])
    for row in read_model.get("blockers") or []:
        lines.append(f"- `{row['agent_id']}` {row['blocker_kind']}: {row['next_safe_move']}")
    if not read_model.get("blockers"):
        lines.append("- None.")
    lines.extend(["", "## Authority Boundary"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`.")
    return "\n".join(lines) + "\n"


def export_telegram_agent_intake_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    out_root = _export_root_path(export_root)
    out_root.mkdir(parents=True, exist_ok=True)
    read_model = build_telegram_agent_intake_read_model(db_path)
    json_path = out_root / JSON_EXPORT_NAME
    operator_path = out_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(_operator_markdown(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "governed_storage_available": read_model["governed_storage_available"],
        "update_count": read_model["counts"]["update_count"],
        "routed_count": read_model["counts"]["routed_count"],
        "receive_ready_count": read_model["counts"]["receive_ready_count"],
        "no_authority_flags": NO_AUTHORITY_FLAGS,
    }


__all__ = [
    "AGENT_METADATA",
    "CORE_AGENTS",
    "NO_AUTHORITY_FLAGS",
    "READ_MODEL_VERSION",
    "REPORT_SECTIONS",
    "TELEGRAM_INTAKE_VERSION",
    "TelegramIntakeCheckResult",
    "TelegramIntakeResult",
    "build_telegram_agent_intake_read_model",
    "build_telegram_agent_intake_report",
    "check_telegram_agent_intake",
    "export_telegram_agent_intake_read_model",
    "format_telegram_agent_intake_report",
    "format_telegram_intake_check_result",
    "init_telegram_agent_intake_schema",
    "record_cassandra_listener_text_update",
    "record_telegram_listener_update_safe",
    "record_telegram_update",
    "stable_json",
    "telegram_agent_intake_table_names",
]
