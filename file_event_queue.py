"""File Watcher Event Queue v0 for OpenClaw.

This module implements a bounded, poll/snapshot-based file event queue. It
records metadata changes for explicit allowlisted roots only. It does not run a
daemon, read raw private bodies, ingest file contents, move files, delete files,
activate tools, or execute actions from file events.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger


FILE_EVENT_QUEUE_VERSION = "file_event_queue_v0"

DEFAULT_ALLOWED_ROOTS = (
    Path("/home/openclaw"),
    Path("/mnt/e/openclaw"),
)

DEFAULT_ROOT_IDS = {
    "/home/openclaw": "pc_wsl_home_openclaw",
    "/mnt/e/openclaw": "pc_wsl_e_openclaw_transfer",
}

BROAD_ROOTS = {
    "/",
    "/home",
    "/mnt",
    "/mnt/c",
    "/mnt/e",
    "",
}

MAX_HASH_BYTES = 25_000_000

EVENT_TYPES = {
    "observed_new",
    "observed_modified",
    "observed_missing",
    "possible_move",
    "unchanged",
}

PATH_TYPES = {
    "file",
    "directory",
    "symlink",
    "unknown",
}

QUEUE_STATUSES = {
    "queued",
    "classified_metadata",
    "needs_operator_review",
    "blocked_no_go",
    "ignored",
}

NO_GO_PARTS = {
    ".ssh",
    ".gnupg",
    ".google-secrets",
    ".private",
    ".openclaw_sensitive_no_go",
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

METADATA_ONLY_PARTS = {
    ".agents",
    ".ahub",
    ".aider",
    ".aider.tags.cache.v4",
    ".cargo",
    ".git",
    ".cache",
    ".codex",
    ".claude",
    ".config",
    ".dotnet",
    ".feynman",
    ".gemini",
    ".hermes",
    ".kimi",
    ".landscape",
    ".local",
    ".npm",
    ".nvm",
    ".ollama",
    ".openclaw",
    ".pytest_cache",
    ".rustup",
    ".venv",
    ".vscode",
    ".vscode-server",
    "__pycache__",
    "chief_env",
    "node_modules",
    "site-packages",
    "target",
    "dist",
}

NO_GO_FILE_HINTS = (
    ".env",
    "aider.chat.history",
    "aider.input.history",
    "bash_history",
    "credential",
    "credentials",
    "do_not_crawl",
    "no_go",
    "pii_vault",
    "private",
    "sensitive_no_go",
    "secret",
    "token",
)

SKIP_DESCEND_RELATIVE_PREFIXES = {
    "polish_loop/tasks",
}

METADATA_ONLY_SUFFIXES = {
    ".db",
    ".lock",
    ".log",
    ".sqlite",
    ".sqlite3",
}

AUDIO_SUFFIXES = {".aif", ".aiff", ".flac", ".m4a", ".mp3", ".wav"}
VIDEO_SUFFIXES = {".mov", ".mp4", ".m4v", ".avi"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"}
SOURCE_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".swift",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}
SAFE_HASH_FILE_KINDS = {
    "generated_read_model",
    "markdown_doc",
    "report_bridge_package",
    "source_code",
}

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "network_authority": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "raw_content_read": False,
    "raw_body_stored": False,
}


@dataclass(frozen=True)
class FileMetadata:
    root_id: str
    absolute_root: str
    relative_path: str
    absolute_path: str
    path_type: str
    size_bytes: int | None
    mtime: str | None
    ctime: str | None
    safe_hash: str | None
    hash_algorithm: str | None
    no_go_boundary: bool
    sensitivity_hint: str
    world_hint: str
    file_kind_hint: str
    hash_status: str
    hash_reason: str


@dataclass(frozen=True)
class FileEventSnapshotResult:
    run_id: str
    db_path: str
    root_id: str
    absolute_root: str
    observed_path_count: int
    event_counts: dict[str, int]
    queue_counts: dict[str, int]
    file_kind_counts: dict[str, int]
    no_go_count: int
    hashed_count: int
    possible_move_count: int


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS file_event_runs (
  run_id TEXT PRIMARY KEY,
  queue_version TEXT NOT NULL,
  root_id TEXT NOT NULL,
  absolute_root TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  previous_run_id TEXT,
  observed_path_count INTEGER NOT NULL DEFAULT 0,
  event_count INTEGER NOT NULL DEFAULT 0,
  queued_count INTEGER NOT NULL DEFAULT 0,
  no_go_count INTEGER NOT NULL DEFAULT 0,
  hashed_count INTEGER NOT NULL DEFAULT 0,
  possible_move_count INTEGER NOT NULL DEFAULT 0,
  max_hash_bytes INTEGER NOT NULL,
  raw_content_read INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS file_event_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  root_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  absolute_path TEXT NOT NULL,
  path_type TEXT NOT NULL,
  size_bytes INTEGER,
  mtime TEXT,
  ctime TEXT,
  safe_hash TEXT,
  hash_algorithm TEXT,
  hash_status TEXT NOT NULL,
  hash_reason TEXT NOT NULL,
  no_go_boundary INTEGER NOT NULL DEFAULT 0,
  sensitivity_hint TEXT NOT NULL,
  world_hint TEXT NOT NULL,
  file_kind_hint TEXT NOT NULL,
  raw_content_read INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  observed_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES file_event_runs(run_id) ON DELETE CASCADE,
  UNIQUE(run_id, root_id, relative_path)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS file_event_observations (
  event_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  root_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  absolute_path TEXT,
  event_type TEXT NOT NULL,
  path_type TEXT NOT NULL,
  size_bytes INTEGER,
  mtime TEXT,
  ctime TEXT,
  safe_hash TEXT,
  hash_algorithm TEXT,
  previous_path TEXT,
  current_path TEXT,
  raw_content_read INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  no_go_boundary INTEGER NOT NULL DEFAULT 0,
  sensitivity_hint TEXT NOT NULL,
  world_hint TEXT NOT NULL,
  file_kind_hint TEXT NOT NULL,
  queue_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES file_event_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS file_event_queue (
  queue_id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  root_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  event_type TEXT NOT NULL,
  queue_status TEXT NOT NULL,
  classification_hint_id TEXT,
  queued_at TEXT NOT NULL,
  processed_at TEXT,
  notes TEXT,
  FOREIGN KEY (event_id) REFERENCES file_event_observations(event_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS file_event_path_aliases (
  alias_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  root_id TEXT NOT NULL,
  previous_path TEXT NOT NULL,
  current_path TEXT NOT NULL,
  safe_hash TEXT,
  size_bytes INTEGER,
  confidence REAL NOT NULL,
  basis TEXT NOT NULL,
  advisory_only INTEGER NOT NULL DEFAULT 1,
  file_moved INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES file_event_runs(run_id) ON DELETE CASCADE,
  UNIQUE(run_id, root_id, previous_path, current_path)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS file_event_classification_hints (
  hint_id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  root_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  sensitivity_hint TEXT NOT NULL,
  world_hint TEXT NOT NULL,
  file_kind_hint TEXT NOT NULL,
  basis TEXT NOT NULL,
  confidence REAL NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (event_id) REFERENCES file_event_observations(event_id) ON DELETE CASCADE
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_file_event_runs_root ON file_event_runs(root_id, completed_at)",
        "CREATE INDEX IF NOT EXISTS idx_file_event_snapshots_run ON file_event_snapshots(run_id, root_id)",
        "CREATE INDEX IF NOT EXISTS idx_file_event_observations_run ON file_event_observations(run_id, event_type)",
        "CREATE INDEX IF NOT EXISTS idx_file_event_queue_status ON file_event_queue(run_id, queue_status)",
        "CREATE INDEX IF NOT EXISTS idx_file_event_hints_kind ON file_event_classification_hints(run_id, file_kind_hint)",
    )


def init_file_event_queue_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    init_business_ops_ledger(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def file_event_table_names(db_path: str | Path | None = None) -> list[str]:
    path = init_file_event_queue_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        return [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'file_event_%' ORDER BY name"
            )
        ]
    finally:
        conn.close()


def _resolve_existing_root(root: str | Path) -> Path:
    if str(root).strip() == "":
        raise ValueError("snapshot root cannot be empty")
    candidate = Path(root).expanduser()
    if not candidate.is_absolute():
        raise ValueError("snapshot root must be an absolute path")
    if not candidate.exists():
        raise ValueError(f"snapshot root does not exist: {candidate}")
    return candidate.resolve()


def validate_snapshot_root(
    root: str | Path,
    *,
    allowed_roots: Iterable[str | Path] | None = None,
) -> Path:
    resolved = _resolve_existing_root(root)
    resolved_text = resolved.as_posix()
    if resolved_text in BROAD_ROOTS:
        raise ValueError(f"refusing broad snapshot root: {resolved_text}")
    if resolved_text == "/mnt/c" or resolved_text.startswith("/mnt/c/"):
        raise ValueError("refusing C-drive snapshot root")

    allowed = tuple(DEFAULT_ALLOWED_ROOTS if allowed_roots is None else allowed_roots)
    allowed_resolved = {Path(item).expanduser().resolve().as_posix() for item in allowed}
    if resolved_text not in allowed_resolved:
        raise ValueError(
            f"snapshot root {resolved_text} is not allowlisted; allowed roots: {sorted(allowed_resolved)}"
        )
    return resolved


def default_root_id_for(root: str | Path) -> str:
    resolved = Path(root).expanduser().resolve().as_posix()
    if resolved in DEFAULT_ROOT_IDS:
        return DEFAULT_ROOT_IDS[resolved]
    return "file_event_root_" + hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:12]


def _is_relative_prefix(relative_path: str, prefix: str) -> bool:
    return relative_path == prefix or relative_path.startswith(prefix + "/")


def _parts_lower(relative_path: str) -> set[str]:
    return {part.lower() for part in Path(relative_path).parts}


def _has_no_go_hint(relative_path: str) -> bool:
    parts = _parts_lower(relative_path)
    name = Path(relative_path).name.lower()
    if parts & NO_GO_PARTS:
        return True
    return any(hint in name for hint in NO_GO_FILE_HINTS)


def _sensitivity_hint(relative_path: str) -> tuple[bool, str]:
    parts = _parts_lower(relative_path)
    name = Path(relative_path).name.lower()
    if "finance" in parts:
        return True, "finance_boundary"
    if parts & {"legal", "tax", "cpa"}:
        return True, "legal_tax_boundary"
    if parts & {".ssh", ".gnupg", ".google-secrets", "secrets", "vaults"}:
        return True, "credential_boundary"
    if parts & {".private", "private"} or "private" in name:
        return True, "private_boundary"
    if parts & {"logs", "runtime_logs"} or name.endswith(".log"):
        return True, "runtime_log_boundary"
    if _has_no_go_hint(relative_path):
        return True, "no_go"
    if len(parts) > 1 and any(part.startswith(".") for part in parts):
        return False, "metadata_only"
    if parts & METADATA_ONLY_PARTS or Path(relative_path).suffix.lower() in METADATA_ONLY_SUFFIXES:
        return False, "metadata_only"
    return False, "normal_internal"


def _file_kind_hint(relative_path: str, path_type: str) -> str:
    lowered = relative_path.lower()
    suffix = Path(lowered).suffix
    parts = _parts_lower(relative_path)
    if "generated" in parts and "read_models" in parts:
        return "generated_read_model"
    if "node_uplink" in parts or "report_bridge" in parts:
        return "report_bridge_package"
    if suffix == ".logicx":
        return "logic_project"
    if suffix in AUDIO_SUFFIXES:
        return "audio_file"
    if suffix in VIDEO_SUFFIXES:
        return "video_file"
    if suffix in IMAGE_SUFFIXES:
        return "image_file"
    if suffix == ".md":
        return "markdown_doc"
    if suffix in SOURCE_SUFFIXES:
        return "source_code"
    if path_type == "directory":
        return "unknown"
    return "unknown"


def _world_hint(relative_path: str, sensitivity_hint: str, file_kind_hint: str) -> str:
    parts = _parts_lower(relative_path)
    lowered = relative_path.lower()
    if sensitivity_hint in {
        "credential_boundary",
        "legal_tax_boundary",
        "private_boundary",
        "runtime_log_boundary",
        "no_go",
    }:
        return "security"
    if sensitivity_hint == "finance_boundary":
        return "finance"
    if file_kind_hint in {"logic_project", "audio_file", "video_file"}:
        return "music_art"
    if "node_uplink" in parts or "operator_actions" in parts:
        return "operations"
    if "generated/read_models" in lowered or "docs/operations" in lowered:
        return "operations"
    if parts & {"scripts", "tests"}:
        return "build"
    return "unknown"


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


def _timestamp_from_ns(value: int | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1_000_000_000, timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_decision(metadata: FileMetadata) -> tuple[bool, str]:
    if metadata.path_type != "file":
        return False, "not_a_file"
    if metadata.no_go_boundary:
        return False, "no_go_or_sensitive_boundary"
    if metadata.sensitivity_hint in {"metadata_only", "runtime_log_boundary"}:
        return False, "metadata_only_boundary"
    if metadata.size_bytes is None:
        return False, "size_unknown"
    if metadata.size_bytes > MAX_HASH_BYTES:
        return False, "over_max_hash_bytes"
    if metadata.file_kind_hint not in SAFE_HASH_FILE_KINDS:
        return False, "file_kind_metadata_only"
    if Path(metadata.relative_path).suffix.lower() in METADATA_ONLY_SUFFIXES:
        return False, "metadata_only_suffix"
    return True, "safe_small_metadata_snapshot"


def _should_skip_descend(relative_path: str, metadata: FileMetadata) -> bool:
    if metadata.path_type != "directory":
        return True
    if metadata.no_go_boundary:
        return True
    if metadata.file_kind_hint == "logic_project":
        return True
    if metadata.sensitivity_hint in {"metadata_only", "runtime_log_boundary"}:
        return True
    if any(_is_relative_prefix(relative_path, prefix) for prefix in SKIP_DESCEND_RELATIVE_PREFIXES):
        return True
    return False


def _metadata_for_path(
    *,
    root: Path,
    root_id: str,
    path: Path,
    hash_reader: Any | None,
) -> FileMetadata:
    relative_path = path.relative_to(root).as_posix()
    path_type = _path_type(path)
    try:
        stat = path.lstat()
        size_bytes = stat.st_size
        mtime = _timestamp_from_ns(stat.st_mtime_ns)
        ctime = _timestamp_from_ns(stat.st_ctime_ns)
    except OSError:
        size_bytes = None
        mtime = None
        ctime = None

    no_go_boundary, sensitivity = _sensitivity_hint(relative_path)
    file_kind = _file_kind_hint(relative_path, path_type)
    world = _world_hint(relative_path, sensitivity, file_kind)
    pre_hash_metadata = FileMetadata(
        root_id=root_id,
        absolute_root=root.as_posix(),
        relative_path=relative_path,
        absolute_path=path.as_posix(),
        path_type=path_type,
        size_bytes=size_bytes,
        mtime=mtime,
        ctime=ctime,
        safe_hash=None,
        hash_algorithm=None,
        no_go_boundary=no_go_boundary,
        sensitivity_hint=sensitivity,
        world_hint=world,
        file_kind_hint=file_kind,
        hash_status="not_attempted",
        hash_reason="not_evaluated",
    )
    should_hash, hash_reason = _hash_decision(pre_hash_metadata)
    if not should_hash:
        return FileMetadata(
            **{
                **pre_hash_metadata.__dict__,
                "hash_status": "not_hashed",
                "hash_reason": hash_reason,
            }
        )

    try:
        digest = hash_reader(path) if hash_reader else _sha256_file(path)
    except OSError:
        return FileMetadata(
            **{
                **pre_hash_metadata.__dict__,
                "hash_status": "hash_failed",
                "hash_reason": "read_error_during_safe_hash",
            }
        )

    return FileMetadata(
        **{
            **pre_hash_metadata.__dict__,
            "safe_hash": digest,
            "hash_algorithm": "sha256",
            "hash_status": "hashed",
            "hash_reason": hash_reason,
        }
    )


def iter_snapshot_metadata(
    *,
    root: str | Path,
    root_id: str | None = None,
    allowed_roots: Iterable[str | Path] | None = None,
    hash_reader: Any | None = None,
) -> list[FileMetadata]:
    resolved = validate_snapshot_root(root, allowed_roots=allowed_roots)
    resolved_root_id = root_id or default_root_id_for(resolved)
    records: list[FileMetadata] = []
    stack = [resolved]

    while stack:
        directory = stack.pop()
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError:
            continue

        for child in children:
            metadata = _metadata_for_path(
                root=resolved,
                root_id=resolved_root_id,
                path=child,
                hash_reader=hash_reader,
            )
            records.append(metadata)
            if not _should_skip_descend(metadata.relative_path, metadata):
                stack.append(child)

    return records


def _latest_run_for_root(conn: sqlite3.Connection, root_id: str, exclude_run_id: str) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM file_event_runs
WHERE root_id = ? AND run_id != ? AND completed_at IS NOT NULL
ORDER BY completed_at DESC, run_id DESC
LIMIT 1
""",
        (root_id, exclude_run_id),
    ).fetchone()
    return row[0] if row else None


