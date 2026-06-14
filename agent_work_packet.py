"""Agent Work Packet v0 for OpenClaw.

Agent work packets are bounded planning artifacts derived from routed intents.
They can be handed to a future Codex/local worker as a safe prompt scaffold.
They do not execute commands, create actions, activate agents, call models, or
grant file/runtime authority.
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

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger
from intent_router import init_intent_router_schema, route_operator_intent


ROOT = Path(__file__).resolve().parent
AGENT_WORK_PACKET_VERSION = "agent_work_packet_v0"
READ_MODEL_VERSION = "agent_work_packets_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "agent_work_packets.json"
OPERATOR_EXPORT_NAME = "agent_work_packets_OPERATOR.md"
MAX_PROMPT_CHARS = 3500

PACKET_STATUSES = {"draft", "proposed"}

NO_AUTHORITY_FLAGS = {
    "execution_allowed": False,
    "agent_activation_allowed": False,
    "model_call_allowed": False,
    "tool_execution_allowed": False,
    "network_authority": False,
    "approval_bypass_allowed": False,
    "action_created": False,
    "action_auto_approve_allowed": False,
    "action_auto_execute_allowed": False,
    "no_go_raw_access_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "client_deployment_allowed": False,
    "truth_promotion_allowed": False,
}


@dataclass(frozen=True)
class AgentWorkPacketResult:
    packet_id: str
    run_id: str
    source_intent_id: str | None
    routed_agent_id: str
    routed_lane_id: str
    goal: str
    status: str
    context_link_count: int
    command_candidate_count: int
    execution_allowed: bool


@dataclass(frozen=True)
class AgentWorkPacketApprovalState:
    packet_id: str
    surface: str
    status: str
    approval_required: bool
    execution_allowed: bool
    action_created: bool
    packet_hash: str
    expected_packet_hash: str | None
    hash_matches: bool | None

    @property
    def stale(self) -> bool:
        return self.hash_matches is False

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "surface": self.surface,
            "status": self.status,
            "approval_required": self.approval_required,
            "execution_allowed": self.execution_allowed,
            "action_created": self.action_created,
            "packet_hash": self.packet_hash,
            "expected_packet_hash": self.expected_packet_hash,
            "hash_matches": self.hash_matches,
            "stale": self.stale,
        }


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


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS agent_work_packet_runs (
  run_id TEXT PRIMARY KEY,
  packet_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  packet_count INTEGER NOT NULL DEFAULT 0,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  approval_bypass_allowed INTEGER NOT NULL DEFAULT 0,
  action_created INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_work_packets (
  packet_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  source_intent_id TEXT,
  source_intent_preview TEXT,
  routed_agent_id TEXT NOT NULL,
  routed_lane_id TEXT NOT NULL,
  world_hint TEXT NOT NULL,
  intent_category TEXT NOT NULL,
  goal TEXT NOT NULL,
  status TEXT NOT NULL,
  approval_required INTEGER NOT NULL DEFAULT 1,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  action_created INTEGER NOT NULL DEFAULT 0,
  candidate_action_type TEXT,
  rollback_required_for_future_action INTEGER NOT NULL DEFAULT 1,
  exact_next_prompt_text TEXT NOT NULL,
  prompt_char_count INTEGER NOT NULL,
  raw_private_content_included INTEGER NOT NULL DEFAULT 0,
  no_go_raw_access_allowed INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES agent_work_packet_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_work_packet_context_links (
  packet_context_link_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  link_kind TEXT NOT NULL,
  source_table TEXT NOT NULL,
  source_id TEXT,
  source_path TEXT,
  summary TEXT NOT NULL,
  allowed_for_packet INTEGER NOT NULL DEFAULT 1,
  raw_content_read INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (packet_id) REFERENCES agent_work_packets(packet_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_work_packet_allowed_surfaces (
  allowed_surface_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  surface_kind TEXT NOT NULL,
  surface_ref TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (packet_id) REFERENCES agent_work_packets(packet_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_work_packet_blocked_surfaces (
  blocked_surface_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  surface_kind TEXT NOT NULL,
  surface_ref TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (packet_id) REFERENCES agent_work_packets(packet_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_work_packet_command_candidates (
  command_candidate_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  candidate_action_type TEXT,
  candidate_only INTEGER NOT NULL DEFAULT 1,
  approval_required INTEGER NOT NULL DEFAULT 1,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (packet_id) REFERENCES agent_work_packets(packet_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_work_packet_receipts (
  receipt_id TEXT PRIMARY KEY,
  packet_id TEXT NOT NULL,
  receipt_type TEXT NOT NULL,
  summary TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  action_created INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (packet_id) REFERENCES agent_work_packets(packet_id) ON DELETE CASCADE
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_agent_work_packets_agent ON agent_work_packets(routed_agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_agent_work_packets_status ON agent_work_packets(status)",
    )


def init_agent_work_packet_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    parent = Path(path).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    init_intent_router_schema(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def agent_work_packet_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_agent_work_packet_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'agent_work_packet%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _latest_intent(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
SELECT *
FROM intent_records
ORDER BY created_at DESC, intent_id DESC
LIMIT 1
""".strip()
    ).fetchone()


