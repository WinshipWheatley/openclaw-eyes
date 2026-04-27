"""Local-only text extraction for legal matter workspaces.

This module is deliberately narrow: it reads registered `.txt` and `.md`
sources from a matter workspace and writes deterministic extracted-text
artifacts without network, cloud, LLM, or OpenClaw agent dependencies.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from legal.path_guard import (
    canonicalize_matter_root,
    resolve_matter_child,
    validate_manifest_source_paths,
)


AUDIT_FILENAME = "audit.jsonl"
EXTRACTED_DIRECTORY = "extracted"
MANIFEST_FILENAME = "manifest.json"
IMAGE_OCR_SUFFIXES = {".jpeg", ".jpg", ".png"}
SUPPORTED_SUFFIXES = {".md", ".pdf", ".txt"} | IMAGE_OCR_SUFFIXES
EXTRACTOR = "local_text_v0"
PDF_EXTRACTOR = "pdftotext_v0"
IMAGE_OCR_EXTRACTOR = "tesseract_ocr_v0"
IMAGE_OCR_TIMEOUT_SECONDS = 60
LOCAL_OCR_NOTICE = "[Extracted via local OCR]"
OCR_MODULE_NOT_INSTALLED = "ocr_module_not_installed"
OCR_NO_TEXT = "ocr_no_text"
OCR_PROCESS_FAILED = "ocr_process_failed"


class ExtractionError(Exception):
    """Raised when a supported source cannot be extracted safely."""


def extract_source_text(
    matter_root: str | Path,
    source_id: str,
    *,
    allowed_vault_roots: Iterable[str | Path] | str | Path | None = None,
) -> dict[str, Any]:
    """Extract UTF-8 text for one registered source in a matter workspace."""

    root = canonicalize_matter_root(
        matter_root,
        allowed_vault_roots=allowed_vault_roots,
    )
    manifest = _read_manifest(root)
    validate_manifest_source_paths(
        root,
        manifest,
        allowed_vault_roots=allowed_vault_roots,
    )
    source = _find_source(manifest.get("sources", []), source_id)
    if source is None:
        raise KeyError(f"source_id not found: {source_id}")

    stored_path = resolve_matter_child(
        root,
        source["stored_path"],
        label=f"manifest stored_path for source_id {source_id}",
        allowed_vault_roots=allowed_vault_roots,
    )
    suffix = stored_path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        result = _unsupported_result(source, stored_path)
        _record_source_extraction_status(root, source_id, result)
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
    if suffix in IMAGE_OCR_SUFFIXES:
        return _extract_image_source(
            root,
            source,
            stored_path,
            allowed_vault_roots=allowed_vault_roots,
        )

    try:
        text = stored_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractionError(
            f"source is not valid UTF-8 and cannot be extracted: {source_id}"
        ) from exc

    extracted_dir = resolve_matter_child(
        root,
        root / EXTRACTED_DIRECTORY,
        label="extracted directory",
        allowed_vault_roots=allowed_vault_roots,
    )
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
        "stored_path": str(stored_path),
        "extracted_path": str(extracted_path),
        "metadata_path": str(metadata_path),
        "extracted_at": extracted_at,
    }
    _record_source_extraction_status(root, source_id, metadata)
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


def extract_all_supported_sources(
    matter_root: str | Path,
    *,
    allowed_vault_roots: Iterable[str | Path] | str | Path | None = None,
) -> list[dict[str, Any]]:
    """Attempt local text extraction for every registered source."""

    root = canonicalize_matter_root(
        matter_root,
        allowed_vault_roots=allowed_vault_roots,
    )
    manifest = _read_manifest(root)
    validate_manifest_source_paths(
        root,
        manifest,
        allowed_vault_roots=allowed_vault_roots,
    )
    results = []
    for source in manifest.get("sources", []):
        results.append(
            extract_source_text(
                root,
                source["source_id"],
                allowed_vault_roots=allowed_vault_roots,
            )
        )
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
        _record_source_extraction_status(matter_root, source["source_id"], failure)
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
        _record_source_extraction_status(matter_root, source["source_id"], no_text)
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

    extracted_dir = resolve_matter_child(
        matter_root,
        matter_root / EXTRACTED_DIRECTORY,
        label="extracted directory",
    )
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
        "stored_path": str(stored_path),
        "extracted_path": str(extracted_path),
        "metadata_path": str(metadata_path),
        "pages": result.get("pages"),
        "chars": result.get("chars", len(text)),
        "extracted_at": extracted_at,
    }
    _record_source_extraction_status(matter_root, source["source_id"], metadata)
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


def _extract_image_source(
    matter_root: Path,
    source: dict[str, Any],
    stored_path: Path,
    *,
    allowed_vault_roots: Iterable[str | Path] | str | Path | None = None,
) -> dict[str, Any]:
    attempted_at = _utc_now()
    if shutil.which("tesseract") is None:
        unavailable = _image_ocr_status_result(
            "unsupported",
            source,
            stored_path,
            OCR_MODULE_NOT_INSTALLED,
            attempted_at,
        )
        _record_source_extraction_status(matter_root, source["source_id"], unavailable)
        _append_audit(
            matter_root / AUDIT_FILENAME,
            {
                "event": "source_extraction_unsupported",
                "source_id": source["source_id"],
                "original_filename": source["original_filename"],
                "sha256": source["sha256"],
                "extractor": IMAGE_OCR_EXTRACTOR,
                "reason": OCR_MODULE_NOT_INSTALLED,
                "attempted_at": attempted_at,
            },
        )
        return unavailable

    try:
        completed = subprocess.run(
            ["tesseract", str(stored_path), "stdout"],
            capture_output=True,
            text=True,
            check=False,
            timeout=IMAGE_OCR_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError):
        return _record_image_ocr_failure(matter_root, source, stored_path, attempted_at)

    if completed.returncode != 0:
        return _record_image_ocr_failure(matter_root, source, stored_path, attempted_at)

    ocr_text = completed.stdout or ""
    if not ocr_text.strip():
        no_text = _image_ocr_status_result(
            "no_text",
            source,
            stored_path,
            OCR_NO_TEXT,
            attempted_at,
        )
        _record_source_extraction_status(matter_root, source["source_id"], no_text)
        _append_audit(
            matter_root / AUDIT_FILENAME,
            {
                "event": "source_extraction_no_text",
                "source_id": source["source_id"],
                "original_filename": source["original_filename"],
                "sha256": source["sha256"],
                "extractor": IMAGE_OCR_EXTRACTOR,
                "reason": OCR_NO_TEXT,
                "attempted_at": attempted_at,
            },
        )
        return no_text

    text = f"{LOCAL_OCR_NOTICE}\n\n{ocr_text}"
    extracted_dir = resolve_matter_child(
        matter_root,
        matter_root / EXTRACTED_DIRECTORY,
        label="extracted directory",
        allowed_vault_roots=allowed_vault_roots,
    )
    extracted_dir.mkdir(exist_ok=True)
    extracted_path = extracted_dir / f"{source['source_id']}.txt"
    metadata_path = extracted_dir / f"{source['source_id']}.json"
    extracted_at = _utc_now()
    metadata = {
        "status": "extracted",
        "extractor": IMAGE_OCR_EXTRACTOR,
        "source_id": source["source_id"],
        "original_filename": source["original_filename"],
        "sha256": source["sha256"],
        "file_type": source.get("file_type", "application/octet-stream"),
        "stored_path": str(stored_path),
        "extracted_path": str(extracted_path),
        "metadata_path": str(metadata_path),
        "chars": len(text),
        "extracted_at": extracted_at,
    }
    _record_source_extraction_status(matter_root, source["source_id"], metadata)
    extracted_path.write_text(text, encoding="utf-8")
    _write_json(metadata_path, metadata)
    _append_audit(
        matter_root / AUDIT_FILENAME,
        {
            "event": "source_text_extracted",
            "source_id": source["source_id"],
            "original_filename": source["original_filename"],
            "sha256": source["sha256"],
            "extractor": IMAGE_OCR_EXTRACTOR,
            "extracted_path": str(extracted_path),
            "metadata_path": str(metadata_path),
            "extracted_at": extracted_at,
        },
    )
    return metadata


def _record_image_ocr_failure(
    matter_root: Path,
    source: dict[str, Any],
    stored_path: Path,
    attempted_at: str,
) -> dict[str, Any]:
    failure = _image_ocr_status_result(
        "failed",
        source,
        stored_path,
        OCR_PROCESS_FAILED,
        attempted_at,
    )
    _record_source_extraction_status(matter_root, source["source_id"], failure)
    _append_audit(
        matter_root / AUDIT_FILENAME,
        {
            "event": "source_extraction_failed",
            "source_id": source["source_id"],
            "original_filename": source["original_filename"],
            "sha256": source["sha256"],
            "extractor": IMAGE_OCR_EXTRACTOR,
            "reason": OCR_PROCESS_FAILED,
            "attempted_at": attempted_at,
        },
    )
    return failure


def _image_ocr_status_result(
    status: str,
    source: dict[str, Any],
    stored_path: Path,
    reason: str,
    attempted_at: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "extractor": IMAGE_OCR_EXTRACTOR,
        "source_id": source["source_id"],
        "original_filename": source["original_filename"],
        "sha256": source["sha256"],
        "stored_path": source["stored_path"],
        "file_type": source.get("file_type", "application/octet-stream"),
        "file_suffix": stored_path.suffix.lower(),
        "reason": reason,
        "attempted_at": attempted_at,
    }


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


def _record_source_extraction_status(
    matter_root: Path,
    source_id: str,
    result: dict[str, Any],
) -> None:
    manifest_path = matter_root / MANIFEST_FILENAME
    manifest = _read_manifest(matter_root)
    for source in manifest.get("sources", []):
        if source.get("source_id") != source_id:
            continue
        source["extraction_status"] = result.get("status", "unknown")
        source["extraction_extractor"] = result.get("extractor")
        attempted_at = result.get("attempted_at") or result.get("extracted_at")
        if attempted_at:
            source["extraction_attempted_at"] = attempted_at
        reason = result.get("reason")
        if reason:
            source["extraction_reason"] = reason
        _write_json(manifest_path, manifest)
        return


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
