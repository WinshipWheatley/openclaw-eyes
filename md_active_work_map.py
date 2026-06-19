"""Active open-work map over the Mac Markdown corpus.

This is a deterministic operator-facing rollup over the existing corpus and
staleness SQLite tables. It does not scan new roots, call models, send
messages, modify source Markdown, or promote Markdown prose into truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from md_corpus_ingest import DEFAULT_DB_PATH, NO_AUTHORITY_FLAGS as CORPUS_NO_AUTHORITY_FLAGS, stable_json


MD_ACTIVE_WORK_MAP_VERSION = "md_active_work_map_v0"
DEFAULT_LIMIT = 20

NO_AUTHORITY_FLAGS = {
    **CORPUS_NO_AUTHORITY_FLAGS,
    "source_markdown_writeback_allowed": False,
    "truth_claimed": False,
    "advisory_only": True,
}


@dataclass(frozen=True)
class MarkdownActiveWorkMapResult:
    map_id: str
    db_path: str
    source_corpus_run_id: str
    staleness_run_id: str
    open_document_count: int
    top_document_count: int
    top_documents: list[dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _latest_run(conn: sqlite3.Connection, table: str) -> str | None:
    row = conn.execute(
        f"""
SELECT run_id
FROM {table}
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row[0] if row else None


def _priority_score(row: sqlite3.Row) -> int:
    score = 0
    score += int(row["open_task_count"] or 0) * 10
    score += int(row["todo_marker_count"] or 0) * 6
    score += int(row["inbound_link_count"] or 0) * 3
    score += min(int(row["outbound_link_count"] or 0), 5)
    if row["staleness_status"] == "active_with_open_tasks":
        score += 5
    return score


def init_md_active_work_map_schema(db_path: str | Path) -> str:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
CREATE TABLE IF NOT EXISTS md_active_work_map_receipts (
  map_id TEXT PRIMARY KEY,
  map_version TEXT NOT NULL,
  source_corpus_run_id TEXT NOT NULL,
  staleness_run_id TEXT NOT NULL,
  open_document_count INTEGER NOT NULL DEFAULT 0,
  top_document_count INTEGER NOT NULL DEFAULT 0,
  top_documents_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  vector_search_allowed INTEGER NOT NULL DEFAULT 0,
  source_markdown_writeback_allowed INTEGER NOT NULL DEFAULT 0,
  truth_claimed INTEGER NOT NULL DEFAULT 0,
  advisory_only INTEGER NOT NULL DEFAULT 1
)
""".strip()
        )
    return Path(db_path).as_posix()


def md_active_work_map_table_names(db_path: str | Path) -> tuple[str, ...]:
    init_md_active_work_map_schema(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'md_active_work_map_%'
ORDER BY name
""".strip()
        ).fetchall()
    return tuple(row[0] for row in rows)


