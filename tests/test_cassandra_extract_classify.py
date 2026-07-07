from __future__ import annotations


def test_extract_event_details_uses_local_cassandra_extract_classify_first(monkeypatch):
    import cassandra_brain

    route_calls = []
    model_calls = []

    monkeypatch.setattr(
        cassandra_brain,
        "resolve_local_model",
        lambda prompt, lane=None, task_class=None: route_calls.append(
            {"lane": lane, "task_class": task_class}
        ) or ("nemotron-3-nano:4b", "fast"),
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "ollama_call",
        lambda prompt, timeout=0, model=None, lane=None, task_class=None: model_calls.append(model) or (
            '{"title":"Doctor Appointment","date":"2026-04-19","start_time":"14:30","duration_minutes":45}'
        ),
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "claude_json",
        lambda prompt, timeout=20: (_ for _ in ()).throw(AssertionError("claude_json should not run")),
        raising=False,
    )

    details = cassandra_brain._extract_event_details("schedule doctor appointment tomorrow at 2:30pm for 45 minutes")

    assert details == {
        "title": "Doctor Appointment",
        "date": "2026-04-19",
        "start_time": "14:30",
        "duration_minutes": 45,
    }
    assert route_calls == [{"lane": None, "task_class": "cassandra_extract_classify"}]
    assert model_calls == ["nemotron-3-nano:4b"]


def test_hidden_extract_classify_retries_downshifted_model_after_empty_primary(monkeypatch):
    import adaptive_model_call as adaptive
    import cassandra_brain

    route_calls = []
    model_calls = []

    monkeypatch.setattr(
        cassandra_brain,
        "resolve_local_model",
        lambda prompt, lane=None, task_class=None: route_calls.append(
            {"lane": lane, "task_class": task_class}
        ) or ("gemma4:31b", "strong"),
        raising=False,
    )
    monkeypatch.setattr(
        adaptive,
        "probe_frontdoor_resources",
        lambda: type(
            "Snapshot",
            (),
            {
                "available_vram_gb": 0.5,
                "available_ram_gb": 10.0,
                "system_load_1m": 20.0,
                "cpu_count": 4,
                "resident_vram_by_model_gb": lambda self: {},
            },
        )(),
        raising=False,
    )
    monkeypatch.setattr(
        adaptive,
        "select_frontdoor_model",
        lambda **_kwargs: ("qwen3:8b-q4_K_M", "frontdoor_step_down_system_load"),
        raising=False,
    )

    def fake_ollama(prompt, timeout=0, model=None, lane=None, task_class=None, attempts=None):
        model_calls.append({"model": model, "timeout": timeout, "attempts": attempts})
        if model == "qwen3:8b-q4_K_M":
            return '{"intent":"calendar_create","confidence":"high"}'
        return ""

    monkeypatch.setattr(cassandra_brain, "ollama_call", fake_ollama, raising=False)

    parsed = cassandra_brain._call_hidden_extract_classify_json("extract intent", validation_label="fixture")

    assert parsed == {"intent": "calendar_create", "confidence": "high"}
    assert route_calls == [{"lane": None, "task_class": "cassandra_extract_classify"}]
    assert model_calls == [
        {"model": "gemma4:31b", "timeout": 20, "attempts": 1},
        {"model": "qwen3:8b-q4_K_M", "timeout": 20, "attempts": 1},
    ]


def test_extract_event_details_parses_exact_doctor_appointment_shape_without_models(monkeypatch):
    import cassandra_brain

    monkeypatch.setattr(
        cassandra_brain,
        "_call_hidden_extract_classify_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("local extract should not run")),
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "claude_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("claude fallback should not run")),
        raising=False,
    )

    details = cassandra_brain._extract_event_details(
        "Cassandra, put Doctor Appointment on my calendar tomorrow at 2:30 PM for 45 minutes."
    )

    assert details["title"] == "Doctor Appointment"
    assert details["start_time"] == "14:30"
    assert details["duration_minutes"] == 45


def test_extract_event_details_fails_closed_when_local_extract_is_invalid(monkeypatch):
    import cassandra_brain

    monkeypatch.setattr(
        cassandra_brain,
        "resolve_local_model",
        lambda prompt, lane=None, task_class=None: ("nemotron-3-nano:4b", "fast"),
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "ollama_call",
        lambda prompt, timeout=0, model=None, lane=None, task_class=None: '{"title": null}',
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "claude_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("claude fallback should not run")),
        raising=False,
    )

    details = cassandra_brain._extract_event_details("put lunch on my calendar tomorrow at noon")

    assert details is None


def test_extract_event_details_does_not_use_claude_fallback(monkeypatch):
    import cassandra_brain

    fallback_calls = []

    monkeypatch.setattr(
        cassandra_brain,
        "resolve_local_model",
        lambda prompt, lane=None, task_class=None: ("nemotron-3-nano:4b", "fast"),
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "ollama_call",
        lambda prompt, timeout=0, model=None, lane=None, task_class=None: '{"title": null}',
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "claude_json",
        lambda prompt, timeout=20, retries=3: fallback_calls.append(
            {"timeout": timeout, "retries": retries}
        ) or {},
        raising=False,
    )

    details = cassandra_brain._extract_event_details(
        "Put lunch with Dana on my calendar sometime tomorrow afternoon."
    )

    assert details is None
    assert fallback_calls == []
