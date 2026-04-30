from __future__ import annotations

import json

import chief_llm


def test_choose_local_model_lane_prefers_fast_for_small_classifier_prompt():
    prompt = "Classify this message by intent and return JSON only."

    assert chief_llm.choose_local_model_lane(prompt) == "fast"


def test_choose_local_model_lane_prefers_strong_by_default():
    prompt = "Write a practical response to this short note."

    assert chief_llm.choose_local_model_lane(prompt) == "strong"


def test_choose_local_model_lane_prefers_deep_for_long_synthesis_prompt():
    prompt = ("Please synthesize this material into a reflection report. " * 90).strip()

    assert chief_llm.choose_local_model_lane(prompt) == "deep"


def test_local_model_route_reason_is_explicit_and_lane_correct():
    assert "fast-lane policy" in chief_llm.local_model_route_reason(
        "Classify this message by intent and return JSON only.",
        "fast",
    )
    assert "default strong lane" in chief_llm.local_model_route_reason(
        "Write a practical response to this short note.",
        "strong",
    )
    assert "deep threshold" in chief_llm.local_model_route_reason(
        ("Please synthesize this material into a reflection report. " * 90).strip(),
        "deep",
    )


def test_resolve_local_model_uses_installed_lane_candidate(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"gemma4:26b", "gemma4:31b", "qwen2.5-coder:14b"},
    )

    model, lane = chief_llm.resolve_local_model("Write a practical reply.")

    assert lane == "strong"
    assert model == "gemma4:31b"


def test_resolve_local_model_deep_falls_back_to_gemma_when_nemotron_missing(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"gemma4:31b", "gemma4:26b"},
    )

    model, lane = chief_llm.resolve_local_model(
        ("Please synthesize this reflection report. " * 90).strip()
    )

    assert lane == "deep"
    assert model == "gemma4:31b"


def test_generic_lanes_do_not_use_cassandra_gemma_26b_by_default():
    assert "gemma4:26b" not in chief_llm.local_model_candidates("strong")
    assert "gemma4:26b" not in chief_llm.local_model_candidates("deep")


def test_ollama_call_lane_uses_resolved_model(monkeypatch):
    calls: list[tuple[str, int]] = []

    monkeypatch.setattr(
        chief_llm,
        "resolve_local_model",
        lambda prompt, lane=None, task_class=None: ("nemotron-3-nano:4b", "fast"),
    )

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"response": "ok"}).encode("utf-8")

    def _fake_urlopen(req, timeout=0):
        payload = json.loads(req.data.decode("utf-8"))
        calls.append((payload["model"], timeout))
        return _Resp()

    monkeypatch.setattr(chief_llm.urllib.request, "urlopen", _fake_urlopen)

    out = chief_llm.ollama_call("Classify this quickly.", lane="fast", timeout=12)

    assert out == "ok"
    assert calls == [("nemotron-3-nano:4b", 12)]


def test_ollama_call_tunes_cassandra_morning_test_timeout_without_retries(monkeypatch):
    calls: list[tuple[str, int]] = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"response": "ok"}).encode("utf-8")

    def _fake_urlopen(req, timeout=0):
        payload = json.loads(req.data.decode("utf-8"))
        calls.append((payload["model"], timeout))
        return _Resp()

    monkeypatch.setattr(chief_llm.urllib.request, "urlopen", _fake_urlopen)

    out = chief_llm.ollama_call(
        "Compact morning test prompt.",
        timeout=45,
        model="gemma4:e4b",
        task_class="cassandra_morning_brief_test",
    )

    assert out == "ok"
    assert calls == [("gemma4:e4b", 180)]


def test_ollama_call_cassandra_morning_brief_falls_back_across_models(monkeypatch):
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(chief_llm, "_CASSANDRA_MORNING_BRIEF_TIMEOUT", 420, raising=False)
    monkeypatch.setattr(chief_llm, "_CASSANDRA_MORNING_BRIEF_ATTEMPTS", 1, raising=False)
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"gemma4:31b", "gemma4:26b"},
    )

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"response": "ok"}).encode("utf-8")

    def _fake_urlopen(req, timeout=0):
        payload = json.loads(req.data.decode("utf-8"))
        calls.append((payload["model"], timeout))
        if payload["model"] == "gemma4:31b":
            raise TimeoutError("timed out")
        return _Resp()

    monkeypatch.setattr(chief_llm.urllib.request, "urlopen", _fake_urlopen)

    out = chief_llm.ollama_call(
        "Generate the morning briefing.",
        timeout=180,
        task_class="cassandra_morning_brief",
    )

    assert out == "ok"
    assert calls == [("gemma4:31b", 420), ("gemma4:26b", 420)]


def test_resolve_local_model_routes_cassandra_user_reply_to_gemma_26b(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"nemotron-3-nano:4b", "gemma4:26b", "gemma4:31b"},
    )

    model, lane = chief_llm.resolve_local_model(
        "Ok.",
        task_class="cassandra_user_reply",
    )

    assert lane == "strong"
    assert model == "gemma4:26b"


def test_resolve_local_model_routes_cassandra_easy_reply_to_small_lane(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"gemma4:e4b", "gemma4:26b", "gemma4:31b"},
    )

    model, lane = chief_llm.resolve_local_model(
        "ok",
        task_class="cassandra_user_reply_fast",
    )

    assert lane == "fast"
    assert model == "gemma4:e4b"


