import os
import sqlite3
import json
import pytest
from unittest.mock import patch, MagicMock
from scripts.generate_agent_context import AgentContextAssembler

TEST_DB_PATH = "tests/test_substrate_ledger.sqlite"

@pytest.fixture
def clean_db():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE events (
            event_id TEXT PRIMARY KEY,
            ts TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor TEXT NOT NULL,
            operator_visible_summary TEXT
        )
    """)
    conn.commit()
    conn.close()
    yield TEST_DB_PATH
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

def test_cassandra_packet_generation_basic():
    assembler = AgentContextAssembler(db_path="non_existent.sqlite")
    packet = assembler.assemble_cassandra_orientation_packet()

    assert packet["substrate_version"] == "v0"
    assert packet["actor_id"] == "cassandra"
    assert packet["purpose"] == "orientation_only"
    assert "source_commit" in packet
    assert packet["verified_capability_types"] == [
        "action_intent_gate_receipt",
        "approval_request_record",
        "approval_log_entry",
        "orientation_snapshot_receipt",
        "test_proof_receipt"
    ]
    assert packet["verified_receipt_rows"] == []
    assert packet["authority"]["execution_authority"] == 0
    assert packet["authority"]["context_packet_only"] is True

def test_cassandra_packet_includes_receipts(clean_db):
    # Insert mock receipts
    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO events (event_id, ts, event_type, actor, operator_visible_summary)
        VALUES (?, ?, ?, ?, ?)
    """, ("ev1", "2026-05-11T10:00:00", "action_intent_gate_receipt", "tester", "Gate Pass"))
    cursor.execute("""
        INSERT INTO events (event_id, ts, event_type, actor, operator_visible_summary)
        VALUES (?, ?, ?, ?, ?)
    """, ("ev2", "2026-05-11T10:05:00", "approval_request_record", "tester", "Requesting Approval"))
    cursor.execute("""
        INSERT INTO events (event_id, ts, event_type, actor, operator_visible_summary)
        VALUES (?, ?, ?, ?, ?)
    """, ("ev3", "2026-05-11T10:10:00", "approval_log_entry", "tester", "Approved"))
    cursor.execute("""
        INSERT INTO events (event_id, ts, event_type, actor, operator_visible_summary)
        VALUES (?, ?, ?, ?, ?)
    """, ("ev4", "2026-05-11T10:15:00", "orientation_snapshot_receipt", "tester", "Snapshot"))
    cursor.execute("""
        INSERT INTO events (event_id, ts, event_type, actor, operator_visible_summary)
        VALUES (?, ?, ?, ?, ?)
    """, ("ev5", "2026-05-11T10:20:00", "test_proof_receipt", "tester", "Proof"))
    conn.commit()
    conn.close()

    assembler = AgentContextAssembler(db_path=clean_db)
    packet = assembler.assemble_cassandra_orientation_packet()

    rows = packet["verified_receipt_rows"]
    assert len(rows) == 5

    # Ordered by ts DESC in the query
    assert rows[0]["receipt_type"] == "test_proof_receipt"
    assert rows[1]["receipt_type"] == "orientation_snapshot_receipt"
    assert rows[2]["receipt_type"] == "approval_log_entry"
    assert rows[3]["receipt_type"] == "approval_request_record"
    assert rows[4]["receipt_type"] == "action_intent_gate_receipt"

    # Check truth labels
    assert rows[4]["truth"] == "gate/evaluation handling recorded only"
    assert rows[3]["truth"] == "approval request formally recorded only"
    assert rows[3]["decision"] is False
    assert rows[2]["truth"] == "approval decision recorded only"
    assert rows[1]["truth"] == "orientation terrain recorded only"
    assert rows[0]["truth"] == "test/proof terrain recorded only"

    # Check non-execution
    for r in rows:
        assert r["execution"] is False

