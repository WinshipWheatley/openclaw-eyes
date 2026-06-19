import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


GMAIL_CAPABILITIES = (
    "google.gmail.unread_count",
    "google.gmail.read.metadata",
    "google.gmail.read.body",
    "google.gmail.draft.create",
    "google.gmail.send",
)


def test_cassandra_gmail_authority_classes_match_intended_policy():
    import google_access_policy as policy

    expected = {
        "google.gmail.unread_count": policy.CLASS_A,
        "google.gmail.read.metadata": policy.CLASS_A,
        "google.gmail.read.body": policy.CLASS_B,
        "google.gmail.draft.create": policy.CLASS_B,
        "google.gmail.send": policy.CLASS_C,
    }

    for capability, approval_class in expected.items():
        assert policy.allowed("cassandra", capability) is True
        assert policy.get_class("cassandra", capability) == approval_class


def test_chief_remains_denied_for_gmail_capabilities():
    import google_access_policy as policy

    for capability in GMAIL_CAPABILITIES:
        assert policy.allowed("chief", capability) is False
        assert policy.get_class("chief", capability) is policy.DENIED


def test_broker_gates_class_b_gmail_body_and_draft_before_credentials(monkeypatch):
    import google_access_broker as broker

    approval_calls = []

    def fake_request_approval(action, tier, approval_context=None):
        approval_calls.append(
            {
                "action": action,
                "tier": tier,
                "approval_context": approval_context,
            }
        )
        return False

    def fail_if_credentials_checked():
        raise AssertionError("credential check should not run before Class B approval")

    monkeypatch.setattr(broker, "_request_approval", fake_request_approval)
    monkeypatch.setattr(broker, "_is_configured", fail_if_credentials_checked)
    monkeypatch.setattr(broker, "check_gmail_broker_runtime_dependencies", lambda: {"ok": True, "missing": []})

    for capability in ("google.gmail.read.body", "google.gmail.draft.create"):
        token = broker.mint_send_hold_gated_broker_capability_token(
            agent="cassandra",
            capability=capability,
            issuer="test_google_access_policy",
            send_hold_checked=True,
            send_hold_active=False,
            send_hold_ref="pytest",
        )
        result = broker.call(
            "cassandra",
            capability,
            {
                "message_id": "synthetic-message",
                "thread_id": "synthetic-thread",
                "to": "review@example.com",
                "subject": "Synthetic subject",
                "body": "Synthetic body",
                "broker_capability_token": token,
            },
        )
        assert result == {"ok": False, "data": None, "error": "denied at L1 approval gate"}

    assert [call["tier"] for call in approval_calls] == [1, 1]
    assert [call["action"] for call in approval_calls] == [
        "Google broker: cassandra \u2192 google.gmail.read.body",
        "Google broker: cassandra \u2192 google.gmail.draft.create",
    ]


def test_broker_gates_class_c_gmail_send_before_credentials(monkeypatch):
    import google_access_broker as broker

    approval_calls = []
    request_id = "policy-gate-fixture"
    payload_hash = "sha256:" + ("c" * 64)
    approval_context = {
        "request_id": request_id,
        "idempotency_key": request_id,
        "payload_hash": payload_hash,
    }

    def fake_request_approval(action, tier, approval_context=None):
        approval_calls.append(
            {
                "action": action,
                "tier": tier,
                "approval_context": approval_context,
            }
        )
        return False

    def fail_if_credentials_checked():
        raise AssertionError("credential check should not run before Class C approval")

    monkeypatch.setattr(broker, "_request_approval", fake_request_approval)
    monkeypatch.setattr(broker, "_is_configured", fail_if_credentials_checked)
    monkeypatch.setattr(broker, "check_gmail_broker_runtime_dependencies", lambda: {"ok": True, "missing": []})

    token = broker.mint_send_hold_gated_broker_capability_token(
        agent="cassandra",
        capability="google.gmail.send",
        issuer="test_google_access_policy",
        request_id=request_id,
        idempotency_key=request_id,
        payload_hash=payload_hash,
        send_hold_checked=True,
        send_hold_active=False,
        send_hold_ref="pytest",
    )

    result = broker.call(
        "cassandra",
        "google.gmail.send",
        {
            "to": "review@example.com",
            "subject": "Synthetic subject",
            "body": "Synthetic body",
            "exact_send_request_id": request_id,
            "idempotency_key": request_id,
            "approval_context": approval_context,
            "broker_capability_token": token,
        },
    )

    assert result == {"ok": False, "data": None, "error": "denied at L2 approval gate"}
    assert approval_calls == [
        {
            "action": "Google broker: cassandra \u2192 google.gmail.send",
            "tier": 2,
            "approval_context": approval_context,
        }
    ]


