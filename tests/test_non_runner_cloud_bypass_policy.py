from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chief_brainstorm_brain  # noqa: E402
import chief_cpa_brain  # noqa: E402
import chief_llm  # noqa: E402


CLOUD_WRAPPERS = {"nemotron_call", "claude_call", "claude_json"}
CLAUDE_WRAPPERS = {"claude_call", "claude_json"}

ALLOWED_DIRECT_IMPORTS = {
    ("chief_brainstorm_brain.py", "nemotron_call", "nemotron_call"),
    ("chief_cpa_brain.py", "nemotron_call", "nemotron_call"),
}

ALLOWED_DIRECT_CALLS = {
    ("chief_brainstorm_brain.py", "nemotron_call", "nemotron_call"),
    ("chief_cpa_brain.py", "nemotron_call", "nemotron_call"),
}

HARD_DENY_MARKERS = [
    "/mnt/c/OpenClawLegalPrivate",
    "OpenClawLegalPrivate",
    "Gmail body",
    "private correspondence",
    ".env",
    "token",
    "secret",
    "PII vault",
    "private vault",
    "Legal matter",
    "client matter",
]


def _chief_cloud_wrapper_inventory() -> tuple[set[tuple[str, str, str]], set[tuple[str, str, str]]]:
    direct_imports: set[tuple[str, str, str]] = set()
    direct_calls: set[tuple[str, str, str]] = set()

    for path in sorted(ROOT.glob("chief_*.py")):
        if path.name == "chief_llm.py":
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        local_wrapper_names: dict[str, str] = {}
        chief_llm_module_aliases: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "chief_llm":
                        chief_llm_module_aliases.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module == "chief_llm":
                for alias in node.names:
                    if alias.name == "*":
                        direct_imports.add((path.name, "*", "*"))
                    elif alias.name in CLOUD_WRAPPERS:
                        local_name = alias.asname or alias.name
                        local_wrapper_names[local_name] = alias.name
                        direct_imports.add((path.name, alias.name, local_name))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = node.func
            if isinstance(called, ast.Name):
                if called.id in local_wrapper_names:
                    direct_calls.add((path.name, local_wrapper_names[called.id], called.id))
                elif called.id in CLOUD_WRAPPERS:
                    direct_calls.add((path.name, called.id, called.id))
            elif (
                isinstance(called, ast.Attribute)
                and called.attr in CLOUD_WRAPPERS
                and isinstance(called.value, ast.Name)
                and called.value.id in chief_llm_module_aliases
            ):
                direct_calls.add((path.name, called.attr, f"{called.value.id}.{called.attr}"))

    return direct_imports, direct_calls


def test_direct_chief_cloud_wrapper_inventory_matches_allowlist():
    direct_imports, direct_calls = _chief_cloud_wrapper_inventory()

    assert direct_imports == ALLOWED_DIRECT_IMPORTS
    assert direct_calls == ALLOWED_DIRECT_CALLS


def _agent_claude_wrapper_inventory() -> tuple[set[tuple[str, str, str]], set[tuple[str, str, str]]]:
    direct_imports: set[tuple[str, str, str]] = set()
    direct_calls: set[tuple[str, str, str]] = set()

    paths = sorted(ROOT.glob("chief_*.py")) + [ROOT / "cassandra_brain.py"]
    for path in paths:
        if path.name == "chief_llm.py":
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        local_wrapper_names: dict[str, str] = {}
        chief_llm_module_aliases: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "chief_llm":
                        chief_llm_module_aliases.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module == "chief_llm":
                for alias in node.names:
                    if alias.name == "*":
                        direct_imports.add((path.name, "*", "*"))
                    elif alias.name in CLAUDE_WRAPPERS:
                        local_name = alias.asname or alias.name
                        local_wrapper_names[local_name] = alias.name
                        direct_imports.add((path.name, alias.name, local_name))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = node.func
            if isinstance(called, ast.Name):
                if called.id in local_wrapper_names:
                    direct_calls.add((path.name, local_wrapper_names[called.id], called.id))
                elif called.id in CLAUDE_WRAPPERS:
                    direct_calls.add((path.name, called.id, called.id))
            elif (
                isinstance(called, ast.Attribute)
                and called.attr in CLAUDE_WRAPPERS
                and isinstance(called.value, ast.Name)
                and called.value.id in chief_llm_module_aliases
            ):
                direct_calls.add((path.name, called.attr, f"{called.value.id}.{called.attr}"))

    return direct_imports, direct_calls


