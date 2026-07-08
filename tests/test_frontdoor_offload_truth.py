"""Task 146 (CLASS #7): residency != speed -- trust the OFFLOAD FRACTION, not /api/ps alone.

Definitive live evidence (2026-07-07 22:4x): ollama /api/ps reported qwen3:8b-q4_K_M
"resident" with size=6.0GB but size_vram=2.4GB -- 60% CPU-offloaded (runner at 286% CPU,
4% GPU util; a 20-token completion took 62s), blowing every interactive timeout in the
fleet. These tests pin the class fix:

  (1) the resource probe records offload_fraction = size_vram/size per resident model;
  (2) select_frontdoor_model: a resident model with offload_fraction < 0.8 does NOT get
      residency preference -- the fully-fitting smaller allowlisted model wins with
      reason "frontdoor_offload_avoidance"; fraction >= 0.8 or UNKNOWN keeps today's
      behavior byte-identical (fail-open);
  (3) receipts carry offload_fraction (via resource_probe_resident_models);
  (4) clock-race rider: cassandra_listener outer timeout staggered to 90s so it no
      longer races the inner 60s model lane with zero margin.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import types

from types import SimpleNamespace

import pytest

import adaptive_model_call as adaptive
import chief_llm
import frontdoor_resource_probe


_SIZES = {
    "qwen3.5:4b": 3.4,
    "qwen3:8b-q4_K_M": 5.2,
    "qwen3.5:9b": 6.6,
}


def _clear_frontdoor_env(monkeypatch) -> None:
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", raising=False)
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", raising=False)
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_OFFLOAD_FRACTION_MIN", raising=False)


# ── (1) probe records offload_fraction per resident model ────────────────────


class _FakePsResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def _patch_probe_environment(monkeypatch, *, gpu_stdout: str, urlopen) -> None:
    def fake_run(cmd, capture_output=False, text=False, timeout=None, check=False):
        return subprocess.CompletedProcess(cmd, 0, stdout=gpu_stdout, stderr="")

    monkeypatch.setattr(frontdoor_resource_probe.subprocess, "run", fake_run)
    monkeypatch.setattr(
        frontdoor_resource_probe,
        "_read_meminfo",
        lambda: "MemTotal:       32800000 kB\nMemAvailable:  20971520 kB\n",
    )
    monkeypatch.setattr(frontdoor_resource_probe.urllib.request, "urlopen", urlopen)


def test_probe_records_offload_fraction_from_api_ps(monkeypatch) -> None:
    """THE fixture: size=6.0GB, size_vram=2.4GB -> offload_fraction=0.4 recorded."""

    payload = {
        "models": [
            {"name": "qwen3:8b-q4_K_M", "size": 6_000_000_000, "size_vram": 2_400_000_000}
        ]
    }
    _patch_probe_environment(
        monkeypatch,
        gpu_stdout="200, 6144\n",
        urlopen=lambda *_a, **_k: _FakePsResponse(payload),
    )

    snapshot = frontdoor_resource_probe.probe_frontdoor_resources()

    assert snapshot.resident_models == [
        {
            "name": "qwen3:8b-q4_K_M",
            "size_vram_gb": 2.4,
            "size_gb": 6.0,
            "offload_fraction": 0.4,
        }
    ]
    assert snapshot.offload_fraction_by_model() == {"qwen3:8b-q4_K_M": 0.4}
    # (3) receipts carry offload_fraction via the resident-models receipt field.
    receipt_models = snapshot.to_receipt_fields()["resource_probe_resident_models"]
    assert receipt_models[0]["offload_fraction"] == 0.4
    assert receipt_models[0]["size_gb"] == 6.0


def test_probe_without_total_size_stays_byte_identical(monkeypatch) -> None:
    """A ps entry with NO usable total ``size`` keeps today's exact shape: fraction UNKNOWN
    (absent), never guessed. Unknown must not change any downstream selection."""

    payload = {"models": [{"name": "qwen3:8b-q4_K_M", "size_vram": 4_600_000_000}]}
    _patch_probe_environment(
        monkeypatch,
        gpu_stdout="5120, 6144\n",
        urlopen=lambda *_a, **_k: _FakePsResponse(payload),
    )

    snapshot = frontdoor_resource_probe.probe_frontdoor_resources()

    assert snapshot.resident_models == [{"name": "qwen3:8b-q4_K_M", "size_vram_gb": 4.6}]
    assert snapshot.offload_fraction_by_model() == {}


def test_probe_fully_resident_fraction_clamped_to_one(monkeypatch) -> None:
    payload = {
        "models": [
            {"name": "qwen3.5:4b", "size": 3_400_000_000, "size_vram": 3_500_000_000}
        ]
    }
    _patch_probe_environment(
        monkeypatch,
        gpu_stdout="2048, 6144\n",
        urlopen=lambda *_a, **_k: _FakePsResponse(payload),
    )

    snapshot = frontdoor_resource_probe.probe_frontdoor_resources()

    assert snapshot.offload_fraction_by_model() == {"qwen3.5:4b": 1.0}


def test_ps_empty_but_vram_used_retry_still_works_and_carries_fraction(monkeypatch) -> None:
    """135's flake-retry is preserved: first ps empty on a hot card -> exactly one retry;
    the recovered entry now ALSO carries offload_fraction."""

    calls = {"count": 0}

    def fake_urlopen(*_a, **_k):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakePsResponse({"models": []})
        return _FakePsResponse(
            {
                "models": [
                    {
                        "name": "qwen3:8b-q4_K_M",
                        "size": 6_000_000_000,
                        "size_vram": 2_400_000_000,
                    }
                ]
            }
        )

    # 6GB card, 200MB free -> ~5.8GB used, well over the 2GB flake threshold.
    _patch_probe_environment(monkeypatch, gpu_stdout="200, 6144\n", urlopen=fake_urlopen)

    snapshot = frontdoor_resource_probe.probe_frontdoor_resources()

    assert calls["count"] == 2, "expected exactly one retry after the empty first probe"
    assert snapshot.resident_models[0]["offload_fraction"] == 0.4
    assert snapshot.offload_fraction_by_model() == {"qwen3:8b-q4_K_M": 0.4}
    assert snapshot.to_receipt_fields()["resource_probe_residency_probe_flake"] is False


# ── (2) selection policy: partial offload loses residency preference ─────────


def _select(fraction_map: dict | None, *, available_vram_gb: float = 3.5, **overrides):
    kwargs = dict(
        installed=set(_SIZES),
        sizes=_SIZES,
        available_ram_gb=64.0,
        available_vram_gb=available_vram_gb,
        resident_vram_by_model_gb={"qwen3:8b-q4_K_M": 2.4},
        max_gb=6.0,  # excludes qwen3.5:9b (6.6GB): 8b is the largest card-fitting candidate
    )
    kwargs.update(overrides)
    if fraction_map is not None:
        kwargs["offload_fraction_by_model"] = fraction_map
    return chief_llm.select_frontdoor_model(**kwargs)


def test_full_residency_keeps_resident_reuse(monkeypatch) -> None:
    """fraction >= 0.8 -> residency preference intact, existing reason unchanged."""
    _clear_frontdoor_env(monkeypatch)

    model, reason = _select({"qwen3:8b-q4_K_M": 0.9}, available_vram_gb=1.3)

    assert model == "qwen3:8b-q4_K_M"
    assert reason == "frontdoor_resident_reuse"


def test_partial_offload_prefers_fully_fitting_smaller_model(monkeypatch) -> None:
    """THE acceptance fixture: 8b 'resident' but 60% CPU-offloaded (fraction 0.4) ->
    selector picks the fully-fitting 4b with reason frontdoor_offload_avoidance."""
    _clear_frontdoor_env(monkeypatch)

    model, reason = _select({"qwen3:8b-q4_K_M": 0.4}, available_vram_gb=3.5)

    assert model == "qwen3.5:4b"
    assert reason == "frontdoor_offload_avoidance"


def test_unknown_fraction_is_byte_identical_to_current_behavior(monkeypatch) -> None:
    """Fail-open: an unknown fraction must NOT change today's selections."""
    _clear_frontdoor_env(monkeypatch)

    baseline = _select(None, available_vram_gb=1.3)
    empty_map = _select({}, available_vram_gb=1.3)
    none_value = _select({"qwen3:8b-q4_K_M": None}, available_vram_gb=1.3)
    other_model_only = _select({"qwen3.5:9b": 0.1}, available_vram_gb=1.3)

    assert baseline == ("qwen3:8b-q4_K_M", "frontdoor_resident_reuse")
    assert empty_map == baseline
    assert none_value == baseline
    assert other_model_only == baseline


