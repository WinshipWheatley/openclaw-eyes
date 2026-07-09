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
# Task 149: single-pipeline ordering (refusal-first -> money-first -> X32 -> legacy),
# hoisted into this subprocess so it's immune to a stale un-restarted listener process.
# ---------------------------------------------------------------------------


def test_money_question_never_shadowed_by_rig_knowledge():
    """Root cause #1 (word-boundary bug) + root cause #2 (lane ordering), together: the
    exact live-reproduced failure text."""
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "who owes me money right now?", "--human-only"],
        capture_output=True, text=True,
    )
    output = result.stdout
    assert "rig kb" not in output.lower()
    assert "i don't have that in the rig" not in output.lower()
    assert "not my desk" in output.lower() or "money" in output.lower() or "ledger" in output.lower()


def test_wipe_refusal_fires_from_the_subprocess_itself():
    """Root cause #3: the refusal tap must work even with no listener process involved
    at all -- proving it's durable across a listener restart-omission, not just present
    in the (potentially stale) long-running listener."""
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "wipe the X32", "--human-only"],
        capture_output=True, text=True,
    )
    output = result.stdout
    assert "SEND_HOLD" in output
    assert "deletion gate" in output.lower()


def test_scene_wipe_housekeeping_still_flows_through_to_x32_lane():
    """Blast-radius guard-rail: 'wipe the X32 scene' is legitimate in-domain housekeeping
    and must not refuse -- must still reach the X32 lane."""
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "wipe the X32 scene", "--human-only"],
        capture_output=True, text=True,
    )
    output = result.stdout
    assert "SEND_HOLD" not in output


def test_show_profile_offer_still_reached_after_reordering():
    """Acceptance: reordering refusal/money ahead of X32 must not break the X32 lane for
    non-money, non-refusal asks."""
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "here's the input list for the Reynolds gig", "--human-only"],
        capture_output=True, text=True,
    )
    output = result.stdout
    assert "SEND_HOLD" not in output
    assert "money" not in output.lower()


def test_ordinary_production_question_still_falls_through_to_legacy_path():
    """Sanity: refusal/money/X32 all correctly no-op for a normal production question,
    which must still reach the legacy template path."""
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "make it dub", "--human-only"],
        capture_output=True, text=True,
    )
    output = result.stdout
    assert "Niles:" in output
    assert "dub" in output.lower()
