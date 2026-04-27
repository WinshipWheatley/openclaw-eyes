"""Sanitized support diagnostics for legal matter workspaces."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from legal.path_guard import (
    canonicalize_matter_root,
    resolve_matter_child,
    validate_manifest_source_paths,
)


AUDIT_FILENAME = "audit.jsonl"
EXPORTER = "support_packet_v0"
EXTRACTED_DIRECTORY = "extracted"
MANIFEST_FILENAME = "manifest.json"
SUPPORT_DIRECTORY = "support"
SUPPORT_PACKET_FILENAME = "support_packet.json"
SUPPORT_PACKET_SCHEMA_VERSION = 1
IMAGE_OCR_SUFFIXES = {".jpeg", ".jpg", ".png"}
SUPPORTED_EXTRACTION_SUFFIXES = {".md", ".pdf", ".txt"} | IMAGE_OCR_SUFFIXES
LEGAL_MODULES = (
    "matter_workspace",
    "local_ingestion",
    "local_search",
    "search_report",
    "review_packet",
    "support_packet",
)


def export_support_packet(
    matter_root: str | Path,
    *,
    packet_name: str | None = None,
    allowed_vault_roots: Iterable[str | Path] | str | Path | None = None,
) -> dict[str, Any]:
    """Write a sanitized support packet that excludes matter content."""

    root = canonicalize_matter_root(
        matter_root,
        allowed_vault_roots=allowed_vault_roots,
    )
    manifest = _read_json(root / MANIFEST_FILENAME)
    validate_manifest_source_paths(
        root,
        manifest,
        allowed_vault_roots=allowed_vault_roots,
    )

    sources = manifest.get("sources", [])
    metadata_entries = _read_extraction_metadata(
        root,
        sources,
        allowed_vault_roots=allowed_vault_roots,
    )
    created_at = _utc_now()
    support_dir = resolve_matter_child(
        root,
        root / SUPPORT_DIRECTORY / _packet_dir_name(packet_name),
        label="support packet directory",
        allowed_vault_roots=allowed_vault_roots,
    )
    support_dir.mkdir(parents=True, exist_ok=True)
    packet_path = resolve_matter_child(
        root,
        support_dir / SUPPORT_PACKET_FILENAME,
        label="support packet path",
        allowed_vault_roots=allowed_vault_roots,
    )

    packet = {
        "artifact_type": "sanitized_support_packet",
        "schema_version": SUPPORT_PACKET_SCHEMA_VERSION,
        "exporter": EXPORTER,
        "created_at": created_at,
        "module_info": {
            "package": "openclaw_legal",
            "modules": list(LEGAL_MODULES),
        },
        "matter": {
            "matter_id_present": bool(manifest.get("matter_id")),
            "display_name_present": bool(manifest.get("display_name")),
            "source_count": len(sources),
        },
        "diagnostics": {
            "source_status_counts": _status_counts(sources, metadata_entries),
            "file_extensions": _file_extensions(sources),
            "file_size_ranges": _file_size_ranges(sources),
            "extractors": _extractors(sources, metadata_entries),
            "redacted_status_summaries": _redacted_status_summaries(
                sources,
                metadata_entries,
            ),
        },
        "exclusions": {
            "source_files": "excluded",
            "extracted_text": "excluded",
            "review_packets": "excluded",
            "attorney_notes": "excluded",
            "client_or_matter_names": "excluded",
            "sensitive_filenames": "excluded",
            "private_absolute_paths": "excluded",
            "raw_audit_logs": "excluded",
        },
        "content_excluded": True,
        "private_paths_excluded": True,
    }
    _write_json(packet_path, packet)
    _append_audit(
        root / AUDIT_FILENAME,
        {
            "event": "support_packet_exported",
            "artifact_type": "sanitized_support_packet",
            "packet_path": str(packet_path),
            "source_count": len(sources),
            "created_at": created_at,
        },
    )
    return {**packet, "packet_path": str(packet_path)}


def _read_extraction_metadata(
    matter_root: Path,
    sources: list[dict[str, Any]],
    *,
    allowed_vault_roots: Iterable[str | Path] | str | Path | None,
) -> dict[str, dict[str, Any]]:
    extracted_dir = resolve_matter_child(
        matter_root,
        matter_root / EXTRACTED_DIRECTORY,
        label="extracted directory",
        allowed_vault_roots=allowed_vault_roots,
    )
    entries: dict[str, dict[str, Any]] = {}
    for source in sources:
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            continue
        metadata_path = resolve_matter_child(
            matter_root,
            extracted_dir / f"{source_id}.json",
            label="extraction metadata path",
            allowed_vault_roots=allowed_vault_roots,
        )
        if metadata_path.exists():
            entries[source_id] = _read_json(metadata_path)
    return entries


def _status_counts(
    sources: list[dict[str, Any]],
    metadata_entries: dict[str, dict[str, Any]],
) -> dict[str, int]:
    counts = {"extracted": 0, "unsupported": 0, "no_text": 0, "failed": 0, "pending": 0}
    for source in sources:
        source_id = source.get("source_id")
        metadata = metadata_entries.get(source_id)
        status = _source_status(source, metadata)
        if status not in counts:
            counts[str(status)] = 0
        counts[str(status)] += 1
    return counts


def _file_extensions(sources: list[dict[str, Any]]) -> list[str]:
    extensions = set()
    for source in sources:
        stored_path = source.get("stored_path")
        if isinstance(stored_path, str):
            suffix = Path(stored_path).suffix.lower()
            if suffix:
                extensions.add(suffix)
    return sorted(extensions)


def _file_size_ranges(sources: list[dict[str, Any]]) -> dict[str, int]:
    ranges = {
        "0-10KB": 0,
        "10KB-100KB": 0,
        "100KB-1MB": 0,
        "1MB-10MB": 0,
        "10MB+": 0,
        "unknown": 0,
    }
    for source in sources:
        stored_path = source.get("stored_path")
        if not isinstance(stored_path, str):
            ranges["unknown"] += 1
            continue
        path = Path(stored_path)
        try:
            size = path.stat().st_size
        except OSError:
            ranges["unknown"] += 1
            continue
        if size < 10 * 1024:
            ranges["0-10KB"] += 1
        elif size < 100 * 1024:
            ranges["10KB-100KB"] += 1
        elif size < 1024 * 1024:
            ranges["100KB-1MB"] += 1
        elif size < 10 * 1024 * 1024:
            ranges["1MB-10MB"] += 1
        else:
            ranges["10MB+"] += 1
    return ranges


def _extractors(
    sources: list[dict[str, Any]],
    metadata_entries: dict[str, dict[str, Any]],
) -> list[str]:
    extractors = {
        metadata["extractor"]
        for metadata in metadata_entries.values()
        if isinstance(metadata.get("extractor"), str) and metadata["extractor"].strip()
    }
    for source in sources:
        extractor = source.get("extraction_extractor")
        if isinstance(extractor, str) and extractor.strip():
            extractors.add(extractor)
    return sorted(extractors)


def _redacted_status_summaries(
    sources: list[dict[str, Any]],
    metadata_entries: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    summaries = []
    for index, source in enumerate(sources, start=1):
        source_id = source.get("source_id")
        metadata = metadata_entries.get(source_id) if isinstance(source_id, str) else None
        status = _source_status(source, metadata)
        summaries.append(
            {
                "source_index": index,
                "source_id_present": isinstance(source_id, str) and bool(source_id),
                "status": status,
                "file_extension": _source_extension(source),
                "file_size_range": _source_size_range(source),
                "extractor": _source_extractor(source, metadata),
                "reason_category": _reason_category(source, metadata),
            }
        )
    return summaries


def _source_extension(source: dict[str, Any]) -> str | None:
    stored_path = source.get("stored_path")
    if not isinstance(stored_path, str):
        return None
    return Path(stored_path).suffix.lower() or None


def _source_status(
    source: dict[str, Any],
    metadata: dict[str, Any] | None,
) -> str:
    manifest_status = source.get("extraction_status")
    if isinstance(manifest_status, str) and manifest_status.strip():
        return manifest_status
    if metadata:
        status = metadata.get("status")
        if isinstance(status, str) and status.strip():
            return status
    extension = _source_extension(source)
    if extension and extension not in SUPPORTED_EXTRACTION_SUFFIXES:
        return "unsupported"
    return "pending"


def _source_size_range(source: dict[str, Any]) -> str:
    stored_path = source.get("stored_path")
    if not isinstance(stored_path, str):
        return "unknown"
    try:
        size = Path(stored_path).stat().st_size
    except OSError:
        return "unknown"
    if size < 10 * 1024:
        return "0-10KB"
    if size < 100 * 1024:
        return "10KB-100KB"
    if size < 1024 * 1024:
        return "100KB-1MB"
    if size < 10 * 1024 * 1024:
        return "1MB-10MB"
    return "10MB+"


def _safe_metadata_value(
    metadata: dict[str, Any] | None,
    key: str,
) -> str | None:
    if not metadata:
        return None
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _source_extractor(
    source: dict[str, Any],
    metadata: dict[str, Any] | None,
) -> str | None:
    manifest_extractor = source.get("extraction_extractor")
    if isinstance(manifest_extractor, str) and manifest_extractor.strip():
        return manifest_extractor
    return _safe_metadata_value(metadata, "extractor")


def _reason_category(
    source: dict[str, Any],
    metadata: dict[str, Any] | None,
) -> str | None:
    reason = source.get("extraction_reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = _safe_metadata_value(metadata, "reason")
    if reason is None:
        return None
    lowered = reason.casefold()
    if lowered == "ocr_module_not_installed":
        return "ocr_module_not_installed"
    if lowered == "ocr_process_failed":
        return "ocr_process_failed"
    if lowered == "ocr_no_text":
        return "no_extractable_text"
    if "unsupported" in lowered:
        return "unsupported_file_type"
    if "no extractable text" in lowered:
        return "no_extractable_text"
    if "unavailable" in lowered:
        return "extractor_unavailable"
    if "failed" in lowered:
        return "extraction_failed"
    return "redacted_status_reason"


def _packet_dir_name(packet_name: str | None) -> str:
    if packet_name and packet_name.strip():
        slug = "".join(
            character.lower() if character.isalnum() else "-"
            for character in packet_name.strip()
        ).strip("-")
    else:
        slug = "latest"
    if not slug:
        slug = "latest"
    if slug.startswith("support-packet-"):
        return slug
    return f"support-packet-{slug}"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
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
