import pytest


def _route_without_side_effects(monkeypatch, text: str) -> dict:
    from chief_router import route_message

    monkeypatch.setitem(route_message.__globals__, "_log_route", lambda *args, **kwargs: None)
    monkeypatch.setitem(route_message.__globals__, "has_pending_approval", lambda: False)
    return route_message(text)


def test_chief_approval_status_query_stays_fast(monkeypatch):
    result = _route_without_side_effects(monkeypatch, "what are my open approvals?")

    assert result["intent"] == "approval_status"
    assert "No pending approval requests" in result["reply"]
    assert result["send_performed"] is False


def test_chief_capability_prompt_is_not_approval_status(monkeypatch):
    result = _route_without_side_effects(monkeypatch, "what can you help me with?")

    assert result["intent"] == "capability"
    assert "No pending approval requests" not in result["reply"]
    assert "HITL approvals" in result["reply"]
    assert "SEND_HOLD" in result["reply"]


def test_chief_send_prompt_stage_denies_without_send(monkeypatch):
    from chief_router import route_message

    monkeypatch.setitem(route_message.__globals__, "_log_route", lambda *args, **kwargs: None)
    monkeypatch.setitem(route_message.__globals__, "has_pending_approval", lambda: False)
    monkeypatch.setitem(
        route_message.__globals__,
        "email_handle",
        lambda *_args, **_kwargs: pytest.fail("send prompt reached email handler"),
    )

    result = route_message("draft and send an email to my client now")

    assert result["intent"] == "send_hold_stage_deny"
    assert result["send_performed"] is False
    assert "Nothing was sent" in result["reply"]
    assert "SEND_HOLD" in result["reply"]
    assert "No pending approval requests" not in result["reply"]


def test_chief_next_best_move_handoffs_without_dispatch(monkeypatch):
    result = _route_without_side_effects(monkeypatch, "what's the next best move?")

    assert result["intent"] == "next_move"
    assert "Cassandra" in result["reply"]
    assert "will not dispatch or send" in result["reply"]
    assert "No pending approval requests" not in result["reply"]


def test_chief_nonsense_asks_for_clarification(monkeypatch):
    result = _route_without_side_effects(monkeypatch, "florble 713 ???")

    assert result["intent"] == "clarification"
    assert "not have enough signal" in result["reply"]
    assert "No pending approval requests" not in result["reply"]


def test_money_prompt_blocks_without_ledger_or_action_paths(monkeypatch):
    from chief_router import route_message

    monkeypatch.setitem(route_message.__globals__, "_log_route", lambda *args, **kwargs: None)
    monkeypatch.setitem(route_message.__globals__, "has_pending_approval", lambda: False)
    for name in (
        "billing_handle",
        "financial_handle",
        "email_handle",
        "sms_handle",
        "_chief_fallback_reply",
        "_llm_classify_intent",
    ):
        monkeypatch.setitem(
            route_message.__globals__,
            name,
            lambda *_args, _name=name, **_kwargs: pytest.fail(f"money prompt reached {_name}"),
        )

    result = route_message("wire $500 to someone")

    assert result["intent"] == "money_block"
    assert result["ledger_touched"] is False
    assert result["send_performed"] is False
    assert "No money moved" in result["reply"]
    assert "SEND_HOLD" in result["reply"]


def test_guardian_send_and_money_prompts_are_plain_safety_blocks():
    from chief_nonapproval_responder import guardian_no_pending_reply

    send_reply = guardian_no_pending_reply("send an email to my client now")
    money_reply = guardian_no_pending_reply("wire $500 to someone")

    assert "Nothing was sent" in send_reply
    assert "SEND_HOLD" in send_reply
    assert "No pending approval requests" not in send_reply
    assert "No money moved" in money_reply
    assert "SEND_HOLD" in money_reply
    assert "contract" not in money_reply.lower()
    assert "ledger" not in money_reply.lower()


def test_guardian_capability_and_safety_questions_are_not_approval_status():
    from chief_nonapproval_responder import guardian_no_pending_reply

    capability = guardian_no_pending_reply("what do you protect against?")
    safety = guardian_no_pending_reply("is it safe to send this?")

    assert "protects the boundary" in capability
    assert "No pending approval requests" not in capability
    assert "actual message, recipient, and intended action" in safety
    assert "Nothing was sent" in safety

