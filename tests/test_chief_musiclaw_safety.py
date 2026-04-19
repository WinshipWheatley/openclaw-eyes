import chief_musiclaw_brain


def test_musiclaw_advice_prompt_contains_legal_boundaries_and_ten_fingers_facts(monkeypatch):
    calls = []

    def fake_call(prompt, timeout=0):
        calls.append({"prompt": prompt, "timeout": timeout})
        return (
            "This is general information, not legal advice. "
            "Because there is no signed agreement, gather documents and consult an entertainment lawyer. "
            "⚠️ Bottom line: get lawyer review before action."
        )

    monkeypatch.setattr(chief_musiclaw_brain, "ollama_call", fake_call)

    result = chief_musiclaw_brain._ask_llm("What are my rights on Ten Fingers?")

    assert "not legal advice" in result.lower()
    assert "entertainment lawyer" in result.lower()
    assert calls == [{
        "prompt": chief_musiclaw_brain._ADVICE_PROMPT.format(
            knowledge=chief_musiclaw_brain.MUSIC_LAW_KNOWLEDGE,
            case=chief_musiclaw_brain.TEN_FINGERS_CASE,
            question="What are my rights on Ten Fingers?",
        ),
        "timeout": 45,
    }]
    prompt = calls[0]["prompt"]
    assert "Never give specific legal advice" in prompt
    assert "Always flag if this situation requires a real entertainment lawyer" in prompt
    assert "Song: \"Ten Fingers\"" in prompt
    assert "No signed co-ownership agreement exists" in prompt
    assert "NOT listed on the Maryland business entity registry" in prompt


def test_musiclaw_options_prompt_contains_lawyer_recommendation_and_case_facts(monkeypatch):
    calls = []

    def fake_call(prompt, timeout=0):
        calls.append({"prompt": prompt, "timeout": timeout})
        return (
            "General information only, not legal advice.\n"
            "1. Register your composition share.\n"
            "⚠️ Recommendation: Consult an entertainment lawyer before taking any action."
        )

    monkeypatch.setattr(chief_musiclaw_brain, "ollama_call", fake_call)

    result = chief_musiclaw_brain._options_summary()

    assert "not legal advice" in result.lower()
    assert "consult an entertainment lawyer" in result.lower()
    assert calls == [{
        "prompt": chief_musiclaw_brain._OPTIONS_PROMPT.format(
            knowledge=chief_musiclaw_brain.MUSIC_LAW_KNOWLEDGE,
            case=chief_musiclaw_brain.TEN_FINGERS_CASE,
        ),
        "timeout": 45,
    }]
    prompt = calls[0]["prompt"]
    assert "Ten Fingers / Log Rhythm Records" in prompt
    assert "Renae Timmi Jenkins" in prompt
    assert "End with: \"⚠️ Recommendation: Consult an entertainment lawyer before taking any action.\"" in prompt


def test_musiclaw_advice_adds_safety_footer_to_bad_model_output(monkeypatch):
    monkeypatch.setattr(chief_musiclaw_brain, "ollama_call", lambda prompt, timeout=0: "You should sue immediately.")

    result = chief_musiclaw_brain._ask_llm("Should I sue over Ten Fingers?")

    assert result.startswith("You should sue immediately.")
    assert "This is general information, not legal advice." in result
    assert "Consult an entertainment lawyer before taking action." in result


def test_musiclaw_empty_advice_output_uses_safe_fallback(monkeypatch):
    monkeypatch.setattr(chief_musiclaw_brain, "ollama_call", lambda prompt, timeout=0: "")

    result = chief_musiclaw_brain._ask_llm("What are my rights?")

    assert "Unable to generate advice right now." in result
    assert "not legal advice" in result.lower()
    assert "entertainment attorney" in result.lower()


def test_musiclaw_empty_options_output_uses_grounded_safe_fallback(monkeypatch):
    monkeypatch.setattr(chief_musiclaw_brain, "ollama_call", lambda prompt, timeout=0: None)

    result = chief_musiclaw_brain._options_summary()

    assert "Options for Ten Fingers dispute" in result
    assert "not legal advice" in result.lower()
    assert "ASCAP/BMI" in result
    assert "internal document" in result
    assert "Consult an entertainment lawyer before taking any action." in result
