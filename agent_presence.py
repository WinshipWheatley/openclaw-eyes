"""Agent Presence v0 for OpenClaw.

This module records actual presence evidence for the core OpenClaw agents. It
distinguishes role/lane readiness from runtime presence and never starts,
restarts, messages, or calls external APIs. Recovery policy is recorded as
metadata and remains blocked unless a future explicit lane grants a narrow
receipt-backed recovery path.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agent_lane_registry import DEFAULT_AGENT_LANE_SEEDS, init_agent_lane_registry_schema, seed_agent_lane_registry
from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger


ROOT = Path(__file__).resolve().parent
AGENT_PRESENCE_VERSION = "agent_presence_v0"
READ_MODEL_VERSION = "agent_presence_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "agent_presence.json"
OPERATOR_EXPORT_NAME = "agent_presence_OPERATOR.md"

DESIRED_STATES = {"online", "offline_intentional", "maintenance", "hard_kill", "unknown_review"}
ACTUAL_STATES = {"online", "offline", "degraded", "unknown", "metadata_available", "not_configured"}
RECOVERY_STATUSES = {"not_needed", "available", "blocked", "attempted", "succeeded", "failed"}
RECOVERY_KINDS = {
    "none",
    "systemd_user_start",
    "systemd_user_restart",
    "local_service_restart",
    "launch_agent_kickstart",
    "systemd_restart",
    "scheduled_task_start",
    "script_start",
    "unknown_review",
}

NO_AUTHORITY_FLAGS = {
    "broad_agent_activation_allowed": False,
    "telegram_api_allowed": False,
    "message_send_allowed": False,
    "arbitrary_command_allowed": False,
    "secret_access_allowed": False,
    "recovery_without_policy_allowed": False,
    "hard_kill_bypass_allowed": False,
    "network_authority": False,
    "model_call_allowed": False,
    "client_deployment_allowed": False,
}


@dataclass(frozen=True)
class RuntimeSurface:
    surface_id: str
    surface_kind: str
    source_path: str
    service_name: str | None = None
    process_name: str | None = None
    classification: str = "candidate_to_extend"
    safe_recovery_kind: str = "unknown_review"
    notes: str = ""


@dataclass(frozen=True)
class PresenceAgentConfig:
    agent_id: str
    display_name: str
    lane_id: str
    desired_state: str
    surfaces: tuple[RuntimeSurface, ...]
    metadata_available_paths: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class AgentPresenceBuildResult:
    run_id: str
    db_path: str
    agent_count: int
    expected_online_count: int
    online_count: int
    offline_unexpected_count: int
    degraded_count: int
    unknown_count: int


@dataclass(frozen=True)
class RecoveryActionSeed:
    recovery_action_id: str
    agent_id: str
    action_kind: str
    command_label: str
    command_argv: tuple[str, ...]
    working_directory: str
    status_check_kind: str
    status_check_argv: tuple[str, ...] | None
    log_path: str | None
    heartbeat_path: str | None
    safe_to_attempt: bool
    requires_operator_approval: bool
    cooldown_seconds: int
    max_attempts_per_hour: int
    receipt_required: bool
    discovered_from: str
    confidence: str
    classification: str
    notes: str


@dataclass(frozen=True)
class AgentRecoveryResult:
    agent_id: str
    status: str
    dry_run: bool
    action_id: str | None
    attempted: bool
    exit_code: int | None
    receipt_id: str | None
    blocker: str | None
    summary: str


DEFAULT_RECOVERY_ACTIONS: tuple[RecoveryActionSeed, ...] = (
    RecoveryActionSeed(
        recovery_action_id="chief_systemd_user_start",
        agent_id="chief",
        action_kind="systemd_user_start",
        command_label="Start Chief systemd user units",
        command_argv=(
            "systemctl",
            "--user",
            "start",
            "chief-listener.service",
            "chief-worker.service",
            "chief-memory-worker.service",
            "chief-state-worker.service",
            "chief-watcher-brain.service",
        ),
        working_directory=str(ROOT),
        status_check_kind="systemd_user_is_active",
        status_check_argv=(
            "systemctl",
            "--user",
            "is-active",
            "chief-listener.service",
            "chief-worker.service",
            "chief-memory-worker.service",
            "chief-state-worker.service",
            "chief-watcher-brain.service",
        ),
        log_path=None,
        heartbeat_path=None,
        safe_to_attempt=False,
        requires_operator_approval=True,
        cooldown_seconds=900,
        max_attempts_per_hour=1,
        receipt_required=True,
        discovered_from="systemd/user/chief-*.service.in; docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md",
        confidence="medium",
        classification="safe_start_candidate",
        notes="Fixed systemd-owned path exists, but runtime side effects and legacy Windows-side logging keep execution blocked in v0.",
    ),
    RecoveryActionSeed(
        recovery_action_id="cassandra_systemd_user_start",
        agent_id="cassandra",
        action_kind="systemd_user_start",
        command_label="Start Cassandra systemd user units",
        command_argv=(
            "systemctl",
            "--user",
            "start",
            "cassandra-listener.service",
            "cassandra-watcher.service",
            "cassandra-briefing-scheduler.service",
        ),
        working_directory=str(ROOT),
        status_check_kind="systemd_user_is_active",
        status_check_argv=(
            "systemctl",
            "--user",
            "is-active",
            "cassandra-listener.service",
            "cassandra-watcher.service",
            "cassandra-briefing-scheduler.service",
        ),
        log_path=None,
        heartbeat_path=None,
        safe_to_attempt=False,
        requires_operator_approval=True,
        cooldown_seconds=900,
        max_attempts_per_hour=1,
        receipt_required=True,
        discovered_from="systemd/user/cassandra-*.service.in; docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md",
        confidence="medium",
        classification="safe_start_candidate",
        notes="Fixed systemd-owned path exists, but Cassandra listener is Telegram-facing and execution remains blocked in v0.",
    ),
    RecoveryActionSeed(
        recovery_action_id="guardian_systemd_user_start",
        agent_id="guardian",
        action_kind="systemd_user_start",
        command_label="Start Guardian approval listener",
        command_argv=("systemctl", "--user", "start", "chief-guardian-listener.service"),
        working_directory=str(ROOT),
        status_check_kind="systemd_user_is_active",
        status_check_argv=("systemctl", "--user", "is-active", "chief-guardian-listener.service"),
        log_path=None,
        heartbeat_path=None,
        safe_to_attempt=False,
        requires_operator_approval=True,
        cooldown_seconds=900,
        max_attempts_per_hour=1,
        receipt_required=True,
        discovered_from="systemd/user/chief-guardian-listener.service.in",
        confidence="medium",
        classification="safe_start_candidate",
        notes="Guardian listener path exists, but it is Telegram-facing and remains blocked unless a future lane grants recovery.",
    ),
    RecoveryActionSeed(
        recovery_action_id="niles_producer_script_start",
        agent_id="niles",
        action_kind="script_start",
        command_label="Start Producer/Niles listener script",
        command_argv=("bash", "scripts/run_producer_listener.sh"),
        working_directory=str(ROOT),
        status_check_kind="process_name",
        status_check_argv=None,
        log_path=None,
        heartbeat_path=None,
        safe_to_attempt=False,
        requires_operator_approval=True,
        cooldown_seconds=900,
        max_attempts_per_hour=1,
        receipt_required=True,
        discovered_from="scripts/run_producer_listener.sh; producer_listener.py",
        confidence="low",
        classification="needs_operator_review",
        notes="Producer/Niles launcher requires secret-backed environment and may call Telegram; not safe for automatic recovery.",
    ),
    RecoveryActionSeed(
        recovery_action_id="hermes_systemd_user_start",
        agent_id="hermes",
        action_kind="systemd_user_start",
        command_label="Start Hermes gateway",
        command_argv=("systemctl", "--user", "start", "hermes-gateway.service"),
        working_directory=str(ROOT),
        status_check_kind="systemd_user_is_active",
        status_check_argv=("systemctl", "--user", "is-active", "hermes-gateway.service"),
        log_path=None,
        heartbeat_path=None,
        safe_to_attempt=False,
        requires_operator_approval=True,
        cooldown_seconds=900,
        max_attempts_per_hour=1,
        receipt_required=True,
        discovered_from="systemd/user/hermes-gateway.service.in; scripts/install_hermes_gateway_service.sh",
        confidence="medium",
        classification="safe_start_candidate",
        notes="Hermes has a narrow service path, but recovery is blocked in v0 unless explicitly allowed.",
    ),
    RecoveryActionSeed(
        recovery_action_id="report_bridge_status_only",
        agent_id="report_bridge",
        action_kind="status_only",
        command_label="Report Bridge metadata status",
        command_argv=(),
        working_directory=str(ROOT),
        status_check_kind="metadata_only",
        status_check_argv=None,
        log_path=None,
        heartbeat_path="generated/read_models/report_bridge.json",
        safe_to_attempt=True,
        requires_operator_approval=False,
        cooldown_seconds=0,
        max_attempts_per_hour=0,
        receipt_required=True,
        discovered_from="report_bridge.py; generated/read_models/report_bridge.json",
        confidence="high",
        classification="safe_status_check",
        notes="Report Bridge is metadata/package intake in v0; no live daemon recovery is needed.",
    ),
)


AGENT_CONFIGS: tuple[PresenceAgentConfig, ...] = (
    PresenceAgentConfig(
        agent_id="chief",
        display_name="Chief",
        lane_id="system_orchestration",
        desired_state="online",
        surfaces=(
            RuntimeSurface("chief_listener_service", "systemd_service", "systemd/user/chief-listener.service.in", "chief-listener.service", "chief_listener.py", "current_active", "systemd_restart"),
            RuntimeSurface("chief_worker_service", "systemd_service", "systemd/user/chief-worker.service.in", "chief-worker.service", "chief_worker.py", "current_active", "systemd_restart"),
            RuntimeSurface("chief_memory_worker_service", "systemd_service", "systemd/user/chief-memory-worker.service.in", "chief-memory-worker.service", "chief_memory_worker.py", "current_active", "systemd_restart"),
            RuntimeSurface("chief_state_worker_service", "systemd_service", "systemd/user/chief-state-worker.service.in", "chief-state-worker.service", "chief_state_worker.py", "current_active", "systemd_restart"),
            RuntimeSurface("chief_watcher_service", "systemd_service", "systemd/user/chief-watcher-brain.service.in", "chief-watcher-brain.service", "chief_watcher_brain.py", "current_active", "systemd_restart"),
        ),
        notes="System orchestration services are documented as systemd-owned; legacy launchers remain frozen.",
    ),
    PresenceAgentConfig(
        agent_id="cassandra",
        display_name="Cassandra",
        lane_id="operator_comms",
        desired_state="online",
        surfaces=(
            RuntimeSurface("cassandra_listener_service", "telegram_bot", "systemd/user/cassandra-listener.service.in", "cassandra-listener.service", "cassandra_listener.py", "current_active", "systemd_restart"),
            RuntimeSurface("cassandra_watcher_service", "local_service", "systemd/user/cassandra-watcher.service.in", "cassandra-watcher.service", "cassandra_watcher.py", "current_active", "systemd_restart"),
            RuntimeSurface("cassandra_briefing_scheduler_service", "local_service", "systemd/user/cassandra-briefing-scheduler.service.in", "cassandra-briefing-scheduler.service", "cassandra_briefing_scheduler.py", "current_active", "systemd_restart"),
        ),
        notes="Cassandra has repo-evident Telegram/listener surfaces, but token/secret contents are not inspected.",
    ),
    PresenceAgentConfig(
        agent_id="guardian",
        display_name="Guardian",
        lane_id="safety_security",
        desired_state="online",
        surfaces=(
            RuntimeSurface("guardian_listener_service", "telegram_bot", "systemd/user/chief-guardian-listener.service.in", "chief-guardian-listener.service", "chief_guardian_listener.py", "current_active", "systemd_restart"),
        ),
        notes="Guardian is the approval listener surface, not a planning agent.",
    ),
    PresenceAgentConfig(
        agent_id="niles",
        display_name="Niles",
        lane_id="music_art_production",
        desired_state="online",
        surfaces=(
            RuntimeSurface("niles_producer_listener", "script", "producer_listener.py", None, "producer_listener.py", "partial_overlap", "script_start", "Producer/Niles listener path exists, but secret-backed launcher is not safe for automatic recovery."),
            RuntimeSurface("niles_producer_intake", "script", "scripts/producer_intake.py", None, "producer_intake.py", "candidate_to_extend", "none", "Metadata/intake surface, not proof of online listener presence."),
        ),
        metadata_available_paths=("generated/producer/producer_compiled_context.json",),
        notes="Producer is treated as a Niles alias unless a later lane separates it.",
    ),
    PresenceAgentConfig(
        agent_id="hermes",
        display_name="Hermes",
        lane_id="advisory_synthesis",
        desired_state="online",
        surfaces=(
            RuntimeSurface("hermes_gateway_service", "systemd_service", "systemd/user/hermes-gateway.service.in", "hermes-gateway.service", "hermes_cli.main", "current_active", "systemd_restart"),
        ),
        metadata_available_paths=("hermes_advisory_packet.py", "docs/operations/HERMES_ADVISORY_PACKET_CONTRACT.md"),
        notes="Hermes gateway has a narrow installer/restart path, but this lane does not invoke it.",
    ),
    PresenceAgentConfig(
        agent_id="report_bridge",
        display_name="Report Bridge",
        lane_id="node_report_intake",
        desired_state="unknown_review",
        surfaces=(),
        metadata_available_paths=("report_bridge.py", "generated/read_models/report_bridge.json"),
        notes="Report Bridge is sanitized metadata/package intake, not a live daemon in v0.",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _display_path(path: str | Path, *, repo_root: str | Path = ROOT) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _resolve_repo_path(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS agent_presence_runs (
  run_id TEXT PRIMARY KEY,
  presence_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  agent_count INTEGER NOT NULL DEFAULT 0,
  expected_online_count INTEGER NOT NULL DEFAULT 0,
  online_count INTEGER NOT NULL DEFAULT 0,
  offline_unexpected_count INTEGER NOT NULL DEFAULT 0,
  degraded_count INTEGER NOT NULL DEFAULT 0,
  unknown_count INTEGER NOT NULL DEFAULT 0,
  broad_agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  telegram_api_allowed INTEGER NOT NULL DEFAULT 0,
  message_send_allowed INTEGER NOT NULL DEFAULT 0,
  arbitrary_command_allowed INTEGER NOT NULL DEFAULT 0,
  secret_access_allowed INTEGER NOT NULL DEFAULT 0,
  recovery_without_policy_allowed INTEGER NOT NULL DEFAULT 0,
  hard_kill_bypass_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  client_deployment_allowed INTEGER NOT NULL DEFAULT 0
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_presence_agents (
  agent_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  display_name TEXT NOT NULL,
  lane_id TEXT NOT NULL,
  desired_state TEXT NOT NULL,
  actual_state TEXT NOT NULL,
  presence_source TEXT NOT NULL,
  runtime_surface_found INTEGER NOT NULL DEFAULT 0,
  runtime_surface_kind TEXT NOT NULL,
  last_seen_at TEXT,
  expected_online INTEGER NOT NULL DEFAULT 0,
  autorecovery_allowed INTEGER NOT NULL DEFAULT 0,
  recovery_action_id TEXT,
  recovery_status TEXT NOT NULL,
  reason TEXT NOT NULL,
  blocker TEXT,
  receipt_id TEXT,
  telegram_ready_metadata INTEGER NOT NULL DEFAULT 0,
  no_authority_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES agent_presence_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_presence_checks (
  check_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  check_kind TEXT NOT NULL,
  surface_id TEXT,
  status TEXT NOT NULL,
  evidence_json TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  raw_secret_accessed INTEGER NOT NULL DEFAULT 0,
  message_sent INTEGER NOT NULL DEFAULT 0,
  command_executed INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (run_id) REFERENCES agent_presence_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_desired_states (
  agent_id TEXT PRIMARY KEY,
  desired_state TEXT NOT NULL,
  expected_online INTEGER NOT NULL DEFAULT 0,
  reason TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  hard_kill_respected INTEGER NOT NULL DEFAULT 1
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_recovery_policies (
  recovery_policy_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  recovery_allowed INTEGER NOT NULL DEFAULT 0,
  recovery_kind TEXT NOT NULL,
  recovery_command_id TEXT,
  requires_operator_clearance INTEGER NOT NULL DEFAULT 1,
  receipt_required INTEGER NOT NULL DEFAULT 1,
  max_attempts INTEGER NOT NULL DEFAULT 1,
  cooldown_seconds INTEGER NOT NULL DEFAULT 900,
  last_attempt_at TEXT,
  next_allowed_attempt_at TEXT,
  hard_kill_respected INTEGER NOT NULL DEFAULT 1,
  policy_reason TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_recovery_actions (
  recovery_action_id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  action_kind TEXT NOT NULL,
  command_label TEXT NOT NULL,
  command_argv_json TEXT NOT NULL,
  working_directory TEXT,
  status_check_kind TEXT NOT NULL,
  status_check_argv_json TEXT,
  log_path TEXT,
  heartbeat_path TEXT,
  safe_to_attempt INTEGER NOT NULL DEFAULT 0,
  requires_operator_approval INTEGER NOT NULL DEFAULT 1,
  cooldown_seconds INTEGER NOT NULL DEFAULT 900,
  max_attempts_per_hour INTEGER NOT NULL DEFAULT 1,
  receipt_required INTEGER NOT NULL DEFAULT 1,
  discovered_from TEXT NOT NULL,
  confidence TEXT NOT NULL,
  classification TEXT NOT NULL,
  notes TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_recovery_attempts (
  recovery_attempt_id TEXT PRIMARY KEY,
  receipt_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  recovery_action_id TEXT,
  attempted_at TEXT NOT NULL,
  dry_run INTEGER NOT NULL DEFAULT 0,
  attempted INTEGER NOT NULL DEFAULT 0,
  succeeded INTEGER NOT NULL DEFAULT 0,
  exit_code INTEGER,
  duration_ms INTEGER NOT NULL DEFAULT 0,
  stdout_excerpt TEXT,
  stderr_excerpt TEXT,
  blocker TEXT,
  command_argv_json TEXT NOT NULL,
  command_executed INTEGER NOT NULL DEFAULT 0,
  shell_used INTEGER NOT NULL DEFAULT 0,
  telegram_api_called INTEGER NOT NULL DEFAULT 0,
  message_sent INTEGER NOT NULL DEFAULT 0,
  secret_accessed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_recovery_receipts (
  receipt_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  recovery_status TEXT NOT NULL,
  recovery_kind TEXT NOT NULL,
  attempted INTEGER NOT NULL DEFAULT 0,
  succeeded INTEGER NOT NULL DEFAULT 0,
  summary TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES agent_presence_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_presence_blockers (
  blocker_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  blocker_kind TEXT NOT NULL,
  severity TEXT NOT NULL,
  summary TEXT NOT NULL,
  next_safe_move TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES agent_presence_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS agent_presence_runtime_surfaces (
  runtime_surface_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  surface_kind TEXT NOT NULL,
  source_path TEXT NOT NULL,
  service_name TEXT,
  process_name TEXT,
  surface_found INTEGER NOT NULL DEFAULT 0,
  classification TEXT NOT NULL,
  service_state TEXT,
  process_count INTEGER NOT NULL DEFAULT 0,
  safe_recovery_kind TEXT NOT NULL,
  recovery_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  observed_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES agent_presence_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_agent_presence_agents_state ON agent_presence_agents(actual_state)",
        "CREATE INDEX IF NOT EXISTS idx_agent_presence_checks_agent ON agent_presence_checks(agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_agent_presence_surfaces_agent ON agent_presence_runtime_surfaces(agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_agent_recovery_actions_agent ON agent_recovery_actions(agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_agent_recovery_attempts_agent ON agent_recovery_attempts(agent_id)",
    )


def init_agent_presence_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    parent = Path(path).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    init_agent_lane_registry_schema(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def agent_presence_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_agent_presence_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table'
  AND (name LIKE 'agent_presence%'
       OR name IN (
         'agent_desired_states',
         'agent_recovery_policies',
         'agent_recovery_actions',
         'agent_recovery_attempts',
         'agent_recovery_receipts'
       ))
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _agent_seed_by_id() -> dict[str, Any]:
    return {seed.agent_id: seed for seed in DEFAULT_AGENT_LANE_SEEDS}


def _process_snapshot() -> dict[str, int]:
    """Return script/process-name counts from /proc cmdlines.

    This reads local process metadata only. It does not inspect process
    environments, secrets, sockets, or network state.
    """

    counts: Counter[str] = Counter()
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return {}
    for pid_dir in proc_root.iterdir():
        if not pid_dir.name.isdigit():
            continue
        try:
            raw = (pid_dir / "cmdline").read_bytes()
        except OSError:
            continue
        if not raw:
            continue
        cmdline = raw.replace(b"\x00", b" ").decode("utf-8", errors="ignore")
        for config in AGENT_CONFIGS:
            for surface in config.surfaces:
                if surface.process_name and surface.process_name in cmdline:
                    counts[surface.process_name] += 1
    return dict(counts)


def _systemd_user_state(service_names: tuple[str, ...]) -> dict[str, str]:
    states: dict[str, str] = {}
    for service in service_names:
        try:
            completed = subprocess.run(
                ["systemctl", "--user", "is-active", service],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            states[service] = "unknown"
            continue
        value = completed.stdout.strip() or completed.stderr.strip() or "unknown"
        states[service] = value if completed.returncode == 0 else value
    return states


def seed_desired_states(
    *,
    db_path: str | Path | None = None,
    desired_state_overrides: dict[str, str] | None = None,
) -> None:
    path = init_agent_presence_schema(db_path)
    now = utc_now()
    overrides = desired_state_overrides or {}
    conn = sqlite3.connect(path)
    try:
        for config in AGENT_CONFIGS:
            desired = overrides.get(config.agent_id, config.desired_state)
            if desired not in DESIRED_STATES:
                raise ValueError(f"invalid desired_state for {config.agent_id}: {desired}")
            expected_online = desired == "online"
            reason = "default expected online" if expected_online else "metadata-only or review-required default"
            if desired in {"offline_intentional", "maintenance", "hard_kill"}:
                reason = f"operator/policy override: {desired}"
            conn.execute(
                """