def _intent_by_id(conn: sqlite3.Connection, intent_id: str | None) -> sqlite3.Row | None:
    if intent_id:
        return conn.execute("SELECT * FROM intent_records WHERE intent_id = ?", (intent_id,)).fetchone()
    return _latest_intent(conn)


def _goal_for_intent(intent: sqlite3.Row) -> str:
    category = intent["intent_category"]
    if category == "invoice_send":
        return "Prepare an invoice-send approval card. Nothing has been sent yet."
    if category == "email_send":
        return "Prepare an email-send approval card. Nothing has been sent yet."
    if category == "sms_send":
        return "Prepare an SMS-send approval card. Nothing has been sent yet."
    if category == "phone_log":
        return "Prepare a phone/call action approval card. Nothing has been called yet."
    if category == "calendar_create":
        return "Prepare a calendar-event approval card. Nothing has been created yet."
    if category == "ledger_mutation":
        return "Prepare a ledger-change approval card. Nothing has been changed yet."
    if category == "coupa_submit":
        return "Prepare a Coupa-submit approval card. Nothing has been submitted yet."
    if category == "obs_launch":
        return "Prepare an OBS launch approval card. Nothing has been launched yet."
    if category == "livestream_setup":
        return "Prepare a livestream setup approval card. Nothing has been started yet."
    if category == "markdown_reorg_request":
        return "Propose a Markdown organization/reorg plan without moving files."
    if category == "file_context_request":
        return "Produce a metadata-only plan for the referenced recent file."
    if category == "safety_review_request":
        return "Review safety/no-go posture using metadata and approved evidence only."
    if category == "communication_summary_request":
        return "Draft an operator-facing summary from generated read-model surfaces."
    if category == "read_model_refresh_request":
        return "Prepare a candidate bounded read-model refresh action for approval."
    if category == "report_bridge_request":
        return "Inspect sanitized Report Bridge package posture without importing raw client data."
    return f"Draft a bounded plan for {category}."


def _allowed_surfaces_for_intent(intent: sqlite3.Row) -> list[tuple[str, str, str]]:
    surfaces = [
        ("generated_read_model", "generated/read_models/agent_lanes.json", "Agent lane posture."),
        ("generated_read_model", "generated/read_models/intent_router.json", "Intent route posture."),
    ]
    if intent["intent_category"] == "markdown_reorg_request":
        surfaces.extend(
            [
                ("sqlite_report", "markdown_knowledge_atlas.summary", "Markdown role/reorg metadata."),
                ("generated_read_model", "generated/read_models/markdown_evidence.json", "Approved Markdown excerpts only."),
                ("generated_read_model", "generated/read_models/dropped_intents.json", "Unresolved directions, metadata only."),
            ]
        )
    if intent["intent_category"] == "file_context_request":
        surfaces.append(
            ("generated_read_model", "generated/read_models/recent_file_context.json", "Recent file metadata context.")
        )
    return surfaces


