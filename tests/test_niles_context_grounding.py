"""Niles can reach its own gear knowledge and the read-model library.

Niles had no conversational grounding at all: a status renderer, a subprocess
intake parser, and introspection. Its gear KB — which already knows the X32,
Push 2, APC40, MPC One, FCB1010, Logic Pro X, Ableton Live and TH-U — was
unreachable when answering a question.
"""

from __future__ import annotations

import json
from pathlib import Path

import niles_context_grounding as grounding


def test_niles_grounding_is_built_through_the_packet_engine(tmp_path: Path) -> None:
    """Same shared path as every other agent: persona, receipt, dank scoring."""

    root = tmp_path / "generated" / "read_models"
    root.mkdir(parents=True)

    packet = grounding.niles_engine_packet(
        "x32 monitor mix", read_model_root=root
    )

    assert packet["agent_id"] == "niles"
    assert packet["packet_engine_receipt"]
    assert packet["persona_delivery"]


def test_gear_question_reaches_the_matching_device() -> None:
    lines = grounding.select_gear_context("how do I control the x32 monitor mix")

    joined = " ".join(lines).lower()
    assert "x32" in joined


def test_controller_question_reaches_ableton_gear() -> None:
    lines = grounding.select_gear_context("push 2 ableton mapping")

    joined = " ".join(lines).lower()
    assert "push" in joined or "ableton" in joined


def test_unrelated_question_returns_no_gear() -> None:
    assert grounding.select_gear_context("what is the weather in paris") == ()


def test_grounding_combines_gear_and_demand_read_models(tmp_path: Path) -> None:
    root = tmp_path / "generated" / "read_models"
    root.mkdir(parents=True)
    (root / "niles_track_registry.json").write_text(
        json.dumps({"tracks": ["one"]}), encoding="utf-8"
    )

    text = grounding.build_niles_grounding(
        "what is in the niles track registry", read_model_root=root
    )

    assert "niles_track_registry" in text


def test_grounded_answer_uses_the_rig_knowledge_in_its_prompt() -> None:
    seen: dict[str, str] = {}

    def fake_model(prompt: str) -> str:
        seen["prompt"] = prompt
        return "Route TH-U as a plugin on an audio track."

    reply = grounding.answer_with_grounding(
        "how do I route th-u into logic pro x", model_call=fake_model
    )

    assert reply == "Route TH-U as a plugin on an audio track."
    assert "logic" in seen["prompt"].lower() or "th-u" in seen["prompt"].lower()


def test_grounded_answer_declines_when_it_knows_nothing_relevant() -> None:
    def fake_model(prompt: str) -> str:  # pragma: no cover - must not be called
        raise AssertionError("model must not be called without grounding")

    assert (
        grounding.answer_with_grounding(
            "what is the weather in paris", model_call=fake_model
        )
        is None
    )


def test_grounded_answer_returns_none_when_the_model_fails() -> None:
    def failing_model(prompt: str) -> str:
        raise RuntimeError("model down")

    assert (
        grounding.answer_with_grounding(
            "x32 monitor mix", model_call=failing_model
        )
        is None
    )


def test_grounding_is_empty_when_nothing_is_relevant(tmp_path: Path) -> None:
    root = tmp_path / "generated" / "read_models"
    root.mkdir(parents=True)

    assert grounding.build_niles_grounding(
        "what is the weather in paris", read_model_root=root
    ) == ""
