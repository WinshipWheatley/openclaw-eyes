"""Codex Work Package Lifecycle V0.

Persists bounded CODEX_WORK_PACKAGE_V0 packages through queue, handoff,
result ingestion, validation, and activation decisions. It does not spawn
workers, push/merge, invoke models, open Gmail/browser/Coupa, send email, or
grant authority from raw text.

Canonical LM2 role: OpenClaw canonical worker run registry and result-ingest
spine. Adjacent worker/package modules are contract/support metadata unless
they explicitly queue through this module.
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

import openclaw_agent_role_registry
import read_only_email_lookup_connector


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Codex Work Package Lifecycle.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/codex_work_package_lifecycle.sqlite")
DEFAULT_PACKAGE_ROOT = Path("generated/system_knowledge/work_packages")
LEGACY_PACKAGE_ROOT = Path("/tmp/openclaw-mission-control/codex_work_packages")

SCHEMA_VERSION = "codex_work_package_lifecycle_v0"
READ_MODEL_ID = "codex_work_package_lifecycle"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "OPENCLAW_CODEX_WORK_PACKAGE_LIFECYCLE_READY"
CANONICAL_WORKER_SPINE_SCHEMA_VERSION = "LM2_CANONICAL_SPINE_V0"
LM2_CANONICAL_SPINE_V0 = CANONICAL_WORKER_SPINE_SCHEMA_VERSION
CANONICAL_WORKER_SPINE_ROLE = "OpenClaw canonical worker run registry and result-ingest spine"
CANONICAL_SQLITE_REGISTRY_PATH = DEFAULT_SQLITE_PATH.as_posix()

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
    "pc_codex",
    "mac_codex",
    "gemini",
    "fable",
    "human",
    "local_script",
    "codex_desktop",
    "codex_vscode",
    "openai_codex_cli",
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
DEFAULT_MAX_SOURCES_PER_WORKER_RUN = 6
DEFAULT_WORKER_TIME_BUDGET_SECONDS = 90
PACKAGE_SIZE_CLASSES = ("tiny", "small", "medium", "large", "too_large")


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


def _as_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (list, tuple, set)):
        return [str(value) for value in values if str(value).strip()]
    return [str(values)] if str(values).strip() else []


def _positive_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def estimate_worker_package_size(
    *,
    sources: Sequence[Any],
    goal: str,
    standard: str,
    proof_required: Sequence[Any],
    stop_condition: str,
    context_refs: Sequence[Any] | None = None,
    worker_time_budget_seconds: int = DEFAULT_WORKER_TIME_BUDGET_SECONDS,
    max_sources_per_worker_run: int = DEFAULT_MAX_SOURCES_PER_WORKER_RUN,
) -> dict[str, Any]:
    """Classify package size before a Codex CLI worker is allowed to run."""

    source_list = _as_list(sources)
    context_ref_list = _as_list(context_refs)
    proof_list = _as_list(proof_required)
    estimated_prompt_chars = len(
        "\n".join(
            [
                str(goal or ""),
                str(standard or ""),
                str(stop_condition or ""),
                "\n".join(source_list),
                "\n".join(proof_list),
                "\n".join(context_ref_list),
            ]
        )
    )
    source_count = len(source_list)
    context_refs_count = len(context_ref_list)
    max_sources = _positive_int(max_sources_per_worker_run, DEFAULT_MAX_SOURCES_PER_WORKER_RUN)
    time_budget = _positive_int(worker_time_budget_seconds, DEFAULT_WORKER_TIME_BUDGET_SECONDS)

    if source_count <= 2 and estimated_prompt_chars <= 2500 and context_refs_count <= 2:
        size_class = "tiny"
    elif source_count <= max_sources and estimated_prompt_chars <= 6000:
        size_class = "small"
    elif source_count <= 10 and estimated_prompt_chars <= 12000:
        size_class = "medium"
    elif source_count <= 20 and estimated_prompt_chars <= 24000:
        size_class = "large"
    else:
        size_class = "too_large"

    operator_approval_required = size_class == "medium"
    split_recommended = size_class in {"large", "too_large"} or source_count > max_sources
    cli_dispatch_allowed = size_class in {"tiny", "small"}
    return {
        "estimated_source_count": source_count,
        "estimated_prompt_chars": estimated_prompt_chars,
        "estimated_context_refs_count": context_refs_count,
        "worker_time_budget_seconds": time_budget,
        "package_size_class": size_class,
        "split_recommended": split_recommended,
        "max_sources_per_worker_run": max_sources,
        "operator_approval_required_for_cli": operator_approval_required,
        "cli_dispatch_allowed": cli_dispatch_allowed,
    }


def _safe_source_paths(sources: Sequence[str]) -> list[str]:
    paths: list[str] = []
    for source in sources:
        value = str(source or "").split("#", 1)[0].strip()
        if not value or "://" in value or value.startswith(("/", "~", "../")):
            continue
        if SECRET_PATTERN.search(value):
            continue
        if any(part in value.lower() for part in (".env", "secret", "token", "credential", "password")):
            continue
        paths.append(value)
    return sorted(dict.fromkeys(paths))


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
    full_context_refs = "\n".join(f"- {item}" for item in package.get("full_agent_context_refs", []))
    return "\n".join(
        [
            "# Codex Work Package",
            "",
            "## Agent role",
            f"Requested by: {package.get('requested_by_agent') or 'operator'}",
            f"Owner agent: {package.get('owner_agent') or 'chief'}",
            f"Role context strategy: {package.get('role_context_strategy') or 'compact_role_card'}",
            str(package.get("agent_role_summary") or ""),
            "",
            "Full role context refs:",
            full_context_refs,
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
            "## Worker output discipline",
            f"Package size class: {package.get('package_size_class') or 'unknown'}",
            f"Worker time budget seconds: {package.get('worker_time_budget_seconds') or DEFAULT_WORKER_TIME_BUDGET_SECONDS}",
            "- Emit a valid JSON result first if possible.",
            "- If blocked, return a blocked JSON result.",
            "- If partial, return a partial JSON result with the evidence reviewed so far.",
            "- Never intentionally produce empty output.",
            "- Keep output concise.",
            "- Do not inspect outside bounded sources.",
            "- Do not edit files unless the package explicitly allows edits.",
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


def canonical_spine_metadata() -> dict[str, Any]:
    return {
        "schema_version": CANONICAL_WORKER_SPINE_SCHEMA_VERSION,
        "canonical_spine_id": "lm2_canonical_worker_spine",
        "canonical_spine_file": "codex_work_package_lifecycle.py",
        "sqlite_registry_path": CANONICAL_SQLITE_REGISTRY_PATH,
        "role": CANONICAL_WORKER_SPINE_ROLE,
        "cli_surface": "scripts/openclaw_run.py",
        "task_container": "assignment_loop_contract.py",
        "consult_transport": "openclaw_lm_consult_spine.py",
        "agent_role_registry": "openclaw_agent_role_registry.py",
        "provider_metadata_sources": ["provider_access_catalog.py", "provider_access_auth_status.py"],
        "proof_verifier": "proof_to_response_verifier.py",
        "projection": "watch_desk_feed.py",
        "model_invocation_allowed": False,
        "runtime_mutation_allowed": False,
        "execution_allowed": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _base_worker_package(
    *,
    package_id: str,
    objective_id: str,
    capability_id: str,
    goal: str,
    sources: Sequence[str],
    standard: str,
    proof_required: Sequence[str],
    stop_condition: str,
    worker_kind: str,
    source_ref: str,
    source_schema_version: str,
    created_at: str,
    provider_metadata: Mapping[str, Any] | None = None,
    assignment_loop_ref: str = "",
    lm_consult_request_ref: str = "",
    permission_boundary: Mapping[str, Any] | None = None,
    expected_output_schema: Any = "bounded_worker_result_v0",
    requested_by_agent: str = "operator",
    owner_agent: str = "chief",
    role_context_strategy: str = "compact_role_card",
) -> dict[str, Any]:
    allowed_paths = _safe_source_paths(sources) or ["generated/read_models/"]
    metadata = dict(provider_metadata or {})
    boundary = dict(permission_boundary or {})
    role_context = openclaw_agent_role_registry.package_role_context(
        requested_by_agent=requested_by_agent,
        owner_agent=owner_agent,
        role_context_strategy=role_context_strategy,
        updated_at_utc=created_at,
    )
    context_refs = _as_list(role_context.get("full_context_refs"))
    sizing = estimate_worker_package_size(
        sources=sources,
        goal=goal,
        standard=standard,
        proof_required=proof_required,
        stop_condition=stop_condition,
        context_refs=context_refs,
        worker_time_budget_seconds=_positive_int(
            boundary.get("worker_time_budget_seconds"),
            DEFAULT_WORKER_TIME_BUDGET_SECONDS,
        ),
        max_sources_per_worker_run=_positive_int(
            boundary.get("max_sources_per_worker_run"),
            DEFAULT_MAX_SOURCES_PER_WORKER_RUN,
        ),
    )
    return {
        "schema_version": "CODEX_WORK_PACKAGE_V0",
        "canonical_worker_spine_schema_version": CANONICAL_WORKER_SPINE_SCHEMA_VERSION,
        "package_id": package_id,
        "objective_id": objective_id,
        "capability_id": capability_id,
        "created_at": created_at,
        "run_mode": "test_dry_run",
        "worktree_root": "/home/openclaw",
        "task_type": capability_id,
        "operator_goal_text": goal,
        "requested_outcome": goal,
        "sources": list(sources),
        "standard": standard,
        "proof_required": list(proof_required),
        "stop_condition": stop_condition,
        **role_context,
        "assignment_loop_ref": assignment_loop_ref,
        "lm_consult_request_ref": lm_consult_request_ref,
        "source_ref": source_ref,
        "source_schema_version": source_schema_version,
        "expected_output_schema": expected_output_schema,
        **sizing,
        "provider_access_metadata": {
            "provider": str(metadata.get("provider") or metadata.get("preferred_provider") or "manual"),
            "access_mode": str(metadata.get("access_mode") or "metadata_only"),
            "tool_name": str(metadata.get("tool_name") or ""),
            "worker_kind": str(worker_kind or metadata.get("worker_kind") or "human"),
            "subscription_backed": metadata.get("subscription_backed", "unknown"),
            "api_billing_required": metadata.get("api_billing_required", "unknown"),
            "model_or_capability_route_ref": str(
                metadata.get("model_or_capability_route_ref")
                or metadata.get("preferred_model_class")
                or metadata.get("provider_model_label")
                or ""
            ),
            "metadata_grants_authority": False,
        },
        "permission_boundary": {
            **boundary,
            "advisory_only": True,
            "execution_allowed": False,
            "runtime_mutation_allowed": False,
            "external_action_allowed": False,
            "model_output_runtime_mutation_allowed": False,
        },
        "allowed_file_paths": allowed_paths,
        "denied_file_paths": [".env", ".chief.env", ".google-secrets/", ".config/", "generated/system_knowledge/*.sqlite"],
        "denied_commands": list(DENIED_COMMAND_PHRASES),
        "allowed_commands": ["git diff --check"],
        "validation_commands": ["git diff --check"],
        "unsafe_scan": "required",
        "authority_grant_ref": "",
        "receipt_ref": f"codex_work_package_receipt:{_short_hash(package_id, created_at)}",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "execution_allowed": False,
        "runtime_mutation_allowed": False,
        "external_action_allowed": False,
        "tools_allowed": False,
    }


def create_worker_package_from_assignment_loop(
    assignment_loop: Mapping[str, Any],
    worker_kind: str | None = None,
    dispatch_mode: str | None = None,
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    package_root: Path = DEFAULT_PACKAGE_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    required = ("assignment_id", "goal", "sources", "standard", "permission_boundary", "proof_required", "stop_condition")
    missing = [field for field in required if not assignment_loop.get(field)]
    if assignment_loop.get("schema_version") != "ASSIGNMENT_LOOP_V0":
        missing.append("schema_version")
    if missing:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "blocked_missing_assignment_loop_fields",
            "missing_fields": sorted(set(missing)),
            "queued": False,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    selected_worker = str(worker_kind or assignment_loop.get("worker_type") or "human")
    if selected_worker not in ALLOWED_WORKER_KINDS:
        selected_worker = "human"
    package_id = "codex_work_package:" + _short_hash(
        "assignment_loop",
        assignment_loop.get("assignment_id"),
        selected_worker,
        generated_at,
    )
    package = _base_worker_package(
        package_id=package_id,
        objective_id=str(assignment_loop.get("assignment_id") or ""),
        capability_id="assignment_loop_worker_package",
        goal=str(assignment_loop.get("goal") or ""),
        sources=_as_list(assignment_loop.get("sources")),
        standard=str(assignment_loop.get("standard") or ""),
        proof_required=_as_list(assignment_loop.get("proof_required")),
        stop_condition=str(assignment_loop.get("stop_condition") or ""),
        worker_kind=selected_worker,
        source_ref=str(assignment_loop.get("assignment_id") or ""),
        source_schema_version=str(assignment_loop.get("schema_version") or ""),
        created_at=generated_at,
        provider_metadata={"worker_kind": selected_worker, "access_mode": str(dispatch_mode or "manual_dispatch")},
        assignment_loop_ref=str(assignment_loop.get("assignment_id") or ""),
        permission_boundary=assignment_loop.get("permission_boundary") if isinstance(assignment_loop.get("permission_boundary"), Mapping) else {},
        expected_output_schema=assignment_loop.get("expected_output_schema") or "bounded_worker_result_v0",
        requested_by_agent=str(assignment_loop.get("requested_by") or "operator"),
        owner_agent=str(assignment_loop.get("owner_agent") or "chief"),
        role_context_strategy=str(assignment_loop.get("role_context_strategy") or "compact_role_card"),
    )
    objective = {
        "objective_id": package["objective_id"],
        "operator_goal_text": package["operator_goal_text"],
        "requested_outcome": package["requested_outcome"],
    }
    result = queue_codex_work_package(
        package,
        objective=objective,
        authority_grant={"grant_id": f"no_runtime_authority:{_short_hash(package_id)}"},
        sqlite_path=sqlite_path,
        package_root=package_root,
        generated_at=generated_at,
    )
    result.update(
        {
            "status": "canonical_worker_package_queued",
            "source_adapter": "assignment_loop",
            "assignment_loop_ref": str(assignment_loop.get("assignment_id") or ""),
            "canonical_spine": canonical_spine_metadata(),
        }
    )
    return result


def create_worker_package_from_lm_consult_request(
    lm_consult_request: Mapping[str, Any],
    worker_kind: str | None = None,
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    package_root: Path = DEFAULT_PACKAGE_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    required = (
        "request_id",
        "requested_by_agent",
        "owner_agent",
        "source_context_ref",
        "task_type",
        "consult_kind",
        "preferred_model_class",
        "preferred_provider",
        "expected_output_schema",
    )
    missing = [field for field in required if not lm_consult_request.get(field)]
    if lm_consult_request.get("schema_version") != "LM_CONSULT_REQUEST_V0":
        missing.append("schema_version")
    if missing:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "blocked_invalid_lm_consult_request",
            "missing_fields": sorted(set(missing)),
            "queued": False,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    if any(bool(lm_consult_request.get(key)) for key in ("execution_allowed", "runtime_mutation_allowed", "external_action_allowed", "tools_exposed")):
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "blocked_lm_consult_requested_authority",
            "queued": False,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    selected_worker = str(worker_kind or lm_consult_request.get("preferred_provider") or "human")
    worker_map = {"gemini": "gemini", "openai": "openai_codex_cli", "manual": "human", "local": "local_script"}
    selected_worker = worker_map.get(selected_worker, selected_worker)
    if selected_worker not in ALLOWED_WORKER_KINDS:
        selected_worker = "human"
    request_id = str(lm_consult_request.get("request_id") or "")
    package_id = "codex_work_package:" + _short_hash("lm_consult", request_id, selected_worker, generated_at)
    sources = _as_list(lm_consult_request.get("context_refs")) or [str(lm_consult_request.get("source_context_ref") or "")]
    provider_metadata = {
        "provider": lm_consult_request.get("preferred_provider"),
        "preferred_provider": lm_consult_request.get("preferred_provider"),
        "preferred_model_class": lm_consult_request.get("preferred_model_class"),
        "provider_model_label": lm_consult_request.get("provider_model_label"),
        "worker_kind": selected_worker,
        "access_mode": "lm_consult_metadata_only",
        "subscription_backed": "unknown",
        "api_billing_required": "unknown",
    }
    package = _base_worker_package(
        package_id=package_id,
        objective_id=request_id,
        capability_id="lm_consult_worker_package",
        goal=str(lm_consult_request.get("task_type") or ""),
        sources=sources,
        standard=f"Return {lm_consult_request.get('expected_output_schema')} using only allowed inputs.",
        proof_required=["lm consult request ref", "worker result receipt", "validation receipt"],
        stop_condition=str(lm_consult_request.get("stop_condition") or "Stop after advisory output; do not execute or mutate runtime."),
        worker_kind=selected_worker,
        source_ref=request_id,
        source_schema_version=str(lm_consult_request.get("schema_version") or ""),
        created_at=generated_at,
        provider_metadata=provider_metadata,
        assignment_loop_ref=str(lm_consult_request.get("assignment_loop_ref") or ""),
        lm_consult_request_ref=request_id,
        permission_boundary={
            "advisory_only": True,
            "execution_allowed": False,
            "runtime_mutation_allowed": False,
            "external_action_allowed": False,
        },
        expected_output_schema=lm_consult_request.get("expected_output_schema"),
        requested_by_agent=str(lm_consult_request.get("requested_by_agent") or "operator"),
        owner_agent=str(lm_consult_request.get("owner_agent") or "chief"),
        role_context_strategy=str(lm_consult_request.get("role_context_strategy") or "compact_role_card"),
    )
    objective = {
        "objective_id": package["objective_id"],
        "operator_goal_text": package["operator_goal_text"],
        "requested_outcome": "bounded advisory worker result",
    }
    result = queue_codex_work_package(
        package,
        objective=objective,
        authority_grant={"grant_id": f"no_runtime_authority:{_short_hash(package_id)}"},
        sqlite_path=sqlite_path,
        package_root=package_root,
        generated_at=generated_at,
    )
    result.update(
        {
            "status": "canonical_worker_package_queued",
            "source_adapter": "lm_consult_request",
            "lm_consult_request_ref": request_id,
            "canonical_spine": canonical_spine_metadata(),
        }
    )
    return result


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


def _store_claim(conn: sqlite3.Connection, claim: Mapping[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO package_claims
        (claim_id, package_id, claimed_at, claim_json)
        VALUES (?, ?, ?, ?)
        """,
        (claim["claim_id"], claim["package_id"], claim["claimed_at"], stable_json(claim)),
    )


