import sqlite3
from pathlib import Path

import hitl_action_service
import hitl_pending_store
from cassandra_recommendation_loop import (
    DECISION_ACCEPTED,
    DECISION_DENIED,
    DECISION_MODIFIED,
    Recommendation,
    accept_recommendation,
    deny_recommendation,
    emit_recommendation,
    get_recommendation,
    get_recommendation_outcomes,
    modify_recommendation,
)
from hitl_pending_store import WAITING_FOR_APPROVAL


def _isolate_hitl(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hitl_pending_store, "HITL_STATE_PATH", tmp_path / "hitl_state.json")
    monkeypatch.setattr(hitl_pending_store, "HITL_AUDIT_LOG", tmp_path / "hitl_audit.jsonl")
    monkeypatch.setattr(hitl_pending_store, "HITL_FLAG_PATH", tmp_path / "hitl_enabled.flag")
    monkeypatch.setattr(hitl_action_service._store, "HITL_STATE_PATH", tmp_path / "hitl_state.json")
    monkeypatch.setattr(hitl_action_service._store, "HITL_AUDIT_LOG", tmp_path / "hitl_audit.jsonl")
    monkeypatch.setattr(hitl_action_service._store, "HITL_FLAG_PATH", tmp_path / "hitl_enabled.flag")


def _recommendation(recommendation_id: str = "rec_accept") -> Recommendation:
    return Recommendation(
        id=recommendation_id,
        surface="correspondence",
        summary="Draft a bounded Reynolds reply.",
        proposed_action={
            "action_type": hitl_action_service.ACTION_TYPE_TEST_DISPATCH,
            "summary": "Draft Reynolds reply",
            "payload": {
                "thread_id": "thread_reynolds_001",
                "body_preview": "Draft reply preview only.",
            },
            "risk_warning": "Draft only; downstream action gates still apply.",
            "route_back": {"handler": "fixture"},
        },
        rationale="Sally confirmed the date and needs a tidy reply.",
        confidence=0.87,
        created_by="cassandra",
    )


