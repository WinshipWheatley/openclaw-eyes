"""Team/roster questions get a deterministic grounded answer in the fallback.

Stress-test finding 2026-07-02: "Who's on my team?" truncated the model
(list-shaped answer > num_predict) and the fallback recited FINANCE facts +
raw doctrine — grounded but topically wrong. The roster is enumerable truth
(agent_lane_registry seeds); an LM should never freestyle the org chart.
"""

import protected_generate as pg

_PACKET = {
    "schema_version": "maestro_context_packet_v0",
    "packet_id": "maestro_context_packet:team",
    "facts": [
        {"topic": "finance_invoice_reconciliation", "label": "Coupa", "value": "Coupa is working."},
    ],
    "source_refs": [],
}


def test_team_intent_detection():
    assert pg._is_team_intent("Who's on my team and what does each of them handle?")
    assert pg._is_team_intent("what agents do i have")
    assert pg._is_team_intent("give me the roster")
    assert not pg._is_team_intent("did capital hilton pay me")
    assert not pg._is_team_intent("make the chorus hit harder")


def test_team_fallback_names_all_six_agents():
    answer = pg._fallback_grounded_answer("Who's on my team?", _PACKET)
    lowered = answer.lower()
    for agent in ("maestro", "chief", "cassandra", "guardian", "niles", "hermes"):
        assert agent in lowered, f"missing {agent}: {answer[:200]}"
    # role substance, not just names
    assert "music" in lowered
    assert "safety" in lowered or "security" in lowered
    # and NOT the topically-wrong finance recitation
    assert "coupa" not in lowered


def test_non_team_questions_keep_existing_fallback():
    answer = pg._fallback_grounded_answer("did capital hilton pay me", _PACKET)
    assert "coupa" in answer.lower() or "invent" in answer.lower() or "don't have" in answer.lower()
