from __future__ import annotations

import ast
import io
import sqlite3
import tokenize
from pathlib import Path

import operator_surface_guard
import origin_bound_output
import typed_contract_decision as typed
import workflow_package_queue as queue


LIVE_ARTS = "the Live Arts PA rental invoice needs to go out — get it to the right agent"
LIVE_ARTS_PARAPHRASE = "can you route the Live Arts PA bill to whoever should own it?"


def _queue_row_count(path: Path) -> int:
    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM packages").fetchone()
    return int(row[0])


def test_mt7_mt8_handoff_rendering_survives_surface_guard_without_raw_receipt(tmp_path):
    db_path = tmp_path / "workflow.sqlite"

    for text in (LIVE_ARTS, LIVE_ARTS_PARAPHRASE):
        result = queue.stage_live_arts_invoice_handoff(
            text,
            source_surface="operator_maestro_chat",
            sqlite_path=db_path,
            created_at="2026-07-11T20:00:00+00:00",
        )
        reply = queue.render_live_arts_handoff_reply(result)
        raw_ref = result["receipt"]["receipt_ref"]

        assert "Cassandra" in reply
        assert "Nothing was sent" in reply
        assert "show receipt" in reply.lower()
        assert raw_ref not in reply
        assert "Receipt:" not in reply
        assert operator_surface_guard.guard_operator_reply(reply, agent_role="MAESTRO") == reply

    assert _queue_row_count(db_path) == 2


def test_workflow_renderers_do_not_advertise_a_fabricated_or_missing_receipt():
    fabricated = {
        "receipt": {
            "receipt_ref": "operator_review_receipt:not-in-provider-store",
        }
    }

    for reply in (
        queue.render_live_arts_handoff_reply({}),
        queue.render_live_arts_handoff_reply(fabricated),
        queue.render_cassandra_nudge_handoff_reply({}),
        queue.render_cassandra_nudge_handoff_reply(fabricated),
    ):
        assert "show receipt" not in reply.lower()
        assert "operator_review_receipt:" not in reply
        assert "No retrievable delivery record was created" in reply


def test_typed_preserve_reply_keeps_raw_pointer_machine_only(tmp_path, monkeypatch):
    receipt_db = tmp_path / "typed.sqlite"
    monkeypatch.setenv(typed.CONTRACT_RECEIPT_DB_ENV, str(receipt_db))

    decision = typed.decide_contract(
        "maybe that other thing",
        context=typed.ContractContext(
            agent="maestro",
            surface="operator_maestro_chat",
            active_session=True,
            session_kind="invoice review",
            session_snapshot={"status": "active"},
        ),
        semantic_vote_enabled=False,
    )

    raw_ref = decision.receipt.receipt_pointer
    assert decision.action is typed.DecisionAction.PRESERVE_SESSION
    assert decision.receipt.receipt_persisted is True
    assert raw_ref.startswith("contract:")
    assert raw_ref not in str(decision.reply)
    assert "show receipt" in str(decision.reply).lower()
    assert operator_surface_guard.guard_operator_reply(
        str(decision.reply), agent_role="MAESTRO"
    ) == decision.reply


def test_typed_preserve_does_not_advertise_lookup_when_persistence_fails(monkeypatch):
    monkeypatch.setenv(typed.CONTRACT_RECEIPT_DB_ENV, "/dev/null/typed.sqlite")

    decision = typed.decide_contract(
        "maybe that other thing",
        context=typed.ContractContext(
            agent="maestro",
            surface="operator_maestro_chat",
            active_session=True,
            session_kind="invoice review",
        ),
        semantic_vote_enabled=False,
    )

    assert decision.action is typed.DecisionAction.PRESERVE_SESSION
    assert decision.receipt.receipt_persisted is False
    assert decision.receipt.receipt_pointer not in str(decision.reply)
    assert "show receipt" not in str(decision.reply).lower()


def test_origin_output_visible_text_never_exposes_raw_pointer():
    origin = origin_bound_output.OutputOrigin(
        surface="cassandra_telegram",
        bot_identity="cassandra",
        chat_id="42",
        source_message_id="100",
        audience=origin_bound_output.OPERATOR_AUDIENCE,
    )
    raw_ref = "origin-output-123456789abc"
    output = origin_bound_output.OriginBoundOutput.guarded_text(
        origin=origin,
        delivery_id="delivery-1",
        receipt_pointer=raw_ref,
        operator_text=f"The review failed safely. Nothing was sent. Receipt: {raw_ref}.",
        advertise_receipt_lookup=True,
    )

    visible = output.visible_text()
    assert raw_ref not in visible
    assert "Receipt:" not in visible
    assert "show receipt" in visible.lower()
    assert operator_surface_guard.guard_operator_reply(visible, agent_role="CASSANDRA") == visible


def test_operator_origin_with_machine_only_pointer_still_advertises_registered_lookup():
    output = origin_bound_output.OriginBoundOutput.guarded_text(
        origin=origin_bound_output.OutputOrigin(
            surface="cassandra_telegram",
            bot_identity="cassandra",
            chat_id="42",
            source_message_id="100",
            audience=origin_bound_output.OPERATOR_AUDIENCE,
        ),
        delivery_id="delivery-safe-text",
        receipt_pointer="origin-output-machine-only",
        operator_text="The prepared review response is ready.",
        advertise_receipt_lookup=True,
    )

    assert output.visible_text() == (
        "The prepared review response is ready. "
        "Say “show receipt” for the delivery record."
    )


