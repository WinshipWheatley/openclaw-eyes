"""Recent File Context Resolver v0 for OpenClaw.

This module resolves vague file references such as "that new file" against
File Event Queue metadata. It records candidate metadata and resolution
receipts only. It does not open raw file bodies, move files, delete files,
execute actions, activate agents, or promote any file observation into truth.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger
from file_event_queue import init_file_event_queue_schema


ROOT = Path(__file__).resolve().parent
RECENT_FILE_CONTEXT_VERSION = "recent_file_context_v0"
READ_MODEL_VERSION = "recent_file_context_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "recent_file_context.json"
OPERATOR_EXPORT_NAME = "recent_file_context_OPERATOR.md"

CANDIDATE_EVENT_TYPES = {"observed_new", "observed_modified", "possible_move"}
RESOLUTION_STATUSES = {
    "resolved",
    "ambiguous",
    "unresolved",
    "blocked_no_go",
    "needs_operator_review",
}
QUERY_TYPES = {
    "generic_recent_file",
    "logic_project",
    "markdown_doc",
    "generated_read_model",
    "report_bridge_package",
    "unknown",
}

CAN_READ_KINDS = {"generated_read_model", "markdown_doc", "source_code"}
METADATA_ONLY_KINDS = {
    "audio_file",
    "image_file",
    "logic_project",
    "report_bridge_package",
    "video_file",
    "unknown",
}

NO_AUTHORITY_FLAGS = {
    "raw_content_read": False,
    "raw_body_stored": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "runtime_authority": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "network_authority": False,
    "action_created": False,
    "approval_bypass_allowed": False,
}


@dataclass(frozen=True)
class RecentFileBuildResult:
    run_id: str
    db_path: str
    source_event_count: int
    candidate_count: int
    counts_by_kind: dict[str, int]
    counts_by_status: dict[str, int]


@dataclass(frozen=True)
class RecentFileResolutionResult:
    query_id: str
    query_text: str
    query_type: str
    resolution_status: str
    candidate_id: str | None
    confidence: float
    reason: str
    next_safe_move: str
    candidate_count: int


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


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


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS recent_file_context_runs (
  run_id TEXT PRIMARY KEY,
  resolver_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  source_event_count INTEGER NOT NULL DEFAULT 0,
  candidate_count INTEGER NOT NULL DEFAULT 0,
  raw_content_read INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  notes TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS recent_file_candidates (
  candidate_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  source_event_id TEXT NOT NULL,
  source_run_id TEXT NOT NULL,
  root_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  absolute_path TEXT,
  observed_at TEXT NOT NULL,
  event_type TEXT NOT NULL,
  file_kind_hint TEXT NOT NULL,
  world_hint TEXT NOT NULL,
  sensitivity_hint TEXT NOT NULL,
  queue_status TEXT NOT NULL,
  safe_hash_available INTEGER NOT NULL DEFAULT 0,
  raw_content_read INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  can_agent_read INTEGER NOT NULL DEFAULT 0,
  metadata_only INTEGER NOT NULL DEFAULT 1,
  no_go_boundary INTEGER NOT NULL DEFAULT 0,
  confidence REAL NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES recent_file_context_runs(run_id) ON DELETE CASCADE,
  UNIQUE(run_id, source_event_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS recent_file_aliases (
  alias_id TEXT PRIMARY KEY,
  alias_text TEXT NOT NULL,
  query_type TEXT NOT NULL,
  file_kind_hint TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(alias_text, query_type)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS recent_file_resolution_queries (
  query_id TEXT PRIMARY KEY,
  run_id TEXT,
  query_text TEXT NOT NULL,
  query_type TEXT NOT NULL,
  resolution_status TEXT NOT NULL,
  candidate_id TEXT,
  candidate_count INTEGER NOT NULL DEFAULT 0,
  confidence REAL NOT NULL,
  reason TEXT NOT NULL,
  next_safe_move TEXT NOT NULL,
  raw_content_read INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (candidate_id) REFERENCES recent_file_candidates(candidate_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS recent_file_context_links (
  link_id TEXT PRIMARY KEY,
  candidate_id TEXT,
  query_id TEXT,
  link_kind TEXT NOT NULL,
  source_table TEXT NOT NULL,
  source_id TEXT,
  source_path TEXT,
  summary TEXT NOT NULL,
  raw_content_read INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS recent_file_rejections (
  rejection_id TEXT PRIMARY KEY,
  query_id TEXT,
  candidate_id TEXT,
  rejection_reason TEXT NOT NULL,
  created_at TEXT NOT NULL
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_recent_candidates_run ON recent_file_candidates(run_id, observed_at)",
        "CREATE INDEX IF NOT EXISTS idx_recent_candidates_kind ON recent_file_candidates(file_kind_hint)",
        "CREATE INDEX IF NOT EXISTS idx_recent_queries_status ON recent_file_resolution_queries(resolution_status)",
    )


def init_recent_file_context_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    parent = Path(path).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    init_file_event_queue_schema(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def recent_file_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_recent_file_context_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'recent_file_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _seed_aliases(conn: sqlite3.Connection, now: str) -> None:
    aliases = (
        ("that new file", "generic_recent_file", None),
        ("the file i just made", "generic_recent_file", None),
        ("the new logic file", "logic_project", "logic_project"),
        ("that markdown doc from earlier", "markdown_doc", "markdown_doc"),
        ("the recent report package", "report_bridge_package", "report_bridge_package"),
    )
    for alias_text, query_type, file_kind in aliases:
        conn.execute(
            """
