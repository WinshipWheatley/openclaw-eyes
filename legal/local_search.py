"""Local-only literal search over extracted legal matter text."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.path_guard import (
    canonicalize_matter_root,
    resolve_matter_child,
    validate_manifest_source_paths,
)


AUDIT_FILENAME = "audit.jsonl"
EXTRACTED_DIRECTORY = "extracted"
MANIFEST_FILENAME = "manifest.json"
REQUIRED_METADATA_FIELDS = ("source_id", "original_filename", "sha256")


class SearchMetadataError(Exception):
    """Raised when extracted text sidecar metadata is missing or invalid."""


def search_extracted_text(
    matter_root: str | Path,
    query: str,
    *,
    max_results: int = 20,
    snippet_chars: int = 80,
) -> list[dict[str, Any]]:
    """Search extracted text artifacts with deterministic literal matching."""

    if not query or not query.strip():
        raise ValueError("query must not be empty")
    if max_results < 1:
        raise ValueError("max_results must be at least 1")
    if snippet_chars < 1:
        raise ValueError("snippet_chars must be at least 1")

    root = canonicalize_matter_root(matter_root)
    manifest_path = root / MANIFEST_FILENAME
    if manifest_path.exists():
        validate_manifest_source_paths(root, _read_json(manifest_path))
    extracted_dir = resolve_matter_child(root, root / EXTRACTED_DIRECTORY, label="extracted directory")
    results: list[dict[str, Any]] = []

    if extracted_dir.exists():
        lowered_query = query.casefold()
        for extracted_path in sorted(extracted_dir.glob("*.txt")):
            safe_extracted_path = resolve_matter_child(
                root,
                extracted_path,
                label="extracted text path",
            )
            text = safe_extracted_path.read_text(encoding="utf-8")
            match_positions = _match_positions(text.casefold(), lowered_query)
            if not match_positions:
                continue

            metadata_path = safe_extracted_path.with_suffix(".json")
            resolve_matter_child(root, metadata_path, label="extracted metadata path")
            metadata = _read_metadata(metadata_path)
            results.append(
                {
                    "source_id": metadata["source_id"],
                    "original_filename": metadata["original_filename"],
                    "sha256": metadata["sha256"],
                    "match_count": len(match_positions),
                    "snippets": _snippets(
                        text,
                        match_positions,
                        len(query),
                        snippet_chars,
                    ),
                    "extracted_path": str(safe_extracted_path),
                    "metadata_path": str(metadata_path),
                }
            )
            if len(results) >= max_results:
                break

    _append_audit(
        root / AUDIT_FILENAME,
        {
            "event": "extracted_text_searched",
            "query": query,
            "result_count": len(results),
            "searched_at": _utc_now(),
        },
    )
    return results


def _match_positions(text: str, query: str) -> list[int]:
    positions = []
    start = 0
    while True:
        index = text.find(query, start)
        if index == -1:
            return positions
        positions.append(index)
        start = index + len(query)


def _snippets(
    text: str,
    positions: list[int],
    query_length: int,
    snippet_chars: int,
) -> list[str]:
    snippets = []
    for position in positions:
        start = max(0, position - snippet_chars)
        end = min(len(text), position + query_length + snippet_chars)
        snippets.append(text[start:end])
    return snippets


def _read_metadata(metadata_path: Path) -> dict[str, Any]:
    if not metadata_path.exists():
        raise SearchMetadataError(f"missing extracted metadata: {metadata_path}")
    try:
        with metadata_path.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)
    except json.JSONDecodeError as exc:
        raise SearchMetadataError(f"corrupt extracted metadata: {metadata_path}") from exc

    missing_fields = [
        field for field in REQUIRED_METADATA_FIELDS if field not in metadata
    ]
    if missing_fields:
        raise SearchMetadataError(
            f"metadata missing required fields: {', '.join(missing_fields)}"
        )
    return metadata


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _append_audit(path: Path, entry: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True))
        handle.write("\n")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
