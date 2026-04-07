#!/usr/bin/env python3
"""Read-only accessor for the settings-suite registry.

Usage:
    from settings_suite_registry import load_registry, get_option, list_by_classification

    reg = load_registry()
    opt = get_option("simplify")              # returns the slash_commands entry or None
    toggles = list_by_classification("settings_toggle")
    gov = list_governance_relevant()
    stale = list_stale()
"""

import json
from pathlib import Path

REGISTRY_PATH = Path(__file__).parent / "settings_suite_registry.json"


def load_registry() -> dict:
    """Load and return the full registry dict."""
    return json.loads(REGISTRY_PATH.read_text())


def get_option(name: str) -> dict | None:
    """Find an option by name across all sections. Returns first match or None.

    Accepts names with or without leading / or -- (e.g., 'simplify', '/simplify',
    '--model', 'model', 'claude').
    """
    reg = load_registry()
    # Search slash commands
    for cmd in reg.get("slash_commands", []):
        if cmd["name"].lstrip("/") == name.lstrip("/"):
            return cmd
    # Search settings toggles
    for tog in reg.get("settings_toggles", []):
        if tog["key"] == name:
            return tog
    # Search CLI flags
    for flag in reg.get("cli_flags", []):
        if flag["flag"].lstrip("-") == name.lstrip("-"):
            return flag
    # Search runners
    for runner in reg.get("runners", []):
        if runner["name"] == name:
            return runner
    return None


def list_by_classification(classification: str) -> list[dict]:
    """Return all slash_command entries matching a classification category."""
    reg = load_registry()
    return [cmd for cmd in reg.get("slash_commands", [])
            if cmd.get("classification") == classification]


def list_governance_relevant() -> list[dict]:
    """Return all entries marked governance_relevant=True across all sections."""
    results = []
    reg = load_registry()
    for section_key in ("slash_commands", "settings_toggles", "cli_flags", "runners"):
        for entry in reg.get(section_key, []):
            if entry.get("governance_relevant"):
                results.append(entry)
    if reg.get("hooks", {}).get("governance_relevant"):
        results.append(reg["hooks"])
    for srv in reg.get("mcp_servers", []):
        if srv.get("governance_relevant"):
            results.append(srv)
    return results


def list_stale() -> list[dict]:
    """Return all slash command entries classified as nonexistent_stale_assumption."""
    return list_by_classification("nonexistent_stale_assumption")


def list_available() -> list[dict]:
    """Return all entries where available is True (slash commands and runners)."""
    results = []
    reg = load_registry()
    for cmd in reg.get("slash_commands", []):
        if cmd.get("available"):
            results.append(cmd)
    for runner in reg.get("runners", []):
        if runner.get("available"):
            results.append(runner)
    return results


def list_runners() -> list[dict]:
    """Return all runner entries."""
    return load_registry().get("runners", [])


def list_profile_tiers() -> dict:
    """Return the profile_tiers section."""
    return load_registry().get("profile_tiers", {})


def get_open_gaps() -> list[dict]:
    """Return all open_gaps entries."""
    return load_registry().get("open_gaps", [])


def get_stale_references() -> list[dict]:
    """Return all stale_references entries."""
    return load_registry().get("stale_references", [])