INSERT INTO recent_file_aliases (
  alias_id, alias_text, query_type, file_kind_hint, created_at
) VALUES (?, ?, ?, ?, ?)
ON CONFLICT(alias_text, query_type) DO UPDATE SET
  file_kind_hint = excluded.file_kind_hint
""".strip(),
            (_row_id("rfalias", alias_text, query_type), alias_text, query_type, file_kind, now),
        )


def _latest_file_event_rows(conn: sqlite3.Connection, limit: int = 100) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            f"""
SELECT event_id, run_id AS source_run_id, root_id, relative_path, absolute_path,
       event_type, path_type, size_bytes, mtime, ctime, safe_hash, hash_algorithm,
       no_go_boundary, sensitivity_hint, world_hint, file_kind_hint,
       queue_status, created_at, observed_at
FROM file_event_observations
WHERE event_type IN ({','.join('?' for _ in sorted(CANDIDATE_EVENT_TYPES))})
ORDER BY observed_at DESC, created_at DESC, relative_path ASC
LIMIT ?
""".strip(),
            (*sorted(CANDIDATE_EVENT_TYPES), limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return []


def _can_agent_read(row: sqlite3.Row) -> bool:
    if row["no_go_boundary"] or row["queue_status"] == "blocked_no_go":
        return False
    if row["sensitivity_hint"] not in {"normal_internal", "metadata_only"}:
        return False
    return row["file_kind_hint"] in CAN_READ_KINDS


def _candidate_confidence(row: sqlite3.Row) -> tuple[float, str]:
    if row["no_go_boundary"] or row["queue_status"] == "blocked_no_go":
        return 0.2, "blocked no-go/sensitive boundary; metadata only"
    if row["file_kind_hint"] == "logic_project":
        return 0.82, "recent Logic project metadata candidate"
    if row["event_type"] == "observed_new":
        return 0.85, "recent observed_new event"
    if row["event_type"] == "observed_modified":
        return 0.72, "recent observed_modified event"
    if row["event_type"] == "possible_move":
        return 0.68, "possible move candidate, advisory only"
    return 0.5, "recent file metadata candidate"


def _insert_candidate(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    row: sqlite3.Row,
    now: str,
) -> str:
    can_read = _can_agent_read(row)
    confidence, reason = _candidate_confidence(row)
    metadata_only = (not can_read) or row["file_kind_hint"] in METADATA_ONLY_KINDS
    candidate_id = _row_id("rfcand", run_id, row["event_id"])
    conn.execute(
        """
