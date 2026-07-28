from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import google_access_broker as broker
import cassandra_operator_objective_loop as objective_loop
from send_hold_scoped_graduation import (
    SendHoldGraduationError,
    issue_send_hold_scoped_graduation,
    verify_send_hold_scoped_graduation,
)


# These were pinned to absolute instants ("2026-07-18T04:30Z" / "…T06:30Z"). The
# graduation is deliberately short-lived, so the moment real time passed 06:30 on
# 2026-07-18 every test that drives the BROKER — which checks expiry against the
# wall clock — began failing, while the tests that only exercise issue/verify with
# an explicit observed_at kept passing. A gate that was working looked broken for
# ten days.
#
# Anchored to now instead. The window keeps the same two-hour shape, so the
# expiry semantics under test are unchanged; it simply cannot rot again.
NOW = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(timespec="seconds")
EXPIRES = (datetime.now(timezone.utc) + timedelta(minutes=90)).isoformat(timespec="seconds")
REQUEST_ID = "exact_send_authority_request:lamd-copy-revision"
PAYLOAD_HASH = "sha256:" + "a" * 64
BODY = "Exact approved body"
BODY_SHA = "sha256:" + hashlib.sha256(BODY.encode()).hexdigest()


def _scope(tmp_path: Path) -> dict:
    sentinel = tmp_path / "SEND_HOLD.md"
    sentinel.write_text("SEND_HOLD remains active.\n", encoding="utf-8")
    sentinel.chmod(0o644)
    attachment = tmp_path / "invoice.pdf"
    attachment.write_bytes(b"%PDF-1.4\nexact approved invoice\n")
    attachment_sha = hashlib.sha256(attachment.read_bytes()).hexdigest()
    graduation = tmp_path / "graduation.json"
    return {
        "graduation_path": graduation,
        "send_hold_path": sentinel,
        "request_id": REQUEST_ID,
        "payload_hash": PAYLOAD_HASH,
        "recipient": "Accountant@liveartsmd.org",
        "body_sha256": BODY_SHA,
        "attachment_paths": [str(attachment)],
        "attachment_sha256": [attachment_sha],
        "authority_provenance": "terminal first-class GO relayed by Fable",
        "active_heartbeat_hold_source": "openclaw-to-codex-lane-watcher",
        "generated_at": NOW,
        "expires_at": EXPIRES,
    }


def test_scoped_graduation_is_hash_bound_single_use_and_leaves_hold_present(tmp_path: Path) -> None:
    scope = _scope(tmp_path)
    issued = issue_send_hold_scoped_graduation(**scope)
    assert issued["status"] == "ACTIVE"
    assert scope["send_hold_path"].is_file()

    observed = {key: scope[key] for key in (
        "graduation_path", "send_hold_path", "request_id", "payload_hash", "recipient",
        "body_sha256", "attachment_paths", "attachment_sha256",
    )}
    verified = verify_send_hold_scoped_graduation(**observed, observed_at=NOW)
    consumed = verify_send_hold_scoped_graduation(**observed, observed_at=NOW, consume=True)
    assert verified["valid"] is True and verified["consumed"] is False
    assert consumed["status"] == "CONSUMED" and consumed["consumed"] is True
    assert scope["send_hold_path"].is_file()
    assert json.loads(scope["graduation_path"].read_text())["use_count"] == 1
    with pytest.raises(SendHoldGraduationError, match="already consumed"):
        verify_send_hold_scoped_graduation(**observed, observed_at=NOW, consume=True)


def test_scoped_graduation_refuses_recipient_or_sentinel_drift(tmp_path: Path) -> None:
    scope = _scope(tmp_path)
    issue_send_hold_scoped_graduation(**scope)
    observed = {key: scope[key] for key in (
        "graduation_path", "send_hold_path", "request_id", "payload_hash", "recipient",
        "body_sha256", "attachment_paths", "attachment_sha256",
    )}
    with pytest.raises(SendHoldGraduationError, match="does not match"):
        verify_send_hold_scoped_graduation(
            **{**observed, "recipient": "other@example.com"}, observed_at=NOW
        )
    scope["send_hold_path"].write_text("changed\n", encoding="utf-8")
    with pytest.raises(SendHoldGraduationError, match="sentinel hash changed"):
        verify_send_hold_scoped_graduation(**observed, observed_at=NOW)


