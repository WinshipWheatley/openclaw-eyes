from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import runner_profiles as profiles  # noqa: E402


def test_cloud_runner_fails_closed_when_headroom_policy_missing(monkeypatch):
    monkeypatch.setattr(profiles, "_load_headroom_policy", lambda: {})

    result = profiles._check_headroom_policy("codex", "standard", {})

    assert result["allow"] is False
    assert result["headroom_state"]["provenance"] == "policy_missing"
    assert "fail_closed" in result["reason"]


def test_local_runner_allowed_when_headroom_policy_missing(monkeypatch):
    monkeypatch.setattr(profiles, "_load_headroom_policy", lambda: {})

    result = profiles._check_headroom_policy("ollama", "standard", {})

    assert result["allow"] is True
    assert result["headroom_state"]["provenance"] == "not_applicable"


def test_cloud_runner_fails_closed_when_provider_missing_from_policy(monkeypatch):
    monkeypatch.setattr(profiles, "_load_headroom_policy", lambda: {"providers": {}})

    result = profiles._check_headroom_policy("gemini", "standard", {})

    assert result["allow"] is False
    assert result["headroom_state"]["provenance"] == "policy_missing_provider"


def test_cloud_runner_fails_closed_when_headroom_probe_errors(monkeypatch):
    def boom():
        raise RuntimeError("probe down")

    monkeypatch.setattr(
        profiles,
        "_load_headroom_policy",
        lambda: {"providers": {"codex": {"policy": "metered", "five_hour_window": {}}}},
    )
    monkeypatch.setitem(sys.modules, "cost_truth_surface", SimpleNamespace(get_headroom=boom))

    result = profiles._check_headroom_policy("codex", "standard", {})

    assert result["allow"] is False
    assert result["headroom_state"]["provenance"] == "error"


def test_cloud_runner_fails_closed_when_provider_headroom_unavailable(monkeypatch):
    monkeypatch.setattr(
        profiles,
        "_load_headroom_policy",
        lambda: {"providers": {"codex": {"policy": "metered", "five_hour_window": {}}}},
    )
    monkeypatch.setitem(
        sys.modules,
        "cost_truth_surface",
        SimpleNamespace(get_headroom=lambda: {"codex": {"available": False}}),
    )

    result = profiles._check_headroom_policy("codex", "standard", {})

    assert result["allow"] is False
    assert result["headroom_state"]["provenance"] == "unavailable"
