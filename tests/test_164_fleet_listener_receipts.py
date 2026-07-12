from __future__ import annotations

import asyncio
import importlib
import inspect
import sqlite3
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

import fleet_receipt_index
import typed_contract_decision as typed_contract
import workflow_package_queue


class _Filter:
    def __and__(self, _other):
        return self

    def __invert__(self):
        return self


class _Builder:
    def token(self, _token):
        return self

    def build(self):
        return SimpleNamespace(add_handler=lambda *_args, **_kwargs: None)


def _install_telegram_stubs(monkeypatch) -> None:
    telegram = types.ModuleType("telegram")
    telegram.Update = object
    telegram.InlineKeyboardMarkup = lambda *args, **kwargs: (args, kwargs)
    errors = types.ModuleType("telegram.error")
    errors.BadRequest = type("BadRequest", (Exception,), {})
    errors.Forbidden = type("Forbidden", (Exception,), {})
    ext = types.ModuleType("telegram.ext")
    ext.ApplicationBuilder = _Builder
    ext.MessageHandler = lambda *_args, **_kwargs: None
    ext.CallbackQueryHandler = lambda *_args, **_kwargs: None
    ext.filters = SimpleNamespace(TEXT=_Filter(), COMMAND=_Filter())
    ext.ContextTypes = SimpleNamespace(DEFAULT_TYPE=object)
    monkeypatch.setitem(sys.modules, "telegram", telegram)
    monkeypatch.setitem(sys.modules, "telegram.error", errors)
    monkeypatch.setitem(sys.modules, "telegram.ext", ext)


def _load_listener(monkeypatch, module_name: str):
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    monkeypatch.setenv("CHIEF_BOT_TOKEN", "chief-test-token")
    monkeypatch.setenv("GUARDIAN_BOT_TOKEN", "guardian-test-token")
    monkeypatch.setenv("NILES_BOT_TOKEN", "niles-test-token")
    _install_telegram_stubs(monkeypatch)
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


class _Bot:
    async def send_chat_action(self, **_kwargs) -> None:
        return None


class _Message:
    def __init__(
        self,
        text: str,
        *,
        message_id: int,
        delivered_message_id: int | None = 9001,
        reply_to_message_id: int | None = None,
        fail_send: bool = False,
    ) -> None:
        self.text = text
        self.message_id = message_id
        self.chat_id = 456
        self.reply_to_message = (
            SimpleNamespace(message_id=reply_to_message_id)
            if reply_to_message_id is not None
            else None
        )
        self.delivered_message_id = delivered_message_id
        self.fail_send = fail_send
        self.replies: list[str] = []
        self.send_attempts = 0

    async def reply_text(self, text: str):
        self.send_attempts += 1
        if self.fail_send:
            raise RuntimeError("telegram send failed")
        self.replies.append(text)
        return SimpleNamespace(message_id=self.delivered_message_id)


def _update(message: _Message):
    return SimpleNamespace(
        update_id=777777,
        effective_user=SimpleNamespace(id=123),
        effective_chat=SimpleNamespace(id=456),
        message=message,
    )


def _row(path: Path):
    if not path.exists():
        return None
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT provider, raw_ref, surface, bot_identity, chat_id, "
            "source_message_id, delivered_message_id FROM fleet_receipt_deliveries"
        ).fetchone()


