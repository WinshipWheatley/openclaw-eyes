"""IB-3 glue — the single entrypoint the listener calls with the operator's message.

If there's no active cockpit session, it only engages when the message is an invoice-send TRIGGER
("send the <client> invoice"); otherwise it returns handled=False so normal routing continues. Once
a session is active, every operator message drives the state machine until the flow ends. State is
persisted between messages via the injected store (a sqlite/json store in production)."""

from __future__ import annotations

import re
from typing import Any

import invoice_send_workflow as wf
import invoice_cockpit_executor as ex

# "send the St Anne's invoice", "email the Capital Hilton invoice", "invoice for Draper" ...
# Must be an IMPERATIVE command ("send the St Anne's invoice"), not a casual mention or a question.
# Verb-first, no '?' before "invoice", so "did they email us the invoice?" does NOT trigger.
_TRIGGER = re.compile(
    r"^\s*(?:please\s+|hey[, ]+|ok(?:ay)?[, ]+)?(?:send|e-?mail|generate|prepare|create|draft|make)\b[^?\n]{0,60}\binvoice\b",
    re.IGNORECASE,
)


def _detect_invoice_trigger(text: str) -> str | None:
    t = str(text or "")
    if not _TRIGGER.search(t):
        return None
    # pull a client name between "the" and "invoice" if present ("send the St Anne's invoice")
    m = re.search(r"\bthe\s+(.+?)\s+invoice\b", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"\binvoice\s+(?:for|to)\s+(.+)$", t, re.IGNORECASE)
    if m:
        return m.group(1).strip().rstrip(".!?")
    return "the client"


def handle_invoice_cockpit_message(text: str, *, ops: Any, store: Any) -> dict[str, Any]:
    session = store.load()
    # Cancel escape: an active session must never trap the operator's chat.
    if session is not None and re.search(r"\b(cancel|nevermind|never mind|forget it|stop the invoice|quit)\b", str(text or ""), re.IGNORECASE):
        store.clear()
        try:
            ops.telegram_message("Okay — cancelled the invoice flow. Nothing was sent.")
        except Exception:
            pass
        return {"handled": True, "stage": "cancelled"}
    if session is None:
        client = _detect_invoice_trigger(text)
        if not client:
            return {"handled": False}
        try:
            invoice_data, pdf_path, digest = ops.prepare_invoice(client)
        except Exception as exc:
            return {"handled": True, "error": f"could not prepare the invoice: {exc}"}
        state, actions = wf.start_invoice_send(client, invoice_data, pdf_path, digest)
    else:
        state, actions = wf.handle_reply(session, text)

    results = ex.execute_actions(actions, ops)
    if state.get("stage") in (wf.SENT, wf.CANCELLED):
        store.clear()
    else:
        store.save(state)
    return {"handled": True, "stage": state.get("stage"), "results": results}


__all__ = ["handle_invoice_cockpit_message", "_detect_invoice_trigger"]
