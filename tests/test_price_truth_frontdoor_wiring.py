from __future__ import annotations

import pytest

import maestro_cassandra_responder as responder


@pytest.mark.parametrize(
    "question",
    (
        "What do I charge for a solo acoustic set now?",
        "how much did I make on gigs last year vs now?",
        "whats my number for a full band these days",
    ),
)
def test_live_frontdoor_owns_price_truth_without_model_or_staging(question: str) -> None:
    handle_calls: list[str] = []
    result = responder.answer_frontdoor_chat(
        question,
        session={"as_of_date": "2026-07-19"},
        handle_fn=lambda text, _session: handle_calls.append(text) or ["should not run"],
        protected_generate_fn=lambda *_args, **_kwargs: pytest.fail("model ran"),
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "price_truth_temporal"
    assert result.allowed_to_call_handle is False
    assert handle_calls == []
    assert result.machine_proof["model_call_performed"] is False
    assert result.machine_proof["workflow_package_staged"] is False
    assert result.machine_proof["action_surfaces_opened"] is False
    packet = result.machine_proof["price_truth_temporal_packet"]
    assert packet["status"] == "TRACE_READY_NOT_SHIPPED"
    assert packet["claim_audit"]["status"] == "PASS"
    assert packet["ship_gate"] == "MAC_COMPUTER_USE_STRESS_TEST_REQUIRED"


def test_phone_number_negative_control_is_not_claimed_by_price_owner() -> None:
    intent, allowed, reason = responder.classify_frontdoor_intent("what's my phone number")
    assert intent != "price_truth_temporal"
    assert allowed is True
    assert reason == ""
