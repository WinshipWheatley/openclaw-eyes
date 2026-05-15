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
from datetime import datetime, timezone
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
       OR name IN ('agent_desired_states', 'agent_recovery_policies', 'agent_recovery_receipts'))
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
    policy_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    override = (policy_overrides or {}).get(config.agent_id, {})
    known_kind = "none"
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
    elif known_kind != "none":
        recovery_status = "blocked"
        reason = "A candidate recovery path exists, but autorecovery is not enabled in v0."
    else:
        recovery_status = "blocked"
        reason = "No known safe recovery path exists."
    recovery_allowed = bool(override.get("recovery_allowed", False))
    if desired_state in {"hard_kill", "offline_intentional", "maintenance"}:
        recovery_allowed = False
    if recovery_allowed and recovery_status == "blocked" and actual_state in {"offline", "degraded"}:
        recovery_status = "available"
        reason = "Recovery is policy-allowed, but this lane still records metadata only unless explicitly invoked."
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
) -> AgentPresenceBuildResult:
    path = init_agent_presence_schema(db_path)
    seed_agent_lane_registry(db_path=path)
    seed_desired_states(db_path=path, desired_state_overrides=desired_state_overrides)
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
            policy = _policy_for_agent(
                config=config,
                desired_state=desired_state,
                actual_state=actual["actual_state"],
                surface_states=surface_states,
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
                "recovery_action_id": policy["recovery_command_id"],
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
                    policy["recovery_command_id"],
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
                    policy["recovery_command_id"],
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
SELECT run_id
FROM agent_presence_runs
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
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


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
        "cassandra_presence": by_agent.get("cassandra"),
        "agents": items,
        "runtime_surfaces": report.get("runtime_surfaces", []),
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
            f"source={item['presence_source']} recovery={item['recovery_status']}"
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
                f"recovery={item['recovery_status']} next={item['next_safe_move']}"
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
    "export_agent_presence_read_model",
    "format_agent_presence_report",
    "init_agent_presence_schema",
    "seed_desired_states",
    "agent_presence_table_names",
]
