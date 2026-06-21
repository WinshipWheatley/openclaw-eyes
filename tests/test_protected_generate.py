from __future__ import annotations

from protected_generate import _fallback_grounded_answer


def test_finance_intent_grounded_answer():
    packet = {
        "facts": [
            {
                "topic": "calendar_day",
                "label": "gig count",
                "value": "Two gigs today, neither about invoices.",
            },
            {
                "topic": "finance_candidate_count",
                "label": "candidate noise",
                "value": "A non-authoritative candidate says three invoices might exist.",
            },
            {
                "topic": "finance_invoice_reconciliation",
                "label": "Capital Hilton",
                "value": "Capital Hilton receivable is $2,000 and marked payment received.",
            },
            {
                "topic": "invoice_status",
                "label": "AR status",
                "value": "No unpaid invoices are ready for send or ledger mutation.",
            },
        ]
    }

    answer = _fallback_grounded_answer("what's owed on invoices?", packet)

    assert "Capital Hilton receivable is $2,000" in answer
    assert "No unpaid invoices are ready" in answer
    assert "Two gigs today" not in answer
    assert "non-authoritative candidate" not in answer


def test_schedule_intent_still_uses_calendar_only():
    packet = {
        "facts": [
            {
                "topic": "finance_invoice_reconciliation",
                "label": "Capital Hilton",
                "value": "Capital Hilton has $400 tied to next Friday gigs.",
            },
            {
                "topic": "calendar_day",
                "label": "today",
                "value": "Two rehearsals and one load-in are on the calendar today.",
            },
        ]
    }

    answer = _fallback_grounded_answer("how many gigs do I have today?", packet)

    assert "Two rehearsals and one load-in" in answer
    assert "Capital Hilton" not in answer
