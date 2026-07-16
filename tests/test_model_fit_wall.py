"""Hardware-fit wall for explicit caller-passed models (2026-07-09 incident).

A pre-doctrine chief_router call site hardcoded qwen3.6:latest (27G) on the
interactive chief_user_reply lane; the adaptive layer honored it, 82% of the
model spilled to RAM, and the whole box swap-died mid-round (Maestro frozen,
Windows-side vsock timeouts). The wall demotes known-oversized EXPLICIT models
through the caller's resolver; the resolver's own choices are already
ceiling-aware and are never re-checked. Unknown sizes fail OPEN — the wall
stops known-oversized loads, it must never block when ollama is unreachable.
"""

from __future__ import annotations

import adaptive_model_call as adaptive


def _run(calls, *, model, task_class, sizes, resolver_model="qwen3:8b-q4_K_M"):
    def fake_ollama(prompt, *, timeout=0, model=None, task_class=None, attempts=None, **_kwargs):
        calls.append(model)
        return "answer"

    return adaptive.adaptive_model_call(
        "hello there",
        task_class=task_class,
        timeout=60,
        primary_model=model,
        primary_lane="explicit_model",
        ollama_call_fn=fake_ollama,
        resolve_model_fn=lambda *a, **k: (resolver_model, "interactive"),
        model_sizes_fn=lambda: sizes,
    )


def test_oversized_explicit_model_on_interactive_lane_is_demoted() -> None:
    calls: list[str] = []
    result = _run(
        calls,
        model="qwen3.6:latest",
        task_class="unclassified_explicit_model",
        sizes={"qwen3.6:latest": 27.1, "qwen3:8b-q4_K_M": 5.2},
    )
    assert result == "answer"
    assert calls == ["qwen3:8b-q4_K_M"], "27G model must never reach ollama on an interactive lane"


def test_oversized_explicit_model_breaches_async_ceiling_too() -> None:
    calls: list[str] = []
    _run(
        calls,
        model="qwen3.6:latest",
        task_class="chief_evidence_synthesis",
        sizes={"qwen3.6:latest": 27.1},
    )
    assert calls == ["qwen3:8b-q4_K_M"]


def test_fourteen_gb_model_requires_governor_lease_and_is_demoted_without_one() -> None:
    async_calls: list[str] = []
    _run(
        async_calls,
        model="mistral-small:latest",
        task_class="chief_evidence_synthesis",
        sizes={"mistral-small:latest": 14.0},
    )
    assert async_calls == ["qwen3:8b-q4_K_M"]

    interactive_calls: list[str] = []
    _run(
        interactive_calls,
        model="mistral-small:latest",
        task_class="chief_user_reply",
        sizes={"mistral-small:latest": 14.0},
    )
    assert interactive_calls == ["qwen3:8b-q4_K_M"], "14G breaches the 8G interactive ceiling"


def test_unknown_size_fails_closed_without_governor_lease() -> None:
    calls: list[str] = []
    _run(
        calls,
        model="mystery:latest",
        task_class="unclassified_explicit_model",
        sizes={},
    )
    assert calls == ["qwen3:8b-q4_K_M"]


def test_size_probe_error_fails_closed_without_governor_lease() -> None:
    calls: list[str] = []

    def broken_sizes():
        raise RuntimeError("ollama unreachable")

    def fake_ollama(prompt, *, timeout=0, model=None, task_class=None, attempts=None, **_kwargs):
        calls.append(model)
        return "answer"

    adaptive.adaptive_model_call(
        "hello",
        task_class="unclassified_explicit_model",
        timeout=60,
        primary_model="qwen3.6:latest",
        primary_lane="explicit_model",
        ollama_call_fn=fake_ollama,
        resolve_model_fn=lambda *a, **k: ("qwen3:8b-q4_K_M", "interactive"),
        model_sizes_fn=broken_sizes,
    )
    assert calls == ["qwen3:8b-q4_K_M"]


def test_resolver_chosen_model_is_not_rechecked() -> None:
    calls: list[str] = []

    def fake_ollama(prompt, *, timeout=0, model=None, task_class=None, attempts=None, **_kwargs):
        calls.append(model)
        return "answer"

    def sizes_must_not_be_called():
        raise AssertionError("resolver choices are ceiling-aware already — no re-check")

    adaptive.adaptive_model_call(
        "hello",
        task_class="unclassified_explicit_model",
        timeout=60,
        ollama_call_fn=fake_ollama,
        resolve_model_fn=lambda *a, **k: ("qwen3:8b-q4_K_M", "interactive"),
        model_sizes_fn=sizes_must_not_be_called,
    )
    assert calls == ["qwen3:8b-q4_K_M"]


def test_demotion_is_route_logged_with_reason() -> None:
    routes: list[dict] = []

    adaptive.adaptive_model_call(
        "hello",
        task_class="unclassified_explicit_model",
        timeout=60,
        primary_model="qwen3.6:latest",
        primary_lane="explicit_model",
        ollama_call_fn=lambda prompt, **k: "answer",
        resolve_model_fn=lambda *a, **k: ("qwen3:8b-q4_K_M", "interactive"),
        model_sizes_fn=lambda: {"qwen3.6:latest": 27.1},
        route_logger=lambda **kwargs: routes.append(kwargs),
    )
    demotions = [r for r in routes if str(r.get("reason", "")).startswith("model_fit_wall_demotion")]
    assert demotions, "the wall must leave a loud route-log trail"
    assert "qwen3.6:latest" in demotions[0]["reason"]
    assert demotions[0]["model"] == "qwen3:8b-q4_K_M"
