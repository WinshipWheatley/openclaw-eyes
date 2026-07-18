from __future__ import annotations

import json

import maestro_context_packet as packets


def test_pending_action_packet_fact_is_metadata_only(tmp_path):
    path = tmp_path / "hitl_pending_state.json"
    path.write_text(
        json.dumps(
            {
                "5FF438AC": {
                    "action_id": "5FF438AC",
                    "action_type": "send_invoice_email",
                    "status": "WAITING_FOR_APPROVAL",
                    "requested_at": "2026-07-17T18:00:00+00:00",
                    "expires_at": "2099-07-18T18:00:00+00:00",
                    "payload": {
                        "summary": "Protected invoice send ready for approval.",
                        "payload": {
                            "operator_eli5": "The exact version you just approved is ready to send.",
                            "send_hold_required": True,
                            "invoice_number": "2026-1004",
                            "recipient": "must-not-leak@example.com",
                            "subject": "must not leak",
                        },
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    facts = packets._pending_operator_action_facts(path)

    assert len(facts) == 1
    fact = facts[0]
    assert fact["topic"] == "pending_operator_action"
    assert fact["source_ref"] == "hitl_pending_store:5FF438AC"
    assert "WAITING_FOR_APPROVAL" in fact["value"]
    assert "has not executed" in fact["value"]
    assert "you just approved" not in fact["value"]
    assert "must-not-leak" not in fact["value"]


def test_advisory_relevance_keeps_current_pending_action():
    pending = {
        "fact_id": "pending_operator_action:5FF438AC",
        "topic": "pending_operator_action",
        "label": "Current Guardian approval waiting for the operator",
        "value": "Action 5FF438AC is WAITING_FOR_APPROVAL.",
        "source_ref": "hitl_pending_store:5FF438AC",
    }
    unrelated = {
        "fact_id": "finance:old",
        "topic": "finance",
        "label": "Old invoice",
        "value": "Unrelated.",
        "source_ref": "generated/read_models/finance.json",
    }

    scoped, proof = packets._apply_question_relevance_contract(
        [unrelated, pending],
        question="Maestro, what do you think the next correct step is?",
        session={"interpreter_route": "BRAIN"},
        fact_selection=None,
        applied_skills=(),
    )

    assert scoped[0] == pending
    assert scoped[1]["source_ref"] == "question_relevance_contract:advisory_current_state"
    assert "current Guardian action fact" in scoped[1]["value"]
    assert "general, non-sensitive guidance" not in scoped[1]["value"]
    assert proof["question_relevance_scope"] == "advisory_current_state"


def test_approved_guardian_decision_is_current_state_not_execution_proof(tmp_path):
    path = tmp_path / "hitl_pending_state.json"
    path.write_text(
        json.dumps(
            {
                "5FF438AC": {
                    "action_type": "exact_gmail_send",
                    "status": "APPROVED",
                    "requested_at": "2026-07-17T18:00:00+00:00",
                    "expires_at": "2099-07-18T18:00:00+00:00",
                    "payload": {
                        "payload": {
                            "invoice_number": "2026-1004",
                            "send_hold_required": True,
                            "recipient": "must-not-leak@example.com",
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    facts = packets._guardian_action_state_facts(path)

    assert len(facts) == 1
    assert facts[0]["topic"] == "current_guardian_action"
    assert facts[0]["decision_status"] == "APPROVED"
    assert "execution is not proven" in facts[0]["value"]
    assert "SEND_HOLD remains required" in facts[0]["value"]
    assert "must-not-leak" not in facts[0]["value"]