def test_cassandra_packet_enforces_boundaries():
    assembler = AgentContextAssembler(db_path="non_existent.sqlite")
    packet = assembler.assemble_cassandra_orientation_packet()

    blocked = packet["blocked_context"]
    assert blocked["gmail"] is True
    assert blocked["pii"] is True
    assert blocked["outreach"] is True
    assert blocked["send_authority"] is True
    assert blocked["runtime_execution"] is True
    assert blocked["guardian_runtime_action"] is True
    assert blocked["hermes_runtime_action"] is True

    authority = packet["authority"]
    assert authority["execution_authority"] == 0
    assert authority["mutation_authority"] == 0

@patch("subprocess.check_output")
def test_git_head_retrieval(mock_git):
    mock_git.return_value = "deadbeef1234\n"
    assembler = AgentContextAssembler()
    assert assembler.get_git_head() == "deadbeef1234"

def test_chief_packet_generation_basic():
    assembler = AgentContextAssembler(db_path="non_existent.sqlite")
    packet = assembler.assemble_chief_operational_packet()

    assert packet["substrate_version"] == "v0"
    assert packet["actor_id"] == "chief"
    assert packet["purpose"] == "operational_review_only"
    assert "source_commit" in packet
    assert packet["verified_capability_types"] == [
        "action_intent_gate_receipt",
        "approval_request_record",
        "approval_log_entry",
        "orientation_snapshot_receipt",
        "test_proof_receipt"
    ]
    assert packet["verified_receipt_rows"] == []
    assert packet["operational_summary"]["pending_approval_requests_count"] == 0
    assert packet["operational_summary"]["latest_recorded_gate_evaluation"] is None

    # Authority check
    assert packet["authority"]["execution_authority"] == 0
    assert packet["authority"]["mutation_authority"] == 0
    assert packet["authority"]["approval_authority"] == 0
    assert packet["authority"]["context_packet_only"] is True
    assert packet["authority"]["recommendation_only"] is True

