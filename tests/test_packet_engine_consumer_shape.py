"""Daemon and spawned packets are shaped differently, not just persona-tagged.

Operator's architecture: the LM2 spot is sometimes an autospawned DOER --
a character (Cassandra, Niles...) played by whichever model fits the task.
A doer's packet is "here is your target, do the job". A daemon's packet is
"help me think" -- breadth, history, nuance, and what the doers did.

Before this, consumer_kind only decided whether the persona core was attached;
both modes received identical content.
"""

from __future__ import annotations

from typing import Any, Mapping

from packet_engine import build_agent_packet


def _wide_builder(**_kwargs: Any) -> Mapping[str, Any]:
    facts = [
        {
            "fact_id": f"t{i}",
            "topic": topic,
            "label": f"{topic} note",
            "value": value,
            "provenance": "generated_read_model",
            "source_ref": f"generated/read_models/{topic}.json",
            "freshness": {"as_of": "2026-07-25"},
        }
        for i, (topic, value) in enumerate(
            [
                ("invoice", "LAMD July invoice 2026-1004 is prepared."),
                ("history", "Last month's gig at Reynolds went fine."),
                ("presence", "6 of 6 agents online."),
                ("weather", "Unrelated chatter about the forecast."),
                ("album", "Album matrix review is pending."),
            ]
        )
    ]
    return {
        "schema_version": "probe_v0",
        "status": "READY",
        "facts": facts,
        "source_refs": [f["source_ref"] for f in facts],
        "packet_text": "\n".join(f"- {f['label']}: {f['value']}" for f in facts),
    }


def test_spawned_doer_packet_is_target_shaped_and_bounded() -> None:
    packet = build_agent_packet(
        agent="cassandra",
        question="send the LAMD invoice",
        consumer_kind="spawned",
        target="prepare the LAMD July invoice for review",
        legacy_builder=_wide_builder,
    )

    assignment = packet.get("assignment")
    assert assignment, "a doer packet must carry its target"
    assert "LAMD" in assignment["target"]
    # the doer gets the invoice fact, not the unrelated breadth
    topics = {f["topic"] for f in packet["facts"] if f.get("topic")}
    assert "invoice" in topics
    assert "weather" not in topics


def test_daemon_packet_keeps_breadth_for_judgement() -> None:
    packet = build_agent_packet(
        agent="cassandra",
        question="what is going on with the invoices",
        consumer_kind="daemon",
        legacy_builder=_wide_builder,
    )

    assert packet.get("assignment") is None
    topics = {f["topic"] for f in packet["facts"] if f.get("topic")}
    assert {"invoice", "history", "presence"} <= topics


def test_spawned_without_a_target_still_builds() -> None:
    packet = build_agent_packet(
        agent="niles",
        question="do the thing",
        consumer_kind="spawned",
        legacy_builder=_wide_builder,
    )

    assert packet["agent_id"] == "niles"
    assert packet["facts"]


def test_doer_facts_are_concentrated_not_raw_dumps() -> None:
    """Premium potency: max signal per token. A doer packet is cured, not raw --
    a wall of JSON blows the model's context and returns nothing."""

    def fat_builder(**_kwargs: Any) -> Mapping[str, Any]:
        return {
            "status": "READY",
            "facts": [
                {
                    "fact_id": "invoice:1",
                    "topic": "invoice",
                    "label": "LAMD invoice",
                    "value": "x" * 4000,
                    "provenance": "generated_read_model",
                    "source_ref": "generated/read_models/lamd.json",
                }
            ],
            "source_refs": ["generated/read_models/lamd.json"],
            "packet_text": "- LAMD invoice: " + "x" * 4000,
        }

    packet = build_agent_packet(
        agent="cassandra",
        question="prepare the invoice",
        consumer_kind="spawned",
        target="prepare the LAMD invoice",
        legacy_builder=fat_builder,
    )

    assert len(packet["packet_text"]) < 2000
