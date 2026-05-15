import json
import sqlite3
from pathlib import Path

from corpus_atlas import run_corpus_atlas
from markdown_evidence_ingestion import (
    NO_AUTHORITY_FLAGS,
    export_markdown_evidence_read_model,
    ingest_approved_markdown_evidence,
    markdown_evidence_table_names,
    query_markdown_evidence,
)
from markdown_knowledge_atlas import build_markdown_knowledge_atlas
from scripts.export_markdown_evidence_read_model import main as export_main
from scripts.ingest_approved_markdown_evidence import main as ingest_main
from scripts.query_markdown_evidence import main as query_main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "openclaw"
    root.mkdir()
    _write(root / "OPENCLAW_RUNTIME.md", "# Runtime\n\nOpenClaw keeps operator approval gates.\n")
    _write(root / "USER.md", "# User\n\nShort answers by default.\n")
    _write(root / "CORE_ARCHITECTURE_PRINCIPLES.md", "# Architecture\n\nUse one source of truth.\n")
    _write(root / "AGENTS.md", "# Adapter\n\nRead runtime law.\n")
    _write(
        root / "docs" / "operations" / "OPENCLAW_CURRENT_SYSTEM_MAP_V0.md",
        "# System Map\n\nMission Control is read-only.\n\n## Boundary\n\nNo runtime activation.\n",
    )
    _write(
        root / "docs" / "operations" / "OPENCLAW_SAFE_OPERATION_DOC.md",
        "# Operation\n\nMission Control surfaces safe read models.\n",
    )
    _write(
        root / "docs" / "operations" / "OPENCLAW_REVIEW_NEEDED_DISCOVERY_V0.md",
        "# Discovery\n\nFuture lane should review this before use.\n",
    )
    _write(root / "secret_token.md", "# Secret\n\nDo not ingest this body.\n")
    _write(root / "finance" / "budget.md", "# Finance\n\nDo not ingest finance.\n")
    _write(root / ".ssh" / "private.md", "# Private\n\nDo not ingest.\n")
    return root


def _build_fixture(tmp_path: Path):
    root = _fixture_root(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    hashed: list[str] = []

    def hash_reader(path: Path) -> str:
        relative = path.relative_to(root).as_posix()
        hashed.append(relative)
        assert not relative.startswith(".ssh/")
        assert not relative.startswith("finance/")
        assert "secret" not in relative
        return "hash-" + relative.replace("/", "_")

    run_corpus_atlas(db_path=db_path, root=root, run_id="corpus_markdown_evidence", hash_reader=hash_reader)
    build_markdown_knowledge_atlas(db_path=db_path, run_id="markdown_atlas_evidence")
    result = ingest_approved_markdown_evidence(
        db_path=db_path,
        repo_root=root,
        run_id="markdown_evidence_fixture",
    )
    return root, db_path, result, hashed


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
    tables = set(markdown_evidence_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "markdown_evidence_runs",
        "markdown_evidence_sources",
        "markdown_evidence_items",
        "markdown_evidence_query_receipts",
    } <= tables


def test_only_approved_agent_retrievable_or_allowlisted_docs_are_ingested(tmp_path):
    _, db_path, result, hashed = _build_fixture(tmp_path)

    paths = {
        row["relative_path"]
        for row in _rows(db_path, "SELECT relative_path FROM markdown_evidence_sources")
    }
    assert "docs/operations/OPENCLAW_CURRENT_SYSTEM_MAP_V0.md" in paths
    assert "OPENCLAW_RUNTIME.md" in paths
    assert "secret_token.md" not in paths
    assert "finance/budget.md" not in paths
    assert ".ssh/private.md" not in paths
    assert "secret_token.md" not in hashed
    assert result.source_count >= 2
    assert result.item_count >= result.source_count


def test_needs_review_no_go_and_sensitive_docs_are_skipped(tmp_path):
    _, db_path, _, _ = _build_fixture(tmp_path)

    skipped = _row(
        db_path,
        """
SELECT skipped_count, full_raw_body_stored, raw_private_scan_allowed
FROM markdown_evidence_runs
WHERE run_id = 'markdown_evidence_fixture'
""",
    )
    assert skipped["skipped_count"] >= 1
    assert skipped["full_raw_body_stored"] == 0
    assert skipped["raw_private_scan_allowed"] == 0
    assert _row(
        db_path,
        "SELECT COUNT(*) AS count FROM markdown_evidence_sources WHERE sensitivity_status IN ('no_go','sensitive_metadata_only')",
    )["count"] == 0


def test_chunks_are_bounded_and_not_truth(tmp_path):
    _, db_path, _, _ = _build_fixture(tmp_path)

    items = _rows(
        db_path,
        """
SELECT excerpt, excerpt_char_count, evidence_label,
       parsed_evidence_not_truth, truth_claimed, source_claim_only
FROM markdown_evidence_items
""",
    )

    assert items
    assert all(row["excerpt_char_count"] <= 420 for row in items)
    assert all(row["parsed_evidence_not_truth"] == 1 for row in items)
    assert all(row["truth_claimed"] == 0 for row in items)
    assert {row["evidence_label"] for row in items} <= {
        "parsed_evidence_not_truth",
        "source_claim",
        "operator_note",
        "generated_status",
        "doctrine_excerpt",
    }


def test_query_and_read_model_export_work(tmp_path, capsys):
    _, db_path, _, _ = _build_fixture(tmp_path)
    export_root = tmp_path / "exports"

    report = query_markdown_evidence(db_path=db_path, query="Mission Control")
    assert report["items"]
    assert all(row["truth_claimed"] == 0 for row in report["items"])

    assert query_main(["--db", str(db_path), "--query", "Mission Control", "--format", "operator"]) == 0
    assert "Approved Markdown Evidence v0" in capsys.readouterr().out

    export = export_markdown_evidence_read_model(db_path=db_path, export_root=export_root)
    payload = json.loads((export_root / "markdown_evidence.json").read_text(encoding="utf-8"))
    assert payload["source_count"] >= 1
    assert payload["item_count"] >= 1
    assert payload["truth_promotion_allowed"] is False
    assert payload["model_call_allowed"] is False
    assert payload["vector_search_allowed"] is False
    assert all(value is False for value in payload["no_authority_flags"].values())

    assert export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "operator"]) == 0
    assert "Approved Markdown Evidence Read-Model Export v0" in capsys.readouterr().out


def test_cli_ingest_works(tmp_path, capsys):
    root = _fixture_root(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    run_corpus_atlas(db_path=db_path, root=root, run_id="corpus_cli")
    build_markdown_knowledge_atlas(db_path=db_path, run_id="markdown_cli")

    assert ingest_main(
        [
            "--db",
            str(db_path),
            "--repo-root",
            str(root),
            "--run-id",
            "markdown_evidence_cli",
            "--format",
            "operator",
        ]
    ) == 0
    assert "Approved Markdown Evidence v0" in capsys.readouterr().out


def test_static_boundaries():
    source = Path("markdown_evidence_ingestion.py").read_text(encoding="utf-8")

    assert "requests" not in source
    assert "httpx" not in source
    assert "urllib" not in source
    assert "socket" not in source
    assert "shell=True" not in source
    assert "os.system" not in source
    assert ".unlink(" not in source
    assert ".rename(" not in source
    assert "shutil.move" not in source
    assert all(value is False for value in NO_AUTHORITY_FLAGS.values())