def test_resolve_local_model_routes_cassandra_outbound_draft_to_strong(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"nemotron-3-nano:4b", "nemotron-3-nano:30b", "gemma4:31b"},
    )

    model, lane = chief_llm.resolve_local_model(
        "Draft a short warm reply.",
        task_class="cassandra_outbound_draft",
    )

    assert lane == "strong"
    assert model == "gemma4:31b"


def test_resolve_local_model_routes_cassandra_bounded_hidden_tasks_to_fast(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"nemotron-3-nano:4b", "gemma4:e4b", "gemma4:31b"},
    )

    model, lane = chief_llm.resolve_local_model(
        "Summarize sender and subject only.",
        task_class="cassandra_inbox_summary",
    )

    assert lane == "fast"
    assert model == "gemma4:e4b"


def test_short_cassandra_user_reply_does_not_downgrade_to_fast(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"nemotron-3-nano:4b", "nemotron-3-nano:30b", "gemma4:31b"},
    )

    model, lane = chief_llm.resolve_local_model(
        "Yep.",
        task_class="cassandra_user_reply_fast",
    )

    assert lane == "fast"
    assert model == "gemma4:31b"


def test_cassandra_easy_reply_falls_back_to_gemma_26b(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"qwen2.5-coder:7b", "gemma4:26b"},
    )

    model, lane = chief_llm.resolve_local_model(
        "Yep.",
        task_class="cassandra_user_reply_fast",
    )

    assert lane == "fast"
    assert model == "gemma4:26b"


def test_cassandra_user_reply_falls_back_to_gemma_26b_before_nemotron(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"nemotron-3-nano:30b", "gemma4:26b"},
    )

    model, lane = chief_llm.resolve_local_model(
        "Write a practical response to this short note.",
        task_class="cassandra_user_reply",
    )

    assert lane == "strong"
    assert model == "gemma4:26b"


def test_cassandra_morning_brief_prefers_gemma_31b(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"nemotron-3-nano:30b", "gemma4:26b", "gemma4:31b"},
    )

    model, lane = chief_llm.resolve_local_model(
        "Generate the morning briefing.",
        task_class="cassandra_morning_brief",
    )

    assert lane == "strong"
    assert model == "gemma4:31b"


def test_cassandra_morning_brief_falls_back_to_gemma_26b(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"nemotron-3-nano:30b", "gemma4:26b"},
    )

    model, lane = chief_llm.resolve_local_model(
        "Generate the morning briefing.",
        task_class="cassandra_morning_brief",
    )

    assert lane == "strong"
    assert model == "gemma4:26b"


def test_cassandra_morning_brief_test_mode_prefers_gemma_e4b(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"gemma4:e4b", "gemma4:26b", "gemma4:31b"},
    )

    model, lane = chief_llm.resolve_local_model(
        "Generate the morning briefing in test mode.",
        task_class="cassandra_morning_brief_test",
    )

    assert lane == "fast"
    assert model == "gemma4:e4b"


def test_cassandra_morning_brief_test_mode_falls_back_to_26b(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"gemma4:26b", "gemma4:31b"},
    )

    model, lane = chief_llm.resolve_local_model(
        "Generate the morning briefing in test mode.",
        task_class="cassandra_morning_brief_test",
    )

    assert lane == "fast"
    assert model == "gemma4:26b"


def test_cassandra_task_candidates_stay_in_gemma4_family():
    for task_class in (
        "cassandra_user_reply_fast",
        "cassandra_user_reply",
        "cassandra_outbound_draft",
        "cassandra_morning_brief",
        "cassandra_morning_brief_test",
        "cassandra_inbox_summary",
        "cassandra_extract_classify",
    ):
        candidates = chief_llm.local_model_candidates("strong", task_class=task_class)
        assert candidates
        assert all(candidate.startswith("gemma4:") for candidate in candidates)


def test_chief_evidence_scan_resolves_to_nemotron_4b(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"nemotron-3-nano:4b", "nemotron-3-nano:30b"},
    )

    model, lane = chief_llm.resolve_local_model(
        "Extract only the evidence rows relevant to this issue.",
        task_class="chief_evidence_scan",
    )

    assert lane == "fast"
    assert model == "nemotron-3-nano:4b"


def test_chief_evidence_synthesis_resolves_to_nemotron_30b(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"nemotron-3-nano:30b", "mistral-small:latest"},
    )

    model, lane = chief_llm.resolve_local_model(
        "Synthesize conflicting log evidence into a short factual report.",
        task_class="chief_evidence_synthesis",
    )

    assert lane == "deep"
    assert model == "nemotron-3-nano:30b"


def test_chief_structured_plan_resolves_to_mistral_small(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"mistral-small:latest", "magistral:latest"},
    )

    model, lane = chief_llm.resolve_local_model(
        "Create a bounded action plan from these known facts.",
        task_class="chief_structured_plan",
    )

    assert lane == "strong"
    assert model == "mistral-small:latest"


def test_chief_ambiguous_debug_resolves_to_magistral(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"magistral:latest", "nemotron-3-nano:30b"},
    )

    model, lane = chief_llm.resolve_local_model(
        "Debug this ambiguous failure with competing evidence.",
        task_class="chief_ambiguous_debug",
    )

    assert lane == "deep"
    assert model == "magistral:latest"


def test_chief_agentic_code_resolves_to_qwen36(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"qwen3.6:latest", "mistral-small:latest"},
    )

    model, lane = chief_llm.resolve_local_model(
        "Plan the smallest safe code patch for this bug.",
        task_class="chief_agentic_code",
    )

    assert lane == "code_challenger"
    assert model == "qwen3.6:latest"
