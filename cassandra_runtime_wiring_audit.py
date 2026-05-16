"""Cassandra Runtime Wiring Audit v0 for OpenClaw.

This module records a metadata-only audit of Cassandra's legacy runtime wiring.
It does not run Repo B code, call Telegram APIs, send messages, read secrets,
start services, approve actions, or execute operator-supplied commands.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_presence import init_agent_presence_schema
from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger
from intent_router import init_intent_router_schema
from telegram_agent_intake import init_telegram_agent_intake_schema, record_telegram_update
from work_board import DEFAULT_BOARD_ID, init_work_board_schema


ROOT = Path(__file__).resolve().parent
AUDIT_VERSION = "cassandra_runtime_wiring_audit_v0"
READ_MODEL_VERSION = "cassandra_runtime_wiring_audit_read_model_v0"
DEFAULT_REPO_B_ROOT = Path("/home/openclaw_external/openclaw-runtime")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "cassandra_runtime_wiring_audit.json"
OPERATOR_EXPORT_NAME = "cassandra_runtime_wiring_audit_OPERATOR.md"

NO_AUTHORITY_FLAGS = {
    "telegram_send_allowed": False,
    "arbitrary_command_allowed": False,
    "repo_b_execution_allowed": False,
    "secret_access_allowed": False,
    "external_api_allowed": False,
    "approval_bypass_allowed": False,
}

CASSANDRA_SERVICES = (
    "cassandra-listener.service",
    "cassandra-watcher.service",
    "cassandra-briefing-scheduler.service",
)

REPO_A_CORE_SURFACES = (
    "telegram_agent_intake.py",
    "agent_presence.py",
    "intent_router.py",
    "agent_lane_registry.py",
    "operator_action_inbox.py",
    "work_board.py",
    "cassandra_identity.py",
    "capital_hilton_finance_fact_intake.py",
)

REPO_B_TARGET_FILES = (
    "cassandra_listener.py",
    "cassandra_brain.py",
    "cassandra_watcher.py",
    "cassandra_whisper_relay.py",
    "cassandra_briefing_brain.py",
    "cassandra_briefing_scheduler.py",
    "cassandra_capability.py",
    "cassandra_outreach.py",
    "chief_listener.py",
    "chief_router.py",
)

REPORT_SECTIONS = {"summary", "surfaces", "comparison", "roundtrip", "gaps", "recommendations"}

SENSITIVE_LOG_PATTERNS = (
    re.compile(r"\b\d{5,}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)\b(token|secret|password|passwd|api[_-]?key|bot[_-]?key|chat[_-]?id)\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)TELEGRAM_[A-Z0-9_]*\s*[:=]\s*\S+"),
)

LOG_TERM_PATTERNS = {
    "polling": re.compile(r"(?i)poll|polling|getUpdates|get_updates|offset"),
    "receive": re.compile(r"(?i)received|message|update|telegram"),
    "send": re.compile(r"(?i)sendMessage|send_message|sent|reply|ack"),
    "blocked": re.compile(r"(?i)block|blocked|approval|guardian|not allowed|denied"),
    "error": re.compile(r"(?i)traceback|error|exception|failed"),
    "you_online_yet": re.compile(r"(?i)you online yet"),
    "capital_hilton": re.compile(r"(?i)capital hilton"),
}

PURPOSES = {
    "telegram_agent_intake.py": "Governed Telegram intake metadata, storage receipts, and safe synthetic route proofs.",
    "agent_presence.py": "Agent presence and fixed recovery policy evidence; no Telegram round-trip proof.",
    "intent_router.py": "Deterministic operator-text routing to role-scoped lanes.",
    "agent_lane_registry.py": "Cassandra/Clara lane identity, advisory authority, and source posture.",
    "operator_action_inbox.py": "Approval-required action request import; rejects raw command/message execution.",
    "work_board.py": "Metadata-only work board cards and read-model linkage.",
    "cassandra_identity.py": "Cassandra/Clara designated-contact identity helpers.",
    "capital_hilton_finance_fact_intake.py": "Governed Capital Hilton finance fact intake and Clara external persona rule.",
    "cassandra_listener.py": "Cassandra Telegram listener and request/reply runtime.",
    "cassandra_brain.py": "Cassandra response, finance, reminder, outreach, and helper logic.",
    "cassandra_watcher.py": "Ambient watcher/reminder loop for Cassandra.",
    "cassandra_whisper_relay.py": "Voice transcript confidence, dedupe, and Cassandra relay logic.",
    "cassandra_briefing_brain.py": "Briefing generation and protected-window logic.",
    "cassandra_briefing_scheduler.py": "Scheduled briefing delivery loop.",
    "cassandra_capability.py": "Cassandra capability posture and refusal wording.",
    "cassandra_outreach.py": "Outreach/contact-state and notification helper logic.",
    "chief_listener.py": "Chief Telegram listener that can route Cassandra requests through Chief.",
    "chief_router.py": "Chief router with Cassandra and finance routing branches.",
}


@dataclass(frozen=True)
class CassandraWiringAuditResult:
    run_id: str
    db_path: str
    service_count: int
    repo_b_file_count: int
    already_ported_count: int
    unsafe_surface_count: int
    gap_count: int
    recommendation_count: int
    live_receive_proven: bool
    governed_storage_proven: bool
    reply_ready: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _bool(value: bool) -> int:
    return 1 if value else 0


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


def _sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 256), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _read_source(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _git_value(repo_root: Path, args: tuple[str, ...]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown"
    return result.stdout.strip() or "unknown"


def repo_metadata(repo_root: str | Path) -> dict[str, str]:
    root = Path(repo_root)
    return {
        "remote": _git_value(root, ("remote", "get-url", "origin")) if root.exists() else "missing",
        "branch": _git_value(root, ("branch", "--show-current")) if root.exists() else "missing",
        "commit": _git_value(root, ("rev-parse", "HEAD")) if root.exists() else "missing",
    }


def _safe_exec_summary(raw_exec: str, repo_root: Path) -> dict[str, Any]:
    scripts = re.findall(rf"{re.escape(repo_root.as_posix())}/[\w./-]+\.py", raw_exec)
    log_paths = re.findall(r"/mnt/c/OpenClaw/logs/[\w./-]+", raw_exec)
    env_sourced = ".env" in raw_exec
    return {
        "entrypoints": sorted(set(scripts)),
        "log_paths": sorted(set(log_paths)),
        "env_file_sourced": env_sourced,
        "raw_exec_stored": False,
    }


def _systemd_service_facts(repo_root: Path) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    try:
        result = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                *CASSANDRA_SERVICES,
                "-p",
                "Id",
                "-p",
                "LoadState",
                "-p",
                "ActiveState",
                "-p",
                "SubState",
                "-p",
                "MainPID",
                "-p",
                "ExecStart",
                "-p",
                "FragmentPath",
                "-p",
                "WorkingDirectory",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [
            {
                "service_name": service,
                "active_state": "unknown",
                "sub_state": "unknown",
                "main_pid": "",
                "fragment_path": "",
                "working_directory": "",
                "exec_entrypoints": [],
                "exec_log_paths": [],
                "env_file_sourced": False,
                "points_to_repo_a": False,
                "status_error": exc.__class__.__name__,
            }
            for service in CASSANDRA_SERVICES
        ]

    blocks = [block.strip() for block in result.stdout.split("\n\n") if block.strip()]
    by_id: dict[str, dict[str, str]] = {}
    for block in blocks:
        data: dict[str, str] = {}
        for line in block.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                data[key] = value
        if data.get("Id"):
            by_id[data["Id"]] = data
    for service in CASSANDRA_SERVICES:
        data = by_id.get(service, {})
        exec_summary = _safe_exec_summary(data.get("ExecStart", ""), repo_root)
        facts.append(
            {
                "service_name": service,
                "active_state": data.get("ActiveState", "unknown"),
                "sub_state": data.get("SubState", "unknown"),
                "main_pid": data.get("MainPID", ""),
                "fragment_path": data.get("FragmentPath", ""),
                "working_directory": data.get("WorkingDirectory", ""),
                "exec_entrypoints": exec_summary["entrypoints"],
                "exec_log_paths": exec_summary["log_paths"],
                "env_file_sourced": exec_summary["env_file_sourced"],
                "points_to_repo_a": any(str(path).startswith(repo_root.as_posix()) for path in exec_summary["entrypoints"]),
                "status_error": "" if result.returncode == 0 else f"systemctl_exit_{result.returncode}",
            }
        )
    return facts


def _scan_log(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    if not path.exists() or not path.is_file():
        return {
            "log_path": path_text,
            "exists": False,
            "size_bytes": 0,
            "line_count": 0,
            "sensitive_content_detected": False,
            "term_counts": {},
        }
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {
            "log_path": path_text,
            "exists": True,
            "size_bytes": int(path.stat().st_size),
            "line_count": 0,
            "sensitive_content_detected": False,
            "term_counts": {},
            "read_error": True,
        }
    return {
        "log_path": path_text,
        "exists": True,
        "size_bytes": int(path.stat().st_size),
        "line_count": len(text.splitlines()),
        "sensitive_content_detected": any(pattern.search(text) for pattern in SENSITIVE_LOG_PATTERNS),
        "term_counts": {name: len(pattern.findall(text)) for name, pattern in LOG_TERM_PATTERNS.items()},
    }


def _source_flags(source: str, filename: str) -> dict[str, Any]:
    lowered = source.lower()
    receives_telegram = "applicationbuilder" in lowered and ("messagehandler" in lowered or "filters." in lowered)
    sends_telegram = bool(
        re.search(
            r"(from\s+cassandra_sender\s+import|import\s+cassandra_sender|\.reply_text\(|\bsend_message\(|\bsend_voice_note\(|bot\.send_message\(|send_chat_action\()",
            source,
        )
    )
    reads_env_token = bool(
        re.search(r"os\.environ(?:\.get)?\([^)]*(TOKEN|CHAT|BOT|AUTHORIZED)", source)
        or re.search(r"os\.environ\[[^\]]*(TOKEN|CHAT|BOT|AUTHORIZED)", source)
        or re.search(r"(?<!os)\.env\b|\.chief\.env", source)
    )
    writes_files = bool(
        re.search(r"\.write_text\(", source)
        or re.search(r"\bopen\([^)]*['\"][aw]", source)
        or re.search(r"\.open\([^)]*['\"][aw]", source)
        or "json.dump" in source
        or "sqlite3.connect" in source
    )
    direct_action_path = bool(
        re.search(
            r"(\bsubprocess\.|import\s+subprocess|create_subprocess_exec|os\.system\(|os\.execv\(|Popen\(|from\s+google_access_broker|import\s+google_access_broker|from\s+invoice_generator|import\s+invoice_generator|\bdispatch_due_actions\(|\brequest_operator_action\()",
            source,
        )
    )
    old_storage = any(
        token in source
        for token in (
            "/mnt/c/OpenClaw/logs",
            "route_log.csv",
            "cassandra_state.json",
            ".jsonl",
            "Ops Actions.md",
            "Ops Payment Follow-ups.md",
        )
    )
    governed_hook = "record_telegram_listener_update_safe" in source
    approval_ref = any(token in lowered for token in ("guardian", "approval", "approval gate", "has_pending_approval"))
    useful_ack_logic = bool("working on it" in lowered or "reply_text" in source or "ack" in lowered)
    classifications: list[str] = []
    if receives_telegram:
        classifications.append("useful_receive_logic")
    if sends_telegram:
        classifications.append("unsafe_direct_send")
    if useful_ack_logic:
        classifications.append("useful_ack_logic")
    if "briefing" in filename:
        classifications.append("useful_briefing_logic")
    if "outreach" in filename:
        classifications.append("useful_outreach_logic")
    if reads_env_token or direct_action_path:
        classifications.append("needs_operator_review")
    if old_storage:
        classifications.append("reference_only")
    return {
        "receives_telegram": receives_telegram,
        "sends_telegram": sends_telegram,
        "reads_env_token": reads_env_token,
        "writes_files": writes_files,
        "uses_direct_action_path": direct_action_path,
        "uses_old_session_storage": old_storage,
        "governed_storage_hook": governed_hook,
        "approval_gate_reference": approval_ref,
        "useful_ack_logic": useful_ack_logic,
        "classifications": classifications,
    }


def _repo_b_classification(
    *,
    relative_path: str,
    repo_a_exists: bool,
    repo_a_identical: bool,
    flags: dict[str, Any],
) -> tuple[list[str], str, str]:
    classes = list(flags["classifications"])
    if repo_a_exists:
        classes.insert(0, "already_ported_to_repo_a")
    else:
        classes.insert(0, "missing_from_repo_a")
    if repo_a_identical:
        classes.append("exact_match_in_repo_a")
    high_risk = flags["sends_telegram"] or flags["reads_env_token"] or flags["uses_direct_action_path"]
    if flags["receives_telegram"] and flags["governed_storage_hook"]:
        classes.append("candidate_to_wrap")
    elif flags["receives_telegram"] and high_risk:
        classes.append("candidate_to_wrap")
    elif high_risk:
        classes.append("blocked_no_go")
    elif relative_path in {"cassandra_capability.py", "cassandra_whisper_relay.py"}:
        classes.append("candidate_to_port")
    else:
        classes.append("reference_only")
    if relative_path in {"cassandra_brain.py", "cassandra_outreach.py", "chief_router.py"}:
        classes.append("reference_only")
    safe_posture = "already_present_review_before_changes" if repo_a_exists else "candidate_to_port"
    if high_risk:
        safe_posture = "candidate_to_wrap" if flags["receives_telegram"] or flags["useful_ack_logic"] else "blocked_no_go"
    if relative_path in {"cassandra_brain.py", "cassandra_outreach.py", "chief_router.py"}:
        safe_posture = "reference_only"
    recommendation = {
        "already_present_review_before_changes": "Repo A already contains this surface; audit and wrap unsafe behavior before changes.",
        "candidate_to_port": "Can be considered for a bounded port only after tests prove no send, secret, or action path.",
        "candidate_to_wrap": "Wrap useful receive/ack behavior behind governed storage and approval-gated send policy.",
        "blocked_no_go": "Do not port directly; direct action or secret/send behavior must be removed or replaced.",
        "reference_only": "Use as reference only; extract narrow safe rules rather than runtime behavior.",
    }[safe_posture]
    return sorted(set(classes)), safe_posture, recommendation


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS cassandra_runtime_wiring_runs (
  run_id TEXT PRIMARY KEY,
  audit_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  repo_a_root TEXT NOT NULL,
  repo_a_commit TEXT NOT NULL,
  repo_b_root TEXT NOT NULL,
  repo_b_remote TEXT NOT NULL,
  repo_b_commit TEXT NOT NULL,
  service_count INTEGER NOT NULL DEFAULT 0,
  repo_b_file_count INTEGER NOT NULL DEFAULT 0,
  already_ported_count INTEGER NOT NULL DEFAULT 0,
  unsafe_surface_count INTEGER NOT NULL DEFAULT 0,
  gap_count INTEGER NOT NULL DEFAULT 0,
  recommendation_count INTEGER NOT NULL DEFAULT 0,
  live_receive_proven INTEGER NOT NULL DEFAULT 0,
  governed_storage_proven INTEGER NOT NULL DEFAULT 0,
  reply_ready INTEGER NOT NULL DEFAULT 0,
  telegram_send_allowed INTEGER NOT NULL DEFAULT 0,
  arbitrary_command_allowed INTEGER NOT NULL DEFAULT 0,
  repo_b_execution_allowed INTEGER NOT NULL DEFAULT 0,
  secret_access_allowed INTEGER NOT NULL DEFAULT 0,
  external_api_allowed INTEGER NOT NULL DEFAULT 0,
  approval_bypass_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS cassandra_runtime_surfaces (
  surface_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  repo_key TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  surface_name TEXT NOT NULL,
  surface_kind TEXT NOT NULL,
  purpose TEXT NOT NULL,
  exists_in_repo INTEGER NOT NULL DEFAULT 0,
  sha256 TEXT,
  service_name TEXT,
  service_active_state TEXT,
  service_sub_state TEXT,
  service_main_pid TEXT,
  service_fragment_path TEXT,
  service_working_directory TEXT,
  exec_entrypoints_json TEXT NOT NULL DEFAULT '[]',
  exec_log_paths_json TEXT NOT NULL DEFAULT '[]',
  points_to_repo_a INTEGER NOT NULL DEFAULT 0,
  env_file_sourced INTEGER NOT NULL DEFAULT 0,
  app_log_summary_json TEXT NOT NULL DEFAULT '{}',
  receives_telegram INTEGER NOT NULL DEFAULT 0,
  sends_telegram INTEGER NOT NULL DEFAULT 0,
  reads_env_token INTEGER NOT NULL DEFAULT 0,
  writes_files INTEGER NOT NULL DEFAULT 0,
  uses_direct_action_path INTEGER NOT NULL DEFAULT 0,
  uses_old_session_storage INTEGER NOT NULL DEFAULT 0,
  governed_storage_hook INTEGER NOT NULL DEFAULT 0,
  approval_gate_reference INTEGER NOT NULL DEFAULT 0,
  classifications_json TEXT NOT NULL DEFAULT '[]',
  safe_port_posture TEXT NOT NULL,
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES cassandra_runtime_wiring_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS cassandra_runtime_comparison (
  comparison_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  repo_b_path TEXT NOT NULL,
  repo_a_path TEXT,
  repo_a_exists INTEGER NOT NULL DEFAULT 0,
  exact_match INTEGER NOT NULL DEFAULT 0,
  classification_json TEXT NOT NULL,
  safe_port_posture TEXT NOT NULL,
  recommendation TEXT NOT NULL,
  receives_telegram INTEGER NOT NULL DEFAULT 0,
  sends_telegram INTEGER NOT NULL DEFAULT 0,
  reads_env_token INTEGER NOT NULL DEFAULT 0,
  writes_files INTEGER NOT NULL DEFAULT 0,
  uses_direct_action_path INTEGER NOT NULL DEFAULT 0,
  uses_old_session_storage INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES cassandra_runtime_wiring_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS cassandra_roundtrip_steps (
  step_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  step_order INTEGER NOT NULL,
  step_name TEXT NOT NULL,
  status TEXT NOT NULL,
  implemented INTEGER NOT NULL DEFAULT 0,
  proven INTEGER NOT NULL DEFAULT 0,
  blocker TEXT,
  evidence_summary TEXT NOT NULL,
  next_safe_move TEXT NOT NULL,
  receipt_ref TEXT,
  telegram_send_allowed INTEGER NOT NULL DEFAULT 0,
  external_send_used INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES cassandra_runtime_wiring_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS cassandra_wiring_gaps (
  gap_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  severity TEXT NOT NULL,
  gap_kind TEXT NOT NULL,
  title TEXT NOT NULL,
  evidence_summary TEXT NOT NULL,
  next_safe_move TEXT NOT NULL,
  no_authority_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES cassandra_runtime_wiring_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS cassandra_wiring_recommendations (
  recommendation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  priority_hint TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  recommended_next_lane TEXT NOT NULL,
  routed_agent TEXT NOT NULL,
  work_board_card_id TEXT,
  operator_decision_required INTEGER NOT NULL DEFAULT 1,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  telegram_send_allowed INTEGER NOT NULL DEFAULT 0,
  approval_bypass_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES cassandra_runtime_wiring_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS cassandra_wiring_query_receipts (
  query_receipt_id TEXT PRIMARY KEY,
  run_id TEXT,
  query_kind TEXT NOT NULL,
  filter_value TEXT,
  result_count INTEGER NOT NULL DEFAULT 0,
  generated_at TEXT NOT NULL,
  raw_body_stored INTEGER NOT NULL DEFAULT 0
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_cassandra_runtime_surfaces_repo ON cassandra_runtime_surfaces(repo_key)",
        "CREATE INDEX IF NOT EXISTS idx_cassandra_runtime_comparison_posture ON cassandra_runtime_comparison(safe_port_posture)",
        "CREATE INDEX IF NOT EXISTS idx_cassandra_roundtrip_steps_status ON cassandra_roundtrip_steps(status)",
        "CREATE INDEX IF NOT EXISTS idx_cassandra_wiring_gaps_kind ON cassandra_wiring_gaps(gap_kind)",
    )


def init_cassandra_runtime_wiring_audit_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path) if db_path is not None else DEFAULT_DB_PATH
    init_business_ops_ledger(path)
    init_agent_presence_schema(path)
    init_intent_router_schema(path)
    init_telegram_agent_intake_schema(path)
    init_work_board_schema(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def cassandra_runtime_wiring_audit_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_cassandra_runtime_wiring_audit_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name FROM sqlite_master
WHERE type = 'table' AND name LIKE 'cassandra_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


def _latest_cassandra_intake_counts(conn: sqlite3.Connection) -> dict[str, int]:
    if not _table_exists(conn, "telegram_agent_update_records"):
        return {"live": 0, "synthetic": 0, "total": 0}
    row = conn.execute(
        """
