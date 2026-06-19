import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import md_corpus_ingest
import md_staleness
from scripts.md_staleness import main as staleness_main


FIXED_NOW = "2026-06-18T12:00:00+00:00"


def _write(path: Path, text: str, *, days_old: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    mtime = datetime.fromisoformat(FIXED_NOW).timestamp() - (days_old * 86400)
    os.utime(path, (mtime, mtime))


def _fixture_db(tmp_path: Path) -> Path:
    root = tmp_path / "mac_root"
    root.mkdir()
    _write(root / "recent.md", "# Recent\n\nFresh note.\n", days_old=1)
    _write(root / "old.md", "# Old\n\nOld note.\n", days_old=45)
    _write(root / "done.md", "# Done\n\nDONE completed.\n", days_old=2)
    _write(root / "todo.md", "# Todo\n\nTODO active\n\n- [ ] open item\n", days_old=20)
    _write(root / "linked.md", "# Linked\n\nSee [Old](old.md).\n", days_old=2)
    _write(root / "legal" / "case.md", "# Legal\n\nSHOULD_NOT_APPEAR\n", days_old=60)
    db_path = tmp_path / "corpus.sqlite"
    md_corpus_ingest.ingest_mac_markdown_corpus(
        root=root,
        db_path=db_path,
        run_id="corpus_fixture",
        machine="mac-test",
    )
    return db_path


def _rows(db_path: Path, sql: str, params=()):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(sql, params).fetchall()


def _doc(db_path: Path, relative_path: str):
    rows = _rows(
        db_path,
        "SELECT * FROM md_staleness_documents WHERE relative_path = ?",
        (relative_path,),
    )
    return rows[0]


def test_schema_initializes_staleness_tables(tmp_path):
    db_path = _fixture_db(tmp_path)
    tables = set(md_staleness.md_staleness_table_names(db_path))

    assert {"md_staleness_runs", "md_staleness_documents"} <= tables


def test_classifies_recent_old_done_todo_and_linked_docs(tmp_path):
    db_path = _fixture_db(tmp_path)

    result = md_staleness.build_markdown_staleness(
        db_path=db_path,
        run_id="stale_fixture",
        now=FIXED_NOW,
        fresh_days=7,
        stale_days=30,
    )

    assert result.document_count == 5
    assert _doc(db_path, "recent.md")["staleness_status"] == "current_recent"
    assert _doc(db_path, "old.md")["staleness_status"] == "stale_by_mtime"
    assert _doc(db_path, "done.md")["staleness_status"] == "done_or_superseded"
    assert _doc(db_path, "todo.md")["staleness_status"] == "active_with_open_tasks"
    assert _doc(db_path, "old.md")["inbound_link_count"] == 1
    assert _doc(db_path, "linked.md")["outbound_link_count"] == 1


def test_unlinked_old_doc_is_stale_unreferenced(tmp_path):
    db_path = _fixture_db(tmp_path)

    md_staleness.build_markdown_staleness(
        db_path=db_path,
        run_id="stale_fixture",
        now=FIXED_NOW,
        fresh_days=7,
        stale_days=30,
    )

    reasons = json.loads(_doc(db_path, "old.md")["reason_codes_json"])
    assert "mtime_older_than_stale_days" in reasons
    assert "has_inbound_links" in reasons
    assert "legal/case.md" not in {
        row["relative_path"]
        for row in _rows(db_path, "SELECT relative_path FROM md_staleness_documents")
    }


def test_rerun_with_same_run_id_is_idempotent(tmp_path):
    db_path = _fixture_db(tmp_path)

    first = md_staleness.build_markdown_staleness(db_path=db_path, run_id="same", now=FIXED_NOW)
    second = md_staleness.build_markdown_staleness(db_path=db_path, run_id="same", now=FIXED_NOW)

    assert first.document_count == second.document_count
    assert _rows(db_path, "SELECT * FROM md_staleness_runs WHERE run_id = 'same'")
    assert len(_rows(db_path, "SELECT * FROM md_staleness_documents WHERE run_id = 'same'")) == second.document_count


def test_cli_json_and_operator_output(tmp_path, capsys):
    db_path = _fixture_db(tmp_path)

    assert staleness_main(
        [
            "--db",
            str(db_path),
            "--run-id",
            "cli_json",
            "--now",
            FIXED_NOW,
            "--format",
            "json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["document_count"] == 5
    assert payload["no_authority_flags"]["file_delete_allowed"] is False

    assert staleness_main(
        [
            "--db",
            str(db_path),
            "--run-id",
            "cli_operator",
            "--now",
            FIXED_NOW,
            "--format",
            "operator",
        ]
    ) == 0
    assert "Markdown Staleness Classifier" in capsys.readouterr().out


def test_source_has_no_scan_network_send_delete_or_move_authority():
    source = Path("md_staleness.py").read_text(encoding="utf-8").lower()

    for token in [
        "os.walk",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "smtplib",
        "send_message",
        "reply_text",
        "os.system",
        "shell=true",
        ".unlink(",
        ".rename(",
        "shutil.move",
        "shutil.rmtree",
    ]:
        assert token not in source
    assert md_staleness.NO_AUTHORITY_FLAGS["advisory_only"] is True
    assert all(value is False for key, value in md_staleness.NO_AUTHORITY_FLAGS.items() if key != "advisory_only")
