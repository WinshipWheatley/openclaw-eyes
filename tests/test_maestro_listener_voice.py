"""Maestro listener fires a Kokoro voice note on its reply (operator-reported
2026-07-02: Maestro replies had no voice while other agents did).

The send itself is fire-and-forget + fail-soft; these tests pin the wiring and
the safety invariants without hitting Telegram."""

import importlib

import maestro_listener as ml


def test_helper_exists_and_is_failsoft(monkeypatch):
    assert hasattr(ml, "_fire_maestro_voice")
    # No event loop / no token available -> must NOT raise.
    ml._fire_maestro_voice("hello", 12345)  # should swallow any error


def test_voice_toggle_off_short_circuits(monkeypatch):
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("should not synth when toggle off")

    import agent_voice_sender
    monkeypatch.setattr(agent_voice_sender, "send_agent_voice_note", boom, raising=False)
    monkeypatch.setenv("OPENCLAW_AGENT_VOICE_NOTES", "0")
    ml._fire_maestro_voice("hello", 1)
    assert called["n"] == 0


def test_empty_reply_is_not_voiced(monkeypatch):
    called = {"n": 0}
    import agent_voice_sender
    monkeypatch.setattr(agent_voice_sender, "send_agent_voice_note",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1), raising=False)
    monkeypatch.setenv("OPENCLAW_AGENT_VOICE_NOTES", "1")
    ml._fire_maestro_voice("   ", 1)
    assert called["n"] == 0


def test_reply_path_source_calls_voice():
    # The success + photo reply sites must reference the voice fire (guards against a
    # future refactor silently dropping Maestro's voice again).
    import inspect
    src = inspect.getsource(ml.handle_message)
    assert "_fire_maestro_voice" in src
