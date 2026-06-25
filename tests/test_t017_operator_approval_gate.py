import os
from pathlib import Path
import sqlite3
import pytest

from agent_lane_registry import seed_agent_lane_registry
from ar_counterparty_contact_operations import _connect
from maestro_context_packet import build_maestro_context_packet

def test_t017_operator_approval_gate_defaults(tmp_path):
    # 1. Verify Agent Lane Defaults for Autonomous Writes / Sends
    registry_db = tmp_path / "agent_registry.sqlite"
    seed_agent_lane_registry(db_path=registry_db)
    
    with _connect(registry_db) as conn:
        rows = conn.execute("SELECT * FROM agent_lanes").fetchall()
        for row in rows:
            assert row["can_execute"] == 0, f"{row['agent_id']} should not default to execute"
            assert row["can_bypass_approval"] == 0, f"{row['agent_id']} should not bypass approval"
            assert row["can_call_network"] == 0, f"{row['agent_id']} should not call network"
            assert row["can_run_tools"] == 0, f"{row['agent_id']} should not run tools"
            assert row["can_call_models"] == 0, f"{row['agent_id']} should not call models automatically"
            assert row["runtime_authority"] == 0
            assert row["client_deployment_authority"] == 0

    # 2. Verify Context Packet Safe States (Send Hold, Money Movement Block)
    packet = build_maestro_context_packet(
        question="Should we pay Capital Hilton?",
        read_model_root=tmp_path,
        require_real_truth=False
    )
    
    bounds = packet.get("bounds", {})
    assert bounds.get("send_hold_absolute") is True
    assert bounds.get("outbound_send_allowed") is False
    assert bounds.get("money_movement_allowed") is False
    assert bounds.get("ledger_mutation_allowed") is False
    
    # Verify the packet text explicitly includes the send hold and mutation blocks
    packet_text = packet.get("packet_text", "")
    assert "SEND_HOLD absolute: True" in packet_text
    assert "Outbound send allowed: False" in packet_text
    assert "Money movement allowed: False" in packet_text
    assert "Ledger mutation allowed: False" in packet_text
