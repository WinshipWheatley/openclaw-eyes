import asyncio
import contextvars
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import first_touch_decision
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from chief_router import route_message
from chief_validator_brain import validate_reply
from chief_queue_brain import check_pending_queue
from chief_output_utils import tts_clean
from telegram_agent_intake import claim_listener_update, record_telegram_listener_update_safe
from telegram_listener_integrity import (
    install_identity_preflight,
    resolve_role_bot_token,
    run_verified_polling,
)

LOG_PATH = Path("/mnt/c/OpenClaw/logs/chief_input.log")
BOT_TOKEN = resolve_role_bot_token("chief")
AUTHORIZED_USER_ID = int(os.environ["TELEGRAM_AUTHORIZED_USER_ID"])
_OUTPUT_BOUNDARY_RECEIPT: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "chief_output_boundary_receipt",
    default=None,
)


def current_output_boundary_receipt() -> dict | None:
    receipt = _OUTPUT_BOUNDARY_RECEIPT.get()
    return dict(receipt) if isinstance(receipt, dict) else None


def _final_operator_text(text: str, *, source_request: str) -> str:
    try:
        from operator_surface_guard import guard_operator_reply_with_receipt

        bounded = guard_operator_reply_with_receipt(
            tts_clean(text),
            agent_role="CHIEF",
            source_request=source_request,
        )
        _OUTPUT_BOUNDARY_RECEIPT.set(bounded.receipt.to_dict())
        return bounded.visible_text
    except Exception:
        _OUTPUT_BOUNDARY_RECEIPT.set({
            "outcome": "adapter_boundary_error",
            "raw_control_text_included": False,
        })
        return "Chief couldn't safely render that answer just now. Nothing was sent or changed."


async def _telegram_typing_loop(bot, chat_id: int | None) -> None:
    if chat_id is None:
        return
    while True:
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception as exc:
            print(f"[chief_listener] typing indicator error: {exc}", flush=True)
        await asyncio.sleep(4.0)


def _fire_agent_voice(agent: str, text: str, update: Update) -> None:
    """Fire-and-forget: synth+send the agent's Kokoro voice note (bm_george for Chief) WITHOUT
    blocking the event loop or letting a TTS/Telegram hiccup break the text reply. Toggle with
    OPENCLAW_AGENT_VOICE_NOTES=0."""
    try:
        import os
        import agent_voice_sender

        if os.environ.get("OPENCLAW_AGENT_VOICE_NOTES", "1").strip().lower() not in ("1", "true", "yes"):
            return
        chat_id = getattr(getattr(update, "message", None), "chat_id", None)
        asyncio.get_event_loop().run_in_executor(
            None, lambda: agent_voice_sender.send_agent_voice_note(agent, text, chat_id=chat_id)
        )
    except Exception as exc:  # never break a text reply on a voice issue
        print(f"[chief_listener] voice note skipped: {exc}", flush=True)


async def _send_reply(
    update: Update,
    text: str,
    *,
    source_request: str | None = None,
) -> None:
    """Send a tts_clean-normalized plain-text reply, plus Chief's Kokoro voice note (fail-soft)."""
    request_text = (
        str(source_request)
        if source_request is not None
        else str(getattr(getattr(update, "message", None), "text", "") or "")
    )
    safe_text = _final_operator_text(text, source_request=request_text)
    await update.message.reply_text(safe_text)
    _fire_agent_voice("chief", safe_text, update)


