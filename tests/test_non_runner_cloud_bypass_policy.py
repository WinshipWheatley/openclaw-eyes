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
import cassandra_brain  # noqa: E402
import chief_cpa_brain  # noqa: E402
import chief_llm  # noqa: E402


CLOUD_WRAPPERS = {"nemotron_call", "openrouter_call", "claude_call", "claude_json"}
CLAUDE_WRAPPERS = {"claude_call", "claude_json"}
NON_RUNNER_SOURCE_FILES = (
    "chief_brainstorm_brain.py",
    "chief_cpa_brain.py",
    "chief_musiclaw_brain.py",
    "chief_publishing_brain.py",
    "chief_fundo_session.py",
    "cassandra_brain.py",
)

ALLOWED_DIRECT_IMPORTS = {
    ("chief_brainstorm_brain.py", "nemotron_call", "nemotron_call"),
    ("chief_cpa_brain.py", "nemotron_call", "nemotron_call"),
    ("cassandra_brain.py", "nemotron_call", "nemotron_call"),
}

ALLOWED_DIRECT_CALLS = {
    ("chief_brainstorm_brain.py", "nemotron_call", "nemotron_call"),
    ("chief_cpa_brain.py", "nemotron_call", "nemotron_call"),
    ("cassandra_brain.py", "nemotron_call", "nemotron_call"),
}

