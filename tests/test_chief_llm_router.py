from __future__ import annotations

import json

import pytest

import chief_llm


def _openrouter_metadata() -> dict[str, str]:
    return {"data_classification": "synthetic_public", "cloud_allowed": "true"}


class _OpenRouterResp:
    def __init__(self, payload: dict | str, *, status: int = 200):
        self.status = status
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        if isinstance(self._payload, str):
            return self._payload.encode("utf-8")
        return json.dumps(self._payload).encode("utf-8")


def _forbidden_request(*args, **kwargs):
    raise AssertionError("OpenRouter request must not be constructed")


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
    assert model == "qwen3:8b-q4_K_M"


def test_resolve_local_model_deep_fails_closed_when_only_oversized_models_exist(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"gemma4:31b", "gemma4:26b"},
    )

    model, lane = chief_llm.resolve_local_model(
        ("Please synthesize this reflection report. " * 90).strip()
    )

    assert lane == "deep"
    assert model == "qwen3:8b-q4_K_M"


def test_generic_lanes_do_not_use_cassandra_gemma_26b_by_default():
    assert "gemma4:26b" not in chief_llm.local_model_candidates("strong")
    assert "gemma4:26b" not in chief_llm.local_model_candidates("deep")


def test_contract_semantic_vote_has_one_explicit_fast_model_route():
    assert chief_llm.local_model_candidates(
        "fast", task_class="contract_semantic_vote"
    ) == ("qwen3:8b-q4_K_M",)
    assert chief_llm.choose_local_model_lane(
        "opaque prompt words",
        task_class="contract_semantic_vote",
    ) == "fast"


def test_ollama_call_fast_lane_uses_governed_interactive_8b(monkeypatch):
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
    assert calls == [("qwen3:8b-q4_K_M", 12)]


def test_ollama_call_enforces_unified_runner_for_interactive_8b(monkeypatch):
    captured: dict = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"response": "ok"}).encode("utf-8")

    def _fake_urlopen(req, timeout=0):
        captured.update(json.loads(req.data.decode("utf-8")))
        return _Resp()

    monkeypatch.setattr(chief_llm.urllib.request, "urlopen", _fake_urlopen)

    out = chief_llm.ollama_call(
        "Answer this operator question.",
        model="qwen3:8b-q4_K_M",
        lane="strong",
        task_class="chief_user_reply",
        options={
            "format": "json",
            "temperature": 0.7,
            "num_ctx": 4096,
            "num_gpu": 1,
            "num_batch": 512,
        },
        keep_alive="0",
        attempts=1,
    )

    assert out == "ok"
    assert captured["model"] == "qwen3:8b-q4_K_M"
    assert captured["options"] == {
        "temperature": 0.7,
        "num_ctx": 2048,
        "num_gpu": 999,
        "num_batch": 128,
    }
    assert captured["format"] == "json"
    assert captured["keep_alive"] == "10m"


def test_ollama_call_does_not_force_interactive_shape_on_async_8b(monkeypatch):
    captured: dict = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"response": "ok"}).encode("utf-8")

    def _fake_urlopen(req, timeout=0):
        captured.update(json.loads(req.data.decode("utf-8")))
        return _Resp()

    monkeypatch.setattr(chief_llm.urllib.request, "urlopen", _fake_urlopen)

    out = chief_llm.ollama_call(
        "Generate an asynchronous brief.",
        model="qwen3:8b-q4_K_M",
        task_class="cassandra_scheduled_brief",
        options={"num_ctx": 4096, "num_gpu": 10, "num_batch": 64},
        keep_alive="0",
        attempts=1,
        _governance_bypass=True,
    )

    assert out == "ok"
    assert captured["options"] == {"num_ctx": 4096, "num_gpu": 10, "num_batch": 64}
    assert captured["keep_alive"] == "0"


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
        lambda force_refresh=False: {"qwen3.5:9b", "qwen3:8b-q4_K_M"},
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
        if payload["model"] == "qwen3.5:9b":
            raise TimeoutError("timed out")
        return _Resp()

    monkeypatch.setattr(chief_llm.urllib.request, "urlopen", _fake_urlopen)

    out = chief_llm.ollama_call(
        "Generate the morning briefing.",
        timeout=180,
        task_class="cassandra_morning_brief",
    )

    assert out == "ok"
    assert calls == [("qwen3.5:9b", 420), ("qwen3:8b-q4_K_M", 420)]


