import asyncio
import os
import sys
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from scripts.producer_telegram_route import extract_producer_payload, truncate_producer_output

# Environment setup
BOT_TOKEN = os.environ.get("PRODUCER_BOT_TOKEN")
AUTHORIZED_USER_ID = os.environ.get("PRODUCER_AUTHORIZED_USER_ID")

if not BOT_TOKEN or not AUTHORIZED_USER_ID:
    print("PRODUCER_BOT_TOKEN and PRODUCER_AUTHORIZED_USER_ID must be set.", file=sys.stderr)
    sys.exit(1)

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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != AUTHORIZED_USER_ID:
        return
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    
    if text.lower() in ("/start", "/help"):
        await update.message.reply_text("Niles online. Producer intake active.")
        return

    # Direct input
    typing_task = asyncio.create_task(_telegram_typing_loop(context.bot, update.effective_chat.id))
    try:
        result = await _run_producer_intake(text)
        await update.message.reply_text(result)
    finally:
        typing_task.cancel()

def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, handle_message))
    print("Niles/Producer online.", flush=True)
    app.run_polling()

if __name__ == "__main__":
    main()
