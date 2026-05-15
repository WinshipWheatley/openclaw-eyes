#!/usr/bin/env python3
"""Manage OpenClaw local automation services for the current machine."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from generated_read_model_files import canonical_generated_read_model_records, sha256_file
from local_automation_registry import (
    NO_AUTHORITY_FLAGS,
    record_service_status,
    seed_local_automation_registry,
    stable_json,
)


MANAGER_VERSION = "openclaw_local_automation_services_v0"
TARGET_READ_MODEL_MIRROR = "read_model_mirror"
MACHINE_MAC = "mac"
MACHINE_PC_WSL = "pc_wsl"
MACHINE_UNSUPPORTED = "unsupported"

PC_SHARE_ROOT = Path("/mnt/e/openclaw")
MAC_SHARE_ROOT = Path("/Volumes/openclaw_e")
PC_MANIFEST_PATH = PC_SHARE_ROOT / "mac_generated_read_models_manifest.json"
PC_REQUEST_MARKER = PC_SHARE_ROOT / "shuttle" / "to_mac" / "read_model_sync_required.json"
PC_COMPLETION_MARKER = PC_SHARE_ROOT / "shuttle" / "from_mac" / "read_model_sync_completed.json"
MAC_REQUEST_MARKER = MAC_SHARE_ROOT / "shuttle" / "to_mac" / "read_model_sync_required.json"
MAC_COMPLETION_MARKER = MAC_SHARE_ROOT / "shuttle" / "from_mac" / "read_model_sync_completed.json"

PC_SERVICE_NAME = "openclaw-read-model-import.service"
PC_TIMER_NAME = "openclaw-read-model-import.timer"
PC_SYSTEMD_USER_DIR = Path("~/.config/systemd/user").expanduser()
PC_SERVICE_TEMPLATE = ROOT / "systemd" / "user" / "openclaw-read-model-import.service.in"
PC_TIMER_TEMPLATE = ROOT / "systemd" / "user" / "openclaw-read-model-import.timer.in"
PC_SERVICE_TARGET = PC_SYSTEMD_USER_DIR / PC_SERVICE_NAME
PC_TIMER_TARGET = PC_SYSTEMD_USER_DIR / PC_TIMER_NAME

MAC_LAUNCH_LABEL = "com.openclaw.read-model-sync"
MAC_PLIST_SOURCE = ROOT / "launchd" / "com.openclaw.read-model-sync.plist"
MAC_LAUNCH_AGENT_DIR = Path("~/Library/LaunchAgents").expanduser()
MAC_PLIST_TARGET = MAC_LAUNCH_AGENT_DIR / "com.openclaw.read-model-sync.plist"
MAC_LOG_DIR = Path("~/Library/Logs/OpenClaw").expanduser()

NEXT_MAC_INSTALL_COMMAND = (
    "cd ~/Developer/OpenClawBackend/openclaw\n"
    "PYTHONDONTWRITEBYTECODE=1 python3 scripts/manage_openclaw_local_services.py "
    "--install read_model_mirror --format operator\n"
    "PYTHONDONTWRITEBYTECODE=1 python3 scripts/manage_openclaw_local_services.py "
    "--start read_model_mirror --format operator"
)
NEXT_PC_INSTALL_COMMAND = (
    "cd /home/openclaw\n"
    "PYTHONDONTWRITEBYTECODE=1 python3 scripts/manage_openclaw_local_services.py "
    "--install read_model_mirror --format operator\n"
    "PYTHONDONTWRITEBYTECODE=1 python3 scripts/manage_openclaw_local_services.py "
    "--start read_model_mirror --format operator"
)

Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class CommandRecord:
    command: list[str]
    returncode: int
    stdout_tail: str
    stderr_tail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
        }


def default_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, shell=False, timeout=60)


def _tail(value: str | bytes | None, limit: int = 2000) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value[-limit:]


def run_fixed_command(command: list[str], *, runner: Runner = default_runner) -> CommandRecord:
    completed = runner(command)
    return CommandRecord(
        command=command,
        returncode=completed.returncode,
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
    )


def _proc_version_text(path: str | Path = "/proc/version") -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return ""


def detect_machine(
    *,
    platform_name: str | None = None,
    pc_share_root: str | Path = PC_SHARE_ROOT,
    proc_version_text: str | None = None,
) -> str:
    observed = platform_name or platform.system()
    if observed == "Darwin":
        return MACHINE_MAC
    if observed == "Linux":
        version_text = proc_version_text if proc_version_text is not None else _proc_version_text()
        if Path(pc_share_root).exists() or "microsoft" in version_text or "wsl" in version_text:
            return MACHINE_PC_WSL
    return MACHINE_UNSUPPORTED


def _systemd_user_available(*, runner: Runner = default_runner) -> tuple[bool, list[dict[str, Any]]]:
    if shutil.which("systemctl") is None:
        return False, []
    record = run_fixed_command(["systemctl", "--user", "show-environment"], runner=runner)
    return record.returncode == 0, [record.as_dict()]


def _launchctl_available() -> bool:
    return shutil.which("launchctl") is not None


def _render_systemd_template(template_path: Path, *, python_executable: str = sys.executable) -> str:
    text = template_path.read_text(encoding="utf-8")
    return text.replace("@REPO_ROOT@", ROOT.as_posix()).replace("@PYTHON@", python_executable)


def install_pc_service(*, runner: Runner = default_runner) -> dict[str, Any]:
    available, checks = _systemd_user_available(runner=runner)
    if not available:
        return {
            "status": "deferred_no_scheduler",
            "message": "WSL user systemd is not available; no service files were installed.",
            "commands": checks,
            "next_safe_move": (
                "Use the one-shot command or run the documented loop manually until a WSL user scheduler is available."
            ),
        }
    PC_SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
    PC_SERVICE_TARGET.write_text(_render_systemd_template(PC_SERVICE_TEMPLATE), encoding="utf-8")
    PC_TIMER_TARGET.write_text(_render_systemd_template(PC_TIMER_TEMPLATE), encoding="utf-8")
    reload_record = run_fixed_command(["systemctl", "--user", "daemon-reload"], runner=runner)
    status = "installed" if reload_record.returncode == 0 else "install_failed"
    return {
        "status": status,
        "service_path": PC_SERVICE_TARGET.as_posix(),
        "timer_path": PC_TIMER_TARGET.as_posix(),
        "commands": [*checks, reload_record.as_dict()],
        "start_command": "python3 scripts/manage_openclaw_local_services.py --start read_model_mirror --format operator",
    }


def start_pc_service(*, runner: Runner = default_runner) -> dict[str, Any]:
    available, checks = _systemd_user_available(runner=runner)
    if not available:
        return {"status": "deferred_no_scheduler", "commands": checks}
    if not PC_TIMER_TARGET.is_file() or not PC_SERVICE_TARGET.is_file():
        return {"status": "needs_install", "message": "PC service/timer files are not installed."}
    start_record = run_fixed_command(["systemctl", "--user", "enable", "--now", PC_TIMER_NAME], runner=runner)
    return {
        "status": "started" if start_record.returncode == 0 else "start_failed",
        "commands": [*checks, start_record.as_dict()],
    }


def stop_pc_service(*, runner: Runner = default_runner) -> dict[str, Any]:
    available, checks = _systemd_user_available(runner=runner)
    if not available:
        return {"status": "deferred_no_scheduler", "commands": checks}
    stop_record = run_fixed_command(["systemctl", "--user", "disable", "--now", PC_TIMER_NAME], runner=runner)
    return {
        "status": "stopped" if stop_record.returncode == 0 else "stop_failed",
        "commands": [*checks, stop_record.as_dict()],
    }


def uninstall_pc_service(*, runner: Runner = default_runner) -> dict[str, Any]:
    stop_result = stop_pc_service(runner=runner)
    removed: list[str] = []
    for path in (PC_SERVICE_TARGET, PC_TIMER_TARGET):
        if path.is_file():
            path.unlink()
            removed.append(path.as_posix())
    commands = list(stop_result.get("commands", []))
    available, checks = _systemd_user_available(runner=runner)
    commands.extend(checks)
    if available:
        reload_record = run_fixed_command(["systemctl", "--user", "daemon-reload"], runner=runner)
        commands.append(reload_record.as_dict())
    return {
        "status": "uninstalled",
        "removed_service_files": removed,
        "data_deleted": False,
        "commands": commands,
    }


def install_mac_service() -> dict[str, Any]:
    MAC_LAUNCH_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    MAC_LOG_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MAC_PLIST_SOURCE, MAC_PLIST_TARGET)
    return {
        "status": "installed",
        "plist_source": MAC_PLIST_SOURCE.as_posix(),
        "plist_target": MAC_PLIST_TARGET.as_posix(),
        "log_dir": MAC_LOG_DIR.as_posix(),
        "start_command": "python3 scripts/manage_openclaw_local_services.py --start read_model_mirror --format operator",
    }


def start_mac_service(*, runner: Runner = default_runner) -> dict[str, Any]:
    if not _launchctl_available():
        return {"status": "launchctl_unavailable"}
    if not MAC_PLIST_TARGET.is_file():
        return {"status": "needs_install", "message": "Mac LaunchAgent plist is not installed."}
    uid = str(os.getuid())
    commands = [
        run_fixed_command(["launchctl", "bootstrap", f"gui/{uid}", MAC_PLIST_TARGET.as_posix()], runner=runner),
        run_fixed_command(["launchctl", "enable", f"gui/{uid}/{MAC_LAUNCH_LABEL}"], runner=runner),
        run_fixed_command(["launchctl", "kickstart", "-k", f"gui/{uid}/{MAC_LAUNCH_LABEL}"], runner=runner),
    ]
    ok = all(item.returncode == 0 for item in commands)
    return {"status": "started" if ok else "start_failed", "commands": [item.as_dict() for item in commands]}


def stop_mac_service(*, runner: Runner = default_runner) -> dict[str, Any]:
    if not _launchctl_available():
        return {"status": "launchctl_unavailable"}
    uid = str(os.getuid())
    record = run_fixed_command(["launchctl", "bootout", f"gui/{uid}", MAC_PLIST_TARGET.as_posix()], runner=runner)
    return {"status": "stopped" if record.returncode == 0 else "stop_failed", "commands": [record.as_dict()]}


def uninstall_mac_service(*, runner: Runner = default_runner) -> dict[str, Any]:
    stop_result = stop_mac_service(runner=runner)
    removed = []
    if MAC_PLIST_TARGET.is_file():
        MAC_PLIST_TARGET.unlink()
        removed.append(MAC_PLIST_TARGET.as_posix())
    return {
        "status": "uninstalled",
        "removed_service_files": removed,
        "data_deleted": False,
        "commands": stop_result.get("commands", []),
    }


def _systemd_state(*, runner: Runner = default_runner) -> dict[str, Any]:
    available, checks = _systemd_user_available(runner=runner)
    result = {
        "scheduler_available": available,
        "availability_checks": checks,
        "service_file_installed": PC_SERVICE_TARGET.is_file(),
        "timer_file_installed": PC_TIMER_TARGET.is_file(),
        "enabled_state": "unknown",
        "running_state": "unknown",
    }
    if available:
        enabled = run_fixed_command(["systemctl", "--user", "is-enabled", PC_TIMER_NAME], runner=runner)
        active = run_fixed_command(["systemctl", "--user", "is-active", PC_TIMER_NAME], runner=runner)
        result["enabled_state"] = "enabled" if enabled.returncode == 0 else "not_enabled"
        result["running_state"] = "active" if active.returncode == 0 else "not_active"
        result["status_commands"] = [enabled.as_dict(), active.as_dict()]
    return result


def _launchd_state(*, runner: Runner = default_runner) -> dict[str, Any]:
    result = {
        "scheduler_available": _launchctl_available(),
        "plist_installed": MAC_PLIST_TARGET.is_file(),
        "running_state": "unknown",
    }
    if result["scheduler_available"]:
        uid = str(os.getuid())
        record = run_fixed_command(["launchctl", "print", f"gui/{uid}/{MAC_LAUNCH_LABEL}"], runner=runner)
        result["running_state"] = "loaded" if record.returncode == 0 else "not_loaded"
        result["status_commands"] = [record.as_dict()]
    return result


def compare_manifest_to_backend(manifest_path: str | Path = PC_MANIFEST_PATH) -> dict[str, Any]:
    manifest = Path(manifest_path)
    expected_records = {item["relative_path"]: item for item in canonical_generated_read_model_records()}
    expected = set(expected_records)
    if not manifest.is_file():
        return {
            "manifest_present": False,
            "manifest_path": manifest.as_posix(),
            "counts": {
                "canonical_expected": len(expected),
                "observed": 0,
                "missing_expected": len(expected),
                "extra": 0,
                "hash_mismatch": 0,
                "matched_hash": 0,
            },
            "missing_expected_files": sorted(expected),
            "extra_files": [],
            "hash_mismatch_files": [],
        }
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    records = payload.get("path_records", [])
    observed_records = {
        record.get("relative_path"): record
        for record in records
        if isinstance(record, dict) and isinstance(record.get("relative_path"), str)
    }
    observed = set(observed_records)
    common = expected & observed
    matched = []
    mismatched = []
    for relative_path in sorted(common):
        expected_hash = expected_records[relative_path].get("sha256")
        observed_hash = observed_records[relative_path].get("content_hash")
        if expected_hash and observed_hash and expected_hash == observed_hash:
            matched.append(relative_path)
        elif expected_hash and observed_hash and expected_hash != observed_hash:
            mismatched.append(relative_path)
    return {
        "manifest_present": True,
        "manifest_path": manifest.as_posix(),
        "manifest_sha256": sha256_file(manifest),
        "counts": {
            "canonical_expected": len(expected),
            "observed": len(observed),
            "missing_expected": len(expected - observed),
            "extra": len(observed - expected),
            "hash_mismatch": len(mismatched),
            "matched_hash": len(matched),
        },
        "missing_expected_files": sorted(expected - observed),
        "extra_files": sorted(observed - expected),
        "hash_mismatch_files": mismatched,
    }


def _pc_import_state_hash(state_path: Path = ROOT / ".openclaw" / "state" / "read_model_import_agent_state.json") -> str | None:
    if not state_path.is_file():
        return None
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("last_successful_manifest_sha256")
    return value if isinstance(value, str) else None


def doctor_report(
    *,
    machine: str,
    runner: Runner = default_runner,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    status = status_report(machine=machine, runner=runner, db_path=db_path)
    if machine == MACHINE_PC_WSL:
        manifest_health = compare_manifest_to_backend(PC_MANIFEST_PATH)
        counts = manifest_health["counts"]
        share_available = PC_SHARE_ROOT.is_dir()
        if not share_available:
            next_status = "share_missing"
            next_safe_move = "Mount or restore /mnt/e/openclaw before relying on the local import service."
        elif not manifest_health["manifest_present"]:
            next_status = "manifest_missing"
            next_safe_move = "Run the Mac sync side after mounting /Volumes/openclaw_e."
        elif counts["hash_mismatch"] > 0:
            next_status = "error"
            next_safe_move = "Review hash mismatches before importing or treating the mirror as current."
        elif counts["missing_expected"] > 0:
            next_status = "needs_mac_sync"
            next_safe_move = "Run the Mac read-model sync side so the share gets a fresh manifest."
        elif counts["extra"] > 0:
            next_status = "review_needed"
            next_safe_move = "Review extra files in the Mac mirror before treating it as current."
        elif _pc_import_state_hash() != manifest_health.get("manifest_sha256"):
            next_status = "needs_pc_import"
            next_safe_move = "Run the PC import agent once or start the PC import service."
        else:
            next_status = "ok"
            next_safe_move = "No read-model mirror action is needed."
        return {
            **status,
            "operation": "doctor",
            "doctor_status": next_status,
            "manifest_health": manifest_health,
            "request_marker_present": PC_REQUEST_MARKER.is_file(),
            "completion_marker_present": PC_COMPLETION_MARKER.is_file(),
            "next_safe_move": next_safe_move,
        }
    if machine == MACHINE_MAC:
        share_available = MAC_SHARE_ROOT.is_dir()
        if not share_available:
            next_status = "share_missing"
            next_safe_move = "Mount /Volumes/openclaw_e before relying on the Mac sync service."
        elif MAC_REQUEST_MARKER.is_file():
            next_status = "sync_required"
            next_safe_move = "Run or start the Mac sync agent; it will process the marker locally."
        elif MAC_COMPLETION_MARKER.is_file():
            next_status = "needs_pc_import"
            next_safe_move = "Run the PC import side so the backend ledger imports the latest manifest."
        else:
            next_status = "idle"
            next_safe_move = "No marker is waiting on the Mac side."
        return {
            **status,
            "operation": "doctor",
            "doctor_status": next_status,
            "share_available": share_available,
            "request_marker_present": MAC_REQUEST_MARKER.is_file(),
            "completion_marker_present": MAC_COMPLETION_MARKER.is_file(),
            "next_safe_move": next_safe_move,
        }
    return {**status, "operation": "doctor", "doctor_status": "unsupported", "next_safe_move": "Run from macOS or PC/WSL."}


def status_report(
    *,
    machine: str,
    runner: Runner = default_runner,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    seed_local_automation_registry(db_path=db_path)
    if machine == MACHINE_PC_WSL:
        service = _systemd_state(runner=runner)
        share_available = PC_SHARE_ROOT.is_dir()
        installed_state = "installed" if service["service_file_installed"] and service["timer_file_installed"] else "not_installed"
        running_state = service["running_state"]
        record_service_status(
            db_path=db_path,
            task_id="read_model_mirror_pc_import",
            machine=machine,
            installed_state=installed_state,
            running_state=running_state,
            scheduler_available=bool(service["scheduler_available"]),
            share_available=share_available,
            details=service,
        )
        return {
            "manager_version": MANAGER_VERSION,
            "operation": "status",
            "machine": machine,
            "target": TARGET_READ_MODEL_MIRROR,
            "share_root": PC_SHARE_ROOT.as_posix(),
            "share_available": share_available,
            "local_task_id": "read_model_mirror_pc_import",
            "service": service,
            "mac_install_command": NEXT_MAC_INSTALL_COMMAND,
            "pc_install_command": NEXT_PC_INSTALL_COMMAND,
            **NO_AUTHORITY_FLAGS,
        }
    if machine == MACHINE_MAC:
        service = _launchd_state(runner=runner)
        share_available = MAC_SHARE_ROOT.is_dir()
        installed_state = "installed" if service["plist_installed"] else "not_installed"
        record_service_status(
            db_path=db_path,
            task_id="read_model_mirror_mac_sync",
            machine=machine,
            installed_state=installed_state,
            running_state=service["running_state"],
            scheduler_available=bool(service["scheduler_available"]),
            share_available=share_available,
            details=service,
        )
        return {
            "manager_version": MANAGER_VERSION,
            "operation": "status",
            "machine": machine,
            "target": TARGET_READ_MODEL_MIRROR,
            "share_root": MAC_SHARE_ROOT.as_posix(),
            "share_available": share_available,
            "local_task_id": "read_model_mirror_mac_sync",
            "service": service,
            "mac_install_command": NEXT_MAC_INSTALL_COMMAND,
            "pc_install_command": NEXT_PC_INSTALL_COMMAND,
            **NO_AUTHORITY_FLAGS,
        }
    return {
        "manager_version": MANAGER_VERSION,
        "operation": "status",
        "machine": machine,
        "target": TARGET_READ_MODEL_MIRROR,
        "status": "unsupported_environment",
        **NO_AUTHORITY_FLAGS,
    }


def manage_service(
    *,
    operation: str,
    target: str = TARGET_READ_MODEL_MIRROR,
    machine: str | None = None,
    runner: Runner = default_runner,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    if target != TARGET_READ_MODEL_MIRROR:
        return {
            "manager_version": MANAGER_VERSION,
            "operation": operation,
            "target": target,
            "status": "unsupported_target",
            **NO_AUTHORITY_FLAGS,
        }
    resolved_machine = machine or detect_machine()
    if operation == "status":
        return status_report(machine=resolved_machine, runner=runner, db_path=db_path)
    if operation == "doctor":
        return doctor_report(machine=resolved_machine, runner=runner, db_path=db_path)
    if resolved_machine == MACHINE_PC_WSL:
        handlers = {
            "install": install_pc_service,
            "start": start_pc_service,
            "stop": stop_pc_service,
            "uninstall": uninstall_pc_service,
        }
        result = handlers[operation](runner=runner)
        return {
            "manager_version": MANAGER_VERSION,
            "operation": operation,
            "machine": resolved_machine,
            "target": target,
            "local_task_id": "read_model_mirror_pc_import",
            "result": result,
            "status": result.get("status"),
            "other_machine_not_controlled": True,
            "mac_install_command": NEXT_MAC_INSTALL_COMMAND,
            **NO_AUTHORITY_FLAGS,
        }
    if resolved_machine == MACHINE_MAC:
        if operation == "install":
            result = install_mac_service()
        elif operation == "start":
            result = start_mac_service(runner=runner)
        elif operation == "stop":
            result = stop_mac_service(runner=runner)
        elif operation == "uninstall":
            result = uninstall_mac_service(runner=runner)
        else:
            result = {"status": "unsupported_operation"}
        return {
            "manager_version": MANAGER_VERSION,
            "operation": operation,
            "machine": resolved_machine,
            "target": target,
            "local_task_id": "read_model_mirror_mac_sync",
            "result": result,
            "status": result.get("status"),
            "other_machine_not_controlled": True,
            "pc_install_command": NEXT_PC_INSTALL_COMMAND,
            **NO_AUTHORITY_FLAGS,
        }
    return {
        "manager_version": MANAGER_VERSION,
        "operation": operation,
        "machine": resolved_machine,
        "target": target,
        "status": "unsupported_environment",
        "message": "Run this manager from macOS or PC/WSL.",
        **NO_AUTHORITY_FLAGS,
    }


def format_service_report(payload: dict[str, Any]) -> str:
    lines = [
        "OpenClaw Local Automation Services v0",
        "",
        f"Operation: `{payload.get('operation')}`",
        f"Machine: `{payload.get('machine')}`",
        f"Target: `{payload.get('target')}`",
        f"Status: `{payload.get('status') or payload.get('doctor_status') or 'ok'}`",
    ]
    if payload.get("share_root"):
        lines.append(f"Share: `{payload['share_root']}` available={str(payload.get('share_available')).lower()}")
    if payload.get("local_task_id"):
        lines.append(f"Local task: `{payload['local_task_id']}`")
    if payload.get("service"):
        service = payload["service"]
        if "scheduler_available" in service:
            lines.append(f"Scheduler available: {str(service['scheduler_available']).lower()}")
        for key in ("service_file_installed", "timer_file_installed", "plist_installed", "enabled_state", "running_state"):
            if key in service:
                lines.append(f"{key}: {service[key]}")
    if payload.get("result"):
        result = payload["result"]
        lines.append(f"Result: `{result.get('status')}`")
        if result.get("message"):
            lines.append(f"Message: {result['message']}")
        if result.get("service_path"):
            lines.append(f"Service file: `{result['service_path']}`")
        if result.get("timer_path"):
            lines.append(f"Timer file: `{result['timer_path']}`")
        if result.get("removed_service_files"):
            lines.append(f"Removed OpenClaw service files: {result['removed_service_files']}")
        if result.get("next_safe_move"):
            lines.append(f"Next safe move: {result['next_safe_move']}")
    if payload.get("doctor_status"):
        lines.append(f"Doctor status: `{payload['doctor_status']}`")
        lines.append(f"Next safe move: {payload.get('next_safe_move')}")
        if payload.get("manifest_health"):
            counts = payload["manifest_health"]["counts"]
            lines.extend(
                [
                    "Manifest health:",
                    f"- canonical_expected={counts['canonical_expected']}",
                    f"- observed={counts['observed']}",
                    f"- missing_expected={counts['missing_expected']}",
                    f"- extra={counts['extra']}",
                    f"- hash_mismatch={counts['hash_mismatch']}",
                ]
            )
    if payload.get("mac_install_command"):
        lines.extend(["", "Mac install/start command:", "```bash", payload["mac_install_command"], "```"])
    if payload.get("pc_install_command"):
        lines.extend(["", "PC/WSL install/start command:", "```bash", payload["pc_install_command"], "```"])
    lines.extend(
        [
            "",
            "Boundary:",
            "- Manages only the current machine's local read-model mirror service half.",
            "- No arbitrary command, remote control, C-drive default, Mission Control change, generated-contract change, runtime, agent, tool, Docker, or Ollama authority is introduced.",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage OpenClaw local automation services.")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--status", action="store_true")
    operation.add_argument("--install", choices=(TARGET_READ_MODEL_MIRROR,))
    operation.add_argument("--start", choices=(TARGET_READ_MODEL_MIRROR,))
    operation.add_argument("--stop", choices=(TARGET_READ_MODEL_MIRROR,))
    operation.add_argument("--uninstall", choices=(TARGET_READ_MODEL_MIRROR,))
    operation.add_argument("--doctor", choices=(TARGET_READ_MODEL_MIRROR,))
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def _operation_from_args(args: argparse.Namespace) -> tuple[str, str]:
    if args.install:
        return "install", args.install
    if args.start:
        return "start", args.start
    if args.stop:
        return "stop", args.stop
    if args.uninstall:
        return "uninstall", args.uninstall
    if args.doctor:
        return "doctor", args.doctor
    return "status", TARGET_READ_MODEL_MIRROR


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    operation, target = _operation_from_args(args)
    payload = manage_service(operation=operation, target=target, db_path=args.db)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_service_report(payload))
    bad_statuses = {
        "install_failed",
        "start_failed",
        "stop_failed",
        "unsupported_environment",
        "unsupported_target",
        "error",
    }
    return 1 if payload.get("status") in bad_statuses else 0


if __name__ == "__main__":
    raise SystemExit(main())
