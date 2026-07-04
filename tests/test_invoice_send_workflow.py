"""IB-3 cockpit: the invoice-send workflow the operator drives from Telegram.
Flow: preview PDF -> approve -> Clara draft + Guardian approval -> approve -> TEST send to operator
inbox -> 'send the real one' -> test mode off -> real send to client. Pure state machine returning
ACTIONS; the caller executes them (Telegram/send/run-mode). Fully testable with no side effects."""

import invoice_send_workflow as wf


def _invoice():
    return {"client_name": "St. Anne's", "client_email": "draper.carter@gmail.com",
            "line_items": [{"description": "Wedding", "service_date": "2026-06-27", "amount": 12500}],
            "amount_total": 12500, "invoice_number": "WL-2026-0007"}


def test_start_sends_pdf_preview_for_approval():
    state, actions = wf.start_invoice_send("St. Anne's", _invoice(), "/tmp/inv.pdf", "abc123")
    assert state["stage"] == wf.AWAITING_INVOICE_APPROVAL
    assert any(a["kind"] == wf.SEND_INVOICE_PREVIEW and a["pdf_path"] == "/tmp/inv.pdf" for a in actions)


def test_approve_pdf_goes_to_draft_and_guardian():
    state, _ = wf.start_invoice_send("St. Anne's", _invoice(), "/tmp/inv.pdf", "abc123")
    state, actions = wf.handle_reply(state, "looks good")
    assert state["stage"] == wf.AWAITING_SEND_APPROVAL
    assert any(a["kind"] == wf.SEND_DRAFT_AND_APPROVAL for a in actions)


def test_approve_send_triggers_TEST_send_to_operator():
    state, _ = wf.start_invoice_send("St. Anne's", _invoice(), "/tmp/inv.pdf", "abc123")
    state, _ = wf.handle_reply(state, "looks good")
    state, actions = wf.handle_reply(state, "approve")
    assert state["stage"] == wf.AWAITING_TEST_CONFIRM
    ts = [a for a in actions if a["kind"] == wf.TEST_SEND]
    assert ts and ts[0]["to"] == "draper.carter@gmail.com" and ts[0]["attachment"] == "/tmp/inv.pdf"
    assert ts[0]["mode"] == "test"   # redirects to operator inbox downstream


def test_send_the_real_one_turns_off_test_and_sends_to_client():
    state, _ = wf.start_invoice_send("St. Anne's", _invoice(), "/tmp/inv.pdf", "abc123")
    state, _ = wf.handle_reply(state, "looks good")
    state, _ = wf.handle_reply(state, "approve")
    state, actions = wf.handle_reply(state, "looks great, send the real one")
    assert state["stage"] == wf.SENT
    rs = [a for a in actions if a["kind"] == wf.REAL_SEND]
    assert rs and rs[0]["to"] == "draper.carter@gmail.com" and rs[0]["mode"] == "real"


def test_edit_at_pdf_stage_reapplies_and_re_previews():
    state, _ = wf.start_invoice_send("St. Anne's", _invoice(), "/tmp/inv.pdf", "abc123")
    state, actions = wf.handle_reply(state, "add the church service on June 28")
    assert state["stage"] == wf.AWAITING_INVOICE_APPROVAL
    assert any(a["kind"] == wf.APPLY_EDIT for a in actions)


def test_reject_at_test_returns_to_pdf_review():
    state, _ = wf.start_invoice_send("St. Anne's", _invoice(), "/tmp/inv.pdf", "abc123")
    state, _ = wf.handle_reply(state, "looks good")
    state, _ = wf.handle_reply(state, "approve")
    state, actions = wf.handle_reply(state, "no that's wrong, the amount is off")
    assert state["stage"] == wf.AWAITING_INVOICE_APPROVAL


def test_ambiguous_reply_asks_for_clarification_without_advancing():
    state, _ = wf.start_invoice_send("St. Anne's", _invoice(), "/tmp/inv.pdf", "abc123")
    prev = state["stage"]
    state, actions = wf.handle_reply(state, "hmm")
    assert state["stage"] == prev
    assert any(a["kind"] == wf.ASK_CLARIFY for a in actions)


def test_never_real_sends_before_test_confirmed():
    # a 'send the real one' at the PDF stage must NOT real-send — safety
    state, _ = wf.start_invoice_send("St. Anne's", _invoice(), "/tmp/inv.pdf", "abc123")
    state, actions = wf.handle_reply(state, "send the real one")
    assert not any(a["kind"] == wf.REAL_SEND for a in actions)
    assert state["stage"] != wf.SENT
