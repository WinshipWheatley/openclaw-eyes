import sqlite3
from pathlib import Path

import pytest

import file_event_queue
from file_event_queue import (
    build_file_event_report,
    build_file_event_snapshot,
    file_event_table_names,
    validate_snapshot_root,
)
from scripts.query_file_event_queue import main as query_main


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


def _snapshot_root(tmp_path: Path) -> Path:
    root = tmp_path / "openclaw"
    root.mkdir()
    _write(root / "docs" / "operations" / "handoff.md", "# Handoff\n")
    _write(root / "generated" / "read_models" / "helm_state.json", '{"mode":"inspect_only"}\n')
    _write(root / "scripts" / "tool.py", "print('safe')\n")
    _write(root / "song.logicx" / "projectData", "logic bundle body should not be hashed\n")
    _write(root / "audio.wav", "audio metadata only\n")
    _write(root / "secret_token.md", "# secret\n")
    _write(root / ".ssh" / "private.md", "# no-go\n")
    return root


def _hash_reader(root: Path, seen: list[str]):
    def reader(path: Path) -> str:
        relative = path.relative_to(root).as_posix()
        seen.append(relative)
        assert not relative.startswith(".ssh/")
        assert "secret" not in relative
        assert not relative.endswith(".logicx/projectData")
        return "hash:" + relative + ":" + path.read_text(encoding="utf-8")

    return reader


def test_schema_initializes(tmp_path):
    tables = set(file_event_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "file_event_runs",
        "file_event_snapshots",
        "file_event_observations",
        "file_event_queue",
        "file_event_path_aliases",
        "file_event_classification_hints",
    } <= tables