def test_chief_packet_operational_summary(clean_db):
    # Insert mock receipts
    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO events (event_id, ts, event_type, actor, operator_visible_summary)
        VALUES (?, ?, ?, ?, ?)
    """, ("ev1", "2026-05-11T10:00:00", "action_intent_gate_receipt", "tester", "Gate Pass"))
    cursor.execute("""
        INSERT INTO events (event_id, ts, event_type, actor, operator_visible_summary)
        VALUES (?, ?, ?, ?, ?)
    """, ("ev2", "2026-05-11T10:05:00", "approval_request_record", "tester", "Request 1"))
    cursor.execute("""
        INSERT INTO events (event_id, ts, event_type, actor, operator_visible_summary)
        VALUES (?, ?, ?, ?, ?)
    """, ("ev3", "2026-05-11T10:10:00", "approval_request_record", "tester", "Request 2"))
    conn.commit()
    conn.close()

    assembler = AgentContextAssembler(db_path=clean_db)
    packet = assembler.assemble_chief_operational_packet()

    summary = packet["operational_summary"]
    assert summary["pending_approval_requests_count"] == 2
    assert summary["latest_recorded_gate_evaluation"] == "Gate Pass"

def test_chief_packet_enforces_boundaries():
    assembler = AgentContextAssembler(db_path="non_existent.sqlite")
    packet = assembler.assemble_chief_operational_packet()

    blocked = packet["blocked_context"]
    assert blocked["gmail"] is True
    assert blocked["pii"] is True
    assert blocked["outreach"] is True
    assert blocked["send_authority"] is True
    assert blocked["runtime_execution"] is True
    assert blocked["runtime_mutation"] is True
    assert blocked["guardian_runtime_action"] is True
    assert blocked["hermes_runtime_action"] is True
    assert blocked["live_service_status"] is True
    assert blocked["self_permission_expansion"] is True

    allowed = packet["allowed_context"]
    assert allowed["receipt_spine_status"] is True
    assert allowed["approval_request_review"] is True
    assert allowed["approval_decision_review"] is True
    assert allowed["gate_evaluation_review"] is True
    assert allowed["safe_next_step_recommendation"] is True

def test_guardian_packet_generation_basic():
    assembler = AgentContextAssembler(db_path="non_existent.sqlite")
    packet = assembler.assemble_guardian_safety_packet()

    assert packet["substrate_version"] == "v0"
    assert packet["actor_id"] == "guardian"
    assert packet["purpose"] == "safety_inspection_only"
    assert "source_commit" in packet
    assert packet["verified_capability_types"] == [
        "action_intent_gate_receipt",
        "approval_request_record",
        "approval_log_entry",
        "orientation_snapshot_receipt",
        "test_proof_receipt"
    ]
    assert packet["verified_receipt_rows"] == []
    assert packet["safety_policy_summary"]["pending_approval_requests_count"] == 0
    assert packet["safety_policy_summary"]["latest_safety_decision_timestamp"] is None
    # active_hard_t2_rule_count should be at least 20 based on chief_approval_policy.py
    assert packet["safety_policy_summary"]["active_hard_t2_rule_count"] >= 20

    # Authority check
    assert packet["authority"]["execution_authority"] == 0
    assert packet["authority"]["mutation_authority"] == 0
    assert packet["authority"]["approval_authority"] == 0
    assert packet["authority"]["denial_authority"] == 0
    assert packet["authority"]["routing_authority"] == 0
    assert packet["authority"]["context_packet_only"] is True
    assert packet["authority"]["inspection_only"] is True

def test_guardian_packet_safety_summary(clean_db):
    # Insert mock receipts
    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO events (event_id, ts, event_type, actor, operator_visible_summary)
        VALUES (?, ?, ?, ?, ?)
    """, ("ev1", "2026-05-11T10:00:00", "approval_log_entry", "tester", "Approved"))
    cursor.execute("""
        INSERT INTO events (event_id, ts, event_type, actor, operator_visible_summary)
        VALUES (?, ?, ?, ?, ?)
    """, ("ev2", "2026-05-11T10:05:00", "approval_request_record", "tester", "Request 1"))
    conn.commit()
    conn.close()

    assembler = AgentContextAssembler(db_path=clean_db)
    packet = assembler.assemble_guardian_safety_packet()

    summary = packet["safety_policy_summary"]
    assert summary["pending_approval_requests_count"] == 1
    assert summary["latest_safety_decision_timestamp"] == "2026-05-11T10:00:00"

def test_guardian_packet_enforces_boundaries():
    assembler = AgentContextAssembler(db_path="non_existent.sqlite")
    packet = assembler.assemble_guardian_safety_packet()

    blocked = packet["blocked_context"]
    assert blocked["gmail"] is True
    assert blocked["pii"] is True
    assert blocked["outreach"] is True
    assert blocked["send_authority"] is True
    assert blocked["runtime_execution"] is True
    assert blocked["runtime_mutation"] is True
    assert blocked["guardian_runtime_action"] is True
    assert blocked["chief_operational_authority"] is True
    assert blocked["cassandra_orientation_authority"] is True
    assert blocked["hermes_runtime_action"] is True
    assert blocked["live_service_status"] is True
    assert blocked["self_permission_expansion"] is True

    allowed = packet["allowed_context"]
    assert allowed["safety_gate_inspection"] is True
    assert allowed["policy_matching_review"] is True
    assert allowed["approval_request_review"] is True
    assert allowed["approval_decision_review"] is True
    assert allowed["truth_label_verification"] is True