async def _resume_interrupted_task(update: Update) -> None:
    """
    After a Claude Code approval gate closes, resume the active album session.

    Priority: use the snapshot saved at interrupt time (most precise), then
    fall back to reading live session state. Sends a clean one-line header
    followed by the pending question so the user knows exactly where to pick up.
    """
    try:
        from chief_album_brain import TOPIC_PROMPTS
        from chief_approval_brain import get_pending_album_snapshot

        # ── 1. Try snapshot saved at interrupt time ────────────────────────
        snapshot = get_pending_album_snapshot()
        if snapshot:
            song  = snapshot.get("song_title", "")
            topic = snapshot.get("last_topic_asked")
            phase = snapshot.get("phase", "")
            if song and topic and phase in ("follow_up", "open"):
                prompt = TOPIC_PROMPTS.get(topic, "")
                if prompt:
                    await _send_reply(update,
                        f"Back to album.\n"
                        f"We're on {song}.\n\n"
                        f"Pending question: {prompt}"
                    )
                    return
            if song:
                # Song was named but no specific pending question (e.g. open phase)
                await _send_reply(update,
                    f"Back to album — {song}.\n"
                    "What's on your mind for this song?"
                )
                return

        # ── 2. Fall back to live session state ────────────────────────────
        from chief_session_manager import load_session
        session = load_session()
        if (session.get("active_workflow") == "album"
                and session.get("status") == "active"):
            wf    = session.get("workflow_state", {})
            topic = wf.get("last_topic_asked")
            phase = wf.get("phase", "")
            song  = wf.get("song_title", "")
            if song and topic and phase in ("follow_up", "open"):
                prompt = TOPIC_PROMPTS.get(topic, "")
                if prompt:
                    await _send_reply(update,
                        f"Back to album.\n"
                        f"We're on {song}.\n\n"
                        f"Pending question: {prompt}"
                    )
            elif song:
                await _send_reply(update,
                    f"Back to album — {song}. What's on your mind?"
                )
    except Exception:
        pass


