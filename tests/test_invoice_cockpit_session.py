"""IB-3 glue: the entrypoint the listener calls. Detects the 'send the invoice' trigger, runs the
brain, executes actions, and persists the session so the operator's next reply continues the flow."""

import invoice_cockpit_session as cs
import invoice_send_workflow as wf


class FakeStore:
    def __init__(self): self.state = None
    def load(self): return self.state
    def save(self, s): self.state = s
    def clear(self): self.state = None


class FakeOps:
    def __init__(self): self.calls = []; self.send_hold = True
    def prepare_invoice(self, client):
        return {"client_name": client, "client_email": "draper.carter@gmail.com"}, "/tmp/i.pdf", "h"
    def telegram_pdf(self, p, c): self.calls.append(("pdf", p)); return {"ok": True}
    def telegram_message(self, t): self.calls.append(("msg", t)); return {"ok": True}
    def clara_draft_and_guardian(self, cl, inv, p): self.calls.append(("draft", cl)); return {"ok": True}
    def apply_edit(self, inv, ins): self.calls.append(("edit", ins)); return {"ok": True}
    def send_email(self, *, to, attachment, attachment_sha256, invoice_data, mode):
        if mode == "real" and self.send_hold:
            self.calls.append(("blocked", to)); return {"ok": False, "error": "SEND_HOLD active"}
        self.calls.append((f"send_{mode}", to)); return {"ok": True}


def test_trigger_starts_flow_and_sends_pdf():
    store, ops = FakeStore(), FakeOps()
    r = cs.handle_invoice_cockpit_message("send the St Anne's invoice", ops=ops, store=store)
    assert r["handled"] is True and r["stage"] == wf.AWAITING_INVOICE_APPROVAL
    assert ("pdf", "/tmp/i.pdf") in ops.calls and store.load() is not None


def test_non_trigger_is_not_handled():
    store, ops = FakeStore(), FakeOps()
    r = cs.handle_invoice_cockpit_message("what's the weather", ops=ops, store=store)
    assert r["handled"] is False and store.load() is None


def test_full_flow_to_test_send_then_real_blocked_by_send_hold():
    store, ops = FakeStore(), FakeOps()
    cs.handle_invoice_cockpit_message("send the St Anne's invoice", ops=ops, store=store)
    cs.handle_invoice_cockpit_message("looks good", ops=ops, store=store)          # -> draft
    cs.handle_invoice_cockpit_message("approve", ops=ops, store=store)             # -> TEST send
    assert ("send_test", "draper.carter@gmail.com") in ops.calls
    r = cs.handle_invoice_cockpit_message("looks great, send the real one", ops=ops, store=store)
    # real send attempted but SEND_HOLD-blocked; session ends but flags blocked
    assert ("blocked", "draper.carter@gmail.com") in ops.calls


def test_reply_without_active_session_and_no_trigger_is_ignored():
    store, ops = FakeStore(), FakeOps()
    r = cs.handle_invoice_cockpit_message("approve", ops=ops, store=store)
    assert r["handled"] is False


def test_cancel_clears_active_session():
    store, ops = FakeStore(), FakeOps()
    cs.handle_invoice_cockpit_message("send the St Anne's invoice", ops=ops, store=store)
    assert store.load() is not None
    r = cs.handle_invoice_cockpit_message("nevermind, cancel", ops=ops, store=store)
    assert r["stage"] == "cancelled" and store.load() is None
