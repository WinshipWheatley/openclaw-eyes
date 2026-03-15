import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

from chief_router import route_message

LOG_PATH = Path("/mnt/c/OpenClaw/logs/chief_input.log")
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
AUTHORIZED_USER_ID = int(os.environ["TELEGRAM_AUTHORIZED_USER_ID"])


def extract_snapshot_name(output: str) -> str | None:
    m = re.search(r"inspection-\d{8}-\d{6}", output or "")
    return m.group(0) if m else None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTHORIZED_USER_ID:
        return

    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    routed = route_message(text)
    intent = routed.get("intent")
    reply = routed.get("reply")

    if intent == "inspection":
        try:
            result = subprocess.run(
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
            await update.message.reply_text(f"Inspection failed: {e}")
        return

    if intent == "cancel":
        await update.message.reply_text(reply or "Current workflow cancelled.")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    if intent == "billing_start":
        await update.message.reply_text(reply or "Ready.")
        return

    if intent == "billing_continue":
        replies = routed.get("replies", [])
        if replies:
            try:
                for r in replies:
                    await update.message.reply_text(r)
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

    if intent == "billing_continue":
        return

    formatted = f"[PHONE][{timestamp}] {text}"

    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
        await update.message.reply_text(reply or "Routed to Chief.")
    except Exception as e:
        print(f"Routing error: {e}")
        await update.message.reply_text("Routing error.")


app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Chief relay online.")
app.run_polling()
