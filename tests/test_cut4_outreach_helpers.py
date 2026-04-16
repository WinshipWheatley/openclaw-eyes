"""
test_cut4_outreach_helpers.py

Focused tests for Cut 4: _load_jsonl_records, _load_outbound_email_records,
_match_outbound_email_record (and supporting helpers) moved to cassandra_outreach.py,
plus thin-wrapper smoke tests in cassandra_brain.py.
"""

import json
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


# ── _load_jsonl_records ──────────────────────────────────────────────────────

class TestLoadJsonlRecords:
    def test_missing_file_returns_empty(self, tmp_path):
        from cassandra_outreach import _load_jsonl_records
        assert _load_jsonl_records(tmp_path / "nope.jsonl") == []

    def test_blank_lines_ignored(self, tmp_path):
        p = tmp_path / "data.jsonl"
        p.write_text('{"a":1}\n\n\n{"b":2}\n', encoding="utf-8")
        from cassandra_outreach import _load_jsonl_records
        assert _load_jsonl_records(p) == [{"a": 1}, {"b": 2}]

    def test_malformed_jsonl_no_crash(self, tmp_path):
        p = tmp_path / "bad.jsonl"
        p.write_text('{"ok":1}\nNOT_JSON\n', encoding="utf-8")
        from cassandra_outreach import _load_jsonl_records
        # Should not raise; may return partial results or empty
        result = _load_jsonl_records(p)
        assert isinstance(result, list)


# ── _load_outbound_email_records ─────────────────────────────────────────────

class TestLoadOutboundEmailRecords:
    def _patch_logs(self, monkeypatch, tmp_path, corr_records=None, outreach_records=None):
        import cassandra_outreach as outreach
        corr_path = tmp_path / "correspondence.jsonl"
        out_path = tmp_path / "outreach.jsonl"
        if corr_records is not None:
            _write_jsonl(corr_path, corr_records)
        if outreach_records is not None:
            _write_jsonl(out_path, outreach_records)
        monkeypatch.setattr(outreach, "_CORRESPONDENCE_LOG", corr_path)
        monkeypatch.setattr(outreach, "_OUTREACH_LOG", out_path)

    def test_only_allowed_states_included(self, tmp_path, monkeypatch):
        from cassandra_outreach import _load_outbound_email_records
        self._patch_logs(monkeypatch, tmp_path, corr_records=[
            {"state": "draft", "subject": "A", "ts": "1"},
            {"state": "queued", "subject": "B", "ts": "2"},
            {"state": "awaiting_approval", "subject": "C", "ts": "3"},
            {"state": "send_attempted", "subject": "D", "ts": "4"},
            {"state": "sent_confirmed", "subject": "E", "ts": "5"},
            {"state": "send_failed", "subject": "F", "ts": "6"},
            {"state": "blocked", "subject": "G", "ts": "7"},
            {"state": "garbage", "subject": "H", "ts": "8"},
        ])
        records = _load_outbound_email_records()
        states = {r["state"] for r in records}
        assert states == {"draft", "queued", "awaiting_approval", "send_attempted", "sent_confirmed"}
        assert len(records) == 5

    def test_subject_fallback_from_detail(self, tmp_path, monkeypatch):
        from cassandra_outreach import _load_outbound_email_records
        self._patch_logs(monkeypatch, tmp_path, corr_records=[
            {"state": "draft", "detail": "subject=Hello World; extra", "ts": "1"},
        ])
        records = _load_outbound_email_records()
        assert records[0]["subject"] == "Hello World"

    def test_recipient_email_fallback_from_detail(self, tmp_path, monkeypatch):
        from cassandra_outreach import _load_outbound_email_records
        self._patch_logs(monkeypatch, tmp_path, corr_records=[
            {"state": "draft", "subject": "X", "detail": "sent to alice@example.com ok", "ts": "1"},
        ])
        records = _load_outbound_email_records()
        assert records[0]["recipient_email"] == "alice@example.com"

    def test_subject_normalization_strips_prefixes(self, tmp_path, monkeypatch):
        from cassandra_outreach import _load_outbound_email_records
        self._patch_logs(monkeypatch, tmp_path, corr_records=[
            {"state": "draft", "subject": "Re: Fw: Fwd: Hello", "ts": "1"},
        ])
        records = _load_outbound_email_records()
        assert records[0]["subject_norm"] == "hello"

    def test_newest_first_sort_by_ts(self, tmp_path, monkeypatch):
        from cassandra_outreach import _load_outbound_email_records
        self._patch_logs(monkeypatch, tmp_path, corr_records=[
            {"state": "draft", "subject": "Old", "ts": "2026-01-01"},
            {"state": "draft", "subject": "New", "ts": "2026-04-15"},
            {"state": "draft", "subject": "Mid", "ts": "2026-02-10"},
        ])
        records = _load_outbound_email_records()
        subjects = [r["subject"] for r in records]
        assert subjects == ["New", "Mid", "Old"]