INSERT INTO recent_file_candidates (
  candidate_id, run_id, source_event_id, source_run_id, root_id,
  relative_path, absolute_path, observed_at, event_type, file_kind_hint,
  world_hint, sensitivity_hint, queue_status, safe_hash_available,
  raw_content_read, raw_body_stored, can_agent_read, metadata_only,
  no_go_boundary, confidence, reason, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?)
ON CONFLICT(run_id, source_event_id) DO UPDATE SET
  relative_path = excluded.relative_path,
  absolute_path = excluded.absolute_path,
  observed_at = excluded.observed_at,
  event_type = excluded.event_type,
  file_kind_hint = excluded.file_kind_hint,
  world_hint = excluded.world_hint,
  sensitivity_hint = excluded.sensitivity_hint,
  queue_status = excluded.queue_status,
  safe_hash_available = excluded.safe_hash_available,
  raw_content_read = 0,
  raw_body_stored = 0,
  can_agent_read = excluded.can_agent_read,
  metadata_only = excluded.metadata_only,
  no_go_boundary = excluded.no_go_boundary,
  confidence = excluded.confidence,
  reason = excluded.reason
""".strip(),
        (
            candidate_id,
            run_id,
            row["event_id"],
            row["source_run_id"],
            row["root_id"],
            row["relative_path"],
            row["absolute_path"],
            row["observed_at"],
            row["event_type"],
            row["file_kind_hint"],
            row["world_hint"],
            row["sensitivity_hint"],
            row["queue_status"],
            1 if row["safe_hash"] else 0,
            1 if can_read else 0,
            1 if metadata_only else 0,
            1 if row["no_go_boundary"] else 0,
            confidence,
            reason,
            now,
        ),
    )
    conn.execute(
        """
INSERT INTO recent_file_context_links (
  link_id, candidate_id, query_id, link_kind, source_table, source_id,
  source_path, summary, raw_content_read, raw_body_stored, created_at
) VALUES (?, ?, NULL, 'file_event_observation', 'file_event_observations', ?, ?, ?, 0, 0, ?)
ON CONFLICT(link_id) DO UPDATE SET
  summary = excluded.summary,
  raw_content_read = 0,
  raw_body_stored = 0
""".strip(),
        (
            _row_id("rflink", candidate_id, "file_event_observation"),
            candidate_id,
            row["event_id"],
            row["relative_path"],
            f"{row['event_type']} {row['relative_path']} kind={row['file_kind_hint']} world={row['world_hint']}",
            now,
        ),
    )
    _link_markdown_document_if_available(conn, candidate_id=candidate_id, row=row, now=now)
    return candidate_id


def _link_markdown_document_if_available(
    conn: sqlite3.Connection,
    *,
    candidate_id: str,
    row: sqlite3.Row,
    now: str,
) -> None:
    if row["file_kind_hint"] != "markdown_doc":
        return
    try:
        markdown = conn.execute(
            """
SELECT markdown_document_id, relative_path, retrieval_policy, sensitivity_status
FROM markdown_documents
WHERE relative_path = ?
ORDER BY created_at DESC, markdown_document_id DESC
LIMIT 1
""".strip(),
            (row["relative_path"],),
        ).fetchone()
    except sqlite3.OperationalError:
        return
    if not markdown:
        return
    conn.execute(
        """
INSERT INTO recent_file_context_links (
  link_id, candidate_id, query_id, link_kind, source_table, source_id,
  source_path, summary, raw_content_read, raw_body_stored, created_at
) VALUES (?, ?, NULL, 'markdown_atlas_document', 'markdown_documents', ?, ?, ?, 0, 0, ?)
ON CONFLICT(link_id) DO UPDATE SET
  summary = excluded.summary,
  raw_content_read = 0,
  raw_body_stored = 0