def test_openrouter_call_missing_key_fails_closed_without_request(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(chief_llm.urllib.request, "Request", _forbidden_request)

    out = chief_llm.openrouter_call(
        "Synthetic public fixture prompt.",
        model="openrouter/test-model",
        metadata=_openrouter_metadata(),
    )

    assert out == ""


@pytest.mark.parametrize(
    ("prompt", "model", "metadata"),
    [
        ("Synthetic public fixture prompt.", "", _openrouter_metadata()),
        ("Synthetic public fixture prompt.", "   ", _openrouter_metadata()),
        ("", "openrouter/test-model", _openrouter_metadata()),
        ("   ", "openrouter/test-model", _openrouter_metadata()),
        ("Synthetic public fixture prompt.", "openrouter/test-model", None),
    ],
)
def test_openrouter_call_requires_prompt_model_and_metadata_without_request(
    monkeypatch,
    prompt,
    model,
    metadata,
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-secret")
    monkeypatch.setattr(chief_llm.urllib.request, "Request", _forbidden_request)

    assert chief_llm.openrouter_call(prompt, model=model, metadata=metadata) == ""


def test_openrouter_call_blocked_policy_does_not_build_request(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-secret")
    monkeypatch.setattr(chief_llm.urllib.request, "Request", _forbidden_request)

    out = chief_llm.openrouter_call(
        "Synthetic public fixture prompt.",
        model="openrouter/test-model",
        metadata={"data_classification": "synthetic_public"},
    )

    assert out == ""


def test_openrouter_call_allowed_public_packet_builds_mocked_request_without_exposing_key(
    monkeypatch,
    capsys,
):
    fake_key = "test-openrouter-secret"
    captured = {}
    logs = []
    monkeypatch.setenv("OPENROUTER_API_KEY", fake_key)
    monkeypatch.setattr(chief_llm, "_log_external_call", lambda *args: logs.append(args))

    def fake_urlopen(req, timeout=0):
        captured["req"] = req
        captured["timeout"] = timeout
        return _OpenRouterResp({"choices": [{"message": {"content": "mocked answer"}}]})

    monkeypatch.setattr(chief_llm.urllib.request, "urlopen", fake_urlopen)

    out = chief_llm.openrouter_call(
        "Synthetic public fixture prompt.",
        model="openrouter/test-model",
        metadata=_openrouter_metadata(),
        timeout=9,
    )
    stdout, stderr = capsys.readouterr()

    assert out == "mocked answer"
    assert captured["timeout"] == 9
    request = captured["req"]
    payload = json.loads(request.data.decode("utf-8"))
    assert request.full_url == chief_llm.OPENROUTER_URL
    assert request.get_header("Authorization") == f"Bearer {fake_key}"
    assert payload == {
        "model": "openrouter/test-model",
        "messages": [{"role": "user", "content": "Synthetic public fixture prompt."}],
        "max_tokens": 1024,
    }
    assert len(logs) == 1
    assert logs[0][0] == "openrouter:openrouter/test-model"
    assert logs[0][1] == 4
    assert logs[0][2] == 2
    assert logs[0][4] is True
    assert fake_key not in out
    assert fake_key not in stdout
    assert fake_key not in stderr
    assert fake_key not in repr(logs)


def test_external_language_model_call_uses_configured_openrouter_model(monkeypatch):
    calls = []
    monkeypatch.setenv("OPENCLAW_CASSANDRA_EXTERNAL_MODEL", "openrouter/test-model")

    def fake_openrouter(prompt, *, model, metadata, timeout=0):
        calls.append({"prompt": prompt, "model": model, "metadata": metadata, "timeout": timeout})
        return "openrouter answer"

    monkeypatch.setattr(chief_llm, "openrouter_call", fake_openrouter)
    monkeypatch.setattr(
        chief_llm,
        "nemotron_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Nemotron should not run")),
    )

    out = chief_llm.external_language_model_call(
        "Synthetic public fixture prompt.",
        metadata=_openrouter_metadata(),
        timeout=7,
    )

    assert out == "openrouter answer"
    assert calls == [
        {
            "prompt": "Synthetic public fixture prompt.",
            "model": "openrouter/test-model",
            "metadata": _openrouter_metadata(),
            "timeout": 7,
        }
    ]


def test_external_language_model_call_falls_back_to_nemotron_when_openrouter_unconfigured(monkeypatch):
    monkeypatch.delenv("OPENCLAW_CASSANDRA_EXTERNAL_MODEL", raising=False)
    monkeypatch.delenv("CASSANDRA_EXTERNAL_MODEL", raising=False)
    monkeypatch.delenv("OPENCLAW_EXTERNAL_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setattr(
        chief_llm,
        "openrouter_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("OpenRouter should not run")),
    )
    monkeypatch.setattr(chief_llm, "nemotron_call", lambda prompt, timeout=0: "nemotron answer")

    out = chief_llm.external_language_model_call(
        "Synthetic public fixture prompt.",
        metadata=_openrouter_metadata(),
    )

    assert out == "nemotron answer"


def test_external_language_model_call_blocked_policy_does_not_call_provider(monkeypatch):
    monkeypatch.setenv("OPENCLAW_CASSANDRA_EXTERNAL_MODEL", "openrouter/test-model")
    monkeypatch.setattr(
        chief_llm,
        "openrouter_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("OpenRouter should not run")),
    )
    monkeypatch.setattr(
        chief_llm,
        "nemotron_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Nemotron should not run")),
    )

    out = chief_llm.external_language_model_call(
        "Synthetic public fixture prompt.",
        metadata={"data_classification": "synthetic_public"},
    )

    assert out == ""


