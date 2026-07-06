from __future__ import annotations

import agent_build_request_flow as flow


def test_fuzzy_build_ask_to_niles_hands_off_to_chief_then_factory() -> None:
    result = flow.handle_agent_build_request(
        "hey niles can you build me a scene recall helper for the X32",
        addressed_agent="niles",
        factory_capacity_available=True,
        chief_allowance=True,
    )

    assert result["handled"] is True
    assert result["agent_reply"] == "Sending that to Chief."
    assert result["handoff"]["from_agent"] == "niles"
    assert result["handoff"]["to_agent_or_worker"] == "chief"
    assert result["handoff"]["package_type"] == "build_request_handoff_packet"
    assert result["chief_decision"]["status"] == "ADMITTED_TO_FACTORY"
    assert result["chief_decision"]["factory_task"]["requested_by_agent"] == "niles"


def test_fuzzy_build_ask_returns_activation_instructions_when_factory_not_available() -> None:
    result = flow.handle_agent_build_request(
        "niles build an autonomous DAW publisher",
        addressed_agent="niles",
        factory_capacity_available=False,
        chief_allowance=True,
    )

    assert result["handled"] is True
    assert result["chief_decision"]["status"] == "ACTIVATION_REQUIRED"
    assert result["activation_instructions"]["next_required_step"]
    assert "polish_loop_factory_mode" in result["activation_instructions"]["capability_id"]
    assert result["operator_message"] == result["chief_decision"]["operator_message"]


def test_operator_can_clarify_activation_instructions_with_agent() -> None:
    result = flow.handle_agent_build_request(
        "niles build an autonomous DAW publisher",
        addressed_agent="niles",
        factory_capacity_available=False,
        chief_allowance=True,
    )

    clarification = flow.clarify_activation_instructions(
        "what does that mean?",
        previous_result=result,
        addressed_agent="niles",
    )

    assert clarification["handled"] is True
    assert clarification["responding_agent"] == "niles"
    assert "Chief needs" in clarification["plain_language"]
    assert result["activation_instructions"]["next_required_step"] in clarification["grounded_instructions"]