""".strip(),
        (
            _row_id("rflink", candidate_id, "markdown_atlas_document", markdown["markdown_document_id"]),
            candidate_id,
            markdown["markdown_document_id"],
            markdown["relative_path"],
            (
                f"Markdown Atlas link retrieval={markdown['retrieval_policy']} "
                f"sensitivity={markdown['sensitivity_status']}"
            ),
            now,
        ),
    )


def build_recent_file_context(
    *,
    db_path: str | Path | None = None,
    run_id: str | None = None,
    limit: int = 100,
) -> RecentFileBuildResult:
    path = init_recent_file_context_schema(db_path)
    now = utc_now()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = _latest_file_event_rows(conn, limit=limit)
        source_digest = hashlib.sha256(
            stable_json([(row["event_id"], row["observed_at"], row["relative_path"]) for row in rows]).encode(
                "utf-8"
            )
        ).hexdigest()[:20]
        resolved_run_id = run_id or f"recent_file_context_{source_digest}"
        conn.execute("PRAGMA foreign_keys = ON")
        for table in (
            "recent_file_rejections",
            "recent_file_context_links",
            "recent_file_resolution_queries",
            "recent_file_candidates",
        ):
            if table == "recent_file_resolution_queries":
                conn.execute("DELETE FROM recent_file_resolution_queries WHERE run_id = ?", (resolved_run_id,))
            elif table == "recent_file_context_links":
                conn.execute(
                    """
DELETE FROM recent_file_context_links
WHERE candidate_id IN (SELECT candidate_id FROM recent_file_candidates WHERE run_id = ?)
   OR query_id IN (SELECT query_id FROM recent_file_resolution_queries WHERE run_id = ?)
""".strip(),
                    (resolved_run_id, resolved_run_id),
                )
            elif table == "recent_file_rejections":
                conn.execute(
                    """
DELETE FROM recent_file_rejections
WHERE candidate_id IN (SELECT candidate_id FROM recent_file_candidates WHERE run_id = ?)
   OR query_id IN (SELECT query_id FROM recent_file_resolution_queries WHERE run_id = ?)
""".strip(),
                    (resolved_run_id, resolved_run_id),
                )
            else:
                conn.execute("DELETE FROM recent_file_candidates WHERE run_id = ?", (resolved_run_id,))
        conn.execute("DELETE FROM recent_file_context_runs WHERE run_id = ?", (resolved_run_id,))
        conn.execute(
            """
INSERT INTO recent_file_context_runs (
  run_id, resolver_version, created_at, completed_at, source_event_count,
  candidate_count, raw_content_read, raw_body_stored, file_move_allowed,
  file_delete_allowed, runtime_authority, agent_activation_allowed,
  tool_execution_allowed, network_authority, notes
) VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?)
""".strip(),
            (
                resolved_run_id,
                RECENT_FILE_CONTEXT_VERSION,
                now,
                now,
                len(rows),
                "Metadata-only resolver over File Event Queue rows; no file body reads or actions.",
            ),
        )
        _seed_aliases(conn, now)
        candidate_ids = [
            _insert_candidate(conn, run_id=resolved_run_id, row=row, now=now)
            for row in rows
        ]
        kind_counts = Counter(row["file_kind_hint"] for row in rows)
        status_counts = Counter(row["queue_status"] for row in rows)
        conn.execute(
            "UPDATE recent_file_context_runs SET candidate_count = ?, completed_at = ? WHERE run_id = ?",
            (len(candidate_ids), now, resolved_run_id),
        )
        conn.commit()
        return RecentFileBuildResult(
            run_id=resolved_run_id,
            db_path=path,
            source_event_count=len(rows),
            candidate_count=len(candidate_ids),
            counts_by_kind=dict(sorted(kind_counts.items())),
            counts_by_status=dict(sorted(status_counts.items())),
        )
    finally:
        conn.close()


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM recent_file_context_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row[0] if row else None


def _query_type_for_text(text: str) -> tuple[str, str | None]:
    lowered = text.lower()
    if "logic" in lowered or ".logicx" in lowered:
        return "logic_project", "logic_project"
    if "markdown" in lowered or " md " in f" {lowered} " or lowered.endswith(".md"):
        return "markdown_doc", "markdown_doc"
    if "read model" in lowered or "read-model" in lowered:
        return "generated_read_model", "generated_read_model"
    if "report package" in lowered or "node uplink" in lowered or "report bridge" in lowered:
        return "report_bridge_package", "report_bridge_package"
    if "new file" in lowered or "that file" in lowered or "file i just made" in lowered:
        return "generic_recent_file", None
    return "unknown", None


def _candidate_rows_for_query(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    file_kind_hint: str | None,
    limit: int = 10,
) -> list[sqlite3.Row]:
    where = "run_id = ?"
    params: list[Any] = [run_id]
    if file_kind_hint:
        where += " AND file_kind_hint = ?"
        params.append(file_kind_hint)
    return conn.execute(
        f"""
