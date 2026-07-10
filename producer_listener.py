import asyncio
import os
import sys
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from scripts.producer_telegram_route import extract_producer_payload, truncate_producer_output
from telegram_agent_intake import claim_listener_update, record_telegram_listener_update_safe
from telegram_listener_integrity import (
    install_identity_preflight,
    resolve_role_bot_token,
    run_verified_polling,
)

# Environment setup
BOT_TOKEN = resolve_role_bot_token("niles")
AUTHORIZED_USER_ID = os.environ.get("TELEGRAM_AUTHORIZED_USER_ID") or os.environ.get("PRODUCER_AUTHORIZED_USER_ID")

if not AUTHORIZED_USER_ID:
    print("TELEGRAM_AUTHORIZED_USER_ID must be set for Niles.", file=sys.stderr)
    sys.exit(1)
if not os.environ.get("TELEGRAM_AUTHORIZED_USER_ID") and os.environ.get("PRODUCER_AUTHORIZED_USER_ID"):
    print(
        "[niles_listener] LOUD WARNING: PRODUCER_AUTHORIZED_USER_ID is a legacy alias; "
        "configure TELEGRAM_AUTHORIZED_USER_ID for the shared operator identity.",
        file=sys.stderr,
    )

AUTHORIZED_USER_ID = int(AUTHORIZED_USER_ID)

async def _telegram_typing_loop(bot, chat_id: int | None) -> None:
    if chat_id is None:
        return
    while True:
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception as exc:
            print(f"[niles_listener] typing indicator error: {exc}", flush=True)
        await asyncio.sleep(4.0)

