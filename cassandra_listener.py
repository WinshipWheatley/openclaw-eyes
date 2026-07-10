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

from scripts.producer_telegram_route import extract_producer_payload, truncate_producer_output
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
from listener_resilience import bounded_reply_timeout, clean_stale_carryover
from origin_bound_output import (
    GENERIC_SAFE_FAILURE,
    OriginBoundOutput,
    OriginDeliveryTracker,
    OutputOrigin,
    collect_origin_outputs,
    receipt_pointer,
)
from telegram_agent_intake import record_cassandra_listener_text_update

_ROUTE_LOG = _Path("/mnt/c/OpenClaw/logs/route_log.csv")
_LISTENER_LOCK = _Path.home() / ".cassandra_listener.lock"
_LISTENER_LOCK_HANDLE = None
# Task 146 rider: TWO 60s clocks raced with ZERO margin -- this outer clock (wraps ALL of
# handle() via bounded_reply_timeout) fired at the same instant as the inner 60s model-call
# lane, so under CPU-offload slowness the operator saw the LISTENER degrade and the
# self-heal blamed the wrong layer. Staggered to inner (60s) + grounded-work margin; the
# inner model lane stays 60s so the model path still times out FIRST and reports honestly.
_REQUEST_TIMEOUT_S = 90
_WORKING_ACK_DELAY_S = 1.0
_HEAVY_REQUEST_SEMAPHORE = asyncio.Semaphore(1)
_WORKING_ON_IT = "Cassandra is working on it."
_ESCALATION_NOTICE = (
    "Cassandra timed out before completing that request. I did not send or change anything. "
    "Chief is investigating and will report the exact failure."
)
_HANDLER_EXCEPTION_NOTICE = (
    "Cassandra hit an internal runtime error before completing that request. "
    "I did not send or change anything. Chief is investigating."
)
_DEGRADED_EMPTY_REPLY_NOTICE = (
    "I couldn't put together a good answer just now. Nothing was sent or changed. "
    "Try me again in a minute."
)
_BACKPRESSURE_NOTICE = (
    "Cassandra is degraded: a heavier request is already running, so I did not queue another model call. "
    "I did not send or change anything. I can still answer deterministic status, date, and capability questions."
)
_UNHANDLED_LISTENER_NOTICE = (
    "Cassandra hit a listener error before completing that request. "
    "I did not send or change anything. Chief is investigating."
)
_APPROVAL_PENDING_PATH = _Path("/mnt/c/OpenClaw/logs/approval_pending.json")
_APPROVAL_WAIT_STALL_S = 300
_APPROVAL_WAIT_NOTICE = "Guardian approval is still pending. Once you approve or deny it, I'll continue."
_APPROVAL_STALLED_NOTICE = "Guardian approval is still pending longer than expected. Chief is investigating while I keep waiting for the result."
_CHAT_REQUEST_TOKENS: dict[int, int] = {}
_TIMEOUT_SENTINEL = object()
_ORIGIN_DELIVERY_TRACKER = OriginDeliveryTracker()

# ── Producer integration ─────────────────────────────────────────────────────

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

# ── Tracking for identity pins ───────────────────────────────────────────────

_RECENT_SENDERS = {}  # sender_name.lower() -> chat_id (int)


def _identifier_digest(value: object | None) -> str:
    if value is None:
        return "none"
    return _hashlib.sha256(f"cassandra-listener-id:{value}".encode("utf-8")).hexdigest()[:12]


async def _telegram_typing_loop(bot, chat_id: int | None) -> None:
    if chat_id is None:
        return
    while True:
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception as exc:
            print(f"[cassandra_listener] typing indicator error: {exc}", flush=True)
        await asyncio.sleep(4.0)


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


