from __future__ import annotations

import chief_llm


# Real installed inventory on the 6GB box (subset that matters for tiering).
_INSTALLED = {
    "qwen3:4b", "qwen3:8b-q4_K_M", "qwen3.5:9b", "ornith:9b",
    "magistral:latest", "mistral-small:latest", "nemotron-3-nano:4b",
    "gemma4:26b", "gemma4:31b", "gemma4:e4b",
}
_SIZES = {
    "qwen3:4b": 2.5, "qwen3:8b-q4_K_M": 5.2, "qwen3.5:9b": 6.6, "ornith:9b": 5.6,
    "magistral:latest": 14.0, "mistral-small:latest": 14.0, "nemotron-3-nano:4b": 2.8,
    "gemma4:26b": 17.0, "gemma4:31b": 19.0, "gemma4:e4b": 9.6,
}


def _wire(monkeypatch):
    monkeypatch.setattr(chief_llm, "_ollama_installed_models", lambda *a, **k: set(_INSTALLED))
    monkeypatch.setattr(chief_llm, "_ollama_model_sizes", lambda *a, **k: dict(_SIZES))


def test_interactive_replies_use_qwen3_8b(monkeypatch) -> None:
    # The real-time chat paths must land on qwen3:8b (clean + fully fits the card), never gemma.
    _wire(monkeypatch)
    for tc in ("cassandra_user_reply", "chief_user_reply"):
        model, _lane = chief_llm.resolve_local_model("hey", task_class=tc)
        assert model == "qwen3:8b-q4_K_M", f"{tc} -> {model}"


def test_interactive_fast_reply_uses_qwen3_4b(monkeypatch) -> None:
    _wire(monkeypatch)
    model, _ = chief_llm.resolve_local_model("classify this", task_class="cassandra_user_reply_fast")
    assert model == "qwen3:4b"


def test_agentic_code_and_code_lane_use_ornith(monkeypatch) -> None:
    # Coding work routes to the coding specialist that fits the card.
    _wire(monkeypatch)
    model, _ = chief_llm.resolve_local_model("write code", task_class="chief_agentic_code")
    assert model == "ornith:9b"
    model2, _ = chief_llm.resolve_local_model("build", lane="code_challenger")
    assert model2 == "ornith:9b"


def test_async_synthesis_reaches_a_reasoner_above_interactive_ceiling(monkeypatch) -> None:
    # Async/heavy paths may exceed the interactive ceiling (spill OK) -> magistral (14GB) is allowed.
    _wire(monkeypatch)
    model, _ = chief_llm.resolve_local_model("synthesize the evidence", task_class="chief_evidence_synthesis")
    assert model == "magistral:latest"


def test_strong_lane_is_interactive_qwen(monkeypatch) -> None:
    # Bare 'strong' lane (Niles/Guardian/fallbacks) is treated as interactive -> qwen3:8b, never gemma4:26b.
    _wire(monkeypatch)
    model, _ = chief_llm.resolve_local_model("a normal user question", lane="strong")
    assert model == "qwen3:8b-q4_K_M"


def test_ceiling_is_context_aware(monkeypatch) -> None:
    # Interactive ceiling excludes the 14GB reasoner; async ceiling admits it (but not 26b).
    interactive = chief_llm._local_model_size_ceiling_gb(task_class="cassandra_user_reply")
    asynchronous = chief_llm._local_model_size_ceiling_gb(task_class="chief_evidence_synthesis")
    assert interactive < 14.0 <= asynchronous
    assert asynchronous < 17.0  # 26b stays excluded even async (swap-death)


def test_async_big_model_gets_long_timeout(monkeypatch) -> None:
    # A big async model must not be killed mid-generation: its effective timeout is long.
    assert chief_llm._effective_model_timeout(15, "magistral:latest", {"magistral:latest": 14.0}) >= 1200
    # An interactive small model keeps the caller's short timeout.
    assert chief_llm._effective_model_timeout(15, "qwen3:8b-q4_K_M", {"qwen3:8b-q4_K_M": 5.2}) == 15
