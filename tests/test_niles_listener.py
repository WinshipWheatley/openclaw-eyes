from __future__ import annotations

import asyncio
import ast
from pathlib import Path

import niles_listener


FIXED_NOW = "2026-06-20T15:45:00+00:00"


class FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id


class FakeChat:
    def __init__(self, chat_id: int):
        self.id = chat_id


class FakeMessage:
    def __init__(self, text: str, message_id: int = 42):
        self.text = text
        self.message_id = message_id
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class FakeUpdate:
    def __init__(self, *, text: str, user_id: int, chat_id: int = 456, update_id: int = 789):
        self.message = FakeMessage(text, message_id=update_id)
        self.effective_user = FakeUser(user_id)
        self.effective_chat = FakeChat(chat_id)
        self.update_id = update_id


class FakeBot:
    def __init__(self):
        self.actions: list[tuple[int, str]] = []

    async def send_chat_action(self, *, chat_id: int, action: str) -> None:
        self.actions.append((chat_id, action))


class FakeContext:
    def __init__(self):
        self.bot = FakeBot()


def test_env_file_loads_niles_token_without_printing(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("NILES_BOT_TOKEN", raising=False)
    env_path = tmp_path / ".chief.env"
    env_path.write_text(
        "NILES_BOT_TOKEN='fake-niles-token'\nTELEGRAM_AUTHORIZED_USER_ID=123\n",
        encoding="utf-8",
    )

    assert niles_listener.env_value("NILES_BOT_TOKEN", env_path=env_path) == "fake-niles-token"

    captured = capsys.readouterr()
    assert "fake-niles-token" not in captured.out
    assert "fake-niles-token" not in captured.err


def test_bridge_request_has_niles_surface_and_all_false_authority_boundary():
    first = niles_listener.build_operator_niles_chat_request(
        "what gear do you control?",
        message_id="42",
        chat_id=456,
        created_at=FIXED_NOW,
    )
    second = niles_listener.build_operator_niles_chat_request(
        "what gear do you control?",
        message_id="43",
        chat_id=456,
        created_at=FIXED_NOW,
    )

    assert first["request_id"] != second["request_id"]
    assert first["active_surface_ref"] == "operator_niles_chat"
    assert first["source_channel"] == "niles_listener"
    assert first["origin_surface"] == "telegram_pc_niles_listener"
    assert first["thread_title"] == "Niles"
    assert first["world_ref"] == "music"
    assert first["source_text"] == "what gear do you control?"
    assert first["payload_hash"]
    assert all(value is False for value in first["authority_boundary"].values())
    assert first["authority_boundary"]["live_hardware_control_allowed"] is False
    assert first["authority_boundary"]["osc_message_allowed"] is False
    assert first["authority_boundary"]["external_action_allowed"] is False


def test_authorized_gear_question_writes_bus_request_and_replies_deterministically(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    written: list[dict] = []
    records: list[dict] = []

    def fake_write(request: dict, *, inbox: Path = niles_listener.DEFAULT_REQUEST_INBOX) -> Path:
        written.append(request)
        return tmp_path / f"{request['request_id']}.json"

    monkeypatch.setattr(niles_listener, "write_bridge_request", fake_write)
    monkeypatch.setattr(niles_listener, "record_niles_intake_metadata", lambda **kwargs: records.append(kwargs))

    update = FakeUpdate(text="what gear do you control?", user_id=123, chat_id=456, update_id=42)
    context = FakeContext()
    asyncio.run(niles_listener.handle_message(update, context))

    assert written
    assert written[0]["request_id"].startswith("niles_telegram_42_")
    assert "x32 rack" in update.message.replies[0].lower()
    assert "explicit operator confirmation" in update.message.replies[0].lower()
    assert context.bot.actions == [(456, "typing")]
    assert records[0]["operator_message"] is True


def test_hardware_action_prompt_records_but_does_not_fire_control(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    written: list[dict] = []
    monkeypatch.setattr(niles_listener, "record_niles_intake_metadata", lambda **kwargs: None)
    monkeypatch.setattr(
        niles_listener,
        "write_bridge_request",
        lambda request, **kwargs: written.append(request) or tmp_path / "request.json",
    )

    update = FakeUpdate(text="set X32 channel 1 fader to -5", user_id=123)
    asyncio.run(niles_listener.handle_message(update, FakeContext()))

    assert written
    assert len(update.message.replies) == 1
    reply = update.message.replies[0].lower()
    assert "no rig or external action ran" in reply
    assert "operator confirmation" in reply
    assert written[0]["authority_boundary"]["live_hardware_control_allowed"] is False
    assert written[0]["authority_boundary"]["osc_message_allowed"] is False


def test_unauthorized_user_records_metadata_but_does_not_reply_or_write_bridge(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    records: list[dict] = []
    writes: list[dict] = []
    monkeypatch.setattr(niles_listener, "record_niles_intake_metadata", lambda **kwargs: records.append(kwargs))
    monkeypatch.setattr(niles_listener, "write_bridge_request", lambda request, **kwargs: writes.append(request))

    update = FakeUpdate(text="hello niles", user_id=999)
    asyncio.run(niles_listener.handle_message(update, FakeContext()))

    assert update.message.replies == []
    assert writes == []
    assert records
    assert records[0]["operator_message"] is False
    assert records[0]["source_user_label"] == "unverified_sender"


def test_listener_has_no_outbound_or_hardware_control_imports():
    source = Path(niles_listener.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )

    forbidden_imports = {
        "cassandra_sender",
        "google_access_broker",
        "gmail_access_broker",
        "pythonosc",
        "mido",
        "rtmidi",
        "pyautogui",
        "subprocess",
    }
    assert imported_modules.isdisjoint(forbidden_imports)
    assert all(value is False for value in niles_listener.AUTHORITY_BOUNDARY.values())


def test_niles_systemd_unit_is_restart_always_and_token_loaded_from_chief_env():
    unit = Path("systemd/user/niles-listener.service.in").read_text(encoding="utf-8")

    assert "Description=OpenClaw Niles Listener" in unit
    assert "Restart=always" in unit
    assert "source @REPO_ROOT@/.chief.env" in unit
    assert "niles_listener.py" in unit
    assert "NILES_BOT_TOKEN=" not in unit
    assert "systemctl" not in unit

