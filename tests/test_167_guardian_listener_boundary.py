from __future__ import annotations

import asyncio
import hashlib
import importlib
import sys
import types
from types import SimpleNamespace


def _load_guardian_listener(monkeypatch):
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
    telegram.InlineKeyboardMarkup = object
    errors = types.ModuleType("telegram.error")
    errors.BadRequest = Exception
    errors.Forbidden = Exception
    ext = types.ModuleType("telegram.ext")
    ext.ApplicationBuilder = Builder
    ext.CallbackQueryHandler = lambda *_args, **_kwargs: None
    ext.MessageHandler = lambda *_args, **_kwargs: None
    ext.filters = SimpleNamespace(TEXT=Filter(), COMMAND=Filter())
    ext.ContextTypes = SimpleNamespace(DEFAULT_TYPE=object)
    monkeypatch.setitem(sys.modules, "telegram", telegram)
    monkeypatch.setitem(sys.modules, "telegram.error", errors)
    monkeypatch.setitem(sys.modules, "telegram.ext", ext)
    monkeypatch.setenv("GUARDIAN_BOT_TOKEN", "task-167-test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    sys.modules.pop("chief_guardian_listener", None)
    return importlib.import_module("chief_guardian_listener")


def _timeout_receipt() -> dict[str, object]:
    return {
        "decision_id": "contract:task-167-guardian",
        "source": "semantic_vote",
        "label": "unresolved",
        "action": "pass_through",
        "reason": "uncertain_outside_session_fail_open",
        "model_called": True,
        "semantic_vote_status": "deadline_exceeded",
    }


def test_guardian_listener_skips_packet_and_reasserts_after_output_guard(
    monkeypatch,
) -> None:
    import chief_approval_brain
    import hitl_notification_service
    import operator_surface_guard
    from chief_nonapproval_responder import GuardianContractReply
    from vote_timeout_clarification import WARM_TIMEOUT_CLARIFICATION

    listener = _load_guardian_listener(monkeypatch)
    receipt = _timeout_receipt()
    sent: list[str] = []
    delivered_boundary_receipts: list[dict | None] = []

    async def reply_text(text, **_kwargs):
        sent.append(str(text))
        delivered_boundary_receipts.append(
            listener.current_output_boundary_receipt()
        )
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
    monkeypatch.setattr(chief_approval_brain, "has_pending_approval", lambda: False)
    monkeypatch.setattr(
        hitl_notification_service,
        "handle_typed_reply",
        lambda *_a, **_k: {"handled": False},
    )
    monkeypatch.setattr(
        listener,
        "guardian_no_pending_reply",
        lambda text, **_kwargs: GuardianContractReply(
            WARM_TIMEOUT_CLARIFICATION,
            contract_receipt=receipt,
            source_text=text,
        ),
    )
    monkeypatch.setattr(
        listener,
        "_build_no_pending_guardian_packet",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("timeout path built/logged a Guardian packet")
        ),
    )
    guard_calls: list[str] = []

    def fake_guard(candidate, *_args, **_kwargs):
        guard_calls.append(str(candidate))
        visible = (
            "UNRELATED GUARDIAN BUSINESS DIGEST"
            if len(guard_calls) == 1
            else str(candidate)
        )
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

    asyncio.run(listener.handle_message(update, SimpleNamespace()))

    assert sent == [WARM_TIMEOUT_CLARIFICATION]
    assert guard_calls == [
        WARM_TIMEOUT_CLARIFICATION,
        WARM_TIMEOUT_CLARIFICATION,
    ]
    assert delivered_boundary_receipts[0]["visible_text_sha256"] == (
        "sha256:"
        + hashlib.sha256(WARM_TIMEOUT_CLARIFICATION.encode("utf-8")).hexdigest()
    )
