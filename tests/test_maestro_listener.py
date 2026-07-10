import asyncio
import ast
import json
from datetime import date
from pathlib import Path

import pytest

import maestro_listener


FIXED_NOW = "2026-06-19T15:18:00+00:00"


@pytest.fixture(autouse=True)
def _claimed_update(monkeypatch):
    monkeypatch.setattr(maestro_listener, "claim_listener_update", lambda *args, **kwargs: True)


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
    assert first["speaker"] == "Winship"
    assert first["lane"] == "telegram_pc_maestro_listener"
    assert first["relay_origin"] is None
    assert first["actor"] == "operator_winship"
    assert first["message_provenance"] == {
        "speaker": "Winship",
        "lane": "telegram_pc_maestro_listener",
        "relay_origin": None,
        "actor": "operator_winship",
        "surface_ref": "operator_maestro_chat",
        "message_role": "operator_prompt",
    }
    assert first["expected_response_provenance"]["speaker"] == "Maestro"
    assert first["expected_response_provenance"]["actor"] == "maestro"
    assert first["expected_response_provenance"]["processing_receipt_user_visible"] is False
    assert first["correlation"]["request_id"] == first["request_id"]
    assert first["correlation"]["telegram_message_id"] == "42"
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
    assert response.detail_disclosure["message_provenance"]["speaker"] == "Maestro"
    assert response.detail_disclosure["message_provenance"]["actor"] == "maestro"
    assert response.detail_disclosure["message_provenance"]["relay_origin"] is None
    assert response.detail_disclosure["request_message_provenance"]["speaker"] == "Winship"
    assert response.detail_disclosure["correlation"]["source_request_id"] == request["request_id"]
    assert response.detail_disclosure["maestro_frontdoor_routing"]["workflow_package_staged"] is False
    assert response.detail_disclosure["workflow_package_staged"] is False
    assert response.detail_disclosure["email_send_performed"] is False


