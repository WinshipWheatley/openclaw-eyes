import json
import sqlite3
import subprocess
from pathlib import Path

from md_corpus_ingest import (
    SCHEMA_VERSION,
    extract_sections,
    ingest_markdown_corpus,
    main,
    table_names,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _rows(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "openclaw"
    root.mkdir()
    _write(
        root / "OPENCLAW_RUNTIME.md",
        """# Runtime Law

See [[USER|operator profile]].

## Safety
- [ ] Keep SEND_HOLD absolute
- [x] DONE gate proof

TODO: keep the corpus current.
""",
    )
    _write(
        root / "docs" / "operations" / "POOL.md",
        """# Pool Work

## Active
BLOCKED items are visible.

### Done
SUPERSEDED packet note.
""",
    )
    _write(root / "finance" / "private_budget.md", "# Finance\nPRIVATE BODY MUST NOT BE READ\n")
    _write(root / "Legal Discovery" / "matter.md", "# Legal\nLEGAL BODY MUST NOT BE READ\n")
    _write(root / "MusicLaw" / "notes.md", "# MusicLaw\nMUSIC BODY MUST NOT BE READ\n")
    _write(root / ".ssh" / "secret.md", "# Secret\nSSH BODY MUST NOT BE READ\n")
    _write(root / "secret_notes.md", "# Secret file\nSECRET BODY MUST NOT BE READ\n")
    return root


def _init_git(root: Path) -> str:
    subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(
        ["git", "config", "user.email", "codex@example.invalid"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    subprocess.run(
        ["git", "config", "user.name", "Codex Test"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    subprocess.run(["git", "add", "OPENCLAW_RUNTIME.md"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(
        ["git", "commit", "-m", "seed markdown"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def test_schema_initializes_md_corpus_namespace(tmp_path):
    db_path = tmp_path / "md.sqlite"

    assert {
        "md_corpus_runs",
        "md_documents",
        "md_sections",
        "md_wikilinks",
        "md_tasks",
        "md_status_markers",
        "md_corpus_exclusions",
    } <= set(table_names(db_path))

    columns = {
        row[1]
        for row in _rows(db_path, "PRAGMA table_info(md_documents)")
    }
    assert {
        "machine",
        "relative_path",
        "title",
        "text",
        "mtime",
        "git_tracked",
        "git_last_commit_hash",
        "git_last_commit_iso",
        "git_last_commit_subject",
    } <= columns


def test_ingest_stores_markdown_body_and_metadata_without_reading_no_go_paths(tmp_path):
    root = _fixture_root(tmp_path)
    head = _init_git(root)
    db_path = tmp_path / "md.sqlite"

    result = ingest_markdown_corpus(
        root=root,
        sqlite_path=db_path,
        machine="pc_test",
        run_id="fixture_run",
    )

    assert result.document_count == 2
    assert result.excluded_count >= 5
    assert result.git_head == head

    run = _row(db_path, "SELECT * FROM md_corpus_runs WHERE run_id = ?", ("fixture_run",))
    assert run["schema_version"] == SCHEMA_VERSION
    assert run["document_count"] == 2
    assert run["no_external_actions"] == 1
    assert run["no_destructive_actions"] == 1

    doc = _row(
        db_path,
        "SELECT * FROM md_documents WHERE relative_path = ?",
        ("OPENCLAW_RUNTIME.md",),
    )
    assert doc["machine"] == "pc_test"
    assert doc["title"] == "Runtime Law"
    assert "Keep SEND_HOLD absolute" in doc["text"]
    assert doc["git_tracked"] == 1
    assert doc["git_last_commit_hash"] == head
    assert doc["git_last_commit_subject"] == "seed markdown"

    all_text = "\n".join(row["text"] for row in _rows(db_path, "SELECT text FROM md_documents"))
    assert "PRIVATE BODY MUST NOT BE READ" not in all_text
    assert "LEGAL BODY MUST NOT BE READ" not in all_text
    assert "MUSIC BODY MUST NOT BE READ" not in all_text
    assert "SSH BODY MUST NOT BE READ" not in all_text
    assert "SECRET BODY MUST NOT BE READ" not in all_text

    exclusions = {row["relative_path"]: row["reason"] for row in _rows(db_path, "SELECT * FROM md_corpus_exclusions")}
    assert "finance" in exclusions
    assert "Legal Discovery" in exclusions
    assert "MusicLaw" in exclusions
    assert ".ssh" in exclusions
    assert "secret_notes.md" in exclusions
    assert all(
        row["body_read"] == 0
        for row in _rows(db_path, "SELECT body_read FROM md_corpus_exclusions")
    )


def test_sections_links_tasks_and_status_markers_are_queryable(tmp_path):
    root = _fixture_root(tmp_path)
    db_path = tmp_path / "md.sqlite"
    ingest_markdown_corpus(root=root, sqlite_path=db_path, machine="pc_test", run_id="fixture_run")

    runtime = _row(db_path, "SELECT document_id FROM md_documents WHERE relative_path = 'OPENCLAW_RUNTIME.md'")
    sections = _rows(db_path, "SELECT * FROM md_sections WHERE document_id = ? ORDER BY start_line", (runtime["document_id"],))
    assert [row["heading"] for row in sections] == ["Runtime Law", "Safety"]
    assert json.loads(sections[1]["heading_path_json"]) == ["Runtime Law", "Safety"]

    link = _row(db_path, "SELECT * FROM md_wikilinks WHERE document_id = ?", (runtime["document_id"],))
    assert link["original"] == "USER|operator profile"
    assert link["target"] == "USER"

    tasks = _rows(db_path, "SELECT checked, text FROM md_tasks WHERE document_id = ? ORDER BY line_number", (runtime["document_id"],))
    assert [(row["checked"], row["text"]) for row in tasks] == [
        (0, "Keep SEND_HOLD absolute"),
        (1, "DONE gate proof"),
    ]

    markers = {
        row["marker"]
        for row in _rows(
            db_path,
            """
            SELECT marker
            FROM md_status_markers m
            JOIN md_documents d ON d.document_id = m.document_id
            WHERE d.run_id = 'fixture_run'
            """,
        )
    }
    assert {"TODO", "DONE", "BLOCKED", "SUPERSEDED", "ACTIVE"} <= markers


def test_ingest_is_idempotent_for_same_run_id(tmp_path):
    root = _fixture_root(tmp_path)
    db_path = tmp_path / "md.sqlite"

    first = ingest_markdown_corpus(root=root, sqlite_path=db_path, machine="pc_test", run_id="same_run")
    second = ingest_markdown_corpus(root=root, sqlite_path=db_path, machine="pc_test", run_id="same_run")

    assert first.document_count == second.document_count == 2
    assert _row(db_path, "SELECT COUNT(*) AS count FROM md_corpus_runs")["count"] == 1
    assert _row(db_path, "SELECT COUNT(*) AS count FROM md_documents")["count"] == 2
    assert _row(db_path, "SELECT COUNT(*) AS count FROM md_corpus_exclusions")["count"] == first.excluded_count


def test_cli_writes_sqlite_and_json_summary(tmp_path, capsys):
    root = _fixture_root(tmp_path)
    db_path = tmp_path / "md.sqlite"

    rc = main([
        "--root",
        str(root),
        "--db",
        str(db_path),
        "--machine",
        "pc_test",
        "--run-id",
        "cli_run",
        "--format",
        "json",
    ])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run_id"] == "cli_run"
    assert payload["document_count"] == 2
    assert db_path.exists()


def test_section_parser_ignores_headings_inside_fenced_code():
    sections = extract_sections(
        """# Real

```markdown
# Not a section
```

## Child
"""
    )

    assert [section.heading for section in sections] == ["Real", "Child"]
