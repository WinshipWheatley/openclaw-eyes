from __future__ import annotations

from datetime import date

from auto_fire_invoicing import (
    AutoFireStateStore,
    run_auto_fire,
    send_invoice_now,
)


class FakeInvoiceStore:
    def __init__(self) -> None:
        self.finalized: list[tuple[str, str]] = []
        self.invoices = {
            ("live-arts-md", "2026-07"): {
                "client_name": "Live Arts MD",
                "period": "2026-07",
                "line_items": [{"description": "Speaker rental", "service_date": "2026-07-01", "amount": 500}],
                "amount_total": 500,
                "invoice_ready": True,
            },
            ("st-annes", "2026-07"): {
                "client_name": "St. Anne's",
                "period": "2026-07",
                "line_items": [{"description": "Wedding", "service_date": "2026-07-15", "amount": 125}],
                "amount_total": 125,
                "invoice_ready": True,
            },
        }

    def load_invoice(self, client_slug: str, period: str) -> dict | None:
        invoice = self.invoices.get((client_slug, period))
        return dict(invoice) if invoice else None

    def finalize_invoice(self, client_slug: str, period: str, invoice: dict) -> dict:
        self.finalized.append((client_slug, period))
        finalized = dict(invoice)
        finalized["finalized"] = True
        return finalized


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, dict]] = []
        self.prepared: list[tuple[str, str, dict, str]] = []

    def send_invoice(self, *, client_slug: str, period: str, invoice: dict, channel: str) -> dict:
        self.sent.append((client_slug, period, dict(invoice)))
        return {"ok": True, "send_receipt": f"send:{client_slug}:{period}", "channel": channel}

    def prepare_for_operator_verify(self, *, client_slug: str, period: str, invoice: dict, reason: str) -> dict:
        self.prepared.append((client_slug, period, dict(invoice), reason))
        return {"ok": True, "review_ref": f"review:{client_slug}:{period}", "reason": reason}


def _client_models() -> dict:
    return {
        "live-arts-md": {
            "display_name": "Live Arts MD",
            "send_policy": {
                "cadence": "monthly",
                "trigger": "first_of_month",
                "channel": "email",
                "proven": True,
            },
        },
        "st-annes": {
            "display_name": "St. Anne's",
            "send_policy": {
                "cadence": "monthly",
                "trigger": "first_of_month",
                "channel": "email",
                "proven": False,
            },
        },
    }


def test_first_of_month_finalizes_prior_period_and_auto_sends_proven_client() -> None:
    invoices = FakeInvoiceStore()
    sender = FakeSender()
    state = AutoFireStateStore()

    result = run_auto_fire(
        today=date(2026, 8, 1),
        client_models={"live-arts-md": _client_models()["live-arts-md"]},
        invoice_store=invoices,
        sender=sender,
        state_store=state,
        send_hold_active=False,
    )

    assert result["period"] == "2026-07"
    assert result["actions"][0]["status"] == "sent"
    assert invoices.finalized == [("live-arts-md", "2026-07")]
    assert sender.sent[0][0:2] == ("live-arts-md", "2026-07")
    assert state.last_sent_period("live-arts-md") == "2026-07"


def test_unproven_policy_prepares_for_operator_verify_without_send() -> None:
    invoices = FakeInvoiceStore()
    sender = FakeSender()

    result = run_auto_fire(
        today=date(2026, 8, 1),
        client_models={"st-annes": _client_models()["st-annes"]},
        invoice_store=invoices,
        sender=sender,
        state_store=AutoFireStateStore(),
        send_hold_active=False,
    )

    assert result["actions"][0]["status"] == "prepared_for_operator_verify"
    assert result["actions"][0]["reason"] == "send_policy_unproven"
    assert sender.sent == []
    assert sender.prepared[0][0:2] == ("st-annes", "2026-07")


def test_send_hold_blocks_even_proven_auto_send() -> None:
    invoices = FakeInvoiceStore()
    sender = FakeSender()

    result = run_auto_fire(
        today=date(2026, 8, 1),
        client_models={"live-arts-md": _client_models()["live-arts-md"]},
        invoice_store=invoices,
        sender=sender,
        state_store=AutoFireStateStore(),
        send_hold_active=True,
    )

    assert result["actions"][0]["status"] == "send_hold_blocked"
    assert sender.sent == []
    assert sender.prepared[0][3] == "send_hold_active"


def test_on_demand_send_records_period_and_auto_fire_dedups() -> None:
    invoices = FakeInvoiceStore()
    sender = FakeSender()
    state = AutoFireStateStore()

    manual = send_invoice_now(
        "live-arts-md",
        period="2026-07",
        client_models=_client_models(),
        invoice_store=invoices,
        sender=sender,
        state_store=state,
        send_hold_active=False,
    )
    auto = run_auto_fire(
        today=date(2026, 8, 1),
        client_models={"live-arts-md": _client_models()["live-arts-md"]},
        invoice_store=invoices,
        sender=sender,
        state_store=state,
        send_hold_active=False,
    )

    assert manual["status"] == "sent"
    assert len(sender.sent) == 1
    assert auto["actions"][0]["status"] == "already_sent"
    assert len(sender.sent) == 1


def test_not_first_of_month_does_not_auto_fire() -> None:
    result = run_auto_fire(
        today=date(2026, 8, 2),
        client_models=_client_models(),
        invoice_store=FakeInvoiceStore(),
        sender=FakeSender(),
        state_store=AutoFireStateStore(),
        send_hold_active=False,
    )

    assert result["status"] == "not_trigger_day"
    assert result["actions"] == []
