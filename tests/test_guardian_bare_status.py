"""Tests for the Guardian bare-status doctrine (task 143, CLASS #4).

Live evidence (pass-1): Guardian's approval_status matcher required "approval"/"approve" to
co-occur with "open"/"pending"/"waiting"/"status" -- a bare "status?" alone fell through to
the generic clarification reply. Separately, _approval_status_reply was hardcoded to always
claim "No pending approval requests." regardless of actual state. These tests pin both fixes.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chief_approval_brain
from chief_nonapproval_responder import (
    classify_nonapproval_prompt,
    guardian_no_pending_reply,
    looks_like_approval_status_query,
)


class TestLooksLikeApprovalStatusQuery:
    def test_bare_word_matches(self):
        assert looks_like_approval_status_query("status") is True

    def test_bare_word_with_question_mark_matches(self):
        assert looks_like_approval_status_query("status?") is True

    def test_existing_explicit_phrase_still_matches(self):
        assert looks_like_approval_status_query("what are my open approvals?") is True

    def test_unrelated_text_does_not_match(self):
        assert looks_like_approval_status_query("send an email to Bob") is False


class TestClassifyNonapprovalPromptBareStatus:
    def test_bare_status_classifies_as_approval_status(self):
        assert classify_nonapproval_prompt("status?") == "approval_status"


class TestApprovalStatusReplyIsLive:
    def test_no_pending_reports_zero(self, monkeypatch):
        monkeypatch.setattr(chief_approval_brain, "has_pending_approval", lambda: False)

        reply = guardian_no_pending_reply("status?")

        assert reply == "No pending approval requests."

    def test_pending_approval_reports_truthfully_not_hardcoded_zero(self, monkeypatch):
        """The exact live bug: this used to say 'No pending approval requests.' even when
        one genuinely existed."""
        monkeypatch.setattr(chief_approval_brain, "has_pending_approval", lambda: True)
        monkeypatch.setattr(chief_approval_brain, "get_pending_info", lambda: ("D36B21F7", {}))

        reply = guardian_no_pending_reply("status?")

        assert "No pending approval requests" not in reply
        assert "1 pending approval request" in reply
        assert "D36B21F7" in reply

    def test_approval_brain_failure_does_not_falsely_claim_zero(self, monkeypatch):
        def _boom():
            raise RuntimeError("approval brain unavailable")

        monkeypatch.setattr(chief_approval_brain, "has_pending_approval", _boom)

        reply = guardian_no_pending_reply("status?")

        assert "No pending approval requests" not in reply
        assert "unavailable" in reply.lower()

    def test_explicit_phrase_also_uses_live_state(self, monkeypatch):
        """Not just the new bare-status path -- the existing explicit phrasing was
        equally hardcoded and is fixed by the same change."""
        monkeypatch.setattr(chief_approval_brain, "has_pending_approval", lambda: True)
        monkeypatch.setattr(chief_approval_brain, "get_pending_info", lambda: ("ABCD1234", {}))

        reply = guardian_no_pending_reply("what are my open approvals?")

        assert "1 pending approval request" in reply
