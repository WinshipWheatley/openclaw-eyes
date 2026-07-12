from __future__ import annotations

import asyncio
import importlib
import sqlite3
import sys
import types
from pathlib import Path

import fleet_receipt_index as receipt_index
from operator_surface_guard import guard_operator_reply
from origin_bound_output import (
    OPERATOR_AUDIENCE,
    OriginBoundOutput,
    OriginDeliveryTracker,
    OutputOrigin,
)


def _load_listener(monkeypatch):
    monkeypatch.setenv("CASSANDRA_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    fake_filters = types.SimpleNamespace(TEXT=object(), COMMAND=object(), VOICE=object())
    fake_context_types = types.SimpleNamespace(DEFAULT_TYPE=object())

    class _FakeApplicationBuilder:
        def token(self, _token):
            return self

        def build(self):
            return types.SimpleNamespace(
                add_handler=lambda *a, **k: None,
                run_polling=lambda: None,
            )

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


def _origin_output(*, kind: str = "text", document_path: str = "") -> OriginBoundOutput:
    origin = OutputOrigin(
        surface="cassandra_telegram",
        bot_identity="cassandra",
        chat_id="77",
        # Deliberately the Telegram update id, not the inbound message id.
        source_message_id="update-999",
        audience=OPERATOR_AUDIENCE,
    )
    if kind == "document":
        return OriginBoundOutput.guarded_document(
            origin=origin,
            delivery_id="delivery-document-1",
            receipt_pointer="origin-raw-document-pointer",
            document_path=document_path,
            caption="The prepared document is attached.",
            advertise_receipt_lookup=True,
        )
    return OriginBoundOutput.guarded_text(
        origin=origin,
        delivery_id="delivery-text-1",
        receipt_pointer="origin-raw-text-pointer",
        operator_text="The requested response is ready.",
        advertise_receipt_lookup=True,
    )


def _row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with sqlite3.connect(path) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM fleet_receipt_deliveries").fetchone()[0])


def _real_cassandra_preserve_decision(monkeypatch, tmp_path: Path):
    import typed_contract_decision as typed

    provider_db = tmp_path / "typed-provider.sqlite3"
    monkeypatch.setenv(typed.CONTRACT_RECEIPT_DB_ENV, str(provider_db))
    decision = typed.decide_contract(
        "this is an unrelated conversation question",
        context=typed.ContractContext(
            agent="cassandra",
            surface="cassandra_telegram",
            active_session=True,
            session_kind="workflow",
            session_snapshot={"status": "active"},
        ),
        semantic_vote_enabled=False,
    )
    assert decision.action is typed.DecisionAction.PRESERVE_SESSION
    assert decision.receipt.receipt_persisted is True
    assert typed.resolve_contract_receipt(
        decision.receipt.receipt_pointer,
        path=provider_db,
    ) is not None
    return decision


def _real_cassandra_workflow_decision(tmp_path: Path):
    import typed_contract_decision as typed
    import workflow_package_queue as workflow

    provider_db = tmp_path / "workflow-provider.sqlite3"

    def stage_handoff(raw_text: str, _context: typed.ContractContext) -> typed.HandoffResult:
        staged = workflow.stage_live_arts_invoice_handoff(
            raw_text,
            source_surface="cassandra_telegram",
            sqlite_path=provider_db,
            created_at="2026-07-11T20:00:00+00:00",
        )
        return typed.HandoffResult(
            reply=workflow.render_live_arts_handoff_reply(staged),
            receipt_pointer=str(staged["receipt"]["receipt_ref"]),
            package_id=str(staged["package"]["package_id"]),
        )

    decision = typed.decide_contract(
        "route the Live Arts PA bill to whoever should own it",
        context=typed.ContractContext(
            agent="cassandra",
            surface="cassandra_telegram",
        ),
        handoff_stager=stage_handoff,
        semantic_vote_enabled=False,
    )
    assert decision.action is typed.DecisionAction.STAGE_HANDOFF
    assert workflow.resolve_workflow_receipt(
        decision.receipt.receipt_pointer,
        sqlite_path=provider_db,
    ) is not None
    return decision, provider_db


def test_successful_origin_text_delivery_registers_actual_message_binding_and_restarts(
    tmp_path,
    monkeypatch,
):
    listener = _load_listener(monkeypatch)
    db_path = tmp_path / "fleet.sqlite3"
    output = _origin_output()
    sent: list[str] = []

    async def send_text(text: str, reply_markup=None):
        sent.append(text)
        return types.SimpleNamespace(message_id=900)

    async def send_document(_path: str, _caption: str):
        raise AssertionError("text output must not use document transport")

    delivered = asyncio.run(
        listener._dispatch_origin_bound_output(
            output,
            bound_origin=output.origin,
            send_text=send_text,
            send_document=send_document,
            tracker=OriginDeliveryTracker(),
            source_message_id="321",
            receipt_db_path=db_path,
        )
    )

    assert delivered is True
    assert sent == [
        "The requested response is ready. Say “show receipt” for the delivery record."
    ]
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT source_message_id, delivered_message_id, raw_ref FROM fleet_receipt_deliveries"
        ).fetchone()
    assert row == ("321", "900", "origin-raw-text-pointer")

    # A fresh resolver invocation proves the lookup survives process restart.
    resolution = receipt_index.resolve_receipt_request(
        "show receipt",
        surface="cassandra_telegram",
        bot_identity="cassandra",
        chat_id="77",
        reply_to_message_id="900",
        db_path=db_path,
    )
    assert resolution is not None
    assert resolution.outcome == "found"
    assert "What happened: Cassandra delivered an operator response." in resolution.text
    assert "Status: Delivered successfully." in resolution.text
    assert (
        "Authority: Reply delivery only; no business-action authority was granted."
        in resolution.text
    )
    assert "No email or external message action is claimed." in resolution.text
    assert "No ledger, payment, or workflow action is claimed." in resolution.text
    assert "origin-raw-text-pointer" not in resolution.text
    assert guard_operator_reply(resolution.text, agent_role="OPENCLAW_SYSTEM") == resolution.text


