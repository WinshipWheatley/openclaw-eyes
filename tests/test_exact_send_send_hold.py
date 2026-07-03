from pathlib import Path

import cassandra_operator_objective_loop as loop


REQUEST_ID = "exact_send_authority_request:test-send-hold"
OBJECTIVE_ID = "objective:test-send-hold"
PAYLOAD_HASH = "sha256:" + ("a" * 64)
GENERATED_AT = "2026-06-15T06:00:00+00:00"
EXPIRES_AT = "2099-01-01T00:00:00+00:00"


def _approved_exact_gmail_send_action() -> dict:
    return {
        "action_id": "hitl_action:test-send-hold",
        "action_type": "exact_gmail_send",
        "status": "APPROVED",
        "idempotency_key": REQUEST_ID,
        "approved_by": "operator:winship",
        "approved_at": GENERATED_AT,
        "payload": {
            "request_id": REQUEST_ID,
            "owner_objective_id": OBJECTIVE_ID,
            "route_back": {
                "type": "cassandra_exact_send_executor",
                "objective_id": OBJECTIVE_ID,
            },
            "payload": {
                "request_id": REQUEST_ID,
                "objective_id": OBJECTIVE_ID,
                "recipient": "ops@example.invalid",
                "subject": "Exact send hold regression",
                "payload_hash": PAYLOAD_HASH,
                "expires_at": EXPIRES_AT,
            },
        },
    }


def test_exact_send_routeback_refuses_when_send_hold_file_exists(tmp_path, monkeypatch):
    send_hold = tmp_path / "SEND_HOLD.md"
    send_hold.write_text("SEND_HOLD active for regression test.\n", encoding="utf-8")

    def _transport_must_not_be_constructed(**_kwargs):
        raise AssertionError("SEND_HOLD must block before exact-send transport construction")

    monkeypatch.setattr(loop, "GovernedGmailBrokerSendTransport", _transport_must_not_be_constructed)

    result = loop.run_exact_send_operator_action_routeback(
        _approved_exact_gmail_send_action(),
        sqlite_path=tmp_path / "objectives.sqlite",
        receipt_dir=tmp_path / "receipts",
        send_hold_path=send_hold,
        generated_at=GENERATED_AT,
    )

    assert result["response_status"] == "EXACT_SEND_HITL_ROUTEBACK_REFUSED"
    assert result["refusal_reason"] == "send_hold_active"
    assert result["send_hold_active"] is True
    assert result["send_hold_ref"] == str(send_hold)
    assert result["gate_convergence"]["send_hold_active"] is True
    assert result["execution_performed"] is False
    assert result["gmail_api_called"] is False
    assert result["email_send_performed"] is False
    assert Path(result["refusal_receipt_path"]).is_file()
    assert result["receipt"]["reason"] == "send_hold_active"
    assert result["receipt"]["send_hold_active"] is True


def test_exact_send_routeback_keeps_absent_hold_as_operator_lift(tmp_path):
    send_hold = tmp_path / "missing_SEND_HOLD.md"

    result = loop.run_exact_send_operator_action_routeback(
        _approved_exact_gmail_send_action(),
        sqlite_path=tmp_path / "objectives.sqlite",
        receipt_dir=tmp_path / "receipts",
        send_hold_path=send_hold,
        generated_at=GENERATED_AT,
    )

    assert result["response_status"] == "EXACT_SEND_LIVE_TRANSPORT_REFUSED"
    assert result["refusal_reason"] != "send_hold_active"
    assert result.get("send_hold_active") is not True
    assert result["execution_performed"] is False
    assert result["receipt"]["gmail_api_called"] is False
    assert result["receipt"]["email_send_performed"] is False
    assert Path(result["refusal_receipt_path"]).is_file()


def test_exact_send_routeback_missing_hold_with_tamper_expectation_fails_closed_and_alerts(tmp_path):
    send_hold = tmp_path / "SEND_HOLD.md"
    alerts = []

    result = loop.run_exact_send_operator_action_routeback(
        _approved_exact_gmail_send_action(),
        sqlite_path=tmp_path / "objectives.sqlite",
        receipt_dir=tmp_path / "receipts",
        send_hold_path=send_hold,
        generated_at=GENERATED_AT,
        send_hold_alert_sink=alerts.append,
        send_hold_missing_is_tamper=True,
    )

    assert result["response_status"] == "EXACT_SEND_HITL_ROUTEBACK_REFUSED"
    assert result["refusal_reason"] == "send_hold_active"
    assert result["send_hold_active"] is True
    assert result["send_hold_ref"] == str(send_hold)
    assert send_hold.is_file()
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "send_hold_sentinel_vanished"
    assert alerts[0]["fail_closed"] is True
    assert result["execution_performed"] is False
    assert result["gmail_api_called"] is False
    assert result["email_send_performed"] is False
