"""Comedy relevance scoping — the fix that stops global signals from landing as non-sequiturs."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from comedy_scope import is_comedy_relevant


def test_approval_cycle_relevant_when_answer_is_about_blocking():
    assert is_comedy_relevant(
        "APPROVAL_DEPENDENCY_CYCLE",
        "why is the release blocked?",
        "The release is blocked by a circular approval dependency.",
    ) is True


def test_approval_cycle_irrelevant_on_unrelated_answer():
    # the real approval-cycle signal must NOT fire a joke on a progress question
    assert is_comedy_relevant(
        "APPROVAL_DEPENDENCY_CYCLE",
        "where are we at with the system?",
        "15 engineering milestones shipped this week.",
    ) is False


def test_confidence_gap_relevant_on_completion_claim():
    assert is_comedy_relevant(
        "CONFIDENCE_EVIDENCE_GAP", "is the task done?", "The task is complete and verified."
    ) is True


def test_no_signal_is_never_relevant():
    assert is_comedy_relevant(None, "blocked approval waiting", "blocked") is False


def test_unknown_signal_is_never_relevant():
    assert is_comedy_relevant("MADE_UP_SIGNAL", "blocked approval", "blocked") is False