def test_successful_origin_document_delivery_registers_only_after_message_id(
    tmp_path,
    monkeypatch,
):
    listener = _load_listener(monkeypatch)
    db_path = tmp_path / "fleet.sqlite3"
    document = tmp_path / "invoice.pdf"
    document.write_bytes(b"fixture")
    output = _origin_output(kind="document", document_path=str(document))
    events: list[str] = []

    async def send_text(_text: str, reply_markup=None):
        raise AssertionError("valid operator document must use document transport")

    async def send_document(path: str, caption: str):
        assert path == str(document)
        assert caption == (
            "The prepared document is attached. "
            "Say “show receipt” for the delivery record."
        )
        events.append("send-complete")
        return types.SimpleNamespace(message_id=901)

    original_register = listener.register_delivered_receipt

    def ordered_register(*args, **kwargs):
        assert events == ["send-complete"]
        events.append("registered")
        return original_register(*args, **kwargs)

    monkeypatch.setattr(listener, "register_delivered_receipt", ordered_register)
    delivered = asyncio.run(
        listener._dispatch_origin_bound_output(
            output,
            bound_origin=output.origin,
            send_text=send_text,
            send_document=send_document,
            tracker=OriginDeliveryTracker(),
            source_message_id="322",
            receipt_db_path=db_path,
        )
    )

    assert delivered is True
    assert events == ["send-complete", "registered"]
    assert _row_count(db_path) == 1


def test_missing_document_fallback_does_not_advertise_or_register_receipt(
    tmp_path,
    monkeypatch,
):
    listener = _load_listener(monkeypatch)
    db_path = tmp_path / "fleet.sqlite3"
    output = _origin_output(kind="document", document_path=str(tmp_path / "missing.pdf"))
    sent: list[str] = []

    async def send_text(text: str, reply_markup=None):
        sent.append(text)
        return types.SimpleNamespace(message_id=904)

    async def send_document(_path: str, _caption: str):
        raise AssertionError("missing documents must not reach document transport")

    assert asyncio.run(
        listener._dispatch_origin_bound_output(
            output,
            bound_origin=output.origin,
            send_text=send_text,
            send_document=send_document,
            tracker=OriginDeliveryTracker(),
            source_message_id="326",
            receipt_db_path=db_path,
        )
    ) is True
    assert sent == ["I couldn't attach the prepared invoice. Nothing was sent."]
    assert "show receipt" not in sent[0].lower()
    assert "origin-raw-document-pointer" not in sent[0]
    assert _row_count(db_path) == 0


