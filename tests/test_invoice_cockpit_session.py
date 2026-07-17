"""IB-3 cockpit glue tests: registry routing, fuzzy invoice intent, and send rollback."""

from pathlib import Path

import interpreter_lm
import invoice_cockpit_session as cs
import invoice_send_workflow as wf


class FakeStore:
    def __init__(self):
        self.state = None

    def load(self):
        return self.state

    def save(self, state):
        self.state = state

    def clear(self):
        self.state = None


class FakeOps:
    def __init__(self, *, send_hold=True, client_email="draper.carter@gmail.com", fail_test_send=False):
        self.calls = []
        self.send_hold = send_hold
        self.client_email = client_email
        self.fail_test_send = fail_test_send

    def prepare_invoice(self, client):
        self.calls.append(("prepare", client))
        client_name = client.get("display_name") if isinstance(client, dict) else client
        return {"client_name": client_name, "client_email": self.client_email}, "/tmp/i.pdf", "h"

    def prepare_existing_finalized_invoice(self, client, *, requested_period=None):
        self.calls.append(("existing_finalized", client, requested_period))
        client_name = client.get("display_name") if isinstance(client, dict) else client
        return (
            {
                "client_name": client_name,
                "client_email": self.client_email,
                "invoice_number": "WL-2026-0009",
                "invoice_status": "issued",
            },
            "/tmp/WL-2026-0009__St_Annes.pdf",
            "issuedhash",
        )

    def telegram_pdf(self, path, caption):
        self.calls.append(("pdf", path, caption))
        return {"ok": True}

    def telegram_message(self, text):
        self.calls.append(("msg", text))
        return {"ok": True}

    def clara_draft_and_guardian(self, client, invoice_data, path):
        self.calls.append(("draft", client))
        return {"ok": True}

    def guardian_approval_board(self, approval):
        self.calls.append(("approval", approval))
        return {"ok": True}

    def apply_edit(self, invoice_data, instruction):
        self.calls.append(("edit", instruction))
        return {"ok": True}

    def send_email(self, *, to, attachment, attachment_sha256, invoice_data, mode):
        if mode == "test" and self.fail_test_send:
            self.calls.append(("send_test_failed", to))
            return {"ok": False, "error": "test send failed"}
        if mode == "real" and self.send_hold:
            self.calls.append(("blocked", to))
            return {"ok": False, "error": "SEND_HOLD active"}
        self.calls.append((f"send_{mode}", to))
        return {"ok": True}


def _prepare_calls(ops):
    return [call for call in ops.calls if call[0] == "prepare"]


def _send_calls(ops):
    return [call for call in ops.calls if call[0].startswith("send_") or call[0] == "blocked"]


class RealReviewOps(FakeOps):
    def prepare_invoice(self, client):
        self.calls.append(("prepare", client))
        client_name = client.get("display_name") if isinstance(client, dict) else client
        return (
            {
                "client_ref": "st_annes",
                "client_name": client_name,
                "client_email": self.client_email,
                "invoice_number": "WL-DRAFT-ST-ANNES",
                "invoice_status": "draft",
                "line_items": [{"description": "Wedding", "service_date": "2026-06-27", "amount": 12500}],
                "amount_total": 12500,
                "balance_due": 12500,
            },
            "/tmp/WL-DRAFT-ST-ANNES.pdf",
            "drafthash",
        )

    def finalized_review_attachment(self, *, attachment, attachment_sha256, invoice_data):
        self.calls.append(("finalize", attachment, attachment_sha256, invoice_data.get("invoice_number")))
        issued_data = dict(invoice_data)
        issued_data["invoice_number"] = "WL-2026-0009"
        issued_data["invoice_status"] = "issued"
        issued_data["lifecycle_state"] = "issued"
        issued_data["attachment_filename"] = "WL-2026-0009.pdf"
        return issued_data, "/tmp/WL-2026-0009.pdf", "issuedhash"

    def apply_edit(self, invoice_data, instruction):
        self.calls.append(("edit", instruction))
        edited = dict(invoice_data)
        edited["amount_total"] = 30000
        edited["balance_due"] = 30000
        edited["attachment_filename"] = "WL-2026-0009-revised.pdf"
        return {
            "ok": True,
            "changed": True,
            "invoice_data": edited,
            "pdf_path": "/tmp/WL-2026-0009-revised.pdf",
            "attachment_sha256": "revisedhash",
        }


