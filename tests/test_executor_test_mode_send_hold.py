"""execute_email_send_packet is run-mode aware: PRODUCTION + SEND_HOLD blocks (unchanged);
in TEST mode the SEND_HOLD hard-stop yields so the send flows to the broker, which redirects it
to the operator's inbox and flags it (Phase 1 packet-path edge)."""

import email_send_executor as ese


def _approved_state(monkeypatch):
    import chief_compose
    state = {"surface": "email_send", "stale": False, "execution_allowed": True,
             "packet_id": "p1", "recipient": "winshiplive@gmail.com"}
    monkeypatch.setattr(chief_compose, "get_packet_approval_state", lambda *a, **k: dict(state))


def test_production_send_hold_blocks_packet(monkeypatch, tmp_path):
    _approved_state(monkeypatch)
    hold = tmp_path / "SEND_HOLD.md"; hold.write_text("HOLD")
    sent = []
    r = ese.execute_email_send_packet(
        packet_id="p1", send_hold_path=hold,
        email_sender=lambda **k: sent.append(k) or {"ok": True},
        outbound_payload={"to": "winshiplive@gmail.com", "subject": "s", "body": "b"},
    )
    assert r.ok is False
    assert getattr(r, "meta", {}).get("send_hold_active") is True or "SEND_HOLD" in (r.detail or "")
    assert sent == []   # blocked before the send


def test_test_mode_yields_send_hold_so_send_reaches_broker(monkeypatch, tmp_path):
    _approved_state(monkeypatch)
    hold = tmp_path / "SEND_HOLD.md"; hold.write_text("HOLD")
    sent = []
    r = ese.execute_email_send_packet(
        packet_id="p1", send_hold_path=hold, run_mode="test_dry_run",
        email_sender=lambda **k: sent.append(k) or {"ok": True},
        outbound_payload={"to": "winshiplive@gmail.com", "subject": "s", "body": "b"},
    )
    # SEND_HOLD did NOT hard-block in test mode; the send proceeded (broker redirects+flags downstream)
    assert not (getattr(r, "meta", {}).get("send_hold_active") is True and r.ok is False and "SEND_HOLD" in (r.detail or ""))
    assert len(sent) == 1