def extract_snapshot_name(output: str) -> str | None:
    m = re.search(r"inspection-\d{8}-\d{6}", output or "")
    return m.group(0) if m else None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != AUTHORIZED_USER_ID:
        return

    if not update.message or not update.message.text:
        return
    if not claim_listener_update(update, role="chief", source_channel="chief_listener"):
        return

    text = update.message.text.strip()
    first_touch = first_touch_decision.attempt_first_touch(
        text,
        agent="chief",
        surface="chief_listener",
    )
    if first_touch.handled and first_touch.decision is not None:
        reply = _final_operator_text(
            first_touch.decision.reply,
            source_request=text,
        )
        await update.message.reply_text(reply)
        return
    record_telegram_listener_update_safe(
        text=text,
        source_channel="chief_listener",
        agent_target="chief",
        source_message_id=str(getattr(update, "update_id", "")) or None,
        source_user_label="operator",
        operator_message=True,
        route_intent=True,
    )
    chat_id = update.effective_chat.id if update.effective_chat else AUTHORIZED_USER_ID
    typing_task = asyncio.create_task(_telegram_typing_loop(context.bot, chat_id))
    try:
        try:
            routed = await asyncio.to_thread(
                route_message,
                text,
                first_touch_receipt=first_touch.receipt if first_touch.attempted else None,
            )
        except Exception as e:
            print(f"[chief_listener] route_message error: {e}", flush=True)
            await update.message.reply_text("Chief hit a snag routing that. Try again.")
            return
    finally:
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass

    intent = routed.get("intent")
    reply = routed.get("reply")

    try:
        if intent == "approval_response":
            await _send_reply(update, reply or "Decision recorded.", source_request=text)
            await _resume_interrupted_task(update)
            return

        if intent == "inspection":
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["/home/openclaw/chief-inspect", "telegram requested snapshot"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                snapshot_name = extract_snapshot_name(result.stdout)
                if snapshot_name:
                    await update.message.reply_text(f"Inspection snapshot created: {snapshot_name}")
                else:
                    await update.message.reply_text("Inspection snapshot created. Check the latest exports folder on OpenClaw.")
                print(result.stdout)
            except Exception as e:
                import traceback
                print("Inspection error:")
                traceback.print_exc()
                await _send_reply(update, f"Inspection failed: {e}", source_request=text)
            return

        if intent == "cancel":
            await _send_reply(update, reply or "Current workflow cancelled.", source_request=text)
            # Surface any deferred ops captured during a now-cancelled album session
            try:
                from chief_ops_brain import deferred_summary
                summary = deferred_summary()
                if summary:
                    for s in summary:
                        await _send_reply(update, s)
            except Exception:
                pass
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        if intent == "billing_start":
            await _send_reply(update, reply or "Ready.", source_request=text)
            return

        if intent == "billing_continue":
            replies = routed.get("replies", [])
            if replies:
                try:
                    for r in replies:
                        await _send_reply(update, r)
                except Exception as e:
                    print(f"Billing direct reply error: {e}")
                    await update.message.reply_text("Billing reply error.")
                return
            formatted = f"[PHONE][{timestamp}] {text}"
            try:
                with open(LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(formatted + "\n")
                await update.message.reply_text("Billing input captured.")
            except Exception as e:
                print(f"Billing fallback routing error: {e}")
                await update.message.reply_text("Billing routing error.")
            return


        if intent == "batch_query":
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent in ("album_status", "nli_status"):
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent == "cassandra":
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent == "album_start":
            await _send_reply(
                update,
                reply or "What song are we working on?",
                source_request=text,
            )
            return

        if intent == "ops_intake":
            replies = routed.get("replies", [])
            try:
                for r in replies:
                    await _send_reply(update, r)
            except Exception as e:
                print(f"Ops intake reply error: {e}")
                await update.message.reply_text("Ops update captured. (Reply formatting error — check logs.)")
            return

        if intent == "album_continue":
            replies = routed.get("replies", [])
            for r in replies:
                r = validate_reply(text, r, intent)
                await _send_reply(update, r, source_request=text)
            # Deferred ops delivery — fires once when album session closes
            try:
                from chief_session_manager import load_session as _ls
                from chief_ops_brain import deferred_summary
                if _ls().get("status") != "active":
                    summary = deferred_summary()
                    if summary:
                        for s in summary:
                            await _send_reply(update, s)
            except Exception:
                pass
            return

        if intent == "album_arc_start":
            try:
                from chief_album_brain import handle_arc
                arc_replies = handle_arc("")
                for r in arc_replies:
                    r = validate_reply(text, r, "album_arc_start")
                    await _send_reply(update, r, source_request=text)
            except Exception as e:
                await _send_reply(update, f"Arc analysis error: {e}", source_request=text)
            return

        if intent == "album_arc_continue":
            replies = routed.get("replies", [])
            for r in replies:
                r = validate_reply(text, r, intent)
                await _send_reply(update, r, source_request=text)
            return

        if intent == "quick_song_update":
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent == "system_report":
            replies = routed.get("replies", [])
            for r in replies:
                r = validate_reply(text, r, intent)
                await _send_reply(update, r, source_request=text)
            return

        if intent in ("scout_report", "integration_proposals", "reflection_report"):
            replies = routed.get("replies", [])
            for r in replies:
                r = validate_reply(text, r, intent)
                await _send_reply(update, r, source_request=text)
            return

        if intent in ("content_calendar", "brand_guide"):
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent in ("marketing_ideas", "content_draft", "content_log_update"):
            replies = routed.get("replies", [])
            for r in replies:
                r = validate_reply(text, r, intent)
                await _send_reply(update, r, source_request=text)
            return

        if intent in ("email_draft", "email_send"):
            replies = routed.get("replies", [])
            for r in replies:
                r = validate_reply(text, r, intent)
                await _send_reply(update, r, source_request=text)
            return

        if intent in ("sms_draft", "sms_send"):
            replies = routed.get("replies", [])
            for r in replies:
                r = validate_reply(text, r, intent)
                await _send_reply(update, r, source_request=text)
            return

        if intent == "phone_log":
            replies = routed.get("replies", [])
            for r in replies:
                r = validate_reply(text, r, intent)
                await _send_reply(update, r, source_request=text)
            return

        if intent in ("cpa_query", "musiclaw_query", "publishing_query"):
            replies = routed.get("replies", [])
            for r in replies:
                r = validate_reply(text, r, intent)
                await _send_reply(update, r, source_request=text)
            return

        if intent in ("website_qa", "website_coordinator", "website_creative"):
            replies = routed.get("replies", [])
            for r in replies:
                r = validate_reply(text, r, intent)
                await _send_reply(update, r, source_request=text)
            return

        if intent == "backup_status":
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent in ("financial_report", "analytics_report", "goals_check", "momentum_check"):
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent == "trinity_check":
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent in ("calendar_query", "queue_request"):
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent == "scheduler":
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent in ("brainstorm_capture", "brainstorm_watch", "brainstorm_queue"):
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent == "focus_status":
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent == "choice_response":
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent == "mix_brief":
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent == "stack_restart":
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent == "fundo_release":
            replies = routed.get("replies", [])
            for r in replies:
                r = validate_reply(text, r, intent)
                await _send_reply(update, r, source_request=text)
            return

        if intent in ("fundo_session", "fundo_identity"):
            replies = routed.get("replies", [])
            for r in replies:
                r = validate_reply(text, r, intent)
                await _send_reply(update, r, source_request=text)
            return

        if intent == "hitl_decision":
            replies = routed.get("replies", [])
            for r in replies:
                await _send_reply(update, r)
            return

        if intent == "generic":
            replies = routed.get("replies", [])
            if replies:
                for r in replies:
                    await _send_reply(update, r)
                return

        formatted = f"[PHONE][{timestamp}] {text}"

        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")
            await _send_reply(
                update,
                reply or "I didn't catch a specific action there. Try rephrasing.",
                source_request=text,
            )
        except Exception as e:
            print(f"Routing error: {e}")
            await update.message.reply_text("Routing error.")
    except Exception as e:
        print(f"[chief_listener] dispatch error (intent={intent}): {e}", flush=True)
        await update.message.reply_text("Chief hit a snag on that. Try again.")


async def handle_callback(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses for choice prompts."""
    query = update.callback_query
    if not query or query.from_user.id != AUTHORIZED_USER_ID:
        return
    if not claim_listener_update(update, role="chief", source_channel="chief_listener"):
        return
    await query.answer()  # dismiss the loading spinner
    callback_data = query.data or ""
    try:
        from chief_approval_bridge import has_pending_choice, handle as bridge_handle
        if has_pending_choice():
            replies = bridge_handle(callback_data)
            for r in replies:
                await query.message.reply_text(
                    _final_operator_text(r, source_request=callback_data)
                )
        else:
            await query.message.reply_text("No pending choice.")
    except Exception as e:
        print(f"[chief_listener] callback error: {e}", flush=True)
        await query.message.reply_text("Button response error.")


# ── Startup: notify about pending queue items (once per unique queue state) ───
_QUEUE_NOTIF_STATE = Path("/mnt/c/OpenClaw/logs/queue_notif_state.json")


def _queue_content_hash(items: list[str]) -> str:
    return hashlib.md5("\n".join(items).encode()).hexdigest()


def _load_queue_notif_state() -> dict:
    if _QUEUE_NOTIF_STATE.exists():
        try:
            return json.loads(_QUEUE_NOTIF_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_queue_notif_state(content_hash: str) -> None:
    _QUEUE_NOTIF_STATE.parent.mkdir(parents=True, exist_ok=True)
    _QUEUE_NOTIF_STATE.write_text(
        json.dumps({"hash": content_hash, "sent_at": datetime.now().isoformat()}, indent=2),
        encoding="utf-8",
    )


async def _post_startup_queue(application):
    pending = check_pending_queue()
    if not pending:
        return

    current_hash = _queue_content_hash(pending)
    last_state   = _load_queue_notif_state()

    # Suppress if the queue content is identical to the last notification sent
    if last_state.get("hash") == current_hash:
        print(f"Queue startup: {len(pending)} pending item(s) unchanged — suppressing repeat notification.")
        return

    _save_queue_notif_state(current_hash)

    lines = [f"📋 {len(pending)} pending queue item(s):\n"]
    for i, item in enumerate(pending, 1):
        lines.append(f"  {i}. {item}")
    lines.append("\nTell me which to work on, or 'queue status' to review.")
    try:
        safe_text = _final_operator_text(
            "\n".join(lines),
            source_request="",
        )
        await application.bot.send_message(
            chat_id=AUTHORIZED_USER_ID,
            text=safe_text,
        )
    except Exception as e:
        print(f"Queue startup notification failed: {e}")


def build_application():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.post_init = _post_startup_queue
    install_identity_preflight(application, "chief")
    return application


async def run_listener(application=None, stop_event: asyncio.Event | None = None) -> None:
    application = application or build_application()
    await run_verified_polling(application, "chief", stop_event=stop_event)


def main() -> None:
    print("[chief_listener] starting...", flush=True)
    asyncio.run(run_listener())


if __name__ == "__main__":
    main()
