import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cassandra_brain

@pytest.fixture
def mock_broker(monkeypatch):
    mock = MagicMock()
    mock.return_value = {"ok": True, "data": [], "error": ""}
    # Patch the actual module that is being imported
    import google_access_broker
    monkeypatch.setattr(google_access_broker, "call", mock)
    # Also patch the reference in cassandra_brain just in case
    monkeypatch.setattr(cassandra_brain, "broker_call", mock)
    return mock

def test_math_prompt_no_gmail_polling(mock_broker):
    cassandra_brain.handle("What is 2+2?")
    # broker_call should NOT have been called with gmail metadata or unread count
    for call in mock_broker.call_args_list:
        args, kwargs = call
        capability = args[1]
        assert "gmail" not in capability
        assert "contacts" not in capability

def test_status_check_no_gmail_polling(mock_broker):
    cassandra_brain.handle("status check")
    for call in mock_broker.call_args_list:
        args, kwargs = call
        capability = args[1]
        assert "gmail" not in capability

def test_llm_health_check_no_gmail_polling(mock_broker):
    cassandra_brain.handle("LLM health check")
    for call in mock_broker.call_args_list:
        args, kwargs = call
        capability = args[1]
        assert "gmail" not in capability

def test_explicit_no_gmail_denial(mock_broker):
    # This prompt would normally trigger gmail (contains 'email')
    # but the 'no gmail' phrase should block it.
    cassandra_brain.handle("Cassandra, text only, no voice, no tools, no Gmail. Did I get any email?")
    for call in mock_broker.call_args_list:
        args, kwargs = call
        capability = args[1]
        assert "gmail" not in capability

def test_find_emails_allows_gmail_polling(mock_broker):
    cassandra_brain.handle("Find emails from Experian")
    # Should have polled gmail
    gmail_calls = [call for call in mock_broker.call_args_list if "gmail" in call[0][1]]
    assert len(gmail_calls) > 0

def test_did_i_get_email_allows_gmail_polling(mock_broker):
    cassandra_brain.handle("Did I get an email from Henry?")
    gmail_calls = [call for call in mock_broker.call_args_list if "gmail" in call[0][1]]
    assert len(gmail_calls) > 0

def test_who_owes_me_money_allows_payment_polling(mock_broker):
    cassandra_brain.handle("Who owes me money?")
    # This triggers payment_verify which calls gmail.read.metadata
    gmail_calls = [call for call in mock_broker.call_args_list if "gmail" in call[0][1]]
    assert len(gmail_calls) > 0

def test_generic_check_denies_gmail(mock_broker):
    cassandra_brain.handle("can you check this?")
    for call in mock_broker.call_args_list:
        args, kwargs = call
        capability = args[1]
        assert "gmail" not in capability

def test_check_my_email_allows_gmail(mock_broker):
    cassandra_brain.handle("check my email")
    gmail_calls = [call for call in mock_broker.call_args_list if "gmail" in call[0][1]]
    assert len(gmail_calls) > 0

def test_scheduled_triage_override(mock_broker):
    # Test internal helper
    decision = cassandra_brain.decide_gmail_intent("any prompt", scheduled_triage=True)
    assert decision.allowed
    assert decision.category == "scheduled_triage"