SELECT *
FROM recent_file_candidates
WHERE {where}
ORDER BY observed_at DESC, confidence DESC, relative_path ASC
LIMIT ?
""".strip(),
        (*params, limit),
    ).fetchall()


def _resolution_next_safe_move(status: str, candidate: sqlite3.Row | None) -> str:
    if status == "resolved" and candidate is not None:
        if candidate["file_kind_hint"] == "logic_project":
            return "Draft a metadata-only music/art production plan; do not open, edit, or move the Logic session."
        if candidate["file_kind_hint"] == "markdown_doc":
            return "Inspect Markdown Atlas and approved evidence posture before proposing changes; do not move files."
        if candidate["file_kind_hint"] == "generated_read_model":
            return "Use generated read-model metadata as evidence surface, not truth promotion."
        return "Use file-event metadata to prepare a bounded plan; do not open raw private content or edit files."
    if status == "ambiguous":
        return "Ask the operator which recent file they mean before routing further."
    if status == "blocked_no_go":
        return "Route to Guardian or operator review; do not read raw no-go content."
    return "Ask the operator for a clearer file reference or run a bounded File Event Queue snapshot."


def resolve_recent_file_reference(
    *,
    query_text: str,
    db_path: str | Path | None = None,
    run_id: str | None = None,
    query_id: str | None = None,
) -> RecentFileResolutionResult:
    normalized = " ".join(query_text.strip().split())
    if not normalized:
        raise ValueError("query_text is required")
    path = init_recent_file_context_schema(db_path)
    now = utc_now()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_run_id(conn)
        query_type, file_kind_hint = _query_type_for_text(normalized)
        resolved_query_id = query_id or _row_id("rfquery", resolved_run_id or "no_run", normalized, now)
        if not resolved_run_id:
            status = "unresolved"
            candidates: list[sqlite3.Row] = []
            candidate = None
            reason = "no Recent File Context run exists"
        else:
            candidates = _candidate_rows_for_query(conn, run_id=resolved_run_id, file_kind_hint=file_kind_hint)
            safe_candidates = [
                row
                for row in candidates
                if not row["no_go_boundary"] and row["queue_status"] != "blocked_no_go"
            ]
            blocked_candidates = [
                row
                for row in candidates
                if row["no_go_boundary"] or row["queue_status"] == "blocked_no_go"
            ]
            if not candidates:
                status = "unresolved"
                candidate = None
                reason = "no recent file candidate matched the query"
            elif blocked_candidates and not safe_candidates:
                status = "blocked_no_go"
                candidate = blocked_candidates[0]
                reason = "matching candidates are no-go/sensitive metadata only"
            elif len(safe_candidates) == 1:
                status = "resolved"
                candidate = safe_candidates[0]
                reason = f"single recent {candidate['file_kind_hint']} candidate matched"
            else:
                status = "ambiguous"
                candidate = None
                reason = f"{len(safe_candidates)} recent candidates matched"

        confidence = float(candidate["confidence"]) if candidate is not None and status == "resolved" else 0.25
        if status == "ambiguous":
            confidence = 0.45
        elif status == "blocked_no_go":
            confidence = 0.2
        next_safe_move = _resolution_next_safe_move(status, candidate)
        conn.execute(
            """
INSERT INTO recent_file_resolution_queries (
  query_id, run_id, query_text, query_type, resolution_status, candidate_id,
  candidate_count, confidence, reason, next_safe_move, raw_content_read,
  raw_body_stored, file_move_allowed, file_delete_allowed, execution_allowed,
  created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, ?)
