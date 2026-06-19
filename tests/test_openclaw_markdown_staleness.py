import json
from pathlib import Path

import openclaw_markdown_staleness as staleness
from scripts.export_openclaw_markdown_staleness import main as export_main


FIXED_NOW = "2026-06-18T23:44:00+00:00"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "openclaw"
    repo.mkdir()
    _write(repo / "OPENCLAW_RUNTIME.md", "# Runtime Law\n\nCanonical runtime law for OpenClaw.\n")
    _write(repo / "USER.md", "# User\n\nOperator identity and preferences.\n")
    _write(
        repo / "docs" / "legacy_plan.md",
        "# Legacy Plan\n\nThis deprecated plan is stale and superseded by the current work queue.\n",
    )
    _write(
        repo / "docs" / "active_queue.md",
        "# Active Queue\n\nCurrent open work queue with TODO markers.\n",
    )
    _write(
        repo / "docs" / "planning" / "legal" / "old_secret.md",
        "# Legal Discovery\n\nLEGAL_DISCOVERY_BODY_SHOULD_NOT_APPEAR stale deprecated superseded\n",
    )
    _write(repo / "finance" / "legacy_private.md", "# Finance\n\nFINANCE_BODY_SHOULD_NOT_APPEAR\n")
    _write(repo / "generated" / "read_models" / "sample_OPERATOR.md", "# Sample Operator\n\nGenerated status.\n")
    return repo


def _build(repo: Path) -> dict:
    return staleness.build_openclaw_markdown_staleness(
        repo_root=repo,
        generated_at=FIXED_NOW,
        max_docs=20,
        max_body_bytes=4096,
    )


def test_staleness_candidates_preserve_bounded_ingest_and_authority_boundary(tmp_path):
    repo = _sample_repo(tmp_path)
    payload = _build(repo)
    text = json.dumps(payload, sort_keys=True)
    candidates = {row["relative_path"]: row for row in payload["candidates"]}

    assert payload["schema_version"] == staleness.SCHEMA_VERSION
    assert payload["contract_status"] == "advisory_markdown_staleness_candidates"
    assert candidates["OPENCLAW_RUNTIME.md"]["staleness_status"] == "current_canonical_root"
    assert candidates["docs/legacy_plan.md"]["staleness_status"] == "stale_or_superseded_candidate"
    assert candidates["generated/read_models/sample_OPERATOR.md"]["staleness_status"] == "generated_read_model_candidate"
    assert "docs/planning/legal/old_secret.md" not in candidates
    assert "finance/legacy_private.md" not in candidates
    assert "LEGAL_DISCOVERY_BODY_SHOULD_NOT_APPEAR" not in text
    assert "FINANCE_BODY_SHOULD_NOT_APPEAR" not in text
    assert payload["summary"]["full_body_exported"] is False
    assert payload["summary"]["action_authority_granted"] is False
    assert payload["authority_boundary"]["file_move_allowed"] is False
    assert payload["machine_proof"]["truth_promotion_allowed"] is False


def test_staleness_export_is_deterministic_and_review_queue_is_signal_ordered(tmp_path):
    repo = _sample_repo(tmp_path)
    first = _build(repo)
    second = _build(repo)
    review_paths = [row["relative_path"] for row in first["review_queue"]]

    assert staleness.stable_json(first) == staleness.stable_json(second)
    assert review_paths[0] == "docs/legacy_plan.md"
    assert first["summary"]["stale_candidate_count"] == 1
    assert first["machine_proof"]["candidate_count_matches_source_documents"] is True
    assert "source_body" not in staleness.stable_json(first)
    assert "extracted_text" not in staleness.stable_json(first)


def test_staleness_exporter_writes_json_and_operator_markdown(tmp_path):
    repo = _sample_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    result = export_main(
        [
            "--repo-root",
            repo.as_posix(),
            "--export-root",
            export_root.as_posix(),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "summary",
        ]
    )

    assert result == 0
    json_path = export_root / staleness.JSON_EXPORT_NAME
    operator_path = export_root / staleness.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["read_model_id"] == staleness.READ_MODEL_ID
    assert payload["summary"]["document_count"] == 5
    assert payload["summary"]["file_mutation_allowed"] is False
    assert "OpenClaw Markdown Staleness Candidates" in operator
    assert "Boundary:" in operator
