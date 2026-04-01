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

Voice input (Whisper relay)
---------------------------
Telegram voice messages from the authorized user are transcribed with
openai-whisper via cassandra_whisper_relay.  Requires ffmpeg on PATH.
If ffmpeg is absent the handler logs a warning and replies with a prompt
to send the request as text instead.
"""

import asyncio
import fcntl
import hashlib as _hashlib
import os
import shutil
import tempfile
import time as _time
from pathlib import Path as _Path
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

from cassandra_brain import handle as cassandra_handle, is_designated_contact_sender
from cassandra_sender import send_voice_note
from cassandra_voice import speak, synthesize_for_voice_note
from cassandra_whisper_relay import relay_transcript, transcribe_audio

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
    sender_name = update.effective_user.full_name if update.effective_user else None
    sender_chat_id = update.effective_chat.id if update.effective_chat else None
    is_authorized_user = bool(update.effective_user and update.effective_user.id == AUTHORIZED_USER_ID)
    is_designated_contact = is_designated_contact_sender(
        sender_name=sender_name,
        sender_chat_id=sender_chat_id,
    )
    if not is_authorized_user and not is_designated_contact:
        return
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    try:
        replies = await asyncio.to_thread(
            cassandra_handle,
            text,
            {
                "sender_name": sender_name,
                "sender_chat_id": sender_chat_id,
            },
        )
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
        if not is_authorized_user:
            return
        suppress = _suppress_voice(text)
        speak(" ".join(replies), suppress=suppress)
        if not suppress:
            wav_path = synthesize_for_voice_note(" ".join(replies))
            if wav_path is not None:
                send_voice_note(str(wav_path), chat_id=str(sender_chat_id))
    except Exception as e:
        print(f"[cassandra_listener] voice error (suppressed): {e}", flush=True)


# ── Voice input handler (Whisper relay) ──────────────────────────────────────

_FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle Telegram voice messages from the authorized user.

    Downloads the OGG/Opus file, transcribes with openai-whisper, and
    passes the transcript through cassandra_whisper_relay for confidence
    checking, deduplication, and Cassandra command intake.
    """
    if not update.effective_user or update.effective_user.id != AUTHORIZED_USER_ID:
        return
    if not update.message or not update.message.voice:
        return

    if not _FFMPEG_AVAILABLE:
        print("[cassandra_listener] voice input skipped: ffmpeg not on PATH", flush=True)
        await update.message.reply_text(
            "Voice input needs ffmpeg installed. Send as text for now."
        )
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        ogg_path = os.path.join(tmp_dir, "voice.ogg")
        try:
            voice_file = await update.message.voice.get_file()
            await voice_file.download_to_drive(ogg_path)
        except Exception as e:
            print(f"[cassandra_listener] voice download error: {e}", flush=True)
            await update.message.reply_text("Could not download your voice message. Try again.")
            return

        try:
            transcript, confidence = await asyncio.to_thread(transcribe_audio, ogg_path)
        except Exception as e:
            print(f"[cassandra_listener] whisper transcription error: {e}", flush=True)
            await update.message.reply_text("Could not transcribe your message. Try again.")
            return

    if not transcript:
        await update.message.reply_text("I could not make out any words. Please try again.")
        return

    result = await asyncio.to_thread(relay_transcript, transcript, confidence)
    status = result["status"]

    if status == "rejected":
        reason = result["reason"]
        await update.message.reply_text(
            f"Could not process voice input ({reason}). Please resend or type it."
        )
        return

    if status == "duplicate":
        await update.message.reply_text("Got it — already processed that one.")
        return

    # accepted or flagged
    sender_chat_id = update.effective_chat.id if update.effective_chat else None
    for r in result["reply"]:
        await update.message.reply_text(r)

    if status == "flagged":
        await update.message.reply_text(
            f"(Low confidence transcript — {result['confidence']:.0%}. "
            "Say it again or type it if that was not right.)"
        )

    _log_cassandra_route(transcript, "whisper_relay")

    try:
        suppress = _suppress_voice(transcript)
        speak(" ".join(result["reply"]), suppress=suppress)
        if not suppress and result["reply"]:
            wav_path = synthesize_for_voice_note(" ".join(result["reply"]))
            if wav_path is not None:
                send_voice_note(str(wav_path), chat_id=str(sender_chat_id))
    except Exception as e:
        print(f"[cassandra_listener] voice reply error (suppressed): {e}", flush=True)


app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(MessageHandler(filters.VOICE, handle_voice))

print("Cassandra online.", flush=True)
app.run_polling()
