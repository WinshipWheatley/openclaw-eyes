"""IB-3 — the invoice-send cockpit the operator drives from Telegram.

A pure state machine: it holds the workflow state and, on each operator reply, returns a new state
plus a list of ACTIONS for the caller to execute (send a Telegram preview, send the Clara draft +
Guardian approval, do the TEST send to the operator's inbox, do the REAL send to the client). No side
effects here — the listener/executor performs the actions with the proven pieces (invoice PDF, Clara
draft, attachment send, run-mode). That keeps the safety-critical flow fully testable.

Hard safety rule: a REAL send can ONLY happen from AWAITING_TEST_CONFIRM after the operator has seen
the test email and explicitly says "send the real one". Nothing else real-sends.

Design ref: Operator/FABLE-WORKFLOW-TEST-MODE-SPEC-20260703.md (proof-registry flagship).
"""

from __future__ import annotations

from typing import Any

# Stages
AWAITING_INVOICE_APPROVAL = "awaiting_invoice_approval"
AWAITING_SEND_APPROVAL = "awaiting_send_approval"
AWAITING_TEST_CONFIRM = "awaiting_test_confirm"
SENT = "sent"
CANCELLED = "cancelled"

# Action kinds (the caller executes these)
SEND_INVOICE_PREVIEW = "send_invoice_preview"      # PDF + "approve or tell me what's wrong"
APPLY_EDIT = "apply_edit"                          # re-generate/re-fetch the invoice from an instruction
SEND_DRAFT_AND_APPROVAL = "send_draft_and_approval" # Clara draft + Guardian approval-to-send
TEST_SEND = "test_send"                            # send WITH attachment in TEST mode -> operator inbox
REAL_SEND = "real_send"                            # test mode OFF -> real send to the client
ASK_CLARIFY = "ask_clarify"                        # ambiguous: ask, do not advance
SEND_MESSAGE = "send_message"                      # a plain status/prompt message


def _preview_action(state: dict[str, Any]) -> dict[str, Any]:
    return {"kind": SEND_INVOICE_PREVIEW, "pdf_path": state.get("pdf_path"),
            "invoice_data": state.get("invoice_data"),
            "prompt": "Here's the invoice. Reply with any change, or 'looks good' to draft it."}


def start_invoice_send(client: str, invoice_data: dict, pdf_path: str, digest: str) -> tuple[dict, list[dict]]:
    state = {
        "stage": AWAITING_INVOICE_APPROVAL,
        "client": client,
        "invoice_data": invoice_data,
        "client_email": str(invoice_data.get("client_email") or ""),
        "pdf_path": pdf_path,
        "attachment_sha256": digest,
    }
    return state, [_preview_action(state)]


def _classify(text: str) -> str:
    t = " " + str(text or "").lower().strip() + " "
    # send-real is the most specific — check first so "looks great, send the real one" reads correctly
    if ("real" in t and "send" in t) or "for real" in t:
        return "send_real"
    if any(k in t for k in (" cancel", "nevermind", "never mind", "forget it", " quit ", "stop the invoice")):
        return "cancel"
    if any(k in t for k in (" wrong", "incorrect", "not right", "isn't right", " stop ",
                            "amount is off", " is off", " nope ", " no that")):
        return "reject"
    if any(k in t for k in ("add ", "change ", "remove ", " fix ", "update ", "should be",
                            "instead", "reword", "different", "wedding to", "make it")):
        return "edit"
    if any(k in t for k in ("looks good", "looks great", "approve", "approved", " yes ", "good to go",
                            "send it", "go ahead", "perfect", "correct", "that's right", "ship it")):
        return "approve"
    return "clarify"


def _clarify(state: dict, message: str) -> tuple[dict, list[dict]]:
    return state, [{"kind": ASK_CLARIFY, "text": message}]


def handle_reply(state: dict, text: str) -> tuple[dict, list[dict]]:
    """Advance the workflow given the operator's Telegram reply. Returns (new_state, actions)."""
    intent = _classify(text)
    stage = state.get("stage")
    if intent == "cancel":
        state["stage"] = CANCELLED
        return state, [{"kind": SEND_MESSAGE, "text": "Okay — cancelled the invoice flow. Nothing was sent."}]
    email = state.get("client_email") or str((state.get("invoice_data") or {}).get("client_email") or "")

    # An explicit edit / rejection always returns to invoice review — never mid-send.
    if intent == "edit":
        state["stage"] = AWAITING_INVOICE_APPROVAL
        return state, [{"kind": APPLY_EDIT, "instruction": text, "invoice_data": state.get("invoice_data")}]
    if intent == "reject":
        state["stage"] = AWAITING_INVOICE_APPROVAL
        return state, [{"kind": SEND_MESSAGE, "text": "Okay — back to the invoice. What should change?"},
                       _preview_action(state)]

    if stage == AWAITING_INVOICE_APPROVAL:
        if intent == "approve":
            state["stage"] = AWAITING_SEND_APPROVAL
            return state, [{"kind": SEND_DRAFT_AND_APPROVAL, "client": state.get("client"),
                            "invoice_data": state.get("invoice_data"), "pdf_path": state.get("pdf_path")}]
        return _clarify(state, "Does the invoice look right? Reply 'looks good', or tell me what to change.")

    if stage == AWAITING_SEND_APPROVAL:
        if intent == "approve":
            state["stage"] = AWAITING_TEST_CONFIRM
            return state, [{"kind": TEST_SEND, "to": email, "attachment": state.get("pdf_path"),
                            "attachment_sha256": state.get("attachment_sha256"), "mode": "test",
                            "invoice_data": state.get("invoice_data")}]
        return _clarify(state, "Approve the draft to run the test send to your inbox, or tell me what to change.")

    if stage == AWAITING_TEST_CONFIRM:
        if intent == "send_real":
            state["stage"] = SENT
            return state, [{"kind": REAL_SEND, "to": email, "attachment": state.get("pdf_path"),
                            "attachment_sha256": state.get("attachment_sha256"), "mode": "real",
                            "invoice_data": state.get("invoice_data")}]
        # "looks good" at the test stage is NOT enough to real-send — require the explicit phrase.
        return _clarify(state, "Check the test email in your inbox. If it's right, reply 'send the real one' "
                               "to send it to the client — or tell me what's wrong.")

    return _clarify(state, "I'm not sure what you'd like — tell me what to change, approve, or send.")


__all__ = [
    "AWAITING_INVOICE_APPROVAL", "AWAITING_SEND_APPROVAL", "AWAITING_TEST_CONFIRM", "SENT", "CANCELLED",
    "SEND_INVOICE_PREVIEW", "APPLY_EDIT", "SEND_DRAFT_AND_APPROVAL", "TEST_SEND", "REAL_SEND",
    "ASK_CLARIFY", "SEND_MESSAGE", "start_invoice_send", "handle_reply",
]