@pytest.mark.parametrize(
    ("module_name", "surface", "bot_identity"),
    (
        ("chief_listener", "chief_listener", "chief"),
        ("chief_guardian_listener", "guardian_listener", "guardian"),
        ("producer_listener", "niles_producer_listener", "niles"),
    ),
)
def test_bound_show_receipt_short_circuits_before_governed_intake(
    monkeypatch,
    tmp_path: Path,
    module_name: str,
    surface: str,
    bot_identity: str,
) -> None:
    listener = _load_listener(monkeypatch, module_name)
    db_path = tmp_path / "fleet.sqlite3"
    monkeypatch.setenv("OPENCLAW_FLEET_RECEIPT_INDEX_DB", str(db_path))
    descriptor = fleet_receipt_index.build_receipt_descriptor(
        provider="typed_contract",
        raw_ref=f"contract:{bot_identity}-machine-only",
        what_happened=f"{bot_identity.title()} preserved the active conversation session.",
        status="Session preserved; no workflow action ran.",
        occurred_at="2026-07-11T12:00:00+00:00",
        authority_summary="Conversation continuity only; no business-action authority was granted.",
        no_action_facts=("Nothing was sent.", "No ledger, payment, or workflow action ran."),
    )
    fleet_receipt_index.register_delivered_receipt(
        descriptor,
        surface=surface,
        bot_identity=bot_identity,
        chat_id="456",
        source_message_id="444",
        delivered_message_id="9000",
        delivery_succeeded=True,
        db_path=db_path,
    )
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        listener,
        "record_telegram_listener_update_safe",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("governed intake ran")),
    )
    if module_name == "chief_listener":
        monkeypatch.setattr(
            listener,
            "route_message",
            lambda _text: (_ for _ in ()).throw(AssertionError("router ran")),
        )
    message = _Message("show receipt", message_id=445, reply_to_message_id=9000)

    asyncio.run(listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert len(message.replies) == 1
    assert message.replies[0].startswith("Receipt R-")
    assert descriptor.raw_ref not in message.replies[0]


@pytest.mark.parametrize(
    "module_name",
    ("chief_listener", "chief_guardian_listener", "producer_listener"),
)
def test_receipt_tap_source_order_is_claim_then_lookup_then_governed_intake(
    monkeypatch,
    module_name: str,
) -> None:
    listener = _load_listener(monkeypatch, module_name)
    source = inspect.getsource(listener.handle_message)

    assert source.index("claim_listener_update") < source.index("resolve_telegram_receipt_request")
    assert source.index("resolve_telegram_receipt_request") < source.index(
        "record_telegram_listener_update_safe"
    )


def test_chief_show_receipt_lookup_exception_fails_closed_before_router_or_intake(
    monkeypatch,
) -> None:
    listener = _load_listener(monkeypatch, "chief_listener")
    calls = []
    monkeypatch.setattr(
        listener,
        "claim_listener_update",
        lambda *_args, **_kwargs: calls.append("claim") or True,
    )
    monkeypatch.setattr(
        listener,
        "resolve_telegram_receipt_request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("index unavailable")),
    )
    monkeypatch.setattr(
        listener,
        "record_telegram_listener_update_safe",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("governed intake ran")),
    )
    monkeypatch.setattr(
        listener,
        "route_message",
        lambda _text: (_ for _ in ()).throw(AssertionError("router ran")),
    )
    message = _Message("show receipt", message_id=445)

    asyncio.run(listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert calls == ["claim"]
    assert message.send_attempts == 1
    assert message.replies == [
        "The receipt index is unavailable right now. No send, workflow, model, tool, "
        "ledger, payment, or external action ran."
    ]


def _contract_receipt(*, action: str, raw_ref: str, persisted: bool) -> dict:
    return {
        "action": action,
        "receipt_pointer": raw_ref,
        "receipt_persisted": persisted,
        "session_preserved": action == "preserve_session",
    }


def _durable_typed_receipt(
    monkeypatch,
    tmp_path: Path,
    *,
    agent: str,
    surface: str,
    text: str,
) -> dict:
    monkeypatch.setenv(
        typed_contract.CONTRACT_RECEIPT_DB_ENV,
        str(tmp_path / "typed_contract.sqlite3"),
    )
    decision = typed_contract.decide_contract(
        text,
        context=typed_contract.ContractContext(
            agent=agent,
            surface=surface,
            active_session=True,
            session_kind="test_session",
        ),
        semantic_vote_enabled=False,
    )
    assert decision.receipt.receipt_persisted is True
    return decision.receipt.to_dict()


def test_niles_registers_direct_typed_receipt_after_successful_message_delivery(
    monkeypatch,
    tmp_path: Path,
) -> None:
    listener = _load_listener(monkeypatch, "producer_listener")
    db_path = tmp_path / "fleet.sqlite3"
    monkeypatch.setenv("OPENCLAW_FLEET_RECEIPT_INDEX_DB", str(db_path))
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_args, **_kwargs: True)
    intake_ids = []
    monkeypatch.setattr(
        listener,
        "record_telegram_listener_update_safe",
        lambda **kwargs: intake_ids.append(kwargs["source_message_id"]),
    )
    monkeypatch.setattr(listener, "_fire_agent_voice", lambda *_args, **_kwargs: None)
    import typed_contract_decision

    receipt = _durable_typed_receipt(
        monkeypatch,
        tmp_path,
        agent="niles",
        surface="niles_producer_listener",
        text="maybe that other thing",
    )
    seen_contexts = []

    def _decide_niles(*_args, **kwargs):
        seen_contexts.append(kwargs["context"])
        return SimpleNamespace(
            handled=True,
            reply="Niles preserved this conversation. Say “show receipt” for the delivery record.",
            receipt=SimpleNamespace(to_dict=lambda: receipt),
        )

    monkeypatch.setattr(
        typed_contract_decision,
        "decide_contract",
        _decide_niles,
    )
    message = _Message("hold this thread", message_id=444, delivered_message_id=9001)

    asyncio.run(listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert _row(db_path) == (
        "typed_contract",
        receipt["receipt_pointer"],
        "niles_producer_listener",
        "niles",
        "456",
        "444",
        "9001",
    )
    assert intake_ids == ["777777"]
    assert seen_contexts[0].source_message_id == "777777"
    assert str(receipt["receipt_pointer"]) not in message.replies[0]


def test_guardian_registers_pending_session_preserve_after_successful_delivery(
    monkeypatch,
    tmp_path: Path,
) -> None:
    listener = _load_listener(monkeypatch, "chief_guardian_listener")
    db_path = tmp_path / "fleet.sqlite3"
    monkeypatch.setenv("OPENCLAW_FLEET_RECEIPT_INDEX_DB", str(db_path))
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_args, **_kwargs: True)
    intake_ids = []
    monkeypatch.setattr(
        listener,
        "record_telegram_listener_update_safe",
        lambda **kwargs: intake_ids.append(kwargs["source_message_id"]),
    )
    import chief_approval_brain
    import hitl_notification_service
    import typed_contract_decision

    monkeypatch.setattr(hitl_notification_service, "handle_typed_reply", lambda *_args, **_kwargs: {"handled": False})
    monkeypatch.setattr(chief_approval_brain, "has_pending_approval", lambda: True)
    monkeypatch.setattr(
        chief_approval_brain,
        "_load_pending",
        lambda: {"id": "A3F2-full", "options": 2, "action": "review"},
    )
    monkeypatch.setattr(chief_approval_brain, "parse_reply_code", lambda *_args, **_kwargs: ("", "not a decision"))
    receipt = _durable_typed_receipt(
        monkeypatch,
        tmp_path,
        agent="guardian",
        surface="guardian_listener",
        text="maybe that other thing",
    )
    seen_contexts = []

    def _decide_guardian(*_args, **kwargs):
        seen_contexts.append(kwargs["context"])
        return SimpleNamespace(
            handled=True,
            label=typed_contract_decision.ContractLabel.UNRESOLVED,
            reply="Guardian kept the pending approval unchanged. Say “show receipt” for the delivery record.",
            receipt=SimpleNamespace(to_dict=lambda: receipt),
        )

    monkeypatch.setattr(
        typed_contract_decision,
        "decide_contract",
        _decide_guardian,
    )
    message = _Message("explain that", message_id=444, delivered_message_id=9002)

    asyncio.run(listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert _row(db_path) == (
        "typed_contract",
        receipt["receipt_pointer"],
        "guardian_listener",
        "guardian",
        "456",
        "444",
        "9002",
    )
    assert intake_ids == ["777777"]
    assert seen_contexts[0].source_message_id == "777777"
    assert str(receipt["receipt_pointer"]) not in message.replies[0]


def test_chief_registers_durable_router_contract_before_fallback_log(
    monkeypatch,
    tmp_path: Path,
) -> None:
    listener = _load_listener(monkeypatch, "chief_listener")
    db_path = tmp_path / "fleet.sqlite3"
    log_path = tmp_path / "chief_input.log"
    monkeypatch.setenv("OPENCLAW_FLEET_RECEIPT_INDEX_DB", str(db_path))
    monkeypatch.setattr(listener, "LOG_PATH", log_path)
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_args, **_kwargs: True)
    intake_ids = []
    monkeypatch.setattr(
        listener,
        "record_telegram_listener_update_safe",
        lambda **kwargs: intake_ids.append(kwargs["source_message_id"]),
    )
    monkeypatch.setattr(listener, "_fire_agent_voice", lambda *_args, **_kwargs: None)
    workflow_db = tmp_path / "workflow.sqlite3"
    monkeypatch.setenv("OPENCLAW_WORKFLOW_PACKAGE_DB", str(workflow_db))
    staged = workflow_package_queue.stage_live_arts_invoice_handoff(
        "route the Live Arts PA bill to whoever should own it",
        source_surface="chief_router",
        sqlite_path=workflow_db,
    )
    receipt = _contract_receipt(
        action="stage_handoff",
        raw_ref=str(staged["receipt"]["receipt_ref"]),
        persisted=False,
    )
    monkeypatch.setattr(
        listener,
        "route_message",
        lambda _text: {
            "intent": "live_arts_invoice_handoff",
            "reply": "Chief staged the bounded handoff. Say “show receipt” for the delivery record.",
            "contract_decision": receipt,
        },
    )
    message = _Message("route it", message_id=444, delivered_message_id=9003)

    asyncio.run(listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert _row(db_path) == (
        "workflow",
        receipt["receipt_pointer"],
        "chief_listener",
        "chief",
        "456",
        "444",
        "9003",
    )
    assert not log_path.exists()
    assert intake_ids == ["777777"]
    assert message.replies == [
        "Chief staged the bounded handoff. Say “show receipt” for the delivery record."
    ]


def test_chief_registers_real_router_bound_typed_receipt_on_listener_delivery(
    monkeypatch,
    tmp_path: Path,
) -> None:
    listener = _load_listener(monkeypatch, "chief_listener")
    db_path = tmp_path / "fleet.sqlite3"
    monkeypatch.setenv("OPENCLAW_FLEET_RECEIPT_INDEX_DB", str(db_path))
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        listener,
        "record_telegram_listener_update_safe",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(listener, "_fire_agent_voice", lambda *_args, **_kwargs: None)
    receipt = _durable_typed_receipt(
        monkeypatch,
        tmp_path,
        agent="chief",
        surface="chief_router",
        text="maybe that other thing",
    )
    monkeypatch.setattr(
        listener,
        "route_message",
        lambda _text: {
            "intent": "typed_contract_session_preserved",
            "reply": "Chief preserved this session. Say “show receipt” for the decision record.",
            "contract_decision": receipt,
        },
    )
    message = _Message("hold this", message_id=444, delivered_message_id=9004)

    asyncio.run(listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert _row(db_path) == (
        "typed_contract",
        receipt["receipt_pointer"],
        "chief_listener",
        "chief",
        "456",
        "444",
        "9004",
    )
    assert str(receipt["receipt_pointer"]) not in message.replies[0]
    assert message.replies[0].lower().count("show receipt") == 1


def test_niles_non_durable_pointer_is_ignored_even_after_successful_delivery(
    monkeypatch,
    tmp_path: Path,
) -> None:
    listener = _load_listener(monkeypatch, "producer_listener")
    db_path = tmp_path / "fleet.sqlite3"
    monkeypatch.setenv("OPENCLAW_FLEET_RECEIPT_INDEX_DB", str(db_path))
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(listener, "record_telegram_listener_update_safe", lambda **_kwargs: None)
    monkeypatch.setattr(listener, "_fire_agent_voice", lambda *_args, **_kwargs: None)
    import typed_contract_decision

    receipt = _contract_receipt(action="preserve_session", raw_ref="contract:not-durable", persisted=False)
    monkeypatch.setattr(
        typed_contract_decision,
        "decide_contract",
        lambda *_args, **_kwargs: SimpleNamespace(
            handled=True,
            reply="No durable receipt was created.",
            receipt=SimpleNamespace(to_dict=lambda: receipt),
        ),
    )
    message = _Message("hold this", message_id=444, delivered_message_id=9004)

    asyncio.run(listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert _row(db_path) is None


def test_niles_durable_receipt_without_returned_outbound_id_creates_no_row(
    monkeypatch,
    tmp_path: Path,
) -> None:
    listener = _load_listener(monkeypatch, "producer_listener")
    db_path = tmp_path / "fleet.sqlite3"
    monkeypatch.setenv("OPENCLAW_FLEET_RECEIPT_INDEX_DB", str(db_path))
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(listener, "record_telegram_listener_update_safe", lambda **_kwargs: None)
    monkeypatch.setattr(listener, "_fire_agent_voice", lambda *_args, **_kwargs: None)
    import typed_contract_decision

    receipt = _durable_typed_receipt(
        monkeypatch,
        tmp_path,
        agent="niles",
        surface="niles_producer_listener",
        text="maybe that other thing",
    )
    monkeypatch.setattr(
        typed_contract_decision,
        "decide_contract",
        lambda *_args, **_kwargs: SimpleNamespace(
            handled=True,
            reply="The session was preserved. Say “show receipt” for the delivery record.",
            receipt=SimpleNamespace(to_dict=lambda: receipt),
        ),
    )
    message = _Message("hold this", message_id=444, delivered_message_id=None)

    asyncio.run(listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert message.send_attempts == 1
    assert _row(db_path) is None


def test_niles_failed_send_never_reaches_receipt_registration(monkeypatch, tmp_path: Path) -> None:
    listener = _load_listener(monkeypatch, "producer_listener")
    db_path = tmp_path / "fleet.sqlite3"
    monkeypatch.setenv("OPENCLAW_FLEET_RECEIPT_INDEX_DB", str(db_path))
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(listener, "record_telegram_listener_update_safe", lambda **_kwargs: None)
    import typed_contract_decision

    receipt = _durable_typed_receipt(
        monkeypatch,
        tmp_path,
        agent="niles",
        surface="niles_producer_listener",
        text="maybe that other thing",
    )
    monkeypatch.setattr(
        typed_contract_decision,
        "decide_contract",
        lambda *_args, **_kwargs: SimpleNamespace(
            handled=True,
            reply="The session was preserved. Say “show receipt” for the delivery record.",
            receipt=SimpleNamespace(to_dict=lambda: receipt),
        ),
    )
    message = _Message("hold this", message_id=444, fail_send=True)

    with pytest.raises(RuntimeError, match="telegram send failed"):
        asyncio.run(listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert message.send_attempts == 1
    assert _row(db_path) is None


def test_chief_post_send_index_failure_is_fail_soft_without_duplicate_reply(
    monkeypatch,
    tmp_path: Path,
) -> None:
    listener = _load_listener(monkeypatch, "chief_listener")
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(listener, "record_telegram_listener_update_safe", lambda **_kwargs: None)
    monkeypatch.setattr(listener, "_fire_agent_voice", lambda *_args, **_kwargs: None)
    receipt = _durable_typed_receipt(
        monkeypatch,
        tmp_path,
        agent="chief",
        surface="chief_router",
        text="maybe that other thing",
    )
    monkeypatch.setattr(
        listener,
        "route_message",
        lambda _text: {
            "intent": "typed_contract_session_preserved",
            "reply": "Chief preserved this session. Say “show receipt” for the delivery record.",
            "contract_decision": receipt,
        },
    )
    monkeypatch.setattr(
        listener,
        "register_telegram_delivery",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("index unavailable")),
    )
    message = _Message("hold this", message_id=444, delivered_message_id=9005)

    asyncio.run(listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert message.send_attempts == 1
    assert message.replies == [
        "Chief preserved this session. Say “show receipt” for the delivery record."
    ]
