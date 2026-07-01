"""Ground-truth crumb crawler seed for the perpetual self-knowledge engine.

This is the first, safe primitive: deterministic filesystem enumeration and a
read-only diff against a SQLite ledger. It does not write production state and
does not start a daemon.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable


EXCLUDED_NAMES = {
    ".git",
    ".openclaw",
    ".chief.env",
    ".google-secrets",
    "LegalPrivate",
    "FinancePrivate",
    "MusicLawPrivate",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "chief_env",
    ".venv",
    "node_modules",
}
EXCLUDED_PARTS = {
    "generated",
    "worktrees",
    "sidecars",
}
EXCLUDED_PREFIXES = (
    ".chief.env",
    ".claude",
    ".google",
)
LEDGER_PATH_COLUMNS = {
    "path",
    "file_path",
    "absolute_path",
    "repo_path",
    "source_path",
    "canonical_path",
}
DEFAULT_LEDGER_INVENTORY_TABLES = (
    "file_inventory",
    "corpus_paths",
    "knowledge_fsatlas_directory_inventory",
    "knowledge_fsatlas_repo_inventory",
    "knowledge_repo_roots",
)


def _is_excluded(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    parts = set(rel.parts)
    if path.name in EXCLUDED_NAMES:
        return True
    if any(path.name.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return True
    if parts & EXCLUDED_NAMES:
        return True
    if parts & EXCLUDED_PARTS:
        return True
    return False


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def crawl_filesystem(root: str | Path, *, max_files: int | None = None) -> list[dict[str, Any]]:
    """Enumerate real on-disk files under root with cheap deterministic metadata."""
    root_path = Path(root).resolve()
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
        for name in sorted(filenames):
            path = current_dir / name
            if _is_excluded(path, root_path) or not path.is_file():
                continue
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
                return crumbs
    return crumbs


def _ledger_tables(conn: sqlite3.Connection) -> Iterable[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    for (name,) in rows:
        yield str(name)


def _ledger_path_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [
        str(row[1])
        for row in columns
        if str(row[1]).lower() in LEDGER_PATH_COLUMNS
    ]


def ledger_known_paths(
    ledger_path: str | Path,
    *,
    tables: Iterable[str] = DEFAULT_LEDGER_INVENTORY_TABLES,
) -> set[str]:
    """Read known paths from conventional path columns in a SQLite ledger."""
    path = Path(ledger_path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    known: set[str] = set()
    with sqlite3.connect(path) as conn:
        existing = set(_ledger_tables(conn))
        for table in tables:
            if table not in existing:
                continue
            for column in _ledger_path_columns(conn, table):
                try:
                    rows = conn.execute(f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL").fetchall()
                except sqlite3.Error:
                    continue
                for (value,) in rows:
                    text = str(value or "").strip()
                    if text:
                        known.add(text)
    return known


def diff_filesystem_against_ledger(
    root: str | Path,
    ledger_path: str | Path,
    *,
    max_files: int | None = None,
    ledger_tables: Iterable[str] = DEFAULT_LEDGER_INVENTORY_TABLES,
) -> dict[str, Any]:
    """Return filesystem crumbs absent from the ledger's known path inventory."""
    crumbs = crawl_filesystem(root, max_files=max_files)
    try:
        known = ledger_known_paths(ledger_path, tables=ledger_tables)
        status = "ok"
    except FileNotFoundError:
        known = set()
        status = "ledger_unavailable"
    unknown = [
        crumb
        for crumb in crumbs
        if crumb["path"] not in known and crumb["relative_path"] not in known
    ]
    if unknown and status == "ok":
        status = "gaps_found"
    return {
        "status": status,
        "counts": {
            "filesystem_files": len(crumbs),
            "ledger_known_paths": len(known),
            "unknown_files": len(unknown),
        },
        "unknown_files": unknown,
    }


__all__ = ["crawl_filesystem", "ledger_known_paths", "diff_filesystem_against_ledger"]
