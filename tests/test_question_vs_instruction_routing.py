"""A question in the middle of a message is still a question.

The acceptance prompt opens with a framing line and closes with a directive, and asks
its real question in between. `_is_general_question_text` looked only at the FIRST
word and the LAST character, so it read as an instruction and routed to
operator_instruction staging — which performs no lookup, so the answer was UNKNOWN no
matter how good the packet was.

No test here hardcodes the operator's phrase. The live SHAPE is what is asserted:
preamble, embedded question, trailing directive.
"""

from __future__ import annotations

import pytest

import workflow_package_request_consumer as c

QUESTIONS = [
    # the live shape: framing, embedded question, trailing directive
    "STATUS CHECK — use only grounded packets. What is the current top blocker? "
    "If unavailable, say UNKNOWN rather than guessing.",
    "Quick one before I go. Which invoices are unpaid this month? Keep it short.",
    "Context: I'm on the road.\nWhat did we agree with the client?\nDon't send anything.",
    "Heads up, reviewing the board now. How many gigs are booked for August?",
    "What is the current top blocker?",
    "which clients are overdue",
]

INSTRUCTIONS = [
    "Draft the invoice for St Annes and hold it for review.",
    "Stage the follow-up email to Megan. Do not send it.",
    "Add a calendar block on Friday afternoon.",
    "Update the work board with the new deadline and tell Chief.",
    "Prepare the monthly speaker rental invoice.",
]


@pytest.mark.parametrize("text", QUESTIONS)
def test_questions_are_recognised_wherever_they_sit(text: str) -> None:
    assert c._is_general_question_text(text) is True, "a genuine question routed to staging"


@pytest.mark.parametrize("text", INSTRUCTIONS)
def test_imperatives_still_stage(text: str) -> None:
    """NON-VACUITY: a detector that says yes to everything destroys staging."""

    assert c._is_general_question_text(text) is False, "an instruction routed to answering"


def test_the_live_shape_specifically() -> None:
    """Preamble + embedded question + trailing directive, no operator phrase reused."""

    text = (
        "ACCEPTANCE CHECK — Use only grounded packets you can actually retrieve. "
        "What is the smallest useful version and what blocks it? "
        "Answer in at most 6 bullets. If the packet is unavailable, say UNKNOWN."
    )
    assert c._is_general_question_text(text) is True


def test_an_instruction_with_a_trailing_question_mark_is_still_a_question() -> None:
    """Deliberate: ambiguity resolves toward answering, which acts on nothing."""

    assert c._is_general_question_text("Stage the invoice, can you?") is True


def test_empty_and_whitespace_are_not_questions() -> None:
    for text in ("", "   ", "\n\n"):
        assert c._is_general_question_text(text) is False


def test_multiline_questions_are_found() -> None:
    assert c._is_general_question_text("Note to self.\nwhy did the send fail\nthanks") is True


def test_a_long_imperative_paragraph_never_becomes_a_question() -> None:
    text = (
        "Please prepare the July invoice for the speaker rental. Use the standard "
        "template. Attach the PDF. Leave it in drafts for review. Do not send."
    )
    assert c._is_general_question_text(text) is False
