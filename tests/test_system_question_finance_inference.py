"""Cold finance questions must reach the finance answers, not the dead end.

Stress-test finding 2026-07-02: "Did Capital Hilton pay me?" (a flagship
operator ask) fell through to "I do not have a deterministic local answer"
because the contextual finance lane only fires when world/thread refs are
already set by the conversation. When the question NAMES the client and asks
about money, the lane must be inferred from content.
"""

from pathlib import Path

from system_question_answer import answer_system_question, infer_lane_from_question


def test_infer_lane_capital_hilton_payment():
    assert infer_lane_from_question("Did Capital Hilton pay me?") == ("finance", "capital_hilton")
    assert infer_lane_from_question("has the hilton invoice been paid") == ("finance", "capital_hilton")


def test_infer_lane_st_annes_payment():
    assert infer_lane_from_question("did st annes send the payment?") == ("finance", "st_annes")


def test_infer_lane_requires_money_terms():
    assert infer_lane_from_question("what is capital hilton") == ("", "")
    assert infer_lane_from_question("tell me about the weather") == ("", "")


def test_cold_capital_hilton_payment_question_gets_watch_answer(tmp_path: Path):
    answer = answer_system_question(
        "Did Capital Hilton pay me?",
        read_model_root=tmp_path,
        sqlite_root=tmp_path,
    )
    assert answer["answer"]["headline"] != "No local answer found"
    summary = answer["answer"]["plain_summary"].lower()
    assert "payment" in summary or "coupa" in summary
    assert answer["contextual_route"]["current_thread_ref"] == "capital_hilton"
    assert answer["contextual_route"].get("lane_inferred_from_content") is True


def test_explicit_refs_still_take_precedence(tmp_path: Path):
    answer = answer_system_question(
        "what should i do here",
        current_world_ref="finance",
        current_thread_ref="capital_hilton",
        read_model_root=tmp_path,
        sqlite_root=tmp_path,
    )
    assert answer["answer"]["headline"] == "Stay on payment watch"
    assert answer["contextual_route"].get("lane_inferred_from_content") is not True


def test_non_finance_cold_question_still_unknown(tmp_path: Path):
    answer = answer_system_question(
        "what is the airspeed of an unladen swallow",
        read_model_root=tmp_path,
        sqlite_root=tmp_path,
    )
    assert answer["answer"]["headline"] == "No local answer found"