@pytest.mark.parametrize(
    ("fraction", "expected_model", "expected_reason"),
    [
        (1.0, "qwen3:8b-q4_K_M", "frontdoor_resident_reuse"),
        (0.9, "qwen3:8b-q4_K_M", "frontdoor_resident_reuse"),
        (0.8, "qwen3:8b-q4_K_M", "frontdoor_resident_reuse"),  # boundary: >= keeps preference
        (0.79, "qwen3.5:4b", "frontdoor_offload_avoidance"),
        (0.4, "qwen3.5:4b", "frontdoor_offload_avoidance"),  # the live 2026-07-07 case
        (0.0, "qwen3.5:4b", "frontdoor_offload_avoidance"),
        (None, "qwen3:8b-q4_K_M", "frontdoor_resident_reuse"),  # unknown -> fail-open
    ],
)
def test_offload_decision_table(monkeypatch, fraction, expected_model, expected_reason) -> None:
    _clear_frontdoor_env(monkeypatch)

    fraction_map = {} if fraction is None else {"qwen3:8b-q4_K_M": fraction}
    # available_vram 3.5: 4b (3.4GB) fully fits free VRAM, offloaded 8b (5.2GB) does not.
    # For fraction >= 0.8 / unknown the resident 8b keeps winning on residency preference.
    model, reason = _select(fraction_map, available_vram_gb=3.5)

    assert (model, reason) == (expected_model, expected_reason)


