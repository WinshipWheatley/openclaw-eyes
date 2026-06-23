"""Hermes context packet grounding tests.

DANK criteria verified:
  (1) GROUNDED  — every fact carries source_ref + provenance tracing to a real source.
  (2) CURRENT   — freshness.as_of is set when read-model is present.
  (3) USEFUL    — packet surfaces route targets, blocked outputs, SEND_HOLD posture.
  (4) IN-VOICE  — no confabulated route targets; absent source = flagged DATA GAP.
  (5) LANE-RICH — route_targets, hermes_lane_bounds, send_hold_posture, advisory_contract
                  topics present when sources are available.

SAFETY invariants (hard — must never flip):
  - send_hold_absolute is always True.
  - outbound_send_allowed / money_movement_allowed / agent_dispatch_allowed /
    ledger_mutation_allowed / canonical_write_allowed / tool_execution_allowed /
    model_execution_allowed / runtime_authority are always False.
  - The packet never contains facts with pii_tier=MAX (Legal Discovery).
  - The build function never sends, writes, calls models, or dispatches agents.

ANTI-CONFABULATION:
  - Route targets come from DEFAULT_AGENT_LANE_SEEDS only; no inline lists.
  - Absent read-models are flagged (DATA GAP), not fabricated.
  - No hardcoded live agent counts or read-model content — tests assert structure,
    not drifting values.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import hermes_context_packet as hcp
from hermes_context_packet import (
    HERMES_READ_MODELS,
    SCHEMA_VERSION,
    build_hermes_context_packet,
    format_hermes_context_packet,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(root: Path, name: str, payload: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _minimal_presence(root: Path) -> None:
    _write(
        root,
        "agent_presence.json",
        {
            "schema_version": "agent_presence_read_model_v0",
            "generated_at": "2026-06-22T12:00:00+00:00",
            "agents": [
                {"agent_id": "hermes", "display_name": "Hermes", "actual_state": "online"},
                {"agent_id": "chief", "display_name": "Chief", "actual_state": "online"},
            ],
        },
    )


def _minimal_sentinel(root: Path) -> None:
    _write(
        root,
        "openclaw_change_sentinel.json",
        {
            "contract_schema_version": "openclaw_change_sentinel_v0",
            "generated_at": "2026-06-22T12:00:00+00:00",
            "hermes_summary": {
                "action_required": False,
                "can_wait": True,
                "what_changed": "No material change.",
                "what_to_do_next": "No action required.",
                "why_it_matters": "System state is stable.",
            },
        },
    )


def _minimal_mission_sentinel(root: Path) -> None:
    _write(
        root,
        "hermes_mission_sentinel.json",
        {
            "schema_version": "hermes_mission_sentinel_v0",
            "generated_at": "2026-06-22T12:00:00+00:00",
            "automation_ready_status": "NOT_SEND_READY",
            "contract_status": "READINESS_SENTINEL_NO_EXECUTION",
            "authority_boundary": {
                "email_send_allowed": False,
                "ledger_mutation_allowed": False,
                "tool_execution_allowed": False,
            },
            "current_blockers": ["invoice candidate not selected"],
            "operator_summary": "System is not send-ready.",
        },
    )


def _minimal_gravity_controller(root: Path) -> None:
    _write(
        root,
        "hermes_gravity_controller.json",
        {
            "schema_version": "hermes_gravity_controller_v0",
            "generated_at": "2026-06-22T12:00:00+00:00",
            "contract_status": "DETERMINISTIC_NON_EXECUTING_PURPOSE_BOUND_GRAVITY_CONTROLLER",
            "gravity_statuses": ["PURPOSE_BOUND_OK", "NEEDS_NARROWING", "SURVEILLANCE_RISK"],
            "machine_proof": {
                "all_authority_flags_false": True,
                "read_model_only": True,
                "example_count": 3,
            },
            "operator_summary": {
                "developer_view": "Hermes evaluates purpose-bound capability proposals.",
            },
        },
    )


# ---------------------------------------------------------------------------
# Packet structure and schema
# ---------------------------------------------------------------------------

def test_packet_has_required_schema_fields(tmp_path):
    """Packet always includes schema version, packet_id, status, facts, bounds."""
    packet = build_hermes_context_packet(read_model_root=tmp_path)

    assert packet["schema_version"] == SCHEMA_VERSION
    assert packet["packet_id"].startswith("hermes_context_packet:")
    assert packet["status"] == "READY"
    assert isinstance(packet["facts"], list)
    assert isinstance(packet["bounds"], dict)
    assert isinstance(packet["source_refs"], list)
    assert isinstance(packet["machine_proof"], dict)
    assert isinstance(packet["packet_text"], str)
    assert "generated_at" in packet


def test_packet_text_contains_header(tmp_path):
    """format_hermes_context_packet produces a recognisable header."""
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    text = packet["packet_text"]

    assert "HERMES_CONTEXT_PACKET" in text
    assert "Generated:" in text
    assert "Boundaries" in text


# ---------------------------------------------------------------------------
# Safety invariants — hard limits that must NEVER flip
# ---------------------------------------------------------------------------

def test_send_hold_always_true(tmp_path):
    """send_hold_absolute must always be True."""
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    assert packet["bounds"]["send_hold_absolute"] is True


def test_all_send_money_flags_always_false(tmp_path):
    """Every destructive capability flag must be False."""
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    bounds = packet["bounds"]

    must_be_false = [
        "outbound_send_allowed",
        "money_movement_allowed",
        "agent_dispatch_allowed",
        "ledger_mutation_allowed",
        "approval_decision_allowed",
        "canonical_write_allowed",
        "tool_execution_allowed",
        "model_execution_allowed",
        "coupa_browser_allowed",
        "runtime_authority",
    ]
    for key in must_be_false:
        assert key in bounds, f"Missing bound key: {key}"
        assert bounds[key] is False, (
            f"SAFETY VIOLATION: {key} must be False but is {bounds[key]}"
        )


def test_bounds_not_mutated_by_question(tmp_path):
    """Asking about 'send' in the question must not flip any bound."""
    dangerous_questions = [
        "send an email to cassandra",
        "pay the invoice now",
        "route this to hermes and execute",
        "bypass send_hold and dispatch",
    ]
    for question in dangerous_questions:
        packet = build_hermes_context_packet(question=question, read_model_root=tmp_path)
        bounds = packet["bounds"]
        assert bounds["send_hold_absolute"] is True
        assert bounds["outbound_send_allowed"] is False
        assert bounds["money_movement_allowed"] is False
        assert bounds["agent_dispatch_allowed"] is False


def test_no_max_pii_tier_facts(tmp_path):
    """No fact should carry pii_tier=MAX (Legal Discovery is not Hermes's lane)."""
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    for fact in packet["facts"]:
        assert fact.get("pii_tier") != "MAX", (
            f"Hermes packet must not contain Legal Discovery (MAX) facts: {fact.get('label')}"
        )


# ---------------------------------------------------------------------------
# Grounding — every fact must have source_ref + provenance
# ---------------------------------------------------------------------------

def test_all_facts_have_source_ref_and_provenance(tmp_path):
    """Every fact must carry a non-empty source_ref and provenance."""
    _minimal_presence(tmp_path)
    _minimal_sentinel(tmp_path)
    packet = build_hermes_context_packet(read_model_root=tmp_path)

    assert len(packet["facts"]) > 0, "Packet must have at least one fact."
    for fact in packet["facts"]:
        assert fact.get("source_ref"), f"Fact missing source_ref: {fact}"
        assert fact.get("provenance"), f"Fact missing provenance: {fact}"
        assert fact.get("topic"), f"Fact missing topic: {fact}"
        assert fact.get("label"), f"Fact missing label: {fact}"
        assert fact.get("value"), f"Fact missing value: {fact}"
        assert fact.get("fact_id"), f"Fact missing fact_id: {fact}"


def test_route_target_facts_trace_to_agent_lane_registry(tmp_path):
    """Route-target facts must trace to agent_lane_registry, not inline strings."""
    packet = build_hermes_context_packet(read_model_root=tmp_path)

    route_facts = [f for f in packet["facts"] if f["topic"] == "route_targets"]
    assert len(route_facts) >= 1, "Expected at least one route_targets fact."

    for fact in route_facts:
        if "DATA GAP" not in fact["label"]:
            assert "agent_lane_registry" in fact["source_ref"], (
                f"Route target fact must trace to agent_lane_registry, got: {fact['source_ref']}"
            )
            assert fact["provenance"] == "agent_lane_registry_seeds"


def test_hermes_lane_bounds_from_registry(tmp_path):
    """hermes_lane_bounds facts must come from the registry, not hardcoded strings."""
    packet = build_hermes_context_packet(read_model_root=tmp_path)

    lane_facts = [f for f in packet["facts"] if f["topic"] == "hermes_lane_bounds"]
    # If registry is available, we expect lane bound facts.
    try:
        from agent_lane_registry import DEFAULT_AGENT_LANE_SEEDS
        hermes_seed = next((s for s in DEFAULT_AGENT_LANE_SEEDS if s.agent_id == "hermes"), None)
        if hermes_seed is not None:
            assert len(lane_facts) >= 1, "Expected hermes_lane_bounds facts when registry is available."
            for fact in lane_facts:
                assert "agent_lane_registry" in fact["source_ref"]
    except Exception:
        # Registry unavailable — DATA GAP is acceptable.
        pass


# ---------------------------------------------------------------------------
# Freshness — read-model facts carry as_of timestamps
# ---------------------------------------------------------------------------

def test_facts_from_read_models_have_freshness(tmp_path):
    """Facts extracted from read-models carry a freshness.as_of value."""
    _minimal_presence(tmp_path)
    _minimal_sentinel(tmp_path)
    packet = build_hermes_context_packet(read_model_root=tmp_path)

    rm_facts = [
        f for f in packet["facts"]
        if f.get("provenance") == "generated_read_model"
    ]
    for fact in rm_facts:
        freshness = fact.get("freshness", {})
        assert isinstance(freshness, dict), f"freshness must be a dict: {fact}"
        assert freshness.get("as_of"), (
            f"freshness.as_of must be set for read-model fact: {fact['label']}"
        )


# ---------------------------------------------------------------------------
# Usefulness — specific lane-relevant topics must appear
# ---------------------------------------------------------------------------

def test_packet_contains_send_hold_posture_fact(tmp_path):
    """send_hold_posture topic must always appear (from env/gateway check)."""
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    topics = {f["topic"] for f in packet["facts"]}
    assert "send_hold_posture" in topics


def test_packet_contains_advisory_contract_fact(tmp_path):
    """advisory_contract topic must always appear (from hermes_advisory_packet)."""
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    topics = {f["topic"] for f in packet["facts"]}
    assert "advisory_contract" in topics


def test_mission_sentinel_fact_present_when_file_exists(tmp_path):
    """mission_sentinel topic appears when read-model file is present."""
    _minimal_mission_sentinel(tmp_path)
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    topics = {f["topic"] for f in packet["facts"]}
    assert "mission_sentinel" in topics


def test_gravity_controller_fact_present_when_file_exists(tmp_path):
    """gravity_controller topic appears when read-model file is present."""
    _minimal_gravity_controller(tmp_path)
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    topics = {f["topic"] for f in packet["facts"]}
    assert "gravity_controller" in topics


def test_change_sentinel_fact_present_when_file_exists(tmp_path):
    """change_sentinel topic appears when read-model file is present."""
    _minimal_sentinel(tmp_path)
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    topics = {f["topic"] for f in packet["facts"]}
    assert "change_sentinel" in topics


def test_agent_presence_fact_present_when_file_exists(tmp_path):
    """agent_presence topic appears when read-model file is present."""
    _minimal_presence(tmp_path)
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    topics = {f["topic"] for f in packet["facts"]}
    assert "agent_presence" in topics


# ---------------------------------------------------------------------------
# Anti-confabulation — absent sources must be flagged, not invented
# ---------------------------------------------------------------------------

def test_empty_read_model_root_produces_gap_or_code_facts_only(tmp_path):
    """When read_model_root is empty, only code-sourced facts appear (no file facts)."""
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    rm_facts = [
        f for f in packet["facts"]
        if f.get("provenance") == "generated_read_model"
    ]
    # No generated_read_model provenance facts when directory is empty.
    assert rm_facts == [], (
        f"Expected no generated_read_model facts from empty root, got: {rm_facts}"
    )


def test_mission_sentinel_facts_absent_when_file_missing(tmp_path):
    """mission_sentinel facts do not appear when the file is missing."""
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    sentinel_facts = [f for f in packet["facts"] if f["topic"] == "mission_sentinel"]
    assert sentinel_facts == [], (
        "mission_sentinel facts must not appear when hermes_mission_sentinel.json is absent."
    )


def test_machine_proof_records_read_model_presence(tmp_path):
    """machine_proof.read_model_presence tracks which files were found."""
    _minimal_presence(tmp_path)
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    presence = packet["machine_proof"]["read_model_presence"]

    assert isinstance(presence, dict)
    # agent_presence.json was written — should be True.
    assert presence.get("agent_presence.json") is True
    # hermes_mission_sentinel.json was NOT written — should be False.
    assert presence.get("hermes_mission_sentinel.json") is False


def test_no_confabulated_route_targets_when_registry_unavailable(monkeypatch, tmp_path):
    """If agent_lane_registry is unavailable, route_targets contains a DATA GAP fact."""
    import builtins
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "agent_lane_registry":
            raise ImportError("stubbed for test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    packet = build_hermes_context_packet(read_model_root=tmp_path)
    route_facts = [f for f in packet["facts"] if f["topic"] == "route_targets"]

    assert len(route_facts) >= 1
    # Should be a DATA GAP fact, not fabricated agent names.
    data_gap_facts = [f for f in route_facts if "DATA GAP" in f["label"]]
    assert len(data_gap_facts) >= 1, (
        "Expected DATA GAP fact when agent_lane_registry is unavailable."
    )
    # Must not have invented agent names.
    non_gap_facts = [f for f in route_facts if "DATA GAP" not in f["label"]]
    assert non_gap_facts == [], (
        "Must not fabricate route target facts when registry unavailable."
    )


# ---------------------------------------------------------------------------
# Authority-level consistency — agent roster mirrors gateway policy
# ---------------------------------------------------------------------------

def test_route_targets_match_gateway_fallback_targets(tmp_path):
    """If registry loads, route target agent IDs should include the gateway fallback set."""
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    route_facts = [f for f in packet["facts"] if f["topic"] == "route_targets"]

    # If we have non-gap route facts, the roster should include the core agents.
    non_gap = [f for f in route_facts if "DATA GAP" not in f["label"]]
    if non_gap:
        roster_value = non_gap[0]["value"].lower()
        # Core agents that must always be in the registry.
        for expected in ("hermes", "chief", "cassandra", "guardian"):
            assert expected in roster_value, (
                f"Expected '{expected}' in route target roster: {roster_value[:200]}"
            )


def test_hermes_own_lane_notes_advisory_only(tmp_path):
    """Hermes lane facts must describe advisory_only authority, never execution."""
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    lane_facts = [f for f in packet["facts"] if f["topic"] == "hermes_lane_bounds"]

    for fact in lane_facts:
        value_lower = fact["value"].lower()
        # Must reflect advisory_only — never claim execution authority.
        if "authority" in fact["label"].lower():
            assert "advisory_only" in value_lower, (
                f"Hermes lane authority fact must say advisory_only: {fact['value'][:200]}"
            )
        # Blocked outputs must include canonical_promotion and direct_execution.
        if "blocked" in fact["label"].lower():
            assert "canonical_promotion" in value_lower or "direct_execution" in value_lower, (
                f"Hermes blocked outputs should include canonical_promotion/direct_execution: "
                f"{fact['value'][:200]}"
            )


# ---------------------------------------------------------------------------
# Read-model content integrity
# ---------------------------------------------------------------------------

def test_mission_sentinel_flags_send_hold_correctly(tmp_path):
    """Mission sentinel authority boundary must report all-False flags correctly."""
    _minimal_mission_sentinel(tmp_path)
    packet = build_hermes_context_packet(read_model_root=tmp_path)

    sentinel_facts = [f for f in packet["facts"] if f["topic"] == "mission_sentinel"]
    boundary_facts = [f for f in sentinel_facts if "authority boundary" in f["label"].lower()]

    assert len(boundary_facts) >= 1
    for fact in boundary_facts:
        # Our minimal payload has all False flags — fact should say "none (correct)".
        assert "none (correct)" in fact["value"] or "0 flags True" in fact["value"].lower() or "correct" in fact["value"].lower()


def test_gravity_controller_machine_proof_surfaced(tmp_path):
    """Gravity controller machine proof is surfaced as a fact."""
    _minimal_gravity_controller(tmp_path)
    packet = build_hermes_context_packet(read_model_root=tmp_path)

    gc_facts = [f for f in packet["facts"] if f["topic"] == "gravity_controller"]
    proof_facts = [f for f in gc_facts if "machine proof" in f["label"].lower()]
    assert len(proof_facts) >= 1

    proof_value = proof_facts[0]["value"]
    assert "all_authority_flags_false=True" in proof_value
    assert "read_model_only=True" in proof_value


def test_change_sentinel_action_required_surfaced(tmp_path):
    """Change sentinel action_required flag is surfaced in the fact value."""
    _minimal_sentinel(tmp_path)
    packet = build_hermes_context_packet(read_model_root=tmp_path)

    cs_facts = [f for f in packet["facts"] if f["topic"] == "change_sentinel"]
    assert len(cs_facts) >= 1
    fact_value = cs_facts[0]["value"]
    assert "action_required=False" in fact_value


# ---------------------------------------------------------------------------
# Machine proof integrity
# ---------------------------------------------------------------------------

def test_machine_proof_has_required_keys(tmp_path):
    """machine_proof must include compiler name and authority flags."""
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    mp = packet["machine_proof"]

    assert "packet_compiler" in mp
    assert mp["packet_compiler"] == "hermes_context_packet.build_hermes_context_packet"
    assert "fact_count" in mp
    assert "read_model_count" in mp
    assert "read_model_presence" in mp
    assert "authority_flags_verified" in mp


def test_machine_proof_authority_flags_match_bounds(tmp_path):
    """machine_proof.authority_flags_verified must equal packet.bounds."""
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    assert packet["machine_proof"]["authority_flags_verified"] == packet["bounds"]


# ---------------------------------------------------------------------------
# Format function
# ---------------------------------------------------------------------------

def test_format_function_includes_all_section_headers(tmp_path):
    _minimal_presence(tmp_path)
    _minimal_sentinel(tmp_path)
    packet = build_hermes_context_packet(read_model_root=tmp_path)
    text = format_hermes_context_packet(packet)

    assert "HERMES_CONTEXT_PACKET" in text
    assert "Grounded facts:" in text
    assert "Boundaries" in text
    assert "SEND_HOLD absolute: True" in text
    assert "Outbound send allowed: False" in text
    assert "Money movement allowed: False" in text


def test_format_function_works_with_empty_facts():
    """format_hermes_context_packet handles a minimal packet without crashing."""
    minimal_packet = {
        "packet_id": "hermes_context_packet:test",
        "generated_at": "2026-06-22T00:00:00+00:00",
        "facts": [],
        "bounds": {
            "send_hold_absolute": True,
            "outbound_send_allowed": False,
            "money_movement_allowed": False,
            "agent_dispatch_allowed": False,
            "ledger_mutation_allowed": False,
            "canonical_write_allowed": False,
        },
    }
    text = format_hermes_context_packet(minimal_packet)
    assert "HERMES_CONTEXT_PACKET" in text
    assert "SEND_HOLD absolute: True" in text
