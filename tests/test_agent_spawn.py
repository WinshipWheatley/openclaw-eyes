"""Spawning a doer: a character, played by a model, given a target.

Operator's architecture: the LM2 spot is sometimes an autospawned DOER. The
agent keeps its name (Cassandra, Niles...) but is played by whichever model
fits the task -- Luna, Terra, Sol, or the local qwen. It gets a target-shaped
packet and does the job.

A doer produces WORK PRODUCT, never effects: money, sends, deletes and installs
stay operator-gated no matter what a doer concludes.
"""

from __future__ import annotations

from typing import Any, Mapping

import agent_spawn


def _builder(**_kwargs: Any) -> Mapping[str, Any]:
    return {
        "schema_version": "probe_v0",
        "status": "READY",
        "facts": [
            {
                "fact_id": "invoice:1",
                "topic": "invoice",
                "label": "LAMD invoice",
                "value": "2026-1004 prepared, $100, awaiting review.",
                "provenance": "generated_read_model",
                "source_ref": "generated/read_models/lamd.json",
                "freshness": {"as_of": "2026-07-25"},
            }
        ],
        "source_refs": ["generated/read_models/lamd.json"],
        "packet_text": "- LAMD invoice: 2026-1004 prepared.",
    }


def test_hard_task_is_played_by_the_hard_lane_model() -> None:
    spawn = agent_spawn.spawn_doer(
        agent="cassandra",
        target="reconcile the whole receivables ledger against the bank",
        task_type="deep analysis of financial reconciliation",
        risk_tier="high",
        legacy_builder=_builder,
        model_call=lambda prompt, **kw: "done",
    )

    assert spawn.lane == "hard_lane"
    assert "sol" in spawn.model


def test_easy_task_is_played_by_the_cheap_lane() -> None:
    spawn = agent_spawn.spawn_doer(
        agent="niles",
        target="list the tracks",
        task_type="easy lookup",
        legacy_builder=_builder,
        model_call=lambda prompt, **kw: "done",
    )

    assert spawn.lane == "easy_lane"
    assert "luna" in spawn.model


def test_doer_gets_a_target_shaped_packet_and_returns_work_product() -> None:
    captured: dict[str, str] = {}

    def fake_model(prompt: str, **_kw: Any) -> str:
        captured["prompt"] = prompt
        return "Invoice 2026-1004 is ready for your review."

    spawn = agent_spawn.spawn_doer(
        agent="cassandra",
        target="prepare the LAMD July invoice for review",
        legacy_builder=_builder,
        model_call=fake_model,
    )

    assert spawn.packet["assignment"]["target"].startswith("prepare the LAMD")
    assert "ASSIGNMENT" in captured["prompt"]
    assert spawn.result == "Invoice 2026-1004 is ready for your review."
    assert spawn.receipt["agent"] == "cassandra"


def test_model_failure_is_honest_not_fabricated() -> None:
    def boom(prompt: str, **_kw: Any) -> str:
        raise RuntimeError("model down")

    spawn = agent_spawn.spawn_doer(
        agent="chief",
        target="do a thing",
        legacy_builder=_builder,
        model_call=boom,
    )

    assert spawn.result is None
    assert spawn.error


def test_doer_declares_it_holds_no_effect_authority() -> None:
    spawn = agent_spawn.spawn_doer(
        agent="cassandra",
        target="send the invoice",
        legacy_builder=_builder,
        model_call=lambda prompt, **kw: "ok",
    )

    assert spawn.receipt["effect_authority"] == "none"


def test_doer_instruction_forbids_routing_around_a_constraint() -> None:
    """Urgency must never read as permission to get around a rule."""

    text = agent_spawn.DOER_INSTRUCTION.lower()
    assert "bypass" in text or "around" in text
    assert "stop" in text


def test_oversized_packet_fails_honestly_not_silently(monkeypatch) -> None:
    """The local model returns '' for an over-context prompt. An empty result
    that looks like 'the doer had nothing to say' hides a real wall."""

    spawn = agent_spawn.spawn_doer(
        agent="chief",
        target="x",
        legacy_builder=_builder,
        model_call=lambda prompt, **kw: "",
        max_prompt_chars=50,
    )

    assert spawn.result is None
    assert "prompt" in (spawn.error or "").lower()
    assert spawn.receipt["error"]
