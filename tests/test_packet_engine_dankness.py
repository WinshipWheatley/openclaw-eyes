"""Every packet built through the engine gets scored for dankness.

The critic was registered as a capability but nothing in a reply path called
it, so no real packet was ever scored. Scoring in the engine means all six
agents get the feedback loop, not one.
"""

from __future__ import annotations

from typing import Any, Mapping

from packet_engine import build_agent_packet


def _builder(**_kwargs: Any) -> Mapping[str, Any]:
    return {
        "schema_version": "probe_v0",
        "status": "READY",
        "facts": [
            {
                "fact_id": "money:1",
                "topic": "money",
                "label": "Hilton invoice",
                "value": "2026-1006 is paid.",
                "provenance": "generated_read_model",
                "source_ref": "generated/read_models/x.json",
                "freshness": {"as_of": "2026-07-25"},
            }
        ],
        "source_refs": ["generated/read_models/x.json"],
        "packet_text": "- Hilton invoice: 2026-1006 is paid.",
    }


def test_engine_scores_every_packet_it_builds() -> None:
    packet = build_agent_packet(
        agent="maestro",
        question="is the hilton invoice paid",
        legacy_builder=_builder,
    )

    score = packet.get("packet_dankness")
    assert score, "engine must attach a dankness score to every packet"
    assert "overall" in score
    assert isinstance(score["overall"], (int, float))


def test_scoring_failure_never_breaks_the_packet(monkeypatch) -> None:
    def boom(*_a: Any, **_k: Any):
        raise RuntimeError("critic exploded")

    monkeypatch.setattr("packet_dankness_critic.score_packet_dankness", boom)

    packet = build_agent_packet(
        agent="maestro", question="anything", legacy_builder=_builder
    )

    assert packet["facts"], "packet must survive a critic failure"
    assert packet.get("packet_dankness", {}).get("error")
