#!/usr/bin/env python3
"""Synthetic known-answer fixture pack for OpenClaw Legal Lane A."""

from __future__ import annotations

import argparse
import base64
import contextlib
import io
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.cli import main as legal_cli_main


ARTIFACT_TYPE = "openclaw_legal_known_answer_fixture_pack"
DEFAULT_OUTPUT_ROOT = Path("/tmp/openclaw_legal_known_answer_fixtures")
FIXTURE_MARKER_DIRECTORY = ".openclaw-synthetic-fixture-pack"
KNOWN_SEARCH_TERM = "fixture-omega-42"
MANIFEST_FILENAME = "manifest.json"
PACK_SCHEMA_VERSION = 1
STAGING_DIRECTORY_NAME = "fixture_staging"
VAULT_DIRECTORY_NAME = "legal_vault"
MATTER_DIRECTORY_NAME = "known_answer_matter"
TEXT_FIXTURE_FILENAME = "known_answer_note.txt"
IMAGE_FIXTURE_FILENAME = "synthetic_scan.png"
UNSUPPORTED_FIXTURE_FILENAME = "unsupported_payload.openclawfake"

_ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def create_known_answer_fixture_pack(
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    """Create a synthetic/public-safe fixture pack outside the product repo."""

    output = Path(output_root).expanduser().resolve(strict=False)
    _require_outside_repo(output)
    staging_dir = output / STAGING_DIRECTORY_NAME
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    marker_dir = staging_dir / FIXTURE_MARKER_DIRECTORY
    marker_dir.mkdir()

    text_fixture = staging_dir / TEXT_FIXTURE_FILENAME
    text_fixture.write_text(
        "Known-answer synthetic fixture for OpenClaw Legal Lane A. "
        f"Search token: {KNOWN_SEARCH_TERM}. No real matter content.\n",
        encoding="utf-8",
    )
    image_fixture = staging_dir / IMAGE_FIXTURE_FILENAME
    image_fixture.write_bytes(base64.b64decode(_ONE_PIXEL_PNG))
    unsupported_fixture = staging_dir / UNSUPPORTED_FIXTURE_FILENAME
    unsupported_fixture.write_bytes(b"synthetic unsupported fixture payload\n")

    manifest = _fixture_manifest()
    manifest_path = marker_dir / MANIFEST_FILENAME
    _write_json(manifest_path, manifest)
    return {
        "artifact_type": ARTIFACT_TYPE,
        "output_root": str(output),
        "staging_dir": str(staging_dir),
        "marker_path": str(marker_dir),
        "manifest_path": str(manifest_path),
        "fixture_files": [
            str(text_fixture),
            str(image_fixture),
            str(unsupported_fixture),
        ],
        "manifest": manifest,
    }


def run_known_answer_fixture_demo(
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    """Run the known-answer fixture pack through the local Legal CLI spine."""

    output = Path(output_root).expanduser().resolve(strict=False)
    _require_outside_repo(output)
    _reset_generated_workflow_dirs(output)
    pack = create_known_answer_fixture_pack(output)
    staging_dir = Path(pack["staging_dir"])
    vault_root = output / VAULT_DIRECTORY_NAME
    matter_root = vault_root / MATTER_DIRECTORY_NAME
    expected = pack["manifest"]["expected_outcomes"]

    _run_cli(
        [
            "create-matter",
            "--vault-root",
            str(vault_root),
            "--root",
            str(matter_root),
            "--matter-id",
            "known-answer-fixture-v0",
            "--display-name",
            "Synthetic Known-Answer Fixture Pack",
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
            KNOWN_SEARCH_TERM,
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
            "known-answer-fixtures",
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

    status_counts = _normalized_status_counts(extraction["status_counts"])
    support_packet_text = Path(support_packet["packet_path"]).read_text(encoding="utf-8")
    tesseract_available = shutil.which("tesseract") is not None
    ocr_needed_count = _count_ocr_needed(alternative_methods)
    checks = {
        "source_count_matches_manifest": (
            imported["source_count_imported"] == expected["source_count"]
        ),
        "searchable_terms_found": search["result_count"] > 0,
        "support_packet_source_text_excluded": all(
            term not in support_packet_text for term in expected["searchable_terms"]
        ),
        "support_packet_private_paths_excluded": all(
            str(path) not in support_packet_text
            for path in (output, staging_dir, vault_root, matter_root)
        ),
        "ocr_needed_count_matches_when_tesseract_unavailable": (
            None
            if tesseract_available
            else ocr_needed_count
            == expected["ocr_needed_count_when_tesseract_unavailable"]
        ),
    }
    boolean_checks = [value for value in checks.values() if isinstance(value, bool)]
    return {
        "artifact_type": "openclaw_legal_known_answer_fixture_run",
        "fixture_pack": pack,
        "vault_root": str(vault_root),
        "matter_root": str(matter_root),
        "manifest_path": str(matter_root / "manifest.json"),
        "imported_source_count": imported["source_count_imported"],
        "skipped_directory_count": imported["skipped_directory_count"],
        "source_status_counts": status_counts,
        "extracted_count": status_counts.get("extracted", 0),
        "unsupported_count": status_counts.get("unsupported", 0),
        "no_text_count": status_counts.get("no_text", 0),
        "failed_count": status_counts.get("failed", 0),
        "search_result_count": search["result_count"],
        "support_packet_path": support_packet["packet_path"],
        "alternative_methods_count": alternative_methods["needs_alternative_methods"],
        "ocr_needed_count": ocr_needed_count,
        "tesseract_available": tesseract_available,
        "known_answer_checks": checks,
        "known_answer_passed": all(boolean_checks),
        "product_repo_data_written": False,
    }


def _fixture_manifest() -> dict[str, Any]:
    return {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": PACK_SCHEMA_VERSION,
        "lane": "synthetic",
        "public_safe": True,
        "real_matter_compatible": False,
        "marker": FIXTURE_MARKER_DIRECTORY,
        "files": [
            {
                "filename": TEXT_FIXTURE_FILENAME,
                "kind": "known_searchable_text",
                "expected_status": "extracted",
                "expected_searchable_terms": [KNOWN_SEARCH_TERM],
            },
            {
                "filename": IMAGE_FIXTURE_FILENAME,
                "kind": "image_ocr_fixture",
                "expected_status_when_tesseract_unavailable": "unsupported",
                "expected_reason_when_tesseract_unavailable": "ocr_module_not_installed",
            },
            {
                "filename": UNSUPPORTED_FIXTURE_FILENAME,
                "kind": "unsupported_fake_extension",
                "expected_status": "unsupported",
            },
        ],
        "expected_outcomes": {
            "source_count": 3,
            "extracted_count": 1,
            "unsupported_count": 1,
            "extracted_count_when_tesseract_unavailable": 1,
            "unsupported_count_when_tesseract_unavailable": 2,
            "ocr_needed_count_when_tesseract_unavailable": 1,
            "searchable_terms": [KNOWN_SEARCH_TERM],
            "support_packet_excludes_source_text": True,
            "support_packet_excludes_private_paths": True,
        },
    }


def _reset_generated_workflow_dirs(output: Path) -> None:
    for name in (STAGING_DIRECTORY_NAME, VAULT_DIRECTORY_NAME):
        target = output / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


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


def _count_ocr_needed(alternative_methods: dict[str, Any]) -> int:
    count = 0
    for item in alternative_methods.get("items", []):
        actions = item.get("available_actions", [])
        if (
            item.get("reason_category") == "ocr_module_needed"
            or item.get("local_capability_reason_category")
            == "ocr_module_not_installed"
            or "ocr_module_needed" in actions
        ):
            count += 1
    return count


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
    raise ValueError(f"fixture output must be outside product repo: {resolved}")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Create or run synthetic OpenClaw Legal known-answer fixtures."
    )
    parser.add_argument("output_root", nargs="?", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Only create the fixture pack; do not import or extract it.",
    )
    args = parser.parse_args(argv[1:])
    if args.generate_only:
        payload = create_known_answer_fixture_pack(args.output_root)
    else:
        payload = run_known_answer_fixture_demo(args.output_root)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))