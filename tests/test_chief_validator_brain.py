import chief_validator_brain as validator


def _captured_log(monkeypatch):
    entries = []

    def append_log(intent: str, issue: str, action: str) -> None:
        entries.append((intent, issue, action))

    monkeypatch.setattr(validator, "_append_log", append_log)
    return entries


def test_severity_failed_softened_to_pending_is_blocked(monkeypatch):
    log_entries = _captured_log(monkeypatch)

    result = validator.validate_reply(
        "Capital Hilton payment failed at the gateway.",
        "The Capital Hilton payment is pending.",
        "system_report",
    )

    assert "Validation blocked" in result
    assert "severity_softening_detected: failed→pending" in result
    assert log_entries == [
        ("system_report", "severity_softening_detected: failed→pending", "Blocked softened severity output")
    ]


def test_severity_failed_kept_exact_passes(monkeypatch):
    log_entries = _captured_log(monkeypatch)

    result = validator.validate_reply(
        "Capital Hilton payment failed at the gateway.",
        "Capital Hilton payment failed; blocked at gateway.",
        "system_report",
    )

    assert result == "Capital Hilton payment failed; blocked at gateway."
    assert log_entries == []


def test_security_risk_with_softening_phrase_is_blocked(monkeypatch):
    log_entries = _captured_log(monkeypatch)

    result = validator.validate_reply(
        "There is a security risk in the route.",
        "There is a soft risk ahead.",
        "system_report",
    )

    assert "Validation blocked" in result
    assert "severity_softening_detected: risk→soft" in result
    assert log_entries == [
        ("system_report", "severity_softening_detected: risk→soft", "Blocked softened severity output")
    ]


def test_calm_denial_wording_that_preserves_denied_state_passes(monkeypatch):
    log_entries = _captured_log(monkeypatch)

    result = validator.validate_reply(
        "The send request was denied by policy.",
        "The system correctly denies that send request by policy.",
        "system_report",
    )

    assert result == "The system correctly denies that send request by policy."
    assert log_entries == []


def test_validator_retry_uses_adaptive_model_call(monkeypatch):
    calls = []

    def fake_adaptive(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return "retry ok"

    assert validator.ollama_call is validator.adaptive_ollama_text
    monkeypatch.setattr(validator, "ollama_call", fake_adaptive)

    assert validator._retry_once("Original prompt", timeout=37) == "retry ok"
    assert calls == [
        (
            "Your previous response was empty or unusable. Please try again and respond to this:\n\nOriginal prompt",
            {"timeout": 37},
        )
    ]


def test_content_recommendation_uses_adaptive_model_call(monkeypatch):
    import chief_content_brain as content

    calls = []

    def fake_adaptive(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return "Post the teaser first on Instagram."

    assert content.ollama_call is content.adaptive_ollama_text
    monkeypatch.setattr(content, "ollama_call", fake_adaptive)

    result = content._get_recommendation(
        [{"platform": "Instagram", "title": "Studio teaser", "size": "short"}],
        ["TikTok (0/3 this week)"],
    )

    assert result == "Post the teaser first on Instagram."
    assert calls
    assert calls[0][1] == {"timeout": 20, "task_class": "chief_structured_plan"}


def test_email_draft_uses_adaptive_model_call_with_strong_lane(monkeypatch):
    import chief_email_brain as email

    calls = []

    def fake_adaptive(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return "Subject: Checking in\n\nHi Dana,\n\nBody copy."

    assert email.ollama_call is email.adaptive_ollama_text
    monkeypatch.setattr(email, "ollama_call", fake_adaptive)

    subject, body = email._draft_email("Dana", "the invoice", "context", "follow-up")

    assert subject == "Checking in"
    assert body == "Hi Dana,\n\nBody copy."
    assert calls
    assert calls[0][1] == {"timeout": 30, "lane": "strong"}
