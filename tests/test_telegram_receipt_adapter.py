from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import telegram_receipt_adapter as adapter
import typed_contract_decision as typed
import workflow_package_queue as workflow


def _preserve_receipt(
    monkeypatch,
    tmp_path,
    *,
    agent: str = "chief",
    surface: str = "chief_router",
    text: str = "maybe that other thing",
) -> dict[str, object]:
    monkeypatch.setenv(typed.CONTRACT_RECEIPT_DB_ENV, str(tmp_path / "typed.sqlite3"))
    decision = typed.decide_contract(
        text,
        context=typed.ContractContext(
            agent=agent,
            surface=surface,
            active_session=True,
            session_kind="billing",
        ),
        semantic_vote_enabled=False,
    )
    assert decision.receipt.receipt_persisted is True
    return decision.receipt.to_dict()


def test_direct_and_legacy_wrapped_contract_receipts_map_to_the_right_providers(
    monkeypatch,
    tmp_path,
):
    typed_receipt = _preserve_receipt(monkeypatch, tmp_path)
    typed_descriptor = adapter.contract_delivery_descriptor(
        typed_receipt,
        actor="chief",
        surface="chief_listener",
        provider_surface="chief_router",
    )
    workflow_db = tmp_path / "workflow.sqlite3"
    staged = workflow.stage_live_arts_invoice_handoff(
        "route the Live Arts PA bill to whoever should own it",
        sqlite_path=workflow_db,
    )
    workflow_descriptor = adapter.contract_delivery_descriptor(
        {
            "receipt": {
                "action": "stage_handoff",
                "receipt_pointer": staged["receipt"]["receipt_ref"],
            }
        },
        actor="maestro",
        surface="operator_maestro_chat",
        workflow_db_path=workflow_db,
    )

    assert typed_descriptor is not None
    assert typed_descriptor.provider == "typed_contract"
    assert typed_descriptor.raw_ref == typed_receipt["receipt_pointer"]
    assert workflow_descriptor is not None
    assert workflow_descriptor.provider == "workflow"
    assert workflow_descriptor.raw_ref == staged["receipt"]["receipt_ref"]
    assert adapter.contract_delivery_descriptor(
        {
            "action": "stage_handoff",
            "receipt_pointer": staged["receipt"]["receipt_ref"],
        },
        actor="cassandra",
        surface="cassandra_telegram",
        workflow_db_path=workflow_db,
    ) is None
    assert adapter.contract_delivery_descriptor(
        {
            "action": "stage_handoff",
            "receipt_pointer": staged["receipt"]["receipt_ref"],
        },
        actor="niles",
        surface="niles_producer_listener",
        provider_surface="operator_maestro_chat",
        workflow_db_path=workflow_db,
    ) is None


def test_nondurable_or_nonretrievable_contract_outcomes_are_not_described(tmp_path):
    nondurable = {
        "action": "preserve_session",
        "receipt_pointer": "contract:1234-5678-9abc-def0-1234",
        "receipt_persisted": False,
    }

    assert adapter.contract_delivery_descriptor(
        nondurable,
        actor="niles",
        surface="niles_producer_listener",
    ) is None
    assert adapter.contract_delivery_descriptor(
        {"action": "direct_answer", "receipt_pointer": "contract:not-durable"},
        actor="niles",
        surface="niles_producer_listener",
    ) is None
    assert adapter.contract_delivery_descriptor(
        {},
        actor="niles",
        surface="niles_producer_listener",
    ) is None
    assert adapter.contract_delivery_descriptor(
        {
            "action": "stage_handoff",
            "receipt_pointer": "operator_review_receipt:fabricated",
        },
        actor="chief",
        surface="chief_listener",
        workflow_db_path=tmp_path / "missing-workflow.sqlite3",
    ) is None
    assert adapter.contract_delivery_descriptor(
        nondurable | {"receipt_persisted": True},
        actor="chief",
        surface="chief_listener",
        provider_surface="chief_router",
        contract_db_path=tmp_path / "missing-typed.sqlite3",
    ) is None