def _lightweight_recovery_reply(text: str) -> list[str] | None:
    normalized = _normalize_message_text(text)
    if not normalized:
        return None
    if any(phrase in normalized for phrase in ("are you alive", "are you online", "are you stuck", "are you degraded")):
        return [
            "Cassandra is ALIVE but may be DEGRADED if a heavy model request is already running. "
            "I did not send or change anything."
        ]
    if "what is today's date" in normalized or "what's today's date" in normalized or "today's date" in normalized:
        return [f"Today is {datetime.now().strftime('%Y-%m-%d')}."]
    if any(phrase in normalized for phrase in ("what can you do", "capability", "capabilities")):
        return [
            "Cassandra can answer deterministic status, date, and capability questions while the model path is degraded. "
            "Send/money actions still require the normal guarded path."
        ]
    return None


def _try_invoice_cockpit(
    text: str,
    session_meta: dict | None = None,
    *,
    ops=None,
    store=None,
) -> list[OriginBoundOutput] | None:
    """Run the cockpit without giving it Telegram credentials.

    ``None`` means the cockpit did not claim the request.  A list (including a
    guarded failure output) means it did, and the bound Cassandra adapter owns the
    sole eventual send.
    """

    origin = OutputOrigin.from_session_meta(
        session_meta,
        default_surface="cassandra_telegram",
        default_bot_identity="cassandra",
    )
    try:
        from invoice_cockpit_session import handle_invoice_cockpit_message
        from invoice_cockpit_ops import RealCockpitOps, JsonSessionStore

        bound_ops = ops if ops is not None else RealCockpitOps(contact_name="", origin=origin)
        bound_store = store if store is not None else JsonSessionStore()
        result = handle_invoice_cockpit_message(
            text,
            ops=bound_ops,
            store=bound_store,
            # Task 142: scope the cockpit clarify session to THIS channel so it
            # can never intercept another surface's traffic (live lane-hostage).
            surface="cassandra_telegram",
        )
        if not result.get("handled"):
            return None
        outputs = collect_origin_outputs(result)
        if outputs:
            return outputs

        receipt = receipt_pointer("invoice-cockpit", origin, salt=text)
        if result.get("error"):
            operator_text = (
                "I couldn't prepare that invoice for review. Nothing was sent. "
                f"Receipt: {receipt}."
            )
        else:
            operator_text = (
                "The invoice workflow handled that step without running an unapproved send. "
                f"Receipt: {receipt}."
            )
        return [
            OriginBoundOutput.guarded_text(
                origin=origin,
                delivery_id=receipt,
                receipt_pointer=receipt,
                operator_text=operator_text,
                generic_text=GENERIC_SAFE_FAILURE,
                internal={"cockpit_result": result},
            )
        ]
    except Exception as exc:
        receipt = receipt_pointer("invoice-cockpit", origin, salt=text)
        return [
            OriginBoundOutput.guarded_text(
                origin=origin,
                delivery_id=receipt,
                receipt_pointer=receipt,
                operator_text=(
                    "I couldn't prepare that invoice for review. Nothing was sent. "
                    f"Receipt: {receipt}."
                ),
                generic_text=GENERIC_SAFE_FAILURE,
                internal={"exception_type": type(exc).__name__, "exception": str(exc)},
            )
        ]


def _operator_refusal_reply(text: str) -> str | None:
    """Task 141 refusal-first tap. Fail-open: guard errors never block Cassandra."""
    try:
        from operator_refusal_guard import refusal_reply_for_text

        return refusal_reply_for_text(text, agent="cassandra", surface="cassandra_listener")
    except Exception:
        return None


async def _run_cassandra_handle_async(
    text: str,
    session_meta: dict,
) -> list[str | OriginBoundOutput]:
    # ── Refusal-first guard (task 141) — FIRST tap, before the invoice-cockpit
    # clarify session and before cassandra_brain.handle (so a destructive or
    # money-movement bait can never be eaten by a clarify session or time out
    # in the model path). Legitimate work ("delete that draft", "prepare the
    # St Anne's invoice for my review") never matches and flows on untouched.
    refusal = _operator_refusal_reply(text)
    if refusal is not None:
        return [refusal]
    # IB-3: helpers return transport-neutral outputs; only this listener's bound
    # adapter may deliver them.
    cockpit_outputs = await asyncio.to_thread(_try_invoice_cockpit, text, session_meta)
    if cockpit_outputs is not None:
        return cockpit_outputs
    return await asyncio.to_thread(cassandra_handle, text, session_meta)


