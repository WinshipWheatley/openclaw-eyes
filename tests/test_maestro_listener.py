from pathlib import Path
import asyncio
import importlib
import sys
import types


def import_maestro_listener(monkeypatch, *, token_env="MAESTRO_BOT_TOKEN"):
    monkeypatch.delenv("MAESTRO_BOT_TOKEN", raising=False)
    monkeypatch.delenv("MAESTRO_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv(token_env, "test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "12345")
    telegram = types.ModuleType("telegram")
    telegram.Update = type("Update", (), {})
    telegram_ext = types.ModuleType("telegram.ext")
    telegram_ext.ApplicationBuilder = type("ApplicationBuilder", (), {})
    telegram_ext.MessageHandler = type("MessageHandler", (), {})
    telegram_ext.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object())
    telegram_ext.filters = types.SimpleNamespace(TEXT=object(), COMMAND=object())
    monkeypatch.setitem(sys.modules, "telegram", telegram)
    monkeypatch.setitem(sys.modules, "telegram.ext", telegram_ext)

    sys.modules.pop("maestro_listener", None)
    return importlib.import_module("maestro_listener")


class _FakeUser:
    id = 12345


class _FakeChat:
    id = 67890


class _FakeMessage:
    def __init__(self, text):
        self.text = text
        self.replies = []

    async def reply_text(self, text):
        self.replies.append(text)


class _FakeUpdate:
    update_id = 111

    def __init__(self, text, *, authorized=True):
        self.message = _FakeMessage(text)
        self.effective_user = _FakeUser() if authorized else types.SimpleNamespace(id=999)
        self.effective_chat = _FakeChat()


class _FakeBot:
    def __init__(self):
        self.actions = []

    async def send_chat_action(self, *, chat_id, action):
        self.actions.append((chat_id, action))


def test_frontdoor_result_formatter_prefers_plain_summary(monkeypatch):
    maestro_listener = import_maestro_listener(monkeypatch)

    result = {
        "status": "ANSWER_READY",
        "layered_response_fields": {
            "one_line_answer": "Short line",
            "plain_summary": "Full Maestro answer.",
        },
    }

    assert maestro_listener._format_frontdoor_reply(result) == "Full Maestro answer."


def test_accepts_maestro_telegram_token_alias(monkeypatch):
    maestro_listener = import_maestro_listener(monkeypatch, token_env="MAESTRO_TELEGRAM_BOT_TOKEN")

    assert maestro_listener.BOT_TOKEN == "test-token"


def test_authorized_message_records_intake_shows_typing_and_replies(monkeypatch):
    maestro_listener = import_maestro_listener(monkeypatch)
    recorded = []

    def fake_record(**kwargs):
        recorded.append(kwargs)
        return "tgupdate_maestro"

    async def fake_run(text, session_meta):
        await asyncio.sleep(0.01)
        assert text == "Maestro, what's going on?"
        assert session_meta["agent_target"] == "maestro"
        return "Maestro is online in the harness."

    monkeypatch.setattr(maestro_listener, "record_maestro_listener_text_update", fake_record)
    monkeypatch.setattr(maestro_listener, "_run_frontdoor_answer", fake_run)

    update = _FakeUpdate("Maestro, what's going on?")
    context = types.SimpleNamespace(bot=_FakeBot())

    asyncio.run(maestro_listener.handle_message(update, context))

    assert context.bot.actions == [(67890, "typing")]
    assert update.message.replies == ["Maestro is online in the harness."]
    assert recorded[0]["source_message_id"] == "111"
    assert recorded[0]["operator_message"] is True
    assert recorded[0]["route_intent"] is False


def test_unauthorized_message_records_metadata_without_reply(monkeypatch):
    maestro_listener = import_maestro_listener(monkeypatch)
    recorded = []

    def fake_record(**kwargs):
        recorded.append(kwargs)
        return "tgupdate_maestro"

    monkeypatch.setattr(maestro_listener, "record_maestro_listener_text_update", fake_record)

    update = _FakeUpdate("hello maestro", authorized=False)
    context = types.SimpleNamespace(bot=_FakeBot())

    asyncio.run(maestro_listener.handle_message(update, context))

    assert context.bot.actions == []
    assert update.message.replies == []
    assert recorded[0]["source_user_label"] == "unverified_sender"
    assert recorded[0]["operator_message"] is False
    assert recorded[0]["route_intent"] is False


def test_missing_frontdoor_responder_fails_closed(monkeypatch, capsys):
    maestro_listener = import_maestro_listener(monkeypatch)
    sys.modules.pop("maestro_cassandra_responder", None)

    reply = maestro_listener._answer_frontdoor_sync("Maestro, go", {})
    output = capsys.readouterr().out

    assert "not importable" in reply
    assert "ImportError" not in output
    assert "ModuleNotFoundError" in output


def test_static_no_send_or_action_imports():
    source = Path("maestro_listener.py").read_text(encoding="utf-8")
    lowered = source.lower()

    forbidden = (
        "cassandra_sender",
        "cassandra_outreach",
        "google_access_broker",
        "email_send",
        "browser",
        "coupa",
        "ledger",
        "workbook",
        "subprocess",
        "os.system",
        "send_message(",
    )
    for token in forbidden:
        assert token not in lowered


def test_build_application_does_not_start_polling(monkeypatch):
    maestro_listener = import_maestro_listener(monkeypatch)

    assert hasattr(maestro_listener, "build_application")
    assert hasattr(maestro_listener, "run_listener")
    assert "app" not in vars(maestro_listener)