# ── _match_outbound_email_record ─────────────────────────────────────────────

class TestMatchOutboundEmailRecord:
    def _patch_logs(self, monkeypatch, tmp_path, corr_records=None, outreach_records=None):
        import cassandra_outreach as outreach
        corr_path = tmp_path / "correspondence.jsonl"
        out_path = tmp_path / "outreach.jsonl"
        if corr_records is not None:
            _write_jsonl(corr_path, corr_records)
        if outreach_records is not None:
            _write_jsonl(out_path, outreach_records)
        monkeypatch.setattr(outreach, "_CORRESPONDENCE_LOG", corr_path)
        monkeypatch.setattr(outreach, "_OUTREACH_LOG", out_path)

    def test_match_by_thread_id(self, tmp_path, monkeypatch):
        from cassandra_outreach import _match_outbound_email_record
        self._patch_logs(monkeypatch, tmp_path, corr_records=[
            {"state": "draft", "subject": "A", "ts": "1", "thread_id": "t123"},
        ])
        result = _match_outbound_email_record({"subject": "A", "thread_id": "t123"}, "someone@x.com")
        assert result is not None
        assert result["matched_via"] == "thread_id"

    def test_fallback_match_by_subject_and_recipient(self, tmp_path, monkeypatch):
        from cassandra_outreach import _match_outbound_email_record
        self._patch_logs(monkeypatch, tmp_path, corr_records=[
            {"state": "draft", "subject": "Re: Hello", "recipient_email": "bob@x.com", "ts": "1"},
        ])
        result = _match_outbound_email_record({"subject": "Re: Hello"}, "bob@x.com")
        assert result is not None
        assert result["matched_via"] == "subject+recipient"

    def test_no_match_returns_none(self, tmp_path, monkeypatch):
        from cassandra_outreach import _match_outbound_email_record
        self._patch_logs(monkeypatch, tmp_path, corr_records=[
            {"state": "draft", "subject": "Other", "recipient_email": "z@z.com", "ts": "1"},
        ])
        result = _match_outbound_email_record({"subject": "Nope"}, "nobody@x.com")
        assert result is None


# ── cassandra_brain.py thin-wrapper smoke tests ──────────────────────────────

class TestBrainWrapperSmoke:
    def test_brain_load_jsonl_records_delegates(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        import cassandra_brain as brain

        p = tmp_path / "data.jsonl"
        p.write_text('{"x":1}\n', encoding="utf-8")
        result = brain._load_jsonl_records(p)
        assert result == [{"x": 1}]

    def test_brain_load_outbound_email_records_delegates(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        import cassandra_brain as brain

        corr_path = tmp_path / "correspondence.jsonl"
        out_path = tmp_path / "outreach.jsonl"
        _write_jsonl(corr_path, [{"state": "draft", "subject": "Hi", "ts": "1"}])
        monkeypatch.setattr(outreach, "_CORRESPONDENCE_LOG", corr_path)
        monkeypatch.setattr(outreach, "_OUTREACH_LOG", out_path)
        records = brain._load_outbound_email_records()
        assert len(records) == 1
        assert records[0]["subject"] == "Hi"

    def test_brain_match_outbound_email_record_delegates(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        import cassandra_brain as brain

        corr_path = tmp_path / "correspondence.jsonl"
        out_path = tmp_path / "outreach.jsonl"
        _write_jsonl(corr_path, [
            {"state": "draft", "subject": "Test", "recipient_email": "a@b.com", "ts": "1"},
        ])
        monkeypatch.setattr(outreach, "_CORRESPONDENCE_LOG", corr_path)
        monkeypatch.setattr(outreach, "_OUTREACH_LOG", out_path)
        result = brain._match_outbound_email_record({"subject": "Test"}, "a@b.com")
        assert result is not None
        assert result["matched_via"] == "subject+recipient"