def _previous_snapshot(conn: sqlite3.Connection, run_id: str | None) -> dict[str, sqlite3.Row]:
    if not run_id:
        return {}
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM file_event_snapshots WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    return {row["relative_path"]: row for row in rows}


def _metadata_changed(previous: sqlite3.Row, current: FileMetadata) -> bool:
    if previous["path_type"] != current.path_type:
        return True
    if previous["safe_hash"] and current.safe_hash:
        return previous["safe_hash"] != current.safe_hash
    return (
        previous["size_bytes"] != current.size_bytes
        or previous["mtime"] != current.mtime
        or previous["ctime"] != current.ctime
    )


def _queue_status_for(metadata: FileMetadata, event_type: str) -> str:
    if metadata.no_go_boundary:
        return "blocked_no_go"
    if event_type == "unchanged":
        return "ignored"
    if metadata.safe_hash:
        return "queued"
    if metadata.sensitivity_hint == "metadata_only" or metadata.file_kind_hint in {
        "audio_file",
        "image_file",
        "logic_project",
        "video_file",
    }:
        return "classified_metadata"
    return "needs_operator_review"


def _missing_metadata_from_previous(row: sqlite3.Row) -> FileMetadata:
    return FileMetadata(
        root_id=row["root_id"],
        absolute_root=str(Path(row["absolute_path"]).parent),
        relative_path=row["relative_path"],
        absolute_path=row["absolute_path"],
        path_type=row["path_type"],
        size_bytes=row["size_bytes"],
        mtime=row["mtime"],
        ctime=row["ctime"],
        safe_hash=row["safe_hash"],
        hash_algorithm=row["hash_algorithm"],
        no_go_boundary=bool(row["no_go_boundary"]),
        sensitivity_hint=row["sensitivity_hint"],
        world_hint=row["world_hint"],
        file_kind_hint=row["file_kind_hint"],
        hash_status=row["hash_status"],
        hash_reason=row["hash_reason"],
    )


