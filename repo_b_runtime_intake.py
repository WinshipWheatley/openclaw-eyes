"""Repo B Runtime Intake v0 for OpenClaw.

This module inventories the legacy ``openclaw-runtime`` repository as
metadata-only, non-canonical input. It does not run legacy code, promote
modules, read secrets, create client repos, approve actions, or start agents.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger


ROOT = Path(__file__).resolve().parent
REPO_B_INTAKE_VERSION = "repo_b_runtime_intake_v0"
READ_MODEL_VERSION = "repo_b_runtime_intake_read_model_v0"
SOURCE_REPO = "openclaw-runtime"
EXPECTED_REMOTE_SLUG = "WinshipWheatley/openclaw-runtime"
DEFAULT_REPO_B_ROOT = Path("/home/openclaw_external/openclaw-runtime")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "repo_b_runtime_intake.json"
OPERATOR_EXPORT_NAME = "repo_b_runtime_intake_OPERATOR.md"

CANONICAL_STATUS = "non_canonical_until_promoted"
IMPORT_STATUS = "metadata_scanned_only"
MAX_HASH_BYTES = 2_000_000
MAX_CLASSIFICATION_BYTES = 120_000

ALLOWED_TEXT_SUFFIXES = {".py", ".sh", ".md", ".txt", ".json", ".toml", ".yaml", ".yml"}
HASHABLE_SUFFIXES = {".py", ".sh", ".md", ".txt", ".toml", ".yaml", ".yml"}

NO_GO_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "secrets",
    "keys",
    "credentials",
    "private",
    "legal",
    "tax",
    "finance",
    "client",
}
NO_GO_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
}
NO_GO_SUFFIXES = {".pem", ".key", ".p12", ".sqlite", ".db"}
SENSITIVE_NAME_TOKENS = {
    "secret",
    "credential",
    "token",
    "private",
    "keychain",
    "vault",
    "pii",
    "google_access",
    "cpa",
    "tax",
    "legal",
    "finance",
    "financial",
    "billing",
    "invoice",
    "client",
}

STARTUP_NAMES = {
    "start_chief.sh",
    "start_chief_logged.sh",
    "start_openclaw_brains.sh",
    "start_album_brain.sh",
    "loop_supervisor.sh",
    "loop_control.sh",
    "builder_watcher.sh",
    "retry_send_demo_dashboard.sh",
}

NO_AUTHORITY_FLAGS = {
    "repo_b_canonical": False,
    "repo_b_execution_allowed": False,
    "repo_b_imported_as_truth": False,
    "script_execution_allowed": False,
    "service_start_allowed": False,
    "secret_access_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "client_deployment_allowed": False,
    "module_promotion_allowed": False,
    "operator_decision_required": True,
}

REPORT_SECTIONS = {
    "summary",
    "agents",
    "startup",
    "risks",
    "module-candidates",
    "client-candidates",
    "burden-reduction",
    "finance-candidates",
    "music-candidates",
}


@dataclass(frozen=True)
class RepoBFileObservation:
    relative_path: str
    filename: str
    extension: str
    size_bytes: int
    modified_at: str
    sha256: str | None
    file_kind: str
    raw_body_stored: bool
    read_for_classification: bool
    skipped_no_go: bool
    skip_reason: str | None
    text_excerpt: str | None


@dataclass(frozen=True)
class RepoBIntakeResult:
    run_id: str
    db_path: str
    repo_root: str
    source_remote: str
    source_branch: str
    source_commit: str
    scanned_file_count: int
    skipped_no_go_count: int
    python_file_count: int
    shell_script_count: int
    markdown_file_count: int
    startup_script_count: int
    agent_surface_count: int
    module_candidate_count: int
    legacy_runtime_risk_count: int


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


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


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
    remote = _git_value(root, ("remote", "get-url", "origin"))
    branch = _git_value(root, ("branch", "--show-current"))
    commit = _git_value(root, ("rev-parse", "HEAD"))
    return {"source_remote": remote, "source_branch": branch, "source_commit": commit}


def remote_matches_expected(source_remote: str) -> bool:
    normalized = source_remote.rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return normalized.endswith(EXPECTED_REMOTE_SLUG)


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS repo_b_intake_runs (
  run_id TEXT PRIMARY KEY,
  intake_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  repo_root TEXT NOT NULL,
  source_repo TEXT NOT NULL,
  source_remote TEXT NOT NULL,
  source_branch TEXT NOT NULL,
  source_commit TEXT NOT NULL,
  scanned_file_count INTEGER NOT NULL DEFAULT 0,
  python_file_count INTEGER NOT NULL DEFAULT 0,
  shell_script_count INTEGER NOT NULL DEFAULT 0,
  markdown_file_count INTEGER NOT NULL DEFAULT 0,
  task_file_count INTEGER NOT NULL DEFAULT 0,
  startup_script_count INTEGER NOT NULL DEFAULT 0,
  invoked_script_count INTEGER NOT NULL DEFAULT 0,
  skipped_no_go_count INTEGER NOT NULL DEFAULT 0,
  agent_surface_count INTEGER NOT NULL DEFAULT 0,
  legacy_runtime_risk_count INTEGER NOT NULL DEFAULT 0,
  direct_execution_risk_count INTEGER NOT NULL DEFAULT 0,
  module_candidate_count INTEGER NOT NULL DEFAULT 0,
  client_product_candidate_count INTEGER NOT NULL DEFAULT 0,
  finance_candidate_count INTEGER NOT NULL DEFAULT 0,
  music_candidate_count INTEGER NOT NULL DEFAULT 0,
  security_hitl_candidate_count INTEGER NOT NULL DEFAULT 0,
  docs_only_count INTEGER NOT NULL DEFAULT 0,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  promotion_required INTEGER NOT NULL DEFAULT 1,
  source_basis_json TEXT NOT NULL,
  notes TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS repo_b_roots (
  root_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  source_repo TEXT NOT NULL,
  source_remote TEXT NOT NULL,
  source_branch TEXT NOT NULL,
  source_commit TEXT NOT NULL,
  repo_path TEXT NOT NULL,
  canonical_status TEXT NOT NULL,
  import_status TEXT NOT NULL,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  promotion_required INTEGER NOT NULL DEFAULT 1,
  reduces_operator_burden_by TEXT NOT NULL,
  future_home_candidate TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  notes TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES repo_b_intake_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS repo_b_runtime_files (
  file_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  root_id TEXT NOT NULL,
  source_repo TEXT NOT NULL,
  source_remote TEXT NOT NULL,
  source_branch TEXT NOT NULL,
  source_commit TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  filename TEXT NOT NULL,
  extension TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  modified_at TEXT NOT NULL,
  sha256 TEXT,
  file_kind TEXT NOT NULL,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  read_for_classification INTEGER NOT NULL DEFAULT 0,
  skipped_no_go INTEGER NOT NULL DEFAULT 0,
  skip_reason TEXT,
  canonical_status TEXT NOT NULL,
  import_status TEXT NOT NULL,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  promotion_required INTEGER NOT NULL DEFAULT 1,
  reduces_operator_burden_by TEXT NOT NULL,
  future_home_candidate TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(source_commit, relative_path),
  FOREIGN KEY (run_id) REFERENCES repo_b_intake_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS repo_b_runtime_signatures (
  signature_id TEXT PRIMARY KEY,
  file_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  signature_kind TEXT NOT NULL,
  signature_text TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  canonical_status TEXT NOT NULL,
  import_status TEXT NOT NULL,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS repo_b_agent_surfaces (
  surface_id TEXT PRIMARY KEY,
  file_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  surface_kind TEXT NOT NULL,
  confidence TEXT NOT NULL,
  basis TEXT NOT NULL,
  current_mapping TEXT NOT NULL,
  reconciliation_classification TEXT NOT NULL,
  future_architectural_role TEXT NOT NULL,
  burden_reduction TEXT NOT NULL,
  invoked_by_startup INTEGER NOT NULL DEFAULT 0,
  canonical_status TEXT NOT NULL,
  import_status TEXT NOT NULL,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  promotion_required INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS repo_b_startup_surfaces (
  startup_id TEXT PRIMARY KEY,
  file_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  references_json TEXT NOT NULL,
  referenced_count INTEGER NOT NULL DEFAULT 0,
  nohup_detected INTEGER NOT NULL DEFAULT 0,
  background_invocation_detected INTEGER NOT NULL DEFAULT 0,
  legacy_runtime_risk INTEGER NOT NULL DEFAULT 1,
  risk_notes TEXT NOT NULL,
  canonical_status TEXT NOT NULL,
  import_status TEXT NOT NULL,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS repo_b_module_candidates (
  candidate_id TEXT PRIMARY KEY,
  file_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  module_name TEXT NOT NULL,
  candidate_status TEXT NOT NULL,
  future_architectural_role TEXT NOT NULL,
  future_home_candidate TEXT NOT NULL,
  burden_reduction TEXT NOT NULL,
  current_equivalent_exists INTEGER NOT NULL DEFAULT 0,
  operator_review_required INTEGER NOT NULL DEFAULT 1,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  promotion_required INTEGER NOT NULL DEFAULT 1,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS repo_b_safety_findings (
  finding_id TEXT PRIMARY KEY,
  file_id TEXT,
  relative_path TEXT NOT NULL,
  finding_type TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  evidence TEXT NOT NULL,
  operator_review_required INTEGER NOT NULL DEFAULT 1,
  no_go_content_read INTEGER NOT NULL DEFAULT 0,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS repo_b_reconciliation_recommendations (
  recommendation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  candidate_scope TEXT NOT NULL,
  recommended_lane TEXT NOT NULL,
  routed_agent TEXT NOT NULL,
  priority_hint TEXT NOT NULL,
  reduces_operator_burden_by TEXT NOT NULL,
  status TEXT NOT NULL,
  next_safe_move TEXT NOT NULL,
  operator_decision_required INTEGER NOT NULL DEFAULT 1,
  action_created INTEGER NOT NULL DEFAULT 0,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS repo_b_query_receipts (
  query_receipt_id TEXT PRIMARY KEY,
  query_kind TEXT NOT NULL,
  filter_value TEXT,
  result_count INTEGER NOT NULL DEFAULT 0,
  generated_at TEXT NOT NULL,
  raw_body_stored INTEGER NOT NULL DEFAULT 0
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_repo_b_files_kind ON repo_b_runtime_files(file_kind)",
        "CREATE INDEX IF NOT EXISTS idx_repo_b_files_path ON repo_b_runtime_files(relative_path)",
        "CREATE INDEX IF NOT EXISTS idx_repo_b_surfaces_agent ON repo_b_agent_surfaces(agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_repo_b_modules_role ON repo_b_module_candidates(future_architectural_role)",
        "CREATE INDEX IF NOT EXISTS idx_repo_b_findings_type ON repo_b_safety_findings(finding_type)",
    )


def init_repo_b_runtime_intake_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path) if db_path is not None else DEFAULT_DB_PATH
    init_business_ops_ledger(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def repo_b_runtime_intake_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_repo_b_runtime_intake_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name FROM sqlite_master
WHERE type = 'table' AND name LIKE 'repo_b_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _is_no_go_path(relative_path: str) -> tuple[bool, str | None]:
    parts = Path(relative_path).parts
    lower_parts = [part.lower() for part in parts]
    filename = lower_parts[-1] if lower_parts else ""
    suffix = Path(filename).suffix.lower()
    if any(part in NO_GO_DIR_NAMES for part in lower_parts[:-1]):
        return True, "no_go_directory"
    if filename in NO_GO_FILE_NAMES or filename.startswith(".env."):
        return True, "env_file"
    if suffix in NO_GO_SUFFIXES:
        return True, "secret_or_database_suffix"
    if any(token in filename for token in ("credential", "secret", "token", "keychain")):
        return True, "credential_like_filename"
    return False, None


def _is_sensitive_name(relative_path: str) -> bool:
    lowered = relative_path.lower()
    return any(token in lowered for token in SENSITIVE_NAME_TOKENS)


def _file_kind(relative_path: str) -> str:
    path = Path(relative_path)
    lowered = relative_path.lower()
    if "/tests/" in f"/{lowered}" or lowered.startswith("tests/"):
        return "test_file"
    if path.suffix == ".py":
        return "python_script"
    if path.suffix == ".sh":
        return "shell_script"
    if path.suffix == ".md":
        return "markdown_doc"
    if path.suffix == ".txt" or "task" in lowered:
        return "task_file"
    if path.suffix in {".json", ".toml", ".yaml", ".yml"}:
        return "config_metadata"
    return "unknown"


def _safe_hash(path: Path, relative_path: str, size_bytes: int, skipped_no_go: bool) -> str | None:
    if skipped_no_go or size_bytes > MAX_HASH_BYTES:
        return None
    if path.suffix.lower() not in HASHABLE_SUFFIXES:
        return None
    if _is_sensitive_name(relative_path):
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 128), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _read_safe_excerpt(path: Path, relative_path: str, size_bytes: int, skipped_no_go: bool) -> tuple[bool, str | None]:
    if skipped_no_go:
        return False, None
    if path.suffix.lower() not in ALLOWED_TEXT_SUFFIXES:
        return False, None
    if size_bytes > MAX_CLASSIFICATION_BYTES:
        return False, None
    if _is_sensitive_name(relative_path):
        return False, None
    try:
        return True, path.read_text(encoding="utf-8", errors="replace")[:MAX_CLASSIFICATION_BYTES]
    except OSError:
        return False, None


def _observe_file(repo_root: Path, absolute_path: Path) -> RepoBFileObservation:
    relative_path = absolute_path.relative_to(repo_root).as_posix()
    stat = absolute_path.stat()
    skipped_no_go, skip_reason = _is_no_go_path(relative_path)
    size_bytes = int(stat.st_size)
    sha256 = _safe_hash(absolute_path, relative_path, size_bytes, skipped_no_go)
    read_for_classification, text_excerpt = _read_safe_excerpt(absolute_path, relative_path, size_bytes, skipped_no_go)
    return RepoBFileObservation(
        relative_path=relative_path,
        filename=absolute_path.name,
        extension=absolute_path.suffix.lower(),
        size_bytes=size_bytes,
        modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat(),
        sha256=sha256,
        file_kind=_file_kind(relative_path),
        raw_body_stored=False,
        read_for_classification=read_for_classification,
        skipped_no_go=skipped_no_go,
        skip_reason=skip_reason,
        text_excerpt=text_excerpt,
    )


def iter_repo_b_observations(repo_root: str | Path) -> list[RepoBFileObservation]:
    root = Path(repo_root)
    observations: list[RepoBFileObservation] = []
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        relative_current = current_path.relative_to(root).as_posix() if current_path != root else ""
        kept_dirs: list[str] = []
        for dirname in dirs:
            rel_dir = f"{relative_current}/{dirname}".strip("/")
            if dirname.lower() in NO_GO_DIR_NAMES:
                continue
            kept_dirs.append(dirname)
        dirs[:] = kept_dirs
        for filename in files:
            absolute_path = current_path / filename
            try:
                observations.append(_observe_file(root, absolute_path))
            except (OSError, ValueError):
                continue
    return sorted(observations, key=lambda item: item.relative_path)


def _combined_text(observation: RepoBFileObservation) -> str:
    return f"{observation.relative_path}\n{observation.text_excerpt or ''}".lower()


def _agent_id(observation: RepoBFileObservation) -> str:
    text = _combined_text(observation)
    path = observation.relative_path.lower()
    if "cassandra" in text:
        return "cassandra"
    if "guardian" in text or "pii" in path or "hitl" in path or "security" in path:
        return "guardian"
    if "hermes" in text:
        return "hermes"
    if any(token in text for token in ("niles", "producer", "album", "music", "mixer", "fundo")):
        return "niles" if "producer" not in path else "producer"
    if "report_bridge" in text or "report package" in text:
        return "report_bridge"
    if "chief" in text:
        return "chief"
    return "unknown"


def _surface_kind(observation: RepoBFileObservation) -> str:
    text = _combined_text(observation)
    path = observation.relative_path.lower()
    name = observation.filename.lower()
    if "telegram" in text and "listener" in name:
        return "telegram_listener"
    if "listener" in name:
        return "runtime_listener"
    if "watcher" in name:
        return "watcher"
    if "worker" in name:
        return "worker"
    if "scheduler" in name:
        return "scheduler"
    if "approval_bridge" in name:
        return "approval_bridge"
    if "approval_policy" in name or "approval_brain" in name:
        return "approval_policy"
    if "session" in name:
        return "session_manager"
    if "file_io" in name:
        return "file_io"
    if "notify" in name or "sender" in name or "outreach" in name or "whisper" in name:
        return "notification_sender"
    if "memory_worker" in name:
        return "memory_worker"
    if "state_worker" in name:
        return "state_worker"
    if "dashboard" in name:
        return "dashboard"
    if "router" in name or "orchestrator" in path or "supervisor" in name:
        return "orchestrator"
    if "polish_loop" in path:
        return "polish_loop"
    if "skill" in name:
        return "skill_loader"
    if any(token in name for token in ("budget", "billing", "invoice", "financial", "cpa")):
        return "budget_finance"
    if any(token in name for token in ("album", "music", "mixer", "fundo", "producer")):
        return "music_album"
    if any(token in name for token in ("website", "marketing", "brand", "content")):
        return "website_marketing_content"
    if "hitl" in name:
        return "hitl_approval"
    if "pii" in name or "vault" in name:
        return "pii_vault"
    if "google_access" in name or "google" in name:
        return "google_access"
    if "loop" in name or "start_" in name:
        return "runtime_listener"
    return "unknown"


def _future_role(observation: RepoBFileObservation, agent_id: str, surface_kind: str) -> str:
    path = observation.relative_path.lower()
    if observation.skipped_no_go or surface_kind in {"pii_vault", "google_access"}:
        return "security_guardrail_candidate"
    if surface_kind in {"telegram_listener", "runtime_listener", "watcher", "worker", "scheduler", "memory_worker", "state_worker"}:
        return "runtime_service_candidate"
    if surface_kind in {"approval_bridge", "approval_policy", "hitl_approval"}:
        return "security_guardrail_candidate"
    if surface_kind == "budget_finance":
        return "personal_only_candidate"
    if surface_kind == "website_marketing_content":
        return "client_template_candidate"
    if surface_kind == "music_album" or agent_id in {"niles", "producer"}:
        return "reusable_module_candidate"
    if "report" in path:
        return "report_bridge_component_candidate"
    if observation.file_kind == "markdown_doc":
        return "context_pack_component_candidate"
    if observation.file_kind in {"python_script", "shell_script"}:
        return "core_module_candidate"
    return "unknown_review"


def _future_home(observation: RepoBFileObservation, future_role: str) -> str:
    if observation.skipped_no_go:
        return "blocked"
    if future_role in {"core_module_candidate", "security_guardrail_candidate"}:
        return "core"
    if future_role in {"reusable_module_candidate", "report_bridge_component_candidate", "context_pack_component_candidate"}:
        return "module"
    if future_role == "client_template_candidate":
        return "client"
    if future_role == "personal_only_candidate":
        return "personal"
    return "unknown"


def _burden_reduction(observation: RepoBFileObservation, surface_kind: str, future_role: str) -> str:
    text = _combined_text(observation)
    if surface_kind == "budget_finance" or any(token in text for token in ("billing", "invoice", "financial", "budget", "cpa")):
        return "reduces_finance_burden"
    if surface_kind == "website_marketing_content" or future_role == "client_template_candidate" or any(token in text for token in ("website", "marketing", "client", "demo")):
        return "reduces_client_delivery_burden"
    if surface_kind == "music_album" or any(token in text for token in ("album", "music", "producer", "mixer")):
        return "reduces_music_burden"
    if surface_kind in {"runtime_listener", "watcher", "worker", "scheduler", "memory_worker", "state_worker", "orchestrator"}:
        return "reduces_system_maintenance_burden"
    if future_role in {"core_module_candidate", "reusable_module_candidate"}:
        return "reduces_build_burden"
    return "mainly_reference"


def _reconciliation_classification(observation: RepoBFileObservation, surface_kind: str, future_role: str) -> str:
    path = observation.relative_path
    if observation.skipped_no_go:
        return "blocked_no_go"
    if surface_kind in {"telegram_listener", "runtime_listener", "watcher", "worker", "scheduler", "orchestrator"}:
        return "legacy_runtime_risk"
    if surface_kind in {"approval_bridge", "approval_policy", "hitl_approval"}:
        return "candidate_to_wrap"
    if surface_kind in {"budget_finance", "music_album", "website_marketing_content", "pii_vault", "google_access"}:
        return "candidate_to_port"
    if observation.file_kind == "markdown_doc":
        return "docs_only"
    if observation.file_kind == "task_file" or "task" in path.lower():
        return "task_backlog_candidate"
    if future_role == "client_template_candidate":
        return "client_product_candidate"
    if future_role != "unknown_review":
        return "module_registry_candidate"
    return "unknown_review"


def _current_mapping(agent_id: str, surface_kind: str) -> str:
    if agent_id == "chief":
        return "Agent Presence / Agent Runtime Readiness / Work Board / Operator Action Path"
    if agent_id == "cassandra":
        return "Agent Presence / Intent Router / Cassandra communication lane"
    if agent_id == "guardian":
        return "Agent Presence / Guardian safety lane / Operator Action boundaries"
    if agent_id in {"niles", "producer"}:
        return "Agent Lane Registry music_art / Recent File Context / Work Board"
    if agent_id == "hermes":
        return "Agent Lane Registry advisory_synthesis / Steel Thread"
    if agent_id == "report_bridge":
        return "Report Bridge / generated read-model intake"
    if surface_kind in {"approval_bridge", "approval_policy"}:
        return "Operator Action Path"
    return "OpenClaw Core review queue"


def _current_equivalent_exists(observation: RepoBFileObservation) -> bool:
    return (ROOT / observation.filename).exists() or (ROOT / observation.relative_path).exists()


def _startup_references(text: str | None) -> list[str]:
    if not text:
        return []
    matches = re.findall(r"[\w./-]+\.(?:py|sh)", text)
    cleaned: list[str] = []
    for match in matches:
        normalized = match.strip("'\"` ")
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def _is_startup_surface(observation: RepoBFileObservation) -> bool:
    name = observation.filename.lower()
    return name in STARTUP_NAMES or (observation.extension == ".sh" and any(token in name for token in ("start", "loop", "supervisor", "watcher")))


def _risk_signatures(observation: RepoBFileObservation) -> list[tuple[str, str, str]]:
    text = observation.text_excerpt or ""
    lowered = text.lower()
    signatures: list[tuple[str, str, str]] = []
    if observation.skipped_no_go:
        signatures.append(("no_go_metadata_only", "high", observation.skip_reason or "no-go path skipped"))
        return signatures
    checks = (
        ("direct_os_system", "high", "os.system", "os.system reference detected"),
        ("subprocess_reference", "medium", "subprocess", "subprocess reference detected"),
        ("nohup_background", "high", "nohup", "nohup/background runtime invocation detected"),
        ("telegram_direct", "high", "telegram", "Telegram-related source reference detected"),
        ("message_send", "high", "send_message", "direct message send reference detected"),
        ("env_token_reference", "high", "token", "token/env reference detected"),
        ("dotenv_reference", "high", ".env", ".env reference detected"),
        ("state_write_reference", "medium", ".write", "direct write reference detected"),
        ("json_state_write", "medium", "json.dump", "JSON state write reference detected"),
        ("approval_bypass_reference", "high", "bypass", "approval bypass reference detected"),
        ("auto_approval_reference", "high", "auto_approve", "auto approval reference detected"),
        ("broad_scan_reference", "medium", "os.walk", "filesystem walking reference detected"),
        ("cloud_api_reference", "medium", "requests.", "external request reference detected"),
        ("google_access_reference", "high", "google", "Google access reference detected"),
    )
    for finding_type, risk_level, needle, evidence in checks:
        if needle in lowered:
            signatures.append((finding_type, risk_level, evidence))
    if observation.extension == ".sh" and ("&" in text or "nohup" in lowered):
        signatures.append(("background_shell_invocation", "high", "shell background invocation detected"))
    return signatures


def _module_name(observation: RepoBFileObservation) -> str:
    return Path(observation.filename).stem.replace("_", " ").title()


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id FROM repo_b_intake_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row["run_id"] if row else None


def build_repo_b_runtime_intake(
    *,
    db_path: str | Path | None = None,
    repo_root: str | Path = DEFAULT_REPO_B_ROOT,
    run_id: str | None = None,
    require_expected_remote: bool = True,
) -> RepoBIntakeResult:
    repo_root_path = Path(repo_root)
    if not repo_root_path.exists() or not repo_root_path.is_dir():
        raise FileNotFoundError(f"Repo B root not found: {repo_root_path}")
    metadata = repo_metadata(repo_root_path)
    if require_expected_remote and not remote_matches_expected(metadata["source_remote"]):
        raise ValueError(f"Repo B remote does not match {EXPECTED_REMOTE_SLUG}: {metadata['source_remote']}")

    path = init_repo_b_runtime_intake_schema(db_path)
    now = utc_now()
    resolved_run_id = run_id or _row_id("repobrun", metadata["source_commit"], now)
    root_id = "repo_b_openclaw_runtime"
    observations = iter_repo_b_observations(repo_root_path)

    file_kind_counts = Counter(item.file_kind for item in observations if not item.skipped_no_go)
    skipped_no_go_count = sum(1 for item in observations if item.skipped_no_go)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
INSERT INTO repo_b_intake_runs (
  run_id, intake_version, created_at, repo_root, source_repo, source_remote,
  source_branch, source_commit, source_basis_json, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
  intake_version = excluded.intake_version,
  repo_root = excluded.repo_root,
  source_remote = excluded.source_remote,
  source_branch = excluded.source_branch,
  source_commit = excluded.source_commit,
  source_basis_json = excluded.source_basis_json,
  notes = excluded.notes
""".strip(),
            (
                resolved_run_id,
                REPO_B_INTAKE_VERSION,
                now,
                repo_root_path.as_posix(),
                SOURCE_REPO,
                metadata["source_remote"],
                metadata["source_branch"],
                metadata["source_commit"],
                stable_json(
                    {
                        "metadata_only": True,
                        "repo_b_executed": False,
                        "repo_b_canonical": False,
                        "secret_content_read": False,
                        "clone_path": repo_root_path.as_posix(),
                    }
                ),
                "Repo B scanned as non-canonical metadata only; promotion and execution require later operator approval.",
            ),
        )
        conn.execute(
            """
INSERT INTO repo_b_roots (
  root_id, run_id, source_repo, source_remote, source_branch, source_commit,
  repo_path, canonical_status, import_status, execution_allowed,
  promotion_required, reduces_operator_burden_by, future_home_candidate,
  observed_at, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?, ?, ?)
ON CONFLICT(root_id) DO UPDATE SET
  run_id = excluded.run_id,
  source_remote = excluded.source_remote,
  source_branch = excluded.source_branch,
  source_commit = excluded.source_commit,
  repo_path = excluded.repo_path,
  canonical_status = excluded.canonical_status,
  import_status = excluded.import_status,
  execution_allowed = excluded.execution_allowed,
  promotion_required = excluded.promotion_required,
  reduces_operator_burden_by = excluded.reduces_operator_burden_by,
  future_home_candidate = excluded.future_home_candidate,
  observed_at = excluded.observed_at,
  notes = excluded.notes
""".strip(),
            (
                root_id,
                resolved_run_id,
                SOURCE_REPO,
                metadata["source_remote"],
                metadata["source_branch"],
                metadata["source_commit"],
                repo_root_path.as_posix(),
                CANONICAL_STATUS,
                IMPORT_STATUS,
                "reduces_system_maintenance_burden",
                "reference",
                now,
                "Quarantined legacy runtime repository. Metadata map reduces operator memory burden without trusting or running code.",
            ),
        )

        existing_file_ids = [
            row["file_id"]
            for row in conn.execute(
                "SELECT file_id FROM repo_b_runtime_files WHERE source_commit = ?",
                (metadata["source_commit"],),
            ).fetchall()
        ]
        if existing_file_ids:
            placeholders = ",".join("?" for _ in existing_file_ids)
            for table in (
                "repo_b_runtime_signatures",
                "repo_b_agent_surfaces",
                "repo_b_startup_surfaces",
                "repo_b_module_candidates",
                "repo_b_safety_findings",
            ):
                conn.execute(f"DELETE FROM {table} WHERE file_id IN ({placeholders})", tuple(existing_file_ids))
            conn.execute("DELETE FROM repo_b_runtime_files WHERE source_commit = ?", (metadata["source_commit"],))

        invoked_refs: set[str] = set()
        startup_count = 0
        agent_surface_count = 0
        module_candidate_count = 0
        legacy_runtime_risk_count = 0
        direct_execution_risk_count = 0
        client_product_candidate_count = 0
        finance_candidate_count = 0
        music_candidate_count = 0
        security_hitl_candidate_count = 0
        docs_only_count = 0

        for observation in observations:
            agent_id = _agent_id(observation)
            surface_kind = _surface_kind(observation)
            future_role = _future_role(observation, agent_id, surface_kind)
            future_home = _future_home(observation, future_role)
            burden = _burden_reduction(observation, surface_kind, future_role)
            reconciliation = _reconciliation_classification(observation, surface_kind, future_role)
            file_id = _row_id("repobfile", metadata["source_commit"], observation.relative_path)
            conn.execute(
                """
INSERT INTO repo_b_runtime_files (
  file_id, run_id, root_id, source_repo, source_remote, source_branch, source_commit,
  relative_path, filename, extension, size_bytes, modified_at, sha256, file_kind,
  raw_body_stored, read_for_classification, skipped_no_go, skip_reason,
  canonical_status, import_status, execution_allowed, promotion_required,
  reduces_operator_burden_by, future_home_candidate, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?, ?)
ON CONFLICT(source_commit, relative_path) DO UPDATE SET
  run_id = excluded.run_id,
  root_id = excluded.root_id,
  source_remote = excluded.source_remote,
  source_branch = excluded.source_branch,
  filename = excluded.filename,
  extension = excluded.extension,
  size_bytes = excluded.size_bytes,
  modified_at = excluded.modified_at,
  sha256 = excluded.sha256,
  file_kind = excluded.file_kind,
  raw_body_stored = excluded.raw_body_stored,
  read_for_classification = excluded.read_for_classification,
  skipped_no_go = excluded.skipped_no_go,
  skip_reason = excluded.skip_reason,
  canonical_status = excluded.canonical_status,
  import_status = excluded.import_status,
  execution_allowed = excluded.execution_allowed,
  promotion_required = excluded.promotion_required,
  reduces_operator_burden_by = excluded.reduces_operator_burden_by,
  future_home_candidate = excluded.future_home_candidate
""".strip(),
                (
                    file_id,
                    resolved_run_id,
                    root_id,
                    SOURCE_REPO,
                    metadata["source_remote"],
                    metadata["source_branch"],
                    metadata["source_commit"],
                    observation.relative_path,
                    observation.filename,
                    observation.extension,
                    observation.size_bytes,
                    observation.modified_at,
                    observation.sha256,
                    observation.file_kind,
                    _bool(observation.raw_body_stored),
                    _bool(observation.read_for_classification),
                    _bool(observation.skipped_no_go),
                    observation.skip_reason,
                    CANONICAL_STATUS,
                    IMPORT_STATUS,
                    burden,
                    future_home,
                    now,
                ),
            )

            for finding_type, risk_level, evidence in _risk_signatures(observation):
                if finding_type in {
                    "direct_os_system",
                    "subprocess_reference",
                    "nohup_background",
                    "background_shell_invocation",
                    "telegram_direct",
                    "message_send",
                    "env_token_reference",
                    "dotenv_reference",
                    "cloud_api_reference",
                }:
                    direct_execution_risk_count += 1
                conn.execute(
                    """
INSERT OR REPLACE INTO repo_b_safety_findings (
  finding_id, file_id, relative_path, finding_type, risk_level, evidence,
  operator_review_required, no_go_content_read, execution_allowed, created_at
) VALUES (?, ?, ?, ?, ?, ?, 1, 0, 0, ?)
""".strip(),
                    (
                        _row_id("repobfinding", metadata["source_commit"], observation.relative_path, finding_type),
                        file_id,
                        observation.relative_path,
                        finding_type,
                        risk_level,
                        evidence,
                        now,
                    ),
                )
                conn.execute(
                    """
INSERT OR REPLACE INTO repo_b_runtime_signatures (
  signature_id, file_id, relative_path, signature_kind, signature_text,
  risk_level, canonical_status, import_status, raw_body_stored, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
""".strip(),
                    (
                        _row_id("repobsig", metadata["source_commit"], observation.relative_path, finding_type),
                        file_id,
                        observation.relative_path,
                        finding_type,
                        evidence,
                        risk_level,
                        CANONICAL_STATUS,
                        IMPORT_STATUS,
                        now,
                    ),
                )

            startup = _is_startup_surface(observation)
            references = _startup_references(observation.text_excerpt)
            if startup:
                startup_count += 1
                invoked_refs.update(Path(ref).name for ref in references)
                lowered_text = (observation.text_excerpt or "").lower()
                nohup_detected = "nohup" in lowered_text
                background_detected = "&" in (observation.text_excerpt or "") or nohup_detected
                legacy_runtime_risk_count += 1
                conn.execute(
                    """
INSERT OR REPLACE INTO repo_b_startup_surfaces (
  startup_id, file_id, relative_path, references_json, referenced_count,
  nohup_detected, background_invocation_detected, legacy_runtime_risk,
  risk_notes, canonical_status, import_status, execution_allowed, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 0, ?)
""".strip(),
                    (
                        _row_id("repobstart", metadata["source_commit"], observation.relative_path),
                        file_id,
                        observation.relative_path,
                        stable_json(references),
                        len(references),
                        _bool(nohup_detected),
                        _bool(background_detected),
                        "Startup script recorded as legacy runtime risk; not executed.",
                        CANONICAL_STATUS,
                        IMPORT_STATUS,
                        now,
                    ),
                )

            if agent_id != "unknown" or surface_kind != "unknown":
                agent_surface_count += 1
                conn.execute(
                    """
INSERT OR REPLACE INTO repo_b_agent_surfaces (
  surface_id, file_id, relative_path, agent_id, surface_kind, confidence,
  basis, current_mapping, reconciliation_classification,
  future_architectural_role, burden_reduction, invoked_by_startup,
  canonical_status, import_status, execution_allowed, promotion_required,
  created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?)
""".strip(),
                    (
                        _row_id("repobsurface", metadata["source_commit"], observation.relative_path, agent_id, surface_kind),
                        file_id,
                        observation.relative_path,
                        agent_id,
                        surface_kind,
                        "high" if agent_id != "unknown" else "medium",
                        "filename_and_bounded_safe_text" if observation.read_for_classification else "filename_metadata_only",
                        _current_mapping(agent_id, surface_kind),
                        reconciliation,
                        future_role,
                        burden,
                        0,
                        CANONICAL_STATUS,
                        IMPORT_STATUS,
                        now,
                    ),
                )

            if future_role != "unknown_review" or reconciliation in {"candidate_to_port", "candidate_to_wrap", "client_product_candidate", "module_registry_candidate"}:
                module_candidate_count += 1
                if future_role == "client_template_candidate":
                    client_product_candidate_count += 1
                if burden == "reduces_finance_burden":
                    finance_candidate_count += 1
                if burden == "reduces_music_burden":
                    music_candidate_count += 1
                if future_role == "security_guardrail_candidate":
                    security_hitl_candidate_count += 1
                if reconciliation == "docs_only":
                    docs_only_count += 1
                conn.execute(
                    """
INSERT OR REPLACE INTO repo_b_module_candidates (
  candidate_id, file_id, relative_path, agent_id, module_name,
  candidate_status, future_architectural_role, future_home_candidate,
  burden_reduction, current_equivalent_exists, operator_review_required,
  execution_allowed, promotion_required, reason, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 1, ?, ?)
""".strip(),
                    (
                        _row_id("repobcand", metadata["source_commit"], observation.relative_path, future_role),
                        file_id,
                        observation.relative_path,
                        agent_id,
                        _module_name(observation),
                        reconciliation,
                        future_role,
                        future_home,
                        burden,
                        _bool(_current_equivalent_exists(observation)),
                        "Planning metadata only; later lane must review, port, wrap, promote, or block deliberately.",
                        now,
                    ),
                )

        if invoked_refs:
            conn.execute(
                """
UPDATE repo_b_agent_surfaces
SET invoked_by_startup = 1
WHERE file_id IN (
  SELECT file_id FROM repo_b_runtime_files
  WHERE source_commit = ? AND filename IN ({})
)
""".format(",".join("?" for _ in invoked_refs)),
                (metadata["source_commit"], *tuple(invoked_refs)),
            )

        recommendations = _recommendations_from_counts(
            run_id=resolved_run_id,
            startup_count=startup_count,
            finance_candidate_count=finance_candidate_count,
            music_candidate_count=music_candidate_count,
            security_hitl_candidate_count=security_hitl_candidate_count,
            client_product_candidate_count=client_product_candidate_count,
            agent_surface_count=agent_surface_count,
            now=now,
        )
        for recommendation in recommendations:
            conn.execute(
                """
INSERT OR REPLACE INTO repo_b_reconciliation_recommendations (
  recommendation_id, run_id, title, summary, candidate_scope,
  recommended_lane, routed_agent, priority_hint, reduces_operator_burden_by,
  status, next_safe_move, operator_decision_required, action_created,
  execution_allowed, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, ?)
""".strip(),
                (
                    recommendation["recommendation_id"],
                    resolved_run_id,
                    recommendation["title"],
                    recommendation["summary"],
                    recommendation["candidate_scope"],
                    recommendation["recommended_lane"],
                    recommendation["routed_agent"],
                    recommendation["priority_hint"],
                    recommendation["reduces_operator_burden_by"],
                    recommendation["status"],
                    recommendation["next_safe_move"],
                    now,
                ),
            )

        conn.execute(
            """
UPDATE repo_b_intake_runs
SET completed_at = ?, scanned_file_count = ?, python_file_count = ?,
    shell_script_count = ?, markdown_file_count = ?, task_file_count = ?,
    startup_script_count = ?, invoked_script_count = ?, skipped_no_go_count = ?,
    agent_surface_count = ?, legacy_runtime_risk_count = ?,
    direct_execution_risk_count = ?, module_candidate_count = ?,
    client_product_candidate_count = ?, finance_candidate_count = ?,
    music_candidate_count = ?, security_hitl_candidate_count = ?,
    docs_only_count = ?
WHERE run_id = ?
""".strip(),
            (
                utc_now(),
                len(observations),
                file_kind_counts["python_script"],
                file_kind_counts["shell_script"],
                file_kind_counts["markdown_doc"],
                file_kind_counts["task_file"],
                startup_count,
                len(invoked_refs),
                skipped_no_go_count,
                agent_surface_count,
                legacy_runtime_risk_count,
                direct_execution_risk_count,
                module_candidate_count,
                client_product_candidate_count,
                finance_candidate_count,
                music_candidate_count,
                security_hitl_candidate_count,
                docs_only_count,
                resolved_run_id,
            ),
        )
        conn.commit()
        return RepoBIntakeResult(
            run_id=resolved_run_id,
            db_path=path,
            repo_root=repo_root_path.as_posix(),
            source_remote=metadata["source_remote"],
            source_branch=metadata["source_branch"],
            source_commit=metadata["source_commit"],
            scanned_file_count=len(observations),
            skipped_no_go_count=skipped_no_go_count,
            python_file_count=file_kind_counts["python_script"],
            shell_script_count=file_kind_counts["shell_script"],
            markdown_file_count=file_kind_counts["markdown_doc"],
            startup_script_count=startup_count,
            agent_surface_count=agent_surface_count,
            module_candidate_count=module_candidate_count,
            legacy_runtime_risk_count=legacy_runtime_risk_count,
        )
    finally:
        conn.close()