def test_openrouter_call_non_2xx_returns_empty(monkeypatch):
    logs = []
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-secret")
    monkeypatch.setattr(chief_llm, "_log_external_call", lambda *args: logs.append(args))
    monkeypatch.setattr(
        chief_llm.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _OpenRouterResp({"choices": []}, status=503),
    )

    out = chief_llm.openrouter_call(
        "Synthetic public fixture prompt.",
        model="openrouter/test-model",
        metadata=_openrouter_metadata(),
    )

    assert out == ""
    assert logs[-1][4] is False


def test_openrouter_call_network_error_returns_empty(monkeypatch):
    logs = []
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-secret")
    monkeypatch.setattr(chief_llm, "_log_external_call", lambda *args: logs.append(args))

    def raise_timeout(*args, **kwargs):
        raise TimeoutError("synthetic timeout")

    monkeypatch.setattr(chief_llm.urllib.request, "urlopen", raise_timeout)

    out = chief_llm.openrouter_call(
        "Synthetic public fixture prompt.",
        model="openrouter/test-model",
        metadata=_openrouter_metadata(),
    )

    assert out == ""
    assert logs[-1][4] is False


def test_openrouter_call_malformed_response_returns_empty(monkeypatch):
    logs = []
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-secret")
    monkeypatch.setattr(chief_llm, "_log_external_call", lambda *args: logs.append(args))
    monkeypatch.setattr(
        chief_llm.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _OpenRouterResp("not-json"),
    )

    out = chief_llm.openrouter_call(
        "Synthetic public fixture prompt.",
        model="openrouter/test-model",
        metadata=_openrouter_metadata(),
    )

    assert out == ""
    assert logs[-1][4] is False


def test_openrouter_call_missing_content_returns_empty(monkeypatch):
    logs = []
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-secret")
    monkeypatch.setattr(chief_llm, "_log_external_call", lambda *args: logs.append(args))
    monkeypatch.setattr(
        chief_llm.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _OpenRouterResp({"choices": [{"message": {}}]}),
    )

    out = chief_llm.openrouter_call(
        "Synthetic public fixture prompt.",
        model="openrouter/test-model",
        metadata=_openrouter_metadata(),
    )

    assert out == ""
    assert logs[-1][4] is False


def test_openrouter_call_empty_content_returns_empty(monkeypatch):
    logs = []
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-secret")
    monkeypatch.setattr(chief_llm, "_log_external_call", lambda *args: logs.append(args))
    monkeypatch.setattr(
        chief_llm.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _OpenRouterResp({"choices": [{"message": {"content": "   "}}]}),
    )

    out = chief_llm.openrouter_call(
        "Synthetic public fixture prompt.",
        model="openrouter/test-model",
        metadata=_openrouter_metadata(),
    )

    assert out == ""
    assert logs[-1][4] is False


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
    assert model == "qwen3:8b-q4_K_M"


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
    assert model == "qwen3:8b-q4_K_M"


