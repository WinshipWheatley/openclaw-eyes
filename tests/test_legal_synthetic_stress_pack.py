from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.demo_legal_synthetic_stress_pack import (
    AUDIO_PLACEHOLDER_FILENAME,
    CORRUPT_PDF_FILENAME,
    KNOWN_SEARCH_TOKEN,
    MARKDOWN_NOTE_FILENAME,
    NO_TEXT_PDF_FILENAME,
    PNG_SCREENSHOT_FILENAME,
    TEXT_NOTE_FILENAME,
    TEXT_PDF_FILENAME,
    UNSUPPORTED_FILENAME,
    VIDEO_PLACEHOLDER_FILENAME,
    create_synthetic_stress_pack,
    run_synthetic_stress_pack_demo,
)


PRODUCT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_synthetic_stress_pack_generation_is_public_safe(tmp_path: Path) -> None:
    pack = create_synthetic_stress_pack(tmp_path / "stress-pack")
    staging_dir = Path(pack["staging_dir"])
    manifest_path = Path(pack["manifest_path"])
    manifest = _read_json(manifest_path)

    assert not staging_dir.resolve().is_relative_to(PRODUCT_REPO_ROOT)
    assert manifest["artifact_type"] == "openclaw_legal_synthetic_stress_pack"
    assert manifest["lane"] == "synthetic"
    assert manifest["public_safe"] is True
    assert manifest["real_matter_compatible"] is False
    assert manifest["known_search_token"] == KNOWN_SEARCH_TOKEN
    assert manifest["expected_outcomes"]["source_count"] == 9
    assert {path.name for path in staging_dir.iterdir() if path.is_file()} == {
        TEXT_NOTE_FILENAME,
        MARKDOWN_NOTE_FILENAME,
        TEXT_PDF_FILENAME,
        NO_TEXT_PDF_FILENAME,
        CORRUPT_PDF_FILENAME,
        PNG_SCREENSHOT_FILENAME,
        UNSUPPORTED_FILENAME,
        VIDEO_PLACEHOLDER_FILENAME,
        AUDIO_PLACEHOLDER_FILENAME,
    }
    assert (staging_dir / PNG_SCREENSHOT_FILENAME).read_bytes().startswith(b"\x89PNG")
    assert KNOWN_SEARCH_TOKEN in (staging_dir / TEXT_NOTE_FILENAME).read_text(
        encoding="utf-8"
    )
    assert KNOWN_SEARCH_TOKEN in (staging_dir / MARKDOWN_NOTE_FILENAME).read_text(
        encoding="utf-8"
    )


def test_synthetic_stress_pack_runs_end_to_end_with_missing_tesseract(
    tmp_path: Path,
) -> None:
    real_which = shutil.which

    def fake_which(command: str) -> str | None:
        if command == "tesseract":
            return None
        return real_which(command)

    with patch("legal.local_ingestion.shutil.which", side_effect=fake_which), patch(
        "legal.local_capability_policy.shutil.which",
        side_effect=fake_which,
    ), patch(
        "scripts.demo_legal_synthetic_stress_pack.shutil.which",
        side_effect=fake_which,
    ):
        result = run_synthetic_stress_pack_demo(tmp_path / "stress-run")

    vault_root = Path(result["vault_root"])
    matter_root = Path(result["matter_root"])
    manifest_path = Path(result["manifest_path"])
    report_path = Path(result["report_path"])
    review_packet_path = Path(result["review_packet_path"])
    support_packet_path = Path(result["support_packet_path"])

    assert not matter_root.resolve().is_relative_to(PRODUCT_REPO_ROOT)
    assert vault_root == tmp_path / "stress-run" / "legal_vault"
    assert matter_root == vault_root / "synthetic_stress_matter"
    assert manifest_path.is_file()
    assert report_path.is_file()
    assert review_packet_path.is_dir()
    assert support_packet_path.is_file()
    assert result["product_repo_data_written"] is False
    assert result["stress_pack_passed"] is True
    assert result["imported_source_count"] == 9
    assert result["skipped_directory_count"] == 1
    assert result["source_status_counts"] == {
        "extracted": 3,
        "failed": 1,
        "no_text": 1,
        "pending": 0,
        "unsupported": 4,
    }
    assert result["actual_status_by_filename"] == {
        TEXT_NOTE_FILENAME: "extracted",
        MARKDOWN_NOTE_FILENAME: "extracted",
        TEXT_PDF_FILENAME: "extracted",
        NO_TEXT_PDF_FILENAME: "no_text",
        CORRUPT_PDF_FILENAME: "failed",
        PNG_SCREENSHOT_FILENAME: "unsupported",
        UNSUPPORTED_FILENAME: "unsupported",
        VIDEO_PLACEHOLDER_FILENAME: "unsupported",
        AUDIO_PLACEHOLDER_FILENAME: "unsupported",
    }
    assert result["search_result_count"] >= 3
    assert result["support_packet_checks"] == {
        "known_token_excluded": True,
        "private_paths_excluded": True,
        "source_filenames_excluded": True,
    }
    assert result["alternative_methods_count"] == 6
    assert all(item["matched"] for item in result["status_evaluations"])
    assert all(item["matched"] for item in result["alternative_method_evaluations"])

    alternative_methods = result["alternative_methods_by_filename"]
    assert alternative_methods[NO_TEXT_PDF_FILENAME]["reason_category"] == "ocr_module_needed"
    assert alternative_methods[CORRUPT_PDF_FILENAME]["reason_category"] in {
        "local_extraction_failed",
        "extraction_failed",
    }
    assert alternative_methods[PNG_SCREENSHOT_FILENAME]["reason_category"] == "ocr_module_needed"
    assert alternative_methods[UNSUPPORTED_FILENAME]["reason_category"] == "unsupported_file_type"
    assert alternative_methods[VIDEO_PLACEHOLDER_FILENAME]["reason_category"] == "unsupported_file_type"
    assert alternative_methods[AUDIO_PLACEHOLDER_FILENAME]["reason_category"] == "unsupported_file_type"

    support_packet_text = support_packet_path.read_text(encoding="utf-8")
    assert KNOWN_SEARCH_TOKEN not in support_packet_text
    assert TEXT_NOTE_FILENAME not in support_packet_text
    assert str(matter_root) not in support_packet_text