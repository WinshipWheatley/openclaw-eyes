from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legal.local_ingestion import extract_source_text
from legal.local_search import search_extracted_text
from legal.matter_workspace import create_matter_workspace, import_staging_sources
from scripts.demo_legal_known_answer_fixtures import (
    FIXTURE_MARKER_DIRECTORY,
    IMAGE_FIXTURE_FILENAME,
    KNOWN_SEARCH_TERM,
    TEXT_FIXTURE_FILENAME,
    UNSUPPORTED_FIXTURE_FILENAME,
    create_known_answer_fixture_pack,
    run_known_answer_fixture_demo,
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _import_pack_into_synthetic_matter(tmp_path: Path) -> tuple[dict, Path, Path, dict]:
    pack = create_known_answer_fixture_pack(tmp_path / "known-answer-output")
    vault = tmp_path / "legal-vault"
    matter_root = vault / "matter"
    create_matter_workspace(
        matter_root,
        "fixture-matter",
        "Synthetic Fixture Matter",
        allowed_vault_roots=[vault],
    )
    imported = import_staging_sources(
        matter_root,
        pack["staging_dir"],
        lane="synthetic",
        allowed_vault_roots=[vault],
    )
    return pack, vault, matter_root, imported


def test_fixture_pack_generation_creates_public_safe_manifest_and_files(
    tmp_path: Path,
) -> None:
    pack = create_known_answer_fixture_pack(tmp_path / "known-answer-output")
    staging_dir = Path(pack["staging_dir"])
    marker_dir = staging_dir / FIXTURE_MARKER_DIRECTORY
    manifest = _read_json(Path(pack["manifest_path"]))

    assert not str(staging_dir).startswith("/home/openclaw")
    assert marker_dir.is_dir()
    assert Path(pack["manifest_path"]).parent == marker_dir
    assert manifest["artifact_type"] == "openclaw_legal_known_answer_fixture_pack"
    assert manifest["lane"] == "synthetic"
    assert manifest["public_safe"] is True
    assert manifest["real_matter_compatible"] is False
    assert manifest["marker"] == FIXTURE_MARKER_DIRECTORY
    assert manifest["expected_outcomes"]["source_count"] == 3
    assert manifest["expected_outcomes"]["extracted_count"] == 1
    assert manifest["expected_outcomes"]["unsupported_count"] == 1
    assert manifest["expected_outcomes"]["searchable_terms"] == [KNOWN_SEARCH_TERM]
    assert {path.name for path in staging_dir.iterdir() if path.is_file()} == {
        TEXT_FIXTURE_FILENAME,
        IMAGE_FIXTURE_FILENAME,
        UNSUPPORTED_FIXTURE_FILENAME,
    }
    assert (staging_dir / TEXT_FIXTURE_FILENAME).read_text(encoding="utf-8").find(
        KNOWN_SEARCH_TERM
    ) >= 0
    assert (staging_dir / IMAGE_FIXTURE_FILENAME).read_bytes().startswith(b"\x89PNG")


def test_generated_pack_imports_under_synthetic_lane(tmp_path: Path) -> None:
    pack, _vault, matter_root, imported = _import_pack_into_synthetic_matter(tmp_path)
    expected = pack["manifest"]["expected_outcomes"]
    matter_manifest = _read_json(matter_root / "manifest.json")

    assert imported["lane"] == "synthetic"
    assert imported["import_context"] == "synthetic"
    assert imported["source_count_imported"] == expected["source_count"]
    assert imported["skipped_directory_count"] == 1
    assert {source["original_filename"] for source in matter_manifest["sources"]} == {
        TEXT_FIXTURE_FILENAME,
        IMAGE_FIXTURE_FILENAME,
        UNSUPPORTED_FIXTURE_FILENAME,
    }
    assert {source["staging_import_context"] for source in matter_manifest["sources"]} == {
        "synthetic"
    }


def test_generated_pack_is_rejected_under_real_matter_lane(tmp_path: Path) -> None:
    pack = create_known_answer_fixture_pack(tmp_path / "known-answer-output")
    vault = tmp_path / "legal-vault"
    matter_root = vault / "matter"
    create_matter_workspace(
        matter_root,
        "matter",
        "Matter",
        allowed_vault_roots=[vault],
    )

    with pytest.raises(ValueError, match="synthetic fixture pack"):
        import_staging_sources(
            matter_root,
            pack["staging_dir"],
            lane="real-matter",
            allowed_vault_roots=[vault],
        )

    assert _read_json(matter_root / "manifest.json")["sources"] == []


def test_known_answer_workflow_with_missing_tesseract_matches_manifest(
    tmp_path: Path,
) -> None:
    with patch("legal.local_ingestion.shutil.which", return_value=None), patch(
        "legal.local_capability_policy.shutil.which",
        return_value=None,
    ), patch("scripts.demo_legal_known_answer_fixtures.shutil.which", return_value=None):
        summary = run_known_answer_fixture_demo(tmp_path / "known-answer-run")

    expected = summary["fixture_pack"]["manifest"]["expected_outcomes"]
    support_packet_text = Path(summary["support_packet_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["known_answer_passed"] is True
    assert summary["imported_source_count"] == expected["source_count"]
    assert (
        summary["extracted_count"]
        == expected["extracted_count_when_tesseract_unavailable"]
    )
    assert (
        summary["unsupported_count"]
        == expected["unsupported_count_when_tesseract_unavailable"]
    )
    assert (
        summary["ocr_needed_count"]
        == expected["ocr_needed_count_when_tesseract_unavailable"]
    )
    assert summary["search_result_count"] == 1
    assert KNOWN_SEARCH_TERM not in support_packet_text
    assert str(Path(summary["fixture_pack"]["staging_dir"])) not in support_packet_text
    assert str(Path(summary["matter_root"])) not in support_packet_text
    assert summary["known_answer_checks"] == {
        "source_count_matches_manifest": True,
        "searchable_terms_found": True,
        "support_packet_source_text_excluded": True,
        "support_packet_private_paths_excluded": True,
        "ocr_needed_count_matches_when_tesseract_unavailable": True,
    }


def test_expected_searchable_term_is_found_after_text_extraction(
    tmp_path: Path,
) -> None:
    _pack, vault, matter_root, imported = _import_pack_into_synthetic_matter(tmp_path)
    text_source = next(
        source
        for source in imported["sources"]
        if source["original_filename"] == TEXT_FIXTURE_FILENAME
    )

    extract_source_text(
        matter_root,
        text_source["source_id"],
        allowed_vault_roots=[vault],
    )
    results = search_extracted_text(
        matter_root,
        KNOWN_SEARCH_TERM,
        allowed_vault_roots=[vault],
    )

    assert len(results) == 1
    assert results[0]["source_id"] == text_source["source_id"]
    assert results[0]["match_count"] == 1


def test_image_fixture_has_deterministic_mocked_ocr_success(tmp_path: Path) -> None:
    _pack, vault, matter_root, imported = _import_pack_into_synthetic_matter(tmp_path)
    image_source = next(
        source
        for source in imported["sources"]
        if source["original_filename"] == IMAGE_FIXTURE_FILENAME
    )
    completed = subprocess.CompletedProcess(
        ["tesseract"],
        0,
        stdout="Mocked fixture image OCR text\n",
        stderr="",
    )

    with patch("legal.local_ingestion.shutil.which", return_value="/usr/bin/tesseract"), patch(
        "legal.local_ingestion.subprocess.run",
        return_value=completed,
    ):
        result = extract_source_text(
            matter_root,
            image_source["source_id"],
            allowed_vault_roots=[vault],
        )

    assert result["status"] == "extracted"
    assert result["extractor"] == "tesseract_ocr_v0"
    extracted_text = Path(result["extracted_path"]).read_text(encoding="utf-8")
    assert extracted_text.startswith("[Extracted via local OCR]\n\n")
    assert "Mocked fixture image OCR text" in extracted_text