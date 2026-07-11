"""
chief_guardian_listener.py

Dedicated approval response listener for the Guardian bot channel.

Primary path: Telegram inline tap buttons (Approve / Deny / Approve All).
Fallback path: Typed CODE DECISION format (e.g. "A3F2 1") — explicit fallback
  for cases where buttons are not delivered or not available.

Both paths enforce the same security guarantees:
  - TELEGRAM_AUTHORIZED_USER_ID check on every message/callback
  - Approval ID binding: the ID embedded in callback_data (buttons) or
    validated by parse_reply_code (typed) must match the active pending ID
  - record_decision() validates the bound ID before writing

Activation:
  Set GUARDIAN_BOT_TOKEN in .chief.env to a bot token distinct from
  CHIEF_BOT_TOKEN and CASSANDRA_BOT_TOKEN. Then start_chief.sh will
  launch this listener automatically.

  If GUARDIAN_BOT_TOKEN is not set, do NOT start this listener. The Chief
  listener handles approval responses in that case (existing behavior).

Role:
  Guardian = approval and safety-boundary control surface.
  Does not execute operational commands, Chief queries, or Cassandra queries.
  Outside a gate window, it gives deterministic safety/capability replies
  instead of collapsing every prompt into approval status.

Security:
  Accepts messages only from TELEGRAM_AUTHORIZED_USER_ID.
  All other senders are silently ignored.
"""

import asyncio
import os

import first_touch_decision
from telegram import Update, InlineKeyboardMarkup
from telegram.error import BadRequest as TelegramBadRequest, Forbidden as TelegramForbidden
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram_agent_intake import claim_listener_update, record_telegram_listener_update_safe
from telegram_listener_integrity import (
    install_identity_preflight,
    resolve_role_bot_token,
    run_verified_polling,
)
from chief_nonapproval_responder import guardian_no_pending_reply
from listener_resilience import clean_stale_carryover, honest_short_fail


def _operator_refusal_reply(text: str) -> str | None:
    """Task 141 refusal-first tap. Fail-open: guard errors never block replies."""
    try:
        from operator_refusal_guard import refusal_reply_for_text

        return refusal_reply_for_text(text, agent="guardian", surface="guardian_listener")
    except Exception:
        return None

# Guardian bot must be explicitly configured — this listener should not
# start on the Chief or Cassandra token.
BOT_TOKEN = resolve_role_bot_token("guardian")
AUTHORIZED_USER_ID = int(os.environ["TELEGRAM_AUTHORIZED_USER_ID"])
GUARDIAN_STALE_CARRYOVER_REPLY = honest_short_fail(
    "Guardian",
    no_action_line="No approval, denial, send, workflow execution, ledger post, payment, or external action occurred.",
    next_step="Retry after checking Guardian listener health and model contention.",
)


def guardian_resilient_reply(text: str) -> str:
    """Task 144 (CLASS #5): every Guardian Telegram reply in this listener flows through
    here (HITL typed-reply, no-pending status, malformed-decision Q&A, decision receipt) --
    the single choke point to guard the whole pipeline from one wrap."""
    cleaned = str(clean_stale_carryover(text, failure_text=GUARDIAN_STALE_CARRYOVER_REPLY))
    try:
        from operator_surface_guard import guard_operator_reply

        return guard_operator_reply(cleaned, agent_role="GUARDIAN")
    except Exception:
        return cleaned


