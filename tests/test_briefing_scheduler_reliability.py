"""
tests/test_briefing_scheduler_reliability.py

Tests for cassandra_briefing_brain protected-window detection.

Covers:
  1. No protected window when all conditions are clear.
  2. focus_mode active → briefing blocked.
  3. Stale approval_pending.json (> 900s old) → NOT blocked.
  4. Fresh approval_pending.json (< 900s old) → blocked.
  5. Ignored-requester approval record → NOT blocked.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import cassandra_briefing_brain as bb


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_approval(
    tmp_path: Path,
    status: str = "pending",
    age_seconds: int = 0,
    requester: str = "loop_auto_heal",
) -> Path:
    """Write a synthetic approval_pending.json at the given age (seconds old)."""
    requested_at = (datetime.now() - timedelta(seconds=age_seconds)).isoformat(timespec="seconds")
    path = tmp_path / "approval_pending.json"
    path.write_text(
        json.dumps({
            "status": status,
            "requester": requester,
            "requested_at": requested_at,
        }),
        encoding="utf-8",
    )
    return path


def _clear_protected(tmp_path: Path, monkeypatch) -> None:
    """Patch all protected-window signals to inactive."""
    monkeypatch.setattr(bb, "is_focus_mode", lambda: False)
    monkeypatch.setattr(bb, "is_social_mode", lambda: False)
    monkeypatch.setattr(bb, "_SESSION_FILE", tmp_path / "no_session.json")
    monkeypatch.setattr(bb, "_SCHEDULER_STATE", tmp_path / "no_sched.json")
    monkeypatch.setattr(bb, "_APPROVAL_PENDING", tmp_path / "no_approval.json")


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_no_protected_window_when_all_clear(tmp_path, monkeypatch):
    """All signals inactive → protected_reason() returns None, is_protected_window() False."""
    _clear_protected(tmp_path, monkeypatch)

    assert bb.protected_reason() is None
    assert not bb.is_protected_window()


def test_focus_mode_blocks_briefing(tmp_path, monkeypatch):
    """focus_mode active → protected_reason() returns 'focus_mode'."""
    _clear_protected(tmp_path, monkeypatch)
    monkeypatch.setattr(bb, "is_focus_mode", lambda: True)

    reason = bb.protected_reason()
    assert reason == "focus_mode"
    assert bb.is_protected_window()


def test_stale_approval_does_not_block(tmp_path, monkeypatch):
    """approval_pending.json older than 900s must NOT block briefings."""
    _clear_protected(tmp_path, monkeypatch)
    stale_path = _write_approval(tmp_path, age_seconds=901)
    monkeypatch.setattr(bb, "_APPROVAL_PENDING", stale_path)

    assert bb.protected_reason() is None
    assert not bb.is_protected_window()


def test_fresh_approval_blocks_briefing(tmp_path, monkeypatch):
    """approval_pending.json newer than 900s MUST block briefings."""
    _clear_protected(tmp_path, monkeypatch)
    fresh_path = _write_approval(tmp_path, age_seconds=60)
    monkeypatch.setattr(bb, "_APPROVAL_PENDING", fresh_path)

    reason = bb.protected_reason()
    assert reason == "approval_pending"
    assert bb.is_protected_window()


def test_ignored_requester_approval_does_not_block(tmp_path, monkeypatch):
    """approval_pending from an ignored requester (e.g. 'codex-test') must NOT block."""
    _clear_protected(tmp_path, monkeypatch)
    ignored_path = _write_approval(tmp_path, age_seconds=30, requester="codex-test")
    monkeypatch.setattr(bb, "_APPROVAL_PENDING", ignored_path)

    assert bb.protected_reason() is None
    assert not bb.is_protected_window()
