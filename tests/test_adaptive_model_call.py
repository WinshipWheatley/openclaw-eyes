from __future__ import annotations

from types import SimpleNamespace

import adaptive_model_call as adaptive


def test_adaptive_model_call_retries_downshifted_model_after_empty_primary() -> None:
    calls: list[dict] = []
    routes: list[dict] = []

    def fake_ollama(prompt, *, timeout=0, model=None, task_class=None, attempts=None, **_kwargs):
        calls.append({"model": model, "timeout": timeout, "task_class": task_class, "attempts": attempts})
        return "draft answer" if model == "qwen3:8b-q4_K_M" else ""

    def fake_selector(**kwargs):
        assert kwargs["available_vram_gb"] == 1.0
        assert kwargs["resident_vram_by_model_gb"] == {"qwen3:8b-q4_K_M": 0.5}
        return "qwen3:8b-q4_K_M", "frontdoor_step_down_vram_contention"

    def fake_probe():
        return SimpleNamespace(
            available_vram_gb=1.0,
            available_ram_gb=12.0,
            system_load_1m=12.0,
            cpu_count=4,
            resident_vram_by_model_gb=lambda: {"qwen3:8b-q4_K_M": 0.5},
        )

    result = adaptive.adaptive_model_call(
        "Draft a warm Clara reply.",
        task_class="cassandra_outbound_draft",
        timeout=60,
        primary_model="gemma4:31b",
        primary_lane="strong",
        ollama_call_fn=fake_ollama,
        select_model_fn=fake_selector,
        resource_probe_fn=fake_probe,
        route_logger=lambda **kwargs: routes.append(kwargs),
        # 2026-07-09 model-fit wall: explicit models are now demoted when their KNOWN size
        # breaches the lane ceiling. This test's intent (primary attempt honors the caller's
        # model) survives via the unknown-size fail-open path — sizes injected empty.
        model_sizes_fn=lambda: {},
    )

    assert result == "draft answer"
    assert calls == [
        {"model": "gemma4:31b", "timeout": 60, "task_class": "cassandra_outbound_draft", "attempts": 1},
        {"model": "qwen3:8b-q4_K_M", "timeout": 60, "task_class": "cassandra_outbound_draft", "attempts": 1},
    ]
    assert routes[0]["chosen_lane"] == "strong"
    assert routes[1]["chosen_lane"] == "adaptive_retry"
    assert routes[1]["escalation"] is True
    assert routes[1]["model"] == "qwen3:8b-q4_K_M"


def test_interactive_retry_reuses_the_same_resident_8b() -> None:
    calls: list[str] = []

    result = adaptive.adaptive_model_call(
        "Answer briefly.",
        task_class="cassandra_user_reply",
        timeout=30,
        primary_model="gemma4:31b",
        primary_lane="strong",
        ollama_call_fn=lambda prompt, **kwargs: calls.append(kwargs["model"]) or "",
        select_model_fn=lambda **_kwargs: ("qwen3:8b-q4_K_M", "frontdoor_step_down_system_load"),
        resource_probe_fn=lambda: SimpleNamespace(
            available_vram_gb=0.5,
            available_ram_gb=10.0,
            system_load_1m=20.0,
            cpu_count=4,
            resident_vram_by_model_gb=lambda: {},
        ),
        # 2026-07-09 model-fit wall: explicit models are now demoted when their KNOWN size
        # breaches the lane ceiling. This test's intent (primary attempt honors the caller's
        # model) survives via the unknown-size fail-open path — sizes injected empty.
        model_sizes_fn=lambda: {},
    )

    assert result == ""
    assert calls == ["qwen3:8b-q4_K_M", "qwen3:8b-q4_K_M"]


def test_adaptive_model_call_supports_legacy_ollama_fixture_without_attempts() -> None:
    calls: list[dict] = []

    def legacy_ollama(prompt, timeout=0, model=None):
        calls.append({"prompt": prompt, "timeout": timeout, "model": model})
        return "legacy answer"

    result = adaptive.adaptive_model_call(
        "Answer briefly.",
        task_class="cassandra_user_reply",
        timeout=30,
        primary_model="gemma4:31b",
        primary_lane="strong",
        ollama_call_fn=legacy_ollama,
        # 2026-07-09 model-fit wall: explicit models are now demoted when their KNOWN size
        # breaches the lane ceiling. This test's intent (primary attempt honors the caller's
        # model) survives via the unknown-size fail-open path — sizes injected empty.
        model_sizes_fn=lambda: {},
    )

    assert result == "legacy answer"
    assert calls == [
        {"prompt": "Answer briefly.", "timeout": 30, "model": "qwen3:8b-q4_K_M"}
    ]