SELECT
  SUM(CASE WHEN source_channel = 'cassandra_listener' AND operator_message = 1 THEN 1 ELSE 0 END) AS live,
  SUM(CASE WHEN source_channel LIKE 'synthetic_cassandra_wiring_audit%' THEN 1 ELSE 0 END) AS synthetic,
  SUM(CASE WHEN agent_target = 'cassandra' OR source_channel LIKE '%cassandra%' THEN 1 ELSE 0 END) AS total
FROM telegram_agent_update_records
""".strip()
    ).fetchone()
    return {key: int(row[key] or 0) for key in ("live", "synthetic", "total")}


def _upsert_work_board_card(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    title: str,
    summary: str,
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
        (board_id, "Local review board over Cassandra runtime wiring metadata.", now, now),
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
) VALUES (?, ?, ?, ?, 'manual_seed', ?, 'communications', 'cassandra',
  'operator_comms', 'cassandra_runtime_wiring_audit', 'needs_review', ?, 'high',
  1, 0, NULL, NULL, NULL, NULL, ?, 'cassandra_runtime_wiring_audit', ?, ?,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
ON CONFLICT(board_id, source_kind, source_id) DO UPDATE SET
  title = excluded.title,
  summary = excluded.summary,
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
        (card_id, board_id, title, summary, source_id, status, next_safe_move, now, now),
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


def _insert_surface(conn: sqlite3.Connection, *, run_id: str, now: str, row: dict[str, Any]) -> None:
    conn.execute(
        """
