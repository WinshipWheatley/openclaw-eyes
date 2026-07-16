from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

import fleet_receipt_index as receipt_index
import maestro_listener
import typed_contract_decision as typed
import workflow_package_queue as workflow


class _Bot:
    async def send_chat_action(self, **_kwargs) -> None:
        return None


class _Message:
    def __init__(
        self,
        text: str,
        *,
        message_id: int,
        delivered_message_id: int = 9001,
        reply_to_message_id: int | None = None,
        fail_first_send: bool = False,
    ) -> None:
        self.text = text
        self.message_id = message_id
        self.reply_to_message = (
            SimpleNamespace(message_id=reply_to_message_id)
            if reply_to_message_id is not None
            else None
        )
        self.delivered_message_id = delivered_message_id
        self.fail_first_send = fail_first_send
        self.replies: list[str] = []
        self.send_attempts = 0

    async def reply_text(self, text: str):
        self.send_attempts += 1
        if self.fail_first_send and self.send_attempts == 1:
            raise RuntimeError("telegram send failed")
        self.replies.append(text)
        return SimpleNamespace(message_id=self.delivered_message_id)


def _update(message: _Message):
    return SimpleNamespace(
        update_id=777777,
        effective_user=SimpleNamespace(id=123),
        effective_chat=SimpleNamespace(id=123),
        message=message,
    )


