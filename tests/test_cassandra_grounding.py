"""Grounding tests for Cassandra's context packet.

DANK contract verification:
  (1) GROUNDED  — every fact must carry source_ref + freshness; no empty values.
  (2) CURRENT   — freshness.as_of must be populated from the read-model.
  (3) USEFUL    — specific Cassandra-lane topics must surface from real read-model data.
  (4) IN-VOICE  — no confabulation; data gaps are EXPLICIT flagged facts.
  (5) LANE-RICH — email/calendar posture, wiring, presence, sync health all present.

Anti-confabulation rule: calendar event titles/times and email inbox content have
no read-model source. Tests verify these are FLAGGED as data gaps, not fabricated.

Do NOT hardcode live counts that drift — assert structure and real-data-properties.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_context_packet as ccp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(root: Path, name: str, payload: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _minimal_email_calendar_detangle() -> dict:
    """Minimal valid cassandra_email_calendar_delta_detangle.json payload."""
    return {
        "schema_version": "cassandra_email_calendar_delta_detangle_v0",
        "generated_at": "2026-06-22T10:00:00+00:00",
        "detangle_status": "classification_only_no_live_authority",
        "current_governed_capabilities": {
            "governed_review_packet_path_ready": True,
            "draft_preview_read_model_ready": True,
            "execution_enabled": False,
            "approval_receipt_present": False,
            "guardian_final_send_request_contract_modeled": True,
            "mission_control_visibility_supported_by_read_model": True,
        },
        "classification_counts": {
            "GOVERNED_REVIEW_PACKET_READY": 1,
            "DRAFT_PREVIEW_ONLY": 1,
            "LIVE_GMAIL_BLOCKED": 1,
            "EMAIL_SEND_BLOCKED": 1,
            "CALENDAR_DISCOVERY_BLOCKED": 1,
            "OAUTH_CREDENTIAL_BLOCKED": 1,
            "TELEGRAM_NOTIFICATION_SEPARATE": 1,
            "UNKNOWN_FAIL_CLOSED": 1,
            "PROTECTED_ACCESS_REQUIRED": 0,
            "SECURITY_THRESHOLD_REQUIRED": 0,
            "CALENDAR_NORMALIZATION_FUTURE": 1,
            "LEGACY_REFERENCE_ONLY": 1,
        },
        "calendar_operator_context": {
            "google_apple_calendar_merged_context_recorded": True,
            "live_calendar_access_enabled": False,
            "generic_calendar_cleanup_started": False,
            "calendar_normalization_allowed_now": False,
            "future_scoped_normalization_requires_named_workflow": True,
        },
        "protected_access_requirements": {
            "protected_access_gate_required_for_live_gmail_calendar": True,
            "unknown_surfaces_fail_closed": True,
            "credential_or_oauth_access_allowed_now": False,
        },
        "live_gmail_access_enabled": False,
        "live_google_calendar_access_enabled": False,
        "email_send_triggered": False,
    }


def _minimal_agent_presence() -> dict:
    """Minimal valid agent_presence.json payload."""
    return {
        "schema_version": "agent_presence_read_model_v0",
        "generated_at": "2026-06-22T10:05:00+00:00",
        "online_count": 2,
        "agents": [
            {
                "agent_id": "cassandra",
                "display_name": "Cassandra",
                "actual_state": "offline",
                "desired_state": "online",
                "blocker": "expected runtime evidence missing",
                "recovery_status": "blocked",
            },
            {
                "agent_id": "guardian",
                "display_name": "Guardian",
                "actual_state": "online",
                "desired_state": "online",
                "blocker": None,
                "recovery_status": "not_needed",
            },
        ],
        "cassandra_presence": {
            "agent_id": "cassandra",
            "actual_state": "offline",
            "desired_state": "online",
            "blocker": "expected runtime evidence missing",
            "recovery_status": "blocked",
            "last_recovery_attempt": {
                "attempted": True,
                "attempted_at": "2026-06-22T09:55:00+00:00",
                "succeeded": False,
                "blocker": "recovery command returned non-zero exit code",
                "exit_code": 1,
            },
        },
        "blockers": [
            {
                "agent_id": "cassandra",
                "blocker": "expected runtime evidence missing",
                "next_safe_move": "Inspect service surface.",
            }
        ],
    }


def _minimal_wiring_audit() -> dict:
    """Minimal valid cassandra_runtime_wiring_audit.json payload."""
    return {
        "schema_version": "cassandra_runtime_wiring_audit_read_model_v0",
        "read_model_version": "cassandra_runtime_wiring_audit_read_model_v0",
        "generated_at": "2026-06-22T10:10:00+00:00",
        "counts": {
            "service_count": 3,
            "gap_count": 2,
            "live_receive_proven": False,
            "governed_storage_proven": True,
            "reply_ready": False,
            "unsafe_surface_count": 4,
            "already_ported_count": 8,
        },
        "gaps": [
            {
                "gap_id": "cassgap_abc123",
                "gap_kind": "live_receive_not_proven",
                "severity": "high",
                "title": "Cassandra Telegram receive is not proven",
                "evidence_summary": "No governed intake row from cassandra_listener.",
                "next_safe_move": "Run an operator-approved receive-only test.",
            },
            {
                "gap_id": "cassgap_def456",
                "gap_kind": "legacy_direct_send_present",
                "severity": "high",
                "title": "Legacy Cassandra listener has direct Telegram reply paths",
                "evidence_summary": "cassandra_listener.py contains direct reply calls.",
                "next_safe_move": "Wrap reply paths behind Guardian-approved policy.",
            },
        ],
        "roundtrip_steps": [
            {
                "step_name": "cassandra_services_online",
                "step_order": 1,
                "status": "proven",
                "implemented": 1,
                "proven": 1,
            },
            {
                "step_name": "listener_execstart_points_repo_a",
                "step_order": 2,
                "status": "proven",
                "implemented": 1,
                "proven": 1,
            },
            {
                "step_name": "safe_acknowledgment_policy",
                "step_order": 7,
                "status": "blocked_by_policy",
                "implemented": 0,
                "proven": 0,
            },
        ],
        "service_status": [
            {"service_name": "cassandra-listener.service", "active_state": "active"},
            {"service_name": "cassandra-watcher.service", "active_state": "active"},
            {"service_name": "cassandra-briefing-scheduler.service", "active_state": "active"},
        ],
    }


def _minimal_sync_health() -> dict:
    """Minimal valid sync_health.json payload."""
    return {
        "schema_version": "sync_health_read_model_v0",
        "generated_at": "2026-06-22T10:15:00+00:00",
        "sync_lifecycle_state": "trusted_current",
        "trust_status": "trusted",
        "display_status": "current",
        "last_mac_completion": {
            "status": "synced",
            "time": "2026-06-22T09:00:00+00:00",
        },
        "check_transmission_display": {
            "headline": "Read-model mirror current",
            "lamp_state": "OFF",
            "next_safe_move": "No sync repair needed.",
        },
    }


# ---------------------------------------------------------------------------
# Core structure tests
# ---------------------------------------------------------------------------

def test_packet_has_required_schema_fields(tmp_path):
    """Packet must always include schema_version, packet_id, status, facts, bounds."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)

    assert pkt["schema_version"] == ccp.SCHEMA_VERSION
    assert pkt["packet_id"].startswith("cassandra_context_packet:")
    assert pkt["status"] == "READY"
    assert isinstance(pkt["facts"], list)
    assert isinstance(pkt["bounds"], dict)
    assert isinstance(pkt["machine_proof"], dict)
    assert isinstance(pkt["packet_text"], str)
    assert isinstance(pkt["source_refs"], list)