def test_typed_receipt_binding_rejects_cross_wired_actor_or_surface(monkeypatch, tmp_path):
    receipt = _preserve_receipt(monkeypatch, tmp_path)

    assert adapter.contract_delivery_descriptor(
        receipt,
        actor="chief",
        surface="chief_listener",
        provider_surface="chief_router",
    ) is not None
    assert adapter.contract_delivery_descriptor(
        receipt,
        actor="niles",
        surface="chief_listener",
    ) is None


def test_delivery_surface_can_differ_from_a_verified_provider_surface(monkeypatch, tmp_path):
    receipt = _preserve_receipt(
        monkeypatch,
        tmp_path,
        agent="chief",
        surface="chief_router",
    )

    assert adapter.contract_delivery_descriptor(
        receipt,
        actor="chief",
        surface="chief_listener",
        provider_surface="chief_router",
    ) is not None
    assert adapter.contract_delivery_descriptor(
        receipt,
        actor="chief",
        surface="chief_listener",
    ) is None
    assert adapter.contract_delivery_descriptor(
        receipt,
        actor="chief",
        surface="chief_listener",
        provider_surface="cassandra_telegram",
    ) is None
    assert adapter.contract_delivery_descriptor(
        receipt,
        actor="chief",
        surface="niles_producer_listener",
    ) is None


def test_workflow_receipt_must_still_be_unclaimed_and_without_authority(tmp_path):
    workflow_db = tmp_path / "workflow.sqlite3"
    staged = workflow.stage_live_arts_invoice_handoff(
        "route the Live Arts PA bill to whoever should own it",
        sqlite_path=workflow_db,
    )
    raw_ref = str(staged["receipt"]["receipt_ref"])
    package_id = str(staged["receipt"]["package_id"])

    with sqlite3.connect(workflow_db) as connection:
        connection.execute(
            "UPDATE worker_assignments SET assigned=1 WHERE package_id=?",
            (package_id,),
        )

    assert adapter.contract_delivery_descriptor(
        {
            "action": "stage_handoff",
            "receipt_pointer": raw_ref,
        },
        actor="maestro",
        surface="operator_maestro_chat",
        workflow_db_path=workflow_db,
    ) is None


def test_registration_uses_actual_inbound_and_outbound_message_ids(tmp_path, monkeypatch):
    db_path = tmp_path / "fleet.sqlite3"
    descriptor = adapter.contract_delivery_descriptor(
        _preserve_receipt(
            monkeypatch,
            tmp_path,
            agent="guardian",
            surface="guardian_listener",
        ),
        actor="guardian",
        surface="guardian_listener",
    )
    assert descriptor is not None

    result = adapter.register_telegram_delivery(
        descriptor,
        surface="guardian_listener",
        bot_identity="guardian",
        chat_id="chat-7",
        source_message_id="actual-in-11",
        delivered_message=SimpleNamespace(message_id="actual-out-22"),
        db_path=db_path,
    )

    assert result is not None and result.registered is True
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT source_message_id, delivered_message_id FROM fleet_receipt_deliveries"
        ).fetchone()
    assert row == ("actual-in-11", "actual-out-22")


def test_missing_delivery_confirmation_creates_no_index(tmp_path, monkeypatch):
    db_path = tmp_path / "fleet.sqlite3"
    descriptor = adapter.contract_delivery_descriptor(
        _preserve_receipt(
            monkeypatch,
            tmp_path,
            agent="cassandra",
            surface="cassandra_telegram",
        ),
        actor="cassandra",
        surface="cassandra_telegram",
    )
    assert descriptor is not None

    result = adapter.register_telegram_delivery(
        descriptor,
        surface="cassandra_telegram",
        bot_identity="cassandra",
        chat_id="chat-7",
        source_message_id="actual-in-11",
        delivered_message=None,
        db_path=db_path,
    )

    assert result is None
    assert not db_path.exists()


def test_reply_binding_is_taken_from_the_message_being_replied_to():
    message = SimpleNamespace(reply_to_message=SimpleNamespace(message_id=9001))
    assert adapter.reply_to_message_id(message) == "9001"
    assert adapter.reply_to_message_id(SimpleNamespace()) == ""