def test_snapshot_records_metadata_hashes_and_hints(tmp_path):
    root = _snapshot_root(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    seen: list[str] = []

    result = build_file_event_snapshot(
        root=root,
        root_id="fixture_root",
        db_path=db_path,
        run_id="run_one",
        allowed_roots=(root,),
        hash_reader=_hash_reader(root, seen),
    )

    assert result.observed_path_count > 0
    assert result.event_counts["observed_new"] == result.observed_path_count
    assert "docs/operations/handoff.md" in seen
    assert "generated/read_models/helm_state.json" in seen
    assert "secret_token.md" not in seen

    markdown = _row(
        db_path,
        """
SELECT file_kind_hint, world_hint, safe_hash, queue_status
FROM file_event_observations
WHERE run_id = ? AND relative_path = ?
""",
        ("run_one", "docs/operations/handoff.md"),
    )
    assert dict(markdown) == {
        "file_kind_hint": "markdown_doc",
        "world_hint": "operations",
        "safe_hash": "hash:docs/operations/handoff.md:# Handoff\n",
        "queue_status": "queued",
    }

    generated = _row(
        db_path,
        """
SELECT file_kind_hint, world_hint, queue_status
FROM file_event_observations
WHERE run_id = ? AND relative_path = ?
""",
        ("run_one", "generated/read_models/helm_state.json"),
    )
    assert tuple(generated) == ("generated_read_model", "operations", "queued")

    logic = _row(
        db_path,
        """
SELECT file_kind_hint, safe_hash, queue_status
FROM file_event_observations
WHERE run_id = ? AND relative_path = ?
""",
        ("run_one", "song.logicx"),
    )
    assert tuple(logic) == ("logic_project", None, "classified_metadata")

    no_go = _row(
        db_path,
        """
SELECT no_go_boundary, sensitivity_hint, safe_hash, queue_status, raw_content_read, raw_body_stored
FROM file_event_observations
WHERE run_id = ? AND relative_path = ?
""",
        ("run_one", "secret_token.md"),
    )
    assert tuple(no_go) == (1, "no_go", None, "blocked_no_go", 0, 0)


def test_second_snapshot_marks_unchanged_new_modified_and_missing(tmp_path):
    root = _snapshot_root(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    seen: list[str] = []
    build_file_event_snapshot(
        root=root,
        root_id="fixture_root",
        db_path=db_path,
        run_id="run_one",
        allowed_roots=(root,),
        hash_reader=_hash_reader(root, seen),
    )

    _write(root / "docs" / "operations" / "handoff.md", "# Handoff changed\n")
    _write(root / "docs" / "operations" / "new_note.md", "# New\n")
    (root / "scripts" / "tool.py").unlink()

    result = build_file_event_snapshot(
        root=root,
        root_id="fixture_root",
        db_path=db_path,
        run_id="run_two",
        allowed_roots=(root,),
        hash_reader=_hash_reader(root, []),
    )

    assert result.event_counts["observed_modified"] >= 1
    assert result.event_counts["observed_new"] >= 1
    assert result.event_counts["observed_missing"] >= 1
    assert result.event_counts["unchanged"] >= 1
    assert _row(
        db_path,
        "SELECT event_type FROM file_event_observations WHERE run_id = ? AND relative_path = ?",
        ("run_two", "docs/operations/handoff.md"),
    )["event_type"] == "observed_modified"
    assert _row(
        db_path,
        "SELECT event_type FROM file_event_observations WHERE run_id = ? AND relative_path = ?",
        ("run_two", "docs/operations/new_note.md"),
    )["event_type"] == "observed_new"
    assert _row(
        db_path,
        "SELECT event_type FROM file_event_observations WHERE run_id = ? AND relative_path = ?",
        ("run_two", "scripts/tool.py"),
    )["event_type"] == "observed_missing"


def test_possible_move_requires_matching_safe_hash_and_size(tmp_path):
    root = tmp_path / "openclaw"
    root.mkdir()
    _write(root / "old_name.md", "# Same\n")
    db_path = tmp_path / "ledger.sqlite"

    build_file_event_snapshot(
        root=root,
        root_id="fixture_root",
        db_path=db_path,
        run_id="run_one",
        allowed_roots=(root,),
    )
    (root / "old_name.md").unlink()
    _write(root / "new_name.md", "# Same\n")
    _write(root / "different_name.md", "# Different\n")

    result = build_file_event_snapshot(
        root=root,
        root_id="fixture_root",
        db_path=db_path,
        run_id="run_two",
        allowed_roots=(root,),
    )

    assert result.possible_move_count == 1
    move = _row(
        db_path,
        """
SELECT previous_path, current_path, event_type
FROM file_event_observations
WHERE run_id = ? AND event_type = 'possible_move'
""",
        ("run_two",),
    )
    assert tuple(move) == ("old_name.md", "new_name.md", "possible_move")
    alias = _row(
        db_path,
        "SELECT advisory_only, file_moved FROM file_event_path_aliases WHERE run_id = ?",
        ("run_two",),
    )
    assert tuple(alias) == (1, 0)


def test_large_and_no_go_files_are_not_hashed(tmp_path, monkeypatch):
    monkeypatch.setattr(file_event_queue, "MAX_HASH_BYTES", 5)
    root = tmp_path / "openclaw"
    root.mkdir()
    _write(root / "large.md", "0123456789")
    _write(root / "finance" / "budget.md", "# finance\n")
    db_path = tmp_path / "ledger.sqlite"
    seen: list[str] = []

    build_file_event_snapshot(
        root=root,
        root_id="fixture_root",
        db_path=db_path,
        run_id="run_one",
        allowed_roots=(root,),
        hash_reader=_hash_reader(root, seen),
    )

    assert seen == []
    assert _row(
        db_path,
        "SELECT safe_hash, hash_reason FROM file_event_snapshots WHERE relative_path = ?",
        ("large.md",),
    )["hash_reason"] == "over_max_hash_bytes"
    assert _row(
        db_path,
        "SELECT safe_hash, queue_status FROM file_event_observations WHERE relative_path = ?",
        ("finance",),
    )["queue_status"] == "blocked_no_go"


def test_broad_roots_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="broad|empty|C-drive"):
        validate_snapshot_root("/")
    with pytest.raises(ValueError, match="broad|empty|C-drive"):
        validate_snapshot_root("/home")
    with pytest.raises(ValueError, match="empty"):
        validate_snapshot_root("")
    with pytest.raises(ValueError, match="not allowlisted"):
        validate_snapshot_root(tmp_path)


def test_reports_work(tmp_path, capsys):
    root = _snapshot_root(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    build_file_event_snapshot(
        root=root,
        root_id="fixture_root",
        db_path=db_path,
        run_id="run_one",
        allowed_roots=(root,),
    )

    summary = build_file_event_report(db_path=db_path, run_id="run_one", section="summary")
    assert summary["event_counts"]["observed_new"] > 0
    assert summary["boundary"]["raw_body_stored"] is False

    by_kind = build_file_event_report(
        db_path=db_path,
        run_id="run_one",
        section="by-kind",
        kind="markdown_doc",
    )
    assert by_kind["items"]
    assert all(item["file_kind_hint"] == "markdown_doc" for item in by_kind["items"])

    assert query_main(
        [
            "--db",
            str(db_path),
            "--run-id",
            "run_one",
            "--report",
            "possible-moves",
            "--format",
            "operator",
        ]
    ) == 0
    assert "File Event Queue v0" in capsys.readouterr().out


def test_static_no_external_runtime_or_file_reorg_behavior():
    sources = [
        Path("file_event_queue.py"),
        Path("scripts/build_file_event_snapshot.py"),
        Path("scripts/query_file_event_queue.py"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)

    forbidden = [
        "import subprocess",
        "os.system",
        "shell=True",
        "requests",
        "httpx",
        "urllib.request",
        "socket",
        "paramiko",
        "scp",
        "rsync",
        ".rename(",
        "Path.replace(",
        ".unlink(",
        "shutil.move",
        "shutil.rmtree",
        "docker run",
        "ollama run",
    ]
    for token in forbidden:
        assert token not in combined

    assert _rows
