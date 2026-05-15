"""Agent Runtime Readiness v0 for OpenClaw.

This module records a safe readiness/start-sequence posture for role-scoped
agent lanes. It does not activate agents, call models, call external APIs, run
tools, execute arbitrary shell, or bypass approval.
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

from agent_lane_registry import (
    DEFAULT_AGENT_LANE_SEEDS,
    init_agent_lane_registry_schema,
    seed_agent_lane_registry,
)
from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger
from file_event_queue import init_file_event_queue_schema
from intent_router import init_intent_router_schema, route_operator_intent
from local_automation_registry import (
    init_local_automation_schema,
    seed_local_automation_registry,
)
from mac_mirror_atlas import query_mac_mirror_report_section
from operator_action import init_operator_action_schema
from operator_action_inbox import init_operator_action_inbox_schema
from report_bridge import build_report_bridge_report, init_report_bridge_schema


ROOT = Path(__file__).resolve().parent
READINESS_VERSION = "agent_runtime_readiness_v0"
READ_MODEL_VERSION = "agent_runtime_readiness_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "agent_runtime_readiness.json"
OPERATOR_EXPORT_NAME = "agent_runtime_readiness_OPERATOR.md"

REQUIRED_AGENT_IDS = (
    "chief",
    "cassandra",
    "guardian",
    "niles",
    "hermes",
    "report_bridge",
)

NO_AUTHORITY_FLAGS = {
    "live_agent_activation_allowed": False,
    "autonomous_loop_allowed": False,
    "telegram_api_allowed": False,
    "gmail_api_allowed": False,
    "model_call_allowed": False,
    "arbitrary_shell_allowed": False,
    "tool_execution_allowed": False,
    "approval_bypass_allowed": False,
    "no_go_raw_access_allowed": False,
    "client_deployment_allowed": False,
}

SMOKE_TESTS = (
    {
        "smoke_test_id": "chief_markdown_status",
        "agent_id": "chief",
        "intent_text": "Chief, organize my Markdown files.",
        "expected_statuses": ("routed", "needs_operator_review"),
        "expected_agent_id": "chief",
        "expected_blocker": "approval_required_before_any_file_reorg",
    },
    {
        "smoke_test_id": "cassandra_changed_summary",
        "agent_id": "cassandra",
        "intent_text": "Cassandra, summarize what changed.",
        "expected_statuses": ("routed", "needs_operator_review"),
        "expected_agent_id": "cassandra",
        "expected_blocker": "no_external_message_send_wired",
    },
    {
        "smoke_test_id": "guardian_safety_review",
        "agent_id": "guardian",
        "intent_text": "Guardian, is this safe?",
        "expected_statuses": ("routed", "needs_operator_review"),
        "expected_agent_id": "guardian",
        "expected_blocker": "no_no_go_raw_reads",
    },
    {
        "smoke_test_id": "niles_new_logic_file",
        "agent_id": "niles",
        "intent_text": "Niles, do something with that new Logic file.",
        "expected_statuses": ("routed", "needs_operator_review"),
        "expected_agent_id": "niles",
        "expected_blocker": "metadata_only_until_file_and_write_approval",
    },
    {
        "smoke_test_id": "hermes_advisory_synthesis",
        "agent_id": "hermes",
        "intent_text": "Hermes, synthesize current posture.",
        "expected_statuses": ("routed", "needs_operator_review"),
        "expected_agent_id": "hermes",
        "expected_blocker": "advisory_only_no_canonical_promotion",
    },
    {
        "smoke_test_id": "report_bridge_posture",
        "agent_id": "report_bridge",
        "intent_text": "Report Bridge, summarize report package posture.",
        "expected_statuses": ("routed", "needs_operator_review"),
        "expected_agent_id": "report_bridge",
        "expected_blocker": "sanitized_package_intake_only_no_remote_control",
    },
)


@dataclass(frozen=True)
class ReadinessBuildResult:
    run_id: str
    db_path: str
    agent_count: int
    ready_for_dry_run_count: int
    partial_count: int
    blocked_count: int
    unknown_review_count: int


@dataclass(frozen=True)
class StartSequenceResult:
    run_id: str
    db_path: str
    dry_run: bool
    overall_status: str
    pass_count: int
    warn_count: int
    block_count: int
    next_safe_move: str


@dataclass(frozen=True)
class SmokeTestRunResult:
    run_id: str
    db_path: str
    smoke_test_count: int
    passed_count: int
    failed_count: int
    no_execution_occurred: bool


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


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_count(conn: sqlite3.Connection, table_name: str) -> int:
    if not _table_exists(conn, table_name):
        return 0
    return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS agent_runtime_readiness_runs (
  run_id TEXT PRIMARY KEY,
  readiness_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  agent_count INTEGER NOT NULL DEFAULT 0,
  ready_for_dry_run_count INTEGER NOT NULL DEFAULT 0,
  partial_count INTEGER NOT NULL DEFAULT 0,
  blocked_count INTEGER NOT NULL DEFAULT 0,
  unknown_review_count INTEGER NOT NULL DEFAULT 0,
  live_agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  autonomous_loop_allowed INTEGER NOT NULL DEFAULT 0,
  telegram_api_allowed INTEGER NOT NULL DEFAULT 0,
  gmail_api_allowed INTEGER NOT NULL DEFAULT 0,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  arbitrary_shell_allowed INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  approval_bypass_allowed INTEGER NOT NULL DEFAULT 0,
  no_go_raw_access_allowed INTEGER NOT NULL DEFAULT 0,
  client_deployment_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_runtime_components (
  component_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  lane_id TEXT,
  registered_in_agent_lane_registry INTEGER NOT NULL DEFAULT 0,
  source_kinds_supported_json TEXT NOT NULL,
  intent_routing_supported INTEGER NOT NULL DEFAULT 0,
  operator_inbox_supported INTEGER NOT NULL DEFAULT 0,
  action_path_supported INTEGER NOT NULL DEFAULT 0,
  read_model_surface_available INTEGER NOT NULL DEFAULT 0,
  required_credentials_present TEXT NOT NULL DEFAULT 'unknown',
  telegram_wired INTEGER NOT NULL DEFAULT 0,
  model_backend_available TEXT NOT NULL DEFAULT 'unknown',
  can_execute_directly INTEGER NOT NULL DEFAULT 0,
  can_bypass_approval INTEGER NOT NULL DEFAULT 0,
  can_read_no_go_raw INTEGER NOT NULL DEFAULT 0,
  readiness_status TEXT NOT NULL,
  blockers_json TEXT NOT NULL,
  next_safe_test TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES agent_runtime_readiness_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_runtime_checks (
  check_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  check_name TEXT NOT NULL,
  status TEXT NOT NULL,
  summary TEXT NOT NULL,
  details_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES agent_runtime_readiness_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_runtime_blockers (
  blocker_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  agent_id TEXT,
  blocker_kind TEXT NOT NULL,
  severity TEXT NOT NULL,
  summary TEXT NOT NULL,
  next_safe_move TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES agent_runtime_readiness_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_runtime_smoke_tests (
  smoke_test_receipt_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  smoke_test_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  intent_text_preview TEXT NOT NULL,
  intent_id TEXT,
  routed_agent_id TEXT,
  routed_lane_id TEXT,
  intent_status TEXT NOT NULL,
  expected_blocker TEXT NOT NULL,
  pass_fail TEXT NOT NULL,
  no_execution_occurred INTEGER NOT NULL DEFAULT 1,
  no_external_api_called INTEGER NOT NULL DEFAULT 1,
  receipt_summary TEXT NOT NULL,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_runtime_start_sequence_steps (
  step_receipt_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  step_order INTEGER NOT NULL,
  step_name TEXT NOT NULL,
  status TEXT NOT NULL,
  summary TEXT NOT NULL,
  details_json TEXT NOT NULL,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_runtime_receipts (
  receipt_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  receipt_kind TEXT NOT NULL,
  status TEXT NOT NULL,
  summary TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_agent_runtime_components_run ON agent_runtime_components(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_agent_runtime_components_agent ON agent_runtime_components(agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_agent_runtime_smoke_tests_run ON agent_runtime_smoke_tests(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_agent_runtime_start_sequence_run ON agent_runtime_start_sequence_steps(run_id)",
    )


def init_agent_runtime_readiness_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    init_business_ops_ledger(path)
    init_agent_lane_registry_schema(path)
    init_intent_router_schema(path)
    init_operator_action_schema(path)
    init_operator_action_inbox_schema(path)
    init_file_event_queue_schema(path)
    init_local_automation_schema(path)
    init_report_bridge_schema(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def agent_runtime_readiness_table_names(db_path: str | Path | None = None) -> set[str]:
    path = init_agent_runtime_readiness_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        return {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'agent_runtime_%'"
            ).fetchall()
        }
    finally:
        conn.close()


def _ensure_seeded_base_tables(db_path: str | Path | None) -> str:
    path = init_agent_runtime_readiness_schema(db_path)
    seed_agent_lane_registry(db_path=path)
    seed_local_automation_registry(db_path=path)
    return path


def _agent_source_kinds(conn: sqlite3.Connection, agent_id: str) -> list[str]:
    if not _table_exists(conn, "agent_lane_source_kinds"):
        return []
    rows = conn.execute(
        """
