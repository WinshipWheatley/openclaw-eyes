import json
import sqlite3
from pathlib import Path

from corpus_atlas import run_corpus_atlas
from file_event_queue import build_file_event_snapshot
from markdown_knowledge_atlas import build_markdown_knowledge_atlas
from recent_file_context import (
    NO_AUTHORITY_FLAGS,
    build_recent_file_context,
    build_recent_file_context_report,
    export_recent_file_context_read_model,
    init_recent_file_context_schema,
    recent_file_table_names,
    resolve_recent_file_reference,
)
from scripts.build_recent_file_context import main as build_main
from scripts.export_recent_file_context_read_model import main as export_main
from scripts.query_recent_file_context import main as query_main


def _write(path: Path, text: str = "fixture") -> None:
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


def test_schema_initializes(tmp_path):
    tables = set(recent_file_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "recent_file_context_runs",
        "recent_file_candidates",
        "recent_file_aliases",
        "recent_file_resolution_queries",
        "recent_file_context_links",
        "recent_file_rejections",
    } <= tables


def test_build_is_idempotent_and_records_candidates(tmp_path):
    root = tmp_path / "openclaw"
    root.mkdir()
    _write(root / "new_note.md", "# New\n")
    db_path = tmp_path / "ledger.sqlite"
    build_file_event_snapshot(
        root=root,
        root_id="fixture_root",
        db_path=db_path,
        run_id="file_run",
        allowed_roots=(root,),
    )

    first = build_recent_file_context(db_path=db_path, run_id="recent_run")
    second = build_recent_file_context(db_path=db_path, run_id="recent_run")

    assert first.run_id == second.run_id
    assert first.candidate_count == second.candidate_count == 1
    assert _row(db_path, "SELECT COUNT(*) AS count FROM recent_file_context_runs")["count"] == 1
    candidate = _row(db_path, "SELECT * FROM recent_file_candidates")
    assert candidate["relative_path"] == "new_note.md"
    assert candidate["raw_content_read"] == 0
    assert candidate["raw_body_stored"] == 0


def test_resolves_unambiguous_new_file(tmp_path):
    root = tmp_path / "openclaw"
    root.mkdir()
    _write(root / "new_note.md", "# New\n")
    db_path = tmp_path / "ledger.sqlite"
    build_file_event_snapshot(root=root, root_id="fixture_root", db_path=db_path, run_id="file_run", allowed_roots=(root,))
    build_recent_file_context(db_path=db_path, run_id="recent_run")

    result = resolve_recent_file_reference(
        query_text="that new file",
        db_path=db_path,
        run_id="recent_run",
        query_id="query_that_new_file",
    )

    assert result.resolution_status == "resolved"
    assert result.candidate_id
    assert result.confidence >= 0.8
    query = _row(db_path, "SELECT raw_content_read, raw_body_stored, execution_allowed FROM recent_file_resolution_queries")
    assert tuple(query) == (0, 0, 0)


def test_ambiguous_recent_files_require_review(tmp_path):
    root = tmp_path / "openclaw"
    root.mkdir()
    _write(root / "first.md", "# First\n")
    _write(root / "second.md", "# Second\n")
    db_path = tmp_path / "ledger.sqlite"
    build_file_event_snapshot(root=root, root_id="fixture_root", db_path=db_path, run_id="file_run", allowed_roots=(root,))
    build_recent_file_context(db_path=db_path, run_id="recent_run")

    result = resolve_recent_file_reference(
        query_text="that new file",
        db_path=db_path,
        run_id="recent_run",
        query_id="query_ambiguous",
    )

    assert result.resolution_status == "ambiguous"
    assert result.candidate_id is None
    assert "which recent file" in result.next_safe_move.lower()


