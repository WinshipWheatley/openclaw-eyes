"""Tests for the Chief bare-status doctrine (task 143, CLASS #4).

Live evidence (pass-1): "status?" got "no specific operational response" from Chief --
looks_like_inspection/scheduler_intent both require multi-word phrases a bare "status?"
lacks, so it fell through to _chief_fallback_reply's LLM call. These tests pin the fix: a
bare status ask is answered deterministically (no model call) with services health +
builds/approvals pending, and stale sources are flagged rather than presented as current.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chief_router


class _GuardMustNotPass(Exception):
    pass


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _seed_fresh_read_models(tmp_path: Path) -> None:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "agent_presence.json",
        {"generated_at": "2026-07-09T14:54:32+00:00", "online_count": 4, "agent_count": 6},
    )
    _write_json(
        root / "chief_status_rail.json",
        {"generated_at": "2026-07-08T00:00:00+00:00", "chief_current_status": "safe_status_read_model_only"},
    )
    _write_json(
        root / "work_board.json",
        {"generated_at": "2026-07-07T15:40:07+00:00", "pending_approval_count": 1, "needs_review_count": 34},
    )


class TestIsBareStatusQuery:
    def test_bare_word_matches(self):
        assert chief_router._is_bare_status_query("status") is True

    def test_bare_word_with_question_mark_matches(self):
        assert chief_router._is_bare_status_query("status?") is True

    def test_inspection_phrase_does_not_match(self):
        """Distinct from looks_like_inspection's richer multi-word matcher."""
        assert chief_router._is_bare_status_query("what's running on the system") is False

    def test_unrelated_text_does_not_match(self):
        assert chief_router._is_bare_status_query("prepare the St Anne's invoice") is False


class TestBuildChiefBareStatusAnswer:
    def test_all_fresh_sources_produce_three_lines(self, tmp_path, monkeypatch):
        _seed_fresh_read_models(tmp_path)
        monkeypatch.chdir(tmp_path)

        answer = chief_router.build_chief_bare_status_answer()

        assert "Services: 4/6 agents online." in answer
        assert "Rail: safe_status_read_model_only." in answer
        assert "Builds: 1 pending approval, 34 need review." in answer
        assert "(stale" not in answer

    def test_stale_rail_is_excluded_and_flagged(self, tmp_path, monkeypatch):
        _seed_fresh_read_models(tmp_path)
        _write_json(
            tmp_path / "generated" / "read_models" / "chief_status_rail.json",
            {"generated_at": "2026-05-19T00:30:34+00:00", "chief_current_status": "safe_status_read_model_only"},
        )
        monkeypatch.chdir(tmp_path)

        answer = chief_router.build_chief_bare_status_answer()

        assert "Rail:" not in answer
        assert "Services: 4/6 agents online." in answer
        assert "chief_status_rail.json" in answer

    def test_missing_read_models_produces_honest_no_data_answer(self, tmp_path, monkeypatch):
        (tmp_path / "generated" / "read_models").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        answer = chief_router.build_chief_bare_status_answer()

        assert "don't have current status data" in answer


class TestRouteMessageBareStatus:
    def test_bare_status_answered_before_approval_gate(self, tmp_path, monkeypatch):
        _seed_fresh_read_models(tmp_path)
        monkeypatch.chdir(tmp_path)

        def _sentinel():
            raise _GuardMustNotPass("must not reach the approval gate for a bare status ask")

        monkeypatch.setattr(chief_router, "has_pending_approval", _sentinel)

        result = chief_router._route_message_inner("status?")

        assert result["intent"] == "chief_bare_status_readback"
        assert "Services: 4/6 agents online." in result["reply"]

    def test_non_status_message_still_reaches_approval_gate(self, tmp_path, monkeypatch):
        """Sanity check: the new tap must not swallow unrelated routing."""
        _seed_fresh_read_models(tmp_path)
        monkeypatch.chdir(tmp_path)

        def _sentinel():
            raise _GuardMustNotPass("reached normal routing")

        monkeypatch.setattr(chief_router, "has_pending_approval", _sentinel)

        import pytest

        with pytest.raises(_GuardMustNotPass):
            chief_router._route_message_inner("prepare the St Anne's invoice for my review")
