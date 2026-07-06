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
SEND_GUARDIAN_APPROVAL = "send_guardian_approval"  # Guardian approval board entry for the scoped send
TEST_SEND = "test_send"                            # send WITH attachment in TEST mode -> operator inbox
REAL_SEND = "real_send"                            # test mode OFF -> real send to the client
ASK_CLARIFY = "ask_clarify"                        # ambiguous: ask, do not advance
SEND_MESSAGE = "send_message"                      # a plain status/prompt message


def _preview_action(state: dict[str, Any]) -> dict[str, Any]:
    return {"kind": SEND_INVOICE_PREVIEW, "pdf_path": state.get("pdf_path"),
            "invoice_data": state.get("invoice_data"),
            "prompt": "Here's the invoice. Reply with any change, or 'looks good' to draft it."}


def _approval_token(value: Any) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or ""))
    return "-".join(part for part in text.split("-") if part) or "client"


def _real_review_approval_id(state: dict[str, Any]) -> str:
    existing = str(state.get("approval_id") or "")
    if existing:
        return existing
    data = state.get("invoice_data") if isinstance(state.get("invoice_data"), dict) else {}
    client_ref = data.get("client_ref") or state.get("client")
    invoice_number = data.get("invoice_number") or "invoice"
    return f"invoice-real-send:{_approval_token(client_ref)}:{_approval_token(invoice_number)}"


def guardian_approval_action(state: dict[str, Any]) -> dict[str, Any]:
    data = state.get("invoice_data") if isinstance(state.get("invoice_data"), dict) else {}
    approval_id = _real_review_approval_id(state)
    state["approval_id"] = approval_id
    return {
        "kind": SEND_GUARDIAN_APPROVAL,
        "approval": {
            "id": approval_id,
            "requester": "Cassandra",
            "tier": 2,
            "action": "Send invoice email",
            "action_summary_label": f"Send invoice {data.get('invoice_number') or ''}".strip(),
            "target": data.get("client_email") or state.get("client_email") or "",
            "supersede_key": approval_id,
            "approval_context": {
                "client": state.get("client") or data.get("client_name") or "",
                "client_ref": data.get("client_ref") or "",
                "invoice_number": data.get("invoice_number") or "",
                "pdf_path": state.get("pdf_path") or "",
                "attachment_sha256": state.get("attachment_sha256") or "",
                "mode": "real_send",
            },
        },
    }


def _draft_action(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": SEND_DRAFT_AND_APPROVAL,
        "client": state.get("client"),
        "invoice_data": state.get("invoice_data"),
        "pdf_path": state.get("pdf_path"),
    }


def start_invoice_send(
    client: str,
    invoice_data: dict,
    pdf_path: str,
    digest: str,
    *,
    real_review: bool = False,
) -> tuple[dict, list[dict]]:
    state = {
        "stage": AWAITING_SEND_APPROVAL if real_review else AWAITING_INVOICE_APPROVAL,
        "client": client,
        "invoice_data": invoice_data,
        "client_email": str(invoice_data.get("client_email") or ""),
        "pdf_path": pdf_path,
        "attachment_sha256": digest,
    }
    if real_review:
        state["review_mode"] = "real"
        state["approved_parts"] = {"invoice": False, "copy": False}
        return state, [_preview_action(state), _draft_action(state), guardian_approval_action(state)]
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


def _edit_part(text: str) -> str:
    t = " " + str(text or "").casefold() + " "
    if any(token in t for token in (" copy", " body", " email", " draft", " clara", " reword", " wording", " message")):
        return "copy"
    return "invoice"


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
        if state.get("review_mode") == "real":
            state["stage"] = AWAITING_SEND_APPROVAL
            approved_parts = dict(state.get("approved_parts") or {})
            part = _edit_part(text)
            approved_parts[part] = False
            state["approved_parts"] = approved_parts
            if part == "copy":
                return state, [_draft_action(state), guardian_approval_action(state)]
            return state, [{"kind": APPLY_EDIT, "instruction": text, "invoice_data": state.get("invoice_data"),
                            "review_part": part}]
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
            if state.get("review_mode") == "real":
                state["stage"] = SENT
                return state, [{"kind": REAL_SEND, "to": email, "attachment": state.get("pdf_path"),
                                "attachment_sha256": state.get("attachment_sha256"), "mode": "real",
                                "invoice_data": state.get("invoice_data")}]
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
    "SEND_INVOICE_PREVIEW", "APPLY_EDIT", "SEND_DRAFT_AND_APPROVAL", "SEND_GUARDIAN_APPROVAL",
    "TEST_SEND", "REAL_SEND", "ASK_CLARIFY", "SEND_MESSAGE", "guardian_approval_action",
    "start_invoice_send", "handle_reply",
]