def _recommendations_from_counts(
    *,
    run_id: str,
    startup_count: int,
    finance_candidate_count: int,
    music_candidate_count: int,
    security_hitl_candidate_count: int,
    client_product_candidate_count: int,
    agent_surface_count: int,
    now: str,
) -> list[dict[str, str]]:
    seeds: list[dict[str, str]] = []
    if agent_surface_count:
        seeds.append(
            {
                "recommendation_id": _row_id("repobreco", run_id, "runtime_agent_review"),
                "title": "Review Repo B agent runtime surfaces",
                "summary": "Chief, Cassandra, Guardian, Niles/Producer, and Hermes-like runtime files are now mapped as non-canonical candidates.",
                "candidate_scope": "agent_runtime",
                "recommended_lane": "Agent Runtime Reconciliation v0",
                "routed_agent": "chief",
                "priority_hint": "high",
                "reduces_operator_burden_by": "reduces_system_maintenance_burden",
                "status": "needs_operator_review",
                "next_safe_move": "Compare mapped runtime surfaces against Agent Presence and recovery policy; do not start services.",
            }
        )
    if startup_count:
        seeds.append(
            {
                "recommendation_id": _row_id("repobreco", run_id, "startup_boundary"),
                "title": "Wrap or retire legacy startup scripts",
                "summary": "Repo B startup scripts are legacy runtime risks because they can launch background processes outside current receipts.",
                "candidate_scope": "startup_runtime",
                "recommended_lane": "Legacy Runtime Startup Boundary Review v0",
                "routed_agent": "guardian",
                "priority_hint": "high",
                "reduces_operator_burden_by": "reduces_system_maintenance_burden",
                "status": "needs_operator_review",
                "next_safe_move": "Convert any still-useful startup behavior into fixed recovery actions with receipts, or keep blocked.",
            }
        )
    if finance_candidate_count:
        seeds.append(
            {
                "recommendation_id": _row_id("repobreco", run_id, "finance_invoice"),
                "title": "Review Repo B finance and invoice helpers",
                "summary": "Billing, invoice, budget, CPA, or financial helper filenames were detected as personal/business candidates.",
                "candidate_scope": "finance_business_ops",
                "recommended_lane": "Finance Invoice Helper Reconciliation v0",
                "routed_agent": "chief",
                "priority_hint": "high",
                "reduces_operator_burden_by": "reduces_finance_burden",
                "status": "needs_operator_review",
                "next_safe_move": "Inspect candidates under Guardian boundaries and decide whether a metadata-only finance helper lane should port safe logic.",
            }
        )
    if music_candidate_count:
        seeds.append(
            {
                "recommendation_id": _row_id("repobreco", run_id, "music_album"),
                "title": "Review Repo B music and album helpers as Niles candidates",
                "summary": "Album, mixer, producer, Fundo, and music helper filenames were detected as Niles/music-art candidates.",
                "candidate_scope": "music_art",
                "recommended_lane": "Niles Music Runtime Candidate Review v0",
                "routed_agent": "niles",
                "priority_hint": "normal",
                "reduces_operator_burden_by": "reduces_music_burden",
                "status": "needs_operator_review",
                "next_safe_move": "Classify useful helpers into metadata-only planning modules before any DAW or file-changing behavior.",
            }
        )
    if security_hitl_candidate_count:
        seeds.append(
            {
                "recommendation_id": _row_id("repobreco", run_id, "security_hitl"),
                "title": "Review Repo B HITL, PII, and access-control candidates",
                "summary": "HITL, approval, PII, and Google access surfaces need Guardian review before reuse.",
                "candidate_scope": "security_hitl",
                "recommended_lane": "Guardian HITL Security Reconciliation v0",
                "routed_agent": "guardian",
                "priority_hint": "high",
                "reduces_operator_burden_by": "reduces_system_maintenance_burden",
                "status": "needs_operator_review",
                "next_safe_move": "Keep sensitive surfaces metadata-only and evaluate whether they map to Operator Action gates or remain blocked.",
            }
        )
    if client_product_candidate_count:
        seeds.append(
            {
                "recommendation_id": _row_id("repobreco", run_id, "client_templates"),
                "title": "Review Repo B website and client product candidates",
                "summary": "Website, marketing, brand, and demo surfaces may become future client template candidates after review.",
                "candidate_scope": "client_productization",
                "recommended_lane": "Client Template Candidate Review v0",
                "routed_agent": "chief",
                "priority_hint": "normal",
                "reduces_operator_burden_by": "reduces_client_delivery_burden",
                "status": "needs_operator_review",
                "next_safe_move": "Map candidate files to Project Capsule/module registry without generating client repos yet.",
            }
        )
    return seeds


