"""
cassandra_listener.py

Standalone Telegram bot for Cassandra.
Handles all messages directly — no chief_router.
All text goes to cassandra_brain.handle().

Voice suppression
-----------------
Content/social/tweet-style requests stay text-only.
The user can explicitly request voice ("say this aloud", "read that out") to
override the suppression.
"""

import asyncio
import fcntl
import hashlib as _hashlib
import os
import time as _time
from pathlib import Path as _Path
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

from cassandra_brain import handle as cassandra_handle
from cassandra_voice import speak

_ROUTE_LOG = _Path("/mnt/c/OpenClaw/logs/route_log.csv")


def _log_cassandra_route(text: str, intent: str) -> None:
    """Log Cassandra routing decisions to shared route_log.csv."""
    try:
        msg_hash = _hashlib.sha256(text.encode()).hexdigest()[:8]
        needs_header = not _ROUTE_LOG.exists() or _ROUTE_LOG.stat().st_size == 0
        with open(_ROUTE_LOG, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                if needs_header:
                    f.write("timestamp,message_hash,intent,route_method,llm_fallback_used\n")
                ts = _time.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{ts},{msg_hash},{intent},cassandra_direct,False\n")
                f.flush()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception as e:
        print(f"[route_log] cassandra write error: {e}", flush=True)

BOT_TOKEN = os.environ["CASSANDRA_BOT_TOKEN"]
AUTHORIZED_USER_ID = int(os.environ["TELEGRAM_AUTHORIZED_USER_ID"])

# ── Content voice suppression ─────────────────────────────────────────────────

_CONTENT_PATTERNS = (
    "tweet", "post idea", "caption", "social", "content idea",
    "hashtag", "instagram", "write a ", "draft a ", "generate a ",
    "promo copy", "ad copy",
)

_VOICE_EXPLICIT = (
    "say this", "say that", "read this", "read that", "speak this",
    "out loud", "aloud", "read aloud",
)


def _suppress_voice(user_text: str) -> bool:
    """
    Return True if the user's message is a content/social request and they
    have NOT explicitly asked for voice output.
    """
    t = user_text.lower()
    if any(p in t for p in _VOICE_EXPLICIT):
        return False
    return any(p in t for p in _CONTENT_PATTERNS)


# ── Message handler ───────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != AUTHORIZED_USER_ID:
        return
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    try:
        replies = await asyncio.to_thread(cassandra_handle, text)
        for r in replies:
            await update.message.reply_text(r)
        _log_cassandra_route(text, "cassandra")
    except Exception as e:
        print(f"[cassandra_listener] error: {e}", flush=True)
        await update.message.reply_text("Something went quiet on my end. Try again.")
        return
    # Speak after all text replies — in a separate try so voice failures
    # don't send the fallback message to Telegram
    try:
        suppress = _suppress_voice(text)
        speak(" ".join(replies), suppress=suppress)
    except Exception as e:
        print(f"[cassandra_listener] voice error (suppressed): {e}", flush=True)


app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Cassandra online.", flush=True)
app.run_polling()