def test_niles_packet_generation_basic():
    assembler = AgentContextAssembler(db_path="non_existent.sqlite")
    packet = assembler.assemble_niles_producer_packet()

    assert packet["substrate_version"] == "v0"
    assert packet["actor_id"] == "niles"
    assert packet["purpose"] == "creative_orientation_only"
    assert "source_commit" in packet

    # Producer Context
    prod = packet["producer_context"]
    assert len(prod["six_pillars"]) == 6
    assert "Rhythmic Spine" in prod["six_pillars"]
    assert "Reference Extraction Principle" in prod["reference_extraction_principle"]
    assert "lyric" in prod["artifact_types"]
    assert "add_arrival_point_without_clutter" in prod["suggested_moves"]

    # Authority check
    auth = packet["authority"]
    assert auth["execution_authority"] == 0
    assert auth["mutation_authority"] == 0
    assert auth["approval_authority"] == 0
    assert auth["daw_execution_authority"] == 0
    assert auth["hardware_authority"] == 0
    assert auth["recommendation_only"] is True
    assert auth["context_packet_only"] is True

def test_niles_packet_enforces_boundaries():
    assembler = AgentContextAssembler(db_path="non_existent.sqlite")
    packet = assembler.assemble_niles_producer_packet()

    blocked = packet["blocked_context"]
    assert blocked["daw_live_state"] is True
    assert blocked["hardware_live_state"] is True
    assert blocked["ableton_execution"] is True
    assert blocked["logic_execution"] is True
    assert blocked["audio_analysis_claims"] is True
    assert blocked["file_mutation"] is True
    assert blocked["gmail"] is True
    assert blocked["pii"] is True
    assert blocked["outreach"] is True
    assert blocked["legal_sensitive_data"] is True
    assert blocked["business_sensitive_data"] is True
    assert blocked["runtime_execution"] is True
    assert blocked["runtime_mutation"] is True
    assert blocked["send_authority"] is True
    assert blocked["self_permission_expansion"] is True

    allowed = packet["allowed_context"]
    assert allowed["creative_critique"] is True
    assert allowed["pillar_alignment_review"] is True
    assert allowed["reference_extraction_analysis"] is True
    assert allowed["artifact_review"] is True
    assert allowed["taste_governor_framing"] is True

def test_hermes_packet_generation_basic():
    assembler = AgentContextAssembler(db_path="non_existent.sqlite")
    packet = assembler.assemble_hermes_advisory_packet()

    assert packet["substrate_version"] == "v0"
    assert packet["actor_id"] == "hermes"
    assert packet["purpose"] == "advisory_review_only"
    assert "source_commit" in packet
    
    # Authority check
    auth = packet["authority"]
    assert auth["execution_authority"] == 0
    assert auth["mutation_authority"] == 0
    assert auth["approval_authority"] == 0
    assert auth["canonical_write_authority"] == 0
    assert auth["queue_mutation_authority"] == 0
    assert auth["tool_execution_authority"] == 0
    assert auth["recommendation_only"] is True
    assert auth["advisory_only"] is True
    assert auth["context_packet_only"] is True

def test_hermes_packet_enforces_boundaries():
    assembler = AgentContextAssembler(db_path="non_existent.sqlite")
    packet = assembler.assemble_hermes_advisory_packet()

    blocked = packet["blocked_context"]
    assert blocked["gmail"] is True
    assert blocked["pii"] is True
    assert blocked["outreach"] is True
    assert blocked["legal_sensitive_data"] is True
    assert blocked["daw_live_state"] is True
    assert blocked["runtime_execution"] is True
    assert blocked["runtime_mutation"] is True
    assert blocked["guardian_runtime_action"] is True
    assert blocked["chief_runtime_action"] is True
    assert blocked["cassandra_runtime_action"] is True
    assert blocked["niles_runtime_action"] is True
    assert blocked["hermes_runtime_action"] is True
    assert blocked["sidecar_runtime_access"] is True
    assert blocked["canonical_write"] is True
    assert blocked["queue_mutation"] is True
    assert blocked["tool_execution"] is True
    assert blocked["shared_memory_expansion"] is True
    assert blocked["self_permission_expansion"] is True
    assert blocked["send_authority"] is True

    allowed = packet["allowed_context"]
    assert allowed["advisory_review"] is True
    assert allowed["systems_synthesis"] is True
    assert allowed["pattern_discovery"] is True
    assert allowed["non_canonical_proposal"] is True
    assert allowed["bounded_critique"] is True