def test_failed_transport_creates_no_row_and_releases_tracker_for_retry(tmp_path, monkeypatch):
    listener = _load_listener(monkeypatch)
    db_path = tmp_path / "fleet.sqlite3"
    output = _origin_output()
    tracker = OriginDeliveryTracker()
    attempts = 0

    async def send_text(_text: str, reply_markup=None):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transport failed")
        return types.SimpleNamespace(message_id=902)

    async def send_document(_path: str, _caption: str):
        raise AssertionError

    async def run_case():
        try:
            await listener._dispatch_origin_bound_output(
                output,
                bound_origin=output.origin,
                send_text=send_text,
                send_document=send_document,
                tracker=tracker,
                source_message_id="323",
                receipt_db_path=db_path,
            )
        except RuntimeError as exc:
            assert str(exc) == "transport failed"
        else:
            raise AssertionError("transport error must propagate")
        assert _row_count(db_path) == 0
        return await listener._dispatch_origin_bound_output(
            output,
            bound_origin=output.origin,
            send_text=send_text,
            send_document=send_document,
            tracker=tracker,
            source_message_id="323",
            receipt_db_path=db_path,
        )

    assert asyncio.run(run_case()) is True
    assert attempts == 2
    assert _row_count(db_path) == 1


def test_missing_outbound_message_id_and_registration_error_are_fail_soft(
    tmp_path,
    monkeypatch,
):
    listener = _load_listener(monkeypatch)
    missing_id_db = tmp_path / "missing.sqlite3"
    output = _origin_output()

    async def send_without_id(_text: str, reply_markup=None):
        return types.SimpleNamespace()

    async def no_document(_path: str, _caption: str):
        raise AssertionError

    assert asyncio.run(
        listener._dispatch_origin_bound_output(
            output,
            bound_origin=output.origin,
            send_text=send_without_id,
            send_document=no_document,
            tracker=OriginDeliveryTracker(),
            source_message_id="324",
            receipt_db_path=missing_id_db,
        )
    ) is True
    assert _row_count(missing_id_db) == 0

    sent = 0

    async def successful_send(_text: str, reply_markup=None):
        nonlocal sent
        sent += 1
        return types.SimpleNamespace(message_id=903)

    def broken_register(*_args, **_kwargs):
        raise sqlite3.OperationalError("index unavailable")

    monkeypatch.setattr(listener, "register_delivered_receipt", broken_register)
    tracker = OriginDeliveryTracker()
    assert asyncio.run(
        listener._dispatch_origin_bound_output(
            output,
            bound_origin=output.origin,
            send_text=successful_send,
            send_document=no_document,
            tracker=tracker,
            source_message_id="325",
            receipt_db_path=tmp_path / "broken.sqlite3",
        )
    ) is True
    # Successful delivery remains claimed; an index failure cannot duplicate it.
    assert asyncio.run(
        listener._dispatch_origin_bound_output(
            output,
            bound_origin=output.origin,
            send_text=successful_send,
            send_document=no_document,
            tracker=tracker,
            source_message_id="325",
            receipt_db_path=tmp_path / "broken.sqlite3",
        )
    ) is False
    assert sent == 1


def _seed_receipt(db_path: Path) -> None:
    descriptor = receipt_index.build_receipt_descriptor(
        provider="origin_output",
        raw_ref="machine-only-origin-pointer",
        what_happened="Cassandra delivered an operator response.",
        status="Delivered successfully.",
        occurred_at="2026-07-11T12:00:00+00:00",
        authority_summary="The delivery used the operator's bound Cassandra chat.",
        no_action_facts=("No additional external action is recorded.",),
    )
    receipt_index.register_delivered_receipt(
        descriptor,
        surface="cassandra_telegram",
        bot_identity="cassandra",
        chat_id="77",
        source_message_id="321",
        delivered_message_id="900",
        delivery_succeeded=True,
        db_path=db_path,
    )


class _Message:
    def __init__(self, text: str, *, reply_to_message_id: int | None = None):
        self.text = text
        self.message_id = 444
        self.forward_origin = None
        self.reply_to_message = (
            types.SimpleNamespace(message_id=reply_to_message_id)
            if reply_to_message_id is not None
            else None
        )
        self.sent: list[str] = []

    async def reply_text(self, text: str, **_kwargs):
        self.sent.append(text)
        return types.SimpleNamespace(message_id=901)


def _update(text: str, *, user_id: int, reply_to_message_id: int | None = None):
    message = _Message(text, reply_to_message_id=reply_to_message_id)
    return types.SimpleNamespace(
        update_id=999,
        message=message,
        effective_user=types.SimpleNamespace(id=user_id, full_name="Operator"),
        effective_chat=types.SimpleNamespace(id=77),
    )