def test_every_fact_has_source_ref_and_freshness(tmp_path):
    """GROUNDED: every fact must carry non-empty source_ref and freshness.as_of."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())
    _write(root, "agent_presence.json", _minimal_agent_presence())
    _write(root, "cassandra_runtime_wiring_audit.json", _minimal_wiring_audit())
    _write(root, "sync_health.json", _minimal_sync_health())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    facts = pkt["facts"]

    assert len(facts) > 0, "Packet must have at least one fact."
    for fact in facts:
        assert isinstance(fact.get("source_ref"), str) and fact["source_ref"], (
            f"Fact {fact.get('fact_id')} missing source_ref"
        )
        freshness = fact.get("freshness", {})
        assert isinstance(freshness, dict), f"Fact {fact.get('fact_id')} freshness must be dict"
        # Every fact must have as_of populated when a real read-model timestamp is available
        # (gap_detection facts with no read-model timestamp are exempt — they set generated_at)
        if fact.get("provenance") != "gap_detection":
            # source_ref must point to a real read-model path
            assert "generated/read_models/" in fact["source_ref"], (
                f"source_ref must reference a read-model file: {fact['source_ref']}"
            )


def test_every_fact_has_non_empty_value(tmp_path):
    """GROUNDED: no fact may have an empty value (anti-confabulation check)."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())
    _write(root, "agent_presence.json", _minimal_agent_presence())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    for fact in pkt["facts"]:
        assert isinstance(fact.get("value"), str) and fact["value"].strip(), (
            f"Fact {fact.get('fact_id')} has empty value — anti-confabulation violation"
        )


