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
import json
import os
import shutil
import sys
import tempfile
import time as _time
from datetime import datetime
from pathlib import Path as _Path
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

from cassandra_brain import (
    handle as cassandra_handle,
    pin_telegram_chat_id,
)
from chief_cassandra_failure import investigate_cassandra_timeout
from cassandra_identity import (
    is_designated_contact_sender,
    find_contact_by_nickname,
)
from cassandra_sender import send_voice_note
from cassandra_voice import speak, synthesize_for_voice_note
from cassandra_whisper_relay import relay_transcript, transcribe_audio

_ROUTE_LOG = _Path("/mnt/c/OpenClaw/logs/route_log.csv")
_LISTENER_LOCK = _Path.home() / ".cassandra_listener.lock"
_LISTENER_LOCK_HANDLE = None
_REQUEST_TIMEOUT_S = 60
_WORKING_ACK_DELAY_S = 1.0
_WORKING_ON_IT = "Cassandra is working on it."
_ESCALATION_NOTICE = "Something isn't working. Chief is investigating and will send you what went wrong."
_APPROVAL_PENDING_PATH = _Path("/mnt/c/OpenClaw/logs/approval_pending.json")
_APPROVAL_WAIT_STALL_S = 300
_APPROVAL_WAIT_NOTICE = "Guardian approval is still pending. Once you approve or deny it, I'll continue."
_APPROVAL_STALLED_NOTICE = "Guardian approval is still pending longer than expected. Chief is investigating while I keep waiting for the result."
_CHAT_REQUEST_TOKENS: dict[int, int] = {}

# ── Tracking for identity pins ───────────────────────────────────────────────

_RECENT_SENDERS = {}  # sender_name.lower() -> chat_id (int)


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


def _acquire_listener_lock() -> None:
    global _LISTENER_LOCK_HANDLE
    try:
        handle = _LISTENER_LOCK.open("w")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _LISTENER_LOCK_HANDLE = handle
    except BlockingIOError:
        print("[cassandra_listener] another listener instance already owns polling; exiting.", flush=True)
        sys.exit(0)
    except Exception as exc:
        print(f"[cassandra_listener] failed to acquire listener lock: {exc}", flush=True)
        raise

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


def _normalize_message_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _should_use_timeout_contract(text: str, *, is_authorized_user: bool) -> bool:
    """
    Apply the timeout/escalation contract only to operator requests that are
    plausibly non-trivial. Keep quick pings and short acknowledgements quiet.
    """
    if not is_authorized_user:
        return False
    normalized = _normalize_message_text(text)
    if not normalized or normalized.startswith("pin chatid "):
        return False
    if normalized in {
        "hi", "hello", "hey", "thanks", "thank you", "ok", "okay",
        "are you online?", "are you online",
    }:
        return False
    if "\n" in text:
        return True
    if len(normalized) >= 48:
        return True
    return any(
        token in normalized
        for token in (
            " email ", " draft ", " send ", " status", "current ",
            "what is", "summarize", "summary", "verify", "check ",
            "look up", "find ", "calendar", "reply", "investigate",
            "capital hilton", "coupa", "invoice", "payment",
        )
    )


async def _run_cassandra_handle_async(text: str, session_meta: dict) -> list[str]:
    return await asyncio.to_thread(cassandra_handle, text, session_meta)


async def _trigger_chief_investigation_async(text: str, session_meta: dict) -> None:
    await asyncio.to_thread(investigate_cassandra_timeout, text, session_meta)


def _pending_cassandra_approval_state() -> tuple[str, dict]:
    try:
        data = json.loads(_APPROVAL_PENDING_PATH.read_text(encoding="utf-8"))
    except Exception:
        return "", {}
    if not data or data.get("status") != "pending":
        return "", {}
    action = str(data.get("action", ""))
    if not action.startswith("Google broker: cassandra →"):
        return "", {}
    requested_at = str(data.get("requested_at", "")).strip()
    if not requested_at:
        return "waiting", data
    try:
        age_s = (datetime.now() - datetime.strptime(requested_at, "%Y-%m-%d %H:%M:%S")).total_seconds()
    except Exception:
        return "waiting", data
    if age_s >= _APPROVAL_WAIT_STALL_S:
        return "stalled", data
    return "waiting", data


def _claim_chat_request(chat_id: int | None) -> int:
    if chat_id is None:
        return 0
    token = _CHAT_REQUEST_TOKENS.get(chat_id, 0) + 1
    _CHAT_REQUEST_TOKENS[chat_id] = token
    return token


def _is_current_chat_request(chat_id: int | None, token: int) -> bool:
    if chat_id is None:
        return True
    return _CHAT_REQUEST_TOKENS.get(chat_id) == token


async def _deliver_late_result(
    task: asyncio.Task,
    *,
    send_reply,
    should_deliver,
) -> None:
    try:
        replies = await task
    except Exception as exc:
        print(f"[cassandra_listener] late result error: {exc}", flush=True)
        return

    for reply in replies or []:
        if should_deliver():
            await send_reply(reply)