def test_adaptive_ollama_text_preserves_explicit_model_without_resolving() -> None:
    calls: list[dict] = []

    def fake_ollama(prompt, **kwargs):
        calls.append(kwargs)
        return "explicit model answer"

    def fail_resolve(*_args, **_kwargs):
        raise AssertionError("explicit model should not resolve a primary route")

    result = adaptive.adaptive_ollama_text(
        "Summarize this packet.",
        timeout=60,
        model="nemotron:30b",
        task_class="chief_evidence_synthesis",
        ollama_call_fn=fake_ollama,
        resolve_model_fn=fail_resolve,
        # 2026-07-09 model-fit wall: explicit models are now demoted when their KNOWN size
        # breaches the lane ceiling. This test's intent (primary attempt honors the caller's
        # model) survives via the unknown-size fail-open path — sizes injected empty.
        model_sizes_fn=lambda: {},
    )

    assert result == "explicit model answer"
    assert calls == [
        {
            "timeout": 60,
            "model": "nemotron:30b",
            "task_class": "chief_evidence_synthesis",
            "attempts": 1,
        }
    ]


def test_default_chief_wrapper_receives_the_resolved_lane(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_ollama(prompt, **kwargs):
        calls.append(kwargs)
        return "ok"

    monkeypatch.setattr(adaptive.chief_llm, "ollama_call", fake_ollama)

    result = adaptive.adaptive_model_call(
        "Operator-facing answer.",
        task_class="chief_user_reply",
        timeout=30,
        primary_model="qwen3:8b-q4_K_M",
        primary_lane="strong",
        retry=False,
        model_sizes_fn=lambda: {},
    )

    assert result == "ok"
    assert calls[0]["lane"] == "strong"


def test_bound_interactive_8b_never_retries_with_a_different_model() -> None:
    calls: list[str] = []

    result = adaptive.adaptive_model_call(
        "Operator-facing answer.",
        task_class="chief_user_reply",
        timeout=30,
        primary_model="qwen3:8b-q4_K_M",
        primary_lane="strong",
        ollama_call_fn=lambda prompt, **kwargs: calls.append(kwargs["model"]) or "",
        select_model_fn=lambda **_kwargs: ("qwen3:4b", "frontdoor_step_down_vram_contention"),
        resource_probe_fn=lambda: SimpleNamespace(
            available_vram_gb=1.0,
            available_ram_gb=12.0,
            system_load_1m=1.0,
            cpu_count=4,
            resident_vram_by_model_gb=lambda: {"qwen3:8b-q4_K_M": 5.5},
        ),
        model_sizes_fn=lambda: {},
    )

    assert result == ""
    assert calls == ["qwen3:8b-q4_K_M"]


def test_adaptive_model_call_stamps_bound_frontdoor_model_and_runner_options() -> None:
    calls: list[dict] = []

    def fake_ollama(prompt, **kwargs):
        calls.append(kwargs)
        return {"text": "frontdoor answer", "done_reason": "stop", "status": "success"}

    result = adaptive.adaptive_model_call(
        "Front-door prompt",
        task_class="frontdoor_reply",
        timeout=25.0,
        primary_model="qwen3.5:4b",
        primary_lane="frontdoor_largest_fitting",
        attempts=1,
        think=False,
        num_predict=180,
        options={"temperature": 0},
        keep_alive="30s",
        return_metadata=True,
        ollama_call_fn=fake_ollama,
        select_model_fn=lambda **_kwargs: ("qwen3:8b-q4_K_M", "frontdoor_step_down_system_load"),
        resource_probe_fn=lambda: SimpleNamespace(
            available_vram_gb=1.0,
            available_ram_gb=12.0,
            system_load_1m=9.0,
            cpu_count=4,
            resident_vram_by_model_gb=lambda: {},
        ),
    )

    assert result["text"] == "frontdoor answer"
    assert calls == [
        {
            "timeout": 25.0,
            "model": "qwen3:8b-q4_K_M",
            "task_class": "frontdoor_reply",
            "attempts": 1,
            "think": False,
            "num_predict": 180,
            "options": {
                "temperature": 0,
                "num_ctx": 2048,
                "num_gpu": 999,
                "num_batch": 128,
            },
            "keep_alive": "10m",
            "return_metadata": True,
        },
    ]
