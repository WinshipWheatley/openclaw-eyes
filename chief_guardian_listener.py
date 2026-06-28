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
  TELEGRAM_BOT_TOKEN and CASSANDRA_BOT_TOKEN. Then start_chief.sh will
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

import os
import sys

from telegram import Update, InlineKeyboardMarkup
from telegram.error import BadRequest as TelegramBadRequest, Forbidden as TelegramForbidden
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram_agent_intake import record_telegram_listener_update_safe
from chief_nonapproval_responder import guardian_no_pending_reply

# Guardian bot must be explicitly configured — this listener should not
# start on the Chief or Cassandra token.
_token = os.environ.get("GUARDIAN_BOT_TOKEN")
if not _token:
    print(
        "[chief_guardian_listener] GUARDIAN_BOT_TOKEN is not set. "
        "This listener should only start when a dedicated approval bot is configured. "
        "Exiting.",
        flush=True,
    )
    sys.exit(1)

BOT_TOKEN = _token
AUTHORIZED_USER_ID = int(os.environ["TELEGRAM_AUTHORIZED_USER_ID"])

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
        await query.answer()
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
        await context.bot.send_message(chat_id=update.effective_chat.id, text=why_text)
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

    text = update.message.text.strip()
    record_telegram_listener_update_safe(
        text=text,
        source_channel="guardian_listener",
        agent_target="guardian",
        source_message_id=str(getattr(update, "update_id", "")) or None,
        source_user_label="operator",
        operator_message=True,
        route_intent=False,
    )

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
        await update.message.reply_text(str(_hitl_result.get("reply") or "HITL reply handled."))
        return

    if not has_pending_approval():
        _reply = guardian_no_pending_reply(text)
        # Surface grounded approval-posture facts from the HITL ledger. READ-ONLY:
        # build_guardian_context_packet never resolves/approves anything. Additive —
        # appended to the existing reply; any failure is silently skipped.
        try:
            from guardian_context_packet import (
                build_guardian_context_packet,
                format_guardian_context_packet,
            )
            _posture = format_guardian_context_packet(build_guardian_context_packet())
            if _posture and _posture.strip():
                _posture = _posture.strip()
                if len(_posture) > 900:  # keep the Telegram reply well under the 4096 cap
                    _posture = _posture[:900].rstrip() + " …"
                _reply = f"{_reply}\n\n{_posture}"
        except Exception:
            pass
        await update.message.reply_text(_reply)
        return

    # Read pending record once: id → binding; options → correct format hint.
    _pd = _load_pending()
    _pending_id = _pd.get("id", "")
    _options = _pd.get("options", 2)

    # Strict CODE DECISION format required (e.g. "A3F2 1").
    # parse_reply_code returns ("", error_msg) on any mismatch or format failure.
    decision, error = parse_reply_code(text, _pending_id, options=_options)
    if error:
        await update.message.reply_text(error)
        return

    reply = record_decision(decision, expected_id=_pending_id)
    await update.message.reply_text(reply)


app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CallbackQueryHandler(handle_callback_query))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Guardian approval listener online.", flush=True)
app.run_polling()
