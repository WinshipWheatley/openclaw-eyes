import json
from pathlib import Path

import openclaw_markdown_body_ingest_query as md_query
from scripts.export_openclaw_markdown_body_ingest_query import main as export_main


FIXED_NOW = "2026-06-18T23:20:00+00:00"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "openclaw"
    repo.mkdir()
    _write(
        repo / "OPENCLAW_RUNTIME.md",
        "# Runtime Law\n\nChief coordinates safe OpenClaw work and keeps action authority bounded.\n",
    )
    _write(
        repo / "docs" / "chief_work.md",
        "# Chief Work Queue\n\nB8 adds Markdown body ingest for Chief work terrain. The work query must cite evidence snippets.\n",
    )
    _write(
        repo / "docs" / "niles.md",
        "# Niles Work\n\nNiles handles deterministic music scoring contracts.\n",
    )
    _write(
        repo / "docs" / "planning" / "openclaw_legal" / "secret.md",
        "# Legal Discovery\n\nLEGAL_DISCOVERY_BODY_SHOULD_NOT_APPEAR\n",
    )
    _write(repo / "finance" / "private.md", "# Finance\n\nFINANCE_BODY_SHOULD_NOT_APPEAR\n")
    _write(repo / ".ssh" / "note.md", "# SSH\n\nSSH_BODY_SHOULD_NOT_APPEAR\n")
    return repo


def _build(repo: Path, query: str = "what work on Chief") -> dict:
    return md_query.build_openclaw_markdown_body_ingest_query(
        repo_root=repo,
        query_text=query,
        generated_at=FIXED_NOW,
        max_docs=20,
        max_body_bytes=4096,
    )


def test_bounded_body_ingest_reads_allowlisted_markdown_without_private_surfaces(tmp_path):
    repo = _sample_repo(tmp_path)
    payload = _build(repo)
    text = md_query.stable_json(payload)
    paths = {card["relative_path"] for card in payload["document_cards"]}

    assert payload["schema_version"] == md_query.SCHEMA_VERSION
    assert payload["contract_status"] == "bounded_markdown_body_ingest_query"
    assert "OPENCLAW_RUNTIME.md" in paths
    assert "docs/chief_work.md" in paths
    assert "docs/niles.md" in paths
    assert not any("legal" in path.lower() for path in paths)
    assert not any(path.startswith("finance/") for path in paths)
    assert not any(path.startswith(".ssh/") for path in paths)
    assert payload["machine_proof"]["body_read_performed"] is True
    assert payload["machine_proof"]["full_body_exported"] is False
    assert payload["machine_proof"]["legal_discovery_excluded"] is True
    assert "LEGAL_DISCOVERY_BODY_SHOULD_NOT_APPEAR" not in text
    assert "FINANCE_BODY_SHOULD_NOT_APPEAR" not in text
    assert "SSH_BODY_SHOULD_NOT_APPEAR" not in text


def test_what_work_on_query_returns_ranked_snippets_without_authority(tmp_path):
    repo = _sample_repo(tmp_path)
    payload = _build(repo, query="what work on Chief")
    receipt = payload["work_query_receipt"]

    assert receipt["query_kind"] == "what_work_on_topic"
    assert receipt["normalized_topic"] == "chief"
    assert receipt["result_count"] >= 1
    assert receipt["results"][0]["relative_path"] == "docs/chief_work.md"
    assert receipt["results"][0]["score"] > 0
    assert receipt["results"][0]["evidence_snippets"]
    assert all(len(snippet) <= md_query.MAX_SNIPPET_CHARS for snippet in receipt["results"][0]["evidence_snippets"])
    assert receipt["truth_status"] == "BODY_EVIDENCE_CANDIDATE_NOT_PROOF"
    assert receipt["action_authority_granted"] is False
    assert receipt["runtime_dispatch_allowed"] is False


def test_body_ingest_query_is_deterministic_and_byte_capped(tmp_path):
    repo = _sample_repo(tmp_path)
    long_body = "# Long Chief Note\n\n" + ("Chief work body " * 5000)
    _write(repo / "docs" / "long_chief.md", long_body)

    first = _build(repo, query="what work on Chief")
    second = _build(repo, query="what work on Chief")
    long_card = next(card for card in first["document_cards"] if card["relative_path"] == "docs/long_chief.md")

    assert md_query.stable_json(first) == md_query.stable_json(second)
    assert long_card["body_bytes_read"] <= 4096
    assert long_card["body_truncated"] is True
    assert "source_body" not in md_query.stable_json(first)
    assert "extracted_text" not in md_query.stable_json(first)


def test_exporter_writes_json_and_operator_markdown(tmp_path):
    repo = _sample_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    result = export_main(
        [
            "--repo-root",
            repo.as_posix(),
            "--export-root",
            export_root.as_posix(),
            "--query",
            "what work on Chief",
            "--generated-at",
            FIXED_NOW,
            "--format",
            "summary",
        ]
    )

    assert result == 0
    json_path = export_root / md_query.JSON_EXPORT_NAME
    operator_path = export_root / md_query.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["read_model_id"] == md_query.READ_MODEL_ID
    assert payload["work_query_receipt"]["normalized_topic"] == "chief"
    assert "OpenClaw Markdown Body Ingest Query" in operator
    assert "Boundary:" in operator
    assert "Next safe move:" in operator
