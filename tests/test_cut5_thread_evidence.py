"""
test_cut5_thread_evidence.py

Focused tests for Cut 5: email-thread evidence helpers moved to cassandra_outreach.py,
plus thin-wrapper smoke tests in cassandra_brain.py.
"""

import json
import sys
import os
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── _bridge_preview ──────────────────────────────────────────────────────────

class TestBridgePreview:
    def test_short_text_unchanged(self):
        from cassandra_outreach import _bridge_preview
        assert _bridge_preview("hello world", limit=140) == "hello world"

    def test_long_text_truncated_with_ellipsis(self):
        from cassandra_outreach import _bridge_preview
        result = _bridge_preview("a" * 200, limit=140)
        assert len(result) <= 140
        assert result.endswith("\u2026")

    def test_whitespace_collapsed(self):
        from cassandra_outreach import _bridge_preview
        assert _bridge_preview("hello   \n  world") == "hello world"

    def test_empty_input(self):
        from cassandra_outreach import _bridge_preview
        assert _bridge_preview("") == ""
        assert _bridge_preview(None) == ""


# ── _parse_event_datetime ────────────────────────────────────────────────────

class TestParseEventDatetime:
    def test_iso_string(self):
        from cassandra_outreach import _parse_event_datetime
        result = _parse_event_datetime("2026-04-15T10:30:00")
        assert result == datetime(2026, 4, 15, 10, 30, 0)

    def test_unix_timestamp_int(self):
        from cassandra_outreach import _parse_event_datetime
        result = _parse_event_datetime(1000000000)
        assert isinstance(result, datetime)

    def test_unix_millis_string(self):
        from cassandra_outreach import _parse_event_datetime
        result = _parse_event_datetime("1700000000000")
        assert isinstance(result, datetime)

    def test_fallback_on_empty(self):
        from cassandra_outreach import _parse_event_datetime
        fallback = datetime(2026, 1, 1)
        assert _parse_event_datetime("", fallback) == fallback
        assert _parse_event_datetime(None, fallback) == fallback

    def test_no_fallback_returns_now(self):
        from cassandra_outreach import _parse_event_datetime
        before = datetime.now()
        result = _parse_event_datetime("")
        after = datetime.now()
        assert before <= result <= after


# ── _significant_terms ───────────────────────────────────────────────────────

class TestSignificantTerms:
    def test_filters_stopwords(self):
        from cassandra_outreach import _significant_terms
        terms = _significant_terms("the quick brown fox is on the mat")
        assert "the" not in terms
        assert "quick" in terms
        assert "brown" in terms
        assert "fox" in terms

    def test_short_tokens_excluded(self):
        from cassandra_outreach import _significant_terms
        terms = _significant_terms("go to my car")
        assert "go" not in terms
        assert "to" not in terms
        assert "my" not in terms
        assert "car" in terms


# ── _question_key ────────────────────────────────────────────────────────────

class TestQuestionKey:
    def test_normalizes_to_lowercase_alphanumeric(self):
        from cassandra_outreach import _question_key
        assert _question_key("What is the STATUS?") == "what is the status"

    def test_empty_input(self):
        from cassandra_outreach import _question_key
        assert _question_key("") == ""
        assert _question_key(None) == ""


# ── _extract_question_candidates ─────────────────────────────────────────────

class TestExtractQuestionCandidates:
    def test_extracts_question_marks(self):
        from cassandra_outreach import _extract_question_candidates
        result = _extract_question_candidates("Hello. What time is it? Where are you?")
        assert any("time" in q.lower() for q in result)
        assert any("where" in q.lower() for q in result)

    def test_request_prefixes_as_fallback(self):
        from cassandra_outreach import _extract_question_candidates
        result = _extract_question_candidates("Can you check if the payment landed.")
        assert len(result) >= 1
        assert "check" in result[0].lower()

    def test_empty_input(self):
        from cassandra_outreach import _extract_question_candidates
        assert _extract_question_candidates("") == []

    def test_max_five_candidates(self):
        from cassandra_outreach import _extract_question_candidates
        text = " ".join(f"Question {i}?" for i in range(20))
        result = _extract_question_candidates(text)
        assert len(result) <= 5


# ── _fetch_email_thread_messages ─────────────────────────────────────────────

