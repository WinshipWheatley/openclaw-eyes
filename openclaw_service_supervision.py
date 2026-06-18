"""OpenClaw service supervision read-model v0.

This module observes user systemd unit state and writes deterministic
supervision read models. It does not start, restart, or enable services; the
keeper script owns bounded allowlisted starts.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_SYSTEM_KNOWLEDGE_ROOT = Path("generated/system_knowledge")

SCHEMA_VERSION = "openclaw_service_supervision_v0"
READ_MODEL_VERSION = "openclaw_service_supervision_read_model_v0"
JSON_EXPORT_NAME = "openclaw_service_supervision.json"
OPERATOR_EXPORT_NAME = "openclaw_service_supervision_OPERATOR.md"
SQLITE_EXPORT_NAME = "openclaw_service_supervision.sqlite"
SCHEMA_EXPORT_NAME = "openclaw_service_supervision_SCHEMA.sql"
SEED_EXPORT_NAME = "openclaw_service_supervision_SEED.sql"

KEEPER_STATUS_JSON_NAME = "openclaw_service_keeper_status.json"

REQUIRED_SQLITE_TABLES = (
    "supervision_run",
    "supervised_unit",
    "supervision_risk",
    "recommended_operator_action",
    "keeper_status",
)

NO_AUTHORITY_FLAGS = {
    "metadata_only": True,
    "read_model_only": True,
    "sqlite_registry_only": True,
    "systemd_read_only": True,
    "services_started": False,
    "services_restarted": False,
    "timers_enabled_or_started": False,
    "chief_launched": False,
    "lm_called": False,
    "email_accessed": False,
    "gmail_accessed": False,
    "browser_accessed": False,
    "coupa_accessed": False,
    "workbook_cells_read": False,
    "pdf_generated_or_exported": False,
    "ledger_mutated": False,
    "production_state_mutated": False,
}


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


CommandRunner = Callable[[list[str]], CommandResult]


@dataclass(frozen=True)
class SupervisedUnitSpec:
    unit_name: str
    unit_kind: str
    expected_active_states: tuple[str, ...]
    expected_sub_states: tuple[str, ...]
    enabled_required: bool
    missing_allowed: bool
    expected_behavior: str
    allowed_supervision_action: str


@dataclass(frozen=True)
class ServiceSupervisionExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    sqlite_path: str
    schema_sql_path: str
    seed_sql_path: str
    supervised_unit_count: int
    ready_unit_count: int
    risk_count: int
    startup_readiness: str


DEFAULT_SUPERVISED_UNITS = (
    SupervisedUnitSpec(
        unit_name="openclaw-request-response.service",
        unit_kind="SERVICE",
        expected_active_states=("active",),
        expected_sub_states=("running",),
        enabled_required=True,
        missing_allowed=False,
        expected_behavior="Long-running request/response bridge process.",
        allowed_supervision_action="START_IF_INACTIVE_ALLOWLISTED",
    ),
    SupervisedUnitSpec(
        unit_name="openclaw-change-sentinel.timer",
        unit_kind="TIMER",
        expected_active_states=("active",),
        expected_sub_states=("waiting",),
        enabled_required=True,
        missing_allowed=False,
        expected_behavior="Runs deterministic change sentinel every 20 minutes.",
        allowed_supervision_action="START_IF_INACTIVE_ALLOWLISTED",
    ),
    SupervisedUnitSpec(
        unit_name="openclaw-change-sentinel.service",
        unit_kind="SERVICE",
        expected_active_states=("inactive", "active"),
        expected_sub_states=("dead", "running", "exited"),
        enabled_required=False,
        missing_allowed=False,
        expected_behavior="Oneshot service triggered by openclaw-change-sentinel.timer.",
        allowed_supervision_action="OBSERVE_ONLY_TIMER_OWNED",
    ),
    SupervisedUnitSpec(
        unit_name="openclaw-service-keeper.timer",
        unit_kind="TIMER",
        expected_active_states=("active",),
        expected_sub_states=("waiting",),
        enabled_required=True,
        missing_allowed=True,
        expected_behavior="Runs the allowlisted service keeper every 5 minutes.",
        allowed_supervision_action="INSTALL_ENABLE_TIMER_IF_APPROVED",
    ),
    SupervisedUnitSpec(
        unit_name="openclaw-service-keeper.service",
        unit_kind="SERVICE",
        expected_active_states=("inactive", "active"),
        expected_sub_states=("dead", "running", "exited"),
        enabled_required=False,
        missing_allowed=True,
        expected_behavior="Oneshot allowlisted service keeper triggered by timer.",
        allowed_supervision_action="OBSERVE_ONLY_TIMER_OWNED",
    ),
    SupervisedUnitSpec(
        unit_name="openclaw-sleep-resilience.service",
        unit_kind="SERVICE",
        expected_active_states=("active",),
        expected_sub_states=("running",),
        enabled_required=True,
        missing_allowed=True,
        expected_behavior=(
            "Keeps the host awake while recent fleet work is visible and records "
            "resume-gap recovery receipts."
        ),
        allowed_supervision_action="INSTALL_ENABLE_IF_APPROVED",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path, *, root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _bool(value: bool) -> int:
    return 1 if value else 0


def _run_command(args: list[str], *, timeout_seconds: int = 8) -> CommandResult:
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        return CommandResult(127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return CommandResult(124, stdout, stderr or "command timed out")
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _parse_key_values(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def _read_unit_file_settings(fragment_path: str) -> dict[str, str]:
    if not fragment_path:
        return {}
    path = Path(fragment_path)
    if not path.is_file():
        return {}
    settings: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("["):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key in {
            "ExecStart",
            "OnBootSec",
            "OnUnitActiveSec",
            "Persistent",
            "Restart",
            "RestartSec",
            "StandardOutput",
            "StandardError",
            "Unit",
            "WantedBy",
            "WorkingDirectory",
        }:
            settings[key] = value
    return settings


def _journal_excerpt(unit_name: str, *, runner: CommandRunner | None) -> str:
    command = ["journalctl", "--user", "-u", unit_name, "-n", "12", "--no-pager"]
    result = (runner or _run_command)(command)
    if result.returncode != 0:
        return (result.stderr or "journal unavailable").strip()
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return "No recent journal lines."
    return " | ".join(lines[-3:])


def _systemctl_available(runner: CommandRunner | None) -> bool:
    if runner is not None:
        return True
    return shutil.which("systemctl") is not None


def read_linger_status(
    *, user_name: str = "openclaw", runner: CommandRunner | None = None
) -> dict[str, str]:
    command = ["loginctl", "show-user", user_name, "-p", "Linger"]
    if runner is None and shutil.which("loginctl") is None:
        return {
            "user": user_name,
            "linger": "UNKNOWN",
            "status": "UNKNOWN",
            "error": "loginctl unavailable",
        }
    result = (runner or _run_command)(command)
    values = _parse_key_values(result.stdout)
    linger = values.get("Linger", "UNKNOWN")
    return {
        "user": user_name,
        "linger": linger,
        "status": "READY" if linger == "yes" else ("RISK_LINGER_DISABLED" if linger == "no" else "UNKNOWN"),
        "error": "" if result.returncode == 0 else (result.stderr.strip() or "loginctl query failed"),
    }


def _unit_startup_readiness(
    spec: SupervisedUnitSpec, values: dict[str, str], enabled_status: str, systemd_available: bool
) -> tuple[str, str]:
    if not systemd_available:
        return "SYSTEMD_UNAVAILABLE", "systemctl is not available."
    load_state = values.get("LoadState", "")
    active_state = values.get("ActiveState", "")
    sub_state = values.get("SubState", "")
    if load_state in {"not-found", "masked"} or (not values.get("FragmentPath") and load_state != "loaded"):
        if spec.missing_allowed:
            return "MISSING_ALLOWED", "Unit is not installed yet."
        return "UNIT_MISSING", "Required unit is missing."
    if spec.enabled_required and enabled_status != "enabled":
        return "NOT_READY", "Unit is not enabled."
    if active_state not in spec.expected_active_states:
        return "NOT_READY", f"Expected ActiveState in {spec.expected_active_states}, got {active_state or 'unknown'}."
    if spec.expected_sub_states and sub_state not in spec.expected_sub_states:
        return "NOT_READY", f"Expected SubState in {spec.expected_sub_states}, got {sub_state or 'unknown'}."
    return "READY", "Unit matches expected supervision state."


def _unit_enabled_status(unit_name: str, *, runner: CommandRunner | None) -> str:
    result = (runner or _run_command)(["systemctl", "--user", "is-enabled", unit_name])
    if result.stdout.strip():
        return result.stdout.strip().splitlines()[0]
    if result.stderr.strip():
        return result.stderr.strip().splitlines()[0]
    return "unknown"


def _read_systemd_unit(spec: SupervisedUnitSpec, *, runner: CommandRunner | None = None) -> dict[str, Any]:
    if not _systemctl_available(runner):
        ready, reason = _unit_startup_readiness(spec, {}, "unknown", False)
        return {
            "unit_name": spec.unit_name,
            "unit_kind": spec.unit_kind,
            "systemd_available": False,
            "load_state": "",
            "active_state": "",
            "sub_state": "",
            "unit_file_state": "",
            "enabled_status": "unknown",
            "enabled": False,
            "active": False,
            "unit_path": "",
            "last_start_time": "",
            "restart_count": "",
            "exec_main_status": "",
            "result": "",
            "timer_settings": {},
            "log_excerpt_summary": "systemctl unavailable",
            "expected_behavior": spec.expected_behavior,
            "startup_readiness": ready,
            "readiness_reason": reason,
            "allowed_supervision_action": spec.allowed_supervision_action,
            "recommended_operator_action": "Inspect systemd availability for this environment.",
        }

    properties = (
        "Id,LoadState,ActiveState,SubState,UnitFileState,FragmentPath,NRestarts,"
        "ExecMainStatus,ExecMainCode,Result,ActiveEnterTimestamp,"
        "ExecMainStartTimestamp,ExecMainExitTimestamp,NextElapseUSecRealtime,"
        "LastTriggerUSecRealtime"
    )
    result = (runner or _run_command)(
        [
            "systemctl",
            "--user",
            "show",
            spec.unit_name,
            f"--property={properties}",
            "--no-pager",
        ]
    )
    values = _parse_key_values(result.stdout)
    if result.returncode != 0 and not values:
        values = {"LoadState": "not-found", "ActiveState": "inactive", "SubState": "dead"}
    enabled_status = _unit_enabled_status(spec.unit_name, runner=runner)
    if enabled_status == "unknown":
        enabled_status = values.get("UnitFileState", "unknown")
    startup_readiness, readiness_reason = _unit_startup_readiness(
        spec, values, enabled_status, True
    )
    settings = _read_unit_file_settings(values.get("FragmentPath", ""))
    recommended = _recommended_operator_action(spec, startup_readiness, readiness_reason)
    return {
        "unit_name": spec.unit_name,
        "unit_kind": spec.unit_kind,
        "systemd_available": True,
        "load_state": values.get("LoadState", ""),
        "active_state": values.get("ActiveState", ""),
        "sub_state": values.get("SubState", ""),
        "unit_file_state": values.get("UnitFileState", ""),
        "enabled_status": enabled_status,
        "enabled": enabled_status == "enabled",
        "active": values.get("ActiveState") == "active",
        "unit_path": values.get("FragmentPath", ""),
        "last_start_time": values.get("ExecMainStartTimestamp")
        or values.get("ActiveEnterTimestamp", ""),
        "restart_count": values.get("NRestarts", ""),
        "exec_main_status": values.get("ExecMainStatus", ""),
        "exec_main_code": values.get("ExecMainCode", ""),
        "result": values.get("Result", ""),
        "next_elapse": values.get("NextElapseUSecRealtime", ""),
        "last_trigger": values.get("LastTriggerUSecRealtime", ""),
        "timer_settings": settings,
        "log_excerpt_summary": _journal_excerpt(spec.unit_name, runner=runner),
        "expected_behavior": spec.expected_behavior,
        "startup_readiness": startup_readiness,
        "readiness_reason": readiness_reason,
        "allowed_supervision_action": spec.allowed_supervision_action,
        "recommended_operator_action": recommended,
    }


def _recommended_operator_action(
    spec: SupervisedUnitSpec, startup_readiness: str, reason: str
) -> str:
    if startup_readiness == "READY":
        return "No operator action required."
    if startup_readiness == "MISSING_ALLOWED":
        return "Install and enable this unit if this supervision component is expected here."
    if spec.allowed_supervision_action == "START_IF_INACTIVE_ALLOWLISTED":
        return f"Allowlisted keeper may start {spec.unit_name} if it is inactive."
    if startup_readiness == "UNIT_MISSING":
        return f"Install required unit {spec.unit_name}."
    return reason


def collect_supervised_units(
    *,
    specs: tuple[SupervisedUnitSpec, ...] = DEFAULT_SUPERVISED_UNITS,
    runner: CommandRunner | None = None,
) -> list[dict[str, Any]]:
    return [_read_systemd_unit(spec, runner=runner) for spec in specs]


def _load_keeper_status(read_model_root: str | Path) -> dict[str, Any]:
    path = _rooted(read_model_root) / KEEPER_STATUS_JSON_NAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "status_path": _display_path(path),
            "last_action_status": "MISSING",
            "action_count": 0,
            "status": "MISSING",
        }
    if not isinstance(payload, dict):
        return {
            "status_path": _display_path(path),
            "last_action_status": "UNKNOWN",
            "action_count": 0,
            "status": "UNKNOWN",
        }
    actions = payload.get("unit_results", [])
    if not isinstance(actions, list):
        actions = []
    statuses = [str(item.get("status", "")) for item in actions if isinstance(item, dict)]
    last_action = next((status for status in statuses if status != "NO_ACTION_REQUIRED"), "NO_ACTION_REQUIRED")
    return {
        "status_path": _display_path(path),
        "last_action_status": payload.get("run_status", last_action),
        "action_count": payload.get("action_count", 0),
        "status": "PRESENT",
        "observed_json": stable_json(payload).strip(),
    }


def _row_by_unit(unit_rows: list[dict[str, Any]], unit_name: str) -> dict[str, Any]:
    for row in unit_rows:
        if row.get("unit_name") == unit_name:
            return row
    return {}


def _reboot_persistence_status(
    *, unit_rows: list[dict[str, Any]], linger: dict[str, str]
) -> tuple[str, str]:
    if linger.get("linger") == "no":
        return "RISK_LINGER_DISABLED", "User lingering is disabled; user units may not persist after reboot."
    if linger.get("linger") not in {"yes"}:
        return "UNKNOWN", linger.get("error") or "Linger state is unknown."
    required_units = [
        _row_by_unit(unit_rows, "openclaw-request-response.service"),
        _row_by_unit(unit_rows, "openclaw-change-sentinel.timer"),
    ]
    missing = [row.get("unit_name", "unknown") for row in required_units if not row.get("enabled")]
    if missing:
        return "PARTIAL", "Required boot units are not enabled: " + ", ".join(missing)
    return "READY", "Linger is enabled and required user units are enabled."


def _risk_rows(unit_rows: list[dict[str, Any]], generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in unit_rows:
        readiness = row.get("startup_readiness", "UNKNOWN")
        if readiness in {"READY", "MISSING_ALLOWED"}:
            continue
        rows.append(
            {
                "risk_ref": f"risk:{row['unit_name']}",
                "unit_name": row["unit_name"],
                "severity": "HIGH" if readiness in {"UNIT_MISSING", "SYSTEMD_UNAVAILABLE"} else "MEDIUM",
                "status": readiness,
                "operator_summary": row.get("readiness_reason", ""),
                "detected_at": generated_at,
            }
        )
    return rows


def _action_rows(risk_rows: list[dict[str, Any]], unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_unit = {row["unit_name"]: row for row in unit_rows}
    rows: list[dict[str, Any]] = []
    for risk in risk_rows:
        unit = by_unit.get(risk["unit_name"], {})
        rows.append(
            {
                "action_ref": f"action:{risk['unit_name']}",
                "unit_name": risk["unit_name"],
                "action_title": "Review service supervision risk",
                "reason": risk["operator_summary"],
                "recommended_command": "systemctl --user status " + risk["unit_name"] + " --no-pager",
                "allowed_supervision_action": unit.get("allowed_supervision_action", ""),
                "forbidden_actions_json": stable_json(
                    [
                        "Do not launch Chief.",
                        "Do not call an LM.",
                        "Do not access email, Gmail, browser, Coupa, workbook, PDF, ledger, or production systems.",
                        "Do not restart active services.",
                    ]
                ).strip(),
            }
        )
    return rows


def build_openclaw_service_supervision(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
    unit_rows: list[dict[str, Any]] | None = None,
    linger_status: dict[str, str] | None = None,
    runner: CommandRunner | None = None,
    include_systemd: bool = True,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    rows = unit_rows if unit_rows is not None else (
        collect_supervised_units(runner=runner) if include_systemd else []
    )
    linger = linger_status if linger_status is not None else read_linger_status(runner=runner)
    keeper = _load_keeper_status(read_model_root)
    boot_status, boot_reason = _reboot_persistence_status(unit_rows=rows, linger=linger)
    risks = _risk_rows(rows, generated)
    actions = _action_rows(risks, rows)
    ready_count = sum(1 for row in rows if row.get("startup_readiness") == "READY")
    startup_readiness = "READY" if not risks else "ACTION_REQUIRED"
    request_response = _row_by_unit(rows, "openclaw-request-response.service")
    sentinel_timer = _row_by_unit(rows, "openclaw-change-sentinel.timer")
    keeper_timer = _row_by_unit(rows, "openclaw-service-keeper.timer")
    return {
        "schema_version": READ_MODEL_VERSION,
        "contract_schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated,
        "purpose": "Observe OpenClaw core user service supervision state without starting services.",
        "required_sqlite_tables": list(REQUIRED_SQLITE_TABLES),
        "startup_readiness": startup_readiness,
        "boot_persistence_state": boot_status,
        "boot_persistence_reason": boot_reason,
        "linger_status": linger,
        "supervised_unit_count": len(rows),
        "ready_unit_count": ready_count,
        "risk_count": len(risks),
        "core_monitor_status": {
            "request_response_active": request_response.get("active_state") == "active",
            "request_response_sub_state": request_response.get("sub_state", ""),
            "sentinel_timer_active": sentinel_timer.get("active_state") == "active",
            "sentinel_timer_sub_state": sentinel_timer.get("sub_state", ""),
            "service_keeper_timer_active": keeper_timer.get("active_state") == "active",
            "service_keeper_timer_sub_state": keeper_timer.get("sub_state", ""),
            "last_keeper_action": keeper.get("last_action_status", "MISSING"),
            "unresolved_supervision_risks": [risk["risk_ref"] for risk in risks],
        },
        "supervised_units": rows,
        "supervision_risks": risks,
        "recommended_operator_actions": actions,
        "keeper_status": keeper,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def sqlite_schema_sql() -> str:
    return """CREATE TABLE supervision_run (
    run_ref TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    startup_readiness TEXT NOT NULL,
    boot_persistence_state TEXT NOT NULL,
    boot_persistence_reason TEXT NOT NULL,
    linger_status TEXT NOT NULL,
    supervised_unit_count INTEGER NOT NULL,
    ready_unit_count INTEGER NOT NULL,
    risk_count INTEGER NOT NULL
);

