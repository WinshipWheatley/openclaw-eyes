from __future__ import annotations

import json
from contextlib import contextmanager

import chief_llm
import local_model_governance as governance
import protected_generate as pg
from protected_generate import protected_generate_with_receipt


class _FakeResp:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@contextmanager
def _capture_ollama_payload(monkeypatch, response_text: str = "hello"):
    captured: dict = {}

    def fake_urlopen(req, timeout=None):
        captured["payload_bytes"] = req.data
        captured["timeout"] = timeout
        return _FakeResp({"response": response_text, "done_reason": "stop"})

    monkeypatch.setattr(chief_llm.urllib.request, "urlopen", fake_urlopen)
    yield captured


def test_ollama_call_default_payload_has_no_warmpin_or_offload_keys(monkeypatch):
    with _capture_ollama_payload(monkeypatch) as captured:
        out = chief_llm.ollama_call("hi", model="qwen3:8b-q4_K_M", attempts=1)

    assert out == "hello"
    decoded = json.loads(captured["payload_bytes"].decode("utf-8"))
    assert decoded == {"model": "qwen3:8b-q4_K_M", "prompt": "hi", "stream": False}
    assert "options" not in decoded
    assert "keep_alive" not in decoded


def test_frontdoor_profile_defaults_to_the_governed_runner_shape(monkeypatch):
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_NUM_CTX", raising=False)
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_NUM_GPU", raising=False)

    assert pg._frontdoor_ollama_options() == {
        "num_ctx": governance.INTERACTIVE_NUM_CTX,
        "num_gpu": governance.INTERACTIVE_NUM_GPU,
        "num_batch": governance.INTERACTIVE_NUM_BATCH,
    }


def test_frontdoor_runner_shape_cannot_be_overridden_by_stale_env(monkeypatch):
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_NUM_CTX", "1024")
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_NUM_GPU", "1")

    assert pg._frontdoor_ollama_options() == governance.interactive_runner_options()


def test_ollama_call_passes_frontdoor_offload_options_and_keep_alive(monkeypatch):
    with _capture_ollama_payload(monkeypatch) as captured:
        chief_llm.ollama_call(
            "hi",
            model="qwen3:8b-q4_K_M",
            attempts=1,
            options={"num_ctx": 1024, "num_gpu": 999},
            keep_alive="30m",
        )

    decoded = json.loads(captured["payload_bytes"].decode("utf-8"))
    assert decoded["options"] == {"num_ctx": 1024, "num_gpu": 999}
    assert decoded["keep_alive"] == "30m"


def test_call_local_ollama_stamps_bound_runner_without_legacy_env(monkeypatch):
    observed: dict = {}

    def fake_ollama(prompt, **kwargs):
        observed["prompt"] = prompt
        observed["kwargs"] = kwargs
        return {"text": "ok", "done_reason": "stop", "elapsed_ms": 1}

    monkeypatch.setattr(chief_llm, "ollama_call", fake_ollama)
    result = pg._call_local_ollama(
        "front door prompt",
        timeout=5,
        attempts=1,
        model="qwen3:8b-q4_K_M",
        task_class="frontdoor_reply",
        think=False,
        num_predict=96,
        return_metadata=True,
    )

    assert result["text"] == "ok"
    assert observed["kwargs"]["options"] == governance.interactive_runner_options()
    assert observed["kwargs"]["keep_alive"] == governance.INTERACTIVE_KEEP_ALIVE


def test_frontdoor_env_options_reach_local_bridge_and_receipt(monkeypatch, tmp_path):
    observed: dict = {}

    monkeypatch.setenv("OPENCLAW_FRONTDOOR_MODEL_PROFILE", "1")
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_REPLY_TIMEOUT", "30")
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_NUM_PREDICT", "96")
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_NUM_CTX", "1024")
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_NUM_GPU", "999")
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_KEEP_ALIVE", "30m")
    monkeypatch.delenv("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", raising=False)
    monkeypatch.setattr(pg, "_live_model_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(chief_llm, "_configured_openrouter_model", lambda: "", raising=False)
    monkeypatch.setattr(chief_llm, "ollama_is_unreachable", lambda **_k: False, raising=False)
    monkeypatch.setattr(
        chief_llm,
        "_ollama_model_sizes",
        lambda: {"qwen3:8b-q4_K_M": 5.2},
    )

    def fake_select(**kwargs):
        observed["selector_kwargs"] = kwargs
        return "qwen3:8b-q4_K_M", "frontdoor_largest_fitting"

    def fake_ollama(prompt, **kwargs):
        observed["ollama_kwargs"] = kwargs
        return {
            "text": "Winship is the operator.",
            "done_reason": "stop",
            "elapsed_ms": 12,
            "response_metadata": {"eval_count": 7},
        }

    monkeypatch.setattr(chief_llm, "select_frontdoor_model", fake_select)
    monkeypatch.setattr(chief_llm, "ollama_call", fake_ollama)

    outcome = protected_generate_with_receipt(
        "Who is the operator?",
        context_packet={
            "schema_version": "maestro_context_packet_v0",
            "packet_id": "maestro_context_packet:test",
            "facts": [{"text": "The operator is Winship."}],
            "source_refs": [],
        },
        audit_log_path=tmp_path / "audit.jsonl",
        allow_live_model=True,
    )

    assert observed["selector_kwargs"]["max_gb"] == 6.0
    assert observed["ollama_kwargs"]["options"] == governance.interactive_runner_options()
    assert observed["ollama_kwargs"]["keep_alive"] == governance.INTERACTIVE_KEEP_ALIVE
    assert observed["ollama_kwargs"]["num_predict"] == 96
    assert observed["ollama_kwargs"]["think"] is False
    assert outcome.receipt["model_num_ctx"] == governance.INTERACTIVE_NUM_CTX
    assert outcome.receipt["model_num_gpu"] == 999
    assert outcome.receipt["model_keep_alive"] == governance.INTERACTIVE_KEEP_ALIVE
    assert outcome.receipt["model_max_gb"] == 6.0


def test_frontdoor_selector_ceiling_rejects_models_above_8b():
    sizes = {
        "qwen3.5:4b": 3.0,
        "qwen3:8b-q4_K_M": 5.5,
        "qwen3.5:9b": 6.5,
        "gemma4:26b": 18.0,
    }
    installed = {"qwen3.5:4b", "qwen3:8b-q4_K_M", "qwen3.5:9b", "gemma4:26b"}

    model, reason = chief_llm.select_frontdoor_model(
        installed=installed,
        sizes=sizes,
        available_ram_gb=16.0,
        max_gb=6.0,
    )

    assert model == "qwen3:8b-q4_K_M"
    assert reason == "frontdoor_largest_fitting"


def test_frontdoor_selector_explicit_allowlist_can_force_8b(monkeypatch):
    monkeypatch.setenv("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", "qwen3:8b-q4_K_M")
    model, reason = chief_llm.select_frontdoor_model(
        installed={"qwen3:8b-q4_K_M", "qwen3.5:9b"},
        sizes={"qwen3:8b-q4_K_M": 5.5, "qwen3.5:9b": 6.5},
        available_ram_gb=64.0,
    )

    assert chief_llm.FRONTDOOR_MODEL_ALLOWLIST() == ("qwen3:8b-q4_K_M",)
    assert model == "qwen3:8b-q4_K_M"
    assert reason == "frontdoor_largest_fitting"