def test_listener_bridge_request_delivers_capability_readback_not_generic_intro(tmp_path, monkeypatch):
    import maestro_cassandra_responder as maestro
    import openclaw_request_processor as processor

    # Freshness is part of the production status contract.  Keep this bridge
    # test deterministic with an explicitly dated source set instead of
    # depending on whichever ignored read models happen to exist in the
    # developer checkout.
    source_root = tmp_path / "status_sources"
    source_root.mkdir()
    generated_at = f"{date.today().isoformat()}T12:00:00+00:00"
    (source_root / "openclaw_capability_index.json").write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "generic_capabilities": [
                    {
                        "capability_id": "request_processing",
                        "capability_name": "Bounded request processor",
                        "capability_status": "LIVE_IMPLEMENTED",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (source_root / "agent_presence.json").write_text(
        json.dumps({"generated_at": generated_at, "agents": []}),
        encoding="utf-8",
    )
    (source_root / "chief_status_rail.json").write_text(
        json.dumps({"generated_at": generated_at, "chief_current_status": "read_model_only"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(maestro, "DEFAULT_READ_MODEL_ROOT", source_root)

    request = maestro_listener.build_operator_maestro_chat_request(
        "what can you help me with?",
        message_id="capability-smoke",
        chat_id=456,
        created_at=FIXED_NOW,
    )
    request_path = tmp_path / "mission_control_operator_instruction_request_maestro_listener_capability_smoke.json"
    request_path.write_text(maestro_listener.stable_json(request), encoding="utf-8")

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )
    payload, _ = processor.build_payloads(response, generated_at=FIXED_NOW)
    reply = maestro_listener.reply_text_from_bridge_response(payload)

    assert response.internal_status == "RESPONSE_READY"
    assert response.request_type == "CHAT"
    assert "Here is the truthful readback from current generated state." in response.operator_message
    assert "Proven live-implemented rails:" in response.operator_message
    assert "Proven live-implemented rails:" in reply
    assert "Recorded, no action ran" not in reply
    assert reply != "Here is the truthful readback from current generated state."
    assert "Maestro-native reply - ref capability-smoke:" in reply


def test_listener_capital_hilton_status_probe_reaches_brain_not_system_question(monkeypatch, tmp_path):
    import maestro_context_packet
    import openclaw_request_processor as processor
    import protected_generate

    packet_calls: list[dict] = []
    protected_calls: list[str] = []

    def fake_packet(*, question, session=None, source_surface="operator_maestro_chat", require_real_truth=True, **_kwargs):
        packet_calls.append(
            {
                "question": question,
                "source_surface": source_surface,
                "require_real_truth": require_real_truth,
            }
        )
        return {
            "packet_id": "maestro_context_packet:test:capital_hilton_status",
            "source_refs": ["generated/read_models/capital_hilton_invoice_operator_run_status.json"],
            "facts": [
                {
                    "label": "Capital Hilton status",
                    "value": "$2000 received through Coupa; July 1 check expected.",
                    "source_ref": "generated/read_models/capital_hilton_invoice_operator_run_status.json",
                }
            ],
            "privacy": {"tiers_present": ["LIGHT"]},
            "packet_text": "Capital Hilton status: $2000 received through Coupa; July 1 check expected.",
        }

    def fake_protected(question, *, context_packet, **_kwargs):
        protected_calls.append(question)
        return {
            "text": "Capital Hilton packet answer: $2000 received through Coupa; July 1 check expected. SEND_HOLD remains active.",
            "receipt": {
                "receipt_id": "receipt:test:capital_hilton_status",
                "decision": "INJECTED_PROTECTED_GENERATE",
                "model_call_performed": False,
                "external_llm_invoked": False,
                "local_model_invoked": False,
            },
        }

    monkeypatch.setattr(maestro_context_packet, "build_maestro_context_packet", fake_packet)
    monkeypatch.setattr(protected_generate, "protected_generate_with_receipt", fake_protected)

    request = maestro_listener.build_operator_maestro_chat_request(
        "what's Winship's day / Capital Hilton status?",
        message_id="238",
        chat_id=456,
        created_at=FIXED_NOW,
    )
    request_path = tmp_path / "mission_control_operator_instruction_request_maestro_telegram_238.json"
    request_path.write_text(maestro_listener.stable_json(request), encoding="utf-8")

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )
    detail = response.detail_disclosure

    assert response.internal_status == "RESPONSE_READY"
    assert response.request_type == "CHAT"
    assert "Capital Hilton packet answer" in response.operator_message
    assert "I do not have a deterministic local answer" not in response.operator_message
    assert detail["workflow_package_staged"] is False
    assert detail["maestro_frontdoor_routing"]["workflow_package_staged"] is False
    assert detail["maestro_cassandra_responder"]["intent_class"] == "maestro_brain_freeform"
    assert detail["maestro_cassandra_responder"]["machine_proof"]["protected_generate_called"] is True
    assert detail["maestro_cassandra_responder"]["machine_proof"]["maestro_context_packet_used"] is True
    assert "system_question_answer" not in json.dumps(detail, sort_keys=True)
    assert packet_calls == [
        {
            "question": "what's Winship's day / Capital Hilton status?",
            "source_surface": "operator_maestro_chat",
            "require_real_truth": True,
        }
    ]
    assert protected_calls == ["what's Winship's day / Capital Hilton status?"]


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
    assert written[0]["protected_text_hash"].startswith("sha256:")
    assert written[0]["source_text_ref"] == "protected_text_hash:" + written[0]["protected_text_hash"]
    assert update.message.replies == [f"Today is {date.today().isoformat()}."]
    assert context.bot.actions == [(456, "typing")]
    assert records[0]["operator_message"] is True


def test_unauthorized_user_does_not_enter_governed_business_intake_or_reply(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    records: list[dict] = []
    writes: list[dict] = []
    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", lambda **kwargs: records.append(kwargs))
    monkeypatch.setattr(maestro_listener, "write_bridge_request", lambda request, **kwargs: writes.append(request))

    update = FakeUpdate(text="hello maestro", user_id=999)
    asyncio.run(maestro_listener.handle_message(update, FakeContext()))

    assert update.message.replies == []
    assert writes == []
    assert records == []


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
    assert "capability readback is live after reconcile" not in reply


def test_reply_prefers_full_final_operator_message_over_generic_one_line():
    payload = {
        "source_request_id": "maestro_telegram_42_abcdef123456",
        "internal_status": "RESPONSE_READY",
        "request_type": "CHAT",
        "one_line_answer": "Here is the truthful readback from current generated state.",
        "operator_message": (
            "Here is the truthful readback from current generated state.\n\n"
            "- Agent roster: Cassandra and Chief are online.\n"
            "- Proven live-implemented rails: Bounded request processor.\n"
            "- I cannot claim send, browser, deploy, or workflow execution from this front door."
        ),
    }

    reply = maestro_listener.reply_text_from_bridge_response(payload)

    assert "- Agent roster: Cassandra and Chief are online." in reply
    assert "Proven live-implemented rails" in reply
    assert reply != "Here is the truthful readback from current generated state."
    assert "Maestro-native reply - ref 42:abcdef" in reply


def test_reply_suppresses_processing_heartbeat_as_final_answer():
    payload = {
        "source_request_id": "maestro_telegram_42_abcdef123456",
        "terminal": False,
        "processing_heartbeat_id": "processing_heartbeat_maestro_telegram_42_abcdef123456",
        "operator_message": "OpenClaw picked this up and is checking the local rails.",
    }

    reply = maestro_listener.reply_text_from_bridge_response(payload)

    assert "OpenClaw picked this up" not in reply
    assert "Recorded, no action ran" in reply
    assert "Maestro-native reply - ref 42:abcdef" in reply


def test_reply_sanitizes_stale_carryover_before_delivery():
    payload = {
        "source_request_id": "maestro_telegram_42_abcdef123456",
        "internal_status": "RESPONSE_READY",
        "request_type": "CHAT",
        "operator_message": (
            "The previous response was truncated. Continue? (61/61)\n"
            "Still working... waiting for stream response\n"
            "Fresh Maestro answer."
        ),
    }

    reply = maestro_listener.reply_text_from_bridge_response(payload)

    assert "Fresh Maestro answer." in reply
    assert "Still working" not in reply
    assert "previous response was truncated" not in reply.lower()
    assert "Maestro-native reply - ref 42:abcdef" in reply


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