CREATE TABLE supervised_unit (
    unit_name TEXT PRIMARY KEY,
    unit_kind TEXT NOT NULL,
    unit_path TEXT NOT NULL,
    enabled INTEGER NOT NULL CHECK(enabled IN (0, 1)),
    active INTEGER NOT NULL CHECK(active IN (0, 1)),
    active_state TEXT NOT NULL,
    sub_state TEXT NOT NULL,
    last_start_time TEXT NOT NULL,
    restart_count TEXT NOT NULL,
    expected_behavior TEXT NOT NULL,
    startup_readiness TEXT NOT NULL,
    reboot_persistence_status TEXT NOT NULL,
    latest_log_excerpt_summary TEXT NOT NULL,
    allowed_supervision_action TEXT NOT NULL,
    recommended_operator_action TEXT NOT NULL,
    observed_json TEXT NOT NULL
);

CREATE TABLE supervision_risk (
    risk_ref TEXT PRIMARY KEY,
    unit_name TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    operator_summary TEXT NOT NULL,
    detected_at TEXT NOT NULL
);

CREATE TABLE recommended_operator_action (
    action_ref TEXT PRIMARY KEY,
    unit_name TEXT NOT NULL,
    action_title TEXT NOT NULL,
    reason TEXT NOT NULL,
    recommended_command TEXT NOT NULL,
    allowed_supervision_action TEXT NOT NULL,
    forbidden_actions_json TEXT NOT NULL
);