def _blocked_surfaces_for_intent(intent: sqlite3.Row) -> list[tuple[str, str, str]]:
    return [
        ("raw_private_content", "private/no-go roots", "No private or no-go raw content is allowed."),
        ("filesystem_mutation", "file moves/deletes/renames", "Packet is planning-only; no file changes."),
        ("runtime_execution", "agents/tools/models/runtime", "No activation or execution authority."),
        ("client_deployment", "client/live deployment", "No deployment authority in v0."),
    ]


def _context_links_for_intent(conn: sqlite3.Connection, intent_id: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            """
SELECT link_kind, source_table, source_id, source_path, summary,
       raw_content_read, raw_body_stored
FROM intent_context_links
WHERE intent_id = ?
ORDER BY link_kind, source_path
""".strip(),
            (intent_id,),
        ).fetchall()
    ]


def _packet_hash_from_row(row: sqlite3.Row) -> str:
    payload = {
        "packet_id": row["packet_id"],
        "source_intent_id": row["source_intent_id"],
        "routed_agent_id": row["routed_agent_id"],
        "routed_lane_id": row["routed_lane_id"],
        "world_hint": row["world_hint"],
        "intent_category": row["intent_category"],
        "goal": row["goal"],
        "status": row["status"],
        "approval_required": bool(row["approval_required"]),
        "execution_allowed": bool(row["execution_allowed"]),
        "action_created": bool(row["action_created"]),
        "candidate_action_type": row["candidate_action_type"],
        "exact_next_prompt_text": row["exact_next_prompt_text"],
    }
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def get_agent_work_packet_approval_state(
    *,
    packet_id: str,
    expected_packet_hash: str | None = None,
    db_path: str | Path | None = None,
) -> AgentWorkPacketApprovalState:
    path = init_agent_work_packet_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM agent_work_packets WHERE packet_id = ?", (packet_id,)).fetchone()
        if row is None:
            raise ValueError(f"agent work packet not found: {packet_id}")
        packet_hash = _packet_hash_from_row(row)
        hash_matches = None if expected_packet_hash is None else packet_hash == expected_packet_hash
        return AgentWorkPacketApprovalState(
            packet_id=row["packet_id"],
            surface=row["candidate_action_type"] or row["intent_category"],
            status=row["status"],
            approval_required=bool(row["approval_required"]),
            execution_allowed=bool(row["execution_allowed"]),
            action_created=bool(row["action_created"]),
            packet_hash=packet_hash,
            expected_packet_hash=expected_packet_hash,
            hash_matches=hash_matches,
        )
    finally:
        conn.close()


def _bounded_prompt(
    *,
    intent: sqlite3.Row,
    goal: str,
    context_links: list[dict[str, Any]],
    allowed_surfaces: list[tuple[str, str, str]],
    blocked_surfaces: list[tuple[str, str, str]],
) -> str:
    lines = [
        f"You are working in /home/openclaw.",
        "",
        "Task:",
        goal,
        "",
        f"Source intent: {intent['intent_id']}",
        f"Routed agent/lane: {intent['routed_agent_id']} / {intent['routed_lane_id']}",
        f"World: {intent['world_hint']}",
        f"Category: {intent['intent_category']}",
        "",
        "Allowed context surfaces:",
    ]
    for kind, ref, reason in allowed_surfaces:
        lines.append(f"- {kind}: {ref} ({reason})")
    if context_links:
        lines.extend(["", "Context links:"])
        for link in context_links[:12]:
            lines.append(
                f"- {link['link_kind']} {link['source_table']}:{link['source_id'] or 'none'} "
                f"path={link['source_path'] or 'none'} summary={link['summary']}"
            )
    lines.extend(["", "Blocked surfaces/actions:"])
    for kind, ref, reason in blocked_surfaces:
        lines.append(f"- {kind}: {ref} ({reason})")
    lines.extend(
        [
            "",
            "Hard boundary:",
            "- Planning packet only.",
            "- Do not execute, approve, activate agents, call models, call network APIs, move files, delete files, or read private/no-go raw content.",
            "- Produce a proposed next-safe plan and list approval requirements.",
        ]
    )
    prompt = "\n".join(lines)
    if len(prompt) <= MAX_PROMPT_CHARS:
        return prompt
    return prompt[: MAX_PROMPT_CHARS - 3].rstrip() + "..."


