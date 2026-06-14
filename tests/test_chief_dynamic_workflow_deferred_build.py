"""Tests for the Chief Dynamic Workflow Deferred Build packet."""

import json
from pathlib import Path
from chief_dynamic_workflow_deferred_build import (
    generate_deferred_build_packet,
    write_models,
    READ_MODEL_ID,
    JSON_EXPORT_NAME
)

def test_deferred_packet_exists_and_parses():
    packet = generate_deferred_build_packet()
    assert packet["packet_ref"] == "deferred_build:chief_dynamic_workflow:v0"

def test_resume_time_is_stored():
    packet = generate_deferred_build_packet()
    assert "resume_after_operator_time" in packet
    assert packet["resume_after_operator_time"] == "Saturday, May 30, 2026 at 5:11 PM"
    assert "timezone_assumption" in packet

def test_preferred_model_is_gpt_5_5_codex():
    packet = generate_deferred_build_packet()
    assert packet["preferred_model"] == "GPT-5.5 Codex"

def test_spark_is_restricted_to_small_surgical_work():
    packet = generate_deferred_build_packet()
    assert "GPT-5.3-Codex-Spark" in packet["fallback_models"]
    assert "surgical" in packet["fallback_models"]["GPT-5.3-Codex-Spark"]

def test_gemini_3_1_pro_is_audit_design_only():
    packet = generate_deferred_build_packet()
    assert "Gemini 3.1 Pro" in packet["fallback_models"]
    assert "audit/design only" in packet["fallback_models"]["Gemini 3.1 Pro"]

def test_customer_mode_hides_developer_build_packet():
    packet = generate_deferred_build_packet()
    assert packet["customer_visibility"] == "hidden"
    assert packet["developer_visibility"] == "visible"

def test_known_unknowns_ledger_includes_required_fields():
    packet = generate_deferred_build_packet()
    ledger = packet["known_unknowns_ledger"]
    assert "required_facts" in ledger
    assert "proven_facts" in ledger
    assert "assumptions" in ledger
    assert "missing_proof" in ledger
    assert "unsafe_claims" in ledger
    assert "operator_decisions_required" in ledger
    assert "capability_gaps" in ledger
    assert "next_package_that_resolves_each_unknown" in ledger

def test_first_codex_prompt_is_present_and_bounded():
    packet = generate_deferred_build_packet()
    prompt = packet["next_prompt_for_codex_5_5"]
    assert "Chief Dynamic Workflow Manifest v0" in prompt
    assert "chief_dynamic_workflow_manifest.py" in prompt
    assert "Do not execute live" in prompt or "manifest outputs only" in prompt

def test_no_production_authority_is_enabled():
    packet = generate_deferred_build_packet()
    forbidden = packet["forbidden_prework_before_resume"]
    assert any("live agents" in f for f in forbidden)
    assert any("Mutating ledgers" in f for f in forbidden)
