"""Agent Lane Registry v0 for OpenClaw.

This module records role-scoped agent/operator lanes in the Business Ops
ledger under a separated ``agent_lane_*`` namespace. It is a planning and
authority registry only. It does not activate agents, call models, execute
tools, contact networks, or grant approval bypass.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger


ROOT = Path(__file__).resolve().parent
LOGGER = logging.getLogger(__name__)
AGENT_LANE_REGISTRY_VERSION = "agent_lane_registry_v0"
READ_MODEL_VERSION = "agent_lanes_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "agent_lanes.json"
OPERATOR_EXPORT_NAME = "agent_lanes_OPERATOR.md"

STATUSES = {"planning_only", "active_registry", "future_gated", "deprecated"}
AUTHORITY_LEVELS = {"advisory_only", "request_only", "approval_required", "future_gated"}
WORLDS = {
    "music_art",
    "finance",
    "operations",
    "security",
    "build",
    "research",
    "communications",
    "business_development",
    "cross_world",
    "no_world",
    "unknown",
}
SOURCE_KINDS = {
    "mission_control",
    "telegram",
    "cli",
    "report_bridge",
    "future_client_node",
}
SOURCE_POSTURES = {"metadata_only", "request_only", "no_auto_execute"}

NO_AUTHORITY_FLAGS = {
    "agent_activation_allowed": False,
    "direct_execution_allowed": False,
    "approval_bypass_allowed": False,
    "no_go_raw_access_allowed": False,
    "network_authority": False,
    "tool_execution_allowed": False,
    "model_execution_allowed": False,
    "runtime_authority": False,
    "client_deployment_allowed": False,
}

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<table>\"[^\"]+\"|`[^`]+`|\[[^\]]+\]|[\w$]+)\s*\(",
    re.IGNORECASE,
)
_COLUMN_RE = re.compile(
    r"(?P<name>\"(?:[^\"]|\"\")+\"|`[^`]+`|\[[^\]]+\]|[\w$]+)\s+(?P<body>.+)",
    re.DOTALL,
)
_TABLE_CONSTRAINT_TOKENS = {"CONSTRAINT", "FOREIGN", "PRIMARY", "UNIQUE", "CHECK", "EXCLUDE"}
_COLUMN_CONSTRAINT_TOKENS = {"PRIMARY", "UNIQUE", "CHECK", "REFERENCES", "COLLATE", "GENERATED", "AS", "CONSTRAINT"}


@dataclass(frozen=True)
class AgentLaneSeed:
    agent_id: str
    display_name: str
    lane_id: str
    lane_label: str
    status: str
    authority_level: str
    role_summary: str
    allowed_worlds: tuple[str, ...]
    allowed_input_kinds: tuple[str, ...]
    blocked_input_kinds: tuple[str, ...]
    allowed_output_kinds: tuple[str, ...]
    blocked_output_kinds: tuple[str, ...]
    approval_required_for: tuple[str, ...]
    receipt_required_for: tuple[str, ...]
    source_kind_postures: tuple[tuple[str, str], ...]
    aliases: tuple[str, ...]
    routing_hints: tuple[str, ...]
    notes: str
    telegram_bot_username: str | None = None
    telegram_display_name: str | None = None


@dataclass(frozen=True)
class AgentLaneRegistryResult:
    run_id: str
    db_path: str
    agent_count: int
    lane_count: int
    alias_count: int


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _default_sources(*, primary_posture: str = "request_only") -> tuple[tuple[str, str], ...]:
    return (
        ("mission_control", primary_posture),
        ("telegram", "metadata_only"),
        ("cli", primary_posture),
        ("report_bridge", "metadata_only"),
        ("future_client_node", "metadata_only"),
    )


DEFAULT_AGENT_LANE_SEEDS: tuple[AgentLaneSeed, ...] = (
    AgentLaneSeed(
        agent_id="maestro",
        display_name="Maestro Front Door",
        lane_id="operator_frontdoor",
        lane_label="Operator Front Door",
        status="active_registry",
        authority_level="request_only",
        role_summary=(
            "Operate the operator front-door chat: receive operator intent, assemble the grounded "
            "context packet, answer, and route to the correct agent. Enforces SEND_HOLD; proposes "
            "and routes but executes or sends nothing on its own."
        ),
        allowed_worlds=("cross_world", "operations", "communications"),
        allowed_input_kinds=(
            "operator_intent",
            "operator_local_intake_event",
            "generated_read_model",
            "context_packet",
            "source_metadata",
        ),
        blocked_input_kinds=(
            "no_go_raw_content",
            "credential_material",
            "raw_private_body",
            "arbitrary_command_string",
        ),
        allowed_output_kinds=(
            "answer",
            "route_request",
            "operator_briefing",
            "telegram_ready_response",
        ),
        blocked_output_kinds=(
            "external_send",
            "approval_decision",
            "direct_execution",
            "truth_promotion",
            "external_ledger_mutation",
            "client_deployment",
            "file_delete",
        ),
        approval_required_for=(
            "sending_messages",
            "external_comms",
            "action_requests",
        ),
        receipt_required_for=("answer", "operator_briefing"),
        source_kind_postures=_default_sources(primary_posture="request_only"),
        aliases=("front_door", "maestro_chat", "operator_chat"),
        routing_hints=(
            "operator chat",
            "front door",
            "question answering",
            "agent routing",
            "context packet assembly",
        ),
        notes=(
            "Maestro is the operator front-door brain: it grounds, answers, and routes, and enforces "
            "SEND_HOLD. It executes or sends nothing on its own — actuation goes through gated "
            "executors with operator approval."
        ),
    ),
    AgentLaneSeed(
        agent_id="chief",
        display_name="Chief",
        lane_id="system_orchestration",
        lane_label="System Orchestration",
        status="active_registry",
        authority_level="request_only",
        role_summary="Coordinate work, create plans, route intents, and prepare bounded Codex work packets.",
        allowed_worlds=("operations", "build", "security", "communications", "business_development", "cross_world"),
        allowed_input_kinds=(
            "operator_intent",
            "context_packet",
            "file_event_metadata",
            "markdown_document_metadata",
            "project_capsule",
            "report_bridge_summary",
            "tool_policy",
            "generated_read_model",
            "action_receipt",
        ),
        blocked_input_kinds=(
            "no_go_raw_content",
            "credential_material",
            "raw_private_body",
            "raw_client_data_without_approval",
            "arbitrary_command_string",
        ),
        allowed_output_kinds=(
            "plan_proposal",
            "action_request_draft",
            "codex_work_packet",
            "status_summary",
            "routing_decision",
        ),
        blocked_output_kinds=(
            "direct_execution",
            "approval_decision",
            "truth_promotion",
            "file_move",
            "file_delete",
            "client_deployment",
        ),
        approval_required_for=("writes", "execution", "reorg", "external_changes", "client_changes", "file_changes"),
        receipt_required_for=("action_request", "routing_decision", "status_summary"),
        source_kind_postures=_default_sources(primary_posture="request_only"),
        aliases=("operations_router", "chief_operator"),
        routing_hints=(
            "route cross-world operator intents",
            "prepare bounded implementation lanes",
            "escalate risky work to Guardian/operator review",
        ),
        notes="Chief may draft requests and packets but cannot execute or bypass approval.",
    ),
    AgentLaneSeed(
        agent_id="cassandra",
        display_name="Cassandra",
        telegram_bot_username="@openclaw_cassandra_bot",
        telegram_display_name="Clara Reid",
        lane_id="operator_comms",
        lane_label="Business Ops and Operator Communications",
        status="active_registry",
        authority_level="advisory_only",
        role_summary=(
            "Own business ops, AR, client follow-up, income/payment/expense/gig logs, "
            "executive continuity, operator-facing summaries, and status explanations."
        ),
        allowed_worlds=("finance", "communications", "operations", "business_development", "cross_world"),
        allowed_input_kinds=(
            "operator_intent",
            "operator_local_intake_event",
            "generated_read_model",
            "context_packet",
            "action_status_summary",
            "source_metadata",
        ),
        blocked_input_kinds=(
            "no_go_raw_content",
            "credential_material",
            "raw_private_body",
            "raw_source_message_storage",
            "arbitrary_command_string",
        ),
        allowed_output_kinds=(
            "summary",
            "draft_message",
            "operator_briefing",
            "telegram_ready_response",
            "local_business_ops_receipt",
            "follow_up_plan",
        ),
        blocked_output_kinds=(
            "external_send",
            "approval_decision",
            "direct_execution",
            "truth_promotion",
            "invoice_paid_mark",
            "external_ledger_mutation",
        ),
        approval_required_for=(
            "sending_messages",
            "external_comms",
            "action_requests",
            "marking_paid",
            "ledger_or_coupa_mutation",
        ),
        receipt_required_for=("draft_message", "operator_briefing", "local_business_ops_receipt"),
        source_kind_postures=_default_sources(primary_posture="metadata_only"),
        aliases=("operator_briefing", "comms_lane", "business_ops", "ar_lane"),
        routing_hints=(
            "operator summaries",
            "message drafting",
            "status explanation",
            "income/payment/expense/gig logs",
            "AR and client follow-up",
        ),
        notes=(
            "Cassandra may log low-risk local receipts and prepare summaries. Email sends, drafts, "
            "paid marks, and external ledger changes remain blocked behind Guardian/operator authority."
        ),
    ),
    AgentLaneSeed(
        agent_id="guardian",
        display_name="Guardian",
        lane_id="safety_security",
        lane_label="Safety and Security",
        status="active_registry",
        authority_level="advisory_only",
        role_summary="Review no-go boundaries, sensitive-data posture, policy risks, and approval cautions.",
        allowed_worlds=("security", "operations", "cross_world"),
        allowed_input_kinds=(
            "action_request",
            "boundary_metadata",
            "corpus_sensitivity",
            "file_event_metadata",
            "risk_package",
            "tool_policy",
        ),
        blocked_input_kinds=(
            "no_go_raw_content",
            "credential_material",
            "secret_material",
            "private_raw_body",
            "arbitrary_command_string",
        ),
        allowed_output_kinds=("risk_verdict", "boundary_review", "approval_caution", "rejection_reason"),
        blocked_output_kinds=("direct_execution", "secret_disclosure", "policy_mutation_without_approval"),
        approval_required_for=("policy_changes", "file_touching_behavior", "sensitive_boundary_changes"),
        receipt_required_for=("risk_verdict", "boundary_review", "rejection_reason"),
        source_kind_postures=_default_sources(primary_posture="request_only"),
        aliases=("safety_gate", "security_review"),
        routing_hints=("sensitive boundary review", "risk caution", "no-go review"),
        notes="Guardian reviews boundaries but this registry grants no secrets access or execution authority.",
    ),
    AgentLaneSeed(
        agent_id="niles",
        display_name="Niles",
        lane_id="music_art_production",
        lane_label="Music and Art Production",
        status="active_registry",
        authority_level="advisory_only",
        role_summary="Support music, audio, Logic, session, and project-production planning.",
        allowed_worlds=("music_art",),
        allowed_input_kinds=(
            "music_art_metadata",
            "logic_project_metadata",
            "audio_file_metadata",
            "file_event_metadata",
            "context_packet",
        ),
        blocked_input_kinds=(
            "no_go_raw_content",
            "credential_material",
            "unapproved_audio_body_mutation",
            "private_raw_body",
            "arbitrary_command_string",
        ),
        allowed_output_kinds=(
            "session_notes",
            "production_checklist",
            "mix_task_plan",
            "metadata_organization_proposal",
        ),
        blocked_output_kinds=("daw_session_edit", "audio_file_mutation", "file_move", "file_delete", "direct_execution"),
        approval_required_for=("writes", "file_movement", "daw_session_edits", "audio_file_changes"),
        receipt_required_for=("production_checklist", "metadata_organization_proposal"),
        source_kind_postures=_default_sources(primary_posture="request_only"),
        aliases=("producer", "creative_file_resolver"),
        routing_hints=("music files", "Logic project metadata", "production plans", "audio session organization"),
        notes="Niles may stage creative prep and metadata organization only; DAW/session/media mutation stays blocked.",
    ),
    AgentLaneSeed(
        agent_id="hermes",
        display_name="Hermes",
        lane_id="advisory_synthesis",
        lane_label="Advisory Synthesis",
        status="active_registry",
        authority_level="advisory_only",
        role_summary="Produce non-canonical synthesis, comparisons, and advisory interpretation.",
        allowed_worlds=("research", "build", "operations", "cross_world"),
        allowed_input_kinds=(
            "evidence_packet",
            "generated_read_model",
            "comparison_source_metadata",
            "context_packet",
            "markdown_document_metadata",
        ),
        blocked_input_kinds=(
            "no_go_raw_content",
            "credential_material",
            "private_raw_body",
            "canonical_promotion_request_without_gate",
            "arbitrary_command_string",
        ),
        allowed_output_kinds=("advisory_memo", "comparison", "synthesis_packet", "noncanonical_analysis"),
        blocked_output_kinds=("canonical_promotion", "approval_decision", "direct_execution", "truth_write"),
        approval_required_for=("promotion", "action_request", "external_model_use"),
        receipt_required_for=("advisory_memo", "synthesis_packet"),
        source_kind_postures=_default_sources(primary_posture="metadata_only"),
        aliases=("advisory", "synthesis_lane"),
        routing_hints=("research synthesis", "architecture comparison", "non-canonical analysis"),
        notes="Hermes owns adapter/protocol/bridge boundary advice only; it must not own business logic or promote truth.",
    ),
    AgentLaneSeed(
        agent_id="watch_desk",
        display_name="Watch Desk",
        lane_id="watch_desk_projection",
        lane_label="Watch Desk Projection",
        status="active_registry",
        authority_level="advisory_only",
        role_summary="Project what needs operator attention from receipts and read models.",
        allowed_worlds=("operations", "finance", "build", "music_art", "cross_world"),
        allowed_input_kinds=(
            "generated_read_model",
            "action_receipt",
            "operator_local_intake_event",
            "status_summary",
        ),
        blocked_input_kinds=(
            "credential_material",
            "raw_private_body",
            "no_go_raw_content",
            "arbitrary_command_string",
        ),
        allowed_output_kinds=("watch_item", "operator_attention_summary", "source_receipt_ref"),
        blocked_output_kinds=("direct_execution", "approval_decision", "state_mutation", "truth_promotion"),
        approval_required_for=("push_notification", "state_mutation", "external_action"),
        receipt_required_for=("watch_item", "operator_attention_summary"),
        source_kind_postures=_default_sources(primary_posture="metadata_only"),
        aliases=("watchdesk", "attention_feed"),
        routing_hints=("what needs me", "watch desk item", "attention projection"),
        notes="Watch Desk is projection only. It must not mutate source state or execute actions.",
    ),
    AgentLaneSeed(
        agent_id="report_bridge",
        display_name="Report Bridge",
        lane_id="node_report_intake",
        lane_label="Node Report Intake",
        status="active_registry",
        authority_level="request_only",
        role_summary="Handle sanitized local report package intake metadata and rejection summaries.",
        allowed_worlds=("operations", "business_development", "cross_world"),
        allowed_input_kinds=(
            "sanitized_report_package_metadata",
            "read_model_package_manifest",
            "report_summary",
            "receipt_metadata",
        ),
        blocked_input_kinds=(
            "raw_client_data",
            "raw_private_body",
            "remote_control_instruction",
            "credential_material",
            "arbitrary_command_string",
        ),
        allowed_output_kinds=("import_receipt", "report_summary", "rejection_reason"),
        blocked_output_kinds=("remote_control", "truth_promotion", "client_data_acceptance_without_approval"),
        approval_required_for=("client_data_package_handling", "new_package_classes", "truth_promotion"),
        receipt_required_for=("import_receipt", "rejection_reason"),
        source_kind_postures=(
            ("mission_control", "metadata_only"),
            ("telegram", "metadata_only"),
            ("cli", "request_only"),
            ("report_bridge", "request_only"),
            ("future_client_node", "request_only"),
        ),
        aliases=("node_report_bridge", "node_uplink"),
        routing_hints=("report package import", "node package rejection", "project/client sanitized package posture"),
        notes="Report Bridge is sanitized package intake, not remote control or client-data authority.",
    ),
)


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS agent_lane_registry_runs (
  run_id TEXT PRIMARY KEY,
  registry_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  agent_count INTEGER NOT NULL DEFAULT 0,
  lane_count INTEGER NOT NULL DEFAULT 0,
  alias_count INTEGER NOT NULL DEFAULT 0,
  source_basis_json TEXT NOT NULL,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  direct_execution_allowed INTEGER NOT NULL DEFAULT 0,
  approval_bypass_allowed INTEGER NOT NULL DEFAULT 0,
  no_go_raw_access_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  model_execution_allowed INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  client_deployment_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_lanes (
  agent_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  lane_id TEXT NOT NULL UNIQUE,
  lane_label TEXT NOT NULL,
  status TEXT NOT NULL,
  authority_level TEXT NOT NULL,
  role_summary TEXT NOT NULL,
  can_execute INTEGER NOT NULL DEFAULT 0,
  can_bypass_approval INTEGER NOT NULL DEFAULT 0,
  can_read_no_go_raw INTEGER NOT NULL DEFAULT 0,
  can_call_network INTEGER NOT NULL DEFAULT 0,
  can_run_tools INTEGER NOT NULL DEFAULT 0,
  can_call_models INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  client_deployment_authority INTEGER NOT NULL DEFAULT 0,
  telegram_bot_username TEXT,
  telegram_display_name TEXT,
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  run_id TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES agent_lane_registry_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_lane_worlds (
  world_binding_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  world_binding TEXT NOT NULL,
  primary_world INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (agent_id) REFERENCES agent_lanes(agent_id) ON DELETE CASCADE,
  UNIQUE(agent_id, world_binding)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_lane_allowed_inputs (
  input_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  input_kind TEXT NOT NULL,
  posture TEXT NOT NULL,
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (agent_id) REFERENCES agent_lanes(agent_id) ON DELETE CASCADE,
  UNIQUE(agent_id, input_kind)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_lane_blocked_inputs (
  blocked_input_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  input_kind TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (agent_id) REFERENCES agent_lanes(agent_id) ON DELETE CASCADE,
  UNIQUE(agent_id, input_kind)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_lane_allowed_outputs (
  output_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  output_kind TEXT NOT NULL,
  posture TEXT NOT NULL,
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (agent_id) REFERENCES agent_lanes(agent_id) ON DELETE CASCADE,
  UNIQUE(agent_id, output_kind)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_lane_blocked_outputs (
  blocked_output_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  output_kind TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (agent_id) REFERENCES agent_lanes(agent_id) ON DELETE CASCADE,
  UNIQUE(agent_id, output_kind)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_lane_action_policies (
  policy_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  policy_kind TEXT NOT NULL,
  policy_text TEXT NOT NULL,
  approval_required INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY (agent_id) REFERENCES agent_lanes(agent_id) ON DELETE CASCADE,
  UNIQUE(agent_id, policy_kind, policy_text)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_lane_receipt_requirements (
  receipt_requirement_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  receipt_kind TEXT NOT NULL,
  required_for TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (agent_id) REFERENCES agent_lanes(agent_id) ON DELETE CASCADE,
  UNIQUE(agent_id, receipt_kind, required_for)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_lane_source_kinds (
  source_kind_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_posture TEXT NOT NULL,
  can_auto_execute INTEGER NOT NULL DEFAULT 0,
  api_wired INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (agent_id) REFERENCES agent_lanes(agent_id) ON DELETE CASCADE,
  UNIQUE(agent_id, source_kind)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_lane_aliases (
  alias_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  alias TEXT NOT NULL,
  alias_kind TEXT NOT NULL,
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (agent_id) REFERENCES agent_lanes(agent_id) ON DELETE CASCADE,
  UNIQUE(alias)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_lane_routing_hints (
  routing_hint_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  match_kind TEXT NOT NULL,
  match_value TEXT NOT NULL,
  route_priority INTEGER NOT NULL DEFAULT 100,
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (agent_id) REFERENCES agent_lanes(agent_id) ON DELETE CASCADE,
  UNIQUE(agent_id, match_kind, match_value)
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_agent_lanes_status ON agent_lanes(status)",
        "CREATE INDEX IF NOT EXISTS idx_agent_lanes_authority ON agent_lanes(authority_level)",
        "CREATE INDEX IF NOT EXISTS idx_agent_lane_worlds_world ON agent_lane_worlds(world_binding)",
        "CREATE INDEX IF NOT EXISTS idx_agent_lane_sources_kind ON agent_lane_source_kinds(source_kind)",
    )


def _strip_identifier_quotes(identifier: str) -> str:
    item = identifier.strip()
    if item.startswith('"') and item.endswith('"'):
        return item[1:-1].replace('""', '"')
    if item.startswith("`") and item.endswith("`"):
        return item[1:-1].replace("``", "`")
    if item.startswith("[") and item.endswith("]"):
        return item[1:-1].replace("]]", "]")
    return item


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _split_sql_items(body: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    index = 0
    while index < len(body):
        char = body[index]
        current.append(char)
        if quote:
            if char == quote:
                if index + 1 < len(body) and body[index + 1] == quote:
                    current.append(body[index + 1])
                    index += 1
                else:
                    quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(depth - 1, 0)
        elif char == "," and depth == 0:
            current.pop()
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
        index += 1
    item = "".join(current).strip()
    if item:
        items.append(item)
    return items


def _create_table_parts(statement: str) -> tuple[str, list[str]] | None:
    match = _CREATE_TABLE_RE.search(statement.strip())
    if not match:
        return None
    table_name = _strip_identifier_quotes(match.group("table"))
    open_paren = statement.find("(", match.end() - 1)
    close_paren = statement.rfind(")")
    if open_paren == -1 or close_paren == -1 or close_paren <= open_paren:
        return None
    return table_name, _split_sql_items(statement[open_paren + 1 : close_paren])


def _column_add_fragment(column_sql: str) -> tuple[str, str] | None:
    first_token = column_sql.lstrip().split(None, 1)[0].upper()
    if first_token in _TABLE_CONSTRAINT_TOKENS:
        return None
    match = _COLUMN_RE.match(column_sql.strip())
    if not match:
        return None
    name = _strip_identifier_quotes(match.group("name"))
    tokens = match.group("body").split()
    kept: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        upper = token.upper()
        if upper == "NOT":
            if index + 1 < len(tokens) and tokens[index + 1].upper() == "NULL":
                index += 2
            else:
                index += 1
            continue
        if upper == "NULL":
            index += 1
            continue
        if upper == "DEFAULT":
            kept.append(token)
            if index + 1 < len(tokens):
                kept.append(tokens[index + 1])
                index += 2
            else:
                index += 1
            continue
        if upper in _COLUMN_CONSTRAINT_TOKENS:
            break
        kept.append(token)
        index += 1
    declaration = " ".join(kept) if kept else "TEXT"
    return name, f"{_quote_identifier(name)} {declaration}"


def _declared_table_columns(statements: Iterable[str]) -> dict[str, dict[str, str]]:
    declared: dict[str, dict[str, str]] = {}
    for statement in statements:
        parts = _create_table_parts(statement)
        if parts is None:
            continue
        table_name, column_items = parts
        columns: dict[str, str] = {}
        for item in column_items:
            parsed = _column_add_fragment(item)
            if parsed is None:
                continue
            column_name, add_fragment = parsed
            columns[column_name] = add_fragment
        declared[table_name] = columns
    return declared


def _existing_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({_quote_identifier(table_name)})").fetchall()
    return {row[1] for row in rows}


def ensure_schema_columns(conn: sqlite3.Connection, statements: Iterable[str]) -> list[tuple[str, str]]:
    """Add missing declared columns to existing tables without dropping or rewriting data."""

    healed: list[tuple[str, str]] = []
    for table_name, columns in _declared_table_columns(statements).items():
        existing = _existing_columns(conn, table_name)
        for column_name, add_fragment in columns.items():
            if column_name in existing:
                continue
            conn.execute(f"ALTER TABLE {_quote_identifier(table_name)} ADD COLUMN {add_fragment}")
            LOGGER.info("healed %s.%s schema drift via ALTER TABLE ADD COLUMN", table_name, column_name)
            healed.append((table_name, column_name))
            existing.add(column_name)
    return healed


def init_agent_lane_registry_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    db_parent = Path(path).parent
    if db_parent and not db_parent.exists():
        db_parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        statements = _sql_statements()
        table_statements = tuple(statement for statement in statements if _create_table_parts(statement) is not None)
        other_statements = tuple(statement for statement in statements if _create_table_parts(statement) is None)
        for statement in table_statements:
            conn.execute(statement)
        ensure_schema_columns(conn, table_statements)
        for statement in other_statements:
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def agent_lane_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_agent_lane_registry_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND (name LIKE 'agent_lane_%' OR name = 'agent_lanes')
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _validate_seed(seed: AgentLaneSeed) -> None:
    if seed.status not in STATUSES:
        raise ValueError(f"bad status for {seed.agent_id}: {seed.status}")
    if seed.authority_level not in AUTHORITY_LEVELS:
        raise ValueError(f"bad authority level for {seed.agent_id}: {seed.authority_level}")
    for world in seed.allowed_worlds:
        if world not in WORLDS:
            raise ValueError(f"bad world for {seed.agent_id}: {world}")
    source_kinds = {kind for kind, _posture in seed.source_kind_postures}
    if source_kinds != SOURCE_KINDS:
        missing = sorted(SOURCE_KINDS - source_kinds)
        extra = sorted(source_kinds - SOURCE_KINDS)
        raise ValueError(f"{seed.agent_id} source kinds mismatch missing={missing} extra={extra}")
    for source_kind, posture in seed.source_kind_postures:
        if source_kind not in SOURCE_KINDS:
            raise ValueError(f"bad source kind for {seed.agent_id}: {source_kind}")
        if posture not in SOURCE_POSTURES:
            raise ValueError(f"bad source posture for {seed.agent_id}: {posture}")


def _delete_child_rows(conn: sqlite3.Connection, agent_id: str) -> None:
    for table in (
        "agent_lane_worlds",
        "agent_lane_allowed_inputs",
        "agent_lane_blocked_inputs",
        "agent_lane_allowed_outputs",
        "agent_lane_blocked_outputs",
        "agent_lane_action_policies",
        "agent_lane_receipt_requirements",
        "agent_lane_source_kinds",
        "agent_lane_aliases",
        "agent_lane_routing_hints",
    ):
        conn.execute(f"DELETE FROM {table} WHERE agent_id = ?", (agent_id,))


def _insert_list_row(
    conn: sqlite3.Connection,
    *,
    table: str,
    id_column: str,
    id_prefix: str,
    agent_id: str,
    value_column: str,
    value: str,
    now: str,
    extra_columns: dict[str, Any],
) -> None:
    columns = [id_column, "agent_id", value_column, *extra_columns.keys(), "created_at"]
    placeholders = ", ".join("?" for _ in columns)
    values = [_row_id(id_prefix, agent_id, value), agent_id, value, *extra_columns.values(), now]
    conn.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
        values,
    )


def seed_agent_lane_registry(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
    agent_seeds: Iterable[AgentLaneSeed] = DEFAULT_AGENT_LANE_SEEDS,
) -> AgentLaneRegistryResult:
    path = init_agent_lane_registry_schema(db_path)
    seeds = tuple(agent_seeds)
    for seed in seeds:
        _validate_seed(seed)
    if len({seed.agent_id for seed in seeds}) != len(seeds):
        raise ValueError("duplicate agent_id in agent lane seeds")
    if len({alias for seed in seeds for alias in seed.aliases}) != sum(len(seed.aliases) for seed in seeds):
        raise ValueError("duplicate alias in agent lane seeds")

    now = utc_now()
    resolved_run_id = run_id or _row_id("aglanerun", AGENT_LANE_REGISTRY_VERSION, now, len(seeds))
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
INSERT INTO agent_lane_registry_runs (
  run_id, registry_version, created_at, source_basis_json, notes
) VALUES (?, ?, ?, ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
  registry_version = excluded.registry_version,
  source_basis_json = excluded.source_basis_json,
  notes = excluded.notes,
  agent_activation_allowed = 0,
  direct_execution_allowed = 0,
  approval_bypass_allowed = 0,
  no_go_raw_access_allowed = 0,
  network_authority = 0,
  tool_execution_allowed = 0,
  model_execution_allowed = 0,
  runtime_authority = 0,
  client_deployment_allowed = 0
""".strip(),
            (
                resolved_run_id,
                AGENT_LANE_REGISTRY_VERSION,
                now,
                stable_json(
                    {
                        "source": "operator_seeded_role_scoped_registry",
                        "legacy_partial_surface": "capability_registry.py",
                        "extends": "Business Ops ledger separated namespace",
                        "agent_activation": False,
                        "network_calls": False,
                        "model_calls": False,
                        "tool_execution": False,
                    }
                ),
                "Role-scoped planning registry. No agent activation or approval bypass.",
            ),
        )

        alias_count = 0
        for seed in seeds:
            existing = conn.execute(
                "SELECT created_at FROM agent_lanes WHERE agent_id = ?",
                (seed.agent_id,),
            ).fetchone()
            created_at = existing[0] if existing else now
            _delete_child_rows(conn, seed.agent_id)
            conn.execute(
                """
INSERT INTO agent_lanes (
  agent_id, display_name, lane_id, lane_label, status, authority_level,
  role_summary, notes, created_at, updated_at, run_id,
  telegram_bot_username, telegram_display_name
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(agent_id) DO UPDATE SET
  display_name = excluded.display_name,
  lane_id = excluded.lane_id,
  lane_label = excluded.lane_label,
  status = excluded.status,
  authority_level = excluded.authority_level,
  role_summary = excluded.role_summary,
  can_execute = 0,
  can_bypass_approval = 0,
  can_read_no_go_raw = 0,
  can_call_network = 0,
  can_run_tools = 0,
  can_call_models = 0,
  runtime_authority = 0,
  client_deployment_authority = 0,
  telegram_bot_username = excluded.telegram_bot_username,
  telegram_display_name = excluded.telegram_display_name,
  notes = excluded.notes,
  updated_at = excluded.updated_at,
  run_id = excluded.run_id
""".strip(),
                (
                    seed.agent_id,
                    seed.display_name,
                    seed.lane_id,
                    seed.lane_label,
                    seed.status,
                    seed.authority_level,
                    seed.role_summary,
                    seed.notes,
                    created_at,
                    now,
                    resolved_run_id,
                    seed.telegram_bot_username,
                    seed.telegram_display_name,
                ),
            )

            for index, world in enumerate(seed.allowed_worlds):
                _insert_list_row(
                    conn,
                    table="agent_lane_worlds",
                    id_column="world_binding_id",
                    id_prefix="agworld",
                    agent_id=seed.agent_id,
                    value_column="world_binding",
                    value=world,
                    now=now,
                    extra_columns={"primary_world": 1 if index == 0 else 0},
                )
            for input_kind in seed.allowed_input_kinds:
                _insert_list_row(
                    conn,
                    table="agent_lane_allowed_inputs",
                    id_column="input_id",
                    id_prefix="aginput",
                    agent_id=seed.agent_id,
                    value_column="input_kind",
                    value=input_kind,
                    now=now,
                    extra_columns={
                        "posture": "metadata_or_evidence_only",
                        "notes": "Allowed input kind does not grant raw no-go access or execution authority.",
                    },
                )
            for input_kind in seed.blocked_input_kinds:
                _insert_list_row(
                    conn,
                    table="agent_lane_blocked_inputs",
                    id_column="blocked_input_id",
                    id_prefix="agblockin",
                    agent_id=seed.agent_id,
                    value_column="input_kind",
                    value=input_kind,
                    now=now,
                    extra_columns={"reason": "Blocked by v0 authority boundary."},
                )
            for output_kind in seed.allowed_output_kinds:
                _insert_list_row(
                    conn,
                    table="agent_lane_allowed_outputs",
                    id_column="output_id",
                    id_prefix="agoutput",
                    agent_id=seed.agent_id,
                    value_column="output_kind",
                    value=output_kind,
                    now=now,
                    extra_columns={
                        "posture": "proposal_or_read_model_surface",
                        "notes": "Output is non-executing unless separately approved through Operator Action Path.",
                    },
                )
            for output_kind in seed.blocked_output_kinds:
                _insert_list_row(
                    conn,
                    table="agent_lane_blocked_outputs",
                    id_column="blocked_output_id",
                    id_prefix="agblockout",
                    agent_id=seed.agent_id,
                    value_column="output_kind",
                    value=output_kind,
                    now=now,
                    extra_columns={"reason": "Blocked by v0 authority boundary."},
                )
            for policy_text in seed.approval_required_for:
                _insert_list_row(
                    conn,
                    table="agent_lane_action_policies",
                    id_column="policy_id",
                    id_prefix="agpolicy",
                    agent_id=seed.agent_id,
                    value_column="policy_text",
                    value=policy_text,
                    now=now,
                    extra_columns={"policy_kind": "approval_required_for", "approval_required": 1},
                )
            for receipt_kind in seed.receipt_required_for:
                _insert_list_row(
                    conn,
                    table="agent_lane_receipt_requirements",
                    id_column="receipt_requirement_id",
                    id_prefix="agreceipt",
                    agent_id=seed.agent_id,
                    value_column="receipt_kind",
                    value=receipt_kind,
                    now=now,
                    extra_columns={"required_for": "agent_lane_output_or_action_request"},
                )
            for source_kind, posture in seed.source_kind_postures:
                _insert_list_row(
                    conn,
                    table="agent_lane_source_kinds",
                    id_column="source_kind_id",
                    id_prefix="agsource",
                    agent_id=seed.agent_id,
                    value_column="source_kind",
                    value=source_kind,
                    now=now,
                    extra_columns={"source_posture": posture, "can_auto_execute": 0, "api_wired": 0},
                )
            for alias in seed.aliases:
                alias_count += 1
                _insert_list_row(
                    conn,
                    table="agent_lane_aliases",
                    id_column="alias_id",
                    id_prefix="agalias",
                    agent_id=seed.agent_id,
                    value_column="alias",
                    value=alias,
                    now=now,
                    extra_columns={
                        "alias_kind": "routing_alias",
                        "notes": "Alias only. Does not create a separate active role.",
                    },
                )
            for priority, hint in enumerate(seed.routing_hints, start=1):
                _insert_list_row(
                    conn,
                    table="agent_lane_routing_hints",
                    id_column="routing_hint_id",
                    id_prefix="aghint",
                    agent_id=seed.agent_id,
                    value_column="match_value",
                    value=hint,
                    now=now,
                    extra_columns={
                        "match_kind": "operator_intent_hint",
                        "route_priority": priority,
                        "notes": "Hint only. Routing requires validation and approval gates.",
                    },
                )

        conn.execute(
            """
UPDATE agent_lane_registry_runs
SET completed_at = ?,
    agent_count = ?,
    lane_count = ?,
    alias_count = ?
WHERE run_id = ?
""".strip(),
            (utc_now(), len(seeds), len({seed.lane_id for seed in seeds}), alias_count, resolved_run_id),
        )
        conn.commit()
        return AgentLaneRegistryResult(
            run_id=resolved_run_id,
            db_path=path,
            agent_count=len(seeds),
            lane_count=len({seed.lane_id for seed in seeds}),
            alias_count=alias_count,
        )
    finally:
        conn.close()


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM agent_lane_registry_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row[0] if row else None