INSERT INTO agent_desired_states (
  agent_id, desired_state, expected_online, reason, updated_at, hard_kill_respected
) VALUES (?, ?, ?, ?, ?, 1)
ON CONFLICT(agent_id) DO UPDATE SET
  desired_state = excluded.desired_state,
  expected_online = excluded.expected_online,
  reason = excluded.reason,
  updated_at = excluded.updated_at,
  hard_kill_respected = 1
""".strip(),
                (config.agent_id, desired, 1 if expected_online else 0, reason, now),
            )
        conn.commit()
    finally:
        conn.close()


def _action_to_row(seed: RecoveryActionSeed, *, updated_at: str) -> tuple[Any, ...]:
    return (
        seed.recovery_action_id,
        seed.agent_id,
        seed.action_kind,
        seed.command_label,
        stable_json(list(seed.command_argv)),
        seed.working_directory,
        seed.status_check_kind,
        stable_json(list(seed.status_check_argv)) if seed.status_check_argv else None,
        seed.log_path,
        seed.heartbeat_path,
        1 if seed.safe_to_attempt else 0,
        1 if seed.requires_operator_approval else 0,
        seed.cooldown_seconds,
        seed.max_attempts_per_hour,
        1 if seed.receipt_required else 0,
        seed.discovered_from,
        seed.confidence,
        seed.classification,
        seed.notes,
        updated_at,
    )


def seed_recovery_actions(
    *,
    db_path: str | Path | None = None,
    action_overrides: dict[str, dict[str, Any]] | None = None,
) -> None:
    path = init_agent_presence_schema(db_path)
    now = utc_now()
    overrides = action_overrides or {}
    conn = sqlite3.connect(path)
    try:
        for seed in DEFAULT_RECOVERY_ACTIONS:
            override = overrides.get(seed.agent_id, {})
            effective = seed
            if override:
                effective = RecoveryActionSeed(
                    recovery_action_id=str(override.get("recovery_action_id", seed.recovery_action_id)),
                    agent_id=seed.agent_id,
                    action_kind=str(override.get("action_kind", seed.action_kind)),
                    command_label=str(override.get("command_label", seed.command_label)),
                    command_argv=tuple(override.get("command_argv", seed.command_argv)),
                    working_directory=str(override.get("working_directory", seed.working_directory)),
                    status_check_kind=str(override.get("status_check_kind", seed.status_check_kind)),
                    status_check_argv=tuple(override["status_check_argv"]) if override.get("status_check_argv") else seed.status_check_argv,
                    log_path=override.get("log_path", seed.log_path),
                    heartbeat_path=override.get("heartbeat_path", seed.heartbeat_path),
                    safe_to_attempt=bool(override.get("safe_to_attempt", seed.safe_to_attempt)),
                    requires_operator_approval=bool(override.get("requires_operator_approval", seed.requires_operator_approval)),
                    cooldown_seconds=int(override.get("cooldown_seconds", seed.cooldown_seconds)),
                    max_attempts_per_hour=int(override.get("max_attempts_per_hour", seed.max_attempts_per_hour)),
                    receipt_required=bool(override.get("receipt_required", seed.receipt_required)),
                    discovered_from=str(override.get("discovered_from", seed.discovered_from)),
                    confidence=str(override.get("confidence", seed.confidence)),
                    classification=str(override.get("classification", seed.classification)),
                    notes=str(override.get("notes", seed.notes)),
                )
            conn.execute(
                """
