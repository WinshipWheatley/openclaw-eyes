from __future__ import annotations

import pytest

from price_truth_packet_adapter import build_price_truth_packet


@pytest.mark.parametrize(
    ("question", "question_class", "subject_ref"),
    (
        ("What do I charge for a solo acoustic set now?", "C1", "solo_acoustic"),
        ("What did I charge for solo work in the past versus now?", "C2", "solo_acoustic"),
        ("Is the evidence for my solo pricing fresh?", "C3", "solo_acoustic"),
        ("What changes in band pricing when the organization comes online?", "C4", "band_event"),
    ),
)
def test_natural_price_questions_route_to_trace_packet(question: str, question_class: str, subject_ref: str) -> None:
    packet = build_price_truth_packet(question, as_of="2026-07-19")

    assert packet["status"] == "TRACE_READY_NOT_SHIPPED"
    assert packet["intent_class"] == "price_truth_temporal"
    assert packet["question_class"] == question_class
    assert packet["subject_ref"] == subject_ref
    assert packet["ship_gate"] == "MAC_COMPUTER_USE_STRESS_TEST_REQUIRED"
    assert packet["action_surfaces_opened"] is False
    assert packet["temporal_truth_answer"]["trace"]["selected_fact_refs"]


def test_unrelated_question_does_not_route() -> None:
    assert build_price_truth_packet("How is the fleet doing?")["status"] == "NOT_RELEVANT"


def test_solo_now_answer_is_honest_unknown_with_history_separate() -> None:
    packet = build_price_truth_packet("What should I charge for a solo acoustic gig?", as_of="2026-07-19")
    answer = packet["temporal_truth_answer"]

    assert answer["direct_answer"]["value_known"] is False
    assert answer["historical_context"][0]["typed_value"]["minor_units"] == 25000
    assert "not declared" in packet["answer_text"].lower()
    assert answer["machine_proof"]["historical_promoted_to_current"] is False
