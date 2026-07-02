"""Incremental crawl state for the perpetual self-knowledge engine.

Tracks a per-directory change signature (name+mtime+size of each direct
child file) in a small persistent SQLite state store, so a repeated crawl
over an unchanged subtree skips re-hashing file content. Only directories
whose signature changed since the last recorded crawl are re-visited for
crumb generation; everything else is skipped entirely.

This reuses the exclusion rules and crumb shape from the read-only seed
(`self_knowledge_crawler.py`) without modifying it.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from self_knowledge_crawler import _is_excluded, _sha256

DEFAULT_STATE_DB = Path("/home/openclaw/.openclaw/self_knowledge/crawl_state.sqlite")


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class CrawlStateStore:
    """Persistent per-directory crawl signature store."""

    def __init__(self, db_path: str | Path = DEFAULT_STATE_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crawl_directory_state (
                    directory_path TEXT PRIMARY KEY,
                    signature TEXT NOT NULL,
                    last_crawled_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def get_signature(self, directory_path: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT signature FROM crawl_directory_state WHERE directory_path = ?",
                (directory_path,),
            ).fetchone()
        return str(row[0]) if row is not None else None

    def record(self, directory_path: str, signature: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO crawl_directory_state (directory_path, signature, last_crawled_at)
                VALUES (?, ?, ?)
                ON CONFLICT(directory_path) DO UPDATE SET
                    signature = excluded.signature,
                    last_crawled_at = excluded.last_crawled_at
                """,
                (directory_path, str(signature), _utc_now_iso()),
            )
            conn.commit()


def _directory_signature(dirpath: Path, visible_filenames: list[str]) -> str:
    """Deterministic signature over the DIRECT child files of this directory
    only (name + mtime + size). Deliberately excludes the directory's own
    mtime and any subdirectories, so adding/removing a *subdirectory* does not
    force re-hashing of files that did not themselves change — a new
    subdirectory gets its own (unseen -> changed) state on its own visit.
    Catches file add (new name appears), remove (name disappears), and
    in-place touch/content change (mtime differs) within this directory.
    """
    parts: list[str] = []
    for name in visible_filenames:
        try:
            stat = (dirpath / name).stat()
        except OSError:
            continue
        parts.append(f"{name}:{stat.st_mtime}:{stat.st_size}")
    return "|".join(parts)


def crawl_filesystem_incremental(
    root: str | Path,
    state_db_path: str | Path = DEFAULT_STATE_DB,
    *,
    max_files: int | None = None,
) -> list[dict[str, Any]]:
    """Like `crawl_filesystem`, but skips directories unchanged since the last
    recorded crawl. The walk itself is always cheap (stat-only); the expensive
    part (sha256 content hashing) only runs for directories whose signature
    changed, and only those directories' state is updated.
    """
    root_path = Path(root).resolve()
    store = CrawlStateStore(state_db_path)
    crumbs: list[dict[str, Any]] = []
    if not root_path.exists():
        return crumbs

    for dirpath, dirnames, filenames in os.walk(root_path):
        current_dir = Path(dirpath)
        dirnames[:] = [
            name
            for name in sorted(dirnames)
            if not _is_excluded(current_dir / name, root_path)
        ]
        visible_files = [
            name
            for name in sorted(filenames)
            if not _is_excluded(current_dir / name, root_path)
            and (current_dir / name).is_file()
        ]

        signature = _directory_signature(current_dir, visible_files)
        previous = store.get_signature(str(current_dir))
        if previous is not None and previous == signature:
            continue  # unchanged subtree: nothing to re-hash here

        for name in visible_files:
            path = current_dir / name
            try:
                stat = path.stat()
                rel = path.relative_to(root_path).as_posix()
                crumbs.append(
                    {
                        "kind": "file",
                        "path": str(path),
                        "relative_path": rel,
                        "size_bytes": stat.st_size,
                        "sha256": _sha256(path),
                    }
                )
            except OSError:
                continue
            if max_files is not None and len(crumbs) >= max(0, int(max_files)):
                store.record(str(current_dir), signature)
                return crumbs

        store.record(str(current_dir), signature)

    return crumbs


__all__ = ["CrawlStateStore", "crawl_filesystem_incremental", "DEFAULT_STATE_DB"]