INSERT INTO agent_recovery_actions (
  recovery_action_id, agent_id, action_kind, command_label,
  command_argv_json, working_directory, status_check_kind,
  status_check_argv_json, log_path, heartbeat_path, safe_to_attempt,
  requires_operator_approval, cooldown_seconds, max_attempts_per_hour,
  receipt_required, discovered_from, confidence, classification,
  notes, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(recovery_action_id) DO UPDATE SET
  action_kind = excluded.action_kind,
  command_label = excluded.command_label,
  command_argv_json = excluded.command_argv_json,
  working_directory = excluded.working_directory,
  status_check_kind = excluded.status_check_kind,
  status_check_argv_json = excluded.status_check_argv_json,
  log_path = excluded.log_path,
  heartbeat_path = excluded.heartbeat_path,
  safe_to_attempt = excluded.safe_to_attempt,
  requires_operator_approval = excluded.requires_operator_approval,
  cooldown_seconds = excluded.cooldown_seconds,
  max_attempts_per_hour = excluded.max_attempts_per_hour,
  receipt_required = excluded.receipt_required,
  discovered_from = excluded.discovered_from,
  confidence = excluded.confidence,
  classification = excluded.classification,
  notes = excluded.notes,
  updated_at = excluded.updated_at
""".strip(),
                _action_to_row(effective, updated_at=now),
            )
        conn.commit()
    finally:
        conn.close()


def _recovery_action_for_agent(conn: sqlite3.Connection, agent_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
SELECT *
FROM agent_recovery_actions
WHERE agent_id = ?
ORDER BY safe_to_attempt DESC, recovery_action_id
LIMIT 1
""".strip(),
        (agent_id,),
    ).fetchone()
    if row is None:
        return None
    payload = dict(row)
    payload["command_argv"] = json.loads(payload["command_argv_json"])
    payload["status_check_argv"] = json.loads(payload["status_check_argv_json"]) if payload.get("status_check_argv_json") else None
    payload["safe_to_attempt"] = bool(payload["safe_to_attempt"])
    payload["requires_operator_approval"] = bool(payload["requires_operator_approval"])
    payload["receipt_required"] = bool(payload["receipt_required"])
    return payload


def _surface_state(
    *,
    surface: RuntimeSurface,
    repo_root: str | Path,
    process_counts: dict[str, int],
    service_states: dict[str, str],
) -> dict[str, Any]:
    source = _resolve_repo_path(surface.source_path, repo_root=repo_root)
    service_state = service_states.get(surface.service_name or "", "not_applicable")
    process_count = process_counts.get(surface.process_name or "", 0)
    return {
        "surface_id": surface.surface_id,
        "surface_kind": surface.surface_kind,
        "source_path": surface.source_path,
        "service_name": surface.service_name,
        "process_name": surface.process_name,
        "surface_found": source.exists(),
        "classification": surface.classification,
        "service_state": service_state,
        "process_count": process_count,
        "safe_recovery_kind": surface.safe_recovery_kind,
        "notes": surface.notes,
    }


