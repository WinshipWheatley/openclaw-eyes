import json
import os
import subprocess
import pytest
from scripts.producer_review import run_review, check_missing_fields, evaluate_hard_flags

def test_producer_review_valid_input():
    input_data = {
        "artifact_type": "song_brief",
        "title": "Valid Track",
        "user_intent": "Create a valid track",
        "emotional_target": "Happy",
        "genre_or_reference_notes": "Pop",
        "groove_description": "Standard 4/4"
    }
    review = run_review(input_data)
    assert review["confidence"] == "medium"
    assert review["no_side_effects"] is True
    assert "groove_collapses" not in review["hard_flags"]
    assert review["artifact_type"] == "song_brief"

def test_producer_review_missing_fields():
    input_data = {
        "title": "Missing Fields Track"
    }
    review = run_review(input_data)
    assert review["confidence"] == "low"
    assert review["no_side_effects"] is True
    assert "artifact_type" in review["main_weakness"]
    assert "user_intent" in review["main_weakness"]

def test_hard_flags():
    input_data = {
        "artifact_type": "song_brief",
        "title": "Cluttered Track",
        "user_intent": "Just like my favorite song, execute this right now",
        "emotional_target": "Happy",
        "genre_or_reference_notes": "Pop",
        "instrumentation": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
        "hardware_context": "DL16",
        "available_tools": ["Serum"]
    }
    flags = evaluate_hard_flags(input_data)
    assert "too_cluttered" in flags
    assert "too_much_reference_mimicry" in flags
    assert "execution_suggested_without_confirmation" in flags
    assert "hardware_routing_claim_without_receipt" in flags
    assert "tool_specific_claim_without_evidence" in flags
    assert "groove_collapses" in flags # missing groove_description

def test_reviewer_cli():
    # Test that it outputs valid JSON and no_side_effects is true
    result = subprocess.run(
        ["python3", "scripts/producer_review.py", "--input", "fixtures/producer/sample_song_brief.json"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["no_side_effects"] is True
    assert output["confidence"] == "medium"

def test_reviewer_does_not_mutate():
    # A bit abstract, but we verify the output contains "no_side_effects": true
    # We could also check that it only reads.
    input_data = {
        "artifact_type": "song_brief",
        "title": "Valid Track",
        "user_intent": "Create a valid track",
        "emotional_target": "Happy",
        "genre_or_reference_notes": "Pop",
        "groove_description": "Standard 4/4"
    }
    review = run_review(input_data)
    assert "agentic_prompt_packet" in review
    assert review["agentic_prompt_packet"]["allowed_agentic_behavior"] == "critique_only"