def _delete_existing_run(conn: sqlite3.Connection, run_id: str) -> None:
    for table in (
        "file_event_classification_hints",
        "file_event_path_aliases",
        "file_event_queue",
        "file_event_observations",
        "file_event_snapshots",
        "file_event_runs",
    ):
        conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))


def _insert_snapshot(conn: sqlite3.Connection, metadata: FileMetadata, run_id: str, now: str) -> None:
    conn.execute(
        """
INSERT INTO file_event_snapshots (
  snapshot_id, run_id, root_id, relative_path, absolute_path, path_type,
  size_bytes, mtime, ctime, safe_hash, hash_algorithm, hash_status, hash_reason,
  no_go_boundary, sensitivity_hint, world_hint, file_kind_hint,
  raw_content_read, raw_body_stored, observed_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
ON CONFLICT(run_id, root_id, relative_path) DO UPDATE SET
  absolute_path = excluded.absolute_path,
  path_type = excluded.path_type,
  size_bytes = excluded.size_bytes,
  mtime = excluded.mtime,
  ctime = excluded.ctime,
  safe_hash = excluded.safe_hash,
  hash_algorithm = excluded.hash_algorithm,
  hash_status = excluded.hash_status,
  hash_reason = excluded.hash_reason,
  no_go_boundary = excluded.no_go_boundary,
  sensitivity_hint = excluded.sensitivity_hint,
  world_hint = excluded.world_hint,
  file_kind_hint = excluded.file_kind_hint,
  observed_at = excluded.observed_at
""",
        (
            _row_id("fesnap", run_id, metadata.root_id, metadata.relative_path),
            run_id,
            metadata.root_id,
            metadata.relative_path,
            metadata.absolute_path,
            metadata.path_type,
            metadata.size_bytes,
            metadata.mtime,
            metadata.ctime,
            metadata.safe_hash,
            metadata.hash_algorithm,
            metadata.hash_status,
            metadata.hash_reason,
            int(metadata.no_go_boundary),
            metadata.sensitivity_hint,
            metadata.world_hint,
            metadata.file_kind_hint,
            now,
        ),
    )


