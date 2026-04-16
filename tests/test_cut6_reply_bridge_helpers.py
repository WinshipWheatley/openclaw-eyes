"""
test_cut6_reply_bridge_helpers.py

Focused tests for Cut 6: reply-bridge orchestration helpers moved to
cassandra_outreach.py, plus thin-wrapper smoke tests in cassandra_brain.py.
"""

import json
import sys
import os
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── _detect_inner_circle_email_reply_intent ──────────────────────────────────

class TestDetectInnerCircleEmailReplyIntent:
    def test_matches_check_inner_circle(self):
        from cassandra_outreach import _detect_inner_circle_email_reply_intent
        assert _detect_inner_circle_email_reply_intent("check inner circle email replies") is True

    def test_matches_hyphenated(self):
        from cassandra_outreach import _detect_inner_circle_email_reply_intent
        assert _detect_inner_circle_email_reply_intent("show inner-circle email replies") is True

    def test_matches_check_email_replies_from(self):
        from cassandra_outreach import _detect_inner_circle_email_reply_intent
        assert _detect_inner_circle_email_reply_intent("check email replies from Dad") is True

    def test_case_insensitive(self):
        from cassandra_outreach import _detect_inner_circle_email_reply_intent
        assert _detect_inner_circle_email_reply_intent("CHECK INNER CIRCLE EMAIL REPLIES") is True

    def test_no_match(self):
        from cassandra_outreach import _detect_inner_circle_email_reply_intent
        assert _detect_inner_circle_email_reply_intent("send an email to Bob") is False

    def test_empty(self):
        from cassandra_outreach import _detect_inner_circle_email_reply_intent
        assert _detect_inner_circle_email_reply_intent("") is False


# ── _email_bridge_message_seen ───────────────────────────────────────────────

class TestEmailBridgeMessageSeen:
    def test_missing_log_returns_false(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", tmp_path / "nope.jsonl")
        assert outreach._email_bridge_message_seen("m1") is False

    def test_empty_message_id_returns_false(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", tmp_path / "nope.jsonl")
        assert outreach._email_bridge_message_seen("") is False

    def test_found_returns_true(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        log = tmp_path / "bridge.jsonl"
        log.write_text(json.dumps({"message_id": "m1"}) + "\n", encoding="utf-8")
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", log)
        assert outreach._email_bridge_message_seen("m1") is True

    def test_not_found_returns_false(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        log = tmp_path / "bridge.jsonl"
        log.write_text(json.dumps({"message_id": "m1"}) + "\n", encoding="utf-8")
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", log)
        assert outreach._email_bridge_message_seen("m999") is False


# ── _log_email_bridge_event ──────────────────────────────────────────────────

class TestLogEmailBridgeEvent:
    def _call_log(self, outreach, **overrides):
        defaults = dict(
            message_id="m1",
            thread_id="t1",
            nickname="dad",
            contact_name="Dad",
            sender_email="dad@example.com",
            subject="Hello",
            preview="Preview text here",
            lane="allowed",
            status="processed",
            unread=True,
        )
        defaults.update(overrides)
        outreach._log_email_bridge_event(**defaults)

    def test_writes_entry(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        log = tmp_path / "bridge.jsonl"
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", log)
        self._call_log(outreach)
        lines = log.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["message_id"] == "m1"
        assert entry["nickname"] == "dad"
        assert entry["route"] == "inner_circle_email_reply"

    def test_dedupe_skips_seen(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        log = tmp_path / "bridge.jsonl"
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", log)
        self._call_log(outreach, message_id="m1")
        self._call_log(outreach, message_id="m1")
        lines = log.read_text().strip().splitlines()
        assert len(lines) == 1

    def test_dedupe_false_allows_duplicate(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        log = tmp_path / "bridge.jsonl"
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", log)
        self._call_log(outreach, message_id="m1")
        self._call_log(outreach, message_id="m1", dedupe=False)
        lines = log.read_text().strip().splitlines()
        assert len(lines) == 2


# ── _predict_likely_next_questions ───────────────────────────────────────────

class TestPredictLikelyNextQuestions:
    def test_no_finance_bundles_returns_empty(self, monkeypatch):
        import cassandra_outreach as outreach
        bundles = [{"question": "What color is the sky?", "bundle_id": "q1"}]
        assert outreach._predict_likely_next_questions(bundles) == []

    def test_finance_bundle_with_next_step(self, monkeypatch):
        import cassandra_outreach as outreach
        monkeypatch.setattr(outreach, "get_finance_status_answer",
                            lambda q: "Payment received. Next: Send invoice to client.")
        bundles = [{"question": "Did the payment clear?", "bundle_id": "q1"}]
        result = outreach._predict_likely_next_questions(bundles)
        assert len(result) == 1
        assert result[0]["question"] == "What needs to happen next?"
        assert "Send invoice" in result[0]["because"]
        assert result[0]["bundle_id"] == "q1"

    def test_finance_bundle_no_next_returns_empty(self, monkeypatch):
        import cassandra_outreach as outreach
        monkeypatch.setattr(outreach, "get_finance_status_answer",
                            lambda q: "Payment received. All done.")
        bundles = [{"question": "Did the deposit land?", "bundle_id": "q1"}]
        assert outreach._predict_likely_next_questions(bundles) == []

    def test_empty_bundles(self):
        from cassandra_outreach import _predict_likely_next_questions
        assert _predict_likely_next_questions([]) == []


# ── Brain thin-wrapper smoke tests ──────────────────────────────────────────

class TestBrainCut6WrapperSmoke:
    def test_brain_detect_inner_circle_email_reply_intent(self):
        import cassandra_brain as brain
        assert brain._detect_inner_circle_email_reply_intent("check inner circle email replies") is True
        assert brain._detect_inner_circle_email_reply_intent("unrelated text") is False

    def test_brain_log_email_bridge_event(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        import cassandra_brain as brain
        log = tmp_path / "bridge.jsonl"
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", log)
        brain._log_email_bridge_event(
            message_id="m1",
            thread_id="t1",
            nickname="dad",
            contact_name="Dad",
            sender_email="dad@example.com",
            subject="Hello",
            preview="Preview",
            lane="allowed",
            status="processed",
            unread=True,
        )
        assert log.exists()
        entry = json.loads(log.read_text().strip())
        assert entry["message_id"] == "m1"

    def test_brain_predict_likely_next_questions(self, monkeypatch):
        import cassandra_outreach as outreach
        import cassandra_brain as brain
        monkeypatch.setattr(outreach, "get_finance_status_answer",
                            lambda q: "Deposit posted. Next: Confirm with client.")
        bundles = [{"question": "Did the deposit arrive?", "bundle_id": "q1"}]
        result = brain._predict_likely_next_questions(bundles)
        assert len(result) == 1
        assert result[0]["question"] == "What needs to happen next?"