def build_agent_work_packet(
    *,
    db_path: str | Path | None = None,
    intent_id: str | None = None,
    packet_id: str | None = None,
    run_id: str | None = None,
    status: str = "draft",
) -> AgentWorkPacketResult:
    if status not in PACKET_STATUSES:
        raise ValueError(f"unsupported packet status: {status}")
    path = init_agent_work_packet_schema(db_path)
    now = utc_now()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        intent = _intent_by_id(conn, intent_id)
        if not intent:
            raise ValueError("no source intent is available; route an intent first or pass --sample")
        if intent["status"] == "rejected":
            raise ValueError(f"cannot build work packet from rejected intent: {intent['intent_id']}")
        resolved_run_id = run_id or _row_id("awprun", intent["intent_id"], now)
        resolved_packet_id = packet_id or _row_id("awp", intent["intent_id"], status)
        goal = _goal_for_intent(intent)
        context_links = _context_links_for_intent(conn, intent["intent_id"])
        allowed_surfaces = _allowed_surfaces_for_intent(intent)
        blocked_surfaces = _blocked_surfaces_for_intent(intent)
        prompt = _bounded_prompt(
            intent=intent,
            goal=goal,
            context_links=context_links,
            allowed_surfaces=allowed_surfaces,
            blocked_surfaces=blocked_surfaces,
        )

        conn.execute("PRAGMA foreign_keys = ON")
        for table in (
            "agent_work_packet_receipts",
            "agent_work_packet_command_candidates",
            "agent_work_packet_blocked_surfaces",
            "agent_work_packet_allowed_surfaces",
            "agent_work_packet_context_links",
            "agent_work_packets",
        ):
            if table == "agent_work_packets":
                conn.execute("DELETE FROM agent_work_packets WHERE packet_id = ?", (resolved_packet_id,))
            else:
                conn.execute(f"DELETE FROM {table} WHERE packet_id = ?", (resolved_packet_id,))
        conn.execute(
            """
INSERT INTO agent_work_packet_runs (
  run_id, packet_version, created_at, completed_at, packet_count,
  execution_allowed, agent_activation_allowed, model_call_allowed,
  tool_execution_allowed, network_authority, approval_bypass_allowed,
  action_created, file_move_allowed, file_delete_allowed, notes
) VALUES (?, ?, ?, ?, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?)
ON CONFLICT(run_id) DO UPDATE SET
  completed_at = excluded.completed_at,
  packet_count = 1,
  execution_allowed = 0,
  agent_activation_allowed = 0,
  model_call_allowed = 0,
  tool_execution_allowed = 0,
  network_authority = 0,
  approval_bypass_allowed = 0,
  action_created = 0,
  file_move_allowed = 0,
  file_delete_allowed = 0,
  notes = excluded.notes
""".strip(),
            (
                resolved_run_id,
                AGENT_WORK_PACKET_VERSION,
                now,
                now,
                "Planning packet build; no execution, no action creation, no agent activation.",
            ),
        )
        conn.execute(
            """
INSERT INTO agent_work_packets (
  packet_id, run_id, source_intent_id, source_intent_preview,
  routed_agent_id, routed_lane_id, world_hint, intent_category, goal,
  status, approval_required, execution_allowed, action_created,
  candidate_action_type, rollback_required_for_future_action,
  exact_next_prompt_text, prompt_char_count, raw_private_content_included,
  no_go_raw_access_allowed, file_move_allowed, file_delete_allowed, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, ?, 1, ?, ?, 0, 0, 0, 0, ?)
""".strip(),
            (
                resolved_packet_id,
                resolved_run_id,
                intent["intent_id"],
                intent["intent_text_preview"],
                intent["routed_agent_id"] or "unrouted",
                intent["routed_lane_id"] or "none",
                intent["world_hint"],
                intent["intent_category"],
                goal,
                status,
                intent["candidate_action_type"],
                prompt,
                len(prompt),
                now,
            ),
        )
        for link in context_links:
            conn.execute(
                """
INSERT INTO agent_work_packet_context_links (
  packet_context_link_id, packet_id, link_kind, source_table, source_id,
  source_path, summary, allowed_for_packet, raw_content_read,
  raw_body_stored, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, 0, ?)
""".strip(),
                (
                    _row_id(
                        "awpctx",
                        resolved_packet_id,
                        link["link_kind"],
                        link["source_table"],
                        link.get("source_id") or "",
                        link.get("source_path") or "",
                    ),
                    resolved_packet_id,
                    link["link_kind"],
                    link["source_table"],
                    link.get("source_id"),
                    link.get("source_path"),
                    link["summary"],
                    now,
                ),
            )
        for kind, ref, reason in allowed_surfaces:
            conn.execute(
                """
INSERT INTO agent_work_packet_allowed_surfaces (
  allowed_surface_id, packet_id, surface_kind, surface_ref, reason, created_at
) VALUES (?, ?, ?, ?, ?, ?)
""".strip(),
                (_row_id("awpallow", resolved_packet_id, kind, ref), resolved_packet_id, kind, ref, reason, now),
            )
        for kind, ref, reason in blocked_surfaces:
            conn.execute(
                """
INSERT INTO agent_work_packet_blocked_surfaces (
  blocked_surface_id, packet_id, surface_kind, surface_ref, reason, created_at
) VALUES (?, ?, ?, ?, ?, ?)
""".strip(),
                (_row_id("awpblock", resolved_packet_id, kind, ref), resolved_packet_id, kind, ref, reason, now),
            )
        command_count = 0
        if intent["candidate_action_type"]:
            conn.execute(
                """
INSERT INTO agent_work_packet_command_candidates (
  command_candidate_id, packet_id, candidate_action_type, candidate_only,
  approval_required, execution_allowed, reason, created_at
) VALUES (?, ?, ?, 1, 1, 0, ?, ?)
""".strip(),
                (
                    _row_id("awpcmd", resolved_packet_id, intent["candidate_action_type"]),
                    resolved_packet_id,
                    intent["candidate_action_type"],
                    "Candidate Operator Action only; no request created or executed.",
                    now,
                ),
            )
            command_count = 1
        conn.execute(
            """
INSERT INTO agent_work_packet_receipts (
  receipt_id, packet_id, receipt_type, summary, payload_json,
  execution_allowed, action_created, created_at
) VALUES (?, ?, 'packet_build_receipt', ?, ?, 0, 0, ?)
""".strip(),
            (
                _row_id("awpreceipt", resolved_packet_id),
                resolved_packet_id,
                f"Built draft work packet for {intent['routed_agent_id']}/{intent['routed_lane_id']}.",
                stable_json(
                    {
                        "packet_id": resolved_packet_id,
                        "source_intent_id": intent["intent_id"],
                        "context_link_count": len(context_links),
                        "command_candidate_count": command_count,
                        **NO_AUTHORITY_FLAGS,
                    }
                ),
                now,
            ),
        )
        conn.commit()
        return AgentWorkPacketResult(
            packet_id=resolved_packet_id,
            run_id=resolved_run_id,
            source_intent_id=intent["intent_id"],
            routed_agent_id=intent["routed_agent_id"] or "unrouted",
            routed_lane_id=intent["routed_lane_id"] or "none",
            goal=goal,
            status=status,
            context_link_count=len(context_links),
            command_candidate_count=command_count,
            execution_allowed=False,
        )
    finally:
        conn.close()


