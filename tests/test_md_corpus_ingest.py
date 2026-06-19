import json
import sqlite3
from pathlib import Path

import md_corpus_ingest as ingest
from scripts.md_corpus_ingest import main as ingest_main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "mac_root"
    root.mkdir()
    _write(
        root / "README.md",
        "\n".join(
            [
                "# Root Readme",
                "",
                "TODO: wire the thing.",
                "",
                "See [[Architecture]] and [Runtime](docs/runtime.md).",
                "",
                "- [ ] open task",
                "- [x] closed task",
            ]
        )
        + "\n",
    )
    _write(
        root / "docs" / "runtime.md",
        "# Runtime",
        )
    _write(root / "legal" / "case.md", "# Legal\n\nSHOULD_NOT_APPEAR\n")
    _write(root / "finance" / "budget.md", "# Finance\n\nSHOULD_NOT_APPEAR\n")
    _write(root / "MusicLaw" / "contract.md", "# MusicLaw\n\nSHOULD_NOT_APPEAR\n")
    _write(root / ".git" / "ignored.md", "# Git cache\n")
    return root


def _rows(db_path: Path, sql: str, params=()):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(sql, params).fetchall()


def _row(db_path: Path, sql: str, params=()):
    rows = _rows(db_path, sql, params)
    return rows[0] if rows else None


def test_schema_initializes_md_corpus_tables(tmp_path):
    tables = set(ingest.md_corpus_table_names(tmp_path / "corpus.sqlite"))

    assert {
        "md_corpus_runs",
        "md_corpus_documents",
        "md_corpus_exclusions",
    } <= tables


def test_ingests_allowed_markdown_fields_to_sqlite(tmp_path):
    root = _fixture_root(tmp_path)
    db_path = tmp_path / "corpus.sqlite"

    result = ingest.ingest_mac_markdown_corpus(
        root=root,
        db_path=db_path,
        run_id="fixture_run",
        machine="mac-test",
    )
    doc = _row(db_path, "SELECT * FROM md_corpus_documents WHERE relative_path = 'README.md'")
    links = json.loads(doc["links_json"])
    tasks = json.loads(doc["tasks_json"])
    markers = json.loads(doc["status_markers_json"])
    sections = json.loads(doc["sections_json"])

    assert result.ingested_document_count == 2
    assert result.machine == "mac-test"
    assert doc["machine"] == "mac-test"
    assert doc["title"] == "Root Readme"
    assert "TODO: wire the thing." in doc["text"]
    assert {"kind": "wiki", "target": "Architecture", "label": "Architecture"} in links
    assert {"kind": "markdown", "target": "docs/runtime.md", "label": "Runtime"} in links
    assert [task["checked"] for task in tasks] == [False, True]
    assert markers[0]["marker"] == "TODO"
    assert sections[0]["heading"] == "Root Readme"
    assert doc["git_last_commit"] is None


def test_sensitive_legal_finance_musiclaw_paths_are_excluded_before_body_storage(tmp_path):
    root = _fixture_root(tmp_path)
    db_path = tmp_path / "corpus.sqlite"

    result = ingest.ingest_mac_markdown_corpus(root=root, db_path=db_path, run_id="sensitive_run")
    rows = _rows(db_path, "SELECT relative_path, text FROM md_corpus_documents")
    excluded = {
        row["relative_path"]: row["reason"]
        for row in _rows(db_path, "SELECT relative_path, reason FROM md_corpus_exclusions")
    }
    stored_text = "\n".join(row["text"] for row in rows)

    assert result.legal_sensitive_exclusion_enforced is True
    assert result.excluded_path_count >= 4
    assert "legal" in excluded
    assert "finance" in excluded
    assert "MusicLaw" in excluded
    assert "SHOULD_NOT_APPEAR" not in stored_text
    assert not any(row["relative_path"].startswith(("legal/", "finance/", "MusicLaw/")) for row in rows)


def test_rerun_with_same_run_id_is_idempotent(tmp_path):
    root = _fixture_root(tmp_path)
    db_path = tmp_path / "corpus.sqlite"

    first = ingest.ingest_mac_markdown_corpus(root=root, db_path=db_path, run_id="same")
    second = ingest.ingest_mac_markdown_corpus(root=root, db_path=db_path, run_id="same")

    assert first.ingested_document_count == second.ingested_document_count
    assert _row(db_path, "SELECT COUNT(*) AS count FROM md_corpus_runs")["count"] == 1
    assert (
        _row(db_path, "SELECT COUNT(*) AS count FROM md_corpus_documents WHERE run_id = 'same'")["count"]
        == second.ingested_document_count
    )


def test_cli_json_output_and_operator_output(tmp_path, capsys):
    root = _fixture_root(tmp_path)
    db_path = tmp_path / "corpus.sqlite"

    assert ingest_main(
        [
            "--root",
            str(root),
            "--db",
            str(db_path),
            "--run-id",
            "cli_json",
            "--machine",
            "mac-cli",
            "--format",
            "json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ingested_document_count"] == 2
    assert payload["no_authority_flags"]["legal_discovery_access_allowed"] is False

    assert ingest_main(
        [
            "--root",
            str(root),
            "--db",
            str(db_path),
            "--run-id",
            "cli_operator",
            "--format",
            "operator",
        ]
    ) == 0
    assert "Mac Markdown Corpus Ingest" in capsys.readouterr().out


def test_source_has_no_network_send_delete_or_move_authority():
    source = Path("md_corpus_ingest.py").read_text(encoding="utf-8").lower()

    for token in [
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
    assert all(value is False for value in ingest.NO_AUTHORITY_FLAGS.values())