class TestFetchEmailThreadMessages:
    def test_success_returns_messages(self, monkeypatch):
        import cassandra_outreach as outreach
        monkeypatch.setattr(outreach, "broker_call", lambda *a, **kw: {
            "ok": True,
            "data": {"messages": [{"message_id": "m1", "body_text": "hi"}]},
        })
        messages, source = outreach._fetch_email_thread_messages({"thread_id": "t1", "message_id": "m1"})
        assert source == "gmail.read.body"
        assert len(messages) == 1

    def test_failure_falls_back(self, monkeypatch):
        import cassandra_outreach as outreach
        monkeypatch.setattr(outreach, "broker_call", lambda *a, **kw: {"ok": False})
        messages, source = outreach._fetch_email_thread_messages({"thread_id": "t1", "snippet": "preview"})
        assert source == "gmail.read.metadata"
        assert len(messages) == 1
        assert messages[0].get("body_text") == ""


# ── _message_evidence_rows ───────────────────────────────────────────────────

class TestMessageEvidenceRows:
    def test_direction_classification(self):
        from cassandra_outreach import _message_evidence_rows
        thread = [
            {"from_email": "bob@x.com", "date_raw": "2026-04-15T10:00:00", "message_id": "m1", "snippet": "hi"},
            {"from_email": "me@x.com", "date_raw": "2026-04-15T11:00:00", "message_id": "m2", "snippet": "reply"},
        ]
        rows = _message_evidence_rows(thread, "bob@x.com")
        assert rows[0]["direction"] == "inbound"
        assert rows[1]["direction"] == "outbound_or_other"

    def test_sorted_by_date(self):
        from cassandra_outreach import _message_evidence_rows
        thread = [
            {"from_email": "a@x.com", "date_raw": "2026-04-15T12:00:00", "message_id": "m2"},
            {"from_email": "a@x.com", "date_raw": "2026-04-15T10:00:00", "message_id": "m1"},
        ]
        rows = _message_evidence_rows(thread, "a@x.com")
        assert rows[0]["message_id"] == "m1"
        assert rows[1]["message_id"] == "m2"


# ── _bundle_answered_in_thread ───────────────────────────────────────────────

class TestBundleAnsweredInThread:
    def test_answered_when_terms_overlap(self):
        from cassandra_outreach import _bundle_answered_in_thread
        bundle = {"question": "What about the payment status?", "last_asked_at": "2026-04-10T10:00:00"}
        thread = [
            {"from_email": "me@x.com", "internal_date": "2026-04-11T10:00:00",
             "body_text": "The payment status is confirmed and posted."},
        ]
        assert _bundle_answered_in_thread(bundle, thread, "them@x.com") is True

    def test_not_answered_when_same_sender(self):
        from cassandra_outreach import _bundle_answered_in_thread
        bundle = {"question": "What about the payment status?", "last_asked_at": "2026-04-10T10:00:00"}
        thread = [
            {"from_email": "them@x.com", "internal_date": "2026-04-11T10:00:00",
             "body_text": "The payment status is confirmed."},
        ]
        assert _bundle_answered_in_thread(bundle, thread, "them@x.com") is False

    def test_not_answered_before_asked(self):
        from cassandra_outreach import _bundle_answered_in_thread
        bundle = {"question": "What about the payment status?", "last_asked_at": "2026-04-10T10:00:00"}
        thread = [
            {"from_email": "me@x.com", "internal_date": "2026-04-09T10:00:00",
             "body_text": "The payment status is confirmed."},
        ]
        assert _bundle_answered_in_thread(bundle, thread, "them@x.com") is False


# ── _is_reply_like_email_message ─────────────────────────────────────────────

class TestIsReplyLikeEmailMessage:
    def test_re_prefix(self):
        from cassandra_outreach import _is_reply_like_email_message
        assert _is_reply_like_email_message({"subject": "Re: Hello"}) is True

    def test_in_reply_to_header(self):
        from cassandra_outreach import _is_reply_like_email_message
        assert _is_reply_like_email_message({"subject": "Hello", "in_reply_to": "<abc@x>"}) is True

    def test_not_reply(self):
        from cassandra_outreach import _is_reply_like_email_message
        assert _is_reply_like_email_message({"subject": "Hello"}) is False


# ── _build_email_bridge_review_text ──────────────────────────────────────────

class TestBuildEmailBridgeReviewText:
    def test_combines_subject_and_snippet(self):
        from cassandra_outreach import _build_email_bridge_review_text
        result = _build_email_bridge_review_text({"subject": "Test Subject", "snippet": "Preview text"})
        assert "Test Subject" in result
        assert "Preview text" in result


