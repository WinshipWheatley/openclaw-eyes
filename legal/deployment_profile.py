"""Portable deployment profile helpers for local legal installs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.path_guard import LegalPathError, canonicalize_vault_roots


REQUIRED_MODULES = (
    "matter_workspace",
    "local_ingestion",
    "local_search",
    "search_report",
    "demo_workflow",
)
REQUIRED_AGENT_LABELS = ("cassandra", "chief", "guardian", "hermes")
REQUIRED_SAFETY_DEFAULTS = (
    "no_autonomous_send",
    "require_attorney_review",
    "no_cloud_llm_by_default",
    "source_grounded_outputs",
    "audit_all_actions",
)
REQUIRED_CONNECTORS = ("gmail_enabled", "calendar_enabled", "drive_enabled")
REQUIRED_TOP_LEVEL = (
    "profile_name",
    "firm_name",
    "created_at",
    "mode",
    "enabled_modules",
    "agent_labels",
    "safety_defaults",
    "storage",
    "connectors",
)


def default_legal_local_profile(
    firm_name: str,
    *,
    profile_name: str = "legal-local",
) -> dict[str, Any]:
    """Return a portable local-first legal deployment profile."""

    return {
        "profile_name": profile_name,
        "firm_name": firm_name,
        "created_at": _utc_now(),
        "mode": "local_first",
        "enabled_modules": {
            "matter_workspace": True,
            "local_ingestion": True,
            "local_search": True,
            "search_report": True,
            "demo_workflow": False,
        },
        "agent_labels": {
            "cassandra": "Legal Intake Assistant",
            "chief": "Legal Operations Coordinator",
            "guardian": "Review and Safety Gate",
            "hermes": "Client Communications Relay",
        },
        "safety_defaults": {
            "no_autonomous_send": True,
            "require_attorney_review": True,
            "no_cloud_llm_by_default": True,
            "source_grounded_outputs": True,
            "audit_all_actions": True,
        },
        "storage": {
            "matters_root": "matters",
            "exports_root": None,
        },
        "connectors": {
            "gmail_enabled": False,
            "calendar_enabled": False,
            "drive_enabled": False,
        },
    }


def validate_deployment_profile(profile: dict[str, Any]) -> list[str]:
    """Return readable validation errors for a deployment profile."""

    errors: list[str] = []
    if not isinstance(profile, dict):
        return ["profile must be a dict"]

    for key in REQUIRED_TOP_LEVEL:
        if key not in profile:
            errors.append(f"missing required field: {key}")

    _require_non_empty_string(profile, "profile_name", errors)
    _require_non_empty_string(profile, "firm_name", errors)
    _require_non_empty_string(profile, "created_at", errors)

    if profile.get("mode") != "local_first":
        errors.append("mode must be 'local_first'")

    _validate_bool_section(
        profile,
        "enabled_modules",
        REQUIRED_MODULES,
        errors,
    )
    _validate_string_section(
        profile,
        "agent_labels",
        REQUIRED_AGENT_LABELS,
        errors,
    )
    _validate_bool_section(
        profile,
        "safety_defaults",
        REQUIRED_SAFETY_DEFAULTS,
        errors,
    )
    _validate_storage(profile, errors)
    _validate_bool_section(
        profile,
        "connectors",
        REQUIRED_CONNECTORS,
        errors,
    )
    return errors


def save_deployment_profile(profile: dict[str, Any], path: str | Path) -> None:
    """Save a deployment profile as stable JSON."""

    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(profile, handle, indent=2, sort_keys=True)
        handle.write("\n")


def load_deployment_profile(path: str | Path) -> dict[str, Any]:
    """Load a deployment profile JSON file."""

    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_bool_section(
    profile: dict[str, Any],
    section_name: str,
    required_keys: tuple[str, ...],
    errors: list[str],
) -> None:
    section = profile.get(section_name)
    if not isinstance(section, dict):
        errors.append(f"{section_name} must be a dict")
        return
    for key in required_keys:
        if key not in section:
            errors.append(f"{section_name}.{key} is required")
        elif not isinstance(section[key], bool):
            errors.append(f"{section_name}.{key} must be a bool")


def _validate_string_section(
    profile: dict[str, Any],
    section_name: str,
    required_keys: tuple[str, ...],
    errors: list[str],
) -> None:
    section = profile.get(section_name)
    if not isinstance(section, dict):
        errors.append(f"{section_name} must be a dict")
        return
    for key in required_keys:
        if key not in section:
            errors.append(f"{section_name}.{key} is required")
        elif not isinstance(section[key], str) or not section[key].strip():
            errors.append(f"{section_name}.{key} must be a non-empty string")


def _validate_storage(profile: dict[str, Any], errors: list[str]) -> None:
    storage = profile.get("storage")
    if not isinstance(storage, dict):
        errors.append("storage must be a dict")
        return
    matters_root = storage.get("matters_root")
    if not isinstance(matters_root, str) or not matters_root.strip():
        errors.append("storage.matters_root must be a non-empty string")
    exports_root = storage.get("exports_root")
    if exports_root is not None and not isinstance(exports_root, str):
        errors.append("storage.exports_root must be a string or null")
    if "vault_roots" in storage:
        _validate_vault_roots(storage["vault_roots"], errors)


def _validate_vault_roots(vault_roots: Any, errors: list[str]) -> None:
    if not isinstance(vault_roots, list):
        errors.append("storage.vault_roots must be a list")
        return
    if not vault_roots:
        errors.append("storage.vault_roots must not be empty when present")
        return
    invalid = [
        index
        for index, vault_root in enumerate(vault_roots)
        if not isinstance(vault_root, str) or not vault_root.strip()
    ]
    if invalid:
        errors.append("storage.vault_roots entries must be non-empty strings")
        return
    try:
        canonicalize_vault_roots(vault_roots)
    except LegalPathError as exc:
        errors.append(f"storage.vault_roots invalid: {exc}")


def _require_non_empty_string(
    profile: dict[str, Any],
    key: str,
    errors: list[str],
) -> None:
    if key not in profile:
        return
    if not isinstance(profile[key], str) or not profile[key].strip():
        errors.append(f"{key} must be a non-empty string")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
