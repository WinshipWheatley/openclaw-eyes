import sqlite3
from pathlib import Path

from corpus_atlas import run_corpus_atlas
from markdown_knowledge_atlas import build_markdown_knowledge_atlas
from markdown_knowledge_query import query_markdown_work
from scripts.query_markdown_work import main as query_main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_query_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "openclaw"
    root.mkdir()
    _write(
        root / "OPENCLAW_RUNTIME.md",
        "# Runtime\n\n## Runtime Gate\n\nRuntime gate work stays branch-only and SEND_HOLD remains absolute.\n",
    )
    _write(root / "docs" / "operations" / "OTHER.md", "# Other\n\nUnrelated operations note.\n")
    db_path = tmp_path / "ledger.sqlite"

    def hash_reader(path: Path) -> str:
        return "hash-" + path.relative_to(root).as_posix().replace("/", "_")

    run_corpus_atlas(
        db_path=db_path,
        root=root,
        run_id="corpus_query_fixture",
        hash_reader=hash_reader,
    )
    build_markdown_knowledge_atlas(db_path=db_path, run_id="markdown_query_fixture")
    return db_path


def test_query_markdown_work_returns_section_and_registry_context(tmp_path):
    db_path = _build_query_fixture(tmp_path)

    payload = query_markdown_work("what work on runtime gate", db_path=db_path, limit=5)

    assert payload["status"] == "ok"
    assert payload["run_id"] == "markdown_query_fixture"
    assert payload["result_count"] >= 1
    assert any(result["relative_path"] == "OPENCLAW_RUNTIME.md" for result in payload["results"])
    runtime_result = next(
        result
        for result in payload["results"]
        if "Runtime gate work stays branch-only" in result["excerpt"]
    )
    assert runtime_result["relative_path"] == "OPENCLAW_RUNTIME.md"
    assert runtime_result["heading"] == "Runtime Gate"
    assert "Runtime gate work stays branch-only" in runtime_result["excerpt"]
    assert runtime_result["canonical_fact_id"]
    assert payload["registry_context"]["system_registry_id"] == "openclaw_system_knowledge_registry"
    assert payload["registry_context"]["estate_topology_schema_version"]
    assert payload["source_modules"] == {
        "markdown_atlas": "markdown_knowledge_atlas.py",
        "ledger": "business_ops_ledger.py",
        "system_registry": "openclaw_system_knowledge_registry.py",
        "estate_topology": "openclaw_estate_topology_registry.py",
    }
    assert payload["authority_boundary"]["read_only_query"] is True
    assert payload["authority_boundary"]["external_call"] is False

    conn = sqlite3.connect(db_path)
    try:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM canonical_facts WHERE doc_category = 'markdown_knowledge_atlas'"
            ).fetchone()[0]
            >= 1
        )
    finally:
        conn.close()


def test_query_cli_and_import_graph_proof(tmp_path, capsys):
    db_path = _build_query_fixture(tmp_path)

    rc = query_main(["runtime gate", "--db", str(db_path), "--format", "operator"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "Markdown Work Query" in out
    assert "OPENCLAW_RUNTIME.md" in out

    query_source = Path("markdown_knowledge_query.py").read_text(encoding="utf-8")
    assert "import openclaw_estate_topology_registry as estate_topology" in query_source
    assert "import openclaw_system_knowledge_registry as system_registry" in query_source
    assert "from business_ops_ledger import" in query_source
    assert "from markdown_knowledge_atlas import" in query_source

    atlas_source = Path("markdown_knowledge_atlas.py").read_text(encoding="utf-8")
    assert "from business_ops_ledger import" in atlas_source
    assert "from corpus_atlas import" in atlas_source