def test_operator_origin_does_not_duplicate_an_existing_lookup_hint():
    hint = "Say “show receipt” for the delivery record."
    output = origin_bound_output.OriginBoundOutput.guarded_text(
        origin=origin_bound_output.OutputOrigin(
            surface="cassandra_telegram",
            bot_identity="cassandra",
            chat_id="42",
            source_message_id="100",
            audience=origin_bound_output.OPERATOR_AUDIENCE,
        ),
        delivery_id="delivery-existing-hint",
        receipt_pointer="origin-output-machine-only",
        operator_text=f"Nothing was sent. {hint}",
        advertise_receipt_lookup=True,
    )

    assert output.visible_text() == f"Nothing was sent. {hint}"
    assert output.visible_text().lower().count("show receipt") == 1


def test_origin_provider_must_opt_in_before_visible_text_advertises_lookup():
    output = origin_bound_output.OriginBoundOutput.guarded_text(
        origin=origin_bound_output.OutputOrigin(
            surface="future_factory_announcement",
            bot_identity="chief",
            chat_id="42",
            source_message_id="100",
            audience=origin_bound_output.OPERATOR_AUDIENCE,
        ),
        delivery_id="future-provider-delivery",
        receipt_pointer="future-provider-machine-pointer",
        operator_text="The factory update is ready.",
    )

    assert output.advertise_receipt_lookup is False
    assert output.visible_text() == "The factory update is ready."
    assert "show receipt" not in output.visible_text().lower()


def test_origin_opt_in_requires_literal_true_not_a_truthy_string():
    output = origin_bound_output.OriginBoundOutput.guarded_text(
        origin=origin_bound_output.OutputOrigin(
            surface="future_factory_announcement",
            bot_identity="chief",
            chat_id="42",
            source_message_id="100",
            audience=origin_bound_output.OPERATOR_AUDIENCE,
        ),
        delivery_id="future-provider-delivery",
        receipt_pointer="future-provider-machine-pointer",
        operator_text="The factory update is ready.",
        advertise_receipt_lookup="true",  # type: ignore[arg-type]
    )

    assert output.advertise_receipt_lookup is False
    assert "show receipt" not in output.visible_text().lower()


def test_unverified_origin_strips_an_upstream_lookup_hint_instead_of_repeating_it():
    output = origin_bound_output.OriginBoundOutput.guarded_text(
        origin=origin_bound_output.OutputOrigin(
            surface="future_factory_announcement",
            bot_identity="chief",
            chat_id="42",
            source_message_id="100",
            audience=origin_bound_output.OPERATOR_AUDIENCE,
        ),
        delivery_id="future-provider-delivery",
        receipt_pointer="future-provider-machine-pointer",
        operator_text=(
            "The factory update is ready. "
            "Say “show receipt” for the decision record."
        ),
    )

    assert output.visible_text() == "The factory update is ready."
    assert "show receipt" not in output.visible_text().lower()


def test_safe_renderer_scrubs_dynamic_raw_label_without_a_supplied_pointer():
    visible = origin_bound_output.OriginBoundOutput.guarded_text(
        origin=origin_bound_output.OutputOrigin(
            surface="cassandra_telegram",
            bot_identity="cassandra",
            chat_id="42",
            source_message_id="100",
            audience=origin_bound_output.OPERATOR_AUDIENCE,
        ),
        delivery_id="dynamic-raw-label",
        receipt_pointer="",
        operator_text="Nothing was sent. Receipt: runtime-created-pointer.",
    ).visible_text()

    assert visible == "Nothing was sent."
    assert "Receipt:" not in visible


def test_nonoperator_origin_neither_exposes_pointer_nor_advertises_operator_lookup():
    raw_ref = "origin-output-contact-123"
    output = origin_bound_output.OriginBoundOutput.guarded_text(
        origin=origin_bound_output.OutputOrigin(
            surface="cassandra_telegram",
            bot_identity="cassandra",
            chat_id="99",
            source_message_id="101",
            audience="designated_contact",
        ),
        delivery_id="delivery-contact",
        receipt_pointer=raw_ref,
        operator_text="Operator-only detail.",
        generic_text=f"Nothing was sent. Receipt: {raw_ref}.",
        advertise_receipt_lookup=True,
    )

    visible = output.visible_text()
    assert raw_ref not in visible
    assert "Receipt:" not in visible
    assert "show receipt" not in visible.lower()


def test_named_operator_visible_emitters_have_no_literal_raw_receipt_label():
    root = Path(__file__).resolve().parents[1]
    operator_visible_sources = (
        "workflow_package_queue.py",
        "typed_contract_decision.py",
        "origin_bound_output.py",
        "cassandra_listener.py",
        "cassandra_guided_review.py",
        "chief_guardian_listener.py",
        "chief_cassandra_failure.py",
        "operator_controller_event_router.py",
        "operator_action.py",
        "workroom_review_decision_consumer.py",
        "read_model_auto_refresh.py",
        "agent_presence.py",
    )

    offenders = []
    for name in operator_visible_sources:
        tree = ast.parse((root / name).read_text(encoding="utf-8"), filename=name)
        if any(
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "Receipt:" in node.value
            for node in ast.walk(tree)
        ):
            offenders.append(name)
    assert offenders == []


def test_repository_has_no_operator_emitter_string_with_raw_receipt_label():
    root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if "tests" in path.parts or ".git" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        try:
            tokens = tokenize.generate_tokens(io.StringIO(source).readline)
            if any(
                token.type == tokenize.STRING and "Receipt:" in token.string
                for token in tokens
            ):
                offenders.append(str(path.relative_to(root)))
        except (IndentationError, tokenize.TokenError):
            continue
    assert offenders == []
