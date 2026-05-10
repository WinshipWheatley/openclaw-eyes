#!/usr/bin/env python3
"""Integration tests for the inner-circle correspondence lane:
contact resolution → topic gate → dispatch → truthful reply.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure project root and tools are in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import cassandra_brain as cb
import cassandra_capability as cap

@pytest.fixture(autouse=True)
def stub_side_effects(monkeypatch, tmp_path):
    """Stub all external I/O so tests run offline."""
    # Stub LLM call — make it smart enough to respect the capability context
    def _smart_call(prompt, deep, cloud_ok=False):
        if "pii_vault: NOT CONNECTED" in prompt:
            return "PII vault is not connected, so I can't look up that information."
        if "future_exec: NOT CONNECTED" in prompt:
            return "I'm not able to set reminders autonomously from here."
        return "TEST_LLM_REPLY"
    monkeypatch.setattr(cb, "_call", _smart_call)
    
    # Stub context fetchers
    monkeypatch.setattr(cb, "_fetch_calendar_context", lambda query, **kwargs: "", raising=False)
    monkeypatch.setattr(cb, "_fetch_gmail_context", lambda query, **kwargs: "", raising=False)
    monkeypatch.setattr(cb, "_fetch_contacts_context", lambda query, **kwargs: "", raising=False)
    
    # Stub handlers that aren't under test
    # (using raising=False in case they are renamed or moved)
    monkeypatch.setattr(cb, "_handle_weather_request", lambda text: None, raising=False)
    monkeypatch.setattr(cb, "_handle_secure_lookup_request", lambda text: None, raising=False)
    monkeypatch.setattr(cb, "_handle_file_verification_request", lambda text: None, raising=False)
    # Keep broad scheduling language from dropping into live calendar-create extraction.
    monkeypatch.setattr(cb, "_handle_calendar_create", lambda text: None, raising=False)
    
    # Route capture
    captured_routes = []
    def _capture_route(user_text, replies, route="llm"):
        captured_routes.append(route)
    monkeypatch.setattr(cb, "_log_conversation", _capture_route)
    
    # Stub chief_notify to capture calls without sending
    notify_calls = []
    def _fake_notify_send(text, **kw):
        notify_calls.append(text)
    monkeypatch.setattr("chief_notify.send", _fake_notify_send)
    
    # Redirect correspondence log to temp dir
    log_file = tmp_path / "correspondence.jsonl"
    monkeypatch.setattr(cb, "_CORRESPONDENCE_LOG", log_file)
    monkeypatch.setattr(cb, "_FOLLOWUP_LOG", tmp_path / "pending_followups.jsonl")
    
    # Ensure state file is in temp dir too if possible, 
    # but at least stub save_state to avoid real writes
    monkeypatch.setattr(cb, "save_state", lambda state: None)

    # Bypass the grounded email review gate — its behaviour is tested in test_send_truth.py.
    # These integration tests focus on the topic gate, identity resolution, and correspondence log.
    monkeypatch.setattr(
        cb,
        "_review_grounded_email_draft",
        lambda *, recipient_name, recipient_email, original_message, draft_subject, draft_body: {
            "status": "allowed",
            "subject": draft_subject,
            "body": draft_body,
            "detail": "test bypass",
            "queued_task_name": None,
            "user_reply": "",
        },
        raising=False,
    )

    # Mock broker call to avoid real network/subprocess and still let the
    # email flow resolve contacts before send.
    broker_overrides = {}

    def _fake_broker_call(_agent, capability, payload):
        override = broker_overrides.get(capability)
        if isinstance(override, Exception):
            raise override
        if callable(override):
            return override(_agent, capability, payload)
        if override is not None:
            return override
        if capability == "google.contacts.read":
            query = str((payload or {}).get("query") or "recipient")
            local_part = query.split()[0].lower()
            return {
                "ok": True,
                "data": [{"display_name": query, "email": f"{local_part}@example.com"}],
            }
        if capability == "google.gmail.draft.create":
            return {"ok": True, "data": {"draft_id": "d1", "message_id": "m1", "thread_id": "t1"}}
        return {"ok": True, "data": []}

    mock_broker = MagicMock(side_effect=_fake_broker_call)
    monkeypatch.setattr(cb, "broker_call", mock_broker, raising=False)
    monkeypatch.setattr("google_access_broker.call", mock_broker)
    
    return {
        "routes": captured_routes, 
        "notify_calls": notify_calls, 
        "tmp_path": tmp_path,
        "mock_broker": mock_broker,
        "broker_overrides": broker_overrides,
    }


def _assert_last_route(stub_side_effects, expected_route):
    assert stub_side_effects["routes"], "expected at least one logged route"
    assert stub_side_effects["routes"][-1] == expected_route


def _read_correspondence_entries(tmp_path):
    log_file = tmp_path / "correspondence.jsonl"
    assert log_file.exists(), "expected correspondence log to be created"
    with log_file.open("r", encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]
    assert entries, "expected correspondence log to contain at least one entry"
    return entries

# ── Test Group A: Contact resolution and routing ──────────────────────────────

def test_a1_dad_identified_by_name():
    result = cb._find_designated_contact(sender_name="Henry Winship Wheatley III")
    assert result is not None
    assert result["nickname"] == "dad"
    assert result["tier"] == "inner_circle"

def test_a2_mom_identified_by_name():
    result = cb._find_designated_contact(sender_name="Susan Elizabeth Wheatley")
    assert result is not None
    assert result["nickname"] == "mom"
    assert result["tier"] == "inner_circle"

def test_a3_draper_identified_by_name():
    result = cb._find_designated_contact(sender_name="Draper Carter")
    assert result is not None
    assert result["nickname"] == "draper"
    assert result["tier"] == "inner_circle"

def test_a4_unknown_sender_not_inner_circle():
    result = cb._find_designated_contact(sender_name="Random Stranger", sender_chat_id="999999")
    assert result is None
    assert not cb.is_designated_contact_sender(sender_name="Random Stranger", sender_chat_id="999999")

def test_a5_sampleclient_not_treated_as_inner_circle():
    result = cb._find_designated_contact(sender_name="Sarah Johansen")
    assert result is not None
    assert result["nickname"] == "sampleclient"
    assert result["tier"] == "client"  # Identified as client, not inner_circle

def test_a6_contact_identified_by_chat_id_when_pinned(monkeypatch):
    # Setup: Pin a chat ID for dad
    def mock_load_nicknames():
        return {
            "dad": {
                "name": "Henry Winship Wheatley III", 
                "tier": "inner_circle", 
                "telegram_chat_id": "11111"
            }
        }
    monkeypatch.setattr(cb, "_load_nicknames", mock_load_nicknames)
    
    result = cb._find_designated_contact(sender_name=None, sender_chat_id="11111")
    assert result is not None
    assert result["nickname"] == "dad"

# ── Test Group B: Topic-sensitivity gate integration ──────────────────────────

def test_b1_dad_allowed_topic_falls_through_to_handler(stub_side_effects):
    session = {"sender_name": "Henry Winship Wheatley III", "sender_chat_id": None, "skip_followup_check": True}
    # "Did the Hilton payment come through?" hits "financial" topic (allowed for dad)
    # It might fall through to financial_lookup or LLM
    reply = cb.handle("Did the Hilton payment come through?", session=session)
    assert reply
    assert "topic_gate_hold" not in stub_side_effects["routes"]
    assert "topic_gate_escalate" not in stub_side_effects["routes"]
    assert not stub_side_effects["notify_calls"]

def test_b2_mom_caution_topic_holds_for_winship(stub_side_effects):
    session = {"sender_name": "Susan Elizabeth Wheatley", "sender_chat_id": None, "skip_followup_check": True}
    # "How much did the Hilton gig pay?" hits "financial" topic (caution for mom)
    reply = cb.handle("How much did the Hilton gig pay?", session=session)
    assert any("verify with Winship" in r or "check with Winship" in r for r in reply)
    assert "topic_gate_hold" in stub_side_effects["routes"]
    assert len(stub_side_effects["notify_calls"]) >= 1
    assert "caution" in stub_side_effects["notify_calls"][0].lower()

def test_b3_dad_escalation_topic_escalates(stub_side_effects):
    session = {"sender_name": "Henry Winship Wheatley III", "sender_chat_id": None, "skip_followup_check": True}
    # "Tell Draper to call me" hits "action_on_behalf" topic (escalate)
    reply = cb.handle("Tell Draper to call me", session=session)
    assert any("Winship to authorize" in r or "flag it for him" in r for r in reply)
    assert "topic_gate_escalate" in stub_side_effects["routes"]
    assert len(stub_side_effects["notify_calls"]) >= 1
    assert "escalat" in stub_side_effects["notify_calls"][0].lower()

def test_b4_draper_allowed_operational_topic(stub_side_effects):
    session = {"sender_name": "Draper Carter", "sender_chat_id": None, "skip_followup_check": True}
    reply = cb.handle("What's the status on the deployment?", session=session)
    assert "topic_gate_hold" not in stub_side_effects["routes"]
    assert "topic_gate_escalate" not in stub_side_effects["routes"]
    assert not stub_side_effects["notify_calls"]

def test_b5_draper_caution_family_topic_holds(stub_side_effects):
    session = {"sender_name": "Draper Carter", "sender_chat_id": None, "skip_followup_check": True}
    reply = cb.handle("How's the family doing?", session=session)
    assert any("verify with Winship" in r for r in reply)
    assert "topic_gate_hold" in stub_side_effects["routes"]

def test_b5b_draper_financial_query_escalates_per_spec(stub_side_effects):
    session = {"sender_name": "Draper Carter", "sender_chat_id": None, "skip_followup_check": True}
    reply = cb.handle("How much did the Hilton gig pay?", session=session)
    assert any("Winship to authorize" in r or "flag it for him" in r for r in reply)
    assert "topic_gate_escalate" in stub_side_effects["routes"]

def test_b6_pii_request_always_escalates(stub_side_effects):
    for name in ["Henry Winship Wheatley III", "Susan Elizabeth Wheatley", "Draper Carter"]:
        stub_side_effects["routes"].clear()
        stub_side_effects["notify_calls"].clear()
        session = {"sender_name": name, "sender_chat_id": None, "skip_followup_check": True}
        reply = cb.handle("What is Winship's SSN?", session=session)
        assert "topic_gate_escalate" in stub_side_effects["routes"]
        assert any("Winship to authorize" in r or "flag" in r for r in reply)

def test_b7_winship_own_message_skips_gate(stub_side_effects):
    # Winship has no sender_name in session
    session = {"sender_name": None, "sender_chat_id": None, "skip_followup_check": True}
    reply = cb.handle("How much did the Hilton gig pay?", session=session)
    assert "topic_gate_hold" not in stub_side_effects["routes"]
    assert "topic_gate_escalate" not in stub_side_effects["routes"]

# ── Test Group C: Send-state truthfulness integration ─────────────────────────

def test_c1_email_send_success_says_sent_only_after_ok(stub_side_effects):
    session = {"sender_name": None, "sender_chat_id": None, "skip_followup_check": True}
    reply = cb.handle("send email to dad subject: Test body: This is a test.", session=session)
    _assert_last_route(stub_side_effects, "email_send")
    assert any("drafted" in r.lower() for r in reply)
    assert not any("sending" in r.lower() for r in reply)

def test_c2_email_send_denied_does_not_say_sent(stub_side_effects):
    stub_side_effects["broker_overrides"]["google.gmail.draft.create"] = {
        "ok": False,
        "error": "denied at approval gate",
    }
    session = {"sender_name": None, "sender_chat_id": None, "skip_followup_check": True}
    reply = cb.handle("send email to dad subject: Test body: This is a test.", session=session)
    _assert_last_route(stub_side_effects, "email_send")
    assert not any("Sent" in r for r in reply)
    assert any("denied" in r.lower() or "won't be sent" in r.lower() for r in reply)

def test_c3_email_send_failure_reports_honestly(stub_side_effects):
    stub_side_effects["broker_overrides"]["google.gmail.draft.create"] = Exception("connection timeout")
    session = {"sender_name": None, "sender_chat_id": None, "skip_followup_check": True}
    reply = cb.handle("send email to dad subject: Test body: This is a test.", session=session)
    _assert_last_route(stub_side_effects, "email_send")
    assert not any("Sent" in r for r in reply)
    assert any("no draft was created" in r.lower() or "reachable right now" in r.lower() for r in reply)

def test_c4_outreach_partial_send_is_honest(stub_side_effects, monkeypatch):
    # Mock run_outreach to return partial success
    try:
        monkeypatch.setattr("cassandra_outreach.run_outreach",
                            lambda *a, **k: [
                                {"nickname": "dad", "display_name": "Dad", "status": "draft"},
                                {"nickname": "mom", "display_name": "Mom", "status": "send_failed"},
                            ])
    except ImportError:
        pass

    session = {"sender_name": None, "sender_chat_id": None, "skip_followup_check": True}
    reply = cb.handle("send the intro emails", session=session)
    _assert_last_route(stub_side_effects, "outreach_email_draft")
    assert any("drafted for dad" in r.lower() for r in reply)
    assert any("didn't go through" in r.lower() for r in reply)

def test_c5_email_draft_prompt_does_not_say_sending(stub_side_effects):
    session = {"sender_name": None, "sender_chat_id": None, "skip_followup_check": True}
    # Incomplete prompt triggers draft/details prompt
    reply = cb.handle("send email to dad", session=session)
    _assert_last_route(stub_side_effects, "email_send")
    assert any("draft" in r.lower() for r in reply)
    assert not any("sending" in r.lower() for r in reply)

# ── Test Group D: Partial completion and disconnected capabilities ────────────

def test_d1_future_action_disconnected_honest_reply(stub_side_effects, monkeypatch):
    monkeypatch.setattr(cap, "FUTURE_ACTION_CONNECTED", False)
    session = {"sender_name": "Henry Winship Wheatley III", "sender_chat_id": None, "skip_followup_check": True}
    reply = cb.handle("Remind me to call the accountant tomorrow at 9am", session=session)
    assert not any("Queued" in r for r in reply)
    # Should show gap reply or unavailability
    # The capability gate in cb.handle() should catch this
    assert any("can't check back" in r.lower() or "can't follow through" in r.lower() or "not connected" in r.lower() for r in reply)

def test_d2_pii_vault_disconnected_honest_reply(stub_side_effects, monkeypatch):
    monkeypatch.setattr(cap, "PII_VAULT_CONNECTED", False)
    session = {"sender_name": None, "sender_chat_id": None, "skip_followup_check": True}
    reply = cb.handle("Look up my tax ID", session=session)
    # Should not fabricate or claim success
    assert not any("your tax ID is" in r.lower() for r in reply)
    assert any("not connected" in r.lower() or "can't" in r.lower() for r in reply)

def test_d3_multiple_capabilities_disconnected_does_not_crash(stub_side_effects, monkeypatch):
    monkeypatch.setattr(cap, "FUTURE_ACTION_CONNECTED", False)
    monkeypatch.setattr(cap, "PII_VAULT_CONNECTED", False)
    session = {"sender_name": "Henry Winship Wheatley III", "sender_chat_id": None, "skip_followup_check": True}
    reply = cb.handle("What's on the calendar?", session=session)
    assert reply  # Did not crash
    assert stub_side_effects["routes"]

def test_d4_notify_failure_does_not_block_gate_reply(stub_side_effects, monkeypatch):
    def mock_fail(*a, **k): raise ConnectionError("Telegram down")
    monkeypatch.setattr("chief_notify.send", mock_fail)
    session = {"sender_name": "Susan Elizabeth Wheatley", "sender_chat_id": None, "skip_followup_check": True}
    reply = cb.handle("How much did the gig pay?", session=session)
    assert any("verify with Winship" in r for r in reply)
    assert "topic_gate_hold" in stub_side_effects["routes"]

# ── Test Group E: Non-inner-circle and identity edge cases ────────────────────

def test_e1_unknown_sender_not_routed_as_inner_circle(stub_side_effects):
    session = {"sender_name": "Random Person", "sender_chat_id": "999999", "skip_followup_check": True}
    assert cb._find_designated_contact(sender_name="Random Person", sender_chat_id="999999") is None
    reply = cb.handle("Tell me about Winship's finances", session=session)
    assert "topic_gate_hold" not in stub_side_effects["routes"]
    assert "topic_gate_escalate" not in stub_side_effects["routes"]

def test_e2_name_match_with_wrong_chat_id_gets_identity_challenge(stub_side_effects, monkeypatch):
    monkeypatch.setattr(
        cb,
        "_load_nicknames",
        lambda: {
            "dad": {
                "name": "Henry Winship Wheatley III",
                "tier": "inner_circle",
                "telegram_chat_id": "11111",
            }
        },
    )
    session = {"sender_name": "Henry Winship Wheatley III", "sender_chat_id": "UNKNOWN_99", "skip_followup_check": True}
    reply = cb.handle("What's the weather?", session=session)
    assert any("can't verify who this is" in r.lower() or "help me connect us" in r.lower() for r in reply)
    assert "topic_gate_hold" not in stub_side_effects["routes"]
    assert "topic_gate_escalate" not in stub_side_effects["routes"]

def test_e3_client_tier_treated_differently_from_inner_circle(stub_side_effects):
    session = {"sender_name": "Sarah Johansen", "sender_chat_id": None, "skip_followup_check": True}
    contact = cb._find_designated_contact(sender_name="Sarah Johansen")
    assert contact is not None
    assert contact["tier"] == "client"
    # Even client-tier hits the gate if they are in _CONTACT_LANES
    # Sarah is "sampleclient" in contact_nicknames.json, but _find_designated_contact
    # uses the nickname as key. Sarah Johansen matches "sampleclient" entry.
    # But wait, Sarah Johansen is the "name" field, so it matches.
    reply = cb.handle("What's Winship's total revenue?", session=session)
    # Since "sampleclient" is NOT in _CONTACT_LANES (only dad, mom, draper are),
    # ccp.classify_topic will return "escalate" for any unknown nickname.
    assert "topic_gate_escalate" in stub_side_effects["routes"]

# ── Test Group F: Correspondence log verification ─────────────────────────────

def test_f1_correspondence_log_written_on_send_success(stub_side_effects):
    session = {"sender_name": None, "sender_chat_id": None, "skip_followup_check": True}

    cb.handle("send email to dad subject: Test body: This is a test.", session=session)
    _assert_last_route(stub_side_effects, "email_send")

    entries = _read_correspondence_entries(stub_side_effects["tmp_path"])
    assert entries[-1]["state"] == "draft"
    assert entries[-1]["route"] == "email_send"


def test_f4_outreach_draft_log_uses_truthful_route(stub_side_effects, monkeypatch):
    monkeypatch.setattr(
        "cassandra_outreach.run_outreach",
        lambda dry_run=False, mode="draft": [
            {"nickname": "draper", "display_name": "Draper", "status": "draft"},
        ],
    )
    session = {"sender_name": None, "sender_chat_id": None, "skip_followup_check": True}

    cb.handle("send the intro emails", session=session)

    entries = [json.loads(line) for line in stub_side_effects["tmp_path"].joinpath("correspondence.jsonl").read_text().splitlines()]
    assert entries[-1]["state"] == "draft"
    assert entries[-1]["route"] == "outreach_email_draft"

def test_f2_correspondence_log_written_on_send_failure(stub_side_effects):
    stub_side_effects["broker_overrides"]["google.gmail.draft.create"] = {"ok": False, "error": "smtp outage"}
    session = {"sender_name": None, "sender_chat_id": None, "skip_followup_check": True}

    cb.handle("send email to dad subject: Test body: This is a test.", session=session)
    _assert_last_route(stub_side_effects, "email_send")

    entries = _read_correspondence_entries(stub_side_effects["tmp_path"])
    assert entries[-1]["state"] == "send_failed"
    assert entries[-1]["detail"] == "smtp outage"


def test_f3_correspondence_log_marks_broker_exception_as_send_failed_per_spec(stub_side_effects):
    stub_side_effects["broker_overrides"]["google.gmail.draft.create"] = Exception("connection timeout")
    session = {"sender_name": None, "sender_chat_id": None, "skip_followup_check": True}

    cb.handle("send email to dad subject: Test body: This is a test.", session=session)
    _assert_last_route(stub_side_effects, "email_send")

    entries = _read_correspondence_entries(stub_side_effects["tmp_path"])
    assert entries[-1]["state"] == "send_failed"

if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