def _all_dicts(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _group_values(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        grouped[row[key]].append(row[value])
    return {item_key: sorted(items) for item_key, items in grouped.items()}


def _agent_summaries(conn: sqlite3.Connection, *, run_id: str) -> list[dict[str, Any]]:
    agents = _all_dicts(
        conn,
        """
SELECT *
FROM agent_lanes
WHERE run_id = ?
ORDER BY agent_id
""".strip(),
        (run_id,),
    )
    agent_ids = tuple(agent["agent_id"] for agent in agents)
    if not agent_ids:
        return []
    placeholders = ",".join("?" for _ in agent_ids)
    worlds = _group_values(
        _all_dicts(conn, f"SELECT agent_id, world_binding FROM agent_lane_worlds WHERE agent_id IN ({placeholders})", agent_ids),
        "agent_id",
        "world_binding",
    )
    allowed_inputs = _group_values(
        _all_dicts(conn, f"SELECT agent_id, input_kind FROM agent_lane_allowed_inputs WHERE agent_id IN ({placeholders})", agent_ids),
        "agent_id",
        "input_kind",
    )
    blocked_inputs = _group_values(
        _all_dicts(conn, f"SELECT agent_id, input_kind FROM agent_lane_blocked_inputs WHERE agent_id IN ({placeholders})", agent_ids),
        "agent_id",
        "input_kind",
    )
    allowed_outputs = _group_values(
        _all_dicts(conn, f"SELECT agent_id, output_kind FROM agent_lane_allowed_outputs WHERE agent_id IN ({placeholders})", agent_ids),
        "agent_id",
        "output_kind",
    )
    blocked_outputs = _group_values(
        _all_dicts(conn, f"SELECT agent_id, output_kind FROM agent_lane_blocked_outputs WHERE agent_id IN ({placeholders})", agent_ids),
        "agent_id",
        "output_kind",
    )
    approvals = _group_values(
        _all_dicts(conn, f"SELECT agent_id, policy_text FROM agent_lane_action_policies WHERE agent_id IN ({placeholders})", agent_ids),
        "agent_id",
        "policy_text",
    )
    receipts = _group_values(
        _all_dicts(conn, f"SELECT agent_id, receipt_kind FROM agent_lane_receipt_requirements WHERE agent_id IN ({placeholders})", agent_ids),
        "agent_id",
        "receipt_kind",
    )
    aliases = _group_values(
        _all_dicts(conn, f"SELECT agent_id, alias FROM agent_lane_aliases WHERE agent_id IN ({placeholders})", agent_ids),
        "agent_id",
        "alias",
    )
    hints = _group_values(
        _all_dicts(conn, f"SELECT agent_id, match_value FROM agent_lane_routing_hints WHERE agent_id IN ({placeholders})", agent_ids),
        "agent_id",
        "match_value",
    )
    source_rows = _all_dicts(
        conn,
        f"""
SELECT agent_id, source_kind, source_posture, can_auto_execute, api_wired
FROM agent_lane_source_kinds
WHERE agent_id IN ({placeholders})
ORDER BY agent_id, source_kind
""".strip(),
        agent_ids,
    )
    sources_by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        sources_by_agent[row["agent_id"]].append(
            {
                "source_kind": row["source_kind"],
                "source_posture": row["source_posture"],
                "can_auto_execute": bool(row["can_auto_execute"]),
                "api_wired": bool(row["api_wired"]),
            }
        )
    summaries: list[dict[str, Any]] = []
    for agent in agents:
        agent_id = agent["agent_id"]
        summaries.append(
            {
                "agent_id": agent_id,
                "display_name": agent["display_name"],
                "lane_id": agent["lane_id"],
                "lane_label": agent["lane_label"],
                "status": agent["status"],
                "authority_level": agent["authority_level"],
                "role_summary": agent["role_summary"],
                "allowed_worlds": worlds.get(agent_id, []),
                "allowed_input_kinds": allowed_inputs.get(agent_id, []),
                "blocked_input_kinds": blocked_inputs.get(agent_id, []),
                "allowed_output_kinds": allowed_outputs.get(agent_id, []),
                "blocked_output_kinds": blocked_outputs.get(agent_id, []),
                "approval_required_for": approvals.get(agent_id, []),
                "receipt_required_for": receipts.get(agent_id, []),
                "source_kinds": sources_by_agent.get(agent_id, []),
                "aliases": aliases.get(agent_id, []),
                "routing_hints": hints.get(agent_id, []),
                "can_execute": bool(agent["can_execute"]),
                "can_bypass_approval": bool(agent["can_bypass_approval"]),
                "can_read_no_go_raw": bool(agent["can_read_no_go_raw"]),
                "can_call_network": bool(agent["can_call_network"]),
                "can_run_tools": bool(agent["can_run_tools"]),
                "can_call_models": bool(agent["can_call_models"]),
                "runtime_authority": bool(agent["runtime_authority"]),
                "client_deployment_authority": bool(agent["client_deployment_authority"]),
                "notes": agent["notes"],
            }
        )
    return summaries


def build_agent_lane_report(
    *,
    db_path: str | Path | None = None,
    run_id: str | None = None,
    report: str = "summary",
    agent_id: str | None = None,
    world: str | None = None,
    source_kind: str | None = None,
) -> dict[str, Any]:
    path = init_agent_lane_registry_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        selected_run_id = run_id or _latest_run_id(conn)
        if selected_run_id is None:
            result = seed_agent_lane_registry(db_path=path)
            selected_run_id = result.run_id
        run = dict(
            conn.execute(
                "SELECT * FROM agent_lane_registry_runs WHERE run_id = ?",
                (selected_run_id,),
            ).fetchone()
        )
        agents = _agent_summaries(conn, run_id=selected_run_id)
        if agent_id:
            normalized = agent_id.strip().lower()
            aliases = _all_dicts(
                conn,
                "SELECT agent_id, alias FROM agent_lane_aliases WHERE lower(alias) = ?",
                (normalized,),
            )
            alias_agent = aliases[0]["agent_id"] if aliases else None
            agents = [
                agent
                for agent in agents
                if agent["agent_id"] == normalized or agent["agent_id"] == alias_agent
            ]
            report = "agent"
        elif report == "world":
            if not world:
                raise ValueError("--world is required for world report")
            agents = [agent for agent in agents if world in agent["allowed_worlds"]]
        elif report == "source-kind":
            if not source_kind:
                raise ValueError("--source-kind is required for source-kind report")
            agents = [
                agent
                for agent in agents
                if any(source["source_kind"] == source_kind for source in agent["source_kinds"])
            ]
        elif report == "approval-required":
            agents = [agent for agent in agents if agent["approval_required_for"]]
        elif report == "agents":
            pass
        elif report == "summary":
            pass
        else:
            raise ValueError(f"unknown agent lane report: {report}")

        world_counts = Counter(world_name for agent in agents for world_name in agent["allowed_worlds"])
        source_counts = Counter(
            source["source_kind"] for agent in agents for source in agent["source_kinds"]
        )
        authority_counts = Counter(agent["authority_level"] for agent in agents)
        return {
            "status": "ok",
            "report": report,
            "db_path": str(path),
            "run": run,
            "counts": {
                "agents": len(agents),
                "lanes": len({agent["lane_id"] for agent in agents}),
                "aliases": sum(len(agent["aliases"]) for agent in agents),
                "worlds": dict(sorted(world_counts.items())),
                "source_kinds": dict(sorted(source_counts.items())),
                "authority_levels": dict(sorted(authority_counts.items())),
            },
            "agents": agents,
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def _counts_line(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def format_agent_lane_report(payload: dict[str, Any]) -> str:
    lines = [
        f"Agent Lane Registry v0 - {payload['report']}",
        "",
        f"Run: `{payload['run']['run_id']}`",
        f"Agents: {payload['counts']['agents']}",
        f"Lanes: {payload['counts']['lanes']}",
        f"Worlds: {_counts_line(payload['counts']['worlds'])}",
        f"Source kinds: {_counts_line(payload['counts']['source_kinds'])}",
        "",
        "Agents:",
    ]
    for agent in payload.get("agents") or []:
        lines.append(
            f"- `{agent['agent_id']}` / `{agent['lane_id']}`: {agent['authority_level']}; "
            f"worlds={','.join(agent['allowed_worlds'])}; "
            f"approval_required_for={','.join(agent['approval_required_for']) or 'none'}"
        )
    if not payload.get("agents"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Registry only; no agent activation, direct execution, approval bypass, no-go raw access, model calls, tool execution, network authority, runtime authority, or client deployment authority.",
        ]
    )
    return "\n".join(lines)


def build_agent_lanes_read_model(
    *,
    db_path: str | Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    report = build_agent_lane_report(db_path=db_path, run_id=run_id, report="summary")
    agents = report["agents"]
    agents_by_world: dict[str, list[str]] = defaultdict(list)
    agents_by_source_kind: dict[str, list[str]] = defaultdict(list)
    aliases: list[dict[str, str]] = []
    routing_hints: list[dict[str, str]] = []
    approval_requirements: dict[str, list[str]] = {}
    for agent in agents:
        for world in agent["allowed_worlds"]:
            agents_by_world[world].append(agent["agent_id"])
        for source in agent["source_kinds"]:
            agents_by_source_kind[source["source_kind"]].append(agent["agent_id"])
        for alias in agent["aliases"]:
            aliases.append({"alias": alias, "agent_id": agent["agent_id"]})
        for hint in agent["routing_hints"]:
            routing_hints.append({"agent_id": agent["agent_id"], "hint": hint})
        approval_requirements[agent["agent_id"]] = agent["approval_required_for"]

    run = report["run"]
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "mode": "role_scoped_agent_lane_registry_only",
        "generated_at": run["completed_at"] or run["created_at"],
        "source_ledger_path": _display_path(report["db_path"]),
        "source_ledger_namespace": "agent_lane_*",
        "latest_run_id": run["run_id"],
        "agent_count": len(agents),
        "lane_count": len({agent["lane_id"] for agent in agents}),
        "agents": agents,
        "agents_by_world": {key: sorted(value) for key, value in sorted(agents_by_world.items())},
        "agents_by_source_kind": {
            key: sorted(value) for key, value in sorted(agents_by_source_kind.items())
        },
        "approval_requirements": approval_requirements,
        "aliases": sorted(aliases, key=lambda item: (item["agent_id"], item["alias"])),
        "routing_hints": sorted(routing_hints, key=lambda item: (item["agent_id"], item["hint"])),
        "source_kind_posture": {
            "mission_control": "request metadata only; no auto-execute",
            "telegram": "metadata only; no Telegram API, polling, or sending wired",
            "cli": "request metadata only; approval still required",
            "report_bridge": "sanitized package/request metadata only",
            "future_client_node": "metadata only until separately approved",
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
            "no_go_raw_access",
            "client_deployment",
            "truth_promotion",
        ],
    }


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


def format_agent_lanes_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# Agent Lanes Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over role-scoped `agent_lane_*` SQLite rows.",
        "- It defines planning lanes, routing hints, source metadata posture, approvals, and receipts.",
        "",
        "What this is not:",
        "- It is not agent activation, runtime execution, Telegram wiring, model calling, tool execution, approval bypass, no-go raw access, or client deployment.",
        "",
        "Summary:",
        f"- Agents: {read_model['agent_count']}.",
        f"- Lanes: {read_model['lane_count']}.",
        f"- Worlds: {_counts_line({key: len(value) for key, value in read_model['agents_by_world'].items()})}.",
        "",
        "Agents:",
    ]
    for agent in read_model["agents"]:
        lines.append(
            f"- `{agent['agent_id']}` -> `{agent['lane_id']}`; "
            f"authority=`{agent['authority_level']}`; worlds={', '.join(agent['allowed_worlds'])}."
        )
    lines.extend(
        [
            "",
            "Source posture:",
            "- Mission Control, Telegram, CLI, Report Bridge, and future client nodes are source metadata/request channels only.",
            "- Telegram is represented for future metadata routing only; no Telegram API, polling, or sending is wired.",
            "- All sources still require approval gates before any bounded execution path.",
            "",
            "Authority boundary:",
            "- agent_activation_allowed=false; direct_execution_allowed=false; approval_bypass_allowed=false.",
            "- no_go_raw_access_allowed=false; network_authority=false; tool_execution_allowed=false.",
            "- model_execution_allowed=false; runtime_authority=false; client_deployment_allowed=false.",
            "",
            "Next safe move:",
            "- Use this read-model as routing context for Operator Intent Inbox and future Mission Control request drafting; do not activate agents from it.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_agent_lanes_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    run_id: str | None = None,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_agent_lanes_read_model(db_path=db_path, run_id=run_id)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_agent_lanes_read_model(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "agent_count": read_model["agent_count"],
        "lane_count": read_model["lane_count"],
        **NO_AUTHORITY_FLAGS,
    }


def format_export_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Agent Lanes Read-Model Export v0",
            "",
            f"Exported: `{summary['json_path']}`",
            f"Operator: `{summary['operator_path']}`",
            f"Agents: {summary['agent_count']}",
            f"Lanes: {summary['lane_count']}",
            "",
            "Boundary:",
            "- Export reads `agent_lane_*` rows and writes generated read-model files only.",
        ]
    )


__all__ = [
    "AGENT_LANE_REGISTRY_VERSION",
    "DEFAULT_AGENT_LANE_SEEDS",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_VERSION",
    "AgentLaneRegistryResult",
    "AgentLaneSeed",
    "agent_lane_table_names",
    "build_agent_lane_report",
    "build_agent_lanes_read_model",
    "ensure_schema_columns",
    "export_agent_lanes_read_model",
    "format_agent_lane_report",
    "format_agent_lanes_read_model",
    "format_export_summary",
    "init_agent_lane_registry_schema",
    "seed_agent_lane_registry",
    "stable_json",
]
