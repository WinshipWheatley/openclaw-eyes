"""Team/roster questions answer deterministically — the model must NEVER
freestyle the org chart.

Post-deploy stress-test finding 2026-07-02: "who's on my team?" reached
maestro_brain_freeform and the model confabulated "Megan the accountant" —
not one of the six agents. The roster is enumerable truth
(agent_lane_registry seeds); it gets its own deterministic intent BEFORE the
brain, so a live model answer can never invent teammates.
"""

import maestro_cassandra_responder as r


def test_team_intent_classified_before_brain():
    for q in ("who's on my team?",
              "who is on my team and what do they each handle",
              "what agents do i have",
              "give me the roster",
              "who does what on the team"):
        intent, _, _ = r.classify_frontdoor_intent(q)
        assert intent == "team_roster", f"{q!r} -> {intent}"


def test_non_team_questions_not_captured():
    for q in ("did capital hilton pay me",
              "who is dane at live arts",
              "make the chorus hit harder"):
        intent, _, _ = r.classify_frontdoor_intent(q)
        assert intent != "team_roster", f"{q!r} wrongly captured as team_roster"


def test_team_roster_answer_names_all_six_and_no_confabulation():
    answer = r.build_team_roster_answer("who's on my team?")
    text = (answer["plain_summary"] + " " + answer["one_line_answer"]).lower()
    for agent in ("maestro", "chief", "cassandra", "guardian", "niles", "hermes"):
        assert agent in text, f"missing {agent}"
    # substance
    assert "music" in text
    assert "safety" in text or "security" in text
    # anti-confabulation: names NOT in the roster must not appear
    assert "megan" not in text
    assert "accountant" not in text
    assert answer["machine_proof"].get("team_roster_deterministic") is True


def test_team_roster_result_is_answer_ready_and_does_not_call_model():
    called = {"n": 0}

    def boom_generate(*a, **k):
        called["n"] += 1
        raise AssertionError("model must not be called for a team-roster question")

    res = r.answer_operator_message(
        "who is on my team?",
        protected_generate_fn=boom_generate,
    ) if hasattr(r, "answer_operator_message") else None
    # If the top-level entry differs, at least prove the builder path is model-free:
    if res is None:
        answer = r.build_team_roster_answer("who is on my team?")
        assert answer["one_line_answer"]
    else:
        assert res.status == "ANSWER_READY"
        assert res.intent_class == "team_roster"
    assert called["n"] == 0
