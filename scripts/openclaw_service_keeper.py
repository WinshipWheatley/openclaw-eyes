#!/usr/bin/env python3
"""Allowlisted OpenClaw user-service keeper.

The keeper checks only the hard-coded core allowlist and starts an allowlisted
unit only when it is inactive. It does not restart active units, launch Chief,
call an LM, or touch business workflow queues.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_READ_MODEL_ROOT = ROOT / "generated/read_models"

JSON_EXPORT_NAME = "openclaw_service_keeper_status.json"
OPERATOR_EXPORT_NAME = "openclaw_service_keeper_status_OPERATOR.md"

ALLOWED_UNITS = (
    "openclaw-request-response.service",
    "openclaw-change-sentinel.timer",
)

STATUS_VALUES = (
    "NO_ACTION_REQUIRED",
    "STARTED_INACTIVE_UNIT",
    "UNIT_MISSING",
    "START_FAILED",
    "NOT_ALLOWLISTED",
    "SYSTEMD_UNAVAILABLE",
    "UNKNOWN",
)

NO_AUTHORITY_FLAGS = {
    "allowlisted_service_keeper_only": True,
    "restarts_active_services": False,
    "starts_arbitrary_services": False,
    "chief_launched": False,
    "lm_called": False,
    "business_workflow_state_mutated": False,
    "queue_files_processed_directly": False,
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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


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


def _systemctl_available(runner: CommandRunner | None) -> bool:
    if runner is not None:
        return True
    return shutil.which("systemctl") is not None


def _require_status(status: str) -> str:
    if status not in STATUS_VALUES:
        raise ValueError(f"unknown keeper status: {status}")
    return status


def _unit_show(unit_name: str, *, runner: CommandRunner | None) -> tuple[CommandResult, dict[str, str]]:
    command = [
        "systemctl",
        "--user",
        "show",
        unit_name,
        "--property=LoadState,ActiveState,SubState,FragmentPath",
        "--no-pager",
    ]
    result = (runner or _run_command)(command)
    values = _parse_key_values(result.stdout)
    if result.returncode != 0 and not values:
        values = {"LoadState": "not-found", "ActiveState": "inactive", "SubState": "dead"}
    return result, values


def check_and_start_unit(
    unit_name: str,
    *,
    runner: CommandRunner | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    observed_at = generated_at or utc_now()
    if unit_name not in ALLOWED_UNITS:
        return {
            "unit_name": unit_name,
            "status": _require_status("NOT_ALLOWLISTED"),
            "active_state_before": "",
            "sub_state_before": "",
            "active_state_after": "",
            "sub_state_after": "",
            "started": False,
            "error_message": "Unit is not in the OpenClaw service keeper allowlist.",
            "observed_at": observed_at,
        }
    if not _systemctl_available(runner):
        return {
            "unit_name": unit_name,
            "status": _require_status("SYSTEMD_UNAVAILABLE"),
            "active_state_before": "",
            "sub_state_before": "",
            "active_state_after": "",
            "sub_state_after": "",
            "started": False,
            "error_message": "systemctl is unavailable.",
            "observed_at": observed_at,
        }
    show_result, values = _unit_show(unit_name, runner=runner)
    load_state = values.get("LoadState", "")
    active_state = values.get("ActiveState", "")
    sub_state = values.get("SubState", "")
    if load_state in {"not-found", "masked"}:
        return {
            "unit_name": unit_name,
            "status": _require_status("UNIT_MISSING"),
            "active_state_before": active_state,
            "sub_state_before": sub_state,
            "active_state_after": active_state,
            "sub_state_after": sub_state,
            "started": False,
            "error_message": show_result.stderr.strip() or "Unit is missing or masked.",
            "observed_at": observed_at,
        }
    if active_state == "active":
        return {
            "unit_name": unit_name,
            "status": _require_status("NO_ACTION_REQUIRED"),
            "active_state_before": active_state,
            "sub_state_before": sub_state,
            "active_state_after": active_state,
            "sub_state_after": sub_state,
            "started": False,
            "error_message": "",
            "observed_at": observed_at,
        }
    start_result = (runner or _run_command)(["systemctl", "--user", "start", unit_name])
    if start_result.returncode != 0:
        return {
            "unit_name": unit_name,
            "status": _require_status("START_FAILED"),
            "active_state_before": active_state,
            "sub_state_before": sub_state,
            "active_state_after": active_state,
            "sub_state_after": sub_state,
            "started": False,
            "error_message": start_result.stderr.strip() or "systemctl start failed.",
            "observed_at": observed_at,
        }
    _, after_values = _unit_show(unit_name, runner=runner)
    return {
        "unit_name": unit_name,
        "status": _require_status("STARTED_INACTIVE_UNIT"),
        "active_state_before": active_state,
        "sub_state_before": sub_state,
        "active_state_after": after_values.get("ActiveState", ""),
        "sub_state_after": after_values.get("SubState", ""),
        "started": True,
        "error_message": "",
        "observed_at": observed_at,
    }


def _run_status(unit_results: list[dict[str, Any]]) -> str:
    statuses = {row["status"] for row in unit_results}
    for status in (
        "START_FAILED",
        "SYSTEMD_UNAVAILABLE",
        "UNIT_MISSING",
        "STARTED_INACTIVE_UNIT",
        "NOT_ALLOWLISTED",
    ):
        if status in statuses:
            return status
    return "NO_ACTION_REQUIRED"


def build_service_keeper_status(
    *,
    units: list[str] | None = None,
    runner: CommandRunner | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    selected_units = units or list(ALLOWED_UNITS)
    unit_results = [
        check_and_start_unit(unit_name, runner=runner, generated_at=generated)
        for unit_name in selected_units
    ]
    action_count = sum(1 for row in unit_results if row["status"] == "STARTED_INACTIVE_UNIT")
    return {
        "schema_version": "openclaw_service_keeper_status_v0",
        "generated_by": "codex",
        "generated_at": generated,
        "purpose": "Start only inactive allowlisted OpenClaw core user units.",
        "allowed_units": list(ALLOWED_UNITS),
        "checked_units": selected_units,
        "run_status": _run_status(unit_results),
        "action_count": action_count,
        "unit_results": unit_results,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def render_operator_summary(payload: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Service Keeper",
        "",
        f"- Run status: {payload['run_status']}",
        f"- Action count: {payload['action_count']}",
        "",
        "## Units",
    ]
    for row in payload["unit_results"]:
        lines.append(
            f"- {row['unit_name']}: {row['status']} "
            f"({row['active_state_before']}/{row['sub_state_before']} -> "
            f"{row['active_state_after']}/{row['sub_state_after']})"
        )
        if row.get("error_message"):
            lines.append(f"  Reason: {row['error_message']}")
    return "\n".join(lines) + "\n"


def write_service_keeper_status(
    payload: dict[str, Any],
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
) -> tuple[Path, Path]:
    root = Path(read_model_root)
    if not root.is_absolute():
        root = ROOT / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(render_operator_summary(payload), encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    parser.add_argument("--unit", action="append", default=None)
    args = parser.parse_args(argv)

    payload = build_service_keeper_status(units=args.unit)
    write_service_keeper_status(payload, read_model_root=args.read_model_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    elif args.format == "operator":
        print(render_operator_summary(payload), end="")
    else:
        print(
            "OpenClaw service keeper: "
            f"{payload['run_status']}; checked={len(payload['unit_results'])}; "
            f"actions={payload['action_count']}"
        )
    return 0 if payload["run_status"] not in {"START_FAILED", "SYSTEMD_UNAVAILABLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