def test_demoted_resident_may_still_win_as_plain_free_vram_fit(monkeypatch) -> None:
    """No residency preference != hard deny: if the demoted model independently fits free
    VRAM (clean reload territory), it can still win -- but as a plain fit, never labeled
    frontdoor_resident_reuse."""
    _clear_frontdoor_env(monkeypatch)

    model, reason = _select({"qwen3:8b-q4_K_M": 0.4}, available_vram_gb=5.5)

    assert model == "qwen3:8b-q4_K_M"
    assert reason == "frontdoor_largest_fitting"


def test_high_system_load_step_down_still_wins_over_offload_logic(monkeypatch) -> None:
    """Existing step-down precedence is untouched by the offload demotion."""
    _clear_frontdoor_env(monkeypatch)

    model, reason = _select(
        {"qwen3:8b-q4_K_M": 0.4},
        available_vram_gb=3.5,
        system_load_1m=8.0,
        cpu_count=8,
    )

    assert model == "qwen3.5:4b"
    assert reason == "frontdoor_step_down_system_load"


# ── adaptive retry wiring: snapshot fractions reach the selector ─────────────


def test_adaptive_retry_passes_offload_fractions_to_selector() -> None:
    seen: dict = {}

    def fake_selector(**kwargs):
        seen.update(kwargs)
        return "qwen3.5:4b", "frontdoor_offload_avoidance"

    def fake_probe():
        return SimpleNamespace(
            available_vram_gb=3.5,
            available_ram_gb=20.0,
            system_load_1m=1.0,
            cpu_count=8,
            resident_vram_by_model_gb=lambda: {"qwen3:8b-q4_K_M": 2.4},
            offload_fraction_by_model=lambda: {"qwen3:8b-q4_K_M": 0.4},
        )

    result = adaptive.adaptive_model_call(
        "Answer briefly.",
        task_class="cassandra_user_reply",
        timeout=30,
        primary_model="qwen3:8b-q4_K_M",
        primary_lane="strong",
        ollama_call_fn=lambda prompt, **kwargs: "ok" if kwargs.get("model") == "qwen3.5:4b" else "",
        select_model_fn=fake_selector,
        resource_probe_fn=fake_probe,
    )

    assert result == "ok"
    assert seen["offload_fraction_by_model"] == {"qwen3:8b-q4_K_M": 0.4}
    assert seen["resident_vram_by_model_gb"] == {"qwen3:8b-q4_K_M": 2.4}


def test_adaptive_retry_snapshot_without_fraction_method_fails_open() -> None:
    seen: dict = {}

    def fake_selector(**kwargs):
        seen.update(kwargs)
        return "qwen3.5:4b", "frontdoor_step_down_vram_contention"

    adaptive.adaptive_model_call(
        "Answer briefly.",
        task_class="cassandra_user_reply",
        timeout=30,
        primary_model="qwen3:8b-q4_K_M",
        primary_lane="strong",
        ollama_call_fn=lambda prompt, **kwargs: "",
        select_model_fn=fake_selector,
        resource_probe_fn=lambda: SimpleNamespace(
            available_vram_gb=0.5,
            available_ram_gb=10.0,
            system_load_1m=2.0,
            cpu_count=4,
            resident_vram_by_model_gb=lambda: {},
        ),
    )

    assert seen["offload_fraction_by_model"] == {}


# ── (4) clock-race rider: outer listener clock staggered above the inner lane ─


def _load_listener(monkeypatch):
    monkeypatch.setenv("CASSANDRA_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    fake_filters = types.SimpleNamespace(TEXT=object(), COMMAND=object(), VOICE=object())
    fake_context_types = types.SimpleNamespace(DEFAULT_TYPE=object())

    class _FakeApplicationBuilder:
        def token(self, _token):
            return self

        def build(self):
            return types.SimpleNamespace(add_handler=lambda *a, **k: None, run_polling=lambda: None)

    monkeypatch.setitem(sys.modules, "telegram", types.SimpleNamespace(Update=object))
    monkeypatch.setitem(
        sys.modules,
        "telegram.ext",
        types.SimpleNamespace(
            ApplicationBuilder=_FakeApplicationBuilder,
            MessageHandler=lambda *a, **k: None,
            filters=fake_filters,
            ContextTypes=fake_context_types,
        ),
    )
    sys.modules.pop("cassandra_listener", None)
    import cassandra_listener

    return importlib.reload(cassandra_listener)


def test_cassandra_listener_outer_clock_staggered_above_inner_60s(monkeypatch) -> None:
    """RIDER: two 60s clocks raced with zero margin -- the outer listener clock fired
    first under CPU-offload slowness, so the self-heal blamed the listener. The outer
    clock must now be >= inner (60s) + grounded-work margin."""

    listener = _load_listener(monkeypatch)

    inner_model_lane_s = 60
    assert listener._REQUEST_TIMEOUT_S == 90
    assert listener._REQUEST_TIMEOUT_S >= inner_model_lane_s + 30
