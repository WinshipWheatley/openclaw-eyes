"""Mac Markdown root inventory for storage-intelligence mapping.

This module counts allowed Markdown files under configured Mac roots using path
and stat metadata only. It excludes sensitive path classes before recording
paths and never reads Markdown bodies.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from md_corpus_ingest import (
    DEFAULT_DB_PATH,
    NO_AUTHORITY_FLAGS as CORPUS_NO_AUTHORITY_FLAGS,
    SKIP_DIR_NAMES,
    sensitive_path_reason,
    stable_json,
)


MD_ROOT_INVENTORY_VERSION = "md_root_inventory_v0"
DEFAULT_SAMPLE_LIMIT = 25
SENSITIVE_REDACTION = "[sensitive-path-redacted]"

NO_AUTHORITY_FLAGS = {
    **CORPUS_NO_AUTHORITY_FLAGS,
    "markdown_body_read_allowed": False,
    "source_markdown_writeback_allowed": False,
    "truth_claimed": False,
    "advisory_only": True,
}


@dataclass(frozen=True)
class MarkdownRootInventoryResult:
    run_id: str
    db_path: str
    root_count: int
    existing_root_count: int
    allowed_markdown_count: int
    excluded_path_count: int
    roots: list[dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _path_hash(path: str) -> str:
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:20]


def _mtime_iso(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat()
    except OSError:
        return None


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def _exclusion_record(root: Path, path: Path, reason: str) -> dict[str, str]:
    relative = _display_path(root, path)
    sensitive = reason != "tool_or_cache_directory_skipped"
    return {
        "path": SENSITIVE_REDACTION if sensitive else relative,
        "path_hash": _path_hash(relative),
        "reason": reason,
        "sensitive_path_redacted": str(sensitive).lower(),
    }


def _root_inventory(root: Path, sample_limit: int) -> dict[str, Any]:
    root_path = root.expanduser()
    exists = root_path.exists()
    if not exists:
        return {
            "root_path": root_path.as_posix(),
            "exists": False,
            "scanned": False,
            "allowed_markdown_count": 0,
            "excluded_path_count": 0,
            "sample_paths": [],
            "latest_mtime_iso": None,
            "exclusions": [],
        }

    allowed_paths: list[str] = []
    exclusions: list[dict[str, str]] = []
    latest_mtime: str | None = None
    for dirpath, dirnames, filenames in os.walk(root_path):
        current = Path(dirpath)
        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            candidate = current / dirname
            relative = Path(_display_path(root_path, candidate))
            reason = sensitive_path_reason(relative)
            if dirname in SKIP_DIR_NAMES:
                exclusions.append(_exclusion_record(root_path, candidate, "tool_or_cache_directory_skipped"))
                continue
            if reason:
                exclusions.append(_exclusion_record(root_path, candidate, reason))
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        for filename in sorted(filenames):
            if not filename.lower().endswith(".md"):
                continue
            path = current / filename
            relative = Path(_display_path(root_path, path))
            reason = sensitive_path_reason(relative)
            if reason:
                exclusions.append(_exclusion_record(root_path, path, reason))
                continue
            display = relative.as_posix()
            allowed_paths.append(display)
            mtime = _mtime_iso(path)
            if mtime and (latest_mtime is None or mtime > latest_mtime):
                latest_mtime = mtime

    return {
        "root_path": root_path.as_posix(),
        "exists": True,
        "scanned": True,
        "allowed_markdown_count": len(allowed_paths),
        "excluded_path_count": len(exclusions),
        "sample_paths": sorted(allowed_paths)[:sample_limit],
        "latest_mtime_iso": latest_mtime,
        "exclusions": exclusions[:sample_limit],
    }


def init_md_root_inventory_schema(db_path: str | Path) -> str:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
CREATE TABLE IF NOT EXISTS md_root_inventory_runs (
  run_id TEXT PRIMARY KEY,
  inventory_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  root_count INTEGER NOT NULL DEFAULT 0,
  existing_root_count INTEGER NOT NULL DEFAULT 0,
  allowed_markdown_count INTEGER NOT NULL DEFAULT 0,
  excluded_path_count INTEGER NOT NULL DEFAULT 0,
  markdown_body_read_allowed INTEGER NOT NULL DEFAULT 0,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  source_markdown_writeback_allowed INTEGER NOT NULL DEFAULT 0,
  truth_claimed INTEGER NOT NULL DEFAULT 0,
  advisory_only INTEGER NOT NULL DEFAULT 1
)
""".strip()
        )
        conn.execute(
            """
CREATE TABLE IF NOT EXISTS md_root_inventory_roots (
  root_inventory_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  root_path TEXT NOT NULL,
  exists_flag INTEGER NOT NULL DEFAULT 0,
  scanned_flag INTEGER NOT NULL DEFAULT 0,
  allowed_markdown_count INTEGER NOT NULL DEFAULT 0,
  excluded_path_count INTEGER NOT NULL DEFAULT 0,
  sample_paths_json TEXT NOT NULL,
  latest_mtime_iso TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES md_root_inventory_runs(run_id) ON DELETE CASCADE,
  UNIQUE(run_id, root_path)
)
""".strip()
        )
        conn.execute(
            """
CREATE TABLE IF NOT EXISTS md_root_inventory_exclusions (
  exclusion_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  root_path TEXT NOT NULL,
  path TEXT NOT NULL,
  path_hash TEXT NOT NULL,
  reason TEXT NOT NULL,
  sensitive_path_redacted INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES md_root_inventory_runs(run_id) ON DELETE CASCADE
)
""".strip()
        )
    return Path(db_path).as_posix()