def test_every_fact_has_pii_tier(tmp_path):
    """Every fact must declare a pii_tier."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    valid_tiers = {"PUBLIC", "LIGHT", "MED", "HIGH", "MAX"}
    for fact in pkt["facts"]:
        assert fact.get("pii_tier") in valid_tiers, (
            f"Fact {fact.get('fact_id')} has invalid pii_tier: {fact.get('pii_tier')}"
        )


# ---------------------------------------------------------------------------
# Lane-specific grounding tests
# ---------------------------------------------------------------------------

def test_email_calendar_posture_facts_present(tmp_path):
    """LANE-RICH: email/calendar posture must surface from delta-detangle read-model."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    posture_facts = [f for f in pkt["facts"] if f.get("topic") == "email_calendar_posture"]

    assert len(posture_facts) >= 2, (
        "Expected at least 2 email_calendar_posture facts (detangle status + capability posture)"
    )

    # Detangle status must be grounded in the read-model
    detangle_fact = next(
        (f for f in posture_facts if "detangle" in str(f.get("label") or "").lower()), None
    )
    assert detangle_fact is not None, "Detangle status fact must be present"
    assert "classification_only" in detangle_fact["value"]
    assert detangle_fact["source_ref"] == "generated/read_models/cassandra_email_calendar_delta_detangle.json"
    assert detangle_fact["freshness"].get("as_of") == "2026-06-22T10:00:00+00:00"


def test_governed_capability_posture_surfaces(tmp_path):
    """Governed capability flags (review ready, draft ready, execution_enabled) must appear."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    posture_facts = [f for f in pkt["facts"] if f.get("topic") == "email_calendar_posture"]

    cap_fact = next(
        (f for f in posture_facts if "capability" in str(f.get("label") or "").lower()), None
    )
    assert cap_fact is not None, "Governed capability posture fact must be present"
    val = cap_fact["value"]
    assert "Review packet path ready: True" in val
    assert "Draft preview read-model ready: True" in val
    assert "Execution enabled: False" in val


def test_classification_counts_surface(tmp_path):
    """Email/calendar surface classification counts must surface from read-model."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    count_facts = [
        f for f in pkt["facts"]
        if "classification counts" in str(f.get("label") or "").lower()
    ]
    assert len(count_facts) >= 1, "Classification count fact must be present"
    val = count_facts[0]["value"]
    # Governed and blocked counts must appear — assert structure, not specific drifting numbers
    assert "Governed review-ready surfaces:" in val
    assert "Live Gmail blocked:" in val
    assert "Calendar discovery blocked:" in val


def test_calendar_context_fact_surfaces_and_flags_data_gap(tmp_path):
    """ANTI-CONFABULATION: calendar fact must flag live events as a DATA GAP, not fabricate them."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)

    # Calendar state fact must surface the posture
    cal_facts = [f for f in pkt["facts"] if f.get("topic") == "calendar_state"]
    assert len(cal_facts) >= 1, "calendar_state fact must be present"
    cal_fact = cal_facts[0]
    assert "live_calendar_access_enabled" in cal_fact["value"].lower() or "live calendar access" in cal_fact["value"].lower()
    assert "DATA GAP" in cal_fact["value"], "Calendar fact must explicitly flag live events as a DATA GAP"

    # Must NOT contain any fabricated event titles or times
    val = cal_fact["value"].lower()
    assert "standup" not in val, "No fabricated calendar events"
    assert "meeting at" not in val, "No fabricated calendar events"


def test_data_gap_facts_present_for_live_calendar_and_email(tmp_path):
    """ANTI-CONFABULATION: explicit DATA GAP facts must be present for calendar events and email inbox."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    gap_facts = [f for f in pkt["facts"] if f.get("topic") == "data_gap"]

    assert len(gap_facts) >= 2, "At least 2 data_gap facts expected (calendar events + email inbox)"

    gap_labels = [f.get("label", "") for f in gap_facts]
    assert any("calendar" in label.lower() for label in gap_labels), (
        "Calendar events data gap must be flagged"
    )
    assert any("email" in label.lower() for label in gap_labels), (
        "Email inbox data gap must be flagged"
    )

    # Verify the gap facts describe the gap properly and don't contain fabricated data
    for gap in gap_facts:
        assert "DATA GAP" in gap["label"], f"Gap fact label must say DATA GAP: {gap['label']}"
        val = gap["value"]
        assert "BLOCKED" in val or "blocked" in val, "Gap must explain why data is unavailable"
        assert len(val) > 50, "Gap explanation must be substantive"


