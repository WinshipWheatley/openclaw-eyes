import os
from pathlib import Path
import sqlite3
import pytest

from agent_lane_registry import seed_agent_lane_registry
from ar_counterparty_contact_operations import _connect
from maestro_context_packet import build_maestro_context_packet

class ApprovalGateError(Exception):
    pass

def check_operator_approval_gate(packet):
    # Dynamic gate simulating actual runtime enforcement
    bounds = packet.get("bounds", {})
    if bounds.get("send_hold_absolute"):
        raise ApprovalGateError("Operator approval required: SEND_HOLD_ABSOLUTE is enforced.")
    if not bounds.get("outbound_send_allowed"):
        raise ApprovalGateError("Operator approval required: outbound_send_allowed is False.")
    if not bounds.get("ledger_mutation_allowed"):
        raise ApprovalGateError("Operator approval required: ledger_mutation_allowed is False.")

def test_t017_operator_approval_gate_dynamic(tmp_path, monkeypatch):
    # 1. Feature disabled by default
    monkeypatch.delenv("OPENCLAW_FEATURE_CAPITAL_HILTON_AR", raising=False)
    packet_disabled = build_maestro_context_packet(
        question="Should we pay Capital Hilton?",
        read_model_root=tmp_path,
        require_real_truth=False
    )
    assert packet_disabled["status"] == "READY"
    assert "deterministic_response" not in packet_disabled

    # 2. Verify dynamic gate prevents autonomous actions
    registry_db = tmp_path / "agent_registry.sqlite"
    seed_agent_lane_registry(db_path=registry_db)
    
    with _connect(registry_db) as conn:
        rows = conn.execute("SELECT * FROM agent_lanes").fetchall()
        for row in rows:
            assert row["can_execute"] == 0
            assert row["can_bypass_approval"] == 0
            assert row["can_call_network"] == 0

    packet = build_maestro_context_packet(
        question="Should we pay Capital Hilton?",
        read_model_root=tmp_path,
        require_real_truth=False
    )

    # Prove that the gate actively raises exceptions and blocks execution
    with pytest.raises(ApprovalGateError, match="SEND_HOLD_ABSOLUTE is enforced"):
        check_operator_approval_gate(packet)

    # Even if send_hold_absolute was somehow bypassed, the next gate catches it
    packet["bounds"]["send_hold_absolute"] = False
    with pytest.raises(ApprovalGateError, match="outbound_send_allowed is False"):
        check_operator_approval_gate(packet)

    packet["bounds"]["outbound_send_allowed"] = True
    with pytest.raises(ApprovalGateError, match="ledger_mutation_allowed is False"):
        check_operator_approval_gate(packet)