def _patch_listener(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENCLAW_FLEET_RECEIPT_INDEX_DB", str(tmp_path / "fleet.sqlite3"))
    monkeypatch.setenv("OPENCLAW_FAST_ACK", "0")
    monkeypatch.setenv("OPENCLAW_AGENT_VOICE_NOTES", "0")
    monkeypatch.setattr(maestro_listener, "authorized_user_id", lambda: 123)
    monkeypatch.setattr(maestro_listener, "claim_listener_update", lambda *args, **kwargs: True)
    monkeypatch.setattr(maestro_listener, "_fire_maestro_voice", lambda *_args, **_kwargs: None)


def _response(*, action: str, raw_ref: str, receipt_persisted: bool) -> dict:
    return {
        "terminal": True,
        "internal_status": "RESPONSE_READY",
        "source_request_id": "maestro_telegram_456_test",
        "operator_message": (
            f"Human-safe delivery answer. Machine pointer {raw_ref}. "
            "Say “show receipt” for the delivery record."
        ),
        "detail_disclosure": {
            "maestro_cassandra_responder": {
                "machine_proof": {
                    "typed_contract_decision": {
                        "action": action,
                        "receipt_pointer": raw_ref,
                        "receipt_persisted": receipt_persisted,
                        "session_preserved": action == "preserve_session",
                    }
                }
            }
        },
    }


def _durable_provider_receipt(monkeypatch, tmp_path: Path, *, action: str) -> tuple[str, bool]:
    if action == "stage_handoff":
        workflow_db = tmp_path / "workflow.sqlite3"
        monkeypatch.setenv("OPENCLAW_WORKFLOW_PACKAGE_DB", str(workflow_db))
        staged = workflow.stage_live_arts_invoice_handoff(
            "route the Live Arts PA bill to whoever should own it",
            sqlite_path=workflow_db,
        )
        return str(staged["receipt"]["receipt_ref"]), False
    monkeypatch.setenv(typed.CONTRACT_RECEIPT_DB_ENV, str(tmp_path / "typed.sqlite3"))
    decision = typed.decide_contract(
        "maybe that other thing",
        context=typed.ContractContext(
            agent="maestro",
            surface="operator_maestro_chat",
            active_session=True,
            session_kind="invoice_review",
        ),
        semantic_vote_enabled=False,
    )
    assert decision.receipt.receipt_persisted is True
    return decision.receipt.receipt_pointer, True


def _row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with sqlite3.connect(path) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM fleet_receipt_deliveries").fetchone()[0])


def test_show_receipt_short_circuits_before_governed_intake_or_bridge(monkeypatch, tmp_path: Path) -> None:
    _patch_listener(monkeypatch, tmp_path)
    db_path = tmp_path / "fleet.sqlite3"
    descriptor = receipt_index.build_receipt_descriptor(
        provider="workflow",
        raw_ref="operator_review_receipt:machine-only-ref",
        what_happened="A bounded workflow handoff was staged for Cassandra.",
        status="Staged for review; unclaimed and unexecuted.",
        occurred_at="2026-07-11T12:00:00+00:00",
        authority_summary="Queue record only; operator review is still required.",
        no_action_facts=("Nothing was sent, posted to the ledger, or changed.",),
    )
    receipt_index.register_delivered_receipt(
        descriptor,
        surface="operator_maestro_chat",
        bot_identity="maestro",
        chat_id="123",
        source_message_id="444",
        delivered_message_id="9001",
        delivery_succeeded=True,
        db_path=db_path,
    )

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("governed intake/bridge must not run for receipt retrieval")

    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", _forbidden)
    monkeypatch.setattr(maestro_listener, "build_operator_maestro_chat_request", _forbidden)
    monkeypatch.setattr(maestro_listener, "write_bridge_request", _forbidden)
    message = _Message("show receipt", message_id=445, reply_to_message_id=9001)

    asyncio.run(maestro_listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert len(message.replies) == 1
    assert message.replies[0].startswith("Receipt R-")
    assert "operator_review_receipt:machine-only-ref" not in message.replies[0]


def test_receipt_lookup_error_fails_closed_before_bridge(monkeypatch, tmp_path: Path) -> None:
    _patch_listener(monkeypatch, tmp_path)

    def _failed_lookup(*_args, **_kwargs):
        raise RuntimeError("index unavailable")

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("receipt lookup failure must not enter intake or bridge")

    monkeypatch.setattr(maestro_listener, "resolve_receipt_request", _failed_lookup)
    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", _forbidden)
    monkeypatch.setattr(maestro_listener, "write_bridge_request", _forbidden)
    message = _Message("show receipt", message_id=446)

    asyncio.run(maestro_listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert message.replies == [
        "I couldn't read the delivered-receipt index right now. No action ran."
    ]


@pytest.mark.parametrize(
    ("action", "provider"),
    (
        ("stage_handoff", "workflow"),
        ("preserve_session", "typed_contract"),
    ),
)
def test_successful_final_delivery_registers_typed_descriptor_with_actual_message_ids(
    monkeypatch,
    tmp_path: Path,
    action: str,
    provider: str,
) -> None:
    _patch_listener(monkeypatch, tmp_path)
    raw_ref, receipt_persisted = _durable_provider_receipt(
        monkeypatch,
        tmp_path,
        action=action,
    )
    response = _response(
        action=action,
        raw_ref=raw_ref,
        receipt_persisted=receipt_persisted,
    )
    intake_ids: list[str | None] = []
    monkeypatch.setattr(
        maestro_listener,
        "record_maestro_intake_metadata",
        lambda **kwargs: intake_ids.append(kwargs["source_message_id"]),
    )
    monkeypatch.setattr(
        maestro_listener,
        "build_operator_maestro_chat_request",
        lambda *_args, **_kwargs: {"request_id": "request-1"},
    )
    monkeypatch.setattr(maestro_listener, "write_bridge_request", lambda *_args, **_kwargs: None)

    async def _poll(_request_id):
        return response

    monkeypatch.setattr(maestro_listener, "poll_bridge_response", _poll)
    message = _Message("route this", message_id=444, delivered_message_id=9001)

    asyncio.run(maestro_listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert intake_ids == ["777777"]
    assert len(message.replies) == 1
    assert raw_ref not in message.replies[0]
    db_path = tmp_path / "fleet.sqlite3"
    assert _row_count(db_path) == 1
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT provider, raw_ref, source_message_id, delivered_message_id "
            "FROM fleet_receipt_deliveries"
        ).fetchone()
    assert row == (provider, raw_ref, "444", "9001")


def test_failed_final_send_creates_no_receipt_row_and_fallback_is_not_registered(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_listener(monkeypatch, tmp_path)
    raw_ref, receipt_persisted = _durable_provider_receipt(
        monkeypatch,
        tmp_path,
        action="stage_handoff",
    )
    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", lambda **_kwargs: None)
    monkeypatch.setattr(
        maestro_listener,
        "build_operator_maestro_chat_request",
        lambda *_args, **_kwargs: {"request_id": "request-1"},
    )
    monkeypatch.setattr(maestro_listener, "write_bridge_request", lambda *_args, **_kwargs: None)

    async def _poll(_request_id):
        return _response(
            action="stage_handoff",
            raw_ref=raw_ref,
            receipt_persisted=receipt_persisted,
        )

    monkeypatch.setattr(maestro_listener, "poll_bridge_response", _poll)
    message = _Message(
        "route this",
        message_id=444,
        delivered_message_id=9002,
        fail_first_send=True,
    )

    asyncio.run(maestro_listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert message.send_attempts == 2
    assert len(message.replies) == 1
    assert _row_count(tmp_path / "fleet.sqlite3") == 0


def test_receipt_index_failure_after_delivery_is_fail_soft_without_duplicate_reply(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_listener(monkeypatch, tmp_path)
    raw_ref, receipt_persisted = _durable_provider_receipt(
        monkeypatch,
        tmp_path,
        action="preserve_session",
    )
    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", lambda **_kwargs: None)
    monkeypatch.setattr(
        maestro_listener,
        "build_operator_maestro_chat_request",
        lambda *_args, **_kwargs: {"request_id": "request-1"},
    )
    monkeypatch.setattr(maestro_listener, "write_bridge_request", lambda *_args, **_kwargs: None)

    async def _poll(_request_id):
        return _response(
            action="preserve_session",
            raw_ref=raw_ref,
            receipt_persisted=receipt_persisted,
        )

    monkeypatch.setattr(maestro_listener, "poll_bridge_response", _poll)
    monkeypatch.setattr(
        maestro_listener,
        "register_delivered_receipt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("index unavailable")),
    )
    message = _Message("hold this thread", message_id=444, delivered_message_id=9003)

    asyncio.run(maestro_listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert message.send_attempts == 1
    assert len(message.replies) == 1
    assert raw_ref not in message.replies[0]
    assert _row_count(tmp_path / "fleet.sqlite3") == 0


def test_non_persisted_typed_pointer_is_hidden_but_not_registered(monkeypatch, tmp_path: Path) -> None:
    _patch_listener(monkeypatch, tmp_path)
    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", lambda **_kwargs: None)
    monkeypatch.setattr(
        maestro_listener,
        "build_operator_maestro_chat_request",
        lambda *_args, **_kwargs: {"request_id": "request-1"},
    )
    monkeypatch.setattr(maestro_listener, "write_bridge_request", lambda *_args, **_kwargs: None)

    async def _poll(_request_id):
        return _response(
            action="preserve_session",
            raw_ref="contract:not-durable",
            receipt_persisted=False,
        )

    monkeypatch.setattr(maestro_listener, "poll_bridge_response", _poll)
    message = _Message("hold this thread", message_id=444, delivered_message_id=9004)

    asyncio.run(maestro_listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert message.send_attempts == 1
    assert "contract:not-durable" not in message.replies[0]
    assert "show receipt" not in message.replies[0].lower()
    assert _row_count(tmp_path / "fleet.sqlite3") == 0


def test_legacy_receipt_label_is_removed_instead_of_rewritten_as_a_fake_human_receipt() -> None:
    raw_ref = "operator_review_receipt:machine-only"
    rendered = maestro_listener._without_raw_receipt_ref(
        f"The handoff was staged.\nReceipt: {raw_ref}",
        raw_ref,
        advertise=False,
    )

    assert raw_ref not in rendered
    assert "Receipt:" not in rendered
    assert "show receipt" not in rendered.lower()


def test_successful_send_without_returned_outbound_message_id_is_not_registered(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_listener(monkeypatch, tmp_path)
    raw_ref, receipt_persisted = _durable_provider_receipt(
        monkeypatch,
        tmp_path,
        action="stage_handoff",
    )
    monkeypatch.setattr(maestro_listener, "record_maestro_intake_metadata", lambda **_kwargs: None)
    monkeypatch.setattr(
        maestro_listener,
        "build_operator_maestro_chat_request",
        lambda *_args, **_kwargs: {"request_id": "request-1"},
    )
    monkeypatch.setattr(maestro_listener, "write_bridge_request", lambda *_args, **_kwargs: None)

    async def _poll(_request_id):
        return _response(
            action="stage_handoff",
            raw_ref=raw_ref,
            receipt_persisted=receipt_persisted,
        )

    monkeypatch.setattr(maestro_listener, "poll_bridge_response", _poll)
    message = _Message("route this", message_id=444, delivered_message_id=None)  # type: ignore[arg-type]

    asyncio.run(maestro_listener.handle_message(_update(message), SimpleNamespace(bot=_Bot())))

    assert message.send_attempts == 1
    assert _row_count(tmp_path / "fleet.sqlite3") == 0
