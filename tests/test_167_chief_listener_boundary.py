from __future__ import annotations

import asyncio
import hashlib
import importlib
import sys
import types
from types import SimpleNamespace


def _load_chief_listener(monkeypatch):
    class Builder:
        def token(self, _token):
            return self

        def build(self):
            return SimpleNamespace(add_handler=lambda *_args, **_kwargs: None)

    class Filter:
        def __and__(self, _other):
            return self

        def __invert__(self):
            return self

    telegram = types.ModuleType("telegram")
    telegram.Update = object
    ext = types.ModuleType("telegram.ext")
    ext.ApplicationBuilder = Builder
    ext.CallbackQueryHandler = lambda *_args, **_kwargs: None
    ext.MessageHandler = lambda *_args, **_kwargs: None
    ext.filters = SimpleNamespace(TEXT=Filter(), COMMAND=Filter())
    ext.ContextTypes = SimpleNamespace(DEFAULT_TYPE=object)
    monkeypatch.setitem(sys.modules, "telegram", telegram)
    monkeypatch.setitem(sys.modules, "telegram.ext", ext)
    monkeypatch.setenv("CHIEF_BOT_TOKEN", "task-167-test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    sys.modules.pop("chief_listener", None)
    return importlib.import_module("chief_listener")


def test_chief_live_listener_keeps_receipt_and_skips_log_and_voice(
    tmp_path,
    monkeypatch,
) -> None:
    import operator_surface_guard
    from vote_timeout_clarification import WARM_TIMEOUT_CLARIFICATION

    listener = _load_chief_listener(monkeypatch)
    receipt = {
        "decision_id": "contract:task-167-chief",
        "source": "semantic_vote",
        "label": "unresolved",
        "action": "pass_through",
        "reason": "uncertain_outside_session_fail_open",
        "model_called": True,
        "semantic_vote_status": "deadline_exceeded",
    }
    listener.LOG_PATH = tmp_path / "chief_input.log"
    delivered: list[str] = []
    delivered_receipts: list[dict | None] = []
    delivered_boundary_receipts: list[dict | None] = []
    voice_calls: list[str] = []

    async def reply_text(text, **_kwargs):
        delivered.append(str(text))
        delivered_receipts.append(listener.current_typed_contract_receipt())
        delivered_boundary_receipts.append(listener.current_output_boundary_receipt())
        return SimpleNamespace(message_id=902)

    message = SimpleNamespace(
        text="maybe circle back on the thing from before",
        message_id=701,
        chat_id=456,
        reply_text=reply_text,
    )
    update = SimpleNamespace(
        update_id=16701,
        effective_user=SimpleNamespace(id=123),
        effective_chat=SimpleNamespace(id=456),
        message=message,
    )
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_a, **_k: True)
    monkeypatch.setattr(
        listener,
        "resolve_telegram_receipt_request",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        listener.first_touch_decision,
        "attempt_first_touch",
        lambda *_a, **_k: SimpleNamespace(
            handled=False,
            attempted=False,
            decision=None,
            receipt=None,
        ),
    )
    monkeypatch.setattr(
        listener,
        "record_telegram_listener_update_safe",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        listener,
        "route_message",
        lambda *_a, **_k: {
            "intent": "typed_contract_vote_timeout_clarification",
            "reply": WARM_TIMEOUT_CLARIFICATION,
            "contract_decision": receipt,
            "contract_matches": ["unresolved"],
            "send_performed": False,
            "ledger_touched": False,
            "workflow_package_staged": False,
        },
    )
    monkeypatch.setattr(
        listener,
        "contract_delivery_descriptor",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        listener,
        "render_verified_receipt_reply",
        lambda text, *_a, **_k: text,
    )
    monkeypatch.setattr(
        listener,
        "_telegram_typing_loop",
        lambda *_a, **_k: asyncio.sleep(0),
    )
    monkeypatch.setattr(
        listener,
        "_fire_agent_voice",
        lambda _agent, text, _update: voice_calls.append(str(text)),
    )
    guard_calls: list[str] = []

    def fake_guard(candidate, *_args, **_kwargs):
        guard_calls.append(str(candidate))
        visible = "UNRELATED CHIEF DIGEST $1,095" if len(guard_calls) == 1 else str(candidate)
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

    asyncio.run(listener.handle_message(update, SimpleNamespace(bot=SimpleNamespace())))

    assert delivered == [WARM_TIMEOUT_CLARIFICATION]
    assert delivered_receipts == [receipt]
    assert voice_calls == []
    assert listener.LOG_PATH.exists() is False
    assert guard_calls == [WARM_TIMEOUT_CLARIFICATION, WARM_TIMEOUT_CLARIFICATION]
    assert delivered_boundary_receipts[0]["visible_text_sha256"] == (
        "sha256:"
        + hashlib.sha256(WARM_TIMEOUT_CLARIFICATION.encode("utf-8")).hexdigest()
    )
