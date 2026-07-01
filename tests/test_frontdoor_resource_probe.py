from __future__ import annotations

import json
import subprocess

import chief_llm
import frontdoor_resource_probe


_SIZES = {
    "qwen3.5:4b": 3.4,
    "qwen3:8b-q4_K_M": 5.2,
    "qwen3.5:9b": 6.6,
}


def test_select_frontdoor_model_uses_real_vram_budget(monkeypatch) -> None:
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", raising=False)
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", raising=False)

    model, reason = chief_llm.select_frontdoor_model(
        installed=set(_SIZES),
        sizes=_SIZES,
        available_ram_gb=64.0,
        available_vram_gb=5.8,
        max_gb=12.0,
    )

    assert model == "qwen3:8b-q4_K_M"
    assert reason == "frontdoor_step_down_vram_contention"


def test_select_frontdoor_model_counts_resident_vram_for_same_model(monkeypatch) -> None:
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", raising=False)
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", raising=False)

    model, reason = chief_llm.select_frontdoor_model(
        installed=set(_SIZES),
        sizes=_SIZES,
        available_ram_gb=64.0,
        available_vram_gb=1.0,
        resident_vram_by_model_gb={"qwen3:8b-q4_K_M": 4.7},
        max_gb=12.0,
    )

    assert model == "qwen3:8b-q4_K_M"
    assert reason == "frontdoor_step_down_vram_contention"


def test_select_frontdoor_model_keeps_already_resident_candidate(monkeypatch) -> None:
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", raising=False)
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", raising=False)

    model, reason = chief_llm.select_frontdoor_model(
        installed=set(_SIZES),
        sizes=_SIZES,
        available_ram_gb=64.0,
        available_vram_gb=0.2,
        resident_vram_by_model_gb={"qwen3:8b-q4_K_M": 4.0},
        max_gb=12.0,
    )

    assert model == "qwen3:8b-q4_K_M"
    assert reason == "frontdoor_step_down_vram_contention"


def test_select_frontdoor_model_spills_to_ram_when_vram_is_tight(monkeypatch) -> None:
    # Operator policy: a model that fits the VRAM CARD (max_gb) is USED even when currently-free
    # VRAM is smaller than the model -- ollama spills the overflow to system RAM. The selector
    # must NOT return no_fitting_model just because free VRAM is tight. Reproduces the live
    # regression that took the front-door brain down (free VRAM 4.3GB < the 5.2GB pinned model,
    # 6GB card) so every question fell back to a deterministic readback dump.
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", raising=False)
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", raising=False)

    model, reason = chief_llm.select_frontdoor_model(
        installed={"qwen3:8b-q4_K_M"},
        sizes={"qwen3:8b-q4_K_M": 5.2},
        available_ram_gb=18.0,
        available_vram_gb=4.3,
        max_gb=6.0,
    )

    assert model == "qwen3:8b-q4_K_M"
    assert reason.startswith("frontdoor_step_down_vram_contention")


def test_frontdoor_resource_probe_parses_gpu_ram_and_ollama_ps(monkeypatch) -> None:
    def fake_run(cmd, capture_output=False, text=False, timeout=None, check=False):
        assert "--query-gpu=memory.free,memory.total" in cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="5120, 6144\n", stderr="")

    def fake_read_meminfo():
        return "MemTotal:       32800000 kB\nMemAvailable:  20971520 kB\n"

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self):
            return json.dumps(
                {
                    "models": [
                        {
                            "name": "qwen3:8b-q4_K_M",
                            "size_vram": 4_600_000_000,
                        }
                    ]
                }
            ).encode("utf-8")

    monkeypatch.setattr(frontdoor_resource_probe.subprocess, "run", fake_run)
    monkeypatch.setattr(frontdoor_resource_probe, "_read_meminfo", fake_read_meminfo)
    monkeypatch.setattr(frontdoor_resource_probe.urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())

    snapshot = frontdoor_resource_probe.probe_frontdoor_resources()

    assert snapshot.available_vram_gb == 5.0
    assert snapshot.total_vram_gb == 6.0
    assert snapshot.available_ram_gb == 20.0
    assert snapshot.resident_models == [{"name": "qwen3:8b-q4_K_M", "size_vram_gb": 4.6}]
    assert snapshot.to_receipt_fields()["resource_probe_available_vram_gb"] == 5.0
