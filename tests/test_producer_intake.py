import pytest
import subprocess
import json

def test_logic_vocal_delay_human_only():
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "make the vocal delay feel wider but keep the words clear in Logic", "--human-only"],
        capture_output=True, text=True
    )
    output = result.stdout
    assert "Niles:" in output
    assert "Logic" in output or "return track" in output
    assert "clear" in output or "clarity" in output
    assert "{" not in output

def test_pretty_json_output():
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "make it dub", "--pretty"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    assert "producer_contract_version" in data

def test_explain_flag_boring_spacious():
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "this chorus feels boring but I want it to stay spacious", "--explain"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    assert data["original_text"] == "this chorus feels boring but I want it to stay spacious"
    assert "boring" in data["detected_taste_terms"]
    assert "spacious" in data["detected_taste_terms"]
    assert data["suggested_move"] == "add_arrival_point_without_clutter"
    assert data["evidence_level"] == "text_only_no_audio"

def test_explain_flag_logic_vocal_delay():
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "make the vocal delay feel wider but keep the words clear in Logic", "--explain"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    assert data["detected_environment"] == "logic_pro"
    assert data["suggested_move"] == "widen_delay_return_preserve_vocal_clarity"
    assert "suggestion_only" in data["allowed_actions"]
    assert "audio_analysis_claims" in data["blocked_actions"]


# ---------------------------------------------------------------------------
# Task 145 (CLASS #6): identity persona core, hoisted into this subprocess
# (Niles' PROBE path via answer_frontdoor_chat doesn't cover his real listener).
# ---------------------------------------------------------------------------


def test_who_are_you_answers_deterministically_not_the_canned_production_line():
    """Pass-1 live evidence: Niles "played his canned line" for an identity ask --
    the generic production-advice catch-all, not a real self-description."""
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "who are you and what do you do for me?", "--human-only"],
        capture_output=True, text=True,
    )
    output = result.stdout.strip()
    assert "niles" in output.lower()
    assert "keep it practical" not in output.lower()
    assert "main goal: groove, melody, or arrangement" not in output.lower()


def test_identity_answer_reached_before_x32_lane():
    """Ordering sanity: identity is checked first so no future X32 marker can shadow
    it (the exact bug class task 149 root-caused for the money branch)."""
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "introduce yourself", "--human-only"],
        capture_output=True, text=True,
    )
    output = result.stdout.strip()
    assert "gated at my trust tier" not in output.lower()
    assert "niles" in output.lower()


def test_production_question_still_reaches_legacy_path():
    """Sanity: the new tap must not swallow ordinary production questions."""
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "make it dub", "--human-only"],
        capture_output=True, text=True,
    )
    output = result.stdout
    assert "Niles:" in output
    assert "dub" in output.lower()
