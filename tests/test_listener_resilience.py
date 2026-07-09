from __future__ import annotations

import asyncio
import importlib
import sys
import types

import listener_resilience


def test_shared_clean_stale_carryover_keeps_only_fresh_lines() -> None:
    cleaned = listener_resilience.clean_stale_carryover(
        "The previous response was truncated. Continue? (61/61)\n"
        "skill_view: factory_handoff_status\n"
        "Still working... (10 min elapsed - iteration 2/90, waiting for stream response)\n"
        "Fresh answer from this turn.",
        failure_text="short fail",
    )

    assert cleaned == "Fresh answer from this turn."


def test_shared_stale_only_output_becomes_honest_short_fail() -> None:
    cleaned = listener_resilience.clean_stale_carryover(
        "Still working... (10 min elapsed - waiting for stream response)\n"
        "The previous response was truncated. Continue?",
        failure_text=listener_resilience.honest_short_fail("TestListener"),
    )

    assert "TestListener could not produce a fresh answer" in cleaned
    assert "Still working" not in cleaned
    assert "previous response was truncated" not in cleaned.lower()


def test_shared_bounded_reply_timeout_returns_configured_short_fail() -> None:
    async def slow_reply() -> str:
        await asyncio.sleep(1)
        return "late reply"

    async def run_case() -> str:
        return await listener_resilience.bounded_reply_timeout(
            slow_reply(),
            timeout_seconds=0.01,
            timeout_result="short timeout fail",
        )

    assert asyncio.run(run_case()) == "short timeout fail"


def test_guardian_reply_sanitizes_stale_carryover(monkeypatch) -> None:
    monkeypatch.setenv("GUARDIAN_BOT_TOKEN", "guardian-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")

    class _FakeApplicationBuilder:
        def token(self, _token):
            return self

        def build(self):
            return types.SimpleNamespace(add_handler=lambda *a, **k: None, run_polling=lambda: None)

    class _FakeFilter:
        def __and__(self, _other):
            return self

        def __invert__(self):
            return self

    sys.modules["telegram"] = types.SimpleNamespace(Update=object, InlineKeyboardMarkup=object)
    sys.modules["telegram.error"] = types.SimpleNamespace(BadRequest=Exception, Forbidden=Exception)
    sys.modules["telegram.ext"] = types.SimpleNamespace(
        ApplicationBuilder=_FakeApplicationBuilder,
        CallbackQueryHandler=lambda *a, **k: None,
        MessageHandler=lambda *a, **k: None,
        filters=types.SimpleNamespace(TEXT=_FakeFilter(), COMMAND=_FakeFilter()),
        ContextTypes=types.SimpleNamespace(DEFAULT_TYPE=object()),
    )
    sys.modules.pop("chief_guardian_listener", None)
    import chief_guardian_listener

    module = importlib.reload(chief_guardian_listener)
    reply = module.guardian_resilient_reply(
        "The previous response was truncated. Continue?\n"
        "Still working... waiting for stream response\n"
        "Guardian fresh answer."
    )

    assert reply == "Guardian fresh answer."


def test_guardian_reply_guards_a_leaked_reply(monkeypatch) -> None:
    """Task 144 (CLASS #5): guardian_resilient_reply is the single choke point for all
    Guardian Telegram sends -- a leak here must be substituted before it reaches
    update.message.reply_text."""
    import operator_surface_guard

    monkeypatch.setenv("GUARDIAN_BOT_TOKEN", "guardian-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")

    class _FakeApplicationBuilder:
        def token(self, _token):
            return self

        def build(self):
            return types.SimpleNamespace(add_handler=lambda *a, **k: None, run_polling=lambda: None)

    class _FakeFilter:
        def __and__(self, _other):
            return self

        def __invert__(self):
            return self

    sys.modules["telegram"] = types.SimpleNamespace(Update=object, InlineKeyboardMarkup=object)
    sys.modules["telegram.error"] = types.SimpleNamespace(BadRequest=Exception, Forbidden=Exception)
    sys.modules["telegram.ext"] = types.SimpleNamespace(
        ApplicationBuilder=_FakeApplicationBuilder,
        CallbackQueryHandler=lambda *a, **k: None,
        MessageHandler=lambda *a, **k: None,
        filters=types.SimpleNamespace(TEXT=_FakeFilter(), COMMAND=_FakeFilter()),
        ContextTypes=types.SimpleNamespace(DEFAULT_TYPE=object()),
    )
    sys.modules.pop("chief_guardian_listener", None)
    import chief_guardian_listener

    module = importlib.reload(chief_guardian_listener)
    reply = module.guardian_resilient_reply("Debug: livegmailaccessenabled=False (data gap)")

    assert reply == operator_surface_guard.SAFE_FALLBACK_REPLY_TEXT


def test_guardian_reply_safe_text_unaffected(monkeypatch) -> None:
    monkeypatch.setenv("GUARDIAN_BOT_TOKEN", "guardian-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")

    class _FakeApplicationBuilder:
        def token(self, _token):
            return self

        def build(self):
            return types.SimpleNamespace(add_handler=lambda *a, **k: None, run_polling=lambda: None)

    class _FakeFilter:
        def __and__(self, _other):
            return self

        def __invert__(self):
            return self

    sys.modules["telegram"] = types.SimpleNamespace(Update=object, InlineKeyboardMarkup=object)
    sys.modules["telegram.error"] = types.SimpleNamespace(BadRequest=Exception, Forbidden=Exception)
    sys.modules["telegram.ext"] = types.SimpleNamespace(
        ApplicationBuilder=_FakeApplicationBuilder,
        CallbackQueryHandler=lambda *a, **k: None,
        MessageHandler=lambda *a, **k: None,
        filters=types.SimpleNamespace(TEXT=_FakeFilter(), COMMAND=_FakeFilter()),
        ContextTypes=types.SimpleNamespace(DEFAULT_TYPE=object()),
    )
    sys.modules.pop("chief_guardian_listener", None)
    import chief_guardian_listener

    module = importlib.reload(chief_guardian_listener)
    reply = module.guardian_resilient_reply("No pending approval requests.")

    assert reply == "No pending approval requests."
