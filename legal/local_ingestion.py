"""Local-only text extraction for legal matter workspaces.

This module is deliberately narrow: it reads registered `.txt` and `.md`
sources from a matter workspace and writes deterministic extracted-text
artifacts without network, cloud, LLM, or OpenClaw agent dependencies.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AUDIT_FILENAME = "audit.jsonl"
EXTRACTED_DIRECTORY = "extracted"
MANIFEST_FILENAME = "manifest.json"
SUPPORTED_SUFFIXES = {".md", ".pdf", ".txt"}
EXTRACTOR = "local_text_v0"
PDF_EXTRACTOR = "pdftotext_v0"


class ExtractionError(Exception):
    """Raised when a supported source cannot be extracted safely."""


def extract_source_text(matter_root: str | Path, source_id: str) -> dict[str, Any]:
    """Extract UTF-8 text for one registered source in a matter workspace."""

    root = Path(matter_root)
    manifest = _read_manifest(root)
    source = _find_source(manifest.get("sources", []), source_id)
    if source is None:
        raise KeyError(f"source_id not found: {source_id}")

    stored_path = Path(source["stored_path"])
    suffix = stored_path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        result = _unsupported_result(source, stored_path)
        _append_audit(
            root / AUDIT_FILENAME,
            {
                "event": "source_extraction_unsupported",
                "source_id": source_id,
                "original_filename": source["original_filename"],
                "sha256": source["sha256"],
                "reason": result["reason"],
                "attempted_at": result["attempted_at"],
            },
        )
        return result

    if suffix == ".pdf":
        return _extract_pdf_source(root, source, stored_path)

    try:
        text = stored_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractionError(
            f"source is not valid UTF-8 and cannot be extracted: {source_id}"
        ) from exc

    extracted_dir = root / EXTRACTED_DIRECTORY
    extracted_dir.mkdir(exist_ok=True)
    extracted_path = extracted_dir / f"{source_id}.txt"
    metadata_path = extracted_dir / f"{source_id}.json"
    extracted_at = _utc_now()

    metadata = {
        "status": "extracted",
        "extractor": EXTRACTOR,
        "source_id": source_id,
        "original_filename": source["original_filename"],
        "sha256": source["sha256"],
        "file_type": source.get("file_type", "application/octet-stream"),
        "stored_path": source["stored_path"],
        "extracted_path": str(extracted_path),
        "metadata_path": str(metadata_path),
        "extracted_at": extracted_at,
    }
    extracted_path.write_text(text, encoding="utf-8")
    _write_json(metadata_path, metadata)
    _append_audit(
        root / AUDIT_FILENAME,
        {
            "event": "source_text_extracted",
            "source_id": source_id,
            "original_filename": source["original_filename"],
            "sha256": source["sha256"],
            "extractor": EXTRACTOR,
            "extracted_path": str(extracted_path),
            "metadata_path": str(metadata_path),
            "extracted_at": extracted_at,
        },
    )
    return metadata


def extract_all_supported_sources(matter_root: str | Path) -> list[dict[str, Any]]:
    """Attempt local text extraction for every registered source."""

    root = Path(matter_root)
    manifest = _read_manifest(root)
    results = []
    for source in manifest.get("sources", []):
        results.append(extract_source_text(root, source["source_id"]))
    return results


def _unsupported_result(source: dict[str, Any], stored_path: Path) -> dict[str, Any]:
    attempted_at = _utc_now()
    return {
        "status": "unsupported",
        "extractor": EXTRACTOR,
        "source_id": source["source_id"],
        "original_filename": source["original_filename"],
        "sha256": source["sha256"],
        "stored_path": source["stored_path"],
        "file_type": source.get("file_type", "application/octet-stream"),
        "file_suffix": stored_path.suffix.lower(),
        "reason": "unsupported file type for local text extraction v0",
        "attempted_at": attempted_at,
    }


def _extract_pdf_source(
    matter_root: Path,
    source: dict[str, Any],
    stored_path: Path,
) -> dict[str, Any]:
    attempted_at = _utc_now()
    result = _pdf_to_text(stored_path)
    if not result.get("ok"):
        failure = _pdf_status_result(
            "failed",
            source,
            stored_path,
            result.get("error", "PDF text extraction failed"),
            attempted_at,
        )
        _append_audit(
            matter_root / AUDIT_FILENAME,
            {
                "event": "source_extraction_failed",
                "source_id": source["source_id"],
                "original_filename": source["original_filename"],
                "sha256": source["sha256"],
                "extractor": PDF_EXTRACTOR,
                "reason": failure["reason"],
                "attempted_at": attempted_at,
            },
        )
        return failure

    text = result.get("text", "")
    if not text.strip():
        no_text = _pdf_status_result(
            "no_text",
            source,
            stored_path,
            "PDF has no extractable text layer",
            attempted_at,
        )
        _append_audit(
            matter_root / AUDIT_FILENAME,
            {
                "event": "source_extraction_no_text",
                "source_id": source["source_id"],
                "original_filename": source["original_filename"],
                "sha256": source["sha256"],
                "extractor": PDF_EXTRACTOR,
                "reason": no_text["reason"],
                "attempted_at": attempted_at,
            },
        )
        return no_text

    extracted_dir = matter_root / EXTRACTED_DIRECTORY
    extracted_dir.mkdir(exist_ok=True)
    extracted_path = extracted_dir / f"{source['source_id']}.txt"
    metadata_path = extracted_dir / f"{source['source_id']}.json"
    extracted_at = _utc_now()
    metadata = {
        "status": "extracted",
        "extractor": PDF_EXTRACTOR,
        "source_id": source["source_id"],
        "original_filename": source["original_filename"],
        "sha256": source["sha256"],
        "file_type": source.get("file_type", "application/pdf"),
        "stored_path": source["stored_path"],
        "extracted_path": str(extracted_path),
        "metadata_path": str(metadata_path),
        "pages": result.get("pages"),
        "chars": result.get("chars", len(text)),
        "extracted_at": extracted_at,
    }
    extracted_path.write_text(text, encoding="utf-8")
    _write_json(metadata_path, metadata)
    _append_audit(
        matter_root / AUDIT_FILENAME,
        {
            "event": "source_text_extracted",
            "source_id": source["source_id"],
            "original_filename": source["original_filename"],
            "sha256": source["sha256"],
            "extractor": PDF_EXTRACTOR,
            "extracted_path": str(extracted_path),
            "metadata_path": str(metadata_path),
            "extracted_at": extracted_at,
        },
    )
    return metadata


def _pdf_status_result(
    status: str,
    source: dict[str, Any],
    stored_path: Path,
    reason: str,
    attempted_at: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "extractor": PDF_EXTRACTOR,
        "source_id": source["source_id"],
        "original_filename": source["original_filename"],
        "sha256": source["sha256"],
        "stored_path": source["stored_path"],
        "file_type": source.get("file_type", "application/pdf"),
        "file_suffix": stored_path.suffix.lower(),
        "reason": reason,
        "attempted_at": attempted_at,
    }


def _pdf_to_text(path: Path) -> dict[str, Any]:
    try:
        from oclaw_doctools import pdf_to_text
    except Exception as exc:
        return {
            "ok": False,
            "error": f"PDF text extraction helper unavailable: {exc}",
        }
    return pdf_to_text(path)


def _find_source(
    sources: list[dict[str, Any]],
    source_id: str,
) -> dict[str, Any] | None:
    for source in sources:
        if source.get("source_id") == source_id:
            return source
    return None


def _read_manifest(root: Path) -> dict[str, Any]:
    with (root / MANIFEST_FILENAME).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _append_audit(path: Path, entry: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True))
        handle.write("\n")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