async def _send_delayed_status(
    *,
    message: str,
    delay_s: float,
    send_reply,
    should_deliver,
) -> None:
    await asyncio.sleep(max(0.0, delay_s))
    if should_deliver():
        await send_reply(message)


async def _run_request_with_timeout_contract(
    *,
    text: str,
    session_meta: dict,
    send_reply,
    is_authorized_user: bool,
    run_cassandra=_run_cassandra_handle_async,
    escalate_failure=_trigger_chief_investigation_async,
    should_deliver=lambda: True,
) -> list[str] | None:
    if not _should_use_timeout_contract(text, is_authorized_user=is_authorized_user):
        replies = await run_cassandra(text, session_meta)
        for reply in replies:
            if should_deliver():
                await send_reply(reply)
        return replies

    working_ack_task = asyncio.create_task(
        _send_delayed_status(
            message=_WORKING_ON_IT,
            delay_s=_WORKING_ACK_DELAY_S,
            send_reply=send_reply,
            should_deliver=should_deliver,
        )
    )
    task = asyncio.create_task(run_cassandra(text, session_meta))
    try:
        replies = await asyncio.wait_for(asyncio.shield(task), timeout=_REQUEST_TIMEOUT_S)
    except asyncio.TimeoutError:
        working_ack_task.cancel()
        if should_deliver():
            approval_state, _approval_data = _pending_cassandra_approval_state()
            if approval_state == "waiting":
                await send_reply(_APPROVAL_WAIT_NOTICE)
            else:
                if approval_state == "stalled":
                    await send_reply(_APPROVAL_STALLED_NOTICE)
                else:
                    await send_reply(_ESCALATION_NOTICE)
                asyncio.create_task(escalate_failure(text, session_meta))
        asyncio.create_task(_deliver_late_result(task, send_reply=send_reply, should_deliver=should_deliver))
        return None

    working_ack_task.cancel()
    for reply in replies:
        if should_deliver():
            await send_reply(reply)
    return replies


# ── Message handler ───────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_name = update.effective_user.full_name if update.effective_user else None
    sender_chat_id = update.effective_chat.id if update.effective_chat else None
    print(f"[chatid-pin] sender_name={sender_name!r} chat_id={sender_chat_id} user_id={update.effective_user.id if update.effective_user else None}", flush=True)

    # Record recent sender mapping for pinning
    if sender_name and sender_chat_id:
        _RECENT_SENDERS[sender_name.lower()] = sender_chat_id

    # Handle forwarded message metadata (forward_origin replaces forward_from in v20+)
    fwd_origin = getattr(update.message, "forward_origin", None) if update.message else None
    if fwd_origin and hasattr(fwd_origin, "sender_user") and fwd_origin.sender_user:
        f_name = fwd_origin.sender_user.full_name
        f_id = fwd_origin.sender_user.id
        if f_name:
            _RECENT_SENDERS[f_name.lower()] = f_id
            print(f"[chatid-pin] recorded forward: {f_name} -> {f_id}", flush=True)

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
    request_token = _claim_chat_request(sender_chat_id)

    async def _send_if_current(reply_text: str):
        if _is_current_chat_request(sender_chat_id, request_token):
            await update.message.reply_text(reply_text)

    # Admin: Pin chat_id to nickname
    if is_authorized_user and text.lower().startswith("pin chatid "):
        nickname = text[len("pin chatid "):].strip().lower()
        target_chat_id = None

        # Look up nickname names in _RECENT_SENDERS
        entry = find_contact_by_nickname(nickname)
        if entry:
            for sn in entry["sender_names"]:
                if sn in _RECENT_SENDERS:
                    target_chat_id = _RECENT_SENDERS[sn]
                    break

        if target_chat_id:
            if pin_telegram_chat_id(nickname, target_chat_id):
                await update.message.reply_text(f"✅ Pinned chat_id {target_chat_id} to nickname '{nickname}'.")
            else:
                await update.message.reply_text(f"❌ Failed to pin to nickname '{nickname}'. See logs.")
        else:
            await update.message.reply_text(
                f"❓ Could not find a recent message from anyone matching nickname '{nickname}'. "
                "Try forwarding a message from them first."
            )
        return

    try:
        replies = await _run_request_with_timeout_contract(
            text=text,
            session_meta={
                "sender_name": sender_name,
                "sender_chat_id": sender_chat_id,
            },
            send_reply=_send_if_current,
            is_authorized_user=is_authorized_user,
            should_deliver=lambda: _is_current_chat_request(sender_chat_id, request_token),
        )
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
        if not replies:
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


def main() -> None:
    _acquire_listener_lock()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    print("Cassandra online.", flush=True)
    app.run_polling()


if __name__ == "__main__":
    main()
