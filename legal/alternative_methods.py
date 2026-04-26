"""Deterministic next-action model for unsupported legal source files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from legal.local_capability_policy import local_capability_policy_for_source
from legal.path_guard import (
    canonicalize_matter_root,
    validate_manifest_source_paths,
)


ARTIFACT_TYPE = "alternative_methods_v0"
MANIFEST_FILENAME = "manifest.json"
ACTIONABLE_STATUSES = {"unsupported", "failed", "no_text"}


def alternative_methods_for_matter(
    matter_root: str | Path,
    *,
    allowed_vault_roots: Iterable[str | Path] | str | Path | None = None,
    escalation_allowed: bool = False,
) -> dict[str, Any]:
    """Return sanitized next actions for sources needing alternate handling."""

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
    items = [
        _item_for_source(index, source, escalation_allowed=escalation_allowed)
        for index, source in enumerate(sources, start=1)
        if _source_status(source) in ACTIONABLE_STATUSES
    ]
    return {
        "artifact_type": ARTIFACT_TYPE,
        "source_count": len(sources),
        "needs_alternative_methods": len(items),
        "items": items,
        "content_excluded": True,
        "private_paths_excluded": True,
    }


def _item_for_source(
    source_index: int,
    source: dict[str, Any],
    *,
    escalation_allowed: bool,
) -> dict[str, Any]:
    status = _source_status(source)
    extension = _source_extension(source)
    available_actions = [
        "view_technical_details",
        "support_packet_available",
        "ignore_for_now",
    ]
    locked_actions = ["request_feature"]

    if status == "unsupported":
        available_actions.insert(0, "try_local_capability")
    if status == "no_text" and extension == ".pdf":
        available_actions.insert(0, "ocr_module_needed")
    if escalation_allowed:
        locked_actions = []
        available_actions.append("request_feature")

    item = {
        "source_index": source_index,
        "source_id_present": bool(source.get("source_id")),
        "status": status,
        "file_extension": extension,
        "reason_category": _reason_category(source),
        "available_actions": available_actions,
        "locked_actions": locked_actions,
    }
    item.update(local_capability_policy_for_source(source))
    if escalation_allowed:
        item["request_feature_state"] = "available"
    return item


def _source_status(source: dict[str, Any]) -> str:
    status = source.get("extraction_status")
    if isinstance(status, str) and status.strip():
        return status
    extension = _source_extension(source)
    if extension and extension not in {".md", ".pdf", ".txt"}:
        return "unsupported"
    return "pending"


def _source_extension(source: dict[str, Any]) -> str | None:
    stored_path = source.get("stored_path")
    if not isinstance(stored_path, str):
        return None
    return Path(stored_path).suffix.lower() or None


def _reason_category(source: dict[str, Any]) -> str | None:
    status = _source_status(source)
    extension = _source_extension(source)
    reason = source.get("extraction_reason")
    reason_text = reason.casefold() if isinstance(reason, str) else ""
    if status == "unsupported":
        return "unsupported_file_type"
    if status == "no_text" and extension == ".pdf":
        return "ocr_module_needed"
    if status == "no_text":
        return "no_extractable_text"
    if "unavailable" in reason_text:
        return "local_extractor_unavailable"
    if status == "failed":
        return "local_extraction_failed"
    return None


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
