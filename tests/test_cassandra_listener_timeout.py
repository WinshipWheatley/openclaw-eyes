from __future__ import annotations

import asyncio
import importlib
import sys
import types


def _load_listener(monkeypatch):
    monkeypatch.setenv("CASSANDRA_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    fake_filters = types.SimpleNamespace(TEXT=object(), COMMAND=object(), VOICE=object())
    fake_context_types = types.SimpleNamespace(DEFAULT_TYPE=object())

    class _FakeApplicationBuilder:
        def token(self, _token):
            return self

        def build(self):
            return types.SimpleNamespace(add_handler=lambda *a, **k: None, run_polling=lambda: None)

    sys.modules["telegram"] = types.SimpleNamespace(Update=object)
    sys.modules["telegram.ext"] = types.SimpleNamespace(
        ApplicationBuilder=_FakeApplicationBuilder,
        MessageHandler=lambda *a, **k: None,
        filters=fake_filters,
        ContextTypes=fake_context_types,
    )
    sys.modules.pop("cassandra_listener", None)
    import cassandra_listener

    module = importlib.reload(cassandra_listener)
    monkeypatch.setattr(module, "_pending_cassandra_approval_state", lambda: ("none", {}), raising=False)
    return module


def test_timeout_contract_success_sends_ack_then_result(monkeypatch):
    listener = _load_listener(monkeypatch)
    sent: list[str] = []
    escalations: list[tuple[str, dict]] = []
    monkeypatch.setattr(listener, "_WORKING_ACK_DELAY_S", 0.0, raising=False)

    async def _case():
        async def fake_send(text: str):
            sent.append(text)

        async def fake_run(text: str, session_meta: dict):
            assert session_meta["sender_name"] == "Winship"
            return ["All set."]

        async def fake_escalate(text: str, session_meta: dict):
            escalations.append((text, session_meta))

        result = await listener._run_request_with_timeout_contract(
            text="Can you email Winship and ask if thread test 6 is working?",
            session_meta={"sender_name": "Winship", "sender_chat_id": 123},
            send_reply=fake_send,
            is_authorized_user=True,
            run_cassandra=fake_run,
            escalate_failure=fake_escalate,
        )
        assert result == ["All set."]

    asyncio.run(_case())

    assert sent == [listener._WORKING_ON_IT, "All set."]
    assert escalations == []


def test_timeout_contract_escalates_after_timeout(monkeypatch):
    listener = _load_listener(monkeypatch)
    sent: list[str] = []
    escalations: list[tuple[str, dict]] = []
    monkeypatch.setattr(listener, "_REQUEST_TIMEOUT_S", 0.01, raising=False)
    monkeypatch.setattr(listener, "_WORKING_ACK_DELAY_S", 0.0, raising=False)

    async def _case():
        async def fake_send(text: str):
            sent.append(text)

        async def slow_run(text: str, session_meta: dict):
            await asyncio.sleep(1)
            return ["Late reply."]

        async def fake_escalate(text: str, session_meta: dict):
            escalations.append((text, session_meta))

        result = await listener._run_request_with_timeout_contract(
            text="Please send Winship a note about tomorrow",
            session_meta={"sender_name": "Winship", "sender_chat_id": 123},
            send_reply=fake_send,
            is_authorized_user=True,
            run_cassandra=slow_run,
            escalate_failure=fake_escalate,
        )
        assert result is None
        await asyncio.sleep(0.02)

    asyncio.run(_case())

    assert sent[:2] == [listener._WORKING_ON_IT, listener._ESCALATION_NOTICE]
    assert "Late reply." not in sent
    assert len(escalations) == 1
    assert escalations[0][0] == "Please send Winship a note about tomorrow"


def test_timeout_contract_runtime_exception_fail_closes_explicitly(monkeypatch):
    listener = _load_listener(monkeypatch)
    sent: list[str] = []
    escalations: list[tuple[str, dict]] = []
    monkeypatch.setattr(listener, "_WORKING_ACK_DELAY_S", 0.0, raising=False)

    async def _case():
        async def fake_send(text: str):
            sent.append(text)

        async def broken_run(text: str, session_meta: dict):
            await asyncio.sleep(0.01)
            raise RuntimeError("local model offline")

        async def fake_escalate(text: str, session_meta: dict):
            escalations.append((text, session_meta))

        result = await listener._run_request_with_timeout_contract(
            text="Can you summarize the Capital Hilton status?",
            session_meta={"sender_name": "Winship", "sender_chat_id": 123},
            send_reply=fake_send,
            is_authorized_user=True,
            run_cassandra=broken_run,
            escalate_failure=fake_escalate,
        )
        assert result is None
        await asyncio.sleep(0.02)

    asyncio.run(_case())

    assert sent == [listener._WORKING_ON_IT, listener._HANDLER_EXCEPTION_NOTICE]
    assert len(escalations) == 1
    assert escalations[0][1]["runtime_error"] == "local model offline"


def test_timeout_contract_replaces_generic_quiet_reply_with_degraded_notice(monkeypatch):
    listener = _load_listener(monkeypatch)
    sent: list[str] = []

    async def _case():
        async def fake_send(text: str):
            sent.append(text)

        async def generic_run(text: str, session_meta: dict):
            return ["I'm here — something went quiet on my end. Try again."]

        result = await listener._run_request_with_timeout_contract(
            text="Can you summarize the Capital Hilton status?",
            session_meta={"sender_name": "Winship", "sender_chat_id": 123},
            send_reply=fake_send,
            is_authorized_user=True,
            run_cassandra=generic_run,
        )
        assert result == ["I'm here — something went quiet on my end. Try again."]

    asyncio.run(_case())

    assert sent == [listener._DEGRADED_EMPTY_REPLY_NOTICE]


def test_timeout_contract_delivers_late_success_once(monkeypatch):
    listener = _load_listener(monkeypatch)
    sent: list[str] = []
    monkeypatch.setattr(listener, "_REQUEST_TIMEOUT_S", 0.01, raising=False)
    monkeypatch.setattr(listener, "_WORKING_ACK_DELAY_S", 0.0, raising=False)

    async def _case():
        async def fake_send(text: str):
            sent.append(text)

        async def slow_run(text: str, session_meta: dict):
            await asyncio.sleep(0.02)
            return ["Done. Added \"Doctor Appointment\" on Sunday April 19 at 2:30 PM."]

        async def fake_escalate(text: str, session_meta: dict):
            return None

        result = await listener._run_request_with_timeout_contract(
            text="Cassandra, put Doctor Appointment on my calendar tomorrow at 2:30 PM for 45 minutes.",
            session_meta={"sender_name": "Winship", "sender_chat_id": 123},
            send_reply=fake_send,
            is_authorized_user=True,
            run_cassandra=slow_run,
            escalate_failure=fake_escalate,
        )
        assert result is None
        await asyncio.sleep(0.05)

    asyncio.run(_case())

    assert sent == [
        listener._WORKING_ON_IT,
        listener._ESCALATION_NOTICE,
        'Done. Added "Doctor Appointment" on Sunday April 19 at 2:30 PM.',
    ]


def test_timeout_contract_reports_waiting_on_guardian_without_escalation(monkeypatch):
    listener = _load_listener(monkeypatch)
    sent: list[str] = []
    escalations: list[tuple[str, dict]] = []
    monkeypatch.setattr(listener, "_REQUEST_TIMEOUT_S", 0.01, raising=False)
    monkeypatch.setattr(listener, "_WORKING_ACK_DELAY_S", 0.0, raising=False)
    monkeypatch.setattr(listener, "_pending_cassandra_approval_state", lambda: ("waiting", {"action": "Google broker: cassandra → google.calendar.write"}), raising=False)

    async def _case():
        async def fake_send(text: str):
            sent.append(text)

        async def slow_run(text: str, session_meta: dict):
            await asyncio.sleep(0.02)
            return ['Done. Added "Doctor Appointment" on Sunday April 19 at 2:30 PM.']

        async def fake_escalate(text: str, session_meta: dict):
            escalations.append((text, session_meta))

        result = await listener._run_request_with_timeout_contract(
            text="Cassandra, put Doctor Appointment on my calendar tomorrow at 2:30 PM for 45 minutes.",
            session_meta={"sender_name": "Winship", "sender_chat_id": 123},
            send_reply=fake_send,
            is_authorized_user=True,
            run_cassandra=slow_run,
            escalate_failure=fake_escalate,
        )
        assert result is None
        await asyncio.sleep(0.05)

    asyncio.run(_case())

    assert sent == [
        listener._WORKING_ON_IT,
        listener._APPROVAL_WAIT_NOTICE,
        'Done. Added "Doctor Appointment" on Sunday April 19 at 2:30 PM.',
    ]
    assert escalations == []


def test_timeout_contract_escalates_stalled_guardian_approval(monkeypatch):
    listener = _load_listener(monkeypatch)
    sent: list[str] = []
    escalations: list[tuple[str, dict]] = []
    monkeypatch.setattr(listener, "_REQUEST_TIMEOUT_S", 0.01, raising=False)
    monkeypatch.setattr(listener, "_WORKING_ACK_DELAY_S", 0.0, raising=False)
    monkeypatch.setattr(listener, "_pending_cassandra_approval_state", lambda: ("stalled", {"action": "Google broker: cassandra → google.calendar.delete"}), raising=False)

    async def _case():
        async def fake_send(text: str):
            sent.append(text)

        async def slow_run(text: str, session_meta: dict):
            await asyncio.sleep(0.05)
            return ["Calendar delete was denied at the approval gate."]

        async def fake_escalate(text: str, session_meta: dict):
            escalations.append((text, session_meta))

        result = await listener._run_request_with_timeout_contract(
            text="Cassandra, remove the two Doctor Appointment events tomorrow at 2:30 PM from my calendar.",
            session_meta={"sender_name": "Winship", "sender_chat_id": 123},
            send_reply=fake_send,
            is_authorized_user=True,
            run_cassandra=slow_run,
            escalate_failure=fake_escalate,
        )
        assert result is None
        await asyncio.sleep(0.06)

    asyncio.run(_case())

    assert sent[:2] == [listener._WORKING_ON_IT, listener._APPROVAL_STALLED_NOTICE]
    assert len(escalations) == 1


def test_timeout_contract_skips_quick_ping(monkeypatch):
    listener = _load_listener(monkeypatch)
    sent: list[str] = []

    async def _case():
        async def fake_send(text: str):
            sent.append(text)

        async def fake_run(text: str, session_meta: dict):
            return ["I am online."]

        result = await listener._run_request_with_timeout_contract(
            text="Are you online?",
            session_meta={"sender_name": "Winship", "sender_chat_id": 123},
            send_reply=fake_send,
            is_authorized_user=True,
            run_cassandra=fake_run,
        )
        assert result == ["I am online."]

    asyncio.run(_case())

    assert sent == ["I am online."]


def test_timeout_contract_skips_working_ack_for_fast_result(monkeypatch):
    listener = _load_listener(monkeypatch)
    sent: list[str] = []
    monkeypatch.setattr(listener, "_WORKING_ACK_DELAY_S", 0.05, raising=False)

    async def _case():
        async def fake_send(text: str):
            sent.append(text)

        async def fast_run(text: str, session_meta: dict):
            await asyncio.sleep(0.005)
            return ["Done quickly."]

        result = await listener._run_request_with_timeout_contract(
            text="Can you summarize tomorrow's calendar?",
            session_meta={"sender_name": "Winship", "sender_chat_id": 123},
            send_reply=fake_send,
            is_authorized_user=True,
            run_cassandra=fast_run,
        )
        assert result == ["Done quickly."]
        await asyncio.sleep(0.06)

    asyncio.run(_case())

    assert sent == ["Done quickly."]


def test_timeout_contract_suppresses_stale_request_after_newer_one(monkeypatch):
    listener = _load_listener(monkeypatch)
    sent: list[str] = []
    escalations: list[tuple[str, dict]] = []
    monkeypatch.setattr(listener, "_REQUEST_TIMEOUT_S", 0.01, raising=False)
    monkeypatch.setattr(listener, "_WORKING_ACK_DELAY_S", 0.05, raising=False)

    delivery_state = {"current": "old"}

    async def _case():
        async def fake_send(text: str):
            sent.append(text)

        async def slow_run(text: str, session_meta: dict):
            await asyncio.sleep(0.05)
            return ["Old late reply."]

        async def fake_escalate(text: str, session_meta: dict):
            escalations.append((text, session_meta))

        result = await listener._run_request_with_timeout_contract(
            text="Please remove the wrong Doctor Appointment events from my calendar tomorrow at 2:30 PM.",
            session_meta={"sender_name": "Winship", "sender_chat_id": 123},
            send_reply=fake_send,
            is_authorized_user=True,
            run_cassandra=slow_run,
            escalate_failure=fake_escalate,
            should_deliver=lambda: delivery_state["current"] == "old",
        )
        assert result is None

    async def _runner():
        task = asyncio.create_task(_case())
        await asyncio.sleep(0.005)
        delivery_state["current"] = "new"
        await task
        await asyncio.sleep(0.05)

    asyncio.run(_runner())

    assert sent == []
    assert escalations == []


def test_handle_message_keeps_original_prompt_delivery_after_newer_prompt(monkeypatch):
    listener = _load_listener(monkeypatch)
    sent: list[str] = []
    captured_should_deliver = []

    class FakeUser:
        id = 123
        full_name = "Winship"

    class FakeChat:
        id = 456

    class FakeMessage:
        text = "Can you summarize the Capital Hilton status?"

        async def reply_text(self, text: str):
            sent.append(text)

    class FakeBot:
        async def send_chat_action(self, **kwargs):
            return None

    async def fake_contract(**kwargs):
        listener._CHAT_REQUEST_TOKENS[456] = 99
        captured_should_deliver.append(kwargs["should_deliver"]())
        await kwargs["send_reply"]("Correlated answer.")
        return ["Correlated answer."]

    monkeypatch.setattr(listener, "_run_request_with_timeout_contract", fake_contract, raising=False)
    monkeypatch.setattr(listener, "record_cassandra_listener_text_update", lambda **kwargs: None, raising=False)
    monkeypatch.setattr(listener, "_log_cassandra_route", lambda text, intent: None, raising=False)
    monkeypatch.setattr(listener, "speak", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(listener, "synthesize_for_voice_note", lambda *args, **kwargs: None, raising=False)

    update = types.SimpleNamespace(
        effective_user=FakeUser(),
        effective_chat=FakeChat(),
        message=FakeMessage(),
        update_id=12345,
    )
    context = types.SimpleNamespace(bot=FakeBot())

    asyncio.run(listener.handle_message(update, context))

    assert captured_should_deliver == [True]
    assert sent == ["Correlated answer."]