def test_default_registry_trigger_starts_flow_and_sends_pdf():
    store, ops = FakeStore(), FakeOps()
    result = cs.handle_invoice_cockpit_message("send the St Anne's invoice", ops=ops, store=store)

    assert result["handled"] is True
    assert result["stage"] == wf.AWAITING_INVOICE_APPROVAL
    assert store.load() is not None
    assert any(call[0] == "pdf" and call[1] == "/tmp/i.pdf" for call in ops.calls)
    assert _prepare_calls(ops)[0][1]["client_ref"] == "st_annes"


def test_live_arts_guardian_gated_registry_allows_intake_preview_but_no_send():
    store, ops = FakeStore(), FakeOps()
    result = cs.handle_invoice_cockpit_message("send the Live Arts MD invoice", ops=ops, store=store)

    assert result["handled"] is True
    assert result["stage"] == wf.AWAITING_INVOICE_APPROVAL
    assert store.load() is not None
    assert _prepare_calls(ops)[0][1]["send_state"] == "SEND_REQUIRES_GUARDIAN"
    assert _prepare_calls(ops)[0][1]["send_authority"] is False
    assert not _send_calls(ops)


def test_reynolds_paid_no_invoice_sent_defers_without_prepare_or_send():
    store, ops = FakeStore(), FakeOps()
    result = cs.handle_invoice_cockpit_message("send the Reynolds invoice", ops=ops, store=store)

    assert result["handled"] is True
    assert result["stage"] == cs.REFUSED
    assert store.load() is None
    assert any(
        "Reynolds is already paid" in call[1] and "invoice next time" in call[1]
        for call in ops.calls
        if call[0] == "msg"
    )
    assert not _prepare_calls(ops)
    assert not _send_calls(ops)


def test_unknown_client_is_honest_and_does_not_guess():
    store, ops = FakeStore(), FakeOps()
    result = cs.handle_invoice_cockpit_message("send the Mystery Client invoice", ops=ops, store=store)

    assert result["handled"] is True
    assert result["stage"] == cs.UNKNOWN_CLIENT
    assert store.load() is None
    assert any("I don't have that client" in call[1] for call in ops.calls if call[0] == "msg")
    assert not _prepare_calls(ops)
    assert not _send_calls(ops)


def test_capital_hilton_excel_path_notes_dual_path_and_starts_flow():
    store, ops = FakeStore(), FakeOps()
    result = cs.handle_invoice_cockpit_message("send the Capital Hilton invoice", ops=ops, store=store)

    assert result["handled"] is True
    assert result["stage"] == wf.AWAITING_INVOICE_APPROVAL
    assert store.load() is not None
    assert any(
        "Capital Hilton" in call[1] and "Coupa" in call[1] and "Excel" in call[1]
        for call in ops.calls
        if call[0] == "msg"
    )
    assert _prepare_calls(ops)[0][1]["client_ref"] == "capital_hilton"
    assert any(call[0] == "pdf" and call[1] == "/tmp/i.pdf" for call in ops.calls)


def test_capital_hilton_coupa_or_po_path_is_flagged_without_excel_send():
    store, ops = FakeStore(), FakeOps()
    result = cs.handle_invoice_cockpit_message("send the Capital Hilton PO invoice", ops=ops, store=store)

    assert result["handled"] is True
    assert result["stage"] == cs.REFUSED
    assert store.load() is None
    assert any("Coupa/PO path is implied" in call[1] for call in ops.calls if call[0] == "msg")
    assert not _prepare_calls(ops)
    assert not _send_calls(ops)


def test_synthetic_po_client_routes_from_model_fields_without_client_branch():
    client_models = {
        "bright_hall": {
            "display_name": "Bright Hall",
            "aliases": ("bright hall",),
            "send_state": "EXCEL_PATH",
            "coupa_requires_purchase_order": True,
            "dual_path_note": "Bright Hall uses its portal when a PO is required.",
        }
    }
    store, ops = FakeStore(), FakeOps()
    result = cs.handle_invoice_cockpit_message(
        "send the Bright Hall PO invoice",
        ops=ops,
        store=store,
        client_models=client_models,
    )

    assert result["handled"] is True
    assert result["stage"] == cs.REFUSED
    assert result["client_model"]["client_ref"] == "bright_hall"
    assert any("Bright Hall uses its portal" in call[1] for call in ops.calls if call[0] == "msg")
    assert any("Coupa/PO path is implied" in call[1] for call in ops.calls if call[0] == "msg")
    assert not _prepare_calls(ops)
    assert not _send_calls(ops)


