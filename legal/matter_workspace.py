"""Deterministic local matter workspace containers.

This module is intentionally standalone: no OpenClaw agent imports, no LLM
calls, and no network/cloud dependencies. Deployment profiles can enable this
package without wiring it into the rest of the runtime.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from legal.path_guard import (
    canonicalize_matter_root,
    resolve_matter_child,
    validate_manifest_source_paths,
)


REQUIRED_DIRECTORIES = ("sources", "transcripts", "notes", "exports")
MANIFEST_FILENAME = "manifest.json"
AUDIT_FILENAME = "audit.jsonl"
SOURCE_ID_PREFIX_LENGTH = 12


@dataclass(frozen=True)
class MatterWorkspace:
    """Handle for a local matter workspace."""

    matter_id: str
    display_name: str
    created_at: str
    root_path: str
    allowed_vault_roots: tuple[str, ...] = ()

    @property
    def root(self) -> Path:
        return Path(self.root_path)

    @property
    def manifest_path(self) -> Path:
        return self.root / MANIFEST_FILENAME

    @property
    def audit_path(self) -> Path:
        return self.root / AUDIT_FILENAME

    def register_source(self, source_path: str | Path) -> dict[str, Any]:
        return register_source(
            self.root,
            source_path,
            allowed_vault_roots=self.allowed_vault_roots or None,
        )


def create_matter_workspace(
    root_path: str | Path,
    matter_id: str,
    display_name: str,
    *,
    created_at: str | None = None,
    allowed_vault_roots: Iterable[str | Path] | str | Path | None = None,
) -> MatterWorkspace:
    """Create a local matter workspace with manifest, audit log, and folders."""

    if not matter_id or not matter_id.strip():
        raise ValueError("matter_id is required")
    if not display_name or not display_name.strip():
        raise ValueError("display_name is required")

    root = canonicalize_matter_root(
        root_path,
        allowed_vault_roots=allowed_vault_roots,
    )
    root.mkdir(parents=True, exist_ok=True)
    for directory in REQUIRED_DIRECTORIES:
        (root / directory).mkdir(exist_ok=True)

    manifest_path = root / MANIFEST_FILENAME
    audit_path = root / AUDIT_FILENAME
    if manifest_path.exists():
        raise FileExistsError(f"manifest already exists: {manifest_path}")

    timestamp = created_at or _utc_now()
    manifest = {
        "matter_id": matter_id,
        "display_name": display_name,
        "created_at": timestamp,
        "root_path": str(root),
        "sources": [],
    }
    _write_json(manifest_path, manifest)
    audit_path.touch(exist_ok=True)
    _append_audit(
        audit_path,
        {
            "event": "matter_created",
            "matter_id": matter_id,
            "created_at": timestamp,
        },
    )
    return _workspace_from_manifest(
        manifest,
        allowed_vault_roots=allowed_vault_roots,
    )


def load_matter_workspace(
    root_path: str | Path,
    *,
    allowed_vault_roots: Iterable[str | Path] | str | Path | None = None,
) -> MatterWorkspace:
    """Load an existing local matter workspace."""

    root = canonicalize_matter_root(
        root_path,
        allowed_vault_roots=allowed_vault_roots,
    )
    manifest = _read_manifest(root)
    validate_manifest_source_paths(
        root,
        manifest,
        allowed_vault_roots=allowed_vault_roots,
    )
    return _workspace_from_manifest(
        manifest,
        expected_root=root,
        allowed_vault_roots=allowed_vault_roots,
    )


def register_source(
    matter_root: str | Path,
    source_path: str | Path,
    *,
    allowed_vault_roots: Iterable[str | Path] | str | Path | None = None,
) -> dict[str, Any]:
    """Copy a source file into the matter and append a source audit entry."""

    root = canonicalize_matter_root(
        matter_root,
        allowed_vault_roots=allowed_vault_roots,
    )
    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError(f"source file not found: {source}")

    manifest = _read_manifest(root)
    validate_manifest_source_paths(
        root,
        manifest,
        allowed_vault_roots=allowed_vault_roots,
    )
    digest = _sha256_file(source)
    source_id = _source_id_for_digest(digest, manifest.get("sources", []))
    destination = resolve_matter_child(
        root,
        root / "sources" / f"{source_id}{source.suffix}",
        label="registered source destination",
        allowed_vault_roots=allowed_vault_roots,
    )

    existing_entry = _find_source_by_id(manifest.get("sources", []), source_id)
    if existing_entry:
        if existing_entry["sha256"] != digest:
            raise ValueError(f"source_id collision for distinct content: {source_id}")
        return existing_entry

    shutil.copy2(source, destination)
    added_at = _utc_now()
    media_type, _ = mimetypes.guess_type(source.name)
    entry = {
        "source_id": source_id,
        "original_filename": source.name,
        "stored_path": str(destination),
        "sha256": digest,
        "file_type": media_type or "application/octet-stream",
        "added_at": added_at,
    }
    manifest.setdefault("sources", []).append(entry)
    _write_json(root / MANIFEST_FILENAME, manifest)
    _append_audit(
        root / AUDIT_FILENAME,
        {
            "event": "source_registered",
            "source_id": source_id,
            "sha256": digest,
            "original_filename": source.name,
            "added_at": added_at,
        },
    )
    return entry


def _source_id_for_digest(digest: str, sources: list[dict[str, Any]]) -> str:
    prefix_length = SOURCE_ID_PREFIX_LENGTH
    while prefix_length <= len(digest):
        candidate = f"src_{digest[:prefix_length]}"
        matching = _find_source_by_id(sources, candidate)
        if matching is None or matching.get("sha256") == digest:
            return candidate
        prefix_length += 1
    raise ValueError("unable to create collision-safe source_id")


def _find_source_by_id(
    sources: list[dict[str, Any]],
    source_id: str,
) -> dict[str, Any] | None:
    for source in sources:
        if source.get("source_id") == source_id:
            return source
    return None


def _read_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / MANIFEST_FILENAME
    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _append_audit(path: Path, entry: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True))
        handle.write("\n")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _workspace_from_manifest(
    manifest: dict[str, Any],
    *,
    expected_root: Path | None = None,
    allowed_vault_roots: Iterable[str | Path] | str | Path | None = None,
) -> MatterWorkspace:
    root = canonicalize_matter_root(
        manifest["root_path"],
        allowed_vault_roots=allowed_vault_roots,
    )
    if expected_root is not None and root != expected_root:
        raise ValueError(
            f"manifest root_path does not match matter root: {root} != {expected_root}"
        )
    return MatterWorkspace(
        matter_id=manifest["matter_id"],
        display_name=manifest["display_name"],
        created_at=manifest["created_at"],
        root_path=str(root),
        allowed_vault_roots=_vault_root_strings(allowed_vault_roots),
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _vault_root_strings(
    allowed_vault_roots: Iterable[str | Path] | str | Path | None,
) -> tuple[str, ...]:
    if allowed_vault_roots is None:
        return ()
    if isinstance(allowed_vault_roots, (str, Path)):
        return (str(allowed_vault_roots),)
    return tuple(str(root) for root in allowed_vault_roots)
