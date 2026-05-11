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
    assert packet["verified_receipts"] == []
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
    conn.commit()
    conn.close()

    assembler = AgentContextAssembler(db_path=clean_db)
    packet = assembler.assemble_cassandra_orientation_packet()
    
    receipts = packet["verified_receipts"]
    assert len(receipts) == 3
    
    # Ordered by ts DESC in the query
    assert receipts[0]["receipt_type"] == "approval_log_entry"
    assert receipts[1]["receipt_type"] == "approval_request_record"
    assert receipts[2]["receipt_type"] == "action_intent_gate_receipt"
    
    # Check truth labels
    assert receipts[2]["truth"] == "gate/evaluation handling recorded only"
    assert receipts[1]["truth"] == "approval request formally recorded only"
    assert receipts[1]["decision"] is False
    assert receipts[0]["truth"] == "approval decision recorded only"
    
    # Check non-execution
    for r in receipts:
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
