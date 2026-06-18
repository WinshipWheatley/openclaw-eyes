"""Markdown corpus ingestion for OpenClaw system knowledge.

The ingester walks allowed PC Markdown files and writes a deterministic SQLite
read substrate. It does not delete, move, send, deploy, call models, or follow
symlinks. Sensitive Legal/Finance/MusicLaw and credential/private boundaries are
pruned before descent and never body-read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
DEFAULT_ROOT = Path("/home/openclaw")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/md_corpus.sqlite")
DEFAULT_MACHINE = "pc_wsl"
SCHEMA_VERSION = "md_corpus_ingest_v0"

PRUNE_DIR_NAMES = {
    ".aider.tags.cache.v4",
    ".cache",
    ".git",
    ".google-secrets",
    ".gnupg",
    ".local",
    ".mypy_cache",
    ".private",
    ".pytest_cache",
    ".ruff_cache",
    ".ssh",
    ".venv",
    ".vscode-server",
    "__pycache__",
    "chief_env",
    "node_modules",
    "venv",
}

NO_GO_COMPONENT_HINTS = {
    ".env",
    "credential",
    "credentials",
    "cpa",
    "finance",
    "financial",
    "legal",
    "legal discovery",
    "legal-discovery",
    "legal_discovery",
    "musiclaw",
    "music-law",
    "private",
    "secret",
    "secrets",
    "tax",
    "token",
    "vault",
    "vaults",
}

NO_GO_FILE_HINTS = {
    ".env",
    "aider.chat.history",
    "aider.input.history",
    "bash_history",
    "credential",
    "credentials",
    "pii_vault",
    "python_history",
    "secret",
    "token",
}

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
TASK_RE = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s+(.*)$")
WIKILINK_RE = re.compile(r"\[\[([^\]\n]+?)\]\]")
STATUS_RE = re.compile(
    r"\b(ARCHIVE[_ -]?CANDIDATE|BLOCKED|CURRENT|DEPRECATED|DONE|DRAFT|FIXME|STALE|SUPERSEDED|TODO|ACTIVE)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Section:
    level: int
    heading: str
    heading_path: tuple[str, ...]
    start_line: int
    end_line: int
    text: str


@dataclass(frozen=True)
class MarkdownCorpusIngestResult:
    run_id: str
    sqlite_path: str
    root_path: str
    machine: str
    document_count: int
    excluded_count: int
    section_count: int
    wikilink_count: int
    task_count: int
    status_marker_count: int
    git_head: str | None
    git_branch: str | None


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rooted(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _hash_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:24]}"


def _safe_rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat()


def _connect(sqlite_path: str | Path = DEFAULT_SQLITE_PATH) -> sqlite3.Connection:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS md_corpus_runs (
          run_id TEXT PRIMARY KEY,
          schema_version TEXT NOT NULL,
          machine TEXT NOT NULL,
          root_path TEXT NOT NULL,
          started_at TEXT NOT NULL,
          completed_at TEXT,
          document_count INTEGER NOT NULL DEFAULT 0,
          excluded_count INTEGER NOT NULL DEFAULT 0,
          section_count INTEGER NOT NULL DEFAULT 0,
          wikilink_count INTEGER NOT NULL DEFAULT 0,
          task_count INTEGER NOT NULL DEFAULT 0,
          status_marker_count INTEGER NOT NULL DEFAULT 0,
          git_head TEXT,
          git_branch TEXT,
          no_external_actions INTEGER NOT NULL DEFAULT 1,
          no_destructive_actions INTEGER NOT NULL DEFAULT 1,
          notes TEXT
        );

        CREATE TABLE IF NOT EXISTS md_documents (
          document_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          machine TEXT NOT NULL,
          absolute_path TEXT NOT NULL,
          relative_path TEXT NOT NULL,
          path_name TEXT NOT NULL,
          title TEXT NOT NULL,
          text TEXT NOT NULL,
          size_bytes INTEGER NOT NULL,
          mtime TEXT NOT NULL,
          git_tracked INTEGER NOT NULL DEFAULT 0,
          git_last_commit_hash TEXT,
          git_last_commit_iso TEXT,
          git_last_commit_subject TEXT,
          section_count INTEGER NOT NULL DEFAULT 0,
          wikilink_count INTEGER NOT NULL DEFAULT 0,
          task_count INTEGER NOT NULL DEFAULT 0,
          status_marker_count INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          FOREIGN KEY (run_id) REFERENCES md_corpus_runs(run_id) ON DELETE CASCADE,
          UNIQUE(run_id, machine, relative_path)
        );

        CREATE TABLE IF NOT EXISTS md_sections (
          section_id TEXT PRIMARY KEY,
          document_id TEXT NOT NULL,
          level INTEGER NOT NULL,
          heading TEXT NOT NULL,
          heading_path_json TEXT NOT NULL,
          start_line INTEGER NOT NULL,
          end_line INTEGER NOT NULL,
          text TEXT NOT NULL,
          FOREIGN KEY (document_id) REFERENCES md_documents(document_id) ON DELETE CASCADE,
          UNIQUE(document_id, start_line, heading)
        );

        CREATE TABLE IF NOT EXISTS md_wikilinks (
          link_id TEXT PRIMARY KEY,
          document_id TEXT NOT NULL,
          line_number INTEGER NOT NULL,
          original TEXT NOT NULL,
          target TEXT NOT NULL,
          FOREIGN KEY (document_id) REFERENCES md_documents(document_id) ON DELETE CASCADE,
          UNIQUE(document_id, line_number, original, target)
        );

        CREATE TABLE IF NOT EXISTS md_tasks (
          task_id TEXT PRIMARY KEY,
          document_id TEXT NOT NULL,
          line_number INTEGER NOT NULL,
          checked INTEGER NOT NULL,
          marker TEXT NOT NULL,
          text TEXT NOT NULL,
          FOREIGN KEY (document_id) REFERENCES md_documents(document_id) ON DELETE CASCADE,
          UNIQUE(document_id, line_number, marker, text)
        );

        CREATE TABLE IF NOT EXISTS md_status_markers (
          marker_id TEXT PRIMARY KEY,
          document_id TEXT NOT NULL,
          line_number INTEGER NOT NULL,
          marker TEXT NOT NULL,
          text TEXT NOT NULL,
          FOREIGN KEY (document_id) REFERENCES md_documents(document_id) ON DELETE CASCADE,
          UNIQUE(document_id, line_number, marker, text)
        );

        CREATE TABLE IF NOT EXISTS md_corpus_exclusions (
          exclusion_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          machine TEXT NOT NULL,
          absolute_path TEXT NOT NULL,
          relative_path TEXT NOT NULL,
          path_type TEXT NOT NULL,
          reason TEXT NOT NULL,
          body_read INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          FOREIGN KEY (run_id) REFERENCES md_corpus_runs(run_id) ON DELETE CASCADE,
          UNIQUE(run_id, machine, relative_path, reason)
        );

        CREATE INDEX IF NOT EXISTS idx_md_documents_run ON md_documents(run_id);
        CREATE INDEX IF NOT EXISTS idx_md_documents_path ON md_documents(relative_path);
        CREATE INDEX IF NOT EXISTS idx_md_sections_doc ON md_sections(document_id);
        CREATE INDEX IF NOT EXISTS idx_md_wikilinks_target ON md_wikilinks(target);
        CREATE INDEX IF NOT EXISTS idx_md_tasks_doc ON md_tasks(document_id);
        CREATE INDEX IF NOT EXISTS idx_md_status_marker ON md_status_markers(marker);
        CREATE INDEX IF NOT EXISTS idx_md_exclusions_run ON md_corpus_exclusions(run_id);
        """
    )