async def _run_cassandra_with_backpressure(run_cassandra, text: str, session_meta: dict) -> list[str]:
    async with _HEAVY_REQUEST_SEMAPHORE:
        return await run_cassandra(text, session_meta)


async def _trigger_chief_investigation_async(text: str, session_meta: dict):
    return await asyncio.to_thread(investigate_cassandra_timeout, text, session_meta)


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

    await _send_reply_batch_or_degraded(
        replies,
        send_reply=send_reply,
        should_deliver=should_deliver,
    )


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


def _telegram_reply_markup(markup):
    if not markup:
        return None
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        rows = []
        for row in markup.get("inline_keyboard", []):
            rows.append(
                [
                    InlineKeyboardButton(
                        text=str(button.get("text") or ""),
                        callback_data=str(button.get("callback_data") or ""),
                    )
                    for button in row
                ]
            )
        return InlineKeyboardMarkup(rows)
    except Exception:
        # Test doubles may not expose Telegram's markup classes.  Keeping the
        # transport-neutral shape is safer than falling back to a global bot.
        return markup


async def _dispatch_origin_bound_output(
    output: OriginBoundOutput,
    *,
    bound_origin: OutputOrigin,
    send_text,
    send_document,
    tracker: OriginDeliveryTracker = _ORIGIN_DELIVERY_TRACKER,
) -> bool:
    """Verify, deduplicate, and deliver through one already-bound adapter."""

    if not tracker.claim(output, bound_origin=bound_origin):
        return False

    try:
        visible = output.visible_text()
        if output.kind == "document" and output.origin.is_operator:
            if not output.document_path or not _Path(output.document_path).is_file() or send_document is None:
                await send_text(
                    "I couldn't attach the prepared invoice. Nothing was sent. "
                    f"Receipt: {output.receipt_pointer}.",
                    reply_markup=None,
                )
            else:
                await send_document(output.document_path, visible)
            return True

        reply_markup = (
            _telegram_reply_markup(output.reply_markup)
            if output.origin.is_operator and output.reply_markup
            else None
        )
        await send_text(visible, reply_markup=reply_markup)
        return True
    except Exception:
        # A failed transport attempt is not a delivery.  Let a replay retry;
        # only a completed bound send is suppressed as a duplicate.
        tracker.release(output)
        raise


async def _escalate_failure_and_deliver(
    *,
    text: str,
    session_meta: dict,
    escalate_failure,
    send_reply,
    should_deliver,
    fallback_text: str,
) -> None:
    try:
        diagnosis = await escalate_failure(text, session_meta)
    except Exception as exc:
        print(
            f"[cassandra_listener] failure investigation error: {type(exc).__name__}",
            flush=True,
        )
        diagnosis = None
    if not should_deliver():
        return
    output = getattr(diagnosis, "output", None)
    if isinstance(output, OriginBoundOutput):
        print(
            f"[cassandra_listener] origin-bound failure receipt={output.receipt_pointer}",
            flush=True,
        )
        await send_reply(output)
    else:
        await send_reply(fallback_text)


def _is_generic_quiet_reply(reply: str) -> bool:
    normalized = " ".join(str(reply or "").lower().split())
    return "something went quiet" in normalized or "quiet on my end" in normalized


async def _send_reply_batch_or_degraded(
    replies,
    *,
    send_reply,
    should_deliver,
) -> list[str]:
    delivered: list[str] = []
    for reply in replies or []:
        if isinstance(reply, OriginBoundOutput):
            if should_deliver():
                await send_reply(reply)
                delivered.append(reply.visible_text())
            continue
        text = str(
            clean_stale_carryover(
                reply,
                failure_text=_DEGRADED_EMPTY_REPLY_NOTICE,
            )
            or ""
        ).strip()
        if not text or _is_generic_quiet_reply(text):
            continue
        if should_deliver():
            await send_reply(text)
            delivered.append(text)
    if not delivered and should_deliver():
        await send_reply(_DEGRADED_EMPTY_REPLY_NOTICE)
    return delivered