def test_accept_queues_recommendation_action_through_hitl_and_records_ledger(tmp_path, monkeypatch):
    _isolate_hitl(monkeypatch, tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    emit_recommendation(_recommendation(), db_path=db_path)

    outcome = accept_recommendation("rec_accept", db_path=db_path, send_hold_path=tmp_path / "missing_hold.md")

    assert outcome.decision == DECISION_ACCEPTED
    assert outcome.hitl_action_id
    action = hitl_action_service.get_pending_action(outcome.hitl_action_id or "")
    assert action is not None
    assert action["status"] == WAITING_FOR_APPROVAL
    assert action["action_type"] == hitl_action_service.ACTION_TYPE_TEST_DISPATCH
    assert action["payload"]["schema_version"] == hitl_action_service.OPERATOR_ACTION_APPROVAL_REQUEST_SCHEMA
    assert action["payload"]["route_back"]["recommendation_id"] == "rec_accept"
    assert action["execution_result"]["status"] == "pending_approval"

    recommendation = get_recommendation("rec_accept", db_path=db_path)
    assert recommendation is not None
    assert recommendation["status"] == "accepted"
    outcomes = get_recommendation_outcomes("rec_accept", db_path=db_path)
    assert [item["decision"] for item in outcomes] == ["proposed", "accepted"]
    assert outcomes[-1]["hitl_action_id"] == outcome.hitl_action_id

    conn = sqlite3.connect(db_path)
    try:
        ledger_event = conn.execute(
            "SELECT event_type FROM events WHERE event_id = ?",
            (outcome.outcome_id,),
        ).fetchone()
    finally:
        conn.close()
    assert ledger_event == ("cassandra_recommendation_accepted",)


def test_modify_applies_operator_edits_before_hitl_queue(tmp_path, monkeypatch):
    _isolate_hitl(monkeypatch, tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    emit_recommendation(_recommendation("rec_modify"), db_path=db_path)

    outcome = modify_recommendation(
        "rec_modify",
        {
            "summary": "Draft Reynolds reply with operator edit",
            "payload": {
                "body_preview": "Edited preview text.",
                "operator_edit_ref": "telegram_reply_42",
            },
        },
        db_path=db_path,
        send_hold_path=tmp_path / "missing_hold.md",
    )

    assert outcome.decision == DECISION_MODIFIED
    action = hitl_action_service.get_pending_action(outcome.hitl_action_id or "")
    assert action is not None
    assert action["payload"]["summary"] == "Draft Reynolds reply with operator edit"
    assert action["payload"]["payload"]["body_preview"] == "Edited preview text."
    assert action["payload"]["payload"]["operator_edit_ref"] == "telegram_reply_42"
    assert action["payload"]["payload"]["thread_id"] == "thread_reynolds_001"

    recommendation = get_recommendation("rec_modify", db_path=db_path)
    assert recommendation is not None
    assert recommendation["status"] == "modified"
    outcomes = get_recommendation_outcomes("rec_modify", db_path=db_path)
    assert outcomes[-1]["edits"]["payload"]["body_preview"] == "Edited preview text."


def test_deny_records_reason_and_queues_no_hitl_action(tmp_path, monkeypatch):
    _isolate_hitl(monkeypatch, tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    emit_recommendation(_recommendation("rec_deny"), db_path=db_path)

    outcome = deny_recommendation("rec_deny", "Operator will answer this directly.", db_path=db_path)

    assert outcome.decision == DECISION_DENIED
    assert outcome.hitl_action_id is None
    assert hitl_action_service.list_pending_actions() == []
    recommendation = get_recommendation("rec_deny", db_path=db_path)
    assert recommendation is not None
    assert recommendation["status"] == "denied"
    outcomes = get_recommendation_outcomes("rec_deny", db_path=db_path)
    assert outcomes[-1]["reason"] == "Operator will answer this directly."
    assert outcomes[-1]["gate_status"] == "denied_no_action_queued"


def test_send_recommendation_acceptance_stays_blocked_under_send_hold(tmp_path, monkeypatch):
    _isolate_hitl(monkeypatch, tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    send_hold = tmp_path / "SEND_HOLD.md"
    send_hold.write_text("SEND_HOLD active for test.\n", encoding="utf-8")
    emit_recommendation(
        Recommendation(
            id="rec_send_hold",
            surface="correspondence",
            summary="Send the approved exact reply.",
            proposed_action={
                "action_type": hitl_action_service.ACTION_TYPE_EXACT_GMAIL_SEND,
                "payload": {
                    "recipient": "fixture@example.com",
                    "subject": "Reynolds Tavern",
                    "payload_hash": "sha256:fixture",
                    "body_preview": "Approved body preview.",
                },
                "risk_warning": "External send remains blocked by SEND_HOLD.",
                "route_back": {"handler": "exact_send_fixture"},
            },
            rationale="The operator asked Cassandra to prepare the reply path.",
            confidence=0.8,
        ),
        db_path=db_path,
    )

    outcome = accept_recommendation("rec_send_hold", db_path=db_path, send_hold_path=send_hold)

    assert outcome.send_hold_active is True
    assert outcome.send_hold_blocked is True
    assert outcome.gate_status == "queued_pending_hitl_send_hold_active"
    assert outcome.receipt["external_send_performed"] is False
    assert outcome.receipt["approval_bypassed"] is False
    assert outcome.receipt["external_send_allowed"] is False

    action = hitl_action_service.get_pending_action(outcome.hitl_action_id or "")
    assert action is not None
    assert action["status"] == WAITING_FOR_APPROVAL
    assert action["execution_result"]["status"] == "pending_approval"
    assert action["payload"]["action_type"] == hitl_action_service.ACTION_TYPE_EXACT_GMAIL_SEND