ON CONFLICT(query_id) DO UPDATE SET
  run_id = excluded.run_id,
  query_text = excluded.query_text,
  query_type = excluded.query_type,
  resolution_status = excluded.resolution_status,
  candidate_id = excluded.candidate_id,
  candidate_count = excluded.candidate_count,
  confidence = excluded.confidence,
  reason = excluded.reason,
  next_safe_move = excluded.next_safe_move,
  raw_content_read = 0,
  raw_body_stored = 0,
  file_move_allowed = 0,
  file_delete_allowed = 0,
  execution_allowed = 0
""".strip(),
            (
                resolved_query_id,
                resolved_run_id,
                normalized,
                query_type,
                status,
                candidate["candidate_id"] if candidate is not None else None,
                len(candidates),
                confidence,
                reason,
                next_safe_move,
                now,
            ),
        )
        if candidate is not None:
            conn.execute(
                """
INSERT INTO recent_file_context_links (
  link_id, candidate_id, query_id, link_kind, source_table, source_id,
  source_path, summary, raw_content_read, raw_body_stored, created_at
) VALUES (?, ?, ?, 'resolution_candidate', 'recent_file_candidates', ?, ?, ?, 0, 0, ?)
ON CONFLICT(link_id) DO UPDATE SET
  summary = excluded.summary,
  raw_content_read = 0,
  raw_body_stored = 0
""".strip(),
                (
                    _row_id("rflink", resolved_query_id, candidate["candidate_id"]),
                    candidate["candidate_id"],
                    resolved_query_id,
                    candidate["candidate_id"],
                    candidate["relative_path"],
                    f"Query resolved status={status} to {candidate['relative_path']}",
                    now,
                ),
            )
        if status in {"ambiguous", "unresolved", "blocked_no_go", "needs_operator_review"}:
            conn.execute(
                """
INSERT INTO recent_file_rejections (
  rejection_id, query_id, candidate_id, rejection_reason, created_at
) VALUES (?, ?, ?, ?, ?)
ON CONFLICT(rejection_id) DO UPDATE SET
  rejection_reason = excluded.rejection_reason
""".strip(),
                (
                    _row_id("rfrej", resolved_query_id, status, reason),
                    resolved_query_id,
                    candidate["candidate_id"] if candidate is not None else None,
                    reason,
                    now,
                ),
            )
        conn.commit()
        return RecentFileResolutionResult(
            query_id=resolved_query_id,
            query_text=normalized,
            query_type=query_type,
            resolution_status=status,
            candidate_id=candidate["candidate_id"] if candidate is not None else None,
            confidence=confidence,
            reason=reason,
            next_safe_move=next_safe_move,
            candidate_count=len(candidates),
        )
    finally:
        conn.close()


REPORT_SECTIONS = {"summary", "recent", "unresolved"}


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _candidate_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": row["candidate_id"],
        "source_event_id": row["source_event_id"],
        "root_id": row["root_id"],
        "relative_path": row["relative_path"],
        "observed_at": row["observed_at"],
        "event_type": row["event_type"],
        "file_kind_hint": row["file_kind_hint"],
        "world_hint": row["world_hint"],
        "sensitivity_hint": row["sensitivity_hint"],
        "queue_status": row["queue_status"],
        "safe_hash_available": bool(row["safe_hash_available"]),
        "can_agent_read": bool(row["can_agent_read"]),
        "metadata_only": bool(row["metadata_only"]),
        "no_go_boundary": bool(row["no_go_boundary"]),
        "confidence": row["confidence"],
        "reason": row["reason"],
    }


def build_recent_file_context_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
    run_id: str | None = None,
) -> dict[str, Any]:
    if report not in REPORT_SECTIONS:
        raise ValueError(f"unknown recent file report: {report}")
    path = init_recent_file_context_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_run_id(conn)
        if not resolved_run_id:
            return {
                "status": "no_runs",
                "report": report,
                "run_id": None,
                "db_path": str(path),
                "counts": {},
                "items": [],
                "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
            }
        run = conn.execute(
            "SELECT * FROM recent_file_context_runs WHERE run_id = ?",
            (resolved_run_id,),
        ).fetchone()
        candidates = _dict_rows(
            conn,
            """
