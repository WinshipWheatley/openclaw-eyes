from __future__ import annotations

import asyncio
import hashlib
import importlib
import sys
import types
from types import SimpleNamespace

import pytest


OPAQUE = "maybe circle back on the thing from before"
EXPECTED_MODEL_FAILURE_CLARIFICATION = (
    "The language model didn't return a usable routing decision. I left your "
    "request untouched; please try again in a moment."
)


def _timeout_decision(*, status: str = "error:TimeoutError"):
    from typed_contract_decision import (
        ContractContext,
        ContractDecision,
        ContractLabel,
        ContractReceipt,
        DecisionAction,
    )

    receipt = ContractReceipt(
        decision_id="contract:167-timeout",
        label=ContractLabel.UNRESOLVED.value,
        action=DecisionAction.PASS_THROUGH.value,
        precedence=40,
        source="semantic_vote",
        reason="uncertain_outside_session_fail_open",
        model_called=True,
        semantic_vote_status=status,
        confidence=0.0,
    )
    return ContractDecision(
        label=ContractLabel.UNRESOLVED,
        matches=(ContractLabel.UNRESOLVED,),
        action=DecisionAction.PASS_THROUGH,
        reply=None,
        context=ContractContext(agent="test", surface="test"),
        receipt=receipt,
    )


def _fail(message: str):
    def blocked(*_args, **_kwargs):
        pytest.fail(message)

    return blocked


class _FakeFilter:
    def __and__(self, _other):
        return self

    def __invert__(self):
        return self


def _load_producer_listener(monkeypatch):
    telegram = types.ModuleType("telegram")
    telegram.Update = object

    class _ApplicationBuilder:
        def token(self, _token):
            return self

        def build(self):
            return SimpleNamespace(add_handler=lambda *_args, **_kwargs: None)

    ext = types.ModuleType("telegram.ext")
    ext.ApplicationBuilder = _ApplicationBuilder
    ext.MessageHandler = lambda *_args, **_kwargs: None
    ext.filters = SimpleNamespace(
        TEXT=_FakeFilter(),
        COMMAND=_FakeFilter(),
        VOICE=_FakeFilter(),
    )
    ext.ContextTypes = SimpleNamespace(DEFAULT_TYPE=object)
    monkeypatch.setitem(sys.modules, "telegram", telegram)
    monkeypatch.setitem(sys.modules, "telegram.ext", ext)
    sys.modules.pop("producer_listener", None)
    return importlib.import_module("producer_listener")


def test_cassandra_listener_timeout_stops_before_brain_cockpit_and_staging(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CASSANDRA_BOT_TOKEN", "task-167-test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "42")
    import typed_contract_decision as typed
    import cassandra_listener as listener
    from vote_timeout_clarification import WARM_TIMEOUT_CLARIFICATION

    decision = _timeout_decision()
    monkeypatch.setattr(typed, "decide_contract", lambda *_args, **_kwargs: decision)
    monkeypatch.setattr(listener, "cassandra_handle", _fail("second Cassandra/model path ran"))
    monkeypatch.setattr(listener, "_try_invoice_cockpit", _fail("cockpit captured timeout"))

    workflow_db = tmp_path / "workflow.sqlite3"
    replies = asyncio.run(
        listener._run_cassandra_handle_async(
            OPAQUE,
            {
                "surface": "cassandra_telegram",
                "source_message_id": "167-cassandra",
                "invoice_cockpit_session_path": str(tmp_path / "cockpit.json"),
                "guided_review_root": str(tmp_path / "guided"),
                "workflow_package_sqlite_path": str(workflow_db),
            },
        )
    )

    assert len(replies) == 1
    assert str(replies[0]) == WARM_TIMEOUT_CLARIFICATION
    assert replies[0].contract_receipt == decision.receipt.to_dict()
    assert workflow_db.exists() is False