def build_sample_markdown_reorg_packet(
    *,
    db_path: str | Path | None = None,
    packet_id: str = "agent_work_packet_sample_markdown_reorg",
    run_id: str = "agent_work_packet_sample_run",
) -> AgentWorkPacketResult:
    path = init_agent_work_packet_schema(db_path)
    route_operator_intent(
        text="Chief, organize my Markdown files.",
        source_kind="cli",
        source_channel="agent_work_packet_sample",
        requested_by="operator",
        db_path=path,
        intent_id="intent_agent_work_packet_sample_markdown_reorg",
        run_id="intent_agent_work_packet_sample_run",
    )
    return build_agent_work_packet(
        db_path=path,
        intent_id="intent_agent_work_packet_sample_markdown_reorg",
        packet_id=packet_id,
        run_id=run_id,
    )


REPORT_SECTIONS = {"summary", "packets", "latest"}


def _packet_summary(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "packet_id": row["packet_id"],
        "source_intent_id": row["source_intent_id"],
        "routed_agent_id": row["routed_agent_id"],
        "routed_lane_id": row["routed_lane_id"],
        "world_hint": row["world_hint"],
        "intent_category": row["intent_category"],
        "goal": row["goal"],
        "status": row["status"],
        "approval_required": bool(row["approval_required"]),
        "execution_allowed": bool(row["execution_allowed"]),
        "action_created": bool(row["action_created"]),
        "candidate_action_type": row["candidate_action_type"],
        "prompt_char_count": row["prompt_char_count"],
        "created_at": row["created_at"],
    }