def test_authorized_show_receipt_short_circuits_before_intake_or_model(
    tmp_path,
    monkeypatch,
):
    listener = _load_listener(monkeypatch)
    db_path = tmp_path / "fleet.sqlite3"
    _seed_receipt(db_path)
    monkeypatch.setenv("OPENCLAW_FLEET_RECEIPT_INDEX_DB", str(db_path))
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_a, **_k: True)
    monkeypatch.setattr(
        listener,
        "record_cassandra_listener_text_update",
        lambda **_k: (_ for _ in ()).throw(AssertionError("governed intake must be bypassed")),
    )
    monkeypatch.setattr(
        listener,
        "_run_request_with_timeout_contract",
        lambda **_k: (_ for _ in ()).throw(AssertionError("model/session path must be bypassed")),
    )
    update = _update("show receipt", user_id=123, reply_to_message_id=900)

    asyncio.run(listener.handle_message(update, types.SimpleNamespace()))

    assert len(update.message.sent) == 1
    assert "What happened: Cassandra delivered an operator response." in update.message.sent[0]
    assert "machine-only-origin-pointer" not in update.message.sent[0]
    assert "999" not in update.message.sent[0]


def test_designated_contact_receipt_request_is_denied_without_index_or_model(
    tmp_path,
    monkeypatch,
):
    listener = _load_listener(monkeypatch)
    db_path = tmp_path / "fleet.sqlite3"
    _seed_receipt(db_path)
    monkeypatch.setenv("OPENCLAW_FLEET_RECEIPT_INDEX_DB", str(db_path))
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_a, **_k: True)
    monkeypatch.setattr(listener, "is_designated_contact_sender", lambda **_k: True)
    monkeypatch.setattr(
        listener,
        "resolve_receipt_request",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("contact must not query index")),
    )
    monkeypatch.setattr(
        listener,
        "record_cassandra_listener_text_update",
        lambda **_k: (_ for _ in ()).throw(AssertionError("receipt command must short-circuit")),
    )
    update = _update("show receipt", user_id=456, reply_to_message_id=900)

    asyncio.run(listener.handle_message(update, types.SimpleNamespace()))

    assert update.message.sent == ["Receipt lookup is available only to the operator."]
    assert "machine-only-origin-pointer" not in update.message.sent[0]


def test_operator_receipt_lookup_error_fails_closed_before_intake(
    tmp_path,
    monkeypatch,
):
    listener = _load_listener(monkeypatch)
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_a, **_k: True)
    monkeypatch.setattr(
        listener,
        "resolve_receipt_request",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("index unavailable")),
    )
    monkeypatch.setattr(
        listener,
        "record_cassandra_listener_text_update",
        lambda **_k: (_ for _ in ()).throw(AssertionError("intake must not run")),
    )
    update = _update("show receipt", user_id=123)

    asyncio.run(listener.handle_message(update, types.SimpleNamespace()))

    assert update.message.sent == [
        "I couldn't read the delivered-receipt index right now. No action ran."
    ]


def test_durable_typed_preserve_metadata_survives_run_path_and_indexes_post_send(
    tmp_path,
    monkeypatch,
):
    listener = _load_listener(monkeypatch)
    import invoice_cockpit_ops
    import typed_contract_decision as typed

    class EmptySessionStore:
        def __init__(self, _path):
            pass

        def load(self):
            return {}

    decision = _real_cassandra_preserve_decision(monkeypatch, tmp_path)
    raw_ref = decision.receipt.receipt_pointer
    monkeypatch.setattr(invoice_cockpit_ops, "JsonSessionStore", EmptySessionStore)
    monkeypatch.setattr(typed, "decide_contract", lambda *_a, **_k: decision)
    replies = asyncio.run(
        listener._run_cassandra_handle_async(
            "uncertain active-session answer",
            {
                "surface": "cassandra_telegram",
                "bot_identity": "cassandra",
                "sender_chat_id": 77,
                "source_message_id": "update-999",
            },
        )
    )
    assert len(replies) == 1
    reply = replies[0]
    assert isinstance(reply, listener._ReceiptBoundReply)
    assert reply.provider == "typed_contract"
    assert "show receipt" in reply.text.lower()

    db_path = tmp_path / "fleet.sqlite3"
    origin = OutputOrigin(
        surface="cassandra_telegram",
        bot_identity="cassandra",
        chat_id="77",
        source_message_id="update-999",
        audience=OPERATOR_AUDIENCE,
    )
    events: list[str] = []

    async def send_text(text: str, reply_markup=None):
        assert "show receipt" in text.lower()
        events.append("send-complete")
        return types.SimpleNamespace(message_id=905)

    original_register = listener.register_delivered_receipt

    def ordered_register(*args, **kwargs):
        assert events == ["send-complete"]
        events.append("registered")
        return original_register(*args, **kwargs)

    monkeypatch.setattr(listener, "register_delivered_receipt", ordered_register)
    assert asyncio.run(
        listener._dispatch_receipt_bound_reply(
            reply,
            bound_origin=origin,
            send_text=send_text,
            source_message_id="327",
            receipt_db_path=db_path,
        )
    ) is True
    assert events == ["send-complete", "registered"]
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT provider, source_message_id, delivered_message_id, raw_ref "
            "FROM fleet_receipt_deliveries"
        ).fetchone()
    assert row == ("typed_contract", "327", "905", raw_ref)

    resolution = receipt_index.resolve_receipt_request(
        "show receipt",
        surface="cassandra_telegram",
        bot_identity="cassandra",
        chat_id="77",
        reply_to_message_id="905",
        db_path=db_path,
    )
    assert resolution is not None
    assert "Status: Session preserved; no workflow action ran." in resolution.text
    assert "business-action authority was granted" in resolution.text
    assert "Nothing was sent." in resolution.text
    assert "No ledger, payment, or workflow action ran." in resolution.text
    assert raw_ref not in resolution.text


