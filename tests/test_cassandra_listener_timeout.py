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

    return importlib.reload(cassandra_listener)


def test_timeout_contract_success_sends_ack_then_result(monkeypatch):
    listener = _load_listener(monkeypatch)
    sent: list[str] = []
    escalations: list[tuple[str, dict]] = []

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


def test_timeout_contract_delivers_late_success_once(monkeypatch):
    listener = _load_listener(monkeypatch)
    sent: list[str] = []
    monkeypatch.setattr(listener, "_REQUEST_TIMEOUT_S", 0.01, raising=False)

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