def _actual_state_for_agent(
    *,
    config: PresenceAgentConfig,
    surface_states: list[dict[str, Any]],
    repo_root: str | Path,
) -> dict[str, Any]:
    runtime_surface_found = any(item["surface_found"] for item in surface_states)
    active_surfaces = [
        item
        for item in surface_states
        if item.get("service_state") == "active" or int(item.get("process_count") or 0) > 0
    ]
    metadata_available = any(_resolve_repo_path(path, repo_root=repo_root).exists() for path in config.metadata_available_paths)
    if not surface_states and metadata_available:
        return {
            "actual_state": "metadata_available",
            "presence_source": "read_model",
            "runtime_surface_found": False,
            "runtime_surface_kind": "metadata_only",
            "last_seen_at": utc_now(),
            "reason": "Metadata/read-model surface is available; no live runtime surface is configured.",
            "blocker": None,
        }
    if not runtime_surface_found and not metadata_available:
        return {
            "actual_state": "not_configured",
            "presence_source": "unknown",
            "runtime_surface_found": False,
            "runtime_surface_kind": "unknown",
            "last_seen_at": None,
            "reason": "No runtime or metadata surface was found in the repo.",
            "blocker": "runtime status path not discovered",
        }
    if active_surfaces:
        expected_count = max(1, len([item for item in surface_states if item["surface_found"]]))
        actual_state = "online" if len(active_surfaces) >= expected_count else "degraded"
        return {
            "actual_state": actual_state,
            "presence_source": "service_check" if any(item.get("service_state") == "active" for item in active_surfaces) else "process_check",
            "runtime_surface_found": runtime_surface_found,
            "runtime_surface_kind": ",".join(sorted({item["surface_kind"] for item in surface_states if item["surface_found"]})) or "unknown",
            "last_seen_at": utc_now(),
            "reason": f"{len(active_surfaces)} runtime surface(s) show active process/service evidence.",
            "blocker": None if actual_state == "online" else "only some expected runtime surfaces show active evidence",
        }
    if runtime_surface_found:
        return {
            "actual_state": "offline",
            "presence_source": "runtime_surface",
            "runtime_surface_found": True,
            "runtime_surface_kind": ",".join(sorted({item["surface_kind"] for item in surface_states if item["surface_found"]})) or "unknown",
            "last_seen_at": None,
            "reason": "Runtime surfaces exist, but no active local process/service evidence was found.",
            "blocker": "expected runtime evidence missing",
        }
    return {
        "actual_state": "metadata_available" if metadata_available else "unknown",
        "presence_source": "read_model" if metadata_available else "unknown",
        "runtime_surface_found": False,
        "runtime_surface_kind": "metadata_only" if metadata_available else "unknown",
        "last_seen_at": utc_now() if metadata_available else None,
        "reason": "Metadata is available, but live runtime evidence is not configured.",
        "blocker": None if metadata_available else "presence evidence unavailable",
    }


def _policy_for_agent(
    *,
    config: PresenceAgentConfig,
    desired_state: str,
    actual_state: str,
    surface_states: list[dict[str, Any]],
    recovery_action: dict[str, Any] | None,
    policy_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    override = (policy_overrides or {}).get(config.agent_id, {})
    known_kind = "none"
    if recovery_action and recovery_action.get("action_kind") != "status_only":
        known_kind = str(recovery_action.get("action_kind") or "unknown_review")
    else:
        for surface in surface_states:
            if surface.get("surface_found") and surface.get("safe_recovery_kind") not in {None, "none", "unknown_review"}:
                known_kind = str(surface["safe_recovery_kind"])
                break
    if desired_state == "hard_kill":
        recovery_status = "blocked"
        reason = "hard_kill state blocks recovery."
    elif desired_state == "offline_intentional":
        recovery_status = "blocked"
        reason = "offline_intentional state blocks recovery."
    elif desired_state == "maintenance":
        recovery_status = "blocked"
        reason = "maintenance state blocks recovery."
    elif actual_state in {"online", "metadata_available"}:
        recovery_status = "not_needed"
        reason = "Presence is online or metadata-available; no recovery is needed."
    elif desired_state == "unknown_review":
        recovery_status = "blocked"
        reason = "unknown_review desired state blocks automatic recovery."
    elif recovery_action and recovery_action.get("action_kind") == "status_only":
        recovery_status = "blocked"
        reason = "Only a status/read-model action exists; no recovery mutation is available."
    elif recovery_action and not recovery_action.get("safe_to_attempt"):
        recovery_status = "blocked"
        reason = f"Candidate recovery action is not safe to attempt in v0: {recovery_action.get('notes')}"
    elif known_kind != "none":
        recovery_status = "blocked"
        reason = "A candidate recovery path exists, but autorecovery is not enabled in v0."
    else:
        recovery_status = "blocked"
        reason = "No known safe recovery path exists."
    recovery_allowed = bool(override.get("recovery_allowed", False))
    if recovery_action and not recovery_action.get("safe_to_attempt"):
        recovery_allowed = False
    if desired_state in {"hard_kill", "offline_intentional", "maintenance"}:
        recovery_allowed = False
    if recovery_allowed and recovery_status == "blocked" and actual_state in {"offline", "degraded"}:
        recovery_status = "available"
        reason = "Recovery is policy-allowed and requires an explicit receipt-backed execute command."
    recovery_kind = str(override.get("recovery_kind", known_kind if known_kind in RECOVERY_KINDS else "unknown_review"))
    if recovery_kind not in RECOVERY_KINDS:
        recovery_kind = "unknown_review"
    return {
        "recovery_allowed": recovery_allowed,
        "recovery_kind": recovery_kind,
        "recovery_command_id": override.get("recovery_command_id"),
        "requires_operator_clearance": bool(override.get("requires_operator_clearance", True)),
        "receipt_required": True,
        "max_attempts": int(override.get("max_attempts", 1)),
        "cooldown_seconds": int(override.get("cooldown_seconds", 900)),
        "last_attempt_at": None,
        "next_allowed_attempt_at": None,
        "hard_kill_respected": True,
        "recovery_status": recovery_status,
        "policy_reason": reason,
        "recovery_action_id": recovery_action.get("recovery_action_id") if recovery_action else None,
    }


def build_agent_presence_snapshot(
    *,
    db_path: str | Path | None = None,
    repo_root: str | Path = ROOT,
    run_id: str | None = None,
    desired_state_overrides: dict[str, str] | None = None,
    process_counts: dict[str, int] | None = None,
    service_states: dict[str, str] | None = None,
    recovery_policy_overrides: dict[str, dict[str, Any]] | None = None,
    recovery_action_overrides: dict[str, dict[str, Any]] | None = None,
) -> AgentPresenceBuildResult:
    path = init_agent_presence_schema(db_path)
    seed_agent_lane_registry(db_path=path)
    seed_desired_states(db_path=path, desired_state_overrides=desired_state_overrides)
    seed_recovery_actions(db_path=path, action_overrides=recovery_action_overrides)
    now = utc_now()
    resolved_run_id = run_id or _row_id("agentpresence", now)
    discovered_process_counts = process_counts if process_counts is not None else _process_snapshot()
    service_names = tuple(
        surface.service_name
        for config in AGENT_CONFIGS
        for surface in config.surfaces
        if surface.service_name
    )
    discovered_service_states = service_states if service_states is not None else _systemd_user_state(service_names)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    agent_rows: list[dict[str, Any]] = []
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for table in (
            "agent_presence_agents",
            "agent_presence_checks",
            "agent_recovery_receipts",
            "agent_presence_blockers",
            "agent_presence_runtime_surfaces",
        ):
            conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (resolved_run_id,))
        desired_rows = {
            row["agent_id"]: dict(row)
            for row in conn.execute("SELECT * FROM agent_desired_states").fetchall()
        }
        conn.execute(
            """
INSERT INTO agent_presence_runs (
  run_id, presence_version, created_at, completed_at, agent_count,
  expected_online_count, online_count, offline_unexpected_count,
  degraded_count, unknown_count, broad_agent_activation_allowed,
  telegram_api_allowed, message_send_allowed, arbitrary_command_allowed,
  secret_access_allowed, recovery_without_policy_allowed, hard_kill_bypass_allowed,
  network_authority, model_call_allowed, client_deployment_allowed
) VALUES (?, ?, ?, NULL, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
ON CONFLICT(run_id) DO NOTHING
""".strip(),
            (resolved_run_id, AGENT_PRESENCE_VERSION, now),
        )
        seed_by_id = _agent_seed_by_id()
        for config in AGENT_CONFIGS:
            desired_row = desired_rows[config.agent_id]
            desired_state = desired_row["desired_state"]
            surface_states = [
                _surface_state(
                    surface=surface,
                    repo_root=repo_root,
                    process_counts=discovered_process_counts,
                    service_states=discovered_service_states,
                )
                for surface in config.surfaces
            ]
            actual = _actual_state_for_agent(config=config, surface_states=surface_states, repo_root=repo_root)
            recovery_action = _recovery_action_for_agent(conn, config.agent_id)
            policy = _policy_for_agent(
                config=config,
                desired_state=desired_state,
                actual_state=actual["actual_state"],
                surface_states=surface_states,
                recovery_action=recovery_action,
                policy_overrides=recovery_policy_overrides,
            )
            expected_online = bool(desired_row["expected_online"])
            if actual["actual_state"] == "metadata_available":
                expected_online = False
            receipt_id = _row_id("agentpresencereceipt", resolved_run_id, config.agent_id, policy["recovery_status"])
            blocker = actual["blocker"]
            if policy["recovery_status"] == "blocked" and expected_online and actual["actual_state"] in {"offline", "degraded", "unknown", "not_configured"}:
                blocker = blocker or policy["policy_reason"]
            agent_row = {
                "agent_id": config.agent_id,
                "display_name": config.display_name,
                "lane_id": config.lane_id,
                "desired_state": desired_state,
                "actual_state": actual["actual_state"],
                "presence_source": actual["presence_source"],
                "runtime_surface_found": bool(actual["runtime_surface_found"]),
                "runtime_surface_kind": actual["runtime_surface_kind"],
                "last_seen_at": actual["last_seen_at"],
                "expected_online": expected_online,
                "autorecovery_allowed": policy["recovery_allowed"],
                "recovery_action_id": policy["recovery_action_id"] or policy["recovery_command_id"],
                "recovery_status": policy["recovery_status"],
                "reason": actual["reason"],
                "blocker": blocker,
                "receipt_id": receipt_id,
                "telegram_ready_metadata": any(
                    posture[0] == "telegram" for posture in seed_by_id.get(config.agent_id, seed_by_id["chief"]).source_kind_postures
                ),
            }
            agent_rows.append(agent_row)
            conn.execute(
                """
INSERT INTO agent_presence_agents (
  agent_id, run_id, display_name, lane_id, desired_state, actual_state,
  presence_source, runtime_surface_found, runtime_surface_kind, last_seen_at,
  expected_online, autorecovery_allowed, recovery_action_id, recovery_status,
  reason, blocker, receipt_id, telegram_ready_metadata, no_authority_json, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(agent_id) DO UPDATE SET
  run_id = excluded.run_id,
  display_name = excluded.display_name,
  lane_id = excluded.lane_id,
  desired_state = excluded.desired_state,
  actual_state = excluded.actual_state,
  presence_source = excluded.presence_source,
  runtime_surface_found = excluded.runtime_surface_found,
  runtime_surface_kind = excluded.runtime_surface_kind,
  last_seen_at = excluded.last_seen_at,
  expected_online = excluded.expected_online,
  autorecovery_allowed = excluded.autorecovery_allowed,
  recovery_action_id = excluded.recovery_action_id,
  recovery_status = excluded.recovery_status,
  reason = excluded.reason,
  blocker = excluded.blocker,
  receipt_id = excluded.receipt_id,
  telegram_ready_metadata = excluded.telegram_ready_metadata,
  no_authority_json = excluded.no_authority_json,
  created_at = excluded.created_at
""".strip(),
                (
                    config.agent_id,
                    resolved_run_id,
                    config.display_name,
                    config.lane_id,
                    desired_state,
                    actual["actual_state"],
                    actual["presence_source"],
                    1 if actual["runtime_surface_found"] else 0,
                    actual["runtime_surface_kind"],
                    actual["last_seen_at"],
                    1 if expected_online else 0,
                    1 if policy["recovery_allowed"] else 0,
                    policy["recovery_action_id"] or policy["recovery_command_id"],
                    policy["recovery_status"],
                    actual["reason"],
                    blocker,
                    receipt_id,
                    1 if agent_row["telegram_ready_metadata"] else 0,
                    stable_json(NO_AUTHORITY_FLAGS),
                    now,
                ),
            )
            conn.execute(
                """
INSERT OR REPLACE INTO agent_recovery_policies (
  recovery_policy_id, agent_id, recovery_allowed, recovery_kind,
  recovery_command_id, requires_operator_clearance, receipt_required,
  max_attempts, cooldown_seconds, last_attempt_at, next_allowed_attempt_at,
  hard_kill_respected, policy_reason, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
                (
                    _row_id("agentrecoverypolicy", config.agent_id),
                    config.agent_id,
                    1 if policy["recovery_allowed"] else 0,
                    policy["recovery_kind"],
                    policy["recovery_action_id"] or policy["recovery_command_id"],
                    1 if policy["requires_operator_clearance"] else 0,
                    1,
                    policy["max_attempts"],
                    policy["cooldown_seconds"],
                    policy["last_attempt_at"],
                    policy["next_allowed_attempt_at"],
                    1,
                    policy["policy_reason"],
                    now,
                ),
            )
            receipt_payload = {
                "agent_id": config.agent_id,
                "desired_state": desired_state,
                "actual_state": actual["actual_state"],
                "recovery_status": policy["recovery_status"],
                "attempted": False,
                **NO_AUTHORITY_FLAGS,
            }
            conn.execute(
                """
INSERT OR REPLACE INTO agent_recovery_receipts (
  receipt_id, run_id, agent_id, recovery_status, recovery_kind,
  attempted, succeeded, summary, payload_json, created_at
) VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, ?)
""".strip(),
                (
                    receipt_id,
                    resolved_run_id,
                    config.agent_id,
                    policy["recovery_status"],
                    policy["recovery_kind"],
                    f"Presence recovery status for {config.agent_id}: {policy['recovery_status']}; no recovery command executed.",
                    stable_json(receipt_payload),
                    now,
                ),
            )
            for surface_state in surface_states:
                conn.execute(
                    """
