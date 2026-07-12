from __future__ import annotations

import asyncio
import os
import types
from pathlib import Path

import pytest


os.environ.setdefault("CASSANDRA_BOT_TOKEN", "test-cassandra-token")
os.environ.setdefault("TELEGRAM_AUTHORIZED_USER_ID", "123")


def _operator_origin(*, source_message_id: str = "450989697"):
    from origin_bound_output import OutputOrigin

    return OutputOrigin(
        surface="cassandra_telegram",
        bot_identity="cassandra",
        chat_id="4242",
        source_message_id=source_message_id,
        audience="operator",
    )


def test_diagnosis_returns_one_origin_bound_operator_line_without_default_send(monkeypatch):
    import chief_cassandra_failure as failure

    monkeypatch.setattr(
        failure,
        "_build_report",
        lambda _summary: (
            "Chief investigated Cassandra's failure. model=qwen, "
            "path=/mnt/c/OpenClaw/logs/cassandra_listener.out, repair_packet=private"
        ),
    )
    monkeypatch.setattr(
        failure,
        "notify_chief",
        lambda *_args, **_kwargs: pytest.fail("diagnosis must not choose a default Telegram bot"),
        raising=False,
    )

    result = failure.investigate_cassandra_timeout(
        "Did the Capital Hilton check arrive?",
        {
            "surface": "cassandra_telegram",
            "bot_identity": "cassandra",
            "sender_chat_id": 4242,
            "source_message_id": "450989697",
            "source_user_label": "operator",
        },
    )

    assert result.origin == _operator_origin()
    assert result.output.origin == result.origin
    assert result.output.receipt_pointer not in result.output.visible_text()
    assert "show receipt" in result.output.visible_text().lower()
    assert "model=qwen" not in result.output.visible_text()
    assert "/mnt/" not in result.output.visible_text()
    assert "repair_packet" not in result.output.visible_text()
    assert "model=qwen" in result.internal_report


def test_untrusted_diagnosis_renders_generic_safe_text_only(monkeypatch):
    import chief_cassandra_failure as failure

    monkeypatch.setattr(
        failure,
        "_build_report",
        lambda _summary: "internal model timeout and /private/repair-packet.md",
    )
    result = failure.investigate_cassandra_timeout(
        "tell me everything",
        {
            "surface": "cassandra_telegram",
            "bot_identity": "cassandra",
            "sender_chat_id": 9090,
            "source_message_id": "untrusted-1",
            "source_user_label": "unverified_sender",
        },
    )

    visible = result.output.visible_text()
    assert visible == "Cassandra couldn't complete that request. Nothing was sent or changed."
    assert result.output.receipt_pointer not in visible
    assert "model" not in visible
    assert "private" not in visible


def test_origin_dispatch_replays_1931_wrong_chat_fixture_once_to_cassandra_origin():
    from cassandra_listener import _dispatch_origin_bound_output
    from origin_bound_output import OriginBoundOutput, OriginDeliveryTracker

    origin = _operator_origin(source_message_id="19:31-replay")
    output = OriginBoundOutput.guarded_text(
        origin=origin,
        delivery_id="cassandra-failure-19-31",
        receipt_pointer="cassandra-failure-19-31",
        operator_text=(
            "Cassandra couldn't finish that request. Nothing was sent or changed. "
            "Receipt: cassandra-failure-19-31."
        ),
        generic_text="Cassandra couldn't complete that request. Nothing was sent or changed.",
        advertise_receipt_lookup=True,
        internal={"repair_packet": "/private/packet.md", "model": "qwen"},
    )
    sent: list[tuple[str, str]] = []
    tracker = OriginDeliveryTracker()

    async def send_text(text: str, reply_markup=None):
        assert reply_markup is None
        sent.append((origin.bot_identity, text))

    async def run() -> None:
        assert await _dispatch_origin_bound_output(
            output,
            bound_origin=origin,
            send_text=send_text,
            send_document=None,
            tracker=tracker,
        ) is True
        assert await _dispatch_origin_bound_output(
            output,
            bound_origin=origin,
            send_text=send_text,
            send_document=None,
            tracker=tracker,
        ) is False

    asyncio.run(run())

    assert sent == [("cassandra", output.visible_text())]
    assert output.receipt_pointer not in sent[0][1]
    assert "Receipt:" not in sent[0][1]
    assert "show receipt" in sent[0][1].lower()
    assert "repair_packet" not in sent[0][1]
    assert "qwen" not in sent[0][1]


