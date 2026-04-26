"""Deterministic local review packet export for legal matters."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from legal.path_guard import (
    canonicalize_matter_root,
    resolve_matter_child,
    validate_manifest_source_paths,
)


AUDIT_FILENAME = "audit.jsonl"
EXPORTS_DIRECTORY = "exports"
MANIFEST_FILENAME = "manifest.json"
PACKET_MANIFEST_FILENAME = "packet_manifest.json"


def export_review_packet(
    matter_root: str | Path,
    *,
    packet_name: str | None = None,
    include_reports: bool = True,
    allowed_vault_roots: Iterable[str | Path] | str | Path | None = None,
) -> dict[str, Any]:
    """Export a buyer-legible review packet folder under matter exports."""

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
    exports_dir = resolve_matter_child(
        root,
        root / EXPORTS_DIRECTORY,
        label="exports directory",
        allowed_vault_roots=allowed_vault_roots,
    )
    exports_dir.mkdir(exist_ok=True)
    packet_path = resolve_matter_child(
        root,
        exports_dir / _packet_dir_name(manifest["matter_id"], packet_name),
        label="review packet path",
        allowed_vault_roots=allowed_vault_roots,
    )

    if packet_path.exists():
        shutil.rmtree(packet_path)
    packet_path.mkdir()

    included_files: list[str] = []
    _copy_file(root / MANIFEST_FILENAME, packet_path / MANIFEST_FILENAME, included_files, packet_path)
    _copy_file(root / AUDIT_FILENAME, packet_path / AUDIT_FILENAME, included_files, packet_path)

    extracted_count = _copy_extracted(root, packet_path, included_files)
    report_count = 0
    if include_reports:
        report_count = _copy_reports(root, packet_path, included_files)

    created_at = _utc_now()
    packet_manifest = {
        "created_at": created_at,
        "matter_id": manifest["matter_id"],
        "source_count": len(manifest.get("sources", [])),
        "extracted_count": extracted_count,
        "report_count": report_count,
        "included_file_count": len(included_files) + 1,
        "included_files": sorted(included_files + [PACKET_MANIFEST_FILENAME]),
        "packet_path": str(packet_path),
    }
    _write_json(packet_path / PACKET_MANIFEST_FILENAME, packet_manifest)

    _append_audit(
        root / AUDIT_FILENAME,
        {
            "event": "review_packet_exported",
            "packet_path": str(packet_path),
            "included_file_count": packet_manifest["included_file_count"],
            "extracted_count": extracted_count,
            "report_count": report_count,
            "created_at": created_at,
        },
    )
    return packet_manifest


def _copy_extracted(
    matter_root: Path,
    packet_path: Path,
    included_files: list[str],
) -> int:
    extracted_dir = resolve_matter_child(matter_root, matter_root / "extracted", label="extracted directory")
    if not extracted_dir.exists():
        return 0
    count = 0
    for source_path in sorted(extracted_dir.iterdir()):
        if source_path.is_file():
            safe_source_path = resolve_matter_child(
                matter_root,
                source_path,
                label="extracted packet source",
            )
            destination = resolve_matter_child(
                matter_root,
                packet_path / "extracted" / source_path.name,
                label="review packet extracted destination",
            )
            _copy_file(safe_source_path, destination, included_files, packet_path)
            count += 1
    return count


def _copy_reports(
    matter_root: Path,
    packet_path: Path,
    included_files: list[str],
) -> int:
    exports_dir = resolve_matter_child(matter_root, matter_root / EXPORTS_DIRECTORY, label="exports directory")
    count = 0
    for source_path in sorted(exports_dir.glob("*.md")):
        if source_path.is_file():
            safe_source_path = resolve_matter_child(
                matter_root,
                source_path,
                label="report packet source",
            )
            destination = resolve_matter_child(
                matter_root,
                packet_path / "reports" / source_path.name,
                label="review packet report destination",
            )
            _copy_file(safe_source_path, destination, included_files, packet_path)
            count += 1
    return count


def _copy_file(
    source_path: Path,
    destination: Path,
    included_files: list[str],
    packet_path: Path,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination)
    included_files.append(str(destination.relative_to(packet_path)))


def _packet_dir_name(matter_id: str, packet_name: str | None) -> str:
    base = packet_name if packet_name and packet_name.strip() else matter_id
    slug = _slugify(Path(base).name)
    if not slug:
        slug = _slugify(matter_id)
    if slug.startswith("review-packet-"):
        return slug
    return f"review-packet-{slug}"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-")
    return slug.lower()


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
