from __future__ import annotations

import asyncio
import copy
import hashlib

import pytest

import invoice_cockpit_session as cockpit
import invoice_send_workflow as workflow


CT3 = "prep the St Anne's July invoice so I can look it over"
CT4 = "would you mind getting the July St Anne's invoice set up for my review?"


class MemoryStore:
    def __init__(self) -> None:
        self.state = None

    def load(self):
        return self.state

    def save(self, state) -> None:
        self.state = state

    def clear(self) -> None:
        self.state = None


class CountingOps:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def prepare_existing_finalized_invoice(self, client, *, requested_period=None):
        self.calls.append(("prepare_existing", client["client_ref"], requested_period))
        return (
            {
                "client_ref": client["client_ref"],
                "client_name": client["display_name"],
                "client_email": "operator@example.invalid",
                "invoice_number": "WL-2026-0009",
                "invoice_status": "issued",
            },
            "/tmp/WL-2026-0009__St_Annes.pdf",
            "finalized-sha256",
        )

    def telegram_pdf(self, path, caption):
        self.calls.append(("preview", path, caption))
        return {"ok": True, "document_path": path, "caption": caption}

    def prepare_invoice(self, *_args, **_kwargs):
        raise AssertionError("generator path ran")

    def clara_draft_and_guardian(self, *_args, **_kwargs):
        raise AssertionError("draft/Guardian path ran")

    def send_email(self, *_args, **_kwargs):
        raise AssertionError("send path ran")


@pytest.mark.parametrize(
    "text",
    (
        CT3,
        CT4,
        "can you line up the st annes july invoice for me to glance at?",
        "have that july st annes bill teed up for my once-over",
    ),
)
def test_dependency_light_owner_covers_the_frozen_artifact_review_family(text: str) -> None:
    from invoice_cockpit_intent import classify_finalized_invoice_review

    decision = classify_finalized_invoice_review(text)

    assert decision.matched is True
    assert decision.client_ref == "st_annes"
    assert decision.requested_period == "2026-07"
    assert decision.client_model is not None
    assert decision.client_model["client_ref"] == "st_annes"


@pytest.mark.parametrize(
    "text",
    (
        "send the St Anne's July invoice now",
        "review my rates and clients",
        "what did St Anne's owe on the July invoice?",
        "set up the stage for my review",
    ),
)
def test_artifact_review_owner_does_not_claim_actions_or_other_domains(text: str) -> None:
    from invoice_cockpit_intent import classify_finalized_invoice_review

    assert classify_finalized_invoice_review(text).matched is False


def test_ct3_then_ct4_resurfaces_one_artifact_without_restarting_the_workflow(
    monkeypatch,
) -> None:
    store = MemoryStore()
    ops = CountingOps()
    real_start = workflow.start_invoice_send
    starts = 0

    def counted_start(*args, **kwargs):
        nonlocal starts
        starts += 1
        return real_start(*args, **kwargs)

    monkeypatch.setattr(workflow, "start_invoice_send", counted_start)
    monkeypatch.setattr(
        cockpit,
        "_interpreter_invoice_trigger",
        lambda _text: (_ for _ in ()).throw(AssertionError("interpreter/model path ran")),
    )

    first = cockpit.handle_invoice_cockpit_message(
        CT3,
        ops=ops,
        store=store,
        surface="cassandra_telegram",
    )
    first_state = copy.deepcopy(store.state)
    second = cockpit.handle_invoice_cockpit_message(
        CT4,
        ops=ops,
        store=store,
        surface="cassandra_telegram",
    )

    assert starts == 1
    assert [call[0] for call in ops.calls].count("prepare_existing") == 2
    assert [call[0] for call in ops.calls].count("preview") == 2
    assert first["attachment"] == second["attachment"] == first_state["pdf_path"]
    assert (
        first["attachment_sha256"]
        == second["attachment_sha256"]
        == first_state["attachment_sha256"]
    )
    assert first["invoice_data"]["invoice_number"] == "WL-2026-0009"
    assert second["invoice_data"]["invoice_number"] == "WL-2026-0009"
    assert second["artifact_reused"] is True
    assert second["artifact_resurfaced"] is False
    assert second["artifact_resurface_staged"] is True
    assert second["delivery_confirmed"] is False
    assert store.state["stage"] == workflow.AWAITING_INVOICE_APPROVAL
    assert store.state["invoice_data"] == first_state["invoice_data"]
    assert store.state["pdf_path"] == first_state["pdf_path"]
    assert store.state["attachment_sha256"] == first_state["attachment_sha256"]