def _all_states(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT state_json FROM package_states ORDER BY updated_at").fetchall()
    return [json.loads(row["state_json"]) for row in rows]


def _latest_claims(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT claim_json FROM package_claims ORDER BY claimed_at DESC").fetchall()
    return [json.loads(row["claim_json"]) for row in rows]


def _latest_results(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT result_json FROM package_results ORDER BY submitted_at DESC").fetchall()
    return [json.loads(row["result_json"]) for row in rows]


def _latest_validations(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT receipt_json FROM validation_receipts ORDER BY created_at DESC").fetchall()
    return [json.loads(row["receipt_json"]) for row in rows]


def _latest_activation_decisions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT decision_json FROM activation_decisions ORDER BY created_at DESC").fetchall()
    return [json.loads(row["decision_json"]) for row in rows]


def _claim_for_package(claims: Sequence[Mapping[str, Any]], package_id: str) -> dict[str, Any]:
    for claim in claims:
        if str(claim.get("package_id") or "") == package_id:
            return dict(claim)
    return {}


def _result_for_package(results: Sequence[Mapping[str, Any]], package_id: str) -> dict[str, Any]:
    for result in results:
        if str(result.get("package_id") or "") == package_id:
            return dict(result)
    return {}


def _validation_for_package(validations: Sequence[Mapping[str, Any]], package_id: str) -> dict[str, Any]:
    for validation in validations:
        if str(validation.get("package_id") or "") == package_id:
            return dict(validation)
    return {}


def _activation_for_package(decisions: Sequence[Mapping[str, Any]], package_id: str) -> dict[str, Any]:
    for decision in decisions:
        if str(decision.get("package_id") or "") == package_id:
            return dict(decision)
    return {}


def _package_json_exists(files: Mapping[str, Any]) -> bool:
    package_json_path = str(files.get("package_json_path") or "")
    return bool(package_json_path and Path(package_json_path).is_file())


def _legacy_package_files(package_id: str) -> dict[str, str]:
    return _package_files(package_id, LEGACY_PACKAGE_ROOT)


def ensure_package_files_for_state(
    state: Mapping[str, Any],
    *,
    package_root: Path = DEFAULT_PACKAGE_ROOT,
) -> tuple[dict[str, Any], str]:
    """Ensure a package file exists without relying on volatile /tmp storage."""

    updated = dict(state)
    current_files = dict(updated.get("package_files") or {}) if isinstance(updated.get("package_files"), Mapping) else {}
    if _package_json_exists(current_files):
        current_root = str(current_files.get("package_dir") or "")
        requested_root = Path(package_root).as_posix()
        status = "present" if current_root.startswith(requested_root) else "legacy_tmp_present"
        updated["package_file_status"] = status
        return updated, status

    package_id = str(updated.get("package_id") or "")
    legacy_files = _legacy_package_files(package_id)
    if _package_json_exists(legacy_files):
        updated["package_files"] = legacy_files
        updated["package_file_status"] = "legacy_tmp_present"
        return updated, "legacy_tmp_present"

    package = updated.get("package_json") if isinstance(updated.get("package_json"), Mapping) else {}
    if package:
        objective = {
            "objective_id": str(updated.get("objective_id") or package.get("objective_id") or ""),
            "operator_goal_text": str(package.get("operator_goal_text") or package.get("task_type") or package.get("capability_id") or ""),
            "requested_outcome": str(package.get("requested_outcome") or ""),
        }
        files = write_package_files(package, objective=objective, package_root=package_root)
        updated["package_files"] = files
        updated["package_file_status"] = "reemitted_from_sqlite_package_json"
        return updated, "reemitted_from_sqlite_package_json"

    updated["package_file_status"] = "package_file_missing"
    updated["blocker_ref"] = str(updated.get("blocker_ref") or "package_file_missing")
    if str(updated.get("state") or "") not in {STATE_BLOCKED, STATE_VALIDATION_FAILED}:
        updated["state"] = STATE_BLOCKED
    return updated, "package_file_missing"


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


def build_dispatch_claim(
    state: Mapping[str, Any],
    *,
    worker_kind: str,
    dispatched_by: str,
    note: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    package_id = str(state.get("package_id") or "")
    return {
        "schema_version": PACKAGE_CLAIM_SCHEMA,
        "claim_id": f"codex_work_package_claim:{_short_hash(package_id, worker_kind, dispatched_by, generated_at)}",
        "package_id": package_id,
        "worker_kind": worker_kind,
        "dispatched_by": dispatched_by,
        "note": note,
        "claimed_at": generated_at,
        "manual_dispatch_only": True,
        "model_invoked": False,
        "external_api_called": False,
        "approval_created": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def record_dispatch(
    package_id: str,
    worker_kind: str,
    dispatched_by: str,
    note: str = "",
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    package_root: Path = DEFAULT_PACKAGE_ROOT,
    generated_at: str | None = None,
    mark_in_progress: bool = False,
) -> dict[str, Any]:
    """Record a manual package handoff without invoking any worker."""

    generated_at = generated_at or utc_now()
    worker_kind = str(worker_kind or "").strip()
    if worker_kind not in ALLOWED_WORKER_KINDS:
        state = {
            "schema_version": PACKAGE_STATE_SCHEMA,
            "package_id": package_id,
            "state": STATE_BLOCKED,
            "blocker_ref": "unsupported_worker_kind",
            "updated_at": generated_at,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "dispatch_rejected",
            "reason": "unsupported_worker_kind",
            "package_state": state,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }

    with _connect(sqlite_path) as conn:
        row = conn.execute("SELECT state_json FROM package_states WHERE package_id = ?", (package_id,)).fetchone()
        if not row:
            state = {
                "schema_version": PACKAGE_STATE_SCHEMA,
                "package_id": package_id,
                "state": STATE_BLOCKED,
                "blocker_ref": "unknown_package_id",
                "updated_at": generated_at,
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            }
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "dispatch_rejected",
                "reason": "unknown_package_id",
                "package_state": state,
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            }
        state = json.loads(row["state_json"])
        state, package_file_status = ensure_package_files_for_state(state, package_root=package_root)
        claim = build_dispatch_claim(
            state,
            worker_kind=worker_kind,
            dispatched_by=str(dispatched_by or "operator"),
            note=str(note or ""),
            generated_at=generated_at,
        )
        new_state = dict(state)
        previous_state = str(new_state.get("state") or "")
        if previous_state in {
            STATE_QUEUED,
            STATE_AWAITING_WORKER_BRIDGE,
            STATE_VALIDATION_PASSED,
            STATE_CLAIMED,
            STATE_IN_PROGRESS,
        }:
            next_state = STATE_IN_PROGRESS if mark_in_progress else STATE_CLAIMED
            new_state.update(
                {
                    "state": next_state,
                    "updated_at": generated_at,
                    "claimed_by": worker_kind,
                    "claim_ref": claim["claim_id"],
                    "blocker_ref": "" if package_file_status != "package_file_missing" else "package_file_missing",
                    "receipt_ref": f"codex_work_package_state_receipt:{_short_hash(package_id, next_state, generated_at)}",
                    "package_file_status": package_file_status,
                }
            )
        else:
            new_state.update(
                {
                    "updated_at": generated_at,
                    "claimed_by": worker_kind,
                    "claim_ref": claim["claim_id"],
                    "package_file_status": package_file_status,
                }
            )
        _store_claim(conn, claim)
        _store_state(conn, new_state)
        queue = build_package_queue(_all_states(conn), generated_at=generated_at)
        _store_queue(conn, queue)
        conn.commit()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "dispatch_recorded",
        "package_claim": claim,
        "package_state": new_state,
        "package_queue": queue,
        "package_file_status": package_file_status,
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


def _proof_verification_for_result(
    result: Mapping[str, Any],
    state: Mapping[str, Any],
) -> dict[str, Any]:
    package = state.get("package_json") if isinstance(state.get("package_json"), Mapping) else {}
    spec = result.get("proof_verification") if isinstance(result.get("proof_verification"), Mapping) else {}
    bundle = (
        result.get("proof_bundle")
        if isinstance(result.get("proof_bundle"), Mapping)
        else spec.get("proof_bundle")
        if isinstance(spec.get("proof_bundle"), Mapping)
        else package.get("proof_bundle")
        if isinstance(package.get("proof_bundle"), Mapping)
        else {}
    )
    candidate = (
        result.get("candidate_response")
        if isinstance(result.get("candidate_response"), Mapping)
        else result.get("proof_to_response_candidate")
        if isinstance(result.get("proof_to_response_candidate"), Mapping)
        else spec.get("candidate_response")
        if isinstance(spec.get("candidate_response"), Mapping)
        else {}
    )
    required = bool(
        result.get("proof_verification_required")
        or spec.get("required")
        or package.get("proof_verification_required")
        or bundle
        or candidate
    )
    if not required:
        return {
            "schema_version": "LM2_WORKER_PROOF_VERIFICATION_V0",
            "proof_verification_status": "not_required",
            "proof_refs": [],
            "verifier_receipt_refs": [],
            "errors": [],
            "verifier_id": "",
            "fail_closed": False,
        }
    proof_refs = _as_list(result.get("proof_refs")) or _as_list(spec.get("proof_refs")) or _as_list(package.get("proof_required"))
    if not bundle or not candidate:
        return {
            "schema_version": "LM2_WORKER_PROOF_VERIFICATION_V0",
            "proof_verification_status": "blocked",
            "proof_refs": proof_refs,
            "verifier_receipt_refs": [],
            "errors": ["proof_bundle_or_candidate_response_missing"],
            "verifier_id": "proof_to_response_verifier_v0",
            "fail_closed": True,
        }
    try:
        import proof_to_response_verifier

        verifier_result = proof_to_response_verifier.verify_lm_shadow_response(
            candidate,
            bundle,
            read_model_root=DEFAULT_EXPORT_ROOT,
        )
    except Exception as exc:  # pragma: no cover - defensive fail-closed guard
        return {
            "schema_version": "LM2_WORKER_PROOF_VERIFICATION_V0",
            "proof_verification_status": "blocked",
            "proof_refs": proof_refs,
            "verifier_receipt_refs": [],
            "errors": [f"proof_verifier_exception:{type(exc).__name__}"],
            "verifier_id": "proof_to_response_verifier_v0",
            "fail_closed": True,
        }
    passed = bool(verifier_result.get("publishable"))
    errors = _as_list(verifier_result.get("errors"))
    receipt_ref = f"proof_to_response_verifier:{_short_hash(result.get('package_id'), bundle.get('proof_bundle_id'), passed, errors)}"
    return {
        "schema_version": "LM2_WORKER_PROOF_VERIFICATION_V0",
        "proof_verification_status": "passed" if passed else "failed",
        "proof_refs": proof_refs or _as_list(bundle.get("proof_refs")),
        "verifier_receipt_refs": [receipt_ref],
        "errors": errors,
        "verifier_id": str(verifier_result.get("verifier_id") or "proof_to_response_verifier_v0"),
        "proof_bundle_id": str(bundle.get("proof_bundle_id") or ""),
        "fail_closed": not passed,
    }


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
    proof_verification: Mapping[str, Any] | None = None,
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
        "proof_verification": dict(
            proof_verification
            or {
                "schema_version": "LM2_WORKER_PROOF_VERIFICATION_V0",
                "proof_verification_status": "not_required",
                "proof_refs": [],
                "verifier_receipt_refs": [],
                "errors": [],
            }
        ),
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
    requested_production_ready = str(result.get("capability_status") or "") == "production_ready"
    connector_status: dict[str, Any] = {}
    connector_configured = True
    if str(state.get("capability_id") or "") == read_only_email_lookup_connector.CAPABILITY_ID:
        connector_status = read_only_email_lookup_connector.get_connector_status(generated_at=generated_at)
        connector_configured = connector_status.get("configured") is True
    production_ready = tests_passed and unsafe_scan_passed and denied_preserved and requested_production_ready and connector_configured
    decision = "activate" if production_ready else "blocked"
    if requested_production_ready and not connector_configured:
        reason = "Read-only email connector setup is still missing; production activation is held for human setup."
    elif production_ready:
        reason = "Validated worker result is safe to activate."
    else:
        reason = "Validation, scan, or authority boundary is incomplete."
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
        "connector_configured": connector_configured,
        "email_connector_status": connector_status,
        "activation_scope": dict((state.get("package_json") or {}).get("scope") or {}) if isinstance(state.get("package_json"), Mapping) else {},
        "decision": decision,
        "reason": reason,
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
    if decision.get("decision") == "activate":
        status = "production_ready"
    elif str(state.get("capability_id") or "") == read_only_email_lookup_connector.CAPABILITY_ID and decision.get("connector_configured") is False:
        status = "human_setup_required"
    else:
        status = "build_requested"
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
        "email_connector_status": decision.get("email_connector_status") if isinstance(decision.get("email_connector_status"), Mapping) else {},
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
    if registry["capability_id"] == read_only_email_lookup_connector.CAPABILITY_ID:
        legacy_registry = dict(registry)
        legacy_registry["capability_id"] = read_only_email_lookup_connector.LEGACY_CAPABILITY_ID
        legacy_registry["canonical_capability_id"] = read_only_email_lookup_connector.CAPABILITY_ID
        conn.execute(
            """
            INSERT OR REPLACE INTO capability_registry
            (capability_id, scope_key, status, updated_at, registry_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                legacy_registry["capability_id"],
                _scope_key(scope),
                legacy_registry["status"],
                generated_at,
                stable_json(legacy_registry),
            ),
        )


def parse_worker_result_text(raw_text: str) -> tuple[dict[str, Any] | None, str]:
    """Parse worker output as JSON or markdown containing one JSON object."""

    text = str(raw_text or "").strip()
    if not text:
        return None, "empty_worker_result"
    candidates = [text]
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())
    brace_index = text.find("{")
    if brace_index >= 0:
        candidates.append(text[brace_index:])

    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            try:
                parsed, _ = decoder.raw_decode(candidate)
            except json.JSONDecodeError:
                continue
        if isinstance(parsed, Mapping):
            return dict(parsed), ""
        return None, "worker_result_not_json_object"
    return None, "worker_result_json_parse_failed"


def reject_worker_result(
    package_id: str,
    reason: str,
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    with _connect(sqlite_path) as conn:
        row = conn.execute("SELECT state_json FROM package_states WHERE package_id = ?", (package_id,)).fetchone()
        if row:
            state = json.loads(row["state_json"])
            state.update(
                {
                    "state": STATE_VALIDATION_FAILED,
                    "updated_at": generated_at,
                    "result_ref": f"codex_work_package_result:{_short_hash(package_id, reason, generated_at)}",
                    "validation_ref": f"codex_work_package_validation:{_short_hash(package_id, reason, generated_at)}",
                    "blocker_ref": reason,
                    "receipt_ref": f"codex_work_package_state_receipt:{_short_hash(package_id, 'result_rejected', generated_at)}",
                }
            )
        else:
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
                "blocker_ref": reason or "unknown_package_id",
                "receipt_ref": f"codex_work_package_state_receipt:{_short_hash(package_id, reason, generated_at)}",
                "package_files": {},
                "package_json": {},
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            }
        result = {
            "schema_version": PACKAGE_RESULT_SCHEMA,
            "result_id": f"codex_work_package_result:{_short_hash(package_id, reason, generated_at)}",
            "package_id": package_id,
            "worker_kind": "unknown",
            "status": "result_rejected",
            "rejection_reason": reason,
            "submitted_at": generated_at,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
        validation = build_validation_receipt(package_id, errors=[reason], validation_logs=[], generated_at=generated_at)
        decision = build_activation_decision(state, result, validation, generated_at=generated_at)
        _store_state(conn, state)
        _store_result(conn, result)
        _store_validation(conn, validation)
        _store_activation(conn, decision)
        queue = build_package_queue(_all_states(conn), generated_at=generated_at)
        _store_queue(conn, queue)
        conn.commit()
    return {
        "schema_version": SCHEMA_VERSION,
        "package_result": result,
        "validation_receipt": validation,
        "activation_decision": decision,
        "package_state": state,
        "package_queue": queue,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


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
        proof_verification = _proof_verification_for_result(worker_result, state)
        if proof_verification.get("proof_verification_status") in {"failed", "blocked"}:
            proof_errors = _as_list(proof_verification.get("errors"))
            errors.append(
                "proof_verification_failed"
                if proof_verification.get("proof_verification_status") == "failed"
                else "proof_verification_blocked"
            )
            errors.extend(f"proof_verification:{error}" for error in proof_errors)
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
        validation = build_validation_receipt(
            package_id,
            errors=errors,
            validation_logs=validation_logs,
            proof_verification=proof_verification,
            generated_at=generated_at,
        )
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
        if decision["decision"] == "activate" or (not errors and decision.get("connector_configured") is False):
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


def ingest_worker_result_text(
    package_id: str,
    raw_text: str,
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    parsed, reason = parse_worker_result_text(raw_text)
    if parsed is None:
        return reject_worker_result(package_id, reason, sqlite_path=sqlite_path, generated_at=generated_at)
    parsed_package_id = str(parsed.get("package_id") or "")
    if parsed_package_id and parsed_package_id != package_id:
        return reject_worker_result(package_id, "package_id_mismatch", sqlite_path=sqlite_path, generated_at=generated_at)
    parsed["package_id"] = package_id
    return ingest_worker_result(parsed, sqlite_path=sqlite_path, generated_at=generated_at)


WATCH_DESK_STATES = {
    STATE_AWAITING_WORKER_BRIDGE,
    STATE_CLAIMED,
    STATE_IN_PROGRESS,
    STATE_RESULT_SUBMITTED,
    STATE_VALIDATION_FAILED,
    STATE_VALIDATION_PASSED,
    STATE_READY_FOR_ACTIVATION,
    STATE_BLOCKED,
}


def _next_action_for_state(state: Mapping[str, Any], validation: Mapping[str, Any], activation: Mapping[str, Any]) -> str:
    state_value = str(state.get("state") or "")
    if state_value == STATE_AWAITING_WORKER_BRIDGE:
        return "Dispatch this package manually with scripts/openclaw_run.py dispatch; do not invoke a worker automatically."
    if state_value == STATE_CLAIMED:
        return "Wait for the assigned worker output, then ingest the result through scripts/openclaw_run.py ingest."
    if state_value == STATE_IN_PROGRESS:
        return "Monitor the manual worker run and ingest a bounded result when available."
    if state_value == STATE_RESULT_SUBMITTED:
        return "Run lifecycle validation before any activation decision."
    if state_value == STATE_VALIDATION_FAILED:
        errors = validation.get("validation_errors") if isinstance(validation.get("validation_errors"), list) else []
        suffix = f" Latest error: {errors[0]}." if errors else ""
        return "Review the validation failure and request a corrected worker result." + suffix
    if state_value == STATE_VALIDATION_PASSED:
        if activation.get("connector_configured") is False:
            return "Validation passed; complete the missing human connector setup before activation."
        return "Review the validation receipt and decide whether activation is still needed."
    if state_value == STATE_READY_FOR_ACTIVATION:
        return "Review the activation decision through the existing guarded process; do not auto-activate."
    if state_value == STATE_BLOCKED:
        return "Resolve the blocker or regenerate the package from stored package data."
    return "Review lifecycle state and keep execution manual."


def _package_summary(
    state: Mapping[str, Any],
    *,
    claim: Mapping[str, Any],
    result: Mapping[str, Any],
    validation: Mapping[str, Any],
    activation: Mapping[str, Any],
) -> dict[str, Any]:
    package_id = str(state.get("package_id") or "")
    return {
        "package_id": package_id,
        "objective_id": str(state.get("objective_id") or ""),
        "capability_id": str(state.get("capability_id") or ""),
        "state": str(state.get("state") or ""),
        "updated_at": str(state.get("updated_at") or ""),
        "claimed_by": str(state.get("claimed_by") or ""),
        "requested_by_agent": str((state.get("package_json") or {}).get("requested_by_agent") or "") if isinstance(state.get("package_json"), Mapping) else "",
        "owner_agent": str((state.get("package_json") or {}).get("owner_agent") or "") if isinstance(state.get("package_json"), Mapping) else "",
        "agent_role_ref": str((state.get("package_json") or {}).get("agent_role_ref") or "") if isinstance(state.get("package_json"), Mapping) else "",
        "role_context_strategy": str((state.get("package_json") or {}).get("role_context_strategy") or "") if isinstance(state.get("package_json"), Mapping) else "",
        "claim_ref": str(state.get("claim_ref") or claim.get("claim_id") or ""),
        "package_file_status": str(state.get("package_file_status") or ""),
        "package_json_path": str((state.get("package_files") or {}).get("package_json_path") or "") if isinstance(state.get("package_files"), Mapping) else "",
        "latest_result_status": str(result.get("status") or ""),
        "latest_validation_status": str(validation.get("validation_status") or ""),
        "proof_verification_status": str(
            (validation.get("proof_verification") if isinstance(validation.get("proof_verification"), Mapping) else {}).get(
                "proof_verification_status",
                "not_required",
            )
        ),
        "latest_activation_decision": str(activation.get("decision") or ""),
        "next_action": _next_action_for_state(state, validation, activation),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _watch_item_for_package(summary: Mapping[str, Any], *, generated_at: str) -> dict[str, Any] | None:
    state_value = str(summary.get("state") or "")
    if state_value not in WATCH_DESK_STATES:
        return None
    package_id = str(summary.get("package_id") or "")
    if not package_id:
        return None
    urgency = "blocked" if state_value in {STATE_BLOCKED, STATE_VALIDATION_FAILED} else "needs_operator" if state_value in {STATE_AWAITING_WORKER_BRIDGE, STATE_READY_FOR_ACTIVATION} else "watch"
    push_class = "failure" if urgency == "blocked" else "on_demand"
    return {
        "item_id": f"codex_work_package:{_safe_id(package_id)}",
        "lane": "chief_runtime",
        "urgency": urgency,
        "plain_line": f"Worker package {package_id} is {state_value}.",
        "source_receipt_ref": f"generated/read_models/{JSON_EXPORT_NAME}#{package_id}",
        "one_next_safe_action": str(summary.get("next_action") or "Review the package lifecycle state."),
        "push_class": push_class,
        "push_allowed": False,
        "package_id": package_id,
        "status": state_value,
        "occurred_at": str(summary.get("updated_at") or generated_at),
        "state": {
            "package_id": package_id,
            "objective_id": str(summary.get("objective_id") or ""),
            "capability_id": str(summary.get("capability_id") or ""),
            "status": state_value,
            "claimed_by": str(summary.get("claimed_by") or ""),
            "requested_by_agent": str(summary.get("requested_by_agent") or ""),
            "owner_agent": str(summary.get("owner_agent") or ""),
            "agent_role_ref": str(summary.get("agent_role_ref") or ""),
            "package_file_status": str(summary.get("package_file_status") or ""),
            "proof_verification_status": str(summary.get("proof_verification_status") or "not_required"),
            "execution_allowed": False,
            "external_call_allowed": False,
            "approval_created": False,
        },
    }


def build_read_model(
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    package_root: Path = DEFAULT_PACKAGE_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    with _connect(sqlite_path) as conn:
        states = []
        for state in _all_states(conn):
            ensured, _ = ensure_package_files_for_state(state, package_root=package_root)
            if ensured != state:
                _store_state(conn, ensured)
            states.append(ensured)
        if states:
            queue = build_package_queue(states, generated_at=generated_at)
            _store_queue(conn, queue)
        else:
            queue = build_package_queue(states, generated_at=generated_at)
        queue_row = conn.execute("SELECT queue_json FROM package_queue ORDER BY updated_at DESC LIMIT 1").fetchone()
        bridge_rows = conn.execute("SELECT status_json FROM worker_bridge_status ORDER BY updated_at DESC").fetchall()
        registry_rows = conn.execute("SELECT registry_json FROM capability_registry ORDER BY updated_at DESC").fetchall()
        claims = _latest_claims(conn)
        results = _latest_results(conn)
        validations = _latest_validations(conn)
        activation_decisions = _latest_activation_decisions(conn)
        conn.commit()
    queued = [state for state in states if state.get("state") in {STATE_QUEUED, STATE_AWAITING_WORKER_BRIDGE, STATE_CLAIMED, STATE_IN_PROGRESS}]
    blocked = [state for state in states if state.get("state") in {STATE_BLOCKED, STATE_VALIDATION_FAILED, STATE_AWAITING_WORKER_BRIDGE}]
    package_summaries = [
        _package_summary(
            state,
            claim=_claim_for_package(claims, str(state.get("package_id") or "")),
            result=_result_for_package(results, str(state.get("package_id") or "")),
            validation=_validation_for_package(validations, str(state.get("package_id") or "")),
            activation=_activation_for_package(activation_decisions, str(state.get("package_id") or "")),
        )
        for state in states
    ]
    watch_desk_items = [
        item
        for item in (_watch_item_for_package(summary, generated_at=generated_at) for summary in package_summaries)
        if item is not None
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "contracts": [
            CANONICAL_WORKER_SPINE_SCHEMA_VERSION,
            PACKAGE_STATE_SCHEMA,
            PACKAGE_QUEUE_SCHEMA,
            WORKER_BRIDGE_STATUS_SCHEMA,
            PACKAGE_CLAIM_SCHEMA,
            PACKAGE_RESULT_SCHEMA,
            ACTIVATION_DECISION_SCHEMA,
            "LM2_WORKER_PROOF_VERIFICATION_V0",
        ],
        "canonical_spine": canonical_spine_metadata(),
        "package_ids": [str(state.get("package_id") or "") for state in states if state.get("package_id")],
        "counts": {
            "total": len(states),
            "queued": len([state for state in states if state.get("state") == STATE_QUEUED]),
            "awaiting_worker_bridge": len([state for state in states if state.get("state") == STATE_AWAITING_WORKER_BRIDGE]),
            "claimed": len([state for state in states if state.get("state") == STATE_CLAIMED]),
            "in_progress": len([state for state in states if state.get("state") == STATE_IN_PROGRESS]),
            "validation_failed": len([state for state in states if state.get("state") == STATE_VALIDATION_FAILED]),
            "validation_passed": len([state for state in states if state.get("state") == STATE_VALIDATION_PASSED]),
            "ready_for_activation": len([state for state in states if state.get("state") == STATE_READY_FOR_ACTIVATION]),
            "blocked": len([state for state in states if state.get("state") == STATE_BLOCKED]),
        },
        "active_objectives": sorted({str(state.get("objective_id") or "") for state in queued if state.get("objective_id")}),
        "queued_packages": queued,
        "blocked_packages": blocked,
        "package_summaries": package_summaries,
        "waiting_on_operator": [
            summary
            for summary in package_summaries
            if summary.get("state") in {STATE_AWAITING_WORKER_BRIDGE, STATE_READY_FOR_ACTIVATION, STATE_VALIDATION_FAILED, STATE_BLOCKED}
        ],
        "dispatch_records": claims,
        "validation_results": validations,
        "latest_results": results,
        "activation_decisions": activation_decisions,
        "watch_desk_items": watch_desk_items,
        "next_action": "Dispatch waiting packages manually or ingest completed worker results; no automatic model execution is allowed.",
        "package_queue": json.loads(queue_row["queue_json"]) if queue_row else queue,
        "worker_bridge_statuses": [json.loads(row["status_json"]) for row in bridge_rows],
        "capability_registry": [json.loads(row["registry_json"]) for row in registry_rows],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "model_calls_performed": False,
            "external_api_calls_performed": False,
            "approval_created": False,
            "runtime_policy_mutated": False,
            "business_system_mutated": False,
            "push_allowed_false_for_all_watch_items": all(item.get("push_allowed") is False for item in watch_desk_items),
        },
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
    package_root: Path = DEFAULT_PACKAGE_ROOT,
    generated_at: str | None = None,
) -> dict[str, str]:
    payload = build_read_model(sqlite_path=sqlite_path, package_root=package_root, generated_at=generated_at)
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
    parser.add_argument("--package-root", default=str(DEFAULT_PACKAGE_ROOT))
    args = parser.parse_args()
    result = export_codex_work_package_lifecycle(
        export_root=Path(args.export_root),
        bridge_root=Path(args.bridge_root) if args.bridge_root else None,
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        package_root=Path(args.package_root),
    )
    print(stable_json(result))


if __name__ == "__main__":
    main()
