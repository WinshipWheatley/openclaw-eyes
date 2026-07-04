from __future__ import annotations

import hashlib
from pathlib import Path

import invoice_cockpit_session as cs
import invoice_send_workflow as wf
from invoice_cockpit_ops import RealCockpitOps


class FakeStore:
    def __init__(self):
        self.state = None

    def load(self):
        return self.state

    def save(self, state):
        self.state = state

    def clear(self):
        self.state = None


class EditingOps:
    def __init__(self):
        self.calls = []

    def prepare_invoice(self, client):
        return (
            {
                "invoice_number": "WL-2026-0001",
                "client_name": client,
                "client_email": "client@example.com",
                "project_desc": "Wedding",
                "service_date": "2026-06-14",
                "issue_date": "2026-07-04",
                "net_terms": "Due on Receipt",
                "amount_total": 12500,
                "balance_due": 12500,
                "deposit_paid": 0,
                "line_items": [
                    {"description": "Wedding", "service_date": "2026-06-14", "amount": 12500},
                ],
            },
            "/tmp/old.pdf",
            "oldhash",
        )

    def telegram_pdf(self, pdf_path, caption):
        self.calls.append(("pdf", pdf_path, caption))
        return {"ok": True}

    def telegram_message(self, text):
        self.calls.append(("msg", text))
        return {"ok": True}

    def apply_edit(self, invoice_data, instruction):
        assert invoice_data["line_items"][0]["description"] == "Wedding"
        self.calls.append(("edit", instruction))
        edited = dict(invoice_data)
        edited["line_items"] = [
            *invoice_data["line_items"],
            {"description": "Church service", "service_date": "2026-06-21", "amount": 12500},
        ]
        edited["amount_total"] = 25000
        edited["balance_due"] = 25000
        return {
            "ok": True,
            "changed": True,
            "invoice_data": edited,
            "pdf_path": "/tmp/new.pdf",
            "attachment_sha256": "newhash",
        }

    def clara_draft_and_guardian(self, client, invoice_data, pdf_path):
        return {"ok": True}

    def send_email(self, **kwargs):
        return {"ok": True}


def test_edit_reply_updates_session_and_repreviews_new_pdf() -> None:
    store = FakeStore()
    ops = EditingOps()

    cs.handle_invoice_cockpit_message("send the Any Client invoice", ops=ops, store=store)
    result = cs.handle_invoice_cockpit_message(
        "add Church service on 2026-06-21 at $125",
        ops=ops,
        store=store,
    )

    state = store.load()
    assert result["stage"] == wf.AWAITING_INVOICE_APPROVAL
    assert state["pdf_path"] == "/tmp/new.pdf"
    assert state["attachment_sha256"] == "newhash"
    assert state["invoice_data"]["amount_total"] == 25000
    assert state["invoice_data"]["line_items"][-1]["service_date"] == "2026-06-21"
    assert any(call[:2] == ("pdf", "/tmp/new.pdf") for call in ops.calls)


def test_real_cockpit_apply_edit_rerenders_pdf(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(tmp_path))
    monkeypatch.setenv("OPENCLAW_INVOICE_TRACKER_DIR", str(tmp_path / "tracker"))
    data = {
        "invoice_number": "WL-2026-0001",
        "client_name": "Any Client",
        "client_email": "client@example.com",
        "project_desc": "Wedding",
        "service_date": "2026-06-14",
        "issue_date": "2026-07-04",
        "net_terms": "Due on Receipt",
        "amount_total": 12500,
        "balance_due": 12500,
        "deposit_paid": 0,
        "line_items": [
            {"description": "Wedding", "service_date": "2026-06-14", "amount": 12500},
        ],
    }

    result = RealCockpitOps().apply_edit(data, "add Church service on 2026-06-21 at $125")

    assert result["ok"] is True
    assert result["changed"] is True
    assert result["invoice_data"]["amount_total"] == 25000
    assert result["invoice_data"]["line_items"][-1]["amount"] == 12500
    pdf_path = Path(result["pdf_path"])
    assert pdf_path.exists()
    assert result["attachment_sha256"] == hashlib.sha256(pdf_path.read_bytes()).hexdigest()