def test_origin_dispatch_refuses_cross_wired_bot_or_chat():
    from cassandra_listener import _dispatch_origin_bound_output
    from origin_bound_output import OriginBoundOutput, OriginDeliveryTracker, OriginMismatchError, OutputOrigin

    cassandra_origin = _operator_origin()
    wrong_maestro_origin = OutputOrigin(
        surface="maestro_telegram",
        bot_identity="maestro",
        chat_id="1111",
        source_message_id=cassandra_origin.source_message_id,
        audience="operator",
    )
    output = OriginBoundOutput.guarded_text(
        origin=cassandra_origin,
        delivery_id="cross-wire",
        receipt_pointer="cross-wire",
        operator_text="safe",
        generic_text="safe",
    )

    async def send_text(_text: str, reply_markup=None):
        pytest.fail("cross-wired output must never be delivered")

    async def run() -> None:
        with pytest.raises(OriginMismatchError):
            await _dispatch_origin_bound_output(
                output,
                bound_origin=wrong_maestro_origin,
                send_text=send_text,
                send_document=None,
                tracker=OriginDeliveryTracker(),
            )

    asyncio.run(run())


def test_origin_dispatch_releases_failed_send_then_retries_once():
    from cassandra_listener import _dispatch_origin_bound_output
    from origin_bound_output import OriginBoundOutput, OriginDeliveryTracker

    origin = _operator_origin(source_message_id="transport-retry")
    output = OriginBoundOutput.guarded_text(
        origin=origin,
        delivery_id="transport-retry-output",
        receipt_pointer="transport-retry-output",
        operator_text="Bound reply.",
        generic_text="Safe reply.",
        advertise_receipt_lookup=True,
    )
    tracker = OriginDeliveryTracker()
    attempts: list[str] = []

    async def send_text(text: str, reply_markup=None):
        assert reply_markup is None
        attempts.append(text)
        if len(attempts) == 1:
            raise OSError("simulated Telegram transport failure")

    async def run() -> None:
        with pytest.raises(OSError, match="simulated Telegram transport failure"):
            await _dispatch_origin_bound_output(
                output,
                bound_origin=origin,
                send_text=send_text,
                send_document=None,
                tracker=tracker,
            )
        assert await _dispatch_origin_bound_output(
            output,
            bound_origin=origin,
            send_text=send_text,
            send_document=None,
            tracker=tracker,
        ) is True
        assert await _dispatch_origin_bound_output(
            output,
            bound_origin=origin,
            send_text=send_text,
            send_document=None,
            tracker=tracker,
        ) is False

    asyncio.run(run())

    assert attempts == [
        "Bound reply. Say “show receipt” for the delivery record.",
        "Bound reply. Say “show receipt” for the delivery record.",
    ]