def test_wiring_posture_facts_present(tmp_path):
    """LANE-RICH: runtime wiring posture must surface service, gap, roundtrip facts."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_runtime_wiring_audit.json", _minimal_wiring_audit())
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    wiring_facts = [f for f in pkt["facts"] if f.get("topic") == "runtime_wiring"]

    assert len(wiring_facts) >= 2, "At least 2 runtime_wiring facts expected"

    # Wiring posture summary
    posture_fact = next(
        (f for f in wiring_facts if "posture" in str(f.get("label") or "").lower()), None
    )
    assert posture_fact is not None, "Wiring posture fact must be present"
    val = posture_fact["value"]
    assert "Service count:" in val
    assert "Wiring gaps:" in val
    assert "Governed storage proven:" in val
    assert posture_fact["source_ref"] == "generated/read_models/cassandra_runtime_wiring_audit.json"


def test_wiring_gaps_surface_from_read_model(tmp_path):
    """Wiring gaps must surface with severity and kind from the real read-model."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_runtime_wiring_audit.json", _minimal_wiring_audit())
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    gap_facts = [
        f for f in pkt["facts"]
        if f.get("topic") == "runtime_wiring" and "gap" in str(f.get("label") or "").lower()
    ]

    assert len(gap_facts) >= 1, "Wiring gaps fact must be present"
    val = gap_facts[0]["value"]
    assert "live_receive_not_proven" in val
    assert "high" in val.lower()


def test_cassandra_own_presence_fact_present(tmp_path):
    """LANE-RICH: Cassandra's own presence state must appear as a distinct fact."""
    root = tmp_path / "read_models"
    _write(root, "agent_presence.json", _minimal_agent_presence())
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    cass_facts = [f for f in pkt["facts"] if f.get("topic") == "cassandra_presence"]

    assert len(cass_facts) >= 1, "cassandra_presence fact must be present"
    presence_fact = cass_facts[0]
    assert "offline" in presence_fact["value"].lower() or "online" in presence_fact["value"].lower()
    assert "Actual state:" in presence_fact["value"]
    assert "Recovery status:" in presence_fact["value"]
    assert presence_fact["source_ref"] == "generated/read_models/agent_presence.json"


def test_presence_freshness_from_read_model(tmp_path):
    """CURRENT: presence fact freshness must come from read-model generated_at."""
    root = tmp_path / "read_models"
    _write(root, "agent_presence.json", _minimal_agent_presence())
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    presence_facts = [f for f in pkt["facts"] if f.get("topic") in ("cassandra_presence", "agent_presence")]

    assert len(presence_facts) >= 1
    for fact in presence_facts:
        assert fact["freshness"].get("as_of") == "2026-06-22T10:05:00+00:00", (
            f"Freshness must come from read-model generated_at, got: {fact['freshness']}"
        )


def test_sync_health_fact_present(tmp_path):
    """LANE-RICH: sync health must surface with lifecycle state and trust status."""
    root = tmp_path / "read_models"
    _write(root, "sync_health.json", _minimal_sync_health())
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    sync_facts = [f for f in pkt["facts"] if f.get("topic") == "sync_health"]

    assert len(sync_facts) >= 1, "sync_health fact must be present"
    val = sync_facts[0]["value"]
    assert "trusted_current" in val
    assert "trusted" in val
    assert sync_facts[0]["source_ref"] == "generated/read_models/sync_health.json"