def build_active_work_map(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    map_id: str | None = None,
    source_corpus_run_id: str | None = None,
    staleness_run_id: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> MarkdownActiveWorkMapResult:
    db = Path(db_path)
    active_map_id = map_id or _row_id("md_active_work_map", utc_now(), limit)
    init_md_active_work_map_schema(db)
    created_at = utc_now()
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        corpus_run = source_corpus_run_id or _latest_run(conn, "md_corpus_runs")
        if not corpus_run:
            raise ValueError("no md_corpus_runs found; run md_corpus_ingest first")
        stale_run = staleness_run_id or _latest_run(conn, "md_staleness_runs")
        if not stale_run:
            raise ValueError("no md_staleness_runs found; run md_staleness first")
        rows = conn.execute(
            """
SELECT d.relative_path,
       d.title,
       d.mtime_iso,
       d.git_last_commit,
       s.staleness_status,
       s.reason_codes_json,
       s.inbound_link_count,
       s.outbound_link_count,
       s.todo_marker_count,
       s.open_task_count,
       s.done_marker_count,
       s.superseded_marker_count
FROM md_corpus_documents d
JOIN md_staleness_documents s
  ON s.source_corpus_run_id = d.run_id
 AND s.relative_path = d.relative_path
WHERE d.run_id = ?
  AND s.run_id = ?
  AND s.staleness_status != 'done_or_superseded'
  AND (s.staleness_status = 'active_with_open_tasks'
       OR s.todo_marker_count > 0
       OR s.open_task_count > 0)
""".strip(),
            (corpus_run, stale_run),
        ).fetchall()
        ranked: list[dict[str, Any]] = []
        for row in rows:
            ranked.append(
                {
                    "relative_path": row["relative_path"],
                    "title": row["title"],
                    "priority_score": _priority_score(row),
                    "staleness_status": row["staleness_status"],
                    "staleness_reasons": json.loads(row["reason_codes_json"] or "[]"),
                    "todo_marker_count": row["todo_marker_count"] or 0,
                    "open_task_count": row["open_task_count"] or 0,
                    "inbound_link_count": row["inbound_link_count"] or 0,
                    "outbound_link_count": row["outbound_link_count"] or 0,
                    "mtime_iso": row["mtime_iso"],
                    "git_last_commit": row["git_last_commit"],
                    "truth_claimed": False,
                    "writeback_allowed": False,
                }
            )
        ranked.sort(key=lambda item: (-item["priority_score"], item["relative_path"]))
        top_documents = ranked[: max(limit, 0)]
        conn.execute(
            """
INSERT OR REPLACE INTO md_active_work_map_receipts (
  map_id, map_version, source_corpus_run_id, staleness_run_id,
  open_document_count, top_document_count, top_documents_json, created_at,
  model_call_allowed, vector_search_allowed, source_markdown_writeback_allowed,
  truth_claimed, advisory_only
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 1)
""".strip(),
            (
                active_map_id,
                MD_ACTIVE_WORK_MAP_VERSION,
                corpus_run,
                stale_run,
                len(ranked),
                len(top_documents),
                stable_json(top_documents),
                created_at,
            ),
        )
    return MarkdownActiveWorkMapResult(
        map_id=active_map_id,
        db_path=db.as_posix(),
        source_corpus_run_id=corpus_run,
        staleness_run_id=stale_run,
        open_document_count=len(ranked),
        top_document_count=len(top_documents),
        top_documents=top_documents,
    )


def result_as_dict(result: MarkdownActiveWorkMapResult) -> dict[str, Any]:
    return {
        **result.__dict__,
        "map_version": MD_ACTIVE_WORK_MAP_VERSION,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
    }


def format_operator_result(result: MarkdownActiveWorkMapResult) -> str:
    lines = [
        "Markdown Active Work Map",
        "",
        "Evidence:",
        f"- Map ID: `{result.map_id}`.",
        f"- DB: `{result.db_path}`.",
        f"- Source corpus run: `{result.source_corpus_run_id}`.",
        f"- Staleness run: `{result.staleness_run_id}`.",
        f"- Open document count: `{result.open_document_count}`.",
        f"- Top document count: `{result.top_document_count}`.",
        "",
        "Top Open-Work Documents:",
    ]
    if not result.top_documents:
        lines.append("- No active/open-work documents found.")
    for item in result.top_documents:
        lines.append(
            f"- `{item['relative_path']}` (score {item['priority_score']}, "
            f"tasks {item['open_task_count']}, TODO {item['todo_marker_count']}): "
            f"{item['title']}"
        )
    lines.extend(
        [
            "",
            "Authority:",
            "- Model calls: `false`.",
            "- Vector search: `false`.",
            "- Source Markdown writeback: `false`.",
            "- Truth claimed: `false`.",
            "- Advisory only: `true`.",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a deterministic active-work map from Mac Markdown SQLite.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite corpus path.")
    parser.add_argument("--map-id", help="Stable map id for deterministic receipts.")
    parser.add_argument("--source-corpus-run-id", help="Specific md_corpus_runs.run_id to map.")
    parser.add_argument("--staleness-run-id", help="Specific md_staleness_runs.run_id to join.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_active_work_map(
        db_path=args.db,
        map_id=args.map_id,
        source_corpus_run_id=args.source_corpus_run_id,
        staleness_run_id=args.staleness_run_id,
        limit=args.limit,
    )
    if args.format == "json":
        print(stable_json(result_as_dict(result)), end="")
    else:
        print(format_operator_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