def test_synthetic_normal_client_starts_invoice_flow_from_registry_model():
    client_models = {
        "green_room": {
            "display_name": "Green Room",
            "aliases": ("green room", "greenroom"),
            "send_state": "NORMAL",
            "operator_note": "Green Room invoice source is already staged.",
        }
    }
    store, ops = FakeStore(), FakeOps()
    result = cs.handle_invoice_cockpit_message(
        "send the Green Room invoice",
        ops=ops,
        store=store,
        client_models=client_models,
    )

    assert result["handled"] is True
    assert result["stage"] == wf.AWAITING_INVOICE_APPROVAL
    assert any(
        "Green Room invoice source is already staged" in call[1]
        for call in ops.calls
        if call[0] == "msg"
    )
    assert _prepare_calls(ops)[0][1]["client_ref"] == "green_room"
    assert _prepare_calls(ops)[0][1]["display_name"] == "Green Room"


def test_interpreter_fuzzy_email_wording_resolves_registry_client_without_auto_send(monkeypatch):
    monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

    def _mock_interpret(text, **kwargs):
        assert text == "test st anne's email"
        return interpreter_lm.InterpretResult(
            route=interpreter_lm.ROUTE_ACTION,
            confidence=0.93,
            intent=interpreter_lm.INVOICE_SEND_INTENT,
            client="St. Anne's",
            reason="operator wants invoice email test",
        )

    monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)
    store, ops = FakeStore(), FakeOps()
    result = cs.handle_invoice_cockpit_message("test st anne's email", ops=ops, store=store)

    assert result["handled"] is True
    assert result["stage"] == wf.AWAITING_INVOICE_APPROVAL
    assert store.load()["stage"] == wf.AWAITING_INVOICE_APPROVAL
    assert _prepare_calls(ops)[0][1]["client_ref"] == "st_annes"
    assert any(call[0] == "pdf" for call in ops.calls)
    assert not any(call[0] in {"draft", "send_test", "send_real", "blocked"} for call in ops.calls)


def test_out_of_test_mode_review_packet_finalizes_orders_and_real_sends():
    store, ops = FakeStore(), RealReviewOps(send_hold=False)
    result = cs.handle_invoice_cockpit_message(
        "take st annes out of test mode and send it",
        ops=ops,
        store=store,
    )

    assert result["handled"] is True
    assert result["stage"] == wf.AWAITING_SEND_APPROVAL
    state = store.load()
    assert state["review_mode"] == "real"
    assert state["pdf_path"] == "/tmp/WL-2026-0009.pdf"
    assert state["attachment_sha256"] == "issuedhash"
    assert state["invoice_data"]["invoice_number"] == "WL-2026-0009"
    assert "DRAFT" not in state["invoice_data"]["invoice_number"]

    call_order = [call[0] for call in ops.calls]
    assert call_order[:5] == ["prepare", "finalize", "pdf", "draft", "approval"]
    assert ops.calls[2][1] == "/tmp/WL-2026-0009.pdf"
    approval = ops.calls[4][1]
    assert approval["id"].startswith("invoice-real-send:")
    assert approval["approval_context"]["pdf_path"] == "/tmp/WL-2026-0009.pdf"

    approved = cs.handle_invoice_cockpit_message("approve", ops=ops, store=store)

    assert approved["stage"] == wf.SENT
    assert ("send_real", "draper.carter@gmail.com") in ops.calls
    assert store.load() is None


def test_test_mode_review_preview_uses_same_finalized_attachment_path():
    store, ops = FakeStore(), RealReviewOps()
    result = cs.handle_invoice_cockpit_message("test st anne's email", ops=ops, store=store)

    assert result["handled"] is True
    assert result["stage"] == wf.AWAITING_INVOICE_APPROVAL
    state = store.load()
    assert state["pdf_path"] == "/tmp/WL-2026-0009.pdf"
    assert state["attachment_sha256"] == "issuedhash"
    assert state["invoice_data"]["invoice_number"] == "WL-2026-0009"
    assert [call[0] for call in ops.calls[:3]] == ["prepare", "finalize", "pdf"]
    assert not any(call[0] in {"draft", "send_test", "send_real", "blocked"} for call in ops.calls)


def test_real_review_invoice_revision_resends_only_pdf_and_preserves_copy_approval():
    store, ops = FakeStore(), RealReviewOps()
    cs.handle_invoice_cockpit_message("take st annes out of test mode and send it", ops=ops, store=store)
    state = store.load()
    state["approved_parts"] = {"invoice": True, "copy": True}
    store.save(state)
    before = len(ops.calls)

    result = cs.handle_invoice_cockpit_message("change the invoice amount to $300", ops=ops, store=store)

    assert result["stage"] == wf.AWAITING_SEND_APPROVAL
    new_calls = ops.calls[before:]
    assert [call[0] for call in new_calls] == ["edit", "pdf", "approval"]
    assert store.load()["pdf_path"] == "/tmp/WL-2026-0009-revised.pdf"
    assert store.load()["approved_parts"]["copy"] is True
    assert store.load()["approved_parts"]["invoice"] is False