SELECT *
FROM recent_file_candidates
WHERE run_id = ?
ORDER BY observed_at DESC, confidence DESC, relative_path ASC
""".strip(),
            (resolved_run_id,),
        )
        queries = _dict_rows(
            conn,
            """
SELECT *
FROM recent_file_resolution_queries
WHERE run_id = ?
ORDER BY created_at DESC, query_id DESC
""".strip(),
            (resolved_run_id,),
        )
        if report == "recent":
            items = candidates[:20]
        elif report == "unresolved":
            items = [
                row
                for row in queries
                if row["resolution_status"] in {"ambiguous", "unresolved", "blocked_no_go", "needs_operator_review"}
            ][:20]
        else:
            items = candidates[:10]
        return {
            "status": "ok",
            "report": report,
            "db_path": str(path),
            "run": dict(run) if run else None,
            "run_id": resolved_run_id,
            "counts": {
                "candidate_count": len(candidates),
                "query_count": len(queries),
                "by_kind": dict(sorted(Counter(row["file_kind_hint"] for row in candidates).items())),
                "by_world": dict(sorted(Counter(row["world_hint"] for row in candidates).items())),
                "by_queue_status": dict(sorted(Counter(row["queue_status"] for row in candidates).items())),
                "by_resolution_status": dict(
                    sorted(Counter(row["resolution_status"] for row in queries).items())
                ),
                "metadata_only": sum(1 for row in candidates if row["metadata_only"]),
                "agent_readable": sum(1 for row in candidates if row["can_agent_read"]),
                "no_go_boundary": sum(1 for row in candidates if row["no_go_boundary"]),
            },
            "items": [_candidate_summary(row) if "candidate_id" in row.keys() else dict(row) for row in items],
            "latest_query": dict(queries[0]) if queries else None,
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def _counts_line(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def format_recent_file_context_report(payload: dict[str, Any]) -> str:
    if payload["status"] != "ok":
        return "\n".join(
            [
                f"Recent File Context v0 - {payload['report']}",
                "",
                f"Status: {payload['status']}",
                "No recent file context run is available.",
            ]
        )
    counts = payload["counts"]
    lines = [
        f"Recent File Context v0 - {payload['report']}",
        "",
        f"Run: `{payload['run_id']}`",
        f"Candidates: {counts['candidate_count']}",
        f"Queries: {counts['query_count']}",
        f"By kind: {_counts_line(counts['by_kind'])}",
        f"By world: {_counts_line(counts['by_world'])}",
        f"By queue status: {_counts_line(counts['by_queue_status'])}",
        f"By resolution: {_counts_line(counts['by_resolution_status'])}",
        f"Metadata-only candidates: {counts['metadata_only']}",
        f"Agent-readable candidates: {counts['agent_readable']}",
        f"No-go boundary candidates: {counts['no_go_boundary']}",
        "",
        "Items:",
    ]
    for item in payload.get("items") or []:
        if "candidate_id" in item:
            lines.append(
                f"- `{item['candidate_id']}` {item['event_type']} `{item['relative_path']}` "
                f"kind={item['file_kind_hint']} world={item['world_hint']} "
                f"metadata_only={str(item['metadata_only']).lower()} can_agent_read={str(item['can_agent_read']).lower()}"
            )
        else:
            lines.append(
                f"- `{item['query_id']}` {item['resolution_status']} query=`{item['query_text']}` reason={item['reason']}"
            )
    if not payload.get("items"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Metadata-only resolver over File Event Queue rows.",
            "- No raw file bodies are read or stored; no file move/delete/action/runtime authority is granted.",
        ]
    )
    return "\n".join(lines)


def build_recent_file_context_read_model(
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    report = build_recent_file_context_report(db_path=db_path, report="summary")
    generated_at = utc_now()
    if report.get("run"):
        generated_at = report["run"].get("completed_at") or generated_at
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "mode": "recent_file_context_metadata_only",
        "generated_at": generated_at,
        "source_ledger_path": _display_path(report["db_path"]),
        "source_ledger_namespace": "recent_file_*",
        "latest_run_id": report.get("run_id"),
        "candidate_count": report.get("counts", {}).get("candidate_count", 0),
        "query_count": report.get("counts", {}).get("query_count", 0),
        "counts_by_kind": report.get("counts", {}).get("by_kind", {}),
        "counts_by_world": report.get("counts", {}).get("by_world", {}),
        "counts_by_queue_status": report.get("counts", {}).get("by_queue_status", {}),
        "counts_by_resolution_status": report.get("counts", {}).get("by_resolution_status", {}),
        "metadata_only_count": report.get("counts", {}).get("metadata_only", 0),
        "agent_readable_count": report.get("counts", {}).get("agent_readable", 0),
        "no_go_boundary_count": report.get("counts", {}).get("no_go_boundary", 0),
        "recent_candidates": report.get("items", []),
        "latest_query": report.get("latest_query"),
        "supported_queries": [
            "that new file",
            "the file I just made",
            "the new Logic file",
            "that Markdown doc from earlier",
            "the recent report package",
        ],
        "next_safe_move": "Use this metadata to route intent or ask a clarifying question; do not open raw private files or execute actions.",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_recent_file_context_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# Recent File Context Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over `recent_file_*` SQLite rows.",
        "- It resolves vague file references against File Event Queue metadata.",
        "",
        "What this is not:",
        "- It is not file ingestion, file editing, raw private content access, agent activation, or execution.",
        "",
        "Summary:",
        f"- Latest run: `{read_model['latest_run_id'] or 'none'}`.",
        f"- Candidates: {read_model['candidate_count']}.",
        f"- Queries: {read_model['query_count']}.",
        f"- By kind: {_counts_line(read_model['counts_by_kind'])}.",
        f"- By world: {_counts_line(read_model['counts_by_world'])}.",
        f"- Metadata-only candidates: {read_model['metadata_only_count']}.",
        f"- Agent-readable candidates: {read_model['agent_readable_count']}.",
        f"- No-go boundary candidates: {read_model['no_go_boundary_count']}.",
        "",
        "Next safe move:",
        f"- {read_model['next_safe_move']}",
        "",
        "Authority boundary:",
        "- raw_content_read=false; raw_body_stored=false; file_move_allowed=false; file_delete_allowed=false.",
        "- runtime_authority=false; agent_activation_allowed=false; tool_execution_allowed=false; network_authority=false.",
    ]
    return "\n".join(lines) + "\n"


def export_recent_file_context_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_recent_file_context_read_model(db_path=db_path)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_recent_file_context_read_model(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "candidate_count": read_model["candidate_count"],
        "query_count": read_model["query_count"],
        **NO_AUTHORITY_FLAGS,
    }


def format_resolution_result(result: RecentFileResolutionResult) -> str:
    return "\n".join(
        [
            "Recent File Context v0",
            "",
            f"Query: `{result.query_text}`",
            f"Query id: `{result.query_id}`",
            f"Type: `{result.query_type}`",
            f"Status: `{result.resolution_status}`",
            f"Candidate: `{result.candidate_id or 'none'}`",
            f"Candidate count: {result.candidate_count}",
            f"Confidence: {result.confidence:.2f}",
            f"Reason: {result.reason}",
            "",
            "Next safe move:",
            f"- {result.next_safe_move}",
            "",
            "Boundary:",
            "- No raw file body was read or stored.",
            "- No file move, delete, action execution, agent activation, model call, or tool execution occurred.",
        ]
    )


__all__ = [
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_VERSION",
    "RECENT_FILE_CONTEXT_VERSION",
    "REPORT_SECTIONS",
    "RecentFileBuildResult",
    "RecentFileResolutionResult",
    "build_recent_file_context",
    "build_recent_file_context_read_model",
    "build_recent_file_context_report",
    "export_recent_file_context_read_model",
    "format_recent_file_context_read_model",
    "format_recent_file_context_report",
    "format_resolution_result",
    "init_recent_file_context_schema",
    "recent_file_table_names",
    "resolve_recent_file_reference",
    "stable_json",
]
