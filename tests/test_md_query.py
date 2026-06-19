import json
import sqlite3
from pathlib import Path

import md_corpus_ingest
import md_query
import md_staleness
from scripts.md_query import main as query_main


FIXED_NOW = "2026-06-18T12:00:00+00:00"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_db(tmp_path: Path) -> Path:
    root = tmp_path / "mac_root"
    root.mkdir()
    _write(root / "send_hold.md", "# SEND HOLD\n\nV0 send bypass needs approval gate work.\n")
    _write(root / "niles.md", "# Niles\n\nNiles Stage 1 schema work is metadata only.\n")
    _write(root / "todo.md", "# Todo\n\nTODO follow up on send hold.\n\n- [ ] inspect packet\n")
    _write(root / "legal" / "case.md", "# Legal\n\nsend hold legal body must stay unread.\n")
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


def test_schema_initializes_query_receipts(tmp_path):
    db_path = _fixture_db(tmp_path)

    assert md_query.md_query_table_names(db_path) == ("md_query_receipts",)


def test_query_returns_ranked_matches_joined_to_staleness(tmp_path):
    db_path = _fixture_db(tmp_path)

    result = md_query.query_markdown_corpus(
        db_path=db_path,
        query="send hold",
        query_id="query_send_hold",
        limit=5,
    )

    assert result.result_count >= 2
    assert result.results[0]["relative_path"] == "send_hold.md"
    assert result.results[0]["staleness_status"] in {
        "current_recent",
        "active_with_open_tasks",
        "current_or_review",
    }
    assert result.results[0]["truth_claimed"] is False
    assert "send bypass" in result.results[0]["excerpt"].lower()


def test_query_records_receipt_without_model_or_vector_search(tmp_path):
    db_path = _fixture_db(tmp_path)

    result = md_query.query_markdown_corpus(
        db_path=db_path,
        query="niles stage",
        query_id="query_niles",
    )
    row = _row(db_path, "SELECT * FROM md_query_receipts WHERE query_id = ?", (result.query_id,))

    assert row["result_count"] == result.result_count
    assert row["model_call_allowed"] == 0
    assert row["vector_search_allowed"] == 0
    assert row["truth_claimed"] == 0
    assert json.loads(row["query_tokens_json"]) == ["niles", "stage"]


def test_query_has_no_matches_for_missing_term(tmp_path):
    db_path = _fixture_db(tmp_path)

    result = md_query.query_markdown_corpus(
        db_path=db_path,
        query="nonexistent-zebra",
        query_id="query_none",
    )

    assert result.result_count == 0
    assert result.results == []


def test_cli_json_and_operator_output(tmp_path, capsys):
    db_path = _fixture_db(tmp_path)

    assert query_main(
        [
            "send hold",
            "--db",
            str(db_path),
            "--query-id",
            "cli_json",
            "--format",
            "json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["result_count"] >= 2
    assert payload["no_authority_flags"]["vector_search_allowed"] is False

    assert query_main(
        [
            "niles",
            "--db",
            str(db_path),
            "--query-id",
            "cli_operator",
            "--format",
            "operator",
        ]
    ) == 0
    assert "Markdown Query" in capsys.readouterr().out


def test_source_has_no_network_send_delete_move_or_model_authority():
    source = Path("md_query.py").read_text(encoding="utf-8").lower()

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
    assert md_query.NO_AUTHORITY_FLAGS["vector_search_allowed"] is False
    assert md_query.NO_AUTHORITY_FLAGS["truth_claimed"] is False
