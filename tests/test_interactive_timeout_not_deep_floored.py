"""Regression: the deep-model timeout floor must not capture interactive calls.

2026-06-29 retiering pointed OLLAMA_MODEL_DEEP at the SAME card-fit model as the
interactive lane (qwen3:8b-q4_K_M). ollama_call's name-equality floor
(`model == OLLAMA_MODEL_DEEP -> timeout = max(timeout, 300)`) then silently
stretched EVERY explicit interactive front-door/Cassandra call from the operator's
44s budget to 300s: under VRAM contention the operator waited 5 minutes for a
deterministic fallback (protected_generate_audit 2026-07-01, model_timeout_s=44
vs model_elapsed_ms=300099). The floor exists so a genuinely BIG deep model is
not killed mid-generation; when deep IS the interactive model, the caller's
real-time timeout must win.
"""

import chief_llm


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _install_capture(monkeypatch, captured: dict):
    def _fake_urlopen(req, timeout=0):
        captured["timeout"] = timeout
        return _FakeResponse(b'{"response": "ok", "done_reason": "stop"}')

    monkeypatch.setattr(chief_llm.urllib.request, "urlopen", _fake_urlopen)


def test_interactive_call_keeps_caller_timeout_when_deep_equals_interactive(monkeypatch):
    monkeypatch.setattr(chief_llm, "OLLAMA_MODEL", "qwen3:8b-q4_K_M")
    monkeypatch.setattr(chief_llm, "OLLAMA_MODEL_DEEP", "qwen3:8b-q4_K_M")
    monkeypatch.setattr(
        chief_llm, "_ollama_model_sizes", lambda force_refresh=False: {"qwen3:8b-q4_K_M": 5.2}
    )
    captured: dict = {}
    _install_capture(monkeypatch, captured)

    result = chief_llm.ollama_call(
        "status?",
        timeout=44,
        model="qwen3:8b-q4_K_M",
        task_class="frontdoor_reply",
        attempts=1,
    )

    assert result == "ok"
    assert captured["timeout"] == 44


def test_distinct_big_deep_model_still_gets_long_timeout(monkeypatch):
    monkeypatch.setattr(chief_llm, "OLLAMA_MODEL", "qwen3:8b-q4_K_M")
    monkeypatch.setattr(chief_llm, "OLLAMA_MODEL_DEEP", "qwen3.6:latest")
    monkeypatch.setattr(
        chief_llm, "_ollama_model_sizes", lambda force_refresh=False: {"qwen3.6:latest": 23.0}
    )
    captured: dict = {}
    _install_capture(monkeypatch, captured)

    result = chief_llm.ollama_call(
        "deep synthesis",
        timeout=44,
        model="qwen3.6:latest",
        attempts=1,
    )

    assert result == "ok"
    # Floor raises to _DEEP_TIMEOUT_FLOOR, then the size-aware stretch takes over.
    assert captured["timeout"] >= chief_llm._DEEP_TIMEOUT_FLOOR