def test_broker_consumes_exact_graduation_once_and_refuses_replay(tmp_path: Path, monkeypatch) -> None:
    scope = _scope(tmp_path)
    issue_send_hold_scoped_graduation(**scope)
    monkeypatch.setenv("OPENCLAW_SEND_HOLD_PATH", str(scope["send_hold_path"]))
    monkeypatch.setattr(broker, "_is_configured", lambda: True)
    monkeypatch.setattr(broker, "_load_credentials", lambda: object())
    monkeypatch.setattr(
        broker,
        "check_gmail_broker_runtime_dependencies",
        lambda: {"ok": True, "checked_modules": [], "missing": [], "credentials_read": False, "google_api_called": False},
    )
    monkeypatch.setattr(broker, "_resolve_broker_run_mode", lambda: ("production", ""))
    sent = []

    def fake_send(_creds, params):
        sent.append(dict(params))
        return {"ok": True, "data": {"message_id": "provider-one", "thread_id": "thread-one"}, "error": ""}

    monkeypatch.setattr(broker, "_exec_gmail_send", fake_send)
    params = {
        "to": scope["recipient"],
        "subject": "Exact subject",
        "body": BODY,
        "attachments": scope["attachment_paths"],
        "attachment_sha256": scope["attachment_sha256"],
        "idempotency_key": REQUEST_ID,
        "exact_send_request_id": REQUEST_ID,
        "send_hold_graduation_ref": str(scope["graduation_path"]),
        "approval_context": {
            "exact_send_gate": True,
            "request_id": REQUEST_ID,
            "idempotency_key": REQUEST_ID,
            "payload_hash": PAYLOAD_HASH,
            "authority_refs": ["authority:one"],
            "credential_lease_refs": ["lease:one"],
            "send_hold_graduation_ref": str(scope["graduation_path"]),
        },
    }
    first = broker.call("cassandra", "google.gmail.send", params)
    second = broker.call("cassandra", "google.gmail.send", params)

    assert first["ok"] is True
    assert second["ok"] is False and "SEND_HOLD" in second["error"]
    assert len(sent) == 1


def test_cassandra_routeback_carries_production_attachment_through_scoped_hold(tmp_path: Path) -> None:
    scope = _scope(tmp_path)
    body = (
        "Hi Megan,\n\nAttached is Invoice 2026-1004 for July 2026, covering the monthly speaker rental "
        "at $100.00.\n\nCould you send me a quick note once the invoice is in your accounting queue? "
        "That helps me know it landed and keeps our records straight.\n\nWarmly,\nClara Reid"
    )
    subject = "2026-1004: July 2026 Monthly Speaker Rental Invoice"
    text = (
        "Draft is approved with this exact text for Accountant@liveartsmd.org.\n"
        f"Subject: {subject}\n\n{body}\n\nPrepare the send authority request; do not send until approved."
    )
    db_path = tmp_path / "cassandra.sqlite"
    route = objective_loop.route_draft_approval_to_send_authority(
        text,
        source_channel="terminal",
        source_message_ref="terminal:first-class-go",
        lane_context={
            "attachments": scope["attachment_paths"],
            "attachment_sha256": scope["attachment_sha256"],
        },
        sqlite_path=db_path,
        generated_at=NOW,
    )
    request = route["send_authority_request"]
    request["expires_at"] = EXPIRES
    route["objective"]["send_authority_request"] = request
    bundle = objective_loop.create_exact_send_scoped_authority(
        request,
        generated_at=NOW,
        expires_at=EXPIRES,
    )
    persisted = objective_loop.persist_exact_send_authority_bundle(
        route["objective"],
        authority_envelope=bundle["authority_envelope"],
        credential_lease=bundle["credential_lease"],
        sqlite_path=db_path,
        authority_provenance=scope["authority_provenance"],
        generated_at=NOW,
    )
    assert persisted["persisted"] is True
    review = objective_loop.build_exact_send_review_packet(
        persisted["objective"]["send_authority_request"],
        draft={"recipient": scope["recipient"], "subject": subject, "body": body},
        expires_at=EXPIRES,
        generated_at=NOW,
    )
    scoped_issue = {
        **scope,
        "request_id": request["request_id"],
        "payload_hash": request["payload_hash"],
        "body_sha256": "sha256:" + hashlib.sha256(body.encode()).hexdigest(),
    }
    issue_send_hold_scoped_graduation(**scoped_issue)
    action = {
        "action_id": "hitl_action:terminal-go",
        "action_type": "exact_gmail_send",
        "status": "APPROVED",
        "idempotency_key": request["request_id"],
        "approved_by": scope["authority_provenance"],
        "approved_at": NOW,
        "payload": {
            "request_id": request["request_id"],
            "owner_objective_id": route["objective"]["objective_id"],
            "route_back": {
                "type": "cassandra_exact_send_executor",
                "objective_id": route["objective"]["objective_id"],
                "request_id": request["request_id"],
            },
            "payload": {
                "request_id": request["request_id"],
                "objective_id": route["objective"]["objective_id"],
                "recipient": scope["recipient"],
                "subject": subject,
                "payload_hash": request["payload_hash"],
                "body_sha256": scoped_issue["body_sha256"],
                "expires_at": EXPIRES,
                "approval_provenance": scope["authority_provenance"],
                "send_hold_graduation_ref": str(scope["graduation_path"]),
                "attachments": scope["attachment_paths"],
                "attachment_sha256": scope["attachment_sha256"],
                "attachment_binding_hash": review["attachment_binding_hash"],
            },
        },
    }
    calls = []

    def fake_broker(agent, capability, params):
        calls.append((agent, capability, params))
        return {"ok": True, "data": {"message_id": "fixture-message", "thread_id": "fixture-thread"}, "error": ""}

    transport = objective_loop.GovernedGmailBrokerSendTransport(
        live_transport_enabled=True,
        broker_call=fake_broker,
        send_hold_graduation_ref=str(scope["graduation_path"]),
    )
    result = objective_loop.run_exact_send_operator_action_routeback(
        action,
        sqlite_path=db_path,
        receipt_dir=tmp_path / "receipts",
        transport=transport,
        live_transport_enabled=True,
        send_hold_path=scope["send_hold_path"],
        generated_at=NOW,
    )

    assert result["response_status"] == "EXACT_SEND_LIVE_TRANSPORT_SUCCESS_RECEIPT_WRITTEN"
    assert result["receipt"]["message_id"] == "fixture-message"
    assert result["receipt"]["attachment_sha256"] == scope["attachment_sha256"]
    assert result["receipt"]["body_sha256"] == scoped_issue["body_sha256"]
    assert calls[0][2]["attachments"] == scope["attachment_paths"]
    assert calls[0][2]["send_hold_graduation_ref"] == str(scope["graduation_path"])


