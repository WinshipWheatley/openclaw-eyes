"""Markdown corpus staleness classifier.

Reads the Mac Markdown corpus SQLite tables and records deterministic freshness
signals without scanning additional files. This is advisory metadata only: no
file moves/deletes, no truth promotion, no Legal Discovery access.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from md_corpus_ingest import DEFAULT_DB_PATH, NO_AUTHORITY_FLAGS as CORPUS_NO_AUTHORITY_FLAGS, stable_json


MD_STALENESS_VERSION = "md_staleness_v0"
DEFAULT_FRESH_DAYS = 7.0
DEFAULT_STALE_DAYS = 30.0

NO_AUTHORITY_FLAGS = {
    **CORPUS_NO_AUTHORITY_FLAGS,
    "file_archive_allowed": False,
    "advisory_only": True,
}


@dataclass(frozen=True)
class MarkdownStalenessResult:
    run_id: str
    db_path: str
    source_corpus_run_id: str
    document_count: int
    counts_by_status: dict[str, int]
    fresh_days: float
    stale_days: float


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _now_epoch(now: str | None = None) -> float:
    if not now:
        return datetime.now(timezone.utc).timestamp()
    return datetime.fromisoformat(now.replace("Z", "+00:00")).timestamp()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS md_staleness_runs (
  run_id TEXT PRIMARY KEY,
  staleness_version TEXT NOT NULL,
  source_corpus_run_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  document_count INTEGER NOT NULL DEFAULT 0,
  fresh_days REAL NOT NULL,
  stale_days REAL NOT NULL,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  truth_promotion_allowed INTEGER NOT NULL DEFAULT 0,
  advisory_only INTEGER NOT NULL DEFAULT 1
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS md_staleness_documents (
  staleness_document_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  source_corpus_run_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  title TEXT NOT NULL,
  staleness_status TEXT NOT NULL,
  reason_codes_json TEXT NOT NULL,
  age_days REAL NOT NULL,
  inbound_link_count INTEGER NOT NULL,
  outbound_link_count INTEGER NOT NULL,
  todo_marker_count INTEGER NOT NULL,
  open_task_count INTEGER NOT NULL,
  done_marker_count INTEGER NOT NULL,
  superseded_marker_count INTEGER NOT NULL,
  mtime_iso TEXT NOT NULL,
  git_last_commit TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES md_staleness_runs(run_id) ON DELETE CASCADE,
  UNIQUE(run_id, relative_path)
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_md_staleness_documents_run ON md_staleness_documents(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_md_staleness_documents_status ON md_staleness_documents(staleness_status)",
    )


def init_md_staleness_schema(db_path: str | Path) -> str:
    with sqlite3.connect(db_path) as conn:
        for statement in _sql_statements():
            conn.execute(statement)
    return Path(db_path).as_posix()


def md_staleness_table_names(db_path: str | Path) -> tuple[str, ...]:
    init_md_staleness_schema(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'md_staleness_%'
ORDER BY name
""".strip()
        ).fetchall()
    return tuple(row[0] for row in rows)


def _latest_corpus_run_id(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        """
SELECT run_id
FROM md_corpus_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    if not row:
        raise ValueError("no md_corpus_runs found; run md_corpus_ingest first")
    return row[0]


def _load_documents(conn: sqlite3.Connection, corpus_run_id: str) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
SELECT *
FROM md_corpus_documents
WHERE run_id = ?
ORDER BY relative_path
""".strip(),
        (corpus_run_id,),
    ).fetchall()


def _path_keys(relative_path: str) -> set[str]:
    path = Path(relative_path)
    return {
        relative_path.lower(),
        path.name.lower(),
        path.stem.lower(),
        path.with_suffix("").as_posix().lower(),
    }


def _link_targets(row: sqlite3.Row) -> list[str]:
    try:
        links = json.loads(row["links_json"])
    except (TypeError, json.JSONDecodeError):
        return []
    targets: list[str] = []
    for link in links:
        if isinstance(link, dict) and link.get("target"):
            targets.append(str(link["target"]).split("#", 1)[0].strip().lower())
    return targets