def build_repo_b_runtime_intake_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
    agent: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    if report not in REPORT_SECTIONS:
        raise ValueError(f"unknown Repo B intake report: {report}")
    path = init_repo_b_runtime_intake_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_run_id(conn)
        if not resolved_run_id:
            return {"status": "no_runs", "report": report, "rows": [], "counts": {}}
        run = dict(conn.execute("SELECT * FROM repo_b_intake_runs WHERE run_id = ?", (resolved_run_id,)).fetchone())
        root = dict(conn.execute("SELECT * FROM repo_b_roots WHERE run_id = ?", (resolved_run_id,)).fetchone())
        counts = _summary_counts(conn, resolved_run_id)
        rows: list[dict[str, Any]]
        if report == "summary":
            rows = _dict_rows(
                conn,
                """
SELECT title, summary, recommended_lane, routed_agent, priority_hint,
       reduces_operator_burden_by, next_safe_move
FROM repo_b_reconciliation_recommendations
WHERE run_id = ?
ORDER BY priority_hint DESC, title
LIMIT 10
""".strip(),
                (resolved_run_id,),
            )
        elif report == "agents":
            sql = """
SELECT agent_id, surface_kind, relative_path, reconciliation_classification,
       future_architectural_role, burden_reduction, invoked_by_startup
FROM repo_b_agent_surfaces
WHERE (? IS NULL OR agent_id = ?)
ORDER BY agent_id, surface_kind, relative_path
LIMIT 80
""".strip()
            rows = _dict_rows(conn, sql, (agent, agent))
        elif report == "startup":
            rows = _dict_rows(
                conn,
                """
SELECT relative_path, referenced_count, nohup_detected,
       background_invocation_detected, risk_notes
FROM repo_b_startup_surfaces
ORDER BY relative_path
""".strip(),
            )
        elif report == "risks":
            rows = _dict_rows(
                conn,
                """
SELECT relative_path, finding_type, risk_level, evidence
FROM repo_b_safety_findings
ORDER BY CASE risk_level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
         relative_path, finding_type
LIMIT 120
""".strip(),
            )
        elif report == "module-candidates":
            rows = _dict_rows(
                conn,
                """
SELECT relative_path, module_name, agent_id, candidate_status,
       future_architectural_role, future_home_candidate, burden_reduction, reason
FROM repo_b_module_candidates
WHERE future_home_candidate IN ('core', 'module', 'personal', 'unknown')
ORDER BY burden_reduction, relative_path
LIMIT 120
""".strip(),
            )
        elif report == "client-candidates":
            rows = _dict_rows(
                conn,
                """
SELECT relative_path, module_name, candidate_status, future_architectural_role,
       burden_reduction, reason
FROM repo_b_module_candidates
WHERE future_architectural_role = 'client_template_candidate'
ORDER BY relative_path
""".strip(),
            )
        elif report == "burden-reduction":
            rows = _dict_rows(
                conn,
                """
SELECT relative_path, module_name, burden_reduction, future_architectural_role,
       candidate_status, reason
FROM repo_b_module_candidates
ORDER BY CASE burden_reduction
  WHEN 'reduces_finance_burden' THEN 0
  WHEN 'reduces_music_burden' THEN 1
  WHEN 'reduces_system_maintenance_burden' THEN 2
  WHEN 'reduces_client_delivery_burden' THEN 3
  WHEN 'reduces_build_burden' THEN 4
  ELSE 5 END,
  relative_path
LIMIT 120
""".strip(),
            )
        elif report == "finance-candidates":
            rows = _dict_rows(
                conn,
                """
SELECT relative_path, module_name, agent_id, candidate_status,
       future_architectural_role, future_home_candidate, burden_reduction, reason
FROM repo_b_module_candidates
WHERE burden_reduction = 'reduces_finance_burden'
ORDER BY relative_path
""".strip(),
            )
        elif report == "music-candidates":
            rows = _dict_rows(
                conn,
                """
SELECT relative_path, module_name, agent_id, candidate_status,
       future_architectural_role, future_home_candidate, burden_reduction, reason
FROM repo_b_module_candidates
WHERE burden_reduction = 'reduces_music_burden'
ORDER BY relative_path
""".strip(),
            )
        conn.execute(
            """
INSERT OR REPLACE INTO repo_b_query_receipts (
  query_receipt_id, query_kind, filter_value, result_count, generated_at, raw_body_stored
) VALUES (?, ?, ?, ?, ?, 0)
""".strip(),
            (_row_id("repobquery", report, agent or "", utc_now()), report, agent, len(rows), utc_now()),
        )
        conn.commit()
        return {
            "status": "ok",
            "report": report,
            "agent": agent,
            "run_id": resolved_run_id,
            "run": run,
            "root": root,
            "counts": counts,
            "rows": rows,
            "no_authority_flags": NO_AUTHORITY_FLAGS,
        }
    finally:
        conn.close()