def test_the_fixture_window_is_live_so_this_suite_cannot_rot_again(tmp_path: Path) -> None:
    """Guard the guard.

    Two tests in this file drive the broker, which checks expiry against the wall
    clock. When the fixture pinned an absolute window those tests failed silently
    from 2026-07-18T06:30Z onward and the exact-send gate looked broken for ten
    days while it was in fact working correctly. A stale RED is expensive in a
    different way than a stale GREEN: it trains people to ignore the gate.
    """

    scope = _scope(tmp_path)
    now = datetime.now(timezone.utc)
    generated = datetime.fromisoformat(scope["generated_at"])
    expires = datetime.fromisoformat(scope["expires_at"])

    assert generated < now < expires, (
        f"fixture window {generated}..{expires} does not contain {now}; "
        "this suite has rotted again"
    )


def test_an_expired_graduation_is_still_refused(tmp_path: Path) -> None:
    """Adversarial: moving the window must not have softened expiry itself."""

    scope = _scope(tmp_path)
    scope["generated_at"] = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(timespec="seconds")
    scope["expires_at"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    issue_send_hold_scoped_graduation(**scope)

    observed = {key: scope[key] for key in (
        "graduation_path", "send_hold_path", "request_id", "payload_hash",
        "recipient", "body_sha256", "attachment_paths", "attachment_sha256",
    )}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with pytest.raises(SendHoldGraduationError) as caught:
        verify_send_hold_scoped_graduation(**observed, observed_at=now)
    assert "expired" in str(caught.value).lower()


def test_expiry_is_evaluated_against_the_clock_not_the_issuance(tmp_path: Path) -> None:
    """A live grant verifies; the same grant observed later does not."""

    scope = _scope(tmp_path)
    issue_send_hold_scoped_graduation(**scope)
    observed = {key: scope[key] for key in (
        "graduation_path", "send_hold_path", "request_id", "payload_hash",
        "recipient", "body_sha256", "attachment_paths", "attachment_sha256",
    )}

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    assert verify_send_hold_scoped_graduation(**observed, observed_at=now)["status"] == "ACTIVE"

    later = (datetime.fromisoformat(scope["expires_at"]) + timedelta(seconds=1)).isoformat(timespec="seconds")
    with pytest.raises(SendHoldGraduationError):
        verify_send_hold_scoped_graduation(**observed, observed_at=later)