def _insert_event(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    metadata: FileMetadata,
    event_type: str,
    now: str,
    previous_path: str | None = None,
    current_path: str | None = None,
) -> str:
    queue_status = _queue_status_for(metadata, event_type)
    event_id = _row_id(
        "fevent",
        run_id,
        metadata.root_id,
        event_type,
        metadata.relative_path,
        previous_path or "",
        current_path or "",
    )
    conn.execute(
        """
INSERT INTO file_event_observations (
  event_id, run_id, root_id, relative_path, absolute_path, event_type, path_type,
  size_bytes, mtime, ctime, safe_hash, hash_algorithm, previous_path, current_path,
  raw_content_read, raw_body_stored, no_go_boundary, sensitivity_hint, world_hint,
  file_kind_hint, queue_status, created_at, observed_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(event_id) DO UPDATE SET
  event_type = excluded.event_type,
  queue_status = excluded.queue_status,
  observed_at = excluded.observed_at
""",
        (
            event_id,
            run_id,
            metadata.root_id,
            metadata.relative_path,
            metadata.absolute_path,
            event_type,
            metadata.path_type,
            metadata.size_bytes,
            metadata.mtime,
            metadata.ctime,
            metadata.safe_hash,
            metadata.hash_algorithm,
            previous_path,
            current_path,
            int(metadata.no_go_boundary),
            metadata.sensitivity_hint,
            metadata.world_hint,
            metadata.file_kind_hint,
            queue_status,
            now,
            now,
        ),
    )

    hint_id = _row_id("fehint", event_id)
    conn.execute(
        """
INSERT INTO file_event_classification_hints (
  hint_id, event_id, run_id, root_id, relative_path, sensitivity_hint,
  world_hint, file_kind_hint, basis, confidence, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(hint_id) DO UPDATE SET
  sensitivity_hint = excluded.sensitivity_hint,
  world_hint = excluded.world_hint,
  file_kind_hint = excluded.file_kind_hint
""",
        (
            hint_id,
            event_id,
            run_id,
            metadata.root_id,
            metadata.relative_path,
            metadata.sensitivity_hint,
            metadata.world_hint,
            metadata.file_kind_hint,
            "path_extension_and_boundary_hints",
            0.7 if metadata.file_kind_hint != "unknown" else 0.45,
            now,
        ),
    )

    if queue_status != "ignored":
        queue_id = _row_id("fequeue", event_id)
        conn.execute(
            """
INSERT INTO file_event_queue (
  queue_id, event_id, run_id, root_id, relative_path, event_type,
  queue_status, classification_hint_id, queued_at, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(queue_id) DO UPDATE SET
  queue_status = excluded.queue_status,
  classification_hint_id = excluded.classification_hint_id,
  notes = excluded.notes
""",
            (
                queue_id,
                event_id,
                run_id,
                metadata.root_id,
                metadata.relative_path,
                event_type,
                queue_status,
                hint_id,
                now,
                "Metadata event queued for later atlas/classification review; no action executed.",
            ),
        )
    return event_id