async def _run_request_with_timeout_contract(
    *,
    text: str,
    session_meta: dict,
    send_reply,
    is_authorized_user: bool,
    run_cassandra=_run_cassandra_handle_async,
    escalate_failure=_trigger_chief_investigation_async,
    should_deliver=lambda: True,
) -> list[str | OriginBoundOutput] | None:
    recovery_reply = _lightweight_recovery_reply(text)
    if _HEAVY_REQUEST_SEMAPHORE.locked() and recovery_reply is not None:
        await _send_reply_batch_or_degraded(
            recovery_reply,
            send_reply=send_reply,
            should_deliver=should_deliver,
        )
        return recovery_reply

    if not _should_use_timeout_contract(text, is_authorized_user=is_authorized_user):
        replies = await run_cassandra(text, session_meta)
        await _send_reply_batch_or_degraded(
            replies,
            send_reply=send_reply,
            should_deliver=should_deliver,
        )
        return replies

    if _HEAVY_REQUEST_SEMAPHORE.locked():
        if should_deliver():
            await send_reply(_BACKPRESSURE_NOTICE)
        return None

    working_ack_task = asyncio.create_task(
        _send_delayed_status(
            message=_WORKING_ON_IT,
            delay_s=_WORKING_ACK_DELAY_S,
            send_reply=send_reply,
            should_deliver=should_deliver,
        )
    )
    task = asyncio.create_task(_run_cassandra_with_backpressure(run_cassandra, text, session_meta))
    try:
        replies = await bounded_reply_timeout(
            asyncio.shield(task),
            timeout_seconds=_REQUEST_TIMEOUT_S,
            timeout_result=_TIMEOUT_SENTINEL,
            clean_result=False,
        )
        if replies is _TIMEOUT_SENTINEL:
            working_ack_task.cancel()
            if should_deliver():
                approval_state, _approval_data = _pending_cassandra_approval_state()
                if approval_state == "waiting":
                    await send_reply(_APPROVAL_WAIT_NOTICE)
                else:
                    asyncio.create_task(
                        _escalate_failure_and_deliver(
                            text=text,
                            session_meta=session_meta,
                            escalate_failure=escalate_failure,
                            send_reply=send_reply,
                            should_deliver=should_deliver,
                            fallback_text=(
                                _APPROVAL_STALLED_NOTICE
                                if approval_state == "stalled"
                                else _ESCALATION_NOTICE
                            ),
                        )
                    )
            asyncio.create_task(_deliver_late_result(task, send_reply=send_reply, should_deliver=should_deliver))
            return None
    except Exception as exc:
        working_ack_task.cancel()
        print(f"[cassandra_listener] request runtime error: {exc}", flush=True)
        if should_deliver():
            asyncio.create_task(
                _escalate_failure_and_deliver(
                    text=text,
                    session_meta=session_meta | {"runtime_error": str(exc)},
                    escalate_failure=escalate_failure,
                    send_reply=send_reply,
                    should_deliver=should_deliver,
                    fallback_text=_HANDLER_EXCEPTION_NOTICE,
                )
            )
        return None

    working_ack_task.cancel()
    await _send_reply_batch_or_degraded(
        replies,
        send_reply=send_reply,
        should_deliver=should_deliver,
    )
    return replies


