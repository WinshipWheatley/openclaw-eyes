"""Read-only local capability policy for Legal Alternative Methods."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


LOCAL_CAPABILITY_NOT_ATTEMPTED = "local_capability_not_attempted"
LOCAL_CAPABILITY_AVAILABLE = "local_capability_available"
LOCAL_CAPABILITY_BLOCKED_BY_POLICY = "local_capability_blocked_by_policy"
LOCAL_CAPABILITY_NOT_INSTALLED = "local_capability_not_installed"
LOCAL_CAPABILITY_FAILED_SAFELY = "local_capability_failed_safely"


IMAGE_OCR_SUFFIXES = {".jpeg", ".jpg", ".png"}
SUPPORTED_TEXT_SUFFIXES = {".md", ".pdf", ".txt"}


def local_ocr_available() -> bool:
    """Return whether the local Tesseract OCR binary is available."""

    return shutil.which("tesseract") is not None


def local_capability_policy_for_source(source_record: dict[str, Any]) -> dict[str, Any]:
    """Return sanitized local capability state for an Alternative Methods source."""

    status = _source_status(source_record)
    extension = _source_extension(source_record)
    reason = _source_reason(source_record)

    if status == "no_text" and extension == ".pdf":
        return _policy(
            LOCAL_CAPABILITY_NOT_INSTALLED,
            kind="ocr",
            reason_category="ocr_module_not_installed",
        )
    if extension in IMAGE_OCR_SUFFIXES:
        if status == "failed":
            return _policy(
                LOCAL_CAPABILITY_FAILED_SAFELY,
                kind="ocr",
                reason_category="ocr_process_failed",
            )
        if status == "no_text":
            return _policy(
                LOCAL_CAPABILITY_FAILED_SAFELY,
                kind="ocr",
                reason_category="ocr_no_text",
            )
        if status == "unsupported":
            if reason == "ocr_module_not_installed" or not local_ocr_available():
                return _policy(
                    LOCAL_CAPABILITY_NOT_INSTALLED,
                    kind="ocr",
                    reason_category="ocr_module_not_installed",
                )
            return _policy(
                LOCAL_CAPABILITY_AVAILABLE,
                kind="ocr",
                reason_category="local_ocr_available",
            )
    if status == "failed" and extension == ".pdf":
        return _policy(
            LOCAL_CAPABILITY_FAILED_SAFELY,
            kind="pdf_text_extraction",
            reason_category="installed_handler_failed",
        )
    if status == "unsupported":
        return _policy(
            LOCAL_CAPABILITY_NOT_ATTEMPTED,
            kind="unknown_local_handler",
            reason_category="unsupported_file_type",
        )
    if status in {"failed", "no_text"}:
        return _policy(
            LOCAL_CAPABILITY_FAILED_SAFELY,
            kind="local_text_extraction",
            reason_category="installed_handler_failed",
        )
    return _policy(
        LOCAL_CAPABILITY_NOT_ATTEMPTED,
        kind=None,
        reason_category="not_actionable",
    )


def _policy(
    state: str,
    *,
    kind: str | None,
    reason_category: str,
) -> dict[str, Any]:
    return {
        "local_capability_state": state,
        "local_capability_kind": kind,
        "local_capability_reason_category": reason_category,
        "request_feature_state": "locked",
    }


def _source_status(source_record: dict[str, Any]) -> str:
    status = source_record.get("extraction_status")
    if isinstance(status, str) and status.strip():
        return status
    extension = _source_extension(source_record)
    if extension in IMAGE_OCR_SUFFIXES:
        return "pending" if local_ocr_available() else "unsupported"
    if extension and extension not in SUPPORTED_TEXT_SUFFIXES:
        return "unsupported"
    return "pending"


def _source_reason(source_record: dict[str, Any]) -> str | None:
    reason = source_record.get("extraction_reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    return None


def _source_extension(source_record: dict[str, Any]) -> str | None:
    stored_path = source_record.get("stored_path")
    if not isinstance(stored_path, str):
        return None
    return Path(stored_path).suffix.lower() or None
