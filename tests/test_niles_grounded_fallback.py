"""Niles retries an unroutable question from its own knowledge."""

from __future__ import annotations

import niles_context_grounding as grounding


UNROUTED = (
    "The language model didn't return a usable routing decision. "
    "I left your request untouched; please try again in a moment."
)


def test_unroutable_question_is_retried_from_niles_knowledge(monkeypatch) -> None:
    monkeypatch.setattr(
        "niles_context_grounding.answer_with_grounding",
        lambda question, **kw: "Run TH-U as a plugin on an audio track in Logic.",
    )

    result = grounding.apply_grounded_fallback(
        UNROUTED, "how do I route th-u into logic pro x"
    )

    assert result == "Run TH-U as a plugin on an audio track in Logic."


def test_successful_intake_result_is_never_replaced(monkeypatch) -> None:
    monkeypatch.setattr(
        "niles_context_grounding.answer_with_grounding",
        lambda question, **kw: "SHOULD NOT BE USED",
    )

    routed = "Logged gig: Reynolds Tavern on 2026-08-01."
    assert grounding.apply_grounded_fallback(routed, "log a gig") == routed


def test_no_relevant_knowledge_keeps_the_honest_reply(monkeypatch) -> None:
    monkeypatch.setattr(
        "niles_context_grounding.answer_with_grounding", lambda question, **kw: None
    )

    assert (
        grounding.apply_grounded_fallback(UNROUTED, "weather in paris")
        == UNROUTED
    )


def test_grounding_failure_keeps_the_honest_reply(monkeypatch) -> None:
    def boom(question, **kw):
        raise RuntimeError("grounding exploded")

    monkeypatch.setattr("niles_context_grounding.answer_with_grounding", boom)

    assert (
        grounding.apply_grounded_fallback(UNROUTED, "x32 monitor mix")
        == UNROUTED
    )
