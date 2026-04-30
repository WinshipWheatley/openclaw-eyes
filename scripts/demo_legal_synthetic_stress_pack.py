#!/usr/bin/env python3
"""Synthetic discovery stress-pack run-through for OpenClaw Legal Lane A."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.cli import main as legal_cli_main


ARTIFACT_TYPE = "openclaw_legal_synthetic_stress_pack"
RUN_ARTIFACT_TYPE = "openclaw_legal_synthetic_stress_pack_run"
DEFAULT_OUTPUT_ROOT = Path("/tmp/openclaw_legal_synthetic_stress_pack_validation")
KNOWN_SEARCH_TOKEN = "stress-omega-77"
MANIFEST_DIRECTORY = ".openclaw-synthetic-stress-pack"
MANIFEST_FILENAME = "manifest.json"
PACK_SCHEMA_VERSION = 1
STAGING_DIRECTORY_NAME = "stress_staging"
VAULT_DIRECTORY_NAME = "legal_vault"
MATTER_DIRECTORY_NAME = "synthetic_stress_matter"

TEXT_NOTE_FILENAME = "stress_evidence_note.txt"
MARKDOWN_NOTE_FILENAME = "stress_timeline_note.md"
TEXT_PDF_FILENAME = "stress_contract_excerpt.pdf"
NO_TEXT_PDF_FILENAME = "stress_image_only_scan.pdf"
CORRUPT_PDF_FILENAME = "stress_corrupt_scan.pdf"
PNG_SCREENSHOT_FILENAME = "stress_text_message_screenshot.png"
UNSUPPORTED_FILENAME = "stress_export.abcxyz"
VIDEO_PLACEHOLDER_FILENAME = "stress_video_placeholder.mp4"
AUDIO_PLACEHOLDER_FILENAME = "stress_audio_placeholder.wav"


def create_synthetic_stress_pack(
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    """Create a synthetic/public-safe stress fixture pack outside the repo."""

    output = Path(output_root).expanduser().resolve(strict=False)
    _require_outside_repo(output)
    staging_dir = output / STAGING_DIRECTORY_NAME
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    _write_synthetic_sources(staging_dir)
    marker_dir = staging_dir / MANIFEST_DIRECTORY
    marker_dir.mkdir()
    manifest = _fixture_manifest()
    manifest_path = marker_dir / MANIFEST_FILENAME
    _write_json(manifest_path, manifest)

    return {
        "artifact_type": ARTIFACT_TYPE,
        "output_root": str(output),
        "staging_dir": str(staging_dir),
        "marker_path": str(marker_dir),
        "manifest_path": str(manifest_path),
        "fixture_files": [str(staging_dir / item["filename"]) for item in manifest["files"]],
        "manifest": manifest,
    }


def run_synthetic_stress_pack_demo(
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    """Run the synthetic stress pack through the existing Legal CLI spine."""

    output = Path(output_root).expanduser().resolve(strict=False)
    _require_outside_repo(output)
    if output.exists():
        shutil.rmtree(output)

    pack = create_synthetic_stress_pack(output)
    staging_dir = Path(pack["staging_dir"])
    vault_root = output / VAULT_DIRECTORY_NAME
    matter_root = vault_root / MATTER_DIRECTORY_NAME

    _run_cli(
        [
            "create-matter",
            "--vault-root",
            str(vault_root),
            "--root",
            str(matter_root),
            "--matter-id",
            "synthetic-stress-pack-v0",
            "--display-name",
            "Synthetic Discovery Stress Pack",
        ]
    )
    imported = _run_cli(
        [
            "import-staging",
            "--vault-root",
            str(vault_root),
            "--root",
            str(matter_root),
            "--staging-dir",
            str(staging_dir),
            "--lane",
            "synthetic",
        ]
    )
    extraction = _run_cli(
        [
            "extract-all",
            "--vault-root",
            str(vault_root),
            "--root",
            str(matter_root),
        ]
    )
    search = _run_cli(
        [
            "search",
            "--vault-root",
            str(vault_root),
            "--root",
            str(matter_root),
            "--query",
            KNOWN_SEARCH_TOKEN,
        ]
    )
    report = _run_cli(
        [
            "report",
            "--vault-root",
            str(vault_root),
            "--root",
            str(matter_root),
            "--query",
            KNOWN_SEARCH_TOKEN,
            "--report-name",
            "synthetic-stress-token-report",
        ]
    )
    review_packet = _run_cli(
        [
            "review-packet",
            "--vault-root",
            str(vault_root),
            "--root",
            str(matter_root),
            "--packet-name",
            "synthetic-stress-review",
        ]
    )
    support_packet = _run_cli(
        [
            "support-packet",
            "--vault-root",
            str(vault_root),
            "--root",
            str(matter_root),
            "--packet-name",
            "synthetic-stress-diagnostics",
        ]
    )
    alternative_methods = _run_cli(
        [
            "alternative-methods",
            "--vault-root",
            str(vault_root),
            "--root",
            str(matter_root),
        ]
    )

    support_packet_text = Path(support_packet["packet_path"]).read_text(
        encoding="utf-8"
    )
    matter_manifest = _read_json(matter_root / "manifest.json")
    status_counts = _normalized_status_counts(extraction["status_counts"])
    actual_status_by_filename = _actual_status_by_filename(extraction["results"])
    status_evaluations = _status_evaluations(
        pack["manifest"],
        actual_status_by_filename,
    )
    alternative_methods_by_filename = _alternative_methods_by_filename(
        matter_manifest,
        alternative_methods,
    )
    alternative_method_evaluations = _alternative_method_evaluations(
        pack["manifest"],
        actual_status_by_filename,
        alternative_methods_by_filename,
    )
    support_packet_checks = _support_packet_checks(
        support_packet_text,
        pack,
        output,
        staging_dir,
        vault_root,
        matter_root,
    )
    product_repo_data_written = False

    stress_pack_passed = all(
        [
            imported["source_count_imported"] == len(pack["manifest"]["files"]),
            all(item["matched"] for item in status_evaluations),
            all(item["matched"] for item in alternative_method_evaluations),
            search["result_count"] >= pack["manifest"]["expected_outcomes"][
                "minimum_search_result_count"
            ],
            all(support_packet_checks.values()),
            product_repo_data_written is False,
        ]
    )

    return {
        "artifact_type": RUN_ARTIFACT_TYPE,
        "fixture_pack": pack,
        "vault_root": str(vault_root),
        "matter_root": str(matter_root),
        "manifest_path": str(matter_root / "manifest.json"),
        "audit_path": str(matter_root / "audit.jsonl"),
        "imported_source_count": imported["source_count_imported"],
        "skipped_directory_count": imported["skipped_directory_count"],
        "source_status_counts": status_counts,
        "actual_status_by_filename": actual_status_by_filename,
        "status_evaluations": status_evaluations,
        "search_query": KNOWN_SEARCH_TOKEN,
        "search_result_count": search["result_count"],
        "report_path": report["report_path"],
        "review_packet_path": review_packet["packet_path"],
        "support_packet_path": support_packet["packet_path"],
        "support_packet_checks": support_packet_checks,
        "alternative_methods_count": alternative_methods["needs_alternative_methods"],
        "alternative_methods_by_filename": alternative_methods_by_filename,
        "alternative_method_evaluations": alternative_method_evaluations,
        "tesseract_available": shutil.which("tesseract") is not None,
        "product_repo_data_written": product_repo_data_written,
        "stress_pack_passed": stress_pack_passed,
    }


def _write_synthetic_sources(staging_dir: Path) -> None:
    (staging_dir / TEXT_NOTE_FILENAME).write_text(
        "Synthetic evidence note for Lane A stress validation. "
        f"Known search token: {KNOWN_SEARCH_TOKEN}. No real matter content.\n",
        encoding="utf-8",
    )
    (staging_dir / MARKDOWN_NOTE_FILENAME).write_text(
        "# Synthetic Timeline Note\n\n"
        f"- 2026-04-30 fake event references {KNOWN_SEARCH_TOKEN}.\n"
        "- Public-safe stress fixture only.\n",
        encoding="utf-8",
    )
    _write_text_layer_pdf(
        staging_dir / TEXT_PDF_FILENAME,
        f"{KNOWN_SEARCH_TOKEN} synthetic contract excerpt marker",
    )
    _write_no_text_pdf(staging_dir / NO_TEXT_PDF_FILENAME)
    (staging_dir / CORRUPT_PDF_FILENAME).write_bytes(
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Broken true >>\n"
    )
    _write_fake_text_message_png(staging_dir / PNG_SCREENSHOT_FILENAME)
    (staging_dir / UNSUPPORTED_FILENAME).write_bytes(
        b"synthetic unsupported export payload\n"
    )
    (staging_dir / VIDEO_PLACEHOLDER_FILENAME).write_bytes(
        b"\x00\x00\x00\x18ftypmp42synthetic video placeholder\n"
    )
    (staging_dir / AUDIO_PLACEHOLDER_FILENAME).write_bytes(
        b"RIFF\x24\x00\x00\x00WAVEfmt synthetic audio placeholder\n"
    )


def _fixture_manifest() -> dict[str, Any]:
    return {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": PACK_SCHEMA_VERSION,
        "lane": "synthetic",
        "public_safe": True,
        "real_matter_compatible": False,
        "marker": MANIFEST_DIRECTORY,
        "known_search_token": KNOWN_SEARCH_TOKEN,
        "files": [
            _file_expectation(
                TEXT_NOTE_FILENAME,
                "plain text evidence-style note",
                "extracted",
                [KNOWN_SEARCH_TOKEN],
                None,
            ),
            _file_expectation(
                MARKDOWN_NOTE_FILENAME,
                "timeline-style markdown note",
                "extracted",
                [KNOWN_SEARCH_TOKEN],
                None,
            ),
            _file_expectation(
                TEXT_PDF_FILENAME,
                "text-layer PDF fixture",
                "extracted",
                [KNOWN_SEARCH_TOKEN],
                None,
            ),
            _file_expectation(
                NO_TEXT_PDF_FILENAME,
                "valid no-text PDF fixture",
                "no_text",
                [],
                "ocr_module_needed",
            ),
            _file_expectation(
                CORRUPT_PDF_FILENAME,
                "malformed PDF failure-safety fixture",
                "failed",
                [],
                "local_extraction_failed",
            ),
            _file_expectation(
                PNG_SCREENSHOT_FILENAME,
                "synthetic fake text-message screenshot PNG",
                "ocr_environment_dependent",
                [],
                "ocr_runtime_dependent",
                expected_status_options=["extracted", "unsupported", "no_text", "failed"],
            ),
            _file_expectation(
                UNSUPPORTED_FILENAME,
                "unsupported fake export extension",
                "unsupported",
                [],
                "unsupported_file_type",
            ),
            _file_expectation(
                VIDEO_PLACEHOLDER_FILENAME,
                "tiny unsupported video-like placeholder",
                "unsupported",
                [],
                "unsupported_file_type",
            ),
            _file_expectation(
                AUDIO_PLACEHOLDER_FILENAME,
                "tiny unsupported audio-like placeholder",
                "unsupported",
                [],
                "unsupported_file_type",
            ),
        ],
        "expected_outcomes": {
            "source_count": 9,
            "minimum_search_result_count": 3,
            "minimum_extracted_count": 3,
            "minimum_no_text_count": 1,
            "minimum_unsupported_count": 3,
            "minimum_failed_count": 1,
            "support_packet_excludes_source_text": True,
            "support_packet_excludes_sensitive_filenames": True,
            "support_packet_excludes_private_paths": True,
            "product_repo_data_written": False,
        },
    }


def _file_expectation(
    filename: str,
    purpose: str,
    expected_status: str,
    expected_searchable_tokens: list[str],
    expected_alternative_methods_category: str | None,
    *,
    expected_status_options: list[str] | None = None,
) -> dict[str, Any]:
    expectation = {
        "filename": filename,
        "purpose": purpose,
        "expected_status": expected_status,
        "expected_searchable_tokens": expected_searchable_tokens,
        "expected_alternative_methods_category": expected_alternative_methods_category,
        "expected_support_packet_redaction": {
            "source_text_excluded": True,
            "sensitive_filename_excluded": True,
            "private_paths_excluded": True,
        },
    }
    if expected_status_options is not None:
        expectation["expected_status_options"] = expected_status_options
    return expectation


def _actual_status_by_filename(results: list[dict[str, Any]]) -> dict[str, str]:
    return {
        result["original_filename"]: str(result.get("status", "unknown"))
        for result in results
    }


def _status_evaluations(
    manifest: dict[str, Any],
    actual_status_by_filename: dict[str, str],
) -> list[dict[str, Any]]:
    evaluations = []
    for file_info in manifest["files"]:
        filename = file_info["filename"]
        actual_status = actual_status_by_filename.get(filename)
        expected_options = file_info.get("expected_status_options")
        if expected_options:
            matched = actual_status in expected_options
        else:
            matched = actual_status == file_info["expected_status"]
        evaluations.append(
            {
                "filename": filename,
                "purpose": file_info["purpose"],
                "expected_status": file_info["expected_status"],
                "expected_status_options": expected_options,
                "actual_status": actual_status,
                "matched": matched,
            }
        )
    return evaluations


def _alternative_methods_by_filename(
    matter_manifest: dict[str, Any],
    alternative_methods: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    source_index_to_filename = {
        index: source["original_filename"]
        for index, source in enumerate(matter_manifest.get("sources", []), start=1)
    }
    mapped = {}
    for item in alternative_methods.get("items", []):
        filename = source_index_to_filename.get(item.get("source_index"))
        if not filename:
            continue
        mapped[filename] = {
            "status": item.get("status"),
            "file_extension": item.get("file_extension"),
            "reason_category": item.get("reason_category"),
            "local_capability_state": item.get("local_capability_state"),
            "local_capability_kind": item.get("local_capability_kind"),
            "local_capability_reason_category": item.get(
                "local_capability_reason_category"
            ),
            "request_feature_state": item.get("request_feature_state"),
        }
    return mapped


def _alternative_method_evaluations(
    manifest: dict[str, Any],
    actual_status_by_filename: dict[str, str],
    alternative_methods_by_filename: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    evaluations = []
    for file_info in manifest["files"]:
        filename = file_info["filename"]
        expected_category = file_info["expected_alternative_methods_category"]
        actual_status = actual_status_by_filename.get(filename)
        actual = alternative_methods_by_filename.get(filename)
        matched = _alternative_category_matches(
            expected_category,
            actual_status,
            actual,
        )
        evaluations.append(
            {
                "filename": filename,
                "expected_alternative_methods_category": expected_category,
                "actual_status": actual_status,
                "actual_reason_category": None if actual is None else actual.get("reason_category"),
                "actual_local_capability_reason_category": (
                    None
                    if actual is None
                    else actual.get("local_capability_reason_category")
                ),
                "matched": matched,
            }
        )
    return evaluations


def _alternative_category_matches(
    expected_category: str | None,
    actual_status: str | None,
    actual: dict[str, Any] | None,
) -> bool:
    if expected_category is None:
        return actual is None
    if expected_category == "ocr_runtime_dependent":
        if actual_status == "extracted":
            return actual is None
        if actual is None:
            return False
        categories = _actual_categories(actual)
        return bool(
            categories
            & {
                "ocr_module_needed",
                "ocr_module_not_installed",
                "ocr_process_failed",
                "ocr_no_text",
                "no_extractable_text",
            }
        )
    if actual is None:
        return False
    categories = _actual_categories(actual)
    if expected_category == "local_extraction_failed":
        return bool(
            categories
            & {
                "local_extraction_failed",
                "extraction_failed",
                "installed_handler_failed",
            }
        )
    return expected_category in categories


def _actual_categories(actual: dict[str, Any]) -> set[str]:
    return {
        value
        for value in (
            actual.get("reason_category"),
            actual.get("local_capability_reason_category"),
        )
        if isinstance(value, str) and value
    }


def _support_packet_checks(
    support_packet_text: str,
    pack: dict[str, Any],
    output: Path,
    staging_dir: Path,
    vault_root: Path,
    matter_root: Path,
) -> dict[str, bool]:
    filenames = [Path(path).name for path in pack["fixture_files"]]
    return {
        "known_token_excluded": KNOWN_SEARCH_TOKEN not in support_packet_text,
        "source_filenames_excluded": all(name not in support_packet_text for name in filenames),
        "private_paths_excluded": all(
            str(path) not in support_packet_text
            for path in (output, staging_dir, vault_root, matter_root)
        ),
    }


def _normalized_status_counts(status_counts: dict[str, int]) -> dict[str, int]:
    normalized = {
        "extracted": 0,
        "unsupported": 0,
        "no_text": 0,
        "failed": 0,
        "pending": 0,
    }
    normalized.update(status_counts)
    return normalized


def _write_text_layer_pdf(path: Path, text: str) -> None:
    escaped_text = _pdf_escape(text)
    content = f"BT /F1 24 Tf 72 720 Td ({escaped_text}) Tj ET"
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            "3 0 obj\n"
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\n"
            "endobj\n"
        ),
        "4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        f"5 0 obj\n<< /Length {len(content)} >>\nstream\n{content}\nendstream\nendobj\n",
    ]
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf.encode("latin-1")))
        pdf += obj
    xref_offset = len(pdf.encode("latin-1"))
    pdf += "xref\n0 6\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += (
        "trailer\n<< /Size 6 /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )
    path.write_bytes(pdf.encode("latin-1"))


def _write_no_text_pdf(path: Path) -> None:
    content = ""
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            "3 0 obj\n"
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << >> /Contents 4 0 R >>\n"
            "endobj\n"
        ),
        f"4 0 obj\n<< /Length {len(content)} >>\nstream\n{content}\nendstream\nendobj\n",
    ]
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf.encode("latin-1")))
        pdf += obj
    xref_offset = len(pdf.encode("latin-1"))
    pdf += "xref\n0 5\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += (
        "trailer\n<< /Size 5 /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )
    path.write_bytes(pdf.encode("latin-1"))


def _write_fake_text_message_png(path: Path) -> None:
    width = 180
    height = 84
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            red, green, blue = 246, 248, 250
            if 10 <= x <= 132 and 10 <= y <= 34:
                red, green, blue = 225, 239, 255
            if 40 <= x <= 170 and 48 <= y <= 72:
                red, green, blue = 232, 232, 232
            if _text_like_pixel(x, y):
                red, green, blue = 24, 32, 42
            row.extend((red, green, blue))
        rows.append(b"\x00" + bytes(row))
    raw = b"".join(rows)
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += _png_chunk(b"IDAT", zlib.compress(raw))
    png += _png_chunk(b"IEND", b"")
    path.write_bytes(png)


def _text_like_pixel(x: int, y: int) -> bool:
    first_line = 16 <= x <= 118 and 17 <= y <= 21 and (x // 4) % 3 != 1
    second_line = 16 <= x <= 94 and 25 <= y <= 29 and (x // 5) % 3 != 2
    third_line = 50 <= x <= 152 and 55 <= y <= 59 and (x // 4) % 3 != 0
    fourth_line = 50 <= x <= 136 and 63 <= y <= 67 and (x // 5) % 4 != 1
    return first_line or second_line or third_line or fourth_line


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _run_cli(args: list[str]) -> dict[str, Any]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = legal_cli_main(args)
    if code != 0:
        raise RuntimeError(
            f"legal CLI failed ({code}): {' '.join(args)}\n{stderr.getvalue()}"
        )
    return json.loads(stdout.getvalue())


def _require_outside_repo(path: Path) -> None:
    resolved = path.expanduser().resolve(strict=False)
    repo_root = ROOT.resolve(strict=False)
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return
    raise ValueError(f"stress-pack output must be outside product repo: {resolved}")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Create or run a synthetic OpenClaw Legal stress pack."
    )
    parser.add_argument("output_root", nargs="?", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Only create the synthetic stress pack; do not import or extract it.",
    )
    args = parser.parse_args(argv[1:])
    if args.generate_only:
        payload = create_synthetic_stress_pack(args.output_root)
    else:
        payload = run_synthetic_stress_pack_demo(args.output_root)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))