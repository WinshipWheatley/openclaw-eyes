from __future__ import annotations

import asyncio
import importlib
import re
import sys
import types
from types import SimpleNamespace

import hitl_notification_service as notify
from guardian_approval_ui import (
    APPROVE_BUTTON_TEXT,
    DENY_BUTTON_TEXT,
    human_reply_code,
)


def test_hitl_notification_keeps_signed_tokens_only_in_callback_data(monkeypatch) -> None:
    monkeypatch.setenv("HITL_NOTIFY_SECRET", "guardian-button-ux-test-secret")
    monkeypatch.setattr("chief_env.load_env", lambda: None)
    action = {
        "action_id": "5FF438AC",
        "source_agent": "cassandra",
        "action_type": "exact_gmail_send",
        "status": "WAITING_FOR_APPROVAL",
        "expires_at": "2099-01-01T00:00:00",
        "payload": {"recipient": "fixture@example.invalid"},
    }

    message = notify.format_notification(action)
    keyboard = notify._build_keyboard(action["action_id"])
    buttons = keyboard["inline_keyboard"][0]

    assert [button["text"] for button in buttons] == [APPROVE_BUTTON_TEXT, DENY_BUTTON_TEXT]
    assert "/hitl_approve" not in message
    assert "/hitl_deny" not in message
    assert "HITL:" not in message
    assert re.search(r"or reply: APPROVE \d{4}", message)
    assert re.search(r"or reply: DENY \d{4}", message)
    for button in buttons:
        raw_token = button["callback_data"].removeprefix("HITL:")
        validated = notify.validate_token(raw_token)
        assert validated["ok"] is True
        assert raw_token not in message


def test_typed_hitl_fallback_is_signed_before_decision(monkeypatch) -> None:
    action = {"action_id": "5FF438AC", "status": "WAITING_FOR_APPROVAL", "payload": {}}
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(notify._svc, "list_pending_actions", lambda status=None: [action])
    monkeypatch.setattr(
        notify,
        "generate_token",
        lambda action_id, decision: calls.append((action_id, decision)) or "signed-token",
    )
    monkeypatch.setattr(
        notify,
        "handle_callback",
        lambda token, approved_by="operator": {
            "ok": token == "signed-token",
            "action_id": action["action_id"],
            "decision": "Y",
            "error": None,
        },
    )

    result = notify.handle_typed_reply(
        f"APPROVE {human_reply_code(action['action_id'])}",
        approved_by="operator-fixture",
    )

    assert result["ok"] is True
    assert calls == [("5FF438AC", "Y")]
    assert result["reply"].startswith("✅ Approved by you at ")
    assert "5FF438AC" not in result["reply"]


def test_typed_hitl_fallback_fails_closed_on_short_code_collision(monkeypatch) -> None:
    actions = [
        {"action_id": "ACTION01", "status": "WAITING_FOR_APPROVAL", "payload": {}},
        {"action_id": "ACTION02", "status": "WAITING_FOR_APPROVAL", "payload": {}},
    ]
    monkeypatch.setattr(notify._svc, "list_pending_actions", lambda status=None: actions)
    monkeypatch.setattr(notify, "_parse_typed_decision", lambda text, action: ("Y", None))
    monkeypatch.setattr(
        notify,
        "generate_token",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("ambiguous code was signed")),
    )

    result = notify.handle_typed_reply("APPROVE 0000")

    assert result["ok"] is False
    assert result["error"] == "ambiguous_reply_code_collision"
    assert "nothing was approved or denied" in result["reply"]


def _load_listener(monkeypatch):
    class Builder:
        def token(self, _token):
            return self

        def build(self):
            return SimpleNamespace(add_handler=lambda *_args, **_kwargs: None)

    class Filter:
        def __and__(self, _other):
            return self

        def __invert__(self):
            return self

    telegram = types.ModuleType("telegram")
    telegram.Update = object
    telegram.InlineKeyboardMarkup = lambda rows: {"inline_keyboard": rows}
    errors = types.ModuleType("telegram.error")
    errors.BadRequest = type("BadRequest", (Exception,), {})
    errors.Forbidden = type("Forbidden", (Exception,), {})
    ext = types.ModuleType("telegram.ext")
    ext.ApplicationBuilder = Builder
    ext.CallbackQueryHandler = lambda *_args, **_kwargs: None
    ext.MessageHandler = lambda *_args, **_kwargs: None
    ext.filters = SimpleNamespace(TEXT=Filter(), COMMAND=Filter())
    ext.ContextTypes = SimpleNamespace(DEFAULT_TYPE=object)
    monkeypatch.setitem(sys.modules, "telegram", telegram)
    monkeypatch.setitem(sys.modules, "telegram.error", errors)
    monkeypatch.setitem(sys.modules, "telegram.ext", ext)
    monkeypatch.setenv("GUARDIAN_BOT_TOKEN", "guardian-button-test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    sys.modules.pop("chief_guardian_listener", None)
    return importlib.import_module("chief_guardian_listener")


def test_callback_acknowledges_then_replaces_original_without_token_text(monkeypatch) -> None:
    listener = _load_listener(monkeypatch)
    import chief_approval_brain
    import guardian_approval_board

    timeline: list[tuple[str, object]] = []

    class Query:
        data = "YES:ABCD1234"
        message = SimpleNamespace(text="Press RAW.SIGNED.TOKEN for yes")

        async def answer(self):
            timeline.append(("answer", None))

        async def edit_message_text(self, text, reply_markup=None):
            timeline.append(("edit", (text, reply_markup)))

    pending_checks = iter((True, False))
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_a, **_k: True)
    monkeypatch.setattr(listener, "guardian_resilient_reply", lambda text, **_k: str(text))
    monkeypatch.setattr(chief_approval_brain, "has_pending_approval", lambda: next(pending_checks))
    monkeypatch.setattr(chief_approval_brain, "record_decision", lambda *_a, **_k: "Approved.")
    monkeypatch.setattr(guardian_approval_board, "mark_resolved", lambda *_a, **_k: True)
    bot = SimpleNamespace(send_message=lambda **_kwargs: None)
    update = SimpleNamespace(
        callback_query=Query(),
        effective_user=SimpleNamespace(id=123),
        effective_chat=SimpleNamespace(id=456),
    )

    asyncio.run(listener.handle_callback_query(update, SimpleNamespace(bot=bot)))

    assert timeline[0][0] == "answer"
    assert timeline[1][0] == "edit"
    edited_text, markup = timeline[1][1]
    assert edited_text.startswith("✅ Approved by you at ")
    assert "RAW.SIGNED.TOKEN" not in edited_text
    assert markup == {"inline_keyboard": []}