def test_agent_brains_do_not_import_or_call_claude_wrappers():
    direct_imports, direct_calls = _agent_claude_wrapper_inventory()

    assert direct_imports == set()
    assert direct_calls == set()


@pytest.mark.parametrize("marker", HARD_DENY_MARKERS)
def test_brainstorm_hard_deny_markers_do_not_route_to_nemotron(monkeypatch, marker):
    local_calls = []

    def forbidden_nemotron(*args, **kwargs):
        raise AssertionError(f"Nemotron must not receive hard deny marker: {marker}")

    def fake_local_model(prompt, timeout=0, task_class=None):
        local_calls.append({"timeout": timeout, "task_class": task_class})
        return json.dumps({
            "title": "Local brainstorm",
            "summary": "Local fallback handled the blocked input.",
            "domain": "other",
            "complexity": "medium",
            "timing_class": "later",
            "recommended_next_step": "Review locally",
            "idea_type": "note",
        })

    monkeypatch.setattr(chief_brainstorm_brain, "nemotron_call", forbidden_nemotron)
    monkeypatch.setattr(chief_brainstorm_brain, "ollama_call", fake_local_model)

    result = chief_brainstorm_brain._synthesize(
        f"Synthetic brainstorm fixture with hard deny marker: {marker}"
    )

    assert result["title"] == "Local brainstorm"
    assert local_calls == [{"timeout": 60, "task_class": "chief_structured_plan"}]


@pytest.mark.parametrize("marker", HARD_DENY_MARKERS)
def test_cpa_hard_deny_markers_do_not_route_to_nemotron(monkeypatch, marker):
    local_calls = []

    def forbidden_nemotron(*args, **kwargs):
        raise AssertionError(f"Nemotron must not receive hard deny marker: {marker}")

    def fake_local_json(prompt, timeout=0, task_class=None):
        local_calls.append({"timeout": timeout, "task_class": task_class})
        return {
            "date": "2026-04-29",
            "amount": 12.0,
            "category": "supplies",
            "description": "local blocked fixture",
        }

    monkeypatch.setattr(chief_cpa_brain, "nemotron_call", forbidden_nemotron)
    monkeypatch.setattr(chief_cpa_brain, "ollama_json", fake_local_json)

    result = chief_cpa_brain._parse_expense_from_text(
        f"Bought a notebook for $12. Hard deny marker: {marker}"
    )

    assert result is not None
    assert result["description"] == "local blocked fixture"
    assert local_calls == [{"timeout": 20, "task_class": None}]


@pytest.mark.parametrize("env_value", [None, "", "0", "false", "no", "1", "true", "yes"])
def test_claude_wrappers_are_blocked_even_with_manual_override_env(monkeypatch, env_value):
    if env_value is None:
        monkeypatch.delenv("OPENCLAW_ALLOW_CLAUDE_MANUAL", raising=False)
    else:
        monkeypatch.setenv("OPENCLAW_ALLOW_CLAUDE_MANUAL", env_value)

    def forbidden_process(*args, **kwargs):
        raise AssertionError("Claude subprocess must not spawn from OpenClaw agents")

    monkeypatch.setattr(chief_llm.subprocess, "run", forbidden_process)

    assert chief_llm.claude_call("synthetic public prompt", timeout=1, retries=1) == ""
    assert chief_llm.claude_json('{"ok": true}', timeout=1, retries=1) == {}
