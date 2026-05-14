"""Metadata-first Corpus Atlas v0.6 for OpenClaw.

The atlas records path/location metadata and classification labels in the
existing Business Ops ledger under a separate ``corpus_*`` namespace. It does
not ingest arbitrary raw text, activate runtime behavior, or grant retrieval
authority.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger


ATLAS_VERSION = "corpus_atlas_v0_6"
DEFAULT_ROOT_ID = "pc_wsl_home_openclaw"
DEFAULT_HOST_KIND = "pc_wsl"
DEFAULT_ROOT = Path("/home/openclaw")
DEFAULT_REPORT_ROOT = Path("generated/corpus_atlas")
MAX_HASH_BYTES = 5_000_000

RAW_CONTENT_ELIGIBILITY = {
    "eligible",
    "metadata_only",
    "no_go",
    "unknown",
}

FRESHNESS_LABELS = {
    "current_source_of_truth",
    "generated_read_model_fact",
    "generated_current",
    "generated_stale",
    "operator_note",
    "source_claim",
    "parsed_evidence",
    "historical",
    "stale_possible",
    "superseded",
    "deprecated",
    "scratch",
    "experiment",
    "no_go_boundary",
    "sensitive_metadata_only",
    "future_gated_capability",
    "unsupported_claim",
    "unknown",
}

RETRIEVAL_ELIGIBILITY = {
    "retrievable",
    "metadata_only",
    "blocked_no_go",
    "blocked_sensitive",
    "blocked_unknown",
    "needs_operator_review",
    "generated_read_model_only",
    "receipt_metadata_only",
}

INGESTION_ELIGIBILITY = {
    "ingest_allowed",
    "metadata_only",
    "no_go",
    "needs_review",
    "generated_snapshot_only",
    "receipt_summary_only",
    "not_for_ingestion",
}

CANONICALITY_LABELS = {
    "canonical_current",
    "generated_current",
    "tracked_source",
    "operator_note",
    "historical",
    "superseded",
    "scratch",
    "experiment",
    "unknown_review",
    "no_go_boundary",
}

SOURCE_ROLES = {
    "generated_read_model",
    "source_inventory",
    "artifact_registry",
    "evidence_freshness",
    "operator_status",
    "receipt",
    "test_result",
    "source_code",
    "script",
    "test",
    "docs",
    "handoff",
    "ux_product_synthesis",
    "config",
    "cache",
    "secret_boundary",
    "private_boundary",
    "scratch",
    "backup",
    "legacy",
    "unknown",
}

WORLD_BINDINGS = {
    "music_art",
    "finance",
    "operations",
    "security",
    "build",
    "research",
    "communications",
    "business_development",
    "cross_world",
    "no_world",
    "unknown",
}

SENSITIVITY_LABELS = {
    "public_project",
    "internal_project",
    "metadata_only",
    "private",
    "credential_boundary",
    "finance_boundary",
    "legal_tax_boundary",
    "runtime_log_boundary",
    "no_go",
    "unknown",
}

EVIDENCE_CATEGORIES = {
    "source_inventory",
    "context_gate",
    "helm_state",
    "world_registry",
    "world_status",
    "artifact_registry",
    "evidence_freshness",
    "runtime_gate",
    "operator_status",
    "handoff",
    "ux_product_synthesis",
    "receipt",
    "test_result",
    "no_go_boundary",
    "private_boundary",
    "future_capability",
    "unsupported_capability",
    "unknown",
}

REORG_BUCKETS = {
    "keep_canonical",
    "generated_output",
    "backend_source",
    "app_source",
    "receipt_archive",
    "docs_current",
    "docs_legacy",
    "scratch_archive",
    "sensitive_no_go",
    "unknown_review",
}

SENSITIVE_TOP_LEVEL = {
    ".chief.env": ("credential_boundary", "secret_boundary", "no_go"),
    ".chief.env.bak": ("credential_boundary", "secret_boundary", "no_go"),
    ".chief_env": ("credential_boundary", "secret_boundary", "no_go"),
    ".google-secrets": ("credential_boundary", "secret_boundary", "no_go"),
    ".ssh": ("credential_boundary", "secret_boundary", "no_go"),
    ".gnupg": ("credential_boundary", "secret_boundary", "no_go"),
    ".private": ("private", "private_boundary", "no_go"),
    "private": ("private", "private_boundary", "no_go"),
    "secrets": ("credential_boundary", "secret_boundary", "no_go"),
    "vaults": ("private", "private_boundary", "no_go"),
    "finance": ("finance_boundary", "private_boundary", "no_go"),
    "legal": ("legal_tax_boundary", "private_boundary", "no_go"),
    "tax": ("legal_tax_boundary", "private_boundary", "no_go"),
    "cpa": ("finance_boundary", "private_boundary", "no_go"),
    ".cache": ("metadata_only", "cache", "metadata_only"),
    ".codex": ("metadata_only", "cache", "metadata_only"),
    ".aider": ("metadata_only", "cache", "metadata_only"),
    ".aider.tags.cache.v4": ("metadata_only", "cache", "metadata_only"),
    ".claude": ("metadata_only", "cache", "metadata_only"),
    ".config": ("metadata_only", "cache", "metadata_only"),
    ".gemini": ("metadata_only", "cache", "metadata_only"),
    ".local": ("metadata_only", "cache", "metadata_only"),
    ".vscode-server": ("metadata_only", "cache", "metadata_only"),
    ".pytest_cache": ("metadata_only", "cache", "metadata_only"),
    "__pycache__": ("metadata_only", "cache", "metadata_only"),
    "logs": ("runtime_log_boundary", "cache", "no_go"),
    "tmp": ("metadata_only", "scratch", "metadata_only"),
}

SENSITIVE_PATH_PARTS = {
    ".google-secrets",
    ".ssh",
    ".gnupg",
    ".private",
    "private",
    "secrets",
    "vaults",
    "finance",
    "legal",
    "tax",
    "cpa",
    "appdata",
    "runtime_logs",
}

SENSITIVE_FILE_HINTS = (
    "credential",
    "credentials",
    "token",
    "secret",
    ".env",
    "pii_vault",
    "bash_history",
    "python_history",
    "aider.chat.history",
    "aider.input.history",
)

KNOWN_STALE_PATHS = {
    "CURRENT_STATE.md",
    "NEXT_ACTIONS.md",
    "docs/operations/OPENCLAW_CURRENT_EVIDENCE_COVERAGE_AUDIT.md",
}

KNOWN_LEGACY_TOP_LEVEL = {
    "OpenClaw",
    "openclaw-builder",
    "Eyes",
    "brain_dumps",
    "recovery-library",
    "prompt-vault",
    "Downloads",
    "openclaw_arko_review",
}

KNOWN_EXPERIMENTAL_TOP_LEVEL = {
    "local_model_benchmarks",
    "rust_test",
    "test_skills",
    "test_skills_sample",
    "polish_loop",
    "staging",
}

KNOWN_SCRATCH_TOP_LEVEL = {
    "077",
    "31",
    "4home",
    "4secret-file0",
    "5s\n",
    "700",
    "77",
    "9input",
    "chmod",
    "chmod 700 4home",
    "hidden0",
    "key",
    "mkdir -p 49dirname",
    "openrouter",
    "printf",
    "printf paste",
    "secret-file=4home",
    "set -euo pipefail",
    "umask",
}

SAFE_HASH_ROOT_PREFIXES = (
    "docs/",
    "generated/read_models/",
    "scripts/",
    "tests/",
    "Operator/",
)

SAFE_HASH_ROOT_FILES = {
    ".gitignore",
    "AGENTS.md",
    "CORE_ARCHITECTURE_PRINCIPLES.md",
    "OPENCLAW_RUNTIME.md",
    "USER.md",
    "README.md",
    "business_ops_ledger.py",
    "backend_data_contract.py",
    "backend_sqlite_schema.py",
    "backend_sqlite_runtime.py",
    "backend_sqlite_repository.py",
    "backend_knowledge_packet.py",
    "backend_storage_intelligence.py",
}

SELECTED_SCAN_MAX_DEPTH = {
    ".openclaw": 2,
    ".openclaw/business_ops": 3,
    ".codex": 2,
    "Operator": 2,
    "apps": 3,
    "compliance_verdicts": 2,
    "config": 3,
    "docs": 3,
    "execution_receipts": 2,
    "fixtures": 3,
    "generated": 3,
    "generated/read_models": 3,
    "scripts": 2,
    "templates": 3,
    "tests": 2,
}

READ_MODEL_SEED_FILES = (
    "source_inventory.json",
    "helm_state.json",
    "world_domain_registry.json",
    "world_status.json",
    "artifact_registry.json",
    "runtime_activation_gate.json",
    "evidence_freshness.json",
)

CANONICAL_CURRENT_PATHS = {
    "AGENTS.md",
    "CORE_ARCHITECTURE_PRINCIPLES.md",
    "OPENCLAW_RUNTIME.md",
    "USER.md",
}

CONCEPTUAL_ROOTS = (
    {
        "root_id": "mac_openclaw_mirror",
        "root_kind": "operating_mirror",
        "host_kind": "mac",
        "owner_scope": "internal_platform",
        "absolute_root": "unknown_until_operator_manifest://mac/openclaw_mirror",
        "root_label": "Future Mac OpenClaw mirror",
        "status": "future_placeholder",
        "canonical_status": "non_canonical_mirror",
        "import_status": "not_scanned",
        "mirror_of_root_id": DEFAULT_ROOT_ID,
        "lineage_source": "pc_wsl_home_openclaw",
    },
    {
        "root_id": "mac_mission_control_app",
        "root_kind": "app_repo",
        "host_kind": "mac",
        "owner_scope": "internal_platform",
        "absolute_root": "/Users/hwinshipwheatley/Developer/OpenClawMissionControl/OpenClaw Mission Controle",
        "root_label": "Future Mac Mission Control app root",
        "status": "future_placeholder",
        "canonical_status": "non_canonical_app_root",
        "import_status": "not_scanned",
        "mirror_of_root_id": DEFAULT_ROOT_ID,
        "lineage_source": "pc_wsl_home_openclaw",
    },
    {
        "root_id": "mac_generated_read_models",
        "root_kind": "generated_read_model_mirror",
        "host_kind": "mac",
        "owner_scope": "internal_platform",
        "absolute_root": "/Users/hwinshipwheatley/openclaw_generated_read_models",
        "root_label": "Future Mac generated read-model mirror",
        "status": "future_placeholder",
        "canonical_status": "non_canonical_mirror",
        "import_status": "not_scanned",
        "mirror_of_root_id": DEFAULT_ROOT_ID,
        "lineage_source": "generated/read_models",
    },
    {
        "root_id": "github_legacy_openclaw",
        "root_kind": "legacy_git_repo",
        "host_kind": "github",
        "owner_scope": "internal_platform",
        "absolute_root": "not_imported://github/legacy_openclaw",
        "root_label": "Legacy GitHub OpenClaw repo",
        "status": "future_placeholder",
        "canonical_status": "non_canonical_until_promoted",
        "import_status": "not_imported",
        "repo_name": "github_legacy_openclaw",
        "lineage_source": "legacy_external_repo",
    },
    {
        "root_id": "client_project_root",
        "root_kind": "client_project_root",
        "host_kind": "unknown",
        "owner_scope": "client_project",
        "absolute_root": "not_scanned://client/project_root",
        "root_label": "Future client project root",
        "status": "future_placeholder",
        "canonical_status": "requires_client_allowlist",
        "import_status": "not_scanned",
        "lineage_source": "future_client_project_capsule",
    },
    {
        "root_id": "client_runtime_root",
        "root_kind": "client_runtime_root",
        "host_kind": "unknown",
        "owner_scope": "client_runtime",
        "absolute_root": "not_scanned://client/runtime_root",
        "root_label": "Future client runtime root",
        "status": "future_placeholder",
        "canonical_status": "requires_client_allowlist",
        "import_status": "not_scanned",
        "lineage_source": "future_client_runtime_capsule",
    },
)


@dataclass(frozen=True)
class CorpusPathRecord:
    path_id: str
    root_id: str
    run_id: str
    absolute_path: str
    relative_path: str
    parent_relative_path: str
    path_name: str
    path_type: str
    tracked_status: str
    git_head: str
    size_bytes: int | None
    mtime: str | None
    ctime: str | None
    content_hash: str | None
    hash_algorithm: str | None
    source_role: str
    freshness_label: str
    sensitivity_label: str
    raw_content_eligibility: str
    retrieval_eligibility: str
    ingestion_eligibility: str
    canonicality: str
    world_binding: str
    evidence_category: str
    reorg_status: str
    reorg_bucket: str
    reorg_reason: str
    reorg_confidence: float
    requires_operator_review: bool
    metadata_basis: str
    body_read: bool = False
    runtime_authority: bool = False


@dataclass(frozen=True)
class CorpusAtlasResult:
    run_id: str
    root_id: str
    db_path: str
    root: str
    path_count: int
    top_level_count: int
    counts: dict[str, dict[str, int]]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def display_path(path: str) -> str:
    return path.replace("\n", "\\n")


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS corpus_roots (
  root_id TEXT PRIMARY KEY,
  root_kind TEXT NOT NULL DEFAULT 'unknown',
  host_kind TEXT NOT NULL,
  owner_scope TEXT NOT NULL DEFAULT 'internal_platform',
  project_id TEXT,
  client_id TEXT,
  instance_id TEXT,
  absolute_root TEXT NOT NULL,
  root_label TEXT,
  status TEXT NOT NULL,
  repo_url TEXT,
  repo_name TEXT,
  branch TEXT,
  commit_sha TEXT,
  remote_origin TEXT,
  canonical_status TEXT NOT NULL DEFAULT 'unknown',
  import_status TEXT NOT NULL DEFAULT 'unknown',
  mirror_of_root_id TEXT,
  lineage_source TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  notes TEXT
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS corpus_atlas_runs (
  run_id TEXT PRIMARY KEY,
  root_id TEXT NOT NULL,
  atlas_version TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  git_head TEXT,
  git_branch TEXT,
  repo_root TEXT,
  scan_mode TEXT NOT NULL,
  max_depth_policy TEXT NOT NULL,
  path_count INTEGER NOT NULL DEFAULT 0,
  top_level_count INTEGER NOT NULL DEFAULT 0,
  body_ingested INTEGER NOT NULL DEFAULT 0,
  raw_sensitive_data_stored INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  activation_allowed INTEGER NOT NULL DEFAULT 0,
  backend_execution_authorized INTEGER NOT NULL DEFAULT 0,
  source_basis_json TEXT NOT NULL,
  notes TEXT,
  FOREIGN KEY (root_id) REFERENCES corpus_roots(root_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS corpus_paths (
  path_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  root_id TEXT NOT NULL,
  absolute_path TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  parent_relative_path TEXT NOT NULL,
  path_name TEXT NOT NULL,
  path_type TEXT NOT NULL CHECK(path_type IN ('file','directory','symlink','unknown')),
  tracked_status TEXT NOT NULL CHECK(tracked_status IN ('tracked','untracked','ignored','unknown')),
  git_head TEXT,
  size_bytes INTEGER,
  mtime TEXT,
  ctime TEXT,
  content_hash TEXT,
  hash_algorithm TEXT,
  source_role TEXT NOT NULL,
  freshness_label TEXT NOT NULL,
  sensitivity_label TEXT NOT NULL,
  raw_content_eligibility TEXT NOT NULL,
  retrieval_eligibility TEXT NOT NULL DEFAULT 'blocked_unknown',
  ingestion_eligibility TEXT NOT NULL DEFAULT 'needs_review',
  canonicality TEXT NOT NULL DEFAULT 'unknown_review',
  world_binding TEXT NOT NULL,
  evidence_category TEXT NOT NULL,
  reorg_status TEXT NOT NULL,
  reorg_bucket TEXT NOT NULL,
  reorg_reason TEXT NOT NULL,
  reorg_confidence REAL NOT NULL,
  requires_operator_review INTEGER NOT NULL,
  metadata_basis TEXT NOT NULL,
  body_read INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES corpus_atlas_runs(run_id),
  FOREIGN KEY (root_id) REFERENCES corpus_roots(root_id),
  UNIQUE(run_id, root_id, relative_path)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS corpus_path_labels (
  label_id TEXT PRIMARY KEY,
  path_id TEXT NOT NULL,
  label_name TEXT NOT NULL,
  label_value TEXT NOT NULL,
  label_basis TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (path_id) REFERENCES corpus_paths(path_id),
  UNIQUE(path_id, label_name, label_value, label_basis)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS corpus_world_bindings (
  binding_id TEXT PRIMARY KEY,
  path_id TEXT NOT NULL,
  world_id TEXT NOT NULL,
  confidence REAL NOT NULL,
  binding_basis TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (path_id) REFERENCES corpus_paths(path_id),
  UNIQUE(path_id, world_id, binding_basis)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS corpus_artifact_links (
  link_id TEXT PRIMARY KEY,
  path_id TEXT NOT NULL,
  artifact_id TEXT NOT NULL,
  artifact_kind TEXT NOT NULL,
  source_read_model TEXT NOT NULL,
  link_basis TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (path_id) REFERENCES corpus_paths(path_id),
  UNIQUE(path_id, artifact_id, source_read_model)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS corpus_freshness_signals (
  signal_id TEXT PRIMARY KEY,
  path_id TEXT NOT NULL,
  signal_type TEXT NOT NULL,
  signal_value TEXT NOT NULL,
  signal_basis TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  FOREIGN KEY (path_id) REFERENCES corpus_paths(path_id),
  UNIQUE(path_id, signal_type, signal_basis)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS corpus_sensitivity_labels (
  label_id TEXT PRIMARY KEY,
  path_id TEXT NOT NULL,
  sensitivity_label TEXT NOT NULL,
  label_basis TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (path_id) REFERENCES corpus_paths(path_id),
  UNIQUE(path_id, sensitivity_label, label_basis)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS corpus_reorg_candidates (
  candidate_id TEXT PRIMARY KEY,
  path_id TEXT NOT NULL,
  current_location TEXT NOT NULL,
  suggested_bucket TEXT NOT NULL,
  candidate_action TEXT NOT NULL,
  reason TEXT NOT NULL,
  confidence REAL NOT NULL,
  requires_operator_review INTEGER NOT NULL,
  advisory_only INTEGER NOT NULL DEFAULT 1,
  moved INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (path_id) REFERENCES corpus_paths(path_id),
  UNIQUE(path_id, suggested_bucket, candidate_action)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS corpus_mirror_candidates (
  mirror_id TEXT PRIMARY KEY,
  path_id TEXT NOT NULL,
  mirror_root_id TEXT NOT NULL,
  suggested_relative_path TEXT NOT NULL,
  mirror_kind TEXT NOT NULL,
  status TEXT NOT NULL,
  basis TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (path_id) REFERENCES corpus_paths(path_id),
  UNIQUE(path_id, mirror_root_id, suggested_relative_path)
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_corpus_paths_run ON corpus_paths(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_corpus_paths_relative ON corpus_paths(root_id, relative_path)",
        "CREATE INDEX IF NOT EXISTS idx_corpus_paths_role ON corpus_paths(run_id, source_role)",
        "CREATE INDEX IF NOT EXISTS idx_corpus_paths_freshness ON corpus_paths(run_id, freshness_label)",
        "CREATE INDEX IF NOT EXISTS idx_corpus_paths_sensitivity ON corpus_paths(run_id, sensitivity_label)",
        "CREATE INDEX IF NOT EXISTS idx_corpus_paths_eligibility ON corpus_paths(run_id, raw_content_eligibility)",
        "CREATE INDEX IF NOT EXISTS idx_corpus_paths_reorg ON corpus_paths(run_id, reorg_bucket)",
    )


def _ensure_column(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {row[1] for row in rows}
    if column_name not in existing:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}")


def _ensure_v0_6_columns(conn: sqlite3.Connection) -> None:
    for column_name, column_definition in (
        ("root_kind", "root_kind TEXT NOT NULL DEFAULT 'unknown'"),
        ("owner_scope", "owner_scope TEXT NOT NULL DEFAULT 'internal_platform'"),
        ("project_id", "project_id TEXT"),
        ("client_id", "client_id TEXT"),
        ("instance_id", "instance_id TEXT"),
        ("repo_url", "repo_url TEXT"),
        ("repo_name", "repo_name TEXT"),
        ("branch", "branch TEXT"),
        ("commit_sha", "commit_sha TEXT"),
        ("remote_origin", "remote_origin TEXT"),
        ("canonical_status", "canonical_status TEXT NOT NULL DEFAULT 'unknown'"),
        ("import_status", "import_status TEXT NOT NULL DEFAULT 'unknown'"),
        ("mirror_of_root_id", "mirror_of_root_id TEXT"),
        ("lineage_source", "lineage_source TEXT"),
    ):
        _ensure_column(conn, "corpus_roots", column_name, column_definition)

    for column_name, column_definition in (
        (
            "retrieval_eligibility",
            "retrieval_eligibility TEXT NOT NULL DEFAULT 'blocked_unknown'",
        ),
        (
            "ingestion_eligibility",
            "ingestion_eligibility TEXT NOT NULL DEFAULT 'needs_review'",
        ),
        ("canonicality", "canonicality TEXT NOT NULL DEFAULT 'unknown_review'"),
    ):
        _ensure_column(conn, "corpus_paths", column_name, column_definition)


def init_corpus_atlas_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    db_parent = Path(path).parent
    if db_parent and not db_parent.exists():
        db_parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for statement in _sql_statements():
            conn.execute(statement)
        _ensure_v0_6_columns(conn)
        conn.commit()
    finally:
        conn.close()
    return path


def corpus_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_corpus_atlas_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'corpus_%' ORDER BY name"
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _run_git(args: list[str], root: Path, *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        input=input_bytes,
        capture_output=True,
        check=False,
        timeout=10,
    )


def git_context(root: Path) -> dict[str, str]:
    context = {
        "git_head": "unknown",
        "git_branch": "unknown",
        "repo_root": "unknown",
        "remote_origin": "unknown",
    }
    try:
        head = _run_git(["rev-parse", "--short=12", "HEAD"], root)
        branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], root)
        repo_root = _run_git(["rev-parse", "--show-toplevel"], root)
        remote_origin = _run_git(["remote", "get-url", "origin"], root)
    except (OSError, subprocess.SubprocessError):
        return context
    if head.returncode == 0:
        context["git_head"] = head.stdout.decode().strip() or "unknown"
    if branch.returncode == 0:
        context["git_branch"] = branch.stdout.decode().strip() or "unknown"
    if repo_root.returncode == 0:
        context["repo_root"] = repo_root.stdout.decode().strip() or "unknown"
    if remote_origin.returncode == 0:
        context["remote_origin"] = remote_origin.stdout.decode().strip() or "unknown"
    return context


def tracked_paths(root: Path) -> set[str]:
    try:
        result = _run_git(["ls-files", "-z"], root)
    except (OSError, subprocess.SubprocessError):
        return set()
    if result.returncode != 0:
        return set()
    return {
        item.decode("utf-8", errors="replace")
        for item in result.stdout.split(b"\x00")
        if item
    }


def ignored_paths(root: Path, relative_paths: Iterable[str]) -> set[str]:
    paths = [path for path in relative_paths if path and path != "."]
    if not paths:
        return set()
    input_bytes = b"".join(path.encode("utf-8", errors="surrogateescape") + b"\x00" for path in paths)
    try:
        result = _run_git(["check-ignore", "-z", "--stdin"], root, input_bytes=input_bytes)
    except (OSError, subprocess.SubprocessError):
        return set()
    if result.returncode not in {0, 1}:
        return set()
    return {
        item.decode("utf-8", errors="replace")
        for item in result.stdout.split(b"\x00")
        if item
    }


def tracked_status_for(
    relative_path: str,
    tracked: set[str],
    ignored: set[str],
) -> str:
    if relative_path in tracked:
        return "tracked"
    prefix = relative_path.rstrip("/") + "/"
    if any(path.startswith(prefix) for path in tracked):
        return "tracked"
    if relative_path in ignored:
        return "ignored"
    return "untracked"


def _parts_lower(relative_path: str) -> tuple[str, ...]:
    return tuple(part.lower() for part in Path(relative_path).parts if part not in {"", "."})


def _top_level(relative_path: str) -> str:
    parts = Path(relative_path).parts
    return parts[0] if parts else relative_path


def _is_sensitive_file_name(name: str) -> bool:
    lower = name.lower()
    return any(hint in lower for hint in SENSITIVE_FILE_HINTS)


def sensitivity_boundary(relative_path: str) -> tuple[str, str, str, str] | None:
    normalized = relative_path.replace("\\", "/").strip("/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    parts_lower = _parts_lower(normalized)
    if not parts_lower:
        return None

    first = parts_lower[0]
    if first in SENSITIVE_TOP_LEVEL:
        sensitivity, role, eligibility = SENSITIVE_TOP_LEVEL[first]
        reason = f"known sensitive top-level boundary: {parts_lower[0]}"
        return sensitivity, role, eligibility, reason

    if parts_lower[:2] == (".codex", "logs_2.sqlite") or parts_lower[:2] == (
        ".codex",
        "state_5.sqlite",
    ):
        return "runtime_log_boundary", "cache", "metadata_only", "codex state/log database boundary"

    if parts_lower[:2] == (".openclaw", "memory"):
        return "private", "private_boundary", "metadata_only", "openclaw memory database boundary"

    if parts_lower[:3] == ("sidecars", "hermes_home", "state.db"):
        return "private", "private_boundary", "metadata_only", "hermes sidecar message database boundary"

    if "runtime_logs" in parts_lower:
        return "runtime_log_boundary", "cache", "no_go", "runtime log boundary"

    if any(part in SENSITIVE_PATH_PARTS for part in parts_lower):
        part = next(part for part in parts_lower if part in SENSITIVE_PATH_PARTS)
        if part in {"finance", "cpa"}:
            return "finance_boundary", "private_boundary", "no_go", f"sensitive path component: {part}"
        if part in {"legal", "tax"}:
            return "legal_tax_boundary", "private_boundary", "no_go", f"sensitive path component: {part}"
        if part in {".ssh", ".gnupg", ".google-secrets", "secrets"}:
            return "credential_boundary", "secret_boundary", "no_go", f"credential path component: {part}"
        return "private", "private_boundary", "no_go", f"private path component: {part}"

    if _is_sensitive_file_name(Path(normalized).name):
        return "credential_boundary", "secret_boundary", "no_go", "credential-like file name"

    return None


def _path_type(path: Path) -> str:
    try:
        if path.is_symlink():
            return "symlink"
        if path.is_file():
            return "file"
        if path.is_dir():
            return "directory"
    except OSError:
        return "unknown"
    return "unknown"


def _stat_metadata(path: Path) -> tuple[int | None, str | None, str | None]:
    try:
        stat_result = path.lstat()
    except OSError:
        return None, None, None
    return (
        stat_result.st_size,
        datetime.fromtimestamp(stat_result.st_mtime, timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        datetime.fromtimestamp(stat_result.st_ctime, timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
    )


def _max_depth_for(relative_path: str) -> int:
    normalized = relative_path.strip("/")
    best = 1
    for prefix, max_depth in SELECTED_SCAN_MAX_DEPTH.items():
        if normalized == prefix or normalized.startswith(prefix + "/") or prefix.startswith(normalized + "/"):
            best = max(best, max_depth)
    return best


def _should_descend(relative_path: str, classification: dict[str, Any], path_type: str) -> bool:
    if path_type != "directory":
        return False
    if classification["raw_content_eligibility"] == "no_go":
        return False
    if classification["sensitivity_label"] in {
        "credential_boundary",
        "finance_boundary",
        "legal_tax_boundary",
        "private",
        "runtime_log_boundary",
        "no_go",
    }:
        return False
    depth = len(Path(relative_path).parts)
    return depth < _max_depth_for(relative_path)


def _is_safe_hash_candidate(
    relative_path: str,
    path_type: str,
    raw_content_eligibility: str,
    size_bytes: int | None,
) -> bool:
    if path_type != "file":
        return False
    if raw_content_eligibility != "eligible":
        return False
    if size_bytes is None or size_bytes > MAX_HASH_BYTES:
        return False
    if relative_path in SAFE_HASH_ROOT_FILES:
        return True
    return any(relative_path.startswith(prefix) for prefix in SAFE_HASH_ROOT_PREFIXES)


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_seed_signals(root: Path, db_path: str | Path | None = None) -> dict[str, Any]:
    read_model_root = root / "generated" / "read_models"
    seeds: dict[str, Any] = {
        "read_models": {},
        "artifact_by_path": {},
        "freshness_by_path": {},
        "source_inventory_by_path": {},
        "world_ids": [],
        "truth_registry_by_path": {},
    }

    for name in READ_MODEL_SEED_FILES:
        path = read_model_root / name
        if not path.is_file():
            continue
        try:
            seeds["read_models"][name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue

    artifact_registry = seeds["read_models"].get("artifact_registry.json", {})
    for artifact in artifact_registry.get("artifacts", []):
        relative = artifact.get("path_or_command")
        if not isinstance(relative, str) or relative.startswith("python3 "):
            continue
        if relative.startswith("generated/read_models/"):
            path_key = relative
        else:
            path_key = relative
        seeds["artifact_by_path"].setdefault(path_key, []).append(artifact)

    evidence_freshness = seeds["read_models"].get("evidence_freshness.json", {})
    for artifact in evidence_freshness.get("artifacts", []):
        relative = artifact.get("path")
        if isinstance(relative, str):
            seeds["freshness_by_path"][relative] = artifact

    source_inventory = seeds["read_models"].get("source_inventory.json", {})
    for record in source_inventory.get("records", []):
        relative = record.get("path")
        if isinstance(relative, str):
            seeds["source_inventory_by_path"][relative.rstrip("/")] = record

    world_registry = seeds["read_models"].get("world_domain_registry.json", {})
    for world in world_registry.get("worlds", []):
        world_id = world.get("world_id")
        if isinstance(world_id, str) and world_id in WORLD_BINDINGS:
            seeds["world_ids"].append(world_id)

    if db_path:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                rows = conn.execute(
                    "SELECT observed_path, source_id, truth_status, approval_status, doc_type FROM truth_registry_entries"
                ).fetchall()
            finally:
                conn.close()
            for observed_path, source_id, truth_status, approval_status, doc_type in rows:
                if observed_path:
                    seeds["truth_registry_by_path"][observed_path] = {
                        "source_id": source_id,
                        "truth_status": truth_status,
                        "approval_status": approval_status,
                        "doc_type": doc_type,
                    }
        except (sqlite3.Error, OSError):
            pass

    return seeds


def _evidence_category_for(relative_path: str) -> str:
    name = Path(relative_path).name
    if relative_path.startswith("generated/read_models/source_inventory"):
        return "source_inventory"
    if relative_path.startswith("generated/read_models/helm_state"):
        return "helm_state"
    if relative_path.startswith("generated/read_models/world_domain_registry"):
        return "world_registry"
    if relative_path.startswith("generated/read_models/world_status"):
        return "world_status"
    if relative_path.startswith("generated/read_models/artifact_registry"):
        return "artifact_registry"
    if relative_path.startswith("generated/read_models/evidence_freshness"):
        return "evidence_freshness"
    if relative_path.startswith("generated/read_models/runtime_activation_gate"):
        return "runtime_gate"
    if relative_path.startswith("Operator/GENERATED_"):
        return "operator_status"
    if "handoff" in relative_path.lower():
        return "handoff"
    if relative_path.startswith("execution_receipts/"):
        return "receipt"
    if relative_path.startswith("compliance_verdicts/"):
        return "test_result"
    if relative_path.startswith("docs/planning/launch_ladder/") or "product" in name.lower():
        return "ux_product_synthesis"
    if "future" in relative_path.lower():
        return "future_capability"
    return "unknown"


def _world_binding_for(relative_path: str, source_role: str, evidence_category: str) -> str:
    lower = relative_path.lower()
    name = Path(lower).name
    if evidence_category in {"helm_state", "world_registry", "world_status", "artifact_registry", "evidence_freshness"}:
        return "cross_world"
    if "music" in lower or "album" in lower or "producer" in lower or "fundo" in lower:
        return "music_art"
    if "finance" in lower or "financial" in lower or "tax" in lower or "cpa" in lower or "invoice" in lower or "payment" in lower:
        return "finance"
    if "secret" in lower or ".ssh" in lower or ".google-secrets" in lower or "approval" in lower or "security" in lower:
        return "security"
    if "gmail" in lower or "email" in lower or "contact" in lower or "outreach" in lower or "briefing" in lower:
        return "communications"
    if "business" in lower or "expert" in lower or "launch" in lower or "producer" in lower:
        return "business_development"
    if "research" in lower or "benchmark" in lower or "alphaxiv" in lower or "local_model" in lower:
        return "research"
    if source_role in {"source_code", "script", "test"} or lower.startswith(("apps/", "generated/", "scripts/", "tests/")):
        return "build"
    if lower.startswith(("operator/", "docs/", "execution_receipts/", "compliance_verdicts/", ".openclaw/business_ops")):
        return "operations"
    if source_role in {"cache", "scratch", "backup"} or name.startswith("."):
        return "no_world"
    return "unknown"


def _source_role_for(relative_path: str, path_type: str, sensitivity_role: str | None = None) -> str:
    if sensitivity_role:
        return sensitivity_role
    lower = relative_path.lower()
    top = _top_level(relative_path)
    if relative_path.startswith("generated/read_models/source_inventory"):
        return "source_inventory"
    if relative_path.startswith("generated/read_models/artifact_registry"):
        return "artifact_registry"
    if relative_path.startswith("generated/read_models/evidence_freshness"):
        return "evidence_freshness"
    if relative_path.startswith("generated/read_models/") or relative_path.startswith("Operator/GENERATED_"):
        return "generated_read_model"
    if relative_path.startswith("execution_receipts/") or ".openclaw/business_ops/ledger.sqlite" in relative_path:
        return "receipt"
    if relative_path.startswith("compliance_verdicts/"):
        return "test_result"
    if relative_path.startswith("scripts/"):
        return "script"
    if relative_path.startswith("tests/") or Path(relative_path).name.startswith("test_"):
        return "test"
    if relative_path.startswith("docs/") or relative_path.endswith(".md"):
        if "handoff" in lower:
            return "handoff"
        if "launch_ladder" in lower or "product" in lower or "ux" in lower:
            return "ux_product_synthesis"
        return "docs"
    if relative_path.startswith("apps/"):
        return "source_code"
    if top in KNOWN_LEGACY_TOP_LEVEL:
        return "legacy"
    if top in KNOWN_EXPERIMENTAL_TOP_LEVEL:
        return "scratch" if top == "staging" else "unknown"
    if top in KNOWN_SCRATCH_TOP_LEVEL:
        return "scratch"
    if top == "backups" or lower.endswith(".bak"):
        return "backup"
    if top.startswith(".") and top not in {".gitignore", ".openclaw"}:
        return "config" if path_type == "file" else "cache"
    if relative_path.endswith(".py") or relative_path.endswith(".rs") or relative_path.endswith(".ts"):
        return "source_code"
    if relative_path.endswith((".json", ".yaml", ".yml", ".toml")):
        return "config"
    return "unknown"


def _freshness_for(
    relative_path: str,
    source_role: str,
    sensitivity_label: str,
    evidence_category: str,
    seeds: dict[str, Any],
) -> str:
    if sensitivity_label in {"credential_boundary", "finance_boundary", "legal_tax_boundary", "private", "no_go"}:
        return "no_go_boundary"
    if sensitivity_label in {"runtime_log_boundary", "metadata_only"} and source_role in {"cache", "private_boundary"}:
        return "sensitive_metadata_only"
    if relative_path in KNOWN_STALE_PATHS:
        return "stale_possible"
    top = _top_level(relative_path)
    if top in KNOWN_LEGACY_TOP_LEVEL or top == "backups":
        return "historical"
    if top in KNOWN_SCRATCH_TOP_LEVEL:
        return "scratch"
    if top in KNOWN_EXPERIMENTAL_TOP_LEVEL:
        return "experiment"
    if relative_path.startswith("generated/read_models/"):
        freshness = seeds.get("freshness_by_path", {}).get(relative_path, {})
        if freshness.get("freshness_state") == "stale":
            return "generated_stale"
        if freshness.get("freshness_state") == "current":
            return "generated_current"
        return "generated_read_model_fact"
    if relative_path.startswith("Operator/GENERATED_"):
        freshness = seeds.get("freshness_by_path", {}).get(relative_path, {})
        if freshness.get("freshness_state") == "stale":
            return "generated_stale"
        if freshness.get("freshness_state") == "current":
            return "generated_current"
        return "generated_read_model_fact"
    if evidence_category == "runtime_gate":
        return "future_gated_capability"
    if relative_path in CANONICAL_CURRENT_PATHS:
        return "current_source_of_truth"
    if source_role in {"source_code", "script", "test"}:
        return "source_claim"
    if source_role in {"docs", "handoff", "ux_product_synthesis"}:
        return "source_claim"
    if source_role == "receipt":
        return "historical"
    return "unknown"


def _canonicality_for(
    relative_path: str,
    source_role: str,
    freshness_label: str,
    sensitivity_label: str,
) -> str:
    if sensitivity_label in {
        "credential_boundary",
        "finance_boundary",
        "legal_tax_boundary",
        "private",
        "runtime_log_boundary",
        "no_go",
    }:
        return "no_go_boundary"
    if freshness_label in {"generated_current", "generated_read_model_fact"}:
        return "generated_current"
    if relative_path in CANONICAL_CURRENT_PATHS:
        return "canonical_current"
    if freshness_label in {"stale_possible", "superseded", "deprecated"}:
        return "superseded"
    if freshness_label == "historical" or source_role in {"receipt", "legacy", "backup"}:
        return "historical"
    if freshness_label == "scratch" or source_role == "scratch":
        return "scratch"
    if freshness_label == "experiment":
        return "experiment"
    if source_role in {"source_code", "script", "test"}:
        return "tracked_source"
    if source_role in {"docs", "handoff", "ux_product_synthesis"}:
        return "operator_note"
    return "unknown_review"


def _retrieval_eligibility_for(
    *,
    source_role: str,
    sensitivity_label: str,
    raw_content_eligibility: str,
    freshness_label: str,
    canonicality: str,
) -> str:
    if raw_content_eligibility == "no_go":
        return "blocked_no_go"
    if sensitivity_label in {
        "credential_boundary",
        "finance_boundary",
        "legal_tax_boundary",
        "private",
        "runtime_log_boundary",
        "no_go",
    }:
        return "blocked_sensitive"
    if source_role in {"generated_read_model", "source_inventory", "artifact_registry", "evidence_freshness"}:
        return "generated_read_model_only"
    if source_role in {"receipt", "test_result"}:
        return "receipt_metadata_only"
    if raw_content_eligibility == "metadata_only":
        return "metadata_only"
    if raw_content_eligibility == "unknown" or freshness_label == "unknown":
        return "blocked_unknown"
    if canonicality == "canonical_current" and raw_content_eligibility == "eligible":
        return "retrievable"
    return "needs_operator_review"


def _ingestion_eligibility_for(
    *,
    source_role: str,
    raw_content_eligibility: str,
    retrieval_eligibility: str,
    canonicality: str,
) -> str:
    if retrieval_eligibility in {"blocked_no_go", "blocked_sensitive"}:
        return "no_go"
    if source_role in {"generated_read_model", "source_inventory", "artifact_registry", "evidence_freshness"}:
        return "generated_snapshot_only"
    if source_role in {"receipt", "test_result"}:
        return "receipt_summary_only"
    if raw_content_eligibility == "metadata_only":
        return "metadata_only"
    if raw_content_eligibility == "unknown":
        return "needs_review"
    if canonicality == "canonical_current" and raw_content_eligibility == "eligible":
        return "ingest_allowed"
    if retrieval_eligibility == "needs_operator_review":
        return "needs_review"
    return "not_for_ingestion"


def _raw_eligibility_for(
    relative_path: str,
    path_type: str,
    source_role: str,
    sensitivity_label: str,
    boundary_eligibility: str | None,
) -> str:
    if boundary_eligibility:
        return boundary_eligibility
    if path_type == "directory":
        return "metadata_only"
    if sensitivity_label in {
        "credential_boundary",
        "finance_boundary",
        "legal_tax_boundary",
        "private",
        "runtime_log_boundary",
        "no_go",
    }:
        return "no_go"
    if relative_path.startswith(SAFE_HASH_ROOT_PREFIXES) or relative_path in SAFE_HASH_ROOT_FILES:
        return "eligible"
    if source_role in {"cache", "backup", "legacy", "scratch"}:
        return "metadata_only"
    if relative_path.endswith((".sqlite", ".db")):
        return "metadata_only"
    return "unknown"


def _reorg_for(
    relative_path: str,
    source_role: str,
    freshness_label: str,
    sensitivity_label: str,
) -> tuple[str, str, str, float, bool]:
    top = _top_level(relative_path)
    if sensitivity_label in {
        "credential_boundary",
        "finance_boundary",
        "legal_tax_boundary",
        "private",
        "runtime_log_boundary",
        "no_go",
    }:
        return "advisory", "sensitive_no_go", "sensitive boundary; register only, do not move", 0.95, True
    if relative_path.startswith("generated/read_models/") or relative_path.startswith("generated/"):
        return "advisory", "generated_output", "generated artifact/output path", 0.9, False
    if source_role in {"source_code", "script", "test"}:
        bucket = "backend_source" if not relative_path.startswith("apps/") else "app_source"
        return "advisory", bucket, "tracked project source/test path", 0.8, False
    if source_role in {"docs", "handoff", "ux_product_synthesis"}:
        if freshness_label in {"stale_possible", "historical", "superseded", "deprecated"}:
            return "advisory", "docs_legacy", "known stale or historical documentation candidate", 0.85, True
        return "advisory", "docs_current", "documentation/current-source candidate", 0.65, False
    if source_role in {"receipt", "test_result"}:
        return "advisory", "receipt_archive", "receipt or verification archive", 0.75, False
    if top in KNOWN_LEGACY_TOP_LEVEL or top in KNOWN_SCRATCH_TOP_LEVEL or source_role in {"scratch", "backup", "legacy"}:
        return "advisory", "scratch_archive", "legacy/scratch path candidate for later operator-reviewed cleanup", 0.8, True
    if relative_path in {"OPENCLAW_RUNTIME.md", "USER.md", "CORE_ARCHITECTURE_PRINCIPLES.md", "AGENTS.md"}:
        return "advisory", "keep_canonical", "operator/runtime doctrine root", 0.95, False
    return "advisory", "unknown_review", "insufficient classification confidence", 0.35, True


def classify_path(
    relative_path: str,
    path_type: str,
    tracked_status: str,
    seeds: dict[str, Any],
) -> dict[str, Any]:
    boundary = sensitivity_boundary(relative_path)
    sensitivity_label = "internal_project"
    boundary_role = None
    boundary_eligibility = None
    metadata_basis = "path_metadata_classification"
    if boundary:
        sensitivity_label, boundary_role, boundary_eligibility, reason = boundary
        metadata_basis = reason

    source_role = _source_role_for(relative_path, path_type, boundary_role)
    evidence_category = _evidence_category_for(relative_path)
    if evidence_category == "unknown" and source_role == "receipt":
        evidence_category = "receipt"
    if evidence_category == "unknown" and source_role == "test":
        evidence_category = "test_result"
    if evidence_category == "unknown" and source_role in {"secret_boundary", "private_boundary"}:
        evidence_category = "no_go_boundary" if boundary_eligibility == "no_go" else "private_boundary"

    raw_eligibility = _raw_eligibility_for(
        relative_path,
        path_type,
        source_role,
        sensitivity_label,
        boundary_eligibility,
    )
    if (
        raw_eligibility == "eligible"
        and tracked_status == "ignored"
        and relative_path not in CANONICAL_CURRENT_PATHS
    ):
        raw_eligibility = "metadata_only"

    freshness_label = _freshness_for(
        relative_path,
        source_role,
        sensitivity_label,
        evidence_category,
        seeds,
    )
    canonicality = _canonicality_for(
        relative_path,
        source_role,
        freshness_label,
        sensitivity_label,
    )
    retrieval_eligibility = _retrieval_eligibility_for(
        source_role=source_role,
        sensitivity_label=sensitivity_label,
        raw_content_eligibility=raw_eligibility,
        freshness_label=freshness_label,
        canonicality=canonicality,
    )
    ingestion_eligibility = _ingestion_eligibility_for(
        source_role=source_role,
        raw_content_eligibility=raw_eligibility,
        retrieval_eligibility=retrieval_eligibility,
        canonicality=canonicality,
    )
    world_binding = _world_binding_for(relative_path, source_role, evidence_category)
    reorg_status, reorg_bucket, reorg_reason, reorg_confidence, requires_review = _reorg_for(
        relative_path,
        source_role,
        freshness_label,
        sensitivity_label,
    )
    if retrieval_eligibility in {"blocked_unknown", "needs_operator_review"}:
        requires_review = True

    return {
        "source_role": source_role if source_role in SOURCE_ROLES else "unknown",
        "freshness_label": freshness_label if freshness_label in FRESHNESS_LABELS else "unknown",
        "sensitivity_label": sensitivity_label if sensitivity_label in SENSITIVITY_LABELS else "unknown",
        "raw_content_eligibility": raw_eligibility if raw_eligibility in RAW_CONTENT_ELIGIBILITY else "unknown",
        "retrieval_eligibility": (
            retrieval_eligibility
            if retrieval_eligibility in RETRIEVAL_ELIGIBILITY
            else "blocked_unknown"
        ),
        "ingestion_eligibility": (
            ingestion_eligibility
            if ingestion_eligibility in INGESTION_ELIGIBILITY
            else "needs_review"
        ),
        "canonicality": canonicality if canonicality in CANONICALITY_LABELS else "unknown_review",
        "world_binding": world_binding if world_binding in WORLD_BINDINGS else "unknown",
        "evidence_category": evidence_category if evidence_category in EVIDENCE_CATEGORIES else "unknown",
        "reorg_status": reorg_status,
        "reorg_bucket": reorg_bucket if reorg_bucket in REORG_BUCKETS else "unknown_review",
        "reorg_reason": reorg_reason,
        "reorg_confidence": reorg_confidence,
        "requires_operator_review": requires_review,
        "metadata_basis": metadata_basis,
    }


def _path_id(root_id: str, run_id: str, relative_path: str) -> str:
    digest = hashlib.sha256(f"{root_id}\0{run_id}\0{relative_path}".encode("utf-8")).hexdigest()
    return f"cpath_{digest[:20]}"


def _row_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _iter_paths(root: Path, seeds: dict[str, Any]) -> list[Path]:
    seen: set[str] = set()
    queue: deque[Path] = deque()
    try:
        for child in sorted(root.iterdir(), key=lambda item: item.name):
            queue.append(child)
    except OSError:
        return []

    paths: list[Path] = []
    while queue:
        path = queue.popleft()
        try:
            relative_path = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if relative_path in seen:
            continue
        seen.add(relative_path)
        paths.append(path)

        path_type = _path_type(path)
        classification = classify_path(relative_path, path_type, "unknown", seeds)
        if not _should_descend(relative_path, classification, path_type):
            continue
        try:
            children = sorted(path.iterdir(), key=lambda item: item.name)
        except OSError:
            continue
        for child in children:
            queue.append(child)
    return paths


def build_corpus_path_records(
    *,
    root: Path = DEFAULT_ROOT,
    root_id: str = DEFAULT_ROOT_ID,
    run_id: str,
    git_head: str,
    seeds: dict[str, Any],
    hash_reader: Callable[[Path], str] = hash_file,
) -> list[CorpusPathRecord]:
    root = root.resolve()
    paths = _iter_paths(root, seeds)
    relative_paths = []
    for path in paths:
        try:
            relative_paths.append(path.relative_to(root).as_posix())
        except ValueError:
            continue
    tracked = tracked_paths(root)
    ignored = ignored_paths(root, relative_paths)

    records: list[CorpusPathRecord] = []
    for path in paths:
        try:
            relative_path = path.relative_to(root).as_posix()
        except ValueError:
            continue
        path_type = _path_type(path)
        size_bytes, mtime, ctime = _stat_metadata(path)
        tracked_status = tracked_status_for(relative_path, tracked, ignored)
        classification = classify_path(relative_path, path_type, tracked_status, seeds)

        content_hash = None
        hash_algorithm = None
        if _is_safe_hash_candidate(
            relative_path,
            path_type,
            classification["raw_content_eligibility"],
            size_bytes,
        ):
            try:
                content_hash = hash_reader(path)
                hash_algorithm = "sha256"
            except OSError:
                content_hash = None
                hash_algorithm = None

        parent = Path(relative_path).parent.as_posix()
        if parent == ".":
            parent = ""
        records.append(
            CorpusPathRecord(
                path_id=_path_id(root_id, run_id, relative_path),
                root_id=root_id,
                run_id=run_id,
                absolute_path=path.as_posix(),
                relative_path=relative_path,
                parent_relative_path=parent,
                path_name=Path(relative_path).name,
                path_type=path_type,
                tracked_status=tracked_status,
                git_head=git_head,
                size_bytes=size_bytes,
                mtime=mtime,
                ctime=ctime,
                content_hash=content_hash,
                hash_algorithm=hash_algorithm,
                body_read=False,
                runtime_authority=False,
                **classification,
            )
        )
    return records


def _insert_root(
    conn: sqlite3.Connection,
    *,
    root_id: str,
    root_kind: str,
    host_kind: str,
    owner_scope: str,
    absolute_root: str,
    root_label: str,
    status: str,
    project_id: str | None = None,
    client_id: str | None = None,
    instance_id: str | None = None,
    repo_url: str | None = None,
    repo_name: str | None = None,
    branch: str | None = None,
    commit_sha: str | None = None,
    remote_origin: str | None = None,
    canonical_status: str = "unknown",
    import_status: str = "unknown",
    mirror_of_root_id: str | None = None,
    lineage_source: str | None = None,
    now: str,
    notes: str | None = None,
) -> None:
    conn.execute(
        """