INSERT OR REPLACE INTO cassandra_runtime_surfaces (
  surface_id, run_id, repo_key, relative_path, surface_name, surface_kind,
  purpose, exists_in_repo, sha256, service_name, service_active_state,
  service_sub_state, service_main_pid, service_fragment_path,
  service_working_directory, exec_entrypoints_json, exec_log_paths_json,
  points_to_repo_a, env_file_sourced, app_log_summary_json,
  receives_telegram, sends_telegram, reads_env_token, writes_files,
  uses_direct_action_path, uses_old_session_storage, governed_storage_hook,
  approval_gate_reference, classifications_json, safe_port_posture, notes,
  created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
        (
            row["surface_id"],
            run_id,
            row["repo_key"],
            row["relative_path"],
            row["surface_name"],
            row["surface_kind"],
            row["purpose"],
            _bool(row.get("exists_in_repo", False)),
            row.get("sha256"),
            row.get("service_name"),
            row.get("service_active_state"),
            row.get("service_sub_state"),
            row.get("service_main_pid"),
            row.get("service_fragment_path"),
            row.get("service_working_directory"),
            stable_json(row.get("exec_entrypoints", [])),
            stable_json(row.get("exec_log_paths", [])),
            _bool(row.get("points_to_repo_a", False)),
            _bool(row.get("env_file_sourced", False)),
            stable_json(row.get("app_log_summary", {})),
            _bool(row.get("receives_telegram", False)),
            _bool(row.get("sends_telegram", False)),
            _bool(row.get("reads_env_token", False)),
            _bool(row.get("writes_files", False)),
            _bool(row.get("uses_direct_action_path", False)),
            _bool(row.get("uses_old_session_storage", False)),
            _bool(row.get("governed_storage_hook", False)),
            _bool(row.get("approval_gate_reference", False)),
            stable_json(row.get("classifications", [])),
            row.get("safe_port_posture", "reference_only"),
            row.get("notes", ""),
            now,
        ),
    )