def test_nondurable_typed_preserve_removes_lookup_hint_and_cannot_index(monkeypatch):
    listener = _load_listener(monkeypatch)
    decision = types.SimpleNamespace(
        reply=(
            "I left the open workflow step unchanged. "
            "Say “show receipt” for the decision record."
        ),
        receipt=types.SimpleNamespace(
            action="preserve_session",
            session_preserved=True,
            receipt_persisted=False,
            receipt_pointer="contract:nondurable-pointer",
        ),
    )

    reply = listener._typed_contract_bound_reply(decision)

    assert isinstance(reply, str)
    assert reply == "I left the open workflow step unchanged."
    assert "show receipt" not in reply.lower()
    assert "contract:nondurable-pointer" not in reply


def test_staged_workflow_receipt_is_carried_to_post_send_registration(tmp_path, monkeypatch):
    listener = _load_listener(monkeypatch)
    decision, workflow_db = _real_cassandra_workflow_decision(tmp_path)

    reply = listener._typed_contract_bound_reply(
        decision,
        workflow_db_path=workflow_db,
    )

    assert isinstance(reply, listener._ReceiptBoundReply)
    assert reply.provider == "workflow"
    assert reply.raw_ref == decision.receipt.receipt_pointer
    assert "show receipt" in reply.text.lower()
    assert reply.raw_ref not in reply.text

    db_path = tmp_path / "fleet.sqlite3"
    origin = OutputOrigin(
        surface="cassandra_telegram",
        bot_identity="cassandra",
        chat_id="77",
        source_message_id="update-999",
        audience=OPERATOR_AUDIENCE,
    )

    async def send_text(_text: str, reply_markup=None):
        return types.SimpleNamespace(message_id=906)

    assert asyncio.run(
        listener._dispatch_receipt_bound_reply(
            reply,
            bound_origin=origin,
            send_text=send_text,
            source_message_id="328",
            receipt_db_path=db_path,
        )
    ) is True
    resolution = receipt_index.resolve_receipt_request(
        "show receipt",
        surface="cassandra_telegram",
        bot_identity="cassandra",
        chat_id="77",
        reply_to_message_id="906",
        db_path=db_path,
    )
    assert resolution is not None
    assert "workflow handoff was staged for Cassandra" in resolution.text
    assert "Nothing was posted to the ledger or changed" in resolution.text
    assert "No ledger, payment, or workflow action is claimed" not in resolution.text


def test_real_typed_receipt_from_another_surface_cannot_cross_wire_into_cassandra(
    tmp_path,
    monkeypatch,
):
    listener = _load_listener(monkeypatch)
    import typed_contract_decision as typed

    provider_db = tmp_path / "typed-provider.sqlite3"
    monkeypatch.setenv(typed.CONTRACT_RECEIPT_DB_ENV, str(provider_db))
    chief_decision = typed.decide_contract(
        "this is an unrelated conversation question",
        context=typed.ContractContext(
            agent="chief",
            surface="chief_listener",
            active_session=True,
            session_kind="billing",
            session_snapshot={"status": "active"},
        ),
        semantic_vote_enabled=False,
    )
    assert chief_decision.receipt.receipt_persisted is True

    reply = listener._typed_contract_bound_reply(chief_decision)

    assert isinstance(reply, str)
    assert "show receipt" not in reply.lower()
    assert chief_decision.receipt.receipt_pointer not in reply
