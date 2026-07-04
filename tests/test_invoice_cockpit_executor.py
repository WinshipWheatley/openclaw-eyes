"""IB-3 executor: turns the cockpit's ACTIONS into real effects via an injected ops object, so the
orchestration is testable and the REAL-send safety (SEND_HOLD) is explicit."""

import invoice_send_workflow as wf
import invoice_cockpit_executor as ex


class FakeOps:
    def __init__(self, send_hold=True):
        self.calls = []
        self.send_hold = send_hold
    def telegram_pdf(self, pdf_path, caption): self.calls.append(("pdf", pdf_path)); return {"ok": True}
    def telegram_message(self, text): self.calls.append(("msg", text)); return {"ok": True}
    def clara_draft_and_guardian(self, client, invoice_data, pdf_path): self.calls.append(("draft", client)); return {"ok": True}
    def apply_edit(self, invoice_data, instruction): self.calls.append(("edit", instruction)); return {"ok": True}
    def send_email(self, *, to, attachment, attachment_sha256, invoice_data, mode):
        # real send is refused while SEND_HOLD is active
        if mode == "real" and self.send_hold:
            self.calls.append(("send_blocked", to)); return {"ok": False, "error": "SEND_HOLD active — lift it to send for real"}
        self.calls.append((f"send_{mode}", to)); return {"ok": True}


def _run(action, ops): return ex.execute_action(action, ops)


def test_preview_action_sends_pdf():
    ops = FakeOps(); state, actions = wf.start_invoice_send("St. Anne's", {"client_email": "d@x.com"}, "/tmp/i.pdf", "h")
    for a in actions: _run(a, ops)
    assert ("pdf", "/tmp/i.pdf") in ops.calls


def test_test_send_executes_in_test_mode():
    ops = FakeOps()
    r = _run({"kind": wf.TEST_SEND, "to": "d@x.com", "attachment": "/tmp/i.pdf",
              "attachment_sha256": "h", "invoice_data": {}, "mode": "test"}, ops)
    assert r["ok"] is True and ("send_test", "d@x.com") in ops.calls


def test_real_send_is_blocked_while_send_hold_active():
    ops = FakeOps(send_hold=True)
    r = _run({"kind": wf.REAL_SEND, "to": "d@x.com", "attachment": "/tmp/i.pdf",
              "attachment_sha256": "h", "invoice_data": {}, "mode": "real"}, ops)
    assert r["ok"] is False and "SEND_HOLD" in r["error"]
    assert ("send_blocked", "d@x.com") in ops.calls


def test_real_send_proceeds_when_send_hold_off():
    ops = FakeOps(send_hold=False)
    r = _run({"kind": wf.REAL_SEND, "to": "d@x.com", "attachment": "/tmp/i.pdf",
              "attachment_sha256": "h", "invoice_data": {}, "mode": "real"}, ops)
    assert r["ok"] is True and ("send_real", "d@x.com") in ops.calls


def test_clarify_and_draft_dispatch():
    ops = FakeOps()
    _run({"kind": wf.ASK_CLARIFY, "text": "which one?"}, ops)
    _run({"kind": wf.SEND_DRAFT_AND_APPROVAL, "client": "St. Anne's", "invoice_data": {}, "pdf_path": "/tmp/i.pdf"}, ops)
    assert ("msg", "which one?") in ops.calls and ("draft", "St. Anne's") in ops.calls
