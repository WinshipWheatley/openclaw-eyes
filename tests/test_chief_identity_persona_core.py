"""Tests for Chief's identity-question wiring (task 145, CLASS #6).

Task 142 built is_identity_question/identity_persona_reply (protected_generate.py) and
wired them into maestro_cassandra_responder.answer_frontdoor_chat -- Chief's PROBE path,
not his REAL Telegram surface (chief_router.route_message). classify_nonapproval_prompt's
"capability" intent doesn't match literal "who are you" phrasing either, so the existing
canned-string bank was never reachable for this exact ask. These tests pin the new tap.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chief_router
import protected_generate as pg


class _GuardMustNotPass(Exception):
    pass


def test_who_are_you_answers_deterministically_before_approval_gate(monkeypatch):
    def _sentinel():
        raise _GuardMustNotPass("must not reach the approval gate for an identity ask")

    monkeypatch.setattr(chief_router, "has_pending_approval", _sentinel)

    result = chief_router._route_message_inner("who are you and what do you do for me?")

    assert result["intent"] == "identity_persona_core"
    assert result["reply"] == pg.identity_persona_reply("chief")


def test_identity_answer_mentions_chief_and_not_another_agents_domain():
    result = chief_router._route_message_inner("who are you and what do you do for me?")

    lowered = result["reply"].lower()
    assert "chief" in lowered
    for other_domain_term in ("song", "track", "x32", "rig", "clara", "invoice"):
        assert other_domain_term not in lowered


def test_non_identity_message_still_reaches_approval_gate(monkeypatch):
    """Sanity: the new tap must not swallow unrelated routing."""
    def _sentinel():
        raise _GuardMustNotPass("reached normal routing")

    monkeypatch.setattr(chief_router, "has_pending_approval", _sentinel)

    import pytest

    with pytest.raises(_GuardMustNotPass):
        chief_router._route_message_inner("prepare the St Anne's invoice for my review")
