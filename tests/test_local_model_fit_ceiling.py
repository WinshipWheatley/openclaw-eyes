from __future__ import annotations

import chief_llm


def test_largest_fitting_installed_model_downshifts_oversized() -> None:
    # gemma4:26b (~19GB) must NOT be chosen on a 12GB-ceiling box -- it swaps to ~0.75 tok/s and
    # starves every other local model. Downshift to the small installed fallback (e4b).
    candidates = ("gemma4:31b", "gemma4:26b", "gemma4:e4b")
    installed = {"gemma4:26b", "gemma4:e4b"}
    sizes = {"gemma4:31b": 20.0, "gemma4:26b": 19.0, "gemma4:e4b": 3.0}
    assert chief_llm._largest_fitting_installed_model(candidates, installed, sizes, 12.0) == "gemma4:e4b"


def test_largest_fitting_installed_model_prefers_largest_that_fits() -> None:
    # Within the ceiling, keep the LARGEST fitting model (best quality), not the smallest.
    candidates = ("gemma4:31b", "qwen2.5-coder:14b", "gemma4:e4b")
    installed = {"qwen2.5-coder:14b", "gemma4:e4b"}
    sizes = {"gemma4:31b": 20.0, "qwen2.5-coder:14b": 9.0, "gemma4:e4b": 3.0}
    assert chief_llm._largest_fitting_installed_model(candidates, installed, sizes, 12.0) == "qwen2.5-coder:14b"


def test_largest_fitting_installed_model_none_when_nothing_known_fits() -> None:
    # No installed candidate with a known fitting size -> None (caller falls back to legacy pick).
    candidates = ("gemma4:31b", "gemma4:26b")
    installed = {"gemma4:26b"}
    sizes = {"gemma4:31b": 20.0, "gemma4:26b": 19.0}
    assert chief_llm._largest_fitting_installed_model(candidates, installed, sizes, 12.0) is None


def test_resolve_local_model_downshifts_oversized_briefing(monkeypatch) -> None:
    # Live regression: cassandra_morning_brief resolved to gemma4:26b, which swapped and took the
    # front-door brain DOWN. With a 12GB ceiling it must downshift to the fitting fallback.
    monkeypatch.setattr(chief_llm, "_ollama_installed_models", lambda *a, **k: {"gemma4:26b", "gemma4:e4b"})
    monkeypatch.setattr(chief_llm, "_ollama_model_sizes", lambda *a, **k: {"gemma4:26b": 19.0, "gemma4:e4b": 3.0})
    monkeypatch.setattr(chief_llm, "_local_model_size_ceiling_gb", lambda: 12.0)
    model, _lane = chief_llm.resolve_local_model("write the morning brief", task_class="cassandra_morning_brief")
    assert model == "gemma4:e4b"


def test_largest_fitting_installed_overall_prefers_family() -> None:
    installed = {"gemma4:26b", "gemma4:e4b", "qwen3.5:9b"}
    sizes = {"gemma4:26b": 18.0, "gemma4:e4b": 9.6, "qwen3.5:9b": 6.6}
    # family-preferred: largest fitting gemma (e4b @9.6) beats the larger-overall rule only via family
    assert chief_llm._largest_fitting_installed_overall(installed, sizes, 12.0, prefer_family="gemma4") == "gemma4:e4b"
    # no family pref -> largest fitting overall (e4b @9.6 > qwen3.5:9b @6.6)
    assert chief_llm._largest_fitting_installed_overall(installed, sizes, 12.0) == "gemma4:e4b"
    # nothing fits -> None
    assert chief_llm._largest_fitting_installed_overall({"gemma4:26b"}, {"gemma4:26b": 18.0}, 12.0) is None


def test_resolve_local_model_global_fallback_when_all_listed_oversized(monkeypatch) -> None:
    # cassandra_user_reply candidates are ALL oversized (gemma4:26b/31b). Rather than fail open to
    # an oversized model that swaps and starves the fleet, downshift to the largest installed model
    # that fits, preferring the gemma family for persona continuity.
    monkeypatch.setattr(
        chief_llm, "_ollama_installed_models",
        lambda *a, **k: {"gemma4:26b", "gemma4:31b", "gemma4:e4b", "qwen3.5:9b"},
    )
    monkeypatch.setattr(
        chief_llm, "_ollama_model_sizes",
        lambda *a, **k: {"gemma4:26b": 18.0, "gemma4:31b": 20.0, "gemma4:e4b": 9.6, "qwen3.5:9b": 6.6},
    )
    monkeypatch.setattr(chief_llm, "_local_model_size_ceiling_gb", lambda: 12.0)
    model, _lane = chief_llm.resolve_local_model("hey cassandra", task_class="cassandra_user_reply")
    assert model == "gemma4:e4b"


def test_resolve_local_model_keeps_legacy_when_no_fitting_known(monkeypatch) -> None:
    # Fail-open: if no installed candidate has a known fitting size, keep the legacy first-installed
    # pick rather than returning nothing.
    monkeypatch.setattr(chief_llm, "_ollama_installed_models", lambda *a, **k: {"gemma4:26b"})
    monkeypatch.setattr(chief_llm, "_ollama_model_sizes", lambda *a, **k: {"gemma4:26b": 19.0})
    monkeypatch.setattr(chief_llm, "_local_model_size_ceiling_gb", lambda: 12.0)
    model, _lane = chief_llm.resolve_local_model("write the morning brief", task_class="cassandra_morning_brief")
    assert model == "gemma4:26b"