def test_broker_does_not_gate_class_a_gmail_unread_or_metadata_before_credentials(monkeypatch):
    import google_access_broker as broker

    approval_calls = []

    def fail_if_approval_requested(action, tier, approval_context=None):
        approval_calls.append((action, tier, approval_context))
        raise AssertionError("Class A Gmail capabilities should not request approval")

    monkeypatch.setattr(broker, "_request_approval", fail_if_approval_requested)
    monkeypatch.setattr(broker, "_is_configured", lambda: False)
    monkeypatch.setattr(broker, "check_gmail_broker_runtime_dependencies", lambda: {"ok": True, "missing": []})

    for capability in ("google.gmail.unread_count", "google.gmail.read.metadata"):
        result = broker.call("cassandra", capability, {})
        assert result["ok"] is False
        assert result["data"] is None
        assert "Google credentials not configured" in result["error"]

    assert approval_calls == []


def test_cassandra_post_draft_send_path_requires_broker_token_before_legacy_approval(monkeypatch):
    if "capital_hilton_agency_status" not in sys.modules:
        capital_module = types.ModuleType("capital_hilton_agency_status")
        capital_module.format_capital_hilton_agency_answer = lambda *args, **kwargs: None
        capital_module.format_capital_hilton_openclaw_status_answer = lambda *args, **kwargs: None
        sys.modules["capital_hilton_agency_status"] = capital_module
    if "reynolds_gig_setup_status" not in sys.modules:
        reynolds_module = types.ModuleType("reynolds_gig_setup_status")
        reynolds_module.format_reynolds_gig_setup_answer = lambda *args, **kwargs: None
        reynolds_module.is_reynolds_gig_setup_query = lambda *args, **kwargs: False
        sys.modules["reynolds_gig_setup_status"] = reynolds_module

    import cassandra_brain as brain
    import google_access_broker as broker

    events = []
    approval_calls = []

    def record_state(recipient_name, state, detail="", route="", metadata=None):
        events.append(
            {
                "recipient_name": recipient_name,
                "state": state,
                "detail": detail,
                "route": route,
                "metadata": metadata or {},
            }
        )

    def fail_if_approval_requested(action, tier, approval_context=None):
        approval_calls.append((action, tier, approval_context))
        raise AssertionError("legacy approval must not run without a broker capability token")

    def fail_if_executor_called(*_args, **_kwargs):
        raise AssertionError("gmail send executor must not run without a broker capability token")

    monkeypatch.setattr(brain, "broker_call", broker.call)
    monkeypatch.setattr(brain, "_log_correspondence_state", record_state)
    monkeypatch.setattr(brain, "_notify_post_draft_send_outcome", lambda **_kwargs: None)
    monkeypatch.setattr(broker, "_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(broker, "_request_approval", fail_if_approval_requested)
    monkeypatch.setattr(broker, "_exec_gmail_send", fail_if_executor_called)
    monkeypatch.setattr(broker, "check_gmail_broker_runtime_dependencies", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(broker, "_is_configured", lambda: True)

    brain._run_email_send_after_draft(
        recipient_name="Fixture Recipient",
        recipient_email="fixture@example.invalid",
        subject="Fixture subject",
        body="Fixture body",
        review_inbox="review@example.invalid",
        approval_context={
            "action_label": "send email",
            "request_id": "v0-fixture",
            "idempotency_key": "v0-fixture",
        },
    )

    assert approval_calls == []
    assert events[-1]["state"] == brain._SS_SEND_FAILED
    assert events[-1]["detail"] == "broker capability token required for google.gmail.send"
    assert events[-1]["route"] == "email_send"
