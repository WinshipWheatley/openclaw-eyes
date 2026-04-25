"""Path boundary checks for local legal matter workspaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any


PRODUCT_REPO_ROOT = Path(__file__).resolve().parents[1]


class LegalPathError(ValueError):
    """Raised when a legal workspace path violates local vault boundaries."""


def canonicalize_matter_root(
    root_path: str | Path,
    *,
    product_repo_root: str | Path = PRODUCT_REPO_ROOT,
) -> Path:
    """Return a resolved matter root, rejecting paths inside the product repo."""

    root = Path(root_path).expanduser().resolve(strict=False)
    repo_root = Path(product_repo_root).expanduser().resolve(strict=False)
    if _is_relative_to(root, repo_root):
        raise LegalPathError(
            f"matter root must be outside product repo: {root} is under {repo_root}"
        )
    return root


def resolve_matter_child(
    matter_root: str | Path,
    child_path: str | Path,
    *,
    label: str = "path",
) -> Path:
    """Resolve a path and require it to stay within the matter root."""

    root = canonicalize_matter_root(matter_root)
    raw_path = Path(child_path).expanduser()
    candidate = raw_path if raw_path.is_absolute() else root / raw_path
    resolved = candidate.resolve(strict=False)
    if not _is_relative_to(resolved, root):
        raise LegalPathError(
            f"{label} must stay inside matter root: {resolved} escapes {root}"
        )
    return resolved


def validate_manifest_source_paths(
    matter_root: str | Path,
    manifest: dict[str, Any],
) -> None:
    """Fail closed if any manifest source path points outside the matter root."""

    for source in manifest.get("sources", []):
        source_id = source.get("source_id", "<unknown>")
        stored_path = source.get("stored_path")
        if not isinstance(stored_path, str) or not stored_path.strip():
            raise LegalPathError(
                f"manifest source stored_path is required for source_id: {source_id}"
            )
        resolve_matter_child(
            matter_root,
            stored_path,
            label=f"manifest stored_path for source_id {source_id}",
        )


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