def test_resolve_local_model_routes_cassandra_outbound_draft_to_strong(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"qwen3.5:9b", "nemotron-3-nano:4b"},
    )
    monkeypatch.setattr(chief_llm, "_ollama_model_sizes", lambda *a, **k: {"qwen3.5:9b": 6.6})

    model, lane = chief_llm.resolve_local_model(
        "Draft a short warm reply.",
        task_class="cassandra_outbound_draft",
    )

    assert lane == "strong"
    assert model == "qwen3.5:9b"


def test_resolve_local_model_routes_cassandra_bounded_hidden_tasks_to_fast(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"qwen3:4b", "nemotron-3-nano:4b"},
    )
    monkeypatch.setattr(chief_llm, "_ollama_model_sizes", lambda *a, **k: {"qwen3:4b": 2.5})

    model, lane = chief_llm.resolve_local_model(
        "Summarize sender and subject only.",
        task_class="cassandra_inbox_summary",
    )

    assert lane == "fast"
    assert model == "qwen3:4b"


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
    assert model == "qwen3:8b-q4_K_M"


def test_cassandra_easy_reply_keeps_operator_bound_8b_when_inventory_is_incomplete(monkeypatch):
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
    assert model == "qwen3:8b-q4_K_M"


def test_cassandra_easy_reply_reason_names_resident_8b_policy():
    reason = chief_llm.local_model_route_reason(
        "Yep.",
        "fast",
        task_class="cassandra_user_reply_fast",
    )

    assert "resident qwen3 8b" in reason
    assert "gemma" not in reason.lower()


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
    assert model == "qwen3:8b-q4_K_M"


def test_cassandra_morning_brief_prefers_safe_qwen9(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"qwen3.5:9b", "gemma4:26b"},
    )
    monkeypatch.setattr(chief_llm, "_ollama_model_sizes", lambda *a, **k: {"qwen3.5:9b": 6.6, "gemma4:26b": 17.0})

    model, lane = chief_llm.resolve_local_model(
        "Generate the morning briefing.",
        task_class="cassandra_morning_brief",
    )

    assert lane == "strong"
    assert model == "qwen3.5:9b"


def test_cassandra_morning_brief_falls_back_to_resident_8b(monkeypatch):
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
    assert model == "qwen3:8b-q4_K_M"


def test_cassandra_morning_brief_test_mode_prefers_qwen4(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"qwen3:4b", "gemma4:e4b"},
    )
    monkeypatch.setattr(chief_llm, "_ollama_model_sizes", lambda *a, **k: {"qwen3:4b": 2.5, "gemma4:e4b": 9.6})

    model, lane = chief_llm.resolve_local_model(
        "Generate the morning briefing in test mode.",
        task_class="cassandra_morning_brief_test",
    )

    assert lane == "fast"
    assert model == "qwen3:4b"


def test_cassandra_morning_brief_test_mode_falls_back_to_resident_8b(monkeypatch):
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
    assert model == "qwen3:8b-q4_K_M"


def test_cassandra_task_candidates_stay_in_qwen3_family():
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
        assert all(candidate.startswith(("qwen", "nemotron", "magistral", "mistral")) for candidate in candidates)


def test_chief_evidence_scan_resolves_to_nemotron_4b(monkeypatch):
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda force_refresh=False: {"nemotron-3-nano:4b", "nemotron-3-nano:30b"},
    )
    monkeypatch.setattr(
        chief_llm,
        "_ollama_model_sizes",
        lambda *a, **k: {"nemotron-3-nano:4b": 2.8, "nemotron-3-nano:30b": 17.0},
    )

    model, lane = chief_llm.resolve_local_model(
        "Extract only the evidence rows relevant to this issue.",
        task_class="chief_evidence_scan",
    )

    assert lane == "fast"
    assert model == "nemotron-3-nano:4b"


def test_chief_evidence_synthesis_fails_closed_when_only_oversized_models_exist(monkeypatch):
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
    assert model == "qwen3:8b-q4_K_M"


def test_chief_structured_plan_fails_closed_when_only_oversized_models_exist(monkeypatch):
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
    assert model == "qwen3:8b-q4_K_M"


def test_chief_ambiguous_debug_fails_closed_when_only_oversized_models_exist(monkeypatch):
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
    assert model == "qwen3:8b-q4_K_M"


def test_chief_agentic_code_fails_closed_when_only_oversized_models_exist(monkeypatch):
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
    assert model == "qwen3:8b-q4_K_M"
