"""The Niles regression, the generic-retry regression, and the citation rule.

Each named test below reproduces a specific observed failure from the 2026-07-28
six-agent battery, using the exact wording that was recorded.
"""

from __future__ import annotations

import pytest

import grounded_answer_contract as gac

#: Verbatim from the battery. Niles was asked a technical exact-send question.
NILES_EXACT_PROMPT = (
    "For the exact-send gate, what evidence proves a draft was approved before it "
    "was released, and which artifact records it?"
)
NILES_OBSERVED_REPLY = "What's the main goal: groove, melody, or arrangement?"

CASSANDRA_OBSERVED_REPLY = (
    "The language model didn't return a usable routing decision. I left your "
    "request untouched; please try again in a moment."
)


# ------------------------------------------------------- question dominance

def test_the_exact_niles_regression() -> None:
    """THE recorded failure. A persona opener instead of an answer or an UNKNOWN."""

    ok, reason = gac.check_question_dominance(NILES_EXACT_PROMPT, NILES_OBSERVED_REPLY)
    assert ok is False
    assert reason == gac.UNSAFE_PERSONA_OVERRIDE


def test_an_honest_unknown_outranks_a_smooth_deflection() -> None:
    ok, _ = gac.check_question_dominance(NILES_EXACT_PROMPT,
                                         "UNKNOWN — no exact-send packet available.")
    assert ok is True


def test_a_real_answer_passes() -> None:
    """NON-VACUITY: a contract that rejects everything protects nothing."""

    reply = ("The scoped graduation records approval; the exact-send receipt in "
             "send_hold_scoped_graduation records the release.")
    ok, reason = gac.check_question_dominance(NILES_EXACT_PROMPT, reply)
    assert ok is True, reason


def test_persona_openers_are_allowed_when_they_also_answer() -> None:
    """A persona is not the enemy — displacing the question is."""

    reply = ("Happy to help! What proves it is the scoped graduation receipt for "
             "that exact draft.")
    ok, _ = gac.check_question_dominance(NILES_EXACT_PROMPT, reply)
    assert ok is True


def test_an_empty_reply_is_never_acceptable() -> None:
    ok, reason = gac.check_question_dominance(NILES_EXACT_PROMPT, "   ")
    assert ok is False and reason == "empty_reply"


@pytest.mark.parametrize("deflection", [
    "What's the main goal: groove, melody, or arrangement?",
    "Tell me more about the track and I'll help.",
    "Let's start with what you're going for.",
])
def test_known_persona_deflections_are_detected(deflection: str) -> None:
    assert gac.is_persona_deflection(deflection) is True


def test_a_technical_answer_is_not_mistaken_for_a_deflection() -> None:
    assert gac.is_persona_deflection(
        "The main goal of the gate is to bind approval to exact bytes."
    ) is False


# ----------------------------------------------------- named routing failure

def test_the_observed_generic_retry_is_detected() -> None:
    """Cassandra and Chief both returned exactly this."""

    assert gac.is_generic_retry(CASSANDRA_OBSERVED_REPLY) is True


def test_a_named_failure_is_not_flagged_as_generic() -> None:
    named = gac.named_routing_failure(
        agent="cassandra", stage="semantic_vote", failure_kind="MODEL_FAILURE",
        detail="vote returned no usable decision",
    )
    assert gac.is_generic_retry(named) is False


def test_a_named_failure_tells_the_operator_what_happened() -> None:
    named = gac.named_routing_failure(
        agent="chief", stage="semantic_vote", failure_kind="MODEL_FAILURE",
        detail="vote returned no usable decision",
    )
    assert "chief" in named
    assert "semantic_vote" in named
    assert "MODEL_FAILURE" in named
    assert "nothing was sent" in named.lower()


def test_a_named_failure_does_not_promise_that_retrying_helps() -> None:
    """"Try again in a moment" trains people to retry forever."""

    named = gac.named_routing_failure(agent="chief", stage="routing",
                                      failure_kind="MODEL_FAILURE")
    assert "unless the named cause changed" in named


def test_the_safety_claim_survives_the_rewording() -> None:
    """The old message's one virtue was saying nothing ran. Keep it."""

    named = gac.named_routing_failure(agent="cassandra", stage="routing",
                                      failure_kind="TIMEOUT")
    for claim in ("not run", "nothing was sent"):
        assert claim in named.lower()


# ------------------------------------------------------------- provenance

def test_a_factual_answer_without_evidence_is_a_violation() -> None:
    ok, reason = gac.check_provenance(
        "What is the current top blocker?", "The top blocker is packet delivery."
    )
    assert ok is False
    assert reason == gac.MISSING_PROVENANCE


def test_naming_the_artifact_satisfies_the_rule() -> None:
    ok, _ = gac.check_provenance(
        "What is the current top blocker?",
        "The top blocker is packet delivery. Evidence: chief_status_rail.json",
    )
    assert ok is True


def test_an_unknown_needs_no_citation_because_it_claims_nothing() -> None:
    ok, _ = gac.check_provenance("What is the current top blocker?", "UNKNOWN.")
    assert ok is True


def test_chit_chat_is_not_forced_to_cite() -> None:
    """NON-VACUITY in the other direction: over-enforcement is its own failure."""

    ok, _ = gac.check_provenance("thanks, good work", "Anytime.")
    assert ok is True
