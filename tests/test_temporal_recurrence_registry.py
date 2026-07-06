from __future__ import annotations

from datetime import date

from temporal_recurrence_registry import (
    ClientRecurrenceRegistry,
    next_expected_invoice,
    paid_up_state,
)


def test_st_annes_monthly_paid_up_decays_at_next_invoice_cycle() -> None:
    assert next_expected_invoice("st_annes", after=date(2026, 6, 15)) == date(2026, 7, 1)

    before_cycle = paid_up_state("st_annes", paid_through=date(2026, 6, 15), now=date(2026, 6, 30))
    assert before_cycle.status == "paid_up_through"
    assert before_cycle.paid_through == date(2026, 6, 15)
    assert before_cycle.next_expected_invoice == date(2026, 7, 1)

    at_cycle = paid_up_state("st_annes", paid_through=date(2026, 6, 15), now=date(2026, 7, 1))
    assert at_cycle.status == "invoice_due"
    assert at_cycle.next_expected_invoice == date(2026, 7, 1)


def test_per_event_clients_do_not_auto_become_due_by_calendar() -> None:
    assert next_expected_invoice("live_arts_md", after=date(2026, 6, 15)) is None
    assert next_expected_invoice("capital_hilton", after=date(2026, 6, 15)) is None

    state = paid_up_state("live_arts_md", paid_through=date(2026, 6, 15), now=date(2026, 9, 1))
    assert state.status == "paid_up_through"
    assert state.next_expected_invoice is None
    assert state.recurrence_cadence == "per_event"


def test_recurrence_registry_is_domain_generic_not_st_annes_specific() -> None:
    registry = ClientRecurrenceRegistry(
        {
            "record_label_alpha": {
                "domain": "record_label",
                "cadence": "monthly",
                "day_of_month": 15,
                "active": True,
            }
        }
    )

    assert registry.next_expected_invoice("record_label_alpha", after=date(2026, 7, 16)) == date(2026, 8, 15)
