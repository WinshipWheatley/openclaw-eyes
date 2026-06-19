import json
import sqlite3
from pathlib import Path

import md_active_work_map
import md_corpus_ingest
import md_staleness
from scripts.md_active_work_map import main as active_work_main


FIXED_NOW = "2026-06-18T12:00:00+00:00"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_db(tmp_path: Path) -> Path:
    root = tmp_path / "mac_root"
    root.mkdir()
    _write(root / "high.md", "# High\n\nTODO active\n\n- [ ] inspect packet\n- [ ] report evidence\n")
    _write(root / "low.md", "# Low\n\nTODO follow up.\n")
    _write(root / "done.md", "# Done\n\nDONE completed.\n\nTODO old note.\n")
    _write(root / "plain.md", "# Plain\n\nNo active work here.\n")
    _write(root / "legal" / "case.md", "# Legal\n\nTODO should stay unread.\n")
    db_path = tmp_path / "corpus.sqlite"
    md_corpus_ingest.ingest_mac_markdown_corpus(
        root=root,
        db_path=db_path,
        run_id="corpus_fixture",
        machine="mac-test",
    )
    md_staleness.build_markdown_staleness(
        db_path=db_path,
        run_id="stale_fixture",
        source_corpus_run_id="corpus_fixture",
        now=FIXED_NOW,
    )
    return db_path


def _row(db_path: Path, sql: str, params=()):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return rows[0] if rows else None


def test_schema_initializes_active_work_receipts(tmp_path):
    db_path = _fixture_db(tmp_path)

    assert md_active_work_map.md_active_work_map_table_names(db_path) == ("md_active_work_map_receipts",)


def test_active_work_map_ranks_open_tasks_and_excludes_done_or_sensitive(tmp_path):
    db_path = _fixture_db(tmp_path)

    result = md_active_work_map.build_active_work_map(
        db_path=db_path,
        map_id="active_fixture",
        limit=10,
    )

    paths = [item["relative_path"] for item in result.top_documents]
    assert result.open_document_count == 2
    assert paths == ["high.md", "low.md"]
    assert result.top_documents[0]["priority_score"] > result.top_documents[1]["priority_score"]
    assert all(item["truth_claimed"] is False for item in result.top_documents)
    assert "done.md" not in paths
    assert "legal/case.md" not in paths


def test_active_work_map_records_receipt_without_authority(tmp_path):
    db_path = _fixture_db(tmp_path)

    result = md_active_work_map.build_active_work_map(
        db_path=db_path,
        map_id="active_receipt",
        limit=1,
    )
    row = _row(db_path, "SELECT * FROM md_active_work_map_receipts WHERE map_id = ?", (result.map_id,))

    assert row["open_document_count"] == 2
    assert row["top_document_count"] == 1
    assert row["model_call_allowed"] == 0
    assert row["vector_search_allowed"] == 0
    assert row["source_markdown_writeback_allowed"] == 0
    assert row["truth_claimed"] == 0
    assert row["advisory_only"] == 1
    assert json.loads(row["top_documents_json"])[0]["relative_path"] == "high.md"


def test_cli_json_and_operator_output(tmp_path, capsys):
    db_path = _fixture_db(tmp_path)

    assert active_work_main(
        [
            "--db",
            str(db_path),
            "--map-id",
            "cli_json",
            "--format",
            "json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["open_document_count"] == 2
    assert payload["no_authority_flags"]["source_markdown_writeback_allowed"] is False

    assert active_work_main(
        [
            "--db",
            str(db_path),
            "--map-id",
            "cli_operator",
            "--format",
            "operator",
        ]
    ) == 0
    assert "Markdown Active Work Map" in capsys.readouterr().out


def test_source_has_no_scan_network_send_delete_move_writeback_or_model_authority():
    source = Path("md_active_work_map.py").read_text(encoding="utf-8").lower()

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
        "open(",
        "write_text",
    ]:
        assert token not in source
    assert md_active_work_map.NO_AUTHORITY_FLAGS["source_markdown_writeback_allowed"] is False
    assert md_active_work_map.NO_AUTHORITY_FLAGS["truth_claimed"] is False
    assert md_active_work_map.NO_AUTHORITY_FLAGS["advisory_only"] is True