def table_names(sqlite_path: str | Path = DEFAULT_SQLITE_PATH) -> tuple[str, ...]:
    with _connect(sqlite_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'md_%' ORDER BY name"
        ).fetchall()
    return tuple(row["name"] for row in rows)


def exclusion_reason(path: Path, *, root: Path, path_type: str) -> str | None:
    relative = _safe_rel(path, root)
    parts = [part.lower() for part in Path(relative).parts]
    name = path.name.lower()
    if path_type == "directory" and name in PRUNE_DIR_NAMES:
        return f"pruned_directory:{name}"
    for part in parts:
        if part in PRUNE_DIR_NAMES:
            return f"pruned_directory:{part}"
        for hint in NO_GO_COMPONENT_HINTS:
            if hint in part:
                return f"no_go_component:{hint}"
    if path_type == "file":
        for hint in NO_GO_FILE_HINTS:
            if hint in name:
                return f"no_go_file_hint:{hint}"
        if path.is_symlink():
            return "symlink_file_not_followed"
    return None


def iter_markdown_paths(root: str | Path = DEFAULT_ROOT) -> tuple[list[Path], list[dict[str, str]]]:
    root_path = Path(root).expanduser().resolve()
    markdown_paths: list[Path] = []
    exclusions: list[dict[str, str]] = []

    for current, dirs, files in os.walk(root_path, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for dirname in sorted(dirs):
            child = current_path / dirname
            reason = exclusion_reason(child, root=root_path, path_type="directory")
            if reason:
                exclusions.append(
                    {
                        "absolute_path": child.as_posix(),
                        "relative_path": _safe_rel(child, root_path),
                        "path_type": "directory",
                        "reason": reason,
                    }
                )
            else:
                kept_dirs.append(dirname)
        dirs[:] = kept_dirs

        for filename in sorted(files):
            if not filename.lower().endswith(".md"):
                continue
            path = current_path / filename
            reason = exclusion_reason(path, root=root_path, path_type="file")
            if reason:
                exclusions.append(
                    {
                        "absolute_path": path.as_posix(),
                        "relative_path": _safe_rel(path, root_path),
                        "path_type": "file",
                        "reason": reason,
                    }
                )
                continue
            markdown_paths.append(path)

    markdown_paths.sort(key=lambda item: _safe_rel(item, root_path))
    exclusions.sort(key=lambda item: (item["relative_path"], item["reason"]))
    return markdown_paths, exclusions


def _is_fence_line(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("```") or stripped.startswith("~~~")


def _iter_content_lines(text: str) -> Iterable[tuple[int, str]]:
    in_fence = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        if _is_fence_line(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield line_number, line


def extract_title(text: str, path: Path) -> str:
    first_heading: str | None = None
    for _, line in _iter_content_lines(text):
        match = HEADING_RE.match(line)
        if not match:
            continue
        heading = match.group(2).strip()
        if first_heading is None:
            first_heading = heading
        if len(match.group(1)) == 1:
            return heading
    return first_heading or path.stem.replace("_", " ").replace("-", " ").strip() or path.name


def extract_sections(text: str) -> list[Section]:
    lines = text.splitlines()
    heading_rows: list[tuple[int, int, str, tuple[str, ...]]] = []
    stack: list[str] = []
    in_fence = False
    for line_number, line in enumerate(lines, start=1):
        if _is_fence_line(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if not match:
            continue
        level = len(match.group(1))
        heading = match.group(2).strip()
        stack = stack[: level - 1]
        stack.append(heading)
        heading_rows.append((line_number, level, heading, tuple(stack)))

    if not heading_rows:
        return [
            Section(
                level=0,
                heading="Document",
                heading_path=(),
                start_line=1,
                end_line=max(len(lines), 1),
                text=text,
            )
        ]

    sections: list[Section] = []
    for index, (line_number, level, heading, heading_path) in enumerate(heading_rows):
        end_line = heading_rows[index + 1][0] - 1 if index + 1 < len(heading_rows) else len(lines)
        section_text = "\n".join(lines[line_number - 1 : end_line])
        sections.append(
            Section(
                level=level,
                heading=heading,
                heading_path=heading_path,
                start_line=line_number,
                end_line=end_line,
                text=section_text,
            )
        )
    return sections


def extract_wikilinks(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in WIKILINK_RE.finditer(line):
            original = match.group(1).strip()
            target = original.split("|", 1)[0].split("#", 1)[0].strip()
            rows.append({"line_number": line_number, "original": original, "target": target})
    return rows


def extract_tasks(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in _iter_content_lines(text):
        match = TASK_RE.match(line)
        if match:
            marker = match.group(1)
            rows.append(
                {
                    "line_number": line_number,
                    "checked": 1 if marker.lower() == "x" else 0,
                    "marker": marker,
                    "text": match.group(2).strip(),
                }
            )
    return rows


def extract_status_markers(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in _iter_content_lines(text):
        seen_on_line: set[str] = set()
        for match in STATUS_RE.finditer(line):
            marker = re.sub(r"[\s-]+", "_", match.group(1).upper())
            if marker in seen_on_line:
                continue
            seen_on_line.add(marker)
            rows.append({"line_number": line_number, "marker": marker, "text": line.strip()})
    return rows


def _git_command(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", repo_root.as_posix(), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _discover_git_root(root: Path) -> Path | None:
    proc = _git_command(root, ["rev-parse", "--show-toplevel"])
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return Path(value).resolve() if value else None


def _git_head_and_branch(repo_root: Path | None) -> tuple[str | None, str | None]:
    if repo_root is None:
        return None, None
    head = _git_command(repo_root, ["rev-parse", "HEAD"])
    branch = _git_command(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    return (
        head.stdout.strip() if head.returncode == 0 else None,
        branch.stdout.strip() if branch.returncode == 0 else None,
    )


def _git_metadata(path: Path, repo_root: Path | None) -> dict[str, Any]:
    if repo_root is None:
        return {
            "git_tracked": 0,
            "git_last_commit_hash": None,
            "git_last_commit_iso": None,
            "git_last_commit_subject": None,
        }
    try:
        git_rel = path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return {
            "git_tracked": 0,
            "git_last_commit_hash": None,
            "git_last_commit_iso": None,
            "git_last_commit_subject": None,
        }
    tracked = _git_command(repo_root, ["ls-files", "--error-unmatch", "--", git_rel]).returncode == 0
    log = _git_command(repo_root, ["log", "-1", "--format=%H%x00%cI%x00%s", "--", git_rel])
    parts = log.stdout.rstrip("\n").split("\0", 2) if log.returncode == 0 and log.stdout.strip() else []
    return {
        "git_tracked": 1 if tracked else 0,
        "git_last_commit_hash": parts[0] if len(parts) >= 1 else None,
        "git_last_commit_iso": parts[1] if len(parts) >= 2 else None,
        "git_last_commit_subject": parts[2] if len(parts) >= 3 else None,
    }


def _delete_run(conn: sqlite3.Connection, run_id: str) -> None:
    for table in (
        "md_sections",
        "md_wikilinks",
        "md_tasks",
        "md_status_markers",
    ):
        conn.execute(
            f"""
            DELETE FROM {table}
            WHERE document_id IN (SELECT document_id FROM md_documents WHERE run_id = ?)
            """,
            (run_id,),
        )
    conn.execute("DELETE FROM md_documents WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM md_corpus_exclusions WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM md_corpus_runs WHERE run_id = ?", (run_id,))


def ingest_markdown_corpus(
    *,
    root: str | Path = DEFAULT_ROOT,
    sqlite_path: str | Path = DEFAULT_SQLITE_PATH,
    machine: str = DEFAULT_MACHINE,
    run_id: str | None = None,
) -> MarkdownCorpusIngestResult:
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Markdown corpus root does not exist: {root_path}")

    started_at = utc_now()
    run_id = run_id or _hash_id("mdrun", machine, root_path.as_posix(), started_at)
    db_path = _rooted(sqlite_path)
    git_root = _discover_git_root(root_path)
    git_head, git_branch = _git_head_and_branch(git_root)
    markdown_paths, exclusions = iter_markdown_paths(root_path)

    document_count = 0
    section_count = 0
    wikilink_count = 0
    task_count = 0
    status_marker_count = 0

    with _connect(db_path) as conn:
        _delete_run(conn, run_id)
        conn.execute(
            """
            INSERT INTO md_corpus_runs (
              run_id, schema_version, machine, root_path, started_at, git_head, git_branch, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                SCHEMA_VERSION,
                machine,
                root_path.as_posix(),
                started_at,
                git_head,
                git_branch,
                "Allowed Markdown body ingest; sensitive/off-limits paths are metadata-only exclusions.",
            ),
        )

        for exclusion in exclusions:
            conn.execute(
                """
                INSERT OR REPLACE INTO md_corpus_exclusions (
                  exclusion_id, run_id, machine, absolute_path, relative_path, path_type, reason, body_read, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    _hash_id("mdexcl", run_id, machine, exclusion["relative_path"], exclusion["reason"]),
                    run_id,
                    machine,
                    exclusion["absolute_path"],
                    exclusion["relative_path"],
                    exclusion["path_type"],
                    exclusion["reason"],
                    started_at,
                ),
            )

        for path in markdown_paths:
            relative_path = _safe_rel(path, root_path)
            text = path.read_text(encoding="utf-8", errors="replace")
            sections = extract_sections(text)
            wikilinks = extract_wikilinks(text)
            tasks = extract_tasks(text)
            status_markers = extract_status_markers(text)
            git_meta = _git_metadata(path, git_root)
            document_id = _hash_id("mddoc", run_id, machine, relative_path)

            conn.execute(
                """
                INSERT OR REPLACE INTO md_documents (
                  document_id, run_id, machine, absolute_path, relative_path, path_name, title, text,
                  size_bytes, mtime, git_tracked, git_last_commit_hash, git_last_commit_iso,
                  git_last_commit_subject, section_count, wikilink_count, task_count,
                  status_marker_count, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    run_id,
                    machine,
                    path.as_posix(),
                    relative_path,
                    path.name,
                    extract_title(text, path),
                    text,
                    path.stat().st_size,
                    _mtime_iso(path),
                    git_meta["git_tracked"],
                    git_meta["git_last_commit_hash"],
                    git_meta["git_last_commit_iso"],
                    git_meta["git_last_commit_subject"],
                    len(sections),
                    len(wikilinks),
                    len(tasks),
                    len(status_markers),
                    started_at,
                ),
            )

            for section in sections:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO md_sections (
                      section_id, document_id, level, heading, heading_path_json, start_line, end_line, text
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _hash_id("mdsec", document_id, section.start_line, section.heading),
                        document_id,
                        section.level,
                        section.heading,
                        stable_json(list(section.heading_path)).strip(),
                        section.start_line,
                        section.end_line,
                        section.text,
                    ),
                )

            for link in wikilinks:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO md_wikilinks (
                      link_id, document_id, line_number, original, target
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        _hash_id("mdlink", document_id, link["line_number"], link["original"], link["target"]),
                        document_id,
                        link["line_number"],
                        link["original"],
                        link["target"],
                    ),
                )

            for task in tasks:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO md_tasks (
                      task_id, document_id, line_number, checked, marker, text
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _hash_id("mdtask", document_id, task["line_number"], task["marker"], task["text"]),
                        document_id,
                        task["line_number"],
                        task["checked"],
                        task["marker"],
                        task["text"],
                    ),
                )

            for marker in status_markers:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO md_status_markers (
                      marker_id, document_id, line_number, marker, text
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        _hash_id("mdmark", document_id, marker["line_number"], marker["marker"], marker["text"]),
                        document_id,
                        marker["line_number"],
                        marker["marker"],
                        marker["text"],
                    ),
                )

            document_count += 1
            section_count += len(sections)
            wikilink_count += len(wikilinks)
            task_count += len(tasks)
            status_marker_count += len(status_markers)

        completed_at = utc_now()
        conn.execute(
            """
            UPDATE md_corpus_runs
            SET completed_at = ?,
                document_count = ?,
                excluded_count = ?,
                section_count = ?,
                wikilink_count = ?,
                task_count = ?,
                status_marker_count = ?
            WHERE run_id = ?
            """,
            (
                completed_at,
                document_count,
                len(exclusions),
                section_count,
                wikilink_count,
                task_count,
                status_marker_count,
                run_id,
            ),
        )

    return MarkdownCorpusIngestResult(
        run_id=run_id,
        sqlite_path=db_path.as_posix(),
        root_path=root_path.as_posix(),
        machine=machine,
        document_count=document_count,
        excluded_count=len(exclusions),
        section_count=section_count,
        wikilink_count=wikilink_count,
        task_count=task_count,
        status_marker_count=status_marker_count,
        git_head=git_head,
        git_branch=git_branch,
    )


def latest_run_summary(sqlite_path: str | Path = DEFAULT_SQLITE_PATH, run_id: str | None = None) -> dict[str, Any]:
    with _connect(sqlite_path) as conn:
        if run_id is None:
            row = conn.execute(
                "SELECT run_id FROM md_corpus_runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return {}
            run_id = row["run_id"]
        run = conn.execute("SELECT * FROM md_corpus_runs WHERE run_id = ?", (run_id,)).fetchone()
        if run is None:
            return {}
        top_status = conn.execute(
            """
            SELECT marker, COUNT(*) AS count
            FROM md_status_markers m
            JOIN md_documents d ON d.document_id = m.document_id
            WHERE d.run_id = ?
            GROUP BY marker
            ORDER BY count DESC, marker
            """,
            (run_id,),
        ).fetchall()
    return {
        "run": dict(run),
        "status_markers": {row["marker"]: row["count"] for row in top_status},
    }


def format_operator_summary(result: MarkdownCorpusIngestResult) -> str:
    return "\n".join(
        [
            "Markdown Corpus Ingest",
            f"- run_id: {result.run_id}",
            f"- machine: {result.machine}",
            f"- root: {result.root_path}",
            f"- sqlite: {result.sqlite_path}",
            f"- documents: {result.document_count}",
            f"- exclusions: {result.excluded_count}",
            f"- sections: {result.section_count}",
            f"- wikilinks: {result.wikilink_count}",
            f"- tasks: {result.task_count}",
            f"- status markers: {result.status_marker_count}",
            f"- git: {result.git_branch or 'unknown'} {result.git_head or 'unknown'}",
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest allowed PC Markdown files into SQLite.")
    parser.add_argument("--root", default=DEFAULT_ROOT.as_posix(), help="Root to walk. Defaults to /home/openclaw.")
    parser.add_argument(
        "--db",
        default=DEFAULT_SQLITE_PATH.as_posix(),
        help="SQLite output path. Relative paths resolve under this module's repo root.",
    )
    parser.add_argument("--machine", default=DEFAULT_MACHINE, help="Machine label to store with each row.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = ingest_markdown_corpus(
        root=args.root,
        sqlite_path=args.db,
        machine=args.machine,
        run_id=args.run_id,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(format_operator_summary(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
