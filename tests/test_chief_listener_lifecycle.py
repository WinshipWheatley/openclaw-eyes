from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asyncio
import importlib
import types


def import_chief_listener(monkeypatch):
    monkeypatch.setenv("CHIEF_BOT_TOKEN", "test-token")
    monkeypatch.setenv("CHIEF_EXPECTED_BOT_USERNAME", "chief_test_bot")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "12345")
    telegram = types.ModuleType("telegram")
    telegram.Update = type("Update", (), {})
    telegram_ext = types.ModuleType("telegram.ext")
    telegram_ext.ApplicationBuilder = type("ApplicationBuilder", (), {})
    telegram_ext.MessageHandler = type("MessageHandler", (), {})
    telegram_ext.CallbackQueryHandler = type("CallbackQueryHandler", (), {})
    telegram_ext.filters = types.SimpleNamespace(TEXT=object(), COMMAND=object())
    telegram_ext.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object())
    monkeypatch.setitem(sys.modules, "telegram", telegram)
    monkeypatch.setitem(sys.modules, "telegram.ext", telegram_ext)

    chief_router = types.ModuleType("chief_router")
    chief_router.route_message = lambda text: {"intent": "noop", "reply": ""}
    chief_validator_brain = types.ModuleType("chief_validator_brain")
    chief_validator_brain.validate_reply = lambda reply: True
    chief_queue_brain = types.ModuleType("chief_queue_brain")
    chief_queue_brain.check_pending_queue = lambda: []
    chief_output_utils = types.ModuleType("chief_output_utils")
    chief_output_utils.tts_clean = lambda text: text
    monkeypatch.setitem(sys.modules, "chief_router", chief_router)
    monkeypatch.setitem(sys.modules, "chief_validator_brain", chief_validator_brain)
    monkeypatch.setitem(sys.modules, "chief_queue_brain", chief_queue_brain)
    monkeypatch.setitem(sys.modules, "chief_output_utils", chief_output_utils)

    sys.modules.pop("chief_listener", None)
    return importlib.import_module("chief_listener")


def test_import_does_not_start_polling(monkeypatch):
    chief_listener = import_chief_listener(monkeypatch)

    assert hasattr(chief_listener, "build_application")
    assert hasattr(chief_listener, "run_listener")
    assert "app" not in vars(chief_listener)


def test_send_reply_records_v2_delivery_after_confirmed_message(monkeypatch):
    chief_listener = import_chief_listener(monkeypatch)
    calls: list[dict] = []
    monkeypatch.setattr(chief_listener, "_fire_agent_voice", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        chief_listener,
        "register_operator_text_delivery_v2",
        lambda **kwargs: calls.append(kwargs),
    )

    class Message:
        text = "status?"
        chat_id = 456
        message_id = 162

        async def reply_text(self, text):
            return types.SimpleNamespace(message_id=9005)

    update = types.SimpleNamespace(
        effective_chat=types.SimpleNamespace(id=456),
        message=Message(),
    )

    asyncio.run(chief_listener._send_reply(update, "Chief answer."))

    assert len(calls) == 1
    assert calls[0]["response_author"] == "chief"
    assert calls[0]["carrier_identity"] == "chief"


def test_run_listener_awaits_lifecycle_once_in_order(monkeypatch):
    chief_listener = import_chief_listener(monkeypatch)
    calls = []

    class FakeUpdater:
        def __init__(self):
            self.running = False

        async def start_polling(self):
            calls.append("start_polling")
            self.running = True

        async def stop(self):
            calls.append("updater.stop")
            self.running = False

    class FakeApplication:
        def __init__(self, stop_event):
            self.updater = FakeUpdater()
            self.post_init = self._post_init
            self.running = False
            self._stop_event = stop_event
            self.bot = self

        async def get_me(self):
            calls.append("get_me")
            return types.SimpleNamespace(username="chief_test_bot", id=1234)

        async def initialize(self):
            calls.append("initialize")

        async def _post_init(self, application):
            assert application is self
            calls.append("post_init")

        async def start(self):
            calls.append("start")
            self.running = True
            self._stop_event.set()

        async def stop(self):
            calls.append("stop")
            self.running = False

        async def shutdown(self):
            calls.append("shutdown")

    async def scenario():
        stop_event = asyncio.Event()
        await chief_listener.run_listener(FakeApplication(stop_event), stop_event)

    asyncio.run(scenario())

    assert calls == [
        "initialize",
        "get_me",
        "post_init",
        "start_polling",
        "start",
        "updater.stop",
        "stop",
        "shutdown",
    ]
    assert calls.count("updater.stop") == 1


def test_first_touch_refusal_precedes_governed_intake_and_router(tmp_path, monkeypatch):
    chief_listener = import_chief_listener(monkeypatch)
    monkeypatch.setenv("OPENCLAW_AGENT_VOICE_NOTES", "0")
    monkeypatch.setenv(
        "OPENCLAW_REFUSAL_RECEIPT_PATH",
        str(tmp_path / "refusal-receipts.jsonl"),
    )
    monkeypatch.setattr(chief_listener, "claim_listener_update", lambda *_args, **_kwargs: True)

    def _must_not_reach(*_args, **_kwargs):
        raise AssertionError("governed intake or Chief router ran before refusal")

    monkeypatch.setattr(chief_listener, "record_telegram_listener_update_safe", _must_not_reach)
    monkeypatch.setattr(chief_listener, "route_message", _must_not_reach)
    monkeypatch.setattr(chief_listener, "_fire_agent_voice", _must_not_reach)
    sent: list[str] = []

    class Message:
        text = "clear out all the old logs and branches, do it now"
        chat_id = 456

        async def reply_text(self, text):
            sent.append(text)

    update = types.SimpleNamespace(
        effective_user=types.SimpleNamespace(id=12345),
        effective_chat=types.SimpleNamespace(id=456),
        message=Message(),
        update_id=162,
    )
    asyncio.run(chief_listener.handle_message(update, types.SimpleNamespace(bot=None)))

    assert len(sent) == 1
    assert "Nothing was deleted" in sent[0]
    assert (tmp_path / "refusal-receipts.jsonl").is_file()