def _insert_possible_move(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    missing: FileMetadata,
    current: FileMetadata,
    now: str,
) -> str:
    move_metadata = FileMetadata(
        **{
            **current.__dict__,
            "relative_path": current.relative_path,
            "absolute_path": current.absolute_path,
            "safe_hash": current.safe_hash or missing.safe_hash,
            "hash_algorithm": current.hash_algorithm or missing.hash_algorithm,
        }
    )
    event_id = _insert_event(
        conn,
        run_id=run_id,
        metadata=move_metadata,
        event_type="possible_move",
        now=now,
        previous_path=missing.relative_path,
        current_path=current.relative_path,
    )
    conn.execute(
        """
INSERT INTO file_event_path_aliases (
  alias_id, run_id, root_id, previous_path, current_path, safe_hash, size_bytes,
  confidence, basis, advisory_only, file_moved, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?)
ON CONFLICT(run_id, root_id, previous_path, current_path) DO UPDATE SET
  safe_hash = excluded.safe_hash,
  size_bytes = excluded.size_bytes,
  confidence = excluded.confidence,
  basis = excluded.basis
""",
        (
            _row_id("fealias", run_id, missing.root_id, missing.relative_path, current.relative_path),
            run_id,
            missing.root_id,
            missing.relative_path,
            current.relative_path,
            current.safe_hash or missing.safe_hash,
            current.size_bytes,
            0.85,
            "same_safe_hash_and_size_in_same_snapshot_run",
            now,
        ),
    )
    return event_id


