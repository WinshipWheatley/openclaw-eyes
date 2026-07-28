import asyncio
import contextvars
import hashlib
import json
import os
import sys
import first_touch_decision
from agent_introspection import (
    answer_agent_introspection,
    classify_agent_introspection,
)
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from scripts.producer_telegram_route import extract_producer_payload, truncate_producer_output
from telegram_agent_intake import claim_listener_update, record_telegram_listener_update_safe
from telegram_listener_integrity import (
    install_identity_preflight,
    resolve_role_bot_token,
    run_verified_polling,
)
from telegram_receipt_adapter import (
    contract_delivery_descriptor,
    register_operator_text_delivery_v2,
    register_telegram_delivery,
    render_verified_receipt_reply,
    resolve_telegram_receipt_request,
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
_OUTPUT_BOUNDARY_RECEIPT: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "niles_output_boundary_receipt",
    default=None,
)
_TYPED_CONTRACT_RECEIPT: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "niles_typed_contract_receipt",
    default=None,
)
_AGENT_INTROSPECTION_PROOF: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "niles_agent_introspection_proof",
    default=None,
)


def current_output_boundary_receipt() -> dict | None:
    receipt = _OUTPUT_BOUNDARY_RECEIPT.get()
    return dict(receipt) if isinstance(receipt, dict) else None


def current_typed_contract_receipt() -> dict | None:
    receipt = _TYPED_CONTRACT_RECEIPT.get()
    return dict(receipt) if isinstance(receipt, dict) else None


def current_agent_introspection_proof() -> dict | None:
    proof = _AGENT_INTROSPECTION_PROOF.get()
    return dict(proof) if isinstance(proof, dict) else None


async def _answer_niles_agent_introspection(
    text: str,
    *,
    source_request_id: str = "",
):
    match = classify_agent_introspection(text, addressed_agent="niles")
    if match is None:
        return None
    return await asyncio.to_thread(
        answer_agent_introspection,
        text,
        agent="niles",
        source_surface="niles_producer_listener",
        source_request_id=source_request_id,
        session={"source_message_id": source_request_id},
        match=match,
    )


def _final_operator_reply(reply: str, *, source_request: str) -> str:
    try:
        from operator_surface_guard import guard_operator_reply_with_receipt

        bounded = guard_operator_reply_with_receipt(
            str(reply or ""),
            agent_role="NILES",
            source_request=source_request,
        )
        _OUTPUT_BOUNDARY_RECEIPT.set(bounded.receipt.to_dict())
        # Niles is the agent that answered a technical exact-send question with
        # "What's the main goal: groove, melody, or arrangement?" — so this funnel
        # is where question dominance matters most.
        from agent_reply_egress import finalize_agent_reply

        return finalize_agent_reply("niles", bounded.visible_text,
                                    question=source_request)
    except Exception:
        _OUTPUT_BOUNDARY_RECEIPT.set({
            "outcome": "adapter_boundary_error",
            "raw_control_text_included": False,
        })
        return "Niles couldn't safely render that answer just now. Nothing was sent or changed."

async def _telegram_typing_loop(bot, chat_id: int | None) -> None:
    if chat_id is None:
        return
    while True:
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception as exc:
            print(f"[niles_listener] typing indicator error: {exc}", flush=True)
        await asyncio.sleep(4.0)