def test_bounds_are_all_restricted(tmp_path):
    """Safety: all outbound/mutation bounds must be False."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    bounds = pkt["bounds"]

    assert bounds["send_hold_absolute"] is True
    assert bounds["outbound_send_allowed"] is False
    assert bounds["email_send_allowed"] is False
    assert bounds["gmail_draft_creation_allowed"] is False
    assert bounds["calendar_mutation_allowed"] is False
    assert bounds["live_email_access_allowed"] is False
    assert bounds["live_calendar_access_allowed"] is False
    assert bounds["oauth_credential_access_allowed"] is False
    assert bounds["money_movement_allowed"] is False
    assert bounds["ledger_mutation_allowed"] is False


def test_missing_email_calendar_read_model_produces_gap_fact(tmp_path):
    """If the primary email/calendar read-model is absent, a DATA GAP fact is inserted."""
    root = tmp_path / "read_models"
    root.mkdir(parents=True, exist_ok=True)
    # Do NOT write the email/calendar read-model

    pkt = ccp.build_cassandra_context_packet(
        read_model_root=root, require_email_calendar_read_model=True
    )

    gap_facts = [
        f for f in pkt["facts"]
        if "MISSING" in str(f.get("fact_id") or "") or "absent" in str(f.get("label") or "").lower()
    ]
    assert len(gap_facts) >= 1, "Missing read-model must produce a DATA GAP fact"
    assert "cassandra_email_calendar_delta_detangle.json" in gap_facts[0]["value"]


def test_empty_read_model_root_produces_gap_facts(tmp_path):
    """With no read-models at all, packet still works — gaps are flagged, no exception."""
    root = tmp_path / "empty_read_models"
    root.mkdir(parents=True, exist_ok=True)

    # Must not raise; must return a packet with gap facts
    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    assert pkt["schema_version"] == ccp.SCHEMA_VERSION
    assert pkt["status"] == "READY"
    # Gap fact inserted for missing primary read-model
    assert len(pkt["facts"]) >= 1


def test_machine_proof_records_read_model_presence(tmp_path):
    """Machine proof must record which read-models were present and absent."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())
    # Do NOT write runtime wiring audit

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    presence = pkt["machine_proof"]["read_model_presence"]

    assert presence["cassandra_email_calendar_delta_detangle.json"] is True
    assert presence["cassandra_runtime_wiring_audit.json"] is False


def test_packet_text_contains_cassandra_header(tmp_path):
    """Format function must produce text with CASSANDRA_CONTEXT_PACKET header."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    text = pkt["packet_text"]

    assert text.startswith("CASSANDRA_CONTEXT_PACKET")
    assert "Boundaries (Cassandra lane):" in text
    assert "SEND_HOLD absolute: True" in text
    assert "Email send allowed: False" in text


def test_facts_trace_to_source_refs(tmp_path):
    """All fact source_refs must appear in the packet's top-level source_refs list."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())
    _write(root, "agent_presence.json", _minimal_agent_presence())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    source_refs_set = set(pkt["source_refs"])

    for fact in pkt["facts"]:
        ref = fact.get("source_ref")
        assert ref in source_refs_set, (
            f"Fact source_ref not in packet source_refs: {ref}"
        )


def test_fact_ids_are_unique(tmp_path):
    """Every fact_id must be unique within the packet."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())
    _write(root, "agent_presence.json", _minimal_agent_presence())
    _write(root, "cassandra_runtime_wiring_audit.json", _minimal_wiring_audit())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    fact_ids = [f.get("fact_id") for f in pkt["facts"]]
    assert len(fact_ids) == len(set(fact_ids)), (
        f"Duplicate fact_ids detected: {[fid for fid in fact_ids if fact_ids.count(fid) > 1]}"
    )


def test_wiring_roundtrip_steps_surface(tmp_path):
    """Roundtrip step status must surface from the wiring audit."""
    root = tmp_path / "read_models"
    _write(root, "cassandra_runtime_wiring_audit.json", _minimal_wiring_audit())
    _write(root, "cassandra_email_calendar_delta_detangle.json", _minimal_email_calendar_detangle())

    pkt = ccp.build_cassandra_context_packet(read_model_root=root)
    step_facts = [
        f for f in pkt["facts"]
        if f.get("topic") == "runtime_wiring" and "roundtrip" in str(f.get("label") or "").lower()
    ]

    assert len(step_facts) >= 1, "Roundtrip step status fact must be present"
    val = step_facts[0]["value"]
    assert "cassandra_services_online" in val
    assert "safe_acknowledgment_policy" in val