SELECT source_kind
FROM agent_lane_source_kinds
WHERE agent_id = ?
ORDER BY source_kind
""".strip(),
        (agent_id,),
    ).fetchall()
    return [row[0] for row in rows]


def _latest_agent_lane_row(conn: sqlite3.Connection, agent_id: str) -> sqlite3.Row | None:
    if not _table_exists(conn, "agent_lanes"):
        return None
    return conn.execute(
        """
SELECT *
FROM agent_lanes
WHERE agent_id = ?
ORDER BY updated_at DESC, created_at DESC
LIMIT 1
""".strip(),
        (agent_id,),
    ).fetchone()


def _insert_check(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    check_name: str,
    status: str,
    summary: str,
    details: dict[str, Any],
    now: str,
) -> None:
    conn.execute(
        """
INSERT OR REPLACE INTO agent_runtime_checks (
  check_id, run_id, check_name, status, summary, details_json, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
""".strip(),
        (
            _row_id("agent_runtime_check", run_id, check_name),
            run_id,
            check_name,
            status,
            summary,
            stable_json(details),
            now,
        ),
    )


def _insert_blocker(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    agent_id: str | None,
    blocker_kind: str,
    severity: str,
    summary: str,
    next_safe_move: str,
    now: str,
) -> None:
    conn.execute(
        """
INSERT OR REPLACE INTO agent_runtime_blockers (
  blocker_id, run_id, agent_id, blocker_kind, severity, summary, next_safe_move, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
        (
            _row_id("agent_runtime_blocker", run_id, agent_id or "global", blocker_kind, summary),
            run_id,
            agent_id,
            blocker_kind,
            severity,
            summary,
            next_safe_move,
            now,
        ),
    )


def build_agent_runtime_readiness(
    *,
    db_path: str | Path | None = None,
    run_id: str | None = None,
) -> ReadinessBuildResult:
    path = _ensure_seeded_base_tables(db_path)
    now = utc_now()
    resolved_run_id = run_id or _row_id("agent_runtime_run", now, READINESS_VERSION)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
INSERT OR REPLACE INTO agent_runtime_readiness_runs (
  run_id, readiness_version, created_at, completed_at, notes
) VALUES (?, ?, ?, ?, ?)
""".strip(),
            (
                resolved_run_id,
                READINESS_VERSION,
                now,
                now,
                "Readiness registry only; no live agent activation or execution authority.",
            ),
        )

        required_tables = {
            "agent_lane_registry": "agent_lanes",
            "intent_router": "intent_records",
            "operator_intent_inbox": "operator_action_inbox_imports",
            "operator_action_path": "operator_action_requests",
            "file_event_queue": "file_event_queue",
            "local_automation": "local_automation_tasks",
            "report_bridge": "report_bridge_packages",
        }
        for check_name, table_name in required_tables.items():
            exists = _table_exists(conn, table_name)
            count = _table_count(conn, table_name)
            status = "pass" if exists else "block"
            summary = f"{table_name} exists with {count} rows" if exists else f"{table_name} table is missing"
            _insert_check(
                conn,
                run_id=resolved_run_id,
                check_name=check_name,
                status=status,
                summary=summary,
                details={"table": table_name, "row_count": count},
                now=now,
            )
            if not exists:
                _insert_blocker(
                    conn,
                    run_id=resolved_run_id,
                    agent_id=None,
                    blocker_kind=f"{check_name}_missing",
                    severity="block",
                    summary=summary,
                    next_safe_move=f"initialize {table_name} through its owning substrate script before runtime testing",
                    now=now,
                )

        statuses: list[str] = []
        expected_agents = {seed.agent_id for seed in DEFAULT_AGENT_LANE_SEEDS}
        for agent_id in REQUIRED_AGENT_IDS:
            row = _latest_agent_lane_row(conn, agent_id)
            registered = row is not None
            source_kinds = _agent_source_kinds(conn, agent_id)
            unsafe_flags = {
                "can_execute": bool(row["can_execute"]) if row else False,
                "can_bypass_approval": bool(row["can_bypass_approval"]) if row else False,
                "can_read_no_go_raw": bool(row["can_read_no_go_raw"]) if row else False,
                "can_call_network": bool(row["can_call_network"]) if row else False,
                "can_run_tools": bool(row["can_run_tools"]) if row else False,
                "can_call_models": bool(row["can_call_models"]) if row else False,
                "runtime_authority": bool(row["runtime_authority"]) if row else False,
                "client_deployment_authority": bool(row["client_deployment_authority"]) if row else False,
            }
            blockers: list[str] = []
            if not registered:
                blockers.append("agent_missing_from_agent_lane_registry")
            if any(unsafe_flags.values()):
                blockers.append("agent_has_unsafe_authority_flags")
            if not source_kinds:
                blockers.append("source_kinds_not_registered")

            read_model_surface = (ROOT / "generated/read_models/agent_lanes.json").exists()
            intent_routing_supported = _table_exists(conn, "intent_records") and registered
            operator_inbox_supported = _table_exists(conn, "operator_action_inbox_imports")
            action_path_supported = _table_exists(conn, "operator_action_allowed_commands")

            if unsafe_flags["can_execute"] or unsafe_flags["can_bypass_approval"]:
                readiness_status = "blocked"
            elif blockers:
                readiness_status = "partial"
            elif not read_model_surface:
                readiness_status = "partial"
                blockers.append("agent_lanes_read_model_not_found")
            elif agent_id not in expected_agents:
                readiness_status = "unknown_review"
                blockers.append("agent_not_in_default_seed_set")
            else:
                readiness_status = "ready_for_dry_run"

            statuses.append(readiness_status)
            for blocker in blockers:
                _insert_blocker(
                    conn,
                    run_id=resolved_run_id,
                    agent_id=agent_id,
                    blocker_kind=blocker,
                    severity="block" if readiness_status == "blocked" else "warn",
                    summary=f"{agent_id}: {blocker}",
                    next_safe_move="keep dry-run only; repair registry metadata before any live activation lane",
                    now=now,
                )

            conn.execute(
                """
INSERT OR REPLACE INTO agent_runtime_components (
  component_id, run_id, agent_id, lane_id, registered_in_agent_lane_registry,
  source_kinds_supported_json, intent_routing_supported, operator_inbox_supported,
  action_path_supported, read_model_surface_available, required_credentials_present,
  telegram_wired, model_backend_available, can_execute_directly,
  can_bypass_approval, can_read_no_go_raw, readiness_status,
  blockers_json, next_safe_test, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
                (
                    _row_id("agent_runtime_component", resolved_run_id, agent_id),
                    resolved_run_id,
                    agent_id,
                    row["lane_id"] if row else None,
                    int(registered),
                    stable_json(source_kinds),
                    int(intent_routing_supported),
                    int(operator_inbox_supported),
                    int(action_path_supported),
                    int(read_model_surface),
                    "unknown",
                    "unknown",
                    int(unsafe_flags["can_execute"]),
                    int(unsafe_flags["can_bypass_approval"]),
                    int(unsafe_flags["can_read_no_go_raw"]),
                    readiness_status,
                    stable_json(blockers),
                    _next_safe_test(agent_id),
                    now,
                ),
            )

        status_counts = Counter(statuses)
        conn.execute(
            """
UPDATE agent_runtime_readiness_runs
SET agent_count = ?,
    ready_for_dry_run_count = ?,
    partial_count = ?,
    blocked_count = ?,
    unknown_review_count = ?,
    completed_at = ?
WHERE run_id = ?
""".strip(),
            (
                len(REQUIRED_AGENT_IDS),
                status_counts.get("ready_for_dry_run", 0),
                status_counts.get("partial", 0),
                status_counts.get("blocked", 0),
                status_counts.get("unknown_review", 0),
                now,
                resolved_run_id,
            ),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO agent_runtime_receipts (
  receipt_id, run_id, receipt_kind, status, summary, payload_json, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
""".strip(),
            (
                _row_id("agent_runtime_receipt", resolved_run_id, "readiness_build"),
                resolved_run_id,
                "readiness_build",
                "recorded",
                "Agent runtime readiness recorded without activating agents.",
                stable_json({"status_counts": dict(status_counts), "no_authority_flags": NO_AUTHORITY_FLAGS}),
                now,
            ),
        )
        conn.commit()
        return ReadinessBuildResult(
            run_id=resolved_run_id,
            db_path=path,
            agent_count=len(REQUIRED_AGENT_IDS),
            ready_for_dry_run_count=status_counts.get("ready_for_dry_run", 0),
            partial_count=status_counts.get("partial", 0),
            blocked_count=status_counts.get("blocked", 0),
            unknown_review_count=status_counts.get("unknown_review", 0),
        )
    finally:
        conn.close()


def _next_safe_test(agent_id: str) -> str:
    return {
        "chief": "route a status or Markdown organization request; no file moves",
        "cassandra": "route a summary request; no external message send",
        "guardian": "route a safety question; no no-go raw reads",
        "niles": "route a Logic-file request; metadata-only until file is resolved and approved",
        "hermes": "route an advisory synthesis request; no canonical promotion",
        "report_bridge": "query Report Bridge posture; no remote control or raw client data",
    }.get(agent_id, "route a dry-run intent and keep approval required")


def _mirror_health(db_path: str | Path | None) -> dict[str, Any]:
    try:
        return query_mac_mirror_report_section(
            db_path=db_path,
            section="generated-read-model-mirror",
        )
    except Exception as exc:  # pragma: no cover - defensive reporting path
        return {
            "status": "error",
            "counts": {"missing_expected": 0, "extra": 0, "hash_mismatch": 0},
            "error": str(exc),
        }


def run_agent_start_sequence(
    *,
    db_path: str | Path | None = None,
    dry_run: bool = True,
    run_id: str | None = None,
) -> StartSequenceResult:
    readiness = build_agent_runtime_readiness(db_path=db_path, run_id=run_id)
    path = readiness.db_path
    now = utc_now()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    steps: list[dict[str, Any]] = []
    try:
        def add_step(name: str, status: str, summary: str, details: dict[str, Any] | None = None) -> None:
            steps.append(
                {
                    "step_order": len(steps) + 1,
                    "step_name": name,
                    "status": status,
                    "summary": summary,
                    "details": details or {},
                }
            )

        add_step("ledger_reachable", "pass", "Business Ops ledger is reachable.", {"db_path": path})
        add_step(
            "agent_lane_registry_present",
            "pass" if _table_count(conn, "agent_lanes") >= len(REQUIRED_AGENT_IDS) else "block",
            f"Agent Lane Registry rows: {_table_count(conn, 'agent_lanes')}.",
        )
        add_step(
            "intent_router_present",
            "pass" if _table_exists(conn, "intent_records") else "block",
            "Intent Router table is present." if _table_exists(conn, "intent_records") else "Intent Router table is missing.",
        )
        add_step(
            "operator_intent_inbox_present",
            "pass" if _table_exists(conn, "operator_action_inbox_imports") else "block",
            "Operator Intent Inbox table is present." if _table_exists(conn, "operator_action_inbox_imports") else "Operator Intent Inbox table is missing.",
        )
        add_step(
            "operator_action_path_present",
            "pass" if _table_exists(conn, "operator_action_allowed_commands") else "block",
            f"Operator Action allowlist rows: {_table_count(conn, 'operator_action_allowed_commands')}.",
        )
        add_step(
            "file_event_queue_present",
            "pass" if _table_exists(conn, "file_event_queue") else "block",
            f"File Event Queue rows: {_table_count(conn, 'file_event_queue')}.",
        )
        mirror = _mirror_health(path)
        mirror_counts = mirror.get("counts", {})
        missing = int(mirror_counts.get("missing_expected", 0) or 0)
        extra = int(mirror_counts.get("extra", 0) or 0)
        mismatch = int(mirror_counts.get("hash_mismatch", 0) or 0)
        if missing == 0 and extra == 0 and mismatch == 0 and mirror.get("status", "ok") != "error":
            mirror_status = "pass"
            mirror_summary = "Read-model mirror is current."
        elif mirror.get("status") == "error" or mismatch:
            mirror_status = "block"
            mirror_summary = f"Read-model mirror has mismatches or query error: missing={missing}, extra={extra}, hash_mismatch={mismatch}."
        else:
            mirror_status = "warn"
            mirror_summary = f"Read-model mirror is stale or needs review: missing={missing}, extra={extra}, hash_mismatch={mismatch}."
        add_step("read_model_mirror_health", mirror_status, mirror_summary, mirror)
        add_step(
            "local_automation_services_present",
            "pass" if _table_count(conn, "local_automation_tasks") >= 2 else "warn",
            f"Local automation task rows: {_table_count(conn, 'local_automation_tasks')}.",
        )
        unsafe_agents = int(
            conn.execute(
                """
SELECT COUNT(*)
FROM agent_lanes
WHERE can_execute != 0
   OR can_bypass_approval != 0
   OR can_read_no_go_raw != 0
   OR can_call_network != 0
   OR can_run_tools != 0
   OR can_call_models != 0
   OR runtime_authority != 0
   OR client_deployment_authority != 0
""".strip()
            ).fetchone()[0]
        )
        add_step(
            "agent_no_authority_bounds",
            "pass" if unsafe_agents == 0 else "block",
            f"Unsafe agent authority rows: {unsafe_agents}.",
        )
        add_step(
            "smoke_test_candidates_available",
            "pass",
            f"{len(SMOKE_TESTS)} deterministic smoke-test candidates are available; no live loops started.",
        )

        for step in steps:
            conn.execute(
                """
INSERT OR REPLACE INTO agent_runtime_start_sequence_steps (
  step_receipt_id, run_id, step_order, step_name, status, summary, details_json, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
                (
                    _row_id("agent_runtime_step", readiness.run_id, step["step_name"]),
                    readiness.run_id,
                    step["step_order"],
                    step["step_name"],
                    step["status"],
                    step["summary"],
                    stable_json(step["details"]),
                    now,
                ),
            )

        status_counts = Counter(step["status"] for step in steps)
        overall_status = "blocked" if status_counts.get("block", 0) else "partial" if status_counts.get("warn", 0) else "ready_for_dry_run"
        next_safe_move = (
            "resolve blocking readiness checks before smoke tests"
            if overall_status == "blocked"
            else "run deterministic smoke tests; keep all execution and external APIs disabled"
            if overall_status == "ready_for_dry_run"
            else "run smoke tests only if the stale/read-only mirror posture is acceptable for this morning check"
        )
        conn.execute(
            """
INSERT OR REPLACE INTO agent_runtime_receipts (
  receipt_id, run_id, receipt_kind, status, summary, payload_json, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
""".strip(),
            (
                _row_id("agent_runtime_receipt", readiness.run_id, "start_sequence"),
                readiness.run_id,
                "start_sequence",
                overall_status,
                "Agent start sequence dry-run recorded; no agents were activated.",
                stable_json({"dry_run": dry_run, "steps": steps, "next_safe_move": next_safe_move}),
                now,
            ),
        )
        conn.commit()
        return StartSequenceResult(
            run_id=readiness.run_id,
            db_path=path,
            dry_run=dry_run,
            overall_status=overall_status,
            pass_count=status_counts.get("pass", 0),
            warn_count=status_counts.get("warn", 0),
            block_count=status_counts.get("block", 0),
            next_safe_move=next_safe_move,
        )
    finally:
        conn.close()


def run_agent_smoke_tests(
    *,
    db_path: str | Path | None = None,
    run_id: str | None = None,
) -> SmokeTestRunResult:
    readiness = build_agent_runtime_readiness(db_path=db_path, run_id=run_id)
    path = readiness.db_path
    now = utc_now()
    passed = 0
    failed = 0
    for smoke in SMOKE_TESTS:
        smoke_id = smoke["smoke_test_id"]
        intent_id = _row_id("smoke_intent", readiness.run_id, smoke_id)
        route = route_operator_intent(
            text=smoke["intent_text"],
            source_kind="cli",
            source_channel="agent_runtime_smoke_test",
            requested_by="agent_runtime_readiness",
            db_path=path,
            intent_id=intent_id,
            run_id=_row_id("smoke_route_run", readiness.run_id, smoke_id),
        )
        if smoke_id == "report_bridge_posture":
            build_report_bridge_report(db_path=path, report="summary")
        expected_agent = smoke["expected_agent_id"]
        expected_statuses = set(smoke["expected_statuses"])
        route_ok = (
            route.routed_agent_id == expected_agent
            and route.status in expected_statuses
            and not route.execution_allowed
            and not route.action_request_created
        )
        result = "pass" if route_ok else "fail"
        if route_ok:
            passed += 1
        else:
            failed += 1
        conn = sqlite3.connect(path)
        try:
            conn.execute(
                """
INSERT OR REPLACE INTO agent_runtime_smoke_tests (
  smoke_test_receipt_id, run_id, smoke_test_id, agent_id,
  intent_text_preview, intent_id, routed_agent_id, routed_lane_id,
  intent_status, expected_blocker, pass_fail, no_execution_occurred,
  no_external_api_called, receipt_summary, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
""".strip(),
                (
                    _row_id("agent_runtime_smoke", readiness.run_id, smoke_id),
                    readiness.run_id,
                    smoke_id,
                    smoke["agent_id"],
                    smoke["intent_text"][:180],
                    route.intent_id,
                    route.routed_agent_id,
                    route.routed_lane_id,
                    route.status,
                    smoke["expected_blocker"],
                    result,
                    f"{smoke_id}: {result}; routed={route.routed_agent_id}; status={route.status}; no execution occurred.",
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
INSERT OR REPLACE INTO agent_runtime_receipts (
  receipt_id, run_id, receipt_kind, status, summary, payload_json, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
""".strip(),
            (
                _row_id("agent_runtime_receipt", readiness.run_id, "smoke_tests"),
                readiness.run_id,
                "smoke_tests",
                "pass" if failed == 0 else "failed",
                "Deterministic smoke tests routed intents without executing actions.",
                stable_json({"passed": passed, "failed": failed, "no_authority_flags": NO_AUTHORITY_FLAGS}),
                now,
            ),
        )
        conn.commit()
        return SmokeTestRunResult(
            run_id=readiness.run_id,
            db_path=path,
            smoke_test_count=len(SMOKE_TESTS),
            passed_count=passed,
            failed_count=failed,
            no_execution_occurred=True,
        )
    finally:
        conn.close()


def build_agent_runtime_readiness_report(
    *,
    db_path: str | Path | None = None,
    run_id: str | None = None,
    report: str = "summary",
) -> dict[str, Any]:
    if report not in {"summary", "components", "blockers", "smoke-tests", "start-sequence"}:
        raise ValueError(f"unknown readiness report: {report}")
    path = init_agent_runtime_readiness_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id
        if not resolved_run_id:
            row = conn.execute(
                """
SELECT run_id
FROM agent_runtime_readiness_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
            ).fetchone()
            resolved_run_id = row["run_id"] if row else None
        if not resolved_run_id:
            return {
                "status": "empty",
                "report": report,
                "db_path": path,
                "run_id": None,
                "counts": {},
                "items": [],
                "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
            }

        run = conn.execute(
            "SELECT * FROM agent_runtime_readiness_runs WHERE run_id = ?",
            (resolved_run_id,),
        ).fetchone()
        components = _dict_rows(
            conn,
            "SELECT * FROM agent_runtime_components WHERE run_id = ? ORDER BY agent_id",
            (resolved_run_id,),
        )
        blockers = _dict_rows(
            conn,
            "SELECT * FROM agent_runtime_blockers WHERE run_id = ? ORDER BY severity DESC, agent_id, blocker_kind",
            (resolved_run_id,),
        )
        smoke_tests = _dict_rows(
            conn,
            "SELECT * FROM agent_runtime_smoke_tests WHERE run_id = ? ORDER BY smoke_test_id",
            (resolved_run_id,),
        )
        steps = _dict_rows(
            conn,
            "SELECT * FROM agent_runtime_start_sequence_steps WHERE run_id = ? ORDER BY step_order",
            (resolved_run_id,),
        )
        status_counts = Counter(item["readiness_status"] for item in components)
        items = {
            "summary": components[:8],
            "components": components,
            "blockers": blockers,
            "smoke-tests": smoke_tests,
            "start-sequence": steps,
        }[report]
        return {
            "status": "ok",
            "report": report,
            "db_path": path,
            "run_id": resolved_run_id,
            "run": dict(run) if run else None,
            "counts": {
                "agent_count": len(components),
                "ready_for_dry_run": status_counts.get("ready_for_dry_run", 0),
                "partial": status_counts.get("partial", 0),
                "blocked": status_counts.get("blocked", 0),
                "unknown_review": status_counts.get("unknown_review", 0),
                "blocker_count": len(blockers),
                "smoke_test_count": len(smoke_tests),
                "smoke_passed": sum(1 for item in smoke_tests if item["pass_fail"] == "pass"),
                "smoke_failed": sum(1 for item in smoke_tests if item["pass_fail"] == "fail"),
                "start_sequence_steps": len(steps),
                "start_sequence_blocks": sum(1 for item in steps if item["status"] == "block"),
                "start_sequence_warnings": sum(1 for item in steps if item["status"] == "warn"),
            },
            "components": components,
            "blockers": blockers,
            "smoke_tests": smoke_tests,
            "start_sequence_steps": steps,
            "items": items,
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def _counts_line(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def format_agent_runtime_readiness_report(payload: dict[str, Any]) -> str:
    counts = payload.get("counts", {})
    lines = [
        f"Agent Runtime Readiness v0 - {payload['report']}",
        "",
        f"Run: `{payload.get('run_id') or 'none'}`",
        f"Agents: {counts.get('agent_count', 0)}",
        f"Ready for dry run: {counts.get('ready_for_dry_run', 0)}",
        f"Partial: {counts.get('partial', 0)}",
        f"Blocked: {counts.get('blocked', 0)}",
        f"Smoke tests: passed={counts.get('smoke_passed', 0)}, failed={counts.get('smoke_failed', 0)}",
        f"Start sequence: steps={counts.get('start_sequence_steps', 0)}, warnings={counts.get('start_sequence_warnings', 0)}, blocks={counts.get('start_sequence_blocks', 0)}",
        "",
        "Items:",
    ]
    for item in payload.get("items") or []:
        if "agent_id" in item and "readiness_status" in item:
            lines.append(
                f"- `{item['agent_id']}` / `{item.get('lane_id') or 'none'}`: {item['readiness_status']}; next={item['next_safe_test']}"
            )
        elif "blocker_kind" in item:
            lines.append(
                f"- `{item.get('agent_id') or 'global'}` {item['severity']}: {item['summary']} -> {item['next_safe_move']}"
            )
        elif "smoke_test_id" in item:
            lines.append(
                f"- `{item['smoke_test_id']}`: {item['pass_fail']}; routed={item.get('routed_agent_id')}; status={item['intent_status']}"
            )
        elif "step_name" in item:
            lines.append(f"- `{item['step_name']}`: {item['status']}; {item['summary']}")
    if not payload.get("items"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Readiness is dry-run posture only; no live agents, autonomous loops, Telegram/Gmail APIs, model calls, tools, arbitrary shell, approval bypass, no-go raw access, or client deployment.",
        ]
    )
    return "\n".join(lines)


def build_agent_runtime_readiness_read_model(
    *,
    db_path: str | Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    report = build_agent_runtime_readiness_report(db_path=db_path, run_id=run_id, report="summary")
    if report["status"] == "empty":
        build_agent_runtime_readiness(db_path=db_path, run_id=run_id)
        report = build_agent_runtime_readiness_report(db_path=db_path, run_id=run_id, report="summary")

    components = report.get("components", [])
    blockers = report.get("blockers", [])
    smoke_tests = report.get("smoke_tests", [])
    steps = report.get("start_sequence_steps", [])
    status_counts = Counter(component["readiness_status"] for component in components)
    smoke_counts = Counter(test["pass_fail"] for test in smoke_tests)
    latest_start_status = "not_run"
    if steps:
        step_counts = Counter(step["status"] for step in steps)
        latest_start_status = "blocked" if step_counts.get("block", 0) else "partial" if step_counts.get("warn", 0) else "ready_for_dry_run"

    stored_blockers = [
        {
            "agent_id": blocker["agent_id"],
            "blocker_kind": blocker["blocker_kind"],
            "severity": blocker["severity"],
            "summary": blocker["summary"],
            "next_safe_move": blocker["next_safe_move"],
        }
        for blocker in blockers
    ]
    step_blockers = [
        {
            "agent_id": None,
            "blocker_kind": step["step_name"],
            "severity": "block" if step["status"] == "block" else "warn",
            "summary": step["summary"],
            "next_safe_move": "repair this start-sequence check before treating the readiness harness as fully current",
        }
        for step in steps
        if step["status"] in {"block", "warn"}
    ]

    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "mode": "agent_runtime_readiness_dry_run_only",
        "generated_at": utc_now(),
        "source_ledger_path": _display_path(report["db_path"]),
        "source_ledger_namespace": "agent_runtime_*",
        "latest_run_id": report["run_id"],
        "agent_count": len(components),
        "ready_for_dry_run_count": status_counts.get("ready_for_dry_run", 0),
        "partial_count": status_counts.get("partial", 0),
        "blocked_count": status_counts.get("blocked", 0),
        "unknown_review_count": status_counts.get("unknown_review", 0),
        "latest_start_sequence_status": latest_start_status,
        "smoke_test_results": {
            "total": len(smoke_tests),
            "passed": smoke_counts.get("pass", 0),
            "failed": smoke_counts.get("fail", 0),
            "items": [
                {
                    "smoke_test_id": test["smoke_test_id"],
                    "agent_id": test["agent_id"],
                    "pass_fail": test["pass_fail"],
                    "routed_agent_id": test["routed_agent_id"],
                    "intent_status": test["intent_status"],
                    "no_execution_occurred": bool(test["no_execution_occurred"]),
                }
                for test in smoke_tests
            ],
        },
        "components": [
            {
                "agent_id": component["agent_id"],
                "lane_id": component["lane_id"],
                "readiness_status": component["readiness_status"],
                "source_kinds_supported": json.loads(component["source_kinds_supported_json"]),
                "intent_routing_supported": bool(component["intent_routing_supported"]),
                "operator_inbox_supported": bool(component["operator_inbox_supported"]),
                "action_path_supported": bool(component["action_path_supported"]),
                "telegram_wired": bool(component["telegram_wired"]),
                "model_backend_available": component["model_backend_available"],
                "can_execute_directly": bool(component["can_execute_directly"]),
                "can_bypass_approval": bool(component["can_bypass_approval"]),
                "can_read_no_go_raw": bool(component["can_read_no_go_raw"]),
                "next_safe_test": component["next_safe_test"],
            }
            for component in components
        ],
        "blockers": stored_blockers + step_blockers,
        "next_safe_morning_tests": [
            "Ask Chief to summarize system status or propose a Markdown reorg plan; expect no file moves.",
            "Ask Cassandra to summarize what changed; expect no external message send.",
            "Ask Guardian whether a proposed path is safe; expect no no-go raw reads.",
            "Ask Niles about a recent Logic file; expect metadata-only routing and approval boundaries.",
            "Ask Hermes for advisory synthesis; expect no canonical promotion.",
            "Check Report Bridge posture; expect sanitized package/report status only.",
        ],
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "claims_not_made": [
            "live_agent_activation",
            "autonomous_loop",
            "telegram_api",
            "gmail_api",
            "model_call",
            "arbitrary_shell",
            "tool_execution",
            "approval_bypass",
            "no_go_raw_access",
            "client_deployment",
        ],
    }


def format_agent_runtime_readiness_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# Agent Runtime Readiness Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over `agent_runtime_*` readiness, start-sequence, and smoke-test receipts.",
        "- It shows whether role-scoped agent lanes are ready for dry-run morning tests.",
        "",
        "What this is not:",
        "- It is not live agent activation, autonomous looping, Telegram/Gmail wiring, model calling, tool execution, arbitrary shell, approval bypass, or client deployment.",
        "",
        "Summary:",
        f"- Agents represented: {read_model['agent_count']}.",
        f"- Ready for dry run: {read_model['ready_for_dry_run_count']}.",
        f"- Partial: {read_model['partial_count']}.",
        f"- Blocked: {read_model['blocked_count']}.",
        f"- Unknown review: {read_model['unknown_review_count']}.",
        f"- Latest start sequence status: `{read_model['latest_start_sequence_status']}`.",
        f"- Smoke tests: passed={read_model['smoke_test_results']['passed']}, failed={read_model['smoke_test_results']['failed']}.",
        "",
        "Agent components:",
    ]
    for component in read_model.get("components", []):
        lines.append(
            f"- `{component['agent_id']}` / `{component['lane_id']}`: {component['readiness_status']}; next={component['next_safe_test']}"
        )
    lines.extend(["", "Blockers:"])
    if read_model.get("blockers"):
        for blocker in read_model["blockers"][:12]:
            lines.append(f"- `{blocker['agent_id'] or 'global'}` {blocker['severity']}: {blocker['summary']}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "Authority boundary:",
            "- live_agent_activation_allowed=false; autonomous_loop_allowed=false.",
            "- telegram_api_allowed=false; gmail_api_allowed=false; model_call_allowed=false.",
            "- arbitrary_shell_allowed=false; tool_execution_allowed=false; approval_bypass_allowed=false.",
            "- no_go_raw_access_allowed=false; client_deployment_allowed=false.",
            "",
            "Next safe morning tests:",
        ]
    )
    for item in read_model["next_safe_morning_tests"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def export_agent_runtime_readiness_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    run_id: str | None = None,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_agent_runtime_readiness_read_model(db_path=db_path, run_id=run_id)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_agent_runtime_readiness_read_model(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "agent_count": read_model["agent_count"],
        "ready_for_dry_run_count": read_model["ready_for_dry_run_count"],
        "partial_count": read_model["partial_count"],
        "blocked_count": read_model["blocked_count"],
        "smoke_passed": read_model["smoke_test_results"]["passed"],
        "smoke_failed": read_model["smoke_test_results"]["failed"],
        **NO_AUTHORITY_FLAGS,
    }


__all__ = [
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READINESS_VERSION",
    "READ_MODEL_VERSION",
    "REQUIRED_AGENT_IDS",
    "SMOKE_TESTS",
    "agent_runtime_readiness_table_names",
    "build_agent_runtime_readiness",
    "build_agent_runtime_readiness_read_model",
    "build_agent_runtime_readiness_report",
    "export_agent_runtime_readiness_read_model",
    "format_agent_runtime_readiness_read_model",
    "format_agent_runtime_readiness_report",
    "init_agent_runtime_readiness_schema",
    "run_agent_smoke_tests",
    "run_agent_start_sequence",
    "stable_json",
]
