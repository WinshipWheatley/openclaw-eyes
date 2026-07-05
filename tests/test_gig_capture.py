from __future__ import annotations

from datetime import datetime
from pathlib import Path

from contacts_registry import ContactsRegistry
from gig_capture import capture_gig


class FakeCalendarRouter:
    def __init__(self, conflicts: dict[str, list[dict]] | None = None) -> None:
        self.conflicts = conflicts or {}
        self.added: list[dict] = []

    def events_on(self, service_date: str) -> list[dict]:
        return list(self.conflicts.get(service_date, ()))

    def add_event(self, event: dict) -> dict:
        self.added.append(dict(event))
        return {"ok": True, "event": dict(event)}


class FakeInvoiceStore:
    def __init__(self) -> None:
        self.saved: list[tuple[str, dict]] = []
        self.invoices: dict[str, dict] = {
            "live-arts-md": {
                "client_name": "Live Arts MD",
                "issue_date": "2026-07-01",
                "deposit_paid": 0,
                "amount_total": 0,
                "balance_due": 0,
                "line_items": [],
                "amount_units": "dollars",
            },
            "st-annes": {
                "client_name": "St. Anne's",
                "issue_date": "2026-07-01",
                "deposit_paid": 0,
                "amount_total": 0,
                "balance_due": 0,
                "line_items": [],
                "amount_units": "dollars",
            },
        }

    def load_current_invoice(self, client_slug: str, service_date: str) -> dict:
        return dict(self.invoices[client_slug])

    def save_current_invoice(self, client_slug: str, invoice_data: dict) -> None:
        self.invoices[client_slug] = dict(invoice_data)
        self.saved.append((client_slug, dict(invoice_data)))


def _registry(tmp_path: Path) -> ContactsRegistry:
    return ContactsRegistry(str(tmp_path / "contacts.sqlite3"))


def _client_models() -> dict:
    return {
        "live-arts-md": {"display_name": "Live Arts MD", "rate": 500},
        "st-annes": {"display_name": "St. Anne's", "rate": 125},
    }


def test_clear_date_adds_calendar_event_and_invoice_line(tmp_path: Path) -> None:
    calendar = FakeCalendarRouter()
    invoices = FakeInvoiceStore()

    result = capture_gig(
        "Dane asked me to do Tech rehearsal on July 12",
        contacts_registry=_registry(tmp_path),
        calendar_router=calendar,
        invoice_store=invoices,
        client_models=_client_models(),
        now=datetime(2026, 7, 5, 12, 0),
    )

    assert result["status"] == "captured"
    assert result["client_slug"] == "live-arts-md"
    assert result["calendar"]["status"] == "event_added"
    assert calendar.added == [
        {
            "title": "Live Arts MD - Tech rehearsal",
            "date": "2026-07-12",
            "client_slug": "live-arts-md",
            "description": "Tech rehearsal",
            "source": "gig_capture",
        }
    ]
    saved_client, invoice_data = invoices.saved[-1]
    assert saved_client == "live-arts-md"
    assert invoice_data["line_items"][-1] == {
        "description": "Tech rehearsal",
        "service_date": "2026-07-12",
        "amount": 500,
    }
    assert "event added" in result["confirmation"].lower()
    assert "invoice line added" in result["confirmation"].lower()


def test_calendar_conflict_surfaces_existing_event_and_still_adds_invoice_line(tmp_path: Path) -> None:
    existing = {"title": "Doctor", "date": "2026-07-13", "id": "cal:existing"}
    calendar = FakeCalendarRouter(conflicts={"2026-07-13": [existing]})
    invoices = FakeInvoiceStore()

    result = capture_gig(
        "Megan asked me to do Speaker rental on 2026-07-13",
        contacts_registry=_registry(tmp_path),
        calendar_router=calendar,
        invoice_store=invoices,
        client_models=_client_models(),
        now=datetime(2026, 7, 5, 12, 0),
    )

    assert result["status"] == "captured"
    assert result["calendar"]["status"] == "conflict"
    assert result["calendar"]["existing_event"] == existing
    assert calendar.added == []
    assert invoices.saved[-1][0] == "live-arts-md"
    assert invoices.saved[-1][1]["line_items"][-1]["description"] == "Speaker rental"
    assert "calendar conflict" in result["confirmation"].lower()


def test_dual_contact_asks_for_client_clarification_without_mutating(tmp_path: Path) -> None:
    calendar = FakeCalendarRouter()
    invoices = FakeInvoiceStore()

    result = capture_gig(
        "Draper asked me to do Wedding ceremony on July 12",
        contacts_registry=_registry(tmp_path),
        calendar_router=calendar,
        invoice_store=invoices,
        client_models=_client_models(),
        now=datetime(2026, 7, 5, 12, 0),
    )

    assert result["status"] == "needs_client_clarify"
    assert result["contact"]["id"] == "draper-carter"
    assert result["client_options"] == ("live-arts-md", "st-annes")
    assert calendar.added == []
    assert invoices.saved == []


def test_message_rate_is_ignored_when_client_model_rate_differs(tmp_path: Path) -> None:
    calendar = FakeCalendarRouter()
    invoices = FakeInvoiceStore()

    result = capture_gig(
        "Dane asked me to do Tech rehearsal on 2026-07-12 for $999",
        contacts_registry=_registry(tmp_path),
        calendar_router=calendar,
        invoice_store=invoices,
        client_models=_client_models(),
        now=datetime(2026, 7, 5, 12, 0),
    )

    line_item = invoices.saved[-1][1]["line_items"][-1]
    assert result["status"] == "captured"
    assert result["rate"]["amount"] == 500
    assert result["rate"]["ignored_message_amount"] == 999
    assert line_item["amount"] == 500
    assert line_item["amount"] != 999