INSERT INTO agent_presence_runtime_surfaces (
  runtime_surface_id, run_id, agent_id, surface_kind, source_path,
  service_name, process_name, surface_found, classification, service_state,
  process_count, safe_recovery_kind, recovery_allowed, notes, observed_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
""".strip(),
                    (
                        _row_id("agentpresencesurface", resolved_run_id, config.agent_id, surface_state["surface_id"]),
                        resolved_run_id,
                        config.agent_id,
                        surface_state["surface_kind"],
                        surface_state["source_path"],
                        surface_state["service_name"],
                        surface_state["process_name"],
                        1 if surface_state["surface_found"] else 0,
                        surface_state["classification"],
                        surface_state["service_state"],
                        int(surface_state["process_count"] or 0),
                        surface_state["safe_recovery_kind"],
                        surface_state["notes"],
                        now,
                    ),
                )
                check_status = "online" if surface_state["service_state"] == "active" or int(surface_state["process_count"] or 0) > 0 else "not_running"
                conn.execute(
                    """
INSERT INTO agent_presence_checks (
  check_id, run_id, agent_id, check_kind, surface_id, status,
  evidence_json, checked_at, raw_secret_accessed, message_sent, command_executed
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
""".strip(),
                    (
                        _row_id("agentpresencecheck", resolved_run_id, config.agent_id, surface_state["surface_id"]),
                        resolved_run_id,
                        config.agent_id,
                        "runtime_surface_check",
                        surface_state["surface_id"],
                        check_status,
                        stable_json(surface_state),
                        now,
                    ),
                )
            if blocker:
                conn.execute(
                    """
INSERT INTO agent_presence_blockers (
  blocker_id, run_id, agent_id, blocker_kind, severity,
  summary, next_safe_move, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
                    (
                        _row_id("agentpresenceblocker", resolved_run_id, config.agent_id, blocker),
                        resolved_run_id,
                        config.agent_id,
                        "presence_or_recovery_blocker",
                        "warning" if desired_state != "hard_kill" else "info",
                        blocker,
                        _next_safe_move(agent_row),
                        now,
                    ),
                )
        counts = Counter(row["actual_state"] for row in agent_rows)
        expected_online_count = sum(1 for row in agent_rows if row["expected_online"])
        offline_unexpected_count = sum(
            1
            for row in agent_rows
            if row["expected_online"] and row["actual_state"] in {"offline", "degraded", "unknown", "not_configured"}
        )
        conn.execute(
            """
INSERT INTO agent_presence_runs (
  run_id, presence_version, created_at, completed_at, agent_count,
  expected_online_count, online_count, offline_unexpected_count,
  degraded_count, unknown_count, broad_agent_activation_allowed,
  telegram_api_allowed, message_send_allowed, arbitrary_command_allowed,
  secret_access_allowed, recovery_without_policy_allowed, hard_kill_bypass_allowed,
  network_authority, model_call_allowed, client_deployment_allowed
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
ON CONFLICT(run_id) DO UPDATE SET
  completed_at = excluded.completed_at,
  agent_count = excluded.agent_count,
  expected_online_count = excluded.expected_online_count,
  online_count = excluded.online_count,
  offline_unexpected_count = excluded.offline_unexpected_count,
  degraded_count = excluded.degraded_count,
  unknown_count = excluded.unknown_count
""".strip(),
            (
                resolved_run_id,
                AGENT_PRESENCE_VERSION,
                now,
                now,
                len(agent_rows),
                expected_online_count,
                counts["online"],
                offline_unexpected_count,
                counts["degraded"],
                counts["unknown"] + counts["not_configured"],
            ),
        )
        conn.commit()
    finally:
        conn.close()
    counts = Counter(row["actual_state"] for row in agent_rows)
    expected_online_count = sum(1 for row in agent_rows if row["expected_online"])
    offline_unexpected_count = sum(
        1
        for row in agent_rows
        if row["expected_online"] and row["actual_state"] in {"offline", "degraded", "unknown", "not_configured"}
    )
    return AgentPresenceBuildResult(
        run_id=resolved_run_id,
        db_path=path,
        agent_count=len(agent_rows),
        expected_online_count=expected_online_count,
        online_count=counts["online"],
        offline_unexpected_count=offline_unexpected_count,
        degraded_count=counts["degraded"],
        unknown_count=counts["unknown"] + counts["not_configured"],
    )


def _next_safe_move(agent: dict[str, Any]) -> str:
    if agent["desired_state"] == "hard_kill":
        return "Respect hard_kill. Do not recover without a new explicit operator lane."
    if agent["desired_state"] == "offline_intentional":
        return "Respect intentional offline state. Do not recover."
    if agent["desired_state"] == "maintenance":
        return "Respect maintenance state. Do not recover until maintenance is cleared."
    if agent["actual_state"] == "online":
        return "No recovery needed."
    if agent["actual_state"] == "metadata_available":
        return "Use metadata/read-model posture; do not pretend a daemon is online."
    if agent["recovery_status"] == "available":
        return "Recovery is policy-available, but execution still requires an explicit receipt-backed recovery command."
    if agent["runtime_surface_found"]:
        return "Inspect the documented service/process surface and choose a bounded recovery lane if needed."
    return "Find or define a real status/heartbeat/runtime surface before attempting recovery."


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT r.run_id
FROM agent_presence_runs r
WHERE EXISTS (
  SELECT 1
  FROM agent_presence_agents a
  WHERE a.run_id = r.run_id
)
ORDER BY completed_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return str(row[0]) if row else None


def _agent_dict(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["runtime_surface_found"] = bool(payload["runtime_surface_found"])
    payload["expected_online"] = bool(payload["expected_online"])
    payload["autorecovery_allowed"] = bool(payload["autorecovery_allowed"])
    payload["telegram_ready_metadata"] = bool(payload["telegram_ready_metadata"])
    payload["no_authority_flags"] = json.loads(payload["no_authority_json"])
    payload["next_safe_move"] = _next_safe_move(payload)
    return payload


REPORTS = {"summary", "offline", "expected-online", "recovery-available"}


def build_agent_presence_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
    agent: str | None = None,
) -> dict[str, Any]:
    if report not in REPORTS:
        raise ValueError(f"unknown agent presence report: {report}")
    path = init_agent_presence_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        run_id = _latest_run_id(conn)
        if not run_id:
            return {
                "status": "empty",
                "report": report,
                "db_path": path,
                "items": [],
                "counts": {},
                "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
            }
        params: list[Any] = [run_id]
        where = "WHERE run_id = ?"
        if agent:
            where += " AND agent_id = ?"
            params.append(agent)
        elif report == "offline":
            where += " AND expected_online = 1 AND actual_state IN ('offline', 'degraded', 'unknown', 'not_configured')"
        elif report == "expected-online":
            where += " AND expected_online = 1"
        elif report == "recovery-available":
            where += " AND recovery_status = 'available'"
        rows = conn.execute(
            f"""
SELECT *
FROM agent_presence_agents
{where}
ORDER BY agent_id
""".strip(),
            tuple(params),
        ).fetchall()
        all_rows = [_agent_dict(row) for row in conn.execute("SELECT * FROM agent_presence_agents WHERE run_id = ?", (run_id,)).fetchall()]
        items = [_agent_dict(row) for row in rows]
        state_counts = Counter(row["actual_state"] for row in all_rows)
        desired_counts = Counter(row["desired_state"] for row in all_rows)
        recovery_counts = Counter(row["recovery_status"] for row in all_rows)
        surfaces = _dict_rows(
            conn,
            """
SELECT agent_id, surface_kind, source_path, service_name, process_name,
       surface_found, classification, service_state, process_count,
       safe_recovery_kind, recovery_allowed, notes
FROM agent_presence_runtime_surfaces
WHERE run_id = ?
ORDER BY agent_id, runtime_surface_id
""".strip(),
            (run_id,),
        )
        actions = _dict_rows(
            conn,
            """
SELECT recovery_action_id, agent_id, action_kind, command_label,
       command_argv_json, working_directory, status_check_kind,
       status_check_argv_json, safe_to_attempt, requires_operator_approval,
       cooldown_seconds, max_attempts_per_hour, receipt_required,
       discovered_from, confidence, classification, notes
FROM agent_recovery_actions
ORDER BY agent_id, recovery_action_id
""".strip(),
        )
        for action in actions:
            action["command_argv"] = json.loads(action.pop("command_argv_json"))
            action["status_check_argv"] = json.loads(action.pop("status_check_argv_json")) if action.get("status_check_argv_json") else None
            action.pop("status_check_argv_json", None)
            action["safe_to_attempt"] = bool(action["safe_to_attempt"])
            action["requires_operator_approval"] = bool(action["requires_operator_approval"])
            action["receipt_required"] = bool(action["receipt_required"])
        attempts = _dict_rows(
            conn,
            """
SELECT recovery_attempt_id, receipt_id, agent_id, recovery_action_id,
       attempted_at, dry_run, attempted, succeeded, exit_code,
       duration_ms, blocker, command_argv_json
FROM agent_recovery_attempts
ORDER BY attempted_at DESC, recovery_attempt_id DESC
LIMIT 20
""".strip(),
        )
        for attempt in attempts:
            attempt["dry_run"] = bool(attempt["dry_run"])
            attempt["attempted"] = bool(attempt["attempted"])
            attempt["succeeded"] = bool(attempt["succeeded"])
            attempt["command_argv"] = json.loads(attempt.pop("command_argv_json"))
        return {
            "status": "ok",
            "report": report,
            "agent": agent,
            "db_path": path,
            "run_id": run_id,
            "agent_count": len(all_rows),
            "counts": {
                "by_actual_state": dict(sorted(state_counts.items())),
                "by_desired_state": dict(sorted(desired_counts.items())),
                "by_recovery_status": dict(sorted(recovery_counts.items())),
                "expected_online": sum(1 for row in all_rows if row["expected_online"]),
                "offline_unexpected": sum(
                    1
                    for row in all_rows
                    if row["expected_online"] and row["actual_state"] in {"offline", "degraded", "unknown", "not_configured"}
                ),
                "online": state_counts["online"],
                "degraded": state_counts["degraded"],
                "unknown": state_counts["unknown"] + state_counts["not_configured"],
                "intentional_offline": desired_counts["offline_intentional"],
                "maintenance_or_hard_kill": desired_counts["maintenance"] + desired_counts["hard_kill"],
            },
            "items": items,
            "runtime_surfaces": surfaces,
            "recovery_actions": actions,
            "recent_recovery_attempts": attempts,
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _excerpt(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 20] + "\n[truncated]\n"


def _argv_is_allowlisted(action: dict[str, Any]) -> bool:
    argv = action.get("command_argv") or []
    if not argv:
        return False
    if action.get("action_kind") in {"systemd_user_start", "systemd_user_restart"}:
        operation = "start" if action["action_kind"] == "systemd_user_start" else "restart"
        return (
            len(argv) >= 4
            and argv[0:3] == ["systemctl", "--user", operation]
            and all(isinstance(item, str) and item.endswith(".service") for item in argv[3:])
        )
    return False


def _latest_agent_and_action(conn: sqlite3.Connection, agent_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    agent_row = conn.execute("SELECT * FROM agent_presence_agents WHERE agent_id = ?", (agent_id,)).fetchone()
    if agent_row is None:
        return None, None, None
    agent = _agent_dict(agent_row)
    action = _recovery_action_for_agent(conn, agent_id)
    policy_row = conn.execute("SELECT * FROM agent_recovery_policies WHERE agent_id = ?", (agent_id,)).fetchone()
    policy = dict(policy_row) if policy_row else None
    if policy:
        policy["recovery_allowed"] = bool(policy["recovery_allowed"])
        policy["requires_operator_clearance"] = bool(policy["requires_operator_clearance"])
        policy["receipt_required"] = bool(policy["receipt_required"])
        policy["hard_kill_respected"] = bool(policy["hard_kill_respected"])
    return agent, action, policy


def _recovery_blocker(
    *,
    agent: dict[str, Any] | None,
    action: dict[str, Any] | None,
    policy: dict[str, Any] | None,
    now: str,
) -> str | None:
    if agent is None:
        return "agent presence row is missing; build presence before recovery"
    if agent["desired_state"] == "hard_kill":
        return "hard_kill prevents recovery"
    if agent["desired_state"] == "offline_intentional":
        return "offline_intentional prevents recovery"
    if agent["desired_state"] == "maintenance":
        return "maintenance prevents recovery"
    if agent["desired_state"] == "unknown_review":
        return "unknown_review desired state prevents recovery"
    if not agent["expected_online"]:
        return "agent is not expected online"
    if agent["actual_state"] not in {"offline", "degraded"}:
        return f"agent actual_state is {agent['actual_state']}; recovery is not needed"
    if not action:
        return "no recovery action is registered"
    if action["action_kind"] == "status_only":
        return "registered action is status-only, not recovery"
    if not action["safe_to_attempt"]:
        return "registered recovery action is not safe_to_attempt"
    if not _argv_is_allowlisted(action):
        return "registered recovery argv is not allowlisted"
    if not policy or not policy["recovery_allowed"]:
        return "recovery policy does not explicitly allow execution"
    current = _parse_iso(now) or datetime.now(timezone.utc)
    cooldown_seconds = int(policy.get("cooldown_seconds") or action.get("cooldown_seconds") or 0)
    last_attempt = _parse_iso(policy.get("last_attempt_at"))
    if last_attempt and current < last_attempt + timedelta(seconds=cooldown_seconds):
        return "cooldown prevents another recovery attempt"
    return None


def _count_recent_attempts(conn: sqlite3.Connection, agent_id: str, *, now: str) -> int:
    current = _parse_iso(now) or datetime.now(timezone.utc)
    threshold = (current - timedelta(hours=1)).replace(microsecond=0).isoformat()
    row = conn.execute(
        """
SELECT COUNT(*) AS count
FROM agent_recovery_attempts
WHERE agent_id = ?
  AND attempted = 1
  AND attempted_at >= ?
""".strip(),
        (agent_id, threshold),
    ).fetchone()
    return int(row["count"] if isinstance(row, sqlite3.Row) else row[0])


def _write_recovery_attempt_receipt(
    conn: sqlite3.Connection,
    *,
    agent_id: str,
    action_id: str | None,
    action_kind: str,
    command_argv: list[str],
    dry_run: bool,
    attempted: bool,
    succeeded: bool,
    exit_code: int | None,
    duration_ms: int,
    stdout: str,
    stderr: str,
    blocker: str | None,
    now: str,
) -> str:
    receipt_id = _row_id("agentrecoveryreceipt", agent_id, action_id or "none", now, attempted, succeeded, blocker or "")
    attempt_id = _row_id("agentrecoveryattempt", receipt_id)
    recovery_status = "succeeded" if attempted and succeeded else "failed" if attempted else "blocked"
    payload = {
        "agent_id": agent_id,
        "recovery_action_id": action_id,
        "dry_run": dry_run,
        "attempted": attempted,
        "succeeded": succeeded,
        "exit_code": exit_code,
        "blocker": blocker,
        "command_label": action_kind,
        "command_argv": command_argv,
        **NO_AUTHORITY_FLAGS,
    }
    conn.execute(
        """
INSERT INTO agent_recovery_attempts (
  recovery_attempt_id, receipt_id, agent_id, recovery_action_id,
  attempted_at, dry_run, attempted, succeeded, exit_code, duration_ms,
  stdout_excerpt, stderr_excerpt, blocker, command_argv_json,
  command_executed, shell_used, telegram_api_called, message_sent,
  secret_accessed, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?)
""".strip(),
        (
            attempt_id,
            receipt_id,
            agent_id,
            action_id,
            now,
            1 if dry_run else 0,
            1 if attempted else 0,
            1 if succeeded else 0,
            exit_code,
            duration_ms,
            _excerpt(stdout),
            _excerpt(stderr),
            blocker,
            stable_json(command_argv),
            1 if attempted else 0,
            now,
        ),
    )
    conn.execute(
        """
INSERT INTO agent_recovery_receipts (
  receipt_id, run_id, agent_id, recovery_status, recovery_kind,
  attempted, succeeded, summary, payload_json, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
        (
            receipt_id,
            _latest_run_id(conn) or "unknown_run",
            agent_id,
            recovery_status,
            action_kind,
            1 if attempted else 0,
            1 if succeeded else 0,
            (
                f"Recovery attempted for {agent_id}: {'succeeded' if succeeded else 'failed'}."
                if attempted
                else f"Recovery blocked for {agent_id}: {blocker}."
            ),
            stable_json(payload),
            now,
        ),
    )
    if attempted:
        conn.execute(
            """
UPDATE agent_recovery_policies
SET last_attempt_at = ?,
    next_allowed_attempt_at = ?,
    updated_at = ?
WHERE agent_id = ?
""".strip(),
            (
                now,
                ((_parse_iso(now) or datetime.now(timezone.utc)) + timedelta(seconds=900)).replace(microsecond=0).isoformat(),
                now,
                agent_id,
            ),
        )
    return receipt_id


def build_agent_recovery_status_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
    agent: str | None = None,
    refresh_presence: bool = True,
) -> dict[str, Any]:
    if refresh_presence:
        build_agent_presence_snapshot(db_path=db_path)
    presence = build_agent_presence_report(db_path=db_path, report="summary")
    items = presence.get("items", [])
    if agent:
        items = [item for item in items if item["agent_id"] == agent]
    action_by_agent = {
        action["agent_id"]: action
        for action in presence.get("recovery_actions", [])
    }
    attempts_by_agent: dict[str, list[dict[str, Any]]] = {}
    for attempt in presence.get("recent_recovery_attempts", []):
        attempts_by_agent.setdefault(attempt["agent_id"], []).append(attempt)
    rows = []
    now = utc_now()
    for item in items:
        action = action_by_agent.get(item["agent_id"])
        blocker = _recovery_blocker(agent=item, action=action, policy={
            "recovery_allowed": item["autorecovery_allowed"],
            "cooldown_seconds": action.get("cooldown_seconds", 0) if action else 0,
            "last_attempt_at": None,
        } if action else None, now=now)
        rows.append(
            {
                "agent_id": item["agent_id"],
                "display_name": item["display_name"],
                "desired_state": item["desired_state"],
                "actual_state": item["actual_state"],
                "expected_online": item["expected_online"],
                "recovery_status": item["recovery_status"],
                "recovery_allowed": item["autorecovery_allowed"],
                "safe_recovery_action_available": bool(action and action["safe_to_attempt"] and item["autorecovery_allowed"]),
                "recovery_action": action,
                "blocked_reason": blocker or item.get("blocker"),
                "last_recovery_attempt": (attempts_by_agent.get(item["agent_id"]) or [None])[0],
                "next_safe_move": item["next_safe_move"],
            }
        )
    return {
        "status": "ok",
        "report": report,
        "agent": agent,
        "items": rows,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
    }


def recover_agent(
    *,
    agent_id: str,
    db_path: str | Path | None = None,
    execute: bool = False,
    repo_root: str | Path = ROOT,
    refresh_presence: bool = True,
    refresh_after: bool = True,
    command_runner: Any | None = None,
) -> AgentRecoveryResult:
    if refresh_presence:
        build_agent_presence_snapshot(db_path=db_path, repo_root=repo_root)
    path = init_agent_presence_schema(db_path)
    now = utc_now()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        agent, action, policy = _latest_agent_and_action(conn, agent_id)
        blocker = _recovery_blocker(agent=agent, action=action, policy=policy, now=now)
        if policy and action and int(policy.get("max_attempts") or action.get("max_attempts_per_hour") or 1) > 0:
            max_attempts = int(action.get("max_attempts_per_hour") or policy.get("max_attempts") or 1)
            if _count_recent_attempts(conn, agent_id, now=now) >= max_attempts:
                blocker = blocker or "max attempts per hour prevents another recovery attempt"
        action_id = action.get("recovery_action_id") if action else None
        command_argv = list(action.get("command_argv") or []) if action else []
        if blocker:
            receipt_id = None
            if execute:
                receipt_id = _write_recovery_attempt_receipt(
                    conn,
                    agent_id=agent_id,
                    action_id=action_id,
                    action_kind=action.get("action_kind") if action else "none",
                    command_argv=command_argv,
                    dry_run=False,
                    attempted=False,
                    succeeded=False,
                    exit_code=None,
                    duration_ms=0,
                    stdout="",
                    stderr="",
                    blocker=blocker,
                    now=now,
                )
                conn.commit()
            return AgentRecoveryResult(
                agent_id=agent_id,
                status="blocked",
                dry_run=not execute,
                action_id=action_id,
                attempted=False,
                exit_code=None,
                receipt_id=receipt_id,
                blocker=blocker,
                summary=f"Recovery blocked for {agent_id}: {blocker}",
            )
        if not execute:
            return AgentRecoveryResult(
                agent_id=agent_id,
                status="dry_run_available",
                dry_run=True,
                action_id=action_id,
                attempted=False,
                exit_code=None,
                receipt_id=None,
                blocker=None,
                summary=f"Dry-run: recovery for {agent_id} would execute fixed action {action_id}.",
            )
        started = datetime.now(timezone.utc)
        runner = command_runner or subprocess.run
        completed = runner(
            command_argv,
            cwd=action.get("working_directory") or str(repo_root),
            capture_output=True,
            text=True,
            timeout=60,
            shell=False,
        )
        duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        succeeded = completed.returncode == 0
        receipt_id = _write_recovery_attempt_receipt(
            conn,
            agent_id=agent_id,
            action_id=action_id,
            action_kind=action["action_kind"],
            command_argv=command_argv,
            dry_run=False,
            attempted=True,
            succeeded=succeeded,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            blocker=None if succeeded else "recovery command returned non-zero exit code",
            now=now,
        )
        conn.commit()
    finally:
        conn.close()
    if refresh_after:
        build_agent_presence_snapshot(db_path=db_path, repo_root=repo_root)
        export_agent_presence_read_model(db_path=db_path)
    return AgentRecoveryResult(
        agent_id=agent_id,
        status="succeeded" if succeeded else "failed",
        dry_run=False,
        action_id=action_id,
        attempted=True,
        exit_code=completed.returncode,
        receipt_id=receipt_id,
        blocker=None if succeeded else "recovery command returned non-zero exit code",
        summary=f"Recovery {'succeeded' if succeeded else 'failed'} for {agent_id}.",
    )


def format_agent_recovery_status_report(payload: dict[str, Any]) -> str:
    lines = ["OpenClaw Agent Recovery Status v0", ""]
    if payload.get("agent"):
        lines.append(f"Agent: `{payload['agent']}`")
    lines.append("Items:")
    for item in payload.get("items", []):
        action = item.get("recovery_action") or {}
        lines.append(
            f"- `{item['agent_id']}` desired={item['desired_state']} actual={item['actual_state']} "
            f"recovery={item['recovery_status']} safe_action=`{str(item['safe_recovery_action_available']).lower()}`"
        )
        lines.append(f"  action: `{action.get('recovery_action_id', 'none')}` kind=`{action.get('action_kind', 'none')}`")
        lines.append(f"  blocked: {item.get('blocked_reason') or 'none'}")
        lines.append(f"  next: {item['next_safe_move']}")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Status only; no service start/restart, Telegram API call, message send, secret read, arbitrary shell, Docker/Ollama, or broad agent activation.",
        ]
    )
    return "\n".join(lines)


def format_agent_recovery_result(result: AgentRecoveryResult) -> str:
    lines = [
        "OpenClaw Agent Recovery v0",
        "",
        f"Agent: `{result.agent_id}`",
        f"Status: `{result.status}`",
        f"Dry run: `{str(result.dry_run).lower()}`",
        f"Action: `{result.action_id or 'none'}`",
        f"Attempted: `{str(result.attempted).lower()}`",
        f"Exit code: `{result.exit_code}`",
        f"Receipt: `{result.receipt_id or 'none'}`",
        f"Blocker: {result.blocker or 'none'}",
        f"Summary: {result.summary}",
        "",
        "Boundary:",
        "- Recovery runs only fixed allowlisted argv after policy allows it; no shell, no user command text, no Telegram message send, no secret inspection.",
    ]
    return "\n".join(lines)


def build_agent_presence_read_model(db_path: str | Path | None = None) -> dict[str, Any]:
    report = build_agent_presence_report(db_path=db_path, report="summary")
    items = report.get("items", [])
    by_agent = {item["agent_id"]: item for item in items}
    counts = report.get("counts", {})
    blockers = [
        {
            "agent_id": item["agent_id"],
            "blocker": item["blocker"],
            "next_safe_move": item["next_safe_move"],
        }
        for item in items
        if item.get("blocker")
    ]
    actions_by_agent: dict[str, list[dict[str, Any]]] = {}
    for action in report.get("recovery_actions", []):
        actions_by_agent.setdefault(action["agent_id"], []).append(action)
    attempts_by_agent: dict[str, list[dict[str, Any]]] = {}
    for attempt in report.get("recent_recovery_attempts", []):
        attempts_by_agent.setdefault(attempt["agent_id"], []).append(attempt)
    enriched_items: list[dict[str, Any]] = []
    for item in items:
        enriched = dict(item)
        enriched["recovery_actions"] = actions_by_agent.get(item["agent_id"], [])
        enriched["last_recovery_attempt"] = (attempts_by_agent.get(item["agent_id"]) or [None])[0]
        enriched_items.append(enriched)
    return {
        "schema_version": READ_MODEL_VERSION,
        "generated_at": utc_now(),
        "source_ledger_path": str(db_path or DEFAULT_DB_PATH),
        "agent_count": report.get("agent_count", 0),
        "expected_online_count": counts.get("expected_online", 0),
        "online_count": counts.get("online", 0),
        "offline_unexpected_count": counts.get("offline_unexpected", 0),
        "degraded_count": counts.get("degraded", 0),
        "unknown_count": counts.get("unknown", 0),
        "intentional_offline_count": counts.get("intentional_offline", 0),
        "maintenance_hard_kill_count": counts.get("maintenance_or_hard_kill", 0),
        "cassandra_presence": next((item for item in enriched_items if item["agent_id"] == "cassandra"), by_agent.get("cassandra")),
        "agents": enriched_items,
        "runtime_surfaces": report.get("runtime_surfaces", []),
        "recovery_actions": report.get("recovery_actions", []),
        "recent_recovery_attempts": report.get("recent_recovery_attempts", []),
        "recovery_available_count": counts.get("by_recovery_status", {}).get("available", 0),
        "blockers": blockers,
        "next_safe_move": (
            "Inspect unexpected offline agents and choose a bounded recovery lane."
            if counts.get("offline_unexpected", 0)
            else "No unexpected offline agent is currently represented."
        ),
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def _operator_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Agent Presence",
        "",
        f"Agents: {payload['agent_count']}",
        f"Expected online: {payload['expected_online_count']}",
        f"Online: {payload['online_count']}",
        f"Unexpected offline/degraded/unknown: {payload['offline_unexpected_count']}",
        f"Recovery available: {payload['recovery_available_count']}",
        "",
        "Cassandra:",
    ]
    cassandra = payload.get("cassandra_presence") or {}
    if cassandra:
        lines.extend(
            [
                f"- desired: `{cassandra['desired_state']}`",
                f"- actual: `{cassandra['actual_state']}`",
                f"- source: `{cassandra['presence_source']}`",
                f"- recovery: `{cassandra['recovery_status']}`",
                f"- recovery action: `{cassandra.get('recovery_action_id') or 'none'}`",
                f"- blocker: {cassandra.get('blocker') or 'none'}",
                f"- next: {cassandra['next_safe_move']}",
            ]
        )
    else:
        lines.append("- not represented")
    lines.extend(["", "Agents:"])
    for item in payload["agents"]:
        lines.append(
            f"- `{item['agent_id']}` desired={item['desired_state']} actual={item['actual_state']} "
            f"source={item['presence_source']} recovery={item['recovery_status']} "
            f"action={item.get('recovery_action_id') or 'none'}"
        )
    if payload["recovery_actions"]:
        lines.extend(["", "Recovery actions:"])
        for action in payload["recovery_actions"]:
            lines.append(
                f"- `{action['agent_id']}` `{action['recovery_action_id']}` "
                f"kind={action['action_kind']} safe_to_attempt=`{str(action['safe_to_attempt']).lower()}` "
                f"classification={action['classification']}"
            )
    if payload["recent_recovery_attempts"]:
        lines.extend(["", "Recent recovery attempts:"])
        for attempt in payload["recent_recovery_attempts"][:5]:
            lines.append(
                f"- `{attempt['agent_id']}` action={attempt.get('recovery_action_id') or 'none'} "
                f"attempted=`{str(attempt['attempted']).lower()}` succeeded=`{str(attempt['succeeded']).lower()}` "
                f"blocker={attempt.get('blocker') or 'none'}"
            )
    if payload["blockers"]:
        lines.extend(["", "Blockers:"])
        for blocker in payload["blockers"]:
            lines.append(f"- `{blocker['agent_id']}`: {blocker['blocker']} -> {blocker['next_safe_move']}")
    lines.extend(["", "No-authority posture:"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Presence is evidence/status only.",
            "- This read-model does not send Telegram messages, inspect secrets, start agents, restart services, call models, or run recovery commands.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def export_agent_presence_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    repo_root: str | Path = ROOT,
) -> dict[str, Any]:
    payload = build_agent_presence_read_model(db_path=db_path)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(_operator_markdown(payload), encoding="utf-8")
    return {
        "json_path": _display_path(json_path, repo_root=repo_root),
        "operator_path": _display_path(operator_path, repo_root=repo_root),
        "agent_count": payload["agent_count"],
        "expected_online_count": payload["expected_online_count"],
        "online_count": payload["online_count"],
        "offline_unexpected_count": payload["offline_unexpected_count"],
        "cassandra_actual_state": (payload.get("cassandra_presence") or {}).get("actual_state"),
    }


def format_agent_presence_report(payload: dict[str, Any]) -> str:
    lines = ["OpenClaw Agent Presence v0", ""]
    if payload.get("status") == "empty":
        lines.append("Status: `empty`")
        lines.append("No agent presence snapshot has been built yet.")
    elif payload.get("agent") and payload.get("items"):
        item = payload["items"][0]
        lines.extend(
            [
                f"Agent: `{item['agent_id']}` / {item['display_name']}",
                f"Desired state: `{item['desired_state']}`",
                f"Actual state: `{item['actual_state']}`",
                f"Evidence source: `{item['presence_source']}`",
                f"Runtime surface found: `{str(item['runtime_surface_found']).lower()}`",
                f"Expected online: `{str(item['expected_online']).lower()}`",
                f"Recovery allowed: `{str(item['autorecovery_allowed']).lower()}`",
                f"Recovery status: `{item['recovery_status']}`",
                f"Recovery action: `{item.get('recovery_action_id') or 'none'}`",
                f"Blocker: {item.get('blocker') or 'none'}",
                f"Next safe move: {item['next_safe_move']}",
            ]
        )
    else:
        counts = payload.get("counts", {})
        lines.extend(
            [
                f"Report: `{payload.get('report')}`",
                f"Agents: {payload.get('agent_count', 0)}",
                f"Expected online: {counts.get('expected_online', 0)}",
                f"Online: {counts.get('online', 0)}",
                f"Unexpected offline/degraded/unknown: {counts.get('offline_unexpected', 0)}",
                "",
                "Items:",
            ]
        )
        for item in payload.get("items", []):
            lines.append(
                f"- `{item['agent_id']}` desired={item['desired_state']} actual={item['actual_state']} "
                f"recovery={item['recovery_status']} action={item.get('recovery_action_id') or 'none'} "
                f"next={item['next_safe_move']}"
            )
    lines.extend(
        [
            "",
            "Boundary:",
            "- No Telegram API call, message send, secret read, arbitrary shell, service restart, model call, Docker/Ollama, or client deployment authority.",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "AGENT_CONFIGS",
    "NO_AUTHORITY_FLAGS",
    "build_agent_presence_read_model",
    "build_agent_presence_report",
    "build_agent_presence_snapshot",
    "build_agent_recovery_status_report",
    "export_agent_presence_read_model",
    "format_agent_recovery_result",
    "format_agent_recovery_status_report",
    "format_agent_presence_report",
    "init_agent_presence_schema",
    "recover_agent",
    "seed_recovery_actions",
    "seed_desired_states",
    "agent_presence_table_names",
]