def _summary_counts(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    run = conn.execute("SELECT * FROM repo_b_intake_runs WHERE run_id = ?", (run_id,)).fetchone()
    if not run:
        return {}
    count_by_agent = {
        row["agent_id"]: row["count"]
        for row in conn.execute(
            """
SELECT agent_id, COUNT(*) AS count
FROM repo_b_agent_surfaces
GROUP BY agent_id
ORDER BY count DESC, agent_id
""".strip()
        ).fetchall()
    }
    count_by_burden = {
        row["burden_reduction"]: row["count"]
        for row in conn.execute(
            """
SELECT burden_reduction, COUNT(*) AS count
FROM repo_b_module_candidates
GROUP BY burden_reduction
ORDER BY count DESC, burden_reduction
""".strip()
        ).fetchall()
    }
    count_by_role = {
        row["future_architectural_role"]: row["count"]
        for row in conn.execute(
            """
SELECT future_architectural_role, COUNT(*) AS count
FROM repo_b_module_candidates
GROUP BY future_architectural_role
ORDER BY count DESC, future_architectural_role
""".strip()
        ).fetchall()
    }
    return {
        "scanned_file_count": run["scanned_file_count"],
        "python_file_count": run["python_file_count"],
        "shell_script_count": run["shell_script_count"],
        "markdown_file_count": run["markdown_file_count"],
        "task_file_count": run["task_file_count"],
        "startup_script_count": run["startup_script_count"],
        "invoked_script_count": run["invoked_script_count"],
        "skipped_no_go_count": run["skipped_no_go_count"],
        "agent_surface_count": run["agent_surface_count"],
        "legacy_runtime_risk_count": run["legacy_runtime_risk_count"],
        "direct_execution_risk_count": run["direct_execution_risk_count"],
        "module_candidate_count": run["module_candidate_count"],
        "client_product_candidate_count": run["client_product_candidate_count"],
        "finance_candidate_count": run["finance_candidate_count"],
        "music_candidate_count": run["music_candidate_count"],
        "security_hitl_candidate_count": run["security_hitl_candidate_count"],
        "docs_only_count": run["docs_only_count"],
        "count_by_agent": count_by_agent,
        "count_by_burden": count_by_burden,
        "count_by_future_role": count_by_role,
    }


def _counts_line(counts: dict[str, Any]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in counts.items())


def format_repo_b_runtime_intake_result(result: RepoBIntakeResult) -> str:
    return "\n".join(
        [
            "Repo B Runtime Intake v0",
            "",
            f"Repo: `{result.repo_root}`",
            f"Remote: `{result.source_remote}`",
            f"Branch: `{result.source_branch}`",
            f"Commit: `{result.source_commit}`",
            f"Run: `{result.run_id}`",
            f"Files scanned: {result.scanned_file_count}",
            f"Python: {result.python_file_count}",
            f"Shell: {result.shell_script_count}",
            f"Markdown: {result.markdown_file_count}",
            f"Startup scripts: {result.startup_script_count}",
            f"Agent surfaces: {result.agent_surface_count}",
            f"Module candidates: {result.module_candidate_count}",
            f"Legacy runtime risks: {result.legacy_runtime_risk_count}",
            "",
            "Boundary:",
            "- Repo B was inventoried as metadata-only and non-canonical.",
            "- No Repo B script was executed and no module was promoted.",
        ]
    )


def format_repo_b_runtime_intake_report(payload: dict[str, Any]) -> str:
    if payload.get("status") == "no_runs":
        return "Repo B Runtime Intake v0\n\nNo Repo B intake runs are recorded."
    root = payload["root"]
    counts = payload["counts"]
    lines = [
        "Repo B Runtime Intake v0",
        "",
        f"Report: `{payload['report']}`",
        f"Repo path: `{root['repo_path']}`",
        f"Remote: `{root['source_remote']}`",
        f"Branch: `{root['source_branch']}`",
        f"Commit: `{root['source_commit']}`",
        f"Canonical status: `{root['canonical_status']}`",
        f"Import status: `{root['import_status']}`",
        "",
        "Counts:",
        f"- Files scanned: {counts.get('scanned_file_count', 0)}",
        f"- Python files: {counts.get('python_file_count', 0)}",
        f"- Shell scripts: {counts.get('shell_script_count', 0)}",
        f"- Markdown docs: {counts.get('markdown_file_count', 0)}",
        f"- Startup scripts: {counts.get('startup_script_count', 0)}",
        f"- Agent surfaces: {counts.get('agent_surface_count', 0)}",
        f"- Legacy runtime risks: {counts.get('legacy_runtime_risk_count', 0)}",
        f"- Direct execution risks: {counts.get('direct_execution_risk_count', 0)}",
        f"- Module candidates: {counts.get('module_candidate_count', 0)}",
        f"- Finance candidates: {counts.get('finance_candidate_count', 0)}",
        f"- Music candidates: {counts.get('music_candidate_count', 0)}",
        f"- No-go/skipped metadata rows: {counts.get('skipped_no_go_count', 0)}",
        "",
        "Rows:",
    ]
    if not payload.get("rows"):
        lines.append("- none")
    for row in payload.get("rows") or []:
        if payload["report"] == "startup":
            lines.append(
                f"- `{row['relative_path']}` refs={row['referenced_count']} nohup={bool(row['nohup_detected'])} background={bool(row['background_invocation_detected'])}"
            )
        elif payload["report"] == "risks":
            lines.append(f"- `{row['relative_path']}` {row['finding_type']} ({row['risk_level']}): {row['evidence']}")
        elif payload["report"] == "agents":
            lines.append(
                f"- `{row['relative_path']}` agent={row['agent_id']} surface={row['surface_kind']} role={row['future_architectural_role']} burden={row['burden_reduction']}"
            )
        elif payload["report"] in {"module-candidates", "client-candidates", "burden-reduction", "finance-candidates", "music-candidates"}:
            lines.append(
                f"- `{row['relative_path']}` {row.get('candidate_status')} role={row.get('future_architectural_role')} burden={row.get('burden_reduction', 'n/a')}"
            )
        else:
            lines.append(
                f"- {row.get('title')}: {row.get('next_safe_move') or row.get('summary')}"
            )
    lines.extend(
        [
            "",
            "Burden-reduction posture:",
            "- This map is meant to remove operator memory burden by making legacy runtime/code candidates queryable.",
            "- It does not ask the operator to babysit Repo B; it preserves reviewable next lanes and blocked boundaries.",
            "",
            "Authority boundary:",
        ]
    )
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`.")
    return "\n".join(lines)


def build_repo_b_runtime_read_model(db_path: str | Path | None = None) -> dict[str, Any]:
    path = init_repo_b_runtime_intake_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        run_id = _latest_run_id(conn)
        if not run_id:
            return {
                "schema_version": READ_MODEL_VERSION,
                "status": "no_runs",
                "no_authority_flags": NO_AUTHORITY_FLAGS,
            }
        run = dict(conn.execute("SELECT * FROM repo_b_intake_runs WHERE run_id = ?", (run_id,)).fetchone())
        root = dict(conn.execute("SELECT * FROM repo_b_roots WHERE run_id = ?", (run_id,)).fetchone())
        counts = _summary_counts(conn, run_id)
        top_findings = _dict_rows(
            conn,
            """
SELECT relative_path, finding_type, risk_level, evidence
FROM repo_b_safety_findings
ORDER BY CASE risk_level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
         relative_path
LIMIT 12
""".strip(),
        )
        top_candidates = _dict_rows(
            conn,
            """
SELECT relative_path, module_name, candidate_status, future_architectural_role,
       future_home_candidate, burden_reduction
FROM repo_b_module_candidates
ORDER BY CASE burden_reduction
  WHEN 'reduces_finance_burden' THEN 0
  WHEN 'reduces_music_burden' THEN 1
  WHEN 'reduces_system_maintenance_burden' THEN 2
  WHEN 'reduces_client_delivery_burden' THEN 3
  WHEN 'reduces_build_burden' THEN 4
  ELSE 5 END,
  relative_path
LIMIT 20
""".strip(),
        )
        startup_scripts = _dict_rows(
            conn,
            """
SELECT relative_path, referenced_count, nohup_detected, background_invocation_detected
FROM repo_b_startup_surfaces
ORDER BY relative_path
""".strip(),
        )
        agent_surfaces = _dict_rows(
            conn,
            """
SELECT agent_id, surface_kind, COUNT(*) AS count
FROM repo_b_agent_surfaces
GROUP BY agent_id, surface_kind
ORDER BY agent_id, surface_kind
""".strip(),
        )
        recommendations = _dict_rows(
            conn,
            """
SELECT title, summary, recommended_lane, routed_agent, priority_hint,
       reduces_operator_burden_by, next_safe_move
FROM repo_b_reconciliation_recommendations
WHERE run_id = ?
ORDER BY priority_hint DESC, title
""".strip(),
            (run_id,),
        )
        return {
            "schema_version": READ_MODEL_VERSION,
            "read_model_version": READ_MODEL_VERSION,
            "generated_at": utc_now(),
            "run_id": run_id,
            "repo_b": {
                "path": root["repo_path"],
                "remote": root["source_remote"],
                "branch": root["source_branch"],
                "commit": root["source_commit"],
                "source_repo": root["source_repo"],
                "canonical_status": root["canonical_status"],
                "import_status": root["import_status"],
                "execution_allowed": False,
                "promotion_required": True,
            },
            "counts": counts,
            "agent_surface_counts": agent_surfaces,
            "startup_scripts": startup_scripts,
            "top_legacy_runtime_risks": top_findings,
            "top_burden_reduction_candidates": top_candidates,
            "reconciliation_recommendations": recommendations,
            "recommended_next_lane": "Repo B Runtime Reconciliation Review v0",
            "decision_packet": {
                "contains_at_a_glance": "Legacy runtime listeners, workers, startup scripts, approval/HITL helpers, Cassandra/Chief/Niles/Guardian surfaces, finance/music/client-product candidates, and legacy docs.",
                "most_valuable_to_reduce_burden": [
                    "Finance/invoice helpers for business ops relief.",
                    "Music/album helpers for Niles support.",
                    "Cassandra/Chief runtime surfaces for agent recovery clarity.",
                    "Approval/HITL/security code for guarded Operator Action reuse.",
                ],
                "do_not_touch_yet": [
                    "Secrets, env files, credential-like files, private/client/legal/tax roots, and startup scripts that launch background processes.",
                    "Any Repo B runtime service until wrapped in fixed recovery policy with receipts.",
                ],
            },
            "no_authority_flags": NO_AUTHORITY_FLAGS,
        }
    finally:
        conn.close()


def _operator_markdown(read_model: dict[str, Any]) -> str:
    if read_model.get("status") == "no_runs":
        return "# Repo B Runtime Intake v0\n\nNo Repo B intake run has been recorded.\n"
    repo = read_model["repo_b"]
    counts = read_model["counts"]
    lines = [
        "# Repo B Runtime Intake v0",
        "",
        "## Source",
        f"- Path: `{repo['path']}`",
        f"- Remote: `{repo['remote']}`",
        f"- Branch: `{repo['branch']}`",
        f"- Commit: `{repo['commit']}`",
        f"- Canonical status: `{repo['canonical_status']}`",
        f"- Import status: `{repo['import_status']}`",
        "",
        "## Counts",
        f"- Files scanned: {counts.get('scanned_file_count', 0)}",
        f"- Python files: {counts.get('python_file_count', 0)}",
        f"- Shell scripts: {counts.get('shell_script_count', 0)}",
        f"- Markdown docs: {counts.get('markdown_file_count', 0)}",
        f"- Startup scripts found: {counts.get('startup_script_count', 0)}",
        f"- Invoked scripts referenced: {counts.get('invoked_script_count', 0)}",
        f"- Agent surfaces found: {counts.get('agent_surface_count', 0)}",
        f"- Legacy runtime risks: {counts.get('legacy_runtime_risk_count', 0)}",
        f"- Direct execution risk findings: {counts.get('direct_execution_risk_count', 0)}",
        f"- Module candidates: {counts.get('module_candidate_count', 0)}",
        f"- Client product candidates: {counts.get('client_product_candidate_count', 0)}",
        f"- Finance/invoice candidates: {counts.get('finance_candidate_count', 0)}",
        f"- Music/album candidates: {counts.get('music_candidate_count', 0)}",
        f"- Security/HITL candidates: {counts.get('security_hitl_candidate_count', 0)}",
        f"- No-go/skipped metadata rows: {counts.get('skipped_no_go_count', 0)}",
        "",
        "## Startup Scripts",
    ]
    for row in read_model.get("startup_scripts") or []:
        lines.append(
            f"- `{row['relative_path']}` refs={row['referenced_count']} nohup={bool(row['nohup_detected'])} background={bool(row['background_invocation_detected'])}"
        )
    if not read_model.get("startup_scripts"):
        lines.append("- None found.")
    lines.extend(["", "## Top Runtime Risks"])
    for row in read_model.get("top_legacy_runtime_risks") or []:
        lines.append(f"- `{row['relative_path']}` {row['finding_type']} ({row['risk_level']}): {row['evidence']}")
    if not read_model.get("top_legacy_runtime_risks"):
        lines.append("- None found.")
    lines.extend(["", "## Top Burden-Reduction Candidates"])
    for row in read_model.get("top_burden_reduction_candidates") or []:
        lines.append(
            f"- `{row['relative_path']}` role={row['future_architectural_role']} burden={row['burden_reduction']} status={row['candidate_status']}"
        )
    if not read_model.get("top_burden_reduction_candidates"):
        lines.append("- None found.")
    lines.extend(["", "## Recommended Next Lanes"])
    for row in read_model.get("reconciliation_recommendations") or []:
        lines.append(f"- {row['recommended_lane']}: {row['next_safe_move']}")
    if not read_model.get("reconciliation_recommendations"):
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Decision Packet",
            f"- At a glance: {read_model['decision_packet']['contains_at_a_glance']}",
            "- Highest burden-reduction targets:",
        ]
    )
    for item in read_model["decision_packet"]["most_valuable_to_reduce_burden"]:
        lines.append(f"  - {item}")
    lines.append("- Do not touch yet:")
    for item in read_model["decision_packet"]["do_not_touch_yet"]:
        lines.append(f"  - {item}")
    lines.extend(["", "## Authority Boundary"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`.")
    return "\n".join(lines) + "\n"


def export_repo_b_runtime_intake_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    out_root = _export_root_path(export_root)
    out_root.mkdir(parents=True, exist_ok=True)
    read_model = build_repo_b_runtime_read_model(db_path)
    json_path = out_root / JSON_EXPORT_NAME
    operator_path = out_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(_operator_markdown(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "repo_b_path": read_model.get("repo_b", {}).get("path"),
        "scanned_file_count": read_model.get("counts", {}).get("scanned_file_count", 0),
        "startup_script_count": read_model.get("counts", {}).get("startup_script_count", 0),
        "module_candidate_count": read_model.get("counts", {}).get("module_candidate_count", 0),
        "no_authority_flags": NO_AUTHORITY_FLAGS,
    }


__all__ = [
    "DEFAULT_REPO_B_ROOT",
    "NO_AUTHORITY_FLAGS",
    "READ_MODEL_VERSION",
    "REPO_B_INTAKE_VERSION",
    "REPORT_SECTIONS",
    "RepoBIntakeResult",
    "build_repo_b_runtime_intake",
    "build_repo_b_runtime_intake_report",
    "build_repo_b_runtime_read_model",
    "export_repo_b_runtime_intake_read_model",
    "format_repo_b_runtime_intake_report",
    "format_repo_b_runtime_intake_result",
    "init_repo_b_runtime_intake_schema",
    "iter_repo_b_observations",
    "remote_matches_expected",
    "repo_b_runtime_intake_table_names",
    "repo_metadata",
    "stable_json",
]
