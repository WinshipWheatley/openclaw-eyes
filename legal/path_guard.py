"""Path boundary checks for local legal matter workspaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


PRODUCT_REPO_ROOT = Path(__file__).resolve().parents[1]


class LegalPathError(ValueError):
    """Raised when a legal workspace path violates local vault boundaries."""


def canonicalize_matter_root(
    root_path: str | Path,
    *,
    product_repo_root: str | Path = PRODUCT_REPO_ROOT,
    allowed_vault_roots: Iterable[str | Path] | str | Path | None = None,
) -> Path:
    """Return a resolved matter root, optionally requiring an approved vault."""

    root = Path(root_path).expanduser().resolve(strict=False)
    repo_root = Path(product_repo_root).expanduser().resolve(strict=False)
    vault_roots = None
    if allowed_vault_roots is not None:
        vault_roots = canonicalize_vault_roots(
            allowed_vault_roots,
            product_repo_root=repo_root,
        )
    if _is_relative_to(root, repo_root):
        raise LegalPathError(
            f"matter root must be outside product repo: {root} is under {repo_root}"
        )
    if vault_roots is not None:
        if not any(_is_relative_to(root, vault_root) for vault_root in vault_roots):
            approved = ", ".join(str(vault_root) for vault_root in vault_roots)
            raise LegalPathError(
                f"matter root must be inside an approved legal vault root: "
                f"{root} is outside {approved}"
            )
    return root


def canonicalize_vault_roots(
    vault_roots: Iterable[str | Path] | str | Path,
    *,
    product_repo_root: str | Path = PRODUCT_REPO_ROOT,
) -> tuple[Path, ...]:
    """Return resolved approved vault roots, rejecting repo-contained roots."""

    repo_root = Path(product_repo_root).expanduser().resolve(strict=False)
    resolved_roots: list[Path] = []
    for raw_root in _path_values(vault_roots):
        vault_root = Path(raw_root).expanduser().resolve(strict=False)
        if _is_relative_to(vault_root, repo_root):
            raise LegalPathError(
                f"legal vault root must be outside product repo: "
                f"{vault_root} is under {repo_root}"
            )
        resolved_roots.append(vault_root)

    if not resolved_roots:
        raise LegalPathError("at least one legal vault root is required")
    return tuple(resolved_roots)


def resolve_matter_child(
    matter_root: str | Path,
    child_path: str | Path,
    *,
    label: str = "path",
    allowed_vault_roots: Iterable[str | Path] | str | Path | None = None,
) -> Path:
    """Resolve a path and require it to stay within the matter root."""

    root = canonicalize_matter_root(
        matter_root,
        allowed_vault_roots=allowed_vault_roots,
    )
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
    *,
    allowed_vault_roots: Iterable[str | Path] | str | Path | None = None,
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
            allowed_vault_roots=allowed_vault_roots,
        )


def _path_values(paths: Iterable[str | Path] | str | Path) -> tuple[str | Path, ...]:
    if isinstance(paths, (str, Path)):
        return (paths,)
    return tuple(paths)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
