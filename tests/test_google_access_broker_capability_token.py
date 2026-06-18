import pytest

import email_send_executor
import google_access_broker as broker


@pytest.fixture(autouse=True)
def reset_broker_tokens():
    broker._BROKER_CAPABILITY_TOKEN_REGISTRY.clear()
    yield
    broker._BROKER_CAPABILITY_TOKEN_REGISTRY.clear()


@pytest.mark.parametrize(
    ("capability", "params"),
    [
        ("google.calendar.write", {"title": "Review", "start_iso": "2026-06-18T10:00:00", "end_iso": "2026-06-18T10:30:00"}),
        ("google.contacts.read", {"query": "Annette"}),
        ("google.gmail.read.body", {"thread_id": "thread-fixture"}),
        ("google.gmail.draft.create", {"to": "ops@example.invalid", "subject": "Draft", "body": "body"}),
        ("google.gmail.send", {"to": "ops@example.invalid", "subject": "Send", "body": "body"}),
    ],
)
def test_broker_refuses_exec_surfaces_without_capability_token(monkeypatch, capability, params):
    audits = []
    monkeypatch.setattr(broker, "_audit", lambda *args, **_kwargs: audits.append(args))

    result = broker.call("cassandra", capability, params)

    assert result["ok"] is False
    assert result["data"] is None
    assert result["error"] == f"broker capability token required for {capability}"
    assert audits[-1][1] == capability
    assert audits[-1][3] is False


def test_read_only_calendar_path_does_not_require_capability_token(monkeypatch):
    monkeypatch.setattr(broker, "_is_configured", lambda: False)
    monkeypatch.setattr(broker, "_audit", lambda *_args, **_kwargs: None)

    result = broker.call("cassandra", "google.calendar.read", {"days_ahead": 1})

    assert result["ok"] is False
    assert "Google credentials not configured" in result["error"]


def test_minted_broker_capability_token_is_bound_and_single_use(monkeypatch):
    payload_hash = "sha256:" + ("1" * 64)
    token = broker.mint_send_hold_gated_broker_capability_token(
        agent="cassandra",
        capability="google.gmail.send",
        issuer="email_send_executor",
        request_id="packet-fixture",
        idempotency_key="packet-fixture",
        payload_hash=payload_hash,
        authority_refs=["authority:fixture"],
        credential_lease_refs=["credential-lease:fixture"],
        send_hold_checked=True,
        send_hold_active=False,
        send_hold_ref="/tmp/missing_SEND_HOLD.md",
    )
    monkeypatch.setattr(broker, "check_gmail_broker_runtime_dependencies", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(broker, "_is_configured", lambda: False)
    monkeypatch.setattr(broker, "_audit", lambda *_args, **_kwargs: None)

    params = {
        "to": "ops@example.invalid",
        "subject": "Send",
        "body": "body",
        "exact_send_request_id": "packet-fixture",
        "idempotency_key": "packet-fixture",
        "approval_context": {
            "exact_send_gate": True,
            "request_id": "packet-fixture",
            "idempotency_key": "packet-fixture",
            "payload_hash": payload_hash,
            "authority_refs": ["authority:fixture"],
            "credential_lease_refs": ["credential-lease:fixture"],
        },
        "broker_capability_token": token,
    }

    first = broker.call("cassandra", "google.gmail.send", params)
    second = broker.call("cassandra", "google.gmail.send", params)

    assert first["ok"] is False
    assert "Google credentials not configured" in first["error"]
    assert second == {"ok": False, "data": None, "error": "broker capability token already consumed"}


def test_broker_capability_token_rejects_capability_mismatch(monkeypatch):
    token = broker.mint_send_hold_gated_broker_capability_token(
        agent="cassandra",
        capability="google.gmail.send",
        issuer="email_send_executor",
        request_id="packet-fixture",
        idempotency_key="packet-fixture",
        payload_hash="sha256:" + ("2" * 64),
        authority_refs=["authority:fixture"],
        credential_lease_refs=["credential-lease:fixture"],
        send_hold_checked=True,
        send_hold_active=False,
        send_hold_ref="/tmp/missing_SEND_HOLD.md",
    )
    monkeypatch.setattr(broker, "_audit", lambda *_args, **_kwargs: None)

    result = broker.call(
        "cassandra",
        "google.gmail.draft.create",
        {
            "to": "ops@example.invalid",
            "subject": "Draft",
            "body": "body",
            "broker_capability_token": token,
        },
    )

    assert result == {"ok": False, "data": None, "error": "broker capability token capability mismatch"}


def test_broker_capability_token_is_redacted_from_audit_params():
    token = broker.mint_send_hold_gated_broker_capability_token(
        agent="cassandra",
        capability="google.gmail.send",
        issuer="email_send_executor",
        request_id="packet-fixture",
        idempotency_key="packet-fixture",
        payload_hash="sha256:" + ("3" * 64),
        send_hold_checked=True,
        send_hold_active=False,
    )

    redacted = broker._redact_audit_params({"broker_capability_token": token, "body": "secret"})

    assert "body" not in redacted
    assert redacted["broker_capability_token"]["token_fingerprint"] == token["token_fingerprint"]
    assert "token_id" not in redacted["broker_capability_token"]


def test_email_broker_helper_requires_send_hold_verified():
    result = email_send_executor.send_email_via_google_broker(
        to="ops@example.invalid",
        subject="Subject",
        body="Body",
        packet_id="packet-fixture",
    )

    assert result == {
        "ok": False,
        "data": None,
        "error": "SEND_HOLD must be checked before minting broker capability token",
    }


def test_email_broker_helper_passes_minted_token_after_send_hold_verified(monkeypatch):
    calls = []

    def fake_call(agent, capability, params):
        calls.append((agent, capability, params))
        return {"ok": True, "data": {"message_id": "msg-fixture", "thread_id": "thread-fixture"}, "error": ""}

    monkeypatch.setattr(broker, "call", fake_call)

    result = email_send_executor.send_email_via_google_broker(
        to="ops@example.invalid",
        subject="Subject",
        body="Body",
        approval_state={"packet_hash": "packet-hash-fixture"},
        packet_id="packet-fixture",
        send_hold_verified=True,
        send_hold_ref="/tmp/missing_SEND_HOLD.md",
    )

    assert result["ok"] is True
    assert calls[0][0] == "cassandra"
    assert calls[0][1] == "google.gmail.send"
    params = calls[0][2]
    assert params["broker_capability_token"]["schema_version"] == broker.BROKER_CAPABILITY_TOKEN_SCHEMA
    assert params["approval_context"]["broker_capability_token_fingerprint"] == params["broker_capability_token"]["token_fingerprint"]
    assert params["approval_context"]["authority_refs"] == ["packet-hash-fixture"]