def test_real_review_copy_revision_resends_only_clara_body_and_preserves_invoice_approval():
    store, ops = FakeStore(), RealReviewOps()
    cs.handle_invoice_cockpit_message("take st annes out of test mode and send it", ops=ops, store=store)
    state = store.load()
    state["approved_parts"] = {"invoice": True, "copy": True}
    store.save(state)
    before = len(ops.calls)

    result = cs.handle_invoice_cockpit_message("reword the copy to mention due on receipt", ops=ops, store=store)

    assert result["stage"] == wf.AWAITING_SEND_APPROVAL
    new_calls = ops.calls[before:]
    assert [call[0] for call in new_calls] == ["draft", "approval"]
    assert store.load()["approved_parts"]["invoice"] is True
    assert store.load()["approved_parts"]["copy"] is False


def test_interpreter_placeholder_client_asks_instead_of_preparing_right(monkeypatch):
    monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

    def _mock_interpret(text, **kwargs):
        return interpreter_lm.InterpretResult(
            route=interpreter_lm.ROUTE_WORKFLOW,
            confidence=0.94,
            intent=interpreter_lm.INVOICE_SEND_INTENT,
            client="",
            reason="placeholder",
        )

    monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)
    store, ops = FakeStore(), FakeOps()
    result = cs.handle_invoice_cockpit_message("send the right invoice", ops=ops, store=store)

    assert result["handled"] is True
    assert result["stage"] == cs.AWAITING_INVOICE_CLIENT
    assert store.load() is None
    assert any("which client" in call[1].lower() for call in ops.calls if call[0] == "msg")
    assert not _prepare_calls(ops)


def test_fuzzy_email_regex_fallback_is_safe_when_interpreter_is_unavailable(monkeypatch):
    monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

    def _mock_interpret(text, **kwargs):
        raise RuntimeError("lm unavailable")

    monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)
    store, ops = FakeStore(), FakeOps()
    result = cs.handle_invoice_cockpit_message("test st anne's email", ops=ops, store=store)

    assert result["handled"] is True
    assert result["stage"] == wf.AWAITING_INVOICE_APPROVAL
    assert _prepare_calls(ops)[0][1]["client_ref"] == "st_annes"
    assert not any(call[0] in {"draft", "send_test", "send_real", "blocked"} for call in ops.calls)


def test_lm_non_send_invoice_question_does_not_fire_cockpit(monkeypatch):
    monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

    def _mock_interpret(text, **kwargs):
        return interpreter_lm.InterpretResult(
            route=interpreter_lm.ROUTE_BRAIN,
            confidence=0.91,
            intent="",
            client="",
            reason="status question",
        )

    monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)
    store, ops = FakeStore(), FakeOps()
    result = cs.handle_invoice_cockpit_message("did they pay the invoice?", ops=ops, store=store)

    assert result["handled"] is False
    assert store.load() is None
    assert not _prepare_calls(ops)


def test_failed_test_send_does_not_advance_to_test_confirm():
    store, ops = FakeStore(), FakeOps(fail_test_send=True)
    cs.handle_invoice_cockpit_message("send the St Anne's invoice", ops=ops, store=store)
    cs.handle_invoice_cockpit_message("looks good", ops=ops, store=store)
    result = cs.handle_invoice_cockpit_message("approve", ops=ops, store=store)

    assert ("send_test_failed", "draper.carter@gmail.com") in ops.calls
    assert result["stage"] == wf.AWAITING_SEND_APPROVAL
    assert store.load()["stage"] == wf.AWAITING_SEND_APPROVAL
    assert any("that send failed: test send failed" in str(item) for item in result["results"])


def test_missing_recipient_blocks_send_before_attempting():
    store, ops = FakeStore(), FakeOps(client_email="unknown")
    cs.handle_invoice_cockpit_message("send the St Anne's invoice", ops=ops, store=store)
    cs.handle_invoice_cockpit_message("looks good", ops=ops, store=store)
    result = cs.handle_invoice_cockpit_message("approve", ops=ops, store=store)

    assert not _send_calls(ops)
    assert result["stage"] == wf.AWAITING_SEND_APPROVAL
    assert store.load()["stage"] == wf.AWAITING_SEND_APPROVAL
    assert any("missing client email" in str(item).lower() for item in result["results"])


