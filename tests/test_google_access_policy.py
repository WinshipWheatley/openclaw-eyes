import sys
from pathlib import Path


sys.path.insert(0, "/home/openclaw")

ROOT = Path(__file__).resolve().parents[1]


GMAIL_CAPABILITIES = (
    "google.gmail.unread_count",
    "google.gmail.read.metadata",
    "google.gmail.read.body",
    "google.gmail.draft.create",
    "google.gmail.send",
)

CALENDAR_SCHEDULER_AGENTS = ("cassandra", "niles", "maestro", "chief")


def test_policy_has_no_wildcard_agent_grants():
    import google_access_policy as policy

    for capability, agent_policy in policy._POLICY.items():
        assert "*" not in agent_policy, f"{capability} must enumerate agents explicitly"


def test_unknown_agents_fail_closed_for_google_capabilities():
    import google_access_policy as policy

    for capability in policy._POLICY:
        assert policy.allowed("unknown", capability) is False
        assert policy.get_class("unknown", capability) is policy.DENIED


def test_calendar_read_write_stays_broad_for_scheduler_agents_delete_guardian_gated():
    import google_access_policy as policy

    for agent in CALENDAR_SCHEDULER_AGENTS:
        assert policy.get_class(agent, "google.calendar.read") == policy.CLASS_A
        assert policy.get_class(agent, "google.calendar.write") == policy.CLASS_A
        assert policy.get_class(agent, "google.calendar.delete") == policy.CLASS_C


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

    for capability in ("google.gmail.read.body", "google.gmail.draft.create"):
        result = broker.call(
            "cassandra",
            capability,
            {
                "message_id": "synthetic-message",
                "thread_id": "synthetic-thread",
                "to": "review@example.com",
                "subject": "Synthetic subject",
                "body": "Synthetic body",
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

    result = broker.call(
        "cassandra",
        "google.gmail.send",
        {
            "to": "review@example.com",
            "subject": "Synthetic subject",
            "body": "Synthetic body",
        },
    )

    assert result == {"ok": False, "data": None, "error": "denied at L2 approval gate"}
    assert approval_calls == [
        {
            "action": "Google broker: cassandra \u2192 google.gmail.send",
            "tier": 2,
            "approval_context": None,
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

    for capability in ("google.gmail.unread_count", "google.gmail.read.metadata"):
        result = broker.call("cassandra", capability, {})
        assert result["ok"] is False
        assert result["data"] is None
        assert "Google credentials not configured" in result["error"]

    assert approval_calls == []


def test_manual_oauth_cli_flag_is_wired_without_replacing_local_server_auth():
    source = (ROOT / "google_access_broker.py").read_text(encoding="utf-8")

    assert '"--auth-manual"' in source
    assert "elif \"--auth-manual\" in sys.argv:\n        run_auth_flow_manual()" in source
    assert "elif \"--auth\" in sys.argv:\n        run_auth_flow()" in source
    assert "OAuth2 paste-the-code flow (WSL-safe, no localhost callback)" in source