def _insert_roundtrip_step(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    now: str,
    order: int,
    name: str,
    status: str,
    implemented: bool,
    proven: bool,
    blocker: str | None,
    evidence: str,
    next_safe_move: str,
    receipt_ref: str | None = None,
) -> None:
    conn.execute(
        """
INSERT OR REPLACE INTO cassandra_roundtrip_steps (
  step_id, run_id, step_order, step_name, status, implemented, proven,
  blocker, evidence_summary, next_safe_move, receipt_ref,
  telegram_send_allowed, external_send_used, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
""".strip(),
        (
            _row_id("cassround", run_id, order, name),
            run_id,
            order,
            name,
            status,
            _bool(implemented),
            _bool(proven),
            blocker,
            evidence,
            next_safe_move,
            receipt_ref,
            now,
        ),
    )


def _insert_gap(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    now: str,
    severity: str,
    kind: str,
    title: str,
    evidence: str,
    next_safe_move: str,
) -> None:
    conn.execute(
        """
INSERT OR REPLACE INTO cassandra_wiring_gaps (
  gap_id, run_id, severity, gap_kind, title, evidence_summary,
  next_safe_move, no_authority_json, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
        (
            _row_id("cassgap", run_id, kind, title),
            run_id,
            severity,
            kind,
            title,
            evidence,
            next_safe_move,
            stable_json(NO_AUTHORITY_FLAGS),
            now,
        ),
    )


def _insert_recommendation(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    now: str,
    priority: str,
    title: str,
    summary: str,
    lane: str,
    routed_agent: str,
    card_id: str | None = None,
) -> None:
    conn.execute(
        """
INSERT OR REPLACE INTO cassandra_wiring_recommendations (
  recommendation_id, run_id, priority_hint, title, summary,
  recommended_next_lane, routed_agent, work_board_card_id,
  operator_decision_required, execution_allowed, telegram_send_allowed,
  approval_bypass_allowed, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, 0, ?)
""".strip(),
        (
            _row_id("cassreco", run_id, title),
            run_id,
            priority,
            title,
            summary,
            lane,
            routed_agent,
            card_id,
            now,
        ),
    )


def build_cassandra_runtime_wiring_audit(
    *,
    db_path: str | Path | None = None,
    repo_a_root: str | Path = ROOT,
    repo_b_root: str | Path = DEFAULT_REPO_B_ROOT,
    run_id: str | None = None,
    service_facts: list[dict[str, Any]] | None = None,
    create_synthetic_proofs: bool = True,
    scan_app_logs: bool = True,
) -> CassandraWiringAuditResult:
    path = init_cassandra_runtime_wiring_audit_schema(db_path)
    repo_a = Path(repo_a_root)
    repo_b = Path(repo_b_root)
    repo_a_meta = repo_metadata(repo_a)
    repo_b_meta = repo_metadata(repo_b)
    now = utc_now()
    resolved_run_id = run_id or _row_id("casswiring", repo_a_meta["commit"], repo_b_meta["commit"], now)
    facts = service_facts if service_facts is not None else _systemd_service_facts(repo_a)

    synthetic_result = None
    capital_result = None
    if create_synthetic_proofs:
        synthetic_result = record_telegram_update(
            text="You online yet?",
            source_channel="synthetic_cassandra_wiring_audit",
            source_message_id=f"{resolved_run_id}:you_online_yet",
            agent_target="cassandra",
            source_user_label="operator",
            operator_message=True,
            route_intent=True,
            create_work_board_card=True,
            db_path=path,
            run_id=resolved_run_id,
        )
        if (repo_a / "capital_hilton_finance_fact_intake.py").exists():
            capital_result = record_telegram_update(
                text="Capital Hilton invoice fact update.",
                source_channel="synthetic_cassandra_wiring_audit_capital_hilton",
                source_message_id=f"{resolved_run_id}:capital_hilton",
                agent_target="cassandra",
                source_user_label="operator",
                operator_message=True,
                route_intent=True,
                create_work_board_card=False,
                db_path=path,
                run_id=resolved_run_id,
            )

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for table in (
            "cassandra_runtime_surfaces",
            "cassandra_runtime_comparison",
            "cassandra_roundtrip_steps",
            "cassandra_wiring_gaps",
            "cassandra_wiring_recommendations",
        ):
            conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (resolved_run_id,))
        conn.execute(
            """
INSERT INTO cassandra_runtime_wiring_runs (
  run_id, audit_version, created_at, repo_a_root, repo_a_commit,
  repo_b_root, repo_b_remote, repo_b_commit, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
  audit_version = excluded.audit_version,
  repo_a_root = excluded.repo_a_root,
  repo_a_commit = excluded.repo_a_commit,
  repo_b_root = excluded.repo_b_root,
  repo_b_remote = excluded.repo_b_remote,
  repo_b_commit = excluded.repo_b_commit,
  telegram_send_allowed = 0,
  arbitrary_command_allowed = 0,
  repo_b_execution_allowed = 0,
  secret_access_allowed = 0,
  external_api_allowed = 0,
  approval_bypass_allowed = 0,
  notes = excluded.notes
""".strip(),
            (
                resolved_run_id,
                AUDIT_VERSION,
                now,
                repo_a.as_posix(),
                repo_a_meta["commit"],
                repo_b.as_posix(),
                repo_b_meta["remote"],
                repo_b_meta["commit"],
                "Metadata-only Cassandra runtime wiring audit; no Telegram send, Repo B execution, secret read, or approval bypass.",
            ),
        )

        unsafe_surface_count = 0
        already_ported_count = 0

        for service in facts:
            log_summaries = [_scan_log(log_path) for log_path in service.get("exec_log_paths", [])] if scan_app_logs else []
            row = {
                "surface_id": _row_id("casssurface", resolved_run_id, "service", service["service_name"]),
                "repo_key": "runtime_service",
                "relative_path": service["service_name"],
                "surface_name": service["service_name"],
                "surface_kind": "systemd_user_service",
                "purpose": "User service status and sanitized ExecStart/source-path metadata.",
                "exists_in_repo": True,
                "service_name": service["service_name"],
                "service_active_state": service.get("active_state", "unknown"),
                "service_sub_state": service.get("sub_state", "unknown"),
                "service_main_pid": str(service.get("main_pid", "")),
                "service_fragment_path": service.get("fragment_path", ""),
                "service_working_directory": service.get("working_directory", ""),
                "exec_entrypoints": service.get("exec_entrypoints", []),
                "exec_log_paths": service.get("exec_log_paths", []),
                "points_to_repo_a": bool(service.get("points_to_repo_a")),
                "env_file_sourced": bool(service.get("env_file_sourced")),
                "app_log_summary": {"logs": log_summaries},
                "classifications": ["service_status", "repo_a_execstart" if service.get("points_to_repo_a") else "unknown_execstart"],
                "safe_port_posture": "reference_only",
                "notes": service.get("status_error", ""),
            }
            _insert_surface(conn, run_id=resolved_run_id, now=now, row=row)

        for relative_path in REPO_A_CORE_SURFACES:
            absolute = repo_a / relative_path
            source = _read_source(absolute)
            flags = _source_flags(source, relative_path)
            classes = ["already_ported_to_repo_a", "governed_shell_surface", *flags["classifications"]]
            row = {
                "surface_id": _row_id("casssurface", resolved_run_id, "repo_a_core", relative_path),
                "repo_key": "repo_a",
                "relative_path": relative_path,
                "surface_name": relative_path,
                "surface_kind": "governed_core" if relative_path != "capital_hilton_finance_fact_intake.py" else "finance_packet_route",
                "purpose": PURPOSES.get(relative_path, "Repo A Cassandra-adjacent governed surface."),
                "exists_in_repo": absolute.exists(),
                "sha256": _sha256(absolute) if absolute.exists() else None,
                **flags,
                "classifications": sorted(set(classes)),
                "safe_port_posture": "already_present_review_before_changes",
                "notes": "Repo A governed surface; inspect behavior through tests and read-models.",
            }
            _insert_surface(conn, run_id=resolved_run_id, now=now, row=row)

        for relative_path in REPO_B_TARGET_FILES:
            b_path = repo_b / relative_path
            a_path = repo_a / relative_path
            b_source = _read_source(b_path)
            a_source = _read_source(a_path)
            flags = _source_flags(b_source, relative_path)
            a_exists = a_path.exists()
            exact = bool(a_exists and b_source and a_source and b_source == a_source)
            classes, safe_posture, recommendation = _repo_b_classification(
                relative_path=relative_path,
                repo_a_exists=a_exists,
                repo_a_identical=exact,
                flags=flags,
            )
            already_ported_count += 1 if a_exists else 0
            unsafe_surface_count += 1 if flags["sends_telegram"] or flags["reads_env_token"] or flags["uses_direct_action_path"] else 0
            row = {
                "surface_id": _row_id("casssurface", resolved_run_id, "repo_b", relative_path),
                "repo_key": "repo_b",
                "relative_path": relative_path,
                "surface_name": relative_path,
                "surface_kind": "legacy_runtime_reference",
                "purpose": PURPOSES.get(relative_path, "Legacy Cassandra-related runtime surface."),
                "exists_in_repo": b_path.exists(),
                "sha256": _sha256(b_path) if b_path.exists() else None,
                **flags,
                "classifications": classes,
                "safe_port_posture": safe_posture,
                "notes": "Static source classification only; Repo B code was not executed.",
            }
            _insert_surface(conn, run_id=resolved_run_id, now=now, row=row)
            conn.execute(
                """
INSERT OR REPLACE INTO cassandra_runtime_comparison (
  comparison_id, run_id, repo_b_path, repo_a_path, repo_a_exists,
  exact_match, classification_json, safe_port_posture, recommendation,
  receives_telegram, sends_telegram, reads_env_token, writes_files,
  uses_direct_action_path, uses_old_session_storage, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
                (
                    _row_id("casscompare", resolved_run_id, relative_path),
                    resolved_run_id,
                    relative_path,
                    relative_path if a_exists else None,
                    _bool(a_exists),
                    _bool(exact),
                    stable_json(classes),
                    safe_posture,
                    recommendation,
                    _bool(flags["receives_telegram"]),
                    _bool(flags["sends_telegram"]),
                    _bool(flags["reads_env_token"]),
                    _bool(flags["writes_files"]),
                    _bool(flags["uses_direct_action_path"]),
                    _bool(flags["uses_old_session_storage"]),
                    now,
                ),
            )

        intake_counts = _latest_cassandra_intake_counts(conn)
        all_services_active = all(service.get("active_state") == "active" for service in facts)
        listener_points_repo_a = any(
            service["service_name"] == "cassandra-listener.service" and service.get("points_to_repo_a")
            for service in facts
        )
        listener_source = _read_source(repo_a / "cassandra_listener.py")
        listener_has_hook = "record_telegram_listener_update_safe" in listener_source
        live_receive_proven = intake_counts["live"] > 0
        synthetic_storage_proven = bool(synthetic_result and synthetic_result.routed_agent_id == "cassandra")
        governed_storage_proven = live_receive_proven or synthetic_storage_proven
        capital_supported = (repo_a / "capital_hilton_finance_fact_intake.py").exists()
        capital_route_proven = bool(capital_result and capital_result.routed_agent_id == "cassandra")

        _insert_roundtrip_step(
            conn,
            run_id=resolved_run_id,
            now=now,
            order=1,
            name="cassandra_services_online",
            status="proven" if all_services_active else "not_proven",
            implemented=True,
            proven=all_services_active,
            blocker=None if all_services_active else "one_or_more_services_not_active",
            evidence=f"{sum(1 for service in facts if service.get('active_state') == 'active')}/{len(CASSANDRA_SERVICES)} Cassandra services active.",
            next_safe_move="Do not equate active services with Telegram receive/reply proof; continue through governed intake checks.",
        )
        _insert_roundtrip_step(
            conn,
            run_id=resolved_run_id,
            now=now,
            order=2,
            name="listener_execstart_points_repo_a",
            status="proven" if listener_points_repo_a else "not_proven",
            implemented=True,
            proven=listener_points_repo_a,
            blocker=None if listener_points_repo_a else "listener_execstart_not_confirmed",
            evidence="cassandra-listener.service ExecStart entrypoint points to Repo A cassandra_listener.py." if listener_points_repo_a else "Listener service entrypoint was not confirmed as Repo A.",
            next_safe_move="Treat Repo A listener source as the active code surface when planning wraps.",
        )
        _insert_roundtrip_step(
            conn,
            run_id=resolved_run_id,
            now=now,
            order=3,
            name="listener_has_governed_storage_hook",
            status="implemented" if listener_has_hook else "missing",
            implemented=listener_has_hook,
            proven=listener_has_hook,
            blocker=None if listener_has_hook else "governed_hook_missing",
            evidence="cassandra_listener.py calls record_telegram_listener_update_safe before request handling." if listener_has_hook else "No governed intake hook found in cassandra_listener.py.",
            next_safe_move="Keep hook before any brain/reply path and make failures visible without printing message text.",
        )
        _insert_roundtrip_step(
            conn,
            run_id=resolved_run_id,
            now=now,
            order=4,
            name="live_telegram_receive_to_governed_storage",
            status="proven" if live_receive_proven else "not_proven",
            implemented=listener_has_hook,
            proven=live_receive_proven,
            blocker=None if live_receive_proven else "no_cassandra_listener_update_record",
            evidence=f"{intake_counts['live']} operator update(s) from source_channel=cassandra_listener are in governed intake.",
            next_safe_move="Ask the operator to send one prefixed Cassandra/Clara test message, then query intake; do not send a reply from automation.",
        )
        _insert_roundtrip_step(
            conn,
            run_id=resolved_run_id,
            now=now,
            order=5,
            name="synthetic_you_online_yet_route_store",
            status="proven" if synthetic_storage_proven else "not_proven",
            implemented=True,
            proven=synthetic_storage_proven,
            blocker=None if synthetic_storage_proven else "synthetic_route_failed",
            evidence=(
                f"Synthetic local update stored as {synthetic_result.update_record_id} and routed to {synthetic_result.routed_agent_id}/{synthetic_result.routed_lane_id}."
                if synthetic_result
                else "Synthetic proof disabled."
            ),
            next_safe_move="Use this only as local storage/routing proof; it is not Telegram API receive proof.",
            receipt_ref=synthetic_result.update_record_id if synthetic_result else None,
        )
        _insert_roundtrip_step(
            conn,
            run_id=resolved_run_id,
            now=now,
            order=6,
            name="capital_hilton_finance_fact_route",
            status="supported" if capital_supported and capital_route_proven else "missing",
            implemented=capital_supported,
            proven=capital_route_proven,
            blocker=None if capital_supported else "capital_hilton_fact_intake_missing",
            evidence=(
                f"Capital Hilton synthetic route stored as {capital_result.update_record_id}; packet substrate is capital_hilton_finance_fact_intake.py."
                if capital_result
                else "Capital Hilton fact intake substrate not proven in this audit run."
            ),
            next_safe_move="Use governed Capital Hilton fact intake or CLI fallback for facts; do not send invoices or messages.",
            receipt_ref=capital_result.update_record_id if capital_result else None,
        )
        _insert_roundtrip_step(
            conn,
            run_id=resolved_run_id,
            now=now,
            order=7,
            name="safe_acknowledgment_policy",
            status="blocked_by_policy",
            implemented=False,
            proven=False,
            blocker="telegram_send_allowed_false",
            evidence="Governed posture keeps telegram_send_allowed=false; legacy listener contains direct reply paths and is not an approved safe ack path.",
            next_safe_move="Operator-facing status should be stored locally: Cassandra can route/store synthetic messages, but live receive is unproven and reply is not governed.",
        )

        if not live_receive_proven:
            _insert_gap(
                conn,
                run_id=resolved_run_id,
                now=now,
                severity="high",
                kind="live_receive_not_proven",
                title="Cassandra Telegram receive is not proven",
                evidence="No governed intake row exists from source_channel=cassandra_listener for an operator message.",
                next_safe_move="Run an operator-approved receive-only test and query telegram_agent_intake; do not send Telegram from automation.",
            )
        if listener_has_hook and not live_receive_proven:
            _insert_gap(
                conn,
                run_id=resolved_run_id,
                now=now,
                severity="medium",
                kind="service_online_not_roundtrip",
                title="Service online is being conflated with Telegram round-trip",
                evidence="Agent Presence says Cassandra online from service checks, but governed live receive count is zero.",
                next_safe_move="Change status reporting to separate service-online, receive-proven, store-proven, and reply-ready.",
            )
        if "reply_text" in listener_source or "send_voice_note" in listener_source:
            _insert_gap(
                conn,
                run_id=resolved_run_id,
                now=now,
                severity="high",
                kind="legacy_direct_send_present",
                title="Legacy Cassandra listener has direct Telegram reply paths",
                evidence="cassandra_listener.py contains direct reply/voice-send calls outside a governed send approval path.",
                next_safe_move="Wrap or disable reply paths behind an explicit Guardian-approved bounded send/ack policy before claiming reply-ready.",
            )
        sensitive_logs = [
            summary["log_path"]
            for service in facts
            for summary in ([_scan_log(path) for path in service.get("exec_log_paths", [])] if scan_app_logs else [])
            if summary.get("sensitive_content_detected")
        ]
        if sensitive_logs:
            _insert_gap(
                conn,
                run_id=resolved_run_id,
                now=now,
                severity="medium",
                kind="log_redaction_required",
                title="Cassandra app log requires redaction before quoting",
                evidence=f"{len(sensitive_logs)} Cassandra app log(s) contain sensitive-looking token/chat-id assignments.",
                next_safe_move="Use aggregate log counters only or add a redaction helper; do not paste raw listener logs.",
            )

        card_receive = _upsert_work_board_card(
            conn,
            source_id="cassandra_runtime_wiring_audit:receive_path",
            title="Cassandra receive path not proven",
            summary="Services are online and a governed hook exists, but no live Cassandra listener update is stored in governed intake.",
            status="needs_review",
            next_safe_move="Perform receive-only Telegram test and query governed intake; no automated reply.",
            now=now,
        )
        card_reply = _upsert_work_board_card(
            conn,
            source_id="cassandra_runtime_wiring_audit:reply_path",
            title="Cassandra reply path blocked/missing",
            summary="Governed send is false; legacy direct replies exist and require wrapping before reply-ready status.",
            status="blocked",
            next_safe_move="Design a status-only acknowledgment lane behind Guardian approval; do not enable broad sends.",
            now=now,
        )
        card_port = _upsert_work_board_card(
            conn,
            source_id="cassandra_runtime_wiring_audit:repo_b_listener_review",
            title="Review/wrap Repo B Cassandra listener logic",
            summary="Repo B listener receive/ack logic is useful but direct-send/env-backed; it must be wrapped, not blindly ported.",
            status="needs_review",
            next_safe_move="Extract receive/storage behavior only; keep send and token use outside the governed audit lane.",
            now=now,
        )
        card_capital = _upsert_work_board_card(
            conn,
            source_id="cassandra_runtime_wiring_audit:capital_hilton_route",
            title="Capital Hilton facts via Cassandra route",
            summary="Synthetic Capital Hilton route reaches Cassandra metadata and existing fact intake substrate; no invoice or send action is authorized.",
            status="planned",
            next_safe_move="Use the governed Capital Hilton fact intake path for operator facts after live receive is proven.",
            now=now,
        )
        _insert_recommendation(
            conn,
            run_id=resolved_run_id,
            now=now,
            priority="high",
            title="Run Cassandra receive-only proof lane",
            summary="Separate service online from Telegram receive/store evidence with one operator-originated Cassandra/Clara test.",
            lane="Cassandra Telegram Receive Proof v1",
            routed_agent="cassandra",
            card_id=card_receive,
        )
        _insert_recommendation(
            conn,
            run_id=resolved_run_id,
            now=now,
            priority="high",
            title="Wrap or block legacy direct replies",
            summary="Direct listener reply paths must not be used as governed send proof.",
            lane="Cassandra Safe Ack Policy v1",
            routed_agent="guardian",
            card_id=card_reply,
        )
        _insert_recommendation(
            conn,
            run_id=resolved_run_id,
            now=now,
            priority="normal",
            title="Review Repo B receive and ack logic",
            summary="Use Repo B as reference for receive/ack semantics while preserving Repo A governed storage and approval gates.",
            lane="Repo B Cassandra Listener Wrap Review v1",
            routed_agent="chief",
            card_id=card_port,
        )
        _insert_recommendation(
            conn,
            run_id=resolved_run_id,
            now=now,
            priority="normal",
            title="Route Capital Hilton facts through Clara/Cassandra metadata",
            summary="The existing Capital Hilton fact intake can own finance facts after Cassandra live receive is proven.",
            lane="Capital Hilton Cassandra Fact Intake v1",
            routed_agent="cassandra",
            card_id=card_capital,
        )

        gap_count = int(conn.execute("SELECT COUNT(*) FROM cassandra_wiring_gaps WHERE run_id = ?", (resolved_run_id,)).fetchone()[0])
        recommendation_count = int(conn.execute("SELECT COUNT(*) FROM cassandra_wiring_recommendations WHERE run_id = ?", (resolved_run_id,)).fetchone()[0])
        conn.execute(
            """
UPDATE cassandra_runtime_wiring_runs
SET completed_at = ?, service_count = ?, repo_b_file_count = ?,
    already_ported_count = ?, unsafe_surface_count = ?, gap_count = ?,
    recommendation_count = ?, live_receive_proven = ?,
    governed_storage_proven = ?, reply_ready = 0,
    telegram_send_allowed = 0, arbitrary_command_allowed = 0,
    repo_b_execution_allowed = 0, secret_access_allowed = 0,
    external_api_allowed = 0, approval_bypass_allowed = 0
WHERE run_id = ?
""".strip(),
            (
                utc_now(),
                len(CASSANDRA_SERVICES),
                len(REPO_B_TARGET_FILES),
                already_ported_count,
                unsafe_surface_count,
                gap_count,
                recommendation_count,
                _bool(live_receive_proven),
                _bool(governed_storage_proven),
                resolved_run_id,
            ),
        )
        conn.commit()
        return CassandraWiringAuditResult(
            run_id=resolved_run_id,
            db_path=path,
            service_count=len(CASSANDRA_SERVICES),
            repo_b_file_count=len(REPO_B_TARGET_FILES),
            already_ported_count=already_ported_count,
            unsafe_surface_count=unsafe_surface_count,
            gap_count=gap_count,
            recommendation_count=recommendation_count,
            live_receive_proven=live_receive_proven,
            governed_storage_proven=governed_storage_proven,
            reply_ready=False,
        )
    finally:
        conn.close()


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id FROM cassandra_runtime_wiring_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row["run_id"] if row else None


def _decode_json_field(row: dict[str, Any], key: str, default: Any) -> Any:
    try:
        return json.loads(row.get(key) or "")
    except (TypeError, json.JSONDecodeError):
        return default


def build_cassandra_runtime_wiring_audit_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
    run_id: str | None = None,
) -> dict[str, Any]:
    if report not in REPORT_SECTIONS:
        raise ValueError(f"unknown Cassandra wiring audit report: {report}")
    path = init_cassandra_runtime_wiring_audit_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_run_id(conn)
        if not resolved_run_id:
            return {"status": "no_runs", "report": report, "rows": [], "counts": {}, "no_authority_flags": NO_AUTHORITY_FLAGS}
        run = dict(conn.execute("SELECT * FROM cassandra_runtime_wiring_runs WHERE run_id = ?", (resolved_run_id,)).fetchone())
        surfaces = _dict_rows(
            conn,
            """
SELECT * FROM cassandra_runtime_surfaces
WHERE run_id = ?
ORDER BY CASE repo_key WHEN 'runtime_service' THEN 0 WHEN 'repo_a' THEN 1 ELSE 2 END,
         relative_path
""".strip(),
            (resolved_run_id,),
        )
        comparison = _dict_rows(conn, "SELECT * FROM cassandra_runtime_comparison WHERE run_id = ? ORDER BY repo_b_path", (resolved_run_id,))
        steps = _dict_rows(conn, "SELECT * FROM cassandra_roundtrip_steps WHERE run_id = ? ORDER BY step_order", (resolved_run_id,))
        gaps = _dict_rows(
            conn,
            """
SELECT * FROM cassandra_wiring_gaps
WHERE run_id = ?
ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, gap_kind
""".strip(),
            (resolved_run_id,),
        )
        recommendations = _dict_rows(
            conn,
            """
SELECT * FROM cassandra_wiring_recommendations
WHERE run_id = ?
ORDER BY CASE priority_hint WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, title
""".strip(),
            (resolved_run_id,),
        )
        counts = {
            "service_count": run["service_count"],
            "repo_b_file_count": run["repo_b_file_count"],
            "already_ported_count": run["already_ported_count"],
            "unsafe_surface_count": run["unsafe_surface_count"],
            "gap_count": run["gap_count"],
            "recommendation_count": run["recommendation_count"],
            "live_receive_proven": bool(run["live_receive_proven"]),
            "governed_storage_proven": bool(run["governed_storage_proven"]),
            "reply_ready": bool(run["reply_ready"]),
            "comparison_by_posture": dict(Counter(row["safe_port_posture"] for row in comparison)),
            "roundtrip_by_status": dict(Counter(row["status"] for row in steps)),
        }
        if report == "surfaces":
            rows = surfaces
        elif report == "comparison":
            rows = comparison
        elif report == "roundtrip":
            rows = steps
        elif report == "gaps":
            rows = gaps
        elif report == "recommendations":
            rows = recommendations
        else:
            rows = recommendations[:8]
        conn.execute(
            """
INSERT OR REPLACE INTO cassandra_wiring_query_receipts (
  query_receipt_id, run_id, query_kind, filter_value, result_count,
  generated_at, raw_body_stored
) VALUES (?, ?, ?, NULL, ?, ?, 0)
""".strip(),
            (_row_id("cassquery", resolved_run_id, report, utc_now()), resolved_run_id, report, len(rows), utc_now()),
        )
        conn.commit()
        return {
            "status": "ok",
            "report": report,
            "run_id": resolved_run_id,
            "run": run,
            "counts": counts,
            "rows": rows,
            "surfaces": surfaces,
            "comparison": comparison,
            "roundtrip_steps": steps,
            "gaps": gaps,
            "recommendations": recommendations,
            "no_authority_flags": NO_AUTHORITY_FLAGS,
        }
    finally:
        conn.close()


def _counts_line(counts: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) if counts else "none"


def format_cassandra_runtime_wiring_audit_result(result: CassandraWiringAuditResult) -> str:
    return "\n".join(
        [
            "Cassandra Runtime Wiring Audit v0",
            "",
            f"Run: `{result.run_id}`",
            f"Services represented: {result.service_count}",
            f"Repo B files classified: {result.repo_b_file_count}",
            f"Already present in Repo A: {result.already_ported_count}",
            f"Unsafe surfaces flagged: {result.unsafe_surface_count}",
            f"Gaps: {result.gap_count}",
            f"Recommendations: {result.recommendation_count}",
            f"Live Telegram receive proven: `{str(result.live_receive_proven).lower()}`",
            f"Governed storage proven: `{str(result.governed_storage_proven).lower()}`",
            f"Reply-ready: `{str(result.reply_ready).lower()}`",
            "",
            "Boundary:",
            "- Metadata/read-model only; no Telegram send, Repo B execution, secret read, approval bypass, arbitrary command, or external API call.",
        ]
    )


def format_cassandra_runtime_wiring_audit_report(payload: dict[str, Any]) -> str:
    if payload.get("status") == "no_runs":
        return "Cassandra Runtime Wiring Audit v0\n\nStatus: `no_runs`"
    counts = payload["counts"]
    lines = [
        f"Cassandra Runtime Wiring Audit v0 - {payload['report']}",
        "",
        f"Run: `{payload['run_id']}`",
        f"Live receive proven: `{str(counts['live_receive_proven']).lower()}`",
        f"Governed storage proven: `{str(counts['governed_storage_proven']).lower()}`",
        f"Reply-ready: `{str(counts['reply_ready']).lower()}`",
        f"Repo B files: {counts['repo_b_file_count']}",
        f"Unsafe surfaces: {counts['unsafe_surface_count']}",
        f"Gaps: {counts['gap_count']}",
        f"Comparison by posture: {_counts_line(counts['comparison_by_posture'])}",
        f"Roundtrip by status: {_counts_line(counts['roundtrip_by_status'])}",
        "",
        "Rows:",
    ]
    report = payload["report"]
    for row in payload.get("rows") or []:
        if report == "roundtrip":
            lines.append(
                f"- {row['step_order']}. `{row['step_name']}` status=`{row['status']}` proven={str(bool(row['proven'])).lower()} blocker={row['blocker'] or 'none'}"
            )
        elif report == "gaps":
            lines.append(f"- `{row['severity']}` {row['gap_kind']}: {row['title']} -> {row['next_safe_move']}")
        elif report == "comparison":
            classes = ", ".join(_decode_json_field(row, "classification_json", []))
            lines.append(f"- `{row['repo_b_path']}` posture=`{row['safe_port_posture']}` classes={classes}")
        elif report == "surfaces":
            lines.append(
                f"- `{row['repo_key']}` `{row['relative_path']}` kind={row['surface_kind']} send={str(bool(row['sends_telegram'])).lower()} env={str(bool(row['reads_env_token'])).lower()} action={str(bool(row['uses_direct_action_path'])).lower()}"
            )
        elif report == "recommendations":
            lines.append(f"- `{row['priority_hint']}` {row['title']} -> {row['recommended_next_lane']}")
        else:
            lines.append(f"- `{row.get('priority_hint', 'normal')}` {row.get('title', row)}")
    if not payload.get("rows"):
        lines.append("- none")
    lines.extend(["", "Authority boundary:"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`.")
    return "\n".join(lines)


def build_cassandra_runtime_wiring_audit_read_model(db_path: str | Path | None = None) -> dict[str, Any]:
    report = build_cassandra_runtime_wiring_audit_report(db_path=db_path, report="summary")
    roundtrip = build_cassandra_runtime_wiring_audit_report(db_path=db_path, report="roundtrip")
    gaps = build_cassandra_runtime_wiring_audit_report(db_path=db_path, report="gaps")
    comparison = build_cassandra_runtime_wiring_audit_report(db_path=db_path, report="comparison")
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "generated_at": utc_now(),
        "run_id": report.get("run_id"),
        "source_ledger_path": str(db_path or DEFAULT_DB_PATH),
        "service_status": [
            {
                "service_name": row["service_name"],
                "active_state": row["service_active_state"],
                "sub_state": row["service_sub_state"],
                "points_to_repo_a": bool(row["points_to_repo_a"]),
                "exec_entrypoints": _decode_json_field(row, "exec_entrypoints_json", []),
                "exec_log_paths": _decode_json_field(row, "exec_log_paths_json", []),
                "env_file_sourced": bool(row["env_file_sourced"]),
                "app_log_summary": _decode_json_field(row, "app_log_summary_json", {}),
            }
            for row in report.get("surfaces", [])
            if row["repo_key"] == "runtime_service"
        ],
        "repo_a_surfaces": [row for row in report.get("surfaces", []) if row["repo_key"] == "repo_a"],
        "repo_b_surfaces": [row for row in report.get("surfaces", []) if row["repo_key"] == "repo_b"],
        "repo_b_comparison": comparison.get("rows", []),
        "roundtrip_steps": roundtrip.get("rows", []),
        "gaps": gaps.get("rows", []),
        "recommendations": report.get("recommendations", []),
        "status_statement": (
            "Cassandra can receive and store synthetic local proof records, but live Telegram receive is not proven and governed Telegram reply is blocked."
            if not report["counts"]["live_receive_proven"]
            else "Cassandra live receive has governed storage evidence; governed Telegram reply remains blocked."
        ),
        "counts": report.get("counts", {}),
        "no_authority_flags": NO_AUTHORITY_FLAGS,
        **NO_AUTHORITY_FLAGS,
    }


def _operator_markdown(read_model: dict[str, Any]) -> str:
    counts = read_model["counts"]
    lines = [
        "# Cassandra Runtime Wiring Audit v0",
        "",
        "## Status",
        f"- {read_model['status_statement']}",
        f"- Live receive proven: `{str(counts['live_receive_proven']).lower()}`",
        f"- Governed storage proven: `{str(counts['governed_storage_proven']).lower()}`",
        f"- Reply-ready: `{str(counts['reply_ready']).lower()}`",
        "",
        "## Services",
    ]
    for service in read_model.get("service_status") or []:
        lines.append(
            f"- `{service['service_name']}` active=`{service['active_state']}` sub=`{service['sub_state']}` points_to_repo_a=`{str(service['points_to_repo_a']).lower()}`"
        )
    lines.extend(["", "## Round Trip"])
    for step in read_model.get("roundtrip_steps") or []:
        lines.append(
            f"- `{step['step_name']}`: status=`{step['status']}`, proven=`{str(bool(step['proven'])).lower()}`, blocker={step['blocker'] or 'none'}"
        )
    lines.extend(["", "## Repo B Comparison"])
    for row in read_model.get("repo_b_comparison") or []:
        classes = ", ".join(_decode_json_field(row, "classification_json", []))
        lines.append(f"- `{row['repo_b_path']}`: `{row['safe_port_posture']}`; {classes}")
    lines.extend(["", "## Gaps"])
    for row in read_model.get("gaps") or []:
        lines.append(f"- `{row['severity']}` `{row['gap_kind']}`: {row['title']}")
    if not read_model.get("gaps"):
        lines.append("- None.")
    lines.extend(["", "## Recommendations"])
    for row in read_model.get("recommendations") or []:
        lines.append(f"- `{row['priority_hint']}` {row['title']}: {row['recommended_next_lane']}")
    lines.extend(["", "## Authority Boundary"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`.")
    return "\n".join(lines) + "\n"


def export_cassandra_runtime_wiring_audit_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    out_root = _export_root_path(export_root)
    out_root.mkdir(parents=True, exist_ok=True)
    read_model = build_cassandra_runtime_wiring_audit_read_model(db_path=db_path)
    json_path = out_root / JSON_EXPORT_NAME
    operator_path = out_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(_operator_markdown(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "live_receive_proven": read_model["counts"]["live_receive_proven"],
        "governed_storage_proven": read_model["counts"]["governed_storage_proven"],
        "reply_ready": read_model["counts"]["reply_ready"],
    }


__all__ = [
    "AUDIT_VERSION",
    "NO_AUTHORITY_FLAGS",
    "READ_MODEL_VERSION",
    "REPO_B_TARGET_FILES",
    "build_cassandra_runtime_wiring_audit",
    "build_cassandra_runtime_wiring_audit_read_model",
    "build_cassandra_runtime_wiring_audit_report",
    "cassandra_runtime_wiring_audit_table_names",
    "export_cassandra_runtime_wiring_audit_read_model",
    "format_cassandra_runtime_wiring_audit_report",
    "format_cassandra_runtime_wiring_audit_result",
    "init_cassandra_runtime_wiring_audit_schema",
]
