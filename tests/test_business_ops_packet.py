import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cassandra_brain
from business_ops_packet import assemble_business_ops_packet, BusinessOpsPacket
from business_ops_intent import IntentFrame

def test_assemble_business_ops_packet_basic():
    # Test with email search intent
    packet = assemble_business_ops_packet(
        query="check my email",
        actor_name="cassandra",
        intent=IntentFrame("email_search", "read_only", "email", 0.9)
    )
    
    assert packet.intent_name == "email_search"
    assert packet.actor_name == "cassandra"
    # Should have email capabilities
    capability_names = [c.name for c in packet.permitted_capabilities]
    assert "gmail_metadata" in capability_names or "email_draft" in capability_names
    # Should have logging
    assert "ops_log_write" in capability_names

def test_assemble_business_ops_packet_no_intent():
    # Test with no intent
    packet = assemble_business_ops_packet(
        query="hello",
        actor_name="cassandra",
        intent=IntentFrame("none", "none", "none", 0.0)
    )
    
    assert packet.intent_name == "none"
    # Should only have logging or read-only generic caps
    capability_names = [c.name for c in packet.permitted_capabilities]
    assert "gmail_metadata" not in capability_names
    assert "calendar_read" not in capability_names
    assert "ops_notes_read" in capability_names or "ops_log_write" in capability_names

def test_assemble_business_ops_packet_monitored_email():
    # Test with monitored_email_conversation intent
    packet = assemble_business_ops_packet(
        query="monitored_email_conversation",
        actor_name="cassandra"
    )

    assert packet.intent_name == "monitored_email_conversation"
    assert packet.actor_name == "cassandra"

    capability_names = [c.name for c in packet.permitted_capabilities]
    # Should have read/draft
    assert "gmail_metadata" in capability_names
    assert "email_draft" in capability_names
    # Should NOT have send
    assert "email_send" not in capability_names

    # Safety posture checks
    assert packet.execution_authority is False
    assert packet.approval_required is True
    assert packet.action_status == "draft_only_until_guardian_approval"

@pytest.fixture
def mock_deps(monkeypatch):
    # Mock broker
    mock_broker = MagicMock()
    mock_broker.return_value = {"ok": True, "data": [], "error": ""}
    import google_access_broker
    monkeypatch.setattr(google_access_broker, "call", mock_broker)
    monkeypatch.setattr(cassandra_brain, "broker_call", mock_broker)

    # Mock _log_conversation to capture the route and metadata
    captured_logs = []
    def fake_log(text, replies, route="llm", metadata=None):
        captured_logs.append({"text": text, "route": route, "metadata": metadata})

    monkeypatch.setattr(cassandra_brain, "_log_conversation", fake_log)

    # Mock LLM call to avoid actual overhead
    monkeypatch.setattr(cassandra_brain, "_call", lambda prompt, **kwargs: "Mocked LLM reply")

    # Mock state
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE))
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None)

    return captured_logs

def test_cassandra_handle_builds_ops_packet(mock_deps):
    # Test that handle builds and logs the packet
    cassandra_brain.handle("check my email")
    
    # Check the first log entry
    assert len(mock_deps) > 0
    metadata = mock_deps[0]["metadata"]
    assert "ops_packet" in metadata
    packet_dict = metadata["ops_packet"]
    assert packet_dict["intent_name"] == "email_search"
    assert "gmail_metadata" in packet_dict["permitted_capability_names"]

def test_cassandra_handle_denies_unauthorized_intent(mock_deps):
    # Test that a generic query doesn't grant email capability
    cassandra_brain.handle("What is the weather?")
    
    assert len(mock_deps) > 0
    metadata = mock_deps[-1]["metadata"] # Use last log entry if multiple
    assert "ops_packet" in metadata
    packet_dict = metadata["ops_packet"]
    assert "gmail_metadata" not in packet_dict["permitted_capability_names"]

def test_cassandra_handle_calendar_intent(mock_deps):
    # Test that calendar intent is correctly handled
    cassandra_brain.handle("what's on my calendar?")
    
    assert len(mock_deps) > 0
    metadata = mock_deps[0]["metadata"]
    assert "ops_packet" in metadata
    packet_dict = metadata["ops_packet"]
    assert packet_dict["intent_name"] == "calendar_read"
    assert "calendar_read" in packet_dict["permitted_capability_names"]

def test_cassandra_handle_contacts_intent(mock_deps):
    # Test that contacts intent is correctly handled
    cassandra_brain.handle("what's the number for Glenn?")
    
    assert len(mock_deps) > 0
    metadata = mock_deps[0]["metadata"]
    assert "ops_packet" in metadata
    packet_dict = metadata["ops_packet"]
    assert packet_dict["intent_name"] == "contacts_read"
    assert "contacts_read" in packet_dict["permitted_capability_names"]
