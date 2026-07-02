import sqlite3
from pathlib import Path

from corpus_atlas import run_corpus_atlas
from markdown_knowledge_atlas import (
    CLASSIFICATION_AXES,
    build_markdown_knowledge_atlas,
    init_markdown_knowledge_atlas_schema,
    markdown_table_names,
    query_markdown_report_section,
)
from scripts.query_markdown_knowledge_atlas import main as query_main


def _write(path: Path, text: str = "# Fixture\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "openclaw"
    root.mkdir()
    _write(
        root / "OPENCLAW_RUNTIME.md",
        "# Runtime\n\nSEND_HOLD is absolute for external sends.\n\n## Current Work\n\nRuntime gate work stays branch-only.\n",
    )
    _write(root / "USER.md", "# User\n")
    _write(root / "CORE_ARCHITECTURE_PRINCIPLES.md", "# Architecture\n")
    _write(root / "AGENTS.md", "# Adapter\n")
    _write(root / "CURRENT_STATE.md", "# Old current state\n")
    _write(root / "NEXT_ACTIONS.md", "# Old next actions\n")
    _write(root / "docs" / "operations" / "OPENCLAW_CURRENT_SYSTEM_MAP_V0.md", "# System map\n")
    _write(
        root / "docs" / "operations" / "OPENCLAW_SUBSTRATE_MISSION_CONTROL_CHECKPOINT_V1.md",
        "# Handoff\n",
    )
    _write(
        root / "docs" / "operations" / "OPENCLAW_FULL_SUITE_FAILURE_BASELINE_V0.md",
        "# Baseline\n",
    )
    _write(
        root / "docs" / "operations" / "OPENCLAW_PROJECT_CAPSULE_STACK_V0_REPORT.md",
        "# Project capsule report\n",
    )
    _write(
        root / "docs" / "operations" / "OPENCLAW_MARKDOWN_KNOWLEDGE_ATLAS_DISCOVERY_V0.md",
        "# Discovery\n",
    )
    _write(
        root / "docs" / "operations" / "OPENCLAW_CURRENT_EVIDENCE_COVERAGE_AUDIT.md",
        "# Stale audit\n",
    )
    _write(root / "docs" / "archives" / "old_handoff.md", "# Old handoff\n")
    _write(root / "generated" / "read_models" / "generated_current_state.md", "# Generated state\n")
    _write(root / "generated" / "read_models" / "generated_next_actions.md", "# Generated actions\n")
    _write(root / ".ssh" / "private_notes.md", "# secret should not be read\n")
    _write(root / "finance" / "private_budget.md", "# private finance should not be read\n")
    _write(root / "secret_notes.md", "# secret should not be read\n")
    return root


def _build(tmp_path: Path):
    root = _fixture_root(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    hashed: list[str] = []

    def hash_reader(path: Path) -> str:
        relative = path.relative_to(root).as_posix()
        hashed.append(relative)
        assert not relative.startswith(".ssh/")
        assert not relative.startswith("finance/")
        return "hash-" + relative.replace("/", "_")

    run_corpus_atlas(
        db_path=db_path,
        root=root,
        run_id="corpus_markdown_fixture",
        hash_reader=hash_reader,
    )
    result = build_markdown_knowledge_atlas(
        db_path=db_path,
        run_id="markdown_fixture",
    )
    return db_path, result, hashed


def _rows(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _row(db_path: Path, sql: str, params=()):
    rows = _rows(db_path, sql, params)
    return rows[0] if rows else None


def _doc(db_path: Path, relative_path: str):
    return _row(
        db_path,
        """
SELECT *
FROM markdown_documents
WHERE relative_path = ?
""",
        (relative_path,),
    )


def test_schema_initializes_markdown_namespace(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    tables = set(markdown_table_names(db_path))

    assert {
        "markdown_atlas_runs",
        "markdown_documents",
        "markdown_document_classifications",
        "markdown_document_bodies",
        "markdown_document_sections",
        "markdown_document_links",
        "markdown_document_reorg_candidates",
        "markdown_document_supersession",
        "markdown_document_query_receipts",
    } <= tables
    conn = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(markdown_documents)")}
    finally:
        conn.close()
    assert {
        "document_role",
        "freshness_status",
        "reorg_status",
        "sensitivity_status",
        "retrieval_policy",
        "corpus_path_id",
        "root_id",
        "root_kind",
        "owner_scope",
    } <= columns


def test_build_is_idempotent_and_links_to_corpus_paths(tmp_path):
    db_path, result, _ = _build(tmp_path)
    second = build_markdown_knowledge_atlas(db_path=db_path, run_id="markdown_fixture")

    assert result.run_id == second.run_id
    assert result.document_count == second.document_count
    assert _row(db_path, "SELECT COUNT(*) AS count FROM markdown_atlas_runs")["count"] == 1
    assert _row(db_path, "SELECT COUNT(*) AS count FROM markdown_documents")["count"] == result.document_count
    assert _row(db_path, "SELECT COUNT(*) AS count FROM markdown_document_bodies")["count"] > 0
    assert _row(db_path, "SELECT COUNT(*) AS count FROM markdown_document_sections")["count"] > 0
    fact_count = _row(
        db_path,
        "SELECT COUNT(*) AS count FROM canonical_facts WHERE doc_category = 'markdown_knowledge_atlas'",
    )["count"]
    build_markdown_knowledge_atlas(db_path=db_path, run_id="markdown_fixture")
    assert (
        _row(
            db_path,
            "SELECT COUNT(*) AS count FROM canonical_facts WHERE doc_category = 'markdown_knowledge_atlas'",
        )["count"]
        == fact_count
    )
    assert (
        _row(
            db_path,
            """
SELECT COUNT(*) AS count
FROM markdown_documents md
JOIN corpus_paths cp ON cp.path_id = md.corpus_path_id
WHERE md.run_id = ?
""",
            ("markdown_fixture",),
        )["count"]
        == result.document_count
    )


def test_classification_uses_separate_axes(tmp_path):
    db_path, _, _ = _build(tmp_path)
    axes = {
        row["axis"]
        for row in _rows(
            db_path,
            "SELECT DISTINCT axis FROM markdown_document_classifications",
        )
    }

    assert set(CLASSIFICATION_AXES) <= axes
    doc = _doc(db_path, "docs/operations/OPENCLAW_CURRENT_SYSTEM_MAP_V0.md")
    assert doc["document_role"] == "current_system_map"
    assert doc["freshness_status"] == "current"
    assert doc["reorg_status"] == "keep_current"
    assert doc["sensitivity_status"] == "normal_internal"
    assert doc["retrieval_policy"] in {"agent_retrievable", "needs_operator_review"}


def test_known_current_generated_baseline_and_stale_docs_are_classified(tmp_path):
    db_path, _, _ = _build(tmp_path)

    assert _doc(db_path, "docs/operations/OPENCLAW_CURRENT_SYSTEM_MAP_V0.md")[
        "document_role"
    ] == "current_system_map"

    generated = _doc(db_path, "generated/read_models/generated_current_state.md")
    assert generated["document_role"] == "generated_status"
    assert generated["freshness_status"] == "current"
    assert generated["retrieval_policy"] == "generated_surface_only"

    baseline = _doc(db_path, "docs/operations/OPENCLAW_FULL_SUITE_FAILURE_BASELINE_V0.md")
    assert baseline["document_role"] == "test_baseline"

    stale = _doc(db_path, "CURRENT_STATE.md")
    assert stale["freshness_status"] in {"stale_possible", "superseded"}
    assert stale["reorg_status"] == "archive_candidate"
    assert stale["document_role"] != "canonical_doctrine"
    assert stale["retrieval_policy"] != "agent_retrievable"


def test_no_go_sensitive_markdown_is_not_retrievable_or_raw_read(tmp_path):
    db_path, _, hashed = _build(tmp_path)

    assert ".ssh/private_notes.md" not in hashed
    assert "finance/private_budget.md" not in hashed
    assert "secret_notes.md" not in hashed
    doc = _doc(db_path, "secret_notes.md")
    assert doc["sensitivity_status"] == "no_go"
    assert doc["retrieval_policy"] == "blocked_no_go"
    assert doc["body_read"] == 0
    assert doc["raw_body_stored"] == 0


def test_archive_candidates_are_advisory_only_and_do_not_move_files(tmp_path):
    db_path, _, _ = _build(tmp_path)
    archive = _doc(db_path, "docs/archives/old_handoff.md")
    assert archive["reorg_status"] == "archive_candidate"
    candidate = _row(
        db_path,
        """
SELECT advisory_only, moved
FROM markdown_document_reorg_candidates
WHERE markdown_document_id = ?
""",
        (archive["markdown_document_id"],),
    )
    assert candidate["advisory_only"] == 1
    assert candidate["moved"] == 0
    assert (tmp_path / "openclaw" / "docs" / "archives" / "old_handoff.md").exists()


def test_reports_work(tmp_path, capsys):
    db_path, _, _ = _build(tmp_path)

    summary = query_markdown_report_section(db_path=db_path, section="summary")
    assert summary["run"]["document_count"] >= 10
    assert summary["counts"]["document_role"]["current_system_map"] == 1

    current = query_markdown_report_section(db_path=db_path, section="current")
    assert any(
        item["relative_path"] == "docs/operations/OPENCLAW_CURRENT_SYSTEM_MAP_V0.md"
        for item in current["items"]
    )

    rc = query_main(["--db", str(db_path), "--report", "agent-retrievable", "--format", "operator"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Markdown Knowledge Atlas v0 - agent-retrievable" in out


def test_safe_markdown_bodies_sections_and_ledger_rows_are_ingested(tmp_path):
    db_path, _, _ = _build(tmp_path)

    doc = _doc(db_path, "OPENCLAW_RUNTIME.md")
    assert doc["body_read"] == 1
    assert doc["raw_body_stored"] == 1

    run = _row(db_path, "SELECT body_read, raw_body_stored FROM markdown_atlas_runs")
    assert run["body_read"] == 1
    assert run["raw_body_stored"] == 1

    body = _row(
        db_path,
        """
SELECT body_text, body_char_count, body_line_count
FROM markdown_document_bodies
WHERE markdown_document_id = ?
""",
        (doc["markdown_document_id"],),
    )
    assert "SEND_HOLD is absolute" in body["body_text"]
    assert body["body_char_count"] == len(body["body_text"])
    assert body["body_line_count"] >= 4

    sections = _rows(
        db_path,
        """
SELECT heading, heading_path_json, section_text, canonical_fact_id
FROM markdown_document_sections
WHERE markdown_document_id = ?
ORDER BY section_ordinal
""",
        (doc["markdown_document_id"],),
    )
    assert [row["heading"] for row in sections] == ["Runtime", "Current Work"]
    assert "SEND_HOLD is absolute" in sections[0]["section_text"]
    assert sections[0]["canonical_fact_id"]
    assert sections[1]["canonical_fact_id"]

    fact = _row(
        db_path,
        """
SELECT source_file, section_heading, truth_status, verification_required
FROM canonical_facts
WHERE fact_id = ?
""",
        (sections[0]["canonical_fact_id"],),
    )
    assert fact["source_file"] == "OPENCLAW_RUNTIME.md"
    assert fact["section_heading"] == "Runtime"
    assert fact["truth_status"] == "candidate_from_markdown_section"
    assert fact["verification_required"] == 1

    inventory = _row(
        db_path,
        """
SELECT file_name, extension, file_type_guess, ingest_eligibility
FROM file_inventory
WHERE relative_path = 'OPENCLAW_RUNTIME.md'
""",
    )
    assert inventory["file_name"] == "OPENCLAW_RUNTIME.md"
    assert inventory["extension"] == ".md"
    assert inventory["file_type_guess"] == "markdown"
    assert inventory["ingest_eligibility"] == "eligible_metadata_only"


def test_markdown_atlas_has_no_external_or_destructive_behavior():
    source = Path("markdown_knowledge_atlas.py").read_text(encoding="utf-8")

    forbidden = (
        "subprocess",
        "requests",
        "httpx",
        "urllib.request",
        "socket",
        "paramiko",
        "docker run",
        "ollama run",
        "ollama pull",
        ".unlink(",
        ".rename(",
        "shutil.move",
        "os.remove",
        "os.system",
        "shell=True",
    )
    for token in forbidden:
        assert token not in source
    assert "open(" not in source
