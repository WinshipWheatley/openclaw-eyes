"""Codex Work Package Lifecycle V0.

Persists bounded CODEX_WORK_PACKAGE_V0 packages through queue, handoff,
result ingestion, validation, and activation decisions. It does not spawn
workers, push/merge, invoke models, open Gmail/browser/Coupa, send email, or
grant authority from raw text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Codex Work Package Lifecycle.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/codex_work_package_lifecycle.sqlite")
DEFAULT_PACKAGE_ROOT = Path("/tmp/openclaw-mission-control/codex_work_packages")

SCHEMA_VERSION = "codex_work_package_lifecycle_v0"
READ_MODEL_ID = "codex_work_package_lifecycle"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "OPENCLAW_CODEX_WORK_PACKAGE_LIFECYCLE_READY"

PACKAGE_STATE_SCHEMA = "CODEX_WORK_PACKAGE_STATE_V0"
PACKAGE_QUEUE_SCHEMA = "CODEX_WORK_PACKAGE_QUEUE_V0"
WORKER_BRIDGE_STATUS_SCHEMA = "CODEX_WORKER_BRIDGE_STATUS_V0"
PACKAGE_CLAIM_SCHEMA = "CODEX_WORK_PACKAGE_CLAIM_V0"
PACKAGE_RESULT_SCHEMA = "CODEX_WORK_PACKAGE_RESULT_V0"
ACTIVATION_DECISION_SCHEMA = "CAPABILITY_ACTIVATION_DECISION_V0"
VALIDATION_RECEIPT_SCHEMA = "CODEX_WORK_PACKAGE_VALIDATION_RECEIPT_V0"

STATE_QUEUED = "queued"
STATE_AWAITING_WORKER_BRIDGE = "awaiting_worker_bridge"
STATE_CLAIMED = "claimed"
STATE_IN_PROGRESS = "in_progress"
STATE_RESULT_SUBMITTED = "result_submitted"
STATE_VALIDATION_RUNNING = "validation_running"
STATE_VALIDATION_PASSED = "validation_passed"
STATE_VALIDATION_FAILED = "validation_failed"
STATE_BLOCKED = "blocked"
STATE_READY_FOR_ACTIVATION = "ready_for_activation"
STATE_ACTIVATED = "activated"
STATE_DISABLED = "disabled"

ALLOWED_WORKER_KINDS = (
    "codex_desktop",
    "codex_vscode",
    "codex_cli_if_available",
    "manual_codex_handoff",
)

DENIED_WORKER_KINDS = (
    "unbounded_shell",
    "external_llm_worker",
    "lm2_tool_expansion",
    "business_action_executor",
)

DENIED_ACTIONS = (
    "send_email",
    "delete_email",
    "archive_email",
    "mark_email_read",
    "open_gmail_ui",
    "open_browser",
    "open_safari",
    "coupa_submit",
    "mark_paid",
    "mutate_ledger",
    "mutate_workbook",
    "export_pdf",
    "git_push",
    "git_merge",
    "spawn_worker",
    "invoke_external_model",
    "lm2_tool_expansion",
    "store_secret_in_repo",
)

DENIED_COMMAND_PHRASES = (
    "git push",
    "git merge",
    "send email",
    "open gmail",
    "open browser",
    "open safari",
    "coupa",
    "mark paid",
    "pip install",
    "npm install",
    "curl ",
    "wget ",
    "ollama",
    "lm2",
)

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "gmail_allowed": False,
    "gmail_ui_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "worker_spawn_allowed": False,
    "external_model_allowed": False,
    "lm2_tool_expansion_allowed": False,
    "authority_granted_from_raw_text_allowed": False,
    "sent": False,
    "paid": False,
}

SECRET_PATTERN = re.compile(r"(?i)(api[_-]?key|password|token|secret)\s*[:=]\s*\S+")
METACHARS = set(";|&`><")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _short_hash(*parts: Any, length: int = 16) -> str:
    digest = hashlib.sha256()
    for part in parts:
        value = json.dumps(part, sort_keys=True, ensure_ascii=False) if isinstance(part, (dict, list, tuple)) else str(part)
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:length]


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "package"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS package_states (
          package_id TEXT PRIMARY KEY,
          objective_id TEXT NOT NULL,
          capability_id TEXT NOT NULL,
          state TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          state_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS package_queue (
          queue_id TEXT PRIMARY KEY,
          updated_at TEXT NOT NULL,
          queue_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS worker_bridge_status (
          bridge_id TEXT PRIMARY KEY,
          worker_kind TEXT NOT NULL,
          available INTEGER NOT NULL,
          updated_at TEXT NOT NULL,
          status_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS package_claims (
          claim_id TEXT PRIMARY KEY,
          package_id TEXT NOT NULL,
          claimed_at TEXT NOT NULL,
          claim_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS package_results (
          result_id TEXT PRIMARY KEY,
          package_id TEXT NOT NULL,
          status TEXT NOT NULL,
          submitted_at TEXT NOT NULL,
          result_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS validation_receipts (
          validation_id TEXT PRIMARY KEY,
          package_id TEXT NOT NULL,
          validation_status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          receipt_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS activation_decisions (
          decision_id TEXT PRIMARY KEY,
          package_id TEXT NOT NULL,
          capability_id TEXT NOT NULL,
          decision TEXT NOT NULL,
          created_at TEXT NOT NULL,
          decision_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS capability_registry (
          capability_id TEXT NOT NULL,
          scope_key TEXT NOT NULL,
          status TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          registry_json TEXT NOT NULL,
          PRIMARY KEY (capability_id, scope_key)
        );

        CREATE TABLE IF NOT EXISTS lifecycle_contract (
          read_model_id TEXT PRIMARY KEY,
          generated_at TEXT NOT NULL,
          status TEXT NOT NULL,
          payload_json TEXT NOT NULL
        );
        """
    )


