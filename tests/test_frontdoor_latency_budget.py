from __future__ import annotations

import pytest

from frontdoor_latency_budget import classify_latency, estimate_frontdoor_budget


_TEST_TPS = {
    "small": {
        "gpu_tps": 20.0,
        "cpu_tps": 1.0,
        "prefill_tps": 100.0,
        "load_bw_gbs": 1.0,
    }
}


def _estimate(**overrides):
    params = {
        "model": "qwen3.5:4b",
        "size_gb": 4.0,
        "gpu_fraction": 1.0,
        "warm": True,
        "num_predict": 100,
        "prompt_tokens": 200,
        "sync_window_s": 45.0,
        "margin": 0.5,
        "slack": 3.0,
        "tps_table": _TEST_TPS,
    }
    params.update(overrides)
    return estimate_frontdoor_budget(**params)


def test_warm_gpu_small_model_has_short_expected_budget():
    estimate = _estimate()

    assert estimate["expected_s"] == pytest.approx(7.0)
    assert estimate["timeout_s"] == pytest.approx(13.5)
    assert estimate["class_hint"] == "WITHIN"
    assert estimate["basis"]["latency_class"] == "small"
    assert estimate["basis"]["eff_tps"] == pytest.approx(20.0)
    assert estimate["basis"]["load_penalty_s"] == 0.0


def test_cold_model_adds_load_penalty_from_size_and_bandwidth():
    warm = _estimate()
    cold = _estimate(warm=False)

    assert cold["basis"]["load_penalty_s"] == pytest.approx(4.0)
    assert cold["expected_s"] == pytest.approx(warm["expected_s"] + 4.0)
    assert cold["timeout_s"] > warm["timeout_s"]


def test_half_gpu_residency_is_roughly_double_decode_time():
    full = _estimate(prompt_tokens=0)
    half = _estimate(prompt_tokens=0, gpu_fraction=0.5)

    assert full["basis"]["decode_s"] == pytest.approx(5.0)
    assert half["basis"]["eff_tps"] == pytest.approx(10.5)
    assert half["basis"]["decode_s"] == pytest.approx(9.5238095)
    assert half["expected_s"] > full["expected_s"] * 1.8


def test_num_predict_scales_decode_budget():
    short = _estimate(prompt_tokens=0, num_predict=100)
    long = _estimate(prompt_tokens=0, num_predict=200)

    assert long["basis"]["decode_s"] == pytest.approx(short["basis"]["decode_s"] * 2)
    assert long["expected_s"] == pytest.approx(short["expected_s"] * 2)


def test_missing_signals_fail_toward_conservative_large_budget():
    known_small = _estimate(size_gb=3.0, gpu_fraction=1.0, warm=True, num_predict=100, prompt_tokens=0)
    missing = estimate_frontdoor_budget(
        model=None,
        size_gb=None,
        gpu_fraction=None,
        warm=None,
        num_predict=None,
        prompt_tokens=None,
        sync_window_s=45.0,
        margin=0.5,
        slack=3.0,
        tps_table=_TEST_TPS,
    )

    assert missing["expected_s"] > known_small["expected_s"]
    assert missing["basis"]["latency_class"] == "large"
    assert missing["basis"]["gpu_fraction"] == 0.0
    assert set(missing["basis"]["missing_signals"]) >= {
        "model",
        "size_gb",
        "gpu_fraction",
        "warm",
        "num_predict",
        "prompt_tokens",
    }


def test_classify_latency_boundaries():
    assert classify_latency(
        expected_s=10.0, timeout_s=18.0, elapsed_ms=10_000, sync_window_s=45.0
    ) == "WITHIN"
    assert classify_latency(
        expected_s=50.0, timeout_s=80.0, elapsed_ms=60_000, sync_window_s=45.0
    ) == "EXPECTED_SLOW"
    assert classify_latency(
        expected_s=10.0, timeout_s=18.0, elapsed_ms=18_001, sync_window_s=45.0
    ) == "ANOMALY"


def test_more_spill_monotonically_increases_expected_budget():
    full = _estimate(prompt_tokens=0, gpu_fraction=1.0)
    half = _estimate(prompt_tokens=0, gpu_fraction=0.5)
    cpu = _estimate(prompt_tokens=0, gpu_fraction=0.0)

    assert full["expected_s"] < half["expected_s"] < cpu["expected_s"]
    assert full["basis"]["eff_tps"] > half["basis"]["eff_tps"] > cpu["basis"]["eff_tps"]


def test_expected_slow_class_hint_when_expected_exceeds_sync_window():
    estimate = _estimate(prompt_tokens=0, gpu_fraction=0.0, num_predict=80, sync_window_s=45.0)

    assert estimate["expected_s"] == pytest.approx(80.0)
    assert estimate["class_hint"] == "EXPECTED_SLOW"
