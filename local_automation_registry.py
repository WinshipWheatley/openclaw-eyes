"""Local Automation Services v0 registry for OpenClaw.

This registry records local maintenance automation tasks in the Business Ops
ledger. It is metadata/control-plane state only: it does not run arbitrary
commands, grant runtime authority, or install services by itself.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger


LOCAL_AUTOMATION_VERSION = "local_automation_services_v0"

MACHINES = {"mac", "pc_wsl"}
COMMAND_KINDS = {"allowlisted_python_script"}
AUTHORITY_SCOPES = {"local_maintenance_only"}
TASK_STATUSES = {"available_planning", "installable", "installed", "disabled"}

NO_AUTHORITY_FLAGS = {
    "arbitrary_command_allowed": False,
    "remote_control_allowed": False,
    "runtime_authority": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "model_execution_allowed": False,
    "container_execution_allowed": False,
    "docker_allowed": False,
    "ollama_allowed": False,
    "network_authority": False,
    "mission_control_modified": False,
    "generated_contracts_modified": False,
    "file_delete_allowed": False,
    "file_move_allowed": False,
}


@dataclass(frozen=True)
class AutomationTaskSeed:
    task_id: str
    display_name: str
    machine: str
    command_kind: str
    script_path: str
    arguments: tuple[str, ...]
    trigger_kind: str
    authority_scope: str
    status: str
    enabled_by_default: bool
    interval_seconds: int
    service_kind: str
    service_name: str
    service_template_path: str | None
    install_target_path: str | None
    log_path: str
    state_path: str
    notes: str


@dataclass(frozen=True)
class LocalAutomationBuildResult:
    run_id: str
    db_path: str
    task_count: int
    service_spec_count: int


DEFAULT_TASK_SEEDS: tuple[AutomationTaskSeed, ...] = (
    AutomationTaskSeed(
        task_id="read_model_mirror_mac_sync",
        display_name="Read-Model Mirror Mac Sync",
        machine="mac",
        command_kind="allowlisted_python_script",
        script_path="scripts/mac_read_model_sync_agent.py",
        arguments=(),
        trigger_kind="launchd_interval_marker_check",
        authority_scope="local_maintenance_only",
        status="installable",
        enabled_by_default=False,
        interval_seconds=300,
        service_kind="launchagent",
        service_name="com.openclaw.read-model-sync",
        service_template_path="launchd/com.openclaw.read-model-sync.plist",
        install_target_path="~/Library/LaunchAgents/com.openclaw.read-model-sync.plist",
        log_path="~/Library/Logs/OpenClaw/read_model_sync_agent.log",
        state_path="/Volumes/openclaw_e/shuttle/from_mac/read_model_sync_completed.json",
        notes="Local Mac half only; watches the shared marker and runs the existing generated read-model sync agent.",
    ),
    AutomationTaskSeed(
        task_id="read_model_mirror_pc_import",
        display_name="Read-Model Mirror PC Import",
        machine="pc_wsl",
        command_kind="allowlisted_python_script",
        script_path="scripts/pc_read_model_import_agent.py",
        arguments=("--once", "--format", "operator"),
        trigger_kind="systemd_user_timer_or_manual_loop",
        authority_scope="local_maintenance_only",
        status="installable",
        enabled_by_default=False,
        interval_seconds=300,
        service_kind="systemd_user_timer",
        service_name="openclaw-read-model-import",
        service_template_path="systemd/user/openclaw-read-model-import.service.in",
        install_target_path="~/.config/systemd/user/openclaw-read-model-import.service",
        log_path=".openclaw/logs/read_model_import_agent.log",
        state_path=".openclaw/state/read_model_import_agent_state.json",
        notes="Local PC/WSL half only; imports the returned Mac manifest when its hash changes.",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS local_automation_runs (
  run_id TEXT PRIMARY KEY,
  registry_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  task_count INTEGER NOT NULL DEFAULT 0,
  service_spec_count INTEGER NOT NULL DEFAULT 0,
  source_basis_json TEXT NOT NULL,
  arbitrary_command_allowed INTEGER NOT NULL DEFAULT 0,
  remote_control_allowed INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  model_execution_allowed INTEGER NOT NULL DEFAULT 0,
  container_execution_allowed INTEGER NOT NULL DEFAULT 0,
  docker_allowed INTEGER NOT NULL DEFAULT 0,
  ollama_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  notes TEXT
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS local_automation_tasks (
  task_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  machine TEXT NOT NULL,
  command_kind TEXT NOT NULL,
  script_path TEXT NOT NULL,
  arguments_json TEXT NOT NULL,
  trigger_kind TEXT NOT NULL,
  authority_scope TEXT NOT NULL,
  status TEXT NOT NULL,
  enabled_by_default INTEGER NOT NULL DEFAULT 0,
  installed INTEGER NOT NULL DEFAULT 0,
  running INTEGER NOT NULL DEFAULT 0,
  can_run_tools INTEGER NOT NULL DEFAULT 0,
  can_execute_arbitrary_shell INTEGER NOT NULL DEFAULT 0,
  can_call_network INTEGER NOT NULL DEFAULT 0,
  can_run_docker INTEGER NOT NULL DEFAULT 0,
  can_run_ollama INTEGER NOT NULL DEFAULT 0,
  can_activate_runtime INTEGER NOT NULL DEFAULT 0,
  can_activate_agents INTEGER NOT NULL DEFAULT 0,
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  run_id TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES local_automation_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS local_automation_service_specs (
  spec_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  service_kind TEXT NOT NULL,
  service_name TEXT NOT NULL,
  service_template_path TEXT,
  install_target_path TEXT,
  log_path TEXT NOT NULL,
  state_path TEXT NOT NULL,
  interval_seconds INTEGER NOT NULL,
  install_supported INTEGER NOT NULL DEFAULT 1,
  start_supported INTEGER NOT NULL DEFAULT 1,
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (task_id) REFERENCES local_automation_tasks(task_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS local_automation_service_status (
  status_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  machine TEXT NOT NULL,
  installed_state TEXT NOT NULL,
  running_state TEXT NOT NULL,
  scheduler_available INTEGER NOT NULL DEFAULT 0,
  share_available INTEGER NOT NULL DEFAULT 0,
  checked_at TEXT NOT NULL,
  details_json TEXT NOT NULL,
  FOREIGN KEY (task_id) REFERENCES local_automation_tasks(task_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS local_automation_receipts (
  receipt_id TEXT PRIMARY KEY,
  run_id TEXT,
  task_id TEXT,
  receipt_kind TEXT NOT NULL,
  status TEXT NOT NULL,
  summary TEXT NOT NULL,
  details_json TEXT NOT NULL,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS local_automation_rejections (
  rejection_id TEXT PRIMARY KEY,
  task_id TEXT,
  attempted_operation TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_local_automation_tasks_machine ON local_automation_tasks(machine)",
        "CREATE INDEX IF NOT EXISTS idx_local_automation_tasks_status ON local_automation_tasks(status)",
        "CREATE INDEX IF NOT EXISTS idx_local_automation_status_task ON local_automation_service_status(task_id)",
    )


def init_local_automation_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    parent = Path(path).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def _validate_seed(seed: AutomationTaskSeed) -> None:
    if seed.machine not in MACHINES:
        raise ValueError(f"bad machine for {seed.task_id}: {seed.machine}")
    if seed.command_kind not in COMMAND_KINDS:
        raise ValueError(f"bad command kind for {seed.task_id}: {seed.command_kind}")
    if seed.authority_scope not in AUTHORITY_SCOPES:
        raise ValueError(f"bad authority scope for {seed.task_id}: {seed.authority_scope}")
    if seed.status not in TASK_STATUSES:
        raise ValueError(f"bad status for {seed.task_id}: {seed.status}")
    if seed.interval_seconds < 60:
        raise ValueError(f"interval too short for {seed.task_id}: {seed.interval_seconds}")


def seed_local_automation_registry(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
    task_seeds: Iterable[AutomationTaskSeed] = DEFAULT_TASK_SEEDS,
) -> LocalAutomationBuildResult:
    path = init_local_automation_schema(db_path)
    seeds = tuple(task_seeds)
    for seed in seeds:
        _validate_seed(seed)
    now = utc_now()
    resolved_run_id = run_id or _row_id("local_auto_run", now, len(seeds))
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
INSERT OR REPLACE INTO local_automation_runs (
  run_id, registry_version, created_at, completed_at, task_count,
  service_spec_count, source_basis_json, arbitrary_command_allowed,
  remote_control_allowed, runtime_authority, agent_activation_allowed,
  tool_execution_allowed, model_execution_allowed, container_execution_allowed,
  docker_allowed, ollama_allowed, network_authority, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?)
""".strip(),
            (
                resolved_run_id,
                LOCAL_AUTOMATION_VERSION,
                now,
                now,
                len(seeds),
                len(seeds),
                stable_json({"source": "operator_seeded_local_maintenance_tasks_v0"}),
                "Registry only; install/start requires explicit service-manager command.",
            ),
        )
        for seed in seeds:
            conn.execute(
                """
INSERT INTO local_automation_tasks (
  task_id, display_name, machine, command_kind, script_path, arguments_json,
  trigger_kind, authority_scope, status, enabled_by_default, installed, running,
  can_run_tools, can_execute_arbitrary_shell, can_call_network, can_run_docker,
  can_run_ollama, can_activate_runtime, can_activate_agents, notes,
  created_at, updated_at, run_id
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?, ?, ?, ?)
ON CONFLICT(task_id) DO UPDATE SET
  display_name = excluded.display_name,
  machine = excluded.machine,
  command_kind = excluded.command_kind,
  script_path = excluded.script_path,
  arguments_json = excluded.arguments_json,
  trigger_kind = excluded.trigger_kind,
  authority_scope = excluded.authority_scope,
  status = excluded.status,
  enabled_by_default = excluded.enabled_by_default,
  can_run_tools = 0,
  can_execute_arbitrary_shell = 0,
  can_call_network = 0,
  can_run_docker = 0,
  can_run_ollama = 0,
  can_activate_runtime = 0,
  can_activate_agents = 0,
  notes = excluded.notes,
  updated_at = excluded.updated_at,
  run_id = excluded.run_id
""".strip(),
                (
                    seed.task_id,
                    seed.display_name,
                    seed.machine,
                    seed.command_kind,
                    seed.script_path,
                    stable_json(list(seed.arguments)),
                    seed.trigger_kind,
                    seed.authority_scope,
                    seed.status,
                    int(seed.enabled_by_default),
                    seed.notes,
                    now,
                    now,
                    resolved_run_id,
                ),
            )
            conn.execute(
                """
INSERT OR REPLACE INTO local_automation_service_specs (
  spec_id, task_id, service_kind, service_name, service_template_path,
  install_target_path, log_path, state_path, interval_seconds,
  install_supported, start_supported, notes, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
""".strip(),
                (
                    _row_id("local_auto_spec", seed.task_id, seed.service_name),
                    seed.task_id,
                    seed.service_kind,
                    seed.service_name,
                    seed.service_template_path,
                    seed.install_target_path,
                    seed.log_path,
                    seed.state_path,
                    seed.interval_seconds,
                    seed.notes,
                    now,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return LocalAutomationBuildResult(
        run_id=resolved_run_id,
        db_path=path,
        task_count=len(seeds),
        service_spec_count=len(seeds),
    )


def local_automation_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_local_automation_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'local_automation_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def record_service_status(
    *,
    db_path: str | Path | None = None,
    task_id: str,
    machine: str,
    installed_state: str,
    running_state: str,
    scheduler_available: bool,
    share_available: bool,
    details: dict[str, Any],
) -> str:
    path = init_local_automation_schema(db_path)
    now = utc_now()
    status_id = _row_id("local_auto_status", task_id, machine, now, uuid.uuid4().hex)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
INSERT INTO local_automation_service_status (
  status_id, task_id, machine, installed_state, running_state,
  scheduler_available, share_available, checked_at, details_json
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
            (
                status_id,
                task_id,
                machine,
                installed_state,
                running_state,
                int(scheduler_available),
                int(share_available),
                now,
                stable_json(details),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return status_id


def build_local_automation_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
    task_id: str | None = None,
) -> dict[str, Any]:
    path = init_local_automation_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        tasks = [dict(row) for row in conn.execute("SELECT * FROM local_automation_tasks ORDER BY task_id")]
        specs = [
            dict(row)
            for row in conn.execute("SELECT * FROM local_automation_service_specs ORDER BY task_id")
        ]
        status_rows = [
            dict(row)
            for row in conn.execute(
                """
SELECT *
FROM local_automation_service_status
ORDER BY checked_at DESC
LIMIT 20
""".strip()
            )
        ]
    finally:
        conn.close()
    if task_id:
        tasks = [item for item in tasks if item["task_id"] == task_id]
        specs = [item for item in specs if item["task_id"] == task_id]
    machine_counts = Counter(item["machine"] for item in tasks)
    status_counts = Counter(item["status"] for item in tasks)
    payload = {
        "schema_version": LOCAL_AUTOMATION_VERSION,
        "source_ledger_path": str(path),
        "report": report,
        "task_count": len(tasks),
        "service_spec_count": len(specs),
        "counts_by_machine": dict(sorted(machine_counts.items())),
        "counts_by_status": dict(sorted(status_counts.items())),
        "tasks": tasks,
        "service_specs": specs,
        "recent_service_status": status_rows,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        "future_task_kinds_supported_by_contract": [
            "report_bridge_import_once",
            "file_event_snapshot_once",
            "markdown_atlas_refresh",
            "dropped_intent_refresh",
            "context_selection_export",
        ],
    }
    if report == "tasks":
        payload["items"] = tasks
    elif report == "services":
        payload["items"] = specs
    elif report == "status":
        payload["items"] = status_rows
    else:
        payload["items"] = tasks
    return payload


def format_local_automation_report(payload: dict[str, Any]) -> str:
    lines = [
        "OpenClaw Local Automation Services v0",
        "",
        f"Report: `{payload['report']}`",
        f"Ledger: `{payload['source_ledger_path']}`",
        f"Tasks: {payload['task_count']}",
        f"Service specs: {payload['service_spec_count']}",
        f"By machine: {payload['counts_by_machine']}",
        f"By status: {payload['counts_by_status']}",
        "",
        "Tasks:",
    ]
    if not payload.get("tasks"):
        lines.append("- none")
    else:
        for item in payload["tasks"]:
            args = ", ".join(json.loads(item["arguments_json"]))
            lines.append(
                f"- `{item['task_id']}` ({item['machine']}): {item['script_path']} {args}".rstrip()
            )
    if payload["report"] == "services":
        lines.extend(["", "Service Specs:"])
        if not payload.get("service_specs"):
            lines.append("- none")
        else:
            for item in payload["service_specs"]:
                lines.append(
                    f"- `{item['task_id']}`: {item['service_kind']} `{item['service_name']}` every {item['interval_seconds']}s"
                )
    if payload["report"] == "status":
        lines.extend(["", "Recent Status Rows:"])
        if not payload.get("recent_service_status"):
            lines.append("- none")
        else:
            for item in payload["recent_service_status"]:
                lines.append(
                    f"- `{item['task_id']}` on {item['machine']}: installed={item['installed_state']}, running={item['running_state']}"
                )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Registry state only. No arbitrary command, remote control, runtime, agent, tool, Docker, Ollama, Mission Control, or generated-contract authority is granted.",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "DEFAULT_TASK_SEEDS",
    "LOCAL_AUTOMATION_VERSION",
    "NO_AUTHORITY_FLAGS",
    "build_local_automation_report",
    "format_local_automation_report",
    "init_local_automation_schema",
    "local_automation_table_names",
    "record_service_status",
    "seed_local_automation_registry",
    "stable_json",
]