def _connect(sqlite_path: Path) -> sqlite3.Connection:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)
    return conn


def _scope_key(scope: Mapping[str, Any]) -> str:
    return stable_json(dict(scope)).strip()


def _package_dir(package_id: str, package_root: Path) -> Path:
    return Path(package_root) / _safe_id(package_id)


def _package_result_dir(package_id: str, package_root: Path) -> Path:
    return _package_dir(package_id, package_root) / "results"


def _package_files(package_id: str, package_root: Path) -> dict[str, str]:
    directory = _package_dir(package_id, package_root)
    return {
        "package_dir": str(directory),
        "package_json_path": str(directory / "package.json"),
        "prompt_path": str(directory / "prompt.md"),
        "expected_result_schema_path": str(directory / "expected_result_schema.json"),
        "allowed_paths_path": str(directory / "allowed_paths.txt"),
        "denied_paths_path": str(directory / "denied_paths.txt"),
        "validation_commands_path": str(directory / "validation_commands.txt"),
        "unsafe_scan_path": str(directory / "unsafe_scan.txt"),
        "receipts_required_path": str(directory / "receipts_required.md"),
        "result_inbox_path": str(_package_result_dir(package_id, package_root)),
    }


def build_worker_bridge_status(*, package_id: str, package_root: Path, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    files = _package_files(package_id, package_root)
    return {
        "schema_version": WORKER_BRIDGE_STATUS_SCHEMA,
        "bridge_id": "codex_worker_bridge:manual_codex_handoff",
        "worker_kind": "manual_codex_handoff",
        "available": True,
        "claim_path": files["package_dir"],
        "result_path": files["result_inbox_path"],
        "last_seen": generated_at,
        "limitations": [
            "No approved programmatic Codex Desktop or VS Code Codex bridge is configured.",
            "Manual handoff files are available for an operator-approved Codex worker.",
            "No package is executed by this lifecycle.",
        ],
        "human_setup_required": True,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _expected_result_schema() -> dict[str, Any]:
    return {
        "schema_version": PACKAGE_RESULT_SCHEMA,
        "required_fields": [
            "package_id",
            "worker_kind",
            "status",
            "authority_grant_ref",
            "files_changed",
            "commands_run",
            "validation_run",
            "unsafe_scan_summary",
            "receipt_refs",
            "submitted_at",
        ],
        "status_values": ["completed", "blocked", "failed"],
        "notes": [
            "Do not report push, merge, protected external action, or secret handling as completed.",
            "Changed files must stay inside allowed paths.",
        ],
    }


def _prompt_text(package: Mapping[str, Any], objective: Mapping[str, Any]) -> str:
    allowed = "\n".join(f"- {item}" for item in package.get("allowed_file_paths", []))
    denied_paths = "\n".join(f"- {item}" for item in package.get("denied_file_paths", []))
    denied_commands = "\n".join(f"- {item}" for item in package.get("denied_commands", []))
    validation = "\n".join(f"- {item}" for item in package.get("validation_commands", []))
    return "\n".join(
        [
            "# Codex Work Package",
            "",
            "## Objective",
            str(objective.get("operator_goal_text") or objective.get("requested_outcome") or package.get("capability_id") or ""),
            "",
            "## Worktree/root",
            str(package.get("worktree_root") or "/home/openclaw"),
            "",
            "## Allowed files",
            allowed,
            "",
            "## Denied paths",
            denied_paths,
            "",
            "## Denied actions",
            denied_commands,
            "- Do not push.",
            "- Do not merge.",
            "- Do not store secrets.",
            "- Do not send email, open Gmail/browser/Coupa, mark paid, or mutate ledger/workbooks/PDFs.",
            "",
            "## Validation",
            validation,
            "",
            "## Return format",
            "Return a CODEX_WORK_PACKAGE_RESULT_V0 JSON object in the result inbox. Include files_changed, commands_run, validation_run, unsafe_scan_summary, blocker_summary, and receipt_refs.",
            "",
        ]
    )


def write_package_files(
    package: Mapping[str, Any],
    *,
    objective: Mapping[str, Any],
    package_root: Path = DEFAULT_PACKAGE_ROOT,
) -> dict[str, str]:
    files = _package_files(str(package["package_id"]), package_root)
    directory = Path(files["package_dir"])
    directory.mkdir(parents=True, exist_ok=True)
    Path(files["result_inbox_path"]).mkdir(parents=True, exist_ok=True)
    _write_json(Path(files["package_json_path"]), package)
    _write_text(Path(files["prompt_path"]), _prompt_text(package, objective))
    _write_json(Path(files["expected_result_schema_path"]), _expected_result_schema())
    _write_text(Path(files["allowed_paths_path"]), "\n".join(str(item) for item in package.get("allowed_file_paths", [])) + "\n")
    _write_text(Path(files["denied_paths_path"]), "\n".join(str(item) for item in package.get("denied_file_paths", [])) + "\n")
    _write_text(Path(files["validation_commands_path"]), "\n".join(str(item) for item in package.get("validation_commands", [])) + "\n")
    _write_text(Path(files["unsafe_scan_path"]), str(package.get("unsafe_scan") or "required") + "\n")
    _write_text(Path(files["receipts_required_path"]), "Result receipt, validation receipt, unsafe scan summary, activation decision.\n")
    return files


def build_package_state(
    package: Mapping[str, Any],
    *,
    state: str,
    authority_grant_ref: str,
    package_files: Mapping[str, Any],
    blocker_ref: str = "",
    result_ref: str = "",
    validation_ref: str = "",
    claimed_by: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": PACKAGE_STATE_SCHEMA,
        "package_id": str(package["package_id"]),
        "objective_id": str(package.get("objective_id") or ""),
        "capability_id": str(package.get("capability_id") or ""),
        "state": state,
        "run_mode": str(package.get("run_mode") or "production"),
        "authority_grant_ref": authority_grant_ref,
        "created_at": str(package.get("created_at") or generated_at),
        "updated_at": generated_at,
        "claimed_by": claimed_by,
        "result_ref": result_ref,
        "validation_ref": validation_ref,
        "blocker_ref": blocker_ref,
        "receipt_ref": f"codex_work_package_state_receipt:{_short_hash(package.get('package_id'), state, generated_at)}",
        "package_files": dict(package_files),
        "package_json": dict(package),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_package_queue(states: Sequence[Mapping[str, Any]], *, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    active = [state for state in states if state.get("state") not in {STATE_ACTIVATED, STATE_DISABLED}]
    return {
        "schema_version": PACKAGE_QUEUE_SCHEMA,
        "queue_id": "codex_work_package_queue:make_it_so",
        "package_refs": [str(state.get("package_id") or "") for state in active],
        "worktree_root": "/home/openclaw",
        "allowed_worker_kinds": list(ALLOWED_WORKER_KINDS),
        "denied_worker_kinds": list(DENIED_WORKER_KINDS),
        "active_package_count": len(active),
        "receipt_ref": f"codex_work_package_queue_receipt:{_short_hash([state.get('package_id') for state in active], generated_at)}",
        "updated_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _store_state(conn: sqlite3.Connection, state: Mapping[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO package_states
        (package_id, objective_id, capability_id, state, updated_at, state_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            state["package_id"],
            state["objective_id"],
            state["capability_id"],
            state["state"],
            state["updated_at"],
            stable_json(state),
        ),
    )


def _store_queue(conn: sqlite3.Connection, queue: Mapping[str, Any]) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO package_queue (queue_id, updated_at, queue_json) VALUES (?, ?, ?)",
        (queue["queue_id"], queue["updated_at"], stable_json(queue)),
    )


def _store_bridge(conn: sqlite3.Connection, bridge: Mapping[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO worker_bridge_status
        (bridge_id, worker_kind, available, updated_at, status_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (bridge["bridge_id"], bridge["worker_kind"], 1 if bridge.get("available") else 0, bridge["last_seen"], stable_json(bridge)),
    )


def _all_states(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT state_json FROM package_states ORDER BY updated_at").fetchall()
    return [json.loads(row["state_json"]) for row in rows]


def queue_codex_work_package(
    package: Mapping[str, Any],
    *,
    objective: Mapping[str, Any],
    authority_grant: Mapping[str, Any],
    enablement_plan: Mapping[str, Any] | None = None,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    package_root: Path = DEFAULT_PACKAGE_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    package_files = write_package_files(package, objective=objective, package_root=package_root)
    blocker_ref = f"codex_worker_bridge_blocker:{_short_hash(package.get('package_id'), 'manual_bridge')}"
    state = build_package_state(
        package,
        state=STATE_AWAITING_WORKER_BRIDGE,
        authority_grant_ref=str(authority_grant.get("grant_id") or ""),
        package_files=package_files,
        blocker_ref=blocker_ref,
        generated_at=generated_at,
    )
    bridge = build_worker_bridge_status(package_id=str(package["package_id"]), package_root=package_root, generated_at=generated_at)
    with _connect(sqlite_path) as conn:
        _store_state(conn, state)
        queue = build_package_queue(_all_states(conn), generated_at=generated_at)
        _store_queue(conn, queue)
        _store_bridge(conn, bridge)
        conn.commit()
    return {
        "schema_version": SCHEMA_VERSION,
        "package_state": state,
        "package_queue": queue,
        "worker_bridge_status": bridge,
        "package_files": package_files,
        "enablement_plan_ref": str((enablement_plan or {}).get("plan_id") or ""),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def load_package_state(package_id: str, *, sqlite_path: Path = DEFAULT_SQLITE_PATH) -> dict[str, Any]:
    with _connect(sqlite_path) as conn:
        row = conn.execute("SELECT state_json FROM package_states WHERE package_id = ?", (package_id,)).fetchone()
    return json.loads(row["state_json"]) if row else {}


def load_lifecycle_for_objective(objective_id: str, *, sqlite_path: Path = DEFAULT_SQLITE_PATH) -> dict[str, Any]:
    with _connect(sqlite_path) as conn:
        row = conn.execute(
            "SELECT state_json FROM package_states WHERE objective_id = ? ORDER BY updated_at DESC LIMIT 1",
            (objective_id,),
        ).fetchone()
        if not row:
            return {}
        state = json.loads(row["state_json"])
        package_id = str(state.get("package_id") or "")
        queue_row = conn.execute("SELECT queue_json FROM package_queue ORDER BY updated_at DESC LIMIT 1").fetchone()
        bridge_row = conn.execute("SELECT status_json FROM worker_bridge_status ORDER BY updated_at DESC LIMIT 1").fetchone()
        result_row = conn.execute(
            "SELECT result_json FROM package_results WHERE package_id = ? ORDER BY submitted_at DESC LIMIT 1",
            (package_id,),
        ).fetchone()
        activation_row = conn.execute(
            "SELECT decision_json FROM activation_decisions WHERE package_id = ? ORDER BY created_at DESC LIMIT 1",
            (package_id,),
        ).fetchone()
    return {
        "schema_version": SCHEMA_VERSION,
        "package_state": state,
        "package_queue": json.loads(queue_row["queue_json"]) if queue_row else {},
        "worker_bridge_status": json.loads(bridge_row["status_json"]) if bridge_row else {},
        "latest_package_result": json.loads(result_row["result_json"]) if result_row else {},
        "latest_activation_decision": json.loads(activation_row["decision_json"]) if activation_row else {},
        "package_files": state.get("package_files") if isinstance(state.get("package_files"), Mapping) else {},
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _inside_allowed_path(path: str, allowed_paths: Sequence[Any]) -> bool:
    normalized = str(path).replace("\\", "/").lstrip("/")
    if normalized.startswith("../") or normalized.startswith("/"):
        return False
    for allowed in allowed_paths:
        allowed_value = str(allowed).replace("\\", "/").lstrip("/")
        if not allowed_value:
            continue
        if allowed_value.endswith("/") and normalized.startswith(allowed_value):
            return True
        if normalized == allowed_value:
            return True
    return False


def _denied_command(command: str) -> str:
    lowered = command.lower()
    if any(char in command for char in METACHARS):
        return "shell_metacharacter_not_allowed"
    for phrase in DENIED_COMMAND_PHRASES:
        if phrase in lowered:
            return f"denied_command:{phrase.strip()}"
    return ""


def _safe_validation_command(command: str, package: Mapping[str, Any]) -> bool:
    command = command.strip()
    listed = {str(item).strip() for item in package.get("validation_commands", [])}
    if command not in listed and command not in set(str(item).strip() for item in package.get("allowed_commands", [])):
        return False
    if _denied_command(command):
        return False
    return command.startswith(("python3 -m py_compile ", "python3 -m json.tool ", "python3 -m pytest tests/")) or command == "git diff --check"


def _run_backend_validation(commands: Sequence[Any], package: Mapping[str, Any], package_files: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    logs: list[dict[str, Any]] = []
    errors: list[str] = []
    log_dir = Path(str(package_files.get("package_dir") or DEFAULT_PACKAGE_ROOT)) / "validation_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    for index, raw_command in enumerate(commands):
        command = str(raw_command).strip()
        if not command:
            continue
        if not _safe_validation_command(command, package):
            errors.append(f"validation_command_not_allowed:{command}")
            continue
        stdout_path = log_dir / f"validation_{index}_stdout.txt"
        stderr_path = log_dir / f"validation_{index}_stderr.txt"
        try:
            completed = subprocess.run(
                shlex.split(command),
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=30,
                shell=False,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"validation_command_failed:{command}")
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text(str(exc), encoding="utf-8")
            continue
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        logs.append(
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            }
        )
        if completed.returncode != 0:
            errors.append(f"validation_command_nonzero:{command}")
    return logs, errors


def _validate_result(result: Mapping[str, Any], state: Mapping[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    package = state.get("package_json") if isinstance(state.get("package_json"), Mapping) else {}
    if str(result.get("authority_grant_ref") or "") != str(state.get("authority_grant_ref") or ""):
        errors.append("authority_grant_mismatch")
    for path in result.get("files_changed", []) if isinstance(result.get("files_changed"), list) else []:
        if not _inside_allowed_path(str(path), package.get("allowed_file_paths", [])):
            errors.append(f"outside_allowed_paths:{path}")
    for action in result.get("denied_actions_reported", []) if isinstance(result.get("denied_actions_reported"), list) else []:
        if str(action) in DENIED_ACTIONS:
            errors.append(f"denied_action_reported:{action}")
    for command in result.get("commands_run", []) if isinstance(result.get("commands_run"), list) else []:
        denied = _denied_command(str(command))
        if denied:
            errors.append(denied)
    for value in result.get("introduced_strings", []) if isinstance(result.get("introduced_strings"), list) else []:
        if SECRET_PATTERN.search(str(value)):
            errors.append("secret_like_string_detected")
            break
    unsafe = result.get("unsafe_scan_summary") if isinstance(result.get("unsafe_scan_summary"), Mapping) else {}
    if unsafe.get("passed") is not True:
        errors.append("unsafe_scan_failed")
    if not result.get("validation_run"):
        errors.append("validation_missing")
    validation_logs, validation_errors = _run_backend_validation(
        result.get("validation_run", []) if isinstance(result.get("validation_run"), list) else [],
        package,
        state.get("package_files") if isinstance(state.get("package_files"), Mapping) else {},
    )
    errors.extend(validation_errors)
    return errors, validation_logs


def build_validation_receipt(
    package_id: str,
    *,
    errors: Sequence[str],
    validation_logs: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": VALIDATION_RECEIPT_SCHEMA,
        "validation_id": f"codex_work_package_validation:{_short_hash(package_id, errors, generated_at)}",
        "package_id": package_id,
        "validation_status": "validation_failed" if errors else "validation_passed",
        "validation_errors": list(errors),
        "validation_logs": [dict(item) for item in validation_logs],
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_activation_decision(
    state: Mapping[str, Any],
    result: Mapping[str, Any],
    validation_receipt: Mapping[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    tests_passed = validation_receipt.get("validation_status") == "validation_passed"
    unsafe_scan = result.get("unsafe_scan_summary") if isinstance(result.get("unsafe_scan_summary"), Mapping) else {}
    unsafe_scan_passed = unsafe_scan.get("passed") is True
    denied_preserved = not result.get("denied_actions_reported")
    production_ready = tests_passed and unsafe_scan_passed and denied_preserved and str(result.get("capability_status") or "") == "production_ready"
    decision = "activate" if production_ready else "blocked"
    return {
        "schema_version": ACTIVATION_DECISION_SCHEMA,
        "decision_id": f"capability_activation_decision:{_short_hash(state.get('package_id'), decision, generated_at)}",
        "capability_id": str(state.get("capability_id") or ""),
        "objective_id": str(state.get("objective_id") or ""),
        "package_id": str(state.get("package_id") or ""),
        "tests_passed": tests_passed,
        "unsafe_scan_passed": unsafe_scan_passed,
        "denied_actions_preserved": denied_preserved,
        "production_ready": production_ready,
        "activation_scope": dict((state.get("package_json") or {}).get("scope") or {}) if isinstance(state.get("package_json"), Mapping) else {},
        "decision": decision,
        "reason": "Validated worker result is safe to activate." if production_ready else "Validation, scan, or authority boundary is incomplete.",
        "receipt_ref": str(validation_receipt.get("validation_id") or ""),
        "created_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _store_result(conn: sqlite3.Connection, result: Mapping[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO package_results
        (result_id, package_id, status, submitted_at, result_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            result["result_id"],
            result["package_id"],
            result["status"],
            result["submitted_at"],
            stable_json(result),
        ),
    )


def _store_validation(conn: sqlite3.Connection, receipt: Mapping[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO validation_receipts
        (validation_id, package_id, validation_status, created_at, receipt_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (receipt["validation_id"], receipt["package_id"], receipt["validation_status"], receipt["created_at"], stable_json(receipt)),
    )


def _store_activation(conn: sqlite3.Connection, decision: Mapping[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO activation_decisions
        (decision_id, package_id, capability_id, decision, created_at, decision_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (decision["decision_id"], decision["package_id"], decision["capability_id"], decision["decision"], decision["created_at"], stable_json(decision)),
    )


def _store_registry(conn: sqlite3.Connection, state: Mapping[str, Any], decision: Mapping[str, Any], *, generated_at: str) -> None:
    package = state.get("package_json") if isinstance(state.get("package_json"), Mapping) else {}
    scope = package.get("scope") if isinstance(package.get("scope"), Mapping) else {}
    status = "production_ready" if decision.get("decision") == "activate" else "build_requested"
    registry = {
        "schema_version": "OPERATOR_CAPABILITY_REGISTRY_V0",
        "capability_id": str(state.get("capability_id") or ""),
        "status": status,
        "approved_scopes": [dict(scope)] if scope else [],
        "allowed_actions": ["read_relevant_email_evidence"] if status == "production_ready" else [],
        "denied_actions": list(DENIED_ACTIONS),
        "run_mode_behavior": {
            "production": "requires separate data-access authority and proof receipts",
            "test_dry_run": "dry-run receipts only",
            "test_live": "test authority only; never production authority",
        },
        "required_receipts": [str(decision.get("receipt_ref") or "")],
        "required_verifier_checks": ["validation_passed", "unsafe_scan_passed", "denied_actions_preserved"],
        "last_test_receipt": str(decision.get("receipt_ref") or ""),
        "last_production_receipt": "",
        "revoked_at": "",
        "updated_at": generated_at,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    conn.execute(
        """
        INSERT OR REPLACE INTO capability_registry
        (capability_id, scope_key, status, updated_at, registry_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (registry["capability_id"], _scope_key(scope), registry["status"], generated_at, stable_json(registry)),
    )


def ingest_worker_result(
    worker_result: Mapping[str, Any],
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    package_id = str(worker_result.get("package_id") or "")
    with _connect(sqlite_path) as conn:
        row = conn.execute("SELECT state_json FROM package_states WHERE package_id = ?", (package_id,)).fetchone()
        if not row:
            state = {
                "schema_version": PACKAGE_STATE_SCHEMA,
                "package_id": package_id,
                "objective_id": "",
                "capability_id": "",
                "state": STATE_BLOCKED,
                "run_mode": "production",
                "authority_grant_ref": "",
                "created_at": generated_at,
                "updated_at": generated_at,
                "claimed_by": "",
                "result_ref": "",
                "validation_ref": "",
                "blocker_ref": "unknown_package_id",
                "receipt_ref": f"codex_work_package_state_receipt:{_short_hash(package_id, 'unknown')}",
                "package_files": {},
                "package_json": {},
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            }
            result = {
                **dict(worker_result),
                "schema_version": PACKAGE_RESULT_SCHEMA,
                "result_id": f"codex_work_package_result:{_short_hash(package_id, generated_at)}",
                "status": "failed",
                "package_id": package_id,
                "submitted_at": str(worker_result.get("submitted_at") or generated_at),
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            }
            validation = build_validation_receipt(package_id, errors=["unknown_package_id"], validation_logs=[], generated_at=generated_at)
            decision = build_activation_decision(state, result, validation, generated_at=generated_at)
            _store_state(conn, state)
            _store_result(conn, result)
            _store_validation(conn, validation)
            _store_activation(conn, decision)
            conn.commit()
            return {"schema_version": SCHEMA_VERSION, "package_result": result, "validation_receipt": validation, "activation_decision": decision, "package_state": state, "authority_boundary": dict(AUTHORITY_BOUNDARY)}
        state = json.loads(row["state_json"])
        errors, validation_logs = _validate_result(worker_result, state)
        result_status = "completed" if not errors and str(worker_result.get("status") or "") == "completed" else "failed"
        result = {
            **dict(worker_result),
            "schema_version": PACKAGE_RESULT_SCHEMA,
            "result_id": f"codex_work_package_result:{_short_hash(package_id, worker_result, generated_at)}",
            "status": result_status,
            "package_id": package_id,
            "submitted_at": str(worker_result.get("submitted_at") or generated_at),
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
        validation = build_validation_receipt(package_id, errors=errors, validation_logs=validation_logs, generated_at=generated_at)
        decision = build_activation_decision(state, result, validation, generated_at=generated_at)
        new_state = dict(state)
        if decision["decision"] == "activate":
            state_value = STATE_ACTIVATED
        elif errors:
            state_value = STATE_VALIDATION_FAILED
        else:
            state_value = STATE_VALIDATION_PASSED
        new_state.update(
            {
                "state": state_value,
                "updated_at": generated_at,
                "result_ref": result["result_id"],
                "validation_ref": validation["validation_id"],
                "blocker_ref": "" if state_value == STATE_ACTIVATED else "validation_failed",
                "receipt_ref": f"codex_work_package_state_receipt:{_short_hash(package_id, state_value, generated_at)}",
            }
        )
        _store_state(conn, new_state)
        _store_result(conn, result)
        _store_validation(conn, validation)
        _store_activation(conn, decision)
        if decision["decision"] == "activate":
            _store_registry(conn, new_state, decision, generated_at=generated_at)
        queue = build_package_queue(_all_states(conn), generated_at=generated_at)
        _store_queue(conn, queue)
        conn.commit()
    return {
        "schema_version": SCHEMA_VERSION,
        "package_result": result,
        "validation_receipt": validation,
        "activation_decision": decision,
        "package_state": new_state,
        "package_queue": queue,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_read_model(*, sqlite_path: Path = DEFAULT_SQLITE_PATH, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    with _connect(sqlite_path) as conn:
        states = _all_states(conn)
        queue_row = conn.execute("SELECT queue_json FROM package_queue ORDER BY updated_at DESC LIMIT 1").fetchone()
        bridge_rows = conn.execute("SELECT status_json FROM worker_bridge_status ORDER BY updated_at DESC").fetchall()
        registry_rows = conn.execute("SELECT registry_json FROM capability_registry ORDER BY updated_at DESC").fetchall()
    queued = [state for state in states if state.get("state") in {STATE_QUEUED, STATE_AWAITING_WORKER_BRIDGE, STATE_CLAIMED, STATE_IN_PROGRESS}]
    blocked = [state for state in states if state.get("state") in {STATE_BLOCKED, STATE_VALIDATION_FAILED, STATE_AWAITING_WORKER_BRIDGE}]
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "contracts": [
            PACKAGE_STATE_SCHEMA,
            PACKAGE_QUEUE_SCHEMA,
            WORKER_BRIDGE_STATUS_SCHEMA,
            PACKAGE_CLAIM_SCHEMA,
            PACKAGE_RESULT_SCHEMA,
            ACTIVATION_DECISION_SCHEMA,
        ],
        "active_objectives": sorted({str(state.get("objective_id") or "") for state in queued if state.get("objective_id")}),
        "queued_packages": queued,
        "blocked_packages": blocked,
        "package_queue": json.loads(queue_row["queue_json"]) if queue_row else build_package_queue(states, generated_at=generated_at),
        "worker_bridge_statuses": [json.loads(row["status_json"]) for row in bridge_rows],
        "capability_registry": [json.loads(row["registry_json"]) for row in registry_rows],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_wiki(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Codex Work Package Lifecycle",
            "",
            f"Status: `{payload['status']}`",
            "",
            "Queues Make-It-So Codex work packages, writes manual handoff files, ingests bounded results, validates them, and records activation decisions.",
            "",
            "- No push or merge.",
            "- No business/client email, Gmail/browser/Coupa, paid, ledger, workbook, or PDF mutation.",
            "- Worker bridge automation is represented honestly; manual handoff is the V0 bridge.",
            "",
        ]
    )


def export_codex_work_package_lifecycle(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    payload = build_read_model(sqlite_path=sqlite_path, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    _write_json(read_model_path, payload)
    wiki = _rooted(wiki_path)
    wiki.parent.mkdir(parents=True, exist_ok=True)
    wiki.write_text(build_wiki(payload), encoding="utf-8")
    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO lifecycle_contract
            (read_model_id, generated_at, status, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (READ_MODEL_ID, str(payload.get("generated_at") or ""), str(payload.get("status") or ""), stable_json(payload)),
        )
        conn.commit()
    bridge_path = ""
    if bridge_root is not None:
        bridge = Path(bridge_root)
        bridge.mkdir(parents=True, exist_ok=True)
        target = bridge / JSON_EXPORT_NAME
        shutil.copy2(read_model_path, target)
        bridge_path = target.as_posix()
    return {
        "status": str(payload["status"]),
        "read_model_path": read_model_path.as_posix(),
        "bridge_path": bridge_path,
        "wiki_path": wiki.as_posix(),
        "sqlite_path": _rooted(sqlite_path).as_posix(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    args = parser.parse_args()
    result = export_codex_work_package_lifecycle(
        export_root=Path(args.export_root),
        bridge_root=Path(args.bridge_root) if args.bridge_root else None,
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
    )
    print(stable_json(result))


if __name__ == "__main__":
    main()
