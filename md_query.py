"""Deterministic Markdown corpus query layer.

Provides bounded "what work on X?" lookup over the Mac Markdown corpus and
staleness SQLite tables. It does not call models, perform vector search, access
new filesystem roots, or promote Markdown prose into truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from md_corpus_ingest import DEFAULT_DB_PATH, NO_AUTHORITY_FLAGS as CORPUS_NO_AUTHORITY_FLAGS, stable_json


MD_QUERY_VERSION = "md_query_v0"
MAX_EXCERPT_CHARS = 320
DEFAULT_LIMIT = 10
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_/-]{2,}")

NO_AUTHORITY_FLAGS = {
    **CORPUS_NO_AUTHORITY_FLAGS,
    "vector_search_allowed": False,
    "truth_claimed": False,
}


@dataclass(frozen=True)
class MarkdownQueryResult:
    query_id: str
    query_text: str
    db_path: str
    source_corpus_run_id: str | None
    staleness_run_id: str | None
    result_count: int
    results: list[dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _tokens(query: str) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for token in TOKEN_PATTERN.findall(query.lower()):
        if token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


def _latest_run(conn: sqlite3.Connection, table: str) -> str | None:
    column = "run_id"
    order_column = "completed_at"
    row = conn.execute(
        f"""
SELECT {column}
FROM {table}
ORDER BY {order_column} DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row[0] if row else None


def _excerpt(text: str, tokens: list[str]) -> str:
    lowered = text.lower()
    position = min((lowered.find(token) for token in tokens if token in lowered), default=0)
    start = max(position - 80, 0)
    end = min(start + MAX_EXCERPT_CHARS, len(text))
    excerpt = text[start:end].replace("\n", " ").strip()
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(text):
        excerpt += "..."
    return excerpt


def init_md_query_schema(db_path: str | Path) -> str:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
CREATE TABLE IF NOT EXISTS md_query_receipts (
  query_id TEXT PRIMARY KEY,
  query_version TEXT NOT NULL,
  query_text TEXT NOT NULL,
  query_tokens_json TEXT NOT NULL,
  source_corpus_run_id TEXT,
  staleness_run_id TEXT,
  result_count INTEGER NOT NULL DEFAULT 0,
  results_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  vector_search_allowed INTEGER NOT NULL DEFAULT 0,
  truth_claimed INTEGER NOT NULL DEFAULT 0
)
""".strip()
        )
    return Path(db_path).as_posix()


def md_query_table_names(db_path: str | Path) -> tuple[str, ...]:
    init_md_query_schema(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'md_query_%'
ORDER BY name
""".strip()
        ).fetchall()
    return tuple(row[0] for row in rows)


def _score_row(row: sqlite3.Row, tokens: list[str]) -> int:
    haystacks = {
        "relative_path": (row["relative_path"] or "").lower(),
        "title": (row["title"] or "").lower(),
        "text": (row["text"] or "").lower(),
    }
    score = 0
    for token in tokens:
        if token in haystacks["relative_path"]:
            score += 8
        if token in haystacks["title"]:
            score += 5
        if token in haystacks["text"]:
            score += min(haystacks["text"].count(token), 5)
    return score


