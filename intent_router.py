"""Intent Router v0 for OpenClaw.

This module records deterministic, non-executing routes from operator text to
role-scoped Agent Lane Registry rows. It stores a short sanitized preview and a
hash of the request text, links only metadata from existing substrate tables,
and exports a bounded read-model. It does not call models, execute tools,
approve actions, activate agents, read no-go raw content, or move files.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_lane_registry import init_agent_lane_registry_schema, seed_agent_lane_registry
from business_ops_ledger import (
    DEFAULT_DB_PATH,
    init_business_ops_ledger,
    is_transient_sqlite_write_error,
    reset_disposable_sqlite_path,
)
from operator_action import ALLOWED_ACTIONS, ALLOWED_SOURCE_KINDS, init_operator_action_schema
from recent_file_context import (
    init_recent_file_context_schema,
)


ROOT = Path(__file__).resolve().parent
INTENT_ROUTER_VERSION = "intent_router_v0"
READ_MODEL_VERSION = "intent_router_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "intent_router.json"
OPERATOR_EXPORT_NAME = "intent_router_OPERATOR.md"
MAX_PREVIEW_CHARS = 180

SOURCE_KINDS = set(ALLOWED_SOURCE_KINDS)
INTENT_CATEGORIES = {
    "invoice_send",
    "email_send",
    "sms_send",
    "phone_log",
    "calendar_create",
    "ledger_mutation",
    "coupa_submit",
    "obs_launch",
    "livestream_setup",
    "gig_intake",
    "musiclaw_query",
    "publishing_query",
    "cpa_query",
    "financial_report",
    "analytics_report",
    "goals_check",
    "momentum_check",
    "reflection_report",
    "system_report",
    "calendar_query",
    "brand_guide",
    "content_calendar",
    "scout_report",
    "phone_assist",
    "backup_status",
    "album_request",
    "brainstorm_status",
    "queue_status",
    "integration_proposals",
    "trinity_check",
    "marketing_ideas",
    "invoice_status_lookup",
    "pending_approval_lookup",
    "schedule_lookup",
    "approval_explainer",
    "capability_query",
    "markdown_reorg_request",
    "file_context_request",
    "read_model_refresh_request",
    "report_bridge_request",
    "safety_review_request",
    "communication_summary_request",
    "music_project_request",
    "project_capsule_request",
    "status_orientation_request",
    "unknown_review",
}
INTENT_STATUSES = {"routed", "needs_operator_review", "rejected"}
ACTION_INTENT_CATEGORIES = {
    "invoice_send",
    "email_send",
    "sms_send",
    "phone_log",
    "calendar_create",
    "ledger_mutation",
    "coupa_submit",
    "obs_launch",
    "livestream_setup",
}
READ_ONLY_INTENT_CATEGORIES = {
    "invoice_status_lookup",
    "pending_approval_lookup",
    "schedule_lookup",
    "communication_summary_request",
    "status_orientation_request",
    "safety_review_request",
    "approval_explainer",
    "capability_query",
    "gig_intake",
    "musiclaw_query",
    "publishing_query",
    "cpa_query",
    "financial_report",
    "analytics_report",
    "goals_check",
    "momentum_check",
    "reflection_report",
    "system_report",
    "calendar_query",
    "brand_guide",
    "content_calendar",
    "scout_report",
    "phone_assist",
    "backup_status",
    "album_request",
    "brainstorm_status",
    "queue_status",
    "integration_proposals",
    "trinity_check",
    "marketing_ideas",
}
ROUTER_CANDIDATE_ACTION_TYPES = set(ALLOWED_ACTIONS) | ACTION_INTENT_CATEGORIES

NO_AUTHORITY_FLAGS = {
    "agent_activation_allowed": False,
    "direct_execution_allowed": False,
    "approval_bypass_allowed": False,
    "action_auto_create_allowed": False,
    "action_auto_approve_allowed": False,
    "action_auto_execute_allowed": False,
    "no_go_raw_access_allowed": False,
    "network_authority": False,
    "tool_execution_allowed": False,
    "model_execution_allowed": False,
    "runtime_authority": False,
    "client_deployment_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
}

AGENT_PHRASES = {
    "chief": "chief",
    "cassandra": "cassandra",
    "guardian": "guardian",
    "niles": "niles",
    "hermes": "hermes",
    "report bridge": "report_bridge",
    "report_bridge": "report_bridge",
    "node uplink": "report_bridge",
    "producer": "niles",
    "creative file resolver": "niles",
}


@dataclass(frozen=True)
class IntentRouteResult:
    intent_id: str
    run_id: str
    source_kind: str
    routed_agent_id: str | None
    routed_lane_id: str | None
    world_hint: str
    intent_category: str
    confidence: float
    status: str
    next_safe_move: str
    candidate_action_type: str | None
    approval_required: bool
    execution_allowed: bool
    action_request_created: bool
    context_link_count: int
    rejection_reason: str | None


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


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _phrase_text(text: str) -> str:
    return re.sub(r"[^a-z0-9_]+", " ", text.lower()).strip()


def _contains_phrase(phrase_text: str, phrase: str) -> bool:
    phrase = phrase.lower().replace("_", " ")
    return re.search(rf"(^|\s){re.escape(phrase)}($|\s)", phrase_text.replace("_", " ")) is not None


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _preview(text: str) -> str:
    normalized = _normalize_text(text)
    if len(normalized) <= MAX_PREVIEW_CHARS:
        return normalized
    return normalized[: MAX_PREVIEW_CHARS - 3].rstrip() + "..."


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS intent_router_runs (
  run_id TEXT PRIMARY KEY,
  router_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  source_kind TEXT NOT NULL,
  source_channel TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  intent_count INTEGER NOT NULL DEFAULT 0,
  routed_count INTEGER NOT NULL DEFAULT 0,
  needs_review_count INTEGER NOT NULL DEFAULT 0,
  rejected_count INTEGER NOT NULL DEFAULT 0,
  raw_text_stored INTEGER NOT NULL DEFAULT 0,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  direct_execution_allowed INTEGER NOT NULL DEFAULT 0,
  approval_bypass_allowed INTEGER NOT NULL DEFAULT 0,
  action_auto_create_allowed INTEGER NOT NULL DEFAULT 0,
  action_auto_approve_allowed INTEGER NOT NULL DEFAULT 0,
  action_auto_execute_allowed INTEGER NOT NULL DEFAULT 0,
  no_go_raw_access_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  model_execution_allowed INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  client_deployment_allowed INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS intent_records (
  intent_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_channel TEXT NOT NULL,
  source_message_id TEXT,
  source_user_label TEXT,
  requested_by TEXT NOT NULL,
  raw_text_hash TEXT NOT NULL,
  raw_text_stored INTEGER NOT NULL DEFAULT 0,
  intent_text_preview TEXT NOT NULL,
  created_at TEXT NOT NULL,
  routed_agent_id TEXT,
  routed_lane_id TEXT,
  world_hint TEXT NOT NULL,
  intent_category TEXT NOT NULL,
  confidence REAL NOT NULL,
  approval_required INTEGER NOT NULL DEFAULT 1,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  action_request_created INTEGER NOT NULL DEFAULT 0,
  candidate_action_type TEXT,
  next_safe_move TEXT NOT NULL,
  status TEXT NOT NULL,
  routing_reason TEXT NOT NULL,
  rejection_reason TEXT,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  direct_execution_allowed INTEGER NOT NULL DEFAULT 0,
  approval_bypass_allowed INTEGER NOT NULL DEFAULT 0,
  no_go_raw_access_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  model_execution_allowed INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  client_deployment_allowed INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (run_id) REFERENCES intent_router_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS intent_route_candidates (
  candidate_id TEXT PRIMARY KEY,
  intent_id TEXT NOT NULL,
  agent_id TEXT,
  lane_id TEXT,
  intent_category TEXT NOT NULL,
  world_hint TEXT NOT NULL,
  confidence REAL NOT NULL,
  selected INTEGER NOT NULL DEFAULT 0,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (intent_id) REFERENCES intent_records(intent_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS intent_context_links (
  context_link_id TEXT PRIMARY KEY,
  intent_id TEXT NOT NULL,
  link_kind TEXT NOT NULL,
  source_table TEXT NOT NULL,
  source_id TEXT,
  source_path TEXT,
  summary TEXT NOT NULL,
  raw_content_read INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (intent_id) REFERENCES intent_records(intent_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS intent_plan_proposals (
  proposal_id TEXT PRIMARY KEY,
  intent_id TEXT NOT NULL,
  proposed_next_safe_move TEXT NOT NULL,
  candidate_action_type TEXT,
  approval_required INTEGER NOT NULL DEFAULT 1,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  action_request_created INTEGER NOT NULL DEFAULT 0,
  truth_promotion_claimed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (intent_id) REFERENCES intent_records(intent_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS intent_router_rejections (
  rejection_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  intent_id TEXT,
  source_kind TEXT NOT NULL,
  rejection_reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES intent_router_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS intent_router_receipts (
  receipt_id TEXT PRIMARY KEY,
  intent_id TEXT NOT NULL,
  receipt_type TEXT NOT NULL,
  summary TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  action_request_created INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (intent_id) REFERENCES intent_records(intent_id) ON DELETE CASCADE
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_intent_records_status ON intent_records(status)",
        "CREATE INDEX IF NOT EXISTS idx_intent_records_agent ON intent_records(routed_agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_intent_records_category ON intent_records(intent_category)",
        "CREATE INDEX IF NOT EXISTS idx_intent_records_source ON intent_records(source_kind)",
    )


def _ensure_agent_registry_rows(db_path: str | Path) -> None:
    init_agent_lane_registry_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM agent_lanes").fetchone()[0]
    finally:
        conn.close()
    if count == 0:
        seed_agent_lane_registry(db_path=db_path)


def init_intent_router_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    parent = Path(path).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            init_business_ops_ledger(path)
            _ensure_agent_registry_rows(path)
            init_operator_action_schema(path)
            init_recent_file_context_schema(path)
            conn = sqlite3.connect(path)
            try:
                for statement in _sql_statements():
                    conn.execute(statement)
                conn.commit()
            finally:
                conn.close()
            return path
        except sqlite3.DatabaseError as exc:
            if attempt >= 2 or not is_transient_sqlite_write_error(exc) or not reset_disposable_sqlite_path(path):
                raise
    return path


def intent_router_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_intent_router_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'intent_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _agent_registry(conn: sqlite3.Connection) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    conn.row_factory = sqlite3.Row
    agents = {
        row["agent_id"]: dict(row)
        for row in conn.execute("SELECT * FROM agent_lanes ORDER BY agent_id").fetchall()
    }
    worlds: dict[str, list[str]] = {}
    for row in conn.execute("SELECT agent_id, world_binding FROM agent_lane_worlds ORDER BY world_binding"):
        worlds.setdefault(row["agent_id"], []).append(row["world_binding"])
    sources: dict[str, list[str]] = {}
    for row in conn.execute("SELECT agent_id, source_kind FROM agent_lane_source_kinds ORDER BY source_kind"):
        sources.setdefault(row["agent_id"], []).append(row["source_kind"])
    aliases = {
        row["alias"].lower(): row["agent_id"]
        for row in conn.execute("SELECT alias, agent_id FROM agent_lane_aliases").fetchall()
    }
    for agent_id, row in agents.items():
        row["allowed_worlds"] = worlds.get(agent_id, [])
        row["source_kinds"] = sources.get(agent_id, [])
    return agents, aliases


def _detect_agent(phrase_text: str, aliases: dict[str, str]) -> tuple[str | None, str | None]:
    phrase_map = dict(AGENT_PHRASES)
    phrase_map.update({alias: agent_id for alias, agent_id in aliases.items()})
    matches: list[tuple[int, int, str, str]] = []
    searchable = " " + phrase_text.replace("_", " ") + " "
    for phrase, agent_id in phrase_map.items():
        normalized_phrase = phrase.lower().replace("_", " ")
        match = re.search(rf"(^|\s){re.escape(normalized_phrase)}($|\s)", searchable)
        if match:
            matches.append((match.start(), -len(normalized_phrase), agent_id, phrase))
    if not matches:
        return None, None
    _position, _length, agent_id, phrase = sorted(matches)[0]
    return agent_id, phrase


def _orbit_read_only_category_for_text(phrase_text: str) -> tuple[str, str] | None:
    has = lambda *phrases: any(_contains_phrase(phrase_text, phrase) for phrase in phrases)
    contains = lambda *needles: any(needle in phrase_text for needle in needles)

    if has("music law", "legal question", "my rights", "ten fingers", "log rhythm", "log rhythm records", "music contract", "sync license", "copyright", "royalty dispute") or contains("publishing rights", "master rights", "work for hire"):
        return "musiclaw_query", "music-law read-only brain wording matched"
    if has("publishing status", "catalog status", "sync opportunities", "sync ready", "song rights", "pro registration", "ascap", "bmi") or contains("publishing catalog", "what songs are registered"):
        return "publishing_query", "publishing read-only brain wording matched"
    if (
        has("what did i make", "income this month", "income summary", "what do i owe", "quarterly tax", "estimated tax", "tax estimate", "what can i deduct", "deductions", "write off", "write-off", "quarterly", "cpa", "tax owed")
        and not has("log expense", "add expense", "i spent", "i paid for", "expense")
    ):
        return "cpa_query", "CPA read-only brain wording matched"
    if has("financial report", "profit and loss", "outstanding invoices", "who owes me", "unpaid invoices", "payment history", "revenue this month", "quarterly projection", "tax projection", "financial summary", "income report", "how's business", "hows business") or contains("p&l"):
        return "financial_report", "financial read-only brain wording matched"
    if has("analytics", "weekly metrics", "metrics report", "show analytics", "business report"):
        return "analytics_report", "analytics read-only brain wording matched"
    if (
        has("goals", "goal check", "how am i doing", "goal progress", "check in", "goal tracker")
        and not has("update goal", "set goal", "milestone goal")
    ):
        return "goals_check", "goals read-only brain wording matched"
    if has("momentum", "am i on track", "activity check", "how active am i", "artist mode", "admin mode", "am i in artist", "am i in admin", "momentum report"):
        return "momentum_check", "momentum read-only brain wording matched"
    if has("reflection report", "monthly report", "what's working", "whats working", "usage report", "system reflection", "how are things going", "assess the system", "how is the system doing"):
        return "reflection_report", "reflection read-only brain wording matched"
    if has("system report", "daily report", "what ran today", "status report", "worker report", "watcher report", "what happened today", "how is the system"):
        return "system_report", "reporter read-only brain wording matched"
    if has("what's my week", "whats my week", "what's today", "whats today", "what's coming up", "whats coming up", "what do i have", "my week", "this week", "upcoming events", "what's happening") or (contains("calendar", "schedule") and has("what is on", "what's on", "whats on", "show me")):
        return "calendar_query", "calendar read-only brain wording matched"
    if has("brand guide", "style guide", "brand rules", "is this on brand", "on brand check", "brand check", "dpr brand", "fundo brand guide"):
        return "brand_guide", "brand read-only brain wording matched"
    if (
        has("content calendar", "content schedule", "what's due for posting", "whats due for posting", "content status", "posting schedule", "what needs to go up")
        and not has("mark posted", "schedule post")
    ):
        return "content_calendar", "content read-only brain wording matched"
    if has("scout report", "what's new in ai", "whats new in ai", "tech digest", "research report", "new tools", "ai tools", "new in ai", "what's new in tech", "whats new in tech", "music tech", "new platforms"):
        return "scout_report", "scout read-only brain wording matched"
    if has("call script", "talking points", "what should i say to", "how should i approach", "script for calling", "call log", "call history", "recent calls", "show calls"):
        return "phone_assist", "phone read-only brain wording matched"
    if (
        has("backup status", "check backup", "git status", "is the repo current", "repo status")
        and not has("backup now", "push backup", "do backup", "backup push")
    ):
        return "backup_status", "backup read-only brain wording matched"
    if has("album status", "session status", "album arc", "album story", "track order", "lyric arc", "album analysis", "song order", "mix brief", "mix status", "mix ready"):
        return "album_request", "album read-only brain wording matched"
    if has("brainstorm status", "brainstorm watch", "brainstorm check", "watching ideas", "idea list", "brainstorm queue", "brainstorm backlog", "show ideas"):
        return "brainstorm_status", "brainstorm read-only brain wording matched"
    if has("queue status", "what's queued", "what s queued", "whats queued", "show queue", "pending queue", "done queue"):
        return "queue_status", "queue read-only brain wording matched"
    if (
        has("integration proposal", "integration proposals", "what can we add", "what can i add", "proposals", "propose")
        and not has("approve prop", "reject prop")
    ):
        return "integration_proposals", "integration read-only brain wording matched"
    if has("trinity check", "system audit", "brain audit", "trinity status", "trinity report", "check trinities", "what's missing", "queue gaps"):
        return "trinity_check", "trinity read-only brain wording matched"
    if (
        has("marketing", "content idea", "content ideas", "what should i post", "what can i post", "what can i make", "post about", "reel", "tiktok", "instagram", "youtube", "social media", "what to post", "marketing idea")
        and not has("log that", "i posted", "mark as posted", "schedule post", "draft a caption", "draft a hook", "write a caption", "write a hook")
    ):
        return "marketing_ideas", "marketing read-only brain wording matched"
    return None


def _category_for_text(phrase_text: str, explicit_agent_id: str | None) -> tuple[str, str]:
    has = lambda *phrases: any(_contains_phrase(phrase_text, phrase) for phrase in phrases)
    contains = lambda *needles: any(needle in phrase_text for needle in needles)
    asks_status = contains("did ", "what happened", "status", "go out", "went out", "sent yet", "already sent")
    asks_pending = contains("pending", "waiting for approval", "needs approval", "approval card")
    asks_explain = contains("explain", "eli5", "like i am five", "like i'm five", "what does", "what is")
    actionish = has(
        "send",
        "submit",
        "create",
        "make",
        "add",
        "schedule",
        "update",
        "mark",
        "post",
        "launch",
        "start",
        "go live",
        "text",
        "email",
        "call",
    )

    if asks_explain and contains("pending_approval", "approval", "packet", "approval card", "checklist card"):
        return "approval_explainer", "approval explainer wording matched"
    if asks_pending or has("what is pending", "what's pending", "show pending"):
        return "pending_approval_lookup", "pending approval/status lookup wording matched"
    if (contains("invoice", "bill", "paid", "payment") and asks_status) or has("did the invoice thing go out"):
        return "invoice_status_lookup", "invoice/payment status lookup wording matched"
    if (
        has("content calendar", "content schedule", "what's due for posting", "whats due for posting", "content status", "posting schedule", "what needs to go up")
        and not has("mark posted", "schedule post")
    ):
        return "content_calendar", "content read-only brain wording matched"
    if has("what's my week", "whats my week", "what's today", "whats today", "what's coming up", "whats coming up", "what do i have", "my week", "this week", "upcoming events", "what's happening"):
        return "calendar_query", "calendar read-only brain wording matched"
    if (contains("calendar", "schedule", "today", "tomorrow", "meeting") and not actionish) or contains("what is on the schedule", "what's on the schedule"):
        return "schedule_lookup", "schedule lookup wording matched"
    if contains("what can you do", "can you", "are you able", "capability", "capabilities"):
        return "capability_query", "capability query wording matched"

    orbit_read_only = _orbit_read_only_category_for_text(phrase_text)
    if orbit_read_only:
        return orbit_read_only

    booking_phrase = has(
        "booked",
        "you are booked",
        "youre booked",
        "you're booked",
        "all set",
        "you are all set",
        "youre all set",
        "you're all set",
        "covering",
        "covering for",
    )
    venue_signal = contains("venue", "tavern", "hotel", "club", "bar", "restaurant", "reynolds")
    date_signal = bool(
        re.search(
            r"\b(20\d{2}|jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\b",
            phrase_text,
        )
    )
    time_signal = bool(re.search(r"\b\d{1,2}\s+\d{1,2}\s*(am|pm)\b|\b\d{1,2}\s*(am|pm)\b", phrase_text))
    money_signal = bool(re.search(r"\b\d{2,6}\b", phrase_text)) or contains("usd", "dollar", "fee", "pay", "paid")
    if booking_phrase and sum(bool(signal) for signal in (venue_signal, date_signal, time_signal, money_signal)) >= 3:
        return "gig_intake", "gig booking intake wording matched"

    if contains("coupa"):
        return "coupa_submit", "Coupa action wording matched"
    if contains("ledger") or has("mark paid", "mark as paid", "post to ledger", "touch the ledger"):
        return "ledger_mutation", "ledger/payment mutation wording matched"
    if contains("gmail", "email") and (has("send", "write", "draft", "create") or actionish):
        return "email_send", "email/Gmail action wording matched"
    if contains("invoice", "bill") and has("send", "issue", "deliver", "email", "send out", "bill"):
        return "invoice_send", "invoice send wording matched"
    if has("text", "sms", "message") and has("send", "text", "message"):
        return "sms_send", "SMS/text action wording matched"
    if has("call", "phone"):
        return "phone_log", "phone/call action wording matched"
    if contains("calendar", "event", "meeting") and has("make", "create", "add", "schedule"):
        return "calendar_create", "calendar event creation wording matched"
    if contains("obs"):
        return "obs_launch", "OBS launch wording matched"
    if has("go live", "live stream", "livestream", "set up the live stream"):
        return "livestream_setup", "livestream setup wording matched"

    if has("safe", "safety", "risk", "guardian") or contains("no go", "no_go", "secret", "credential"):
        return "safety_review_request", "safety/risk wording matched"
    if contains("markdown") or has("md docs", "docs") and has("organize", "reorg", "archive", "classify"):
        return "markdown_reorg_request", "Markdown/docs organization wording matched"
    if contains("logicx", "logic file", "logic session") or has("logic", "new file", "that new file", "that file", "audio file"):
        return "file_context_request", "file-context wording matched"
    if contains("read model", "read models", "read_model", "mirror", "shuttle") or has("refresh", "sync"):
        return "read_model_refresh_request", "read-model/mirror refresh wording matched"
    if contains("report package", "node uplink", "report bridge") or has("import report", "import package"):
        return "report_bridge_request", "report package / Report Bridge wording matched"
    if contains("project capsule", "client project", "project generator") or has("build for"):
        return "project_capsule_request", "project/client capsule wording matched"
    if explicit_agent_id == "niles" or contains("music", "mix", "song", "session"):
        return "music_project_request", "music/project wording matched"
    if explicit_agent_id == "cassandra" or contains("summarize", "summary", "what changed", "status explanation"):
        return "communication_summary_request", "summary/comms wording matched"
    if contains("status", "current state", "where are we", "orientation"):
        return "status_orientation_request", "status/orientation wording matched"
    return "unknown_review", "no deterministic intent category matched"


def _default_agent_for_category(category: str, phrase_text: str) -> tuple[str | None, str]:
    if category in {
        "invoice_send",
        "email_send",
        "sms_send",
        "phone_log",
        "calendar_create",
        "ledger_mutation",
        "coupa_submit",
        "invoice_status_lookup",
        "pending_approval_lookup",
        "schedule_lookup",
        "approval_explainer",
        "capability_query",
        "gig_intake",
    }:
        return "cassandra", f"default Cassandra route for {category}"
    if category in {"obs_launch", "livestream_setup"}:
        return "chief", f"default Chief route for {category}"
    if category in {
        "musiclaw_query",
        "publishing_query",
        "cpa_query",
        "financial_report",
        "analytics_report",
        "goals_check",
        "momentum_check",
        "reflection_report",
        "system_report",
        "calendar_query",
        "brand_guide",
        "content_calendar",
        "scout_report",
        "phone_assist",
        "backup_status",
        "album_request",
        "brainstorm_status",
        "queue_status",
        "integration_proposals",
        "trinity_check",
        "marketing_ideas",
    }:
        return "chief", f"default Chief route for {category}"
    if category in {"markdown_reorg_request", "read_model_refresh_request", "project_capsule_request", "status_orientation_request"}:
        return "chief", f"default Chief route for {category}"
    if category == "file_context_request":
        if "logic" in phrase_text or "audio" in phrase_text or "music" in phrase_text:
            return "niles", "file context mentions music/audio/Logic"
        return None, "file context is ambiguous without a lane cue"
    if category == "safety_review_request":
        return "guardian", "default Guardian route for safety review"
    if category == "communication_summary_request":
        return "cassandra", "default Cassandra route for summaries"
    if category == "report_bridge_request":
        return "report_bridge", "default Report Bridge route for report-package intake"
    if category == "music_project_request":
        return "niles", "default Niles route for music/art request"
    return None, "unknown category requires operator review"


def _world_for(agent_id: str | None, category: str) -> str:
    if category in {"invoice_send", "invoice_status_lookup", "ledger_mutation", "coupa_submit", "cpa_query", "financial_report"}:
        return "finance"
    if category in {"musiclaw_query", "publishing_query"}:
        return "business_development"
    if category in {"email_send", "sms_send", "phone_log", "calendar_create", "pending_approval_lookup", "schedule_lookup", "approval_explainer", "capability_query"}:
        return "communications"
    if category in {"calendar_query", "phone_assist"}:
        return "communications"
    if category == "gig_intake":
        return "business_development"
    if category in {"obs_launch", "livestream_setup", "analytics_report", "goals_check", "momentum_check", "reflection_report", "system_report", "scout_report", "backup_status", "brainstorm_status", "queue_status", "integration_proposals", "trinity_check"}:
        return "operations"
    if agent_id == "niles" or category in {"music_project_request", "file_context_request", "album_request", "brand_guide", "content_calendar", "marketing_ideas"}:
        return "music_art"
    if agent_id == "guardian" or category == "safety_review_request":
        return "security"
    if agent_id == "cassandra" or category == "communication_summary_request":
        return "communications"
    if agent_id == "report_bridge" or category == "report_bridge_request":
        return "operations"
    if category == "project_capsule_request":
        return "business_development"
    if category in {"markdown_reorg_request", "read_model_refresh_request", "status_orientation_request"}:
        return "operations"
    return "unknown"


def _candidate_action_for(category: str, phrase_text: str) -> str | None:
    if category in ACTION_INTENT_CATEGORIES:
        return category
    if category != "read_model_refresh_request":
        return None
    if "report bridge" in phrase_text:
        return "export_report_bridge_read_model"
    if "context" in phrase_text:
        return "export_context_selection_read_model"
    if "query" in phrase_text or "status" in phrase_text:
        return "query_generated_read_model_mirror"
    if "mirror" in phrase_text or "shuttle" in phrase_text or "sync" in phrase_text or "mac" in phrase_text:
        return "prepare_mac_read_model_shuttle"
    return "prepare_mac_read_model_shuttle"


def _next_safe_move(category: str, agent_id: str | None, candidate_action_type: str | None) -> str:
    if category in ACTION_INTENT_CATEGORIES:
        return (
            f"Prepare an approval card for `{category}`. Nothing has been sent yet; "
            "execution remains blocked until explicit operator approval."
        )
    if category == "invoice_status_lookup":
        return "Look up invoice/payment status from receipts and read models; do not create a new action packet."
    if category == "pending_approval_lookup":
        return "List pending approval cards and receipts; do not create a new action packet."
    if category == "schedule_lookup":
        return "Answer from available schedule context; do not create or modify calendar events."
    if category == "approval_explainer":
        return "Explain approval state in plain language; do not create a new action packet."
    if category == "capability_query":
        return "Explain current capabilities and boundaries in plain language; do not create a new action packet."
    if category == "gig_intake":
        return "Start a Cassandra gig-intake session, pre-fill extractable booking details, and ask only for missing confirmation fields. No send or invoice execution is allowed."
    if category in READ_ONLY_INTENT_CATEGORIES:
        return f"Route `{category}` through the existing read-only brain handler; do not create an action packet."
    if category == "markdown_reorg_request":
        return "Query Markdown Knowledge Atlas and draft an advisory reorg/archive plan; do not move files."
    if category == "file_context_request":
        return "Resolve recent file-event metadata and draft a metadata-only plan; do not open private/raw file bodies or edit files."
    if category == "safety_review_request":
        return "Run a metadata-only safety/no-go boundary review; do not read no-go raw content."
    if category == "communication_summary_request":
        return "Summarize generated read-model and status surfaces for the operator; do not send external messages."
    if category == "read_model_refresh_request":
        if candidate_action_type:
            return f"Prepare a candidate Operator Action request for `{candidate_action_type}`; approval is still required before execution."
        return "Identify the bounded read-model refresh action candidate; approval is still required before execution."
    if category == "report_bridge_request":
        return "Validate a sanitized Report Bridge package if supplied; do not accept raw client data or promote truth."
    if category == "music_project_request":
        return "Draft a music/art production checklist from metadata only; do not modify DAW sessions or media files."
    if category == "project_capsule_request":
        return "Draft or query a project capsule proposal without deployment, client data access, or tool execution."
    if category == "status_orientation_request":
        return "Use current generated read-models and handoff docs to produce an orientation summary."
    return "Ask the operator for a clearer target agent, file, world, or allowed action; do not execute anything."


def _approval_required_for(
    status: str,
    candidate_action_type: str | None,
    *,
    category: str | None = None,
    agent_id: str | None = None,
) -> bool:
    """Only cleanly routed, non-action requests may use the read-only fast path."""
    if agent_id == "guardian" or category == "safety_review_request":
        return True
    return status != "routed" or bool(candidate_action_type)


def _latest_recent_file_context_run(conn: sqlite3.Connection) -> str | None:
    try:
        row = conn.execute(
            """
