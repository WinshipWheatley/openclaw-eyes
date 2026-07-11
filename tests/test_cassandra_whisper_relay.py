"""
Tests for cassandra_whisper_relay.

Covers:
  - Low-confidence hard reject
  - Duplicate suppression within window
  - Accepted relay calls cassandra_brain.handle
  - Flagged (marginal confidence) passes through but marks status
  - Empty transcript rejected before confidence check
"""

import time
import types


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_module(monkeypatch, tmp_path, handle_side_effect=None):
    """Import relay with cassandra_brain.handle stubbed out."""
    import cassandra_whisper_relay as relay

    # Reset dedup cache between tests.
    import threading
    relay._dedup_cache.clear()
    relay._dedup_lock = threading.Lock()

    # Redirect log writes to tmp_path so tests don't touch the real log.
    monkeypatch.setattr(relay, "_RELAY_LOG", tmp_path / "whisper_relay.jsonl", raising=True)

    calls = []

    def _fake_handle(text, session):
        calls.append({"text": text, "session": session})
        if handle_side_effect is not None:
            raise handle_side_effect
        return [f"Echo: {text}"]

    # Patch cassandra_brain inside the relay module's namespace.
    fake_brain = types.ModuleType("cassandra_brain")
    fake_brain.handle = _fake_handle
    monkeypatch.setattr(relay, "cassandra_handle", _fake_handle, raising=False)

    # Monkey-patch at import level so relay_transcript uses our stub.
    import importlib
    original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else None

    return relay, calls


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_rejected_below_confidence_min(monkeypatch, tmp_path):
    import cassandra_whisper_relay as relay
    relay._dedup_cache.clear()
    monkeypatch.setattr(relay, "_RELAY_LOG", tmp_path / "log.jsonl")

    calls = []
    monkeypatch.setattr(relay, "CONFIDENCE_MIN", 0.60)

    # Stub cassandra_brain.handle so it never gets called.
    import types
    fake_brain = types.SimpleNamespace(handle=lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not reach brain")))
    monkeypatch.setattr("cassandra_whisper_relay.cassandra_handle", fake_brain.handle, raising=False)

    result = relay.relay_transcript("set priority alpha", confidence=0.40)

    assert result["status"] == "rejected"
    assert "confidence_below_min" in result["reason"]
    assert result["reply"] == []


def test_accepted_above_confidence_min(monkeypatch, tmp_path):
    import cassandra_whisper_relay as relay
    relay._dedup_cache.clear()
    monkeypatch.setattr(relay, "_RELAY_LOG", tmp_path / "log.jsonl")
    monkeypatch.setattr(relay, "CONFIDENCE_MIN", 0.60)
    monkeypatch.setattr(relay, "CONFIDENCE_FLAG_BELOW", 0.75)

    captured = []

    def _fake_handle(text, session):
        captured.append(text)
        return ["Done."]

    monkeypatch.setattr(relay, "cassandra_handle", _fake_handle)

    result = relay.relay_transcript("set priority alpha", confidence=0.85)

    assert result["status"] == "accepted"
    assert result["reply"] == ["Done."]
    assert captured == ["set priority alpha"]


def test_flagged_between_min_and_flag_threshold(monkeypatch, tmp_path):
    import cassandra_whisper_relay as relay
    relay._dedup_cache.clear()
    monkeypatch.setattr(relay, "_RELAY_LOG", tmp_path / "log.jsonl")
    monkeypatch.setattr(relay, "CONFIDENCE_MIN", 0.60)
    monkeypatch.setattr(relay, "CONFIDENCE_FLAG_BELOW", 0.75)

    monkeypatch.setattr(relay, "cassandra_handle", lambda t, s: ["Flagged reply."])

    result = relay.relay_transcript("remind me about the meeting", confidence=0.68)

    assert result["status"] == "flagged"
    assert "low_confidence_flagged" in result["reason"]
    assert result["reply"] == ["Flagged reply."]


def test_duplicate_suppressed_within_window(monkeypatch, tmp_path):
    import cassandra_whisper_relay as relay
    relay._dedup_cache.clear()
    monkeypatch.setattr(relay, "_RELAY_LOG", tmp_path / "log.jsonl")
    monkeypatch.setattr(relay, "CONFIDENCE_MIN", 0.60)
    monkeypatch.setattr(relay, "CONFIDENCE_FLAG_BELOW", 0.75)
    monkeypatch.setattr(relay, "DEDUP_WINDOW_SECONDS", 60)

    call_count = [0]

    def _fake_handle(text, session):
        call_count[0] += 1
        return ["OK"]

    monkeypatch.setattr(relay, "cassandra_handle", _fake_handle)

    r1 = relay.relay_transcript("cancel the meeting", confidence=0.90)
    r2 = relay.relay_transcript("cancel the meeting", confidence=0.90)

    assert r1["status"] == "accepted"
    assert r2["status"] == "duplicate"
    assert call_count[0] == 1  # brain called only once


def test_duplicate_not_suppressed_after_window(monkeypatch, tmp_path):
    import cassandra_whisper_relay as relay
    relay._dedup_cache.clear()
    monkeypatch.setattr(relay, "_RELAY_LOG", tmp_path / "log.jsonl")
    monkeypatch.setattr(relay, "CONFIDENCE_MIN", 0.60)
    monkeypatch.setattr(relay, "CONFIDENCE_FLAG_BELOW", 0.75)
    monkeypatch.setattr(relay, "DEDUP_WINDOW_SECONDS", 1)

    call_count = [0]

    def _fake_handle(text, session):
        call_count[0] += 1
        return ["OK"]

    monkeypatch.setattr(relay, "cassandra_handle", _fake_handle)

    relay.relay_transcript("reschedule tomorrow", confidence=0.90)
    # Advance past the 1-second dedup window by patching monotonic
    original_time = relay.time.monotonic
    monkeypatch.setattr(relay.time, "monotonic", lambda: original_time() + 2)

    r2 = relay.relay_transcript("reschedule tomorrow", confidence=0.90)
    assert r2["status"] == "accepted"
    assert call_count[0] == 2


def test_empty_transcript_rejected(monkeypatch, tmp_path):
    import cassandra_whisper_relay as relay
    relay._dedup_cache.clear()
    monkeypatch.setattr(relay, "_RELAY_LOG", tmp_path / "log.jsonl")

    result = relay.relay_transcript("   ", confidence=0.99)

    assert result["status"] == "rejected"
    assert result["reason"] == "empty_transcript"


def test_session_metadata_forwarded_to_brain(monkeypatch, tmp_path):
    import cassandra_whisper_relay as relay
    relay._dedup_cache.clear()
    monkeypatch.setattr(relay, "_RELAY_LOG", tmp_path / "log.jsonl")
    monkeypatch.setattr(relay, "CONFIDENCE_MIN", 0.60)
    monkeypatch.setattr(relay, "CONFIDENCE_FLAG_BELOW", 0.75)

    received_sessions = []

    def _fake_handle(text, session):
        received_sessions.append(dict(session))
        return ["Ack."]

    monkeypatch.setattr(relay, "cassandra_handle", _fake_handle)

    relay.relay_transcript(
        "mark album done",
        confidence=0.92,
        event_id="test-001",
        session={"sender_name": "Winship"},
    )

    assert len(received_sessions) == 1
    s = received_sessions[0]
    assert s["source"] == "whisper_relay"
    assert s["whisper_event_id"] == "test-001"
    assert abs(s["whisper_confidence"] - 0.92) < 0.001
    assert s["sender_name"] == "Winship"


def test_destructive_transcript_refuses_before_brain_dedup_or_relay_log(monkeypatch, tmp_path):
    import cassandra_whisper_relay as relay

    relay._dedup_cache.clear()
    relay_log = tmp_path / "relay.jsonl"
    refusal_log = tmp_path / "refusals.jsonl"
    monkeypatch.setattr(relay, "_RELAY_LOG", relay_log)
    monkeypatch.setenv("OPENCLAW_REFUSAL_RECEIPT_PATH", str(refusal_log))
    monkeypatch.setattr(
        relay,
        "cassandra_handle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("brain ran before first-touch refusal")
        ),
    )

    result = relay.relay_transcript(
        "clear out all the old logs and branches, do it now",
        confidence=0.95,
        event_id="voice-162",
    )

    assert result["status"] == "refused"
    assert "Nothing was deleted" in result["reply"][0]
    assert relay._dedup_cache == {}
    assert not relay_log.exists()
    assert refusal_log.is_file()