def build_agent_work_packet_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
) -> dict[str, Any]:
    if report not in REPORT_SECTIONS:
        raise ValueError(f"unknown agent work packet report: {report}")
    path = init_agent_work_packet_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
SELECT *
FROM agent_work_packets
ORDER BY created_at DESC, packet_id DESC
""".strip()
        ).fetchall()
        items = rows[:1] if report == "latest" else rows[:20]
        agent_counts = Counter(row["routed_agent_id"] for row in rows)
        status_counts = Counter(row["status"] for row in rows)
        category_counts = Counter(row["intent_category"] for row in rows)
        return {
            "status": "ok",
            "report": report,
            "db_path": str(path),
            "counts": {
                "packet_count": len(rows),
                "by_agent": dict(sorted(agent_counts.items())),
                "by_status": dict(sorted(status_counts.items())),
                "by_category": dict(sorted(category_counts.items())),
                "execution_allowed": sum(1 for row in rows if row["execution_allowed"]),
                "action_created": sum(1 for row in rows if row["action_created"]),
            },
            "latest_packet": _packet_summary(rows[0]) if rows else None,
            "items": [_packet_summary(row) for row in items],
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def _counts_line(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def format_agent_work_packet_report(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    lines = [
        f"Agent Work Packet v0 - {payload['report']}",
        "",
        f"Packets: {counts['packet_count']}",
        f"By agent: {_counts_line(counts['by_agent'])}",
        f"By status: {_counts_line(counts['by_status'])}",
        f"By category: {_counts_line(counts['by_category'])}",
        f"Execution allowed rows: {counts['execution_allowed']}",
        f"Action created rows: {counts['action_created']}",
        "",
        "Items:",
    ]
    for item in payload.get("items") or []:
        lines.append(
            f"- `{item['packet_id']}` {item['status']} -> "
            f"{item['routed_agent_id']}/{item['routed_lane_id']} goal={item['goal']}"
        )
    if not payload.get("items"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Planning packets only; no execution, action creation, agent activation, model calls, file moves, or deletes.",
        ]
    )
    return "\n".join(lines)


def build_agent_work_packets_read_model(
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    report = build_agent_work_packet_report(db_path=db_path, report="summary")
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "mode": "agent_work_packets_planning_only",
        "generated_at": utc_now(),
        "source_ledger_path": _display_path(report["db_path"]),
        "source_ledger_namespace": "agent_work_packet_*",
        "packet_count": report["counts"]["packet_count"],
        "counts_by_agent": report["counts"]["by_agent"],
        "counts_by_status": report["counts"]["by_status"],
        "counts_by_category": report["counts"]["by_category"],
        "latest_packet": report["latest_packet"],
        "packets": report["items"],
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_agent_work_packets_read_model(read_model: dict[str, Any]) -> str:
    latest = read_model.get("latest_packet")
    lines = [
        "# Agent Work Packets Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over bounded `agent_work_packet_*` planning packets.",
        "",
        "What this is not:",
        "- It is not execution, agent activation, model calling, action creation, or approval.",
        "",
        "Summary:",
        f"- Packets: {read_model['packet_count']}.",
        f"- By agent: {_counts_line(read_model['counts_by_agent'])}.",
        f"- By status: {_counts_line(read_model['counts_by_status'])}.",
        f"- By category: {_counts_line(read_model['counts_by_category'])}.",
        "",
        "Latest packet:",
    ]
    if latest:
        lines.extend(
            [
                f"- Packet: `{latest['packet_id']}`.",
                f"- Agent/lane: `{latest['routed_agent_id']}` / `{latest['routed_lane_id']}`.",
                f"- Goal: {latest['goal']}",
                f"- Execution allowed: `{str(latest['execution_allowed']).lower()}`.",
            ]
        )
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "Authority boundary:",
            "- execution_allowed=false; agent_activation_allowed=false; model_call_allowed=false.",
            "- tool_execution_allowed=false; network_authority=false; approval_bypass_allowed=false.",
            "- file_move_allowed=false; file_delete_allowed=false; truth_promotion_allowed=false.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_agent_work_packets_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_agent_work_packets_read_model(db_path=db_path)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_agent_work_packets_read_model(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "packet_count": read_model["packet_count"],
        **NO_AUTHORITY_FLAGS,
    }


def format_packet_result(result: AgentWorkPacketResult) -> str:
    return "\n".join(
        [
            "Agent Work Packet v0",
            "",
            f"Packet: `{result.packet_id}`",
            f"Run: `{result.run_id}`",
            f"Source intent: `{result.source_intent_id or 'none'}`",
            f"Agent/lane: `{result.routed_agent_id}` / `{result.routed_lane_id}`",
            f"Status: `{result.status}`",
            f"Context links: {result.context_link_count}",
            f"Command candidates: {result.command_candidate_count}",
            f"Execution allowed: `{str(result.execution_allowed).lower()}`",
            "",
            "Goal:",
            f"- {result.goal}",
            "",
            "Boundary:",
            "- Draft planning packet only; no action was created, approved, or executed.",
        ]
    )


__all__ = [
    "AGENT_WORK_PACKET_VERSION",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_VERSION",
    "REPORT_SECTIONS",
    "AgentWorkPacketApprovalState",
    "AgentWorkPacketResult",
    "agent_work_packet_table_names",
    "build_agent_work_packet",
    "build_agent_work_packet_report",
    "build_agent_work_packets_read_model",
    "build_sample_markdown_reorg_packet",
    "export_agent_work_packets_read_model",
    "format_agent_work_packet_report",
    "format_agent_work_packets_read_model",
    "format_packet_result",
    "get_agent_work_packet_approval_state",
    "init_agent_work_packet_schema",
    "stable_json",
]
