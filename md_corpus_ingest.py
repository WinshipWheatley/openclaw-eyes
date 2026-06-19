"""Mac-safe Markdown corpus ingest to SQLite.

This module indexes allowed Markdown files into a deterministic SQLite corpus
for local Mac knowledge work. It prunes Legal/Finance/MusicLaw-sensitive paths
before reading file bodies. It does not move/delete files, call networks, run
models, or promote Markdown prose into truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
MD_CORPUS_VERSION = "mac_md_corpus_ingest_v0"
DEFAULT_DB_PATH = Path("generated/system_knowledge/mac_md_corpus.sqlite")

SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".DS_Store",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "node_modules",
}

SENSITIVE_PATH_HINTS = {
    "legal",
    "legal_discovery",
    "legal-discovery",
    "legal discovery",
    "finance",
    "financial",
    "tax",
    "cpa",
    "musiclaw",
    "music_law",
    "music-law",
    "music law",
}

STATUS_PATTERN = re.compile(r"\b(TODO|DONE|BLOCKED|READY|CLAIMED|CLAIM|FIXME|HACK)\b")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TASK_PATTERN = re.compile(r"^\s*[-*]\s+\[([ xX-])\]\s+(.+?)\s*$")
WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "tool_execution_allowed": False,
    "network_authority": False,
    "model_call_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "legal_discovery_access_allowed": False,
    "finance_corpus_access_allowed": False,
    "musiclaw_corpus_access_allowed": False,
    "truth_promotion_allowed": False,
}


@dataclass(frozen=True)
class MarkdownCorpusIngestResult:
    run_id: str
    db_path: str
    root_path: str
    machine: str
    scanned_markdown_files: int
    ingested_document_count: int
    excluded_path_count: int
    legal_sensitive_exclusion_enforced: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _normalize_part(part: str) -> str:
    return part.strip().lower().replace(" ", "_").replace("-", "_")


def sensitive_path_reason(path: Path) -> str | None:
    normalized_parts = {_normalize_part(part) for part in path.parts}
    if {"legal", "legal_discovery"} & normalized_parts:
        return "legal_discovery_or_legal_path_excluded"
    if {"finance", "financial", "tax", "cpa"} & normalized_parts:
        return "finance_or_tax_path_excluded"
    if {"musiclaw", "music_law"} & normalized_parts:
        return "musiclaw_path_excluded"
    joined = "/".join(normalized_parts)
    for hint in SENSITIVE_PATH_HINTS:
        normalized_hint = _normalize_part(hint)
        if normalized_hint in joined:
            if "music" in normalized_hint:
                return "musiclaw_path_excluded"
            if "financ" in normalized_hint or normalized_hint in {"tax", "cpa"}:
                return "finance_or_tax_path_excluded"
            return "legal_discovery_or_legal_path_excluded"
    return None


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def _iter_markdown_files(root: Path) -> tuple[list[Path], list[tuple[str, str]]]:
    markdown_files: list[Path] = []
    exclusions: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            candidate = current / dirname
            relative = Path(_display_path(root, candidate))
            reason = sensitive_path_reason(relative)
            if dirname in SKIP_DIR_NAMES:
                exclusions.append((relative.as_posix(), "tool_or_cache_directory_skipped"))
                continue
            if reason:
                exclusions.append((relative.as_posix(), reason))
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        for filename in sorted(filenames):
            if not filename.lower().endswith(".md"):
                continue
            path = current / filename
            relative = Path(_display_path(root, path))
            reason = sensitive_path_reason(relative)
            if reason:
                exclusions.append((relative.as_posix(), reason))
                continue
            markdown_files.append(path)
    return markdown_files, exclusions


def _extract_title(lines: list[str], fallback: str) -> str:
    for line in lines:
        match = HEADING_PATTERN.match(line)
        if match and len(match.group(1)) == 1:
            return match.group(2).strip()
    return Path(fallback).stem


def _extract_sections(lines: list[str]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        match = HEADING_PATTERN.match(line)
        if match:
            sections.append(
                {
                    "line": index,
                    "level": len(match.group(1)),
                    "heading": match.group(2).strip(),
                }
            )
    return sections


def _extract_links(text: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for target in WIKI_LINK_PATTERN.findall(text):
        links.append({"kind": "wiki", "target": target.strip(), "label": target.strip()})
    for label, target in MARKDOWN_LINK_PATTERN.findall(text):
        links.append({"kind": "markdown", "target": target.strip(), "label": label.strip()})
    return links


def _extract_status_markers(lines: list[str]) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        for match in STATUS_PATTERN.finditer(line):
            markers.append({"line": index, "marker": match.group(1), "text": line.strip()})
    return markers


def _extract_tasks(lines: list[str]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        match = TASK_PATTERN.match(line)
        if not match:
            continue
        state = match.group(1)
        tasks.append(
            {
                "line": index,
                "checked": state in {"x", "X"},
                "state": state,
                "text": match.group(2).strip(),
            }
        )
    return tasks


def _git_last_commit(repo_root: Path, path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "log", "-1", "--format=%H", "--", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS md_corpus_runs (
  run_id TEXT PRIMARY KEY,
  corpus_version TEXT NOT NULL,
  machine TEXT NOT NULL,
  root_path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  scanned_markdown_files INTEGER NOT NULL DEFAULT 0,
  ingested_document_count INTEGER NOT NULL DEFAULT 0,
  excluded_path_count INTEGER NOT NULL DEFAULT 0,
  legal_sensitive_exclusion_enforced INTEGER NOT NULL DEFAULT 1,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  truth_promotion_allowed INTEGER NOT NULL DEFAULT 0
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS md_corpus_documents (
  document_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  machine TEXT NOT NULL,
  absolute_path TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  title TEXT NOT NULL,
  sections_json TEXT NOT NULL,
  text TEXT NOT NULL,
  byte_count INTEGER NOT NULL,
  line_count INTEGER NOT NULL,
  mtime_epoch REAL NOT NULL,
  mtime_iso TEXT NOT NULL,
  git_last_commit TEXT,
  links_json TEXT NOT NULL,
  status_markers_json TEXT NOT NULL,
  tasks_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES md_corpus_runs(run_id) ON DELETE CASCADE,
  UNIQUE(run_id, relative_path)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS md_corpus_exclusions (
  exclusion_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  reason TEXT NOT NULL,
  body_read INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES md_corpus_runs(run_id) ON DELETE CASCADE,
  UNIQUE(run_id, relative_path, reason)
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_md_corpus_documents_run ON md_corpus_documents(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_md_corpus_documents_path ON md_corpus_documents(relative_path)",
        "CREATE INDEX IF NOT EXISTS idx_md_corpus_exclusions_run ON md_corpus_exclusions(run_id)",
    )


def init_md_corpus_schema(db_path: str | Path) -> str:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        for statement in _sql_statements():
            conn.execute(statement)
    return path.as_posix()


def md_corpus_table_names(db_path: str | Path) -> tuple[str, ...]:
    init_md_corpus_schema(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'md_corpus_%'
ORDER BY name
""".strip()
        ).fetchall()
    return tuple(row[0] for row in rows)