def _fire_agent_voice(agent: str, text: str, update) -> None:
    """Fire-and-forget Kokoro voice note (Guardian=am_onyx), non-blocking + fail-soft.
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
        print(f"[chief_guardian_listener] {agent} voice note skipped: {exc}", flush=True)


def _build_no_pending_guardian_packet(question: str) -> dict:
    from guardian_context_packet import build_guardian_context_packet
    from packet_engine import build_agent_packet

    return build_agent_packet(
        agent="guardian",
        question=question,
        question_class="approval_posture_no_pending",
        legacy_builder=build_guardian_context_packet,
    )


def _log_no_pending_guardian_packet(packet: dict) -> None:
    receipt = packet.get("packet_engine_receipt") if isinstance(packet, dict) else None
    receipt_id = receipt.get("receipt_id") if isinstance(receipt, dict) else ""
    packet_id = packet.get("packet_id") if isinstance(packet, dict) else ""
    if packet_id or receipt_id:
        print(
            f"[guardian] no-pending context packet built packet_id={packet_id} receipt_id={receipt_id}",
            flush=True,
        )


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Primary approval path: handle inline button taps.

    Callback data format: 'DECISION:APPROVAL_ID' (e.g. 'YES:A3F2B8D1').
    The approval ID is bound at send time and validated here — stale button
    presses from a previous approval cycle are rejected by record_decision().
    """
    query = update.callback_query
    if not query:
        return

    # Auth check — only the authorized user's taps are processed.
    if not update.effective_user or update.effective_user.id != AUTHORIZED_USER_ID:
        return
    if not claim_listener_update(update, role="guardian", source_channel="guardian_listener"):
        return

    # Acknowledge the tap immediately to stop the Telegram loading spinner.
    await query.answer()

    # Null-safe original text: query.message may be None if the message was deleted
    # between send time and callback handling time.
    _orig = (query.message.text if query.message else "") or ""

    async def _update(text: str) -> None:
        """
        Edit the original approval message to show outcome and remove the keyboard.

        Known Telegram edit failure modes handled explicitly:
        - "message is not modified": content unchanged — no-op, no fallback needed.
        - BadRequest (deleted / not found / can't edit): log reason, fall back to send_message.
        - Forbidden (bot blocked / chat gone): log reason, no fallback (send_message would also fail).
        Other exceptions are re-raised so they surface in logs.
        """
        text = guardian_resilient_reply(text)
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([]))
        except TelegramBadRequest as e:
            _reason = str(e).lower()
            if "message is not modified" in _reason:
                # Edit is a no-op — content unchanged. Not an error; no fallback needed.
                return
            # Message unavailable (deleted, not found, can't edit) — log and fall back.
            print(
                f"[guardian] _update: BadRequest ({e.__class__.__name__}: {e}) "
                "— edit unavailable, falling back to send_message.",
                flush=True,
            )
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        except TelegramForbidden as e:
            # Bot was blocked or chat became unavailable — send_message would also fail.
            print(
                f"[guardian] _update: Forbidden ({e.__class__.__name__}: {e}) "
                "— bot blocked or chat unavailable, status update not delivered.",
                flush=True,
            )

    callback_data = query.data or ""
    if ":" not in callback_data:
        await _update(_orig + "\n\n[Invalid button data — no action taken.]")
        return

    decision_token, approval_id_from_cb = callback_data.split(":", 1)

    # ── HITL Action Approve/Deny (pending HITL action queue) ─────────────────
    if decision_token in {"HITL", "HITL_WHY"}:
        from hitl_notification_service import process_callback as _hitl_cb
        _approved_by = str(update.effective_user.id) if update.effective_user else "operator"
        _result = _hitl_cb(callback_data, approved_by=_approved_by)
        await _update(f"{_orig}\n\n{_result}")
        return

    # ── Build-request approval (polish-loop factory intake, Gap A) ────────────
    # Additive: only the BUILDOK/BUILDNO tokens reach here; existing approvals are
    # untouched. Wrapped so a polish_loop import hiccup can never crash the listener.
    if decision_token in {"BUILDOK", "BUILDNO"}:
        try:
            from polish_loop.build_request_intake import handle_build_approval
            from polish_loop.control_plane import ControlPlaneLedger

            _br = handle_build_approval(callback_data, ledger=ControlPlaneLedger())
            if _br["result"] == "approved":
                await _update(f"{_orig}\n\n✅ Approved — build queued (READY).")
            elif _br["result"] == "denied":
                await _update(f"{_orig}\n\n🛑 Denied — build request dropped.")
            else:
                await _update(f"{_orig}\n\n[Build request no longer actionable.]")
        except Exception as _exc:  # never crash the Guardian listener
            await _update(f"{_orig}\n\n[Build approval error: {type(_exc).__name__}]")
        return

    # ── Calendar delete approval (async Guardian-gated delete) ────────────────
    # Additive: only CALDEL/CALNO reach here. On Approve, fire the broker delete.
    if decision_token in {"CALDEL", "CALNO"}:
        try:
            from calendar_delete_approval import handle_calendar_delete_callback

            _cr = handle_calendar_delete_callback(callback_data)
            _title = _cr.get("title", "")
            if _cr["result"] == "deleted":
                await _update(f"{_orig}\n\n✅ Deleted “{_title}”.")
            elif _cr["result"] == "denied":
                await _update(f"{_orig}\n\n🛑 Kept “{_title}” — not deleted.")
            elif _cr["result"] == "expired":
                await _update(f"{_orig}\n\n[That delete request expired.]")
            elif _cr["result"] == "error":
                await _update(f"{_orig}\n\n[Delete failed: {_cr.get('error', '')}]")
            else:
                await _update(f"{_orig}\n\n[No longer actionable.]")
        except Exception as _exc:  # never crash the Guardian listener
            await _update(f"{_orig}\n\n[Calendar delete error: {type(_exc).__name__}]")
        return

    from chief_approval_brain import (
        record_decision, has_pending_approval, _load_pending, _save_pending, _is_hard_t2,
    )

    # ── WHY NOW? — informational; leaves original message and buttons intact ───
    if decision_token == "WHY":
        _pd = _load_pending()
        if not has_pending_approval() or _pd.get("id") != approval_id_from_cb:
            # Stale or expired — update the message (edit or fallback send).
            await _update(_orig + "\n\n[Expired] No matching pending approval.")
            return
        _action = _pd.get("action", "Unknown action")
        _requester = _pd.get("requester", "Unknown")
        _at = _pd.get("requested_at", "Unknown time")
        _risk = "Irreversible" if _is_hard_t2(_action) else "Recoverable"
        # ELI5 explainer (bounded local 8b, off the event loop, fail-closed). Gives the
        # operator a plain-English read of the request above the structured details.
        _eli5 = ""
        try:
            import asyncio as _asyncio
            from guardian_eli5 import eli5_explain
            _pkt = {"action": _action, "risk": _risk, "requester": _requester, "requested_at": _at}
            _eli5 = await _asyncio.get_event_loop().run_in_executor(
                None, lambda: eli5_explain(_pkt, depth="detailed")
            )
        except Exception:  # never break the Why-now path on the explainer
            _eli5 = ""
        why_text = (
            (f"{_eli5}\n\n———\n" if _eli5 else "")
            + f"Why is this approval being requested?\n\n"
            f"Action: {_action}\n"
            f"Risk: {_risk}\n"
            f"Requested by: {_requester} at {_at}\n\n"
            f"If you approve: the action proceeds immediately.\n"
            f"If you deny: the action is cancelled.\n"
            f"If no action: request expires and is auto-denied.\n\n"
            f"Use the buttons on the message above to respond."
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=guardian_resilient_reply(why_text))
        return  # Original message with buttons left intact

    # ── DELAY 5m — safe deferral; polling loop resets timeout and re-sends ─────
    if decision_token == "DELAY":
        _pd = _load_pending()
        if not has_pending_approval() or _pd.get("id") != approval_id_from_cb:
            await _update(_orig + "\n\n[Expired] No matching pending approval to delay.")
            return
        # Set status to "delayed" — the polling loop in request_approval() detects this,
        # resets its timeout window, and re-sends the approval message with fresh buttons.
        _pd["status"] = "delayed"
        _save_pending(_pd)
        await _update(_orig + "\n\n[Delayed] Deferring — a new approval message will arrive shortly.")
        return

    # ── Normal decision path (YES / NO / YES_FOR_ALL) ─────────────────────────
    if not has_pending_approval():
        await _update(_orig + "\n\nNo pending approval — tap ignored.")
        return

    # Pass the ID from callback_data as expected_id.
    # record_decision() validates it against the active pending ID.
    # Mismatch (stale button from a prior approval) is rejected and logged there.
    reply = record_decision(decision_token, expected_id=approval_id_from_cb)

    # Map record_decision() return strings to explicit, operator-correct status labels.
    # Binary approved/[Denied] would misclassify expired and rejected taps as denials.
    if reply in ("Approved.", "Approved for all."):
        status = "[Approved]"
    elif reply == "Denied.":
        status = "[Denied]"
    elif reply == "No pending approval request found.":
        status = "[Expired]"
    else:
        status = "[Rejected]"
    await _update(f"{_orig}\n\n{status} {reply}")

    # ── GREEN-CHECK ───────────────────────────────────────────────────────────
    # After a real Approve/Deny the one-at-a-time approval queue is empty, so send the
    # operator the "all clear" they actively look for: its ABSENCE means something is
    # still pending. Guarded so it can never crash the listener.
    if status in ("[Approved]", "[Denied]") and not has_pending_approval():
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="✅ All clear — no approvals waiting.",
            )
        except Exception:
            pass


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Fallback approval path: typed CODE DECISION format (e.g. "A3F2 1").

    This path is retained as an explicit fallback for cases where inline buttons
    are not delivered or not available. It enforces the same security guarantees
    as the button path: CODE format validation + approval ID binding.
    """
    if not update.effective_user or update.effective_user.id != AUTHORIZED_USER_ID:
        return
    if not update.message or not update.message.text:
        return
    if not claim_listener_update(update, role="guardian", source_channel="guardian_listener"):
        return

    text = update.message.text.strip()
    first_touch = first_touch_decision.attempt_first_touch(
        text,
        agent="guardian",
        surface="guardian_listener",
    )
    if first_touch.handled and first_touch.decision is not None:
        await update.message.reply_text(first_touch.decision.reply)
        return
    record_telegram_listener_update_safe(
        text=text,
        source_channel="guardian_listener",
        agent_target="guardian",
        source_message_id=str(getattr(update, "update_id", "")) or None,
        source_user_label="operator",
        operator_message=True,
        route_intent=False,
    )

    # ── Refusal-first guard (task 141) — FIRST tap, before HITL typed-reply
    # intake, approval parsing, or any clarify. Blanket approvals, money
    # moves, and destructive-scope asks get an instant refusal naming the
    # gate; legitimate typed decisions ("A3F2 1") never match and flow on.
    _refusal = None if first_touch.attempted else _operator_refusal_reply(text)
    if _refusal is not None:
        await update.message.reply_text(_refusal)
        return

    # Import here to avoid circular import at module load time
    from chief_approval_brain import (
        record_decision, has_pending_approval, _load_pending, parse_reply_code,
    )

    from hitl_notification_service import handle_typed_reply as _hitl_typed_reply

    _hitl_result = _hitl_typed_reply(
        text,
        approved_by=str(update.effective_user.id) if update.effective_user else "operator",
    )
    if _hitl_result.get("handled"):
        await update.message.reply_text(guardian_resilient_reply(str(_hitl_result.get("reply") or "HITL reply handled.")))
        return

    if not has_pending_approval():
        _reply = guardian_no_pending_reply(
            text,
            first_touch_receipt=first_touch.receipt if first_touch.attempted else None,
        )
        # Ground the reply with a read-only packet and packet-engine receipt, but
        # never expose the raw packet text in the operator-visible Telegram reply.
        try:
            _log_no_pending_guardian_packet(_build_no_pending_guardian_packet(text))
        except Exception:
            pass
        await update.message.reply_text(guardian_resilient_reply(_reply))
        return

    # Read pending record once: id → binding; options → correct format hint.
    _pd = _load_pending()
    _pending_id = _pd.get("id", "")
    _options = _pd.get("options", 2)

    # Strict CODE DECISION format required (e.g. "A3F2 1").
    # parse_reply_code returns ("", error_msg) on any mismatch or format failure.
    decision, error = parse_reply_code(text, _pending_id, options=_options)
    if error:
        # Task 151: only after the strict HITL/CODE parser has declined the
        # message may the safe conversational contract answer it.  This keeps
        # authority deterministic and lets gate narration/status avoid the
        # pending-session ELI5 model path.
        _typed_context = None
        _preserve_contract = None
        try:
            from typed_contract_decision import (
                ContractContext,
                ContractLabel,
                decide_contract,
                preserve_session_on_error,
                semantic_vote_enabled_for_adapter,
            )
            _preserve_contract = preserve_session_on_error
            _typed_context = ContractContext(
                agent="guardian",
                surface="guardian_listener",
                source_message_id=str(getattr(update, "update_id", "") or ""),
                active_session=True,
                session_kind="guardian_pending_approval",
                session_field=str(_pending_id),
                authority_pending=True,
                session_snapshot={"status": "active", "pending_id": str(_pending_id)},
            )

            _typed = decide_contract(
                text,
                context=_typed_context,
                status_renderer=lambda: f"1 pending approval request ({_pending_id}), awaiting a decision.",
                semantic_vote_enabled=semantic_vote_enabled_for_adapter("guardian", default=True),
                first_touch_receipt=first_touch.receipt if first_touch.attempted else None,
            )
        except Exception as exc:
            print(
                f"[typed_contract][guardian] {type(exc).__name__}; active_session=true",
                flush=True,
            )
            if _typed_context is not None and _preserve_contract is not None:
                _typed = _preserve_contract(
                    text,
                    context=_typed_context,
                    error_type=type(exc).__name__,
                )
            else:
                await update.message.reply_text(
                    guardian_resilient_reply(
                        "I couldn't classify that against the pending approval, so I left the approval unchanged. "
                        "Receipt: contract:guardian-adapter-error."
                    )
                )
                return
        if _typed is not None and _typed.handled and _typed.label not in {
            ContractLabel.REFUSAL,
            ContractLabel.AUTHORITY_TOKEN,
        }:
            await update.message.reply_text(guardian_resilient_reply(str(_typed.reply or "")))
            return

        # CHAT-WITH-GUARDIAN: if the message clearly isn't a decision attempt (doesn't
        # start with the 4-char reply code), treat it as a free-form QUESTION about THIS
        # pending approval and answer it conversationally (bounded local LM, fail-closed),
        # then still show how to decide. A malformed decision attempt keeps the strict
        # hint. This never touches approval semantics.
        _code = (_pending_id[:4] or "").upper()
        _ans = ""
        if _code and not text.strip().upper().startswith(_code):
            try:
                import asyncio as _asyncio
                from chief_approval_brain import _build_eli5_packet, _is_hard_t2
                from guardian_eli5 import answer_question

                _action = str(_pd.get("action", ""))
                _pkt = _build_eli5_packet(
                    _action, _pd.get("approval_context"),
                    requester=str(_pd.get("requester", "")),
                    is_irreversible=_is_hard_t2(_action),
                )
                _ans = await _asyncio.get_event_loop().run_in_executor(
                    None, lambda: answer_question(_pkt, text)
                )
            except Exception:
                _ans = ""
        await update.message.reply_text(guardian_resilient_reply(f"{_ans}\n\n———\n{error}" if _ans else error))
        if _ans:
            _fire_agent_voice("guardian", _ans, update)
        return

    reply = record_decision(decision, expected_id=_pending_id)
    await update.message.reply_text(guardian_resilient_reply(reply))


def build_application():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    install_identity_preflight(application, "guardian")
    return application


async def run_listener(application=None, stop_event: asyncio.Event | None = None) -> None:
    application = application or build_application()
    await run_verified_polling(application, "guardian", stop_event=stop_event)


def main() -> None:
    print("Guardian approval listener online.", flush=True)
    asyncio.run(run_listener())


if __name__ == "__main__":
    main()