async def _run_producer_intake(payload: str, *, first_touch_receipt=None) -> str:
    """Executes producer_intake.py and returns the output."""
    try:
        command = [
            "python3",
            "/home/openclaw/scripts/producer_intake.py",
            "--text",
            payload,
            "--human-only",
        ]
        if first_touch_decision.valid_pass_through_marker(
            first_touch_receipt,
            text=payload,
            agent="niles",
        ):
            command.extend(
                ["--first-touch-receipt-json", json.dumps(dict(first_touch_receipt), sort_keys=True)]
            )
        proc = await asyncio.create_subprocess_exec(
            *command,
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


def _apply_niles_grounded_fallback(result: str, text: str) -> str:
    """Answer from Niles' own knowledge when intake could not route.

    Logic lives in niles_context_grounding so it stays testable without the
    Telegram runtime. Strictly an upgrade of a dead end: with no relevant
    knowledge, or on failure, the original honest reply is returned untouched.
    """
    try:
        from niles_context_grounding import apply_grounded_fallback

        return apply_grounded_fallback(result, text)
    except Exception:
        return result


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
    _TYPED_CONTRACT_RECEIPT.set(None)
    effective_chat = getattr(update, "effective_chat", None)
    chat_id = effective_chat.id if effective_chat else AUTHORIZED_USER_ID
    delivery_source_message_id = str(getattr(update.message, "message_id", "") or "")
    source_binding = hashlib.sha256(
        f"niles|{chat_id}|{delivery_source_message_id}".encode("utf-8")
    ).hexdigest()[:12]
    source_request_id = (
        f"niles_telegram_{delivery_source_message_id}_{source_binding}"
    )

    async def _reply_text(reply_text: str, **kwargs):
        delivered = await update.message.reply_text(reply_text, **kwargs)
        try:
            register_operator_text_delivery_v2(
                delivered_text=reply_text,
                source_request_id=source_request_id,
                chat_id=chat_id,
                source_message_id=delivery_source_message_id,
                delivered_message=delivered,
                effective_service="niles-listener.service",
                effective_surface="niles_producer_listener",
                effective_bot_identity="niles",
                token_owner_label="NILES_BOT_TOKEN",
                bot_token=BOT_TOKEN,
                response_author="niles",
                carrier_identity="niles",
            )
        except Exception as exc:
            print(
                f"[producer_listener] v2 delivery receipt skipped: {type(exc).__name__}",
                flush=True,
            )
        return delivered
    try:
        receipt_resolution = resolve_telegram_receipt_request(
            text,
            surface="niles_producer_listener",
            bot_identity="niles",
            chat_id=chat_id,
            message=update.message,
        )
    except Exception as exc:
        print(f"[producer_listener] receipt lookup failed: {type(exc).__name__}", flush=True)
        await _reply_text(_final_operator_reply(
            "The receipt index is unavailable right now. No send, workflow, model, tool, "
            "ledger, payment, or external action ran.",
            source_request=text,
        ))
        return
    if receipt_resolution is not None:
        await _reply_text(
            _final_operator_reply(receipt_resolution.text, source_request=text)
        )
        return

    trace_source_message_id = str(getattr(update, "update_id", "") or "")
    first_touch = first_touch_decision.attempt_first_touch(
        text,
        agent="niles",
        surface="niles_producer_listener",
    )
    if first_touch.handled and first_touch.decision is not None:
        reply = _final_operator_reply(
            first_touch.decision.reply,
            source_request=text,
        )
        await _reply_text(reply)
        return

    record_telegram_listener_update_safe(
        text=text,
        source_channel="niles_producer_listener",
        agent_target="niles",
        source_message_id=trace_source_message_id or None,
        source_user_label="operator",
        operator_message=True,
        route_intent=True,
    )

    _introspection_answer = await _answer_niles_agent_introspection(
        text,
        source_request_id=f"niles:{trace_source_message_id}",
    )
    if _introspection_answer is not None:
        _AGENT_INTROSPECTION_PROOF.set(
            dict(_introspection_answer.machine_proof)
        )
        await update.message.reply_text(
            _final_operator_reply(
                _introspection_answer.text,
                source_request=text,
            )
        )
        return

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
                source_message_id=trace_source_message_id,
            ),
            status_renderer=build_niles_bare_status_answer,
            semantic_vote_enabled=semantic_vote_enabled_for_adapter("niles", default=True),
            first_touch_receipt=first_touch.receipt if first_touch.attempted else None,
        )
    except Exception:
        _typed = None
    _timeout_reply = None
    if _typed is not None and not _typed.handled:
        try:
            from vote_timeout_clarification import warm_clarification_for_vote_timeout

            _timeout_reply = warm_clarification_for_vote_timeout(text, _typed)
        except Exception:
            _timeout_reply = None
    if _typed is not None and (_typed.handled or _timeout_reply is not None):
        _typed_reply = str(_timeout_reply or _typed.reply or "")
        _TYPED_CONTRACT_RECEIPT.set(_typed.receipt.to_dict())
        try:
            _typed_descriptor = contract_delivery_descriptor(
                _typed.receipt.to_dict(),
                actor="niles",
                surface="niles_producer_listener",
            )
        except Exception as exc:
            print(f"[producer_listener] contract receipt skipped: {type(exc).__name__}", flush=True)
            _typed_descriptor = None
        _typed_reply = render_verified_receipt_reply(
            _typed_reply,
            _typed_descriptor,
            raw_ref=str(getattr(_typed.receipt, "receipt_pointer", "") or ""),
        )
        _typed_reply = _final_operator_reply(_typed_reply, source_request=text)
        try:
            from vote_timeout_clarification import enforce_vote_timeout_output

            _enforced_reply = enforce_vote_timeout_output(
                text,
                _typed_reply,
                _typed,
            )
            if _enforced_reply != _typed_reply:
                _typed_reply = _final_operator_reply(
                    _enforced_reply,
                    source_request=text,
                )
                _enforced_reply = enforce_vote_timeout_output(
                    text,
                    _typed_reply,
                    _typed,
                )
            _typed_reply = _enforced_reply
        except Exception:
            pass
        delivered_message = await _reply_text(_typed_reply)
        try:
            register_telegram_delivery(
                _typed_descriptor,
                surface="niles_producer_listener",
                bot_identity="niles",
                chat_id=chat_id,
                source_message_id=delivery_source_message_id,
                delivered_message=delivered_message,
            )
        except Exception as exc:
            print(
                f"[producer_listener] delivered receipt index skipped: {type(exc).__name__}",
                flush=True,
            )
        # A timeout clarification is one bounded text response, not a second
        # voice delivery or another interpretation attempt.
        if _timeout_reply is None:
            _fire_agent_voice("niles", _typed_reply, update)
        return

    # ── Refusal-first guard (task 141) — FIRST tap, before the producer
    # intake subprocess (no model, no timeout). "wipe the X32" refuses with
    # the gate named; scene/session/take housekeeping ("wipe the X32 scene")
    # never matches and flows to the normal intake path.
    refusal = None if first_touch.attempted else _operator_refusal_reply(text)
    if refusal is not None:
        refusal = _final_operator_reply(refusal, source_request=text)
        await _reply_text(refusal)
        _fire_agent_voice("niles", refusal, update)
        return

    if text.lower() in ("/start", "/help"):
        await _reply_text(
            _final_operator_reply("Niles online. Producer intake active.", source_request=text)
        )
        return

    if _is_bare_status_query(text):
        status_reply = _final_operator_reply(
            build_niles_bare_status_answer(),
            source_request=text,
        )
        await _reply_text(status_reply)
        _fire_agent_voice("niles", status_reply, update)
        return

    _queue_for_memory(text)  # feed Niles persistent memory only after contract decisions

    # Direct input
    typing_task = asyncio.create_task(_telegram_typing_loop(context.bot, update.effective_chat.id))
    try:
        try:
            result = await _run_producer_intake(
                text,
                first_touch_receipt=first_touch.receipt if first_touch.attempted else None,
            )
        except TypeError as exc:
            if "first_touch_receipt" not in str(exc):
                raise
            result = await _run_producer_intake(text)
        result = _apply_niles_grounded_fallback(result, text)
        result = _final_operator_reply(result, source_request=text)
        await _reply_text(result)
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