SELECT run_id
FROM recent_file_context_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return row["run_id"] if row else None


def _query_type_for_phrase(phrase_text: str) -> tuple[str, str | None]:
    if "logic" in phrase_text or "logicx" in phrase_text:
        return "logic_project", "logic_project"
    if "markdown" in phrase_text or " md " in f" {phrase_text} ":
        return "markdown_doc", "markdown_doc"
    if "read model" in phrase_text or "read_model" in phrase_text:
        return "generated_read_model", "generated_read_model"
    if "report package" in phrase_text or "node uplink" in phrase_text or "report bridge" in phrase_text:
        return "report_bridge_package", "report_bridge_package"
    if "that new" in phrase_text or "new file" in phrase_text or "that file" in phrase_text:
        return "generic_recent_file", None
    return "unknown", None


def _recent_file_candidate_preview(conn: sqlite3.Connection, phrase_text: str) -> dict[str, Any] | None:
    run_id = _latest_recent_file_context_run(conn)
    if not run_id:
        return None
    _query_type, file_kind = _query_type_for_phrase(phrase_text)
    where = "run_id = ?"
    params: list[Any] = [run_id]
    if file_kind:
        where += " AND file_kind_hint = ?"
        params.append(file_kind)
    try:
        rows = conn.execute(
            f"""
SELECT *
FROM recent_file_candidates
WHERE {where}
ORDER BY observed_at DESC, confidence DESC, relative_path ASC
LIMIT 3
""".strip(),
            tuple(params),
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    safe_rows = [
        dict(row)
        for row in rows
        if not row["no_go_boundary"] and row["queue_status"] != "blocked_no_go"
    ]
    if len(safe_rows) != 1:
        return None
    return safe_rows[0]


def _recent_file_resolution_from_conn(
    conn: sqlite3.Connection,
    phrase_text: str,
) -> tuple[str, dict[str, Any] | None, int, str]:
    run_id = _latest_recent_file_context_run(conn)
    if not run_id:
        return "unresolved", None, 0, "no Recent File Context run exists"
    _query_type, file_kind = _query_type_for_phrase(phrase_text)
    where = "run_id = ?"
    params: list[Any] = [run_id]
    if file_kind:
        where += " AND file_kind_hint = ?"
        params.append(file_kind)
    try:
        rows = conn.execute(
            f"""
SELECT *
FROM recent_file_candidates
WHERE {where}
ORDER BY observed_at DESC, confidence DESC, relative_path ASC
LIMIT 10
""".strip(),
            tuple(params),
        ).fetchall()
    except sqlite3.OperationalError:
        return "unresolved", None, 0, "Recent File Context tables are unavailable"
    safe_rows = [
        dict(row)
        for row in rows
        if not row["no_go_boundary"] and row["queue_status"] != "blocked_no_go"
    ]
    blocked_rows = [
        dict(row)
        for row in rows
        if row["no_go_boundary"] or row["queue_status"] == "blocked_no_go"
    ]
    if not rows:
        return "unresolved", None, 0, "no recent file candidate matched the query"
    if blocked_rows and not safe_rows:
        return "blocked_no_go", blocked_rows[0], len(rows), "matching candidates are no-go/sensitive metadata only"
    if len(safe_rows) == 1:
        candidate = safe_rows[0]
        return (
            "resolved",
            candidate,
            len(rows),
            f"single recent {candidate['file_kind_hint']} candidate matched",
        )
    return "ambiguous", None, len(rows), f"{len(safe_rows)} recent candidates matched"


def _latest_markdown_context(conn: sqlite3.Connection) -> dict[str, Any] | None:
    try:
        run = conn.execute(
            """
SELECT run_id, document_count, completed_at, body_read, raw_body_stored
FROM markdown_atlas_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not run:
        return None
    counts = {
        row[0]: row[1]
        for row in conn.execute(
            """
SELECT reorg_status, COUNT(*)
FROM markdown_documents
WHERE run_id = ?
GROUP BY reorg_status
ORDER BY reorg_status
""".strip(),
            (run["run_id"],),
        ).fetchall()
    }
    return {
        "run_id": run["run_id"],
        "document_count": run["document_count"],
        "completed_at": run["completed_at"],
        "body_read": bool(run["body_read"]),
        "raw_body_stored": bool(run["raw_body_stored"]),
        "reorg_counts": counts,
    }


def _context_links_for(
    conn: sqlite3.Connection,
    *,
    intent_id: str,
    category: str,
    phrase_text: str,
    query_text: str,
    now: str,
) -> tuple[list[dict[str, Any]], bool]:
    links: list[dict[str, Any]] = []
    unresolved_file_reference = False
    file_reference_status: str | None = None

    if category == "markdown_reorg_request":
        context = _latest_markdown_context(conn)
        if context:
            links.append(
                {
                    "link_kind": "markdown_atlas_run",
                    "source_table": "markdown_atlas_runs",
                    "source_id": context["run_id"],
                    "source_path": None,
                    "summary": (
                        f"Markdown Atlas run {context['run_id']} has "
                        f"{context['document_count']} documents; reorg_counts={context['reorg_counts']}"
                    ),
                }
            )
        if "that new" in phrase_text or "new file" in phrase_text or "that file" in phrase_text:
            file_reference_status, candidate, _candidate_count, _reason = _recent_file_resolution_from_conn(
                conn,
                phrase_text,
            )
            if candidate:
                links.append(
                    {
                        "link_kind": "recent_file_context_candidate",
                        "source_table": "recent_file_candidates",
                        "source_id": candidate["candidate_id"],
                        "source_path": candidate["relative_path"],
                        "summary": (
                            f"Recent file context {file_reference_status}: "
                            f"{candidate['relative_path']} kind={candidate['file_kind_hint']} "
                            f"world={candidate['world_hint']} metadata_only={bool(candidate['metadata_only'])}"
                        ),
                    }
                )
            if file_reference_status in {"ambiguous", "unresolved", "blocked_no_go", "needs_operator_review"}:
                unresolved_file_reference = True
    elif category == "file_context_request":
        file_reference_status, candidate, _candidate_count, _reason = _recent_file_resolution_from_conn(
            conn,
            phrase_text,
        )
        if file_reference_status in {"ambiguous", "unresolved", "blocked_no_go", "needs_operator_review"}:
            unresolved_file_reference = True
        file_rows = [candidate] if candidate else []
        for row in file_rows:
            links.append(
                {
                    "link_kind": "recent_file_context_candidate",
                    "source_table": "recent_file_candidates",
                    "source_id": row["candidate_id"],
                    "source_path": row["relative_path"],
                    "summary": (
                        f"Recent file context {file_reference_status}: "
                        f"{row['relative_path']} kind={row['file_kind_hint']} "
                        f"world={row['world_hint']} metadata_only={bool(row['metadata_only'])}"
                    ),
                }
            )
    elif category == "read_model_refresh_request":
        links.append(
            {
                "link_kind": "allowed_action_catalog",
                "source_table": "operator_action_allowed_commands",
                "source_id": "operator_action_allowed_commands",
                "source_path": None,
                "summary": "Intent maps to an Operator Action candidate only; no action request was created.",
            }
        )

    for link in links:
        conn.execute(
            """
INSERT INTO intent_context_links (
  context_link_id, intent_id, link_kind, source_table, source_id,
  source_path, summary, raw_content_read, raw_body_stored, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
ON CONFLICT(context_link_id) DO UPDATE SET
  summary = excluded.summary,
  raw_content_read = 0,
  raw_body_stored = 0
""".strip(),
            (
                _row_id(
                    "irctx",
                    intent_id,
                    link["link_kind"],
                    link["source_table"],
                    link.get("source_id") or "",
                    link.get("source_path") or "",
                ),
                intent_id,
                link["link_kind"],
                link["source_table"],
                link.get("source_id"),
                link.get("source_path"),
                link["summary"],
                now,
            ),
        )
    return links, unresolved_file_reference


def route_operator_intent(
    *,
    text: str,
    source_kind: str,
    source_channel: str,
    requested_by: str,
    source_message_id: str | None = None,
    source_user_label: str | None = None,
    db_path: str | Path | None = None,
    intent_id: str | None = None,
    run_id: str | None = None,
) -> IntentRouteResult:
    normalized_text = _normalize_text(text)
    if not normalized_text:
        raise ValueError("intent text is required")
    source_kind = source_kind.strip()
    source_channel = source_channel.strip()
    requested_by = requested_by.strip()
    if source_kind not in SOURCE_KINDS:
        raise ValueError(f"unsupported source_kind: {source_kind}")
    if not source_channel:
        raise ValueError("source_channel is required")
    if not requested_by:
        raise ValueError("requested_by is required")

    path = init_intent_router_schema(db_path)
    now = utc_now()
    text_hash = _text_hash(normalized_text)
    resolved_run_id = run_id or _row_id("irun", source_kind, source_channel, requested_by, text_hash, now)
    resolved_intent_id = intent_id or _row_id("intent", source_kind, source_channel, requested_by, text_hash, now)
    phrase_text = _phrase_text(normalized_text)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        agents, aliases = _agent_registry(conn)
        explicit_agent_id, agent_token = _detect_agent(phrase_text, aliases)
        category, category_reason = _category_for_text(phrase_text, explicit_agent_id)
        inferred_agent_id, inferred_reason = _default_agent_for_category(category, phrase_text)
        routed_agent_id = explicit_agent_id or inferred_agent_id
        routing_reason = (
            f"explicit_agent={agent_token} matched; {category_reason}"
            if explicit_agent_id
            else f"{inferred_reason}; {category_reason}"
        )
        if category == "file_context_request" and routed_agent_id is None:
            recent_preview = _recent_file_candidate_preview(conn, phrase_text)
            if recent_preview:
                if recent_preview["file_kind_hint"] == "logic_project" or recent_preview["world_hint"] == "music_art":
                    routed_agent_id = "niles"
                    routing_reason += "; Recent File Context resolved music/Logic metadata, routing to Niles"
                elif recent_preview["file_kind_hint"] == "markdown_doc":
                    routed_agent_id = "chief"
                    routing_reason += "; Recent File Context resolved Markdown metadata, routing to Chief"
                elif recent_preview["file_kind_hint"] == "report_bridge_package":
                    routed_agent_id = "report_bridge"
                    routing_reason += "; Recent File Context resolved Report Bridge package metadata"
                elif recent_preview["file_kind_hint"] == "generated_read_model":
                    routed_agent_id = "chief"
                    routing_reason += "; Recent File Context resolved generated read-model metadata, routing to Chief"
        candidate_action_type = _candidate_action_for(category, phrase_text)
        if candidate_action_type not in ROUTER_CANDIDATE_ACTION_TYPES:
            candidate_action_type = None
        world_hint = _world_for(routed_agent_id, category)
        routed_lane_id = agents.get(routed_agent_id, {}).get("lane_id") if routed_agent_id else None
        confidence = 0.9 if explicit_agent_id and category != "unknown_review" else 0.75
        if category == "unknown_review" or routed_agent_id is None:
            confidence = 0.3

        rejection_reason: str | None = None
        status = "routed"
        if routed_agent_id is None:
            status = "needs_operator_review"
            routing_reason += "; no safe deterministic agent/lane could be inferred"
        elif routed_agent_id not in agents:
            status = "rejected"
            rejection_reason = f"routed agent is not present in Agent Lane Registry: {routed_agent_id}"
        elif any(
            bool(agents[routed_agent_id].get(flag))
            for flag in (
                "can_execute",
                "can_bypass_approval",
                "can_read_no_go_raw",
                "can_call_network",
                "can_run_tools",
                "can_call_models",
                "runtime_authority",
                "client_deployment_authority",
            )
        ):
            status = "rejected"
            rejection_reason = f"routed agent has unsafe authority flags: {routed_agent_id}"
        elif source_kind == "unknown" or source_kind not in agents[routed_agent_id].get("source_kinds", []):
            status = "needs_operator_review"
            routing_reason += "; source_kind needs operator review for this route"
        elif category == "unknown_review":
            status = "needs_operator_review"
            routing_reason += "; intent category is unknown_review"

        conn.execute(
            """
INSERT INTO intent_router_runs (
  run_id, router_version, created_at, source_kind, source_channel,
  requested_by, notes
) VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
  source_kind = excluded.source_kind,
  source_channel = excluded.source_channel,
  requested_by = excluded.requested_by,
  raw_text_stored = 0,
  execution_allowed = 0,
  agent_activation_allowed = 0,
  direct_execution_allowed = 0,
  approval_bypass_allowed = 0,
  action_auto_create_allowed = 0,
  action_auto_approve_allowed = 0,
  action_auto_execute_allowed = 0,
  no_go_raw_access_allowed = 0,
  network_authority = 0,
  tool_execution_allowed = 0,
  model_execution_allowed = 0,
  runtime_authority = 0,
  client_deployment_allowed = 0,
  file_move_allowed = 0,
  file_delete_allowed = 0,
  notes = excluded.notes
""".strip(),
            (
                resolved_run_id,
                INTENT_ROUTER_VERSION,
                now,
                source_kind,
                source_channel,
                requested_by,
                "Deterministic routing only; no execution, approval, model call, or agent activation.",
            ),
        )

        next_safe_move = _next_safe_move(category, routed_agent_id, candidate_action_type)
        approval_required = _approval_required_for(
            status,
            candidate_action_type,
            category=category,
            agent_id=routed_agent_id,
        )
        conn.execute(
            """
INSERT INTO intent_records (
  intent_id, run_id, source_kind, source_channel, source_message_id,
  source_user_label, requested_by, raw_text_hash, raw_text_stored,
  intent_text_preview, created_at, routed_agent_id, routed_lane_id,
  world_hint, intent_category, confidence, approval_required,
  execution_allowed, action_request_created, candidate_action_type,
  next_safe_move, status, routing_reason, rejection_reason
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?)
ON CONFLICT(intent_id) DO UPDATE SET
  run_id = excluded.run_id,
  source_kind = excluded.source_kind,
  source_channel = excluded.source_channel,
  source_message_id = excluded.source_message_id,
  source_user_label = excluded.source_user_label,
  requested_by = excluded.requested_by,
  raw_text_hash = excluded.raw_text_hash,
  raw_text_stored = 0,
  intent_text_preview = excluded.intent_text_preview,
  routed_agent_id = excluded.routed_agent_id,
  routed_lane_id = excluded.routed_lane_id,
  world_hint = excluded.world_hint,
  intent_category = excluded.intent_category,
  confidence = excluded.confidence,
  approval_required = excluded.approval_required,
  execution_allowed = 0,
  action_request_created = 0,
  candidate_action_type = excluded.candidate_action_type,
  next_safe_move = excluded.next_safe_move,
  status = excluded.status,
  routing_reason = excluded.routing_reason,
  rejection_reason = excluded.rejection_reason,
  agent_activation_allowed = 0,
  direct_execution_allowed = 0,
  approval_bypass_allowed = 0,
  no_go_raw_access_allowed = 0,
  network_authority = 0,
  tool_execution_allowed = 0,
  model_execution_allowed = 0,
  runtime_authority = 0,
  client_deployment_allowed = 0,
  file_move_allowed = 0,
  file_delete_allowed = 0
""".strip(),
            (
                resolved_intent_id,
                resolved_run_id,
                source_kind,
                source_channel,
                source_message_id,
                source_user_label,
                requested_by,
                text_hash,
                _preview(normalized_text),
                now,
                routed_agent_id,
                routed_lane_id,
                world_hint,
                category,
                confidence,
                1 if approval_required else 0,
                candidate_action_type,
                next_safe_move,
                status,
                routing_reason,
                rejection_reason,
            ),
        )

        conn.execute(
            """
INSERT INTO intent_route_candidates (
  candidate_id, intent_id, agent_id, lane_id, intent_category, world_hint,
  confidence, selected, reason, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(candidate_id) DO UPDATE SET
  confidence = excluded.confidence,
  selected = excluded.selected,
  reason = excluded.reason
""".strip(),
            (
                _row_id("ircand", resolved_intent_id, routed_agent_id or "none", category),
                resolved_intent_id,
                routed_agent_id,
                routed_lane_id,
                category,
                world_hint,
                confidence,
                1 if status in {"routed", "needs_operator_review"} and routed_agent_id else 0,
                routing_reason,
                now,
            ),
        )

        links, unresolved_file_reference = _context_links_for(
            conn,
            intent_id=resolved_intent_id,
            category=category,
            phrase_text=phrase_text,
            query_text=normalized_text,
            now=now,
        )
        if unresolved_file_reference and status != "rejected":
            status = "needs_operator_review"
            routing_reason += "; file reference is unresolved in recent File Event Queue metadata"
            next_safe_move = _next_safe_move(category, routed_agent_id, candidate_action_type)
            approval_required = _approval_required_for(
                status,
                candidate_action_type,
                category=category,
                agent_id=routed_agent_id,
            )
            conn.execute(
                """
UPDATE intent_records
SET status = ?, routing_reason = ?, next_safe_move = ?, confidence = MIN(confidence, 0.55),
    approval_required = ?
WHERE intent_id = ?
""".strip(),
                (status, routing_reason, next_safe_move, 1 if approval_required else 0, resolved_intent_id),
            )

        conn.execute(
            """
INSERT INTO intent_plan_proposals (
  proposal_id, intent_id, proposed_next_safe_move, candidate_action_type,
  approval_required, execution_allowed, action_request_created,
  truth_promotion_claimed, created_at
) VALUES (?, ?, ?, ?, ?, 0, 0, 0, ?)
ON CONFLICT(proposal_id) DO UPDATE SET
  proposed_next_safe_move = excluded.proposed_next_safe_move,
  candidate_action_type = excluded.candidate_action_type,
  approval_required = excluded.approval_required,
  execution_allowed = 0,
  action_request_created = 0,
  truth_promotion_claimed = 0
""".strip(),
            (
                _row_id("irplan", resolved_intent_id),
                resolved_intent_id,
                next_safe_move,
                candidate_action_type,
                1 if approval_required else 0,
                now,
            ),
        )

        if status == "rejected":
            conn.execute(
                """
INSERT INTO intent_router_rejections (
  rejection_id, run_id, intent_id, source_kind, rejection_reason, created_at
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(rejection_id) DO NOTHING
""".strip(),
                (
                    _row_id("irrej", resolved_run_id, resolved_intent_id, rejection_reason or "rejected"),
                    resolved_run_id,
                    resolved_intent_id,
                    source_kind,
                    rejection_reason or "rejected",
                    now,
                ),
            )

        receipt_summary = (
            f"Intent routed to {routed_agent_id}/{routed_lane_id} as {category}."
            if status == "routed"
            else f"Intent requires review: {routing_reason}."
            if status == "needs_operator_review"
            else f"Intent rejected: {rejection_reason}."
        )
        conn.execute(
            """
INSERT INTO intent_router_receipts (
  receipt_id, intent_id, receipt_type, summary, payload_json, created_at,
  execution_allowed, action_request_created, agent_activation_allowed,
  runtime_authority
) VALUES (?, ?, 'routing_receipt', ?, ?, ?, 0, 0, 0, 0)
ON CONFLICT(receipt_id) DO UPDATE SET
  summary = excluded.summary,
  payload_json = excluded.payload_json,
  execution_allowed = 0,
  action_request_created = 0,
  agent_activation_allowed = 0,
  runtime_authority = 0
""".strip(),
            (
                _row_id("irreceipt", resolved_intent_id),
                resolved_intent_id,
                receipt_summary,
                stable_json(
                    {
                        "intent_id": resolved_intent_id,
                        "status": status,
                        "routed_agent_id": routed_agent_id,
                        "routed_lane_id": routed_lane_id,
                        "intent_category": category,
                        "candidate_action_type": candidate_action_type,
                        "context_link_count": len(links),
                        **NO_AUTHORITY_FLAGS,
                    }
                ),
                now,
            ),
        )

        counts = {
            row["status"]: row["count"]
            for row in conn.execute(
                "SELECT status, COUNT(*) AS count FROM intent_records WHERE run_id = ? GROUP BY status",
                (resolved_run_id,),
            ).fetchall()
        }
        conn.execute(
            """
UPDATE intent_router_runs
SET completed_at = ?,
    intent_count = ?,
    routed_count = ?,
    needs_review_count = ?,
    rejected_count = ?
WHERE run_id = ?
""".strip(),
            (
                utc_now(),
                sum(counts.values()),
                counts.get("routed", 0),
                counts.get("needs_operator_review", 0),
                counts.get("rejected", 0),
                resolved_run_id,
            ),
        )
        conn.commit()
        final = conn.execute(
            "SELECT status, confidence, routing_reason FROM intent_records WHERE intent_id = ?",
            (resolved_intent_id,),
        ).fetchone()
        return IntentRouteResult(
            intent_id=resolved_intent_id,
            run_id=resolved_run_id,
            source_kind=source_kind,
            routed_agent_id=routed_agent_id,
            routed_lane_id=routed_lane_id,
            world_hint=world_hint,
            intent_category=category,
            confidence=float(final["confidence"]),
            status=final["status"],
            next_safe_move=next_safe_move,
            candidate_action_type=candidate_action_type,
            approval_required=approval_required,
            execution_allowed=False,
            action_request_created=False,
            context_link_count=len(links),
            rejection_reason=rejection_reason,
        )
    finally:
        conn.close()


REPORT_SECTIONS = {"summary", "latest", "by-agent", "needs-review"}


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _safe_intent_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "intent_id": row["intent_id"],
        "source_kind": row["source_kind"],
        "source_channel": row["source_channel"],
        "requested_by": row["requested_by"],
        "intent_text_preview": row["intent_text_preview"],
        "raw_text_stored": bool(row["raw_text_stored"]),
        "routed_agent_id": row["routed_agent_id"],
        "routed_lane_id": row["routed_lane_id"],
        "world_hint": row["world_hint"],
        "intent_category": row["intent_category"],
        "confidence": row["confidence"],
        "status": row["status"],
        "approval_required": bool(row["approval_required"]),
        "execution_allowed": bool(row["execution_allowed"]),
        "action_request_created": bool(row["action_request_created"]),
        "candidate_action_type": row["candidate_action_type"],
        "next_safe_move": row["next_safe_move"],
        "created_at": row["created_at"],
    }


def build_intent_router_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
    agent: str | None = None,
) -> dict[str, Any]:
    if report not in REPORT_SECTIONS:
        raise ValueError(f"unknown intent router report: {report}")
    path = init_intent_router_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = _dict_rows(conn, "SELECT * FROM intent_records ORDER BY created_at DESC, intent_id DESC")
        if report == "latest":
            items = rows[:1]
        elif report == "needs-review":
            items = [row for row in rows if row["status"] == "needs_operator_review"]
        elif report == "by-agent":
            if not agent:
                raise ValueError("--agent is required for by-agent report")
            normalized = agent.strip().lower().replace(" ", "_")
            items = [row for row in rows if row["routed_agent_id"] == normalized]
        else:
            items = rows[:10]
        status_counts = Counter(row["status"] for row in rows)
        agent_counts = Counter(row["routed_agent_id"] or "unrouted" for row in rows)
        category_counts = Counter(row["intent_category"] for row in rows)
        source_counts = Counter(row["source_kind"] for row in rows)
        latest = rows[0] if rows else None
        context_counts = {
            row["link_kind"]: row["count"]
            for row in conn.execute(
                """
SELECT link_kind, COUNT(*) AS count
FROM intent_context_links
GROUP BY link_kind
ORDER BY link_kind
""".strip()
            ).fetchall()
        }
        latest_context_links = (
            _dict_rows(
                conn,
                """
SELECT link_kind, source_table, source_id, source_path, summary,
       raw_content_read, raw_body_stored, created_at
FROM intent_context_links
WHERE intent_id = ?
ORDER BY created_at DESC, link_kind, source_path
LIMIT 10
""".strip(),
                (latest["intent_id"],),
            )
            if latest
            else []
        )
        return {
            "status": "ok",
            "report": report,
            "db_path": str(path),
            "counts": {
                "total_intents": len(rows),
                "routed": status_counts.get("routed", 0),
                "needs_operator_review": status_counts.get("needs_operator_review", 0),
                "rejected": status_counts.get("rejected", 0),
                "by_agent": dict(sorted(agent_counts.items())),
                "by_category": dict(sorted(category_counts.items())),
                "by_source_kind": dict(sorted(source_counts.items())),
                "by_context_link_kind": dict(sorted(context_counts.items())),
            },
            "latest_intent": _safe_intent_summary(latest),
            "latest_context_links": latest_context_links,
            "items": [_safe_intent_summary(row) for row in items],
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def _counts_line(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def format_intent_router_report(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    lines = [
        f"Intent Router v0 - {payload['report']}",
        "",
        f"Total intents: {counts['total_intents']}",
        f"Routed: {counts['routed']}",
        f"Needs review: {counts['needs_operator_review']}",
        f"Rejected: {counts['rejected']}",
        f"By agent: {_counts_line(counts['by_agent'])}",
        f"By category: {_counts_line(counts['by_category'])}",
        f"By source: {_counts_line(counts['by_source_kind'])}",
        f"By context link: {_counts_line(counts.get('by_context_link_kind', {}))}",
        "",
        "Items:",
    ]
    for item in payload.get("items") or []:
        lines.append(
            f"- `{item['intent_id']}`: {item['status']} -> "
            f"{item['routed_agent_id'] or 'unrouted'}/{item['routed_lane_id'] or 'none'}; "
            f"category={item['intent_category']}; world={item['world_hint']}; "
            f"candidate_action={item['candidate_action_type'] or 'none'}"
        )
    if not payload.get("items"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Deterministic routing only; no agent activation, model calls, tool execution, approval bypass, action auto-create, action auto-approve, or action auto-execute.",
            "- Context links are metadata-only and do not read no-go raw content or move/delete files.",
        ]
    )
    return "\n".join(lines)


def build_intent_router_read_model(
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    report = build_intent_router_report(db_path=db_path, report="summary")
    path = report["db_path"]
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        latest_run = conn.execute(
            """
SELECT *
FROM intent_router_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
        ).fetchone()
        latest_time = (
            latest_run["completed_at"]
            if latest_run
            else report["latest_intent"]["created_at"]
            if report["latest_intent"]
            else "not_available_no_intents"
        )
        return {
            "schema_version": READ_MODEL_VERSION,
            "read_model_version": READ_MODEL_VERSION,
            "mode": "deterministic_intent_routing_posture_only",
            "generated_at": latest_time,
            "source_ledger_path": _display_path(path),
            "source_ledger_namespace": "intent_router_*",
            "latest_run_id": latest_run["run_id"] if latest_run else None,
            "total_intents": report["counts"]["total_intents"],
            "routed_count": report["counts"]["routed"],
            "needs_review_count": report["counts"]["needs_operator_review"],
            "rejected_count": report["counts"]["rejected"],
            "latest_intent": report["latest_intent"],
            "counts_by_agent": report["counts"]["by_agent"],
            "counts_by_category": report["counts"]["by_category"],
            "counts_by_source_kind": report["counts"]["by_source_kind"],
            "counts_by_context_link_kind": report["counts"].get("by_context_link_kind", {}),
            "latest_context_links": report.get("latest_context_links", []),
            "available_source_kinds": sorted(SOURCE_KINDS),
            "routing_rules_summary": {
                "explicit_agent_names": sorted(AGENT_PHRASES),
                "producer_alias_routes_to": "niles",
                "markdown_requests": "chief/system_orchestration with advisory-only reorg next step",
                "logic_or_music_file_requests": "niles/music_art_production with metadata-only Recent File Context links",
                "safety_requests": "guardian/safety_security",
                "summary_requests": "cassandra/operator_comms",
                "report_package_requests": "report_bridge/node_report_intake",
                "read_model_refresh_requests": "candidate Operator Action only; no action request created automatically",
            },
            "source_posture": {
                "mission_control": "metadata/request source only",
                "telegram": "metadata only; no Telegram API, polling, or sending wired",
                "cli": "local text source only",
                "report_bridge": "sanitized package/request metadata only",
                "future_client_node": "metadata only until separately approved",
                "unknown": "allowed only as needs-review posture",
            },
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
            **NO_AUTHORITY_FLAGS,
            "claims_not_made": [
                "agent_activation",
                "model_call",
                "tool_execution",
                "telegram_wiring",
                "runtime_execution",
                "approval_bypass",
                "action_auto_create",
                "action_auto_approve",
                "action_auto_execute",
                "no_go_raw_access",
                "client_deployment",
                "truth_promotion",
            ],
        }
    finally:
        conn.close()


def format_intent_router_read_model(read_model: dict[str, Any]) -> str:
    latest = read_model.get("latest_intent")
    lines = [
        "# Intent Router Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over deterministic `intent_router_*` SQLite rows.",
        "- It shows how operator text was routed to role-scoped agent lanes and what next safe move was proposed.",
        "",
        "What this is not:",
        "- It is not agent activation, LLM routing, Telegram wiring, model calling, tool execution, approval bypass, or runtime execution.",
        "",
        "Summary:",
        f"- Total intents: {read_model['total_intents']}.",
        f"- Routed: {read_model['routed_count']}.",
        f"- Needs review: {read_model['needs_review_count']}.",
        f"- Rejected: {read_model['rejected_count']}.",
        f"- By agent: {_counts_line(read_model['counts_by_agent'])}.",
        f"- By category: {_counts_line(read_model['counts_by_category'])}.",
        f"- By source kind: {_counts_line(read_model['counts_by_source_kind'])}.",
        f"- By context link kind: {_counts_line(read_model['counts_by_context_link_kind'])}.",
        "",
        "Latest intent:",
    ]
    if latest:
        lines.extend(
            [
                f"- Intent: `{latest['intent_id']}`.",
                f"- Status: `{latest['status']}`.",
                f"- Route: `{latest['routed_agent_id'] or 'unrouted'}` / `{latest['routed_lane_id'] or 'none'}`.",
                f"- Category: `{latest['intent_category']}`.",
                f"- World: `{latest['world_hint']}`.",
                f"- Candidate action: `{latest['candidate_action_type'] or 'none'}`.",
                f"- Next safe move: {latest['next_safe_move']}",
            ]
        )
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "Authority boundary:",
            "- agent_activation_allowed=false; direct_execution_allowed=false; approval_bypass_allowed=false.",
            "- action_auto_create_allowed=false; action_auto_approve_allowed=false; action_auto_execute_allowed=false.",
            "- no_go_raw_access_allowed=false; network_authority=false; tool_execution_allowed=false.",
            "- model_execution_allowed=false; runtime_authority=false; client_deployment_allowed=false.",
            "- file_move_allowed=false; file_delete_allowed=false.",
            "",
            "Next safe move:",
            "- Surface this read-model in Mission Control as route posture before adding any frontend request writer.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_intent_router_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_intent_router_read_model(db_path=db_path)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_intent_router_read_model(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "total_intents": read_model["total_intents"],
        "routed_count": read_model["routed_count"],
        "needs_review_count": read_model["needs_review_count"],
        "rejected_count": read_model["rejected_count"],
        **NO_AUTHORITY_FLAGS,
    }


def format_route_result(result: IntentRouteResult) -> str:
    return "\n".join(
        [
            "Intent Router v0",
            "",
            f"Intent: `{result.intent_id}`",
            f"Run: `{result.run_id}`",
            f"Status: `{result.status}`",
            f"Route: `{result.routed_agent_id or 'unrouted'}` / `{result.routed_lane_id or 'none'}`",
            f"World: `{result.world_hint}`",
            f"Category: `{result.intent_category}`",
            f"Confidence: {result.confidence:.2f}",
            f"Candidate action: `{result.candidate_action_type or 'none'}`",
            f"Context links: {result.context_link_count}",
            "",
            "Next safe move:",
            f"- {result.next_safe_move}",
            "",
            "Boundary:",
            "- No action was created, approved, or executed.",
            "- No agent, model, tool, network, runtime, file move, or file delete authority was granted.",
        ]
    )


__all__ = [
    "INTENT_CATEGORIES",
    "INTENT_ROUTER_VERSION",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_VERSION",
    "REPORT_SECTIONS",
    "IntentRouteResult",
    "build_intent_router_read_model",
    "build_intent_router_report",
    "export_intent_router_read_model",
    "format_intent_router_read_model",
    "format_intent_router_report",
    "format_route_result",
    "init_intent_router_schema",
    "intent_router_table_names",
    "route_operator_intent",
    "stable_json",
]