def test_listener_preserves_ct3_when_ct4_arrives_on_another_surface(monkeypatch) -> None:
    monkeypatch.setenv("CASSANDRA_BOT_TOKEN", "task-166-test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "42")
    import cassandra_listener as listener

    store = MemoryStore()
    ops = CountingOps()
    cockpit.handle_invoice_cockpit_message(
        CT3,
        ops=ops,
        store=store,
        surface="cassandra_telegram",
    )
    before = copy.deepcopy(store.state)
    calls_before = tuple(ops.calls)

    result = listener._try_invoice_cockpit(
        CT4,
        {
            "surface": "operator_maestro_chat",
            "bot_identity": "cassandra",
            "sender_chat_id": "42",
            "source_message_id": "ct4-foreign",
            "source_user_label": "operator",
        },
        ops=ops,
        store=store,
    )

    assert result is None
    assert store.state == before
    assert tuple(ops.calls) == calls_before


def test_custom_client_resolver_identity_is_reused_without_restart(monkeypatch) -> None:
    store = MemoryStore()
    ops = CountingOps()
    starts = 0
    real_start = workflow.start_invoice_send

    def counted_start(*args, **kwargs):
        nonlocal starts
        starts += 1
        return real_start(*args, **kwargs)

    def resolver(_requested: str):
        return {
            "client_ref": "st_annes_custom",
            "display_name": "St Anne's",
            "aliases": ("St Anne's",),
        }

    monkeypatch.setattr(workflow, "start_invoice_send", counted_start)
    cockpit.handle_invoice_cockpit_message(
        CT3,
        ops=ops,
        store=store,
        client_resolver=resolver,
        surface="cassandra_telegram",
    )
    result = cockpit.handle_invoice_cockpit_message(
        CT4,
        ops=ops,
        store=store,
        client_resolver=resolver,
        surface="cassandra_telegram",
    )

    assert starts == 1
    assert store.state["client_ref"] == "st_annes_custom"
    assert result["artifact_resurface_staged"] is True


def test_owner_binds_client_and_period_to_the_review_clause() -> None:
    from invoice_cockpit_intent import classify_finalized_invoice_review

    decision = classify_finalized_invoice_review(
        "compare Capital Hilton payment, then get the St Anne's July invoice "
        "ready for my review",
        reference_year=2026,
    )

    assert decision.matched is True
    assert decision.client_ref == "st_annes"
    assert decision.requested_period == "2026-07"


def test_unknown_client_parser_does_not_invent_review_as_the_client() -> None:
    from invoice_cockpit_intent import classify_finalized_invoice_review

    decision = classify_finalized_invoice_review(
        "set up the Acme invoice for review",
        reference_year=2026,
    )

    assert decision.matched is True
    assert decision.client_ref == "acme"
    assert decision.client_model is not None
    assert decision.client_model["display_name"] == "Acme"


def test_owner_accepts_an_injected_reference_year_for_rollover_stability() -> None:
    from invoice_cockpit_intent import classify_finalized_invoice_review

    text = "get the St Anne's July invoice ready for my review"

    assert classify_finalized_invoice_review(
        text, reference_year=2026
    ).requested_period == "2026-07"
    assert classify_finalized_invoice_review(
        text, reference_year=2027
    ).requested_period == "2027-07"


def test_document_dispatch_rechecks_bound_sha256_before_transport(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CASSANDRA_BOT_TOKEN", "task-166-test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "42")
    import cassandra_listener as listener
    from origin_bound_output import (
        OPERATOR_AUDIENCE,
        OriginBoundOutput,
        OriginDeliveryTracker,
        OutputOrigin,
    )

    document = tmp_path / "invoice.pdf"
    document.write_bytes(b"original invoice bytes")
    expected = hashlib.sha256(document.read_bytes()).hexdigest()
    origin = OutputOrigin(
        surface="cassandra_telegram",
        bot_identity="cassandra",
        chat_id="42",
        source_message_id="ct4",
        audience=OPERATOR_AUDIENCE,
    )
    output = OriginBoundOutput.guarded_document(
        origin=origin,
        delivery_id="delivery-ct4",
        receipt_pointer="invoice-artifact-test",
        document_path=str(document),
        caption="Finalized invoice is ready for review.",
        internal={"document_sha256": expected},
    )
    document.write_bytes(b"changed after revalidation")
    fallback: list[str] = []

    async def send_text(text: str, reply_markup=None):
        fallback.append(text)
        return type("Message", (), {"message_id": 901})()

    async def send_document(_path: str, _caption: str):
        raise AssertionError("drifted document reached transport")

    monkeypatch.setattr(
        listener,
        "register_delivered_receipt",
        lambda *_args, **_kwargs: pytest.fail("drifted document was receipted"),
    )

    delivered = asyncio.run(
        listener._dispatch_origin_bound_output(
            output,
            bound_origin=origin,
            send_text=send_text,
            send_document=send_document,
            tracker=OriginDeliveryTracker(),
            source_message_id="ct4",
            receipt_db_path=tmp_path / "fleet.sqlite3",
        )
    )

    assert delivered is True
    assert fallback == [
        "I couldn't attach the prepared invoice because its contents changed. "
        "Nothing was sent."
    ]


def test_same_artifact_uses_one_provider_ref_across_distinct_deliveries(tmp_path) -> None:
    from invoice_cockpit_ops import RealCockpitOps
    from origin_bound_output import OPERATOR_AUDIENCE, OutputOrigin

    document = tmp_path / "invoice.pdf"
    document.write_bytes(b"one immutable finalized invoice")
    digest = hashlib.sha256(document.read_bytes()).hexdigest()

    def output_for(source_message_id: str):
        ops = RealCockpitOps(
            origin=OutputOrigin(
                surface="cassandra_telegram",
                bot_identity="cassandra",
                chat_id="42",
                source_message_id=source_message_id,
                audience=OPERATOR_AUDIENCE,
            ),
            source_request=CT4,
        )
        return ops.telegram_pdf_verified(
            str(document),
            "Finalized invoice is ready for review.",
            digest,
        )["origin_output"]

    first = output_for("ct3")
    second = output_for("ct4")

    assert first.receipt_pointer == second.receipt_pointer
    assert first.delivery_id != second.delivery_id
    assert first.internal["document_sha256"] == digest
    assert second.internal["document_sha256"] == digest


def test_ct4_refuses_to_resurface_when_the_held_artifact_identity_drifted(
    monkeypatch,
) -> None:
    store = MemoryStore()
    ops = CountingOps()
    real_prepare = ops.prepare_existing_finalized_invoice
    real_start = workflow.start_invoice_send
    starts = 0

    def counted_start(*args, **kwargs):
        nonlocal starts
        starts += 1
        return real_start(*args, **kwargs)

    monkeypatch.setattr(workflow, "start_invoice_send", counted_start)
    cockpit.handle_invoice_cockpit_message(
        CT3,
        ops=ops,
        store=store,
        surface="cassandra_telegram",
    )
    before = copy.deepcopy(store.state)

    def changed_artifact(*args, **kwargs):
        invoice_data, path, _digest = real_prepare(*args, **kwargs)
        return invoice_data, path, "changed-sha256"

    monkeypatch.setattr(ops, "prepare_existing_finalized_invoice", changed_artifact)
    result = cockpit.handle_invoice_cockpit_message(
        CT4,
        ops=ops,
        store=store,
        surface="cassandra_telegram",
    )

    assert starts == 1
    assert result["handled"] is True
    assert result["artifact_resurfaced"] is False
    assert "changed or could not be reverified" in result["error"]
    assert store.state == before
    assert [call[0] for call in ops.calls].count("preview") == 1


def test_ct4_on_another_surface_preserves_the_active_ct3_state_byte_for_byte() -> None:
    store = MemoryStore()
    ops = CountingOps()
    cockpit.handle_invoice_cockpit_message(
        CT3,
        ops=ops,
        store=store,
        surface="cassandra_telegram",
    )
    before = copy.deepcopy(store.state)
    calls_before = tuple(ops.calls)

    result = cockpit.handle_invoice_cockpit_message(
        CT4,
        ops=ops,
        store=store,
        surface="maestro",
    )

    assert result["handled"] is False
    assert result["pass_through_reason"] == "surface_mismatch"
    assert store.state == before
    assert tuple(ops.calls) == calls_before


def test_cancel_on_another_surface_cannot_clear_the_active_ct3_state() -> None:
    store = MemoryStore()
    ops = CountingOps()
    cockpit.handle_invoice_cockpit_message(
        CT3,
        ops=ops,
        store=store,
        surface="cassandra_telegram",
    )
    before = copy.deepcopy(store.state)
    calls_before = tuple(ops.calls)

    result = cockpit.handle_invoice_cockpit_message(
        "cancel",
        ops=ops,
        store=store,
        surface="operator_maestro_chat",
    )

    assert result["handled"] is False
    assert result["pass_through_reason"] == "surface_mismatch"
    assert store.state == before
    assert tuple(ops.calls) == calls_before
