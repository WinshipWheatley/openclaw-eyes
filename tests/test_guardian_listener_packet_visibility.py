from __future__ import annotations

import asyncio
import importlib
import sys
import types
from types import SimpleNamespace


def _install_telegram_stubs(monkeypatch) -> None:
    class _Application:
        def __init__(self) -> None:
            self.handlers = []

        def add_handler(self, handler) -> None:
            self.handlers.append(handler)

        def run_polling(self) -> None:
            return None

    class _ApplicationBuilder:
        def token(self, token):
            self.token_value = token
            return self

        def build(self):
            return _Application()

    class _Handler:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

    class _Filter:
        def __and__(self, other):
            return self

        def __invert__(self):
            return self

    telegram = types.ModuleType("telegram")
    telegram.Update = object
    telegram.InlineKeyboardMarkup = lambda *args, **kwargs: ("keyboard", args, kwargs)

    error = types.ModuleType("telegram.error")
    error.BadRequest = type("BadRequest", (Exception,), {})
    error.Forbidden = type("Forbidden", (Exception,), {})

    ext = types.ModuleType("telegram.ext")
    ext.ApplicationBuilder = _ApplicationBuilder
    ext.CallbackQueryHandler = _Handler
    ext.MessageHandler = _Handler
    ext.filters = SimpleNamespace(TEXT=_Filter(), COMMAND=_Filter())
    ext.ContextTypes = SimpleNamespace(DEFAULT_TYPE=object)

    monkeypatch.setitem(sys.modules, "telegram", telegram)
    monkeypatch.setitem(sys.modules, "telegram.error", error)
    monkeypatch.setitem(sys.modules, "telegram.ext", ext)


def _load_listener(monkeypatch):
    monkeypatch.setenv("GUARDIAN_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    _install_telegram_stubs(monkeypatch)
    sys.modules.pop("chief_guardian_listener", None)
    return importlib.import_module("chief_guardian_listener")


class _ReplyMessage:
    def __init__(self, text: str, sent: list[str]) -> None:
        self.text = text
        self.chat_id = 456
        self._sent = sent

    async def reply_text(self, text: str) -> None:
        self._sent.append(text)


def test_guardian_no_pending_reply_builds_packet_but_does_not_show_raw_packet(monkeypatch) -> None:
    listener = _load_listener(monkeypatch)
    monkeypatch.setattr(listener, "claim_listener_update", lambda *args, **kwargs: True)
    monkeypatch.setattr(listener, "record_telegram_listener_update_safe", lambda **kwargs: None)

    import chief_approval_brain
    import hitl_notification_service
    import packet_engine

    monkeypatch.setattr(hitl_notification_service, "handle_typed_reply", lambda *args, **kwargs: {"handled": False})
    monkeypatch.setattr(chief_approval_brain, "has_pending_approval", lambda: False)
    monkeypatch.setattr(chief_approval_brain, "_load_pending", lambda: {})
    monkeypatch.setattr(chief_approval_brain, "parse_reply_code", lambda *args, **kwargs: ("", ""))

    packet_calls: list[dict[str, object]] = []

    def fake_build_agent_packet(**kwargs):
        packet_calls.append(kwargs)
        return {
            "packet_id": "guardian_context_packet:test",
            "packet_engine_receipt": {"receipt_id": "packet_engine_receipt:test"},
            "packet_text": "GUARDIAN_CONTEXT_PACKET test\nTEMPORAL ANCHOR\nGrounded facts: yes",
        }

    monkeypatch.setattr(packet_engine, "build_agent_packet", fake_build_agent_packet)

    sent: list[str] = []
    update = SimpleNamespace(
        update_id=99,
        effective_user=SimpleNamespace(id=123),
        message=_ReplyMessage("what is pending my approval", sent),
    )

    asyncio.run(listener.handle_message(update, SimpleNamespace()))

    assert sent == ["No pending approval requests."]
    assert packet_calls
    assert packet_calls[0]["agent"] == "guardian"
    assert packet_calls[0]["question"] == "what is pending my approval"
    assert packet_calls[0]["question_class"] == "approval_posture_no_pending"
    assert "GUARDIAN_CONTEXT_PACKET" not in sent[0]
    assert "TEMPORAL ANCHOR" not in sent[0]


def test_first_touch_refusal_precedes_guardian_intake_and_approval_parser(tmp_path, monkeypatch) -> None:
    listener = _load_listener(monkeypatch)
    monkeypatch.setenv(
        "OPENCLAW_REFUSAL_RECEIPT_PATH",
        str(tmp_path / "refusal-receipts.jsonl"),
    )
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_args, **_kwargs: True)

    def _must_not_reach(*_args, **_kwargs):
        raise AssertionError("Guardian intake or approval parser ran before refusal")

    monkeypatch.setattr(listener, "record_telegram_listener_update_safe", _must_not_reach)
    sent: list[str] = []
    update = SimpleNamespace(
        update_id=162,
        effective_user=SimpleNamespace(id=123),
        message=_ReplyMessage(
            "clear out all the old logs and branches, do it now",
            sent,
        ),
    )

    asyncio.run(listener.handle_message(update, SimpleNamespace()))

    assert len(sent) == 1
    assert "Nothing was deleted" in sent[0]
    assert (tmp_path / "refusal-receipts.jsonl").is_file()
