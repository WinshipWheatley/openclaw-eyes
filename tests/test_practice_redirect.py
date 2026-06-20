import base64
import json
import sys
from email import message_from_string
from pathlib import Path

import cassandra_operator_objective_loop as loop
import google_access_broker as broker
import practice_redirect


REQUEST_ID = "exact_send_authority_request:practice-fixture"
OBJECTIVE_ID = "objective:practice-fixture"
PAYLOAD_HASH = "sha256:" + ("a" * 64)


def _decode_raw_message(raw: str):
    padding = "=" * (-len(raw) % 4)
    text = base64.urlsafe_b64decode(raw + padding).decode("utf-8", errors="ignore")
    return text, message_from_string(text)


def _arm_practice(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("OPENCLAW_PRACTICE_MODE", "1")
    monkeypatch.setenv("OPENCLAW_PRACTICE_BENCH", "1")
    monkeypatch.delenv("OPENCLAW_TEST_MODE", raising=False)
    monkeypatch.delenv("OPENCLAW_NETWORK_DISABLED", raising=False)
    monkeypatch.delenv("OPENCLAW_LIVE_RUNTIME_DISABLED", raising=False)
    creds = tmp_path / "credentials.json"
    token = tmp_path / "bench-token.json"
    creds.write_text("{}\\n", encoding="utf-8")
    token.write_text("{}\\n", encoding="utf-8")
    monkeypatch.setattr(broker, "_CREDS_FILE", creds)
    monkeypatch.setattr(broker, "_TOKEN_FILE", token)
    monkeypatch.setattr(broker, "_load_credentials", lambda: object())
    monkeypatch.setattr(broker, "_import_runtime_dependency", lambda _name: object())


def _exact_send_params(**extra):
    params = {
        "to": "client@example.com",
        "cc": "team@example.com",
        "bcc": "hidden@example.com",
        "subject": "Client follow-up",
        "body": "Practice body",
        "thread_id": "thread-real",
        "in_reply_to": "<real@example.com>",
        "references": "<real@example.com>",
        "idempotency_key": REQUEST_ID,
        "exact_send_request_id": REQUEST_ID,
        "approval_context": {
            "exact_send_gate": True,
            "request_id": REQUEST_ID,
            "idempotency_key": REQUEST_ID,
            "objective_id": OBJECTIVE_ID,
            "payload_hash": PAYLOAD_HASH,
            "authority_refs": ["authority_envelope:fixture"],
            "credential_lease_refs": ["credential_lease:fixture"],
        },
    }
    params.update(extra)
    return params


def test_practice_mode_redirects_exact_gmail_send_to_safe_sink_after_gate(tmp_path, monkeypatch):
    _arm_practice(monkeypatch, tmp_path)
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(broker, "_AUDIT_LOG", audit_path)
    approval_calls = []
    monkeypatch.setattr(broker, "_request_approval", lambda *args, **kwargs: approval_calls.append((args, kwargs)) or False)

    captured = {}

    class FakeSendCall:
        def execute(self):
            return {"id": "sent-practice", "threadId": "thread-practice"}

    class FakeMessages:
        def send(self, userId, body):
            captured["userId"] = userId
            captured["body"] = body
            return FakeSendCall()

    class FakeUsers:
        def messages(self):
            return FakeMessages()

    class FakeService:
        def users(self):
            return FakeUsers()

    monkeypatch.setitem(
        sys.modules,
        "googleapiclient.discovery",
        type("DiscoveryModule", (), {"build": lambda *args, **kwargs: FakeService()})(),
    )

    result = broker.call("cassandra", "google.gmail.send", _exact_send_params())

    assert approval_calls == []
    assert result["ok"] is True
    assert result["data"]["status"] == practice_redirect.EXACT_SEND_PRACTICE_REDIRECTED
    assert result["data"]["practice_redirect_applied"] is True
    assert result["data"]["target_redirected_to"] == practice_redirect.PRACTICE_SINK_EMAIL
    assert result["data"]["practice_redirect_meta"]["original_recipient"] == "client@example.com"

    assert captured["userId"] == "me"
    assert "threadId" not in captured["body"]
    raw_text, message = _decode_raw_message(captured["body"]["raw"])
    assert message["To"] == practice_redirect.PRACTICE_SINK_EMAIL
    assert message["Cc"] is None
    assert message["Subject"] == "[PRACTICE] Client follow-up"
    assert message["X-OpenClaw-Practice"] == "true"
    assert message["X-OpenClaw-Practice-Status"] == practice_redirect.EXACT_SEND_PRACTICE_REDIRECTED
    assert "In-Reply-To" not in message
    assert "References" not in message
    assert "client@example.com" not in raw_text
    assert "team@example.com" not in raw_text
    assert "hidden@example.com" not in raw_text

    audit = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert audit["params"]["to"] == "client@example.com"
    assert audit["params"]["cc"] == "team@example.com"
    assert audit["params"]["target_redirected_to"] == practice_redirect.PRACTICE_SINK_EMAIL
    assert audit["params"]["terminal_status"] == practice_redirect.EXACT_SEND_PRACTICE_REDIRECTED
    assert "body" not in audit["params"]


def test_practice_mode_does_not_weaken_unapproved_l2_gate(tmp_path, monkeypatch):
    _arm_practice(monkeypatch, tmp_path)
    monkeypatch.setattr(broker, "_AUDIT_LOG", tmp_path / "audit.jsonl")
    monkeypatch.setattr(broker, "_request_approval", lambda *args, **kwargs: False)
    monkeypatch.setattr(broker, "_load_credentials", lambda: (_ for _ in ()).throw(AssertionError("credentials not reached")))

    result = broker.call(
        "cassandra",
        "google.gmail.send",
        {
            "to": "client@example.com",
            "subject": "Needs approval",
            "body": "Practice body",
        },
    )

    assert result["ok"] is False
    assert result["error"] == "denied at L2 approval gate"
    assert result.get("data") is None
    audit = json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert audit["params"]["to"] == "client@example.com"
    assert "target_redirected_to" not in audit["params"]


def test_practice_mode_cannot_arm_in_sandbox_or_with_prod_token(tmp_path, monkeypatch):
    bench_token = tmp_path / "bench-token.json"
    bench_token.write_text("{}\\n", encoding="utf-8")
    monkeypatch.setenv("OPENCLAW_PRACTICE_MODE", "1")
    monkeypatch.setenv("OPENCLAW_PRACTICE_BENCH", "1")
    monkeypatch.setenv("OPENCLAW_NETWORK_DISABLED", "1")
    monkeypatch.delenv("OPENCLAW_TEST_MODE", raising=False)
    monkeypatch.delenv("OPENCLAW_LIVE_RUNTIME_DISABLED", raising=False)
    assert practice_redirect.practice_mode_armed(active_token_path=bench_token) is False

    monkeypatch.delenv("OPENCLAW_NETWORK_DISABLED", raising=False)
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    assert practice_redirect.practice_mode_armed(active_token_path=bench_token) is False

    monkeypatch.delenv("OPENCLAW_TEST_MODE", raising=False)
    monkeypatch.delenv("OPENCLAW_NETWORK_DISABLED", raising=False)
    monkeypatch.delenv("OPENCLAW_LIVE_RUNTIME_DISABLED", raising=False)
    assert practice_redirect.practice_mode_armed(active_token_path="/home/openclaw/.google-secrets/token.json") is False


def test_send_hold_blocks_before_practice_transport_construction(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_PRACTICE_MODE", "1")
    monkeypatch.setenv("OPENCLAW_PRACTICE_BENCH", "1")
    send_hold = tmp_path / "SEND_HOLD.md"
    send_hold.write_text("SEND_HOLD active for practice regression test.\\n", encoding="utf-8")

    def _transport_must_not_be_constructed(**_kwargs):
        raise AssertionError("SEND_HOLD must block before broker practice transport construction")

    monkeypatch.setattr(loop, "GovernedGmailBrokerSendTransport", _transport_must_not_be_constructed)
    result = loop.run_exact_send_operator_action_routeback(
        {
            "action_id": "hitl_action:practice-send-hold",
            "action_type": "exact_gmail_send",
            "status": "APPROVED",
            "idempotency_key": REQUEST_ID,
            "approved_by": "operator:winship",
            "approved_at": "2026-06-20T22:20:00+00:00",
            "payload": {
                "request_id": REQUEST_ID,
                "owner_objective_id": OBJECTIVE_ID,
                "route_back": {"type": "cassandra_exact_send_executor", "objective_id": OBJECTIVE_ID},
                "payload": {
                    "request_id": REQUEST_ID,
                    "objective_id": OBJECTIVE_ID,
                    "recipient": "client@example.com",
                    "subject": "Practice hold regression",
                    "payload_hash": PAYLOAD_HASH,
                    "expires_at": "2099-01-01T00:00:00+00:00",
                },
            },
        },
        sqlite_path=tmp_path / "objectives.sqlite",
        receipt_dir=tmp_path / "receipts",
        send_hold_path=send_hold,
        generated_at="2026-06-20T22:20:00+00:00",
    )

    assert result["response_status"] == "EXACT_SEND_HITL_ROUTEBACK_REFUSED"
    assert result["refusal_reason"] == "send_hold_active"
    assert result["gmail_api_called"] is False
    assert result["email_send_performed"] is False