def md_root_inventory_table_names(db_path: str | Path) -> tuple[str, ...]:
    init_md_root_inventory_schema(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'md_root_inventory_%'
ORDER BY name
""".strip()
        ).fetchall()
    return tuple(row[0] for row in rows)


def build_root_inventory(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    roots: Iterable[str | Path],
    run_id: str | None = None,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT,
) -> MarkdownRootInventoryResult:
    db = Path(db_path)
    active_run_id = run_id or _row_id("md_root_inventory", utc_now(), ",".join(str(root) for root in roots))
    root_list = [Path(root) for root in roots]
    created_at = utc_now()
    init_md_root_inventory_schema(db)
    inventories = [_root_inventory(root, sample_limit) for root in root_list]
    root_count = len(inventories)
    existing_root_count = sum(1 for item in inventories if item["exists"])
    allowed_markdown_count = sum(int(item["allowed_markdown_count"]) for item in inventories)
    excluded_path_count = sum(int(item["excluded_path_count"]) for item in inventories)

    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM md_root_inventory_exclusions WHERE run_id = ?", (active_run_id,))
        conn.execute("DELETE FROM md_root_inventory_roots WHERE run_id = ?", (active_run_id,))
        conn.execute("DELETE FROM md_root_inventory_runs WHERE run_id = ?", (active_run_id,))
        conn.execute(
            """
INSERT INTO md_root_inventory_runs (
  run_id, inventory_version, created_at, root_count, existing_root_count,
  allowed_markdown_count, excluded_path_count, markdown_body_read_allowed,
  model_call_allowed, network_authority, file_move_allowed, file_delete_allowed,
  source_markdown_writeback_allowed, truth_claimed, advisory_only
) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 1)
""".strip(),
            (
                active_run_id,
                MD_ROOT_INVENTORY_VERSION,
                created_at,
                root_count,
                existing_root_count,
                allowed_markdown_count,
                excluded_path_count,
            ),
        )
        for item in inventories:
            conn.execute(
                """
INSERT INTO md_root_inventory_roots (
  root_inventory_id, run_id, root_path, exists_flag, scanned_flag,
  allowed_markdown_count, excluded_path_count, sample_paths_json,
  latest_mtime_iso, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
                (
                    _row_id("md_root", active_run_id, item["root_path"]),
                    active_run_id,
                    item["root_path"],
                    1 if item["exists"] else 0,
                    1 if item["scanned"] else 0,
                    item["allowed_markdown_count"],
                    item["excluded_path_count"],
                    stable_json(item["sample_paths"]),
                    item["latest_mtime_iso"],
                    created_at,
                ),
            )
            for exclusion in item["exclusions"]:
                conn.execute(
                    """
INSERT INTO md_root_inventory_exclusions (
  exclusion_id, run_id, root_path, path, path_hash, reason,
  sensitive_path_redacted, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
                    (
                        _row_id("md_root_excl", active_run_id, item["root_path"], exclusion["path_hash"]),
                        active_run_id,
                        item["root_path"],
                        exclusion["path"],
                        exclusion["path_hash"],
                        exclusion["reason"],
                        1 if exclusion["sensitive_path_redacted"] == "true" else 0,
                        created_at,
                    ),
                )

    public_roots = [{key: value for key, value in item.items() if key != "exclusions"} for item in inventories]
    return MarkdownRootInventoryResult(
        run_id=active_run_id,
        db_path=db.as_posix(),
        root_count=root_count,
        existing_root_count=existing_root_count,
        allowed_markdown_count=allowed_markdown_count,
        excluded_path_count=excluded_path_count,
        roots=public_roots,
    )


def result_as_dict(result: MarkdownRootInventoryResult) -> dict[str, Any]:
    return {
        **result.__dict__,
        "inventory_version": MD_ROOT_INVENTORY_VERSION,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
    }


def format_operator_result(result: MarkdownRootInventoryResult) -> str:
    lines = [
        "Markdown Root Inventory",
        "",
        "Evidence:",
        f"- Run ID: `{result.run_id}`.",
        f"- DB: `{result.db_path}`.",
        f"- Roots requested: `{result.root_count}`.",
        f"- Existing roots: `{result.existing_root_count}`.",
        f"- Allowed Markdown files: `{result.allowed_markdown_count}`.",
        f"- Excluded paths: `{result.excluded_path_count}`.",
        "",
        "Roots:",
    ]
    for item in result.roots:
        lines.append(
            f"- `{item['root_path']}`: exists `{str(item['exists']).lower()}`, "
            f"allowed `.md` `{item['allowed_markdown_count']}`, "
            f"excluded `{item['excluded_path_count']}`."
        )
    lines.extend(
        [
            "",
            "Authority:",
            "- Markdown body reads: `false`.",
            "- Model calls: `false`.",
            "- Network authority: `false`.",
            "- Source Markdown writeback: `false`.",
            "- Truth claimed: `false`.",
            "- Advisory only: `true`.",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory allowed Markdown files under Mac roots.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite inventory path.")
    parser.add_argument("--run-id", help="Stable inventory run id.")
    parser.add_argument("--root", action="append", required=True, help="Root path to inventory. Repeatable.")
    parser.add_argument("--sample-limit", type=int, default=DEFAULT_SAMPLE_LIMIT)
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_root_inventory(
        db_path=args.db,
        roots=args.root,
        run_id=args.run_id,
        sample_limit=args.sample_limit,
    )
    if args.format == "json":
        print(stable_json(result_as_dict(result)), end="")
    else:
        print(format_operator_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
