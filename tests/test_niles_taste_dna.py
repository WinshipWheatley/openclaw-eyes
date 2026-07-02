"""Niles must know his own music DNA (operator FYI from the gig, 2026-07-02).

The taste doc (docs/producer/PRODUCER_ARCHETYPE.md, Six Pillars) is ledger-
ingested but the producer intake never read it. A taste/DNA ask now answers
deterministically FROM the archetype file — no LM freestyle about taste.
"""

import subprocess
import sys


def _intake(text: str) -> str:
    proc = subprocess.run(
        [sys.executable, "scripts/producer_intake.py", "--text", text, "--human-only"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_taste_dna_question_answers_from_archetype():
    out = _intake("what's my taste? whats our music dna?")
    lowered = out.lower()
    assert "rhythmic spine" in lowered
    assert "controlled chaos" in lowered or "emotional rawness" in lowered
    assert "healing dance" in lowered or "transcendence" in lowered
    # do-not-mimic principle present
    assert "mimic" in lowered or "extract" in lowered


def test_pillars_question_routes_to_dna():
    out = _intake("remind me of the six pillars")
    assert "Rhythmic Spine" in out


def test_production_questions_unchanged():
    out = _intake("the mix sounds boring but spacious")
    assert "arrival point" in out