def test_cassandra_brain_timeout_survives_output_guard_without_state_or_model(
    monkeypatch,
) -> None:
    import typed_contract_decision as typed
    import cassandra_brain as brain
    import operator_surface_guard
    from vote_timeout_clarification import WARM_TIMEOUT_CLARIFICATION

    decision = _timeout_decision(status="deadline_exceeded")
    monkeypatch.setattr(typed, "decide_contract", lambda *_args, **_kwargs: decision)
    monkeypatch.setattr(brain, "_inner_circle_topic_gate", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(brain, "load_state", _fail("state loaded after timeout"))
    monkeypatch.setattr(brain, "save_state", _fail("state mutated after timeout"))
    monkeypatch.setattr(brain, "_call_hidden", _fail("second model call ran"), raising=False)
    monkeypatch.setattr(brain, "_log_conversation", _fail("conversation log mutated"))
    monkeypatch.setattr(
        operator_surface_guard,
        "guard_operator_reply",
        lambda *_args, **_kwargs: "UNRELATED BUSINESS DIGEST",
    )

    replies = brain.handle(OPAQUE, {"surface": "cassandra_brain.handle"})
    assert replies == [WARM_TIMEOUT_CLARIFICATION]
    assert replies[0].contract_receipt == decision.receipt.to_dict()


def test_chief_legacy_vote_failure_is_structured_and_not_called_a_timeout(
    monkeypatch,
) -> None:
    import typed_contract_decision as typed
    import chief_router
    import operator_surface_guard
    decision = _timeout_decision(status="timeout_or_invalid")
    monkeypatch.setattr(typed, "decide_contract", lambda *_args, **_kwargs: decision)
    monkeypatch.setattr(chief_router, "load_session", lambda: {})
    monkeypatch.setattr(chief_router, "has_pending_approval", lambda: False)
    monkeypatch.setattr(chief_router, "has_pending_choice", lambda: False)
    monkeypatch.setattr(chief_router, "_chief_fallback_reply", _fail("Chief model fallback ran"))
    monkeypatch.setattr(chief_router, "_log_route", _fail("Chief route log mutated"))
    monkeypatch.setattr(
        operator_surface_guard,
        "guard_operator_reply",
        lambda *_args, **_kwargs: "UNRELATED CHIEF DIGEST",
    )

    result = chief_router.route_message(OPAQUE)

    assert result["reply"] == EXPECTED_MODEL_FAILURE_CLARIFICATION
    assert "timeout" not in result["reply"].lower()
    assert result["contract_decision"] == decision.receipt.to_dict()
    assert result["send_performed"] is False
    assert result["ledger_touched"] is False


def test_guardian_timeout_returns_warm_structured_nonapproval_response(monkeypatch) -> None:
    import typed_contract_decision as typed
    import chief_nonapproval_responder as responder
    from vote_timeout_clarification import WARM_TIMEOUT_CLARIFICATION

    decision = _timeout_decision(status="error:TimeoutError")
    monkeypatch.setattr(typed, "decide_contract", lambda *_args, **_kwargs: decision)
    monkeypatch.setattr(
        responder,
        "classify_nonapproval_prompt",
        _fail("Guardian legacy classifier ran"),
    )

    response = responder.nonapproval_response_for_text(OPAQUE, surface="guardian")

    assert response is not None
    assert response.reply == WARM_TIMEOUT_CLARIFICATION
    assert response.receipt == decision.receipt.to_dict()
    assert response.send_performed is False
    assert response.ledger_touched is False
    carrier = responder.guardian_no_pending_reply(OPAQUE)
    assert str(carrier) == WARM_TIMEOUT_CLARIFICATION
    assert carrier.contract_receipt == decision.receipt.to_dict()


def test_niles_listener_timeout_stops_before_queue_subprocess_and_voice(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("PRODUCER_BOT_TOKEN", "task-167-test-token")
    monkeypatch.setenv("NILES_BOT_TOKEN", "task-167-test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "42")
    import typed_contract_decision as typed
    import operator_surface_guard
    from vote_timeout_clarification import WARM_TIMEOUT_CLARIFICATION

    producer_listener = _load_producer_listener(monkeypatch)

    decision = _timeout_decision(status="deadline_exceeded")
    captured_receipts: list[dict] = []
    delivered: list[str] = []
    delivered_contract_receipts: list[dict | None] = []
    delivered_boundary_receipts: list[dict | None] = []

    async def reply_text(text, **_kwargs):
        delivered.append(str(text))
        delivered_contract_receipts.append(
            producer_listener.current_typed_contract_receipt()
        )
        delivered_boundary_receipts.append(
            producer_listener.current_output_boundary_receipt()
        )
        return SimpleNamespace(message_id=902)

    message = SimpleNamespace(
        text=OPAQUE,
        message_id=701,
        chat_id=42,
        reply_text=reply_text,
    )
    update = SimpleNamespace(
        update_id=16701,
        effective_user=SimpleNamespace(id=42),
        effective_chat=SimpleNamespace(id=42),
        message=message,
    )
    context = SimpleNamespace(bot=SimpleNamespace())

    monkeypatch.setattr(typed, "decide_contract", lambda *_args, **_kwargs: decision)
    monkeypatch.setattr(producer_listener, "claim_listener_update", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        producer_listener.first_touch_decision,
        "attempt_first_touch",
        lambda *_args, **_kwargs: SimpleNamespace(
            handled=False,
            attempted=False,
            decision=None,
            receipt=None,
        ),
    )
    monkeypatch.setattr(
        producer_listener,
        "record_telegram_listener_update_safe",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        producer_listener,
        "contract_delivery_descriptor",
        lambda receipt, **_kwargs: captured_receipts.append(dict(receipt)) or None,
    )
    monkeypatch.setattr(producer_listener, "register_telegram_delivery", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(producer_listener, "_queue_for_memory", _fail("Niles queue mutated"))
    monkeypatch.setattr(producer_listener, "_run_producer_intake", _fail("Niles subprocess ran"))
    monkeypatch.setattr(producer_listener, "_fire_agent_voice", _fail("voice side effect ran"))
    guard_calls: list[str] = []

    def fake_guard(candidate, *_args, **_kwargs):
        guard_calls.append(str(candidate))
        visible = "UNRELATED NILES DIGEST" if len(guard_calls) == 1 else str(candidate)
        return SimpleNamespace(
            visible_text=visible,
            receipt=SimpleNamespace(
                to_dict=lambda: {
                    "visible_text_sha256": "sha256:"
                    + hashlib.sha256(visible.encode("utf-8")).hexdigest()
                }
            ),
        )

    monkeypatch.setattr(
        operator_surface_guard,
        "guard_operator_reply_with_receipt",
        fake_guard,
    )

    asyncio.run(producer_listener.handle_message(update, context))

    assert delivered == [WARM_TIMEOUT_CLARIFICATION]
    assert captured_receipts == [decision.receipt.to_dict()]
    assert guard_calls == [WARM_TIMEOUT_CLARIFICATION, WARM_TIMEOUT_CLARIFICATION]
    assert delivered_boundary_receipts[0][
        "visible_text_sha256"
    ] == "sha256:" + hashlib.sha256(
        WARM_TIMEOUT_CLARIFICATION.encode("utf-8")
    ).hexdigest()
    assert delivered_contract_receipts == [decision.receipt.to_dict()]


def test_niles_subprocess_mirror_keeps_legacy_model_failure_receipt(monkeypatch) -> None:
    import typed_contract_decision as typed
    from scripts import producer_intake
    decision = _timeout_decision(status="timeout_or_invalid")
    monkeypatch.setattr(typed, "decide_contract", lambda *_args, **_kwargs: decision)

    result = producer_intake._typed_contract_result(OPAQUE)

    assert result == {
        "reply": EXPECTED_MODEL_FAILURE_CLARIFICATION,
        "contract_decision": decision.receipt.to_dict(),
    }


def test_hermes_timeout_survives_final_boundary_and_retains_receipt(monkeypatch) -> None:
    import typed_contract_decision as typed
    import openclaw_hermes_gateway_policy as hermes
    from vote_timeout_clarification import WARM_TIMEOUT_CLARIFICATION

    decision = _timeout_decision(status="error:TimeoutError")
    monkeypatch.setattr(typed, "decide_contract", lambda *_args, **_kwargs: decision)
    monkeypatch.setattr(hermes, "_route_target", _fail("Hermes route fallback ran"))

    reply = hermes.truthful_reply_for_text(OPAQUE)

    assert reply == WARM_TIMEOUT_CLARIFICATION
    assert hermes.current_gateway_vote_timeout_receipt() == decision.receipt.to_dict()
    assert hermes.sanitize_gateway_response(
        "UNRELATED HERMES DIGEST",
        source_request=OPAQUE,
    ) == WARM_TIMEOUT_CLARIFICATION


def test_chief_compose_api_keeps_timeout_receipt_in_read_only_meta(
    monkeypatch,
) -> None:
    import chief_compose
    import chief_router
    import intent_router
    import openclaw_api_server
    import pii_vault
    from vote_timeout_clarification import WARM_TIMEOUT_CLARIFICATION

    decision = _timeout_decision(status="deadline_exceeded")
    receipt = decision.receipt.to_dict()
    monkeypatch.setattr(
        intent_router,
        "route_operator_intent",
        lambda **_kwargs: SimpleNamespace(
            rejection_reason=None,
            status="accepted",
            approval_required=False,
            intent_category="communication_summary_request",
            candidate_action_type=None,
            run_id="task-167-chief-compose",
        ),
    )
    monkeypatch.setattr(pii_vault, "redact_text", lambda text: (text, {}))
    monkeypatch.setattr(
        chief_router,
        "route_message",
        lambda _text: {
            "intent": "typed_contract_vote_timeout_clarification",
            "reply": WARM_TIMEOUT_CLARIFICATION,
            "contract_decision": receipt,
            "contract_matches": ["unresolved"],
        },
    )

    result = chief_compose.compose(OPAQUE)
    payload = openclaw_api_server.render_api_compose_result(result)

    assert payload["gate_state"] == "READ_ONLY"
    assert payload["segments"] == [WARM_TIMEOUT_CLARIFICATION]
    assert payload["meta"]["contract_decision"] == receipt
    assert payload["meta"]["contract_matches"] == ["unresolved"]