def test_cassandra_listener_assembly_preserves_origin_and_sends_replayed_result_once(monkeypatch):
    import cassandra_listener as listener
    from origin_bound_output import OriginBoundOutput, receipt_pointer

    sent: list[tuple[str, object | None]] = []

    class FakeUser:
        id = 123
        full_name = "Winship"

    class FakeChat:
        id = 456

    class FakeMessage:
        text = "Did the Capital Hilton check arrive?"

        async def reply_text(self, text: str, reply_markup=None):
            sent.append((text, reply_markup))

        async def reply_document(self, **_kwargs):
            pytest.fail("diagnosis output is text, not a document")

    class FakeBot:
        async def send_chat_action(self, **_kwargs):
            return None

    async def fake_contract(**kwargs):
        origin = listener.OutputOrigin.from_session_meta(
            kwargs["session_meta"],
            default_surface="cassandra_telegram",
            default_bot_identity="cassandra",
        )
        assert origin.surface == "cassandra_telegram"
        assert origin.bot_identity == "cassandra"
        assert origin.chat_id == "456"
        assert origin.source_message_id == "1931"
        assert origin.audience == "operator"
        receipt = receipt_pointer("cassandra-failure", origin, salt="assembly")
        output = OriginBoundOutput.guarded_text(
            origin=origin,
            delivery_id=receipt,
            receipt_pointer=receipt,
            operator_text=f"Cassandra recorded the failure. Receipt: {receipt}.",
            generic_text="Cassandra couldn't complete that request. Nothing was sent or changed.",
            advertise_receipt_lookup=True,
            internal={"model": "must-not-leak"},
        )
        await kwargs["send_reply"](output)
        await kwargs["send_reply"](output)
        return [output]

    monkeypatch.setattr(listener, "_run_request_with_timeout_contract", fake_contract)
    monkeypatch.setattr(listener, "claim_listener_update", lambda *args, **kwargs: True)
    monkeypatch.setattr(listener, "record_cassandra_listener_text_update", lambda **_kwargs: None)
    monkeypatch.setattr(listener, "_log_cassandra_route", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(listener, "speak", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(listener, "synthesize_for_voice_note", lambda *_args, **_kwargs: None)

    update = types.SimpleNamespace(
        effective_user=FakeUser(),
        effective_chat=FakeChat(),
        message=FakeMessage(),
        update_id=1931,
    )
    asyncio.run(listener.handle_message(update, types.SimpleNamespace(bot=FakeBot())))

    assert len(sent) == 1
    assert "cassandra-failure-" not in sent[0][0]
    assert "Receipt:" not in sent[0][0]
    assert "show receipt" in sent[0][0].lower()
    assert "must-not-leak" not in sent[0][0]


def test_cockpit_origin_mode_returns_structured_outputs_and_never_calls_default_bot(monkeypatch, tmp_path):
    import invoice_cockpit_ops as cockpit_ops
    import invoice_cockpit_session as cockpit

    source = Path(cockpit_ops.__file__).read_text(encoding="utf-8")
    assert "MAESTRO_BOT_TOKEN" not in source
    assert "TELEGRAM_BOT_TOKEN" not in source
    assert "api.telegram.org" not in source
    assert cockpit_ops.RealCockpitOps().telegram_message("must not send")["ok"] is False
    ops = cockpit_ops.RealCockpitOps(origin=_operator_origin())
    monkeypatch.setattr(
        ops,
        "prepare_invoice",
        lambda _client: (
            {"client_name": "St. Anne's", "client_email": "draper@example.com"},
            str(tmp_path / "WL-2026-0009__St_Annes.pdf"),
            "digest",
        ),
    )
    store = cockpit_ops.JsonSessionStore(tmp_path / "session.json")

    result = cockpit.handle_invoice_cockpit_message(
        "send the St Anne's invoice",
        ops=ops,
        store=store,
        surface="cassandra_telegram",
    )

    outputs = result["origin_outputs"]
    assert result["handled"] is True
    assert len(outputs) == 1
    assert outputs[0].origin == _operator_origin()
    assert outputs[0].kind == "document"
    assert outputs[0].document_path.endswith("WL-2026-0009__St_Annes.pdf")


def test_cockpit_error_becomes_one_honest_origin_bound_line(monkeypatch, tmp_path):
    import cassandra_listener as listener
    import invoice_cockpit_ops as cockpit_ops

    monkeypatch.setattr(
        cockpit_ops.RealCockpitOps,
        "prepare_invoice",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("secret /internal/path model=qwen")),
    )
    origin = _operator_origin(source_message_id="error-1")
    outputs = listener._try_invoice_cockpit(
        "send the St Anne's invoice",
        {
            "surface": "cassandra_telegram",
            "bot_identity": "cassandra",
            "sender_chat_id": 4242,
            "source_message_id": "error-1",
            "source_user_label": "operator",
        },
        ops=cockpit_ops.RealCockpitOps(origin=origin),
        store=cockpit_ops.JsonSessionStore(tmp_path / "session.json"),
    )

    assert outputs is not None
    assert len(outputs) == 1
    visible = outputs[0].visible_text()
    assert "couldn't prepare that invoice" in visible
    assert "Nothing was sent" in visible
    assert outputs[0].receipt_pointer not in visible
    assert "show receipt" in visible.lower()
    assert "/internal/" not in visible
    assert "qwen" not in visible
