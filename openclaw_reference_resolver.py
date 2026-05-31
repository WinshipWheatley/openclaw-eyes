"""OpenClaw Reference Resolver v0.

Canonical configuration stores stable reference targets. Exported read-models
and SQLite rows store values resolved at export time, such as branch heads,
mirror hashes, latest receipt pointers, and artifact validity.

This module is read-only: it inspects Git refs and hashes files, but it does
not start services, push/fetch/pull, open browsers/accounts, read workbooks,
export PDFs, mutate ledgers, or mutate production state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_SYSTEM_KNOWLEDGE_ROOT = Path("generated/system_knowledge")

SCHEMA_VERSION = "openclaw_reference_resolver_v0"
READ_MODEL_VERSION = "openclaw_reference_resolver_read_model_v0"
JSON_EXPORT_NAME = "openclaw_reference_resolver.json"
OPERATOR_EXPORT_NAME = "openclaw_reference_resolver_OPERATOR.md"
SQLITE_EXPORT_NAME = "openclaw_reference_resolver.sqlite"
SCHEMA_EXPORT_NAME = "openclaw_reference_resolver_SCHEMA.sql"
SEED_EXPORT_NAME = "openclaw_reference_resolver_SEED.sql"

OPENCLAW_EYES_REGISTRY_REVIEW_BRANCH_TARGET_REF = "openclaw_eyes_registry_review_branch"
OPENCLAW_EYES_SYSTEM_KNOWLEDGE_REVIEW_BRANCH_REF = OPENCLAW_EYES_REGISTRY_REVIEW_BRANCH_TARGET_REF
OPENCLAW_EYES_SYSTEM_KNOWLEDGE_REVIEW_BRANCH = "codex/system-knowledge-registry-v0-local"

TARGET_TYPES = (
    "GIT_BRANCH",
    "READ_MODEL_MIRROR",
    "WORKFLOW_RECEIPT",
    "ARTIFACT",
    "SERVICE",
    "FILE_PATH",
    "UNKNOWN",
)

RESOLVED_STATUSES = (
    "RESOLVED",
    "UNREACHABLE",
    "DIRTY",
    "DRIFT",
    "MISSING",
    "UNKNOWN",
)

REQUIRED_SQLITE_TABLES = (
    "reference_target",
    "reference_resolution",
    "reference_dependency",
    "drift_event",
    "resolution_run",
)

NO_AUTHORITY_FLAGS = {
    "metadata_only": True,
    "read_model_only": True,
    "sqlite_registry_only": True,
    "read_only_git_inspection_only": True,
    "git_fetch_pull_push_performed": False,
    "services_started": False,
    "services_modified": False,
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
class ReferenceTargetSpec:
    target_ref: str
    target_type: str
    repo_ref: str = ""
    local_path: str = ""
    remote_url: str = ""
    branch: str = ""
    source_path: str = ""
    bridge_path: str = ""
    receipt_type: str = ""
    artifact_ref: str = ""
    canonical_input: dict[str, Any] | None = None
    refresh_policy: str = "ON_EXPORT"
    owner_component: str = ""
    status: str = "ACTIVE"


@dataclass(frozen=True)
class ReferenceDependencySpec:
    dependency_ref: str
    target_ref: str
    consumer_component: str
    generated_model_path: str
    reason: str


@dataclass(frozen=True)
class ReferenceResolverExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    sqlite_path: str
    schema_sql_path: str
    seed_sql_path: str
    target_count: int
    resolution_count: int
    drift_count: int


DEFAULT_REFERENCE_TARGETS = (
    ReferenceTargetSpec(
        target_ref=OPENCLAW_EYES_REGISTRY_REVIEW_BRANCH_TARGET_REF,
        target_type="GIT_BRANCH",
        repo_ref="openclaw-eyes",
        local_path="/Users/hwinshipwheatley/Eyes",
        remote_url="git@github.com:WinshipWheatley/openclaw-eyes.git",
        branch=OPENCLAW_EYES_SYSTEM_KNOWLEDGE_REVIEW_BRANCH,
        canonical_input={
            "repo_ref": "openclaw-eyes",
            "branch": OPENCLAW_EYES_SYSTEM_KNOWLEDGE_REVIEW_BRANCH,
        },
        refresh_policy="ON_EXPORT",
        owner_component="openclaw_estate_topology_registry",
        status="ACTIVE",
    ),
    ReferenceTargetSpec(
        target_ref="estate_topology_registry_read_model_mirror",
        target_type="READ_MODEL_MIRROR",
        source_path="generated/read_models/openclaw_estate_topology_registry.json",
        bridge_path="/mnt/e/openclaw/generated/read_models/openclaw_estate_topology_registry.json",
        canonical_input={
            "source_path": "generated/read_models/openclaw_estate_topology_registry.json",
            "bridge_path": "/mnt/e/openclaw/generated/read_models/openclaw_estate_topology_registry.json",
        },
        refresh_policy="ON_EXPORT",
        owner_component="openclaw_estate_topology_registry",
        status="ACTIVE",
    ),
)

DEFAULT_REFERENCE_DEPENDENCIES = (
    ReferenceDependencySpec(
        dependency_ref="estate_topology_uses_openclaw_eyes_registry_review_branch",
        target_ref=OPENCLAW_EYES_REGISTRY_REVIEW_BRANCH_TARGET_REF,
        consumer_component="openclaw_estate_topology_registry",
        generated_model_path="generated/read_models/openclaw_estate_topology_registry.json",
        reason="Estate topology stores the branch ref as canonical input and resolves current_head_commit during export.",
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


def _require_target_type(target_type: str) -> str:
    if target_type not in TARGET_TYPES:
        raise ValueError(f"unknown reference target type: {target_type}")
    return target_type


def _require_resolved_status(status: str) -> str:
    if status not in RESOLVED_STATUSES:
        raise ValueError(f"unknown reference resolved status: {status}")
    return status


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _git(args: list[str], *, cwd: str | Path, timeout_seconds: int = 12) -> tuple[int, str, str]:
    if not args or args[0] not in {"rev-parse", "status"}:
        raise ValueError("reference resolver only allows read-only local git inspection commands")
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def reference_target_record(spec: ReferenceTargetSpec) -> dict[str, Any]:
    canonical_input = dict(spec.canonical_input or {})
    if not canonical_input:
        canonical_input = {
            "repo_ref": spec.repo_ref,
            "local_path": spec.local_path,
            "remote_url": spec.remote_url,
            "branch": spec.branch,
            "source_path": spec.source_path,
            "bridge_path": spec.bridge_path,
            "receipt_type": spec.receipt_type,
            "artifact_ref": spec.artifact_ref,
        }
        canonical_input = {key: value for key, value in canonical_input.items() if value}
    return {
        "target_ref": spec.target_ref,
        "target_type": _require_target_type(spec.target_type),
        "repo_ref": spec.repo_ref,
        "local_path": spec.local_path,
        "remote_url": spec.remote_url,
        "branch": spec.branch,
        "source_path": spec.source_path,
        "bridge_path": spec.bridge_path,
        "receipt_type": spec.receipt_type,
        "artifact_ref": spec.artifact_ref,
        "canonical_input_json": stable_json(canonical_input).strip(),
        "refresh_policy": spec.refresh_policy,
        "owner_component": spec.owner_component,
        "status": spec.status,
    }


def reference_dependency_record(spec: ReferenceDependencySpec) -> dict[str, Any]:
    return {
        "dependency_ref": spec.dependency_ref,
        "target_ref": spec.target_ref,
        "consumer_component": spec.consumer_component,
        "generated_model_path": spec.generated_model_path,
        "reason": spec.reason,
    }


def _dirty_status(local_path: str) -> tuple[str, str]:
    path = _rooted(local_path)
    if not path.exists():
        return "UNKNOWN", "local path does not exist"
    code, stdout, stderr = _git(["status", "--porcelain"], cwd=path)
    if code != 0:
        return "UNKNOWN", stderr or "git status failed"
    if stdout:
        return "DIRTY", "working copy has uncommitted or untracked changes"
    return "CLEAN", ""


def _local_branch_head(local_path: str, branch: str) -> tuple[bool, str, str]:
    path = _rooted(local_path)
    if not path.exists():
        return False, "", "local path does not exist"
    for ref in (f"refs/heads/{branch}", branch):
        code, stdout, stderr = _git(["rev-parse", "--verify", ref], cwd=path)
        if code == 0 and stdout:
            return True, stdout.splitlines()[0], ""
    return False, "", f"local branch not reachable: {branch}"


def _resolution_ref(target_ref: str) -> str:
    return f"{target_ref}_resolution"


def _resolution_row(
    *,
    target_ref: str,
    resolved_status: str,
    resolved_value: str,
    resolved_payload: dict[str, Any],
    dirty_status: str,
    error_message: str,
    resolved_at: str,
) -> dict[str, Any]:
    return {
        "resolution_ref": _resolution_ref(target_ref),
        "target_ref": target_ref,
        "resolved_status": _require_resolved_status(resolved_status),
        "resolved_value": resolved_value,
        "resolved_json": stable_json(resolved_payload).strip(),
        "dirty_status": dirty_status,
        "error_message": error_message,
        "resolved_at": resolved_at,
    }


def _resolve_git_branch(spec: ReferenceTargetSpec, *, resolved_at: str) -> dict[str, Any]:
    dirty_status, dirty_error = _dirty_status(spec.local_path)
    reachable, commit, branch_error = _local_branch_head(spec.local_path, spec.branch)
    if not reachable:
        status = "UNREACHABLE"
        error = branch_error or dirty_error
    elif dirty_status == "DIRTY":
        status = "DIRTY"
        error = dirty_error
    else:
        status = "RESOLVED"
        error = ""
    payload = {
        "target_ref": spec.target_ref,
        "target_type": spec.target_type,
        "repo_ref": spec.repo_ref,
        "local_path": spec.local_path,
        "remote_url": spec.remote_url,
        "branch": spec.branch,
        "current_head_commit": commit if reachable else "",
        "reachable": reachable,
        "dirty_status": dirty_status,
        "resolved_status": status,
        "resolved_at": resolved_at,
    }
    return _resolution_row(
        target_ref=spec.target_ref,
        resolved_status=status,
        resolved_value=commit if reachable else "",
        resolved_payload=payload,
        dirty_status=dirty_status,
        error_message=error,
        resolved_at=resolved_at,
    )


def _resolve_read_model_mirror(spec: ReferenceTargetSpec, *, resolved_at: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    source = _rooted(spec.source_path)
    bridge = _rooted(spec.bridge_path)
    source_exists = source.is_file()
    bridge_exists = bridge.is_file()
    source_hash = sha256_file(source) if source_exists else ""
    bridge_hash = sha256_file(bridge) if bridge_exists else ""
    hash_match = bool(source_hash and bridge_hash and source_hash == bridge_hash)
    if source_exists and bridge_exists and not hash_match:
        status = "DRIFT"
        error = "source and bridge hashes differ"
    elif source_exists and bridge_exists:
        status = "RESOLVED"
        error = ""
    elif source_exists or bridge_exists:
        status = "MISSING"
        error = "source or bridge counterpart missing"
    else:
        status = "MISSING"
        error = "source and bridge files missing"
    payload = {
        "target_ref": spec.target_ref,
        "target_type": spec.target_type,
        "source_path": spec.source_path,
        "bridge_path": spec.bridge_path,
        "source_exists": source_exists,
        "bridge_exists": bridge_exists,
        "sha256_source": source_hash,
        "sha256_bridge": bridge_hash,
        "hash_match": hash_match,
        "resolved_status": status,
        "resolved_at": resolved_at,
    }
    drift = None
    if status == "DRIFT":
        drift = {
            "drift_ref": f"{spec.target_ref}_hash_drift",
            "target_ref": spec.target_ref,
            "drift_type": "HASH_MISMATCH",
            "expected_value": source_hash,
            "actual_value": bridge_hash,
            "severity": "HIGH",
            "detected_at": resolved_at,
            "operator_summary": "Generated read-model source and bridge hashes do not match.",
        }
    return (
        _resolution_row(
            target_ref=spec.target_ref,
            resolved_status=status,
            resolved_value=source_hash,
            resolved_payload=payload,
            dirty_status="",
            error_message=error,
            resolved_at=resolved_at,
        ),
        drift,
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_workflow_receipt(spec: ReferenceTargetSpec, *, resolved_at: str) -> dict[str, Any]:
    candidates = [spec.source_path, spec.local_path]
    target_path = next((path for path in candidates if path), "")
    path = _rooted(target_path) if target_path else Path()
    exists = bool(target_path) and path.is_file()
    payload = _read_json_object(path) if exists else {}
    pointer = ""
    if exists:
        pointer = str(
            payload.get("receipt_ref")
            or payload.get("read_model_id")
            or payload.get("source_request_id")
            or ""
        )
    status = "RESOLVED" if pointer else ("MISSING" if target_path else "UNKNOWN")
    resolved_payload = {
        "target_ref": spec.target_ref,
        "target_type": spec.target_type,
        "receipt_type": spec.receipt_type,
        "source_path": target_path,
        "receipt_exists": exists,
        "latest_pointer": pointer,
        "current_pointer": pointer,
        "resolved_status": status,
        "resolved_at": resolved_at,
    }
    return _resolution_row(
        target_ref=spec.target_ref,
        resolved_status=status,
        resolved_value=pointer,
        resolved_payload=resolved_payload,
        dirty_status="",
        error_message="" if pointer else "receipt store missing or pointer unknown",
        resolved_at=resolved_at,
    )


def _resolve_artifact(spec: ReferenceTargetSpec, *, resolved_at: str) -> dict[str, Any]:
    candidate_paths = [spec.local_path, spec.source_path, spec.bridge_path]
    primary = next((_rooted(path) for path in candidate_paths if path and _rooted(path).is_file()), None)
    digest = sha256_file(primary) if primary else ""
    status = "RESOLVED" if primary else "MISSING"
    resolved_payload = {
        "target_ref": spec.target_ref,
        "target_type": spec.target_type,
        "artifact_ref": spec.artifact_ref,
        "local_path": spec.local_path,
        "source_path": spec.source_path,
        "bridge_path": spec.bridge_path,
        "primary_existing_path": primary.as_posix() if primary else "",
        "sha256": digest,
        "validity_status": "VALID" if primary else "MISSING",
        "resolved_status": status,
        "resolved_at": resolved_at,
    }
    return _resolution_row(
        target_ref=spec.target_ref,
        resolved_status=status,
        resolved_value=digest,
        resolved_payload=resolved_payload,
        dirty_status="",
        error_message="" if primary else "artifact path missing",
        resolved_at=resolved_at,
    )


def resolve_reference_target(
    spec: ReferenceTargetSpec,
    *,
    resolved_at: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    _require_target_type(spec.target_type)
    if spec.target_type == "GIT_BRANCH":
        return _resolve_git_branch(spec, resolved_at=resolved_at), None
    if spec.target_type == "READ_MODEL_MIRROR":
        return _resolve_read_model_mirror(spec, resolved_at=resolved_at)
    if spec.target_type == "WORKFLOW_RECEIPT":
        return _resolve_workflow_receipt(spec, resolved_at=resolved_at), None
    if spec.target_type == "ARTIFACT":
        return _resolve_artifact(spec, resolved_at=resolved_at), None
    payload = {
        "target_ref": spec.target_ref,
        "target_type": spec.target_type,
        "resolved_status": "UNKNOWN",
        "resolved_at": resolved_at,
    }
    return (
        _resolution_row(
            target_ref=spec.target_ref,
            resolved_status="UNKNOWN",
            resolved_value="",
            resolved_payload=payload,
            dirty_status="",
            error_message="resolver not implemented for target type",
            resolved_at=resolved_at,
        ),
        None,
    )


def _resolution_run(
    *,
    started_at: str,
    completed_at: str,
    targets_checked: int,
    drift_count: int,
) -> dict[str, Any]:
    return {
        "run_ref": "openclaw_reference_resolver_run",
        "started_at": started_at,
        "completed_at": completed_at,
        "targets_checked": targets_checked,
        "drift_count": drift_count,
        "status": "DRIFT" if drift_count else "RESOLVED",
    }


def build_openclaw_reference_resolver(
    *,
    generated_at: str | None = None,
    reference_targets: tuple[ReferenceTargetSpec, ...] = DEFAULT_REFERENCE_TARGETS,
    reference_dependencies: tuple[ReferenceDependencySpec, ...] = DEFAULT_REFERENCE_DEPENDENCIES,
) -> dict[str, Any]:
    resolved_at = generated_at or utc_now()
    target_rows = [reference_target_record(spec) for spec in reference_targets]
    dependency_rows = [reference_dependency_record(spec) for spec in reference_dependencies]
    resolution_rows: list[dict[str, Any]] = []
    drift_rows: list[dict[str, Any]] = []
    for spec in reference_targets:
        resolution, drift = resolve_reference_target(spec, resolved_at=resolved_at)
        resolution_rows.append(resolution)
        if drift is not None:
            drift_rows.append(drift)
    run_rows = [
        _resolution_run(
            started_at=resolved_at,
            completed_at=resolved_at,
            targets_checked=len(reference_targets),
            drift_count=len(drift_rows),
        )
    ]
    return {
        "schema_version": READ_MODEL_VERSION,
        "contract_schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": resolved_at,
        "purpose": "Persist stable reference targets and resolve volatile values at export time.",
        "rules": [
            "Canonical sources store stable refs.",
            "Generated read-models store resolved values.",
            "Do not manually hardcode branch commit hashes as source truth.",
            "If a repo or branch cannot be reached, mark UNREACHABLE and leave the resolved value blank.",
            "If a working copy is dirty, mark DIRTY.",
            "If source and bridge hashes differ, mark DRIFT.",
        ],
        "target_type_values": list(TARGET_TYPES),
        "resolved_status_values": list(RESOLVED_STATUSES),
        "required_sqlite_tables": list(REQUIRED_SQLITE_TABLES),
        "target_count": len(target_rows),
        "resolution_count": len(resolution_rows),
        "dependency_count": len(dependency_rows),
        "drift_count": len(drift_rows),
        "run_count": len(run_rows),
        "reference_targets": target_rows,
        "reference_resolutions": resolution_rows,
        "reference_dependencies": dependency_rows,
        "drift_events": drift_rows,
        "resolution_runs": run_rows,
        "git_branch_refs": _git_branch_compat_rows(target_rows, resolution_rows),
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def _git_branch_compat_rows(
    target_rows: list[dict[str, Any]],
    resolution_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    targets_by_ref = {row["target_ref"]: row for row in target_rows}
    rows: list[dict[str, Any]] = []
    for resolution in resolution_rows:
        target = targets_by_ref.get(resolution["target_ref"], {})
        if target.get("target_type") != "GIT_BRANCH":
            continue
        resolved_json = json.loads(resolution["resolved_json"])
        rows.append(
            {
                "target_ref": target["target_ref"],
                "repo_ref": target["target_ref"],
                "repo_name": target.get("repo_ref", ""),
                "local_path": target.get("local_path", ""),
                "remote_url": target.get("remote_url", ""),
                "branch": target.get("branch", ""),
                "current_head_commit": resolution["resolved_value"],
                "reachable": resolution["resolved_status"] in {"RESOLVED", "DIRTY"},
                "resolution_status": resolution["resolved_status"],
                "dirty_status": resolution["dirty_status"],
                "dirty": resolution["dirty_status"] == "DIRTY",
                "last_resolved_at": resolution["resolved_at"],
                "resolved_json": resolved_json,
            }
        )
    return rows


def git_branch_ref_by_repo_ref(read_model: dict[str, Any], repo_ref: str) -> dict[str, Any]:
    for row in read_model.get("git_branch_refs", []):
        if row.get("target_ref") == repo_ref or row.get("repo_ref") == repo_ref:
            return dict(row)
    return {
        "target_ref": repo_ref,
        "repo_ref": repo_ref,
        "local_path": "",
        "remote_url": "",
        "branch": "",
        "current_head_commit": "",
        "reachable": False,
        "resolution_status": "UNREACHABLE",
        "dirty_status": "UNKNOWN",
        "dirty": False,
        "last_resolved_at": read_model.get("generated_at", ""),
    }


def sqlite_schema_sql() -> str:
    target_types = ", ".join(f"'{value}'" for value in TARGET_TYPES)
    statuses = ", ".join(f"'{value}'" for value in RESOLVED_STATUSES)
    return f"""CREATE TABLE reference_target (
    target_ref TEXT PRIMARY KEY,
    target_type TEXT NOT NULL CHECK(target_type IN ({target_types})),
    repo_ref TEXT NOT NULL,
    local_path TEXT NOT NULL,
    remote_url TEXT NOT NULL,
    branch TEXT NOT NULL,
    source_path TEXT NOT NULL,
    bridge_path TEXT NOT NULL,
    receipt_type TEXT NOT NULL,
    artifact_ref TEXT NOT NULL,
    canonical_input_json TEXT NOT NULL,
    refresh_policy TEXT NOT NULL,
    owner_component TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE reference_resolution (
    resolution_ref TEXT PRIMARY KEY,
    target_ref TEXT NOT NULL REFERENCES reference_target(target_ref),
    resolved_status TEXT NOT NULL CHECK(resolved_status IN ({statuses})),
    resolved_value TEXT NOT NULL,
    resolved_json TEXT NOT NULL,
    dirty_status TEXT NOT NULL,
    error_message TEXT NOT NULL,
    resolved_at TEXT NOT NULL
);

CREATE TABLE reference_dependency (
    dependency_ref TEXT PRIMARY KEY,
    target_ref TEXT NOT NULL REFERENCES reference_target(target_ref),
    consumer_component TEXT NOT NULL,
    generated_model_path TEXT NOT NULL,
    reason TEXT NOT NULL
);

CREATE TABLE drift_event (
    drift_ref TEXT PRIMARY KEY,
    target_ref TEXT NOT NULL REFERENCES reference_target(target_ref),
    drift_type TEXT NOT NULL,
    expected_value TEXT NOT NULL,
    actual_value TEXT NOT NULL,
    severity TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    operator_summary TEXT NOT NULL
);

CREATE TABLE resolution_run (
    run_ref TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    targets_checked INTEGER NOT NULL,
    drift_count INTEGER NOT NULL,
    status TEXT NOT NULL
);
"""


def _rows_for_sqlite(read_model: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        "reference_target": read_model["reference_targets"],
        "reference_resolution": read_model["reference_resolutions"],
        "reference_dependency": read_model["reference_dependencies"],
        "drift_event": read_model["drift_events"],
        "resolution_run": read_model["resolution_runs"],
    }


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def sqlite_seed_sql(read_model: dict[str, Any]) -> str:
    statements: list[str] = []
    rows_by_table = _rows_for_sqlite(read_model)
    for table in REQUIRED_SQLITE_TABLES:
        for row in rows_by_table[table]:
            columns = list(row)
            statement = (
                f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({', '.join(_sql_literal(row[column]) for column in columns)});"
            )
            statements.append(statement)
    return "\n".join(statements) + "\n"


def create_sqlite_registry(read_model: dict[str, Any], sqlite_path: str | Path) -> None:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    try:
        connection.executescript(sqlite_schema_sql())
        rows_by_table = _rows_for_sqlite(read_model)
        for table in REQUIRED_SQLITE_TABLES:
            for row in rows_by_table[table]:
                columns = list(row)
                placeholders = ", ".join("?" for _ in columns)
                connection.execute(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                    [row[column] for column in columns],
                )
        connection.commit()
    finally:
        connection.close()


def format_operator_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Reference Resolver",
        "",
        "Purpose:",
        "- Keep stable refs in canonical config and resolve volatile values during export.",
        "",
        "Targets:",
    ]
    for target in read_model["reference_targets"]:
        resolution = next(
            row for row in read_model["reference_resolutions"] if row["target_ref"] == target["target_ref"]
        )
        value = resolution["resolved_value"] or "none"
        lines.append(
            f"- `{target['target_ref']}` `{target['target_type']}` -> `{resolution['resolved_status']}` `{value}`."
        )
    if read_model["drift_events"]:
        lines.extend(["", "Drift:"])
        for drift in read_model["drift_events"]:
            lines.append(f"- `{drift['target_ref']}`: {drift['operator_summary']}")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Read-only Git inspection and file hashing only.",
            "- No service, push, browser, email, Coupa, workbook, PDF, ledger, or production action.",
            "",
        ]
    )
    return "\n".join(lines)


def export_openclaw_reference_resolver(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    system_knowledge_root: str | Path = DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    generated_at: str | None = None,
    reference_targets: tuple[ReferenceTargetSpec, ...] = DEFAULT_REFERENCE_TARGETS,
    reference_dependencies: tuple[ReferenceDependencySpec, ...] = DEFAULT_REFERENCE_DEPENDENCIES,
) -> ReferenceResolverExportResult:
    read_root = _rooted(read_model_root)
    system_root = _rooted(system_knowledge_root)
    read_root.mkdir(parents=True, exist_ok=True)
    system_root.mkdir(parents=True, exist_ok=True)
    read_model = build_openclaw_reference_resolver(
        generated_at=generated_at,
        reference_targets=reference_targets,
        reference_dependencies=reference_dependencies,
    )
    json_path = read_root / JSON_EXPORT_NAME
    operator_path = read_root / OPERATOR_EXPORT_NAME
    sqlite_path = system_root / SQLITE_EXPORT_NAME
    schema_path = system_root / SCHEMA_EXPORT_NAME
    seed_path = system_root / SEED_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_operator_read_model(read_model), encoding="utf-8")
    schema_path.write_text(sqlite_schema_sql(), encoding="utf-8")
    seed_path.write_text(sqlite_seed_sql(read_model), encoding="utf-8")
    create_sqlite_registry(read_model, sqlite_path)
    return ReferenceResolverExportResult(
        schema_version=READ_MODEL_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        sqlite_path=_display_path(sqlite_path),
        schema_sql_path=_display_path(schema_path),
        seed_sql_path=_display_path(seed_path),
        target_count=read_model["target_count"],
        resolution_count=read_model["resolution_count"],
        drift_count=read_model["drift_count"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export OpenClaw reference resolver read-model.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--system-knowledge-root", default=str(DEFAULT_SYSTEM_KNOWLEDGE_ROOT))
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_openclaw_reference_resolver(
        read_model_root=args.read_model_root,
        system_knowledge_root=args.system_knowledge_root,
    )
    if args.format == "json":
        payload = json.loads(_rooted(result.json_path).read_text(encoding="utf-8"))
        print(stable_json(payload), end="")
    elif args.format == "operator":
        print(_rooted(result.operator_path).read_text(encoding="utf-8"), end="")
    else:
        print(f"OpenClaw Reference Resolver: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
        print(f"- SQLite: `{result.sqlite_path}`")
        print(f"- Targets: {result.target_count}")
        print(f"- Resolutions: {result.resolution_count}")
        print(f"- Drift events: {result.drift_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
