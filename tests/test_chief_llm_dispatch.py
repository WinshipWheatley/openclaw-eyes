from __future__ import annotations

import inspect
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
import provider_policy_registry as registry


def _reset_auth_cache():
    chief_llm._AUTH_OBS_CACHE = None


def test_dispatch_lane_cascades_to_local_when_candidates_unavailable(monkeypatch):
    _reset_auth_cache()
    monkeypatch.setattr(auth_status, "collect_candidate_auth_observations", lambda: {"cached": {"ok": True}})
    monkeypatch.setattr(auth_status, "candidate_available", lambda candidate_id, *, observations=None: {"available": False})
    monkeypatch.setattr(chief_llm, "ollama_call", lambda *args, **kwargs: "local")

    assert chief_llm.dispatch_lane("hi", lane_id="balanced") == "local"


def test_dispatch_lane_picks_first_available_candidate(monkeypatch):
    _reset_auth_cache()
    seen = []
    monkeypatch.setattr(auth_status, "collect_candidate_auth_observations", lambda: {"cached": {"ok": True}})

    def fake_available(candidate_id, *, observations=None):
        seen.append((candidate_id, observations))
        return {"available": candidate_id == "kimi_openrouter"}

    monkeypatch.setattr(auth_status, "candidate_available", fake_available)
    monkeypatch.setattr(lanes, "run_candidate", lambda candidate_id, *args, **kwargs: "kimi-ans" if candidate_id == "kimi_openrouter" else "")

    assert chief_llm.dispatch_lane("hi", lane_id="fast", metadata={"classification": "public", "cloud_allowed": True}) == "kimi-ans"
    assert seen[0][0] == "local_qwen_fast"
    assert seen[1][0] == "kimi_openrouter"
    assert all(row[1] == {"cached": {"ok": True}} for row in seen)


def test_dispatch_lane_does_not_fabricate_cloud_allowed(monkeypatch):
    _reset_auth_cache()
    metadata_seen = []
    monkeypatch.setattr(auth_status, "collect_candidate_auth_observations", lambda: {})
    monkeypatch.setattr(
        auth_status,
        "candidate_available",
        lambda candidate_id, *, observations=None: {"available": candidate_id in {"kimi_openrouter", "local_qwen_fast"}},
    )

    def fake_run(candidate_id, prompt, *, metadata=None, **kwargs):
        metadata_seen.append((candidate_id, metadata))
        if candidate_id == "kimi_openrouter":
            return "router" if metadata and metadata.get("cloud_allowed") is True else ""
        return "local"

    monkeypatch.setattr(lanes, "run_candidate", fake_run)

    assert chief_llm.dispatch_lane("hi", lane_id="cheap_bulk", metadata={"classification": "public"}) == "local"
    assert metadata_seen[0] == ("kimi_openrouter", {"classification": "public"})


def test_dispatch_lane_collects_observations_once(monkeypatch):
    _reset_auth_cache()
    calls = []
    availability_kwargs = []
    run_kwargs = []
    monkeypatch.setattr(auth_status, "collect_candidate_auth_observations", lambda: calls.append("collect") or {"obs": {"ok": True}})

    def fake_available(candidate_id, *, observations=None):
        availability_kwargs.append(observations)
        return {"available": candidate_id == "kimi_openrouter"}

    def fake_run(candidate_id, prompt, **kwargs):
        run_kwargs.append(kwargs)
        return "done"

    monkeypatch.setattr(auth_status, "candidate_available", fake_available)
    monkeypatch.setattr(lanes, "run_candidate", fake_run)

    assert chief_llm.dispatch_lane("hi", lane_id="fast", metadata={"classification": "public", "cloud_allowed": True}) == "done"
    assert calls == ["collect"]
    assert availability_kwargs
    assert all(observations == {"obs": {"ok": True}} for observations in availability_kwargs)
    assert run_kwargs[0]["observations"] == {"obs": {"ok": True}}


def test_candidate_observation_collector_uses_only_shipped_probe_ids(monkeypatch):
    called = []

    def fake_probe(command_id, command, *, timeout_seconds=8):
        called.append(command_id)
        return {"command_id": command_id, "ok": True, "_stdout": "", "_stderr": ""}

    monkeypatch.setattr(auth_status, "run_safe_auth_probe_command", fake_probe)
    auth_status.collect_candidate_auth_observations()

    retired = {
        "".join(("ge", "mini_which")),
        "".join(("ge", "mini_version")),
        "".join(("ge", "mini_help")),
        "".join(("a", "gy_which")),
        "".join(("a", "gy_version")),
        "".join(("a", "gy_help")),
    }
    assert retired.isdisjoint(set(called))


def test_direct_cli_wrappers_preserve_fail_closed_gates(monkeypatch):
    spawned = []
    monkeypatch.setattr(lanes.subprocess, "run", lambda *args, **kwargs: spawned.append((args, kwargs)) or subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr=""))

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

    assert chief_llm.codex_exec_call("hi") == ""
    assert chief_llm.claude_cli_call("hi") == ""
    assert chief_llm.claude_cli_call("hi", allow_claude_cli=True) == "ok"

    spawned.clear()
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
    assert chief_llm.claude_cli_call("hi", allow_claude_cli=True) == ""
    assert spawned == []


def test_added_code_backend_token_guard_and_known_debt():
    forbidden = re.compile(
        r"(?i)\b("
        + "|".join(
            [
                "".join(("ge", "mini")),
                "".join(("go", "ogle")),
                "".join(("ge", "nai")),
                "".join(("ver", "tex")),
                "".join(("a", "gy")),
                "".join(("anti", "gravity")),
            ]
        )
        + r")\b"
    )

    full_sources = [
        Path("provider_lanes.py").read_text(encoding="utf-8"),
        Path("tests/test_provider_lanes.py").read_text(encoding="utf-8"),
        Path("tests/test_chief_llm_dispatch.py").read_text(encoding="utf-8"),
    ]
    added_sources = [
        inspect.getsource(auth_status.candidate_available),
        inspect.getsource(auth_status.collect_candidate_auth_observations),
        inspect.getsource(auth_status._candidate_probe_command_ids),
        inspect.getsource(chief_llm._candidate_auth_observations),
        inspect.getsource(chief_llm.codex_exec_call),
        inspect.getsource(chief_llm.claude_cli_call),
        inspect.getsource(chief_llm.dispatch_lane),
    ]
    assert not forbidden.search("\n".join(full_sources + added_sources))

    assert chief_llm._GREP_GUARD_KNOWN_DEBT == {"nemotron_call"}
    assert "nemotron_call" not in inspect.getsource(lanes.run_candidate)
    assert "nemotron_call" not in inspect.getsource(chief_llm.dispatch_lane)