def test_no_recent_file_requires_review(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    init_recent_file_context_schema(db_path)

    result = resolve_recent_file_reference(
        query_text="that new file",
        db_path=db_path,
        query_id="query_no_run",
    )

    assert result.resolution_status == "unresolved"
    assert result.candidate_id is None
    assert "snapshot" in result.next_safe_move.lower()


def test_logic_file_resolves_as_music_art_metadata_only(tmp_path):
    root = tmp_path / "openclaw"
    root.mkdir()
    (root / "song.logicx").mkdir()
    _write(root / "song.logicx" / "projectData", "logic body should not be read\n")
    db_path = tmp_path / "ledger.sqlite"
    build_file_event_snapshot(root=root, root_id="fixture_root", db_path=db_path, run_id="file_run", allowed_roots=(root,))
    build_recent_file_context(db_path=db_path, run_id="recent_run")

    result = resolve_recent_file_reference(
        query_text="the new Logic file",
        db_path=db_path,
        run_id="recent_run",
        query_id="query_logic",
    )
    candidate = _row(db_path, "SELECT * FROM recent_file_candidates WHERE candidate_id = ?", (result.candidate_id,))

    assert result.resolution_status == "resolved"
    assert candidate["file_kind_hint"] == "logic_project"
    assert candidate["world_hint"] == "music_art"
    assert candidate["metadata_only"] == 1
    assert candidate["can_agent_read"] == 0
    assert candidate["raw_content_read"] == 0
    assert "do not open" in result.next_safe_move.lower()


def test_markdown_links_to_markdown_atlas_when_safe(tmp_path):
    root = tmp_path / "openclaw"
    root.mkdir()
    _write(root / "OPENCLAW_RUNTIME.md", "# Runtime\n")
    _write(root / "docs" / "operations" / "OPENCLAW_CURRENT_SYSTEM_MAP_V0.md", "# System\n")
    db_path = tmp_path / "ledger.sqlite"

    run_corpus_atlas(db_path=db_path, root=root, run_id="corpus_run")
    build_markdown_knowledge_atlas(db_path=db_path, run_id="markdown_run")
    build_file_event_snapshot(root=root, root_id="fixture_root", db_path=db_path, run_id="file_run", allowed_roots=(root,))
    build_recent_file_context(db_path=db_path, run_id="recent_run")

    candidate = _row(
        db_path,
        """
SELECT candidate_id
FROM recent_file_candidates
WHERE relative_path = 'docs/operations/OPENCLAW_CURRENT_SYSTEM_MAP_V0.md'
""",
    )
    link = _row(
        db_path,
        """
SELECT source_table, raw_content_read, raw_body_stored
FROM recent_file_context_links
WHERE candidate_id = ? AND link_kind = 'markdown_atlas_document'
""",
        (candidate["candidate_id"],),
    )

    assert tuple(link) == ("markdown_documents", 0, 0)


def test_no_go_candidate_is_blocked_and_not_agent_retrievable(tmp_path):
    root = tmp_path / "openclaw"
    root.mkdir()
    _write(root / "secret_token.md", "# Secret\n")
    db_path = tmp_path / "ledger.sqlite"
    seen: list[str] = []

    def hash_reader(path: Path) -> str:
        seen.append(path.relative_to(root).as_posix())
        return "hash"

    build_file_event_snapshot(
        root=root,
        root_id="fixture_root",
        db_path=db_path,
        run_id="file_run",
        allowed_roots=(root,),
        hash_reader=hash_reader,
    )
    build_recent_file_context(db_path=db_path, run_id="recent_run")
    result = resolve_recent_file_reference(
        query_text="that new file",
        db_path=db_path,
        run_id="recent_run",
        query_id="query_secret",
    )
    candidate = _row(db_path, "SELECT * FROM recent_file_candidates")

    assert seen == []
    assert result.resolution_status == "blocked_no_go"
    assert candidate["no_go_boundary"] == 1
    assert candidate["can_agent_read"] == 0
    assert candidate["raw_content_read"] == 0
    assert candidate["raw_body_stored"] == 0


def test_reports_and_read_model_export_work(tmp_path, capsys):
    root = tmp_path / "openclaw"
    root.mkdir()
    _write(root / "new_note.md", "# New\n")
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "exports"
    build_file_event_snapshot(root=root, root_id="fixture_root", db_path=db_path, run_id="file_run", allowed_roots=(root,))

    assert build_main(["--db", str(db_path), "--run-id", "recent_run", "--format", "operator"]) == 0
    assert "Recent File Context v0" in capsys.readouterr().out

    assert query_main(["--db", str(db_path), "--resolve", "that new file", "--run-id", "recent_run", "--format", "operator"]) == 0
    assert "Status: `resolved`" in capsys.readouterr().out

    summary = build_recent_file_context_report(db_path=db_path, run_id="recent_run")
    assert summary["counts"]["candidate_count"] == 1

    export = export_recent_file_context_read_model(db_path=db_path, export_root=export_root)
    assert Path(export["json_path"]).name == "recent_file_context.json"
    payload = json.loads((export_root / "recent_file_context.json").read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 1
    assert payload["raw_content_read"] is False
    assert payload["file_move_allowed"] is False
    assert all(value is False for value in payload["no_authority_flags"].values())

    assert export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "operator"]) == 0
    assert "Recent File Context Read-Model Export v0" in capsys.readouterr().out


def test_static_boundaries():
    source = Path("recent_file_context.py").read_text(encoding="utf-8")

    assert "os.system" not in source
    assert "shell=True" not in source
    assert ".unlink(" not in source
    assert ".rename(" not in source
    assert "shutil.move" not in source
    assert "requests" not in source
    assert "httpx" not in source
    assert all(value is False for value in NO_AUTHORITY_FLAGS.values())
