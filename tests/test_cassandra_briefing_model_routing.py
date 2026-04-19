from __future__ import annotations

def test_generate_morning_brief_uses_cassandra_morning_brief_task_class(monkeypatch, tmp_path):
    import cassandra_briefing_brain as bb

    synthesis = tmp_path / "Chief Morning Synthesis.md"
    cache = tmp_path / "morning_reference_cache.json"
    synthesis.write_text(
        "# Chief Morning Synthesis\n\n"
        "## Top Priorities\n\n"
        "- Ops Actions Context: Follow up on Coupa verification.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bb, "_CHIEF_MORNING_SYNTHESIS", synthesis, raising=False)
    monkeypatch.setattr(bb, "_MORNING_REFERENCE_CACHE", cache, raising=False)
    monkeypatch.setattr(bb, "_morning_task_config", lambda: ("cassandra_morning_brief", "llm"))
    monkeypatch.setattr(
        bb,
        "build_context_snapshot",
        lambda: (_ for _ in ()).throw(AssertionError("morning should use Chief synthesis")),
        raising=False,
    )

    route_calls = []
    model_calls = []
    prompts = []

    monkeypatch.setattr(
        bb,
        "ollama_json",
        lambda prompt, timeout=0, task_class=None: (
            prompts.append(prompt),
            route_calls.append({"task_class": task_class}),
        )[-1] or [{"header": "TEST", "body": "Morning briefing."}],
        raising=False,
    )

    text = bb.generate_briefing("morning")

    assert "Morning briefing." in text
    assert route_calls == [{"task_class": "cassandra_morning_brief"}]
    assert "Executive Assistant to the Founder" in prompts[0]
    assert "CHIEF MORNING SYNTHESIS" in prompts[0]
    assert "Follow up on Coupa verification" in prompts[0]
    assert cache.exists()


def test_generate_morning_brief_test_mode_uses_test_task_class(monkeypatch, tmp_path):
    import cassandra_briefing_brain as bb

    synthesis = tmp_path / "Chief Morning Synthesis.md"
    cache = tmp_path / "morning_reference_cache.json"
    synthesis.write_text(
        "# Chief Morning Synthesis\n\n"
        "## Top Priorities\n\n"
        "- Test mode priority.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CASSANDRA_MORNING_BRIEF_TEST_MODE", "1")
    monkeypatch.setattr(bb, "_CHIEF_MORNING_SYNTHESIS", synthesis, raising=False)
    monkeypatch.setattr(bb, "_MORNING_REFERENCE_CACHE", cache, raising=False)

    route_calls = []
    model_calls = []
    prompts = []
    
    monkeypatch.setattr(
        bb,
        "ollama_json",
        lambda prompt, timeout=0, task_class=None: (
            prompts.append(prompt),
            route_calls.append({"task_class": task_class}),
        )[-1] or [{"header": "TEST", "body": "Fast test briefing."}],
        raising=False,
    )

    text = bb.generate_briefing("morning")

    assert "Fast test briefing." in text
    assert route_calls == [{"task_class": "cassandra_morning_brief_test"}]
    assert "Executive Assistant to the Founder" not in prompts[0]
    assert "COMPACT TEST CONTEXT" in prompts[0]
    assert "## Top Priorities" not in prompts[0]
    assert str(synthesis) not in prompts[0]
    assert len(prompts[0].split()) < 180


def test_generate_afternoon_brief_uses_cassandra_user_reply_task_class(monkeypatch):
    import cassandra_briefing_brain as bb

    monkeypatch.setattr(bb, "build_context_snapshot", lambda: "live context", raising=False)

    route_calls = []
    model_calls = []

    monkeypatch.setattr(
        bb,
        "resolve_local_model",
        lambda prompt, lane=None, task_class=None: route_calls.append(
            {"lane": lane, "task_class": task_class}
        ) or ("gemma4:26b", "strong"),
        raising=False,
    )
    monkeypatch.setattr(
        bb,
        "ollama_call",
        lambda prompt, timeout=0, model=None, lane=None, task_class=None: model_calls.append(model) or "Afternoon briefing.",
        raising=False,
    )

    text = bb.generate_briefing("afternoon")

    assert text == "Afternoon briefing."
    assert route_calls == [{"lane": None, "task_class": "cassandra_user_reply"}]
    assert model_calls == ["gemma4:26b"]