# ── _advance_email_thread_cadence ────────────────────────────────────────────

class TestAdvanceEmailThreadCadence:
    def test_resolved_when_no_unresolved(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        state_path = tmp_path / "state.json"
        state_path.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(outreach, "_EMAIL_THREAD_STATE", state_path)
        result = outreach._advance_email_thread_cadence(
            thread_id="t1",
            contact_name="Bob",
            unresolved_bundles=[],
            predictions=[],
        )
        assert result["status"] == "resolved"

    def test_waiting_when_before_followup_window(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        state_path = tmp_path / "state.json"
        state_path.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(outreach, "_EMAIL_THREAD_STATE", state_path)
        now = datetime(2026, 4, 15, 12, 0, 0)
        bundles = [{"question": "Test?", "last_asked_at": now.isoformat(), "status": "answer_now"}]
        result = outreach._advance_email_thread_cadence(
            thread_id="t1",
            contact_name="Bob",
            unresolved_bundles=bundles,
            predictions=[],
            now=now,
        )
        assert result["status"] == "waiting"

    def test_followup_due_after_window(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        state_path = tmp_path / "state.json"
        state_path.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(outreach, "_EMAIL_THREAD_STATE", state_path)
        asked = datetime(2026, 4, 1, 12, 0, 0)
        now = datetime(2026, 4, 15, 12, 0, 0)
        bundles = [{"question": "Test?", "last_asked_at": asked.isoformat(), "status": "answer_now"}]
        result = outreach._advance_email_thread_cadence(
            thread_id="t1",
            contact_name="Bob",
            unresolved_bundles=bundles,
            predictions=[],
            now=now,
        )
        assert result["status"] == "followup_due"


# ── _log_email_thread_analysis ───────────────────────────────────────────────

class TestLogEmailThreadAnalysis:
    def test_writes_jsonl(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        log_path = tmp_path / "analysis.jsonl"
        monkeypatch.setattr(outreach, "_EMAIL_THREAD_ANALYSIS_LOG", log_path)
        outreach._log_email_thread_analysis({"ts": "2026-04-15", "thread_id": "t1"})
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["thread_id"] == "t1"


# ── Brain thin-wrapper smoke tests ──────────────────────────────────────────

class TestBrainCut5WrapperSmoke:
    def test_brain_bridge_preview(self):
        import cassandra_brain as brain
        assert brain._bridge_preview("hello world") == "hello world"

    def test_brain_parse_event_datetime(self):
        import cassandra_brain as brain
        result = brain._parse_event_datetime("2026-04-15T10:30:00")
        assert result == datetime(2026, 4, 15, 10, 30, 0)

    def test_brain_question_key(self):
        import cassandra_brain as brain
        assert brain._question_key("Hello World!") == "hello world"

    def test_brain_extract_question_candidates(self):
        import cassandra_brain as brain
        result = brain._extract_question_candidates("Where is the file?")
        assert len(result) >= 1

    def test_brain_is_reply_like(self):
        import cassandra_brain as brain
        assert brain._is_reply_like_email_message({"subject": "Re: Test"}) is True

    def test_brain_build_email_bridge_review_text(self):
        import cassandra_brain as brain
        result = brain._build_email_bridge_review_text({"subject": "Hi", "snippet": "body"})
        assert "Hi" in result

    def test_brain_fetch_email_thread_messages_fallback(self, monkeypatch):
        import cassandra_outreach as outreach
        monkeypatch.setattr(outreach, "broker_call", lambda *a, **kw: {"ok": False})
        import cassandra_brain as brain
        messages, source = brain._fetch_email_thread_messages({"thread_id": "t1"})
        assert source == "gmail.read.metadata"

    def test_brain_advance_email_thread_cadence(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        import cassandra_brain as brain
        state_path = tmp_path / "state.json"
        state_path.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(outreach, "_EMAIL_THREAD_STATE", state_path)
        result = brain._advance_email_thread_cadence(
            thread_id="t1",
            contact_name="Bob",
            unresolved_bundles=[],
            predictions=[],
        )
        assert result["status"] == "resolved"

    def test_brain_log_email_thread_analysis(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        import cassandra_brain as brain
        log_path = tmp_path / "analysis.jsonl"
        monkeypatch.setattr(outreach, "_EMAIL_THREAD_ANALYSIS_LOG", log_path)
        brain._log_email_thread_analysis({"ts": "2026-04-15", "thread_id": "t1"})
        assert log_path.exists()