# ── Message handler ───────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_name = update.effective_user.full_name if update.effective_user else None
    sender_chat_id = update.effective_chat.id if update.effective_chat else None
    sender_user_id = update.effective_user.id if update.effective_user else None
    print(
        "[chatid-pin] "
        f"sender_name_present={str(bool(sender_name)).lower()} "
        f"chat_id_hash={_identifier_digest(sender_chat_id)} "
        f"user_id_hash={_identifier_digest(sender_user_id)}",
        flush=True,
    )

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
            print(
                "[chatid-pin] recorded forward "
                f"sender_name_present=true sender_id_hash={_identifier_digest(f_id)}",
                flush=True,
            )

    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if not text:
        return

    is_authorized_user = bool(update.effective_user and update.effective_user.id == AUTHORIZED_USER_ID)
    is_designated_contact = is_designated_contact_sender(
        sender_name=sender_name,
        sender_chat_id=sender_chat_id,
    )
    if is_authorized_user:
        source_user_label = "operator"
    elif is_designated_contact:
        source_user_label = "designated_contact"
    else:
        source_user_label = "unverified_sender"

    record_cassandra_listener_text_update(
        text=text,
        source_message_id=str(getattr(update, "update_id", "")) or None,
        source_user_label=source_user_label,
        operator_message=is_authorized_user,
        route_intent=is_authorized_user,
    )
    if not is_authorized_user and not is_designated_contact:
        return

    request_token = _claim_chat_request(sender_chat_id)
    source_message_id = str(getattr(update, "update_id", "")) or ""
    session_meta = {
        "surface": "cassandra_telegram",
        "bot_identity": "cassandra",
        "sender_name": sender_name,
        "sender_chat_id": sender_chat_id,
        "source_message_id": source_message_id,
        "source_user_label": source_user_label,
    }
    bound_origin = OutputOrigin.from_session_meta(
        session_meta,
        default_surface="cassandra_telegram",
        default_bot_identity="cassandra",
    )

    async def _send_bound_text(reply_text: str, reply_markup=None):
        if reply_markup is None:
            await update.message.reply_text(reply_text)
        else:
            await update.message.reply_text(reply_text, reply_markup=reply_markup)

    async def _send_bound_document(document_path: str, caption: str):
        with _Path(document_path).open("rb") as document:
            await update.message.reply_document(document=document, caption=caption)

    async def _send_to_prompt(reply):
        if isinstance(reply, OriginBoundOutput):
            await _dispatch_origin_bound_output(
                reply,
                bound_origin=bound_origin,
                send_text=_send_bound_text,
                send_document=_send_bound_document,
            )
            return
        await _send_bound_text(str(reply), reply_markup=None)

    # Producer: Handle intake
    producer_payload = extract_producer_payload(text)
    if producer_payload:
        if not is_authorized_user:
            return
        if not producer_payload:
            await _send_to_prompt("Usage: /producer <message> or producer: <message>")
        else:
            typing_task = asyncio.create_task(_telegram_typing_loop(context.bot, sender_chat_id))
            try:
                result = await _run_producer_intake(producer_payload)
                await _send_to_prompt(result)
            finally:
                typing_task.cancel()
        return

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

    typing_task = asyncio.create_task(_telegram_typing_loop(context.bot, sender_chat_id))
    try:
        try:
            replies = await _run_request_with_timeout_contract(
                text=text,
                session_meta=session_meta,
                send_reply=_send_to_prompt,
                is_authorized_user=is_authorized_user,
                should_deliver=lambda: True,
            )
            _log_cassandra_route(text, "cassandra")
        except Exception as e:
            print(f"[cassandra_listener] error: {e}", flush=True)
            try:
                diagnosis = await _trigger_chief_investigation_async(
                    text,
                    session_meta | {"listener_error": str(e)},
                )
                await _send_to_prompt(diagnosis.output)
            except Exception:
                await _send_to_prompt(_UNHANDLED_LISTENER_NOTICE)
            return
    finally:
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass

    # Speak after all text replies — in a separate try so voice failures
    # don't send the fallback message to Telegram
    try:
        if not is_authorized_user:
            return
        if not replies:
            return
        text_replies = [str(reply) for reply in replies if not isinstance(reply, OriginBoundOutput)]
        if not text_replies:
            return
        suppress = _suppress_voice(text)
        speak(" ".join(text_replies), suppress=suppress)
        if not suppress:
            wav_path = synthesize_for_voice_note(" ".join(text_replies))
            if wav_path is not None:
                send_voice_note(str(wav_path), chat_id=str(sender_chat_id))
    except Exception as e:
        print(f"[VOICE_SIDE_EFFECT] cassandra_listener voice_reply_error: {e}", flush=True)


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
        print(f"[VOICE_SIDE_EFFECT] cassandra_listener voice_reply_error: {e}", flush=True)


def main() -> None:
    _acquire_listener_lock()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    print("Cassandra online.", flush=True)
    app.run_polling()


if __name__ == "__main__":
    main()
