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


def test_extract_event_details_falls_back_to_claude_when_local_extract_is_invalid(monkeypatch):
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
        lambda prompt, timeout=20: {
            "title": "Lunch",
            "date": "2026-04-19",
            "start_time": "12:00",
            "duration_minutes": 60,
        },
        raising=False,
    )

    details = cassandra_brain._extract_event_details("put lunch on my calendar tomorrow at noon")

    assert details == {
        "title": "Lunch",
        "date": "2026-04-19",
        "start_time": "12:00",
        "duration_minutes": 60,
    }
