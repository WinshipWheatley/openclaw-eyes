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