def query_markdown_corpus(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    query: str,
    limit: int = DEFAULT_LIMIT,
    source_corpus_run_id: str | None = None,
    staleness_run_id: str | None = None,
    query_id: str | None = None,
) -> MarkdownQueryResult:
    db = Path(db_path)
    tokens = _tokens(query)
    if not tokens:
        raise ValueError("query must contain at least one searchable token")
    init_md_query_schema(db)
    active_query_id = query_id or _row_id("md_query", query, utc_now())
    created_at = utc_now()
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        corpus_run = source_corpus_run_id or _latest_run(conn, "md_corpus_runs")
        if not corpus_run:
            raise ValueError("no md_corpus_runs found; run md_corpus_ingest first")
        stale_run = staleness_run_id or _latest_run(conn, "md_staleness_runs")
        rows = conn.execute(
            """
SELECT d.*,
       s.staleness_status,
       s.reason_codes_json,
       s.inbound_link_count,
       s.outbound_link_count,
       s.todo_marker_count,
       s.open_task_count,
       s.done_marker_count
FROM md_corpus_documents d
LEFT JOIN md_staleness_documents s
  ON s.source_corpus_run_id = d.run_id
 AND s.relative_path = d.relative_path
 AND (? IS NULL OR s.run_id = ?)
WHERE d.run_id = ?
""".strip(),
            (stale_run, stale_run, corpus_run),
        ).fetchall()
        scored: list[tuple[int, sqlite3.Row]] = []
        for row in rows:
            score = _score_row(row, tokens)
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], item[1]["relative_path"]))
        results: list[dict[str, Any]] = []
        for score, row in scored[:limit]:
            results.append(
                {
                    "relative_path": row["relative_path"],
                    "title": row["title"],
                    "score": score,
                    "excerpt": _excerpt(row["text"], tokens),
                    "staleness_status": row["staleness_status"] or "not_classified",
                    "staleness_reasons": json.loads(row["reason_codes_json"] or "[]"),
                    "todo_marker_count": row["todo_marker_count"] or 0,
                    "open_task_count": row["open_task_count"] or 0,
                    "done_marker_count": row["done_marker_count"] or 0,
                    "inbound_link_count": row["inbound_link_count"] or 0,
                    "outbound_link_count": row["outbound_link_count"] or 0,
                    "mtime_iso": row["mtime_iso"],
                    "git_last_commit": row["git_last_commit"],
                    "truth_claimed": False,
                }
            )
        conn.execute(
            """
INSERT OR REPLACE INTO md_query_receipts (
  query_id, query_version, query_text, query_tokens_json, source_corpus_run_id,
  staleness_run_id, result_count, results_json, created_at, model_call_allowed,
  vector_search_allowed, truth_claimed
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
""".strip(),
            (
                active_query_id,
                MD_QUERY_VERSION,
                query,
                stable_json(tokens),
                corpus_run,
                stale_run,
                len(results),
                stable_json(results),
                created_at,
            ),
        )
    return MarkdownQueryResult(
        query_id=active_query_id,
        query_text=query,
        db_path=db.as_posix(),
        source_corpus_run_id=corpus_run,
        staleness_run_id=stale_run,
        result_count=len(results),
        results=results,
    )


def result_as_dict(result: MarkdownQueryResult) -> dict[str, Any]:
    return {
        **result.__dict__,
        "query_version": MD_QUERY_VERSION,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
    }


def format_operator_result(result: MarkdownQueryResult) -> str:
    lines = [
        "Markdown Query",
        "",
        "Evidence:",
        f"- Query ID: `{result.query_id}`.",
        f"- Query: `{result.query_text}`.",
        f"- DB: `{result.db_path}`.",
        f"- Source corpus run: `{result.source_corpus_run_id}`.",
        f"- Staleness run: `{result.staleness_run_id}`.",
        f"- Result count: `{result.result_count}`.",
        "",
        "Results:",
    ]
    if not result.results:
        lines.append("- No matches.")
    for item in result.results:
        lines.append(
            f"- `{item['relative_path']}` ({item['staleness_status']}, score {item['score']}): "
            f"{item['excerpt']}"
        )
    lines.extend(
        [
            "",
            "Authority:",
            "- Model calls: `false`.",
            "- Vector search: `false`.",
            "- Truth claimed: `false`.",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Mac Markdown corpus SQLite deterministically.")
    parser.add_argument("query", help="Plain text query, e.g. 'what work on V0 send hold'")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite corpus path.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--source-corpus-run-id", help="Specific md_corpus_runs.run_id to query.")
    parser.add_argument("--staleness-run-id", help="Specific md_staleness_runs.run_id to join.")
    parser.add_argument("--query-id", help="Stable query id for deterministic receipts.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = query_markdown_corpus(
        db_path=args.db,
        query=args.query,
        limit=args.limit,
        source_corpus_run_id=args.source_corpus_run_id,
        staleness_run_id=args.staleness_run_id,
        query_id=args.query_id,
    )
    if args.format == "json":
        print(stable_json(result_as_dict(result)), end="")
    else:
        print(format_operator_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
