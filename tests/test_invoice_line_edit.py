from __future__ import annotations

from copy import deepcopy

from invoice_line_edit import apply_invoice_edit


def _invoice_data() -> dict:
    return {
        "invoice_number": "WL-2026-0001",
        "client_name": "Any Client",
        "client_email": "client@example.com",
        "project_desc": "Wedding; June 7 service",
        "service_date": "2026-06-07",
        "issue_date": "2026-07-04",
        "net_terms": "Due on Receipt",
        "deposit_paid": 0,
        "amount_total": 25000,
        "balance_due": 25000,
        "line_items": [
            {"description": "June 7 service", "service_date": "2026-06-07", "amount": 12500},
            {"description": "Wedding", "service_date": "2026-06-14", "amount": 12500},
        ],
    }


def test_add_line_item_updates_total_in_minor_units() -> None:
    edited = apply_invoice_edit(
        _invoice_data(),
        "add Church service (10:00 AM) on 2026-06-21 at $125",
    )

    assert edited["line_items"][-1] == {
        "description": "Church service (10:00 AM)",
        "service_date": "2026-06-21",
        "amount": 12500,
    }
    assert edited["amount_total"] == 37500
    assert edited["balance_due"] == 37500
    assert edited["project_desc"] == "June 7 service; Wedding; Church service (10:00 AM)"
    assert edited["invoice_edit"]["status"] == "applied"
    assert edited["invoice_edit"]["operation"] == "add"


def test_remove_line_by_date_updates_total() -> None:
    edited = apply_invoice_edit(_invoice_data(), "remove the June 7 line")

    assert edited["line_items"] == [
        {"description": "Wedding", "service_date": "2026-06-14", "amount": 12500},
    ]
    assert edited["amount_total"] == 12500
    assert edited["balance_due"] == 12500
    assert edited["invoice_edit"]["operation"] == "remove"


def test_change_amount_updates_minor_units_without_25000_bug() -> None:
    edited = apply_invoice_edit(_invoice_data(), "change the wedding to $150")

    wedding = edited["line_items"][1]
    assert wedding["description"] == "Wedding"
    assert wedding["amount"] == 15000
    assert edited["amount_total"] == 27500
    assert edited["balance_due"] == 27500
    assert edited["invoice_edit"]["operation"] == "change"
    assert edited["amount_total"] != 2750000


def test_unparseable_edit_leaves_invoice_facts_unchanged_with_note() -> None:
    original = _invoice_data()
    edited = apply_invoice_edit(original, "make it more correct")

    assert edited["line_items"] == original["line_items"]
    assert edited["amount_total"] == original["amount_total"]
    assert edited["balance_due"] == original["balance_due"]
    assert edited["invoice_edit"]["status"] == "unparsed"
    assert "couldn't parse" in edited["invoice_edit"]["note"].lower()
    assert original == _invoice_data()


def test_apply_invoice_edit_does_not_mutate_input() -> None:
    original = _invoice_data()
    snapshot = deepcopy(original)

    apply_invoice_edit(original, "add Church service on 2026-06-21 at $125")

    assert original == snapshot