def _count_status(row: sqlite3.Row, marker_name: str) -> int:
    try:
        markers = json.loads(row["status_markers_json"])
    except (TypeError, json.JSONDecodeError):
        return 0
    return sum(
        1
        for marker in markers
        if isinstance(marker, dict) and str(marker.get("marker", "")).upper() == marker_name
    )


def _open_task_count(row: sqlite3.Row) -> int:
    try:
        tasks = json.loads(row["tasks_json"])
    except (TypeError, json.JSONDecodeError):
        return 0
    return sum(1 for task in tasks if isinstance(task, dict) and task.get("checked") is False)


def _classify_document(
    row: sqlite3.Row,
    *,
    age_days: float,
    inbound_link_count: int,
    outbound_link_count: int,
    fresh_days: float,
    stale_days: float,
) -> tuple[str, list[str], dict[str, int]]:
    text = (row["text"] or "").lower()
    path = (row["relative_path"] or "").lower()
    todo_count = _count_status(row, "TODO")
    done_count = _count_status(row, "DONE")
    open_tasks = _open_task_count(row)
    superseded_count = text.count("superseded") + path.count("superseded")
    reasons: list[str] = []

    if superseded_count or done_count:
        reasons.append("done_or_superseded_marker")
        status = "done_or_superseded"
    elif todo_count or open_tasks:
        reasons.append("open_todo_or_task")
        status = "active_with_open_tasks"
    elif age_days > stale_days and inbound_link_count == 0:
        reasons.extend(["mtime_older_than_stale_days", "no_inbound_links"])
        status = "stale_unreferenced"
    elif age_days > stale_days:
        reasons.append("mtime_older_than_stale_days")
        status = "stale_by_mtime"
    elif age_days <= fresh_days:
        reasons.append("mtime_within_fresh_days")
        status = "current_recent"
    else:
        reasons.append("within_review_window")
        status = "current_or_review"

    if outbound_link_count:
        reasons.append("has_outbound_links")
    if inbound_link_count:
        reasons.append("has_inbound_links")

    return (
        status,
        reasons,
        {
            "todo_marker_count": todo_count,
            "open_task_count": open_tasks,
            "done_marker_count": done_count,
            "superseded_marker_count": superseded_count,
        },
    )


