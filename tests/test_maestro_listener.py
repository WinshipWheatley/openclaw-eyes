import asyncio
import ast
from datetime import date
from pathlib import Path

import pytest

import maestro_listener


FIXED_NOW = "2026-06-19T15:18:00+00:00"


class FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id


class FakeChat:
    def __init__(self, chat_id: int):
        self.id = chat_id


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class FakeUpdate:
    def __init__(self, *, text: str, user_id: int, chat_id: int = 456, update_id: int = 789):
        self.message = FakeMessage(text)
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


def test_env_file_loads_maestro_token_without_printing(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("MAESTRO_BOT_TOKEN", raising=False)
    env_path = tmp_path / ".chief.env"
    env_path.write_text("MAESTRO_BOT_TOKEN='fake-maestro-token'\nTELEGRAM_AUTHORIZED_USER_ID=123\n", encoding="utf-8")

    assert maestro_listener.env_value("MAESTRO_BOT_TOKEN", env_path=env_path) == "fake-maestro-token"

    captured = capsys.readouterr()
    assert "fake-maestro-token" not in captured.out
    assert "fake-maestro-token" not in captured.err


def test_bridge_request_has_unique_id_and_full_false_authority_boundary(tmp_path):
    first = maestro_listener.build_operator_maestro_chat_request(
        "what day is it",
        message_id="42",
        chat_id=456,
        created_at=FIXED_NOW,
    )
    second = maestro_listener.build_operator_maestro_chat_request(
        "what day is it",
        message_id="43",
        chat_id=456,
        created_at=FIXED_NOW,
    )

    assert first["request_id"] != second["request_id"]
    assert first["active_surface_ref"] == "operator_maestro_chat"
    assert first["kind"] == "OPERATOR_INSTRUCTION_PACKAGE_REQUEST"
    assert first["request_type"] == "WORKFLOW_PACKAGE_REQUEST_V0"
    assert first["source_surface"] == "mission_control"
    assert first["source_channel"] == "maestro_listener"
    assert first["source_text"] == "what day is it"
    assert first["operator_message"] == "what day is it"
    assert first["payload_hash"]
    assert first["authority_boundary"]
    assert all(value is False for value in first["authority_boundary"].values())
    assert "live_email_send_allowed" in first["authority_boundary"]
    assert "email_send_allowed" in first["authority_boundary"]
    assert "runtime_dispatch_allowed" in first["authority_boundary"]


def test_listener_bridge_request_routes_through_pc_processor_for_date_answer(tmp_path):
    import openclaw_request_processor as processor

    request = maestro_listener.build_operator_maestro_chat_request(
        "what day is it",
        message_id="processor-smoke",
        chat_id=456,
        created_at=FIXED_NOW,
    )
    request_path = tmp_path / "mission_control_operator_instruction_request_maestro_listener_processor_smoke.json"
    request_path.write_text(maestro_listener.stable_json(request), encoding="utf-8")

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )

    assert response.internal_status == "RESPONSE_READY"
    assert response.request_type == "CHAT"
    assert response.operator_message == f"Today is {date.today().isoformat()} ({date.today().strftime('%A')})."
    assert response.detail_disclosure["maestro_frontdoor_routing"]["workflow_package_staged"] is False
    assert response.detail_disclosure["workflow_package_staged"] is False
    assert response.detail_disclosure["email_send_performed"] is False


def test_authorized_date_question_replies_from_bridge_and_sends_typing(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    written: list[dict] = []

    def fake_write(request: dict, *, inbox: Path = maestro_listener.DEFAULT_REQUEST_INBOX) -> Path:
        written.append(request)
        return tmp_path / f"{request['request_id']}.json"

    async def fake_poll(*args, **kwargs):
        await asyncio.sleep(0)
        return {"one_line_answer": f"Today is {date.today().isoformat()}."}

    records: list[dict] = []
    monkeypatch.setattr(maestro_listener, "write_bridge_request", fake_write)
    monkeypatch.setattr(maestro_listener, "poll_bridge_response", fake_poll)
    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", lambda **kwargs: records.append(kwargs))

    update = FakeUpdate(text="what day is it", user_id=123, chat_id=456, update_id=42)
    context = FakeContext()
    asyncio.run(maestro_listener.handle_message(update, context))

    assert written
    assert written[0]["request_id"].startswith("maestro_telegram_42_")
    assert update.message.replies == [f"Today is {date.today().isoformat()}."]
    assert context.bot.actions == [(456, "typing")]
    assert records[0]["operator_message"] is True


def test_unauthorized_user_records_metadata_but_does_not_reply_or_write_bridge(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    records: list[dict] = []
    writes: list[dict] = []
    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", lambda **kwargs: records.append(kwargs))
    monkeypatch.setattr(maestro_listener, "write_bridge_request", lambda request, **kwargs: writes.append(request))

    update = FakeUpdate(text="hello maestro", user_id=999)
    asyncio.run(maestro_listener.handle_message(update, FakeContext()))

    assert update.message.replies == []
    assert writes == []
    assert records
    assert records[0]["operator_message"] is False
    assert records[0]["source_user_label"] == "unverified_sender"


def test_blocked_or_unknown_bridge_response_is_explicit_not_silent(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", lambda **kwargs: None)
    monkeypatch.setattr(maestro_listener, "write_bridge_request", lambda request, **kwargs: Path("/tmp/request.json"))

    async def fake_poll(*args, **kwargs):
        await asyncio.sleep(0)
        return {
            "internal_status": "RESPONSE_READY",
            "request_type": "WORKFLOW_PACKAGE_REQUEST",
            "operator_headline": "Workflow package staged",
            "operator_message": "OpenClaw staged a package instead of answering directly.",
        }

    monkeypatch.setattr(maestro_listener, "poll_bridge_response", fake_poll)

    update = FakeUpdate(text="send an email", user_id=123)
    asyncio.run(maestro_listener.handle_message(update, FakeContext()))

    assert len(update.message.replies) == 1
    reply = update.message.replies[0].lower()
    assert "recorded, no action ran" in reply
    assert "capability readback" in reply


def test_listener_has_no_outbound_send_imports_and_send_hold_boundary_false():
    source = Path(maestro_listener.__file__).read_text(encoding="utf-8")
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
        "gated_email_send_adapter",
        "gmail_access_broker",
        "google_access_broker",
        "coupa_supplier_portal_package_compiler",
    }
    assert imported_modules.isdisjoint(forbidden_imports)
    assert all(value is False for value in maestro_listener.AUTHORITY_BOUNDARY.values())
    assert maestro_listener.AUTHORITY_BOUNDARY["live_email_send_allowed"] is False
    assert maestro_listener.AUTHORITY_BOUNDARY["email_send_allowed"] is False
    assert maestro_listener.AUTHORITY_BOUNDARY["external_action_allowed"] is False