def _insert_exclusions(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    exclusions: Iterable[tuple[str, str]],
    created_at: str,
) -> int:
    count = 0
    for relative_path, reason in exclusions:
        conn.execute(
            """
INSERT OR REPLACE INTO md_corpus_exclusions (
  exclusion_id, run_id, relative_path, reason, body_read, created_at
) VALUES (?, ?, ?, ?, 0, ?)
""".strip(),
            (_row_id("md_excl", run_id, relative_path, reason), run_id, relative_path, reason, created_at),
        )
        count += 1
    return count


def ingest_mac_markdown_corpus(
    *,
    root: str | Path,
    db_path: str | Path = DEFAULT_DB_PATH,
    run_id: str | None = None,
    machine: str | None = None,
) -> MarkdownCorpusIngestResult:
    root_path = Path(root).expanduser().resolve()
    db = Path(db_path)
    active_run_id = run_id or f"mac_md_corpus_{utc_now().replace(':', '').replace('+', 'Z')}"
    machine_name = machine or platform.node() or "mac"
    created_at = utc_now()
    init_md_corpus_schema(db)
    markdown_files, exclusions = _iter_markdown_files(root_path)

    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM md_corpus_documents WHERE run_id = ?", (active_run_id,))
        conn.execute("DELETE FROM md_corpus_exclusions WHERE run_id = ?", (active_run_id,))
        conn.execute("DELETE FROM md_corpus_runs WHERE run_id = ?", (active_run_id,))
        conn.execute(
            """
INSERT INTO md_corpus_runs (
  run_id, corpus_version, machine, root_path, created_at, scanned_markdown_files,
  ingested_document_count, excluded_path_count, legal_sensitive_exclusion_enforced,
  runtime_authority, tool_execution_allowed, network_authority, model_call_allowed,
  file_move_allowed, file_delete_allowed, truth_promotion_allowed
) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0)
""".strip(),
            (active_run_id, MD_CORPUS_VERSION, machine_name, root_path.as_posix(), created_at, len(markdown_files)),
        )
        excluded_count = _insert_exclusions(conn, run_id=active_run_id, exclusions=exclusions, created_at=created_at)
        ingested = 0
        for path in markdown_files:
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            relative_path = _display_path(root_path, path)
            stat = path.stat()
            mtime_iso = datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat()
            conn.execute(
                """
INSERT OR REPLACE INTO md_corpus_documents (
  document_id, run_id, machine, absolute_path, relative_path, title,
  sections_json, text, byte_count, line_count, mtime_epoch, mtime_iso,
  git_last_commit, links_json, status_markers_json, tasks_json, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
                (
                    _row_id("md_doc", active_run_id, relative_path),
                    active_run_id,
                    machine_name,
                    path.as_posix(),
                    relative_path,
                    _extract_title(lines, relative_path),
                    stable_json(_extract_sections(lines)),
                    text,
                    len(text.encode("utf-8")),
                    len(lines),
                    stat.st_mtime,
                    mtime_iso,
                    _git_last_commit(root_path, path),
                    stable_json(_extract_links(text)),
                    stable_json(_extract_status_markers(lines)),
                    stable_json(_extract_tasks(lines)),
                    created_at,
                ),
            )
            ingested += 1
        completed_at = utc_now()
        conn.execute(
            """
UPDATE md_corpus_runs
SET completed_at = ?,
    ingested_document_count = ?,
    excluded_path_count = ?
WHERE run_id = ?
""".strip(),
            (completed_at, ingested, excluded_count, active_run_id),
        )

    return MarkdownCorpusIngestResult(
        run_id=active_run_id,
        db_path=db.as_posix(),
        root_path=root_path.as_posix(),
        machine=machine_name,
        scanned_markdown_files=len(markdown_files),
        ingested_document_count=ingested,
        excluded_path_count=excluded_count,
        legal_sensitive_exclusion_enforced=True,
    )


def result_as_dict(result: MarkdownCorpusIngestResult) -> dict[str, Any]:
    return {
        **result.__dict__,
        "corpus_version": MD_CORPUS_VERSION,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
    }


def format_operator_result(result: MarkdownCorpusIngestResult) -> str:
    return "\n".join(
        [
            "Mac Markdown Corpus Ingest",
            "",
            "Evidence:",
            f"- Run ID: `{result.run_id}`.",
            f"- DB: `{result.db_path}`.",
            f"- Root: `{result.root_path}`.",
            f"- Machine: `{result.machine}`.",
            f"- Markdown files scanned: `{result.scanned_markdown_files}`.",
            f"- Documents ingested: `{result.ingested_document_count}`.",
            f"- Paths excluded before body read: `{result.excluded_path_count}`.",
            "- Legal/Finance/MusicLaw exclusion enforced: `true`.",
            "- Runtime/tool/model/network authority: `false`.",
            "- File move/delete authority: `false`.",
            "- Truth promotion: `false`.",
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Mac Markdown corpus metadata/text into SQLite.")
    parser.add_argument("--root", default=str(ROOT), help="Root directory to scan for allowed Markdown.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite output path.")
    parser.add_argument("--run-id", help="Stable run id for deterministic test or receipt runs.")
    parser.add_argument("--machine", help="Machine label to store in SQLite.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = ingest_mac_markdown_corpus(
        root=args.root,
        db_path=args.db,
        run_id=args.run_id,
        machine=args.machine,
    )
    if args.format == "json":
        print(stable_json(result_as_dict(result)), end="")
    else:
        print(format_operator_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