async def _run_producer_intake(payload: str) -> str:
    """Executes producer_intake.py and returns the output."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3",
            "/home/openclaw/scripts/producer_intake.py",
            "--text",
            payload,
            "--human-only",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20.0)
            if proc.returncode != 0:
                return f"❌ Producer error: {stderr.decode().strip() or 'Unknown failure'}"
            output = stdout.decode().strip()
            if not output:
                return "Producer returned no output."
            return truncate_producer_output(output)
        except asyncio.TimeoutError:
            proc.terminate()
            return "❌ Producer request timed out."
    except Exception as e:
        return f"❌ Producer system error: {str(e)}"

NILES_QUEUE_LOG = "/mnt/c/OpenClaw/logs/niles_queue.log"


def _queue_for_memory(text: str) -> None:
    """Append operator intake to the niles queue so niles_memory_worker tails it
    into persistent memory. Best-effort: never raises, never blocks intake."""
    try:
        os.makedirs("/mnt/c/OpenClaw/logs", exist_ok=True)
        with open(NILES_QUEUE_LOG, "a", encoding="utf-8") as f:
            f.write(text.replace("\n", " ").strip() + "\n")
    except Exception:
        pass


def _fire_agent_voice(agent: str, text: str, update) -> None:
    """Fire-and-forget Kokoro voice note (Niles=am_puck), non-blocking + fail-soft.
    Toggle with OPENCLAW_AGENT_VOICE_NOTES=0."""
    try:
        import os
        import asyncio as _aio
        import agent_voice_sender

        if os.environ.get("OPENCLAW_AGENT_VOICE_NOTES", "1").strip().lower() not in ("1", "true", "yes"):
            return
        chat_id = getattr(getattr(update, "message", None), "chat_id", None)
        _aio.get_event_loop().run_in_executor(
            None, lambda: agent_voice_sender.send_agent_voice_note(agent, text, chat_id=chat_id)
        )
    except Exception as exc:  # never break a text reply on a voice issue
        print(f"[producer_listener] {agent} voice note skipped: {exc}", flush=True)


def _operator_refusal_reply(text: str) -> str | None:
    """Task 141 refusal-first tap. Fail-open: guard errors never block Niles."""
    try:
        from operator_refusal_guard import refusal_reply_for_text

        return refusal_reply_for_text(text, agent="niles", surface="niles_producer_listener")
    except Exception:
        return None


# Task 143 (CLASS #4): bare-status doctrine. A bare "status?" gets a short, current,
# Niles-scoped answer (studio/rig state + tracks in flight) -- no model call, no network
# ping (a live X32 ping could hang past the shared <5s budget), distinct from the normal
# production-intent parser (which has zero status awareness and would treat "status" as an
# unrecognized production question).
_BARE_STATUS_PHRASES = frozenset(
    {
        "status",
        "status update",
        "status check",
        "status please",
        "quick status",
        "whats the status",
        "what is the status",
        "give me a status",
        "give me a status update",
    }
)
_NILES_TRACK_REGISTRY_STALE_SLA_DAYS = 30


def _is_bare_status_query(text: str) -> bool:
    stripped = str(text or "").strip().rstrip("?!.").strip()
    normalized = stripped.lower().replace("'", "")
    normalized = " ".join(normalized.split())
    return normalized in _BARE_STATUS_PHRASES


def build_niles_bare_status_answer() -> str:
    from agent_contract_renderers import render_niles_status

    return render_niles_status()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != AUTHORIZED_USER_ID:
        return
    if not update.message or not update.message.text:
        return
    if not claim_listener_update(update, role="niles", source_channel="niles_producer_listener"):
        return

    text = update.message.text.strip()
    record_telegram_listener_update_safe(
        text=text,
        source_channel="niles_producer_listener",
        agent_target="niles",
        source_message_id=str(getattr(update, "update_id", "")) or None,
        source_user_label="operator",
        operator_message=True,
        route_intent=True,
    )

    # Task 151: typed contract before the memory queue and subprocess.  This is
    # the long-running listener defense; scripts/producer_intake.py mirrors it
    # so a stale listener still gets the same decision in the fresh subprocess.
    try:
        from typed_contract_decision import (
            ContractContext,
            decide_contract,
            semantic_vote_enabled_for_adapter,
        )

        _typed = decide_contract(
            text,
            context=ContractContext(
                agent="niles",
                surface="niles_producer_listener",
                source_message_id=str(getattr(update, "update_id", "") or ""),
            ),
            status_renderer=build_niles_bare_status_answer,
            semantic_vote_enabled=semantic_vote_enabled_for_adapter("niles", default=True),
        )
    except Exception:
        _typed = None
    if _typed is not None and _typed.handled:
        _typed_reply = str(_typed.reply or "")
        await update.message.reply_text(_typed_reply)
        _fire_agent_voice("niles", _typed_reply, update)
        return

    # ── Refusal-first guard (task 141) — FIRST tap, before the producer
    # intake subprocess (no model, no timeout). "wipe the X32" refuses with
    # the gate named; scene/session/take housekeeping ("wipe the X32 scene")
    # never matches and flows to the normal intake path.
    refusal = _operator_refusal_reply(text)
    if refusal is not None:
        await update.message.reply_text(refusal)
        _fire_agent_voice("niles", refusal, update)
        return

    if text.lower() in ("/start", "/help"):
        await update.message.reply_text("Niles online. Producer intake active.")
        return

    if _is_bare_status_query(text):
        status_reply = build_niles_bare_status_answer()
        await update.message.reply_text(status_reply)
        _fire_agent_voice("niles", status_reply, update)
        return

    _queue_for_memory(text)  # feed Niles persistent memory only after contract decisions

    # Direct input
    typing_task = asyncio.create_task(_telegram_typing_loop(context.bot, update.effective_chat.id))
    try:
        result = await _run_producer_intake(text)
        await update.message.reply_text(result)
        _fire_agent_voice("niles", result, update)
    finally:
        typing_task.cancel()

def build_application():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.COMMAND, handle_message))
    install_identity_preflight(application, "niles")
    return application


async def run_listener(application=None, stop_event: asyncio.Event | None = None) -> None:
    application = application or build_application()
    await run_verified_polling(application, "niles", stop_event=stop_event)


def main() -> None:
    print("Niles/Producer online.", flush=True)
    asyncio.run(run_listener())

if __name__ == "__main__":
    main()