INSERT INTO corpus_roots (
  root_id, root_kind, host_kind, owner_scope, project_id, client_id, instance_id,
  absolute_root, root_label, status, repo_url, repo_name, branch, commit_sha,
  remote_origin, canonical_status, import_status, mirror_of_root_id,
  lineage_source, created_at, updated_at, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(root_id) DO UPDATE SET
  root_kind = excluded.root_kind,
  host_kind = excluded.host_kind,
  owner_scope = excluded.owner_scope,
  project_id = excluded.project_id,
  client_id = excluded.client_id,
  instance_id = excluded.instance_id,
  absolute_root = excluded.absolute_root,
  root_label = excluded.root_label,
  status = excluded.status,
  repo_url = excluded.repo_url,
  repo_name = excluded.repo_name,
  branch = excluded.branch,
  commit_sha = excluded.commit_sha,
  remote_origin = excluded.remote_origin,
  canonical_status = excluded.canonical_status,
  import_status = excluded.import_status,
  mirror_of_root_id = excluded.mirror_of_root_id,
  lineage_source = excluded.lineage_source,
  updated_at = excluded.updated_at,
  notes = excluded.notes
""".strip(),
        (
            root_id,
            root_kind,
            host_kind,
            owner_scope,
            project_id,
            client_id,
            instance_id,
            absolute_root,
            root_label,
            status,
            repo_url,
            repo_name,
            branch,
            commit_sha,
            remote_origin,
            canonical_status,
            import_status,
            mirror_of_root_id,
            lineage_source,
            now,
            now,
            notes,
        ),
    )


def _register_conceptual_roots(conn: sqlite3.Connection, now: str) -> None:
    for root in CONCEPTUAL_ROOTS:
        _insert_root(
            conn,
            root_id=root["root_id"],
            root_kind=root["root_kind"],
            host_kind=root["host_kind"],
            owner_scope=root["owner_scope"],
            absolute_root=root["absolute_root"],
            root_label=root["root_label"],
            status=root["status"],
            repo_url=root.get("repo_url"),
            repo_name=root.get("repo_name"),
            branch=root.get("branch"),
            commit_sha=root.get("commit_sha"),
            remote_origin=root.get("remote_origin"),
            canonical_status=root["canonical_status"],
            import_status=root["import_status"],
            mirror_of_root_id=root.get("mirror_of_root_id"),
            lineage_source=root.get("lineage_source"),
            now=now,
            notes="Conceptual future root only; not scanned in Corpus Atlas v0.6.",
        )


def _insert_run_start(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    root_id: str,
    started_at: str,
    git_context_payload: dict[str, str],
    source_basis: dict[str, Any],
) -> None:
    conn.execute(
        """
INSERT INTO corpus_atlas_runs (
  run_id, root_id, atlas_version, started_at, completed_at, git_head, git_branch,
  repo_root, scan_mode, max_depth_policy, path_count, top_level_count,
  body_ingested, raw_sensitive_data_stored, runtime_authority,
  activation_allowed, backend_execution_authorized, source_basis_json, notes
) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
  root_id = excluded.root_id,
  atlas_version = excluded.atlas_version,
  started_at = excluded.started_at,
  git_head = excluded.git_head,
  git_branch = excluded.git_branch,
  repo_root = excluded.repo_root,
  scan_mode = excluded.scan_mode,
  max_depth_policy = excluded.max_depth_policy,
  source_basis_json = excluded.source_basis_json,
  notes = excluded.notes
""".strip(),
        (
            run_id,
            root_id,
            ATLAS_VERSION,
            started_at,
            git_context_payload["git_head"],
            git_context_payload["git_branch"],
            git_context_payload["repo_root"],
            "bounded_metadata_atlas_no_raw_no_go",
            stable_json(SELECTED_SCAN_MAX_DEPTH).strip(),
            stable_json(source_basis).strip(),
            "Metadata/location classification only; no arbitrary body ingestion or runtime activation.",
        ),
    )


def _insert_path(conn: sqlite3.Connection, record: CorpusPathRecord, now: str) -> None:
    conn.execute(
        """
INSERT INTO corpus_paths (
  path_id, run_id, root_id, absolute_path, relative_path, parent_relative_path,
  path_name, path_type, tracked_status, git_head, size_bytes, mtime, ctime,
  content_hash, hash_algorithm, source_role, freshness_label, sensitivity_label,
  raw_content_eligibility, retrieval_eligibility, ingestion_eligibility,
  canonicality, world_binding, evidence_category, reorg_status,
  reorg_bucket, reorg_reason, reorg_confidence, requires_operator_review,
  metadata_basis, body_read, runtime_authority, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(run_id, root_id, relative_path) DO UPDATE SET
  absolute_path = excluded.absolute_path,
  parent_relative_path = excluded.parent_relative_path,
  path_name = excluded.path_name,
  path_type = excluded.path_type,
  tracked_status = excluded.tracked_status,
  git_head = excluded.git_head,
  size_bytes = excluded.size_bytes,
  mtime = excluded.mtime,
  ctime = excluded.ctime,
  content_hash = excluded.content_hash,
  hash_algorithm = excluded.hash_algorithm,
  source_role = excluded.source_role,
  freshness_label = excluded.freshness_label,
  sensitivity_label = excluded.sensitivity_label,
  raw_content_eligibility = excluded.raw_content_eligibility,
  retrieval_eligibility = excluded.retrieval_eligibility,
  ingestion_eligibility = excluded.ingestion_eligibility,
  canonicality = excluded.canonicality,
  world_binding = excluded.world_binding,
  evidence_category = excluded.evidence_category,
  reorg_status = excluded.reorg_status,
  reorg_bucket = excluded.reorg_bucket,
  reorg_reason = excluded.reorg_reason,
  reorg_confidence = excluded.reorg_confidence,
  requires_operator_review = excluded.requires_operator_review,
  metadata_basis = excluded.metadata_basis,
  body_read = excluded.body_read,
  runtime_authority = excluded.runtime_authority
""".strip(),
        (
            record.path_id,
            record.run_id,
            record.root_id,
            record.absolute_path,
            record.relative_path,
            record.parent_relative_path,
            record.path_name,
            record.path_type,
            record.tracked_status,
            record.git_head,
            record.size_bytes,
            record.mtime,
            record.ctime,
            record.content_hash,
            record.hash_algorithm,
            record.source_role,
            record.freshness_label,
            record.sensitivity_label,
            record.raw_content_eligibility,
            record.retrieval_eligibility,
            record.ingestion_eligibility,
            record.canonicality,
            record.world_binding,
            record.evidence_category,
            record.reorg_status,
            record.reorg_bucket,
            record.reorg_reason,
            record.reorg_confidence,
            1 if record.requires_operator_review else 0,
            record.metadata_basis,
            1 if record.body_read else 0,
            1 if record.runtime_authority else 0,
            now,
        ),
    )


def _insert_standard_labels(conn: sqlite3.Connection, record: CorpusPathRecord, now: str) -> None:
    labels = {
        "raw_content_eligibility": record.raw_content_eligibility,
        "freshness_label": record.freshness_label,
        "source_role": record.source_role,
        "sensitivity_label": record.sensitivity_label,
        "evidence_category": record.evidence_category,
        "tracked_status": record.tracked_status,
        "reorg_bucket": record.reorg_bucket,
        "retrieval_eligibility": record.retrieval_eligibility,
        "ingestion_eligibility": record.ingestion_eligibility,
        "canonicality": record.canonicality,
    }
    for name, value in labels.items():
        label_id = _row_id("clabel", record.path_id, name, value, record.metadata_basis)
        conn.execute(
            """
INSERT INTO corpus_path_labels (
  label_id, path_id, label_name, label_value, label_basis, created_at
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(path_id, label_name, label_value, label_basis) DO NOTHING
""".strip(),
            (label_id, record.path_id, name, value, record.metadata_basis, now),
        )


def _insert_world_binding(
    conn: sqlite3.Connection,
    *,
    path_id: str,
    world_id: str,
    confidence: float,
    basis: str,
    now: str,
) -> None:
    binding_id = _row_id("cworld", path_id, world_id, basis)
    conn.execute(
        """
INSERT INTO corpus_world_bindings (
  binding_id, path_id, world_id, confidence, binding_basis, created_at
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(path_id, world_id, binding_basis) DO NOTHING
""".strip(),
        (binding_id, path_id, world_id, confidence, basis, now),
    )


def _insert_artifact_links(
    conn: sqlite3.Connection,
    *,
    record: CorpusPathRecord,
    seeds: dict[str, Any],
    now: str,
) -> None:
    for artifact in seeds.get("artifact_by_path", {}).get(record.relative_path, []):
        artifact_id = artifact.get("artifact_id")
        if not artifact_id:
            continue
        link_id = _row_id("cartifact", record.path_id, artifact_id, "artifact_registry.json")
        conn.execute(
            """
INSERT INTO corpus_artifact_links (
  link_id, path_id, artifact_id, artifact_kind, source_read_model, link_basis, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(path_id, artifact_id, source_read_model) DO NOTHING
""".strip(),
            (
                link_id,
                record.path_id,
                artifact_id,
                artifact.get("artifact_type", "unknown"),
                "generated/read_models/artifact_registry.json",
                "artifact_registry_path_or_command_match",
                now,
            ),
        )


def _insert_freshness_signal(
    conn: sqlite3.Connection,
    *,
    record: CorpusPathRecord,
    seeds: dict[str, Any],
    now: str,
) -> None:
    signal = seeds.get("freshness_by_path", {}).get(record.relative_path)
    if not signal:
        return
    signal_id = _row_id("cfresh", record.path_id, "evidence_freshness_state")
    conn.execute(
        """
INSERT INTO corpus_freshness_signals (
  signal_id, path_id, signal_type, signal_value, signal_basis, observed_at
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(path_id, signal_type, signal_basis) DO NOTHING
""".strip(),
        (
            signal_id,
            record.path_id,
            "evidence_freshness_state",
            signal.get("freshness_state", "unknown"),
            signal.get("basis", "generated/read_models/evidence_freshness.json"),
            now,
        ),
    )


def _insert_sensitivity_label(conn: sqlite3.Connection, record: CorpusPathRecord, now: str) -> None:
    label_id = _row_id("csens", record.path_id, record.sensitivity_label, record.metadata_basis)
    conn.execute(
        """
INSERT INTO corpus_sensitivity_labels (
  label_id, path_id, sensitivity_label, label_basis, created_at
) VALUES (?, ?, ?, ?, ?)
ON CONFLICT(path_id, sensitivity_label, label_basis) DO NOTHING
""".strip(),
        (label_id, record.path_id, record.sensitivity_label, record.metadata_basis, now),
    )


def _insert_reorg_candidate(conn: sqlite3.Connection, record: CorpusPathRecord, now: str) -> None:
    candidate_id = _row_id("creorg", record.path_id, record.reorg_bucket, "advisory_only")
    conn.execute(
        """
INSERT INTO corpus_reorg_candidates (
  candidate_id, path_id, current_location, suggested_bucket, candidate_action,
  reason, confidence, requires_operator_review, advisory_only, moved, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?)
ON CONFLICT(path_id, suggested_bucket, candidate_action) DO UPDATE SET
  reason = excluded.reason,
  confidence = excluded.confidence,
  requires_operator_review = excluded.requires_operator_review,
  advisory_only = 1,
  moved = 0
""".strip(),
        (
            candidate_id,
            record.path_id,
            record.relative_path,
            record.reorg_bucket,
            "classify_only_no_filesystem_change",
            record.reorg_reason,
            record.reorg_confidence,
            1 if record.requires_operator_review else 0,
            now,
        ),
    )


def _insert_mirror_candidate(conn: sqlite3.Connection, record: CorpusPathRecord, now: str) -> None:
    if record.relative_path.startswith("generated/read_models/"):
        mirror_id = _row_id("cmirror", record.path_id, "mac_generated_read_models", record.relative_path)
        conn.execute(
            """
INSERT INTO corpus_mirror_candidates (
  mirror_id, path_id, mirror_root_id, suggested_relative_path, mirror_kind,
  status, basis, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(path_id, mirror_root_id, suggested_relative_path) DO NOTHING
""".strip(),
            (
                mirror_id,
                record.path_id,
                "mac_generated_read_models",
                record.relative_path,
                "future_read_model_mirror",
                "candidate_not_scanned",
                "schema supports later Mac mirror mapping; Mac not scanned in this lane",
                now,
            ),
        )


def _insert_seed_world_bindings(
    conn: sqlite3.Connection,
    *,
    records_by_relative_path: dict[str, CorpusPathRecord],
    seeds: dict[str, Any],
    now: str,
) -> None:
    registry_record = records_by_relative_path.get("generated/read_models/world_domain_registry.json")
    if not registry_record:
        return
    for world_id in seeds.get("world_ids", []):
        _insert_world_binding(
            conn,
            path_id=registry_record.path_id,
            world_id=world_id,
            confidence=1.0,
            basis="world_domain_registry_read_model_represents_registered_world",
            now=now,
        )


def store_corpus_atlas_records(
    *,
    db_path: str | Path,
    root: Path,
    root_id: str,
    host_kind: str,
    run_id: str,
    started_at: str,
    git_context_payload: dict[str, str],
    records: list[CorpusPathRecord],
    seeds: dict[str, Any],
) -> CorpusAtlasResult:
    path = init_corpus_atlas_schema(db_path)
    now = utc_now()
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        _insert_root(
            conn,
            root_id=root_id,
            root_kind="operating_home_repo",
            host_kind=host_kind,
            owner_scope="internal_platform",
            absolute_root=root.as_posix(),
            root_label="PC WSL /home/openclaw operating home",
            status="active_metadata_root",
            repo_name="openclaw",
            branch=git_context_payload.get("git_branch"),
            commit_sha=git_context_payload.get("git_head"),
            remote_origin=git_context_payload.get("remote_origin"),
            canonical_status="canonical_current",
            import_status="scanned_metadata_only",
            lineage_source="local_operating_home",
            now=now,
            notes="Initial active root for Corpus Atlas v0.6; future roots are registered conceptually but not scanned here.",
        )
        _register_conceptual_roots(conn, now)
        source_basis = {
            "read_model_seed_files": sorted(seeds.get("read_models", {}).keys()),
            "truth_registry_seeded": bool(seeds.get("truth_registry_by_path")),
            "whole_repo_body_ingest": False,
            "no_go_raw_read": False,
            "runtime_authority": False,
        }
        _insert_run_start(
            conn,
            run_id=run_id,
            root_id=root_id,
            started_at=started_at,
            git_context_payload=git_context_payload,
            source_basis=source_basis,
        )

        for record in records:
            _insert_path(conn, record, now)
            _insert_standard_labels(conn, record, now)
            _insert_world_binding(
                conn,
                path_id=record.path_id,
                world_id=record.world_binding,
                confidence=0.75 if record.world_binding not in {"unknown", "no_world"} else 0.4,
                basis="path_classification",
                now=now,
            )
            _insert_artifact_links(conn, record=record, seeds=seeds, now=now)
            _insert_freshness_signal(conn, record=record, seeds=seeds, now=now)
            _insert_sensitivity_label(conn, record, now)
            _insert_reorg_candidate(conn, record, now)
            _insert_mirror_candidate(conn, record, now)

        _insert_seed_world_bindings(
            conn,
            records_by_relative_path={record.relative_path: record for record in records},
            seeds=seeds,
            now=now,
        )

        top_level_count = sum(1 for record in records if not record.parent_relative_path)
        conn.execute(
            """
UPDATE corpus_atlas_runs
SET completed_at = ?, path_count = ?, top_level_count = ?
WHERE run_id = ?
""".strip(),
            (now, len(records), top_level_count, run_id),
        )
        conn.commit()
    finally:
        conn.close()

    return CorpusAtlasResult(
        run_id=run_id,
        root_id=root_id,
        db_path=path,
        root=root.as_posix(),
        path_count=len(records),
        top_level_count=sum(1 for record in records if not record.parent_relative_path),
        counts=_count_records(records),
    )


def _count_records(records: list[CorpusPathRecord]) -> dict[str, dict[str, int]]:
    fields = {
        "source_role": "source_role",
        "freshness_label": "freshness_label",
        "sensitivity_label": "sensitivity_label",
        "raw_content_eligibility": "raw_content_eligibility",
        "retrieval_eligibility": "retrieval_eligibility",
        "ingestion_eligibility": "ingestion_eligibility",
        "canonicality": "canonicality",
        "world_binding": "world_binding",
        "reorg_bucket": "reorg_bucket",
    }
    counts: dict[str, dict[str, int]] = {}
    for label, attr in fields.items():
        counter = Counter(getattr(record, attr) for record in records)
        counts[label] = dict(sorted(counter.items()))
    return counts


def run_corpus_atlas(
    *,
    db_path: str | Path | None = None,
    root: str | Path = DEFAULT_ROOT,
    root_id: str = DEFAULT_ROOT_ID,
    host_kind: str = DEFAULT_HOST_KIND,
    run_id: str | None = None,
    hash_reader: Callable[[Path], str] = hash_file,
) -> CorpusAtlasResult:
    root_path = Path(root).resolve()
    db_path = str(db_path or DEFAULT_DB_PATH)
    init_corpus_atlas_schema(db_path)
    started_at = utc_now()
    git_context_payload = git_context(root_path)
    run_id = run_id or f"catlas_{started_at.replace(':', '').replace('+', 'Z')}_{git_context_payload['git_head']}"
    seeds = load_seed_signals(root_path, db_path=db_path)
    records = build_corpus_path_records(
        root=root_path,
        root_id=root_id,
        run_id=run_id,
        git_head=git_context_payload["git_head"],
        seeds=seeds,
        hash_reader=hash_reader,
    )
    return store_corpus_atlas_records(
        db_path=db_path,
        root=root_path,
        root_id=root_id,
        host_kind=host_kind,
        run_id=run_id,
        started_at=started_at,
        git_context_payload=git_context_payload,
        records=records,
        seeds=seeds,
    )


def latest_run_id(db_path: str | Path | None = None) -> str | None:
    path = init_corpus_atlas_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            """
SELECT run_id
FROM corpus_atlas_runs
ORDER BY completed_at DESC, started_at DESC
LIMIT 1
""".strip()
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _group_counts(conn: sqlite3.Connection, run_id: str, column: str) -> dict[str, int]:
    allowed = {
        "source_role",
        "freshness_label",
        "sensitivity_label",
        "raw_content_eligibility",
        "world_binding",
        "reorg_bucket",
        "path_type",
        "tracked_status",
        "retrieval_eligibility",
        "ingestion_eligibility",
        "canonicality",
    }
    if column not in allowed:
        raise ValueError(f"unsupported count column: {column}")
    rows = conn.execute(
        f"SELECT {column}, COUNT(*) FROM corpus_paths WHERE run_id = ? GROUP BY {column} ORDER BY {column}",
        (run_id,),
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def _sample_paths(
    conn: sqlite3.Connection,
    run_id: str,
    where_sql: str,
    params: tuple[Any, ...] = (),
    limit: int = 12,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
SELECT relative_path, path_type, source_role, freshness_label, sensitivity_label,
       raw_content_eligibility, retrieval_eligibility, ingestion_eligibility,
       canonicality, world_binding, reorg_bucket
FROM corpus_paths
WHERE run_id = ? AND ({where_sql})
ORDER BY relative_path
LIMIT ?
""".strip(),
        (run_id, *params, limit),
    ).fetchall()
    keys = (
        "relative_path",
        "path_type",
        "source_role",
        "freshness_label",
        "sensitivity_label",
        "raw_content_eligibility",
        "retrieval_eligibility",
        "ingestion_eligibility",
        "canonicality",
        "world_binding",
        "reorg_bucket",
    )
    return [dict(zip(keys, row)) for row in rows]


def _root_registry(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
SELECT root_id, root_kind, host_kind, owner_scope, project_id, client_id,
       instance_id, absolute_root, root_label, status, repo_url, repo_name,
       branch, commit_sha, remote_origin, canonical_status, import_status,
       mirror_of_root_id, lineage_source
FROM corpus_roots
ORDER BY root_id
""".strip()
    ).fetchall()
    keys = (
        "root_id",
        "root_kind",
        "host_kind",
        "owner_scope",
        "project_id",
        "client_id",
        "instance_id",
        "absolute_root",
        "root_label",
        "status",
        "repo_url",
        "repo_name",
        "branch",
        "commit_sha",
        "remote_origin",
        "canonical_status",
        "import_status",
        "mirror_of_root_id",
        "lineage_source",
    )
    return [dict(zip(keys, row)) for row in rows]


def _mirror_candidates(conn: sqlite3.Connection, run_id: str, limit: int = 30) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
SELECT p.relative_path, m.mirror_root_id, m.suggested_relative_path, m.mirror_kind,
       m.status, m.basis
FROM corpus_mirror_candidates m
JOIN corpus_paths p ON p.path_id = m.path_id
WHERE p.run_id = ?
ORDER BY p.relative_path, m.mirror_root_id
LIMIT ?
""".strip(),
        (run_id, limit),
    ).fetchall()
    keys = (
        "relative_path",
        "mirror_root_id",
        "suggested_relative_path",
        "mirror_kind",
        "status",
        "basis",
    )
    return [dict(zip(keys, row)) for row in rows]


def build_atlas_report(db_path: str | Path | None = None, run_id: str | None = None) -> dict[str, Any]:
    path = init_corpus_atlas_schema(db_path)
    run_id = run_id or latest_run_id(path)
    if not run_id:
        return {
            "atlas_version": ATLAS_VERSION,
            "run_id": None,
            "status": "no_runs",
            "runtime_authority": False,
            "activation_allowed": False,
        }
    conn = sqlite3.connect(path)
    try:
        run = conn.execute(
            """
SELECT run_id, root_id, started_at, completed_at, git_head, git_branch, repo_root,
       scan_mode, path_count, top_level_count, runtime_authority, activation_allowed,
       backend_execution_authorized, body_ingested, raw_sensitive_data_stored
FROM corpus_atlas_runs
WHERE run_id = ?
""".strip(),
            (run_id,),
        ).fetchone()
        root = conn.execute(
            """
SELECT root_id, root_kind, host_kind, owner_scope, project_id, client_id,
       instance_id, absolute_root, root_label, status, repo_url, repo_name,
       branch, commit_sha, remote_origin, canonical_status, import_status,
       mirror_of_root_id, lineage_source
FROM corpus_roots
WHERE root_id = ?
""".strip(),
            (run[1],),
        ).fetchone()
        counts = {
            "source_role": _group_counts(conn, run_id, "source_role"),
            "freshness_label": _group_counts(conn, run_id, "freshness_label"),
            "sensitivity_label": _group_counts(conn, run_id, "sensitivity_label"),
            "raw_content_eligibility": _group_counts(conn, run_id, "raw_content_eligibility"),
            "retrieval_eligibility": _group_counts(conn, run_id, "retrieval_eligibility"),
            "ingestion_eligibility": _group_counts(conn, run_id, "ingestion_eligibility"),
            "canonicality": _group_counts(conn, run_id, "canonicality"),
            "world_binding": _group_counts(conn, run_id, "world_binding"),
            "reorg_bucket": _group_counts(conn, run_id, "reorg_bucket"),
            "tracked_status": _group_counts(conn, run_id, "tracked_status"),
            "path_type": _group_counts(conn, run_id, "path_type"),
        }
        top_level = _sample_paths(conn, run_id, "parent_relative_path = ''", limit=40)
        report = {
            "atlas_version": ATLAS_VERSION,
            "run": {
                "run_id": run[0],
                "root_id": run[1],
                "started_at": run[2],
                "completed_at": run[3],
                "git_head": run[4],
                "git_branch": run[5],
                "repo_root": run[6],
                "scan_mode": run[7],
                "path_count": run[8],
                "top_level_count": run[9],
                "runtime_authority": bool(run[10]),
                "activation_allowed": bool(run[11]),
                "backend_execution_authorized": bool(run[12]),
                "body_ingested": bool(run[13]),
                "raw_sensitive_data_stored": bool(run[14]),
            },
            "root": {
                "root_id": root[0],
                "root_kind": root[1],
                "host_kind": root[2],
                "owner_scope": root[3],
                "project_id": root[4],
                "client_id": root[5],
                "instance_id": root[6],
                "absolute_root": root[7],
                "root_label": root[8],
                "status": root[9],
                "repo_url": root[10],
                "repo_name": root[11],
                "branch": root[12],
                "commit_sha": root[13],
                "remote_origin": root[14],
                "canonical_status": root[15],
                "import_status": root[16],
                "mirror_of_root_id": root[17],
                "lineage_source": root[18],
            },
            "counts": counts,
            "top_level_atlas": top_level,
            "multi_root_registry": _root_registry(conn),
            "future_mirror_candidates": _mirror_candidates(conn, run_id, limit=30),
            "legacy_root_readiness": [
                root
                for root in _root_registry(conn)
                if root["root_kind"] == "legacy_git_repo"
            ],
            "no_go_sensitive_boundaries": _sample_paths(
                conn,
                run_id,
                "raw_content_eligibility IN ('no_go','metadata_only') AND sensitivity_label IN ('credential_boundary','finance_boundary','legal_tax_boundary','private','runtime_log_boundary','no_go','metadata_only')",
                limit=30,
            ),
            "current_generated_source_of_truth_candidates": _sample_paths(
                conn,
                run_id,
                "canonicality IN ('canonical_current','generated_current')",
                limit=30,
            ),
            "canonical_current_candidates": _sample_paths(
                conn,
                run_id,
                "canonicality = 'canonical_current'",
                limit=30,
            ),
            "overbroad_current_source_of_truth_candidates": _sample_paths(
                conn,
                run_id,
                "freshness_label = 'current_source_of_truth' AND canonicality != 'canonical_current'",
                limit=30,
            ),
            "stale_historical_scratch_candidates": _sample_paths(
                conn,
                run_id,
                "freshness_label IN ('stale_possible','historical','scratch','experiment','superseded','deprecated')",
                limit=30,
            ),
            "unknown_review_queue": _sample_paths(
                conn,
                run_id,
                "retrieval_eligibility IN ('blocked_unknown','needs_operator_review') OR ingestion_eligibility = 'needs_review' OR canonicality = 'unknown_review'",
                limit=30,
            ),
            "generated_read_model_artifact_map": _sample_paths(
                conn,
                run_id,
                "relative_path LIKE 'generated/read_models/%'",
                limit=30,
            ),
            "world_bound_paths": _sample_paths(
                conn,
                run_id,
                "world_binding NOT IN ('unknown','no_world')",
                limit=30,
            ),
            "reorg_candidates": _sample_paths(
                conn,
                run_id,
                "reorg_bucket != 'keep_canonical'",
                limit=30,
            ),
            "ingestion_eligibility": _sample_paths(
                conn,
                run_id,
                "ingestion_eligibility IN ('ingest_allowed','metadata_only','no_go','needs_review','generated_snapshot_only','receipt_summary_only','not_for_ingestion')",
                limit=30,
            ),
            "retrieval_eligibility": _sample_paths(
                conn,
                run_id,
                "retrieval_eligibility IN ('retrievable','metadata_only','blocked_no_go','blocked_sensitive','blocked_unknown','needs_operator_review','generated_read_model_only','receipt_metadata_only')",
                limit=30,
            ),
            "claims_not_made": [
                "raw_sensitive_data_storage",
                "arbitrary_body_ingest",
                "source_text_as_truth",
                "runtime_activation",
                "agent_activation",
                "broker_connection",
                "external_api_call",
                "filesystem_reorganization",
                "mac_scan",
            ],
        }
        return report
    finally:
        conn.close()


def _count_line(title: str, counts: dict[str, int]) -> str:
    if not counts:
        return f"- {title}: none"
    rendered = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    return f"- {title}: {rendered}"


def _sample_lines(samples: list[dict[str, Any]], *, max_items: int = 8) -> list[str]:
    if not samples:
        return ["- none"]
    lines = []
    for item in samples[:max_items]:
        lines.append(
            "- "
            + display_path(item["relative_path"])
            + f" ({item['source_role']}, {item['freshness_label']}, "
            + f"{item['canonicality']}, {item['retrieval_eligibility']}, "
            + f"{item['ingestion_eligibility']}, {item['reorg_bucket']})"
        )
    return lines


def format_atlas_report(report: dict[str, Any]) -> str:
    if report.get("status") == "no_runs":
        return "Corpus Atlas v0.6\n\nNo atlas runs are recorded."
    run = report["run"]
    root = report["root"]
    counts = report["counts"]
    lines = [
        "Corpus Atlas v0.6",
        "",
        "Evidence:",
        f"- Run `{run['run_id']}` scanned `{root['absolute_root']}` as `{root['root_id']}`.",
        f"- Git `{run['git_branch']}` at `{run['git_head']}`; recorded {run['path_count']} paths, including {run['top_level_count']} top-level paths.",
        _count_line("Source roles", counts["source_role"]),
        _count_line("Freshness labels", counts["freshness_label"]),
        _count_line("Sensitivity labels", counts["sensitivity_label"]),
        _count_line("Raw-content eligibility", counts["raw_content_eligibility"]),
        _count_line("Retrieval eligibility", counts["retrieval_eligibility"]),
        _count_line("Ingestion eligibility", counts["ingestion_eligibility"]),
        _count_line("Canonicality", counts["canonicality"]),
        _count_line("World bindings", counts["world_binding"]),
        _count_line("Reorg buckets", counts["reorg_bucket"]),
        "",
        "No-Go / Sensitive Boundaries:",
        *_sample_lines(report["no_go_sensitive_boundaries"]),
        "",
        "Current / Generated Source Candidates:",
        *_sample_lines(report["current_generated_source_of_truth_candidates"]),
        "",
        "Unknown Review Queue:",
        *_sample_lines(report["unknown_review_queue"]),
        "",
        "Overbroad Current Source-of-Truth Candidates:",
        *_sample_lines(report["overbroad_current_source_of_truth_candidates"]),
        "",
        "Stale / Historical / Scratch Candidates:",
        *_sample_lines(report["stale_historical_scratch_candidates"]),
        "",
        "Generated Read-Model Artifact Map:",
        *_sample_lines(report["generated_read_model_artifact_map"]),
        "",
        "World-Bound Paths:",
        *_sample_lines(report["world_bound_paths"]),
        "",
        "Reorg Candidates:",
        *_sample_lines(report["reorg_candidates"]),
        "",
        "Multi-Root Registry:",
        *[
            "- "
            + root["root_id"]
            + f" ({root['root_kind']}, {root['owner_scope']}, {root['canonical_status']}, {root['import_status']})"
            for root in report["multi_root_registry"][:8]
        ],
        "",
        "Boundary:",
        "- Atlas rows are metadata/location classifications, generated read-model facts, and retrieval/ingestion gates only.",
        "- `body_ingested=false`; `raw_sensitive_data_stored=false`; no no-go content hashes are recorded.",
        "- Unknown paths are not retrievable or ingestible without operator review.",
        "- Reorg rows are advisory; `moved=0` and no filesystem changes are authorized.",
        "- `runtime_authority=false`; `activation_allowed=false`; `backend_execution_authorized=false`.",
    ]
    return "\n".join(lines)


def write_report_artifacts(
    report: dict[str, Any],
    *,
    report_root: str | Path = DEFAULT_REPORT_ROOT,
) -> dict[str, str]:
    root = Path(report_root)
    if not root.is_absolute():
        root = DEFAULT_ROOT / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "corpus_atlas_latest.json"
    md_path = root / "corpus_atlas_latest.md"
    json_path.write_text(stable_json(report), encoding="utf-8")
    md_path.write_text(format_atlas_report(report) + "\n", encoding="utf-8")
    return {
        "json": json_path.as_posix(),
        "markdown": md_path.as_posix(),
    }


def query_report_section(
    *,
    db_path: str | Path | None = None,
    run_id: str | None = None,
    section: str = "summary",
) -> dict[str, Any]:
    report = build_atlas_report(db_path=db_path, run_id=run_id)
    if report.get("status") == "no_runs":
        return report
    if section == "summary":
        return {
            "atlas_version": report["atlas_version"],
            "run": report["run"],
            "root": report["root"],
            "counts": report["counts"],
        }
    section_map = {
        "top-level": "top_level_atlas",
        "no-go": "no_go_sensitive_boundaries",
        "generated-read-models": "generated_read_model_artifact_map",
        "stale": "stale_historical_scratch_candidates",
        "world-bound": "world_bound_paths",
        "reorg": "reorg_candidates",
        "ingestion": "ingestion_eligibility",
        "retrieval": "retrieval_eligibility",
        "unknown-review": "unknown_review_queue",
        "canonical-current": "canonical_current_candidates",
        "overbroad-current": "overbroad_current_source_of_truth_candidates",
        "multi-root": "multi_root_registry",
        "mirrors": "future_mirror_candidates",
        "legacy-root": "legacy_root_readiness",
    }
    if section not in section_map:
        raise ValueError(f"unknown report section: {section}")
    payload = {
        "atlas_version": report["atlas_version"],
        "run_id": report["run"]["run_id"],
        "section": section,
        "items": report[section_map[section]],
    }
    count_key_by_section = {
        "retrieval": "retrieval_eligibility",
        "ingestion": "ingestion_eligibility",
        "unknown-review": "retrieval_eligibility",
        "canonical-current": "canonicality",
        "overbroad-current": "canonicality",
        "generated-read-models": "ingestion_eligibility",
        "no-go": "retrieval_eligibility",
        "stale": "canonicality",
        "reorg": "reorg_bucket",
    }
    count_key = count_key_by_section.get(section)
    if count_key:
        payload["counts"] = report["counts"].get(count_key, {})
    return payload