def test_real_send_blocked_by_send_hold_does_not_advance_or_clear_session():
    store, ops = FakeStore(), FakeOps()
    cs.handle_invoice_cockpit_message("send the St Anne's invoice", ops=ops, store=store)
    cs.handle_invoice_cockpit_message("looks good", ops=ops, store=store)
    cs.handle_invoice_cockpit_message("approve", ops=ops, store=store)
    result = cs.handle_invoice_cockpit_message("looks great, send the real one", ops=ops, store=store)

    assert ("blocked", "draper.carter@gmail.com") in ops.calls
    assert result["stage"] == wf.AWAITING_TEST_CONFIRM
    assert store.load()["stage"] == wf.AWAITING_TEST_CONFIRM
    assert any("that send failed: SEND_HOLD active" in str(item) for item in result["results"])


def test_successful_real_send_advances_and_clears_session():
    store, ops = FakeStore(), FakeOps(send_hold=False)
    cs.handle_invoice_cockpit_message("send the St Anne's invoice", ops=ops, store=store)
    cs.handle_invoice_cockpit_message("looks good", ops=ops, store=store)
    cs.handle_invoice_cockpit_message("approve", ops=ops, store=store)
    result = cs.handle_invoice_cockpit_message("send the real one", ops=ops, store=store)

    assert ("send_real", "draper.carter@gmail.com") in ops.calls
    assert result["stage"] == wf.SENT
    assert store.load() is None


def test_reply_without_active_session_and_no_trigger_is_ignored():
    store, ops = FakeStore(), FakeOps()
    result = cs.handle_invoice_cockpit_message("approve", ops=ops, store=store)

    assert result["handled"] is False
    assert store.load() is None


def test_cancel_clears_active_session():
    store, ops = FakeStore(), FakeOps()
    cs.handle_invoice_cockpit_message("send the St Anne's invoice", ops=ops, store=store)
    assert store.load() is not None

    result = cs.handle_invoice_cockpit_message("nevermind, cancel", ops=ops, store=store)

    assert result["stage"] == "cancelled"
    assert store.load() is None


def test_trigger_is_imperative_only_not_casual_mentions():
    assert cs._detect_invoice_trigger("send the St Anne's invoice") is not None
    assert cs._detect_invoice_trigger("email the St Anne's invoice to Draper") is not None
    for casual in (
        "did they email us the invoice?",
        "what's the invoice status",
        "the invoice looks wrong",
        "I paid the invoice already",
        "check the invoice folder",
    ):
        assert cs._detect_invoice_trigger(casual) is None, casual


def test_get_invoice_ready_for_review_reaches_the_cockpit_end_to_end():
    """Task 148 acceptance: the exact live-evidence text must reach the SAME cockpit
    flow as the pre-existing "prepare" phrasing, staged for approval -- not the guided-
    review data-room wizard."""
    store, ops = FakeStore(), FakeOps()
    result = cs.handle_invoice_cockpit_message(
        "get the St Anne's July invoice ready for my review", ops=ops, store=store
    )

    assert result["handled"] is True
    assert result["stage"] == wf.AWAITING_INVOICE_APPROVAL
    existing = [call for call in ops.calls if call[0] == "existing_finalized"]
    assert existing[0][1]["client_ref"] == "st_annes"
    assert existing[0][2] == "2026-07"


def test_get_invoice_ready_for_review_is_a_trigger():
    """Task 148 live evidence: "get the St Anne's July invoice ready for my review" was
    missing this trigger entirely (verb list had no "get"), so it fell through to
    cassandra_guided_review's client-name alias scoring and got misrouted into the
    unrelated "Rates, Clients, Venues Review" data-room wizard."""
    client = cs._detect_invoice_trigger("get the St Anne's July invoice ready for my review")
    assert client is not None
    assert "st anne" in client.lower()

    assert cs._detect_invoice_trigger("get the Capital Hilton invoice ready") is not None
    # "get" must still respect the imperative-only boundary -- a genuine question stays
    # excluded regardless of the new verb.
    assert cs._detect_invoice_trigger("how do I get an invoice sent to them?") is None
    assert cs._detect_invoice_trigger("did you get the invoice yet?") is None


def test_cockpit_session_has_no_client_ref_specific_branching():
    source = Path(cs.__file__).read_text(encoding="utf-8")

    assert 'client_ref == "capital_hilton"' not in source
    assert '"capital_hilton" and' not in source
    assert "client_ref ==" not in source
    for client_literal in ("capital_hilton", "st_annes", "live_arts_md", "reynolds_tavern"):
        assert client_literal not in source
