"""Execute IB-3 cockpit ACTIONS against an injected ops object. Keeps the state machine pure and
the real-world effects (Telegram, Clara draft + Guardian, the attachment send, run-mode) in one
place. The ops object is the real integration in production and a fake in tests.

REAL send safety: the REAL send to the client is refused while SEND_HOLD is active — the operator's
master kill-switch must be deliberately lifted before a real external send. TEST sends are always
safe (redirected to the operator inbox + flagged downstream)."""

from __future__ import annotations

from typing import Any

import invoice_send_workflow as wf


def execute_action(action: dict[str, Any], ops: Any) -> dict[str, Any]:
    kind = action.get("kind")
    if kind == wf.SEND_INVOICE_PREVIEW:
        inv = action.get("invoice_data") or {}
        caption = action.get("prompt") or "Here's the invoice for your review."
        return ops.telegram_pdf(action.get("pdf_path"), caption)
    if kind in (wf.ASK_CLARIFY, wf.SEND_MESSAGE):
        return ops.telegram_message(action.get("text") or "")
    if kind == wf.APPLY_EDIT:
        return ops.apply_edit(action.get("invoice_data"), action.get("instruction"))
    if kind == wf.SEND_DRAFT_AND_APPROVAL:
        return ops.clara_draft_and_guardian(action.get("client"), action.get("invoice_data"), action.get("pdf_path"))
    if kind == wf.SEND_GUARDIAN_APPROVAL:
        return ops.guardian_approval_board(action.get("approval") or {})
    if kind in (wf.TEST_SEND, wf.REAL_SEND):
        return ops.send_email(
            to=action.get("to"), attachment=action.get("attachment"),
            attachment_sha256=action.get("attachment_sha256"),
            invoice_data=action.get("invoice_data"), mode=action.get("mode"),
        )
    return {"ok": False, "error": f"unknown action kind: {kind}"}


def execute_actions(actions: list[dict[str, Any]], ops: Any) -> list[dict[str, Any]]:
    return [execute_action(a, ops) for a in actions]


__all__ = ["execute_action", "execute_actions"]
