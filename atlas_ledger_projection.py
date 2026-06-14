"""Project filesystem atlas metadata into the business ops ledger inventory.

The atlas is a metadata-only read model. This helper copies only path/count
metadata into `file_inventory`; it does not read file bodies, move files, or
grant cleanup authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from business_ops_ledger import init_business_ops_ledger, record_file_inventory_entry


DEFAULT_ATLAS_PATHS = (
    Path("generated/read_models/openclaw_filesystem_atlas.json"),
    Path("/mnt/e/openclaw/orchestration/artifacts/openclaw_filesystem_atlas.json"),
    Path("/mnt/e/openclaw-source/generated/read_models/openclaw_filesystem_atlas.json"),
)


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _load_atlas(atlas_path: str | Path | None = None) -> tuple[Path, dict[str, Any]]:
    candidates = [Path(atlas_path)] if atlas_path else list(DEFAULT_ATLAS_PATHS)
    for candidate in candidates:
        if candidate.is_file():
            return candidate, json.loads(candidate.read_text(encoding="utf-8"))
    raise FileNotFoundError("No filesystem atlas JSON found in known local locations")


def _root_lookup(atlas: dict[str, Any]) -> dict[str, str]:
    return {root["root_id"]: root["path"] for root in atlas.get("roots") or []}


def _relative_path(path: str, root_path: str | None) -> str:
    if not root_path:
        return Path(path).name or path
    try:
        return Path(path).resolve(strict=False).relative_to(Path(root_path).resolve(strict=False)).as_posix() or "."
    except ValueError:
        return Path(path).name or path


def _inventory_row_from_directory(row: dict[str, Any], root_paths: dict[str, str], generated_at: str) -> dict[str, Any]:
    path = str(row["path"])
    root_path = root_paths.get(str(row.get("root_id")))
    category = str(row.get("category") or "unknown")
    excluded = category == "protected_or_sensitive" or bool(row.get("blocked_reason"))
    content_fingerprint = {
        "path": path,
        "direct_file_count": row.get("direct_file_count"),
        "direct_dir_count": row.get("direct_dir_count"),
        "direct_size_bytes": row.get("direct_size_bytes"),
        "category": category,
        "blocked_reason": row.get("blocked_reason") or "",
    }
    return {
        "file_id": _stable_id("atlas_dir", row.get("run_id"), path),
        "root_id": str(row.get("root_id") or "atlas"),
        "drive_label": str(row.get("machine") or "pc"),
        "absolute_path": path,
        "relative_path": _relative_path(path, root_path),
        "file_name": str(row.get("name") or Path(path).name or path),
        "extension": None,
        "file_type_guess": "directory",
        "size_bytes": int(row.get("direct_size_bytes") or 0),
        "modified_at": generated_at,
        "content_hash": "atlas:" + hashlib.sha256(json.dumps(content_fingerprint, sort_keys=True).encode()).hexdigest(),
        "sensitivity_guess": category,
        "ingest_eligibility": "excluded" if excluded else "eligible_metadata_only",
        "exclusion_reason": str(row.get("blocked_reason") or category) if excluded else None,
    }


def _inventory_row_from_priority_file(row: dict[str, Any], root_paths: dict[str, str], generated_at: str) -> dict[str, Any]:
    path = str(row["path"])
    root_path = root_paths.get(str(row.get("root_id")))
    content_fingerprint = {
        "path": path,
        "direct_size_bytes": row.get("direct_size_bytes"),
        "category": row.get("category"),
    }
    suffix = Path(path).suffix or None
    return {
        "file_id": _stable_id("atlas_file", row.get("run_id"), path),
        "root_id": str(row.get("root_id") or "atlas"),
        "drive_label": str(row.get("machine") or "pc"),
        "absolute_path": path,
        "relative_path": _relative_path(path, root_path),
        "file_name": str(row.get("name") or Path(path).name or path),
        "extension": suffix,
        "file_type_guess": suffix.lstrip(".") if suffix else "file",
        "size_bytes": int(row.get("direct_size_bytes") or 0),
        "modified_at": generated_at,
        "content_hash": "atlas:" + hashlib.sha256(json.dumps(content_fingerprint, sort_keys=True).encode()).hexdigest(),
        "sensitivity_guess": str(row.get("category") or "priority_source_file"),
        "ingest_eligibility": "eligible_metadata_only",
        "exclusion_reason": None,
    }


def record_atlas_file_inventory(
    *,
    atlas_path: str | Path | None = None,
    db_path: str | Path | None = None,
    max_records: int | None = None,
) -> dict[str, Any]:
    """Record atlas metadata rows into `file_inventory`."""

    source_path, atlas = _load_atlas(atlas_path)
    init_business_ops_ledger(str(db_path) if db_path is not None else None)
    root_paths = _root_lookup(atlas)
    generated_at = str(atlas.get("run", {}).get("generated_at") or atlas.get("generated_at") or "")
    if not generated_at:
        generated_at = "atlas_generated_at_unknown"

    rows = [
        _inventory_row_from_directory(row, root_paths, generated_at)
        for row in atlas.get("directories") or []
    ]
    rows.extend(
        _inventory_row_from_priority_file(row, root_paths, generated_at)
        for row in atlas.get("priority_files") or []
    )
    if max_records is not None:
        rows = rows[:max_records]

    recorded = 0
    failed = 0
    for row in rows:
        ok = record_file_inventory_entry(db_path=str(db_path) if db_path is not None else None, **row)
        if ok:
            recorded += 1
        else:
            failed += 1

    return {
        "source_atlas_path": source_path.as_posix(),
        "metadata_only": True,
        "file_body_reads": False,
        "cleanup_authority_granted": False,
        "records_attempted": len(rows),
        "records_recorded": recorded,
        "records_failed": failed,
    }


__all__ = ["DEFAULT_ATLAS_PATHS", "record_atlas_file_inventory"]
