#!/usr/bin/env python3
"""Gated ingest from the old system_catalog.sqlite3 into the knowledge ledger."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def _columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    if not _table_exists(conn, table_name):
        return set()
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table_name})")}


def _row_value(row: sqlite3.Row, *names: str) -> str:
    for name in names:
        if name in row.keys() and row[name] is not None:
            return str(row[name])
    return ""


def _dedupe_key(row: sqlite3.Row) -> str:
    remote = _row_value(row, "remote_url", "remote_origin", "remote", "url")
    name = _row_value(row, "repo_name", "name")
    path = _row_value(row, "repo_path", "path", "absolute_path")
    if remote:
        return remote.lower()
    if name:
        return f"name:{name.lower()}"
    return f"path:{path.lower()}"


def _load_catalog_repos(catalog_path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(catalog_path)
    conn.row_factory = sqlite3.Row
    try:
        if not _table_exists(conn, "repos"):
            return []
        cols = _columns(conn, "repos")
        order_col = "repo_path" if "repo_path" in cols else next(iter(cols))
        rows = conn.execute(f"SELECT * FROM repos ORDER BY {order_col}").fetchall()
    finally:
        conn.close()
    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        path = _row_value(row, "repo_path", "path", "absolute_path")
        is_worktree = _row_value(row, "is_worktree", "worktree")
        kind = _row_value(row, "kind")
        worktreeish = (
            is_worktree in {"1", "true", "True"}
            or kind == "worktree"
            or "/worktrees/" in path
        )
        key = _dedupe_key(row)
        record = {
            "repo_key": key,
            "repo_name": _row_value(row, "repo_name", "name") or Path(path).name,
            "repo_path": path,
            "remote_url": _row_value(row, "remote_url", "remote_origin", "remote", "url"),
            "branch": _row_value(row, "branch", "current_branch"),
            "head_commit": _row_value(row, "head_commit", "commit_sha", "git_head", "head_sha"),
            "worktree_count": 1 if worktreeish else 0,
            "catalog_source": str(catalog_path),
        }
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = record
            continue
        existing["worktree_count"] = int(existing["worktree_count"]) + int(record["worktree_count"])
        if (
            "/worktrees/" in str(existing["repo_path"])
            or str(existing.get("repo_path") or "").endswith("/generated/external_sources/openclaw-eyes")
        ) and "/worktrees/" not in path:
            existing.update({k: v for k, v in record.items() if k != "worktree_count"})
    return sorted(by_key.values(), key=lambda item: (item["repo_name"], item["repo_path"]))


def _catalog_repo_count(catalog_path: Path) -> int:
    conn = sqlite3.connect(catalog_path)
    try:
        if not _table_exists(conn, "repos"):
            return 0
        return int(conn.execute("SELECT count(*) FROM repos").fetchone()[0])
    finally:
        conn.close()


def _init_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_repo_roots (
            repo_key TEXT PRIMARY KEY,
            repo_name TEXT,
            repo_path TEXT,
            remote_url TEXT,
            branch TEXT,
            head_commit TEXT,
            worktree_count INTEGER DEFAULT 0,
            catalog_source TEXT,
            ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def ingest_system_catalog_to_ledger(
    catalog_path: str | Path,
    ledger_path: str | Path,
    *,
    confirm: bool = False,
) -> dict[str, Any]:
    catalog = Path(catalog_path)
    ledger = Path(ledger_path)
    repos = _load_catalog_repos(catalog)
    raw_repo_count = _catalog_repo_count(catalog)
    result = {
        "catalog_path": str(catalog),
        "ledger_path": str(ledger),
        "source_repo_count": raw_repo_count,
        "deduped_repo_count": len(repos),
        "target_table": "knowledge_repo_roots",
    }
    if not confirm:
        return {
            **result,
            "status": "operator_confirmation_required",
            "operator_command": (
                f"python3 scripts/ingest_system_catalog_to_ledger.py "
                f"--catalog {catalog} --ledger {ledger} --confirm"
            ),
        }
    ledger.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ledger)
    try:
        _init_table(conn)
        conn.executemany(
            """
            INSERT INTO knowledge_repo_roots (
                repo_key, repo_name, repo_path, remote_url, branch, head_commit,
                worktree_count, catalog_source
            ) VALUES (
                :repo_key, :repo_name, :repo_path, :remote_url, :branch, :head_commit,
                :worktree_count, :catalog_source
            )
            ON CONFLICT(repo_key) DO UPDATE SET
                repo_name=excluded.repo_name,
                repo_path=excluded.repo_path,
                remote_url=excluded.remote_url,
                branch=excluded.branch,
                head_commit=excluded.head_commit,
                worktree_count=excluded.worktree_count,
                catalog_source=excluded.catalog_source,
                ingested_at=CURRENT_TIMESTAMP
            """,
            repos,
        )
        conn.commit()
    finally:
        conn.close()
    return {**result, "status": "written", "rows_written": len(repos)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default="system_catalog.sqlite3")
    parser.add_argument("--ledger", default=".openclaw/business_ops/ledger.sqlite")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            ingest_system_catalog_to_ledger(args.catalog, args.ledger, confirm=args.confirm),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