ALLOWED_DIRECT_NEMOTRON_GATES = {
    ("chief_brainstorm_brain.py", "_synthesize"): "_brainstorm_cloud_safe",
    ("chief_cpa_brain.py", "_parse_expense_from_text"): "_expense_cloud_safe",
    ("cassandra_brain.py", "_call"): "external_model_packet_policy",
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

PROFESSIONAL_PACKET_FIXTURES = [
    ("legal", "Legal matter packet for a law firm client intake."),
    ("musiclaw", "Music Law contract royalty dispute with private deal terms."),
    ("cpa", "CPA tax packet with income, invoice, and payment details."),
    ("publishing", "Publishing catalog registration with splits and private rights admin data."),
    ("gmail", "Gmail private correspondence about a client invoice payment."),
]


def _source_paths() -> list[Path]:
    return [ROOT / filename for filename in NON_RUNNER_SOURCE_FILES]


def _called_name(node: ast.Call) -> str:
    called = node.func
    if isinstance(called, ast.Name):
        return called.id
    if isinstance(called, ast.Attribute):
        if isinstance(called.value, ast.Name):
            return f"{called.value.id}.{called.attr}"
        return called.attr
    return ""


def _function_defs(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _find_function(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for function in _function_defs(tree):
        if function.name == name:
            return function
    raise AssertionError(f"missing function: {name}")


def _function_call_lines(function: ast.FunctionDef | ast.AsyncFunctionDef, names: set[str]) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(function):
        if isinstance(node, ast.Call) and _called_name(node) in names:
            lines.append(node.lineno)
    return sorted(lines)


def _chief_cloud_wrapper_inventory() -> tuple[set[tuple[str, str, str]], set[tuple[str, str, str]]]:
    direct_imports: set[tuple[str, str, str]] = set()
    direct_calls: set[tuple[str, str, str]] = set()

    for path in _source_paths():
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


def _direct_wrapper_call_sites(wrapper_name: str) -> set[tuple[str, str, int]]:
    sites: set[tuple[str, str, int]] = set()

    for path in _source_paths():
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
                    if alias.name == wrapper_name:
                        local_wrapper_names[alias.asname or alias.name] = alias.name

        for function in _function_defs(tree):
            for node in ast.walk(function):
                if not isinstance(node, ast.Call):
                    continue
                called_name = _called_name(node)
                if local_wrapper_names.get(called_name) == wrapper_name:
                    sites.add((path.name, function.name, node.lineno))
                elif called_name == wrapper_name:
                    sites.add((path.name, function.name, node.lineno))
                elif any(called_name == f"{alias}.{wrapper_name}" for alias in chief_llm_module_aliases):
                    sites.add((path.name, function.name, node.lineno))

    return sites


def test_allowed_direct_nemotron_call_sites_are_policy_gated():
    sites = _direct_wrapper_call_sites("nemotron_call")
    assert {(filename, function_name) for filename, function_name, _line in sites} == set(
        ALLOWED_DIRECT_NEMOTRON_GATES
    )

    for filename, function_name, call_line in sites:
        tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"), filename=filename)
        function = _find_function(tree, function_name)
        gate_name = ALLOWED_DIRECT_NEMOTRON_GATES[(filename, function_name)]
        gate_lines = _function_call_lines(function, {gate_name})

        assert any(line < call_line for line in gate_lines), (filename, function_name, call_line)
        if gate_name != "external_model_packet_policy":
            guard_function = _find_function(tree, gate_name)
            assert _function_call_lines(guard_function, {"external_model_packet_policy"}), (
                filename,
                gate_name,
            )


def test_no_direct_openrouter_call_sites_in_agent_brains():
    assert _direct_wrapper_call_sites("openrouter_call") == set()


def _agent_claude_wrapper_inventory() -> tuple[set[tuple[str, str, str]], set[tuple[str, str, str]]]:
    direct_imports: set[tuple[str, str, str]] = set()
    direct_calls: set[tuple[str, str, str]] = set()

    for path in _source_paths():
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


def test_chief_llm_claude_wrappers_are_fail_closed_definitions():
    tree = ast.parse((ROOT / "chief_llm.py").read_text(encoding="utf-8"), filename="chief_llm.py")

    claude_call_function = _find_function(tree, "claude_call")
    claude_json_function = _find_function(tree, "claude_json")

    for function in (claude_call_function, claude_json_function):
        docstring = ast.get_docstring(function) or ""
        lowered_docstring = docstring.lower()
        assert "human-only" in lowered_docstring or "blocked" in lowered_docstring
        assert not _function_call_lines(function, {"subprocess.run"})

    claude_call_returns = [node.value for node in ast.walk(claude_call_function) if isinstance(node, ast.Return)]
    assert any(isinstance(value, ast.Constant) and value.value == "" for value in claude_call_returns)

    claude_json_returns = [node.value for node in ast.walk(claude_json_function) if isinstance(node, ast.Return)]
    assert any(isinstance(value, ast.Dict) and not value.keys for value in claude_json_returns)


@pytest.mark.parametrize("cloud_flag", ["cloud_allowed", "allow_cloud", "cloud_ok"])
@pytest.mark.parametrize("label,packet", PROFESSIONAL_PACKET_FIXTURES)
def test_external_model_policy_blocks_professional_packets_even_with_cloud_metadata(label, packet, cloud_flag):
    policy = chief_llm.external_model_packet_policy(
        packet,
        metadata={"data_classification": "non_sensitive", cloud_flag: "true"},
    )

    assert policy["external_model_safe"] is False, label
    assert policy["sensitive"] is True, policy
    assert policy["reason"].startswith("blocked_"), policy


def test_external_model_policy_fails_closed_for_unclassified_packet():
    policy = chief_llm.external_model_packet_policy("Update an ordinary helper.")

    assert policy["external_model_safe"] is False
    assert policy["sensitive"] is False
    assert policy["reason"] == "cloud_not_explicitly_allowed"


def test_external_model_policy_allows_explicit_public_synthetic_packet():
    policy = chief_llm.external_model_packet_policy(
        "Synthetic public fixture for a generic parser helper.",
        metadata={"data_classification": "synthetic_public", "cloud_allowed": "true"},
    )

    assert policy["external_model_safe"] is True
    assert policy["sensitive"] is False
    assert policy["reason"] == "explicit_cloud_allowed_public_or_synthetic"


@pytest.mark.parametrize("cloud_flag", ["cloud_allowed", "allow_cloud", "cloud_ok"])
def test_external_model_policy_treats_cloud_allowance_aliases_as_explicit_safe_metadata(cloud_flag):
    policy = chief_llm.external_model_packet_policy(
        "Synthetic public fixture for a generic parser helper.",
        metadata={"data_classification": "synthetic_public", cloud_flag: "true"},
    )

    assert policy["external_model_safe"] is True
    assert policy["cloud_allowed"] is True


@pytest.mark.parametrize("label,packet", PROFESSIONAL_PACKET_FIXTURES)
def test_non_runner_cloud_gates_block_professional_packets(label, packet):
    assert chief_brainstorm_brain._brainstorm_cloud_safe(packet) is False, label
    assert chief_cpa_brain._expense_cloud_safe(packet) is False, label


def _cassandra_clean_context(query: str, *, context_snapshot: str = "") -> bool:
    return cassandra_brain._cassandra_context_clean(
        "",
        "",
        "",
        "",
        "",
        "",
        context_snapshot,
        query,
    )


@pytest.mark.parametrize("label,packet", PROFESSIONAL_PACKET_FIXTURES)
def test_cassandra_cloud_gate_blocks_professional_packets_without_live_context(label, packet):
    assert _cassandra_clean_context(packet) is False, label


def test_cassandra_cloud_gate_fails_closed_for_unclassified_packet():
    assert _cassandra_clean_context("Update an ordinary helper.") is False


def test_cassandra_cloud_gate_delegates_clean_context_to_central_policy(monkeypatch):
    calls = []

    def fake_policy(packet, metadata=None):
        calls.append({"packet": packet, "metadata": metadata})
        return {"external_model_safe": True}

    monkeypatch.setattr(cassandra_brain, "external_model_packet_policy", fake_policy)

    assert _cassandra_clean_context("Synthetic public fixture for a generic reply.") is True
    assert calls == [
        {
            "packet": {
                "query": "Synthetic public fixture for a generic reply.",
                "context_snapshot": "",
            },
            "metadata": {"workload": "cassandra_user_reply"},
        }
    ]


def test_cassandra_cloud_ok_true_still_requires_external_model_policy(monkeypatch):
    def forbidden_nemotron(*args, **kwargs):
        raise AssertionError("cloud_ok=True must not bypass central external-model policy")

    monkeypatch.setattr(cassandra_brain, "nemotron_call", forbidden_nemotron)
    monkeypatch.setattr(
        cassandra_brain,
        "resolve_local_model",
        lambda prompt, lane=None, task_class=None: ("chief-fast:latest", "fast"),
    )
    monkeypatch.setattr(
        cassandra_brain,
        "ollama_call",
        lambda prompt, timeout=0, model=None, lane=None, task_class=None: "local reply",
    )

    reply = cassandra_brain._call(
        "Synthetic public prompt without explicit classification metadata.",
        task_class="cassandra_user_reply",
        cloud_ok=True,
    )

    assert reply == "local reply"


def test_cassandra_cloud_ok_allows_only_explicit_public_metadata(monkeypatch):
    local_calls = []

    monkeypatch.setattr(cassandra_brain, "nemotron_call", lambda *args, **kwargs: "cloud reply")
    monkeypatch.setattr(
        cassandra_brain,
        "ollama_call",
        lambda *args, **kwargs: local_calls.append(args) or "local reply",
    )

    reply = cassandra_brain._call(
        "Synthetic public fixture for a generic reply.",
        task_class="cassandra_user_reply",
        cloud_ok=True,
        external_model_metadata={"data_classification": "synthetic_public", "cloud_allowed": "true"},
    )

    assert reply == "cloud reply"
    assert local_calls == []


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
