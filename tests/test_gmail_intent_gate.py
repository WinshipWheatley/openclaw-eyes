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

@pytest.fixture
def mock_deps(monkeypatch):
    # Mock broker
    mock_broker = MagicMock()
    mock_broker.return_value = {"ok": True, "data": [], "error": ""}
    import google_access_broker
    monkeypatch.setattr(google_access_broker, "call", mock_broker)
    monkeypatch.setattr(cassandra_brain, "broker_call", mock_broker)

    # Mock _log_conversation to capture the route
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

def test_who_owes_me_money_answers_from_money_truth_not_gmail(mock_broker):
    # Task 140: a read-only money question is answered from the ONE money truth
    # (receivables_month_bounded) — it is not Gmail work and must not poll.
    cassandra_brain.handle("Who owes me money?")
    gmail_calls = [call for call in mock_broker.call_args_list if "gmail" in call[0][1]]
    assert len(gmail_calls) == 0

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

def test_check_my_email_route(mock_deps):
    cassandra_brain.handle("check my email")
    routes = [log["route"] for log in mock_deps]
    assert "payment_verify" not in routes

def test_hilton_payment_route(mock_deps):
    cassandra_brain.handle("Did the Hilton payment come through?")
    routes = [log["route"] for log in mock_deps]
    assert "payment_verify" in routes

def test_who_owes_me_money_route(mock_deps):
    # Task 140: money-class read questions ride the money_truth lane,
    # never payment_verify (that lane keeps only arrival verification).
    cassandra_brain.handle("Who owes me money?")
    routes = [log["route"] for log in mock_deps]
    assert "money_truth" in routes
    assert "payment_verify" not in routes

def test_find_emails_from_experian_route(mock_deps):
    cassandra_brain.handle("Find emails from Experian")
    routes = [log["route"] for log in mock_deps]
    assert "payment_verify" not in routes
