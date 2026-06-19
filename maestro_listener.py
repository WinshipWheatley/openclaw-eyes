"""
maestro_listener.py

Standalone Telegram bot for Maestro, the OpenClaw front-door conductor.

This surface records governed intake, shows Telegram typing while the front-door
responder thinks, and replies only to the authorized internal operator. It does
not import outbound sender paths or execute work.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import signal
from collections.abc import Callable, Mapping
from typing import Any

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from telegram_agent_intake import record_maestro_listener_text_update


def _require_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    joined = " or ".join(names)
    raise RuntimeError(f"{joined} must be set.")


BOT_TOKEN = _require_env("MAESTRO_BOT_TOKEN", "MAESTRO_TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID = int(_require_env("TELEGRAM_AUTHORIZED_USER_ID"))
_FRONTDOOR_READY_STATUSES = {"ANSWER_READY", "RESPONSE_READY", "TEXT_RESPONSE_READY"}
_UNAVAILABLE_REPLY = (
    "Maestro's Telegram surface is registered, but the front-door responder is "
    "not importable in this Mac runtime yet. I recorded the request without "
    "running actions."
)


async def _telegram_typing_loop(bot, chat_id: int | None) -> None:
    if chat_id is None:
        return
    while True:
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception as exc:
            print(f"[maestro_listener] typing indicator error: {exc.__class__.__name__}", flush=True)
        await asyncio.sleep(4.0)


def _load_frontdoor_responder() -> Callable[..., Any] | None:
    try:
        from maestro_cassandra_responder import answer_frontdoor_chat
    except Exception as exc:
        print(f"[maestro_listener] front-door responder unavailable: {exc.__class__.__name__}", flush=True)
        return None
    return answer_frontdoor_chat


def _call_frontdoor_responder(answer_frontdoor_chat: Callable[..., Any], text: str, session_meta: dict[str, Any]) -> Any:
    signature = inspect.signature(answer_frontdoor_chat)
    parameters = signature.parameters
    if "session" in parameters:
        return answer_frontdoor_chat(text, session=session_meta)
    if "session_meta" in parameters:
        return answer_frontdoor_chat(text, session_meta=session_meta)

    positional = [
        param
        for param in parameters.values()
        if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    has_varargs = any(param.kind == inspect.Parameter.VAR_POSITIONAL for param in parameters.values())
    if has_varargs or len(positional) >= 2:
        return answer_frontdoor_chat(text, session_meta)
    return answer_frontdoor_chat(text)


def _first_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return "\n".join(str(item).strip() for item in value if str(item).strip()).strip()
    return str(value).strip()


def _mapping_text(payload: Mapping[str, Any]) -> str:
    for key in ("plain_summary", "one_line_answer", "answer", "text", "message", "summary"):
        text = _first_text(payload.get(key))
        if text:
            return text

    for key in ("layered_response_fields", "operator_display", "detail_disclosure", "display", "response"):
        nested = payload.get(key)
        if isinstance(nested, Mapping):
            text = _mapping_text(nested)
            if text:
                return text
    return ""


def _format_frontdoor_reply(result: Any) -> str:
    if isinstance(result, Mapping):
        status = str(result.get("status") or result.get("route_status") or result.get("internal_status") or "")
        text = _mapping_text(result)
        if text and (not status or status in _FRONTDOOR_READY_STATUSES):
            return text
        blocked = _first_text(result.get("blocked_reason") or result.get("rejection_reason") or result.get("next_safe_move"))
        if blocked:
            return f"Maestro cannot answer that directly yet: {blocked}"
        if text:
            return text
        return "Maestro returned a response without display text. No action was run."

    text = _first_text(result)
    if text:
        return text
    return "Maestro returned no displayable response. No action was run."


def _answer_frontdoor_sync(text: str, session_meta: dict[str, Any]) -> str:
    responder = _load_frontdoor_responder()
    if responder is None:
        return _UNAVAILABLE_REPLY
    result = _call_frontdoor_responder(responder, text, session_meta)
    return _format_frontdoor_reply(result)


async def _run_frontdoor_answer(text: str, session_meta: dict[str, Any]) -> str:
    return await asyncio.to_thread(_answer_frontdoor_sync, text, session_meta)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if not text:
        return

    is_authorized_user = bool(update.effective_user and update.effective_user.id == AUTHORIZED_USER_ID)
    source_user_label = "operator" if is_authorized_user else "unverified_sender"
    record_maestro_listener_text_update(
        text=text,
        source_message_id=str(getattr(update, "update_id", "")) or None,
        source_user_label=source_user_label,
        operator_message=is_authorized_user,
        route_intent=False,
    )
    if not is_authorized_user:
        return

    chat_id = update.effective_chat.id if update.effective_chat else AUTHORIZED_USER_ID
    typing_task = asyncio.create_task(_telegram_typing_loop(context.bot, chat_id))
    try:
        reply = await _run_frontdoor_answer(
            text,
            {
                "surface": "telegram",
                "source_channel": "maestro_listener",
                "agent_target": "maestro",
                "authorized_internal_operator": True,
            },
        )
        await update.message.reply_text(reply)
    except Exception as exc:
        print(f"[maestro_listener] front-door error: {exc.__class__.__name__}", flush=True)
        await update.message.reply_text("Maestro hit a front-door error. I recorded the request without running actions.")
    finally:
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass


def build_application():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application


async def run_listener(application=None, stop_event: asyncio.Event | None = None) -> None:
    application = application or build_application()
    updater = application.updater
    if updater is None:
        raise RuntimeError("Maestro listener application must have an updater.")

    loop = asyncio.get_running_loop()
    stop_event = stop_event or asyncio.Event()
    registered_signals: list[signal.Signals] = []
    polling_started = False
    app_started = False
    initialized = False

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
            registered_signals.append(sig)
        except (NotImplementedError, RuntimeError):
            pass

    try:
        await application.initialize()
        initialized = True
        if application.post_init:
            await application.post_init(application)
        await updater.start_polling()
        polling_started = True
        await application.start()
        app_started = True
        await stop_event.wait()
    finally:
        for sig in registered_signals:
            try:
                loop.remove_signal_handler(sig)
            except (NotImplementedError, RuntimeError):
                pass

        if polling_started:
            await updater.stop()
        if app_started and application.running:
            await application.stop()
        if initialized:
            await application.shutdown()


def main() -> None:
    print("[maestro_listener] starting...", flush=True)
    asyncio.run(run_listener())


if __name__ == "__main__":
    main()
