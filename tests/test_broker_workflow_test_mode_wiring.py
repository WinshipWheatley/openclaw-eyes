"""Broker consults the send-disposition at the last gate: production+SEND_HOLD blocks;
test-mode redirects to the operator inbox + flags (and skips approval)."""

import google_access_broker as broker
from global_run_mode_context import TEST_MARKER


def _ready(monkeypatch, sent):
    monkeypatch.setattr(broker, "_is_configured", lambda: True)
    monkeypatch.setattr(broker, "_load_credentials", lambda: object())
    def fake_exec(creds, params):
        sent.append(dict(params)); return {"ok": True, "data": {"id": "x"}, "error": ""}
    monkeypatch.setattr(broker, "_exec_gmail_send", fake_exec)


def test_production_send_hold_blocks_gmail_send_at_broker(monkeypatch, tmp_path):
    sent = []; _ready(monkeypatch, sent)
    hold = tmp_path / "SEND_HOLD.md"; hold.write_text("HOLD")
    monkeypatch.setenv("OPENCLAW_SEND_HOLD_PATH", str(hold))
    # allowlisted recipient so the self-test lock passes -> proves SEND_HOLD (not self-test) blocks
    res = broker.call("cassandra", "google.gmail.send",
                      {"to": "winshiplive@gmail.com", "subject": "s", "body": "b"})
    assert res["ok"] is False and "SEND_HOLD" in res["error"]
    assert sent == []


def test_test_mode_redirects_and_flags_and_skips_approval(monkeypatch, tmp_path):
    sent = []; _ready(monkeypatch, sent)
    hold = tmp_path / "SEND_HOLD.md"; hold.write_text("HOLD")   # even with SEND_HOLD on...
    monkeypatch.setenv("OPENCLAW_SEND_HOLD_PATH", str(hold))
    # approval must NOT be consulted for a test-mode send
    monkeypatch.setattr(broker, "_request_approval",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no approval in test mode")))
    res = broker.call("cassandra", "google.gmail.send",
                      {"to": "attorney@example.com", "cc": "third@x.com",
                       "subject": "Invoice", "body": "pay", "run_mode": "test_dry_run"})
    assert res["ok"] is True and len(sent) == 1
    assert sent[0]["to"] == "winshiplive@gmail.com"    # redirected to operator
    assert not sent[0].get("cc")                        # no one else reachable
    assert TEST_MARKER in sent[0]["body"]               # flagged
    assert "[OPENCLAW TEST]" in sent[0]["subject"]


def test_production_no_send_hold_still_reaches_normal_gates(monkeypatch, tmp_path):
    sent = []; _ready(monkeypatch, sent)
    monkeypatch.setenv("OPENCLAW_SEND_HOLD_PATH", str(tmp_path / "absent.md"))  # SEND_HOLD off
    monkeypatch.setattr(broker, "_request_approval", lambda *a, **k: True)  # approved
    res = broker.call("cassandra", "google.gmail.send",
                      {"to": "winshiplive@gmail.com", "subject": "s", "body": "b"})
    assert res["ok"] is True and sent[0]["to"] == "winshiplive@gmail.com"  # not redirected/flagged
    assert TEST_MARKER not in sent[0]["body"]
