from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chief_llm
import provider_access_auth_status as auth_status
import provider_lanes as lanes


def test_registry_integrity_and_local_floors():
    for lane_id, candidate_ids in lanes.LANES.items():
        assert candidate_ids, lane_id
        assert all(lanes.get_candidate(candidate_id) is not None for candidate_id in candidate_ids)
        assert lanes.get_candidate(candidate_ids[-1]).transport == "ollama"
        if lane_id != "local_only":
            assert len(set(candidate_ids)) >= 2

    for candidate in lanes.CANDIDATES:
        assert candidate.transport in {"ollama", "codex", "claude", "openrouter"}
        assert candidate.is_metered_api is False
        if candidate.is_cloud:
            assert lanes.rank(candidate.max_privacy_level) <= lanes.rank("TOKENIZED_SENSITIVE_METADATA")
        else:
            assert candidate.max_privacy_level == "RAW_PRIVATE_BODY"


def test_build_cli_command_keeps_prompt_as_single_argv_element():
    prompt = "quote ; rm -rf / && still one arg"

    assert lanes.build_cli_command(lanes.get_candidate("codex_exec"), prompt) == ["codex", "exec", prompt]
    assert lanes.build_cli_command(lanes.get_candidate("claude_cli"), prompt) == [
        "claude",
        "-p",
        prompt,
        "--model",
        "opus",
    ]


def test_cost_guard_is_fail_closed_for_capped_and_metered_candidates(monkeypatch):
    local = lanes.get_candidate("local_qwen_fast")
    codex = lanes.get_candidate("codex_exec")
    router = lanes.get_candidate("kimi_openrouter")

    lanes.cost_guard_check(local)
    lanes.cost_guard_check(codex)

    monkeypatch.delenv("OPENROUTER_PREPAID_CAP_USD", raising=False)
    monkeypatch.delenv("OPENROUTER_SPENT_USD", raising=False)
    monkeypatch.delenv("OPENROUTER_AUTOTOPUP", raising=False)
    try:
        lanes.cost_guard_check(router)
    except lanes.CostGuardRefusal as exc:
        assert exc.reason == "openrouter_prepaid_gate_closed"
    else:
        raise AssertionError("capped candidate must refuse with default env")

    monkeypatch.setenv("OPENROUTER_PREPAID_CAP_USD", "5")
    monkeypatch.setenv("OPENROUTER_SPENT_USD", "0")
    lanes.cost_guard_check(router)
    monkeypatch.setenv("OPENROUTER_AUTOTOPUP", "1")
    try:
        lanes.cost_guard_check(router)
    except lanes.CostGuardRefusal:
        pass
    else:
        raise AssertionError("auto top-up must close the gate")

    synthetic = lanes.synthetic_metered_candidate()
    monkeypatch.delenv("OPENCLAW_ALLOW_METERED_API", raising=False)
    try:
        lanes.cost_guard_check(synthetic)
    except lanes.CostGuardRefusal as exc:
        assert exc.reason == "metered_api_refused"
    else:
        raise AssertionError("metered candidate must default-refuse")
    monkeypatch.setenv("OPENCLAW_ALLOW_METERED_API", "1")
    lanes.cost_guard_check(synthetic, per_call_budget_usd=0.01)


def test_minimal_cli_env_is_strict_allowlist(monkeypatch):
    source = {
        "PATH": "/usr/bin",
        "HOME": "/home/openclaw",
        "LANG": "C.UTF-8",
        "CODEX_HOME": "/tmp/codex",
        "PII_VAULT_KEY": "x",
        "OPENROUTER_API_KEY": "x",
        "MY_SECRET_TOKEN": "x",
        "OPENCLAW_TEST_SENTINEL_SECRET": "x",
        "ANTHROPIC_BASE_URL": "http://example.invalid",
        "HTTPS_PROXY": "http://proxy.invalid",
        "OPENAI_PROXY": "http://proxy.invalid",
        "GITHUB_PAT": "x",
        "BEARER": "x",
        "COOKIE": "x",
    }

    child = lanes._minimal_cli_env(lanes.get_candidate("codex_exec"), source_env=source)

    assert child == {"CODEX_HOME": "/tmp/codex", "HOME": "/home/openclaw", "LANG": "C.UTF-8", "PATH": "/usr/bin"}
    assert not any(re.search(r"(?i)(key|token|secret|credential|password)", key) for key in child)


def test_run_candidate_cli_paths_fail_closed_and_do_not_spawn_when_blocked(monkeypatch):
    spawned = []

    def fake_run(*args, **kwargs):
        spawned.append((args, kwargs))
        return subprocess.CompletedProcess(args[0], 0, stdout="hi\n", stderr="")

    monkeypatch.setattr(lanes.subprocess, "run", fake_run)
    monkeypatch.setattr(
        auth_status,
        "candidate_available",
        lambda candidate_id, *, observations=None: {
            "candidate_id": candidate_id,
            "available": True,
            "reason": "authenticated_subscription",
            "transport": "claude",
        },
    )

    assert lanes.run_candidate("claude_cli", "hello", allow_claude_cli=True) == "hi"
    assert spawned

    spawned.clear()
    assert lanes.run_candidate("claude_cli", "hello", allow_claude_cli=False) == ""
    assert spawned == []

    spawned.clear()
    assert lanes.run_candidate("codex_exec", "hello") == ""
    assert spawned == []


def test_run_candidate_direct_billing_chokepoint_blocks_without_spawn(monkeypatch):
    spawned = []
    monkeypatch.setattr(lanes.subprocess, "run", lambda *args, **kwargs: spawned.append((args, kwargs)))
    monkeypatch.setattr(
        auth_status,
        "candidate_available",
        lambda candidate_id, *, observations=None: {
            "candidate_id": candidate_id,
            "available": False,
            "reason": "billing_mode_unproven",
            "transport": "claude",
        },
    )

    assert lanes.run_candidate("claude_cli", "hello", allow_claude_cli=True) == ""
    assert lanes.run_candidate("codex_exec", "hello") == ""
    assert spawned == []


def test_run_candidate_openrouter_and_local_paths(monkeypatch):
    called = []

    monkeypatch.delenv("OPENROUTER_PREPAID_CAP_USD", raising=False)
    monkeypatch.setattr(chief_llm, "openrouter_call", lambda *args, **kwargs: called.append("router") or "router")
    assert lanes.run_candidate("kimi_openrouter", "hello", metadata={"classification": "public", "cloud_allowed": True}) == ""
    assert called == []

    monkeypatch.setattr(chief_llm, "ollama_call", lambda *args, **kwargs: "local-ans")
    assert lanes.run_candidate("local_qwen_fast", "hello") == "local-ans"