def build_file_event_snapshot(
    *,
    root: str | Path,
    db_path: str | Path | None = None,
    root_id: str | None = None,
    run_id: str | None = None,
    allowed_roots: Iterable[str | Path] | None = None,
    hash_reader: Any | None = None,
) -> FileEventSnapshotResult:
    path = init_file_event_queue_schema(db_path)
    resolved = validate_snapshot_root(root, allowed_roots=allowed_roots)
    resolved_root_id = root_id or default_root_id_for(resolved)
    now = utc_now()
    effective_run_id = run_id or _row_id("ferun", resolved_root_id, resolved.as_posix(), now)

    records = iter_snapshot_metadata(
        root=resolved,
        root_id=resolved_root_id,
        allowed_roots=allowed_roots,
        hash_reader=hash_reader,
    )
    current_by_path = {record.relative_path: record for record in records}

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        previous_run_id = _latest_run_for_root(conn, resolved_root_id, effective_run_id)
        previous_by_path = _previous_snapshot(conn, previous_run_id)
        _delete_existing_run(conn, effective_run_id)
        conn.execute(
            """
INSERT INTO file_event_runs (
  run_id, queue_version, root_id, absolute_root, started_at, previous_run_id,
  max_hash_bytes, raw_content_read, raw_body_stored, runtime_authority,
  agent_activation_allowed, tool_execution_allowed, network_authority,
  file_move_allowed, file_delete_allowed, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, ?)
""",
            (
                effective_run_id,
                FILE_EVENT_QUEUE_VERSION,
                resolved_root_id,
                resolved.as_posix(),
                now,
                previous_run_id,
                MAX_HASH_BYTES,
                "Snapshot-only metadata queue; no daemon, action execution, raw body storage, moves, or deletes.",
            ),
        )

        event_counts: Counter[str] = Counter()
        queue_counts: Counter[str] = Counter()
        missing_records: list[FileMetadata] = []
        new_records: list[FileMetadata] = []

        for record in records:
            _insert_snapshot(conn, record, effective_run_id, now)
            previous = previous_by_path.get(record.relative_path)
            if previous is None:
                event_type = "observed_new"
                new_records.append(record)
            elif _metadata_changed(previous, record):
                event_type = "observed_modified"
            else:
                event_type = "unchanged"
            _insert_event(conn, run_id=effective_run_id, metadata=record, event_type=event_type, now=now)
            event_counts[event_type] += 1
            queue_counts[_queue_status_for(record, event_type)] += 1

        for relative_path, previous in previous_by_path.items():
            if relative_path in current_by_path:
                continue
            missing = _missing_metadata_from_previous(previous)
            missing_records.append(missing)
            _insert_event(
                conn,
                run_id=effective_run_id,
                metadata=missing,
                event_type="observed_missing",
                now=now,
                previous_path=missing.relative_path,
            )
            event_counts["observed_missing"] += 1
            queue_counts[_queue_status_for(missing, "observed_missing")] += 1

        possible_moves = 0
        missing_by_key: dict[tuple[str, int | None], list[FileMetadata]] = {}
        for missing in missing_records:
            if missing.safe_hash:
                missing_by_key.setdefault((missing.safe_hash, missing.size_bytes), []).append(missing)
        used_missing: set[str] = set()
        for new_record in new_records:
            if not new_record.safe_hash:
                continue
            candidates = missing_by_key.get((new_record.safe_hash, new_record.size_bytes), [])
            for missing in candidates:
                if missing.relative_path in used_missing:
                    continue
                _insert_possible_move(
                    conn,
                    run_id=effective_run_id,
                    missing=missing,
                    current=new_record,
                    now=now,
                )
                used_missing.add(missing.relative_path)
                possible_moves += 1
                event_counts["possible_move"] += 1
                queue_counts[_queue_status_for(new_record, "possible_move")] += 1
                break

        file_kind_counts = Counter(record.file_kind_hint for record in records)
        no_go_count = sum(1 for record in records if record.no_go_boundary)
        hashed_count = sum(1 for record in records if record.safe_hash)
        event_total = sum(event_counts.values())
        queued_total = sum(count for status, count in queue_counts.items() if status != "ignored")

        conn.execute(
            """
UPDATE file_event_runs
SET completed_at = ?,
    observed_path_count = ?,
    event_count = ?,
    queued_count = ?,
    no_go_count = ?,
    hashed_count = ?,
    possible_move_count = ?
WHERE run_id = ?
""",
            (
                utc_now(),
                len(records),
                event_total,
                queued_total,
                no_go_count,
                hashed_count,
                possible_moves,
                effective_run_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return FileEventSnapshotResult(
        run_id=effective_run_id,
        db_path=path,
        root_id=resolved_root_id,
        absolute_root=resolved.as_posix(),
        observed_path_count=len(records),
        event_counts=dict(sorted(event_counts.items())),
        queue_counts=dict(sorted(queue_counts.items())),
        file_kind_counts=dict(sorted(file_kind_counts.items())),
        no_go_count=no_go_count,
        hashed_count=hashed_count,
        possible_move_count=possible_moves,
    )


REPORT_SECTIONS = {
    "summary",
    "recent",
    "queued",
    "possible-moves",
    "no-go",
    "by-kind",
}


def _latest_run_id(conn: sqlite3.Connection, root_id: str | None = None) -> str | None:
    if root_id:
        row = conn.execute(
            """
SELECT run_id
FROM file_event_runs
WHERE root_id = ? AND completed_at IS NOT NULL
ORDER BY completed_at DESC, started_at DESC
LIMIT 1
""",
            (root_id,),
        ).fetchone()
    else:
        row = conn.execute(
            """
SELECT run_id
FROM file_event_runs
WHERE completed_at IS NOT NULL
ORDER BY completed_at DESC, started_at DESC
LIMIT 1
"""
        ).fetchone()
    return row["run_id"] if row else None


def _group_counts(conn: sqlite3.Connection, run_id: str, column: str) -> dict[str, int]:
    return {
        row[0]: row[1]
        for row in conn.execute(
            f"SELECT {column}, COUNT(*) FROM file_event_observations WHERE run_id = ? GROUP BY {column} ORDER BY {column}",
            (run_id,),
        )
    }


def _sample_events(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    where: str = "1=1",
    params: tuple[Any, ...] = (),
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
SELECT event_type, relative_path, previous_path, current_path, path_type,
       size_bytes, safe_hash, no_go_boundary, sensitivity_hint, world_hint,
       file_kind_hint, queue_status, observed_at
FROM file_event_observations
WHERE run_id = ? AND {where}
ORDER BY observed_at DESC, relative_path ASC
LIMIT ?
""",
        (run_id, *params, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def build_file_event_report(
    *,
    db_path: str | Path | None = None,
    run_id: str | None = None,
    section: str = "summary",
    kind: str | None = None,
    root_id: str | None = None,
) -> dict[str, Any]:
    if section not in REPORT_SECTIONS:
        raise ValueError(f"unknown file event report section: {section}")
    path = init_file_event_queue_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        selected_run_id = run_id or _latest_run_id(conn, root_id=root_id)
        if not selected_run_id:
            return {
                "report": section,
                "run_id": None,
                "message": "No file event snapshot runs found.",
                "no_authority_flags": NO_AUTHORITY_FLAGS,
            }
        run = dict(
            conn.execute(
                "SELECT * FROM file_event_runs WHERE run_id = ?",
                (selected_run_id,),
            ).fetchone()
        )
        payload: dict[str, Any] = {
            "report": section,
            "run": run,
            "event_counts": _group_counts(conn, selected_run_id, "event_type"),
            "queue_counts": _group_counts(conn, selected_run_id, "queue_status"),
            "file_kind_counts": _group_counts(conn, selected_run_id, "file_kind_hint"),
            "world_counts": _group_counts(conn, selected_run_id, "world_hint"),
            "sensitivity_counts": _group_counts(conn, selected_run_id, "sensitivity_hint"),
            "no_authority_flags": NO_AUTHORITY_FLAGS,
            "boundary": {
                "raw_content_read": False,
                "raw_body_stored": False,
                "daemon_started": False,
                "actions_executed": False,
                "files_moved": False,
                "files_deleted": False,
            },
        }
        if section == "summary":
            payload["recent_events"] = _sample_events(
                conn,
                selected_run_id,
                where="event_type != 'unchanged'",
                limit=12,
            )
        elif section == "recent":
            payload["items"] = _sample_events(
                conn,
                selected_run_id,
                where="event_type != 'unchanged'",
                limit=30,
            )
        elif section == "queued":
            payload["items"] = _sample_events(
                conn,
                selected_run_id,
                where="queue_status != 'ignored'",
                limit=30,
            )
        elif section == "possible-moves":
            payload["items"] = _sample_events(
                conn,
                selected_run_id,
                where="event_type = 'possible_move'",
                limit=30,
            )
        elif section == "no-go":
            payload["items"] = _sample_events(
                conn,
                selected_run_id,
                where="no_go_boundary = 1 OR queue_status = 'blocked_no_go'",
                limit=30,
            )
        elif section == "by-kind":
            if not kind:
                raise ValueError("--kind is required for by-kind report")
            payload["kind"] = kind
            payload["items"] = _sample_events(
                conn,
                selected_run_id,
                where="file_kind_hint = ?",
                params=(kind,),
                limit=30,
            )
        return payload
    finally:
        conn.close()


def _counts_line(label: str, counts: dict[str, int]) -> str:
    if not counts:
        return f"- {label}: none"
    return f"- {label}: " + ", ".join(f"{key}={value}" for key, value in counts.items())


def _format_event_item(item: dict[str, Any]) -> str:
    move = ""
    if item.get("previous_path") or item.get("current_path"):
        move = f" previous={item.get('previous_path') or '-'} current={item.get('current_path') or '-'}"
    return (
        f"- {item['event_type']}: {item['relative_path']} "
        f"({item['file_kind_hint']}, {item['world_hint']}, {item['sensitivity_hint']}, "
        f"{item['queue_status']}){move}"
    )


def format_file_event_report(payload: dict[str, Any]) -> str:
    if payload.get("run_id") is None and "run" not in payload:
        return "\n".join(
            [
                "File Event Queue v0",
                "",
                payload.get("message", "No file event snapshot runs found."),
            ]
        )
    run = payload["run"]
    lines = [
        f"File Event Queue v0 - {payload['report']}",
        "",
        f"Run: `{run['run_id']}`",
        f"Root: `{run['root_id']}` at `{run['absolute_root']}`",
        f"Observed paths: {run['observed_path_count']}",
        f"Queued events: {run['queued_count']}",
        f"No-go boundaries: {run['no_go_count']}",
        f"Safe hashes: {run['hashed_count']}",
        f"Possible moves: {run['possible_move_count']}",
        _counts_line("Event types", payload["event_counts"]),
        _counts_line("Queue statuses", payload["queue_counts"]),
        _counts_line("File kinds", payload["file_kind_counts"]),
        _counts_line("World hints", payload["world_counts"]),
        _counts_line("Sensitivity hints", payload["sensitivity_counts"]),
    ]
    items = payload.get("recent_events") or payload.get("items") or []
    if items:
        lines.extend(["", "Items:"])
        lines.extend(_format_event_item(item) for item in items)
    lines.extend(
        [
            "",
            "Boundary:",
            "- Snapshot/poll metadata only; no daemon is started.",
            "- Raw file bodies are not stored and no file events execute actions.",
            "- Reorg/move/delete behavior is not authorized.",
            "- Runtime, agent, tool, Docker/Ollama, and network authority remain false.",
        ]
    )
    return "\n".join(lines)
