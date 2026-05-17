from datetime import datetime
from pathlib import Path


FIXED_NOW = datetime(2026, 5, 17, 9, 0)


def test_relative_date_resolution_from_may_17_2026():
    from cassandra_date_awareness import resolve_relative_date_phrase

    expected = {
        "today": ("2026-05-17", None, "Sunday"),
        "yesterday": ("2026-05-16", None, "Saturday"),
        "tomorrow": ("2026-05-18", None, "Monday"),
        "this friday": ("2026-05-22", None, "Friday"),
        "last thursday": ("2026-05-14", None, "Thursday"),
        "next week": ("2026-05-18", "2026-05-24", None),
        "last week": ("2026-05-04", "2026-05-10", None),
        "next month": ("2026-06", None, None),
        "last month": ("2026-04", None, None),
        "next year": ("2027", None, None),
        "last year": ("2025", None, None),
    }

    for phrase, (start, end, weekday) in expected.items():
        resolved = resolve_relative_date_phrase(phrase, now=FIXED_NOW)
        assert resolved.start_date == start
        assert resolved.end_date == end
        assert resolved.weekday == weekday


def test_authoritative_date_context_mentions_current_date_and_model_memory_rule():
    from cassandra_date_awareness import build_authoritative_date_context

    context = build_authoritative_date_context(now=FIXED_NOW)

    assert context.startswith("[AUTHORITATIVE DATE CONTEXT]")
    assert "2026-05-17" in context
    assert "Sunday" in context
    assert "this friday: 2026-05-22 (friday)" in context.lower()
    assert "Do not use stale model memory for dates." in context


def test_direct_date_awareness_answers_required_phrases():
    from cassandra_date_awareness import answer_date_awareness_query

    checks = {
        "What date is today?": "Today is 2026-05-17 (Sunday).",
        "What day was yesterday?": "Yesterday is 2026-05-16 (Saturday).",
        "What date is tomorrow?": "Tomorrow is 2026-05-18 (Monday).",
        "When is this Friday?": "This Friday is 2026-05-22 (Friday).",
        "What day was last Thursday?": "Last Thursday is 2026-05-14 (Thursday).",
        "What date is next week?": "Next Week is 2026-05-18 (Monday) through 2026-05-24 (Sunday).",
        "What date was last week?": "Last Week is 2026-05-04 (Monday) through 2026-05-10 (Sunday).",
        "What is next month?": "Next Month is June 2026.",
        "What is last month?": "Last Month is April 2026.",
        "What is next year?": "Next Year is 2027.",
        "What is last year?": "Last Year is 2025.",
    }

    for query, expected in checks.items():
        assert answer_date_awareness_query(query, now=FIXED_NOW) == expected


def test_non_date_use_of_today_does_not_trigger_date_answer():
    from cassandra_date_awareness import answer_date_awareness_query

    assert answer_date_awareness_query("what matters today?", now=FIXED_NOW) is None


def test_cassandra_handle_direct_date_query_bypasses_llm(monkeypatch):
    import cassandra_brain

    logged = []
    monkeypatch.setattr(cassandra_brain, "record_cassandra_packet_event", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "answer_date_awareness_query",
        lambda query: "Today is 2026-05-17 (Sunday).",
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda text, replies, route="llm", metadata=None: logged.append({"route": route, "replies": replies}),
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should not be called")),
        raising=False,
    )

    assert cassandra_brain.handle("What date is today?") == ["Today is 2026-05-17 (Sunday)."]
    assert logged[-1]["route"] == "date_awareness"


def test_llm_prompt_places_authoritative_date_context_before_persona():
    source = Path("/home/openclaw/cassandra_brain.py").read_text(encoding="utf-8")
    prompt_start = source.index("prompt = (")
    date_context = source.index('f"{build_authoritative_date_context()}\\n\\n"', prompt_start)
    persona = source.index('f"{persona}\\n"', prompt_start)

    assert date_context < persona


def test_wrong_date_scan_redacts_raw_content(tmp_path: Path):
    from cassandra_date_awareness import scan_wrong_date_correspondence

    log_path = tmp_path / "cassandra_conversations.jsonl"
    log_path.write_text(
        '{"ts":"2026-05-17 09:00:00","route":"llm","replies":["Today is June 24, 2024."]}\n',
        encoding="utf-8",
    )

    result = scan_wrong_date_correspondence((log_path,))

    assert result["wrong_date_correspondence_found"] is True
    assert result["wrong_date_match_count"] == 1
    assert result["raw_content_included"] is False
    assert result["matches"][0]["line_number"] == 1
    assert "Today is June" not in str(result["matches"])