def build_markdown_staleness(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    run_id: str | None = None,
    source_corpus_run_id: str | None = None,
    now: str | None = None,
    fresh_days: float = DEFAULT_FRESH_DAYS,
    stale_days: float = DEFAULT_STALE_DAYS,
) -> MarkdownStalenessResult:
    db = Path(db_path)
    active_run_id = run_id or f"md_staleness_{utc_now().replace(':', '').replace('+', 'Z')}"
    created_at = utc_now()
    now_epoch = _now_epoch(now)
    init_md_staleness_schema(db)

    with sqlite3.connect(db) as conn:
        corpus_run_id = source_corpus_run_id or _latest_corpus_run_id(conn)
        documents = _load_documents(conn, corpus_run_id)
        target_keys: dict[str, str] = {}
        for row in documents:
            for key in _path_keys(row["relative_path"]):
                target_keys[key] = row["relative_path"]
        inbound: dict[str, int] = defaultdict(int)
        outbound: dict[str, int] = {}
        for row in documents:
            targets = _link_targets(row)
            outbound[row["relative_path"]] = len(targets)
            for target in targets:
                target_path = target_keys.get(target) or target_keys.get(Path(target).name.lower())
                if target_path:
                    inbound[target_path] += 1

        conn.execute("DELETE FROM md_staleness_documents WHERE run_id = ?", (active_run_id,))
        conn.execute("DELETE FROM md_staleness_runs WHERE run_id = ?", (active_run_id,))
        conn.execute(
            """
INSERT INTO md_staleness_runs (
  run_id, staleness_version, source_corpus_run_id, created_at, document_count,
  fresh_days, stale_days, runtime_authority, tool_execution_allowed,
  network_authority, model_call_allowed, file_move_allowed, file_delete_allowed,
  truth_promotion_allowed, advisory_only
) VALUES (?, ?, ?, ?, 0, ?, ?, 0, 0, 0, 0, 0, 0, 0, 1)
""".strip(),
            (active_run_id, MD_STALENESS_VERSION, corpus_run_id, created_at, fresh_days, stale_days),
        )
        counts: Counter[str] = Counter()
        for row in documents:
            age_days = max((now_epoch - float(row["mtime_epoch"])) / 86400.0, 0.0)
            inbound_count = inbound[row["relative_path"]]
            outbound_count = outbound.get(row["relative_path"], 0)
            status, reasons, marker_counts = _classify_document(
                row,
                age_days=age_days,
                inbound_link_count=inbound_count,
                outbound_link_count=outbound_count,
                fresh_days=fresh_days,
                stale_days=stale_days,
            )
            counts[status] += 1
            conn.execute(
                """
INSERT OR REPLACE INTO md_staleness_documents (
  staleness_document_id, run_id, source_corpus_run_id, relative_path, title,
  staleness_status, reason_codes_json, age_days, inbound_link_count,
  outbound_link_count, todo_marker_count, open_task_count, done_marker_count,
  superseded_marker_count, mtime_iso, git_last_commit, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
                (
                    _row_id("md_stale", active_run_id, row["relative_path"]),
                    active_run_id,
                    corpus_run_id,
                    row["relative_path"],
                    row["title"],
                    status,
                    stable_json(reasons),
                    age_days,
                    inbound_count,
                    outbound_count,
                    marker_counts["todo_marker_count"],
                    marker_counts["open_task_count"],
                    marker_counts["done_marker_count"],
                    marker_counts["superseded_marker_count"],
                    row["mtime_iso"],
                    row["git_last_commit"],
                    created_at,
                ),
            )
        conn.execute(
            """
UPDATE md_staleness_runs
SET completed_at = ?, document_count = ?
WHERE run_id = ?
""".strip(),
            (utc_now(), len(documents), active_run_id),
        )

    return MarkdownStalenessResult(
        run_id=active_run_id,
        db_path=db.as_posix(),
        source_corpus_run_id=corpus_run_id,
        document_count=len(documents),
        counts_by_status=dict(sorted(counts.items())),
        fresh_days=fresh_days,
        stale_days=stale_days,
    )


def result_as_dict(result: MarkdownStalenessResult) -> dict[str, Any]:
    return {
        **result.__dict__,
        "staleness_version": MD_STALENESS_VERSION,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
    }


def format_operator_result(result: MarkdownStalenessResult) -> str:
    lines = [
        "Markdown Staleness Classifier",
        "",
        "Evidence:",
        f"- Run ID: `{result.run_id}`.",
        f"- DB: `{result.db_path}`.",
        f"- Source corpus run: `{result.source_corpus_run_id}`.",
        f"- Documents classified: `{result.document_count}`.",
        f"- Fresh days: `{result.fresh_days}`.",
        f"- Stale days: `{result.stale_days}`.",
        "- Counts by status:",
    ]
    lines.extend(f"  - `{key}`: `{value}`." for key, value in result.counts_by_status.items())
    lines.extend(
        [
            "- Advisory only: `true`.",
            "- Runtime/tool/model/network authority: `false`.",
            "- File move/delete/archive authority: `false`.",
            "- Truth promotion: `false`.",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify Markdown corpus staleness from SQLite.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite corpus path.")
    parser.add_argument("--run-id", help="Stable staleness run id.")
    parser.add_argument("--source-corpus-run-id", help="Specific md_corpus_runs.run_id to classify.")
    parser.add_argument("--now", help="ISO timestamp for deterministic age calculations.")
    parser.add_argument("--fresh-days", type=float, default=DEFAULT_FRESH_DAYS)
    parser.add_argument("--stale-days", type=float, default=DEFAULT_STALE_DAYS)
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_markdown_staleness(
        db_path=args.db,
        run_id=args.run_id,
        source_corpus_run_id=args.source_corpus_run_id,
        now=args.now,
        fresh_days=args.fresh_days,
        stale_days=args.stale_days,
    )
    if args.format == "json":
        print(stable_json(result_as_dict(result)), end="")
    else:
        print(format_operator_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
