import pytest
import json
from scripts.producer_intake import build_producer_input, generate_human_response, generate_tool_intent_packet
from scripts.producer_review import run_review

def test_producer_intake_basic_parsing():
    text = "this chorus feels boring and I want it to hit harder but stay spacious"
    data = build_producer_input(text)

    assert data["artifact_type"] == "production_question"
    assert "boring" in data["emotional_target"]
    assert "spacious" in data["emotional_target"]
    assert data["target_environment"] == "unknown"

    # Should not emit a tool packet
    packet = generate_tool_intent_packet(text, data)
    assert packet is None

def test_producer_intake_target_environments():
    text = "in Ableton, sketch me a spacious afro-dub groove but don't make it cheesy"
    data = build_producer_input(text)

    assert data["target_environment"] == "ableton_live"
    assert "spacious" in data["emotional_target"]
    assert "cheesy" in data["emotional_target"]
    assert "afro-dub" in data["groove_description"]
    assert "groove" in data["groove_description"]

    # constraint extraction
    assert len(data["constraints"]) >= 1
    assert "don't make it cheesy" in data["constraints"][0]

    # Should emit a ToolIntentPacket
    packet = generate_tool_intent_packet(text, data)
    assert packet is not None
    assert packet["target_environment"] == "ableton_live"
    assert packet["intent_type"] == "suggest_groove"
    assert packet["human_confirmation_required"] is True
    assert packet["no_execution_without_approval"] is True

    # Human response should contain suggestion section
    review = run_review(data)
    human_resp = generate_human_response(data, review, packet)
    assert "Suggested tool intent" in human_resp

def test_producer_intake_logic_pro_plugin_chain():
    text = "in Logic add a spacious delay and reverb chain without washing out the vocal"
    data = build_producer_input(text)
    assert data["target_environment"] == "logic_pro"

    packet = generate_tool_intent_packet(text, data)
    assert packet is not None
    assert packet["intent_type"] == "suggest_plugin_chain"
    assert packet["target_environment"] == "logic_pro"

def test_producer_intake_routing_setup():
    text = "set up X32/DL16 recording routing"
    data = build_producer_input(text)

    packet = generate_tool_intent_packet(text, data)
    assert packet is not None
    assert packet["intent_type"] == "suggest_recording_setup"
    # Does not claim live hardware state in the packet (hardware_context is just mentioned if logic flags it, which it does if x32 or dl16 is present)
    assert packet["human_confirmation_required"] is True

    review = run_review(data)
    human_resp = generate_human_response(data, review, packet)
    assert "Note: Hardware mentioned, but does not claim live state without explicit receipts." in human_resp

def test_producer_intake_logic_pro():
    text = "Logic needs a dark groove"
    data = build_producer_input(text)
    assert data["target_environment"] == "logic_pro"
    assert "dark" in data["emotional_target"]

def test_producer_intake_hardware_claim():
    text = "Run this through the X32"
    data = build_producer_input(text)
    assert data["target_environment"] == "x32_rack"
    assert "hardware_context" in data

    review = run_review(data)
    assert "hardware_routing_claim_without_receipt" in review["hard_flags"]

    human_resp = generate_human_response(data, review)
    assert "Note: Hardware mentioned, but does not claim live state without explicit receipts." in human_resp

def test_producer_intake_missing_evidence():
    text = "just make it happen"
    data = build_producer_input(text)
    review = run_review(data)

    human_resp = generate_human_response(data, review)
    assert "Note: Missing evidence. Does not claim audio was heard." in human_resp

def test_producer_intake_tool_action_implied():
    text = "bounce the track in ableton"
    data = build_producer_input(text)
    review = run_review(data)

    assert "execution_suggested_without_confirmation" in review["hard_flags"]

    human_resp = generate_human_response(data, review)
    assert "Tool action implied. Would require confirmation and a separate execution lane." in human_resp