CREATE TABLE keeper_status (
    status_ref TEXT PRIMARY KEY,
    status_path TEXT NOT NULL,
    last_action_status TEXT NOT NULL,
    action_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    observed_json TEXT NOT NULL
);
"""


def _write_sqlite(path: str | Path, payload: dict[str, Any]) -> None:
    sqlite_path = Path(path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    if sqlite_path.exists():
        sqlite_path.unlink()
    connection = sqlite3.connect(sqlite_path)
    try:
        connection.executescript(sqlite_schema_sql())
        connection.execute(
            """
            INSERT INTO supervision_run VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "openclaw_service_supervision_run",
                payload["generated_at"],
                payload["startup_readiness"],
                payload["boot_persistence_state"],
                payload["boot_persistence_reason"],
                payload["linger_status"].get("linger", "UNKNOWN"),
                payload["supervised_unit_count"],
                payload["ready_unit_count"],
                payload["risk_count"],
            ),
        )
        for row in payload["supervised_units"]:
            connection.execute(
                """
                INSERT INTO supervised_unit VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["unit_name"],
                    row["unit_kind"],
                    row.get("unit_path", ""),
                    _bool(bool(row.get("enabled"))),
                    _bool(bool(row.get("active"))),
                    row.get("active_state", ""),
                    row.get("sub_state", ""),
                    row.get("last_start_time", ""),
                    str(row.get("restart_count", "")),
                    row.get("expected_behavior", ""),
                    row.get("startup_readiness", ""),
                    payload["boot_persistence_state"],
                    row.get("log_excerpt_summary", ""),
                    row.get("allowed_supervision_action", ""),
                    row.get("recommended_operator_action", ""),
                    stable_json(row).strip(),
                ),
            )
        for risk in payload["supervision_risks"]:
            connection.execute(
                "INSERT INTO supervision_risk VALUES (?, ?, ?, ?, ?, ?)",
                (
                    risk["risk_ref"],
                    risk["unit_name"],
                    risk["severity"],
                    risk["status"],
                    risk["operator_summary"],
                    risk["detected_at"],
                ),
            )
        for action in payload["recommended_operator_actions"]:
            connection.execute(
                "INSERT INTO recommended_operator_action VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    action["action_ref"],
                    action["unit_name"],
                    action["action_title"],
                    action["reason"],
                    action["recommended_command"],
                    action["allowed_supervision_action"],
                    action["forbidden_actions_json"],
                ),
            )
        keeper = payload["keeper_status"]
        connection.execute(
            "INSERT INTO keeper_status VALUES (?, ?, ?, ?, ?, ?)",
            (
                "keeper_status:latest",
                keeper.get("status_path", ""),
                keeper.get("last_action_status", "UNKNOWN"),
                int(keeper.get("action_count", 0) or 0),
                keeper.get("status", "UNKNOWN"),
                keeper.get("observed_json", stable_json(keeper).strip()),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def render_operator_summary(payload: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Service Supervision",
        "",
        f"- Startup readiness: {payload['startup_readiness']}",
        f"- Boot persistence: {payload['boot_persistence_state']}",
        f"- Linger: {payload['linger_status'].get('linger', 'UNKNOWN')}",
        f"- Risk count: {payload['risk_count']}",
        "",
        "## Core Units",
    ]
    for row in payload["supervised_units"]:
        lines.append(
            "- "
            + row["unit_name"]
            + f": enabled={row.get('enabled_status', 'unknown')} "
            + f"active={row.get('active_state', '')}/{row.get('sub_state', '')} "
            + f"readiness={row.get('startup_readiness', '')}"
        )
    lines.extend(["", "## Keeper", f"- Last keeper action: {payload['core_monitor_status']['last_keeper_action']}"])
    if payload["supervision_risks"]:
        lines.extend(["", "## Risks"])
        for risk in payload["supervision_risks"]:
            lines.append(f"- {risk['unit_name']}: {risk['status']} - {risk['operator_summary']}")
    else:
        lines.extend(["", "No unresolved supervision risks."])
    return "\n".join(lines) + "\n"


def export_openclaw_service_supervision(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    system_knowledge_root: str | Path = DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    generated_at: str | None = None,
    unit_rows: list[dict[str, Any]] | None = None,
    linger_status: dict[str, str] | None = None,
    runner: CommandRunner | None = None,
    include_systemd: bool = True,
) -> ServiceSupervisionExportResult:
    read_root = _rooted(read_model_root)
    system_root = _rooted(system_knowledge_root)
    read_root.mkdir(parents=True, exist_ok=True)
    system_root.mkdir(parents=True, exist_ok=True)
    payload = build_openclaw_service_supervision(
        read_model_root=read_root,
        generated_at=generated_at,
        unit_rows=unit_rows,
        linger_status=linger_status,
        runner=runner,
        include_systemd=include_systemd,
    )
    json_path = read_root / JSON_EXPORT_NAME
    operator_path = read_root / OPERATOR_EXPORT_NAME
    sqlite_path = system_root / SQLITE_EXPORT_NAME
    schema_path = system_root / SCHEMA_EXPORT_NAME
    seed_path = system_root / SEED_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(render_operator_summary(payload), encoding="utf-8")
    schema_path.write_text(sqlite_schema_sql(), encoding="utf-8")
    seed_path.write_text(
        "-- OpenClaw service supervision seed is generated from live systemd state at export time.\n",
        encoding="utf-8",
    )
    _write_sqlite(sqlite_path, payload)
    return ServiceSupervisionExportResult(
        schema_version=READ_MODEL_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        sqlite_path=_display_path(sqlite_path),
        schema_sql_path=_display_path(schema_path),
        seed_sql_path=_display_path(seed_path),
        supervised_unit_count=payload["supervised_unit_count"],
        ready_unit_count=payload["ready_unit_count"],
        risk_count=payload["risk_count"],
        startup_readiness=payload["startup_readiness"],
    )


def _print_payload(payload: dict[str, Any] | ServiceSupervisionExportResult, fmt: str) -> None:
    if isinstance(payload, ServiceSupervisionExportResult):
        data = payload.__dict__
    else:
        data = payload
    if fmt == "json":
        print(stable_json(data), end="")
    elif fmt == "operator":
        if isinstance(payload, ServiceSupervisionExportResult):
            operator_path = _rooted(payload.operator_path)
            print(operator_path.read_text(encoding="utf-8"), end="")
        else:
            print(render_operator_summary(payload), end="")
    else:
        if isinstance(payload, ServiceSupervisionExportResult):
            print(
                "OpenClaw service supervision: "
                f"{payload.startup_readiness}; units={payload.supervised_unit_count}; "
                f"ready={payload.ready_unit_count}; risks={payload.risk_count}"
            )
        else:
            print(
                "OpenClaw service supervision: "
                f"{data['startup_readiness']}; units={data['supervised_unit_count']}; "
                f"ready={data['ready_unit_count']}; risks={data['risk_count']}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--system-knowledge-root", default=str(DEFAULT_SYSTEM_KNOWLEDGE_ROOT))
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--no-systemd", action="store_true")
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    args = parser.parse_args(argv)

    result = export_openclaw_service_supervision(
        read_model_root=args.read_model_root,
        system_knowledge_root=args.system_knowledge_root,
        generated_at=args.generated_at,
        include_systemd=not args.no_systemd,
    )
    if args.format == "json":
        payload = json.loads((_rooted(args.read_model_root) / JSON_EXPORT_NAME).read_text(encoding="utf-8"))
        _print_payload(payload, "json")
    elif args.format == "operator":
        _print_payload(result, "operator")
    else:
        _print_payload(result, "summary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
