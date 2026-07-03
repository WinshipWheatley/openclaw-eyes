"""Broker send-edge, hardened: run-mode comes ONLY from the trusted backend state (never caller
params). PRODUCTION+SEND_HOLD blocks; genuine test mode redirects to the operator inbox + flags +
skips approval; a spoofed params run_mode is ignored; and a test-mode send that wasn't redirected
is refused."""

import google_access_broker as broker
from global_run_mode_context import TEST_MARKER


def _ready(monkeypatch, sent):
    monkeypatch.setattr(broker, "_is_configured", lambda: True)
    monkeypatch.setattr(broker, "_load_credentials", lambda: object())
    def fake_exec(creds, params):
        sent.append(dict(params)); return {"ok": True, "data": {"id": "x"}, "error": ""}
    monkeypatch.setattr(broker, "_exec_gmail_send", fake_exec)


def _hold(monkeypatch, tmp_path, active=True):
    h = tmp_path / "SEND_HOLD.md"
    if active: h.write_text("HOLD")
    monkeypatch.setenv("OPENCLAW_SEND_HOLD_PATH", str(h))


def test_production_send_hold_blocks_gmail_send_at_broker(monkeypatch, tmp_path):
    sent = []; _ready(monkeypatch, sent); _hold(monkeypatch, tmp_path)
    res = broker.call("cassandra", "google.gmail.send",
                      {"to": "winshiplive@gmail.com", "subject": "s", "body": "b"})
    assert res["ok"] is False and "SEND_HOLD" in res["error"]
    assert sent == []


def test_spoofed_params_run_mode_is_IGNORED(monkeypatch, tmp_path):
    # caller tries to flip to test mode via params; trusted state is PRODUCTION -> spoof ignored,
    # so SEND_HOLD still blocks and the send never reaches the provider.
    sent = []; _ready(monkeypatch, sent); _hold(monkeypatch, tmp_path)
    # even grant approval — the spoofed run_mode must NOT trigger the test-mode redirect; the
    # production disposition (SEND_HOLD) applies and the send is refused, never redirected.
    monkeypatch.setattr(broker, "_request_approval", lambda *a, **k: True)
    res = broker.call("cassandra", "google.gmail.send",
                      {"to": "attacker@example.com", "subject": "x", "body": "y",
                       "run_mode": "test_live", "requested_run_mode": "test_dry_run"})
    assert res["ok"] is False and "SEND_HOLD" in res["error"]
    assert sent == []   # not redirected, not sent — the spoof did nothing


def test_genuine_test_mode_redirects_flags_skips_approval(monkeypatch, tmp_path):
    sent = []; _ready(monkeypatch, sent); _hold(monkeypatch, tmp_path)
    # genuine test mode = trusted backend state (simulated by the trusted resolver)
    monkeypatch.setattr(broker, "_resolve_broker_run_mode", lambda: ("test_dry_run", "run-1"))
    monkeypatch.setattr(broker, "_request_approval",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no approval in test mode")))
    res = broker.call("cassandra", "google.gmail.send",
                      {"to": "attorney@example.com", "cc": "third@x.com", "subject": "Invoice", "body": "pay"})
    assert res["ok"] is True and len(sent) == 1
    assert sent[0]["to"] == "winshiplive@gmail.com" and not sent[0].get("cc")
    assert TEST_MARKER in sent[0]["body"] and "[OPENCLAW TEST]" in sent[0]["subject"]


def test_test_mode_send_refused_if_redirect_did_not_apply(monkeypatch, tmp_path):
    # Part B invariant: if the redirect somehow fails to set the operator inbox, the send is refused.
    sent = []; _ready(monkeypatch, sent); _hold(monkeypatch, tmp_path)
    monkeypatch.setattr(broker, "_resolve_broker_run_mode", lambda: ("test_dry_run", "run-1"))
    monkeypatch.setattr(broker, "_request_approval", lambda *a, **k: True)
    monkeypatch.setattr(broker, "apply_test_mode_send", lambda params, **k: dict(params))  # redirect fails
    res = broker.call("cassandra", "google.gmail.send",
                      {"to": "attacker@example.com", "subject": "x", "body": "y"})
    assert res["ok"] is False and "redirect" in res["error"].lower()
    assert sent == []


def test_production_no_send_hold_reaches_normal_gates(monkeypatch, tmp_path):
    sent = []; _ready(monkeypatch, sent); _hold(monkeypatch, tmp_path, active=False)
    monkeypatch.setattr(broker, "_request_approval", lambda *a, **k: True)
    res = broker.call("cassandra", "google.gmail.send",
                      {"to": "winshiplive@gmail.com", "subject": "s", "body": "b"})
    assert res["ok"] is True and sent[0]["to"] == "winshiplive@gmail.com"
    assert TEST_MARKER not in sent[0]["body"]
